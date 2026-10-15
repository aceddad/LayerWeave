import {afterEach, describe, expect, it, vi} from 'vitest';
import {drawWaveform, peaksFor, waveformLevels, waveformSize} from '../Waveform';
afterEach(() => vi.unstubAllGlobals());

describe('waveform raster compatibility', () => {
  it('retains the original 18dB normalisation and quiet floor', () => {
    const result = waveformLevels([1, .5, .01, 0]);
    expect(result[0]).toBe(1);
    expect(result[1]).toBeCloseTo((20 * Math.log10(.5) + 18) / 18);
    expect(result.slice(2)).toEqual([.04, .04]);
  });
  it('uses DPR without zoom and keeps independent original dimension limits', () => {
    expect(waveformSize(100, 54, 1.25)).toEqual({width: 125, height: 68});
    expect(waveformSize(10000, 1000, 2)).toEqual({width: 4096, height: 512});
    expect(waveformSize(0, 0, 1)).toEqual({width: 160, height: 40});
  });
  it('draws the same sample bars, amplitude, centering, minimum height and alpha', () => {
    const ctx = {clearRect: vi.fn(), fillRect: vi.fn(), fillStyle: ''};
    drawWaveform(ctx as unknown as CanvasRenderingContext2D, [1, .5, .25], 6, 40, 2);
    expect(ctx.clearRect).toHaveBeenCalledWith(0, 0, 6, 40);
    expect(ctx.fillStyle).toBe('rgba(255,255,255,.75)');
    expect(ctx.fillRect.mock.calls).toEqual([[0, 0, 2, 40], [2, 10, 2, 20], [4, 15, 2, 10]]);
    ctx.fillRect.mockClear();
    drawWaveform(ctx as unknown as CanvasRenderingContext2D, [.01], 1, 20, 1);
    expect(ctx.fillRect).toHaveBeenCalledWith(0, 9.9, 1, 1);
  });
  it('keeps the existing failure text and its DPR font', () => {
    const ctx = {clearRect: vi.fn(), fillText: vi.fn(), fillStyle: '', font: ''};
    drawWaveform(ctx as unknown as CanvasRenderingContext2D, null, 100, 40, 2);
    expect(ctx.fillStyle).toBe('#ffffff88'); expect(ctx.font).toBe('20px sans-serif');
    expect(ctx.fillText).toHaveBeenCalledWith('无法解码', 4, 20);
  });
  it('shares waveform data for the same source URL while a new source is fetched separately', async () => {
    const fetcher = vi.fn(async () => ({ok: true, json: async () => ({rms: [1, .5]})}));
    vi.stubGlobal('fetch', fetcher);
    const a = peaksFor('/media/1/999?lw_source=A.wav');
    expect(peaksFor('/media/1/999?lw_source=A.wav')).toBe(a);
    const b = peaksFor('/media/1/999?lw_source=B.wav');
    expect(b).not.toBe(a); await Promise.all([a, b]);
    expect(fetcher.mock.calls).toEqual([['/wave/1/999?lw_source=A.wav'], ['/wave/1/999?lw_source=B.wav']]);
  });
});
