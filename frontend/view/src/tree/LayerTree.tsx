import {tr, useI18n} from '../i18n';
// 左边的目录树：项目的层按 根 → 层 → 子层 列出来，一眼看全（画面外的、折叠起来的也在）。
// 点层名：镜头过去；▾/▸ 只在树里收起，不动画布上的折叠（那是人和 AI 共用的，另有按钮）；勾选 = 选了一组层，给"只看"、一次折叠、插件用。
// 对象不默认列：点层上的数字才列这一层的对象（最多 200 个）
import {memo, useCallback, useMemo, useState} from 'react';
import {useShallow} from 'zustand/react/shallow';
import {flyToLayer, selectObject, setTree, showOnlyPicked, toggleFold} from '../actions';
import {layerTree, togglePick} from '../model/tree';
import type {Tree, TreeNode} from '../model/tree';
import {RECORD} from '../params';
import {setState, useModel, useNotes, useStore} from '../store';

const LIST = 200;   // 展开对象时最多列几个

export function LayerTree() {
  useI18n();
  const model = useModel(), notes = useNotes();
  // 不订阅选中的对象：点画布上的对象时目录不用重画（5000 个对象的项目，点选是按毫秒算的）；列出来的对象自己订阅
  const {picked, only, target} = useStore(useShallow((s) => ({picked: s.picked, only: s.only, target: s.targetLayer})));
  const tree = useMemo(() => (model ? layerTree(model, notes?.threads) : null), [model, notes]);
  const [closed, setClosed] = useState<Set<number>>(() => new Set());
  const [listed, setListed] = useState<Set<number>>(() => new Set());
  const onOpen = useCallback((id: number) => setClosed((set) => flip(set, id)), []);
  const onList = useCallback((id: number) => setListed((set) => flip(set, id)), []);
  if (!model || !tree) return <aside className="tree" />;
  const checked = new Set(picked);
  const onlyPicked = !!only && only.size === picked.length && picked.every((id) => only.has(id));
  const rows: TreeNode[] = [];
  const walk = (id: number) => {
    const node = tree.nodes.get(id)!;
    rows.push(node);
    if (!closed.has(id)) node.children.forEach(walk);
  };
  tree.top.forEach(walk);
  return (
    <aside className="tree">
      <div className="tree-head">
        <strong>{tr("tree.title")}</strong>
        <span className="hint">{picked.length ? tr("tree.selectedCount", {value1: picked.length}) : tr("tree.layerCount", {value1: tree.nodes.size})}</span>
        <span className="spacer" />
        <button title={tr("tree.hide")} onClick={() => setTree(false)}>‹</button>
      </div>
      <div className="tree-tools">
        <button className={only ? 'on' : ''} disabled={!picked.length && !only}
                title={only ? tr("tree.resetFilterHint") : tr("tree.filterHint")}
                onClick={() => showOnlyPicked(!only || !onlyPicked)}>{only && !onlyPicked ? tr("tree.filteredCount", {value1: only.size}) : tr("tree.onlySelected")}</button>
        {RECORD && <button disabled={!picked.length} title={tr("tree.foldHint")} onClick={() => toggleFold(picked, true)}>{tr("tree.foldSelected")}</button>}
        <button disabled={!picked.length} title={tr("tree.clearHint")} onClick={() => setState({picked: []})}>{tr("tree.clear")}</button>
      </div>
      <div className="tree-rows">
        {rows.map((node) => <Row key={node.layer.id} node={node} tree={tree} picked={picked} checked={checked.has(node.layer.id)}
          target={target === node.layer.id} open={!closed.has(node.layer.id)} listed={listed.has(node.layer.id)}
          onOpen={onOpen} onList={onList} />)}
      </div>
    </aside>
  );
}

interface RowProps {
  node: TreeNode; tree: Tree; picked: number[]; checked: boolean; target: boolean; open: boolean; listed: boolean;
  onOpen: (id: number) => void; onList: (id: number) => void;
}
const flip = (set: Set<number>, id: number) => {
  const next = new Set(set);
  if (next.has(id)) next.delete(id); else next.add(id);
  return next;
};

const Row = memo(function Row({node, tree, picked, checked, target, open, listed, onOpen, onList}: RowProps) {
  useI18n();
  const {layer, depth, children, own, total, notes, mine, theirs} = node;
  const name = layer.name || layer.type || tr("common.layerId", {value1: layer.id});
  const count = children.length && total !== own ? `${own} / ${total}` : `${total}`;
  return (
    <>
      <div className={`tree-row${checked ? ' checked' : ''}${target ? ' target' : ''}${layer.hidden ? ' hidden' : ''}${layer.role === 'note' ? ' note-layer' : ''}`}
           style={{paddingLeft: 4 + depth * 14}} data-layer={layer.id}>
        <span className={`caret${children.length ? '' : ' none'}`} onClick={children.length ? () => onOpen(layer.id) : undefined}>{children.length ? (open ? '▾' : '▸') : ''}</span>
        <input type="checkbox" checked={checked} title={tr("tree.selectHint")} onChange={(e) => setState({picked: togglePick(picked, tree, layer.id, e.target.checked)})} />
        <span className="tn" title={tr("tree.layerHint", {value1: name, value2: layer.type, value3: layer.id, value4: layer.tips ? '\n' + layer.tips : ''})} onClick={() => flyToLayer(layer.id)}>{name}</span>
        <small className="tt">{layer.type}</small>
        {mine && <i className="tf mine" title={tr("tree.foldedBy", {value1: mine.by, value2: mine.tips ? '：' + mine.tips : ''})}>{tr("common.collapsed")}</i>}
        {theirs && <i className="tf theirs" title={tr("tree.foldedBy", {value1: theirs.by, value2: theirs.tips ? '：' + theirs.tips : ''})}>{theirs.by}{tr("common.collapsed")}</i>}
        {notes > 0 && <i className="tnote" title={tr("tree.notesHint", {value1: notes})}>💬{notes}</i>}
        <span className="spacer" />
        <button className={`tcount${listed ? ' on' : ''}`} disabled={!own}
                title={children.length ? tr("tree.objectsWithChildren", {value1: own, value2: total}) : tr("tree.objectsHint", {value1: own})} onClick={() => onList(layer.id)}>{count}</button>
        {RECORD && <button className="tfold" title={mine ? tr("tree.expandHint") : tr("tree.collapseHint")}
                           onClick={() => toggleFold([layer.id], !mine)}>{mine ? tr("common.expand") : tr("common.collapse.variant")}</button>}
      </div>
      {listed && own > 0 && <Objects layer={layer} depth={depth} />}
    </>
  );
});

// 一层的对象（点层上的数字才列）：自己订阅选中的对象
function Objects({layer, depth}: {layer: TreeNode['layer']; depth: number}) {
  useI18n();
  const selected = useStore((s) => s.selected);
  return (
    <div className="tree-objs" style={{paddingLeft: 36 + depth * 14}}>
      {layer.objects.slice(0, LIST).map((o) => (
        <div key={o.id} className={`tree-obj${selected === o.id ? ' sel' : ''}`} title={`#${o.id}（${o.type}）`} onClick={() => selectObject(o.id)}>
          {o.name || o.text || (o.media?.source || '').split(/[\\/]/).pop() || tr("common.objectId", {value1: o.id})}
        </div>
      ))}
      {layer.objects.length > LIST && <div className="hint">{tr("tree.morePrefix")} {layer.objects.length - LIST}  {tr("tree.moreSuffix")}</div>}
    </div>
  );
}
