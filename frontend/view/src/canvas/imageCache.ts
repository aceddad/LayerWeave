// 当前对象持有 lease；已无人使用的解码图只保留少量最近项。取消一个使用者不取消共享加载。
export interface ImageLease {
  url: string;
  promise: Promise<HTMLImageElement | null>;
  release: () => void;
}
interface CachedImage {
  promise: Promise<HTMLImageElement | null>; users: number; bytes: number; used: number; failed: boolean;
}
const decode = (src: string): Promise<HTMLImageElement | null> => {
  const image = new Image(); image.decoding = 'async'; image.src = src;
  return image.decode().then(() => image, () => null);
};
export class ImageCache {
  private entries = new Map<string, CachedImage>();
  private serial = 0;
  constructor(private loader = decode, private unusedLimit = 16, private unusedBytes = 64 * 1024 * 1024) {}
  get size() { return this.entries.size; }
  private get(url: string) {
    let record = this.entries.get(url);
    if (!record) {
      record = {promise: this.loader(url), users: 0, bytes: 0, used: ++this.serial, failed: false};
      this.entries.set(url, record);
      const current = record;
      record.promise.then((image) => {
        current.bytes = image ? image.naturalWidth * image.naturalHeight * 4 : 0;
        current.failed = !image;
        if (this.entries.get(url) !== current) return;
        if (!image && !current.users) this.entries.delete(url);
        this.trim();
      }, () => {
        current.failed = true;
        if (this.entries.get(url) === current && !current.users) this.entries.delete(url);
      });
    }
    record.used = ++this.serial;
    return record;
  }
  acquire(url: string): ImageLease {
    const record = this.get(url); record.users++;
    let released = false;
    return {url, promise: record.promise, release: () => {
      if (released) return;
      released = true; record.users--; record.used = ++this.serial;
      if (record.failed && !record.users && this.entries.get(url) === record) this.entries.delete(url);
      this.trim();
    }};
  }
  // 保留原 loadImage 的 Promise 接口；长期展示者应持有 acquire 返回的 lease。
  load(url: string) { const record = this.get(url); this.trim(); return record.promise; }
  private trim() {
    const unused = [...this.entries].filter(([, entry]) => !entry.users).sort((a, b) => a[1].used - b[1].used);
    let bytes = unused.reduce((sum, [, entry]) => sum + entry.bytes, 0), count = unused.length;
    for (const [url, entry] of unused) {
      if (count <= this.unusedLimit && bytes <= this.unusedBytes) break;
      this.entries.delete(url); bytes -= entry.bytes; count--;
    }
  }
}
export const decodedImages = new ImageCache();
