import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
const hooks = vi.hoisted(() => ({
  effects: [] as (() => void | (() => void))[],
  canvas: null as unknown,
  failed: vi.fn(),
}));
vi.mock('react', async (original) => ({
  ...await original<typeof import('react')>(),
  useEffect: (effect: () => void | (() => void)) => hooks.effects.push(effect),
  useRef: (initial: unknown) => ({current: initial === null ? hooks.canvas : initial}),
}));
vi.mock('../../params', () => ({CAPTURE: false, DECODE: 'async', LAZY: 'lazy'}));
vi.mock('../../camera', () => ({viewport: () => ({zoom: 1})}));
vi.mock('../../store', () => ({useStore: () => 1}));
vi.mock('../../plugin/slots', () => ({pluginFailed: hooks.failed}));
import {CanvasImg, PluginCanvas, legacyPaintState} from '../Media';
import {Waveform} from '../Waveform';
import {paintQueue} from '../mediaQueue';
import type {Layer, Obj} from '../../types';

class CanvasStub {
  width = 0; height = 0;
  dataset: Record<string, string> = {};
  context = {drawImage: vi.fn(), clearRect: vi.fn()};
  getContext() { return this.context; }
}
let frames: (() => void)[], cleanups: (() => void)[];
function mounted() {
  const effects = hooks.effects.splice(0);
  const dispose = effects.map((effect) => effect()).filter((value): value is () => void => !!value);
  const cleanup = () => { for (const fn of dispose.splice(0)) fn(); };
  cleanups.push(cleanup);
  return cleanup;
}
async function drain() {
  for (let i = 0; i < 20; i++) { frames.shift()?.(); await Promise.resolve(); await Promise.resolve(); }
}
async function expectIdle() {
  let finished = false; const waiting = paintQueue.idle().then(() => { finished = true; });
  await drain(); expect(finished).toBe(true); await waiting;
}
beforeEach(() => {
  frames = []; cleanups = []; hooks.effects = []; hooks.canvas = new CanvasStub(); hooks.failed.mockClear();
  vi.stubGlobal('devicePixelRatio', 1);
  vi.stubGlobal('requestAnimationFrame', (fn: () => void) => { frames.push(fn); return frames.length; });
  vi.stubGlobal('document', {createElement: () => new CanvasStub()});
  vi.stubGlobal('ResizeObserver', class {
    constructor(private callback: (entries: unknown[]) => void) {}
    observe() { this.callback([{contentRect: {width: 100, height: 54}}]); }
    disconnect() {}
  });
  vi.stubGlobal('IntersectionObserver', class {
    constructor(private callback: (entries: unknown[]) => void) {}
    observe() { this.callback([{isIntersecting: true}]); }
    disconnect() {}
  });
});
afterEach(async () => { for (const cleanup of cleanups) cleanup(); await drain(); vi.unstubAllGlobals(); });

describe('current owners of legacy media and waveforms', () => {
  it('does not wait for an unmounted image with a never-resolving cached decode', async () => {
    vi.stubGlobal('Image', class {src = ''; decoding = ''; decode() { return new Promise<void>(() => {}); }});
    CanvasImg({src: '/unmounted-image'}); const cleanup = mounted();
    await drain(); expect(paintQueue.pending).toBeGreaterThan(0);
    cleanup(); await expectIdle();
    expect(legacyPaintState()).toEqual([]);
  });
  it('does not wait for a removed waveform just because its resource cache still holds a Promise', async () => {
    vi.stubGlobal('fetch', () => new Promise(() => {}));
    Waveform({url: '/media/1/unmounted-wave'}); const cleanup = mounted();
    await drain(); expect(paintQueue.pending).toBeGreaterThan(0);
    cleanup(); await expectIdle();
  });
  it('draws asynchronous legacy plugins offscreen and cancels only their obsolete wait', async () => {
    const shown = hooks.canvas as CanvasStub; let finish!: () => void, context: unknown;
    const work = new Promise<void>((resolve) => { finish = resolve; });
    PluginCanvas({name: 'legacy-async', painter: {draw: (ctx) => { context = ctx; return work; }}, o: {} as Obj, layer: {} as Layer, unit: 's'});
    const cleanup = mounted(); await drain();
    expect(context).not.toBe(shown.context); expect(shown.dataset.mediaState).toBe('pending');
    cleanup(); await expectIdle();
    finish(); await drain();
    expect(shown.context.drawImage).not.toHaveBeenCalled(); expect(hooks.failed).not.toHaveBeenCalled();
  });
  it('marks a live asynchronous legacy plugin ready only after its queued copy completes', async () => {
    const shown = hooks.canvas as CanvasStub; let finish!: () => void;
    const work = new Promise<void>((resolve) => { finish = resolve; });
    PluginCanvas({name: 'legacy-live', painter: {draw: () => work}, o: {} as Obj, layer: {} as Layer, unit: 's'});
    mounted(); await drain(); expect(shown.dataset.mediaState).toBe('pending');
    finish(); await expectIdle();
    expect(shown.dataset.mediaState).toBe('ready'); expect(shown.context.drawImage).toHaveBeenCalledOnce();
  });
});
