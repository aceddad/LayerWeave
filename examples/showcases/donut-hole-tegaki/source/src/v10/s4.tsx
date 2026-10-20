// v9 · 间奏二、C 段、副歌三、鼓的过门、尾声（2:22–3:24）
import React from 'react';
import {useT} from '../core/clock';
import {KICKS, SNARES, pulse} from '../core/time';
import {A, BEAT, CREAM, Cam, Cut, E, Fill, Flash, Field, Glow, Grade, Hole, Horizon, KText, L, Letterbox, Motes, Plane, Rays, Ribbon, Scene3D, T0, T1,
  Vignette, WarpDef, charT, clamp, ease, io, lerp, near, on12, pick, rnd, seg, shake, stem, useLyrics} from './kit';
import {GlyphWord, Panes, impact} from './GlyphWord';
import {Pose, SING_34, SING_FRONT, Sing, breath, cycle} from './parts';
import BOLD from '../data/glyph_bold.json';
import LIGHT from '../data/glyph_light.json';

type GData = Parameters<typeof GlyphWord>[0]['data'];
const GB = BOLD as unknown as GData, GL = LIGHT as unknown as GData;
const OBJ = [71, 68, 65, 67, 69, 70, 72, 66];
const FALL = [81, 82, 80, 83];
const RUN = [86, 87, 88, 89, 90, 91, 92, 93];
const TOWARD = Array.from({length: 46}, (_, i) => 1269 + i);
// 网屏：把旧画风的画统一成"印刷的点"
const Screen: React.FC<{k?: number; color?: string; cell?: number}> = ({k = 1, color = '#1a0a04', cell = 9}) =>
  <Fill style={{backgroundImage: `radial-gradient(circle, transparent 38%, ${color} 72%)`, backgroundSize: `${cell}px ${cell}px`, mixBlendMode: 'multiply', opacity: k, pointerEvents: 'none'}} />;

// ================================================================ 间奏二 2:22.45–2:39.59（高潮：塌、坠、落地、跑、冲进光里、静音里回头）
export const Interlude2_9: React.FC = () => {
  const t = useT();
  return (
    <Fill style={{background: '#000'}}>
      <Cut a={142.45} b={142.96}><Break t={t} /></Cut>
      <Cut a={142.96} b={149.2}><Fall t={t} /></Cut>
      <Cut a={149.2} b={150.4}><Land t={t} /></Cut>
      <Cut a={150.4} b={153.5}><Run t={t} /></Cut>
      <Cut a={153.5} b={156.4}><Rush t={t} /></Cut>
      <Cut a={156.4} b={158.25}><White t={t} /></Cut>
      <Cut a={158.25} b={159.59}><LookBack t={t} /></Cut>
    </Fill>
  );
};

// 黑场一闪，地平线从中间断开，两半往下掉
const Break: React.FC<{t: number}> = ({t}) => {
  const k = ease(seg(t, 142.5, 142.96));
  return (
    <Fill>
      <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}>
        <line x1={0} y1={540} x2={940} y2={540 + 260 * k * k} stroke={CREAM} strokeWidth={3} transform={`rotate(${8 * k} 0 540)`} />
        <line x1={980} y1={540 + 260 * k * k} x2={1920} y2={540} stroke={CREAM} strokeWidth={3} transform={`rotate(${-8 * k} 1920 540)`} />
      </svg>
    </Fill>
  );
};

