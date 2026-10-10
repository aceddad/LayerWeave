// LayerWeave 只读视图。只读：不向数据库写任何东西，只把"用户正在看哪儿"报给本机服务。
const $ = (s) => document.querySelector(s);
const params = new URLSearchParams(location.search);
const RECORD = params.get('record') !== '0';           // 截图用的无界面页面不记录状态，免得覆盖用户的
const CAPTURE = params.get('capture') === '1';
if (CAPTURE) document.body.classList.add('capture');

const S = {
  projects: [], data: null, project: null, view: params.get('view') || 'timeline',
  pps: null, playhead: params.has('playhead') ? Number(params.get('playhead')) : null,
  selected: params.has('select') ? Number(params.get('select')) : null,
  collapsed: new Set(), only: params.has('layers') ? new Set(params.get('layers').split(',').map(Number)) : null,
  kind: 'all', version: null, autoFit: true, frames: false,   // frames：服务端能用 ffmpeg 抽帧   // 用户手动缩放前，窗口变化时自动适应宽度
};
const KIND = (o) => (o.media ? o.media.kind : o.text != null ? 'text' : 'other');
const ROW = 46, LANE = 40, PAD = 3;

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
  const keep = S.data && S.project === id ? $('#scroller').scrollLeft : null;
  S.project = id;
  S.data = await api(`/api/project/${id}`);
  if (first || S.pps == null) {                 // 先排好版、等浏览器算完宽度，再按实际宽度适应
    S.pps = 1; render();
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    fitZoom();
  }
  render();
  if (keep != null) $('#scroller').scrollLeft = keep;
  else if (params.has('begin')) $('#scroller').scrollLeft = (Number(params.get('begin')) - S.data.extent[0]) * S.pps;
  report();
}

async function poll() {
  try {
    const {version} = await api('/api/version');
    $('#live').classList.add('ok');
    if (S.version != null && version !== S.version && S.project != null) await loadProject(S.project);
    S.version = version;
  } catch { $('#live').classList.remove('ok'); }
}

// ---------- 工具 ----------
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const unit = () => S.data?.unit || '';
const isSec = () => ['秒', 's', 'sec', 'second', 'seconds'].includes(unit());
function fmt(t) {
  if (t == null || !isFinite(t)) return '—';
  if (!isSec()) return `${+t.toFixed(3)} ${unit()}`.trim();
  const m = Math.floor(t / 60), s = t - m * 60;
  return `${m}:${s.toFixed(2).padStart(5, '0')}`;
}
function message(text) { const m = $('#message'); m.textContent = text; m.hidden = !text; }
const allLayers = () => S.data?.layers || [];
const allObjects = () => allLayers().flatMap((l) => l.objects.map((o) => ({...o, layer: l})));

