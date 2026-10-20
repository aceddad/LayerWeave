import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {chapters} from './fixtures';
import type {ProjectPage} from '../../types';

const settings = vi.hoisted(() => ({record: false}));
vi.mock('../../params', () => ({CAPTURE: false, get RECORD() { return settings.record; }, VIEWER: 'user', numParam: () => null, params: new URLSearchParams()}));
vi.mock('../../camera', () => ({visibleBoards: () => [], visibleRange: () => null, viewport: () => ({x: 0, y: 0, zoom: 1})}));
vi.mock('../../plugin/registry', () => ({refreshPlugins: vi.fn()}));
vi.mock('../../api', () => ({api: {snapshot: vi.fn(), delta: vi.fn(), layout: vi.fn(), version: vi.fn(),
  note: vi.fn(), fold: vi.fn(), changes: vi.fn(), walk: vi.fn(), state: vi.fn(), saveLayout: vi.fn()}}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return {promise, resolve};
}
const flush = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
const snapshot = (id = 1, cursor = 10): ProjectPage => ({mode: 'snapshot', data: {...chapters(), project: {id, name: `p${id}`, tips: ''}}, next_cursor: cursor, has_more: false});

beforeEach(() => {
  vi.resetModules();
  settings.record = false;
  vi.stubGlobal('window', {innerWidth: 1290, innerHeight: 800});
  vi.stubGlobal('localStorage', {getItem: () => null});
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.clearAllMocks(); });

async function setup() {
  const {api} = await import('../../api');
  vi.mocked(api.snapshot).mockImplementation(async (id) => snapshot(id));
  vi.mocked(api.delta).mockImplementation(async (_id, after) => ({mode: 'delta', changes: [], next_cursor: after, has_more: false}));
  vi.mocked(api.layout).mockResolvedValue({boards: [{rows: [[1]], x: 0, y: 0, pps: 20}], serial: 1});
  vi.mocked(api.version).mockResolvedValue({version: 1, layout: 1});
  vi.mocked(api.saveLayout).mockResolvedValue({boards: [], serial: 2});
  vi.mocked(api.state).mockResolvedValue({});
  const sync = await import('../../sync'), store = await import('../../store');
  return {api, sync, store};
}

describe('共享布局写入', () => {
  it('首次自动摆放只更新前端，不悄悄写项目数据库', async () => {
    vi.useFakeTimers(); settings.record = true;
    const {api, sync} = await setup();
    vi.mocked(api.layout).mockResolvedValue({boards: [{rows: [[1]], x: null, y: null, pps: null}], serial: '0:0'});
    await sync.loadProject(1);
    await vi.runOnlyPendingTimersAsync();
    expect(api.saveLayout).not.toHaveBeenCalled();
  });
  it('连续尺寸修改按顺序提交，各请求保留自己的偏好快照', async () => {
    settings.record = true;
    const {api, sync, store} = await setup(); await sync.loadProject(1);
    const first = deferred<{boards: never[]; serial: string}>();
    vi.mocked(api.saveLayout).mockImplementationOnce(() => first.promise);
    const current = store.getState().boards[0];
    store.setState({boards: [{...current, styles: {1: {pps: 20, lane_height: 96}}}]});
    const one = sync.saveLayoutNow(); await flush();
    store.setState({boards: [{...current, styles: {1: {pps: 20, lane_height: 180}}}]});
    const two = sync.saveLayoutNow(); await flush();
    expect(api.saveLayout).toHaveBeenCalledTimes(1);
    first.resolve({boards: [], serial: '1:0'});
    await one; await two;
    expect(api.saveLayout).toHaveBeenCalledTimes(2);
    expect(vi.mocked(api.saveLayout).mock.calls.map((call) => call[1][0].styles?.[1].lane_height)).toEqual([96, 180]);
  });
  it('切换项目会取消前一个项目尚未开始的延迟布局保存', async () => {
    vi.useFakeTimers(); settings.record = true;
    const {api, sync} = await setup(); await sync.loadProject(1);
    sync.saveLayout(300);
    await sync.loadProject(2);
    await vi.advanceTimersByTimeAsync(350);
    expect(api.saveLayout).not.toHaveBeenCalled();
  });
  it('保存失败后通过下一轮读取恢复数据库中的布局', async () => {
    settings.record = true;
    const {api, sync, store} = await setup(); await sync.loadProject(1);
    store.setState({boards: [{...store.getState().boards[0], pps: 100}]});
    vi.mocked(api.saveLayout).mockRejectedValueOnce(new Error('readonly database'));
    await sync.saveLayoutNow();
    expect(store.getState().serial).toBe('reload');
    await sync.poll();
    expect(store.getState().boards[0].pps).toBe(20);
  });
});

describe('真实同步编排的请求竞态', () => {
  it('切换项目后旧快照不能回写，快照请求按序完成', async () => {
    const {api, sync, store} = await setup(), first = deferred<ProjectPage>();
    vi.mocked(api.snapshot).mockImplementationOnce(() => first.promise);
    const one = sync.loadProject(1); await flush();
    const two = sync.loadProject(2); await flush();
    expect(store.getState().project).toBe(2);
    expect(api.snapshot).toHaveBeenCalledTimes(1);
    first.resolve(snapshot(1)); await one; await two;
    expect(store.getState().data?.project.id).toBe(2);
    expect(store.getState().cursor).toBe(10);
  });
  it('轮询单飞，网络失败不推进cursor或version，重试能接着处理', async () => {
    const {api, sync, store} = await setup(); await sync.loadProject(1);
    store.setState({version: 1});
    vi.mocked(api.version).mockResolvedValue({version: 2, layout: 1});
    vi.mocked(api.delta).mockRejectedValueOnce(new Error('offline'));
    await sync.poll();
    expect(store.getState().cursor).toBe(10); expect(store.getState().version).toBe(1);
    const next = deferred<ProjectPage>(); vi.mocked(api.delta).mockImplementationOnce(() => next.promise);
    const one = sync.poll(); await flush(); const two = sync.poll();
    expect(one).toBe(two);
    next.resolve({mode: 'delta', changes: [], next_cursor: 12, has_more: false}); await one;
    expect(store.getState().cursor).toBe(12); expect(store.getState().version).toBe(2);
  });
  it('本地折叠使在途旧增量失效，写入成功前不能覆盖乐观状态', async () => {
    const {api, sync, store} = await setup(); await sync.loadProject(1);
    const read = deferred<ProjectPage>(), write = deferred<{recorded: boolean}>();
    vi.mocked(api.delta).mockImplementationOnce(() => read.promise);
    vi.mocked(api.fold).mockImplementationOnce(() => write.promise);
    const polling = sync.poll(); await flush();
    const folding = sync.foldAction([2], 'fold'); await flush();
    expect(store.getState().data?.folds?.[0]?.user).toBe('用户');
    read.resolve({mode: 'delta', changes: [{kind: 'view_layer', id: 2, after: null}], next_cursor: 11, has_more: false});
    await polling;
    expect(store.getState().cursor).toBe(10);
    expect(store.getState().data?.folds?.[0]?.user).toBe('用户');
    vi.mocked(api.delta).mockResolvedValueOnce({mode: 'delta', changes: [{kind: 'view_layer', id: 2,
      after: {layer: 2, user: '用户', user_tips: '', ai: '', ai_tips: ''}}], next_cursor: 12, has_more: false});
    write.resolve({recorded: true}); expect(await folding).toBe(true);
    expect(store.getState().cursor).toBe(12);
    expect(api.snapshot).toHaveBeenCalledTimes(1);
  });
  it('写入失败重读恢复乐观状态；已读delta保持几何索引与布局，插件仍拿到最新数据', async () => {
    const {api, sync, store} = await setup(); await sync.loadProject(1);
    vi.mocked(api.fold).mockResolvedValue({error: 'failed'});
    expect(await sync.foldAction([2], 'fold')).toBe(false);
    expect(store.getState().data?.folds).toBeUndefined();
    const before = store.modelOf(store.getState());
    const board = store.getState().boards[0], layout = before!.boardLayout(board);
    vi.mocked(api.delta).mockResolvedValueOnce({mode: 'delta', changes: [{kind: 'view_note', id: 99, after: {U: 100}}], next_cursor: 13, has_more: false});
    await sync.poll();
    expect(store.getState().reads).toEqual({'99': {U: 100}});
    const next = store.modelOf(store.getState())!;
    expect(next.layers).toBe(before!.layers);
    expect(next.boardLayout(board)).toBe(layout);
    expect(next.data.noteReads).toEqual({'99': {U: 100}});
  });
  it('多页先合成：后页失败不会发布前页或前移游标', async () => {
    const {api, sync, store} = await setup(); await sync.loadProject(1);
    const before = store.getState().data;
    vi.mocked(api.delta).mockResolvedValueOnce({mode: 'delta', changes: [{kind: 'view_note', id: 99, after: {U: 101}}], next_cursor: 11, has_more: true});
    vi.mocked(api.delta).mockRejectedValueOnce(new Error('second page failed'));
    await sync.poll();
    expect(store.getState().data).toBe(before);
    expect(store.getState().cursor).toBe(10);
    vi.mocked(api.delta).mockResolvedValueOnce({mode: 'delta', changes: [{kind: 'view_note', id: 99, after: {U: 101}}], next_cursor: 11, has_more: true});
    vi.mocked(api.delta).mockResolvedValueOnce({mode: 'delta', changes: [{kind: 'view_note', id: 99, after: {U: 102}}], next_cursor: 12, has_more: false});
    await sync.poll();
    expect(store.getState().reads).toEqual({'99': {U: 102}});
    expect(store.getState().cursor).toBe(12);
  });
  it('折叠写入期间切走再回来，不把尚未载入的空排版保存进原项目', async () => {
    vi.useFakeTimers();
    settings.record = true;
    const {api, sync, store} = await setup(); await sync.loadProject(1);
    const write = deferred<{recorded: boolean}>();
    vi.mocked(api.fold).mockImplementationOnce(() => write.promise);
    const folding = sync.foldAction([2], 'fold'); await flush();
    await sync.loadProject(2);
    await sync.loadProject(1);
    expect(store.getState().data).toBeNull();
    expect(store.getState().boards).toEqual([]);
    vi.mocked(api.saveLayout).mockClear();
    write.resolve({recorded: true});
    expect(await folding).toBe(true);
    expect(api.saveLayout).not.toHaveBeenCalled();
    expect(store.getState().data?.project.id).toBe(1);
    expect(store.getState().boards).not.toEqual([]);
  });
});
