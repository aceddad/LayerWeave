// 插件清单改了以后页面怎么跟上：新开的载入，关掉、去掉的拿下来，文件改过的换成新的
import {describe, expect, it} from 'vitest';
import {plan, targetProblem} from '../plan';
import type {PluginRow} from '../../types';

const row = (name: string, url?: string, extra: Partial<PluginRow> = {}): PluginRow =>
  ({name, id: name, label: name, source: 'link', path: `D:/p/${name}.js`, on: !!url, problem: null, about: '', url, ...extra});

describe('插件清单', () => {
  it('不可用目标逐项解释，不把插件页面替换成画布', () => {
    expect(targetProblem('alice.demo', 'page', [], [], {})).toContain('未安装');
    expect(targetProblem('alice.demo', 'page', [row('alice.demo')], [], {})).toContain('已关闭');
    expect(targetProblem('alice.demo', 'page', [row('alice.demo', '/new')], [], {'alice.demo': 'JS 错误'})).toContain('加载失败');
    expect(targetProblem('alice.demo', 'page', [row('alice.demo', '/new')], [{name: 'alice.demo', side: {}}], {})).toContain('未提供 page');
    expect(targetProblem('canvas', 'page', [], [], {})).toBeNull();
  });
  it('第一次：开着的都载入，关着的、有问题的不载入', () => {
    const r = plan([row('alice.page', '/plugins/alice.page/a1/plugin.js'), row('alice.off'), row('alice.gone', undefined, {on: true, problem: '找不到文件'})], new Map());
    expect(r.load.map((x) => x.name)).toEqual(['alice.page']);
    expect(r.drop).toEqual([]);
  });

  it('关掉、去掉的拿下来；已经载入、没变的不动', () => {
    const now = new Map([['alice.page', {url: '/plugins/alice.page/a1/plugin.js'}], ['local.mine', {url: '/plugins/local.mine/a1/p.js'}]]);
    const r = plan([row('alice.page', '/plugins/alice.page/a1/plugin.js'), row('local.mine')], now);
    expect(r.drop).toEqual(['local.mine']);
    expect(r.load).toEqual([]);
    expect(r.wanted.map((x) => x.name)).toEqual(['alice.page']);
  });

  it('插件文件改过（资源路径中的修订号变了）：拿下来再载入新的', () => {
    const r = plan([row('local.mine', '/plugins/local.mine/a2/p.js')], new Map([['local.mine', {url: '/plugins/local.mine/a1/p.js'}]]));
    expect(r.drop).toEqual(['local.mine']);
    expect(r.load.map((x) => x.url)).toEqual(['/plugins/local.mine/a2/p.js']);
  });
});
