// 把原型按时刻一帧帧截下来（无头 Edge）：node scripts/capture.mjs 起秒 止秒 输出目录 [fps=24] [缩放=0.6667]
// 原型的画面只由 t 决定，所以逐帧 seek 截下来的就是播放时看到的。输出目录请用英文路径。
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';

const [, , from, to, outDir, fps = '24', scale = '0.6667'] = process.argv;
const browser = await puppeteer.launch({
  executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  headless: true,
  args: ['--disable-extensions', '--disable-sync', '--hide-scrollbars', '--disable-background-networking', '--no-first-run', '--mute-audio'],
});
const page = await browser.newPage();
await page.setViewport({width: 1920, height: 1080, deviceScaleFactor: +scale});
// 环境变量 Q 可追加参数，例如 Q='&v=4'
await page.goto(`http://localhost:5199/?clean&t=${from}${process.env.Q ?? ''}`, {waitUntil: 'networkidle0', timeout: 180000});
await page.waitForFunction('window.__ready === true', {timeout: 300000});
fs.mkdirSync(outDir, {recursive: true});
const n = Math.round((+to - +from) * +fps);
for (let i = 0; i < n; i++) {
  const t = +from + i / +fps;
  await page.evaluate(async (t) => {
    window.seek(t);
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    await Promise.all([...document.images].map((im) => (im.complete ? im.decode().catch(() => {}) : new Promise((r) => { im.onload = im.onerror = r; }))));
  }, t);
  await page.screenshot({path: `${outDir}/${String(i).padStart(5, '0')}.jpg`, type: 'jpeg', quality: 86});
}
await browser.close();
console.log(`${n} frames → ${outDir}`);
