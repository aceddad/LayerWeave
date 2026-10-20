// v10（手书）· 前奏、A1、A2（0:00–0:47）
// 手书的做法：纯色 / 纸的底，人物是透明图，字是主角；整张插画只留给要说话的那几下。不把画掰歪。
import React from 'react';
import {useT} from '../core/clock';
import {KICKS, SNARES, bar, hitsIn, pulse} from '../core/time';
import {A, BEAT, CREAM, Cam, Cut, E, Fill, Flash, Field, Grade, Horizon, INK, KText, L, Letterbox, Motes, NAVY, ORANGE, PAPER, Paper, Rect, Ribbon, Scene3D, Plane, Slit, T0, T1,
  Vignette, blurAt, charT, clamp, ease, io, lerp, near, on12, rnd, seg, shake, src, useLyrics} from './kit';
import {Pose, cycle} from './parts';

// ================================================================ 前奏 0:00–0:16.73
export const Intro9: React.FC = () => {
  const t = useT();
  useLyrics();
  const HY = 560;
  const open = t < 8.62 ? lerp(2, 360, io(seg(t, 1.49, bar(3)))) + 60 * seg(t, bar(3), 8.62) : lerp(420, 0, io(seg(t, 8.62, 9.11)));
  const pan = -300 - 520 * seg(t, 1.49, 9.11);
  return (
    <Fill style={{background: '#000'}}>
      <Cut a={0} b={1.49}><div style={{position: 'absolute', left: 0, top: HY - 1, height: 2, width: 1920 * ease(seg(t, 1.21, 1.47)), background: CREAM}} /></Cut>
      {/* 海平线裂开成缝，缝里是夏天的会场 */}
      <Cut a={1.49} b={9.11}>
        <Field temp="autumn" glow={[1300, HY]} k={0.6} />
        <Fill style={{background: 'rgba(0,0,0,.72)'}} />
        <Motes n={60} color="#ffc98a" size={3} area={[0, HY - 500, 1920, 480]} speed={0.6} op={0.55} seed={2} />
        <Slit y={HY} h={open}>
          <Grade mode="autumn" extra="brightness(1.08)"><Cam x={pan} y={HY - 600}><A id={1} /></Cam></Grade>
          <Motes n={40} color="#ffd29a" size={4} area={[700, HY - 240, 1200, 400]} op={0.8} glow seed={5} />
        </Slit>
        <Horizon y={HY - open / 2} k={1} width={2} />
        <Horizon y={HY + open / 2} k={1} width={2} />
        <KText text="ドーナツホール" t0={bar(1)} t1={8.7} x={1760} y={40} size={34} vertical enter="type" step={BEAT * 0.5} drift={[0, -4]} weight={400} spacing={0.5} kanji={1} />
      </Cut>
      {/* 门票：墨色的墙上一道斜的窗光，门票是唯一的暖色；光随军鼓一格一格挪 */}
      <Cut a={9.11} b={12.92}>
        <Fill style={{background: NAVY}} />
        <WindowBars t={t} a={9.11} />
        <Pose id={71} x={960 + 24 * Math.sin((t - 9.11) * 0.9)} y={560 - 12 * Math.sin((t - 9.11) * 1.3)} s={0.62} anchor="center"
              style={{transform: `rotate(${-8 + 3 * Math.sin((t - 9.11) * 0.7)}deg)`, filter: 'drop-shadow(18px 26px 0 rgba(0,0,0,.35))'}} />
        <Motes n={40} color="#ffe2b8" size={2.5} area={[200, 100, 1500, 900]} op={0.7} glow seed={14} speed={0.35} sway={60} />
      </Cut>
      {/* 床边背影：墙是一块墨色，窗是唯一的画（从窗形里看见黄昏的城），她坐在前面 */}
      <Cut a={12.92} b={16.25}>
        <Fill style={{background: '#10141f'}} />
        <Rect box={[504, 20, 912, 540]}><Grade mode="autumn" extra="brightness(1.1)"><Cam s={1 + 0.03 * seg(t, 12.92, 16.25)} ox={960} oy={290}><A id={5} /></Cam></Grade></Rect>
        <div style={{position: 'absolute', left: 504, top: 20, width: 912, height: 540, border: `14px solid #0a0d15`, boxSizing: 'border-box'}} />
        <div style={{position: 'absolute', left: 953, top: 20, width: 14, height: 540, background: '#0a0d15'}} />
        <Fill style={{background: 'linear-gradient(180deg, transparent 50%, rgba(255,170,100,.08) 52%, transparent 100%)'}} />
        <Cam s={1 + 0.06 * io(seg(t, 12.92, 16.25))} oy={1080}><A id={4} y={8 * Math.sin(t * 1.9)} /></Cam>
        <Motes n={26} color="#ffe6c0" size={2.5} area={[500, 100, 900, 500]} op={0.5} seed={8} speed={0.4} />
      </Cut>
      {/* 鞋抬起、落下；落下那一下地平线从鞋底展开 */}
      <Cut a={16.25} b={16.73}>
        <Fill style={{transform: shake(t, [16.52], 10, 2)}}><Grade mode="autumn"><A id={t < 16.52 - E ? 6 : 7} s={1.06} /></Grade></Fill>
        {t >= 16.52 - E && <Horizon y={925} w={[960 - 1400 * ease(seg(t, 16.52, 16.7)), 960 + 1400 * ease(seg(t, 16.52, 16.7))]} k={1} width={3} glow />}
      </Cut>
      <Flash at={[16.69]} frames={1} color={PAPER} />
      <Vignette k={t > 9.11 && t < 16.25 ? 0.35 : 0.5} />
    </Fill>
  );
};

