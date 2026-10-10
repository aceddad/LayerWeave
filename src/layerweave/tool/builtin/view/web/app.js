// LayerWeave 只读视图：画布上每个根（连同子树）是一块时间轴画板。画板里的根排成几行：
// 上下 = 同时（共用一把尺子）；左右 = 接续（后一个根的 0 接在前一个的结尾，名字相同的层合成一条轨道）。
// 不向数据库写任何东西；只把"用户正在看哪儿"和画板排版报给本机服务。
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const params = new URLSearchParams(location.search);
const RECORD = params.get('record') !== '0';           // 截图用的无界面页面不记录状态、不改排版，免得覆盖用户的
const CAPTURE = params.get('capture') === '1';
if (CAPTURE) document.body.classList.add('capture');
const LAZY = CAPTURE ? 'eager' : 'lazy';                 // 无界面截图时图片要立刻加载，懒加载在那里不一定触发
const DECODE = CAPTURE ? 'sync' : 'async';
const SOLO = CAPTURE && params.has('board');            // 截某一块画板时，别的画板不进画面，免得混进不相干的刻度

const NAMES = 200, ROW = 46, LANE = 40, PAD = 3, GAP = 48, STRIP = 24;

const S = {
  projects: [], data: null, project: null,
  view: params.get('view') === 'assets' ? 'assets' : 'canvas',
  boards: [], serial: null, version: null,              // boards：[{rows: [[根, 根…], …], x, y, pps}]，来自服务端的排版
  cam: {x: 32, y: 32, z: 1}, tickZ: 1,                  // 画布镜头：屏幕坐标 = 世界坐标 × z + (x, y)
  active: params.has('board') ? Number(params.get('board')) : null,   // 当前画板，用其中任一根层的编号表示
  playhead: params.has('playhead') ? Number(params.get('playhead')) : null,   // 当前画板上的时间（左右接续时是连续时间）
  selected: params.has('select') ? Number(params.get('select')) : null,
  collapsed: new Set(), only: params.has('layers') ? new Set(params.get('layers').split(',').map(Number)) : null,
  kind: 'all', frames: false, drag: null, justDragged: false,
  autoFit: true,                                        // 用户自己平移、缩放之前，窗口大小变了就重新铺满
  size: null,                                           // 上次排画板时的画布尺寸
  side: params.has('changes') ? 'changes' : 'now',      // 右侧面板：此刻 / 改动；改动打开时画布上标出改过的对象
  changes: Number(params.get('changes')) || 10,         // 看最近几次操作
  changeOps: [], changed: new Map(), changedLayers: new Map(), ghosts: new Map(),
  find: {q: '', hits: [], at: -1},
};
const KIND = (o) => (o.media ? o.media.kind : o.text != null ? 'text' : 'other');

// ---------- 数据 ----------
const api = (path) => fetch(path).then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status))));

async function loadProjects() {
  S.frames = (await api('/api/capabilities')).frames;
  S.projects = await api('/api/projects');
  const sel = $('#project');
  sel.innerHTML = S.projects.map((p) => `<option value="${p.id}">${p.id} · ${esc(p.name || '未命名')}</option>`).join('');
  const want = Number(params.get('project')) || S.projects[0]?.id;
  if (!want) return message('数据库里还没有项目。');
  sel.value = want;
  await loadProject(want, true);
}

async function loadProject(id, first = false) {
  S.project = id;
  const [data, layout] = await Promise.all([api(`/api/project/${id}`), api(`/api/layout/${id}`)]);
  S.data = data;
  adoptOrphans();
  setBoards(layout);
  await loadChanges();
  if (S.selected != null && S.active == null) S.active = objectById(S.selected)?.layer.root ?? null;
  if (S.active == null || !boardOf(S.active)) S.active = keyOf(S.boards[0]) ?? null;
  render();
  if (first) {
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    focusInitial();
  }
  report();
}

async function reloadLayout() {
  setBoards(await api(`/api/layout/${S.project}`));
  if (!boardOf(S.active)) S.active = keyOf(S.boards[0]) ?? null;
  render();
}

function setBoards(layout) {
  S.serial = layout.serial;
  S.boards = layout.boards;
  if (S.data.roots.some((r) => r.id === 0)) S.boards.push({rows: [[0]], x: null, y: null, pps: null});
}

// 找不到根的层（正常情况下核心不允许）放进一块"未归属"画板，不让它们在画布上消失
function adoptOrphans() {
  const orphans = allLayers().filter((l) => l.root == null);
  if (!orphans.length) return;
  orphans.forEach((l) => (l.root = 0));
  const times = orphans.flatMap((l) => l.objects.flatMap((o) => [o.begin, o.end])).filter(Number.isFinite);
  const a = times.length ? Math.min(...times) : 0, e = times.length ? Math.max(...times) : 10;
  S.data.roots.push({id: 0, name: '未归属的层', unit: '', key: null, extent: [a, e > a ? e : a + 10]});
}

async function poll() {
  try {
    const v = await api('/api/version');
    $('#live').classList.add('ok');
    if (S.drag || S.project == null) return;
    if (S.version != null && v.version !== S.version) { S.version = v.version; await loadProject(S.project); return; }
    S.version = v.version;
    if (S.serial != null && v.layout !== S.serial) await reloadLayout();
  } catch { $('#live').classList.remove('ok'); }
}

