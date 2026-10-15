import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
const mocks = vi.hoisted(() => ({
  state: {settledZoom: 1},
  listeners: new Set<(state: {settledZoom: number}, previous: {settledZoom: number}) => void>(),
  failed: vi.fn(),
  image: vi.fn(async (_url: string) => ({naturalWidth: 160, naturalHeight: 90})),
  peaks: vi.fn(async (_url: string): Promise<number[] | null> => [1, .5]),
  capture: true,
  released: vi.fn(),
  nativeDecode: vi.fn(async () => {}),
}));
vi.mock('../../store', () => ({
  getState: () => mocks.state,
  useStore: {subscribe: (fn: (state: {settledZoom: number}, previous: {settledZoom: number}) => void) => {
    mocks.listeners.add(fn); return () => mocks.listeners.delete(fn);
  }},
}));
vi.mock('../../params', () => ({get CAPTURE() { return mocks.capture; }, params: new URLSearchParams()}));
vi.mock('../../api', () => ({thumbUrl: (_p: number, id: number, width: number) => id + '/' + width,
  frameUrl: (_p: number, id: number, at: number) => id + '/' + at}));
vi.mock('../Media', () => ({acquireImage: (url: string) => ({url, promise: mocks.image(url), release: vi.fn(() => mocks.released(url))}),
  legacyPaintState: () => []}));
vi.mock('../../plugin/slots', () => ({pluginFailed: mocks.failed}));
vi.mock('../Waveform', async (original) => ({...await original<typeof import('../Waveform')>(), peaksFor: mocks.peaks}));
import {TrackSurface, mediaPaintState} from '../TrackMedia';
import type {MediaSpec} from '../TrackMedia';
import {paintQueue} from '../mediaQueue';

let failImage = false;
class ElementStub {
  dataset: Record<string, string> = {};
  style = {cssText: ''};
  isConnected = false;
  className = '';
  width = 0; height = 0;
  children: ElementStub[] = [];
  parent: ElementStub | null = null;
  calls: unknown[][] = [];
  ctx = {
    scale: (...v: unknown[]) => this.calls.push(['scale', ...v]),
    translate: (...v: unknown[]) => this.calls.push(['translate', ...v]),
    drawImage: (...v: unknown[]) => { if (failImage) { failImage = false; throw new Error('draw failed'); } this.calls.push(['drawImage', ...v]); },
    clearRect: (...v: unknown[]) => this.calls.push(['clearRect', ...v]),
    roundRect: (...v: unknown[]) => this.calls.push(['roundRect', ...v]),
    fillRect: (...v: unknown[]) => this.calls.push(['fillRect', ...v]),
    fillText: (...v: unknown[]) => this.calls.push(['fillText', ...v]),
    beginPath: () => {}, fill: () => {}, save: () => {}, restore: () => {}, clip: () => {},
    fillStyle: '', globalAlpha: 1,
  };
  getContext() { return this.ctx; }
  append(el: ElementStub) {
    if (el.parent) el.remove();
    el.isConnected = true; el.parent = this; this.children.push(el);
  }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter((el) => el !== this); this.parent = null; this.isConnected = false; }
}
let frames: (() => void)[];
let surfaces: TrackSurface[];
async function drain() {
  for (let i = 0; i < 80; i++) {
    frames.shift()?.();
    await Promise.resolve(); await Promise.resolve();
    if (!paintQueue.pending && !frames.length) return;
  }
  throw new Error('media queue did not settle');
}
function fixture(width = 1000, height = 58) {
  const root = new ElementStub(), surface = new TrackSurface(width, height);
  surfaces.push(surface); surface.attach(root as unknown as HTMLDivElement);
  return {root, surface};
}
function spec(id: number, x = 0, width = 100): MediaSpec {
  return {o: {id, media: {url: '/image'}} as MediaSpec['o'], layer: {} as MediaSpec['layer'],
    kind: 'image', unit: 's', project: 1, frames: false, last: 1, rect: {x, y: 2, w: width, h: 54}};
}
beforeEach(() => {
  frames = []; surfaces = []; failImage = false; mocks.state = {settledZoom: 1}; mocks.failed.mockClear();
  mocks.image.mockReset().mockResolvedValue({naturalWidth: 160, naturalHeight: 90});
  mocks.released.mockClear(); mocks.nativeDecode.mockReset().mockResolvedValue(undefined);
  mocks.capture = true; mocks.peaks.mockReset().mockResolvedValue([1, .5]);
  vi.stubGlobal('requestAnimationFrame', (fn: () => void) => { frames.push(fn); return frames.length; });
  vi.stubGlobal('devicePixelRatio', 1);
  vi.stubGlobal('document', {createElement: () => new ElementStub()});
  vi.stubGlobal('Image', class extends ElementStub {
    src = ''; decoding = ''; naturalWidth = 160; naturalHeight = 90;
    decode() { return mocks.nativeDecode(); }
  });
  vi.stubGlobal('getComputedStyle', () => ({getPropertyValue: () => '#3d8bfd'}));
  vi.stubGlobal('IntersectionObserver', class {observe() {} unobserve() {} disconnect() {}});
});
afterEach(async () => { for (const surface of surfaces) surface.dispose(); await drain(); vi.useRealTimers(); vi.unstubAllGlobals(); });

