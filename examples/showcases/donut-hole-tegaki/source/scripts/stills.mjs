// 按时刻截几张审阅静帧，并拼成一张总览：node scripts/stills.mjs 输出目录 秒1 秒2 …（环境变量 Q 追加地址参数，例如 Q='&v=9'）
// 输出：目录/秒.jpg（960×540）和 目录/_sheet.jpg（4 列，每格左上角写秒数）
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';

const [, , outDir, ...times] = process.argv;
fs.mkdirSync(outDir, {recursive: true});
const browser = await puppeteer.launch({executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true,
  args: ['--disable-extensions', '--hide-scrollbars', '--mute-audio', '--no-first-run']});
const page = await browser.newPage();
await page.setViewport({width: 1920, height: 1080, deviceScaleFactor: 0.5});
await page.goto(`http://localhost:5199/?clean&t=${times[0]}${process.env.Q ?? ''}`, {waitUntil: 'networkidle0', timeout: 300000});
await page.waitForFunction('window.__ready === true', {timeout: 300000});
page.on('console', (m) => { if (m.type() === 'error') console.log('console:', m.text()); });
const files = [];
for (const t of times) {
  await page.evaluate(async (t) => {
    window.seek(+t);
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    await Promise.all([...document.images].map((im) => (im.complete ? im.decode().catch(() => {}) : new Promise((r) => { im.onload = im.onerror = r; }))));
    await new Promise((r) => requestAnimationFrame(r));
  }, t);
  const f = `${outDir}/${(+t).toFixed(2)}.jpg`;
  await page.screenshot({path: f, type: 'jpeg', quality: 85});
  files.push([t, f]);
}
// 拼总览：在页面里画
const sheet = await page.evaluate(async (items) => {
  const C = 4, W = 480, H = 270, rows = Math.ceil(items.length / C);
  const cv = document.createElement('canvas'); cv.width = C * W; cv.height = rows * (H + 4);
  const c = cv.getContext('2d'); c.fillStyle = '#222'; c.fillRect(0, 0, cv.width, cv.height);
  for (let i = 0; i < items.length; i++) {
    const im = new Image(); im.src = items[i][1]; await im.decode();
    const x = (i % C) * W, y = Math.floor(i / C) * (H + 4);
    c.drawImage(im, x, y, W, H);
    c.fillStyle = '#000'; c.fillRect(x, y, 70, 22); c.fillStyle = '#ffd060'; c.font = '16px monospace'; c.fillText((+items[i][0]).toFixed(2), x + 4, y + 16);
  }
  return cv.toDataURL('image/jpeg', 0.85);
}, files.map(([t, f]) => [t, 'data:image/jpeg;base64,' + fs.readFileSync(f).toString('base64')]));
fs.writeFileSync(`${outDir}/_sheet.jpg`, Buffer.from(sheet.split(',')[1], 'base64'));
await browser.close();
console.log(`${files.length} stills → ${outDir}/_sheet.jpg`);
