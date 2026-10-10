// LayerWeave 只读视图：画布上每个根（连同子树）是一块时间轴画板；单位相同的根拼在同一块画板里，共用一把尺子。
// 不向数据库写任何东西；只把"用户正在看哪儿"和画板排版报给本机服务。
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const params = new URLSearchParams(location.search);
const RECORD = params.get('record') !== '0';           // 截图用的无界面页面不记录状态、不改排版，免得覆盖用户的
const CAPTURE = params.get('capture') === '1';
if (CAPTURE) document.body.classList.add('capture');
const LAZY = CAPTURE ? 'eager' : 'lazy';
const SOLO = CAPTURE && params.has('board');            // 截某一块画板时，别的画板不进画面，免得混进不相干的刻度                 // 无界面截图时图片要立刻加载，懒加载在那里不一定触发

const NAMES = 200, HEAD = 34, RULER = 26, ROW = 46, LANE = 40, PAD = 3, GAP = 48;

const S = {
  projects: [], data: null, project: null,
  view: params.get('view') === 'assets' ? 'assets' : 'canvas',
  boards: [], serial: null, version: null,              // boards：[{roots, x, y, pps}]，来自服务端的排版
  cam: {x: 32, y: 32, z: 1}, tickZ: 1,                  // 画布镜头：屏幕坐标 = 世界坐标 × z + (x, y)
  active: params.has('board') ? Number(params.get('board')) : null,   // 当前画板，用其中任一根层的编号表示
  playhead: params.has('playhead') ? Number(params.get('playhead')) : null,
  selected: params.has('select') ? Number(params.get('select')) : null,
  collapsed: new Set(), only: params.has('layers') ? new Set(params.get('layers').split(',').map(Number)) : null,
  kind: 'all', frames: false, drag: null, justDragged: false,
  autoFit: true,                                        // 用户自己平移、缩放之前，窗口大小变了就重新铺满
  size: null,                                           // 上次排画板时的画布尺寸
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
  if (S.selected != null && S.active == null) S.active = allObjects().find((o) => o.id === S.selected)?.layer.root ?? null;
  if (S.active == null || !boardOf(S.active)) S.active = S.boards[0]?.roots[0] ?? null;
  render();
  if (first) {
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    focusInitial();
  }
  report();
}

async function reloadLayout() {
  setBoards(await api(`/api/layout/${S.project}`));
  if (!boardOf(S.active)) S.active = S.boards[0]?.roots[0] ?? null;
  render();
}

function setBoards(layout) {
  S.serial = layout.serial;
  S.boards = layout.boards;
  if (S.data.roots.some((r) => r.id === 0)) S.boards.push({roots: [0], x: null, y: null, pps: null});
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
  const m = Math.floor(t / 60), s = t - m * 60;
  return `${m}:${s.toFixed(2).padStart(5, '0')}`;
}
function message(text) { const m = $('#message'); m.textContent = text; m.hidden = !text; }
const allLayers = () => S.data?.layers || [];
const allObjects = () => allLayers().flatMap((l) => l.objects.map((o) => ({...o, layer: l})));
const rootInfo = (id) => S.data?.roots.find((r) => r.id === id);
const unitOfRoot = (id) => rootInfo(id)?.unit || '';
const boardOf = (rootId) => S.boards.find((b) => b.roots.includes(rootId));
const activeBoard = () => boardOf(S.active) || S.boards[0];
const unitOf = (b) => unitOfRoot(b.roots[0]);
const elOf = (b) => $(`#world .board[data-key="${b.roots[0]}"]`);
const boardFor = (el) => S.boards.find((b) => b.roots[0] === Number(el.dataset.key));
const canvasSize = () => [$('#canvas').clientWidth, $('#canvas').clientHeight];

function extentOf(b) {
  let a = Infinity, e = -Infinity;
  for (const r of b.roots) { const x = rootInfo(r)?.extent; if (x) { a = Math.min(a, x[0]); e = Math.max(e, x[1]); } }
  return isFinite(a) ? [a, e > a ? e : a + 10] : [0, 10];
}
// 每单位多少像素：用户缩放过就用存下的；否则让画板正好铺满画布宽度
const ppsOf = (b) => b.tempPps || b.pps || Math.max(400, canvasSize()[0] - NAMES - 90) / Math.max(1e-6, extentOf(b)[1] - extentOf(b)[0]);

