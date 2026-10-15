import {afterEach, describe, expect, it, vi} from 'vitest';
vi.mock('../../params', () => ({CAPTURE: false, DECODE: 'async', LAZY: 'lazy'}));
vi.mock('../../camera', () => ({viewport: () => ({zoom: 1})}));
vi.mock('../../store', () => ({useStore: () => 1}));
vi.mock('../../plugin/slots', () => ({pluginFailed: vi.fn()}));
import {BlockFrame, BlockThumb, Frame, Thumb, loadImage} from '../Media';
import {mediaUrl} from '../mediaUrl';
import type {Obj} from '../../types';
const object = (source: string) => ({id: 9, media: {source, url: '/media/1/9', kind: 'image', available: true}} as Obj);
afterEach(() => vi.unstubAllGlobals());

describe('media identity includes the selected source', () => {
  it('keeps a stable URL for unchanged sources and preserves route parameters and fragments', () => {
    const a = mediaUrl('/frame/1/9?t=0.10#t=1', '目录/A & B.png');
    expect(a).toBe('/frame/1/9?t=0.10&lw_source=' + encodeURIComponent('目录/A & B.png') + '#t=1');
    expect(a).toBe(mediaUrl('/frame/1/9?t=0.10#t=1', '目录/A & B.png'));
    expect(mediaUrl('/media/1/9')).toBe('/media/1/9');
  });
  it('starts a new decode when source changes at the same object id, and reuses unchanged decode', async () => {
    const decoded: string[] = [];
    class ImageStub {
      src = ''; decoding = '';
      decode() { decoded.push(this.src); return Promise.resolve(); }
    }
    vi.stubGlobal('Image', ImageStub);
    const a = mediaUrl('/media/1/9', 'A.png'), b = mediaUrl('/media/1/9', 'B.png');
    const first = loadImage(a), changed = loadImage(b);
    expect(changed).not.toBe(first);
    expect(loadImage(a)).toBe(first); expect(loadImage(b)).toBe(changed);
    await Promise.all([first, changed]);
    expect(decoded).toEqual([a, b]);
  });
  it('versions sidebar thumbnails, legacy canvas thumbnails, and both frame routes', () => {
    const a = object('A.png'), b = object('B.png');
    for (const component of [Thumb, BlockThumb]) {
      const first = component({project: 1, o: a, width: 160, frames: true}).props.src;
      const second = component({project: 1, o: b, width: 160, frames: true}).props.src;
      expect(first).toContain('?w=160&lw_source=A.png'); expect(second).toContain('lw_source=B.png'); expect(first).not.toBe(second);
      expect(component({project: 1, o: a, width: 160, frames: false}).props.src).toBe('/media/1/9?lw_source=A.png');
    }
    for (const component of [Frame, BlockFrame]) {
      expect(component({project: 1, o: b, at: 1, frames: true}).props.src).toBe('/frame/1/9?t=1.00&lw_source=B.png');
    }
    expect(Frame({project: 1, o: b, at: 1, frames: false}).props.src).toBe('/media/1/9?lw_source=B.png#t=1');
  });
  it('keeps the source version on server waveform and original audio requests', () => {
    const a = mediaUrl('/media/1/9', 'A.wav'), b = mediaUrl('/media/1/9', 'B.wav');
    expect(a.replace('/media/', '/wave/')).toBe('/wave/1/9?lw_source=A.wav');
    expect(b.replace('/media/', '/wave/')).toBe('/wave/1/9?lw_source=B.wav');
    expect(a).not.toBe(b);
  });
});
