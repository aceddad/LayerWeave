// v9 · A3、B2、副歌二（1:31–2:22）
import React from 'react';
import {useT} from '../core/clock';
import {KICKS, pulse} from '../core/time';
import {A, BEAT, CREAM, Cam, Cut, Dots, E, Fill, Flash, Field, Glow, Grade, Hole, KText, L, Motes, Plane, Rays, Ribbon, Scene3D, T0, T1, Vignette,
  charT, clamp, ease, io, lerp, near, on12, rnd, seg, stem, useLyrics} from './kit';
import {GlyphWord} from './GlyphWord';
import {Pose, SING_34, SING_FRONT, Sing, breath} from './parts';
import LIGHT from '../data/glyph_light.json';
import HT54 from '../data/ht_0054.json';

type GData = Parameters<typeof GlyphWord>[0]['data'];
const GL = LIGHT as unknown as GData;
const OBJ = [71, 68, 65, 67, 69, 70, 72, 66];      // 门票、票根、折扇、照片背面、腕带、贝壳、饮料杯、外套

// ================================================================ A3 1:31.02–1:46.26（房间，夜，甜甜圈）
export const A3_9: React.FC = () => {
  const t = useT();
  useLyrics();
  return (
    <Fill style={{background: '#000'}}>
      <Cut a={91.02} b={94.84}><Donut18 t={t} /></Cut>
      <Cut a={94.84} b={98.84}><Lift19 t={t} /></Cut>
      <Cut a={98.84} b={102.64}><Through20 t={t} /></Cut>
      <Cut a={102.64} b={106.26}><Gap21 t={t} /></Cut>
      <Vignette k={0.6} />
    </Fill>
  );
};

// ⑱ 桌上的甜甜圈，手伸进来；沿着洞画一圈虚线，想"只把洞切下来"——切下来的那块只是桌面，原地留下一个真的黑洞
const Donut18: React.FC<{t: number}> = ({t}) => {
  const a = 91.02, b = 94.84;
  const hc = [680, 490], hr = [62, 46];
  const c0 = charT(18, '穴を穴'), c1 = c0 + 0.9;
  const draw = seg(t, c0, c1);
  const lift = ease(seg(t, c1, c1 + 0.8));
  const hand = ease(seg(t, a + 0.2, a + 1.6));
  const circ = Math.PI * (hr[0] + hr[1]);
  return (
    <Fill>
      <Grade mode="night" extra="brightness(1.15) saturate(.9)">
        <Cam s={1.12 + 0.1 * io(seg(t, a, b))} ox={680} oy={500}>
          <A id={57} />
          {/* 切下来以后：原地是真的黑洞 */}
          {lift > 0 && <Hole cx={hc[0]} cy={hc[1]} r={hr[0]} ry={hr[1]}><Fill style={{background: '#000'}} /></Hole>}
          {lift > 0 && (
            <Fill style={{transform: `translate(${240 * lift}px, ${-190 * lift}px) rotate(${-14 * lift}deg) scale(${1 + 0.15 * lift})`, transformOrigin: `${hc[0]}px ${hc[1]}px`,
              filter: `drop-shadow(0 ${30 * lift}px ${20 * lift}px rgba(0,0,0,.7))`}}>
              <Hole cx={hc[0]} cy={hc[1]} r={hr[0]} ry={hr[1]}><A id={57} style={{filter: 'brightness(1.4)'}} /></Hole>
              <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}><ellipse cx={hc[0]} cy={hc[1]} rx={hr[0]} ry={hr[1]} fill="none" stroke="#fff4e0" strokeWidth={2.5} strokeDasharray="10 8" /></svg>
            </Fill>
          )}
          <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}>
            {draw > 0 && lift < 1 && <ellipse cx={hc[0]} cy={hc[1]} rx={hr[0] + 3} ry={hr[1] + 3} fill="none" stroke="#fff4e0" strokeWidth={2.5} strokeDasharray="10 8"
              strokeDashoffset={0} pathLength={circ} style={{strokeDasharray: `${circ * draw} ${circ}`}} opacity={1 - lift} />}
          </svg>
          <Fill style={{transform: `translate(${lerp(700, 120, hand)}px, ${lerp(300, 40, hand)}px)`}}><A id={56} /></Fill>
        </Cam>
      </Grade>
      <KText text={L(18).split('　')[0]} t0={T0(18)} t1={c0 - 0.05} x={1100} y={150} size={52} drift={[0, -4]} />
      <KText text={L(18).split('　')[1] ?? ''} t0={c0} t1={T1(18) - 0.1} x={1100} y={250} size={52} drift={[0, -4]} />
    </Fill>
  );
};