// 窗光：两块硬边的斜光（手书的平涂），按军鼓一格一格往右挪
const WindowBars: React.FC<{t: number; a: number}> = ({t, a}) => {
  const steps = hitsIn(SNARES, a, t + E).length;
  const x = 260 + steps * 70;
  return (
    <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}>
      {[0, 1].map((i) => <polygon key={i} points={`${x + i * 330},-20 ${x + i * 330 + 230},-20 ${x + i * 330 - 270},1100 ${x + i * 330 - 500},1100`} fill="#f2a764" opacity={0.22} />)}
    </svg>
  );
};

// ================================================================ A1 0:16.73–0:31.97（纸和墨）
const WALK = [8, 9, 10, 11];
export const A1_9: React.FC = () => {
  const t = useT();
  useLyrics();
  return (
    <Fill style={{background: PAPER}}>
      <Cut a={16.73} b={20.56}><Walk1 t={t} /></Cut>
      <Cut a={20.56} b={24.52}><Face2 t={t} /></Cut>
      <Cut a={24.52} b={28.07}><Again3 t={t} /></Cut>
      <Cut a={28.07} b={31.97}><Forget4 t={t} /></Cut>
    </Fill>
  );
};

// ① 纸上一条墨线是地面，她走过去，身后的字一个一个印上去（越走越多）
const Walk1: React.FC<{t: number}> = ({t}) => {
  const a = 16.73, b = 20.56;
  const x = lerp(260, 1540, seg(t, a, b));
  const chars = [...L(1).replace(/\s+/g, '')];
  const pose = cycle(on12(t), WALK, BEAT * 2, a);
  return (
    <Fill>
      <Paper />
      {chars.map((c, i) => {
        const cx = 140 + (i / chars.length) * 1640;
        const k = ease(seg(x, cx + 60, cx + 200));
        const big = /[一-鿿]/.test(c);
        return <span key={i} style={{position: 'absolute', left: cx, top: big ? 110 : 128, font: `700 ${big ? 92 : 70}px var(--mincho)`, color: INK, opacity: k,
          transform: `translateY(${(1 - k) * -18}px)`}}>{c}</span>;
      })}
      <div style={{position: 'absolute', left: 0, top: 838, width: 1920, height: 4, background: INK}} />
      <Pose id={pose} x={x} y={840} s={0.92} />
      <Motes n={12} color={ORANGE} size={9} up={false} sway={120} seed={4} op={0.9} />
    </Fill>
  );
};

