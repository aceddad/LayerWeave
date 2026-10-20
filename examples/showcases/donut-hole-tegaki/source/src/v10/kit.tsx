// v9 的部件。画面 = 色场（代码）+ 窗（插画从形状里露出来）+ 她（透明图）+ 字 + 点 + 效果。
// 一切只由时刻 t 决定；坐标是 1920×1080 舞台像素。设计见 01_企划/10_编排_v9.md。
import React, {useEffect, useLayoutEffect, useRef, useState} from 'react';
import type {CSSProperties, ReactNode} from 'react';
import {useT} from '../core/clock';
import {BAR, BEAT, E, clamp, easeOut, lerp, rnd, seg} from '../core/time';
import {cues, loadCues} from '../ui/kit';
import ASSETS from '../data/v9_assets.json';
import STEMS from '../data/stems.json';

export const CREAM = '#efe8dc';
export const KANJI = /[一-鿿々]/;
type Box = [number, number, number, number];
const MAN = ASSETS as unknown as Record<string, {box: Box; alpha: boolean}>;
export const src = (id: string | number) => {
  const k = typeof id === 'number' ? String(id).padStart(4, '0') : id;
  return `/v9/${k}.webp`;
};
export const boxOf = (id: string | number) => MAN[typeof id === 'number' ? String(id).padStart(4, '0') : id].box;
export const V9_IMAGES = Object.keys(MAN).map((k) => `/v9/${k}.webp`);

// ---------------------------------------------------------------- 声音
const ENV = (STEMS as unknown as {env: Record<string, number[]>}).env;
const at = (arr: number[], t: number) => arr[clamp(Math.round(t * 24), 0, arr.length - 1)] ?? 0;
/** 分轨响度（0–1），可以取几帧平均让它更顺 */
export const stem = (name: 'drums_kick' | 'drums_snare' | 'drums_hat' | 'bass' | 'other' | 'vocals', t: number, smooth = 0) => {
  const a = ENV[name];
  if (!smooth) return at(a, t);
  let s = 0;
  for (let i = -smooth; i <= smooth; i++) s += at(a, t + i / 24);
  return s / (2 * smooth + 1);
};
/** 嘴：0 闭 1 小 2 大（一拍二取样，跟手书的口型一样一拍二换） */
export const mouthAt = (t: number, lo = 0.18, hi = 0.5) => {
  const q = Math.floor(t * 12) / 12;
  const v = stem('vocals', q, 1);
  return v > hi ? 2 : v > lo ? 1 : 0;
};

// ---------------------------------------------------------------- 基础
export const Fill: React.FC<{children?: ReactNode; style?: CSSProperties; className?: string}> = ({children, style, className}) => (
  <div className={className} style={{position: 'absolute', left: 0, top: 0, width: 1920, height: 1080, ...style}}>{children}</div>
);
/** 一张素材，放在它原来构图里的位置；可以整体平移、缩放（绕 origin） */
export const A: React.FC<{id: string | number; x?: number; y?: number; s?: number; r?: number; origin?: string; box?: Box; style?: CSSProperties; flip?: boolean}> =
  ({id, x = 0, y = 0, s = 1, r = 0, origin = '960px 540px', box, style, flip}) => {
    const b = box ?? boxOf(id);
    return (
      <img src={src(id)} draggable={false}
           style={{position: 'absolute', left: b[0], top: b[1], width: b[2], height: b[3], transformOrigin: originRel(origin, b),
             transform: `translate(${x}px, ${y}px) scale(${flip ? -s : s}, ${s}) rotate(${r}deg)`, ...style}} />
    );
  };
// origin 写的是舞台坐标，换成相对图片自身的坐标
const originRel = (o: string, b: Box) => {
  const m = o.match(/^(-?[\d.]+)px (-?[\d.]+)px$/);
  return m ? `${+m[1] - b[0]}px ${+m[2] - b[1]}px` : o;
};
/** 镜头：平移、推拉、旋转都在一个容器上做，里面的东西照常按舞台坐标摆 */
export const Cam: React.FC<{x?: number; y?: number; s?: number; r?: number; ox?: number; oy?: number; children: ReactNode; style?: CSSProperties}> =
  ({x = 0, y = 0, s = 1, r = 0, ox = 960, oy = 540, children, style}) => (
    <Fill style={{transformOrigin: `${ox}px ${oy}px`, transform: `translate(${x}px, ${y}px) scale(${s}) rotate(${r}deg)`, ...style}}>{children}</Fill>
  );
