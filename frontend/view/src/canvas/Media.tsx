// 图片、视频画面的小部件：服务端有 ffmpeg 时视频画面由它抽帧（结果稳定，截图也拍得到），没有时交给浏览器解码
import {useEffect, useRef} from 'react';
import {frameUrl, thumbUrl} from '../api';
import {viewport} from '../camera';
import {CAPTURE, DECODE, LAZY} from '../params';
import {useStore} from '../store';
import type {BlockPainter} from '../plugin/host';
import {pluginFailed} from '../plugin/slots';
import type {Layer, Obj} from '../types';

export function Img({src}: {src: string}) {
  return <img loading={LAZY} decoding={DECODE} src={src} alt="" />;
}

// 图片对象的缩略图：服务端有 ffmpeg 时按宽度缩好（缩不了的它自己送原图）；没有 ffmpeg 时直接用原图。
// 画布格子、一览网格用 320 宽，接缝页、侧栏卡片 640 宽；原图只在点开时看
export function Thumb({project, o, width, frames}: {project: number; o: Obj; width: number; frames: boolean}) {
  return <Img src={frames ? thumbUrl(project, o.id, width) : o.media!.url!} />;
}

export function Frame({project, o, at, frames}: {project: number; o: Obj; at: number | 'end'; frames: boolean}) {
  if (frames) return <Img src={frameUrl(project, o.id, at)} />;
  return <video muted preload="metadata" src={`${o.media!.url}#t=${at === 'end' ? 9999 : at}`} />;
}

// ---------- 画布上格子里的图：画进 <canvas>，只画一次 ----------
// 放大以后画面里有上百张缩略图时，用 <img> 平移会卡：浏览器每一帧都要把这些图重新画进画面（手书：放大到 1.6 倍、104 张图，
// 95% 的帧在 35–55 毫秒以内；藏掉这些图就降到 7–14 毫秒）。画布里的内容画好就固定了，平移时只是整块挪动（实验里同样降到 7–14 毫秒，
// 2026-10-14 量的）。清晰度按镜头停下来时的缩放算，换档时重画一次
const images = new Map<string, Promise<HTMLImageElement | null>>();
function loadImage(src: string): Promise<HTMLImageElement | null> {
  if (!images.has(src)) {
    const img = new Image();
    img.decoding = 'async';
    img.src = src;
    images.set(src, img.decode().then(() => img, () => null));
  }
  return images.get(src)!;
}

// 重画排队，每一帧最多画 8 毫秒：镜头停下来换缩放时上百张图要一起重画，一口气画完会卡一下（50–80 毫秒的长任务，2026-10-14 量的）
const queue = new Set<() => void>();
let pumping = false;
function schedule(draw: () => void) {
  queue.add(draw);
  if (!pumping) { pumping = true; requestAnimationFrame(pump); }
}
function pump() {
  const end = performance.now() + 8;
  for (const draw of queue) {
    queue.delete(draw);
    draw();
    if (performance.now() > end) break;
  }
  if (queue.size) requestAnimationFrame(pump);
  else pumping = false;
}

// 截图要等这些画完再举手（capture.ts）
const drawing = new Set<Promise<void>>();
export const pendingThumbs = () => [...drawing];

export function CanvasImg({src}: {src: string}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const zoom = useStore((s) => s.settledZoom);
  const state = useRef({w: 0, h: 0, zoom: 0, img: undefined as HTMLImageElement | null | undefined, drawn: '', draw: () => {}});
  state.current.zoom = zoom;
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const st = state.current;
    st.img = undefined;
    st.drawn = '';
    let alive = true, finish = () => {};
    if (CAPTURE) {
      const done = new Promise<void>((resolve) => { finish = resolve; setTimeout(resolve, 8000); });
      drawing.add(done);
      done.then(() => drawing.delete(done));
    }
    st.draw = () => {
      if (!alive || st.img === undefined) return;
      if (!st.img) { finish(); return; }
      if (!st.w || !st.h) return;
      const k = st.zoom || viewport().zoom || 1;
      let cw = Math.max(1, Math.round(st.w * k)), ch = Math.max(1, Math.round(st.h * k));
      const cap = 2048 / Math.max(cw, ch);
      if (cap < 1) { cw = Math.max(1, Math.round(cw * cap)); ch = Math.max(1, Math.round(ch * cap)); }
      const key = `${cw}x${ch}`;
      if (key === st.drawn) return;
      st.drawn = key;
      canvas.width = cw;
      canvas.height = ch;
      // 和 object-fit: cover 一样：铺满格子，多出来的从两边（或上下）裁掉
      const img = st.img, ir = img.naturalWidth / Math.max(1, img.naturalHeight), cr = cw / ch;
      let sw = img.naturalWidth, sh = img.naturalHeight, sx = 0, sy = 0;
      if (ir > cr) { sw = sh * cr; sx = (img.naturalWidth - sw) / 2; } else { sh = sw / cr; sy = (img.naturalHeight - sh) / 2; }
      canvas.getContext('2d')!.drawImage(img, sx, sy, sw, sh, 0, 0, cw, ch);
      finish();
    };
    // 格子在页面上的尺寸（设备像素，不含画布的缩放）；排版完才回调，不逼浏览器当场排版
    const sizes = new ResizeObserver(([entry]) => {
      const box = entry.devicePixelContentBoxSize?.[0];
      st.w = box ? box.inlineSize : entry.contentRect.width * devicePixelRatio;
      st.h = box ? box.blockSize : entry.contentRect.height * devicePixelRatio;
      schedule(st.draw);
    });
    try { sizes.observe(canvas, {box: 'device-pixel-content-box'}); } catch { sizes.observe(canvas); }
    // 离画面近了才下载、解码（和 <img loading="lazy"> 一样）；截图时马上下
    const start = () => loadImage(src).then((img) => { st.img = img; schedule(st.draw); });
    let near: IntersectionObserver | undefined;
    if (CAPTURE) start();
    else {
      near = new IntersectionObserver((entries) => { if (entries.some((e) => e.isIntersecting)) { near!.disconnect(); start(); } }, {rootMargin: '600px'});
      near.observe(canvas);
    }
    return () => { alive = false; queue.delete(st.draw); sizes.disconnect(); near?.disconnect(); finish(); };
  }, [src]);
  useEffect(() => { schedule(state.current.draw); }, [zoom]);   // 镜头停下来换了缩放：按新的清晰度重画
  return <canvas ref={ref} />;
}

