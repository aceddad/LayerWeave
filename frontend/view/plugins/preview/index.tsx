// 预览（视图自带的插件）：把一个文件里的帧罗列出来——视频、会动的 SVG、GIF / 动态 WebP / APNG。
// 默认逐帧缩略图；开始时刻、间隔（逐帧 / 每 N 帧 / 每 N 秒）、帧率可以改；一页一屏，截图拍一张就是一页，AI 用它自查一段。
// 地址参数：object=对象编号、from=开始的秒、step=1f / 3f / 0.5s、fps=、per=、page=（截图 --param object=812 --param step=1f）。
// 只看一个文件里的帧，不把几层叠起来合成（那是渲染）。编译成 view/plugins/preview/plugin.js，是视图的内置插件
import type {PluginHost, ViewPlugin} from '../../src/plugin/host';
import type {ObjWithLayer} from '../../src/model/model';
import {maybeAnimated, parseStep, shots, stepText, svgAnimated, svgDuration} from './frames';
import type {Shot, Step} from './frames';
import css from './preview.css?raw';

let host: PluginHost;
let h: PluginHost['React']['createElement'];
let Fragment: PluginHost['React']['Fragment'];

const SIZES = [24, 48, 96];
const STEPS = ['1f', '2f', '5f', '0.5s', '1s'];
const query = new URLSearchParams(location.search);

type Source =
  | {kind: 'video'; duration: number; fps: number | null; aspect: number}
  | {kind: 'svg'; duration: number; text: string; still: boolean; aspect: number}
  | {kind: 'frames'; duration: number; starts: number[]; decoder: any; aspect: number}
  | {kind: 'still'; message: string}
  | {kind: 'error'; message: string};

const nameOf = (o: ObjWithLayer) => o.name || (o.media?.source || '').split(/[\\/]/).pop() || `对象 ${o.id}`;
const urlOf = (o: ObjWithLayer) => host.util.mediaUrl(o.media!.url!, o.media?.source);
const fileOf = (o: ObjWithLayer) => o.media?.source || o.media?.url || '';

function candidates(objects: ObjWithLayer[], picked: number[]): ObjWithLayer[] {
  const {kindOf} = host.util, only = picked.length ? new Set(picked) : null;
  return objects.filter((o) => o.media?.url && o.media.available !== false && (!only || only.has(o.layer.id)) &&
    (kindOf(o) === 'video' || (kindOf(o) === 'image' && maybeAnimated(fileOf(o)))))
    .sort((a, b) => Number(kindOf(a) !== 'video') - Number(kindOf(b) !== 'video'));   // 视频在前
}

const timeout = <T,>(p: Promise<T>, ms: number, what: string) =>
  Promise.race([p, new Promise<T>((_, reject) => setTimeout(() => reject(new Error(what + '超时')), ms))]);
const once = (el: EventTarget, ok: string) => new Promise<void>((resolve, reject) => {
  const done = () => { el.removeEventListener(ok, done); el.removeEventListener('error', fail); resolve(); };
  const fail = () => { el.removeEventListener(ok, done); el.removeEventListener('error', fail); reject(new Error('文件读不出来')); };
  el.addEventListener(ok, done); el.addEventListener('error', fail);
});

// 帧率：播几帧，看 requestVideoFrameCallback 给的 mediaTime 相差多少；量不到返回 null
async function measureFps(video: HTMLVideoElement): Promise<number | null> {
  if (!('requestVideoFrameCallback' in video)) return null;
  const times: number[] = [];
  try {
    await timeout(new Promise<void>((resolve) => {
      const tick = (_: number, meta: {mediaTime: number}) => {
        times.push(meta.mediaTime);
        if (times.length >= 6) resolve(); else video.requestVideoFrameCallback(tick);
      };
      video.requestVideoFrameCallback(tick);
      video.play().catch(() => resolve());
    }), 1500, '量帧率');
  } catch { /* 量不到就算了 */ }
  video.pause();
  const gaps = times.slice(1).map((t, i) => t - times[i]).filter((d) => d > 0.004 && d < 0.2).sort((a, b) => a - b);
  return gaps.length ? Math.round(1 / gaps[gaps.length >> 1]) : null;
}

