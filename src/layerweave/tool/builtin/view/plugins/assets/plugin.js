//#region plugins/assets/assets.css?raw
var e, t, n = [
	"all",
	"image",
	"video",
	"audio",
	"text"
], r = {
	all: "全部",
	image: "图片",
	video: "视频",
	audio: "音频",
	text: "文字"
}, i = {
	image: "var(--image)",
	video: "var(--video)",
	audio: "var(--audio)",
	text: "var(--text-c)"
}, a = [
	30,
	60,
	120
];
function o({ o: n, project: a, frames: o, unit: s }) {
	let { Thumb: c, Frame: l, Waveform: u } = e.components, { kindOf: d, mediaUrl: f, fmt: p } = e.util, m = d(n), h = !!n.media && !n.media.available;
	return /* @__PURE__ */ t("div", {
		className: "tile",
		title: n.media?.source ?? "",
		onClick: () => e.selectObject(n.id)
	}, /* @__PURE__ */ t("div", { className: "thumb" }, h ? "文件不存在" : m === "image" ? /* @__PURE__ */ t(c, {
		project: a,
		o: n,
		width: 320,
		frames: o
	}) : m === "video" ? /* @__PURE__ */ t(l, {
		project: a,
		o: n,
		at: .1,
		frames: o
	}) : m === "audio" ? /* @__PURE__ */ t(u, {
		url: f(n.media.url, n.media?.source),
		className: "tile-wave"
	}) : m === "text" ? /* @__PURE__ */ t("div", { className: "txt" }, n.text) : null, /* @__PURE__ */ t("span", {
		className: "badge",
		style: { background: i[m] ?? "var(--other)" }
	}, r[m] ?? m)), /* @__PURE__ */ t("div", { className: "info" }, /* @__PURE__ */ t("div", { className: "nm" }, n.name || (n.media?.source || "").split(/[\\/]/).pop() || `对象 ${n.id}`), /* @__PURE__ */ t("div", { className: "meta" }, n.layer.name || `层 ${n.layer.id}`, " · ", p(n.begin, s), " – ", p(n.end, s))));
}
function s() {
	let { React: i } = e, { model: s, project: c, frames: l } = e.useView(), [u, d] = i.useState("all"), [f, p] = i.useState(() => e.numParam("page") ?? 1), [m, h] = i.useState(() => e.numParam("per") ?? 60);
	if (i.useEffect(() => {
		s && e.markReady();
	}, [s]), !s || c == null) return null;
	let { kindOf: g, pageSlice: _ } = e.util, { Pager: v } = e.components, y = s.allObjects().filter((e) => e.layer.role !== "note" && (u === "all" ? g(e) !== "other" : g(e) === u)), b = _(y, f, m);
	return /* @__PURE__ */ t("main", { className: "assets-view" }, /* @__PURE__ */ t("div", { className: "filters" }, n.map((e) => /* @__PURE__ */ t("button", {
		key: e,
		className: u === e ? "on" : "",
		onClick: () => {
			d(e), p(1);
		}
	}, r[e])), /* @__PURE__ */ t("span", { className: "spacer" }), /* @__PURE__ */ t(v, {
		total: y.length,
		page: b.page,
		per: m,
		onPage: p,
		sizes: a,
		onPer: (e) => {
			h(e), p(1);
		}
	})), /* @__PURE__ */ t("div", { className: "grid" }, !y.length && /* @__PURE__ */ t("p", { className: "hint" }, "没有这类对象。"), b.items.map((e) => /* @__PURE__ */ t(o, {
		key: e.id,
		o: e,
		project: c,
		frames: l,
		unit: s.unitOfRoot(e.layer.root)
	}))));
}
function c(n) {
	return e = n, t = n.React.createElement, n.React.Fragment, n.addStyle("/* 一览插件的样式（以前在视图的 styles.css 里） */\r\n.assets-view { flex: 1; display: flex; flex-direction: column; min-height: 0; }\r\n.assets-view .filters { display: flex; align-items: center; gap: 4px; padding: 10px 12px; border-bottom: 1px solid var(--line); }\r\n.assets-view .grid { flex: 1; overflow: auto; padding: 12px; display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; align-content: start; }\r\n.tile { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; overflow: hidden; cursor: pointer; }\r\n.tile:hover { border-color: var(--accent); }\r\n.tile .thumb { height: 120px; background: #0d0f13; display: flex; align-items: center; justify-content: center; color: var(--dim); position: relative; }\r\n.tile .thumb img, .tile .thumb video, .tile .thumb canvas { width: 100%; height: 100%; object-fit: contain; }\r\n.tile .thumb .badge { position: absolute; top: 6px; left: 6px; font-size: 10px; padding: 0 5px; border-radius: 3px; color: #fff; }\r\n.tile .info { padding: 6px 8px; }\r\n.tile .info .nm { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }\r\n.tile .info .meta { color: var(--dim); font-size: 11px; }\r\n.tile .thumb .txt { padding: 10px; font-size: 12px; color: var(--text); overflow: hidden; max-height: 100%; }\r\n.assets-view .filters .spacer { flex: 1; }\r\nbody.full .assets-view, body.full .assets-view .grid { overflow: visible; flex: none; }\r\n"), {
		name: "assets",
		label: "一览",
		title: "按种类列出项目里所有的对象：图片、视频、音频、文字……分页；点一下回到画布上的位置",
		page: s
	};
}
//#endregion
export { c as default };