/** 3D 镜头：Plane 的 z 越小越远；远处的层自动放大补偿，静止时看起来和平面一样，镜头一动就有真实的视差 */
export const Scene3D: React.FC<{camX?: number; camY?: number; camZ?: number; rotY?: number; rotX?: number; persp?: number; children: ReactNode}> =
  ({camX = 0, camY = 0, camZ = 0, rotY = 0, rotX = 0, persp = 1400, children}) => (
    <Fill style={{perspective: persp, perspectiveOrigin: '960px 540px', overflow: 'hidden'}}>
      <Fill style={{transformStyle: 'preserve-3d', transformOrigin: `960px 540px ${-0}px`,
        transform: `translate3d(${-camX}px, ${-camY}px, ${camZ}px) rotateY(${rotY}deg) rotateX(${rotX}deg)`}}>{children}</Fill>
    </Fill>
  );
export const Plane: React.FC<{z: number; persp?: number; children: ReactNode; style?: CSSProperties}> = ({z, persp = 1400, children, style}) => (
  <Fill style={{transformStyle: 'preserve-3d', transformOrigin: '960px 540px', transform: `translateZ(${z}px) scale(${(persp - z) / persp})`, ...style}}>{children}</Fill>
);
/** 一个镜头只在 [a, b) 里显示 */
export const Cut: React.FC<{a: number; b: number; children: ReactNode}> = ({a, b, children}) => {
  const t = useT();
  return t >= a - E && t < b - E ? <>{children}</> : null;
};
/** 摄影表：按时刻取第几张（停在上一张，不插值） */
export const pick = <V,>(t: number, keys: [number, V][]): V => {
  let v = keys[0][1];
  for (const [k, val] of keys) if (t >= k - E) v = val;
  return v;
};
export const on12 = (t: number) => Math.floor(t * 12 + 1e-6) / 12;
export const near = (t: number, times: number[], dur: number) => times.some((a) => t >= a - E && t < a + dur);
export const ease = easeOut;
export const io = (k: number) => { k = clamp(k); return k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2; };
export {seg, lerp, clamp, rnd, BEAT, BAR, E};

// ---------------------------------------------------------------- 色场
export type Temp = 'autumn' | 'night' | 'heat' | 'void' | 'dawn' | 'white';
const FIELD: Record<Temp, [string, string, string]> = {
  autumn: ['#141a24', '#2c3442', '#4a4c52'],
  night: ['#05070d', '#0d1424', '#1a2238'],
  heat: ['#2a0c04', '#b8461a', '#ffc27a'],
  void: ['#030405', '#0b0e12', '#151a20'],
  dawn: ['#1c2436', '#7d8aa2', '#e9d6c0'],
  white: ['#fff3e0', '#fff8ee', '#ffffff'],
};
/** 渐变色场：上暗下亮（或者中心亮），随底鼓轻轻一跳 */
export const Field: React.FC<{temp: Temp; glow?: [number, number]; k?: number; mix?: {temp: Temp; k: number}}> = ({temp, glow = [960, 760], k = 1, mix}) => {
  const t = useT();
  const beat = stem('drums_kick', t) * 0.08 * k;
  const g = (c: [string, string, string]) =>
    `radial-gradient(ellipse 120% 90% at ${glow[0]}px ${glow[1]}px, ${c[2]} 0%, ${c[1]} 38%, ${c[0]} 85%)`;
  return (
    <>
      <Fill style={{background: g(FIELD[temp]), filter: `brightness(${1 + beat})`}} />
      {mix && mix.k > 0 && <Fill style={{background: g(FIELD[mix.temp]), opacity: mix.k, filter: `brightness(${1 + beat})`}} />}
    </>
  );
};

