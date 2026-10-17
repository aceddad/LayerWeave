import {ui, tr, useI18n} from '../i18n';
// 载入插件：问视图服务本机清单里有哪些（/api/plugins），开着的一个个 import()，把 host 交给它，登记返回的 ViewPlugin。
// 清单改了（顶栏「插件」小窗、view_plugin 命令）就再对一遍：新开的载入，关掉、去掉的拿下来、样式跟着拿掉，不用刷新页面。
// 一个插件载入失败只记下原因、提示一句，不影响别的插件和视图本身；没有任何插件时视图照常工作
import {api} from '../api';
import {kindOf} from '../model/kinds';
import type {Model} from '../model/model';
import {getState, setState} from '../store';
import {toast} from '../sync';
import type {Board, PluginList} from '../types';
import {makeHost} from './host';
import type {LoadedPlugin, PluginFactory, ViewPlugin} from './host';
import {plan, targetProblem} from './plan';
import {CAPTURE} from '../params';
import {currentLocale, useLocale} from '../i18n/store';
import type {Localizations} from '../i18n/types';

interface Loaded { url: string; plugin: LoadedPlugin; localizations: Localizations; dispose: () => void }
const loaded = new Map<string, Loaded>();
let queue: Promise<void> = Promise.resolve();
let first: Promise<void> | null = null;

// 页面启动时载入一次
export function loadPlugins(): Promise<void> {
  first ??= refreshPlugins();
  return first;
}

// 按清单再对一遍；一次只对一遍，后来的排在后面
export function refreshPlugins(): Promise<void> {
  queue = queue.then(sync, sync);
  return queue;
}

async function sync() {
  let list: PluginList;
  try { list = await api.plugins(); } catch (error) {
    if (CAPTURE) window.__layerweaveError = tr("plugin.listFailed") + String(error);
    return;
  }
  const {wanted, drop, load} = plan(list.plugins, loaded);
  for (const name of drop) { loaded.get(name)!.dispose(); loaded.delete(name); }
  const errors: Record<string, string> = {};
  const before = getState().pluginErrors;
  for (const row of load) {
    const styles: HTMLStyleElement[] = [];
    try {
      const mod = await import(/* @vite-ignore */ row.url!) as {default?: PluginFactory};
      if (typeof mod.default !== 'function') throw new Error(tr("plugin.noFactory"));
      const plugin = mod.default(makeHost(styles, row.localizations));
      if (!plugin?.label) throw new Error(tr("plugin.noLabel"));
      loaded.set(row.name, {url: row.url!, plugin: {...plugin, name: row.name}, localizations: row.localizations ?? {}, dispose: () => styles.forEach((el) => el.remove())});
    } catch (error) {
      styles.forEach((el) => el.remove());
      errors[row.name] = tr("plugin.importFailed") + ((error as Error).message || String(error));
      if (before[row.name] !== errors[row.name]) toast(ui("plugin.problem", {value1: row.name, value2: errors[row.name]}), 6000);
    }
  }
  for (const row of wanted) if (!loaded.has(row.name) && !errors[row.name] && before[row.name]) errors[row.name] = before[row.name];
  const plugins = wanted.map((r) => localizedPlugin(loaded.get(r.name))).filter((p): p is LoadedPlugin => !!p);
  const s = getState(), view = list.aliases[s.view] ?? s.view, side = list.aliases[s.side] ?? s.side;
  const problem = targetProblem(view, 'page', list.plugins, plugins, errors, tr) ?? targetProblem(side, 'side', list.plugins, plugins, errors, tr);
  if (CAPTURE && problem) { window.__layerweaveError = problem; window.__layerweaveReady = false; }
  setState({plugins, pluginList: list, pluginErrors: errors, view, side});
}

function localizedPlugin(entry?: Loaded): LoadedPlugin | undefined {
  if (!entry) return undefined;
  const display = {...entry.localizations.zh?.display, ...entry.localizations[currentLocale()]?.display};
  return {...entry.plugin, label: display.label ?? entry.plugin.label, title: display.title ?? entry.plugin.title};
}

// Keep factories, component identities and styles intact; only publish display metadata.
useLocale.subscribe(() => {
  setState({plugins: getState().plugins.map((p) => localizedPlugin(loaded.get(p.name)) ?? p)});
});

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
