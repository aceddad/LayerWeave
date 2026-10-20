// 时间数据：小节、拍、段落、鼓、人声包络都来自 05_素材/音频（旧库导出的时间结构）。画面只由时刻 t（秒）决定。
import data from '../data/timeline.json';
import voice from '../data/voice.json';

export type Hit = {t: number; k: 'kick' | 'snare' | 'hat'; s: number};
type Timeline = {duration: number; bpm: number; beat0: number; bars: number[]; sections: {name: string; begin: number; end: number}[]; drums: Hit[]};
export const T = data as unknown as Timeline;
export const BEAT = 60 / T.bpm;
export const BAR = BEAT * 4;
export const FPS = 24;
export const E = 1 / FPS;                       // 早一帧：变化落在起音那一帧
export const DUR = T.duration;
export const bar = (n: number) => T.bars[0] + n * BAR;

export const KICKS = T.drums.filter((d) => d.k === 'kick' && d.s >= 0.3);
export const SNARES = T.drums.filter((d) => d.k === 'snare' && d.s >= 0.4);

// ---------------------------------------------------------------- 小工具
export const clamp = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a: number, b: number, k: number) => a + (b - a) * k;
export const seg = (t: number, a: number, b: number) => clamp((t - a) / (b - a));
export const easeOut = (k: number) => 1 - Math.pow(1 - clamp(k), 3);
export const easeInOut = (k: number) => { k = clamp(k); return k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2; };
// 一拍二：代码画的运动用 12 张/秒的时间
export const step = (t: number, fps = 12) => Math.floor(t * fps + 1e-6) / fps;
// 摄影表：[[秒, 值], …] → 停在上一个，不插值（早一帧）
export function sheet<V>(t: number, keys: [number, V][]): V {
  let v = keys[0][1];
  for (const [k, val] of keys) if (t >= k - E) v = val;
  return v;
}
// 第几拍（从 from 起，含当前），from 之前是 -1
export const beatIndex = (t: number, from: number) => (t < from - E ? -1 : Math.floor((t - from + E) / BEAT));
// 确定性随机（以整数为种子）
export const rnd = (i: number) => { const s = Math.sin(i * 12.9898 + 78.233) * 43758.5453; return s - Math.floor(s); };

// ---------------------------------------------------------------- 鼓
function lastIndex(list: Hit[], t: number) {
  let lo = 0, hi = list.length - 1, r = -1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (list[m].t <= t) { r = m; lo = m + 1; } else hi = m - 1; }
  return r;
}
// 最近一下的余震（0–1）
export function pulse(list: Hit[], t: number, len = 0.09) {
  const i = lastIndex(list, t + E);
  if (i < 0) return 0;
  return list[i].s * Math.exp(-(t + E - list[i].t) / len);
}
export const hitsIn = (list: Hit[], a: number, b: number) => list.filter((h) => h.t >= a && h.t < b);
export const countUntil = (list: Hit[], a: number, t: number) => list.filter((h) => h.t >= a && h.t <= t + E).length;
export const lastHit = (list: Hit[], t: number) => { const i = lastIndex(list, t + E); return i < 0 ? null : list[i]; };

// ---------------------------------------------------------------- 人声
const ENV = (voice as {env: number[]}).env;
export const voiceAt = (t: number) => ENV[clamp(Math.floor((t * 24) / 2) * 2, 0, ENV.length - 1)] ?? 0;   // 一拍二取
export const mouth = (t: number) => { const v = voiceAt(t); return v > 0.62 ? 2 : v > 0.3 ? 1 : 0; };

// ---------------------------------------------------------------- 段落
export const SECTIONS = T.sections;
export const section = (name: string) => SECTIONS.find((s) => s.name === name)!;
export const sectionAt = (t: number) => { let s = SECTIONS[0]; for (const x of SECTIONS) if (t >= x.begin - E) s = x; return s; };