function visibleLayers(rootId) {
  const hidden = new Set(), out = [];
  for (const l of allLayers()) {
    if (l.root !== rootId) continue;
    if (l.father != null && hidden.has(l.father)) { hidden.add(l.id); continue; }
    if (S.only && !S.only.has(l.id)) continue;
    out.push(l);
    if (S.collapsed.has(l.id)) hidden.add(l.id);
  }
  return out;
}

// 同一层里互相重叠的对象排进不同的小行，免得互相遮住
function lanes(objects) {
  const ends = [];
  return objects.map((o) => {
    const b = o.begin, e = Math.max(o.end, o.begin);
    let k = ends.findIndex((x) => x <= b + 1e-9 && !(e === b && x === b));
    if (k < 0) { k = ends.length; ends.push(e); } else ends[k] = e;
    return k;
  });
}

// 视频画面：服务端有 ffmpeg 时由它抽帧（结果稳定，截图也拍得到）；没有时交给浏览器自己解码
const frameUrl = (o, t) => `/frame/${S.project}/${o.id}?t=${(+t).toFixed(2)}`;
const cover = (o, t) => (S.frames ? `<img loading="${LAZY}" decoding="${CAPTURE ? 'sync' : 'async'}" src="${frameUrl(o, t)}" alt="">` : `<video muted preload="metadata" src="${o.media.url}#t=${t}"></video>`);

// ---------- 画布与画板 ----------
function render() {
  if (!S.data) return;
  document.title = `${S.data.project.name || '项目'} · LayerWeave 视图`;
  $('#canvas-view').hidden = S.view !== 'canvas';
  $('#assets-view').hidden = S.view !== 'assets';
  $$('.canvas-only').forEach((e) => (e.style.visibility = S.view === 'canvas' ? '' : 'hidden'));
  $$('#tabs button').forEach((b) => b.classList.toggle('on', b.dataset.view === S.view));
  if (S.view === 'canvas') renderCanvas(); else renderAssets();
  renderNow();
}

function renderCanvas() {
  const childCount = {};
  for (const l of allLayers()) if (l.father != null) childCount[l.father] = (childCount[l.father] || 0) + 1;
  S.tickZ = S.cam.z;
  S.size = canvasSize();
  $('#world').innerHTML = S.boards.map((b) => boardHtml(b, childCount)).join('');
  placeAuto();
  positionBoards();
  afterBoards($('#world'));
  applyCamera(false);
}

function boardHtml(b, childCount) {
  if (SOLO && b !== activeBoard()) return '';
  const [a, e] = extentOf(b), pps = ppsOf(b), unit = unitOf(b), W = (e - a) * pps + 40;
  const secs = b.roots.map((r) => sectionHtml(b, r, a, pps, W, childCount)).filter(Boolean);
  if (!secs.length) return '';
  const title = b.roots.map((r) => esc(rootInfo(r)?.name || '层 ' + r)).join(' ＋ ');
  return `<div class="board" data-key="${b.roots[0]}" style="width:${NAMES + W + 2}px">
    <div class="bhead"><div class="stick"><span class="grip">⠿</span><b>${title}</b><span class="unit">${esc(unit || '没有单位')}</span>
      <button data-tz="out" title="时间缩小">−</button><button data-tz="fit" title="时间恢复成铺满画布">适应</button><button data-tz="in" title="时间放大">＋</button></div></div>
    <div class="rrow"><div class="corner stick">${esc(unit)}</div><div class="ruler" style="width:${W}px">${ticks(a, e, pps, unit)}</div></div>
    ${secs.join('')}
    <div class="playhead"></div>
  </div>`;
}

