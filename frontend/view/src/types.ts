// 和 Python 视图服务（view/server.py、data.py）返回的结构一一对应

export type Kind = 'object' | 'layer';

export interface Ref {
  kind: Kind;
  project: number;
  id: number;
}

export interface Bind {
  id: number;
  tips: string;
  source: Ref;
  target: Ref;
}

export interface Media {
  kind: 'image' | 'video' | 'audio' | 'file';
  source: string;
  available: boolean;
  url: string | null;
}

export interface Obj {
  id: number;
  name: string;
  type: string;
  begin: number;
  end: number;
  tips: string;
  text: string | null;
  media: Media | null;
  information: Record<string, any>;
}

export interface Layer {
  id: number;
  name: string;
  type: string;
  father: number | null;
  depth: number | null;
  root: number | null;
  axis: Record<string, any> | null;
  tips: string;
  objects: Obj[];
  role: 'note' | null;
  hidden: boolean;
}

export interface Root {
  id: number;
  name: string;
  axis: Record<string, any>;
  unit: string;
  key: string | null;
  extent: [number, number];
}

export interface ProjectData {
  project: {id: number; name: string; tips: string};
  roots: Root[];
  layers: Layer[];
  binds: Bind[];
  folds?: FoldRow[];   // 折叠：人和 AI 各一份（数据库里视图自己的表 view_layer）
  noteReads?: Record<string, Record<string, number>>;   // 批注的已读：{楼主: {名字: 读到的最后一条}}（视图自己的表 view_note）
}

// 一层的折叠：user / ai 是那一边谁折叠的（空着就是没折叠），tips 是说明
export interface FoldRow {
  layer: number; user: string; user_tips: string; ai: string; ai_tips: string;
}

export interface ProjectSummary {
  id: number;
  name: string;
  tips: string;
}

// 画板：rows 里每一行是左右接续的根；不同行上下拼、同时
export interface Board {
  rows: number[][];
  x: number | null;
  y: number | null;
  pps: number | null;
  tempPps?: number;   // 截图、外部链接临时放大一段时用，不保存
}

export interface Layout {
  boards: Board[];
  serial: number;
}

export interface ChangeRecord {
  name?: string;
  layer?: number;
  begin?: number;
  end?: number;
  text?: string;
  source?: string;
}

export interface ChangeItem {
  kind: 'object' | 'layer' | 'bind' | 'project';
  id: number;
  action: 'create' | 'update' | 'delete';
  before: ChangeRecord | null;
  after: ChangeRecord | null;
  fields?: string[];
  information?: {key: string; before: string | null; after: string | null}[];
}

export interface ChangeOp {
  operation_id: string;
  at: string;
  undo_of: string | null;
  items: ChangeItem[];
}

export type View = string;   // canvas、assets，或某个插件的页面名（比如接缝插件的 cuts）

// 本机插件清单（/api/plugins，view/plugins.py）：内置的在前，然后是链接来的
export interface PluginRow {
  name: string;                    // 清单里的名字，也是页面的 view=
  source: 'builtin' | 'link';
  path: string;                    // js 文件在哪
  on: boolean;
  problem: string | null;          // 有问题就不载入：文件不在、重名、在安装目录里……
  about: string;                   // 内置插件的一句说明
  url?: string;                    // 开着、没问题的才有：页面 import() 它
}
export interface PluginList {
  plugins: PluginRow[];
  file: string;                    // 清单文件在哪
  folder: string;                  // 只写名字的插件放在这个文件夹下面
  problem: string | null;          // 清单本身坏了
}
export type Side = 'now' | 'changes' | 'notes' | 'walk';

// 沿着读（服务端 view/walk.py 的结果）：从起点顺着关联一步步往外走，按步数排好
export type WalkDirection = 'both' | 'out' | 'in';
export interface WalkVia { bind: number; other: string; arrow: 'from' | 'to'; tips: string }
export interface WalkStep {
  ref: string; kind: 'object' | 'layer'; project: number; id: number; depth: number;
  status: 'found' | 'missing' | 'other_project';
  name: string; type: string; layer: {id: number; name: string; type: string} | null; root: number | null; unit: string;
  begin: number | null; end: number | null; text: string | null; source: string | null;
  note: {author: string; status: 'open' | 'done' | null; reply: boolean; span: {begin: number; end: number} | null} | null;
  via: WalkVia[];
}
export interface WalkResult {
  start: string; direction: WalkDirection; depth: number; max_nodes: number;
  steps: WalkStep[]; loops: number; beyond: number; skipped: number; text: string;
}