// ② 低垂的脸：纸上一个橙色的圆，她在圆前面；字竖着写在左边
const Face2: React.FC<{t: number}> = ({t}) => {
  const a = 20.56, b = 24.52;
  const p = io(seg(t, a, b));
  return (
    <Fill>
      <Paper />
      <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}>
        <circle cx={1180 - 40 * p} cy={430} r={380 + 20 * pulse(KICKS, t, 0.2)} fill={ORANGE} opacity={0.9} />
      </svg>
      <Cam s={1.0 + 0.06 * p} x={240 - 60 * p} oy={1080}><A id={13} y={Math.abs(Math.sin((t - a) * Math.PI / (BEAT * 2))) * -6} /></Cam>
      <KText text={L(2).split('　')[0]} t0={T0(2)} t1={T1(2) - 0.05} x={330} y={110} size={74} vertical enter="type" step={0.09} color={INK} shadow="none" weight={700} />
      <KText text={L(2).split('　')[1] ?? ''} t0={charT(2, 'ひとつ')} t1={T1(2) - 0.05} x={210} y={110} size={74} vertical enter="type" step={0.09} color={INK} shadow="none" weight={700} />
      <Motes n={8} color={ORANGE} size={10} up={false} sway={100} seed={9} op={0.9} />
    </Fill>
  );
};

// ③ "もう一回"一行一行往下叠（每叠一次更大）；"その顔"：想不起的脸，一闪一闪地换，眼睛总被纸条遮住
const Again3: React.FC<{t: number}> = ({t}) => {
  const a = 24.52, b = 28.07;
  const face = charT(3, 'その顔');
  const n = clamp(Math.floor((t - a + E) / (BEAT * 0.5)) + 1, 1, 6);
  const word = L(3).split('　')[0] ?? '';
  const faces = [1036, 1037, 1038, 1039, 1040, 1041, 1042];
  const fi = faces[Math.floor(on12(t) * 6) % faces.length];
  return (
    <Fill>
      <Paper />
      {t < face - E ? (
        Array.from({length: n}, (_, i) => (
          <div key={i} style={{position: 'absolute', left: 120 + i * 18, top: 90 + i * 150, font: `800 ${70 + i * 14}px var(--mincho)`, color: INK, opacity: 0.25 + 0.75 * (i === n - 1 ? 1 : 0.4),
            whiteSpace: 'nowrap'}}>{word}</div>
        ))
      ) : (
        <Fill>
          <Fill style={{opacity: 0.28, WebkitMaskImage: 'radial-gradient(ellipse 600px 420px at 900px 900px, transparent 55%, #000 85%)'}}><A id={fi} style={{filter: 'blur(3px)'}} /></Fill>
          <KText text={L(3).split('　')[1] ?? ''} t0={face} t1={T1(3) - 0.05} x={1660} y={110} size={84} vertical enter="cut" weight={800} color={INK} shadow="none" kanji={1.45} />
        </Fill>
      )}
    </Fill>
  );
};

// ④ 她的背影很小，站着；身后巨大的"思い出せない"，字一个个被擦掉又浮出来
const Forget4: React.FC<{t: number}> = ({t}) => {
  const a = 28.07, b = 31.97;
  const big = [...'思い出せない'];
  return (
    <Fill>
      <Paper />
      {big.map((c, i) => {
        const on = 0.5 + 0.5 * Math.sin((t - a) * 3 + i * 1.7);
        return <span key={i} style={{position: 'absolute', left: 120 + i * 290, top: 300, font: `900 300px var(--mincho)`, color: INK, opacity: 0.06 + 0.16 * on}}>{c}</span>;
      })}
      <Cam s={1 - 0.1 * io(seg(t, a, b))} oy={900}><Pose id={98} x={960} y={900} s={0.42} /></Cam>
      <div style={{position: 'absolute', left: 0, top: 898, width: 1920, height: 3, background: INK}} />
      <KText text={L(4)} t0={T0(4)} t1={31.5} x={220} y={960} size={44} enter="type" step={0.07} drift={[6, 0]} weight={600} color={INK} shadow="none" />
      {/* 电车的光带扫过，接 A2 */}
      <Fill style={{background: `linear-gradient(90deg, transparent, ${ORANGE}, transparent)`, width: 900, transform: `translateX(${-1000 + 3200 * seg(t, 31.45, 31.97)}px)`, opacity: t > 31.45 ? 0.9 : 0}} />
    </Fill>
  );
};