// ---------- 工具 ----------
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const isSec = (unit) => ['秒', 's', 'sec', 'secs', 'second', 'seconds'].includes(String(unit || '').trim().toLowerCase());
function fmt(t, unit = '') {
  if (t == null || !isFinite(t)) return '—';
  if (!isSec(unit)) return `${+(+t).toFixed(3)}${unit ? ' ' + unit : ''}`;
  const sign = t < 0 ? '-' : '', a = Math.abs(t), m = Math.floor(a / 60), s = a - m * 60;
  return `${sign}${m}:${s.toFixed(2).padStart(5, '0')}`;
}
function message(text) { const m = $('#message'); m.textContent = text; m.hidden = !text; }
let toastTimer = null;
function toast(text) { message(text); clearTimeout(toastTimer); toastTimer = setTimeout(() => message(''), 2500); }
function ago(iso) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return '刚刚';
  if (s < 3600) return `${Math.floor(s / 60)} 分钟前`;
  if (s < 86400) return `${Math.floor(s / 3600)} 小时前`;
  return new Date(iso).toLocaleString('zh-CN', {month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'});
}
const allLayers = () => S.data?.layers || [];
const allObjects = () => allLayers().flatMap((l) => l.objects.map((o) => ({...o, layer: l})));
const objectById = (id) => allObjects().find((o) => o.id === id);
const layerById = (id) => allLayers().find((l) => l.id === id);
const rootInfo = (id) => S.data?.roots.find((r) => r.id === id);
const unitOfRoot = (id) => rootInfo(id)?.unit || '';
const keyOf = (b) => b?.rows[0][0];
const rootsOf = (b) => b.rows.flat();
const boardOf = (rootId) => S.boards.find((b) => rootsOf(b).includes(rootId));
const activeBoard = () => boardOf(S.active) || S.boards[0];
const unitOf = (b) => unitOfRoot(keyOf(b));
const elOf = (b) => $(`#world .board[data-key="${keyOf(b)}"]`);
const boardFor = (el) => el && S.boards.find((b) => keyOf(b) === Number(el.dataset.key));
const canvasSize = () => [$('#canvas').clientWidth, $('#canvas').clientHeight];
const nameOf = (rootId) => rootInfo(rootId)?.name || '层 ' + rootId;

// 左右接续：第一段不动，后一段的本地 0 接在前一段的结尾（和 view_layout 的 chain_offsets 一致）
function segmentsOf(row) {
  let end = null;
  return row.map((r) => {
    const [b, e] = rootInfo(r)?.extent || [0, 10];
    const offset = end == null ? 0 : end - Math.min(0, b);
    end = offset + e;
    return {root: r, offset, begin: b + offset, end: e + offset};
  });
}
function offsetOf(rootId) {
  for (const row of boardOf(rootId)?.rows || []) { const s = segmentsOf(row).find((x) => x.root === rootId); if (s) return s.offset; }
  return 0;
}
function segmentAt(row, t) {
  const segs = segmentsOf(row);
  return segs.find((s) => t >= s.begin - 1e-9 && t < s.end) || (Math.abs(t - segs[segs.length - 1].end) < 1e-9 ? segs[segs.length - 1] : null);
}
function extentOf(b) {
  let a = Infinity, e = -Infinity;
  for (const row of b.rows) for (const s of segmentsOf(row)) { a = Math.min(a, s.begin); e = Math.max(e, s.end); }
  return isFinite(a) ? [a, e > a ? e : a + 10] : [0, 10];
}
// 每单位多少像素：用户缩放过就用存下的；否则让画板正好铺满画布宽度
const ppsOf = (b) => b.tempPps || b.pps || Math.max(400, canvasSize()[0] - NAMES - 90) / Math.max(1e-6, extentOf(b)[1] - extentOf(b)[0]);

// 一行里的轨道：按"从根往下的名字路径"把层合起来，第一章的「字幕」后面接第二章的「字幕」；只有一个根时就是原来的层树
function rowTracks(row) {
  const byKey = new Map(), children = new Map(), top = [];
  for (const seg of segmentsOf(row)) {
    const pathOf = new Map(), seen = new Map();
    for (const l of allLayers()) {
      if (l.root !== seg.root) continue;
      let key = '', parent = null;
      if (l.id !== seg.root) {
        parent = pathOf.has(l.father) ? pathOf.get(l.father) : '';
        const base = `${parent}/${l.name || l.type}`, n = (seen.get(base) || 0) + 1;
        seen.set(base, n);
        key = n > 1 ? `${base}#${n}` : base;                // 同一父层下重名的层按出现次序区分
      }
      pathOf.set(l.id, key);
      let t = byKey.get(key);
      if (!t) {
        const depth = parent == null ? 0 : (byKey.get(parent)?.depth ?? -1) + 1;
        t = {key, parent, name: l.name, type: l.type, tips: l.tips, depth, parts: []};
        byKey.set(key, t);
        if (parent == null) top.push(key);
        else { if (!children.has(parent)) children.set(parent, []); children.get(parent).push(key); }
      }
      t.parts.push({layer: l, seg});
    }
  }
  const out = [];
  const walk = (key) => { const t = byKey.get(key); t.hasChildren = children.has(key); out.push(t); (children.get(key) || []).forEach(walk); };
  top.forEach(walk);
  if (!byKey.has('')) (children.get('') || []).forEach(walk);   // 未归属的层没有根轨道
  return out;
}

function visibleTracks(row) {
  const hidden = new Set(), out = [];
  for (const t of rowTracks(row)) {
    if (t.parent != null && hidden.has(t.parent)) { hidden.add(t.key); continue; }
    if (S.only && !t.parts.some((p) => S.only.has(p.layer.id))) continue;
    out.push(t);
    if (S.collapsed.has(`${row[0]}|${t.key}`)) hidden.add(t.key);
  }
  return out;
}

// 同一轨道里互相重叠的对象排进不同的小行，免得互相遮住
function lanes(items) {
  const ends = [];
  return items.map((o) => {
    const b = o.begin, e = Math.max(o.end, o.begin);
    let k = ends.findIndex((x) => x <= b + 1e-9 && !(e === b && x === b));
    if (k < 0) { k = ends.length; ends.push(e); } else ends[k] = e;
    return k;
  });
}

// 视频画面：服务端有 ffmpeg 时由它抽帧（结果稳定，截图也拍得到）；没有时交给浏览器自己解码
const frameUrl = (o, t) => `/frame/${S.project}/${o.id}?t=${(+t).toFixed(2)}`;
const img = (src) => `<img loading="${LAZY}" decoding="${DECODE}" src="${src}" alt="">`;
const cover = (o, t) => (S.frames ? img(frameUrl(o, t)) : `<video muted preload="metadata" src="${o.media.url}#t=${t}"></video>`);

// ---------- 画布与画板 ----------
function render() {
  if (!S.data) return;
  document.title = `${S.data.project.name || '项目'} · LayerWeave 视图`;
  $('#canvas-view').hidden = S.view !== 'canvas';
  $('#assets-view').hidden = S.view !== 'assets';
  $$('.canvas-only').forEach((e) => (e.style.visibility = S.view === 'canvas' ? '' : 'hidden'));
  $$('#tabs button').forEach((b) => b.classList.toggle('on', b.dataset.view === S.view));
  if (S.view === 'canvas') renderCanvas(); else renderAssets();
  renderSide();
}

function renderCanvas() {
  S.tickZ = S.cam.z;
  S.size = canvasSize();
  $('#world').innerHTML = S.boards.map(boardHtml).join('');
  placeAuto();
  positionBoards();
  afterBoards($('#world'));
  applyCamera(false);
}

function boardHtml(b) {
  if (SOLO && b !== activeBoard()) return '';
  const [a, e] = extentOf(b), pps = ppsOf(b), unit = unitOf(b), W = (e - a) * pps + 40;
  const secs = b.rows.map((row, i) => sectionHtml(b, row, i, a, pps, W)).filter(Boolean);
  if (!secs.length) return '';
  const title = b.rows.map((row) => row.map((r) => esc(nameOf(r))).join(' → ')).join(' ＋ ');
  return `<div class="board" data-key="${keyOf(b)}" style="width:${NAMES + W + 2}px">
    <div class="bhead"><div class="stick"><span class="grip">⠿</span><b>${title}</b><span class="unit">${esc(unit || '没有单位')}</span>
      <button data-tz="out" title="时间缩小">−</button><button data-tz="fit" title="时间恢复成铺满画布">适应</button><button data-tz="in" title="时间放大">＋</button></div></div>
    <div class="rrow"><div class="corner stick">${esc(unit)}</div><div class="ruler" style="width:${W}px">${ticks(a, e, pps, unit)}</div></div>
    ${secs.join('')}
    <div class="playhead"></div>
  </div>`;
}

function sectionHtml(b, row, ri, a, pps, W) {
  const tracks = visibleTracks(row);
  if (!tracks.length) return '';
  const segs = segmentsOf(row), unit = unitOfRoot(row[0]), many = rootsOf(b).length > 1, chain = segs.length > 1;
  const names = [], lines = [];
  for (const t of tracks) {
    const items = t.parts.flatMap(({layer, seg}) => layer.objects.map((o) => ({o, offset: seg.offset, begin: o.begin + seg.offset, end: o.end + seg.offset})))
      .sort((p, q) => p.begin - q.begin || p.end - q.end || p.o.id - q.o.id);
    const ln = lanes(items), n = Math.max(1, ...ln.map((k) => k + 1));
    const h = Math.max(ROW, n * LANE + PAD * 2);
    const ck = `${row[0]}|${t.key}`, isRoot = t.key === '';
    const tog = t.hasChildren ? `<span class="tog" data-tog="${esc(ck)}">${S.collapsed.has(ck) ? '▸' : '▾'}</span>` : '<span class="tog"></span>';
    const label = isRoot ? row.map(nameOf).join(' → ') : (t.name || t.type);
    const split = isRoot && many && !chain ? `<button class="split" data-split="${row[0]}" title="把这个根拆出去，单独成一块画板">拆出</button>` : '';
    names.push(`<div class="lname${isRoot ? ' root' : ''}" style="height:${h}px;padding-left:${8 + 14 * t.depth}px" title="${esc(t.tips || label)}">${tog}<span class="lt">${esc(t.type)}</span><span class="nm">${esc(label)}</span>${layerMark(t.parts)}${split}</div>`);
    const ghosts = marksOn() ? t.parts.flatMap(({layer, seg}) => (S.ghosts.get(layer.id) || []).map((g) => ghostHtml(g, seg.offset, a, pps, unit))).join('') : '';
    lines.push(`<div class="track" data-layers="${t.parts.map((p) => p.layer.id).join(',')}" style="height:${h}px">${items.map((it, i) => block(it, ln[i], a, pps, unit)).join('')}${ghosts}</div>`);
  }
  if (chain) {                                         // 接续的一行上方多一条窄带：每一段叫什么、从画板上哪里开始
    names.unshift(`<div class="lname strip" style="height:${STRIP}px"><span class="nm">左右接续 ${segs.length} 段</span></div>`);
    lines.unshift(`<div class="segstrip" style="height:${STRIP}px">${segs.map((s) => chipHtml(s, a, pps, unit, many)).join('')}</div>`);
  }
  const seams = chain ? segs.slice(1).map((s) => `<div class="seam" style="left:${(s.offset - a) * pps}px"></div>`).join('') : '';
  return `<div class="sec" data-row="${ri}"><div class="names stick">${names.join('')}</div><div class="tracks" style="width:${W}px">${lines.join('')}${seams}</div></div>`;
}

// 每一段的名牌：是哪个根、从画板上哪里开始；拆出按钮也放在这里
function chipHtml(s, a, pps, unit, many) {
  const split = many ? `<button class="split" data-split="${s.root}" title="把这一段拆出去，单独成一块画板">拆出</button>` : '';
  return `<span class="seg-chip" style="left:${(s.offset - a) * pps}px">▶ ${esc(nameOf(s.root))}<small>${fmt(s.offset, unit)} 起</small>${split}</span>`;
}

function block(it, lane, a, pps, unit) {
  const o = it.o, k = KIND(o), instant = o.end <= o.begin;
  const left = (it.begin - a) * pps, w = Math.max(instant ? 8 : 3, (o.end - o.begin) * pps);
  const missing = o.media && !o.media.available;
  let inner = '';
  if (!missing && o.media?.url) {
    if (k === 'image') inner = img(o.media.url);
    else if (k === 'video') inner = cover(o, 0.1);
    else if (k === 'audio') inner = `<canvas data-wave="${o.media.url}"></canvas>`;
  }
  const label = o.text ?? o.name ?? '';
  const board = it.offset ? `（画板上 ${fmt(it.begin, unit)} – ${fmt(it.end, unit)}）` : '';
  const title = `#${o.id} ${o.name || ''}（${o.type}）\n${fmt(o.begin, unit)} – ${fmt(o.end, unit)}${board}${missing ? '\n文件不存在：' + o.media.source : ''}`;
  const ch = marksOn() ? S.changed.get(o.id) : null;
  const badge = ch ? `<i class="chg-n" title="${ch.n === 1 ? '最近一次' : `倒数第 ${ch.n} 次`}操作${ch.action === 'create' ? '新建' : '修改'}">${ch.n}</i>` : '';
  return `<div class="obj ${k}${instant ? ' instant' : ''}${missing ? ' missing' : ''}${o.id === S.selected ? ' sel' : ''}${ch ? ` chg chg-${ch.action}` : ''}" data-id="${o.id}"
    style="left:${left}px;width:${w}px;top:${PAD + lane * LANE}px;height:${LANE - 4}px" title="${esc(title)}">${inner}<span class="lab">${esc(label || o.type)}</span>${badge}</div>`;
}

const SEC_STEPS = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1800, 3600];
const NUM_STEPS = [0.001, 0.01, 0.1, 1, 10, 100, 1000, 10000, 100000, 1000000].flatMap((m) => [m, 2 * m, 5 * m]);
function ticks(a, e, pps, unit) {
  const steps = isSec(unit) ? SEC_STEPS : NUM_STEPS;
  const step = steps.find((s) => s * pps * S.cam.z >= 70) || steps[steps.length - 1];
  const out = [];
  for (let i = Math.ceil(a / step); i * step <= e + step; i++) {
    const t = +(i * step).toFixed(6);
    out.push(`<span class="tick" style="left:${(t - a) * pps}px">${isSec(unit) ? fmt(t, unit) : t}</span>`);
  }
  return out.join('');
}

