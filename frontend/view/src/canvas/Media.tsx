// 图片、视频画面的小部件：服务端有 ffmpeg 时视频画面由它抽帧（结果稳定，截图也拍得到），没有时交给浏览器解码
import {useEffect, useRef} from 'react';
import {frameUrl, thumbUrl} from '../api';
import {viewport} from '../camera';
import {CAPTURE, DECODE, LAZY} from '../params';
import {useStore} from '../store';
import type {Layer, Obj} from '../types';
import {paintQueue} from './mediaQueue';
import {mediaUrl} from './mediaUrl';
import {decodedImages} from './imageCache';
import type {ImageLease} from './imageCache';

export function Img({src}: {src: string}) {
  return <img loading={LAZY} decoding={DECODE} src={src} alt="" />;
}

// 图片对象的缩略图：服务端有 ffmpeg 时按宽度缩好（缩不了的它自己送原图）；没有 ffmpeg 时直接用原图。
// 一览网格通常用 320，接缝页/侧栏卡片用 640；共享画布按实际显示尺寸在 TrackMedia 选源档位。
export function Thumb({project, o, width, frames}: {project: number; o: Obj; width: number; frames: boolean}) {
  return <Img src={mediaUrl(frames ? thumbUrl(project, o.id, width) : o.media!.url!, o.media?.source)} />;
}

export function Frame({project, o, at, frames}: {project: number; o: Obj; at: number | 'end'; frames: boolean}) {
  if (frames) return <Img src={mediaUrl(frameUrl(project, o.id, at), o.media?.source)} />;
  return <video muted preload="metadata" src={`${mediaUrl(o.media!.url!, o.media?.source)}#t=${at === 'end' ? 9999 : at}`} />;
}

// ---------- 画布上格子里的图：画进 <canvas>，只画一次 ----------
// 放大以后画面里有上百张缩略图时，用 <img> 平移会卡：浏览器每一帧都要把这些图重新画进画面（手书：放大到 1.6 倍、104 张图，
// 95% 的帧在 35–55 毫秒以内；藏掉这些图就降到 7–14 毫秒）。画布里的内容画好就固定了，平移时只是整块挪动（实验里同样降到 7–14 毫秒，
// 2026-10-14 量的）。清晰度按镜头停下来时的缩放算，换档时重画一次
export const loadImage = (src: string) => decodedImages.load(src);
export const acquireImage = (src: string) => decodedImages.acquire(src);

// 旧逐格画布对照也使用共享预算队列；截图等待同时覆盖新旧两种绘制路径。
const schedule = (draw: () => void) => paintQueue.schedule(draw, draw);

// 当前挂载画布的反馈；等待由有 owner 的共享队列负责，不等待全局缓存全集。
const legacy = new Map<HTMLCanvasElement, {state: string; error?: string}>();
const mark = (canvas: HTMLCanvasElement, state: string, error?: unknown) => {
  canvas.dataset.mediaState = state; legacy.set(canvas, {state, error: error == null ? undefined : String(error)});
};
export const legacyPaintState = () => [...legacy.values()];

export function CanvasImg({src}: {src: string}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const zoom = useStore((s) => s.settledZoom);
  const state = useRef({w: 0, h: 0, zoom: 0, img: undefined as HTMLImageElement | null | undefined, drawn: '', draw: () => {}});
  state.current.zoom = zoom;
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    mark(canvas, 'idle');
    const st = state.current;
    st.img = undefined;
    st.drawn = '';
    let alive = true;
    let lease: ImageLease | undefined;
    const owner = {};
    st.draw = () => {
      if (!alive || st.img === undefined) return;
      if (!st.img) { mark(canvas, 'failed', '媒体无法解码'); return; }
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
      mark(canvas, 'ready');
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
    const start = () => {
      mark(canvas, 'pending');
      lease = acquireImage(src);
      return paintQueue.track(lease.promise.then((img) => {
        if (alive) { st.img = img; schedule(st.draw); }
      }, (error) => { if (alive) mark(canvas, 'failed', error); }), owner);
    };
    let near: IntersectionObserver | undefined;
    if (CAPTURE) start();
    else {
      near = new IntersectionObserver((entries) => { if (entries.some((e) => e.isIntersecting)) { near!.disconnect(); start(); } }, {rootMargin: '600px'});
      near.observe(canvas);
    }
    return () => { alive = false; lease?.release(); paintQueue.cancel(owner); paintQueue.cancel(st.draw); sizes.disconnect(); near?.disconnect(); legacy.delete(canvas); };
  }, [src]);
  useEffect(() => { schedule(state.current.draw); }, [zoom]);   // 镜头停下来换了缩放：按新的清晰度重画
  return <canvas ref={ref} />;
}

// 画布上的格子用：图片格子的缩略图、视频格子的画面（有 ffmpeg 时）都画进 canvas；没有 ffmpeg 的视频照旧交给浏览器解码
export function BlockThumb({project, o, width, frames}: {project: number; o: Obj; width: number; frames: boolean}) {
  return <CanvasImg src={mediaUrl(frames ? thumbUrl(project, o.id, width) : o.media!.url!, o.media?.source)} />;
}
export function BlockFrame({project, o, at, frames}: {project: number; o: Obj; at: number | 'end'; frames: boolean}) {
  if (frames) return <CanvasImg src={mediaUrl(frameUrl(project, o.id, at), o.media?.source)} />;
  return <Frame project={project} o={o} at={at} frames={false} />;
}
