// 空当：一条轨道里两个对象之间没有东西的时间。
// 画布上在空当里画一条标尺 |— 3.000 —|，写出长度（位数按轴的精度），AI 看截图不用再拿前后两个对象去算；
// 第一个对象之前、最后一个之后不算空当，不画。"此刻"面板另外写出播放头落在哪种空里
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

// 一条轨道里对象之间的空当（几个小行合起来算：任何一个小行有对象就不算空）。
// 只看有时长的对象：瞬间对象（小节线、卡点这类标记）之间的距离不是"空着"，标出来只会刷满一条轨道。
// min：短于它的不算（按轴精度的一半，免得浮点误差画出 0.000 的空当）
export function trackGaps(items: {begin: number; end: number}[], min = 1e-9): {from: number; to: number}[] {
  const sorted = items.filter((it) => it.end > it.begin).sort((p, q) => p.begin - q.begin || p.end - q.end);
  const out: {from: number; to: number}[] = [];
  let cursor = -Infinity;
  for (const it of sorted) {
    if (cursor !== -Infinity && it.begin - cursor >= min) out.push({from: cursor, to: it.begin});
    cursor = Math.max(cursor, it.begin, it.end);
  }
  return out;
}

// 轴精度 → 小数位数：精度写成小数要几位就是几位（0.001 → 3，0.25 → 2，1 → 0）；
// 写不尽的（1/24 秒）按数量级取；没有精度时返回 null（按需要的位数写，最多 3 位）
export function decimalsOf(precision: unknown): number | null {
  const p = Number(precision);
  if (!isFinite(p) || p <= 0) return null;
  for (let k = 0; k <= 6; k++) if (Math.abs(p * 10 ** k - Math.round(p * 10 ** k)) < 1e-9 * 10 ** k) return k;
  return Math.max(0, Math.ceil(-Math.log10(p)));
}

export const fmtLength = (d: number, decimals: number | null) => (decimals == null ? String(+d.toFixed(3)) : d.toFixed(decimals));
