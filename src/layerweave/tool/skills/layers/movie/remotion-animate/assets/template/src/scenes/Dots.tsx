import {AbsoluteFill} from 'remotion';
import {beat, hash, on12, prog} from '../time';
import {Layer, dot, trail} from '../ui/Layer';

// 示例：Canvas 画的几百个点。时间先量化到 12 fps（一拍二），动起来更像手绘；
// 每个点的位置只由 t 和自己的编号决定（hash），同一帧任何时候重画都一样。
const N = 400;

const pos = (i: number, t: number): [number, number] => {
  const a = hash(i) * Math.PI * 2 + t * (0.3 + hash(i + 1) * 0.6);
  const rad = 120 + hash(i + 2) * 380;
  return [960 + Math.cos(a) * rad, 540 + Math.sin(a) * rad * 0.6];
};

export const Dots: React.FC<{t: number}> = ({t}) => {
  const u = on12(t);
  const gather = prog(t, beat(24), beat(28));                           // 最后一小节向中心聚拢
  return (
    <AbsoluteFill style={{background: '#0b0b12'}}>
      <Layer t={u} draw={(c) => {
        for (let i = 0; i < N; i++) {
          const [x, y] = pos(i, u);
          dot(c, x + (960 - x) * gather, y + (540 - y) * gather, 3 + hash(i + 3) * 4, i % 7 ? '#29E0FF' : '#FF2E88', 0.85);
        }
        trail(c, (s) => pos(0, s), u, 0.8, '#FF2E88', 4);
      }}/>
    </AbsoluteFill>
  );
};
