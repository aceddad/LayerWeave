import {afterEach, describe, expect, it, vi} from 'vitest';
import {dictionaries, initialLocale, interpolate, translator} from '../core';
import {currentLocale, initializeLocale, renderMessage, setLocale, ui, useLocale} from '..';
import {linkQuery} from '../../model/link';
import {fmt, fmtSpan, ago} from '../../model/units';

afterEach(() => { useLocale.setState({locale: 'zh'}); vi.unstubAllGlobals(); });
describe('language resources and state', () => {
  it('keeps authored languages and named placeholders in sync', () => {
    expect(Object.keys(dictionaries.en).sort()).toEqual(Object.keys(dictionaries.zh).sort());
    const names = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort();
    for (const key of Object.keys(dictionaries.zh)) expect(names(dictionaries.en[key]), key).toEqual(names(dictionaries.zh[key]));
  });
  it('substitutes once, keeping user content and replacement syntax literal', () => {
    expect(interpolate('{text}: {count}', {text: '正文 {count} $&', count: 3})).toBe('正文 {count} $&: 3');
    expect(interpolate('{unknown}')).toBe('{unknown}');
  });
  it('falls back within a plugin, never to a host or another plugin', () => {
    const t = translator('en', {zh: {hello: '中文'}, en: {}});
    expect(t('hello')).toBe('中文'); expect(t('common.cancel')).toBe('common.cancel');
  });
  it('uses URL then saved preference then Chinese; capture ignores saved preferences', () => {
    expect(initialLocale('en', 'zh')).toBe('en');
    expect(initialLocale('unknown', 'en')).toBe('en');
    expect(initialLocale(null, 'other')).toBe('zh');
    expect(initialLocale(null, 'en', true)).toBe('zh');
    expect(initialLocale('en', 'zh', true)).toBe('en');
  });
  it('switches without navigating and preserves unrelated link parameters', () => {
    const setItem = vi.fn(), replaceState = vi.fn();
    vi.stubGlobal('location', {href:'http://localhost/?project=7&object=9&step=3f', search:'?project=7&object=9&step=3f'});
    vi.stubGlobal('document', {documentElement: {lang: ''}});
    vi.stubGlobal('localStorage', {getItem: () => 'zh', setItem});
    vi.stubGlobal('history', {state: {marker: 1}, replaceState});
    initializeLocale(); setLocale('en');
    expect(currentLocale()).toBe('en'); expect(document.documentElement.lang).toBe('en');
    expect(setItem).toHaveBeenCalledWith('layerweave.view.locale','en');
    const url = replaceState.mock.calls[0][2] as URL;
    expect(url.searchParams.get('step')).toBe('3f'); expect(url.searchParams.get('lang')).toBe('en');
  });
  it('URL override does not save preference; unavailable storage does not block switching', () => {
    vi.stubGlobal('location', {href:'http://localhost/?lang=en',search:'?lang=en'});
    vi.stubGlobal('document', {documentElement: {lang:''}});
    const setItem = vi.fn(() => {throw Error('disabled');});
    vi.stubGlobal('localStorage', {getItem: () => {throw Error('disabled');}, setItem});
    vi.stubGlobal('history', {state:null,replaceState:vi.fn()});
    initializeLocale(); expect(currentLocale()).toBe('en'); expect(setItem).not.toHaveBeenCalled();
    expect(() => setLocale('zh')).not.toThrow(); expect(currentLocale()).toBe('zh');
  });
  it('renders an existing diagnostic in the current language, preserving raw details', () => {
    const message = ui('error.request', undefined, 'driver: 原始详情');
    expect(renderMessage(message)).toContain('请求未完成');
    useLocale.setState({locale:'en'});
    expect(renderMessage(message)).toBe('The request could not be completed.\ndriver: 原始详情');
  });
  it('includes host language in copied links without accepting a plugin override', () => {
    const query = new URLSearchParams(linkQuery({project:7,view:'alice.demo',side:'now',lang:'en',pluginParams:new URLSearchParams('lang=zh&page=3')}));
    expect(query.get('lang')).toBe('en'); expect(query.get('page')).toBe('3');
  });
  it('does not localize axis interpretation or serialized numbers', () => {
    expect(fmt(65,'秒')).toBe(fmt(65,'s'));
    expect(fmtSpan(.3,'秒',translator('en'))).toBe('0.3 s');
    expect(fmtSpan(.3,'拍',translator('en'))).toBe('0.3 拍');
    expect(ago(new Date().toISOString(),'en')).toBe('Just now');
  });
});
