// 插件的纯计算，单独放着好测试：清单和已经载入的插件对一遍（registry.ts）；画布格子找谁来画（ObjectBlock）
import {kindOf} from '../model/kinds';
import type {Obj, PluginRow} from '../types';
import type {BlockPainter, LoadedPlugin} from './host';

// 清单里开着、没问题的（有 url）才要；url 变了（插件文件改过）就拿下来重新载入
export function plan(rows: PluginRow[], current: Map<string, {url: string}>) {
  const wanted = rows.filter((r) => r.url);
  const drop = [...current].filter(([name, item]) => !wanted.some((r) => r.name === name && r.url === item.url)).map(([name]) => name);
  const load = wanted.filter((r) => !current.has(r.name) || drop.includes(r.name));
  return {wanted, drop, load};
}

// 画布格子：先按类型名（o.type）找，再按种类（kindOf）找；都有人认时，清单里排在前面的插件画。
// 按插件列表缓存成两张表，每个格子每次只查一下表（画布上有几百个格子，每次状态变化都会问）
export interface Painter { name: string; painter: BlockPainter }
let cache: {plugins: LoadedPlugin[]; types: Map<string, Painter>; kinds: Map<string, Painter>} | null = null;

export function painterFor(plugins: LoadedPlugin[], o: Obj): Painter | null {
  if (!plugins.length) return null;
  if (cache?.plugins !== plugins) {
    const types = new Map<string, Painter>(), kinds = new Map<string, Painter>();
    for (const p of plugins) {
      if (!p.block || typeof p.block.draw !== 'function') continue;
      const entry = {name: p.name, painter: p.block};
      for (const t of p.block.types ?? []) if (!types.has(t)) types.set(t, entry);
      for (const k of p.block.kinds ?? []) if (!kinds.has(k)) kinds.set(k, entry);
    }
    cache = {plugins, types, kinds};
  }
  return cache.types.get(o.type) ?? cache.kinds.get(kindOf(o)) ?? null;
}