// ---------------------------------------------------------------- 地平线（贝斯）
export const Horizon: React.FC<{y?: number; color?: string; k?: number; w?: [number, number]; width?: number; glow?: boolean}> = ({y = 640, color = CREAM, k = 1, w = [0, 1920], width = 2, glow}) => {
  const t = useT();
  if (k <= 0) return null;
  const amp = stem('bass', t, 1) * 14 * k;
  const pts: string[] = [];
  for (let x = w[0]; x <= w[1]; x += 24) {
    const v = Math.sin(x * 0.011 + t * 2.1) * 0.6 + Math.sin(x * 0.023 - t * 3.3) * 0.4;
    pts.push(`${x},${(y + v * amp).toFixed(1)}`);
  }
  return (
    <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible', pointerEvents: 'none'}}>
      <polyline points={pts.join(' ')} fill="none" stroke={color} strokeWidth={width} opacity={Math.min(1, k)}
                style={glow ? {filter: `drop-shadow(0 0 6px ${color})`} : undefined} />
    </svg>
  );
};

// ---------------------------------------------------------------- 粒子（Canvas，几百颗也不卡）
type Mote = {n: number; color: string; size?: number; up?: boolean; area?: Box; sway?: number; seed?: number; op?: number; speed?: number;
  gather?: {x: number; y: number; k: number}; burst?: {x: number; y: number; at: number; power?: number}; glow?: boolean; fall?: number};
export const Motes: React.FC<Mote & {style?: CSSProperties}> = (p) => {
  const t = useT();
  const ref = useRef<HTMLCanvasElement>(null);
  useLayoutEffect(() => {
    const c = ref.current!.getContext('2d')!;
    c.clearRect(0, 0, 1920, 1080);
    const [ax, ay, aw, ah] = p.area ?? [0, 0, 1920, 1080];
    const u = on12(t);
    c.globalCompositeOperation = p.glow ? 'lighter' : 'source-over';
    for (let i = 0; i < p.n; i++) {
      const sd = i * 7.13 + (p.seed ?? 0);
      const life = (3 + 4 * rnd(sd)) / (p.speed ?? 1);
      const ph = ((u + rnd(sd + 1) * life) % life) / life;
      let x = ax + rnd(sd + 2) * aw + Math.sin(ph * 6 + i) * (p.sway ?? 24);
      let y = p.up === false ? ay + ah * ph : ay + ah - ah * ph;
      if (p.burst && t >= p.burst.at - E) {
        const age = t - p.burst.at, a = rnd(sd + 5) * Math.PI * 2, v = (200 + 700 * rnd(sd + 6)) * (p.burst.power ?? 1);
        x = p.burst.x + Math.cos(a) * v * (1 - Math.exp(-age * 2.2)) / 1.2;
        y = p.burst.y + Math.sin(a) * v * (1 - Math.exp(-age * 2.2)) / 1.2 - 60 * age * age + (p.fall ?? 0) * age * age;
      }
      if (p.gather && p.gather.k > 0) { x = lerp(x, p.gather.x, p.gather.k); y = lerp(y, p.gather.y, p.gather.k); }
      const s = (p.size ?? 4) * (0.45 + rnd(sd + 3));
      const a = (p.op ?? 0.8) * Math.sin(Math.PI * ph);
      if (a <= 0.01) continue;
      c.globalAlpha = a;
      c.fillStyle = p.color;
      c.beginPath();
      c.arc(x, y, s, 0, Math.PI * 2);
      c.fill();
      if (p.glow) { c.globalAlpha = a * 0.25; c.beginPath(); c.arc(x, y, s * 3, 0, Math.PI * 2); c.fill(); }
    }
  });
  return <canvas ref={ref} width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0, pointerEvents: 'none', ...p.style}} />;
};

