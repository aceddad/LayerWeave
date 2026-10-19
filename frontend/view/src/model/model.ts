import {tr as defaultTranslate, translator} from '../i18n/core';
import type {Translate, Locale} from '../i18n/types';
// 项目数据加上视图设置以后的"画面模型"：画板分几行几段、每行哪些轨道、对象排在哪个小行、画板多宽多高。
// 全是纯计算，不碰页面；画板的尺寸由数据直接算出来，排版（拼接、拆出、吸附）不需要量页面。
import type {Board, Layer, Obj, ProjectData, Root} from '../types';
import {trackGaps} from './gaps';

export const NAMES = 200, HEAD = 34, RULER = 26, ROW = 46, LANE = 40, PAD = 3, GAP = 48, STRIP = 24, FOLD = 26;

export interface Segment { root: number; offset: number; begin: number; end: number }
export interface Part { layer: Layer; seg: Segment }
export interface Track {
  key: string; parent: string | null; name: string; type: string; tips: string; depth: number;
  parts: Part[]; hasChildren: boolean;
}
export interface Item { o: Obj; layer: Layer; offset: number; begin: number; end: number; lane: number }
// 折叠：人和 AI 各有一份。自己这边折叠的轨道收起它和下面所有的层（fold）；对方折叠的照常画，只标出来（other）
export interface FoldMark { by: string; tips: string }
// layers：收起的全部层编号；below：下面收起了几条轨道；objects：一共几个对象
export interface FoldInfo extends FoldMark { layers: number[]; below: number; objects: number }
export interface TrackLayout { track: Track; height: number; items: Item[]; gaps: {from: number; to: number}[]; fold: FoldInfo | null; other: FoldMark | null }
export interface SectionLayout {
  row: number[]; index: number; segments: Segment[]; tracks: TrackLayout[]; strip: boolean; height: number; top: number;
}
export interface BoardLayout {
  board: Board; key: number; a: number; e: number; pps: number; unit: string; precision: number;
  tracksWidth: number; width: number; height: number; sections: SectionLayout[];
}

export interface ViewOptions {
  viewer?: 'user' | 'ai';                                 // 这个页面算哪一边（缺省是人这边）
  only: Set<number> | null;
  showHidden: boolean;
  canvasWidth: number;
}

export type ObjWithLayer = Obj & {layer: Layer};

export const keyOf = (b: Board) => b.rows[0][0];
export const rootsOf = (b: Board) => b.rows.flat();

// 同一轨道里互相重叠的对象排进不同的小行，免得互相遮住
export function lanes(items: {begin: number; end: number}[]): number[] {
  const ends: number[] = [];
  return items.map((o) => {
    const b = o.begin, e = Math.max(o.end, o.begin);
    let k = ends.findIndex((x) => x <= b + 1e-9 && !(e === b && x === b));
    if (k < 0) { k = ends.length; ends.push(e); } else ends[k] = e;
    return k;
  });
}

export class Model {
  readonly roots = new Map<number, Root>();
  readonly layers = new Map<number, Layer>();
  readonly objects = new Map<number, ObjWithLayer>();
  readonly own = new Map<number, FoldMark>();             // 自己这边折叠的层
  readonly other = new Map<number, FoldMark>();           // 对方折叠的层
  private trackCache = new Map<string, Track[]>();

