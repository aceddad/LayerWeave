// @ts-check
// 视图插件的样板：「字数」——文字对象有几个字、每秒几个字（字幕、歌词读不读得过来）。
// 不用构建：这一个文件就是插件。试一下：view_plugin add <仓库>/frontend/view/example-plugin（或者网页顶栏「插件」里加）。
// 照着改成自己的：复制这个文件夹，放到 LayerWeave 安装目录以外的地方，改完再加进清单。
//
// 它用到了两个栏位（ViewPlugin 的字段，接口见 ../src/plugin/host.ts）：
//   side          侧栏多一个「字数」标签：每个文字层一共多少字、最快的一段每秒几个字，点一行选中那一段
//   objectDetail  选中文字对象时，详情里多一行：几个字、每秒几个字
// 顶栏页面（page）和键盘跳转点（jumpPoints）的写法见独立仓库 layerweave-plugins 的 plugins/layerweave.cuts/src/index.tsx。
//
// 只用宿主给的东西：React 是宿主那一份（host.React），不要自己 import react。下面的注释类型给编辑器和类型检查用，删掉也能跑。

/** @typedef {import('../src/plugin/host').PluginHost} PluginHost */
/** @typedef {import('../src/plugin/host').ViewPlugin} ViewPlugin */
/** @typedef {import('../src/model/model').Model} Model */
/** @typedef {import('../src/model/model').ObjWithLayer} ObjWithLayer */
/** @typedef {import('../src/types').Obj} Obj */

export const FAST = 8;   // 每秒超过几个字算"偏快"：这里随便取了 8，按自己的需要改

/**
 * 几个字（不算空白）
 * @param {string | null} text
 */
export function count(text) {
  return text ? [...text.replace(/\s/g, '')].length : 0;
}

/**
 * 每秒几个字；单位不是秒、或者对象没有长度时是 null
 * @param {Obj} o
 * @param {boolean} seconds
 */
export function perSecond(o, seconds) {
  const length = o.end - o.begin;
  return seconds && length > 0 ? count(o.text) / length : null;
}

/**
 * @param {PluginHost} host
 * @returns {ViewPlugin}
 */
export default function plugin(host) {
  const h = host.React.createElement;
  const {kindOf, isSec, fmt} = host.util;
  host.addStyle(`
    .wc-row { display: flex; justify-content: space-between; gap: 8px; padding: 4px 0; border-top: 1px solid var(--line); cursor: pointer; }
    .wc-row:hover { color: #fff; }
    .wc-fast { color: #ff8fa8; }
  `);
  /**
   * @param {Model} model
   * @param {ObjWithLayer} o
   */
  const rateOf = (model, o) => perSecond(o, isSec(model.unitOfRoot(o.layer.root)));

  // 侧栏：每个文字层一行
  function Side() {
    const {model} = host.useView();
    if (!model) return null;
    /** @type {Map<number, {name: string; chars: number; fastest: ObjWithLayer | null; rate: number}>} */
    const layers = new Map();
    for (const o of model.allObjects()) {
      if (kindOf(o) !== 'text' || o.layer.role === 'note') continue;
      const row = layers.get(o.layer.id) ?? {name: o.layer.name || `层 ${o.layer.id}`, chars: 0, fastest: null, rate: 0};
      row.chars += count(o.text);
      const rate = rateOf(model, o);
      if (rate != null && rate > row.rate) { row.rate = rate; row.fastest = o; }
      layers.set(o.layer.id, row);
    }
    return h('section', null,
      h('h2', null, '字数 ', h('span', null, `每秒超过 ${FAST} 个字标红`)),
      [...layers.values()].map((row) => h('div', {
        key: row.name + row.chars, className: 'wc-row', title: row.fastest ? '点一下选中最快的那一段' : '',
        onClick: () => row.fastest && host.selectObject(row.fastest.id),
      }, h('span', null, row.name), h('span', {className: row.rate > FAST ? 'wc-fast' : ''},
        `${row.chars} 字` + (row.fastest ? ` · 最快每秒 ${row.rate.toFixed(1)} 字` : '')))),
      layers.size ? null : h('p', {className: 'hint'}, '项目里没有文字对象。'));
  }

  // 对象详情：一行
  /** @param {{object: ObjWithLayer; model: Model}} props */
  function Detail({object, model}) {
    const rate = rateOf(model, object), unit = model.unitOfRoot(object.layer.root);
    return h('div', null, `字数：${count(object.text)} 个`,
      rate != null ? h('span', {className: rate > FAST ? 'wc-fast' : ''}, ` · 每秒 ${rate.toFixed(1)} 个（${fmt(object.end - object.begin, unit)} 里）`) : null);
  }

  return {
    label: '字数',
    title: '样板插件：文字对象有几个字、每秒几个字',
    handles: ['text'],          // 项目里没有文字对象时，侧栏不出现「字数」；详情只给文字对象
    side: Side,
    objectDetail: Detail,
  };
}
