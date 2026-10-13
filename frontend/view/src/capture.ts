// 截图用：图片、视频封面、波形都画好以后才举手（window.__layerweaveReady），截图工具（view_screenshot）等到它再拍
import {pendingThumbs} from './canvas/Media';
import {pendingWaves} from './canvas/Waveform';
import {CAPTURE} from './params';

declare global {
  interface Window { __layerweaveReady?: boolean }
}

const frames = () => new Promise<void>((r) => requestAnimationFrame(() => requestAnimationFrame(() => r())));
const settle = (el: Element, events: string[]) => new Promise<void>((done) => {
  events.forEach((name) => el.addEventListener(name, () => done(), {once: true}));
  setTimeout(done, 8000);                                 // 个别文件解不开也不要一直等
});

let started = false;
export async function markReady() {
  if (!CAPTURE || started) return;
  started = true;
  await frames();
  await frames();
  const images = [...document.querySelectorAll('img')];
  await Promise.all(images.filter((i) => !i.complete).map((i) => settle(i, ['load', 'error'])));
  await Promise.all([...document.querySelectorAll('video')].filter((v) => v.readyState < 2 && v.preload !== 'none').map((v) => settle(v, ['loadeddata', 'error'])));
  await Promise.all(pendingWaves());
  await Promise.all(pendingThumbs());   // 格子里的图画进 canvas（canvas/Media.tsx）
  await Promise.all([...document.querySelectorAll('img')].map((i) => i.decode().catch(() => undefined)));
  await frames();
  window.__layerweaveReady = true;
}