/** 网点画：插画转成的点（halftone 技能导出的 [x, y, r]），每颗点可以各自动：fx 返回 [x, y, r, 透明度] */
export const Dots: React.FC<{data: number[][]; color: string; fx?: (x: number, y: number, r: number, i: number) => [number, number, number, number]; glow?: boolean; style?: CSSProperties}> =
  ({data, color, fx, glow, style}) => {
    const t = useT();
    const ref = useRef<HTMLCanvasElement>(null);
    useLayoutEffect(() => {
      const c = ref.current!.getContext('2d')!;
      c.clearRect(0, 0, 1920, 1080);
      c.fillStyle = color;
      c.globalCompositeOperation = glow ? 'lighter' : 'source-over';
      for (let i = 0; i < data.length; i++) {
        const [x0, y0, r0] = data[i];
        const [x, y, r, a] = fx ? fx(x0, y0, r0, i) : [x0, y0, r0, 1];
        if (a <= 0.01 || r <= 0.2) continue;
        c.globalAlpha = Math.min(1, a);
        c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.fill();
      }
    });
    void t;
    return <canvas ref={ref} width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0, pointerEvents: 'none', ...style}} />;
  };

// 放射的光线（动态 SVG 那一版用过，用户觉得好看）
export const Rays: React.FC<{cx?: number; cy?: number; n?: number; color?: string; k?: number; spin?: number; r0?: number; r1?: number; width?: number; dash?: boolean}> =
  ({cx = 960, cy = 540, n = 48, color = '#ffe2b0', k = 1, spin = 0, r0 = 160, r1 = 1300, width = 3, dash = true}) => {
    const t = useT();
    if (k <= 0) return null;
    return (
      <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0, pointerEvents: 'none', mixBlendMode: 'screen'}}>
        {Array.from({length: n}, (_, i) => {
          const a = (i / n) * Math.PI * 2 + spin * t;
          const flow = ((t * 0.9 + rnd(i)) % 1);
          const a0 = r0 + (r1 - r0) * (dash ? flow * 0.7 : 0), a1 = a0 + (dash ? 120 + 160 * rnd(i + 2) : r1 - r0);
          return <line key={i} x1={cx + Math.cos(a) * a0} y1={cy + Math.sin(a) * a0} x2={cx + Math.cos(a) * a1} y2={cy + Math.sin(a) * a1}
                       stroke={color} strokeWidth={width * (0.5 + rnd(i + 1))} opacity={k * (0.25 + 0.5 * rnd(i + 4))} strokeLinecap="round" />;
        })}
      </svg>
    );
  };

// ---------------------------------------------------------------- 窗：插画只从形状里露出来
/** 横缝：海平线裂开成一条缝，缝里是画面 */
export const Slit: React.FC<{y: number; h: number; children: ReactNode; soft?: number}> = ({y, h, children, soft = 0}) => (
  <Fill style={soft ? {WebkitMaskImage: `linear-gradient(to bottom, transparent ${y - h / 2 - soft}px, #000 ${y - h / 2}px, #000 ${y + h / 2}px, transparent ${y + h / 2 + soft}px)`}
                    : {clipPath: `inset(${y - h / 2}px 0 ${1080 - y - h / 2}px 0)`}}>{children}</Fill>
);
export const Hole: React.FC<{cx: number; cy: number; r: number; children: ReactNode; soft?: number; ry?: number}> = ({cx, cy, r, children, soft = 0, ry}) => r <= 0 ? null : (
  <Fill style={soft ? {WebkitMaskImage: `radial-gradient(${ry ? `ellipse ${r}px ${ry}px` : `circle ${r}px`} at ${cx}px ${cy}px, #000 ${100 - soft}%, transparent 100%)`}
                    : {clipPath: ry ? `ellipse(${r}px ${ry}px at ${cx}px ${cy}px)` : `circle(${r}px at ${cx}px ${cy}px)`}}>{children}</Fill>
);
export const Rect: React.FC<{box: Box; children: ReactNode; r?: number; style?: CSSProperties}> = ({box, children, r = 0, style}) => (
  <Fill style={{clipPath: `inset(${box[1]}px ${1920 - box[0] - box[2]}px ${1080 - box[1] - box[3]}px ${box[0]}px${r ? ` round ${r}px` : ''})`, ...style}}>{children}</Fill>
);

