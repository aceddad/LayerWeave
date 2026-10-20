// 和本机视图服务说话；接口说明见 view/README.md
import {currentLocale, renderMessage} from './i18n';
import type {UiMessage} from './i18n/types';
import type {Board, ChangeOp, Layout, PluginList, PluginResult, ProjectData, ProjectPage, ProjectSummary, WalkDirection, WalkResult} from './types';

export class ViewApiError extends Error {
  constructor(readonly ui: UiMessage | undefined, fallback: string) {
    super(fallback);
    Object.defineProperty(this, 'message', {get: () => ui ? renderMessage(ui) : fallback});
  }
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) { const data = await response.json().catch(() => ({})); throw new ViewApiError(data.ui, data.error ?? `${path}: ${response.status}`); }
  return response.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new ViewApiError(data?.ui, data?.error ?? `${path}: ${response.status}`);
  return data;
}

export const api = {
  capabilities: () => get<{frames: boolean}>('/api/capabilities'),
  plugins: () => get<PluginList>('/api/plugins'),
  // 插件清单：加链接（target 是路径或默认文件夹里的名字）、去掉、开、关；和 view_plugin 命令改同一份
  plugin: (body: {action: string; target?: string; name?: string; catalog?: string; version?: string; file?: string; files?: boolean}) =>
    post<PluginResult>('/api/plugins', body),
  projects: () => get<ProjectSummary[]>('/api/projects'),
  project: (id: number) => get<ProjectData>(`/api/project/${id}`),
  snapshot: (id: number) => get<ProjectPage>(`/api/project/${id}/snapshot`),
  delta: (id: number, after: number) => get<ProjectPage>(`/api/project/${id}/delta?after=${after}`),
  layout: (id: number) => get<Layout>(`/api/layout/${id}`),
  saveLayout: (id: number, boards: Board[]) => post<Layout & {recorded?: boolean}>(`/api/layout/${id}`, {boards}),
  version: () => get<{version: number; layout: number | string; plugins?: number}>('/api/version'),
  changes: (id: number, limit: number) => get<ChangeOp[]>(`/api/changes/${id}?limit=${limit}`),
  at: (id: number, spans: string[]) => get<{text: string}>(`/api/at/${id}?lang=${currentLocale()}&${spans.map((s) => `span=${encodeURIComponent(s)}`).join('&')}`),
  walk: (id: number, from: string, direction: WalkDirection, depth: number) =>
    get<WalkResult>(`/api/walk/${id}?from=${encodeURIComponent(from)}&direction=${direction}&depth=${depth}`),
  state: (body: unknown) => post('/api/state', body),
  note: (id: number, body: unknown) => post<{error?: string; recorded?: boolean; note?: number}>(`/api/notes/${id}`, body),
  fold: (id: number, body: unknown) => post<{error?: string; recorded?: boolean}>(`/api/folds/${id}`, body),
};

export const thumbUrl = (project: number, objectId: number, width: number) => `/thumb/${project}/${objectId}?w=${width}`;

export const frameUrl = (project: number, objectId: number, at: number | 'end') =>
  `/frame/${project}/${objectId}?t=${at === 'end' ? 'end' : (+at).toFixed(2)}`;