// 没有位置的画板（第一次打开、AI 刚拆出来的）依次排在已有画板的下方，然后记住
function placeAuto() {
  const fixed = S.boards.filter((b) => b.x != null && b.y != null && elOf(b));
  let x = fixed.length ? Math.min(...fixed.map((b) => b.x)) : 0;
  let y = fixed.length ? Math.max(...fixed.map((b) => b.y + elOf(b).offsetHeight)) + GAP : 0;
  let changed = false;
  for (const b of S.boards) {
    const el = elOf(b);
    if (!el || (b.x != null && b.y != null)) continue;
    b.x = x; b.y = y; y += el.offsetHeight + GAP; changed = true;
  }
  if (changed) saveLayout();
}

function positionBoards() {
  for (const b of S.boards) { const el = elOf(b); if (el) { el.style.left = b.x + 'px'; el.style.top = b.y + 'px'; } }
}

function afterBoards(scope) {
  $$('.obj canvas[data-wave]', scope).forEach((c) => drawWave(c, c.dataset.wave));
  placePlayheads();
}

function rerenderBoard(b) {
  const el = elOf(b);
  if (!el) return renderCanvas();
  el.outerHTML = boardHtml(b);
  positionBoards();
  afterBoards(elOf(b));
  applyCamera(false);
}

function applyCamera(announce = true) {
  const {x, y, z} = S.cam;
  $('#world').style.transform = `translate(${x}px, ${y}px) scale(${z})`;
  $('#canvas').style.backgroundPosition = `${x}px ${y}px`;
  $('#canvas').style.backgroundSize = `${24 * z}px ${24 * z}px`;
  if (Math.abs(Math.log(z / S.tickZ)) > 0.2) {          // 缩放后刻度太密或太疏：重排刻度
    S.tickZ = z;
    for (const b of S.boards) { const el = elOf(b); if (el) { const [a, e] = extentOf(b); $('.ruler', el).innerHTML = ticks(a, e, ppsOf(b), unitOf(b)); } }
  }
  $$('#world .board').forEach(stick);
  if (announce) report();
}

// 画板左边移出视口时，名字列、刻度角、标题跟着往右挪，始终看得到每一行是哪一层
function stick(el) {
  const b = boardFor(el);
  if (!b) return;
  const left = S.cam.x + b.x * S.cam.z;
  el.style.setProperty('--stick', Math.max(0, Math.min(-left / S.cam.z, el.offsetWidth - NAMES - 60)) + 'px');
}

