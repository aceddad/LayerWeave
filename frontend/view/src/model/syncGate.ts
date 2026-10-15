// 请求凭据只有在项目、代次和本地写入均未改变时有效；不取消已发出的数据库写入。
export interface SyncToken {project: number; generation: number; writes: number}
export class SyncGate {
  project: number | null = null;
  private generation = 0;
  private revision = 0;
  private pending = new Map<number, number>();
  select(project: number) { this.project = project; this.generation++; }
  selection() { return {project: this.project, generation: this.generation}; }
  sameSelection(t: {project: number | null; generation: number}) { return t.project === this.project && t.generation === this.generation; }
  blocked(project = this.project) { return project != null && (this.pending.get(project) ?? 0) > 0; }
  token(): SyncToken | null {
    return this.project == null || this.blocked() ? null : {project: this.project, generation: this.generation, writes: this.revision};
  }
  valid(t: SyncToken) { return t.project === this.project && t.generation === this.generation && t.writes === this.revision && !this.blocked(); }
  beginWrite(project: number) {
    this.revision++;
    this.pending.set(project, (this.pending.get(project) ?? 0) + 1);
    let ended = false;
    return () => {
      if (ended) return;
      ended = true;
      this.pending.set(project, (this.pending.get(project) ?? 1) - 1);
    };
  }
}