// 坠落：没有地面；她翻着往下掉（四张），夏天的东西和会场的碎片往上飞；镲是一下一下的碎光
const Fall: React.FC<{t: number}> = ({t}) => {
  const a = 142.96, b = 149.2;
  const id = cycle(on12(t), FALL, 2.4, a);
  const rot = (t - a) * 38;
  const hat = stem('drums_hat', t);
  const u = t - a;
  return (
    <Fill>
      <Field temp="void" glow={[960, 300]} />
      <Fill style={{background: `radial-gradient(circle at 50% 30%, rgba(80,110,160,${0.25 + 0.3 * hat}), transparent 60%)`}} />
      {/* 往上飞的东西：碎片（矩形）、物件、会场的碎块 */}
      <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}>
        {Array.from({length: 70}, (_, i) => {
          const sp = 500 + 900 * rnd(i), y = 1200 - ((u * sp + rnd(i + 1) * 1400) % 1400);
          const x = rnd(i + 2) * 1920, w = 10 + 60 * rnd(i + 3);
          return <rect key={i} x={x} y={y} width={w} height={w * 0.4} fill="#8fa4c4" opacity={0.25 + 0.4 * rnd(i + 4)} transform={`rotate(${u * 90 * (rnd(i + 5) - 0.5) + i * 20} ${x} ${y})`} />;
        })}
      </svg>
      {OBJ.map((oid, j) => {
        const sp = 300 + 220 * rnd(j + 30), y = 1250 - ((u * sp + j * 170) % 1500);
        return <Pose key={oid} id={oid} x={150 + j * 230} y={y} s={0.1 * (oid === 66 ? 1.3 : 1)} anchor="center"
                     style={{transform: `rotate(${u * 120 * (j % 2 ? 1 : -1)}deg)`, filter: 'saturate(.4) brightness(.8)'}} />;
      })}
      <Cam r={rot} s={0.62 + 0.08 * Math.sin(u * 2)} y={-40}>
        <A id={id} style={{filter: 'saturate(.2) contrast(1.15) brightness(1.05) sepia(.15) hue-rotate(180deg)'}} />
      </Cam>
      {hat > 0.45 && <Fill style={{background: `rgba(220,235,255,${0.12 * hat})`, mixBlendMode: 'screen'}} />}
      <Motes n={90} color="#dfe8ff" size={2.5} op={0.8} speed={2.5} seed={111} />
      <Vignette k={0.7} />
    </Fill>
  );
};

// 落地：鞋（落地前 → 着地），地平线猛地弹回来
const Land: React.FC<{t: number}> = ({t}) => {
  const hit = 149.71;
  const k = ease(seg(t, hit, hit + 0.18));
  return (
    <Fill style={{transform: shake(t, [hit], 16, 3)}}>
      <Grade mode="heat"><Cam s={1.1 - 0.06 * k}><A id={t < hit - E ? 84 : 85} /></Cam></Grade>
      {t >= hit - E && <Horizon y={905} w={[960 - 1300 * k, 960 + 1300 * k]} k={1} width={4} glow color="#fff2dc" />}
      <Flash at={[hit]} frames={2} />
    </Fill>
  );
};

// 跑：侧面跑步循环（八张，一拍二），背景拉成光条，脚下的地平线飞快地流
const Run: React.FC<{t: number}> = ({t}) => {
  const a = 150.4, b = 153.5;
  const sp = lerp(1, 1.5, seg(t, a, b));
  const id = cycle(on12(t), RUN, 0.62 / sp, a);
  const pan = -((t - a) * 900 * sp) % 1920;
  return (
    <Fill>
      <Field temp="heat" glow={[1500, 500]} />
      <Grade mode="heat" extra="brightness(.9)">
        <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}><circle cx={1500 + pan * 0.05} cy={420} r={330} fill="#ffe0aa" /></svg>
      </Grade>
      <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0, mixBlendMode: 'screen'}}>
        {Array.from({length: 40}, (_, i) => {
          const y = 80 + rnd(i) * 900, len = 200 + 500 * rnd(i + 1), x = 1920 - (((t - a) * (2200 + 1500 * rnd(i + 2)) + rnd(i + 3) * 2600) % 2600);
          return <line key={i} x1={x} y1={y} x2={x + len} y2={y} stroke="#ffe3b8" strokeWidth={1 + 3 * rnd(i + 4)} opacity={0.5} />;
        })}
      </svg>
      <Horizon y={985} k={1.2} width={3} glow color="#fff2dc" />
      <Pose id={id} x={900} y={990} s={1.0} />
      <Motes n={80} color="#ffd59a" size={4} op={0.9} glow seed={121} speed={2} />
    </Fill>
  );
};

