// 全片按"全局帧号"分块截帧（块边界对齐 1/24 秒，拼起来不会漂）：node scripts/capture_frames.mjs 输出根目录 [并行数=3] [起帧] [止帧]
// 每块存到 输出根目录/cNNN/，块内文件名从 00000 起；按块号顺序拼起来就是全片。环境变量 Q 照常传给 capture.mjs。
// 任何一块失败（子进程退出码非 0，或帧数不对）都会列出来，并以退出码 1 结束；全部成功才输出 ALL DONE。
import {spawn} from 'node:child_process';
import fs from 'node:fs';
const T = JSON.parse(fs.readFileSync('src/data/timeline.json', 'utf8'));
const [, , root, par = '3', f0 = '0', f1 = String(Math.ceil(T.duration * 24))] = process.argv;
if (!root) { console.error('用法：node scripts/capture_frames.mjs 输出根目录 [并行数] [起帧] [止帧]'); process.exit(2); }
const CH = 360;
const jobs = [];
for (let a = +f0; a < +f1; a += CH) jobs.push([a, Math.min(+f1, a + CH)]);
const dirOf = (a) => `${root}/c${String(a / CH).padStart(3, '0')}`;
const count = (d) => (fs.existsSync(d) ? fs.readdirSync(d).filter((f) => f.endsWith('.jpg')).length : 0);
const failed = [];
let next = 0;
const run = () => new Promise((done) => {
  const go = () => {
    if (next >= jobs.length) return done();
    const [a, b] = jobs[next++];
    const out = dirOf(a);
    if (count(out) === b - a) return go();
    const p = spawn(process.execPath, ['scripts/capture.mjs', String(a / 24), String(b / 24), out], {stdio: 'inherit'});
    p.on('error', (e) => { failed.push(`${out}：启动失败 ${e.message}`); go(); });
    p.on('exit', (code) => {
      const n = count(out);
      if (code !== 0) failed.push(`${out}：截帧进程退出码 ${code}（已有 ${n}/${b - a} 帧）`);
      else if (n !== b - a) failed.push(`${out}：帧数不对 ${n}/${b - a}`);
      go();
    });
  };
  go();
});
await Promise.all(Array.from({length: +par}, run));
if (failed.length) {
  console.error(`\n${failed.length} 块失败（重新运行同一条命令只会补跑这些块）：\n  ` + failed.join('\n  '));
  process.exit(1);
}
console.log('ALL DONE');
