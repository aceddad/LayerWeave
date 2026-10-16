//#region plugins/preview/frames.ts
function e(e) {
	let t = /^\s*(\d+(?:\.\d+)?)\s*([fs])\s*$/i.exec(e ?? "");
	if (!t) return null;
	let n = Number(t[1]), r = t[2].toLowerCase();
	return !(n > 0) || r === "f" && !Number.isInteger(n) ? null : {
		unit: r,
		n
	};
}
var t = (e) => `${e.n}${e.unit}`;
function n(e, t, n, r = 1e5) {
	if (!(e > 0) || !(n > 0)) return [];
	let i = Math.min(Math.max(0, t), e), a = [];
	for (let t = 0; a.length < r; t++) {
		let r = +(i + t * n).toFixed(6);
		if (r > e + 1e-9) break;
		a.push(r);
	}
	return a;
}
function r(e, t) {
	let n = 0, r = e.length - 1;
	if (r < 0) return -1;
	for (; n < r;) {
		let i = n + r + 1 >> 1;
		e[i] <= t + 1e-9 ? n = i : r = i - 1;
	}
	return n;
}
function i(e) {
	let { duration: t, from: i, step: a, fps: o, starts: s } = e;
	if (s?.length) {
		if (a.unit === "f") {
			let e = [];
			for (let t = Math.max(0, r(s, i)); t < s.length; t += a.n) e.push({
				t: s[t],
				frame: t
			});
			return e;
		}
		return n(t, i, a.n).map((e) => ({
			t: e,
			frame: r(s, e)
		}));
	}
	return n(t, i, a.unit === "f" ? a.n / Math.max(1, o) : a.n).map((e) => ({
		t: e,
		frame: Math.round(e * o)
	}));
}
var a = (e) => /<(animate|animateTransform|animateMotion|set)\b|@keyframes|animation(-name)?\s*:/i.test(e);
function o(e, t) {
	let n = 0;
	for (let t of e.matchAll(/\bdur\s*=\s*["']\s*([\d.]+)\s*(ms|s)?\s*["']/gi)) n = Math.max(n, Number(t[1]) / (t[2]?.toLowerCase() === "ms" ? 1e3 : 1));
	for (let t of e.matchAll(/animation(?:-duration)?\s*:[^;"'}]*?([\d.]+)(ms|s)\b/gi)) n = Math.max(n, Number(t[1]) / (t[2].toLowerCase() === "ms" ? 1e3 : 1));
	return n > 0 ? n : t;
}
var s = (e) => /\.(svg|gif|webp|apng)$/i.test(e.split(/[?#]/)[0]), c = "/* 预览插件的样式 */\n.preview { flex: 1; display: flex; min-height: 0; }\n.pv-list { width: 220px; flex: none; overflow: auto; border-right: 1px solid var(--line); background: var(--panel); padding: 8px 0; }\n.pv-list .hint { padding: 0 10px 6px; font-size: 12px; }\n.pv-item { padding: 3px 10px; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }\n.pv-item small { color: var(--dim); margin-left: 6px; font-size: 11px; }\n.pv-item:hover { background: #232733; }\n.pv-item.on { background: #2a3550; color: var(--sel); }\n.pv-main { flex: 1; min-width: 0; display: flex; flex-direction: column; }\n.pv-bar { display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-bottom: 1px solid var(--line); flex-wrap: wrap; }\n.pv-bar input[type=number] { width: 5em; padding: 1px 4px; }\n.pv-bar select { padding: 1px 4px; }\n.pv-bar .spacer { flex: 1; }\n.pv-status { margin: 8px 12px 0; }\n.pv-grid { flex: 1; overflow: auto; padding: 10px 12px; display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; align-content: start; }\n.pv-grid figure { margin: 0; cursor: pointer; }\n.pv-grid .pv-cell { display: block; width: 100%; height: auto; background: #0d0f13; border: 1px solid var(--line); border-radius: 4px; overflow: hidden; }\n.pv-grid .pv-cell[data-state=failed] { border-color: #a33; }\n.pv-grid figcaption { font-size: 11px; color: var(--dim); margin-top: 2px; text-align: center; }\nbody.full .preview, body.full .pv-grid { overflow: visible; flex: none; }\n", l, u, d = [
	24,
	48,
	96
], f = [
	"1f",
	"2f",
	"5f",
	"0.5s",
	"1s"
], p = new URLSearchParams(location.search), m = (e) => e.name || (e.media?.source || "").split(/[\\/]/).pop() || `对象 ${e.id}`, h = (e) => l.util.mediaUrl(e.media.url, e.media?.source), g = (e) => e.media?.source || e.media?.url || "";
function _(e, t) {
	let { kindOf: n } = l.util, r = t.length ? new Set(t) : null;
	return e.filter((e) => e.media?.url && e.media.available !== !1 && (!r || r.has(e.layer.id)) && (n(e) === "video" || n(e) === "image" && s(g(e)))).sort((e, t) => Number(n(e) !== "video") - Number(n(t) !== "video"));
}
var v = (e, t, n) => Promise.race([e, new Promise((e, r) => setTimeout(() => r(/* @__PURE__ */ Error(n + "超时")), t))]), y = (e, t) => new Promise((n, r) => {
	let i = () => {
		e.removeEventListener(t, i), e.removeEventListener("error", a), n();
	}, a = () => {
		e.removeEventListener(t, i), e.removeEventListener("error", a), r(/* @__PURE__ */ Error("文件读不出来"));
	};
	e.addEventListener(t, i), e.addEventListener("error", a);
});
async function b(e) {
	if (!("requestVideoFrameCallback" in e)) return null;
	let t = [];
	try {
		await v(new Promise((n) => {
			let r = (i, a) => {
				t.push(a.mediaTime), t.length >= 6 ? n() : e.requestVideoFrameCallback(r);
			};
			e.requestVideoFrameCallback(r), e.play().catch(() => n());
		}), 1500, "量帧率");
	} catch {}
	e.pause();
	let n = t.slice(1).map((e, n) => e - t[n]).filter((e) => e > .004 && e < .2).sort((e, t) => e - t);
	return n.length ? Math.round(1 / n[n.length >> 1]) : null;
}
async function x(e, t) {
	let n = h(e), { kindOf: r } = l.util;
	if (r(e) === "video") {
		t.muted = !0, t.preload = "auto", t.src = n, await v(y(t, "loadeddata"), 2e4, "读视频");
		let e = await b(t);
		return {
			kind: "video",
			duration: t.duration,
			fps: e,
			aspect: t.videoWidth / Math.max(1, t.videoHeight)
		};
	}
	let i = await fetch(n);
	if (!i.ok) throw Error("文件读不出来");
	if (/\.svg$/i.test(g(e).split(/[?#]/)[0]) || i.headers.get("content-type")?.includes("svg")) {
		let t = await i.text(), n = !a(t), r = /viewBox\s*=\s*["']\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)/i.exec(t);
		return {
			kind: "svg",
			text: t,
			still: n,
			duration: o(t, Math.max(.5, e.end - e.begin) || 4),
			aspect: r ? Number(r[1]) / Math.max(1, Number(r[2])) : 1
		};
	}
	let s = globalThis.ImageDecoder;
	if (!s) return {
		kind: "error",
		message: "这个浏览器不支持逐帧读图（没有 ImageDecoder）"
	};
	let c = i.headers.get("content-type") || {
		gif: "image/gif",
		webp: "image/webp",
		png: "image/png",
		apng: "image/apng"
	}[g(e).split(".").pop().toLowerCase()] || "image/gif", u = new s({
		data: await i.arrayBuffer(),
		type: c
	});
	await u.tracks.ready;
	let d = Math.min(5e3, u.tracks.selectedTrack?.frameCount ?? 1);
	if (d <= 1) return u.close(), {
		kind: "still",
		message: "这张图不会动"
	};
	let f = [], p = 0, m = 1;
	for (let e = 0; e < d; e++) {
		let { image: t } = await u.decode({ frameIndex: e });
		f.push(+p.toFixed(6)), p += (t.duration ?? 1e5) / 1e6, e === 0 && (m = t.displayWidth / Math.max(1, t.displayHeight)), t.close();
	}
	return {
		kind: "frames",
		duration: p,
		starts: f,
		decoder: u,
		aspect: m
	};
}
function S(e) {
	let t = new DOMParser().parseFromString(e, "image/svg+xml");
	t.querySelectorAll("script").forEach((e) => e.remove()), t.querySelectorAll("*").forEach((e) => {
		for (let t of [...e.attributes]) (/^on/i.test(t.name) || /^\s*javascript:/i.test(t.value)) && e.removeAttribute(t.name);
	});
	let n = t.documentElement;
	return n.setAttribute("width", "100%"), n.setAttribute("height", "100%"), new XMLSerializer().serializeToString(n);
}
function C(e, t) {
	let n = e.querySelector("svg");
	n?.pauseAnimations?.(), n?.setCurrentTime?.(t);
	for (let n of e.getAnimations({ subtree: !0 })) n.pause(), n.currentTime = t * 1e3;
}
function w(e, t, n, r) {
	let { width: i, height: a } = e.canvas, o = Math.min(i / n, a / r), s = n * o, c = r * o;
	e.clearRect(0, 0, i, a), e.drawImage(t, (i - s) / 2, (a - c) / 2, s, c);
}
function T() {
	let { React: n } = l, { model: r, selected: a, picked: o } = l.useView(), s = n.useMemo(() => r ? _(r.allObjects(), o) : [], [r, o]), [c, h] = n.useState(() => l.numParam("object") ?? null), [b, T] = n.useState(() => l.numParam("from") ?? 0), [E, D] = n.useState(() => e(p.get("step")) ?? {
		unit: "f",
		n: 1
	}), [O, k] = n.useState(() => l.numParam("fps")), [A, j] = n.useState(() => l.numParam("per") ?? 48), [M, N] = n.useState(() => l.numParam("page") ?? 1), [P, F] = n.useState(null), [I, L] = n.useState(0), R = n.useRef(null), z = n.useRef([]), B = s.find((e) => e.id === c) ?? s.find((e) => e.id === a) ?? s[0] ?? null;
	n.useEffect(() => {
		if (!r) return;
		if (!B) {
			l.markReady();
			return;
		}
		let e = !0;
		F(null), L(0);
		let t = R.current ??= document.createElement("video");
		return x(B, t).then((t) => {
			e && F(t);
		}).catch((t) => {
			e && F({
				kind: "error",
				message: t.message
			});
		}), () => {
			e = !1;
		};
	}, [r != null, B?.id]);
	let V = O ?? (P?.kind === "video" ? P.fps : null) ?? 24, H = n.useMemo(() => !P || P.kind === "still" || P.kind === "error" || P.kind === "svg" && P.still ? [] : i({
		duration: P.duration,
		from: b,
		step: E,
		fps: V,
		starts: P.kind === "frames" ? P.starts : void 0
	}), [
		P,
		b,
		E,
		V
	]), U = l.util.pageSlice(H, M, A);
	if (n.useEffect(() => {
		if (!P) return;
		if (!U.items.length) {
			l.markReady();
			return;
		}
		let e = !0;
		return L(0), (async () => {
			for (let t = 0; t < U.items.length && e; t++) {
				let n = U.items[t], r = z.current[t];
				if (r) {
					try {
						if (P.kind === "video") {
							let t = R.current;
							if (t.currentTime = Math.min(n.t, Math.max(0, P.duration - .001)), await v(y(t, "seeked"), 8e3, "跳到这一帧"), !e) break;
							w(r.getContext("2d"), t, t.videoWidth, t.videoHeight), r.dataset.t = String(t.currentTime);
						} else if (P.kind === "svg") r.innerHTML = S(P.text), C(r, n.t);
						else if (P.kind === "frames") {
							let { image: t } = await P.decoder.decode({ frameIndex: n.frame });
							e && w(r.getContext("2d"), t, t.displayWidth, t.displayHeight), t.close();
						}
						r.dataset.state = "ready";
					} catch (e) {
						r.dataset.state = "failed", r.title = e.message;
					}
					e && L(t + 1);
				}
			}
			e && l.markReady();
		})(), () => {
			e = !1;
		};
	}, [
		P,
		U.page,
		A,
		H
	]), !r) return null;
	let { fmt: W } = l.util, { Pager: G } = l.components, K = P && "aspect" in P && P.aspect > 0 ? P.aspect : 16 / 9, q = B ? P ? P.kind === "error" || P.kind === "still" ? P.message : P.kind === "svg" && P.still ? "这张 SVG 不会动" : I < U.items.length ? `正在取帧 ${I} / ${U.items.length}` : "" : "正在读文件……" : o.length ? "勾选的层里没有视频或会动的图" : "项目里没有视频或会动的图";
	return /* @__PURE__ */ u("main", { className: "preview" }, /* @__PURE__ */ u("aside", { className: "pv-list" }, /* @__PURE__ */ u("div", { className: "hint" }, o.length ? "勾选的层里" : "全部", " ", s.length, " 个"), s.map((e) => /* @__PURE__ */ u("div", {
		key: e.id,
		className: `pv-item${e.id === B?.id ? " on" : ""}`,
		title: `#${e.id} ${g(e)}`,
		onClick: () => {
			h(e.id), N(1);
		}
	}, m(e), /* @__PURE__ */ u("small", null, e.layer.name)))), /* @__PURE__ */ u("section", { className: "pv-main" }, /* @__PURE__ */ u("div", { className: "pv-bar" }, /* @__PURE__ */ u("strong", null, B ? m(B) : "预览"), /* @__PURE__ */ u("label", null, "开始 ", /* @__PURE__ */ u("input", {
		type: "number",
		min: 0,
		step: .1,
		value: b,
		onChange: (e) => {
			T(Math.max(0, Number(e.target.value) || 0)), N(1);
		}
	}), " 秒"), /* @__PURE__ */ u("label", null, "间隔 ", /* @__PURE__ */ u("select", {
		value: t(E),
		onChange: (t) => {
			D(e(t.target.value)), N(1);
		}
	}, [.../* @__PURE__ */ new Set([...f, t(E)])].map((e) => /* @__PURE__ */ u("option", {
		key: e,
		value: e
	}, e === "1f" ? "逐帧" : e.endsWith("f") ? `每 ${parseInt(e)} 帧` : `每 ${parseFloat(e)} 秒`)))), P?.kind !== "frames" && /* @__PURE__ */ u("label", { title: "视频按实际的帧率（播几帧量出来）；量不到时用 24" }, "帧率 ", /* @__PURE__ */ u("input", {
		type: "number",
		min: 1,
		max: 240,
		value: V,
		onChange: (e) => {
			k(Math.max(1, Number(e.target.value) || 24)), N(1);
		}
	})), P && "duration" in P && /* @__PURE__ */ u("span", { className: "hint" }, "共 ", W(P.duration, "秒")), /* @__PURE__ */ u("span", { className: "spacer" }), /* @__PURE__ */ u(G, {
		total: H.length,
		page: U.page,
		per: A,
		onPage: N,
		sizes: d,
		onPer: (e) => {
			j(e), N(1);
		}
	})), q && /* @__PURE__ */ u("p", { className: "hint pv-status" }, q), /* @__PURE__ */ u("div", { className: "pv-grid" }, U.items.map((e, t) => /* @__PURE__ */ u("figure", {
		key: `${B?.id}:${e.t}:${e.frame}`,
		onClick: () => B && l.selectObject(B.id)
	}, P?.kind === "svg" ? /* @__PURE__ */ u("div", {
		className: "pv-cell",
		ref: (e) => {
			z.current[t] = e;
		},
		style: { aspectRatio: String(K) }
	}) : /* @__PURE__ */ u("canvas", {
		className: "pv-cell",
		ref: (e) => {
			z.current[t] = e;
		},
		width: Math.round(320 * Math.min(2, devicePixelRatio)),
		height: Math.round(320 * Math.min(2, devicePixelRatio) / K),
		style: { aspectRatio: String(K) }
	}), /* @__PURE__ */ u("figcaption", null, W(e.t, "秒"), " · 第 ", e.frame, " 帧"))))));
}
function E(e) {
	return l = e, u = e.React.createElement, e.React.Fragment, e.addStyle(c), {
		name: "preview",
		label: "预览",
		title: "把视频、会动的 SVG、GIF 的帧罗列出来：默认逐帧，可以改开始时刻和间隔；一页一屏",
		handles: ["video", "image"],
		page: T
	};
}
//#endregion
export { E as default };
