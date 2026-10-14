// 清单和已经载入的插件对一遍：哪些要拿下来、哪些要载入（plugin/registry.ts 用；单独放着好测试）
import type {PluginRow} from '../types';

// 清单里开着、没问题的（有 url）才要；url 变了（插件文件改过）就拿下来重新载入
export function plan(rows: PluginRow[], current: Map<string, {url: string}>) {
  const wanted = rows.filter((r) => r.url);
  const drop = [...current].filter(([name, item]) => !wanted.some((r) => r.name === name && r.url === item.url)).map(([name]) => name);
  const load = wanted.filter((r) => !current.has(r.name) || drop.includes(r.name));
  return {wanted, drop, load};
}