function placePlayheads() {
  const act = activeBoard();
  for (const el of $$('#world .board')) {
    const b = boardFor(el), p = $('.playhead', el);
    el.classList.toggle('active', b === act);
    if (S.playhead == null || b !== act) { p.style.display = 'none'; continue; }
    p.style.display = 'block';
    p.style.left = NAMES + (S.playhead - extentOf(b)[0]) * ppsOf(b) + 'px';
  }
  $('#clock').textContent = S.playhead != null && act ? fmt(S.playhead, unitOf(act)) : '—';
}

// ---------- 镜头 ----------
function zoomAt(mx, my, f) {
  const z = Math.min(4, Math.max(0.05, S.cam.z * f)), k = z / S.cam.z;
  S.cam.x = mx - (mx - S.cam.x) * k; S.cam.y = my - (my - S.cam.y) * k; S.cam.z = z;
  applyCamera();
}

function fitBoards(boards) {
  const els = boards.map((b) => [b, elOf(b)]).filter(([, el]) => el);
  if (!els.length || canvasSize()[1] < 50) return;     // 页面还没有尺寸（比如在后台标签里打开）：等 resize 再铺
  const x0 = Math.min(...els.map(([b]) => b.x)), y0 = Math.min(...els.map(([b]) => b.y));
  const x1 = Math.max(...els.map(([b, el]) => b.x + el.offsetWidth)), y1 = Math.max(...els.map(([b, el]) => b.y + el.offsetHeight));
  const [cw, ch] = canvasSize(), pad = 24;
  const z = Math.max(0.05, Math.min(1, (cw - 2 * pad) / (x1 - x0), (ch - 2 * pad - 20) / (y1 - y0)));
  S.cam = {x: pad - x0 * z, y: pad - y0 * z, z};
  applyCamera();
}

// 让某块画板的 [begin, end] 正好铺满画布宽度（截图、从外部链接打开时用；不改存下来的缩放）
function focusRange(b, begin, end) {
  const [cw] = canvasSize(), [a] = extentOf(b);
  b.tempPps = Math.max(1e-6, cw - NAMES - 40) / Math.max(1e-6, end - begin);
  S.cam.z = 1;
  rerenderBoard(b);
  S.cam.x = NAMES + 12 - (b.x + NAMES + (begin - a) * ppsOf(b));
  S.cam.y = 16 - b.y;
  applyCamera();
}

function focusInitial() {
  const b = activeBoard();
  if (b && params.has('begin') && params.has('end')) focusRange(b, Number(params.get('begin')), Number(params.get('end')));
  else if (b && params.has('board')) fitBoards([b]);
  else fitBoards(S.boards);
  if (params.has('focus')) focusObject(Number(params.get('focus')));
}

// 把镜头移到某个对象（或改动标记里删除前的位置）上，放在画面左上三分之一处
function focusObject(id, ghost = false) {
  const find = () => $(ghost ? `#world .ghost[data-ghost="${id}"]` : `#world .obj[data-id="${id}"]`);
  if (!find()) { toast('这个对象现在不在画布上：可能在折叠的层里，或者被只显示部分层过滤掉了'); return false; }
  if (S.cam.z < 0.6) { S.cam.z = 0.8; applyCamera(false); }
  const r = find().getBoundingClientRect(), c = canvas.getBoundingClientRect(), [cw, ch] = canvasSize();
  S.cam.x += cw / 3 - (r.left - c.left); S.cam.y += ch / 3 - (r.top - c.top); S.autoFit = false;
  applyCamera();
  if (!CAPTURE) { const node = find(); node.classList.add('flash'); setTimeout(() => node.classList.remove('flash'), 1500); }
  return true;
}

function selectObject(o, fly = true) {
  S.selected = o.id; S.active = o.layer.root; S.playhead = +(o.begin + offsetOf(o.layer.root)).toFixed(6);
  if (S.view !== 'canvas') { S.view = 'canvas'; render(); }
  else { $$('.obj.sel').forEach((n) => n.classList.remove('sel')); $(`#world .obj[data-id="${o.id}"]`)?.classList.add('sel'); placePlayheads(); renderSide(); }
  if (fly) focusObject(o.id);
  report();
}

// 时间缩放：只改这块画板每单位的像素数，鼠标下的那一刻留在原处
function timeZoom(b, f, mx) {
  const [a] = extentOf(b), old = ppsOf(b);
  S.autoFit = false;
  const t = a + ((mx - S.cam.x) / S.cam.z - b.x - NAMES) / old;
  b.pps = f == null ? null : Math.max(1e-6, old * f);
  delete b.tempPps;
  if (f != null && t >= a) S.cam.x = mx - (b.x + NAMES + (t - a) * ppsOf(b)) * S.cam.z;
  rerenderBoard(b);
  saveLayout(400);
  report();
}

// ---------- 拖动：平移画布、移动画板、拼接 ----------
const canvas = $('#canvas');
canvas.addEventListener('pointerdown', (e) => {
  if (e.button === 2 || e.target.closest('button')) return;
  const head = e.button === 0 && e.target.closest('.bhead');
  if (head) {
    const el = head.closest('.board'), b = boardFor(el);
    if (!b || keyOf(b) === 0) return;
    S.drag = {mode: 'board', b, el, x0: b.x, y0: b.y, cx: e.clientX, cy: e.clientY, moved: false, pointer: e.pointerId};
  } else {
    S.drag = {mode: 'pan', x0: S.cam.x, y0: S.cam.y, cx: e.clientX, cy: e.clientY, moved: false, pointer: e.pointerId};
  }
});
canvas.addEventListener('pointermove', (e) => {
  const d = S.drag;
  if (!d) return;
  const dx = e.clientX - d.cx, dy = e.clientY - d.cy;
  if (!d.moved && Math.hypot(dx, dy) < 4) return;
  if (!d.moved) {                                      // 真的拖起来才捕获指针；只是点一下时，点击照常落在对象、按钮上
    d.moved = true;
    canvas.setPointerCapture(d.pointer);
    d.mode === 'board' ? d.el.classList.add('dragging') : canvas.classList.add('panning');
  }
  if (d.mode === 'pan') { S.cam.x = d.x0 + dx; S.cam.y = d.y0 + dy; applyCamera(false); return; }
  d.b.x = d.x0 + dx / S.cam.z; d.b.y = d.y0 + dy / S.cam.z;
  snap(d);
  d.el.style.left = d.b.x + 'px'; d.el.style.top = d.b.y + 'px';
  stick(d.el);
  showDrop(d.drop = dropTarget(e.clientX, e.clientY, d.b));
});
canvas.addEventListener('pointercancel', () => { if (S.drag?.mode === 'board') { S.drag.el.classList.remove('dragging'); showDrop(null); saveLayout(); } S.drag = null; canvas.classList.remove('panning'); });
canvas.addEventListener('pointerup', () => {
  const d = S.drag;
  S.drag = null;
  canvas.classList.remove('panning');
  if (!d || !d.moved) return;
  S.justDragged = true;
  setTimeout(() => (S.justDragged = false), 0);
  if (d.mode === 'pan') { S.autoFit = false; return report(); }
  d.el.classList.remove('dragging');
  showDrop(null);
  if (d.drop?.ok) mergeBoards(d.b, d.drop.target, d.drop.root, d.drop.side, {x: d.x0, y: d.y0, w: d.el.offsetWidth, h: d.el.offsetHeight});
  else saveLayout();
  report();
});

