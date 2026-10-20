// v9 里反复用到的"她"的部件：站位、走路循环、对口型。
import React from 'react';
import type {CSSProperties} from 'react';
import {useT} from '../core/clock';
import {boxOf, mouthAt, src, stem} from './kit';

/** 一张透明图，按"脚底中心"摆：(x, y) 是脚底，s 是缩放 */
export const Pose: React.FC<{id: string | number; x: number; y: number; s?: number; flip?: boolean; style?: CSSProperties; anchor?: 'feet' | 'center'}> =
  ({id, x, y, s = 1, flip, style, anchor = 'feet'}) => {
    const b = boxOf(id);
    const w = b[2] * s, h = b[3] * s;
    return <img src={src(id)} draggable={false}
                style={{position: 'absolute', left: x - w / 2, top: anchor === 'feet' ? y - h : y - h / 2, width: w, height: h,
                  transform: flip ? 'scaleX(-1)' : undefined, ...style}} />;
  };

/** 循环：几张图按周期轮换（一拍二的手感） */
export const cycle = <V,>(t: number, frames: V[], period: number, t0 = 0) =>
  frames[((Math.floor(((t - t0) / period) * frames.length) % frames.length) + frames.length) % frames.length];

/** 对口型：三张嘴（闭、小、大）按人声换，一拍二 */
export const Sing: React.FC<{ids: [string | number, string | number, string | number]; on?: boolean; x?: number; y?: number; s?: number; origin?: string; style?: CSSProperties; lo?: number; hi?: number}> =
  ({ids, on = true, x = 0, y = 0, s = 1, origin = '960px 540px', style, lo, hi}) => {
    const t = useT();
    const m = on ? mouthAt(t, lo, hi) : 0;
    const b = boxOf(ids[m]);
    const o = origin.match(/^(-?[\d.]+)px (-?[\d.]+)px$/);
    return <img src={src(ids[m])} draggable={false}
                style={{position: 'absolute', left: b[0], top: b[1], width: b[2], height: b[3],
                  transformOrigin: o ? `${+o[1] - b[0]}px ${+o[2] - b[1]}px` : origin, transform: `translate(${x}px, ${y}px) scale(${s})`, ...style}} />;
  };
export const SING_FRONT: [string, string, string] = ['0047', 'g047_m1', 'g047_m2'];
export const SING_34: [string, string, string] = ['g050_m0', 'g050_m1', '0050'];
export const SING_FACE: [string, string, string] = ['0055', 'g055_m1', 'g055_m2'];

export const breath = (t: number, amp = 0.006) => 1 + Math.sin(t * 2.2) * amp;
export const vocal = (t: number) => stem('vocals', t, 2);
