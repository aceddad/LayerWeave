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

export type View = 'canvas' | 'cuts' | 'assets';
export type Side = 'now' | 'changes' | 'notes';
