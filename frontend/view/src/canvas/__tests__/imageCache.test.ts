import {describe, expect, it, vi} from 'vitest';
import {ImageCache} from '../imageCache';
const image = (w = 10, h = 10) => ({naturalWidth: w, naturalHeight: h} as HTMLImageElement);

describe('decoded image leases and idle LRU', () => {
  it('shares decoding and keeps a still-used resource when another owner releases', async () => {
    const loader = vi.fn(async () => image()), cache = new ImageCache(loader, 0, 0);
    const a = cache.acquire('same'), b = cache.acquire('same');
    expect(a.promise).toBe(b.promise); await a.promise;
    a.release(); a.release(); expect(cache.size).toBe(1);
    expect(cache.acquire('same').promise).toBe(b.promise);
    expect(loader).toHaveBeenCalledOnce();
    b.release(); expect(cache.size).toBe(1); // 第三个使用者仍持有。
  });
  it('releases the last owner without aborting its unfinished shared Promise', async () => {
    let finish!: (value: HTMLImageElement) => void;
    const work = new Promise<HTMLImageElement>((resolve) => { finish = resolve; });
    const cache = new ImageCache(() => work, 0, 0), a = cache.acquire('same'), b = cache.acquire('same');
    a.release(); expect(cache.size).toBe(1); b.release(); expect(cache.size).toBe(0);
    const result = image(); finish(result);
    expect(await a.promise).toBe(result); expect(await b.promise).toBe(result);
  });
  it('evicts least-recently-used idle images while retaining active images', async () => {
    const loader = vi.fn(async () => image()), cache = new ImageCache(loader, 1);
    const a = cache.acquire('a'), active = cache.acquire('active'), c = cache.acquire('c');
    await Promise.all([a.promise, active.promise, c.promise]);
    a.release(); c.release(); expect(cache.size).toBe(2);
    expect(cache.acquire('active').promise).toBe(active.promise);
    cache.acquire('a'); expect(loader).toHaveBeenCalledTimes(4);
  });
  it('bounds unused decoded bytes and preserves the loadImage Promise compatibility', async () => {
    const loader = vi.fn(async () => image(20, 20)), cache = new ImageCache(loader, 16, 1000);
    const a = cache.acquire('large'); await a.promise;
    expect(cache.load('large')).toBe(a.promise);
    a.release(); expect(cache.size).toBe(0);
    expect(cache.load('large')).not.toBe(a.promise);
  });
  it('retries a failed decode after its last active lease is released', async () => {
    const loader = vi.fn<() => Promise<HTMLImageElement | null>>().mockResolvedValueOnce(null).mockResolvedValueOnce(image());
    const cache = new ImageCache(loader), first = cache.acquire('recovered'), second = cache.acquire('recovered');
    expect(await first.promise).toBeNull(); first.release(); expect(cache.size).toBe(1);
    second.release(); expect(cache.size).toBe(0);
    const retry = cache.acquire('recovered');
    expect(await retry.promise).not.toBeNull(); expect(loader).toHaveBeenCalledTimes(2); retry.release();
  });
});
