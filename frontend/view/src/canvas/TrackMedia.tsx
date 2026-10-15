// 轨道共享媒体表面：对象 DOM、文字、标记、连接点仍归 ObjectBlock；这里仅画背景和媒体。
import {createContext, useContext, useEffect, useMemo, useRef} from 'react';
import type {ReactNode, RefObject} from 'react';
import {frameUrl, thumbUrl} from '../api';
import {CAPTURE, params} from '../params';
import {getState, useStore} from '../store';
import type {Layer, Obj} from '../types';
import {acquireImage, legacyPaintState} from './Media';
import {detailAt, paintQueue, TILE_PIXELS, tileKeys} from './mediaQueue';
import type {MediaRect} from './mediaQueue';
import {mediaUrl} from './mediaUrl';
import {drawWaveform, peaksFor, waveformSize} from './Waveform';
import {coverCrop, endCoverage, sourceWidth, videoEnds} from './mediaGeometry';
import type {ImageLease} from './imageCache';

export const SHARED_MEDIA = params.get('media') !== 'legacy'; // 研发视觉对照，非持久配置。
export interface MediaSpec {
  o: Obj; layer: Layer; unit: string; project: number; frames: boolean;
  kind: string; rect: MediaRect; last: number | 'end';
}
interface Entry {
  spec: MediaSpec; node: HTMLElement; near: boolean; epoch: number; alive: boolean;
  source?: HTMLCanvasElement; direct?: DirectImage[]; keys: string[]; standalone?: HTMLElement; failure?: string;
  leases: ImageLease[]; pending: ImageLease[]; retired: ImageLease[];
  job: object; detail: number; signature: string; readyScale?: number; nativeRequest?: object;
}
interface Tile { key: string; canvas: HTMLCanvasElement; members: Set<Entry>; job: object; x: number; y: number; dirty: boolean }
interface DirectImage {image: HTMLImageElement; url: string; identity: string; rect: MediaRect; opacity: number}
interface PreparedMedia { draw?: () => HTMLCanvasElement; direct?: DirectImage[]; failure?: string }
const Context = createContext<TrackSurface | null>(null);
const surfaces = new Set<TrackSurface>();
const colors: Record<string, string> = {image: '--image', video: '--video', audio: '--audio', text: '--text-c'};
const releaseAll = (leases: ImageLease[]) => { for (const lease of leases.splice(0)) lease.release(); };
const isEnds = (entry: Entry) => !!entry.direct && entry.spec.kind === 'video' && entry.spec.frames && entry.spec.rect.w >= 150;