// ⑲ 举起甜甜圈：胸前 → 举起 → 透过洞看（三张，落在拍上，换张时往上一抬）
const Lift19: React.FC<{t: number}> = ({t}) => {
  const a = 94.84, b = 98.84;
  const k1 = a + BEAT * 2, k2 = a + BEAT * 5;
  const id = t < k1 - E ? 58 : t < k2 - E ? 59 : 60;
  const since = t - (id === 58 ? a : id === 59 ? k1 : k2);
  const up = id === 58 ? 0 : 14 * Math.exp(-since / 0.1);
  return (
    <Fill>
      <Grade mode="night" extra="brightness(1.1)">
        <Fill style={{background: 'radial-gradient(circle 700px at 350px 150px, #3a2a1c 0%, #141824 60%, #0b0e16 100%)'}} />
        <Cam s={1.0 + 0.06 * io(seg(t, a, b))} oy={420} y={up}><A id={id} /></Cam>
      </Grade>
      <Glow x={350} y={150} r={500} color="255,190,120" k={0.25} />
      <KText text={L(19).split('　')[0]} t0={T0(19)} t1={charT(19, '決して') - 0.05} x={1580} y={130} size={50} vertical />
      <KText text={L(19).split('　')[1] ?? ''} t0={charT(19, '決して')} t1={T1(19) - 0.1} x={1480} y={130} size={50} vertical />
    </Fill>
  );
};

// ⑳ 透过洞：画面全是甜甜圈的环，只有洞里是夏天（暖、过曝、在晃）；"その顔"那一下洞里闪过想不起的脸
const Through20: React.FC<{t: number}> = ({t}) => {
  const a = 98.84, b = 102.64;
  const r = 300 + 20 * Math.sin((t - a) * 1.7) + 30 * pulse(KICKS, t, 0.2);
  const face = charT(20, 'その顔');
  const ghost = near(t, [face], 4 / 24);
  const ring = (rr: number) => `M ${960 - rr} 540 A ${rr} ${rr} 0 1 1 ${960 + rr} 540 A ${rr} ${rr} 0 1 1 ${960 - rr} 540`;
  return (
    <Fill style={{background: '#120a06'}}>
      {/* 甜甜圈的环（代码画的巧克力环），撑满画面 */}
      <Fill style={{background: `radial-gradient(circle at 960px 540px, transparent ${r}px, #2a1209 ${r + 6}px, #5a2a14 ${r + 90}px, #3a1a0c ${r + 330}px, #160904 ${r + 700}px)`}} />
      <Hole cx={960 + 14 * Math.sin(t * 3.1)} cy={540 + 10 * Math.cos(t * 2.3)} r={r} soft={4}>
        <Grade mode="heat" extra="brightness(1.25)">
          <Cam s={1.25} x={40 * Math.sin(t * 1.3)} r={3 * Math.sin(t * 0.9)}><A id={49} /></Cam>
          {ghost && <A id={1036} style={{opacity: 0.7, mixBlendMode: 'multiply'}} box={[660, 240, 600, 600]} />}
        </Grade>
        <Motes n={30} color="#fff0c8" size={3} op={0.9} glow seed={81} area={[600, 200, 720, 700]} />
      </Hole>
      <Ribbon id="ring20" d={ring(r + 60)} text={L(20)} t0={a} speed={90} size={40} color="#f6e0c4" glow="rgba(0,0,0,.6)" repeat={2} />
    </Fill>
  );
};

