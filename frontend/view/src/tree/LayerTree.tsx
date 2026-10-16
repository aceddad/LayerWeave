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
        <strong>目录</strong>
        <span className="hint">{picked.length ? `勾了 ${picked.length} 层` : `${tree.nodes.size} 层`}</span>
        <span className="spacer" />
        <button title="收起目录" onClick={() => setTree(false)}>‹</button>
      </div>
      <div className="tree-tools">
        <button className={only ? 'on' : ''} disabled={!picked.length && !only}
                title={only ? '画布上只显示这几层；点一下恢复全部' : '画布上只显示勾选的层（复制链接、截图的 --layers 是同一个）'}
                onClick={() => showOnlyPicked(!only || !onlyPicked)}>{only && !onlyPicked ? `只看 ${only.size} 层` : '只看勾选的'}</button>
        {RECORD && <button disabled={!picked.length} title="把勾选的层在你这边折叠起来（AI 也看得见）" onClick={() => toggleFold(picked, true)}>折叠勾选的</button>}
        <button disabled={!picked.length} title="取消全部勾选" onClick={() => setState({picked: []})}>清空</button>
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
  const {layer, depth, children, own, total, notes, mine, theirs} = node;
  const name = layer.name || layer.type || `层 ${layer.id}`;
  const count = children.length && total !== own ? `${own} / ${total}` : `${total}`;
  return (
    <>
      <div className={`tree-row${checked ? ' checked' : ''}${target ? ' target' : ''}${layer.hidden ? ' hidden' : ''}${layer.role === 'note' ? ' note-layer' : ''}`}
           style={{paddingLeft: 4 + depth * 14}} data-layer={layer.id}>
        <span className={`caret${children.length ? '' : ' none'}`} onClick={children.length ? () => onOpen(layer.id) : undefined}>{children.length ? (open ? '▾' : '▸') : ''}</span>
        <input type="checkbox" checked={checked} title="勾选（连同下面的层）" onChange={(e) => setState({picked: togglePick(picked, tree, layer.id, e.target.checked)})} />
        <span className="tn" title={`${name}（${layer.type}，#${layer.id}）${layer.tips ? '\n' + layer.tips : ''}\n点一下：镜头过去`} onClick={() => flyToLayer(layer.id)}>{name}</span>
        <small className="tt">{layer.type}</small>
        {mine && <i className="tf mine" title={`${mine.by} 折叠的${mine.tips ? '：' + mine.tips : ''}`}>折叠</i>}
        {theirs && <i className="tf theirs" title={`${theirs.by} 折叠的${theirs.tips ? '：' + theirs.tips : ''}`}>{theirs.by}折叠</i>}
        {notes > 0 && <i className="tnote" title={`${notes} 楼批注没处理（指着这一层、它的对象或下面的层）`}>💬{notes}</i>}
        <span className="spacer" />
        <button className={`tcount${listed ? ' on' : ''}`} disabled={!own}
                title={children.length ? `这一层 ${own} 个对象，连同下面 ${total} 个；点一下列出这一层的` : `${own} 个对象；点一下列出来`} onClick={() => onList(layer.id)}>{count}</button>
        {RECORD && <button className="tfold" title={mine ? '在你这边展开这一层' : '在你这边折叠这一层（AI 也看得见）'}
                           onClick={() => toggleFold([layer.id], !mine)}>{mine ? '展开' : '折叠'}</button>}
      </div>
      {listed && own > 0 && <Objects layer={layer} depth={depth} />}
    </>
  );
});

// 一层的对象（点层上的数字才列）：自己订阅选中的对象
function Objects({layer, depth}: {layer: TreeNode['layer']; depth: number}) {
  const selected = useStore((s) => s.selected);
  return (
    <div className="tree-objs" style={{paddingLeft: 36 + depth * 14}}>
      {layer.objects.slice(0, LIST).map((o) => (
        <div key={o.id} className={`tree-obj${selected === o.id ? ' sel' : ''}`} title={`#${o.id}（${o.type}）`} onClick={() => selectObject(o.id)}>
          {o.name || o.text || (o.media?.source || '').split(/[\\/]/).pop() || `对象 ${o.id}`}
        </div>
      ))}
      {layer.objects.length > LIST && <div className="hint">还有 {layer.objects.length - LIST} 个</div>}
    </div>
  );
}