// ---------- 插件画的格子（ViewPlugin.block）：和缩略图同一个重画队列、同一套"只在需要时画" ----------
// 格子大小变了、镜头停下换了缩放、对象变了才画；离画面近了才开始画；截图等它画完（draw 返回 Promise 时等 Promise）
export function PluginCanvas({name, painter, o, layer, unit}: {name: string; painter: BlockPainter; o: Obj; layer: Layer; unit: string}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const zoom = useStore((s) => s.settledZoom);
  const state = useRef({w: 0, h: 0, zoom: 0, drawn: '', draw: () => {}});
  state.current.zoom = zoom;
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const st = state.current;
    st.drawn = '';
    let alive = true, started = false, finish = () => {};
    if (CAPTURE) {
      const done = new Promise<void>((resolve) => { finish = resolve; setTimeout(resolve, 8000); });
      drawing.add(done);
      done.then(() => drawing.delete(done));
    }
    st.draw = () => {
      if (!alive || !started || !st.w || !st.h) return;
      const k = st.zoom || viewport().zoom || 1;
      let cw = Math.max(1, Math.round(st.w * k)), ch = Math.max(1, Math.round(st.h * k));
      const cap = 2048 / Math.max(cw, ch);
      if (cap < 1) { cw = Math.max(1, Math.round(cw * cap)); ch = Math.max(1, Math.round(ch * cap)); }
      const key = `${cw}x${ch}`;
      if (key === st.drawn) return;
      st.drawn = key;
      canvas.width = cw;
      canvas.height = ch;
      try {
        const result = painter.draw(canvas.getContext('2d')!, o, {width: cw, height: ch, unit, layer});
        if (result && typeof result.then === 'function') result.then(finish, (error) => { pluginFailed(name, error); finish(); });
        else finish();
      } catch (error) { pluginFailed(name, error); finish(); }
    };
    const sizes = new ResizeObserver(([entry]) => {
      const box = entry.devicePixelContentBoxSize?.[0];
      st.w = box ? box.inlineSize : entry.contentRect.width * devicePixelRatio;
      st.h = box ? box.blockSize : entry.contentRect.height * devicePixelRatio;
      schedule(st.draw);
    });
    try { sizes.observe(canvas, {box: 'device-pixel-content-box'}); } catch { sizes.observe(canvas); }
    const start = () => { started = true; schedule(st.draw); };
    let near: IntersectionObserver | undefined;
    if (CAPTURE) start();
    else {
      near = new IntersectionObserver((entries) => { if (entries.some((e) => e.isIntersecting)) { near!.disconnect(); start(); } }, {rootMargin: '600px'});
      near.observe(canvas);
    }
    return () => { alive = false; queue.delete(st.draw); sizes.disconnect(); near?.disconnect(); finish(); };
  }, [name, painter, o, layer, unit]);
  useEffect(() => { schedule(state.current.draw); }, [zoom]);
  return <canvas ref={ref} className="plugin-paint" />;
}

// 画布上的格子用：图片格子的缩略图、视频格子的画面（有 ffmpeg 时）都画进 canvas；没有 ffmpeg 的视频照旧交给浏览器解码
export function BlockThumb({project, o, width, frames}: {project: number; o: Obj; width: number; frames: boolean}) {
  return <CanvasImg src={frames ? thumbUrl(project, o.id, width) : o.media!.url!} />;
}
export function BlockFrame({project, o, at, frames}: {project: number; o: Obj; at: number | 'end'; frames: boolean}) {
  if (frames) return <CanvasImg src={frameUrl(project, o.id, at)} />;
  return <Frame project={project} o={o} at={at} frames={false} />;
}