async function loadSource(o: ObjWithLayer, video: HTMLVideoElement): Promise<Source> {
  const url = urlOf(o), {kindOf} = host.util;
  if (kindOf(o) === 'video') {
    video.muted = true; video.preload = 'auto'; video.src = url;
    await timeout(once(video, 'loadeddata'), 20000, '读视频');
    const fps = await measureFps(video);
    return {kind: 'video', duration: video.duration, fps, aspect: video.videoWidth / Math.max(1, video.videoHeight)};
  }
  const response = await fetch(url);
  if (!response.ok) throw new Error('文件读不出来');
  if (/\.svg$/i.test(fileOf(o).split(/[?#]/)[0]) || response.headers.get('content-type')?.includes('svg')) {
    const text = await response.text(), still = !svgAnimated(text);
    const box = /viewBox\s*=\s*["']\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)/i.exec(text);
    return {kind: 'svg', text, still, duration: svgDuration(text, Math.max(0.5, o.end - o.begin) || 4),
            aspect: box ? Number(box[1]) / Math.max(1, Number(box[2])) : 1};
  }
  const Decoder = (globalThis as any).ImageDecoder;
  if (!Decoder) return {kind: 'error', message: '这个浏览器不支持逐帧读图（没有 ImageDecoder）'};
  const type = response.headers.get('content-type') || ({gif: 'image/gif', webp: 'image/webp', png: 'image/png', apng: 'image/apng'} as Record<string, string>)[fileOf(o).split('.').pop()!.toLowerCase()] || 'image/gif';
  const decoder = new Decoder({data: await response.arrayBuffer(), type});
  await decoder.tracks.ready;
  const count = Math.min(5000, decoder.tracks.selectedTrack?.frameCount ?? 1);
  if (count <= 1) { decoder.close(); return {kind: 'still', message: '这张图不会动'}; }
  const starts: number[] = [];
  let at = 0, aspect = 1;
  for (let i = 0; i < count; i++) {
    const {image} = await decoder.decode({frameIndex: i});
    starts.push(+at.toFixed(6));
    at += (image.duration ?? 100000) / 1e6;
    if (i === 0) aspect = image.displayWidth / Math.max(1, image.displayHeight);
    image.close();
  }
  return {kind: 'frames', duration: at, starts, decoder, aspect};
}

// SVG 的副本：去掉脚本和 on* 事件属性
function cleanSvg(text: string): string {
  const doc = new DOMParser().parseFromString(text, 'image/svg+xml');
  doc.querySelectorAll('script').forEach((el) => el.remove());
  doc.querySelectorAll('*').forEach((el) => {
    for (const a of [...el.attributes]) if (/^on/i.test(a.name) || /^\s*javascript:/i.test(a.value)) el.removeAttribute(a.name);
  });
  const svg = doc.documentElement;
  svg.setAttribute('width', '100%'); svg.setAttribute('height', '100%');
  return new XMLSerializer().serializeToString(svg);
}

// 一个副本停在 t 秒：SMIL 用 pauseAnimations + setCurrentTime，CSS 动画逐个设 currentTime
function freeze(holder: HTMLElement, t: number) {
  const svg = holder.querySelector('svg') as SVGSVGElement | null;
  svg?.pauseAnimations?.();
  svg?.setCurrentTime?.(t);
  for (const a of holder.getAnimations({subtree: true})) { a.pause(); a.currentTime = t * 1000; }
}

function contain(ctx: CanvasRenderingContext2D, source: CanvasImageSource, sw: number, sh: number) {
  const {width, height} = ctx.canvas, k = Math.min(width / sw, height / sh), w = sw * k, hh = sh * k;
  ctx.clearRect(0, 0, width, height);
  ctx.drawImage(source, (width - w) / 2, (height - hh) / 2, w, hh);
}

function PreviewPage() {
  const {React} = host, {model, selected, picked} = host.useView();
  const list = React.useMemo(() => (model ? candidates(model.allObjects(), picked) : []), [model, picked]);
  const [objectId, setObjectId] = React.useState<number | null>(() => host.numParam('object') ?? null);
  const [from, setFrom] = React.useState(() => host.numParam('from') ?? 0);
  const [step, setStep] = React.useState<Step>(() => parseStep(query.get('step')) ?? {unit: 'f', n: 1});
  const [fps, setFps] = React.useState<number | null>(() => host.numParam('fps'));
  const [per, setPer] = React.useState(() => host.numParam('per') ?? 48);
  const [page, setPage] = React.useState(() => host.numParam('page') ?? 1);
  const [source, setSource] = React.useState<Source | null>(null);
  const [done, setDone] = React.useState(0);
  const video = React.useRef<HTMLVideoElement | null>(null);
  const cells = React.useRef<(HTMLCanvasElement | HTMLDivElement | null)[]>([]);
  const o = list.find((x) => x.id === objectId) ?? list.find((x) => x.id === selected) ?? list[0] ?? null;

  // 换了对象：读文件、量帧率、数帧
  React.useEffect(() => {
    if (!model) return;
    if (!o) { host.markReady(); return; }
    let alive = true;
    setSource(null); setDone(0);
    const el = video.current ?? (video.current = document.createElement('video'));
    loadSource(o, el).then((s) => { if (alive) setSource(s); })
      .catch((error) => { if (alive) setSource({kind: 'error', message: (error as Error).message}); });
    return () => { alive = false; };
  }, [model != null, o?.id]);

  const rate = fps ?? (source?.kind === 'video' ? source.fps : null) ?? 24;
  const all: Shot[] = React.useMemo(() => {
    if (!source || source.kind === 'still' || source.kind === 'error') return [];
    if (source.kind === 'svg' && source.still) return [];
    return shots({duration: source.duration, from, step, fps: rate, starts: source.kind === 'frames' ? source.starts : undefined});
  }, [source, from, step, rate]);
  const shown = host.util.pageSlice(all, page, per);

  // 把这一页的帧一张张画出来；参数一变，旧的这一轮作废
  React.useEffect(() => {
    if (!source) return;
    if (!shown.items.length) { host.markReady(); return; }
    let alive = true;
    setDone(0);
    (async () => {
      for (let i = 0; i < shown.items.length && alive; i++) {
        const shot = shown.items[i], cell = cells.current[i];
        if (!cell) continue;
        try {
          if (source.kind === 'video') {
            const v = video.current!;
            v.currentTime = Math.min(shot.t, Math.max(0, source.duration - 0.001));
            await timeout(once(v, 'seeked'), 8000, '跳到这一帧');
            if (!alive) break;
            contain((cell as HTMLCanvasElement).getContext('2d')!, v, v.videoWidth, v.videoHeight);
            cell.dataset.t = String(v.currentTime);
          } else if (source.kind === 'svg') {
            cell.innerHTML = cleanSvg(source.text);
            freeze(cell as HTMLDivElement, shot.t);
          } else if (source.kind === 'frames') {
            const {image} = await source.decoder.decode({frameIndex: shot.frame});
            if (alive) contain((cell as HTMLCanvasElement).getContext('2d')!, image, image.displayWidth, image.displayHeight);
            image.close();
          }
          cell.dataset.state = 'ready';
        } catch (error) {
          cell.dataset.state = 'failed';
          cell.title = (error as Error).message;
        }
        if (alive) setDone(i + 1);
      }
      if (alive) host.markReady();
    })();
    return () => { alive = false; };
  }, [source, shown.page, per, all]);

  if (!model) return null;
  const {fmt} = host.util, {Pager} = host.components;
  const aspect = source && 'aspect' in source && source.aspect > 0 ? source.aspect : 16 / 9;
  const status = !o ? (picked.length ? '勾选的层里没有视频或会动的图' : '项目里没有视频或会动的图')
    : !source ? '正在读文件……'
    : source.kind === 'error' || source.kind === 'still' ? source.message
    : source.kind === 'svg' && source.still ? '这张 SVG 不会动'
    : done < shown.items.length ? `正在取帧 ${done} / ${shown.items.length}` : '';
  return (
    <main className="preview">
      <aside className="pv-list">
        <div className="hint">{picked.length ? '勾选的层里' : '全部'} {list.length} 个</div>
        {list.map((x) => <div key={x.id} className={`pv-item${x.id === o?.id ? ' on' : ''}`} title={`#${x.id} ${fileOf(x)}`}
                               onClick={() => { setObjectId(x.id); setPage(1); }}>{nameOf(x)}<small>{x.layer.name}</small></div>)}
      </aside>
      <section className="pv-main">
        <div className="pv-bar">
          <strong>{o ? nameOf(o) : '预览'}</strong>
          <label>开始 <input type="number" min={0} step={0.1} value={from} onChange={(e) => { setFrom(Math.max(0, Number(e.target.value) || 0)); setPage(1); }} /> 秒</label>
          <label>间隔 <select value={stepText(step)} onChange={(e) => { setStep(parseStep(e.target.value)!); setPage(1); }}>
            {[...new Set([...STEPS, stepText(step)])].map((s) => <option key={s} value={s}>{s === '1f' ? '逐帧' : s.endsWith('f') ? `每 ${parseInt(s)} 帧` : `每 ${parseFloat(s)} 秒`}</option>)}
          </select></label>
          {source?.kind !== 'frames' && <label title="视频按实际的帧率（播几帧量出来）；量不到时用 24">帧率 <input type="number" min={1} max={240} value={rate}
            onChange={(e) => { setFps(Math.max(1, Number(e.target.value) || 24)); setPage(1); }} /></label>}
          {source && 'duration' in source && <span className="hint">共 {fmt(source.duration, '秒')}</span>}
          <span className="spacer" />
          <Pager total={all.length} page={shown.page} per={per} onPage={setPage} sizes={SIZES} onPer={(n) => { setPer(n); setPage(1); }} />
        </div>
        {status && <p className="hint pv-status">{status}</p>}
        <div className="pv-grid">
          {shown.items.map((shot, i) => (
            <figure key={`${o?.id}:${shot.t}:${shot.frame}`} onClick={() => o && host.selectObject(o.id)}>
              {source?.kind === 'svg'
                ? <div className="pv-cell" ref={(el) => { cells.current[i] = el; }} style={{aspectRatio: String(aspect)}} />
                : <canvas className="pv-cell" ref={(el) => { cells.current[i] = el; }} width={Math.round(320 * Math.min(2, devicePixelRatio))}
                          height={Math.round(320 * Math.min(2, devicePixelRatio) / aspect)} style={{aspectRatio: String(aspect)}} />}
              <figcaption>{fmt(shot.t, '秒')} · 第 {shot.frame} 帧</figcaption>
            </figure>
          ))}
        </div>
      </section>
    </main>
  );
}

export default function preview(given: PluginHost): ViewPlugin {
  host = given;
  h = given.React.createElement;
  Fragment = given.React.Fragment;
  given.addStyle(css);
  return {
    name: 'preview', label: '预览', title: '把视频、会动的 SVG、GIF 的帧罗列出来：默认逐帧，可以改开始时刻和间隔；一页一屏',
    handles: ['video', 'image'], page: PreviewPage,
  };
}
