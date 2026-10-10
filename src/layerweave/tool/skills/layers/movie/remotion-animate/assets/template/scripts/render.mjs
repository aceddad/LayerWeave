// 导出视频。
// 用法：node scripts/render.mjs <输出.mp4> [--comp Film] [--frames 0-47] [--concurrency N] [--crf 18] [--gl angle]
// 资源：--concurrency 是同时渲染的浏览器标签数，默认取 CPU 核数的四分之一（至少 1），机器吃紧时设为 1；
//       编码线程跟随 Remotion 默认值。临时文件跟随系统 TEMP/TMP，系统盘紧张时把它们指到别的盘再运行。
// 浏览器：设置环境变量 REMOTION_BROWSER_EXECUTABLE 时用它；否则由 Remotion 自行准备 Chrome Headless Shell。
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const i = args.indexOf(name);
  if (i < 0) return fallback;
  const value = args[i + 1];
  args.splice(i, 2);
  return value;
};
const comp = option('--comp', 'Film');
const frames = option('--frames', null)?.split('-').map(Number);
const concurrency = Number(option('--concurrency', String(Math.max(1, Math.floor(os.cpus().length / 4)))));
const crf = Number(option('--crf', '18'));
const gl = option('--gl', null);                 // 用到 WebGL（three.js 等）时传 --gl angle
const chromiumOptions = gl ? {gl} : {};
const [output] = args;
if (!output) {
  console.error('用法：node scripts/render.mjs <输出.mp4> [--comp Film] [--frames 0-47] [--concurrency N] [--crf 18] [--gl angle]');
  process.exit(1);
}

const app = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE || null;
const serveUrl = await bundle({entryPoint: path.join(app, 'src', 'index.ts')});
const composition = await selectComposition({serveUrl, id: comp, browserExecutable, chromiumOptions});
console.log(`渲染 ${comp}（${frames ? `第 ${frames[0]}–${frames[1]} 帧` : `全片 ${composition.durationInFrames} 帧`}，并发 ${concurrency}）→ ${output}`);
let last = -1;
await renderMedia({
  composition, serveUrl, browserExecutable, chromiumOptions, outputLocation: output, codec: 'h264', crf, audioBitrate: '320k', concurrency,
  ...(frames ? {frameRange: [frames[0], frames[1]]} : {}),
  onProgress: ({progress}) => {
    const p = Math.floor(progress * 100);
    if (p >= last + 10) { console.log(`  ${p}%`); last = p; }
  },
});
console.log('完成：' + output);
