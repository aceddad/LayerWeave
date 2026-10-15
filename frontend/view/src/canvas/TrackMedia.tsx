// 轨道共享媒体表面：对象 DOM、文字、标记、连接点仍归 ObjectBlock；这里仅画背景和媒体。
import {createContext, useContext, useEffect, useMemo, useRef} from 'react';
import type {ReactNode, RefObject} from 'react';
import {frameUrl, thumbUrl} from '../api';
import {CAPTURE, params} from '../params';
import {getState, useStore} from '../store';
import type {Layer, Obj} from '../types';
import type {BlockPainter} from '../plugin/host';
import {pluginFailed} from '../plugin/slots';
import {legacyPaintState, loadImage} from './Media';
import {detailAt, paintQueue, TILE_PIXELS, tileKeys} from './mediaQueue';
import type {MediaRect} from './mediaQueue';
import {mediaUrl} from './mediaUrl';
import {drawWaveform, peaksFor, waveformSize} from './Waveform';

export const SHARED_MEDIA = params.get('media') !== 'legacy'; // 研发视觉对照，非持久配置。
export interface MediaSpec {
  o: Obj; layer: Layer; unit: string; project: number; frames: boolean;
  kind: string; rect: MediaRect; last: number | 'end'; painter?: {name: string; painter: BlockPainter} | null;
}
interface Entry {
  spec: MediaSpec; node: HTMLElement; near: boolean; epoch: number; alive: boolean;
  source?: HTMLCanvasElement; keys: string[]; standalone?: HTMLCanvasElement; failure?: string;
  job: object; detail: number; signature: string;
}
interface Tile { canvas: HTMLCanvasElement; members: Set<Entry>; job: object; x: number; y: number; dirty: boolean }
interface PreparedMedia { draw: () => HTMLCanvasElement; failure?: string }
const Context = createContext<TrackSurface | null>(null);
const surfaces = new Set<TrackSurface>();
const colors: Record<string, string> = {image: '--image', video: '--video', audio: '--audio', text: '--text-c'};

function canvas(width: number, height: number) {
  const result = document.createElement('canvas');
  result.width = Math.max(1, Math.round(width)); result.height = Math.max(1, Math.round(height));
  return result;
}
function cover(ctx: CanvasRenderingContext2D, image: HTMLImageElement, x: number, y: number, w: number, h: number) {
  const ir = image.naturalWidth / Math.max(1, image.naturalHeight), cr = w / h;
  let sw = image.naturalWidth, sh = image.naturalHeight, sx = 0, sy = 0;
  if (ir > cr) { sw = sh * cr; sx = (image.naturalWidth - sw) / 2; }
  else { sh = sw / cr; sy = (image.naturalHeight - sh) / 2; }
  ctx.drawImage(image, sx, sy, sw, sh, x, y, w, h);
}

