import {tr as defaultTranslate, translator} from '../i18n/core';
import type {Translate, Locale} from '../i18n/types';
// 插件的纯计算，单独放着好测试：清单和已经载入的插件对一遍（registry.ts）
import type {PluginRow} from '../types';

// 清单里开着、没问题的（有 url）才要；url 变了（插件文件改过）就拿下来重新载入
export function plan(rows: PluginRow[], current: Map<string, {url: string}>) {
  const wanted = rows.filter((r) => r.url);
  const drop = [...current].filter(([name, item]) => !wanted.some((r) => r.name === name && r.url === item.url)).map(([name]) => name);
  const load = wanted.filter((r) => !current.has(r.name) || drop.includes(r.name));
  return {wanted, drop, load};
}

// 目标不可用时保留目标并解释原因，不把一次插件截图悄悄改成画布。
export function targetProblem(name: string, slot: 'page' | 'side', rows: PluginRow[], loaded: {name: string; page?: unknown; side?: unknown}[], errors: Record<string, string>, tr: Translate = defaultTranslate) {
  if (slot === 'page' && name === 'canvas' || slot === 'side' && ['now', 'changes', 'notes', 'walk'].includes(name)) return null;
  const row = rows.find((r) => r.name === name);
  if (!row) return tr("plugin.notInstalled", {value1: name});
  if (!row.on) return tr("plugin.disabled", {value1: name});
  if (row.problem) return tr("plugin.unavailable", {value1: name, value2: row.problem});
  if (errors[name]) return tr("plugin.loadFailed", {value1: name, value2: errors[name]});
  const plugin = loaded.find((p) => p.name === name);
  if (!plugin?.[slot]) return tr("plugin.missingSlot", {value1: name, value2: slot});
  return null;
}