// ---------------------------------------------------------------- 效果
export const Flash: React.FC<{at: number[]; color?: string; frames?: number; z?: number}> = ({at, color = '#fff', frames = 2, z = 30}) => {
  const t = useT();
  return near(t, at, frames / 24) ? <Fill style={{background: color, zIndex: z}} /> : null;
};
export const shake = (t: number, times: number[], amp = 7, frames = 2) => {
  if (!near(t, times, frames / 24)) return '';
  const i = Math.floor(t * 24);
  return `translate(${((rnd(i) - 0.5) * 2 * amp).toFixed(1)}px, ${((rnd(i + 3) - 0.5) * 2 * amp).toFixed(1)}px)`;
};
export const blurAt = (t: number, times: number[], px = 9, dur = 0.12) => {
  const a = times.find((x) => t >= x - E && t < x + dur);
  return a === undefined ? 0 : px * (1 - (t - a) / dur);
};
export const Letterbox: React.FC<{h: number; color?: string}> = ({h, color = '#000'}) => h <= 0 ? null : (
  <>
    <div style={{position: 'absolute', left: 0, top: 0, width: 1920, height: h, background: color, zIndex: 25}} />
    <div style={{position: 'absolute', left: 0, bottom: 0, width: 1920, height: h, background: color, zIndex: 25}} />
  </>
);
export const Vignette: React.FC<{k?: number; color?: string}> = ({k = 0.55, color = '0,0,0'}) =>
  <Fill style={{background: `radial-gradient(ellipse at 50% 50%, transparent 52%, rgba(${color},${k}) 100%)`, zIndex: 20, pointerEvents: 'none'}} />;
export const Glow: React.FC<{x: number; y: number; r: number; color?: string; k?: number; blend?: CSSProperties['mixBlendMode']}> = ({x, y, r, color = '255,190,120', k = 1, blend = 'screen'}) => k <= 0 ? null :
  <Fill style={{background: `radial-gradient(circle ${r}px at ${x}px ${y}px, rgba(${color},${0.9 * k}) 0%, rgba(${color},${0.35 * k}) 40%, transparent 100%)`, mixBlendMode: blend, pointerEvents: 'none'}} />;
/** 调色：滤镜 + 一层颜色 */
const GRADE: Record<string, [string, string, CSSProperties['mixBlendMode']]> = {
  autumn: ['saturate(.62) contrast(1.05) brightness(.95)', 'rgba(70,92,125,.22)', 'multiply'],
  night: ['saturate(.5) contrast(1.1) brightness(.8)', 'rgba(30,45,90,.35)', 'multiply'],
  heat: ['saturate(1.2) contrast(1.08) brightness(1.03)', 'rgba(255,120,40,.22)', 'soft-light'],
  cold: ['saturate(.15) contrast(1.15) brightness(.85)', 'rgba(60,80,110,.3)', 'multiply'],
  none: ['', 'transparent', 'normal'],
};
export const Grade: React.FC<{mode: keyof typeof GRADE; children: ReactNode; extra?: string}> = ({mode, children, extra = ''}) => (
  <Fill>
    <Fill style={{filter: `${GRADE[mode][0]} ${extra}`.trim() || undefined}}>{children}</Fill>
    <Fill style={{background: GRADE[mode][1], mixBlendMode: GRADE[mode][2], pointerEvents: 'none'}} />
  </Fill>
);
/** 色差：同一份画面再叠两份，分别偏红、偏青 */
export const Chroma: React.FC<{d: number; children: ReactNode}> = ({d, children}) => d <= 0.3 ? <>{children}</> : (
  <Fill>
    {children}
    <Fill style={{transform: `translateX(${d}px)`, mixBlendMode: 'screen', opacity: 0.55, filter: 'sepia(1) saturate(6) hue-rotate(-40deg)'}}>{children}</Fill>
    <Fill style={{transform: `translateX(${-d}px)`, mixBlendMode: 'screen', opacity: 0.45, filter: 'sepia(1) saturate(6) hue-rotate(150deg)'}}>{children}</Fill>
  </Fill>
);
/** 故障：横向切成几条，各自错开 */
export const Glitch: React.FC<{on: boolean; seed: number; n?: number; amp?: number; children: ReactNode}> = ({on, seed, n = 7, amp = 120, children}) => !on ? <>{children}</> : (
  <>
    {Array.from({length: n}, (_, i) => {
      const a = (rnd(i + seed * 3) * 0.5 + i) / n * 100, b = (i + 1) / n * 100;
      return <Fill key={i} style={{clipPath: `inset(${a}% 0 ${100 - b}% 0)`, transform: `translateX(${(rnd(i + seed) - 0.5) * amp}px)`}}>{children}</Fill>;
    })}
  </>
);
/** 热浪 / 雨窗：SVG 湍流扭曲。返回 filter 值，配合 <Warp id> 定义 */
export const WarpDef: React.FC<{id: string; scale: number; freq?: [number, number]; seed?: number}> = ({id, scale, freq = [0.006, 0.02], seed = 1}) => (
  <svg width={0} height={0} style={{position: 'absolute'}}>
    <filter id={id} x="-10%" y="-10%" width="120%" height="120%">
      <feTurbulence type="fractalNoise" baseFrequency={`${freq[0]} ${freq[1]}`} numOctaves={2} seed={seed} />
      <feDisplacementMap in="SourceGraphic" scale={scale} xChannelSelector="R" yChannelSelector="G" />
    </filter>
  </svg>
);

