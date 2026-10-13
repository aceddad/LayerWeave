// 先改画面、再写数据库：已读、已处理、折叠这几种点一下就该有反应的写入，按服务端的规则先在本地改一份。
// 原来要等服务端写完、再把整个项目重读一遍（手书 800 个对象：430–900 毫秒）才变。写失败时重读项目，改回服务端的样子
import type {FoldRow, ProjectData} from '../types';
import type {NoteReads, Thread} from './notes';

// 已读：记下读到楼里最新的一条（和 view_note read 一样）；标为未读：去掉这个人的记录
export function withRead(reads: NoteReads, thread: Thread, reader: string, read: boolean): NoteReads {
  const top = String(thread.top.id), name = reader.trim(), mine = {...(reads[top] ?? {})};
  if (read) mine[name] = Math.max(thread.top.id, ...thread.replies.map((r) => r.id));
  else delete mine[name];
  return {...reads, [top]: mine};
}

// 已处理 / 重新打开：改那条批注的 information.status
export function withNoteStatus(data: ProjectData, noteId: number, status: 'open' | 'done'): ProjectData {
  return {...data, layers: data.layers.map((l) => (l.role !== 'note' || !l.objects.some((o) => o.id === noteId) ? l : {
    ...l, objects: l.objects.map((o) => (o.id === noteId ? {...o, information: {...o.information, status}} : o)),
  }))};
}

// 折叠：和 fold.py 的 set_folds 同一套规则。折叠时已经折着的保留原来的人；没带说明就留着原来的；展开时人和说明一起清掉
export function withFolds(folds: FoldRow[], layers: number[], side: 'user' | 'ai', action: 'fold' | 'unfold' | 'tips', by: string, tips?: string): FoldRow[] {
  const who = by.trim() || (side === 'user' ? '用户' : 'AI');
  const rows = new Map(folds.map((f) => [f.layer, f]));
  for (const layer of layers) {
    const row = rows.get(layer) ?? {layer, user: '', user_tips: '', ai: '', ai_tips: ''};
    const now = {fold: row[side], tips: row[`${side}_tips`]};
    let want = now;
    if (action === 'fold') want = {fold: now.fold || who, tips: (tips ?? (now.fold ? now.tips : '')).trim()};
    else if (action === 'unfold') want = {fold: '', tips: ''};
    else if (now.fold) want = {fold: now.fold, tips: (tips ?? '').trim()};
    rows.set(layer, {...row, [side]: want.fold, [`${side}_tips`]: want.tips});
  }
  return [...rows.values()].filter((f) => f.user || f.ai || f.user_tips || f.ai_tips);
}