// 靠近别的画板边缘时吸附：左右上下对齐，或隔一个间距并排。只是摆放，不改变时间
function snap(d) {
  const tol = 10 / S.cam.z, me = d.b, w = d.el.offsetWidth, h = d.el.offsetHeight;
  let bestX = null, bestY = null;
  for (const o of S.boards) {
    const el = elOf(o);
    if (o === me || !el) continue;
    const ow = el.offsetWidth, oh = el.offsetHeight;
    for (const x of [o.x, o.x + ow - w, o.x + ow + GAP, o.x - w - GAP]) if (Math.abs(me.x - x) < tol && (bestX == null || Math.abs(me.x - x) < Math.abs(me.x - bestX))) bestX = x;
    for (const y of [o.y, o.y + oh - h, o.y + oh + GAP, o.y - h - GAP]) if (Math.abs(me.y - y) < tol && (bestY == null || Math.abs(me.y - y) < Math.abs(me.y - bestY))) bestY = y;
  }
  if (bestX != null) me.x = bestX;
  if (bestY != null) me.y = bestY;
}

// 拖着画板经过另一块画板时，按鼠标位置决定怎么拼：
// 落在某一段的开头或结尾附近 → 左右接续；落在一行的中间 → 拼在这一行的上方或下方（同时）
function dropTarget(cx, cy, moving) {
  const hit = document.elementFromPoint(cx, cy), bel = hit?.closest('#world .board');
  if (!bel) return null;
  const target = boardFor(bel);
  if (!target || target === moving || keyOf(target) === 0) return null;
  const secs = $$('.sec', bel);
  if (!secs.length) return null;
  const sec = hit.closest('.sec') || (cy < secs[0].getBoundingClientRect().top ? secs[0] : secs[secs.length - 1]);
  const row = target.rows[Number(sec.dataset.row)], segs = segmentsOf(row);
  const tracks = $('.tracks', sec).getBoundingClientRect(), [a] = extentOf(target), pps = ppsOf(target);
  const t = a + (cx - tracks.left) / S.cam.z / pps;
  const edge = (s) => Math.max((s.end - s.begin) * 0.15, 36 / pps / S.cam.z);   // 至少 36 屏幕像素宽的接续区
  let side = null, root = row[0], at = null;
  const first = segs[0], last = segs[segs.length - 1];
  if (hit.closest('.tracks')) {
    if (t < first.begin + edge(first)) { side = 'left'; root = first.root; at = first.offset; }
    else if (t > last.end - edge(last)) { side = 'right'; root = last.root; at = last.end; }
    else for (const s of segs.slice(0, -1)) if (Math.abs(t - s.end) < edge(s)) { side = 'right'; root = s.root; at = s.end; break; }
  }
  if (!side) { const r = sec.getBoundingClientRect(); side = cy < r.top + r.height / 2 ? 'above' : 'below'; }
  const ka = rootInfo(keyOf(moving))?.key, kb = rootInfo(keyOf(target))?.key;
  let reason = '';
  if (ka == null || ka !== kb) reason = `单位不同（${unitOf(moving) || '没有单位'} / ${unitOf(target) || '没有单位'}），不能拼在一起；松手只是摆在这里`;
  else if ((side === 'left' || side === 'right') && moving.rows.length > 1) reason = '这块画板有好几行，不知道接哪一行：先把要接的根拆出来再接；松手只是摆在这里';
  return {target, el: bel, sec, root, side, at, a, pps, ok: !reason, reason};
}

function showDrop(drop) {
  $$('.dropmark, .dropnote').forEach((n) => n.remove());
  $$('#world .board.canmerge, #world .board.nomerge').forEach((n) => n.classList.remove('canmerge', 'nomerge'));
  if (!drop) return;
  drop.el.classList.add(drop.ok ? 'canmerge' : 'nomerge');
  const mark = document.createElement('div');
  if (!drop.ok) {
    mark.className = 'dropnote';
    mark.textContent = drop.reason;
  } else if (drop.side === 'left' || drop.side === 'right') {
    mark.className = 'dropmark v';
    mark.style.left = NAMES + 1 + (drop.at - drop.a) * drop.pps + 'px';
    mark.style.top = drop.sec.offsetTop + 'px';
    mark.style.height = drop.sec.offsetHeight + 'px';
    mark.textContent = drop.side === 'left' ? '接在这一段前面' : '接在这一段后面';
  } else {
    mark.className = 'dropmark';
    mark.style.top = drop.sec.offsetTop + (drop.side === 'below' ? drop.sec.offsetHeight : 0) + 'px';
  }
  drop.el.appendChild(mark);
}

function mergeBoards(moving, target, rootId, side, gap) {
  const oldH = elOf(target).offsetHeight;
  const ri = target.rows.findIndex((row) => row.includes(rootId));
  if (side === 'above' || side === 'below') target.rows.splice(ri + (side === 'below' ? 1 : 0), 0, ...moving.rows);
  else { const row = target.rows[ri]; row.splice(row.indexOf(rootId) + (side === 'right' ? 1 : 0), 0, ...moving.rows[0]); }
  S.boards.splice(S.boards.indexOf(moving), 1);
  renderCanvas();
  pushBelow(target, oldH, elOf(target).offsetHeight - oldH);
  if (gap) closeGap(gap);
  saveLayout();
}

// 被拼走的画板原来的位置留下空当：正下方的画板往上补，补到碰到上面的画板为止（和拆出时往下推对应）
function closeGap(gap) {
  const box = new Map(S.boards.map((b) => [b, {x: b.x, w: elOf(b)?.offsetWidth || 0, h: elOf(b)?.offsetHeight || 0}]));
  const overlapX = (p, q) => p.x < q.x + q.w && q.x < p.x + p.w;
  const below = S.boards.filter((o) => o.y >= gap.y + gap.h - 1 && overlapX(box.get(o), gap)).sort((p, q) => p.y - q.y);
  for (const o of below) {
    const above = S.boards.filter((p) => p !== o && p.y < o.y && overlapX(box.get(p), box.get(o))).map((p) => p.y + box.get(p).h + GAP);
    const floor = Math.max(gap.y, ...above);
    if (floor < o.y) o.y = Math.max(floor, o.y - gap.h - GAP);
  }
  positionBoards();
}

// 拆出：新画板放在原画板正下方，量出实际高度后把更下面的画板往下推
function splitRoot(rootId) {
  const b = boardOf(rootId), oldBottom = b.y + elOf(b).offsetHeight, w = elOf(b).offsetWidth;
  b.rows = b.rows.map((row) => row.filter((r) => r !== rootId)).filter((row) => row.length);
  const nb = {rows: [[rootId]], x: b.x, y: b.y, pps: b.pps};
  S.boards.splice(S.boards.indexOf(b) + 1, 0, nb);
  renderCanvas();
  nb.y = b.y + elOf(b).offsetHeight + GAP;
  const delta = nb.y + elOf(nb).offsetHeight - oldBottom;
  if (delta > 0) for (const o of S.boards) {
    const ow = elOf(o)?.offsetWidth || 0;
    if (o !== b && o !== nb && o.y >= oldBottom - 1 && o.x < b.x + w && b.x < o.x + ow) o.y += delta;
  }
  positionBoards();
  applyCamera(false);
  saveLayout();
}

// 画板变高后，把它正下方的画板往下推，免得叠在一起
function pushBelow(b, oldH, delta) {
  if (!delta) return;
  const w = elOf(b)?.offsetWidth || 0;
  for (const o of S.boards) {
    if (o === b || o.y < b.y + oldH - 1) continue;
    const ow = elOf(o)?.offsetWidth || 0;
    if (o.x < b.x + w && b.x < o.x + ow) o.y += delta;
  }
  positionBoards();
}

