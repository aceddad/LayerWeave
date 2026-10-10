import {AbsoluteFill} from 'remotion';
import {BAR, PHASE, beat, ease, hit, onBeats, prog, pulse} from '../time';

// 示例：SVG 画的几何图形。圆在每拍上"跳"一下，每小节换一种颜色，第 8 拍时方块从左边滑入。
const COLORS = ['#FF2E88', '#29E0FF', '#FFD23F', '#7CFF6B'];

export const Intro: React.FC<{t: number}> = ({t}) => {
  const r = 120 + 60 * pulse(t);                                       // 每拍一次的脉冲
  const color = COLORS[Math.max(0, Math.floor((t - PHASE) / BAR)) % COLORS.length];
  const slide = ease(prog(t, beat(8), beat(9)));                        // 第 8 拍开始滑入，一拍内到位
  const flash = hit(t, beat(12), 8);                                    // 第 12 拍的一次闪白
  return (
    <AbsoluteFill style={{background: '#111'}}>
      <svg viewBox="0 0 1920 1080" width="100%" height="100%">
        <circle cx={960} cy={540} r={r} fill="none" stroke={color} strokeWidth={14}/>
        <rect x={-300 + slide * 700} y={460} width={160} height={160} fill={color} transform={`rotate(${onBeats(t) * 15} ${-220 + slide * 700} 540)`}/>
      </svg>
      <AbsoluteFill style={{background: '#fff', opacity: flash}}/>
    </AbsoluteFill>
  );
};
