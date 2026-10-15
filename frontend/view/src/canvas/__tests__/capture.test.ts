import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
const mocks = vi.hoisted(() => ({idle: vi.fn(async () => {})}));
vi.mock('../../params', () => ({CAPTURE: true}));
vi.mock('../../sync', () => ({pendingWalk: () => Promise.resolve()}));
vi.mock('../../camera', () => ({pendingZoom: () => Promise.resolve()}));
vi.mock('../mediaQueue', () => ({paintQueue: {idle: mocks.idle}}));
vi.mock('../TrackMedia', () => ({mediaPaintState: () => ({pending: 0, ready: 0, failed: 0, errors: []})}));

class NativeMedia extends EventTarget {
  complete = false; readyState = 0; preload = 'metadata';
  decode() { return Promise.resolve(); }
}
let frames: (() => void)[], images: NativeMedia[], videos: NativeMedia[];
async function drain() {
  for (let i = 0; i < 40; i++) { frames.shift()?.(); await Promise.resolve(); await Promise.resolve(); }
}
beforeEach(() => {
  vi.resetModules(); frames = []; images = []; videos = []; mocks.idle.mockReset().mockResolvedValue(undefined);
  vi.stubGlobal('window', {});
  vi.stubGlobal('document', {querySelectorAll: (selector: string) => selector === 'img' ? images : videos});
  vi.stubGlobal('requestAnimationFrame', (fn: () => void) => { frames.push(fn); return frames.length; });
  vi.useFakeTimers({toFake: ['setTimeout', 'clearTimeout', 'Date']});
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

describe('capture readiness reflects real media completion', () => {
  it('does not mark a slow native image ready after eight seconds', async () => {
    const image = new NativeMedia(); images.push(image);
    const {markReady} = await import('../../capture'); const ready = markReady();
    await drain(); await vi.advanceTimersByTimeAsync(9000); await drain();
    expect(window.__layerweaveReady).not.toBe(true); expect(mocks.idle).not.toHaveBeenCalled();
    image.complete = true; image.dispatchEvent(new Event('load'));
    await drain(); await ready; expect(window.__layerweaveReady).toBe(true);
  });
  it('waits for a real native video completion or error instead of a page-local timeout', async () => {
    const video = new NativeMedia(); videos.push(video);
    const {markReady} = await import('../../capture'); const ready = markReady();
    await drain(); await vi.advanceTimersByTimeAsync(9000); await drain();
    expect(window.__layerweaveReady).not.toBe(true);
    video.dispatchEvent(new Event('error'));
    await drain(); await ready; expect(window.__layerweaveReady).toBe(true);
  });
  it('waits until the current media owner queue has committed its final surfaces', async () => {
    let finish!: () => void;
    mocks.idle.mockImplementation(() => new Promise<void>((resolve) => { finish = resolve; }));
    const {markReady} = await import('../../capture'); const ready = markReady();
    await drain(); await vi.advanceTimersByTimeAsync(9000); expect(window.__layerweaveReady).not.toBe(true);
    mocks.idle.mockResolvedValue(undefined); finish();
    await drain(); await ready; expect(window.__layerweaveReady).toBe(true);
  });
});