// ㉑ 被子和床的缝：两条横带往中间压，字被压扁在缝里
const Gap21: React.FC<{t: number}> = ({t}) => {
  const a = 102.64, b = 106.26;
  const gap = lerp(1100, 90, io(seg(t, a + 0.4, b - 0.3)));
  return (
    <Fill>
      <Grade mode="night" extra="brightness(1.15)"><Cam s={1.25 + 0.04 * Math.sin(t * 1.6)} ox={680} oy={300}><A id={62} /></Cam></Grade>
      <Fill style={{background: '#0b0f1a', clipPath: `inset(0 0 ${540 + gap / 2}px 0)`, opacity: 0.94}} />
      <Fill style={{background: '#0b0f1a', clipPath: `inset(${540 + gap / 2}px 0 0 0)`, opacity: 0.94}} />
      <KText text={L(21)} t0={T0(21)} t1={T1(21) - 0.1} x={180} y={540 - 50} size={78} drift={[6, 0]} squash={clamp(gap / 220, 0.3, 1)} weight={600} />
    </Fill>
  );
};

// ================================================================ B2 1:46.26–2:03.40（把夏天的东西摆出来，想拼出一个形状）
export const B2_9: React.FC = () => {
  const t = useT();
  useLyrics();
  return (
    <Fill style={{background: '#000'}}>
      <Cut a={106.26} b={114.03}><Lay t={t} /></Cut>
      <Cut a={114.03} b={118.03}><Photo24 t={t} /></Cut>
      <Cut a={118.03} b={123.4}><Shape25 t={t} /></Cut>
      <Flash at={[123.35]} frames={2} />
      <Vignette k={0.6} />
    </Fill>
  );
};

// 物件在地板上的位置（俯拍）
const SPOT: [number, number, number][] = [[520, 300, -12], [1390, 280, 15], [430, 720, 8], [1480, 760, -20], [760, 860, 4], [1180, 880, -6], [300, 500, 20], [1640, 520, -8]];
// ㉒㉓ 俯拍：她跪坐在中间，一拍两拍地落下一件东西（带影子，落地小回弹）；镜头慢慢升高
const Lay: React.FC<{t: number}> = ({t}) => {
  const a = 106.26, b = 114.03;
  const second = t >= T0(23) - E;
  const s = second ? 1.55 - 0.12 * seg(t, T0(23), b) : 1.15 - 0.15 * io(seg(t, a, T0(23)));
  return (
    <Fill>
      <Grade mode="night" extra="brightness(1.25) saturate(.9)">
        <Cam s={s} r={second ? 8 : 0} ox={960} oy={second ? 600 : 540}>
          <A id={63} />
          <Glow x={960} y={500} r={700} color="255,190,120" k={0.35} blend="soft-light" />
          {OBJ.map((id, i) => {
            const at = a + 0.5 + i * BEAT * 2;
            if (t < at - E) return null;
            const k = ease(seg(t, at, at + 0.22));
            const bounce = Math.sin(seg(t, at + 0.22, at + 0.45) * Math.PI) * 0.04;
            const [x, y, r] = SPOT[i];
            return (
              <div key={id} style={{position: 'absolute', left: 0, top: 0, width: 1920, height: 1080, filter: `drop-shadow(${8 + 30 * (1 - k)}px ${10 + 40 * (1 - k)}px ${6 + 20 * (1 - k)}px rgba(0,0,0,.55))`}}>
                <Pose id={id} x={x} y={y} s={(0.16 + (1 - k) * 0.08 + bounce) * (id === 66 ? 1.4 : 1)} anchor="center" style={{transform: `rotate(${r}deg)`, opacity: 0.4 + 0.6 * k}} />
              </div>
            );
          })}
          <Pose id={64} x={960} y={560} s={0.62} anchor="center" />
        </Cam>
      </Grade>
      <KText text={L(22)} t0={T0(22)} t1={T1(22) - 0.1} x={140} y={110} size={46} drift={[5, 0]} />
      <KText text={L(23)} t0={T0(23)} t1={T1(23) - 0.1} x={900} y={950} size={46} drift={[-5, 0]} />
    </Fill>
  );
};

