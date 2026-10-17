import {initialLocale, translator, validLocale} from './core';
import {currentLocale, useLocale} from './store';
import type {Locale, Translate, UiMessage} from './types';
export * from './types';
export {currentLocale, useLocale};
const STORAGE = 'layerweave.view.locale';
const translations = {zh: translator('zh'), en: translator('en')};
export const tr: Translate = (key, values) => translations[currentLocale()](key, values);
export function useI18n() {
  const locale = useLocale((s) => s.locale);
  return {locale, t: translations[locale]};
}
export function initializeLocale() {
  const q = new URLSearchParams(location.search);
  let saved = null;
  try { saved = localStorage.getItem(STORAGE); } catch { /* Private browser storage may be unavailable. */ }
  useLocale.setState({locale: initialLocale(q.get('lang'), saved, q.get('capture') === '1')});
  document.documentElement.lang = currentLocale() === 'zh' ? 'zh-CN' : 'en';
}
export function setLocale(locale: Locale) {
  if (!validLocale(locale)) return;
  useLocale.setState({locale});
  document.documentElement.lang = locale === 'zh' ? 'zh-CN' : 'en';
  const url = new URL(location.href);
  url.searchParams.set('lang', locale);
  history.replaceState(history.state, '', url);
  if (url.searchParams.get('capture') !== '1') {
    try { localStorage.setItem(STORAGE, locale); } catch { /* Switching still works for this page. */ }
  }
}
export function renderMessage(message: string | UiMessage): string {
  if (typeof message === 'string') return message;
  const text = tr(message.key, message.values);
  return text + (message.detail ? '\n' + message.detail : '');
}
export function ui(key: string, values?: UiMessage['values'], detail?: string): UiMessage {
  return {key, values, ...(detail ? {detail} : {})};
}