describe('shared track media lifecycle', () => {
  it('draws decoded images directly and requests physical resolution without downsampling into an intermediate canvas', async () => {
    vi.stubGlobal('devicePixelRatio', 1.25);
    mocks.image.mockImplementation(async (url) => {
      const w = Number(url.split('/').at(-1)); return {naturalWidth: w, naturalHeight: w * 9 / 16};
    });
    const {root, surface} = fixture(), node = new ElementStub();
    surface.add({...spec(1, 0, 600), frames: true}, node as unknown as HTMLElement); await drain();
    expect(mocks.image).toHaveBeenCalledWith('1/1280');
    const last = root.children[0].calls.filter((call) => call[0] === 'drawImage').at(-1)!;
    expect(last[1]).toMatchObject({naturalWidth: 1280}); expect(last.slice(-2)).toEqual([598, 52]);
    expect(root.children[0].calls).toContainEqual(['scale', 1.25, 1.25]);
    mocks.state = {settledZoom: .5};
    for (const fn of mocks.listeners) fn(mocks.state, {settledZoom: 1});
    await drain();
    expect(mocks.image.mock.calls.at(-1)).toEqual(['1/1280']); // 已有足够高源，不退到更小源再放大。
  });
  it('upgrades a narrow target when cover needs a wide panoramic source, releasing the unused probe', async () => {
    mocks.image.mockImplementation(async (url) => ({naturalWidth: Number(url.split('/').at(-1)), naturalHeight: 2}));
    const {surface} = fixture(), node = new ElementStub();
    surface.add({...spec(1, 0, 20), frames: true}, node as unknown as HTMLElement); await drain();
    expect(mocks.image.mock.calls).toEqual([['1/160'], ['1/2048']]);
    expect(mocks.released).toHaveBeenCalledWith('1/160');
    expect(mocks.released).not.toHaveBeenCalledWith('1/2048');
  });
  it('keeps the two video-end destinations sharp and allocates no tiles for a huge empty middle', async () => {
    mocks.image.mockResolvedValue({naturalWidth: 640, naturalHeight: 360});
    const {root, surface} = fixture(1000000), node = new ElementStub();
    surface.add({...spec(1, 0, 1000000), kind: 'video', frames: true}, node as unknown as HTMLElement); await drain();
    expect(root.children.length).toBeLessThanOrEqual(4);
    expect(root.children.every((tile) => tile.className === 'media-tile')).toBe(true);
    expect(node.dataset.atlas).toBe('ends');
    const drawings = root.children.flatMap((tile) => tile.calls.filter((call) => call[0] === 'drawImage'));
    expect(drawings.length).toBeGreaterThan(0);
    for (const call of drawings) { expect(call[1]).toMatchObject({naturalWidth: 640}); expect(call.slice(-2)).toEqual([64, 52]); }
  });
  it('preserves the displayed image and its lease until a source replacement is decoded and committed', async () => {
    const a = {naturalWidth: 160, naturalHeight: 90}, b = {naturalWidth: 320, naturalHeight: 180};
    mocks.image.mockResolvedValueOnce(a);
    const {root, surface} = fixture(), node = new ElementStub(), original = spec(1);
    original.o = {...original.o, media: {...original.o.media!, source: 'A.png'}};
    const registration = surface.add(original, node as unknown as HTMLElement); await drain();
    let finish!: (image: typeof b) => void;
    mocks.image.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
    registration.update({...original, o: {...original.o, media: {...original.o.media!, source: 'B.png'}}});
    for (let i = 0; i < 12; i++) { frames.shift()?.(); await Promise.resolve(); }
    expect(node.dataset.mediaState).toBe('pending'); expect(node.dataset.atlas).toBe('ready');
    expect(root.children[0].calls.filter((call) => call[0] === 'drawImage').at(-1)![1]).toBe(a);
    expect(mocks.released).not.toHaveBeenCalledWith('/image?lw_source=A.png');
    finish(b); await drain();
    expect(root.children[0].calls.filter((call) => call[0] === 'drawImage').at(-1)![1]).toBe(b);
    expect(mocks.released).toHaveBeenCalledWith('/image?lw_source=A.png');
    expect(node.dataset.mediaState).toBe('ready');
  });
  it('cancels an obsolete source lease and cannot paste its late result over the latest source', async () => {
    const {root, surface} = fixture(), node = new ElementStub(), original = spec(1);
    original.o = {...original.o, media: {...original.o.media!, source: 'A.png'}};
    const registration = surface.add(original, node as unknown as HTMLElement); await drain();
    let oldFinish!: (image: {naturalWidth: number; naturalHeight: number}) => void;
    mocks.image.mockImplementationOnce(() => new Promise((resolve) => { oldFinish = resolve; }));
    registration.update({...original, o: {...original.o, media: {...original.o.media!, source: 'B.png'}}});
    for (let i = 0; i < 8; i++) { frames.shift()?.(); await Promise.resolve(); }
    const newest = {naturalWidth: 640, naturalHeight: 360}; mocks.image.mockResolvedValueOnce(newest);
    registration.update({...original, o: {...original.o, media: {...original.o.media!, source: 'C.png'}}});
    await drain(); expect(mocks.released).toHaveBeenCalledWith('/image?lw_source=B.png');
    oldFinish({naturalWidth: 20, naturalHeight: 10}); await drain();
    expect(root.children[0].calls.filter((call) => call[0] === 'drawImage').at(-1)![1]).toBe(newest);
  });
  it('reports a failed source replacement and releases both pending and displayed leases', async () => {
    const {root, surface} = fixture(), node = new ElementStub(), original = spec(1);
    const registration = surface.add(original, node as unknown as HTMLElement); await drain();
    mocks.image.mockRejectedValueOnce(new Error('bad source'));
    registration.update({...original, o: {...original.o, media: {...original.o.media!, source: 'bad.png'}}});
    await drain();
    expect(node.dataset.mediaState).toBe('failed'); expect(root.children).toHaveLength(0);
    expect(mocks.released).toHaveBeenCalledWith('/image'); expect(mocks.released).toHaveBeenCalledWith('/image?lw_source=bad.png');
  });
  it('waits for native fallback decoding and does not move a shared decoded element into the DOM', async () => {
    const cached = {naturalWidth: 2048, naturalHeight: 1152}; mocks.image.mockResolvedValue(cached);
    let finish!: () => void;
    mocks.nativeDecode.mockImplementationOnce(() => new Promise<void>((resolve) => { finish = resolve; }));
    const {root, surface} = fixture(1000000), node = new ElementStub();
    surface.add({...spec(1, 0, 1000000), frames: true}, node as unknown as HTMLElement);
    for (let i = 0; i < 16; i++) { frames.shift()?.(); await Promise.resolve(); }
    expect(root.children).toHaveLength(0); expect(node.dataset.mediaState).toBe('pending');
    finish(); await drain();
    expect(root.children[0].className).toBe('media-native');
    expect(root.children[0].dataset.objectId).toBe('1'); expect(root.children[0].dataset.mediaSource).toBe('1/2048');
    expect(root.children[0].children[0]).not.toBe(cached); expect(node.dataset.mediaState).toBe('ready');
    surface.add({...spec(2, 0, 1000000), frames: true}, new ElementStub() as unknown as HTMLElement); await drain();
    expect(root.children).toHaveLength(2);
    expect(root.children[0].children[0]).not.toBe(root.children[1].children[0]);
  });
  it('keeps an old native fallback until the new DOM image has decoded', async () => {
    const {root, surface} = fixture(1000000), node = new ElementStub(), original = spec(1, 0, 1000000);
    const registration = surface.add(original, node as unknown as HTMLElement); await drain();
    const old = root.children[0]; let finish!: () => void;
    mocks.nativeDecode.mockImplementationOnce(() => new Promise<void>((resolve) => { finish = resolve; }));
    registration.update({...original, o: {...original.o, media: {...original.o.media!, source: 'new.png'}}});
    for (let i = 0; i < 16; i++) { frames.shift()?.(); await Promise.resolve(); }
    expect(root.children).toEqual([old]); expect(mocks.released).not.toHaveBeenCalledWith('/image');
    finish(); await drain();
    expect(root.children).toHaveLength(1); expect(root.children[0]).not.toBe(old);
    expect(mocks.released).toHaveBeenCalledWith('/image');
  });
  it('releases empty tile entries when an object moves to a distant position', async () => {
    const {root, surface} = fixture(10000), node = new ElementStub(), original = spec(1);
    const registration = surface.add(original, node as unknown as HTMLElement); await drain(); const old = root.children[0];
    registration.update({...original, rect: {...original.rect, x: 5000}}); await drain();
    expect(old.isConnected).toBe(false); expect(root.children).toHaveLength(1);
    expect((surface as unknown as {tiles: Map<string, unknown>}).tiles.size).toBe(1);
  });
  it('puts two images in one surface while keeping their object identities and readiness', async () => {
    const {root, surface} = fixture(), first = new ElementStub(), second = new ElementStub();
    surface.add(spec(1), first as unknown as HTMLElement);
    surface.add(spec(2, 100), second as unknown as HTMLElement);
    expect(first.dataset.mediaState).toBe('idle');
    await drain();
    expect(root.children).toHaveLength(1);
    expect(first.dataset.mediaState).toBe('ready'); expect(second.dataset.mediaState).toBe('ready');
    expect(root.children[0].dataset.mediaTile).toBe('ready');
    expect(mediaPaintState()).toMatchObject({ready: 2, failed: 0, pending: 0});
  });
  it('requests a new source when an object keeps its id but its media is replaced', async () => {
    const {surface} = fixture(), node = new ElementStub(), a = spec(1);
    a.o = {...a.o, media: {...a.o.media!, source: 'A.png'}};
    const remove = surface.add(a, node as unknown as HTMLElement); await drain(); remove();
    surface.add({...a, o: {...a.o, media: {...a.o.media!, source: 'B.png'}}}, node as unknown as HTMLElement); await drain();
    expect(mocks.image.mock.calls.map((args) => args[0])).toEqual(['/image?lw_source=A.png', '/image?lw_source=B.png']);
    expect(node.dataset.mediaState).toBe('ready');
  });
  it('merges ordinary audio into the track while retaining its original raster size and alpha', async () => {
    const {root, surface} = fixture(), first = new ElementStub(), second = new ElementStub();
    surface.add({...spec(1), kind: 'audio'}, first as unknown as HTMLElement);
    surface.add({...spec(2, 100), kind: 'audio'}, second as unknown as HTMLElement); await drain();
    expect(root.children).toHaveLength(1); expect(first.dataset.mediaState).toBe('ready'); expect(second.dataset.mediaState).toBe('ready');
    const stamp = root.children[0].calls.filter((c) => c[0] === 'drawImage').at(-1)![1] as ElementStub;
    const wave = stamp.calls.find((c) => c[0] === 'drawImage')![1] as ElementStub;
    expect([wave.width, wave.height]).toEqual([98, 52]);
    expect(wave.ctx.fillStyle).toBe('rgba(255,255,255,.75)'); expect(stamp.ctx.globalAlpha).toBe(.85);
    expect(wave.calls.find((c) => c[0] === 'fillRect')).toEqual(['fillRect', 0, 0, 1, 52]);
    mocks.state = {settledZoom: 2};
    for (const fn of mocks.listeners) fn(mocks.state, {settledZoom: 1}); await drain();
    expect(mocks.peaks).toHaveBeenCalledTimes(2); // 镜头变化只重排共享表面，不重新采样波形。
    expect(root.children[0].calls.filter((c) => c[0] === 'drawImage').at(-1)![1]).toBe(stamp);
  });
  it('keeps ordinary audio active at detail zero without adding near-viewport loading, but preserves plugin LOD', async () => {
    mocks.capture = false; mocks.state = {settledZoom: .05};
    const {surface} = fixture(), audio = new ElementStub(), plugin = new ElementStub(), draw = vi.fn();
    surface.add({...spec(1), kind: 'audio'}, audio as unknown as HTMLElement);
    surface.add({...spec(2, 100), kind: 'audio', painter: {name: 'audio-plugin', painter: {draw}}}, plugin as unknown as HTMLElement);
    await drain();
    expect(audio.dataset.mediaState).toBe('ready'); expect(plugin.dataset.mediaState).toBe('idle');
    expect(mocks.peaks).toHaveBeenCalledOnce(); expect(draw).not.toHaveBeenCalled();
  });
  it('retains the original 4096-pixel waveform on an extremely long object', async () => {
    const {root, surface} = fixture(1000000), node = new ElementStub();
    surface.add({...spec(1, 0, 1000000), kind: 'audio'}, node as unknown as HTMLElement); await drain();
    expect(root.children).toHaveLength(1);
    const wave = root.children[0].calls.find((c) => c[0] === 'drawImage')![1] as ElementStub;
    expect(wave.width).toBe(4096); expect(wave.height).toBe(52);
    expect(root.children[0].width).toBeLessThanOrEqual(4098);
  });
  it('still paints the failure label while reporting a failed waveform honestly', async () => {
    mocks.peaks.mockResolvedValueOnce(null);
    const {root, surface} = fixture(), node = new ElementStub();
    surface.add({...spec(1), kind: 'audio'}, node as unknown as HTMLElement); await drain();
    expect(root.children).toHaveLength(1); expect(node.dataset.mediaState).toBe('failed');
    expect(mediaPaintState().failed).toBe(1);
    const stamp = root.children[0].calls.find((c) => c[0] === 'drawImage')![1] as ElementStub;
    const wave = stamp.calls.find((c) => c[0] === 'drawImage')![1] as ElementStub;
    expect(wave.calls.find((c) => c[0] === 'fillText')).toEqual(['fillText', '无法解码', 4, 26]);
  });
  it('does not retain a removed audio owner just because waveform loading has not resolved', async () => {
    mocks.peaks.mockImplementationOnce(() => new Promise(() => {}));
    const {surface} = fixture(), node = new ElementStub();
    const remove = surface.add({...spec(1), kind: 'audio'}, node as unknown as HTMLElement);
    frames.shift()?.(); await Promise.resolve(); expect(paintQueue.pending).toBeGreaterThan(0);
    remove(); await drain(); expect(paintQueue.pending).toBe(0);
  });
  it('keeps async plugins off the shared context and waits for their completed drawing', async () => {
    const {root, surface} = fixture(), node = new ElementStub();
    let finish!: () => void, pluginContext: unknown;
    const deferred = new Promise<void>((resolve) => { finish = resolve; });
    const plugin = {name: 'async-painter', painter: {draw: (ctx: CanvasRenderingContext2D) => { pluginContext = ctx; return deferred; }}};
    surface.add({...spec(1), painter: plugin}, node as unknown as HTMLElement);
    frames.shift()?.(); await Promise.resolve();
    expect(root.children).toHaveLength(0); expect(node.dataset.mediaState).toBe('pending');
    expect(node.dataset.mediaPlugin).toBe('async-painter');
    finish(); await drain();
    expect(node.dataset.mediaState).toBe('ready'); expect(pluginContext).not.toBe(root.children[0].ctx);
  });
  it('does not paste a plugin result after the object was removed', async () => {
    const {root, surface} = fixture(), node = new ElementStub();
    let finish!: () => void;
    const deferred = new Promise<void>((resolve) => { finish = resolve; });
    const remove = surface.add({...spec(1), painter: {name: 'slow', painter: {draw: () => deferred}}}, node as unknown as HTMLElement);
    frames.shift()?.(); await Promise.resolve(); remove(); finish(); await drain();
    expect(root.children).toHaveLength(0); expect(node.dataset.mediaState).toBeUndefined();
  });
  it('keeps a legitimate long-running plugin pending past eight seconds and later pastes it', async () => {
    vi.useFakeTimers({toFake: ['setTimeout', 'clearTimeout', 'Date']});
    const {root, surface} = fixture(), node = new ElementStub(); let finish!: () => void;
    const deferred = new Promise<void>((resolve) => { finish = resolve; });
    surface.add({...spec(1), painter: {name: 'long', painter: {draw: () => deferred}}}, node as unknown as HTMLElement);
    frames.shift()?.(); await Promise.resolve();
    await vi.advanceTimersByTimeAsync(9000);
    expect(node.dataset.mediaState).toBe('pending'); expect(mediaPaintState().failed).toBe(0);
    expect(root.children).toHaveLength(0);
    finish(); await drain(); expect(node.dataset.mediaState).toBe('ready');
  });
  it('stops waiting for a removed plugin even when its Promise never resolves', async () => {
    const {surface} = fixture(), node = new ElementStub();
    const remove = surface.add({...spec(1), painter: {name: 'unmounted', painter: {draw: () => new Promise<void>(() => {})}}}, node as unknown as HTMLElement);
    frames.shift()?.(); await Promise.resolve();
    let idle = false; const waiting = paintQueue.idle().then(() => { idle = true; });
    remove();
    for (let i = 0; i < 10; i++) { await Promise.resolve(); frames.shift()?.(); }
    await waiting; expect(idle).toBe(true); expect(mediaPaintState().failed).toBe(0);
  });
  it('finishes a new zoom generation without awaiting a superseded never-resolving plugin', async () => {
    const {surface} = fixture(), node = new ElementStub(); let call = 0;
    surface.add({...spec(1), painter: {name: 'replaced', painter: {draw: () => ++call === 1 ? new Promise<void>(() => {}) : Promise.resolve()}}}, node as unknown as HTMLElement);
    frames.shift()?.(); await Promise.resolve();
    mocks.state = {settledZoom: 2};
    for (const fn of mocks.listeners) fn(mocks.state, {settledZoom: 1});
    await drain();
    expect(call).toBe(2); expect(node.dataset.mediaState).toBe('ready'); expect(mediaPaintState().pending).toBe(0);
  });
  it('does not let an older asynchronous zoom generation overwrite the new surface', async () => {
    const {root, surface} = fixture(), node = new ElementStub(), finishes: (() => void)[] = [];
    const painter = {name: 'zoom-painter', painter: {draw: () => new Promise<void>((resolve) => finishes.push(resolve))}};
    surface.add({...spec(1), painter}, node as unknown as HTMLElement);
    frames.shift()?.(); await Promise.resolve();
    mocks.state = {settledZoom: 2};
    for (const fn of mocks.listeners) fn(mocks.state, {settledZoom: 1});
    frames.shift()?.(); await Promise.resolve();
    expect(finishes).toHaveLength(2);
    finishes[1]();
    for (let i = 0; i < 12; i++) { frames.shift()?.(); await Promise.resolve(); }
    finishes[0](); await drain();
    const last = root.children[0].calls.filter((call) => call[0] === 'drawImage').at(-1)!;
    expect((last[1] as ElementStub).width).toBe(200);
    expect(node.dataset.mediaState).toBe('ready');
  });
  it('reports rejected plugins as failures rather than painted empty canvases', async () => {
    const {root, surface} = fixture(), node = new ElementStub();
    surface.add({...spec(1), painter: {name: 'broken', painter: {draw: async () => { throw new Error('no paint'); }}}}, node as unknown as HTMLElement);
    await drain();
    expect(root.children).toHaveLength(0); expect(node.dataset.mediaState).toBe('failed');
    expect(mediaPaintState().failed).toBe(1); expect(mocks.failed).toHaveBeenCalledOnce();
  });
  it('settles image preparation when drawImage throws after decode', async () => {
    const {surface} = fixture(), node = new ElementStub();
    failImage = true;
    surface.add(spec(1), node as unknown as HTMLElement); await drain();
    expect(node.dataset.mediaState).toBe('failed');
    expect(mediaPaintState()).toMatchObject({pending: 0, failed: 1});
  });
  it('bounds a very long object instead of allocating tiles for its whole duration', async () => {
    const {root, surface} = fixture(1000000), node = new ElementStub();
    surface.add(spec(1, 0, 1000000), node as unknown as HTMLElement); await drain();
    expect(root.children).toHaveLength(1); expect(root.children[0].className).toBe('media-native');
    expect(root.children[0].children).toHaveLength(1);
    expect(node.dataset.mediaState).toBe('ready');
  });
  it('replaces density after zoom without moving object DOM or exceeding tile dimensions', async () => {
    const {root, surface} = fixture(), node = new ElementStub();
    surface.add(spec(1), node as unknown as HTMLElement); await drain();
    const before = root.children[0];
    mocks.state = {settledZoom: 2};
    for (const fn of mocks.listeners) fn(mocks.state, {settledZoom: 1});
    await drain();
    expect(root.children).toHaveLength(1); expect(root.children[0]).not.toBe(before);
    expect(root.children[0].width).toBeLessThanOrEqual(2048); expect(root.children[0].height).toBeLessThanOrEqual(2048);
    expect(node.dataset.mediaState).toBe('ready');
  });
});