let saveTimer = null;
function saveLayout(delay = 0) {
  if (!RECORD || S.project == null) return;
  clearTimeout(saveTimer);
  const project = S.project;
  saveTimer = setTimeout(async () => {
    const boards = S.boards.filter((b) => rootsOf(b).every((r) => r > 0)).map(({rows, x, y, pps}) => ({rows, x, y, pps: pps ?? null}));
    try {
      const res = await fetch(`/api/layout/${project}`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({boards})}).then((r) => r.json());
      if (res.serial != null && project === S.project) S.serial = res.serial;
    } catch { /* 服务停了：下次轮询会显示断开 */ }
  }, delay);
}

// ---------- 改动：最近几次操作改了什么，画布上标出来 ----------
const marksOn = () => S.side === 'changes';

async function loadChanges() {
  S.changeOps = []; S.changed = new Map(); S.changedLayers = new Map(); S.ghosts = new Map();
  if (!marksOn() || S.project == null) return;
  try { S.changeOps = await api(`/api/changes/${S.project}?limit=${S.changes}`); } catch { toast('读不到改动记录'); return; }
  const before = new Map();
  S.changeOps.forEach((op, i) => {
    for (const it of op.items) {
      if (it.kind === 'object') {
        if (it.action !== 'delete' && !S.changed.has(it.id)) S.changed.set(it.id, {n: i + 1, action: it.action});
        const moved = it.action === 'update' && it.before && it.after && ['layer', 'begin', 'end'].some((f) => it.before[f] !== it.after[f]);
        if ((it.action === 'delete' || moved) && it.before) before.set(it.id, it.before);   // 从新往旧走，最后留下的是这几次操作之前的位置
      } else if (it.kind === 'layer' && !S.changedLayers.has(it.id)) S.changedLayers.set(it.id, {n: i + 1, action: it.action});
    }
  });
  for (const [id, was] of before) {
    const now = objectById(id);
    if (!layerById(was.layer) || (now && now.layer.id === was.layer && now.begin === was.begin && now.end === was.end)) continue;
    const ghost = {id, action: now ? 'move' : 'delete', begin: was.begin, end: was.end, label: was.name || was.text || (was.source || '').split(/[\\/]/).pop()};
    if (!S.ghosts.has(was.layer)) S.ghosts.set(was.layer, []);
    S.ghosts.get(was.layer).push(ghost);
  }
}

function ghostHtml(g, offset, a, pps, unit) {
  const left = (g.begin + offset - a) * pps, w = Math.max(6, (g.end - g.begin) * pps);
  const what = g.action === 'delete' ? '删除前' : '移动前';
  return `<div class="ghost ${g.action}" data-ghost="${g.id}" style="left:${left}px;width:${w}px;top:${PAD}px;height:${LANE - 4}px"
    title="${esc(`#${g.id} ${g.label}：${what}在这里（${fmt(g.begin, unit)} – ${fmt(g.end, unit)}）`)}"><span>${what} #${g.id} ${esc(g.label)}</span></div>`;
}

function layerMark(parts) {
  if (!marksOn()) return '';
  const hits = parts.map((p) => S.changedLayers.get(p.layer.id)).filter(Boolean);
  if (!hits.length) return '';
  const n = Math.min(...hits.map((h) => h.n));
  return `<i class="chg-dot" title="这个层在倒数第 ${n} 次操作里被${hits[0].action === 'create' ? '新建' : '修改'}">${n}</i>`;
}

function renderChanges() {
  const list = $('#chg-list');
  $('#chg-limit').value = String(S.changes);
  if (!S.changeOps.length) { list.innerHTML = '<p class="hint">这个项目还没有改动记录。</p>'; return; }
  list.innerHTML = S.changeOps.map((op, i) => `<div class="op"><div class="op-head"><b>${i + 1}</b>${ago(op.at)}${op.undo_of ? ' · 撤销' : ''} · ${op.items.length} 处</div>${op.items.map(changeItem).join('')}</div>`).join('');
}

function changeItem(it) {
  const verb = {create: '新建', update: '修改', delete: '删除'}[it.action] || it.action;
  const what = {object: '', layer: '层', bind: '关联', project: '项目'}[it.kind] ?? it.kind;
  const rec = it.after || it.before || {};
  const label = rec.name || rec.text || (rec.source || '').split(/[\\/]/).pop() || '';
  const unitOfLayer = (id) => unitOfRoot(layerById(id)?.root);
  const pos = (r) => `${fmt(r.begin, unitOfLayer(r.layer))} – ${fmt(r.end, unitOfLayer(r.layer))}`;
  const layerName = (id) => esc(layerById(id)?.name || `层 ${id}`);
  const details = [];
  if (it.kind === 'object' && it.action === 'update' && it.before && it.after) {
    if (it.before.layer !== it.after.layer) details.push(`${layerName(it.before.layer)} → ${layerName(it.after.layer)}`);
    if (it.before.begin !== it.after.begin || it.before.end !== it.after.end) details.push(`${pos(it.before)} → ${pos(it.after)}`);
    for (const x of it.information || []) details.push(`${esc(x.key)}：${esc(x.before ?? '—')} → ${esc(x.after ?? '—')}`);
    const other = (it.fields || []).filter((f) => !['layer', 'begin', 'end', 'information'].includes(f));
    if (other.length) details.push('改了 ' + other.map(esc).join('、'));
  } else if (it.kind === 'object') details.push(`${layerName(rec.layer)} · ${pos(rec)}`);
  else if (it.action === 'update' && it.fields?.length) details.push('改了 ' + it.fields.map(esc).join('、'));
  const focus = it.kind === 'object' ? ` data-focus="${it.id}"${objectById(it.id) ? '' : ' data-ghost="1"'}` : '';
  return `<div class="chg-item ${it.action}"${focus}><span class="verb">${verb}${what}</span> #${it.id} ${esc(label)}${details.length ? `<div class="det">${details.join('<br>')}</div>` : ''}</div>`;
}

// ---------- 右侧面板：此刻 / 改动 ----------
function renderSide() {
  $$('#side-tabs button').forEach((b) => b.classList.toggle('on', b.dataset.side === S.side));
  $('#now-pane').hidden = S.side !== 'now';
  $('#changes-pane').hidden = S.side !== 'changes';
  if (S.side === 'changes') renderChanges(); else renderNow();
}