// ㉔ 看过曝的照片：照片的白光一点点吃掉画面
const Photo24: React.FC<{t: number}> = ({t}) => {
  const a = 114.03, b = 118.03;
  const k = io(seg(t, a, b));
  return (
    <Fill>
      <Grade mode="night" extra="brightness(1.1)"><Cam s={1.05 + 0.15 * k} ox={740} oy={590}><A id={73} /></Cam></Grade>
      <Glow x={740} y={590} r={160 + 900 * k} color="255,250,240" k={0.6 + 0.4 * k} />
      <KText text={L(24)} t0={T0(24)} t1={T1(24) - 0.1} x={1500} y={150} size={50} vertical color={k > 0.6 ? '#3a3026' : CREAM} shadow={k > 0.6 ? 'none' : undefined} />
    </Fill>
  );
};

// ㉕ 所有东西排成一个圈，中间空着；光从空里渗出来，越来越亮
const Shape25: React.FC<{t: number}> = ({t}) => {
  const a = 118.03, b = 123.4;
  const gather = io(seg(t, a, a + 1.6));
  const spin = (t - a) * 0.15;
  const light = ease(seg(t, a + 1.2, b));
  return (
    <Fill>
      <Field temp="night" k={0.3} />
      <Grade mode="night" extra="brightness(1.3)"><Cam s={0.95}><A id={63} style={{opacity: 0.55}} /></Cam></Grade>
      <Glow x={960} y={540} r={120 + 700 * light} color="255,215,160" k={0.4 + 0.6 * light} />
      {light > 0.6 && <Rays cx={960} cy={540} n={40} k={(light - 0.6) * 2} r0={150} spin={0.1} />}
      {OBJ.map((id, i) => {
        const ang = (i / OBJ.length) * Math.PI * 2 + spin;
        const [sx, sy] = SPOT[i];
        const x = lerp(sx, 960 + Math.cos(ang) * 330, gather), y = lerp(sy, 540 + Math.sin(ang) * 330, gather);
        return <Pose key={id} id={id} x={x} y={y} s={0.15 * (id === 66 ? 1.3 : 1)} anchor="center"
                     style={{transform: `rotate(${(ang * 180) / Math.PI + 90}deg)`, filter: 'drop-shadow(0 10px 10px rgba(0,0,0,.5))'}} />;
      })}
      <KText text={L(25)} t0={T0(25)} t1={T1(25) + 0.6} x={330} y={900} size={72} enter="type" step={0.11} drift={[0, -4]} weight={700} glow="rgba(255,190,110,.6)" />
      <Fill style={{background: '#fff8ec', opacity: Math.pow(seg(t, 122.2, b), 2)}} />
    </Fill>
  );
};

// ================================================================ 副歌二 2:03.40–2:22.45（热浪更满；东西被卷起来；声音；照片烧掉；泪）
export const Chorus2_9: React.FC = () => {
  const t = useT();
  useLyrics();
  const k = pulse(KICKS, t, 0.12);
  return (
    <Fill style={{background: '#000', transform: `scale(${1 + 0.015 * k})`}}>
      <Cut a={123.4} b={126.66}><Swirl26 t={t} /></Cut>
      <Cut a={126.66} b={131.13}><Voice27 t={t} /></Cut>
      <Cut a={131.13} b={134.26}><Burn28 t={t} /></Cut>
      <Cut a={134.26} b={138.72}><Seats29 t={t} /></Cut>
      <Cut a={138.72} b={142.45}><Tear30 t={t} /></Cut>
      <Vignette k={0.45} />
    </Fill>
  );
};