// 2:33.5 起：半拍一切，越来越快；朝镜头跑来的连续画（旧画风，用网屏统一）和 astra 的奔跑特写交替；光往中心收
const Rush: React.FC<{t: number}> = ({t}) => {
  const a = 153.5, b = 156.4;
  const half = BEAT / 2;
  const n = Math.floor((t - a + E) / half);
  const toward = TOWARD[clamp(Math.floor((t - a) * 14), 0, 45)];
  const close = [94, 95, 96, 97][Math.floor(n / 2) % 4];
  const showToward = n % 2 === 0;
  const glow = seg(t, a, b);
  return (
    <Fill>
      {showToward ? (
        <Fill>
          <Grade mode="heat" extra="grayscale(1) sepia(1) saturate(3) hue-rotate(-12deg) contrast(1.35) brightness(1.05)"><Cam y={-120}><A id={toward} /></Cam></Grade>
          <Screen k={0.85} />
        </Fill>
      ) : (
        <Grade mode="heat"><Cam s={1.05 + 0.04 * ((t - a) % half) / half}><A id={close} /></Cam></Grade>
      )}
      <Rays cx={960} cy={500} n={70} k={0.5 + 0.5 * glow} spin={0} r0={80} color="#fff3dc" />
      <Glow x={960} y={500} r={200 + 900 * glow} color="255,240,215" k={0.3 + 0.6 * glow} />
      <Fill style={{transform: `scale(${1 + 0.02 * pulse(KICKS, t, 0.08)})`}} />
    </Fill>
  );
};

// 冲进光里：主观往前猛推，画面全白
const White: React.FC<{t: number}> = ({t}) => {
  const a = 156.4, b = 158.25;
  const k = io(seg(t, a, b));
  return (
    <Fill style={{background: '#000'}}>
      <Field temp="heat" glow={[960, 540]} />
      <Cam s={1 + 3 * k * k}><Grade mode="heat"><A id={49} /></Grade></Cam>
      <Rays cx={960} cy={540} n={90} k={1} spin={0.02} r0={40 + 200 * k} color="#fff8ea" width={4} />
      <Fill style={{background: '#fff8ee', opacity: Math.pow(k, 1.6)}} />
    </Fill>
  );
};

// 全曲唯一的静音：声音停了，画面没停；冷下来的光慢慢落，她停住，回头
const LookBack: React.FC<{t: number}> = ({t}) => {
  const a = 158.25;
  const id = t < a + 0.45 ? 98 : t < a + 0.9 ? 99 : 100;
  return (
    <Fill>
      <Fill style={{background: '#fff8ee', opacity: 1 - ease(seg(t, a, a + 0.5))}} />
      <Grade mode="cold" extra="brightness(1.05)"><Cam s={1.05}><A id={101} /></Cam></Grade>
      <Grade mode="cold"><Cam s={1.35} oy={140} y={60}><A id={id} /></Cam></Grade>
      <Motes n={50} color="#ffd8b0" size={3} up={false} op={0.7} speed={0.3} seed={131} />
      <Fill style={{background: '#fff8ee', opacity: 1 - ease(seg(t, a, a + 0.35)), zIndex: 22}} />
      <Vignette k={0.7} />
    </Fill>
  );
};

// ================================================================ C 段 2:39.59–2:54.83（没有地面。冷的虚空，胸口的洞里是夏天）
export const C9: React.FC = () => {
  const t = useT();
  useLyrics();
  const kick = pulse(KICKS, t, 0.16);
  const sink = kick * 14;
  return (
    <Fill style={{background: '#000', transform: `translateY(${sink}px)`, filter: `brightness(${1 - 0.25 * kick})`}}>
      <Cut a={159.59} b={162.74}><Void31 t={t} /></Cut>
      <Cut a={162.74} b={167.2}><Chest32 t={t} /></Cut>
      <Cut a={167.2} b={170.46}><Hollow33 t={t} /></Cut>
      <Cut a={170.46} b={174.83}><Tear34 t={t} /></Cut>
      <Vignette k={0.75} />
    </Fill>
  );
};

// 冷光：'其他'轨变成断开的短音，每一下是一道冷光
const coldPulse = (t: number) => stem('other', t) * 0.8;

const Void31: React.FC<{t: number}> = ({t}) => {
  const a = 159.59, b = 162.74;
  const s = lerp(1.35, 1.05, io(seg(t, a, b)));
  const hole = 30 + 40 * ease(seg(t, T0(31) + 0.6, T0(31) + 1.6)) + 6 * pulse(KICKS, t, 0.2);
  return (
    <Fill>
      <Field temp="void" glow={[960, 520]} />
      <Fill style={{background: `radial-gradient(circle at 50% 45%, rgba(170,190,220,${0.12 + 0.2 * coldPulse(t)}), transparent 55%)`}} />
      <Cam s={s} oy={330} y={-60 * (s - 1)}>
        <A id={102} style={{filter: 'brightness(1.1)'}} />
        {/* 胸口的洞：洞里是夏天的会场 */}
        <Hole cx={958} cy={330} r={hole} soft={8}>
          <Grade mode="heat" extra="brightness(1.3)"><Cam s={0.35} ox={958} oy={330}><A id={49} /></Cam></Grade>
        </Hole>
        <Glow x={958} y={330} r={hole * 2.6} color="255,170,90" k={0.6} />
      </Cam>
      <KText text={L(31)} t0={T0(31)} t1={T1(31) - 0.05} x={1460} y={170} size={58} vertical enter="type" step={0.13} weight={400} color="#d9e1ee" spacing={0.3} />
    </Fill>
  );
};