function renderNow() {
  const list = $('#now-list');
  if (!S.data) return;
  const parts = [], act = activeBoard();
  const sel = S.selected != null ? objectById(S.selected) : null;
  if (sel) parts.push(`<h3>选中的对象</h3>${card(sel, true, null)}`);
  $('#now-time').textContent = S.playhead != null && act ? `${fmt(S.playhead, unitOf(act))} · ${act.rows.map((row) => row.map(nameOf).join(' → ')).join(' ＋ ')}` : '';
  if (S.playhead != null && act) {
    const t = S.playhead, near = 4 / ppsOf(act);
    for (const row of act.rows) {
      const seg = segmentAt(row, t);
      if (!seg) continue;
      const local = t - seg.offset, unit = unitOfRoot(seg.root);
      if (row.length > 1) parts.push(`<h3 class="seg">▶ ${esc(nameOf(seg.root))} 的 ${fmt(local, unit)}</h3>`);
      for (const track of visibleTracks(row)) for (const {layer} of track.parts.filter((p) => p.seg.root === seg.root)) {
        const here = layer.objects.filter((o) => (o.begin <= local && local < o.end) || (o.begin === o.end && Math.abs(o.begin - local) < near));
        if (here.length) parts.push(`<h3>${esc(layer.name || '层 ' + layer.id)} · ${esc(layer.type)}</h3>` + here.map((o) => card({...o, layer}, false, local)).join(''));
      }
    }
    if (parts.length === (sel ? 1 : 0)) parts.push('<p class="hint">这一刻没有对象。</p>');
  }
  if (parts.length) list.innerHTML = parts.join('');
  list.querySelectorAll('video[data-at]').forEach((v) => {
    const at = Number(v.dataset.at);
    v.addEventListener('loadedmetadata', () => { v.currentTime = Math.min(at, Math.max(0, v.duration - 0.05)); }, {once: true});
  });
  list.querySelectorAll('canvas[data-wave]').forEach((c) => drawWave(c, c.dataset.wave, c.dataset.mark));
}

// local：播放头在这个对象所在根里的本地时间；只在单位是秒时用来取片内画面
function card(o, full, local) {
  const k = KIND(o), missing = o.media && !o.media.available, unit = unitOfRoot(o.layer.root);
  if (local == null && S.playhead != null && boardOf(o.layer.root) === activeBoard()) local = S.playhead - offsetOf(o.layer.root);
  const onClip = local != null && isSec(unit);
  const offset = onClip ? Math.max(0, local - o.begin) : 0;
  let body = '';
  if (missing) body = `<p class="hint">文件不存在：${esc(o.media.source)}</p>`;
  else if (k === 'image') body = `<img src="${o.media.url}" alt="">`;
  else if (k === 'video') body = S.frames
    ? `<img src="${frameUrl(o, offset)}" alt="">` + (CAPTURE ? '' : `<video muted controls preload="none" src="${o.media.url}" data-at="${offset}" style="margin-top:4px"></video>`)
    : `<video muted controls preload="metadata" src="${o.media.url}" data-at="${offset}"></video>`;
  else if (k === 'audio') body = `<canvas data-wave="${o.media.url}" data-mark="${onClip && o.end > o.begin ? offset / (o.end - o.begin) : ''}"></canvas><audio controls preload="none" src="${o.media.url}" style="width:100%"></audio>`;
  if (o.text != null) body += `<div class="txt">${esc(o.text)}</div>`;
  const info = full ? `<pre>${esc(JSON.stringify(o.information, null, 1))}</pre>${o.tips ? `<pre>备注：${esc(o.tips)}</pre>` : ''}` : '';
  return `<div class="card${o.id === S.selected ? ' sel' : ''}"><div class="meta">#${o.id} ${esc(o.name)} · ${esc(o.type)} · ${fmt(o.begin, unit)} – ${fmt(o.end, unit)}</div>${body}${info}</div>`;
}

// ---------- 素材（资源管理器式预览） ----------
function renderAssets() {
  $$('#filters button').forEach((b) => b.classList.toggle('on', b.dataset.kind === S.kind));
  const items = allObjects().filter((o) => (S.kind === 'all' ? KIND(o) !== 'other' : KIND(o) === S.kind));
  $('#grid').innerHTML = items.length ? items.map(tile).join('') : '<p class="hint">没有这类素材。</p>';
  $$('#grid canvas[data-wave]').forEach((c) => drawWave(c, c.dataset.wave));
}

function tile(o) {
  const k = KIND(o), missing = o.media && !o.media.available, unit = unitOfRoot(o.layer.root);
  const color = {image: 'var(--image)', video: 'var(--video)', audio: 'var(--audio)', text: 'var(--text-c)'}[k] || 'var(--other)';
  let thumb = '';
  if (missing) thumb = '文件不存在';
  else if (k === 'image') thumb = img(o.media.url);
  else if (k === 'video') thumb = cover(o, 0.1);
  else if (k === 'audio') thumb = `<canvas data-wave="${o.media.url}"></canvas>`;
  else if (k === 'text') thumb = `<div class="txt">${esc(o.text)}</div>`;
  const label = {image: '图片', video: '视频', audio: '音频', text: '文字'}[k] || k;
  return `<div class="tile" data-id="${o.id}" title="${esc(o.media?.source || '')}"><div class="thumb">${thumb}<span class="badge" style="background:${color}">${label}</span></div>
    <div class="info"><div class="nm">${esc(o.name || (o.media?.source || '').split(/[\\/]/).pop() || '对象 ' + o.id)}</div>
    <div class="meta">${esc(o.layer.name || '层 ' + o.layer.id)} · ${fmt(o.begin, unit)} – ${fmt(o.end, unit)}</div></div></div>`;
}

// ---------- 音频波形（浏览器自己解码，结果缓存） ----------
const waves = new Map();
const audioCtx = () => (window._ac ??= new (window.AudioContext || window.webkitAudioContext)());
function peaksFor(url) {
  if (!waves.has(url)) waves.set(url, fetch(url).then((r) => r.arrayBuffer()).then((buf) => audioCtx().decodeAudioData(buf)).then((audio) => {
    const data = audio.getChannelData(0), n = 400, size = Math.floor(data.length / n) || 1, peaks = [];
    for (let i = 0; i < n; i++) { let m = 0; for (let j = i * size; j < (i + 1) * size && j < data.length; j++) m = Math.max(m, Math.abs(data[j])); peaks.push(m); }
    return peaks;
  }).catch(() => null));
  return waves.get(url);
}
async function drawWave(canvasEl, url, mark) {
  const peaks = await peaksFor(url);
  const w = (canvasEl.width = canvasEl.clientWidth || 160), h = (canvasEl.height = canvasEl.clientHeight || 40);
  const c = canvasEl.getContext('2d');
  c.clearRect(0, 0, w, h);
  if (!peaks) { c.fillStyle = '#ffffff88'; c.fillText('无法解码', 4, h / 2); return; }
  c.fillStyle = 'rgba(255,255,255,.75)';
  for (let x = 0; x < w; x++) { const p = peaks[Math.floor((x / w) * peaks.length)]; c.fillRect(x, h / 2 - (p * h) / 2, 1, Math.max(1, p * h)); }
  if (mark !== undefined && mark !== '') { c.fillStyle = '#ff4f7a'; c.fillRect(Number(mark) * w, 0, 2, h); }
}

// ---------- 报告"正在看哪儿" ----------
function visibleBoards() {
  const [cw, ch] = canvasSize(), {x, y, z} = S.cam;
  const l = -x / z, t = -y / z, r = (cw - x) / z, btm = (ch - y) / z;
  return S.boards.filter((b) => { const el = elOf(b); return el && b.x < r && b.x + el.offsetWidth > l && b.y < btm && b.y + el.offsetHeight > t; });
}
function visibleRange(b) {
  const el = elOf(b);
  if (!el) return undefined;
  const [cw] = canvasSize(), {x, z} = S.cam, [a, e] = extentOf(b), pps = ppsOf(b);
  const left = -x / z, right = (cw - x) / z;
  const t0 = Math.max(a, a + Math.max(0, left - b.x) / pps), t1 = Math.min(e, a + (right - b.x - NAMES) / pps);
  return t1 > t0 ? [+t0.toFixed(3), +t1.toFixed(3)] : undefined;
}

