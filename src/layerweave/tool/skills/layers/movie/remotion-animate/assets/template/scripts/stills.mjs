// 按全局秒数渲染几张静帧，用来审阅画面（不用渲整片）。
// 用法：node scripts/stills.mjs <输出文件夹> <秒1> [秒2 ...] [--comp Film-Review] [--scale 0.5] [--gl angle]
// 浏览器：设置环境变量 REMOTION_BROWSER_EXECUTABLE 时用它；否则由 Remotion 自行准备 Chrome Headless Shell。
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const i = args.indexOf(name);
  if (i < 0) return fallback;
  const value = args[i + 1];
  args.splice(i, 2);
  return value;
};
const comp = option('--comp', 'Film-Review');
const scale = Number(option('--scale', '0.5'));
const gl = option('--gl', null);                 // 用到 WebGL（three.js 等）时传 --gl angle
const chromiumOptions = gl ? {gl} : {};
const [outDir, ...seconds] = args;
if (!outDir || seconds.length === 0) {
  console.error('用法：node scripts/stills.mjs <输出文件夹> <秒1> [秒2 ...] [--comp Film-Review] [--scale 0.5] [--gl angle]');
  process.exit(1);
}

const app = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE || null;
fs.mkdirSync(outDir, {recursive: true});
const serveUrl = await bundle({entryPoint: path.join(app, 'src', 'index.ts')});
const composition = await selectComposition({serveUrl, id: comp, browserExecutable, chromiumOptions});
for (const s of seconds) {
  const frame = Math.min(composition.durationInFrames - 1, Math.round(Number(s) * composition.fps));
  const output = path.join(outDir, `${comp}_${Number(s).toFixed(2)}s_f${frame}.jpg`);
  await renderStill({composition, serveUrl, browserExecutable, frame, output, imageFormat: 'jpeg', scale, chromiumOptions});
  console.log(output);
}