function visibleLayers() {
  const hidden = new Set();
  const out = [];
  for (const l of allLayers()) {
    if (S.only && !S.only.has(l.id)) continue;
    if (l.father != null && hidden.has(l.father)) { hidden.add(l.id); continue; }
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
const cover = (o, t) => (S.frames ? `<img loading="lazy" src="${frameUrl(o, t)}" alt="">` : `<video muted preload="metadata" src="${o.media.url}#t=${t}"></video>`);

// ---------- 时间轴 ----------
function fitZoom() {
  const w = Math.max(200, $('#scroller').clientWidth - 20);
  const [a, b] = rangeParam() || S.data.extent;
  S.pps = w / Math.max(1e-6, b - a);
}
function rangeParam() {
  return params.has('begin') && params.has('end') ? [Number(params.get('begin')), Number(params.get('end'))] : null;
}
const X = (t) => (t - S.data.extent[0]) * S.pps;
const T = (x) => x / S.pps + S.data.extent[0];

function render() {
  if (!S.data) return;
  document.title = `${S.data.project.name || '项目'} · LayerWeave 视图`;
  $('#timeline-view').hidden = S.view !== 'timeline';
  $('#assets-view').hidden = S.view !== 'assets';
  document.querySelectorAll('.timeline-only').forEach((e) => (e.style.visibility = S.view === 'timeline' ? '' : 'hidden'));
  document.querySelectorAll('#tabs button').forEach((b) => b.classList.toggle('on', b.dataset.view === S.view));
  if (S.view === 'timeline') renderTimeline(); else renderAssets();
  renderNow();
}

function renderTimeline() {
  const [a, b] = S.data.extent;
  const width = Math.max(X(b) + 120, $('#scroller').clientWidth);
  const names = [], tracks = [];
  const childCount = {};
  for (const l of allLayers()) if (l.father != null) childCount[l.father] = (childCount[l.father] || 0) + 1;
  for (const l of visibleLayers()) {
    const objs = [...l.objects].sort((p, q) => p.begin - q.begin || p.end - q.end || p.id - q.id);
    const ln = lanes(objs), n = Math.max(1, ...ln.map((k) => k + 1));
    const h = Math.max(ROW, n * LANE + PAD * 2);
    const tog = childCount[l.id] ? `<span class="tog" data-tog="${l.id}">${S.collapsed.has(l.id) ? '▸' : '▾'}</span>` : '<span class="tog"></span>';
    names.push(`<div class="lname" style="height:${h}px;padding-left:${8 + 14 * (l.depth ?? 0)}px" title="${esc(l.tips)}">${tog}<span class="lt">${esc(l.type)}</span><span class="nm">${esc(l.name || '层 ' + l.id)}</span></div>`);
    const blocks = objs.map((o, i) => block(o, ln[i])).join('');
    tracks.push(`<div class="track" data-layer="${l.id}" style="height:${h}px;width:${width}px">${blocks}</div>`);
  }
  $('#layer-names').innerHTML = names.join('');
  $('#tracks').innerHTML = tracks.join('');
  $('#tracks').style.width = width + 'px';
  $('#ruler').style.width = width + 'px';
  $('#ruler').innerHTML = ticks(a, b);
  syncNames();
  placePlayhead();
  document.querySelectorAll('.obj canvas[data-wave]').forEach((c) => drawWave(c, c.dataset.wave));
}

function block(o, lane) {
  const k = KIND(o), instant = o.end <= o.begin;
  const left = X(o.begin), w = Math.max(instant ? 8 : 3, X(o.end) - X(o.begin));
  const missing = o.media && !o.media.available;
  let inner = '';
  if (!missing && o.media?.url) {
    if (k === 'image') inner = `<img loading="lazy" src="${o.media.url}" alt="">`;
    else if (k === 'video') inner = cover(o, 0.1);
    else if (k === 'audio') inner = `<canvas data-wave="${o.media.url}"></canvas>`;
  }
  const label = o.text ?? o.name ?? '';
  const title = `${o.name || '对象 ' + o.id}（${o.type}）\n${fmt(o.begin)} – ${fmt(o.end)}${missing ? '\n文件不存在：' + o.media.source : ''}`;
  return `<div class="obj ${k}${instant ? ' instant' : ''}${missing ? ' missing' : ''}${o.id === S.selected ? ' sel' : ''}" data-id="${o.id}"
    style="left:${left}px;width:${w}px;top:${PAD + lane * LANE}px;height:${LANE - 4}px" title="${esc(title)}">${inner}<span class="lab">${esc(label || o.type)}</span></div>`;
}

function ticks(a, b) {
  const steps = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1800, 3600];
  const step = steps.find((s) => s * S.pps >= 70) || 3600;
  const out = [];
  for (let t = Math.ceil(a / step) * step; t <= b + step; t += step) out.push(`<span class="tick" style="left:${X(t)}px">${fmt(+t.toFixed(6))}</span>`);
  return out.join('');
}

function syncNames() { $('#layer-names').scrollTop = $('#scroller').scrollTop; }
function placePlayhead() {
  const p = $('#playhead');
  if (S.playhead == null || !S.data) { p.style.display = 'none'; return; }
  p.style.display = 'block';
  p.style.left = X(S.playhead) + 'px';
  p.style.height = $('#tracks').offsetHeight + 28 + 'px';
  $('#clock').textContent = fmt(S.playhead);
}

// ---------- 此刻面板 ----------
function renderNow() {
  const list = $('#now-list');
  if (!S.data) return;
  const parts = [];
  const sel = S.selected != null ? allObjects().find((o) => o.id === S.selected) : null;
  if (sel) parts.push(`<h3>选中的对象</h3>${card(sel, true)}`);
  if (S.playhead != null) {
    $('#now-time').textContent = fmt(S.playhead);
    const t = S.playhead;
    for (const l of visibleLayers()) {
      const here = l.objects.filter((o) => (o.begin <= t && t < o.end) || (o.begin === o.end && Math.abs(o.begin - t) < 1 / (S.pps || 1) * 4));
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
  const k = KIND(o), missing = o.media && !o.media.available;
  const offset = S.playhead != null ? Math.max(0, S.playhead - o.begin) : 0;
  let body = '';
  if (missing) body = `<p class="hint">文件不存在：${esc(o.media.source)}</p>`;
  else if (k === 'image') body = `<img src="${o.media.url}" alt="">`;
  else if (k === 'video') body = S.frames
    ? `<img src="${frameUrl(o, offset)}" alt="">` + (CAPTURE ? '' : `<video muted controls preload="none" src="${o.media.url}" data-at="${offset}" style="margin-top:4px"></video>`)
    : `<video muted controls preload="metadata" src="${o.media.url}" data-at="${offset}"></video>`;
  else if (k === 'audio') body = `<canvas data-wave="${o.media.url}" data-mark="${o.end > o.begin ? offset / (o.end - o.begin) : ''}"></canvas><audio controls preload="none" src="${o.media.url}" style="width:100%"></audio>`;
  if (o.text != null) body += `<div class="txt">${esc(o.text)}</div>`;
  const info = full ? `<pre>${esc(JSON.stringify(o.information, null, 1))}</pre>${o.tips ? `<pre>备注：${esc(o.tips)}</pre>` : ''}` : '';
  return `<div class="card${o.id === S.selected ? ' sel' : ''}"><div class="meta">#${o.id} ${esc(o.name)} · ${esc(o.type)} · ${fmt(o.begin)} – ${fmt(o.end)}</div>${body}${info}</div>`;
}

// ---------- 素材（资源管理器式预览） ----------
function renderAssets() {
  document.querySelectorAll('#filters button').forEach((b) => b.classList.toggle('on', b.dataset.kind === S.kind));
  const items = allObjects().filter((o) => (S.kind === 'all' ? KIND(o) !== 'other' : KIND(o) === S.kind));
  $('#grid').innerHTML = items.length ? items.map(tile).join('') : '<p class="hint">没有这类素材。</p>';
  document.querySelectorAll('#grid canvas[data-wave]').forEach((c) => drawWave(c, c.dataset.wave));
}

function tile(o) {
  const k = KIND(o), missing = o.media && !o.media.available;
  const color = {image: 'var(--image)', video: 'var(--video)', audio: 'var(--audio)', text: 'var(--text-c)'}[k] || 'var(--other)';
  let thumb = '';
  if (missing) thumb = '文件不存在';
  else if (k === 'image') thumb = `<img loading="lazy" src="${o.media.url}" alt="">`;
  else if (k === 'video') thumb = cover(o, 0.1);
  else if (k === 'audio') thumb = `<canvas data-wave="${o.media.url}"></canvas>`;
  else if (k === 'text') thumb = `<div class="txt">${esc(o.text)}</div>`;
  const label = {image: '图片', video: '视频', audio: '音频', text: '文字'}[k] || k;
  return `<div class="tile" data-id="${o.id}" title="${esc(o.media?.source || '')}"><div class="thumb">${thumb}<span class="badge" style="background:${color}">${label}</span></div>
    <div class="info"><div class="nm">${esc(o.name || (o.media?.source || '').split(/[\\/]/).pop() || '对象 ' + o.id)}</div>
    <div class="meta">${esc(o.layer.name || '层 ' + o.layer.id)} · ${fmt(o.begin)} – ${fmt(o.end)}</div></div></div>`;
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
async function drawWave(canvas, url, mark) {
  const peaks = await peaksFor(url);
  const w = (canvas.width = canvas.clientWidth || 160), h = (canvas.height = canvas.clientHeight || 40);
  const c = canvas.getContext('2d');
  c.clearRect(0, 0, w, h);
  if (!peaks) { c.fillStyle = '#ffffff88'; c.fillText('无法解码', 4, h / 2); return; }
  c.fillStyle = 'rgba(255,255,255,.75)';
  for (let x = 0; x < w; x++) { const p = peaks[Math.floor((x / w) * peaks.length)]; c.fillRect(x, h / 2 - (p * h) / 2, 1, Math.max(1, p * h)); }
  if (mark !== undefined && mark !== '') { c.fillStyle = '#ff4f7a'; c.fillRect(Number(mark) * w, 0, 2, h); }
}

// ---------- 报告"正在看哪儿" ----------
let reportTimer = null;
function report() {
  if (!RECORD || !S.data) return;
  clearTimeout(reportTimer);
  reportTimer = setTimeout(() => {
    const sc = $('#scroller');
    const sel = S.selected != null ? allObjects().find((o) => o.id === S.selected) : null;
    const body = {
      project: S.project, view: S.view,
      range: S.view === 'timeline' ? [+T(sc.scrollLeft).toFixed(3), +T(sc.scrollLeft + sc.clientWidth).toFixed(3)] : undefined,
      playhead: S.playhead ?? undefined,
      selected: sel ? {id: sel.id, layer: sel.layer.id, name: sel.name} : undefined,
      layers: visibleLayers().map((l) => l.id),
    };
    fetch('/api/state', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}).catch(() => {});
  }, 400);
}

// ---------- 交互 ----------
$('#project').addEventListener('change', (e) => { S.selected = null; S.playhead = null; S.pps = null; loadProject(Number(e.target.value), true); });
document.querySelectorAll('#tabs button').forEach((b) => b.addEventListener('click', () => { S.view = b.dataset.view; render(); report(); }));
document.querySelectorAll('#filters button').forEach((b) => b.addEventListener('click', () => { S.kind = b.dataset.kind; renderAssets(); }));
$('#zoom').addEventListener('click', (e) => {
  const z = e.target.dataset.zoom; if (!z || !S.data) return;
  const sc = $('#scroller'), mid = T(sc.scrollLeft + sc.clientWidth / 2);
  if (z === 'fit') { params.delete('begin'); params.delete('end'); fitZoom(); S.autoFit = true; } else { S.pps *= z === 'in' ? 1.6 : 1 / 1.6; S.autoFit = false; }
  renderTimeline();
  sc.scrollLeft = X(mid) - sc.clientWidth / 2;
  report();
});
$('#scroller').addEventListener('scroll', () => { syncNames(); report(); });
$('#layer-names').addEventListener('click', (e) => {
  const id = Number(e.target.dataset.tog); if (!id) return;
  S.collapsed.has(id) ? S.collapsed.delete(id) : S.collapsed.add(id);
  renderTimeline(); report();
});
$('#scroller').addEventListener('click', (e) => {
  const obj = e.target.closest('.obj');
  const x = e.clientX - $('#scroller').getBoundingClientRect().left + $('#scroller').scrollLeft;
  S.playhead = +T(x).toFixed(3);
  if (obj) S.selected = Number(obj.dataset.id);
  else if (!e.target.closest('#ruler')) S.selected = null;
  document.querySelectorAll('.obj.sel').forEach((n) => n.classList.remove('sel'));
  if (S.selected != null) document.querySelector(`.obj[data-id="${S.selected}"]`)?.classList.add('sel');
  placePlayhead(); renderNow(); report();
});
$('#grid').addEventListener('click', (e) => {
  const t = e.target.closest('.tile'); if (!t) return;
  const o = allObjects().find((x) => x.id === Number(t.dataset.id));
  S.selected = o.id; S.playhead = o.begin; S.view = 'timeline';
  render();
  const sc = $('#scroller'); sc.scrollLeft = Math.max(0, X(o.begin) - sc.clientWidth / 3);
  report();
});
window.addEventListener('resize', () => { if (S.view !== 'timeline' || !S.data) return; if (S.autoFit) fitZoom(); renderTimeline(); });

loadProjects().then(poll).catch((e) => message('读取失败：' + e.message));
if (!CAPTURE) setInterval(poll, 2000);
