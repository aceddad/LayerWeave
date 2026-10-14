// 加载插件：问视图服务有哪些（/api/plugins），一个个 import()，把 host 交给它，登记返回的 ViewPlugin。
// 一个插件加载失败只提示一句，不影响别的插件和视图本身；没有任何插件时视图照常工作
import {api} from '../api';
import {kindOf} from '../model/kinds';
import type {Model} from '../model/model';
import {getState, setState} from '../store';
import {toast} from '../sync';
import type {Board} from '../types';
import {makeHost} from './host';
import type {PluginFactory, ViewPlugin} from './host';

let loading: Promise<void> | null = null;
export const pendingPlugins = () => loading;

export function loadPlugins(): Promise<void> {
  loading ??= (async () => {
    let list: {name: string; url: string}[] = [];
    try { list = await api.plugins(); } catch { /* 老的视图服务没有这个接口：当作没有插件 */ }
    const host = makeHost(), plugins: ViewPlugin[] = [];
    for (const item of list) {
      try {
        const mod = await import(/* @vite-ignore */ item.url) as {default?: PluginFactory};
        if (typeof mod.default !== 'function') throw new Error('没有默认导出的函数');
        const plugin = mod.default(host);
        if (!plugin?.name || !plugin.label) throw new Error('返回的插件缺 name 或 label');
        plugins.push(plugin);
      } catch (error) {
        toast(`插件「${item.name}」没有加载上：${(error as Error).message}`, 6000);
      }
    }
    const s = getState();
    // 地址里给的是插件的页面（比如 view=cuts），插件却不在：回到画布
    const known = ['canvas', 'assets', ...plugins.filter((p) => p.page).map((p) => p.name)];
    setState({plugins, view: known.includes(s.view) ? s.view : 'canvas'});
  })();
  return loading;
}

// 项目里有没有这个插件管的对象：没有就不显示它的标签
export function pluginApplies(plugin: ViewPlugin, model: Model | null): boolean {
  if (!plugin.handles?.length || !model) return true;
  const kinds = new Set(plugin.handles);
  return model.allObjects().some((o) => kinds.has(kindOf(o)));
}

// 键盘 [ ]：所有插件给的跳转点合在一起
export function jumpPoints(model: Model, board: Board): number[] {
  const set = new Set<number>();
  for (const p of getState().plugins) for (const t of p.jumpPoints?.(model, board) ?? []) set.add(+t.toFixed(6));
  return [...set].sort((a, b) => a - b);
}