// ---------------------------------------------------------------- 歌词
export const useLyrics = () => { const [, s] = useState(0); useEffect(() => { loadCues().then(() => s(1)); }, []); };
const ln = (i: number) => cues()[i - 1];
export const L = (i: number) => ln(i)?.ja ?? '';
export const T0 = (i: number) => ln(i)?.start ?? 0;
export const T1 = (i: number) => ln(i)?.end ?? 0;
/** 歌词里某几个字唱到的时刻（按字数在整句里均分，够卡点用） */
export const charT = (i: number, sub: string) => {
  const s = L(i), k = s.indexOf(sub);
  if (k < 0) return T0(i);
  return T0(i) + (T1(i) - T0(i)) * (k / [...s].length);
};

// 动态文字：じわパン（淡入 + 滑入，之后继续慢慢漂）；汉字放大；可以一个字一个字出
export type KT = {text: string; t0: number; t1: number; x: number; y: number; size: number; vertical?: boolean; color?: string;
  enter?: 'jiwa' | 'type' | 'cut' | 'drop'; step?: number; exit?: 'fade' | 'cut' | 'chars' | 'blur'; drift?: [number, number]; weight?: number; glow?: string;
  rot?: number; spacing?: number; kanji?: number; wrap?: number; shadow?: string; style?: CSSProperties; squash?: number; outline?: boolean};
export const KText: React.FC<KT> = ({text, t0, t1, x, y, size: size0, vertical, color = CREAM, enter = 'jiwa', step, exit = 'fade', drift = [0, -10], weight = 600, glow,
  rot = 0, spacing = 0.12, kanji = 1.35, wrap, shadow, style, squash = 1, outline}) => {
  const t = useT();
  if (!text || t < t0 - E || t > t1 + 0.5) return null;
  const chars = [...text.replace(/\s+/g, '　')];
  const units = chars.reduce((a, c) => a + (KANJI.test(c) ? kanji : 1), 0) * (1 + spacing);
  const room = vertical ? 1080 - y - 60 : (wrap ?? 1920 - x - 60);
  const rows = wrap ? Math.ceil((units * size0) / wrap) : 1;
  const size = Math.min(size0, (room * (wrap ? Math.max(1, rows) : 1)) / units);
  const st = step ?? Math.min(0.08, ((t1 - t0) * 0.45) / chars.length);
  const k = enter === 'cut' ? 1 : easeOut(seg(t, t0, t0 + 0.32));
  const slide = enter === 'jiwa' ? (1 - k) * 26 : 0;
  const dx = drift[0] * (t - t0) + (vertical ? 0 : slide), dy = drift[1] * (t - t0) + (vertical ? slide : 0);
  const out = exit === 'cut' ? (t > t1 ? 0 : 1) : exit === 'fade' || exit === 'blur' ? 1 - seg(t, t1, t1 + 0.3) : 1;
  const bl = exit === 'blur' ? 10 * seg(t, t1 - 0.1, t1 + 0.3) : 0;
  return (
    <div style={{position: 'absolute', left: x, top: y, transform: `translate(${dx}px, ${dy}px) rotate(${rot}deg) scaleY(${squash})`, transformOrigin: '0 50%',
      writingMode: vertical ? 'vertical-rl' : 'horizontal-tb', font: `${weight} ${size}px/1.18 var(--mincho)`, letterSpacing: `${spacing}em`,
      color: outline ? 'transparent' : color, WebkitTextStroke: outline ? `1.5px ${color}` : undefined,
      whiteSpace: wrap ? 'normal' : 'nowrap', width: wrap, wordBreak: 'break-all', opacity: (enter === 'jiwa' ? k : 1) * out, filter: bl ? `blur(${bl}px)` : undefined,
      textShadow: glow ? `0 0 ${size * 0.35}px ${glow}` : shadow ?? '0 2px 12px rgba(0,0,0,.5)', zIndex: 18, ...style}}>
      {chars.map((c, i) => {
        const ct = t0 + i * st;
        let a = enter === 'type' || enter === 'drop' ? (t >= ct - E ? 1 : 0) : 1;
        const dropY = enter === 'drop' ? -40 * (1 - easeOut(seg(t, ct, ct + 0.18))) : 0;
        if (exit === 'chars') a *= 1 - seg(t, t1 - (chars.length - i) * 0.05, t1 - (chars.length - i) * 0.05 + 0.12);
        return <span key={i} style={{opacity: a, fontSize: KANJI.test(c) ? size * kanji : size, display: 'inline-block', transform: dropY ? `translateY(${dropY}px)` : undefined}}>{c}</span>;
      })}
    </div>
  );
};