function sectionHtml(b, rootId, a, pps, W, childCount) {
  const layers = visibleLayers(rootId);
  if (!layers.length) return '';
  const unit = unitOfRoot(rootId), names = [], tracks = [];
  for (const l of layers) {
    const objs = [...l.objects].sort((p, q) => p.begin - q.begin || p.end - q.end || p.id - q.id);
    const ln = lanes(objs), n = Math.max(1, ...ln.map((k) => k + 1));
    const h = Math.max(ROW, n * LANE + PAD * 2);
    const tog = childCount[l.id] ? `<span class="tog" data-tog="${l.id}">${S.collapsed.has(l.id) ? '▸' : '▾'}</span>` : '<span class="tog"></span>';
    const split = l.depth === 0 && b.roots.length > 1 ? `<button class="split" data-split="${l.id}" title="把这个根拆出去，单独成一块画板">拆出</button>` : '';
    names.push(`<div class="lname${l.depth === 0 ? ' root' : ''}" style="height:${h}px;padding-left:${8 + 14 * (l.depth ?? 0)}px" title="${esc(l.tips)}">${tog}<span class="lt">${esc(l.type)}</span><span class="nm">${esc(l.name || '层 ' + l.id)}</span>${split}</div>`);
    tracks.push(`<div class="track" data-layer="${l.id}" style="height:${h}px">${objs.map((o, i) => block(o, ln[i], a, pps, unit)).join('')}</div>`);
  }
  return `<div class="sec" data-root="${rootId}"><div class="names stick">${names.join('')}</div><div class="tracks" style="width:${W}px">${tracks.join('')}</div></div>`;
}

function block(o, lane, a, pps, unit) {
  const k = KIND(o), instant = o.end <= o.begin;
  const left = (o.begin - a) * pps, w = Math.max(instant ? 8 : 3, (o.end - o.begin) * pps);
  const missing = o.media && !o.media.available;
  let inner = '';
  if (!missing && o.media?.url) {
    if (k === 'image') inner = `<img loading="${LAZY}" decoding="${CAPTURE ? 'sync' : 'async'}" src="${o.media.url}" alt="">`;
    else if (k === 'video') inner = cover(o, 0.1);
    else if (k === 'audio') inner = `<canvas data-wave="${o.media.url}"></canvas>`;
  }
  const label = o.text ?? o.name ?? '';
  const title = `${o.name || '对象 ' + o.id}（${o.type}）\n${fmt(o.begin, unit)} – ${fmt(o.end, unit)}${missing ? '\n文件不存在：' + o.media.source : ''}`;
  return `<div class="obj ${k}${instant ? ' instant' : ''}${missing ? ' missing' : ''}${o.id === S.selected ? ' sel' : ''}" data-id="${o.id}"
    style="left:${left}px;width:${w}px;top:${PAD + lane * LANE}px;height:${LANE - 4}px" title="${esc(title)}">${inner}<span class="lab">${esc(label || o.type)}</span></div>`;
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
  const childCount = {};
  for (const l of allLayers()) if (l.father != null) childCount[l.father] = (childCount[l.father] || 0) + 1;
  el.outerHTML = boardHtml(b, childCount);
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
    if (!b || b.roots[0] === 0) return;
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
  if (d.drop?.ok) { d.b.x = d.x0; d.b.y = d.y0; mergeBoards(d.b, d.drop.target, d.drop.root, d.drop.side); }
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

// 拖着画板经过另一块画板时：同单位就提示拼在哪一段的上方或下方；单位不同就说明为什么不能拼
function dropTarget(cx, cy, moving) {
  const hit = document.elementFromPoint(cx, cy), bel = hit?.closest('#world .board');
  if (!bel) return null;
  const target = boardFor(bel);
  if (!target || target === moving || target.roots[0] === 0) return null;
  const secs = $$('.sec', bel);
  const sec = hit.closest('.sec') || (cy < secs[0].getBoundingClientRect().top ? secs[0] : secs[secs.length - 1]);
  const r = sec.getBoundingClientRect(), side = cy < r.top + r.height / 2 ? 'above' : 'below';
  const ka = rootInfo(moving.roots[0])?.key, kb = rootInfo(target.roots[0])?.key, ok = ka != null && ka === kb;
  const reason = ok ? '' : `单位不同（${unitOf(moving) || '没有单位'} / ${unitOf(target) || '没有单位'}），不能拼在一起；松手只是摆在这里`;
  return {target, el: bel, sec, root: Number(sec.dataset.root), side, ok, reason};
}

function showDrop(drop) {
  $$('.dropmark, .dropnote').forEach((n) => n.remove());
  $$('#world .board.canmerge, #world .board.nomerge').forEach((n) => n.classList.remove('canmerge', 'nomerge'));
  if (!drop) return;
  drop.el.classList.add(drop.ok ? 'canmerge' : 'nomerge');
  const mark = document.createElement('div');
  if (drop.ok) {
    mark.className = 'dropmark';
    mark.style.top = drop.sec.offsetTop + (drop.side === 'below' ? drop.sec.offsetHeight : 0) + 'px';
  } else {
    mark.className = 'dropnote';
    mark.textContent = drop.reason;
  }
  drop.el.appendChild(mark);
}

function mergeBoards(moving, target, rootId, side) {
  const oldH = elOf(target).offsetHeight;
  const at = target.roots.indexOf(rootId) + (side === 'below' ? 1 : 0);
  target.roots.splice(at, 0, ...moving.roots);
  S.boards.splice(S.boards.indexOf(moving), 1);
  renderCanvas();
  pushBelow(target, oldH, elOf(target).offsetHeight - oldH);
  saveLayout();
}

function splitRoot(rootId) {
  const b = boardOf(rootId), el = elOf(b);
  const oldH = el.offsetHeight, secH = $(`.sec[data-root="${rootId}"]`, el)?.offsetHeight || 0;
  b.roots = b.roots.filter((r) => r !== rootId);
  S.boards.splice(S.boards.indexOf(b) + 1, 0, {roots: [rootId], x: b.x, y: b.y + oldH - secH + GAP, pps: b.pps});
  pushBelow(b, oldH, HEAD + RULER + GAP + 4);
  renderCanvas();
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
    const boards = S.boards.filter((b) => b.roots.every((r) => r > 0)).map(({roots, x, y, pps}) => ({roots, x, y, pps: pps ?? null}));
    try {
      const res = await fetch(`/api/layout/${project}`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({boards})}).then((r) => r.json());
      if (res.serial != null && project === S.project) S.serial = res.serial;
    } catch { /* 服务停了：下次轮询会显示断开 */ }
  }, delay);
}