// ================================================================ A2 0:31.97–0:47.21
export const A2_9: React.FC = () => {
  const t = useT();
  useLyrics();
  return (
    <Fill style={{background: '#000'}}>
      <Cut a={31.97} b={34.83}><Globe t={t} /></Cut>
      <Cut a={34.83} b={35.78}><Overpass t={t} /></Cut>
      <Cut a={35.78} b={39.74}><Seawall t={t} /></Cut>
      <Cut a={39.74} b={43.5}><Multiply t={t} /></Cut>
      <Cut a={43.5} b={47.21}><Rain t={t} /></Cut>
    </Fill>
  );
};

// ⑤ 纸上的地球仪：墨线、一圈橙色的环线，小电车绕着跑，太阳从球后升起；字绕着环流
const Globe: React.FC<{t: number}> = ({t}) => {
  const a = 31.97, b = 34.83;
  const cx = 960, cy = 560, R = 330;
  const rot = (t - a) * 0.9;
  const sun = ease(seg(t, a, b));
  const ring = (k: number): [number, number] => [cx + Math.cos(k) * R * 1.32, cy + Math.sin(k) * R * 0.42];
  const k = -Math.PI / 2 + (t - a) * 1.6;
  const [tx, ty] = ring(k), [nx, ny] = ring(k + 0.02);
  const front = Math.sin(k) > -0.15;
  const zoom = 1 + 2.4 * Math.pow(seg(t, 34.2, b), 2);
  return (
    <Fill>
      <Paper />
      <Cam s={zoom} ox={tx} oy={ty}>
        <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}>
          <circle cx={cx} cy={cy + 300 - 520 * sun} r={170} fill={ORANGE} />
          <circle cx={cx} cy={cy} r={R} fill={PAPER} stroke={INK} strokeWidth={3} />
          {Array.from({length: 6}, (_, i) => {
            const ph = ((i / 6) * Math.PI + rot) % Math.PI;
            return <ellipse key={i} cx={cx} cy={cy} rx={Math.abs(Math.cos(ph)) * R} ry={R} fill="none" stroke={INK} strokeWidth={1.5} opacity={0.45} />;
          })}
          {[-0.6, -0.3, 0, 0.3, 0.6].map((l, i) => <ellipse key={`l${i}`} cx={cx} cy={cy + l * R} rx={Math.sqrt(1 - l * l) * R} ry={Math.sqrt(1 - l * l) * R * 0.18} fill="none" stroke={INK} strokeWidth={1.5} opacity={0.4} />)}
          <ellipse cx={cx} cy={cy} rx={R * 1.32} ry={R * 0.42} fill="none" stroke={ORANGE} strokeWidth={5} />
        </svg>
        <Ribbon id="ring5" d={`M ${cx - R * 1.32} ${cy} A ${R * 1.32} ${R * 0.42} 0 1 0 ${cx + R * 1.32} ${cy} A ${R * 1.32} ${R * 0.42} 0 1 0 ${cx - R * 1.32} ${cy}`}
                text={L(5)} t0={a} speed={-120} size={34} color={INK} glow="rgba(0,0,0,0)" repeat={2} weight={700} />
        <img src={src(24)} style={{position: 'absolute', left: tx - 70, top: ty - 9, width: 140, height: 18, opacity: front ? 1 : 0.35,
          transform: `rotate(${Math.atan2(ny - ty, nx - tx) * 180 / Math.PI}deg)`}} />
      </Cam>
    </Fill>
  );
};

const Overpass: React.FC<{t: number}> = ({t}) => {
  const a = 34.83, b = 35.78;
  return (
    <Fill>
      <Grade mode="autumn" extra="saturate(1.3)">
        <Cam s={1.3 - 0.25 * ease(seg(t, a, a + 0.5))}><A id={25} /></Cam>
        <Fill style={{transform: `translateX(${-1900 + 3000 * seg(t, a, b)}px)`, filter: 'blur(1.5px)'}}><A id={24} /></Fill>
        <A id={cycle(on12(t), [21, 22, 23], 0.6)} />
      </Grade>
    </Fill>
  );
};