const Chest32: React.FC<{t: number}> = ({t}) => {
  const a = 162.74, b = 167.2;
  const beat = 1 + 0.025 * pulse(KICKS, t, 0.2);
  return (
    <Fill>
      <Grade mode="cold" extra="brightness(1.1)"><Cam s={(1.05 + 0.08 * io(seg(t, a, b))) * beat} oy={520}><A id={103} /></Cam></Grade>
      <Glow x={1330} y={790} r={170 + 60 * pulse(KICKS, t, 0.2)} color="255,160,80" k={0.35} />
      <KText text={L(32)} t0={T0(32)} t1={T1(32) - 0.05} x={180} y={150} size={54} vertical enter="type" step={0.12} weight={400} color="#d9e1ee" spacing={0.3} />
    </Fill>
  );
};

// 只有字：空心的"虚しくて"，冷光一下一下
const Hollow33: React.FC<{t: number}> = ({t}) => {
  const a = 167.2, b = 170.46;
  const w0 = charT(33, '虚');
  const word = '虚しくて';
  const shown = clamp(Math.floor((t - w0 + E) / (BEAT * 0.75)) + 1, 0, 4);
  return (
    <Fill style={{background: '#06080b'}}>
      <Fill style={{background: `radial-gradient(circle at 50% 50%, rgba(160,180,210,${0.1 + 0.25 * coldPulse(t)}), transparent 60%)`}} />
      <KText text={L(33).replace(word, '')} t0={T0(33)} t1={b - 0.1} x={240} y={300} size={40} weight={300} color="#aeb8c8" spacing={0.4} />
      {t >= w0 - E && (
        <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}>
          <g clipPath="url(#hollowclip)">
            <GlyphWord data={GL} word={word} x={250} y={380} w={1420} h={369} fill="none" stroke="#e6edf7" strokeWidth={2.2} />
          </g>
          <defs><clipPath id="hollowclip"><rect x={0} y={0} width={250 + (1420 / 4) * shown} height={1080} /></clipPath></defs>
        </svg>
      )}
      {near(t, SNARES.filter((s) => s.t > a && s.t < b).map((s) => s.t), 2 / 24) && <Fill style={{background: 'rgba(200,215,240,.08)'}} />}
    </Fill>
  );
};

// 心が千切れそうだ：画面被冷光切成竖条，一条条撕开；字本身也被切开
const Tear34: React.FC<{t: number}> = ({t}) => {
  const a = 170.46, b = 174.83;
  const tw = charT(34, '千切');
  const piece = (j: number) => {
    const age = t - tw - (j % 3) * 0.06;
    const k = age < 0 ? 0 : ease(Math.min(1, age / 1.6));
    return {x: (j - 3.5) * 14 * k, y: (j % 2 ? -1 : 1) * 160 * k, z: 0, rotateY: 0, rotateZ: (j % 2 ? -1 : 1) * 2 * k};
  };
  const hit = impact(t - tw);
  const back = seg(t, 174.38, b);
  return (
    <Fill>
      <Field temp="void" />
      <Panes count={8} width={240} slope={0} offset={0} piece={piece}>
        <Grade mode="cold" extra="brightness(1.1)"><Cam s={1.25} oy={330}><A id={102} /></Cam></Grade>
      </Panes>
      {t >= tw - E && (
        <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}>
          {(['above', 'below'] as const).map((keep, j) => (
            <GlyphWord key={keep} data={GB} word="千切れそうだ" x={200} y={420} w={1520} h={256} fill="#eef3fa" opacity={0.92}
              cut={{x: 960, y: 548, angle: 4, keep}} warp={(x, y) => [x + (j ? 1 : -1) * 16 * ease(seg(t, tw, tw + 1)) + hit * 10, y + (j ? 1 : -1) * 22 * ease(seg(t, tw, tw + 1))]} />
          ))}
        </svg>
      )}
      <KText text={L(34).split('　')[1] ?? ''} t0={charT(34, 'どう')} t1={174.35} x={620} y={860} size={40} weight={400} color="#c6d0de" spacing={0.3} />
      {back > 0 && <Horizon y={560} k={back * 2} width={3} glow />}
      <Flash at={[174.8]} frames={2} />
    </Fill>
  );
};