function canvas(width: number, height: number) {
  const result = document.createElement('canvas');
  result.width = Math.max(1, Math.round(width)); result.height = Math.max(1, Math.round(height));
  return result;
}
function cover(ctx: CanvasRenderingContext2D, image: HTMLImageElement, x: number, y: number, w: number, h: number) {
  const crop = coverCrop(image.naturalWidth, image.naturalHeight, w, h);
  ctx.drawImage(image, crop.x, crop.y, crop.w, crop.h, x, y, w, h);
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
        const keepOld = !this.retired.length;
        for (const tile of this.tiles.values()) {
          paintQueue.cancel(tile.job);
          if (keepOld) this.retired.push(tile.canvas); else tile.canvas.remove();
        }
        this.tiles.clear();
        for (const entry of this.entries) { entry.keys = []; entry.readyScale = undefined; }
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
    // 波形原本就立即加载、缩小时照画。
    const entry: Entry = {spec, node, near: CAPTURE || spec.kind === 'audio',
      epoch: 0, alive: true, keys: [], leases: [], pending: [], retired: [], job: {}, detail: -1, signature: ''};
    this.entries.add(entry); this.owners.set(node, entry);
    node.dataset.mediaState = 'idle';
    if (this.root) this.observe(entry);
    return Object.assign(() => this.remove(entry), {update: (next: MediaSpec) => {
      if (entry.spec === next) return;
      entry.spec = next; entry.signature = '';
      entry.near ||= CAPTURE || next.kind === 'audio';
      this.prepare(entry);
    }});
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
    delete entry.node.dataset.mediaState; delete entry.node.dataset.atlas;
    this.clearRetired();
  }
  private erase(entry: Entry) {
    releaseAll(entry.leases); releaseAll(entry.pending); releaseAll(entry.retired);
    entry.source = undefined; entry.direct = undefined; entry.nativeRequest = undefined;
    entry.standalone?.remove(); entry.standalone = undefined;
    for (const key of entry.keys) { const tile = this.tiles.get(key); if (tile) { tile.members.delete(entry); this.redraw(tile); } }
    entry.keys = []; delete entry.node.dataset.atlas;
  }
  private prepare(entry: Entry) {
    paintQueue.cancel(entry.job);
    releaseAll(entry.pending); entry.pending = [];
    entry.job = {};
    const owner = entry.job;
    const epoch = ++entry.epoch;
    paintQueue.schedule(owner, () => {
      if (!entry.alive || !this.alive || epoch !== entry.epoch) return;
      const {spec} = entry, detail = detailAt(this.zoom, spec.rect.w, spec.rect.h, CAPTURE);
      const audio = spec.kind === 'audio';
      if (!detail && !audio) { entry.detail = detail; entry.signature = ''; this.erase(entry); entry.node.dataset.mediaState = 'idle'; this.clearRetired(); return; }
      if (!entry.near) return; // 沿用已有的 near 下载规则，DOM 始终保留。
      const density = Math.max(0.01, this.scale);
      const ratio = Math.min(density, 2048 / Math.max(spec.rect.w, spec.rect.h));
      const size = audio ? waveformSize(Math.max(1, spec.rect.w - 2), Math.max(1, spec.rect.h - 2), devicePixelRatio) : null;
      const w = size?.width ?? Math.max(1, Math.round((spec.rect.w - 2) * ratio)), h = size?.height ?? Math.max(1, Math.round((spec.rect.h - 2) * ratio));
      const direct = spec.kind === 'image' || spec.kind === 'video';
      const signature = direct ? 'direct:' + density + ':' + spec.rect.w + ':' + spec.rect.h : (audio ? 'wave' : detail) + ':' + w + ':' + h;
      if (entry.signature === signature && (entry.source || entry.direct)) { this.place(entry); return; }
      entry.node.dataset.mediaState = 'pending';
      this.errors.delete(entry);
      const current = () => this.alive && entry.alive && epoch === entry.epoch;
      const fail = (error: unknown) => {
        if (!current()) return;
        this.erase(entry); entry.node.dataset.mediaState = 'failed'; this.errors.set(entry, String(error));
        this.clearRetired();
      };
      const pending = entry.pending;
      const acquire = (url: string) => {
        if (!current()) return Promise.resolve(null);
        const lease = acquireImage(url); pending.push(lease); return lease.promise;
      };
      const work = this.paint(spec, detail, w, h, acquire, entry.direct).then((prepared) => {
        if (!current()) return;
        // 准备完成以后，贴图也回到同一预算队列。
        paintQueue.schedule(owner, () => {
          if (!current()) return;
          try {
          if (prepared.direct) {
            const urls = new Set(prepared.direct.map((part) => part.url));
            entry.retired.push(...entry.leases); entry.leases = pending.filter((lease) => urls.has(lease.url));
            for (const lease of pending) if (!urls.has(lease.url)) lease.release();
            entry.pending = [];
            entry.direct = prepared.direct; entry.source = undefined;
            entry.signature = signature; entry.detail = detail; entry.failure = undefined;
            this.place(entry); return;
          }
          const inner = prepared.draw!();
          // 波形沿用原来的、不乘 zoom 的位图采样，含独立宽高上限；分块只负责摆放。
          const output = canvas(audio ? spec.rect.w * w / Math.max(1, spec.rect.w - 2) : spec.rect.w * ratio,
            audio ? spec.rect.h * h / Math.max(1, spec.rect.h - 2) : spec.rect.h * ratio), ctx = output.getContext('2d')!;
          ctx.scale(output.width / spec.rect.w, output.height / spec.rect.h);
          ctx.fillStyle = this.backgrounds[spec.kind] || this.backgrounds.other;
          ctx.beginPath(); ctx.roundRect(0, 0, spec.rect.w, spec.rect.h, 4); ctx.fill();
          ctx.save(); ctx.beginPath(); ctx.roundRect(1, 1, Math.max(1, spec.rect.w - 2), Math.max(1, spec.rect.h - 2), 3); ctx.clip();
          ctx.globalAlpha = spec.kind === 'video' && spec.frames && spec.rect.w >= 150 ? .9 : .85;
          ctx.drawImage(inner, 1, 1, Math.max(1, spec.rect.w - 2), Math.max(1, spec.rect.h - 2)); ctx.restore();
          entry.source = output; entry.signature = signature; entry.detail = detail;
          entry.direct = undefined;
          entry.retired.push(...entry.leases); entry.leases = [];
          entry.failure = prepared.failure;
          if (prepared.failure) this.errors.set(entry, prepared.failure);
          this.place(entry);
          } catch (error) { fail(error); }
        });
      }).catch(fail);
      paintQueue.track(work, owner);
    });
  }
  private async paint(spec: MediaSpec, detail: number, w: number, h: number,
                      acquire: (url: string) => Promise<HTMLImageElement | null>, previous?: DirectImage[]): Promise<PreparedMedia> {
    if (spec.kind === 'image' || spec.kind === 'video') return this.directImages(spec, acquire, previous);
    const out = canvas(w, h), ctx = out.getContext('2d')!;
    if (spec.kind === 'audio') {
      const values = await peaksFor(mediaUrl(spec.o.media!.url!, spec.o.media?.source));
      return {failure: values ? undefined : '波形无法解码：对象 #' + spec.o.id,
        draw: () => { drawWaveform(ctx, values, w, h, devicePixelRatio); return out; }};
    }
    return {draw: () => out};
  }
  private async directImages(spec: MediaSpec, acquire: (url: string) => Promise<HTMLImageElement | null>, previous?: DirectImage[]): Promise<PreparedMedia> {
    const width = Math.max(1, spec.rect.w - 2), height = Math.max(1, spec.rect.h - 2);
    const identity = mediaUrl(spec.o.media!.url!, spec.o.media?.source);
    if (spec.kind === 'video') {
      const ends = spec.frames && spec.rect.w >= 150;
      const rects = ends ? videoEnds(spec.rect.w, spec.rect.h) : [{x: 1, y: 1, w: width, h: height}];
      const urls = (ends ? [frameUrl(spec.project, spec.o.id, .05), frameUrl(spec.project, spec.o.id, spec.last)]
        : [frameUrl(spec.project, spec.o.id, .1)]).map((url) => mediaUrl(url, spec.o.media?.source));
      const images = await Promise.all(urls.map(acquire));
      if (images.some((image) => !image)) throw new Error('媒体无法解码：对象 #' + spec.o.id);
      return {direct: images.map((image, i) => ({image: image!, url: urls[i], identity, rect: rects[i], opacity: ends ? .9 : .85}))};
    }
    const old = previous?.find((part) => part.identity === identity);
    const aspect = old ? old.image.naturalWidth / Math.max(1, old.image.naturalHeight) : 0;
    const scale = this.scale;
    let requested = sourceWidth(width, height, aspect, scale);
    const need = Math.max(width, height * aspect) * scale;
    let url = old && old.image.naturalWidth >= need ? old.url
      : spec.frames ? mediaUrl(thumbUrl(spec.project, spec.o.id, requested), spec.o.media?.source) : identity;
    let image = await acquire(url);
    if (!image) throw new Error('媒体无法解码：对象 #' + spec.o.id);
    // 先按目标宽度取足够的一档，获知源比例后再补 cover 所需高度；不先画一份更小的图。
    if (spec.frames) {
      const wanted = sourceWidth(width, height, image.naturalWidth / Math.max(1, image.naturalHeight), scale);
      if (wanted > requested && image.naturalWidth < wanted) {
        requested = wanted; url = mediaUrl(thumbUrl(spec.project, spec.o.id, requested), spec.o.media?.source);
        image = await acquire(url);
        if (!image) throw new Error('媒体无法解码：对象 #' + spec.o.id);
      }
    }
    return {direct: [{image, url, identity, rect: {x: 1, y: 1, w: width, h: height}, opacity: .85}]};
  }
  private place(entry: Entry) {
    if (!this.root || (!entry.source && !entry.direct)) return;
    const r = entry.spec.rect, size = TILE_PIXELS / this.scale;
    const coverage = isEnds(entry) ? endCoverage(r) : [r];
    // 极长的单个对象仍用一块有尺寸上限的表面，避免按空时间跨度分配无数纹理。
    const count = coverage.reduce((sum, rect) => sum + (Math.ceil((rect.x + rect.w) / size) - Math.floor(rect.x / size))
      * (Math.ceil((rect.y + rect.h) / size) - Math.floor(rect.y / size)), 0);
    if (count > 16 && entry.direct) { this.nativeImage(entry); return; }
    if (count > 16) {
      for (const key of entry.keys) { const tile = this.tiles.get(key); if (tile) { tile.members.delete(entry); this.redraw(tile); } }
      entry.keys = [];
      entry.standalone?.remove(); entry.standalone = entry.source!;
      entry.source!.className = 'media-tile';
      entry.source!.style.cssText = 'left:' + r.x + 'px;top:' + r.y + 'px;width:' + r.w + 'px;height:' + r.h + 'px';
      entry.source!.dataset.mediaTile = 'ready'; this.root.append(entry.source!);
      this.ready(entry, true);
      this.clearRetired(); return;
    }
    entry.nativeRequest = undefined;
    const keys = [...new Set(coverage.flatMap((rect) => tileKeys(rect, this.scale)))];
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
        tile = {key, canvas: el, members: new Set(), job: {}, x: x * size, y: y * size, dirty: false};
        this.tiles.set(key, tile);
      }
      tile.members.add(entry); this.redraw(tile);
    }
  }
  private nativeImage(entry: Entry) {
    const part = entry.direct![0], r = entry.spec.rect, owner = entry.job;
    const style = 'left:' + r.x + 'px;top:' + r.y + 'px;width:' + r.w + 'px;height:' + r.h + 'px;background:' + (this.backgrounds[entry.spec.kind] || this.backgrounds.other);
    const attach = (wrapper: HTMLElement) => {
      for (const key of entry.keys) { const tile = this.tiles.get(key); if (tile) { tile.members.delete(entry); this.redraw(tile); } }
      entry.keys = [];
      if (entry.standalone !== wrapper) entry.standalone?.remove();
      entry.standalone = wrapper; wrapper.style.cssText = style;
      if (!wrapper.isConnected) this.root!.append(wrapper);
      this.ready(entry, true); this.clearRetired();
    };
    if (entry.standalone?.dataset.mediaSource === part.url) { attach(entry.standalone); return; }
    const request = {}; entry.nativeRequest = request;
    const current = () => this.alive && entry.alive && entry.job === owner && entry.nativeRequest === request;
    const wrapper = document.createElement('div'), image = new Image();
    wrapper.className = 'media-native'; wrapper.dataset.objectId = String(entry.spec.o.id); wrapper.dataset.mediaSource = part.url;
    image.decoding = 'async'; image.src = part.url; wrapper.append(image);
    // 新 DOM img 独立于共享解码图；等它就绪以后才换下旧画面并释放旧 lease。
    paintQueue.track(image.decode().then(() => {
      if (current()) paintQueue.schedule(owner, () => { if (current()) attach(wrapper); });
    }, (error) => {
      if (!current()) return;
      this.erase(entry); entry.node.dataset.mediaState = 'failed'; this.errors.set(entry, String(error)); this.clearRetired();
    }), owner);
  }
  private ready(entry: Entry, keepStandalone = false) {
    if (!keepStandalone) { entry.standalone?.remove(); entry.standalone = undefined; }
    entry.readyScale = this.scale;
    entry.node.dataset.atlas = isEnds(entry) ? 'ends' : 'ready';
    entry.node.dataset.mediaState = entry.failure ? 'failed' : 'ready';
    releaseAll(entry.retired);
  }
  private redraw(tile: Tile) {
    tile.dirty = true;
    paintQueue.schedule(tile.job, () => {
      if (!this.root || !this.alive) return;
      const ctx = tile.canvas.getContext('2d')!;
      ctx.clearRect(0, 0, tile.canvas.width, tile.canvas.height);
      ctx.save(); ctx.scale(this.scale, this.scale); ctx.translate(-tile.x, -tile.y);
      for (const entry of tile.members) if (entry.alive && (entry.source || entry.direct)) {
        const r = entry.spec.rect;
        if (entry.direct) {
          ctx.save();
          try {
          ctx.translate(r.x, r.y);
          ctx.beginPath(); ctx.roundRect(0, 0, r.w, r.h, 4); ctx.clip();
          ctx.fillStyle = this.backgrounds[entry.spec.kind] || this.backgrounds.other;
          if (isEnds(entry)) { ctx.fillRect(0, 0, 65, r.h); ctx.fillRect(r.w - 65, 0, 65, r.h); }
          else ctx.fillRect(0, 0, r.w, r.h);
          ctx.beginPath(); ctx.roundRect(1, 1, Math.max(1, r.w - 2), Math.max(1, r.h - 2), 3); ctx.clip();
          for (const part of entry.direct) { ctx.globalAlpha = part.opacity; cover(ctx, part.image, part.rect.x, part.rect.y, part.rect.w, part.rect.h); }
          } catch (error) { entry.failure = String(error); this.errors.set(entry, String(error)); }
          finally { ctx.restore(); }
        } else ctx.drawImage(entry.source!, r.x, r.y, r.w, r.h);
      }
      ctx.restore(); tile.dirty = false;
      tile.canvas.dataset.mediaTile = 'ready';
      if (!tile.canvas.isConnected) this.root.append(tile.canvas);
      for (const entry of tile.members) if (entry.keys.every((key) => !this.tiles.get(key)?.dirty)) {
        this.ready(entry);
      }
      if (!tile.members.size) {
        tile.canvas.remove();
        if (this.tiles.get(tile.key) === tile) this.tiles.delete(tile.key);
      }
      this.clearRetired();
    });
  }
  private clearRetired() {
    if ([...this.tiles.values()].some((tile) => tile.dirty)) return;
    if ([...this.entries].some((entry) => (entry.source || entry.direct) && entry.readyScale !== this.scale)) return;
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
  const registration = useRef<ReturnType<TrackSurface['add']> | null>(null);
  useEffect(() => {
    if (!SHARED_MEDIA || !surface || !spec || !node.current) return;
    const remove = surface.add(spec, node.current); registration.current = remove;
    return () => { remove(); if (registration.current === remove) registration.current = null; };
  }, [surface, !!spec, node]); // 内容更新保留注册和旧画面，只有离开共享路径才卸载。
  useEffect(() => { if (spec) registration.current?.update(spec); }, [spec]);
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