// ㉖ 她在光里唱，地上摆好的东西被热浪卷起来，绕着她飞（前后有深度）
const Swirl26: React.FC<{t: number}> = ({t}) => {
  const a = 123.4, b = 126.66;
  const up = ease(seg(t, a, a + 1.2));
  const wave = (ph: number, y: number, amp: number) => {
    let d = `M -200 ${y}`;
    for (let x = -200; x <= 2200; x += 60) d += ` L ${x} ${(y + Math.sin(x * 0.005 + ph) * amp).toFixed(1)}`;
    return d;
  };
  const orbit = (i: number, front: boolean) => OBJ.map((id, j) => {
    const ang = (j / OBJ.length) * Math.PI * 2 + (t - a) * 1.4;
    const isFront = Math.sin(ang) > 0;
    if (isFront !== front) return null;
    const x = 960 + Math.cos(ang) * 620, y = lerp(950, 520, up) + Math.sin(ang) * 120 - j * 12;
    const sc = 0.11 * (1 + 0.35 * Math.sin(ang)) * (id === 66 ? 1.3 : 1);
    return <Pose key={`${i}${id}`} id={id} x={x} y={y} s={sc} anchor="center" style={{transform: `rotate(${(t - a) * 200 + j * 40}deg)`, filter: isFront ? undefined : 'blur(2px) brightness(.8)'}} />;
  });
  return (
    <Fill>
      <Field temp="heat" glow={[960, 480]} />
      <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}><circle cx={960} cy={420} r={500} fill="#ffd9a0" opacity={0.85} /></svg>
      <Rays cx={960} cy={400} n={64} k={0.9} spin={0.08} r0={220} />
      <Motes n={120} color="#ffd59a" size={4} op={0.95} glow seed={91} speed={1.8} />
      {orbit(0, false)}
      <Ribbon id="r26" d={wave((t - a) * 1.1, 600, 110)} text={L(26)} t0={a} speed={380} size={64} op={0.9} repeat={3} weight={700} />
      <Cam s={1.06 + 0.06 * io(seg(t, a, b))} oy={1000}><Sing ids={SING_FRONT} y={60} s={breath(t)} origin="960px 1080px" /></Cam>
      {orbit(1, true)}
      <Flash at={[a]} frames={2} />
    </Fill>
  );
};

// ㉗ "声"：一条声波线跟着她的声音起伏，唱到"いつか"以后越来越平，最后只剩一条线
const Voice27: React.FC<{t: number}> = ({t}) => {
  const a = 126.66, b = 131.13;
  const rot = lerp(14, -14, io(seg(t, a, b)));
  const fade = seg(t, charT(27, 'いつか'), b);
  const pts: string[] = [];
  for (let x = 0; x <= 1920; x += 12) {
    const tt = t - (1920 - x) / 1920 * 1.4;
    const v = stem('vocals', tt, 1) * (1 - fade);
    pts.push(`${x},${(820 + Math.sin(x * 0.09 + t * 20) * v * 90 + Math.sin(x * 0.031 - t * 7) * v * 40).toFixed(1)}`);
  }
  const voice = charT(27, '声');
  return (
    <Fill>
      <Field temp="heat" glow={[960 - rot * 20, 460]} />
      <Rays cx={1060} cy={360} n={48} k={0.6} spin={0.05} />
      <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}><circle cx={1060} cy={420} r={420} fill="#ffd9a0" opacity={0.7} /></svg>
      <Cam x={140 + rot * 3} s={breath(t)} oy={1080}><Sing ids={SING_34} y={30} /></Cam>
      <KText text={L(27)} t0={T0(27)} t1={b - 0.1} x={110} y={130} size={60} enter="type" step={0.1} drift={[0, 0]} weight={700} wrap={760} glow="rgba(255,140,40,.6)" />
      <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}>
        <polyline points={pts.join(' ')} fill="none" stroke="#fff3e2" strokeWidth={3} style={{filter: 'drop-shadow(0 0 8px rgba(255,160,60,.9))'}} />
      </svg>
      <KText text="声" t0={voice} t1={b - 0.1} x={1500} y={120} size={260} enter="cut" weight={800} glow="rgba(255,140,40,.8)" kanji={1}
             style={{filter: `blur(${10 * fade}px)`, opacity: 1 - 0.7 * fade}} />
      <Motes n={70} color="#ffd59a" size={4} op={0.85} glow seed={95} speed={1.5} />
    </Fill>
  );
};