// ================================================================ 副歌三 2:54.83–3:06.26（热回来，她更近；"体温"是暗的；这次手放下了）
export const Chorus3_9: React.FC = () => {
  const t = useT();
  useLyrics();
  const k = pulse(KICKS, t, 0.12);
  return (
    <Fill style={{background: '#000', transform: `scale(${1 + 0.018 * k})`}}>
      <Cut a={174.83} b={178.05}><Near35 t={t} /></Cut>
      <Cut a={178.05} b={182.51}><Dark36 t={t} /></Cut>
      <Cut a={182.51} b={186.26}><Down37 t={t} /></Cut>
      <Vignette k={0.45} />
    </Fill>
  );
};

const Near35: React.FC<{t: number}> = ({t}) => {
  const a = 174.83, b = 178.05;
  const wave = (ph: number, y: number, amp: number) => {
    let d = `M -200 ${y}`;
    for (let x = -200; x <= 2200; x += 60) d += ` L ${x} ${(y + Math.sin(x * 0.005 + ph) * amp).toFixed(1)}`;
    return d;
  };
  return (
    <Fill>
      <Field temp="heat" glow={[960, 420]} />
      <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}><circle cx={960} cy={380} r={200 + 360 * ease(seg(t, a, a + 0.8))} fill="#ffe0aa" opacity={0.9} /></svg>
      <Rays cx={960} cy={300} n={72} k={0.95} spin={0.1} r0={200} />
      <Motes n={130} color="#ffd59a" size={4.5} op={0.95} glow seed={141} speed={2} />
      <Ribbon id="r35b" d={wave((t - a) * 1.2, 380, 120)} text={L(35)} t0={a} speed={420} size={62} op={0.8} repeat={3} />
      <Cam s={1.9 + 0.1 * io(seg(t, a, b))} oy={260} y={170}><Sing ids={SING_FRONT} s={breath(t)} origin="960px 1080px" /></Cam>
      <Ribbon id="r35f" d={wave((t - a) * 1.2 + 2, 860, 90)} text={L(35)} t0={a - 1.3} speed={480} size={80} op={0.95} repeat={3} weight={800} />
    </Fill>
  );
};

const Dark36: React.FC<{t: number}> = ({t}) => {
  const a = 178.05, b = 182.51;
  const rot = lerp(-24, 24, io(seg(t, a, b)));
  const tw = charT(36, '体温');
  return (
    <Fill>
      <Field temp="heat" glow={[960 - rot * 20, 460]} />
      <Rays cx={1100} cy={300} n={64} k={0.8} spin={0.1} />
      <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}><circle cx={1100} cy={360} r={460} fill="#ffd9a0" opacity={0.75} /></svg>
      <Cam s={1.45} oy={200} y={90} x={180 + rot * 2}><Sing ids={SING_34} s={breath(t)} origin="960px 1080px" /></Cam>
      <Ribbon id="r36f" d={`M -200 900 C 400 780, 900 1020, 2200 860`} text={L(36)} t0={a} speed={520} size={62} weight={700} />
      <Motes n={90} color="#ffd59a" size={4} op={0.85} glow seed={151} speed={1.8} />
      {/* 体温：这一次是暗的，烧焦的颜色，没有光 */}
      {t >= tw - E && (
        <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}>
          <GlyphWord data={GB} word="体温" x={80} y={110} w={600} h={303} fill="#2a0e04" opacity={0.92 * ease(seg(t, tw, tw + 0.3))} stroke="#ff8a3a" strokeWidth={1.2}
                     warp={(x, y) => [x + impact(t - tw) * 10, y]} />
        </svg>
      )}
    </Fill>
  );
};

