import zh from './zh.json';
import en from './en.json';
import type {Locale, MessageValues, Translate} from './types';

export const dictionaries: Record<Locale, Record<string, string>> = {zh, en};
export const validLocale = (value: unknown): value is Locale => value === 'zh' || value === 'en';
export function interpolate(text: string, values: MessageValues = {}): string {
  return text.replace(/\{(\w+)\}/g, (whole, key: string) => Object.hasOwn(values, key) ? String(values[key]) : whole);
}
export function translator(locale: Locale, packs = dictionaries): Translate {
  return (key, values) => interpolate(packs[locale]?.[key] ?? packs.zh?.[key] ?? key, values);
}
export const tr = translator('zh');
export function initialLocale(url: string | null, saved: string | null, capture = false): Locale {
  return validLocale(url) ? url : !capture && validLocale(saved) ? saved : 'zh';
}