  constructor(readonly data: ProjectData, readonly opts: ViewOptions, previous?: Model) {
    const sameOptions = previous && previous.project === data.project.id && previous.opts.viewer === opts.viewer &&
      previous.opts.only === opts.only && previous.opts.showHidden === opts.showHidden && previous.opts.canvasWidth === opts.canvasWidth;
    // Model.data 仍是当前完整快照（插件可以读取已读信息）；只换壳时复用整个几何索引。
    if (sameOptions && previous.data.layers === data.layers && previous.data.roots === data.roots && previous.data.folds === data.folds) {
      this.roots = previous.roots; this.layers = previous.layers; this.objects = previous.objects;
      this.own = previous.own; this.other = previous.other;
      this.trackCache = previous.trackCache; this.layoutCache = previous.layoutCache;
      return;
    }
    const me = opts.viewer ?? 'user', them = me === 'user' ? 'ai' : 'user';
    for (const f of data.folds ?? []) {
      if (f[me]) this.own.set(f.layer, {by: f[me], tips: f[`${me}_tips`]});
      if (f[them]) this.other.set(f.layer, {by: f[them], tips: f[`${them}_tips`]});
    }
    for (const r of data.roots) this.roots.set(r.id, r);
    for (const l of data.layers) {
      this.layers.set(l.id, l);
      for (const o of l.objects) this.objects.set(o.id, previous?.layers.get(l.id) === l ? previous.objects.get(o.id)! : {...o, layer: l});
    }
    if (sameOptions) {
      const dirty = new Set<number>();
      const mark = (root: number | null | undefined) => { if (root != null) dirty.add(root); };
      for (const l of [...previous.layers.values(), ...this.layers.values()]) if (previous.layers.get(l.id) !== this.layers.get(l.id)) mark(l.root);
      for (const r of [...previous.roots.values(), ...this.roots.values()]) if (previous.roots.get(r.id) !== this.roots.get(r.id)) dirty.add(r.id);
      const oldFolds = new Map((previous.data.folds ?? []).map((f) => [f.layer, f]));
      const newFolds = new Map((data.folds ?? []).map((f) => [f.layer, f]));
      for (const id of new Set([...oldFolds.keys(), ...newFolds.keys()])) if (oldFolds.get(id) !== newFolds.get(id)) mark(this.layers.get(id)?.root);
      // 行可以左右接续多个根；其中任一根范围变化都会影响后续段的 offset。
      const clean = (key: string) => key.split('@')[0].split(/[|,]/).every((r) => !dirty.has(Number(r)));
      for (const [key, value] of previous.trackCache) if (clean(key)) this.trackCache.set(key, value);
      for (const [key, value] of previous.layoutCache) if (clean(key)) this.layoutCache.set(key, value);
    }
  }

  get project() { return this.data.project.id; }
  root(id: number) { return this.roots.get(id); }
  layer(id: number) { return this.layers.get(id); }
  object(id: number) { return this.objects.get(id); }
  unitOfRoot(id: number | null | undefined) { return (id != null && this.roots.get(id)?.unit) || ''; }
  precisionOf(id: number | null | undefined): number | null {
    const p = id != null ? Number(this.roots.get(id)?.axis?.precision) : NaN;
    return isFinite(p) && p > 0 ? p : null;
  }
  nameOf(id: number, tr: Translate = defaultTranslate) { if (id === 0) return tr("common.orphanLayers"); return this.roots.get(id)?.name || tr("common.layerId", {value1: id}); }
  allObjects() { return [...this.objects.values()]; }

  // 左右接续：第一段不动，后一段的本地 0 接在前一段的结尾（和 Python 的 layout.chain_offsets 一致）
  segments(row: number[]): Segment[] {
    let end: number | null = null;
    return row.map((r) => {
      const [b, e] = this.roots.get(r)?.extent ?? [0, 10];
      const offset = end == null ? 0 : end - Math.min(0, b);
      end = offset + e;
      return {root: r, offset, begin: b + offset, end: e + offset};
    });
  }

  segmentAt(row: number[], t: number): Segment | null {
    const segs = this.segments(row);
    return segs.find((s) => t >= s.begin - 1e-9 && t < s.end) ?? (Math.abs(t - segs[segs.length - 1].end) < 1e-9 ? segs[segs.length - 1] : null);
  }

  extent(b: Board): [number, number] {
    let a = Infinity, e = -Infinity;
    for (const row of b.rows) for (const s of this.segments(row)) { a = Math.min(a, s.begin); e = Math.max(e, s.end); }
    return isFinite(a) ? [a, e > a ? e : a + 10] : [0, 10];
  }

  // 每单位多少像素：缩放过的用存下来的；否则让画板铺满画布宽度
  pps(b: Board): number {
    if (b.tempPps) return b.tempPps;
    if (b.pps) return b.pps;
    const [a, e] = this.extent(b);
    return Math.max(400, this.opts.canvasWidth - NAMES - 90) / Math.max(1e-6, e - a);
  }