const Down37: React.FC<{t: number}> = ({t}) => {
  const a = 182.51, b = 186.26;
  const down = charT(37, 'もう');
  return (
    <Fill>
      <Grade mode="heat"><Cam s={1.04 + 0.05 * io(seg(t, a, b))}><A id={t < down - E ? 104 : 105} /></Cam></Grade>
      <Motes n={80} color="#ffd59a" size={4} op={0.8} up={t >= down} glow seed={161} />
      <KText text={L(37)} t0={T0(37)} t1={T1(37) - 0.1} x={140} y={130} size={90} enter="type" step={0.1} drift={[0, 0]} weight={800} wrap={1300} glow="rgba(255,140,40,.6)" />
    </Fill>
  );
};

// ================================================================ 鼓的过门 3:06.26–3:09.35（不唱了，热烧到最满：过曝，只剩她的剪影，字的碎片往上烧）
export const Fill9: React.FC = () => {
  const t = useT();
  useLyrics();
  const a = 186.26, b = 189.35;
  const burn = io(seg(t, a, b));
  const chars = [...(L(35) + L(36) + L(37)).replace(/\s+/g, '')];
  return (
    <Fill style={{background: '#fff4e2'}}>
      <Field temp="white" />
      <Glow x={960} y={500} r={1300} color="255,170,90" k={0.7} />
      <Cam s={1.0 + 0.1 * burn}><Pose id={47} x={960} y={1080} s={1} style={{filter: 'brightness(0) saturate(0)', opacity: 0.9}} /></Cam>
      {chars.map((c, i) => {
        const st = a + rnd(i) * 1.5;
        const age = t - st;
        if (age < 0) return null;
        const x = 120 + rnd(i + 1) * 1680, y = 1000 - age * (300 + 500 * rnd(i + 2)) - age * age * 60;
        return <span key={i} style={{position: 'absolute', left: x, top: y, font: `700 ${40 + 60 * rnd(i + 3)}px var(--mincho)`, color: '#ff8a30',
          opacity: Math.max(0, 1 - age / 1.6), filter: `blur(${age * 3}px)`, transform: `rotate(${(rnd(i + 4) - 0.5) * 60 * age}deg)`}}>{c}</span>;
      })}
      <Motes n={160} color="#ff9a40" size={4} op={0.9} speed={2.5} seed={171} />
      <Fill style={{background: '#fff', opacity: 0.6 * Math.pow(seg(t, 188.6, b), 2)}} />
    </Fill>
  );
};