export class TrackSurface {
  private entries = new Set<Entry>();
  private tiles = new Map<string, Tile>();
  private retired: HTMLCanvasElement[] = [];
  private observer: IntersectionObserver | null = null;
  private owners = new Map<Element, Entry>();
  private root: HTMLDivElement | null = null;
  private zoom = getState().settledZoom;
  private scale = Math.max(.01, this.zoom) * (globalThis.devicePixelRatio || 1);
  private alive = true;
  private unsubscribe = () => {};
  private backgrounds: Record<string, string> = {};
  errors = new Map<Entry, string>();
  constructor(private width: number, private height: number) {}
  attach(root: HTMLDivElement) {
    this.root = root; this.alive = true; surfaces.add(this);
    const style = getComputedStyle(root);
    for (const [kind, variable] of Object.entries(colors)) this.backgrounds[kind] = style.getPropertyValue(variable).trim();
    this.backgrounds.other = style.getPropertyValue('--other').trim() || '#6b7385';
    if (!CAPTURE) this.observer = new IntersectionObserver((changes) => {
      for (const change of changes) {
        const entry = this.owners.get(change.target);
        if (entry && change.isIntersecting) {
          entry.near = true; this.observer!.unobserve(change.target); this.prepare(entry);
        }
      }
    }, {rootMargin: '600px'});
    this.unsubscribe = useStore.subscribe((s, prev) => {
      if (s.settledZoom === prev.settledZoom) return;
      this.zoom = s.settledZoom;
      const scale = Math.max(.01, this.zoom) * (globalThis.devicePixelRatio || 1);
      if (scale !== this.scale) {
        this.scale = scale;
        for (const tile of this.tiles.values()) { paintQueue.cancel(tile.job); this.retired.push(tile.canvas); }
        this.tiles.clear();
        for (const entry of this.entries) { entry.keys = []; if (entry.source) this.place(entry); }
      }
      for (const entry of this.entries) this.prepare(entry);
      this.clearRetired();
    });
    // 子组件的 effect 可能早于父 effect；登记可以先于 attach。
    for (const entry of this.entries) this.observe(entry);
  }
  dispose() {
    this.alive = false; this.unsubscribe(); this.observer?.disconnect(); surfaces.delete(this);
    for (const entry of [...this.entries]) this.remove(entry);
    for (const tile of this.tiles.values()) { paintQueue.cancel(tile.job); tile.canvas.remove(); }
    for (const element of this.retired) element.remove();
    this.tiles.clear(); this.retired = []; this.root = null;
  }
  add(spec: MediaSpec, node: HTMLElement) {
    // 普通波形原本就立即加载、缩小时照画；插件接管音频则继续使用插件的 near/LOD。
    const entry: Entry = {spec, node, near: CAPTURE || (spec.kind === 'audio' && !spec.painter),
      epoch: 0, alive: true, keys: [], job: {}, detail: -1, signature: ''};
    this.entries.add(entry); this.owners.set(node, entry);
    node.dataset.mediaState = 'idle';
    if (spec.painter) node.dataset.mediaPlugin = spec.painter.name;
    if (this.root) this.observe(entry);
    return () => this.remove(entry);
  }
  private observe(entry: Entry) {
    if (entry.near) this.prepare(entry);
    else { this.observer?.observe(entry.node); this.prepare(entry); }
  }
  private remove(entry: Entry) {
    entry.alive = false; entry.epoch++;
    paintQueue.cancel(entry.job); this.observer?.unobserve(entry.node);
    this.entries.delete(entry); this.owners.delete(entry.node); this.errors.delete(entry);
    this.erase(entry);
    delete entry.node.dataset.mediaState; delete entry.node.dataset.mediaPlugin; delete entry.node.dataset.atlas;
  }
  private erase(entry: Entry) {
    entry.source = undefined; entry.standalone?.remove(); entry.standalone = undefined;
    for (const key of entry.keys) { const tile = this.tiles.get(key); if (tile) { tile.members.delete(entry); this.redraw(tile); } }
    entry.keys = []; delete entry.node.dataset.atlas;
  }
  private prepare(entry: Entry) {
    paintQueue.cancel(entry.job);
    entry.job = {};
    const owner = entry.job;
    const epoch = ++entry.epoch;
    paintQueue.schedule(owner, () => {
      if (!entry.alive || !this.alive || epoch !== entry.epoch) return;
      const {spec} = entry, detail = detailAt(this.zoom, spec.rect.w, spec.rect.h, CAPTURE);
      const audio = spec.kind === 'audio' && !spec.painter;
      if (!detail && !audio) { entry.detail = detail; entry.signature = ''; this.erase(entry); entry.node.dataset.mediaState = 'idle'; return; }
      if (!entry.near) return; // 沿用已有的 near 下载规则，DOM 始终保留。
      const density = Math.max(0.01, this.scale);
      const ratio = Math.min(density, 2048 / Math.max(spec.rect.w, spec.rect.h));
      const size = audio ? waveformSize(Math.max(1, spec.rect.w - 2), Math.max(1, spec.rect.h - 2), devicePixelRatio) : null;
      const w = size?.width ?? Math.max(1, Math.round((spec.rect.w - 2) * ratio)), h = size?.height ?? Math.max(1, Math.round((spec.rect.h - 2) * ratio));
      const signature = (audio ? 'wave' : detail) + ':' + w + ':' + h;
      if (entry.signature === signature && entry.source) return;
      entry.node.dataset.mediaState = 'pending';
      this.errors.delete(entry);
      const current = () => this.alive && entry.alive && epoch === entry.epoch;
      const fail = (error: unknown) => {
        if (!current()) return;
        this.erase(entry); entry.node.dataset.mediaState = 'failed'; this.errors.set(entry, String(error));
        if (spec.painter) pluginFailed(spec.painter.name, error);
      };
      const work = this.paint(spec, detail, w, h).then((prepared) => {
        if (!current()) return;
        // 准备完成以后，贴图也回到同一预算队列；异步插件不会取得共享 ctx。
        paintQueue.schedule(owner, () => {
          if (!current()) return;
          try {
          const inner = prepared.draw();
          // 波形沿用原来的、不乘 zoom 的位图采样，含独立宽高上限；分块只负责摆放。
          const output = canvas(audio ? spec.rect.w * w / Math.max(1, spec.rect.w - 2) : spec.rect.w * ratio,
            audio ? spec.rect.h * h / Math.max(1, spec.rect.h - 2) : spec.rect.h * ratio), ctx = output.getContext('2d')!;
          ctx.scale(output.width / spec.rect.w, output.height / spec.rect.h);
          ctx.fillStyle = this.backgrounds[spec.kind] || this.backgrounds.other;
          ctx.beginPath(); ctx.roundRect(0, 0, spec.rect.w, spec.rect.h, 4); ctx.fill();
          ctx.save(); ctx.beginPath(); ctx.roundRect(1, 1, Math.max(1, spec.rect.w - 2), Math.max(1, spec.rect.h - 2), 3); ctx.clip();
          ctx.globalAlpha = spec.painter ? 1 : spec.kind === 'video' && spec.frames && spec.rect.w >= 150 ? .9 : .85;
          ctx.drawImage(inner, 1, 1, Math.max(1, spec.rect.w - 2), Math.max(1, spec.rect.h - 2)); ctx.restore();
          entry.source = output; entry.signature = signature; entry.detail = detail;
          entry.failure = prepared.failure;
          if (prepared.failure) this.errors.set(entry, prepared.failure);
          this.place(entry);
          } catch (error) { fail(error); }
        });
      }).catch(fail);
      paintQueue.track(work, owner);
    });
  }
  private async paint(spec: MediaSpec, detail: number, w: number, h: number): Promise<PreparedMedia> {
    const out = canvas(w, h), ctx = out.getContext('2d')!;
    if (spec.painter) {
      await spec.painter.painter.draw(ctx, spec.o, {width: w, height: h, unit: spec.unit, layer: spec.layer});
      return {draw: () => out};
    }
    if (spec.kind === 'audio') {
      const values = await peaksFor(mediaUrl(spec.o.media!.url!, spec.o.media?.source));
      return {failure: values ? undefined : '波形无法解码：对象 #' + spec.o.id,
        draw: () => { drawWaveform(ctx, values, w, h, devicePixelRatio); return out; }};
    }
    const ends = spec.kind === 'video' && spec.frames && spec.rect.w >= 150;
    const sources = spec.kind === 'video'
      ? (ends ? [frameUrl(spec.project, spec.o.id, .05), frameUrl(spec.project, spec.o.id, spec.last)] : [frameUrl(spec.project, spec.o.id, .1)])
      : [spec.frames ? thumbUrl(spec.project, spec.o.id, detail === 1 ? 160 : 320) : spec.o.media!.url!];
    const images = await Promise.all(sources.map((url) => loadImage(mediaUrl(url, spec.o.media?.source))));
    if (images.some((image) => !image)) throw new Error('媒体无法解码：对象 #' + spec.o.id);
    // 只把已解码资源准备好；实际画图和贴图一起在 owner 的预算任务中做。
    return {draw: () => {
      if (ends) { const sw = Math.min(w / 2, 64 * w / Math.max(1, spec.rect.w - 2)); cover(ctx, images[0]!, 0, 0, sw, h); cover(ctx, images[1]!, w - sw, 0, sw, h); }
      else cover(ctx, images[0]!, 0, 0, w, h);
      return out;
    }};
  }
  private place(entry: Entry) {
    if (!this.root || !entry.source) return;
    const r = entry.spec.rect, size = TILE_PIXELS / this.scale;
    // 极长的单个对象仍用一块有尺寸上限的表面，避免按空时间跨度分配无数纹理。
    const count = (Math.ceil((r.x + r.w) / size) - Math.floor(r.x / size)) * (Math.ceil((r.y + r.h) / size) - Math.floor(r.y / size));
    if (count > 16) {
      for (const key of entry.keys) { const tile = this.tiles.get(key); if (tile) { tile.members.delete(entry); this.redraw(tile); } }
      entry.keys = [];
      entry.standalone?.remove(); entry.standalone = entry.source;
      entry.source.className = 'media-tile';
      entry.source.style.cssText = 'left:' + r.x + 'px;top:' + r.y + 'px;width:' + r.w + 'px;height:' + r.h + 'px';
      entry.source.dataset.mediaTile = 'ready'; this.root.append(entry.source);
      entry.node.dataset.atlas = 'ready'; entry.node.dataset.mediaState = entry.failure ? 'failed' : 'ready';
      this.clearRetired(); return;
    }
    entry.standalone?.remove(); entry.standalone = undefined;
    const keys = tileKeys(r, this.scale);
    for (const key of entry.keys) if (!keys.includes(key)) {
      const old = this.tiles.get(key); if (old) { old.members.delete(entry); this.redraw(old); }
    }
    entry.keys = keys;
    for (const key of keys) {
      let tile = this.tiles.get(key);
      if (!tile) {
        const [x, y] = key.split(':').map(Number), el = canvas(Math.min(TILE_PIXELS, Math.ceil((this.width - x * size) * this.scale)), Math.min(TILE_PIXELS, Math.ceil((this.height - y * size) * this.scale)));
        el.className = 'media-tile';
        el.style.cssText = 'left:' + (x * size) + 'px;top:' + (y * size) + 'px;width:' + (el.width / this.scale) + 'px;height:' + (el.height / this.scale) + 'px';
        tile = {canvas: el, members: new Set(), job: {}, x: x * size, y: y * size, dirty: false};
        this.tiles.set(key, tile);
      }
      tile.members.add(entry); this.redraw(tile);
    }
  }
  private redraw(tile: Tile) {
    tile.dirty = true;
    paintQueue.schedule(tile.job, () => {
      if (!this.root || !this.alive) return;
      const ctx = tile.canvas.getContext('2d')!;
      ctx.clearRect(0, 0, tile.canvas.width, tile.canvas.height);
      ctx.save(); ctx.scale(this.scale, this.scale); ctx.translate(-tile.x, -tile.y);
      for (const entry of tile.members) if (entry.alive && entry.source) {
        const r = entry.spec.rect;
        ctx.drawImage(entry.source, r.x, r.y, r.w, r.h);
      }
      ctx.restore(); tile.dirty = false;
      tile.canvas.dataset.mediaTile = 'ready';
      if (!tile.canvas.isConnected) this.root.append(tile.canvas);
      for (const entry of tile.members) if (entry.keys.every((key) => !this.tiles.get(key)?.dirty)) {
        entry.node.dataset.atlas = 'ready'; entry.node.dataset.mediaState = entry.failure ? 'failed' : 'ready';
      }
      if (!tile.members.size) tile.canvas.remove();
      this.clearRetired();
    });
  }
  private clearRetired() {
    if ([...this.tiles.values()].some((tile) => tile.dirty)) return;
    for (const el of this.retired) el.remove();
    this.retired = [];
  }
  status() {
    let ready = 0, failed = 0, pending = 0;
    for (const entry of this.entries) {
      if (entry.node.dataset.mediaState === 'ready') ready++;
      else if (entry.node.dataset.mediaState === 'failed') failed++;
      else if (entry.node.dataset.mediaState === 'pending') pending++;
    }
    return {ready, failed, pending, errors: [...this.errors.values()]};
  }
}