// ⑥ 海堤：天一小节暗一档，她逆着电车的方向走
const Seawall: React.FC<{t: number}> = ({t}) => {
  const a = 35.78, b = 39.74;
  const dark = Math.floor(seg(t, a, b) * 4 + 1e-6) / 4;
  const x = lerp(1300, 760, seg(t, a, b));
  return (
    <Fill>
      <Grade mode="autumn">
        <Cam s={1.08} x={30 * seg(t, a, b)}><A id={29} /><A id={30} style={{opacity: dark}} /></Cam>
        <Horizon y={598} k={0.6} color="#f3e2c8" width={1.5} />
        <Pose id={cycle(on12(t), [26, 27, 28], BEAT * 1.5, a)} x={x} y={1000} s={0.95} flip />
      </Grade>
      <Motes n={30} color="#e9eef7" size={2} area={[0, 0, 1920, 520]} op={0.5 * dark} seed={12} speed={0.2} />
      <KText text={L(6).split('　')[0]} t0={T0(6)} t1={T1(6) - 0.1} x={140} y={140} size={52} drift={[-8, 0]} />
      <KText text={L(6).split('　')[1] ?? ''} t0={charT(6, '望')} t1={T1(6) - 0.1} x={140} y={240} size={52} drift={[-8, 0]} color="#cfd8ea" />
    </Fill>
  );
};

// ⑦ 何万回：纸上的格子，每格一个在走的她，一拍翻倍 1 → 4 → 16 → 64
const Multiply: React.FC<{t: number}> = ({t}) => {
  const a = 39.74;
  const i = clamp(Math.floor((t - a + E) / BEAT), 0, 7);
  const n = [1, 1, 2, 2, 4, 4, 8, 8][i];
  const w = 1920 / n, h = 1080 / n;
  const pop = 1 + 0.08 * Math.exp(-((t - a + E) % BEAT) / 0.08);
  return (
    <Fill>
      <Paper />
      {Array.from({length: n * n}, (_, k) => {
        const col = k % n, row = Math.floor(k / n);
        const pose = WALK[(Math.floor(on12(t) * 12 / 3) + k) % 4];
        return (
          <React.Fragment key={k}>
            {n > 1 && <div style={{position: 'absolute', left: col * w, top: row * h, width: w, height: h, border: `${Math.max(1, 4 / n * 2)}px solid ${INK}`, boxSizing: 'border-box', opacity: 0.5}} />}
            <Pose id={pose} x={col * w + w / 2} y={row * h + h * 0.88} s={(0.9 / n) * pop} flip={(k + row) % 2 === 1} />
          </React.Fragment>
        );
      })}
      <KText text={L(7)} t0={T0(7)} t1={T1(7) - 0.05} x={130} y={420} size={104} enter="type" step={0.1} drift={[0, 0]} weight={900} wrap={1660}
             color={ORANGE} shadow={`0 0 0 ${PAPER}, 4px 4px 0 ${INK}`} />
      <Flash at={[43.3]} frames={1} color={INK} />
    </Fill>
  );
};

// ⑧ 雨：仰头闭眼（整张画，这里要说话）；后半句的字一个个熄灭，画面跟着暗下去
const Rain: React.FC<{t: number}> = ({t}) => {
  const a = 43.5, b = 47.21;
  const half = charT(8, '聞');
  const dim = seg(t, half, b);
  return (
    <Fill>
      <Grade mode="night" extra={`brightness(${1 - 0.6 * dim})`}><Cam s={1.04 + 0.07 * seg(t, a, b)}><A id={35} /></Cam></Grade>
      <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}>
        {Array.from({length: 110}, (_, i) => {
          const d = 0.4 + 0.3 * rnd(i * 2), p = ((t + rnd(i * 3) * d) % d) / d;
          const x = rnd(i) * 2100 - 80 * p, y = -80 + 1250 * p;
          return <line key={i} x1={x} y1={y} x2={x - 7} y2={y + 48} stroke="rgba(210,225,245,.5)" strokeWidth={1.6} />;
        })}
      </svg>
      <KText text={L(8).split('　')[0]} t0={T0(8)} t1={half - 0.1} x={1180} y={180} size={58} vertical exit="blur" />
      <KText text={L(8).split('　')[1] ?? ''} t0={half} t1={46.9} x={1030} y={180} size={50} vertical exit="chars" color="#c9d3e3" />
      <Vignette />
    </Fill>
  );
};
void Letterbox; void Scene3D; void Plane; void near; void blurAt; void rnd; void KICKS;
