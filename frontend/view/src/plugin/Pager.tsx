import {tr, useI18n} from '../i18n';
// 分页：一页一屏，截图拍一张就是一页。一览、预览和别的插件共用（host.components.Pager、host.util.pageSlice）。页码从 1 数
// 地址参数 page=、per= 是初始的页码和每页张数（截图 --param page=3 拍第 3 页）

// 取出第 page 页；页码超出范围时夹到第一页或最后一页
export function pageSlice<T>(items: T[], page: number, per: number): {items: T[]; page: number; pages: number} {
  const size = Math.max(1, Math.floor(per) || 1), pages = Math.max(1, Math.ceil(items.length / size));
  const p = Math.min(Math.max(1, Math.floor(page) || 1), pages);
  return {items: items.slice((p - 1) * size, p * size), page: p, pages};
}

export function Pager({total, page, per, onPage, sizes, onPer}: {
  total: number; page: number; per: number; onPage: (page: number) => void;
  sizes?: number[]; onPer?: (per: number) => void;   // 给了就能换每页张数
}) {
  useI18n();
  const pages = Math.max(1, Math.ceil(total / Math.max(1, per)));
  return (
    <div className="pager">
      <button disabled={page <= 1} onClick={() => onPage(page - 1)}>{tr("pager.previous")}</button>
      <span>{tr("pager.position", {page, pages})}</span>
      <button disabled={page >= pages} onClick={() => onPage(page + 1)}>{tr("pager.next")}</button>
      <span className="hint">{tr("pager.total", {count: total})}</span>
      {sizes && onPer && <select value={per} title={tr("pager.sizeHint")} onChange={(e) => onPer(Number(e.target.value))}>
        {sizes.map((n) => <option key={n} value={n}>{tr("pager.perPage", {count: n})}</option>)}
      </select>}
    </div>
  );
}