export function mediaPaintState() {
  const total = {ready: 0, failed: paintQueue.errors.length, pending: paintQueue.pending, errors: [...paintQueue.errors]};
  for (const surface of surfaces) { const s = surface.status(); total.ready += s.ready; total.failed += s.failed; total.errors.push(...s.errors); }
  for (const state of legacyPaintState()) {
    if (state.state === 'ready') total.ready++;
    if (state.state === 'failed') { total.failed++; if (state.error) total.errors.push(state.error); }
  }
  return total;
}
export function useSharedMedia(spec: MediaSpec | null, node: RefObject<HTMLDivElement | null>) {
  const surface = useContext(Context);
  useEffect(() => {
    if (!SHARED_MEDIA || !surface || !spec || !node.current) return;
    return surface.add(spec, node.current);
  }, [surface, spec, node]);
}
export function MediaTrack({width, height, className, children}: {width: number; height: number; className: string; children: ReactNode}) {
  const root = useRef<HTMLDivElement>(null);
  const surface = useMemo(() => new TrackSurface(width, height), [width, height]);
  useEffect(() => { if (SHARED_MEDIA && root.current) { surface.attach(root.current); return () => surface.dispose(); } }, [surface]);
  return <Context.Provider value={surface}><div className={className} style={{height}}>
    {SHARED_MEDIA && <div className="media-atlas" ref={root} aria-hidden="true" />}
    {children}
  </div></Context.Provider>;
}
