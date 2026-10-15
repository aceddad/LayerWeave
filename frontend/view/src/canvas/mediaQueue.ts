// 所有媒体准备与贴图共用一个队列。预算限制同步工作；不能抢占插件的一次 draw。
export class FrameQueue {
  private jobs = new Map<object, () => void>();
  private awaiting = new Map<object, object>(); // 每次登记独立 token；同一个 Promise 可以有多个 owner。
  private waiters = new Set<() => void>();
  private scheduled = false;
  readonly errors: string[] = [];
  constructor(private frame: (job: () => void) => unknown = (job) => requestAnimationFrame(job),
              private now: () => number = () => performance.now(), private budget = 3) {}
  get pending() { return this.jobs.size + this.awaiting.size + Number(this.scheduled); }
  schedule(key: object, job: () => void) {
    this.jobs.set(key, job);
    if (!this.scheduled) { this.scheduled = true; this.frame(() => this.pump()); }
  }
  cancel(owner: object) {
    this.jobs.delete(owner);
    for (const [token, belongs] of this.awaiting) if (belongs === owner) this.awaiting.delete(token);
    this.notifyIdle();
  }
  track<T>(promise: Promise<T>, owner: object = promise): Promise<T> {
    const token = {};
    this.awaiting.set(token, owner);
    const clear = () => { this.awaiting.delete(token); this.notifyIdle(); };
    promise.then(clear, clear);
    return promise;
  }
  private notifyIdle() {
    if (this.pending) return;
    const waiting = [...this.waiters]; this.waiters.clear();
    for (const resolve of waiting) resolve();
  }
  private pump() {
    const end = this.now() + this.budget;
    for (const [key, work] of this.jobs) {
      this.jobs.delete(key);
      try { work(); } catch (error) { this.errors.push(String(error)); }
      if (this.now() >= end) break;
    }
    this.scheduled = !!this.jobs.size;
    if (this.scheduled) this.frame(() => this.pump());
    this.notifyIdle();
  }
  async idle() {
    // 两帧允许 React effects、ResizeObserver、IntersectionObserver 加入当前工作。
    do {
      // 不直接 await 旧 Promise 快照：已卸载/换代的 owner 取消后即不再阻塞。
      if (this.pending) await new Promise<void>((resolve) => this.waiters.add(resolve));
      await new Promise<void>((resolve) => this.frame(() => this.frame(resolve)));
    } while (this.pending);
  }
}

export const paintQueue = new FrameQueue();

export function detailAt(zoom: number, width: number, height: number, capture = false): number {
  if (capture) return 2;
  const h = height * zoom;
  return h < 16 || width * zoom < 6 ? 0 : h < 60 ? 1 : 2;
}

export const TILE_PIXELS = 2048;
export interface MediaRect { x: number; y: number; w: number; h: number }
export function tileKeys(rect: MediaRect, scale: number): string[] {
  const size = TILE_PIXELS / scale;
  const x0 = Math.floor(rect.x / size), y0 = Math.floor(rect.y / size);
  const x1 = Math.floor((rect.x + rect.w - 1e-7) / size), y1 = Math.floor((rect.y + rect.h - 1e-7) / size);
  const result: string[] = [];
  for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) result.push(`${x}:${y}`);
  return result;
}
