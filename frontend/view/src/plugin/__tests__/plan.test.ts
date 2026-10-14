// 插件清单改了以后页面怎么跟上：新开的载入，关掉、去掉的拿下来，文件改过的换成新的
import {describe, expect, it} from 'vitest';
import {plan} from '../plan';
import type {PluginRow} from '../../types';

const row = (name: string, url?: string, extra: Partial<PluginRow> = {}): PluginRow =>
  ({name, source: 'link', path: `D:/p/${name}.js`, on: !!url, problem: null, about: '', url, ...extra});

describe('插件清单', () => {
  it('第一次：开着的都载入，关着的、有问题的不载入', () => {
    const r = plan([row('cuts', '/plugins/cuts/plugin.js?v=1'), row('off'), row('gone', undefined, {on: true, problem: '找不到文件'})], new Map());
    expect(r.load.map((x) => x.name)).toEqual(['cuts']);
    expect(r.drop).toEqual([]);
  });

  it('关掉、去掉的拿下来；已经载入、没变的不动', () => {
    const now = new Map([['cuts', {url: '/plugins/cuts/plugin.js?v=1'}], ['mine', {url: '/plugins/mine/p.js?v=1'}]]);
    const r = plan([row('cuts', '/plugins/cuts/plugin.js?v=1'), row('mine')], now);
    expect(r.drop).toEqual(['mine']);
    expect(r.load).toEqual([]);
    expect(r.wanted.map((x) => x.name)).toEqual(['cuts']);
  });

  it('插件文件改过（url 的 v 变了）：拿下来再载入新的', () => {
    const r = plan([row('mine', '/plugins/mine/p.js?v=2')], new Map([['mine', {url: '/plugins/mine/p.js?v=1'}]]));
    expect(r.drop).toEqual(['mine']);
    expect(r.load.map((x) => x.url)).toEqual(['/plugins/mine/p.js?v=2']);
  });
});
