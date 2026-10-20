// CSS 动画照常写 @keyframes，但由时刻 t 驱动：动画暂停住，用负的 animation-delay 把它拨到 (t - start) 那一刻。
// 这样开发时（跟着音频播）和出片时（Remotion 逐帧、乱序渲染）看到的是同一帧，动画可以随意拖动。
// 过渡效果同理：写成一段 @keyframes，用 play() 在某个时刻触发。
import type {CSSProperties} from 'react';

type Opts = {ease?: string; iter?: number | 'infinite'; fill?: 'both' | 'forwards' | 'backwards' | 'none'; dir?: 'normal' | 'reverse' | 'alternate'};

export function play(name: string, start: number, dur: number, t: number, o: Opts = {}): CSSProperties {
  return {
    animationName: name,
    animationDuration: `${dur}s`,
    animationTimingFunction: o.ease ?? 'linear',
    animationDelay: `${(start - t).toFixed(4)}s`,
    animationPlayState: 'paused',
    animationFillMode: o.fill ?? 'both',
    animationIterationCount: o.iter ?? 1,
    animationDirection: o.dir ?? 'normal',
  };
}

// 一拍二版本：时间先取整到 12 张/秒，再拨动画（手书的顿挫感）
export const playStep = (name: string, start: number, dur: number, t: number, o: Opts = {}) =>
  play(name, start, dur, Math.floor(t * 12 + 1e-6) / 12, o);