// ㉘ バイバイ：抓住飞过的照片（伸手 → 抓住 → 纸边烧起来），烧成火星
const Burn28: React.FC<{t: number}> = ({t}) => {
  const a = 131.13, b = 134.26;
  const i = clamp(Math.floor((t - a + E) / BEAT), 0, 2);
  const boom = charT(28, '永遠');
  return (
    <Fill>
      <Field temp="heat" glow={[1100, 400]} />
      <Grade mode="heat"><Cam s={1.0} x={i === 0 ? 40 * (1 - ease(seg(t, a, a + BEAT))) : 0}><A id={[74, 75, 76][i]} style={{opacity: t > boom + 0.3 ? 1 - seg(t, boom + 0.3, boom + 0.9) : 1}} /></Cam></Grade>
      {i === 2 && <Glow x={1300} y={300} r={300 + 200 * stem('other', t, 2)} color="255,140,50" k={0.9} />}
      <Motes n={160} color="#ffcf8a" size={4} op={1} glow seed={101} burst={{x: 1300, y: 300, at: boom, power: 1.1}} fall={200} style={{opacity: t >= boom - E ? 1 : 0}} />
      <KText text={L(28)} t0={T0(28)} t1={T1(28) - 0.05} x={120} y={760} size={84} enter="type" step={0.09} drift={[0, 0]} weight={800} wrap={1300} glow="rgba(255,140,40,.6)" />
    </Fill>
  );
};

// ㉙ 空会场俯拍（同副歌一的构图），这次网点之间漂着她的东西
const Seats29: React.FC<{t: number}> = ({t}) => {
  const a = 134.26, b = 138.72;
  const data = HT54 as number[][];
  const drift = seg(t, a, b);
  return (
    <Fill style={{background: '#0a0402'}}>
      <Cam s={1.05 - 0.1 * io(drift)}>
        <Dots data={data} color="#ffcf8a" glow fx={(x, y, r, i) => [x + Math.sin(t * 1.5 + i) * 3, y - drift * 40 * rnd(i), r * (0.8 + 0.3 * Math.sin(t * 3 + i * 0.7)), 0.95]} />
        {OBJ.map((id, j) => (
          <Pose key={id} id={id} x={300 + (j % 4) * 440 + Math.sin(t + j) * 30} y={260 + Math.floor(j / 4) * 520 - drift * 120 + Math.cos(t * 0.8 + j) * 20} s={0.09 * (id === 66 ? 1.3 : 1)} anchor="center"
                style={{transform: `rotate(${(t - a) * 25 * (j % 2 ? 1 : -1) + j * 30}deg)`, opacity: 0.9, filter: 'sepia(.5) brightness(1.1)'}} />
        ))}
      </Cam>
      <KText text={L(29).split('　')[0]} t0={T0(29)} t1={charT(29, 'そう思') - 0.05} x={140} y={150} size={84} enter="type" step={0.08} drift={[4, 0]} weight={800} glow="rgba(255,140,40,.5)" />
      <KText text={L(29).split('　')[1] ?? ''} t0={charT(29, 'そう思')} t1={b - 0.1} x={560} y={780} size={84} enter="type" step={0.08} drift={[-4, 0]} weight={800} glow="rgba(255,140,40,.5)" />
    </Fill>
  );
};

// ㉚ 眼里的泪：蓄泪 → 滑下来；光一点点暗下去
const Tear30: React.FC<{t: number}> = ({t}) => {
  const a = 138.72, b = 142.45;
  const fall = charT(30, '出る');
  const dim = seg(t, 140.6, b);
  return (
    <Fill>
      <Grade mode="heat" extra={`brightness(${1 - 0.8 * dim})`}>
        <Cam s={1.04 + 0.08 * io(seg(t, a, b))}><A id={t < fall - E ? 79 : 78} /></Cam>
      </Grade>
      <KText text={L(30).split('　')[0]} t0={T0(30)} t1={charT(30, 'どう') - 0.05} x={1700} y={150} size={62} vertical enter="type" step={0.12} weight={700} />
      <KText text={L(30).split('　')[1] ?? ''} t0={charT(30, 'どう')} t1={b - 0.2} x={140} y={150} size={54} vertical exit="chars" color="#d9d0c4" />
    </Fill>
  );
};
void on12; void Plane; void Scene3D;