/** 字带：一句歌词沿着曲线流动（SVG textPath）。part='back' 只画上半圈（在人物后面），'front' 只画下半圈 */
export const Ribbon: React.FC<{id: string; d: string; text: string; t0: number; speed: number; size: number; color?: string; part?: 'back' | 'front' | 'all'; cy?: number;
  glow?: string; op?: number; weight?: number; hot?: string; hotColor?: string; repeat?: number}> =
  ({id, d, text, t0, speed, size, color = '#fff2de', part = 'all', cy = 540, glow = 'rgba(255,140,40,.7)', op = 1, weight = 600, hot, hotColor = '#fff', repeat = 3}) => {
    const t = useT();
    const full = Array(repeat).fill(text).join('　　');
    const off = -((t - t0) * speed);
    const clip = part === 'back' ? `inset(0 0 ${1080 - cy}px 0)` : part === 'front' ? `inset(${cy}px 0 0 0)` : undefined;
    return (
      <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible', clipPath: clip, pointerEvents: 'none', opacity: op}}>
        <defs><path id={id} d={d} /></defs>
        <text style={{font: `${weight} ${size}px var(--mincho)`, letterSpacing: '0.08em', filter: `drop-shadow(0 0 ${size * 0.3}px ${glow})`}} fill={color}>
          <textPath href={`#${id}`} startOffset={off}>
            {hot ? full.split(hot).flatMap((s, i, arr) => i < arr.length - 1 ? [s, <tspan key={i} fill={hotColor} fontWeight={900}>{hot}</tspan>] : [s]) : full}
          </textPath>
        </text>
      </svg>
    );
  };

// ---------------------------------------------------------------- 手书：纸、墨、纯色
export const PAPER = '#ece4d6', INK = '#24212b', ORANGE = '#e2672a', NAVY = '#141a2b';
/** 纸：米色底 + 很淡的纤维纹（一拍二抖） */
export const Paper: React.FC<{color?: string}> = ({color = PAPER}) => {
  const t = useT();
  const j = Math.floor(t * 12) % 4;
  return (
    <Fill style={{background: color}}>
      <Fill style={{opacity: 0.35, mixBlendMode: 'multiply', backgroundPosition: `${j * 37}px ${j * 53}px`,
        backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='p'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.6' numOctaves='3'/%3E%3CfeColorMatrix values='0 0 0 0 .45 0 0 0 0 .4 0 0 0 0 .35 0 0 0 .5 0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23p)'/%3E%3C/svg%3E\")"}} />
    </Fill>
  );
};
/** 纯色 */
export const Flat: React.FC<{color: string}> = ({color}) => <Fill style={{background: color}} />;