  boardHidden(b: Board) {
    return !this.opts.showHidden && rootsOf(b).every((r) => this.layers.get(r)?.hidden);
  }

  // 一行里的轨道：按"从根往下的名字路径"把层合起来；只有一个根时就是原来的层树
  rowTracks(row: number[]): Track[] {
    const cacheKey = row.join(',');
    const cached = this.trackCache.get(cacheKey);
    if (cached) return cached;
    const byKey = new Map<string, Track>(), children = new Map<string, string[]>(), top: string[] = [];
    for (const seg of this.segments(row)) {
      const pathOf = new Map<number, string>(), seen = new Map<string, number>();
      for (const l of this.data.layers) {
        if (l.root !== seg.root) continue;
        let key = '', parent: string | null = null;
        if (l.id !== seg.root) {
          parent = l.father != null && pathOf.has(l.father) ? pathOf.get(l.father)! : '';
          const base = `${parent}/${l.name || l.type}`, n = (seen.get(base) ?? 0) + 1;
          seen.set(base, n);
          key = n > 1 ? `${base}#${n}` : base;             // 同一父层下重名的层按出现次序区分
        }
        pathOf.set(l.id, key);
        let t = byKey.get(key);
        if (!t) {
          const depth = parent == null ? 0 : (byKey.get(parent)?.depth ?? -1) + 1;
          t = {key, parent, name: l.name, type: l.type, tips: l.tips, depth, parts: [], hasChildren: false};
          byKey.set(key, t);
          if (parent == null) top.push(key);
          else { if (!children.has(parent)) children.set(parent, []); children.get(parent)!.push(key); }
        }
        t.parts.push({layer: l, seg});
      }
    }
    const out: Track[] = [];
    const walk = (key: string) => {
      const t = byKey.get(key)!;
      t.hasChildren = children.has(key);
      out.push(t);
      (children.get(key) ?? []).forEach(walk);
    };
    top.forEach(walk);
    if (!byKey.has('')) (children.get('') ?? []).forEach(walk);   // 未归属的层没有根轨道
    this.trackCache.set(cacheKey, out);
    return out;
  }

  // 轨道在自己这边折叠了吗：它合起来的层里有一个折叠了就算（左右接续时，网页上折叠一条轨道会折叠它的每一个层）
  foldOf(t: Track): FoldMark | null {
    for (const p of t.parts) if (this.own.has(p.layer.id)) return this.own.get(p.layer.id)!;
    return null;
  }
  otherFoldOf(t: Track): FoldMark | null {
    for (const p of t.parts) if (this.other.has(p.layer.id)) return this.other.get(p.layer.id)!;
    return null;
  }

  // 画出来的轨道：折叠的轨道还在（画成一条细条），它下面的轨道不画
  visibleTracks(row: number[]): Track[] {
    const hidden = new Set<string>(), out: Track[] = [];
    for (const t of this.rowTracks(row)) {
      if (t.parent != null && hidden.has(t.parent)) { hidden.add(t.key); continue; }
      if (this.opts.only && !t.parts.some((p) => this.opts.only!.has(p.layer.id))) continue;
      if (!this.opts.showHidden && t.parts.every((p) => p.layer.hidden)) continue;
      out.push(t);
      if (this.foldOf(t) != null) hidden.add(t.key);
    }
    return out;
  }

  // 一条轨道下面的所有轨道（按名字路径）
  below(t: Track, row: number[]): Track[] {
    return this.rowTracks(row).filter((x) => (t.key === '' ? x.key !== '' : x.key.startsWith(t.key + '/')));
  }

