import {describe, expect, it} from 'vitest';
import {coverCrop, endCoverage, sourceWidth, videoEnds} from '../mediaGeometry';
import {tileKeys} from '../mediaQueue';

describe('physical source sizing and sparse video ends', () => {
  it('chooses sufficient existing buckets using width, height, aspect and physical scale', () => {
    expect(sourceWidth(98, 34, 16 / 9, 1.25)).toBe(160);
    expect(sourceWidth(168, 34, 16 / 9, 2)).toBe(640);
    expect(sourceWidth(598, 34, 16 / 9, 1.25)).toBe(1280);
    expect(sourceWidth(10, 34, 10, 2)).toBe(1280);
    expect(sourceWidth(10000, 34, 16 / 9, 2)).toBe(2048);
  });
  it('crops cover in original source coordinates without creating a low-resolution intermediate', () => {
    expect(coverCrop(1920, 1080, 64, 34)).toEqual({x: 0, y: 30, w: 1920, h: 1020});
    expect(coverCrop(1920, 1080, 34, 64)).toEqual({x: 673.125, y: 0, w: 573.75, h: 1080});
  });
  it('keeps each end 64 CSS pixels irrespective of an object lasting a short or very long time', () => {
    for (const width of [200, 10000, 1000000]) {
      expect(videoEnds(width, 36)).toEqual([{x: 1, y: 1, w: 64, h: 34}, {x: width - 65, y: 1, w: 64, h: 34}]);
      const keys = new Set(endCoverage({x: 0, y: 0, w: width, h: 36}).flatMap((r) => tileKeys(r, 2)));
      expect(keys.size).toBeLessThanOrEqual(4);
    }
  });
});
