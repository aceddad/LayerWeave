// 预览插件的纯计算：间隔怎么写、一页取哪些时刻、某一时刻是 GIF 的第几帧。单独放着好测试

export interface Step { unit: 'f' | 's'; n: number }   // 每 n 帧 / 每 n 秒

// "1f" 逐帧、"3f" 每 3 帧、"0.5s" 每半秒；写错了返回 null
export function parseStep(text: string | null | undefined): Step | null {
  const m = /^\s*(\d+(?:\.\d+)?)\s*([fs])\s*$/i.exec(text ?? '');
  if (!m) return null;
  const n = Number(m[1]), unit = m[2].toLowerCase() as Step['unit'];
  if (!(n > 0) || (unit === 'f' && !Number.isInteger(n))) return null;
  return {unit, n};
}
export const stepText = (s: Step) => `${s.n}${s.unit}`;

// 按秒取的时刻：从 from 起每 dt 秒一张，到 duration 为止（含两头；最后一张不超过 duration）
export function sampleTimes(duration: number, from: number, dt: number, limit = 100000): number[] {
  if (!(duration > 0) || !(dt > 0)) return [];
  const start = Math.min(Math.max(0, from), duration), out: number[] = [];
  for (let i = 0; out.length < limit; i++) {
    const t = +(start + i * dt).toFixed(6);
    if (t > duration + 1e-9) break;
    out.push(t);
  }
  return out;
}

// GIF 一类按帧存的：starts 是每一帧开始的时刻（秒，递增）；t 落在哪一帧
export function frameAt(starts: number[], t: number): number {
  let lo = 0, hi = starts.length - 1;
  if (hi < 0) return -1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (starts[mid] <= t + 1e-9) lo = mid; else hi = mid - 1;
  }
  return lo;
}

// 一张格子：时刻（秒）和帧号（按帧存的文件是真实帧号；视频、SVG 按帧率算）
export interface Shot { t: number; frame: number }

// 这一页之前的全部格子：按帧存的、间隔按帧时直接数帧；否则按时刻取，再换算帧号
export function shots(opts: {duration: number; from: number; step: Step; fps: number; starts?: number[]}): Shot[] {
  const {duration, from, step, fps, starts} = opts;
  if (starts?.length) {
    if (step.unit === 'f') {
      const out: Shot[] = [];
      for (let i = Math.max(0, frameAt(starts, from)); i < starts.length; i += step.n) out.push({t: starts[i], frame: i});
      return out;
    }
    return sampleTimes(duration, from, step.n).map((t) => ({t, frame: frameAt(starts, t)}));
  }
  const dt = step.unit === 'f' ? step.n / Math.max(1, fps) : step.n;
  return sampleTimes(duration, from, dt).map((t) => ({t, frame: Math.round(t * fps)}));
}

// SVG 会不会动：有 SMIL 动画元素或 CSS 动画
export const svgAnimated = (text: string) => /<(animate|animateTransform|animateMotion|set)\b|@keyframes|animation(-name)?\s*:/i.test(text);

// SVG 动画多长：取 dur / animation-duration 里最长的；都没有时用 fallback
export function svgDuration(text: string, fallback: number): number {
  let best = 0;
  for (const m of text.matchAll(/\bdur\s*=\s*["']\s*([\d.]+)\s*(ms|s)?\s*["']/gi)) best = Math.max(best, Number(m[1]) / (m[2]?.toLowerCase() === 'ms' ? 1000 : 1));
  for (const m of text.matchAll(/animation(?:-duration)?\s*:[^;"'}]*?([\d.]+)(ms|s)\b/gi)) best = Math.max(best, Number(m[1]) / (m[2].toLowerCase() === 'ms' ? 1000 : 1));
  return best > 0 ? best : fallback;
}

// 可能会动的图：按扩展名认（PNG 几乎都是静图，只认写明 .apng 的）
export const maybeAnimated = (name: string) => /\.(svg|gif|webp|apng)$/i.test(name.split(/[?#]/)[0]);
