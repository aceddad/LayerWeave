import {tr as defaultTranslate, translator} from '../i18n/core';
import type {Translate, Locale} from '../i18n/types';
// 时间的写法：单位是秒时写成 分:秒，其他单位（帧、条……）照数字写
export const isSec = (unit?: string | null) =>
  ['秒', 's', 'sec', 'secs', 'second', 'seconds'].includes(String(unit || '').trim().toLowerCase());

export function fmt(t: number | null | undefined, unit = ''): string {
  if (t == null || !isFinite(t)) return '—';
  if (!isSec(unit)) return `${+(+t).toFixed(3)}${unit ? ' ' + unit : ''}`;
  const sign = t < 0 ? '-' : '', a = Math.abs(t), m = Math.floor(a / 60), s = a - m * 60;
  return `${sign}${m}:${s.toFixed(2).padStart(5, '0')}`;
}

export const fmtSpan = (d: number, unit: string, tr: Translate = defaultTranslate) => (isSec(unit) ? tr("time.seconds", {value1: +d.toFixed(2)}) : `${+d.toFixed(3)}${unit ? ' ' + unit : ''}`);

export function ago(iso: string, locale: Locale = 'zh'): string {
  const tr = translator(locale);
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return tr("time.justNow");
  if (s < 3600) return tr("time.minutesAgo", {value1: Math.floor(s / 60)});
  if (s < 86400) return tr("time.hoursAgo", {value1: Math.floor(s / 3600)});
  return new Date(iso).toLocaleString(locale === 'zh' ? 'zh-CN' : 'en', {month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'});
}

const SEC_STEPS = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1800, 3600];
const NUM_STEPS = [0.001, 0.01, 0.1, 1, 10, 100, 1000, 10000, 100000, 1000000].flatMap((m) => [m, 2 * m, 5 * m]);

// 尺子上的刻度：屏幕上相邻两格至少 70 像素
export function ticks(a: number, e: number, pps: number, zoom: number, unit: string): {t: number; x: number; label: string}[] {
  const steps = isSec(unit) ? SEC_STEPS : NUM_STEPS;
  const step = steps.find((s) => s * pps * zoom >= 70) ?? steps[steps.length - 1];
  const out = [];
  for (let i = Math.ceil(a / step); i * step <= e + step; i++) {
    const t = +(i * step).toFixed(6);
    out.push({t, x: (t - a) * pps, label: isSec(unit) ? fmt(t, unit) : String(t)});
  }
  return out;
}
