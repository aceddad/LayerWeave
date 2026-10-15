// 截图用：图片、视频封面、波形都画好以后才举手（window.__layerweaveReady），截图工具（view_screenshot）等到它再拍
import {pendingWalk} from './sync';
import {CAPTURE} from './params';
import {pendingZoom} from './camera';
import {paintQueue} from './canvas/mediaQueue';
import {mediaPaintState} from './canvas/TrackMedia';

declare global {
  interface Window {
    __layerweaveReady?: boolean;
    __layerweavePaintIdle?: () => Promise<void>;
    __layerweavePaintState?: typeof mediaPaintState;
  }
}

const frames = () => new Promise<void>((r) => requestAnimationFrame(() => requestAnimationFrame(() => r())));
const settle = (el: Element, events: string[]) => new Promise<void>((done) => {
  const finish = () => { events.forEach((name) => el.removeEventListener(name, finish)); done(); };
  events.forEach((name) => el.addEventListener(name, finish, {once: true}));
  // 页面不把超时伪装成完成；截图工具的 wait_ms 和量具决定各自等待多久。
});

let started = false;
// 正常页面的只读等待入口不设置 capture，也不强迫屏幕外媒体开始下载。
window.__layerweavePaintIdle = async () => {
  await pendingZoom();
  await frames();
  await paintQueue.idle();
  await pendingZoom();
  await paintQueue.idle();
};
window.__layerweavePaintState = mediaPaintState;

export async function markReady() {
  if (!CAPTURE || started) return;
  started = true;
  await frames();
  await frames();
  await pendingWalk();                  // 沿着读的结果可能挂载新的媒体，先让对应 DOM/effects 提交。
  await frames();
  const images = [...document.querySelectorAll('img')];
  await Promise.all(images.filter((i) => !i.complete).map((i) => settle(i, ['load', 'error'])));
  await Promise.all([...document.querySelectorAll('video')].filter((v) => v.readyState < 2 && v.preload !== 'none').map((v) => settle(v, ['loadeddata', 'error'])));
  await window.__layerweavePaintIdle!();
  await Promise.all([...document.querySelectorAll('img')].map((i) => i.decode().catch(() => undefined)));
  await frames();
  window.__layerweaveReady = true;
}
