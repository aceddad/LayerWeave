// 批注：视图工具登记的批注层（configs/layers/note.toml）里的对象，一层就是一个有序列表；指向另一条批注的就是回复，回复成楼
import type {Ref} from '../types';
import type {Model} from './model';

export interface Note {
  id: number; index: number; text: string; author: string; status: 'open' | 'done';
  span: {begin: number; end: number} | null; targets: Ref[]; replyTo: number | null; thread: number;
}
export interface Thread { top: Note; replies: Note[] }

export const sameRef = (ref: Ref, kind: Ref['kind'], id: number, project: number) => ref.kind === kind && ref.project === project && ref.id === id;

export function noteList(model: Model): Note[] {
  const project = model.project;
  const list: Note[] = model.data.layers.filter((l) => l.role === 'note').flatMap((l) => l.objects)
    .sort((p, q) => p.begin - q.begin || p.id - q.id)
    .map((o) => ({
      id: o.id, index: o.begin, text: o.information?.text ?? '', author: o.information?.author || '',
      status: o.information?.status === 'done' ? 'done' : 'open', span: o.information?.span || null,
      targets: model.data.binds.filter((b) => sameRef(b.source, 'object', o.id, project)).map((b) => b.target),
      replyTo: null, thread: o.id,
    }));
  const byId = new Map(list.map((n) => [n.id, n]));
  for (const n of list) n.replyTo = n.targets.find((t) => t.kind === 'object' && t.project === project && byId.has(t.id))?.id ?? null;
  for (const n of list) {                                 // 顺着回复往上找到楼主
    let top = n;
    const seen = new Set<number>();
    while (top.replyTo != null && !seen.has(top.id)) { seen.add(top.id); top = byId.get(top.replyTo)!; }
    n.thread = top.id;
  }
  return list;
}

// 按楼分组：楼主在前，回复按写的先后；楼主的状态代表整楼
export function noteThreads(list: Note[]): Thread[] {
  const groups = new Map<number, Note[]>();
  for (const n of list) {
    if (!groups.has(n.thread)) groups.set(n.thread, []);
    groups.get(n.thread)!.push(n);
  }
  return [...groups.values()].map((group) => ({top: group.find((n) => n.id === n.thread) ?? group[0], replies: group.filter((n) => n.id !== n.thread)}));
}

// 待处理的楼主按"指向谁"建索引（object:16、layer:5），画布上的 💬 标记用；回复指向批注，不算
export function noteIndex(threads: Thread[], project: number): Map<string, Thread[]> {
  const index = new Map<string, Thread[]>();
  for (const th of threads) {
    if (th.top.status !== 'open') continue;
    for (const t of th.top.targets) {
      if (t.project !== project) continue;
      const key = `${t.kind}:${t.id}`;
      if (!index.has(key)) index.set(key, []);
      index.get(key)!.push(th);
    }
  }
  return index;
}

// 已读：{楼主编号: {名字: 读到的最后一条批注编号}}，存在视图自己的表 view_note。每个人各记各的；楼里后来又有人写了新的一条，就又算没读
export type NoteReads = Record<string, Record<string, number>>;
export const lastOf = (th: Thread) => th.replies[th.replies.length - 1] ?? th.top;
const newestId = (th: Thread) => Math.max(th.top.id, ...th.replies.map((r) => r.id));
export const readBy = (th: Thread, name: string, reads: NoteReads | undefined) =>
  (reads?.[String(th.top.id)]?.[name.trim()] ?? 0) >= newestId(th);

// 等 name 的楼：还没处理、最后一句不是 name 说的，name 也没在最后一条之后标过已读（和 view_note --waiting 同一条规则）
export const waitingFor = (threads: Thread[], name: string, reads?: NoteReads) =>
  threads.filter((th) => th.top.status === 'open' && lastOf(th).author !== name.trim() && !readBy(th, name, reads));