// ================================================================ 尾声 3:09.35–3:24.36（浪停了。闭眼 → 会场冷下来 → 睁眼两次 → 海市蜃楼，名字出来之前定格）
export const Outro9: React.FC = () => {
  const t0 = useT();
  useLyrics();
  const FREEZE = 203.83;
  const t = Math.min(t0, FREEZE);
  return (
    <Fill style={{background: '#000'}}>
      <Cut a={189.35} b={193.86}>
        <Fill style={{background: '#fff4e2', opacity: 1 - ease(seg(t, 189.35, 190.6))}} />
        <Grade mode={t < 191.5 ? 'heat' : 'autumn'} extra={`brightness(${lerp(1.3, 0.95, seg(t, 189.35, 193.86))})`}>
          <Cam s={1.12 - 0.06 * seg(t, 189.35, 193.86)}><A id={108} /></Cam>
        </Grade>
        <Fill style={{background: '#fff4e2', opacity: 0.7 * (1 - ease(seg(t, 189.35, 191.5))), mixBlendMode: 'screen'}} />
        <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0, mixBlendMode: 'screen'}}>
          {Array.from({length: 6}, (_, i) => {
            const ph = ((t - 189.35) / 1.4 + i / 6) % 1;
            return <ellipse key={i} cx={1030} cy={520} rx={120 + 1500 * ph} ry={(120 + 1500 * ph) * 0.7} fill="none" stroke="#ffe2b8" strokeWidth={2 + 10 * (1 - ph)}
                            opacity={(1 - ph) * 0.5 * (1 - seg(t, 192, 193.86))} />;
          })}
        </svg>
        <KText text={L(38).split('　')[0]} t0={T0(38)} t1={charT(38, 'その') - 0.05} x={1660} y={160} size={52} vertical weight={400} spacing={0.25} />
        <KText text={L(38).split('　')[1] ?? ''} t0={charT(38, 'その')} t1={T1(38) - 0.1} x={1560} y={160} size={52} vertical weight={400} spacing={0.25} />
      </Cut>
      <Cut a={193.86} b={charT(39, '目を')}>
        <Grade mode="autumn"><Cam s={1.0} x={-700 + 120 * seg(t, 193.86, 197.69)}><A id={2} /></Cam></Grade>
        <Breath t={t} />
        <KText text={L(39).split('　')[0]} t0={T0(39)} t1={charT(39, '目を') - 0.1} x={160} y={150} size={46} weight={400} drift={[4, 0]} spacing={0.3} />
      </Cut>
      <Cut a={charT(39, '目を')} b={T1(39)}>
        <Grade mode="autumn"><Cam s={1.06}><A id={pick(t, [[charT(39, '目を'), 108], [charT(39, '目を') + 0.25, 106], [charT(39, '目を') + 0.85, 108], [charT(39, '目を') + 1.0, 106]])} /></Cam></Grade>
        <KText text={L(39).split('　')[1] ?? ''} t0={charT(39, '目を')} t1={T1(39) - 0.05} x={1660} y={170} size={52} vertical weight={400} spacing={0.25} />
      </Cut>
      {/* 第二次睁眼：完全睁开，然后镜头钻进瞳孔，瞳孔变成窗，窗里是海平线 */}
      <Cut a={T1(39)} b={T0(41)}>
        <Cam s={1 + 2.2 * Math.pow(seg(t, 199.4, T0(41)), 2)} ox={1030} oy={520}>
          <Grade mode="none" extra="brightness(1.05) saturate(.9)"><A id={t < T1(39) + 0.6 ? 106 : 107} /></Grade>
          <Hole cx={1030} cy={520} r={lerp(0, 760, Math.pow(seg(t, 199.6, T0(41)), 1.6))} soft={10}>
            <Cam s={1 / (1 + 2.2 * Math.pow(seg(t, 199.4, T0(41)), 2))} ox={1030} oy={520}><Grade mode="none" extra="brightness(1.05)"><Cam s={1.05}><A id={109} /></Cam></Grade></Cam>
          </Hole>
        </Cam>
        <KText text={L(40)} t0={T0(40)} t1={T1(40) - 0.05} x={1660} y={170} size={60} vertical weight={500} spacing={0.25} />
      </Cut>
      <Cut a={T0(41)} b={205}>
        <Mirage t={t} />
      </Cut>
      <Vignette k={0.55} />
    </Fill>
  );
};

// 地平线在呼吸：会场的冷色版，海平线一条，随她的呼吸起伏
const Breath: React.FC<{t: number}> = ({t}) => {
  const k = 0.5 + 0.5 * Math.sin((t - 193.86) * 1.6);
  return <Horizon y={596} k={0.4 + 0.5 * k} width={1.5} color="#f0e6d8" />;
};

// 海市蜃楼：海平线上浮着一片热气，热气里好像有人；"あなたの名前は"；203.83 定格
const Mirage: React.FC<{t: number}> = ({t}) => {
  const a = T0(41);
  const seed = Math.floor(on12(t) * 12) % 9;
  const word = ease(seg(t, a, a + 1.0));
  return (
    <Fill>
      <WarpDef id="mirage" scale={22} freq={[0.004, 0.035]} seed={seed} />
      <Grade mode="none" extra="brightness(1.05)">
        <Cam s={1.05 + 0.04 * seg(t, a, 203.83)}>
          <A id={109} />
          <Fill style={{filter: 'url(#mirage)', WebkitMaskImage: 'linear-gradient(180deg, transparent 52%, #000 60%, #000 70%, transparent 76%)'}}>
            <A id={109} />
            <Pose id={98} x={1000} y={714} s={0.09} style={{opacity: 0.55, filter: 'blur(1.2px) brightness(1.4) saturate(.3)'}} />
            <Glow x={1000} y={690} r={160} color="255,240,220" k={0.5} />
          </Fill>
        </Cam>
      </Grade>
      <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}>
        <GlyphWord data={GL} word="あなたの名前は" x={960 - 560} y={250} w={1120} h={165} fill="#fffaf2" opacity={0.92 * word} />
      </svg>
      <Letterbox h={110} />
    </Fill>
  );
};
void Plane; void Scene3D; void Hole; void Letterbox; void SING_34; void SING_FRONT; void GB;