let reportTimer = null;
function report() {
  if (!RECORD || !S.data) return;
  clearTimeout(reportTimer);
  reportTimer = setTimeout(() => {
    const sel = S.selected != null ? objectById(S.selected) : null;
    const act = activeBoard(), canvasView = S.view === 'canvas';
    const shown = canvasView ? visibleBoards() : [];
    const at = S.playhead != null && act ? act.rows.map((row) => segmentAt(row, S.playhead)).filter(Boolean)
      .map((s) => ({root: s.root, name: nameOf(s.root), local: +(S.playhead - s.offset).toFixed(6)})) : undefined;
    const body = {
      project: S.project, view: S.view,
      board: act ? {rows: act.rows, names: act.rows.map((row) => row.map(nameOf)), unit: unitOf(act)} : undefined,
      range: canvasView && act ? visibleRange(act) : undefined,
      playhead: S.playhead ?? undefined, playhead_at: at,
      selected: sel ? {id: sel.id, layer: sel.layer.id, name: sel.name} : undefined,
      boards: canvasView ? shown.map(rootsOf) : undefined,
      layers: (canvasView ? shown : S.boards).flatMap((b) => b.rows.flatMap((row) => visibleTracks(row).flatMap((t) => t.parts.map((p) => p.layer.id)))),
    };
    fetch('/api/state', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}).catch(() => {});
  }, 400);
}

// ---------- 交互 ----------
$('#project').addEventListener('change', (e) => {
  S.selected = null; S.playhead = null; S.active = null; S.autoFit = true;
  loadProject(Number(e.target.value), true);
});
$$('#tabs button').forEach((b) => b.addEventListener('click', () => { S.view = b.dataset.view; render(); report(); }));
$$('#filters button').forEach((b) => b.addEventListener('click', () => { S.kind = b.dataset.kind; renderAssets(); }));
$('#zoom').addEventListener('click', (e) => {
  const z = e.target.dataset.zoom, [cw, ch] = canvasSize();
  if (!z || !S.data) return;
  S.autoFit = z === 'fit';
  if (z === 'fit') fitBoards(S.boards); else zoomAt(cw / 2, ch / 2, z === 'in' ? 1.25 : 0.8);
});
$$('#side-tabs button').forEach((btn) => btn.addEventListener('click', async () => {
  S.side = btn.dataset.side;
  await loadChanges();
  if (S.view === 'canvas') renderCanvas();
  renderSide();
}));
$('#chg-limit').addEventListener('change', async (e) => {
  S.changes = Number(e.target.value);
  await loadChanges();
  if (S.view === 'canvas') renderCanvas();
  renderChanges();
});
$('#chg-list').addEventListener('click', (e) => {
  const item = e.target.closest('[data-focus]');
  if (!item) return;
  const id = Number(item.dataset.focus), o = objectById(id);
  if (S.view !== 'canvas') { S.view = 'canvas'; render(); }
  if (o) selectObject(o); else focusObject(id, true);
});
$('#find').addEventListener('keydown', (e) => {
  if (e.key !== 'Enter' || !S.data) return;
  const q = e.target.value.trim().toLowerCase();
  if (!q) return;
  if (q !== S.find.q) {
    S.find = {q, at: -1, hits: allObjects().filter((o) => [o.name, o.text, o.media?.source, `#${o.id}`].some((v) => v && String(v).toLowerCase().includes(q)))};
  }
  const n = S.find.hits.length;
  $('#find-count').textContent = n ? '' : '没找到';
  if (!n) return;
  S.find.at = (S.find.at + (e.shiftKey ? -1 : 1) + n) % n;
  $('#find-count').textContent = `${S.find.at + 1}/${n}`;
  selectObject(S.find.hits[S.find.at]);
});

canvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  const r = canvas.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  const b = boardFor(e.target.closest('#world .board'));
  if (e.altKey && b) return timeZoom(b, Math.exp(-e.deltaY * 0.002), mx);
  S.autoFit = false;
  if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) { S.cam.x -= e.shiftKey ? e.deltaY : e.deltaX; return applyCamera(); }
  zoomAt(mx, my, Math.exp(-e.deltaY * 0.0015));
}, {passive: false});

canvas.addEventListener('click', (e) => {
  if (S.justDragged) { S.justDragged = false; return; }
  const tz = e.target.dataset.tz;
  if (tz) return timeZoom(boardFor(e.target.closest('.board')), tz === 'fit' ? null : tz === 'in' ? 1.6 : 1 / 1.6, canvasSize()[0] / 2);
  if (e.target.dataset.split) return splitRoot(Number(e.target.dataset.split));
  if (e.target.dataset.tog) {
    const key = e.target.dataset.tog, b = boardFor(e.target.closest('.board'));
    S.collapsed.has(key) ? S.collapsed.delete(key) : S.collapsed.add(key);
    const oldH = elOf(b).offsetHeight;
    rerenderBoard(b);
    pushBelow(b, oldH, elOf(b).offsetHeight - oldH);
    saveLayout();
    return report();
  }
  const area = e.target.closest('.tracks, .ruler');
  if (!area) return;
  const b = boardFor(area.closest('.board'));
  const rect = area.getBoundingClientRect();
  S.active = keyOf(b);
  S.playhead = +(extentOf(b)[0] + (e.clientX - rect.left) / S.cam.z / ppsOf(b)).toFixed(3);
  const obj = e.target.closest('.obj');
  if (obj) S.selected = Number(obj.dataset.id);
  else if (!e.target.closest('.ruler')) S.selected = null;
  $$('.obj.sel').forEach((n) => n.classList.remove('sel'));
  if (S.selected != null) $(`#world .obj[data-id="${S.selected}"]`)?.classList.add('sel');
  placePlayheads(); renderSide(); report();
});

$('#grid').addEventListener('click', (e) => {
  const t = e.target.closest('.tile');
  if (t) selectObject(objectById(Number(t.dataset.id)));
});

// 画布尺寸变化（窗口缩放、面板显隐）：自动宽度的画板重排；用户还没动过镜头就重新铺满
new ResizeObserver(() => {
  const size = canvasSize(), last = S.size;
  if (S.view !== 'canvas' || !S.data) return;
  const widthChanged = !last || Math.abs(size[0] - last[0]) > 1;
  if (last && !widthChanged && Math.abs(size[1] - last[1]) <= 1) return;
  S.size = size;
  if (widthChanged && S.boards.some((b) => !b.pps)) renderCanvas();   // 只有宽度变了，自动宽度的画板才需要重排
  if (S.autoFit) focusInitial();
}).observe(canvas);

// 截图用：图片、视频封面、波形都画好以后才举手（window.__layerweaveReady），截图工具等到它再拍
async function markReady() {
  if (!CAPTURE) return;
  const settle = (el, events) => new Promise((done) => {
    events.forEach((name) => el.addEventListener(name, done, {once: true}));
    setTimeout(done, 8000);                             // 个别文件解不开也不要一直等
  });
  const frames = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  await frames();
  await Promise.all($$('img').filter((i) => !i.complete).map((i) => settle(i, ['load', 'error'])));
  await Promise.all($$('video').filter((v) => v.readyState < 2 && v.preload !== 'none').map((v) => settle(v, ['loadeddata', 'error'])));
  await Promise.all([...waves.values()]);
  await Promise.all($$('img').map((i) => (i.decode ? i.decode().catch(() => {}) : null)));
  await frames();
  window.__layerweaveReady = true;
}

loadProjects().then(poll).catch((e) => message('读取失败：' + e.message)).finally(markReady);
if (!CAPTURE) setInterval(poll, 2000);