  trackLayout(track: Track, row: number[]): TrackLayout {
    const mine = this.foldOf(track), other = this.otherFoldOf(track);
    if (mine != null) {
      const under = this.below(track, row), all = [track, ...under].flatMap((t) => t.parts.map((p) => p.layer));
      return {track, height: FOLD, items: [], gaps: [], other,
              fold: {...mine, layers: all.map((l) => l.id), below: under.length, objects: all.reduce((n, l) => n + l.objects.length, 0)}};
    }
    const raw = track.parts.flatMap(({layer, seg}) => layer.objects.map((o) => ({o, layer, offset: seg.offset, begin: o.begin + seg.offset, end: o.end + seg.offset})))
      .sort((p, q) => p.begin - q.begin || p.end - q.end || p.o.id - q.o.id);
    const ln = lanes(raw);
    const items = raw.map((it, i) => ({...it, lane: ln[i]}));
    const n = Math.max(1, ...ln.map((k) => k + 1));
    const gaps = trackGaps(items, (this.precisionOf(row[0]) ?? 1e-6) / 2);
    return {track, height: Math.max(ROW, n * LANE + PAD * 2), items, gaps, fold: null, other};
  }

  // 画板的完整布局；返回 null 表示这块画板现在不画（收起的层、全被过滤掉）。
  // 按"哪几行、每单位多少像素"缓存（按内容，不按数组：拼接时会原地改 rows）：布局和画板摆在哪无关。
  // 拖画板时位置每一帧都变，原来每一帧都重算一遍，几百个格子拿到新的 item 全部重画（拖画板一卡一卡，2026-10-14 量的）。
  // 缓存里的 board 是第一次算时的那份，位置可能已经旧了：要位置去读画板本身
  boardLayout(b: Board): BoardLayout | null {
    const key = `${b.rows.map((r) => r.join(',')).join('|')}@${this.pps(b)}`;
    if (!this.layoutCache.has(key)) {
      if (this.layoutCache.size > 64) this.layoutCache.clear();   // Alt+滚轮缩放时间时每一档都是新的像素比，别一直攒着
      this.layoutCache.set(key, this.computeLayout(b));
    }
    return this.layoutCache.get(key)!;
  }
  private layoutCache = new Map<string, BoardLayout | null>();

  private computeLayout(b: Board): BoardLayout | null {
    if (this.boardHidden(b)) return null;
    const [a, e] = this.extent(b), pps = this.pps(b), tracksWidth = (e - a) * pps + 40;
    const sections: SectionLayout[] = [];
    let top = HEAD + RULER;
    b.rows.forEach((row, index) => {
      const tracks = this.visibleTracks(row).map((t) => this.trackLayout(t, row));
      if (!tracks.length) return;
      const segments = this.segments(row), strip = segments.length > 1;
      const border = sections.length ? 2 : 0;
      const height = (strip ? STRIP : 0) + tracks.reduce((sum, t) => sum + t.height, 0);
      sections.push({row, index, segments, tracks, strip, height, top: top + border});
      top += border + height;
    });
    if (!sections.length) return null;
    // 共享尺子按画板内最细的根轴刻度显示；根自己的写入精度保持不变。
    const precision = Math.min(...rootsOf(b).map((root) => this.precisionOf(root) ?? 1e-6));
    return {board: b, key: keyOf(b), a, e, pps, unit: this.unitOfRoot(keyOf(b)), precision, tracksWidth,
            width: NAMES + tracksWidth + 2, height: top + 2, sections};
  }

  boardOf(boards: Board[], rootId: number | null | undefined) {
    return rootId == null ? undefined : boards.find((b) => rootsOf(b).includes(rootId));
  }

  offsetOf(boards: Board[], rootId: number): number {
    for (const row of this.boardOf(boards, rootId)?.rows ?? []) {
      const s = this.segments(row).find((x) => x.root === rootId);
      if (s) return s.offset;
    }
    return 0;
  }
}

// 找不到根的层（正常情况下核心不允许）放进一块"未归属"画板，不让它们在画布上消失
export function adoptOrphans(data: ProjectData): ProjectData {
  const orphans = data.layers.filter((l) => l.root == null);
  if (!orphans.length) return data;
  const times = orphans.flatMap((l) => l.objects.flatMap((o) => [o.begin, o.end])).filter(Number.isFinite);
  const a = times.length ? Math.min(...times) : 0, e = times.length ? Math.max(...times) : 10;
  return {
    ...data,
    layers: data.layers.map((l) => (l.root == null ? {...l, root: 0} : l)),
    roots: [...data.roots, {id: 0, name: defaultTranslate("common.orphanLayers"), axis: {}, unit: '', key: null, extent: [a, e > a ? e : a + 10]}],
  };
}
