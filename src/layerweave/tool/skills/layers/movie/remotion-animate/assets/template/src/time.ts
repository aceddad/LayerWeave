// 全片只有一个时钟：音轨的秒数 t。所有场景都用 t 计算，不各自重置。
// BPM 和 PHASE（第 0 拍的秒数）从卡点表（audio-cues 输出的 *_cues.json 里的 bpm、beat0）抄过来。
export const FPS = 24;
export const WIDTH = 1920;
export const HEIGHT = 1080;
export const BPM = 124;
export const PHASE = 0.3;
export const BEAT = 60 / BPM;
export const BAR = BEAT * 4;
export const FILM_END = 16; // 全片秒数
export const FILM_FRAMES = Math.round(FILM_END * FPS);
export const MUSIC: string | null = 'media/song.wav'; // public/ 下的音轨；没有音轨时设为 null

/** 第 n 拍的秒数 */
export const beat = (n: number) => PHASE + n * BEAT;
/** 秒 → 帧 */
export const fr = (sec: number) => Math.round(sec * FPS);
/** t 所在的拍（带小数） */
export const beatPos = (t: number) => (t - PHASE) / BEAT;
/** 本拍内的进度 0..1 */
export const beatFrac = (t: number) => {
  const b = beatPos(t);
  return b - Math.floor(b);
};
/** 每拍一次的衰减脉冲：落拍时为 1，随后衰减 */
export const pulse = (t: number, k = 5) => (t < PHASE ? 0 : Math.exp(-beatFrac(t) * BEAT * k * 2));
/** 一次性冲击：在 at 秒触发，随后衰减 */
export const hit = (t: number, at: number, k = 6) => (t < at ? 0 : Math.exp(-(t - at) * k));
/** 手绘节奏：时间量化到 12 fps（一拍二） */
export const on12 = (t: number) => Math.floor(t * 12) / 12;
/** 每 n 拍跳一次的计数 */
export const onBeats = (t: number, n = 1) => Math.floor(beatPos(t) / n);

export const clamp = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x));
/** t 在 [a, b] 之间的进度 0..1 */
export const prog = (t: number, a: number, b: number) => clamp((t - a) / (b - a));
export const ease = (x: number) => 1 - Math.pow(1 - clamp(x), 3);
export const easeIn = (x: number) => Math.pow(clamp(x), 3);
export const lerp = (a: number, b: number, x: number) => a + (b - a) * x;
/** 可复现的伪随机 0..1：同一个 n 每帧都一样，避免画面闪烁 */
export const hash = (n: number) => {
  const s = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return s - Math.floor(s);
};
