//#region plugins/cuts/cuts.ts
function e(e, t, n, r) {
	let i = [];
	for (let a of n) (r.board == null || e.rootsOf(a).includes(r.board)) && a.rows.forEach((n, r) => {
		for (let o of t.visibleTracks(n)) {
			if (t.foldOf(o) != null) continue;
			let s = o.parts.flatMap(({ layer: t, seg: n }) => t.objects.filter((t) => ["image", "video"].includes(e.kindOf(t))).map((e) => ({
				o: e,
				layer: t,
				offset: n.offset,
				root: n.root,
				begin: e.begin + n.offset,
				end: e.end + n.offset,
				lane: 0
			}))).sort((e, t) => e.begin - t.begin || e.end - t.end || e.o.id - t.o.id), c = e.lanes(s), l = [];
			s.forEach((e, t) => {
				let s = l[c[t]];
				s && i.push({
					board: a,
					row: n,
					rowIndex: r,
					track: o,
					a: s,
					b: e,
					gap: e.begin - s.end
				}), l[c[t]] = e;
			});
		}
	});
	let a = r.begin ?? -Infinity, o = r.end ?? Infinity;
	return i.filter((e) => e.b.begin >= a && e.b.begin <= o);
}
var t = (e, t) => `${e.keyOf(t.board)}|${t.rowIndex}|${t.track.key}`;
function n(t, n, r) {
	return [...new Set(e(t, n, [r], {}).map((e) => +e.b.begin.toFixed(6)))].sort((e, t) => e - t);
}
//#endregion
//#region plugins/cuts/cuts.css?raw
var r = "/* 接缝插件的样式：插件加载时由 host.addStyle 加进页面 */\r\n.cuts-view { flex: 1; overflow: auto; padding: 12px 16px; }\r\n.cut-group h3 { font-size: 13px; margin: 14px 0 8px; }\r\n.cut-group h3 small { color: var(--dim); font-weight: normal; }\r\n.cut { display: flex; align-items: center; gap: 12px; padding: 8px; margin-bottom: 8px; border: 1px solid var(--line); border-radius: 6px; background: var(--panel); cursor: pointer; }\r\n.cut:hover { border-color: var(--accent); }\r\n.cut figure { margin: 0; width: 320px; }\r\n.cut .shot { width: 320px; height: 180px; background: #0d0f13; border-radius: 4px; overflow: hidden; display: flex; align-items: center; justify-content: center; color: var(--dim); text-align: center; font-size: 12px; }\r\n.cut .shot img, .cut .shot video { width: 100%; height: 100%; object-fit: contain; }\r\n.cut .shot.missing { background: repeating-linear-gradient(45deg, #3a2a2a, #3a2a2a 6px, #2a1f1f 6px, #2a1f1f 12px); color: #f2b0b0; }\r\n.cut figcaption { font-size: 12px; margin-top: 4px; }\r\n.cut figcaption small { color: var(--dim); }\r\n.cut-mid { display: flex; flex-direction: column; align-items: center; gap: 4px; min-width: 90px; color: var(--dim); font-size: 12px; text-align: center; }\r\n.cut-mid b { font-size: 22px; color: var(--accent); }\r\n.cut-mid .cross { color: #dfe8ff; }\r\nbody.full .cuts-view { overflow: visible; flex: none; }\r\n", i, a;
function o({ model: e, it: t, end: n, project: r, frames: o }) {
	let { Thumb: s, Frame: c } = i.components, { kindOf: l, lastAt: u, isSec: d } = i.util, f = t.o, p = e.unitOfRoot(t.root);
	return f.media && !f.media.available ? /* @__PURE__ */ a("div", { className: "shot missing" }, "文件不存在", /* @__PURE__ */ a("br", null), f.media.source) : f.media?.url ? l(f) === "image" ? /* @__PURE__ */ a("div", { className: "shot" }, /* @__PURE__ */ a(s, {
		project: r,
		o: f,
		width: 640,
		frames: o
	})) : /* @__PURE__ */ a("div", { className: "shot" }, /* @__PURE__ */ a(c, {
		project: r,
		o: f,
		at: n ? u(f, d(p)) : .05,
		frames: o
	})) : /* @__PURE__ */ a("div", { className: "shot missing" }, "没有文件");
}
function s({ model: e, cut: t, project: n, frames: r }) {
	let { kindOf: s, fmt: c, fmtSpan: l } = i.util, u = e.unitOfRoot(t.a.root), d = (e, t) => s(e.o) === "video" ? t ? "最后一帧" : "第一帧" : "图片", f = (t, n) => c(n - t.offset, e.unitOfRoot(t.root)) + (t.offset ? `（画板 ${c(n, u)}）` : ""), p = Math.abs(t.gap) < 1e-6 ? "紧接" : t.gap > 0 ? `中间空 ${l(t.gap, u)}` : `叠了 ${l(-t.gap, u)}`, m = (e) => `#${e.o.id} ${e.o.name || (e.o.media?.source || "").split(/[\\/]/).pop()}`;
	return /* @__PURE__ */ a("div", {
		className: "cut",
		onClick: () => i.selectObject(t.b.o.id)
	}, /* @__PURE__ */ a("figure", null, /* @__PURE__ */ a(o, {
		model: e,
		it: t.a,
		end: !0,
		project: n,
		frames: r
	}), /* @__PURE__ */ a("figcaption", null, m(t.a), " 的", d(t.a, !0), /* @__PURE__ */ a("br", null), /* @__PURE__ */ a("small", null, "结束于 ", f(t.a, t.a.end)))), /* @__PURE__ */ a("div", { className: "cut-mid" }, /* @__PURE__ */ a("b", null, "→"), /* @__PURE__ */ a("small", null, p), t.a.root !== t.b.root && /* @__PURE__ */ a("small", { className: "cross" }, "跨段：", e.nameOf(t.a.root), " → ", e.nameOf(t.b.root))), /* @__PURE__ */ a("figure", null, /* @__PURE__ */ a(o, {
		model: e,
		it: t.b,
		end: !1,
		project: n,
		frames: r
	}), /* @__PURE__ */ a("figcaption", null, m(t.b), " 的", d(t.b, !1), /* @__PURE__ */ a("br", null), /* @__PURE__ */ a("small", null, "开始于 ", f(t.b, t.b.begin)))));
}
function c() {
	let { model: n, boards: r, project: o, frames: c } = i.useView();
	if (i.React.useEffect(() => {
		n && i.markReady();
	}, [n]), !n || o == null) return null;
	let l = e(i.util, n, r, {
		board: i.numParam("board"),
		begin: i.numParam("begin"),
		end: i.numParam("end")
	}), u = /* @__PURE__ */ new Map();
	for (let e of l) {
		let n = t(i.util, e);
		u.has(n) || u.set(n, []), u.get(n).push(e);
	}
	return /* @__PURE__ */ a("main", { className: "cuts-view" }, !l.length && /* @__PURE__ */ a("p", { className: "hint" }, "没有接缝：同一条轨道里至少要有前后两个图片或视频。"), [...u.entries()].map(([e, t]) => {
		let r = t[0], i = r.row.map((e) => n.nameOf(e)).join(" → ") + (r.track.key ? " · " + (r.track.name || r.track.type) : "");
		return /* @__PURE__ */ a("section", {
			key: e,
			className: "cut-group"
		}, /* @__PURE__ */ a("h3", null, i, " ", /* @__PURE__ */ a("small", null, t.length, " 个接缝")), t.map((e) => /* @__PURE__ */ a(s, {
			key: `${e.a.o.id}-${e.b.o.id}`,
			model: n,
			cut: e,
			project: o,
			frames: c
		})));
	}));
}
function l(e) {
	return i = e, a = e.React.createElement, e.React.Fragment, e.addStyle(r), {
		name: "cuts",
		label: "接缝",
		title: "同一条轨道里前后相接的画面：上一段的最后一帧和下一段的第一帧并排",
		handles: ["image", "video"],
		page: c,
		jumpPoints: (t, r) => n(e.util, t, r)
	};
}
//#endregion
export { l as default };
