import {describe, expect, it} from 'vitest';
import {FrameQueue, detailAt, tileKeys, TILE_PIXELS} from '../mediaQueue';

function fixture() {
  const frames: (() => void)[] = [];
  let time = 0;
  const queue = new FrameQueue((f) => frames.push(f), () => time, 3);
  return {queue, frames, tick: () => frames.shift()?.(), spend: (n: number) => { time += n; }};
}
describe('media preparation budget', () => {
  it('coalesces a superseded task and yields once the frame budget is spent', () => {
    const f = fixture(), key = {}, seen: number[] = [];
    f.queue.schedule(key, () => seen.push(0));
    f.queue.schedule(key, () => { seen.push(1); f.spend(4); });
    f.queue.schedule({}, () => seen.push(2));
    f.tick(); expect(seen).toEqual([1]); expect(f.frames).toHaveLength(1);
    f.tick(); expect(seen).toEqual([1, 2]); expect(f.queue.pending).toBe(0);
  });
  it('does not run cancelled generation work', () => {
    const f = fixture(), key = {}, seen: number[] = [];
    f.queue.schedule(key, () => seen.push(1)); f.queue.cancel(key); f.tick();
    expect(seen).toEqual([]); expect(f.queue.pending).toBe(0);
  });
  it('tracks asynchronous preparation through success and rejection', async () => {
    const f = fixture(); let finish!: () => void;
    const work = new Promise<void>((resolve) => { finish = resolve; });
    f.queue.track(work); expect(f.queue.pending).toBe(1);
    finish(); await work; expect(f.queue.pending).toBe(0);
    await expect(f.queue.track(Promise.reject(new Error('bad source')))).rejects.toThrow('bad source');
    expect(f.queue.pending).toBe(0);
  });
  it('keeps later jobs alive and reports a failed drawing callback', () => {
    const f = fixture(), seen: number[] = [];
    f.queue.schedule({}, () => { throw new Error('bad painter'); });
    f.queue.schedule({}, () => seen.push(2)); f.tick();
    expect(seen).toEqual([2]); expect(f.queue.errors[0]).toContain('bad painter'); expect(f.queue.pending).toBe(0);
  });
  it('waits for asynchronous tasks that enqueue a later surface commit', async () => {
    const f = fixture(), seen: number[] = []; let finish!: () => void;
    const work = new Promise<void>((resolve) => { finish = resolve; }).then(() => f.queue.schedule({}, () => seen.push(1)));
    f.queue.track(work);
    let idle = false; const waiting = f.queue.idle().then(() => { idle = true; });
    finish(); await work; await Promise.resolve();
    expect(idle).toBe(false);
    for (let i = 0; i < 8; i++) { f.tick(); await Promise.resolve(); }
    await waiting; expect(seen).toEqual([1]); expect(idle).toBe(true);
  });
  it('cancels an owner whose Promise never settles, waking an already waiting idle call', async () => {
    const f = fixture(), owner = {};
    f.queue.track(new Promise<void>(() => {}), owner);
    let idle = false; const waiting = f.queue.idle().then(() => { idle = true; });
    f.queue.cancel(owner);
    for (let i = 0; i < 8; i++) { await Promise.resolve(); f.tick(); }
    await waiting; expect(idle).toBe(true); expect(f.queue.pending).toBe(0);
  });
  it('cancelling one owner does not release another owner of the same Promise', async () => {
    const f = fixture(), first = {}, second = {}; let finish!: () => void;
    const work = new Promise<void>((resolve) => { finish = resolve; });
    f.queue.track(work, first); f.queue.track(work, second);
    f.queue.cancel(first); expect(f.queue.pending).toBe(1);
    let idle = false; const waiting = f.queue.idle().then(() => { idle = true; });
    for (let i = 0; i < 4; i++) { f.tick(); await Promise.resolve(); }
    expect(idle).toBe(false);
    finish(); await work;
    for (let i = 0; i < 8; i++) { await Promise.resolve(); f.tick(); }
    await waiting; expect(idle).toBe(true);
  });
  it('rechecks new work added in the same turn as cancellation instead of returning early', async () => {
    const f = fixture(), old = {}, next = {}; let finish!: () => void;
    f.queue.track(new Promise<void>(() => {}), old);
    let idle = false; const waiting = f.queue.idle().then(() => { idle = true; });
    f.queue.cancel(old);
    f.queue.schedule(next, () => f.queue.track(new Promise<void>((resolve) => { finish = resolve; }), next));
    for (let i = 0; i < 8; i++) { await Promise.resolve(); f.tick(); }
    expect(idle).toBe(false); expect(f.queue.pending).toBe(1);
    finish();
    for (let i = 0; i < 8; i++) { await Promise.resolve(); f.tick(); }
    await waiting; expect(idle).toBe(true);
  });
  it('finishing a cancelled token cannot release a later task reusing the owner', async () => {
    const f = fixture(), owner = {}; let oldFinish!: () => void, newFinish!: () => void;
    const old = new Promise<void>((resolve) => { oldFinish = resolve; });
    f.queue.track(old, owner); f.queue.cancel(owner);
    f.queue.track(new Promise<void>((resolve) => { newFinish = resolve; }), owner);
    oldFinish(); await old; expect(f.queue.pending).toBe(1);
    newFinish(); await Promise.resolve(); expect(f.queue.pending).toBe(0);
  });
});
describe('media geometry stays compatible', () => {
  it('preserves all existing detail boundaries and capture behavior', () => {
    expect(detailAt(.2, 100, 54)).toBe(0);
    expect(detailAt(1, 5.99, 54)).toBe(0);
    expect(detailAt(1, 6, 54)).toBe(1);
    expect(detailAt(60 / 54, 100, 54)).toBe(2);
    expect(detailAt(.01, 1, 54, true)).toBe(2);
  });
  it('shares a tile among nearby objects and splits exactly at physical bounds', () => {
    expect(tileKeys({x: 0, y: 0, w: 100, h: 54}, 1)).toEqual(['0:0']);
    expect(tileKeys({x: 100, y: 0, w: 100, h: 54}, 1)).toEqual(['0:0']);
    expect(tileKeys({x: 0, y: 0, w: TILE_PIXELS, h: 54}, 1)).toEqual(['0:0']);
    expect(tileKeys({x: 1000, y: 0, w: 100, h: 54}, 2)).toEqual(['0:0', '1:0']);
  });
});