// ---------- 此刻面板 ----------
function renderNow() {
  const list = $('#now-list');
  if (!S.data) return;
  const parts = [], act = activeBoard();
  const sel = S.selected != null ? allObjects().find((o) => o.id === S.selected) : null;
  if (sel) parts.push(`<h3>选中的对象</h3>${card(sel, true)}`);
  $('#now-time').textContent = S.playhead != null && act ? `${fmt(S.playhead, unitOf(act))} · ${act.roots.map((r) => rootInfo(r)?.name).join(' ＋ ')}` : '';
  if (S.playhead != null && act) {
    const t = S.playhead, near = 4 / ppsOf(act);
    for (const r of act.roots) for (const l of visibleLayers(r)) {
      const here = l.objects.filter((o) => (o.begin <= t && t < o.end) || (o.begin === o.end && Math.abs(o.begin - t) < near));
      if (here.length) parts.push(`<h3>${esc(l.name || '层 ' + l.id)} · ${esc(l.type)}</h3>` + here.map((o) => card({...o, layer: l})).join(''));
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

function card(o, full = false) {
  const k = KIND(o), missing = o.media && !o.media.available, unit = unitOfRoot(o.layer.root);
  // 片内位置只在播放头落在这个对象所在的画板、且单位是秒时才有意义
  const onBoard = S.playhead != null && boardOf(o.layer.root) === activeBoard() && isSec(unit);
  const offset = onBoard ? Math.max(0, S.playhead - o.begin) : 0;
  let body = '';
  if (missing) body = `<p class="hint">文件不存在：${esc(o.media.source)}</p>`;
  else if (k === 'image') body = `<img src="${o.media.url}" alt="">`;
  else if (k === 'video') body = S.frames
    ? `<img src="${frameUrl(o, offset)}" alt="">` + (CAPTURE ? '' : `<video muted controls preload="none" src="${o.media.url}" data-at="${offset}" style="margin-top:4px"></video>`)
    : `<video muted controls preload="metadata" src="${o.media.url}" data-at="${offset}"></video>`;
  else if (k === 'audio') body = `<canvas data-wave="${o.media.url}" data-mark="${onBoard && o.end > o.begin ? offset / (o.end - o.begin) : ''}"></canvas><audio controls preload="none" src="${o.media.url}" style="width:100%"></audio>`;
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
  else if (k === 'image') thumb = `<img loading="${LAZY}" decoding="${CAPTURE ? 'sync' : 'async'}" src="${o.media.url}" alt="">`;
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
    const sel = S.selected != null ? allObjects().find((o) => o.id === S.selected) : null;
    const act = activeBoard(), canvasView = S.view === 'canvas';
    const shown = canvasView ? visibleBoards() : [];
    const body = {
      project: S.project, view: S.view,
      board: act ? {roots: act.roots, names: act.roots.map((r) => rootInfo(r)?.name || ''), unit: unitOf(act)} : undefined,
      range: canvasView && act ? visibleRange(act) : undefined,
      playhead: S.playhead ?? undefined,
      selected: sel ? {id: sel.id, layer: sel.layer.id, name: sel.name} : undefined,
      boards: canvasView ? shown.map((b) => b.roots) : undefined,
      layers: (canvasView ? shown : S.boards).flatMap((b) => b.roots.flatMap((r) => visibleLayers(r).map((l) => l.id))),
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

canvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  const r = canvas.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  const el = e.target.closest('#world .board'), b = el && boardFor(el);
  if (e.altKey && b) return timeZoom(b, Math.exp(-e.deltaY * 0.002), mx);
  S.autoFit = false;
  if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) { S.cam.x -= e.shiftKey ? e.deltaY : e.deltaX; return applyCamera(); }
  zoomAt(mx, my, Math.exp(-e.deltaY * 0.0015));
}, {passive: false});

canvas.addEventListener('click', (e) => {
  if (S.justDragged) { S.justDragged = false; return; }
  const tz = e.target.dataset.tz;
  if (tz) {
    const b = boardFor(e.target.closest('.board'));
    return timeZoom(b, tz === 'fit' ? null : tz === 'in' ? 1.6 : 1 / 1.6, canvasSize()[0] / 2);
  }
  if (e.target.dataset.split) return splitRoot(Number(e.target.dataset.split));
  if (e.target.dataset.tog) {
    const id = Number(e.target.dataset.tog);
    S.collapsed.has(id) ? S.collapsed.delete(id) : S.collapsed.add(id);
    const b = boardOf(allLayers().find((l) => l.id === id)?.root);
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
  S.active = b.roots[0];
  S.playhead = +(extentOf(b)[0] + (e.clientX - rect.left) / S.cam.z / ppsOf(b)).toFixed(3);
  const obj = e.target.closest('.obj');
  if (obj) S.selected = Number(obj.dataset.id);
  else if (!e.target.closest('.ruler')) S.selected = null;
  $$('.obj.sel').forEach((n) => n.classList.remove('sel'));
  if (S.selected != null) $(`.obj[data-id="${S.selected}"]`)?.classList.add('sel');
  placePlayheads(); renderNow(); report();
});

$('#grid').addEventListener('click', (e) => {
  const t = e.target.closest('.tile');
  if (!t) return;
  const o = allObjects().find((x) => x.id === Number(t.dataset.id));
  S.selected = o.id; S.playhead = o.begin; S.active = o.layer.root; S.view = 'canvas';
  render();
  const node = $(`#world .obj[data-id="${o.id}"]`);
  if (node) {
    const r = node.getBoundingClientRect(), c = canvas.getBoundingClientRect(), [cw, ch] = canvasSize();
    S.cam.x += cw / 3 - (r.left - c.left); S.cam.y += ch / 3 - (r.top - c.top); S.autoFit = false;
    applyCamera();
  }
  report();
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
