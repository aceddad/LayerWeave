// 播放头落在层里没有对象的地方时，说清楚是哪种空：两个对象之间空着（从哪到哪）、还没开始、已经结束。
// 只在"此刻"面板里写出来，画布上不加标记（空当本来就看得见，缺的是长度和它是中间空还是后面没了）
export type Gap =
  | {kind: 'between'; from: number; to: number}
  | {kind: 'before'; next: number}
  | {kind: 'after'; last: number};

// near：瞬间对象（begin = end）离 t 多近算"在这一刻"，和此刻面板列对象时用的一样
export function gapAt(objects: {begin: number; end: number}[], t: number, near = 0): Gap | null {
  if (!objects.length) return null;                       // 整层没有对象（容器层）：不算空当
  let last = -Infinity, next = Infinity;
  for (const o of objects) {
    if ((o.begin <= t && t < o.end) || (o.begin === o.end && Math.abs(o.begin - t) <= near)) return null;
    if (Math.max(o.begin, o.end) <= t) last = Math.max(last, Math.max(o.begin, o.end));
    if (o.begin > t) next = Math.min(next, o.begin);
  }
  if (last === -Infinity) return {kind: 'before', next};
  if (next === Infinity) return {kind: 'after', last};
  return {kind: 'between', from: last, to: next};
}
