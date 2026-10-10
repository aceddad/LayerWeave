"""人物 / 物体的入场、离场与运动自然度。
python actors.py <视频.mp4> [--start 秒] [--end 秒] [--out 前缀]

做法（适合纯色或近纯色背景的动画 / PV）：
1. 背景色 = 每帧的众数颜色（抽象片、纸底、黑底都适用）；与背景色差异大的像素 = 前景
2. 前景做闭运算后取连通区域（面积 > 0.4% 画面）= 一个"演员"
3. 逐帧按重叠度 / 距离把区域连成轨迹
4. 每条轨迹判断：
   入场：从画面边缘进来 / 由小放大（展开）/ 由淡到实（淡入）/ 一帧之内完整出现（闪现、硬切）
   离场：同理反过来
   运动：位移跳变（> 中位 4 倍且 > 画宽 2%）= 跳位；起步 / 停下时速度是否渐变（缓出 / 缓入）；方向频繁抖动 = 抖
输出：<前缀>_actors.md（文字报告）、<前缀>_actors.jpg（轨迹泳道 + 入场 / 离场缩略图）
"""
import argparse
import av, numpy as np
from scipy import ndimage
from PIL import Image, ImageDraw

W, H = 320, 180


def frames_of(path, t0, t1):
    c = av.open(path); c.streams.video[0].thread_type = 'AUTO'; fps = float(c.streams.video[0].average_rate)
    out = []
    for i, f in enumerate(c.decode(video=0)):
        t = i / fps
        if t < t0: continue
        if t1 and t >= t1: break
        out.append(np.asarray(f.to_image().resize((W, H), Image.BILINEAR)).astype(np.int16))
    return out, fps


def bg_color(a):
    q = (a[::4, ::4] // 16).reshape(-1, 3)
    vals, cnt = np.unique(q, axis=0, return_counts=True)
    return (vals[np.argmax(cnt)] * 16 + 8).astype(np.int16)


def blobs(a, min_area=0.004):
    diff = np.abs(a - bg_color(a)).sum(-1)
    fg = diff > 60
    fg = ndimage.binary_closing(fg, iterations=2)
    lab, n = ndimage.label(fg)
    out = []
    for k in range(1, n + 1):
        m = lab == k; area = m.sum() / (W * H)
        if area < min_area: continue
        ys, xs = np.nonzero(m)
        out.append(dict(mask=m, area=area, cx=xs.mean() / W, cy=ys.mean() / H, box=(xs.min(), ys.min(), xs.max(), ys.max()),
                        contrast=float(diff[m].mean()), edge=bool(xs.min() <= 1 or ys.min() <= 1 or xs.max() >= W - 2 or ys.max() >= H - 2)))
    return out


def track(all_blobs):
    tracks, live = [], []
    for t, bl in enumerate(all_blobs):
        used = set(); nxt = []
        for tr in live:
            last = tr['obs'][-1][1]; best, bi = 0, -1
            for i, b in enumerate(bl):
                if i in used: continue
                inter = (last['mask'] & b['mask']).sum(); union = (last['mask'] | b['mask']).sum()
                iou = inter / max(1, union)
                close = np.hypot(last['cx'] - b['cx'], last['cy'] - b['cy']) < 0.12 and 0.5 < b['area'] / last['area'] < 2
                sc = iou + (0.3 if close else 0)
                if sc > best: best, bi = sc, i
            if bi >= 0 and best > 0.25:
                used.add(bi); tr['obs'].append((t, bl[bi])); nxt.append(tr)
            else:
                tr['end'] = t - 1; tracks.append(tr)
        for i, b in enumerate(bl):
            if i not in used: nxt.append(dict(start=t, obs=[(t, b)]))
        live = nxt
    for tr in live: tr['end'] = len(all_blobs) - 1; tracks.append(tr)
    return [tr for tr in tracks if len(tr['obs']) >= 3]


def classify_in(obs, fps):
    first = obs[:min(len(obs), int(fps * 0.5))]
    a0, aN = first[0][1]['area'], max(o[1]['area'] for o in first)
    c0, cN = first[0][1]['contrast'], max(o[1]['contrast'] for o in first)
    if first[0][1]['edge'] and len(first) > 2 and not first[-1][1]['edge']: return '从画面边缘进入'
    if a0 < 0.45 * aN: return f'由小变大（展开 / 放大），{_ramp(first, "area")} 帧长成'
    if c0 < 0.6 * cN: return f'淡入，{_ramp(first, "contrast")} 帧到实'
    return '一帧内完整出现（闪现 / 硬切）'


def _ramp(seq, key):
    vals = [o[1][key] for o in seq]; top = max(vals)
    return next((i for i, v in enumerate(vals) if v >= 0.9 * top), len(vals))


def classify_out(obs, fps, total):
    last = obs[-min(len(obs), int(fps * 0.5)):]
    if obs[-1][0] >= total - 1: return '到片段结尾还在'
    a0, aN = max(o[1]['area'] for o in last), last[-1][1]['area']
    c0, cN = max(o[1]['contrast'] for o in last), last[-1][1]['contrast']
    if last[-1][1]['edge'] and not last[0][1]['edge']: return '从画面边缘离开'
    if aN < 0.45 * a0: return '由大变小（收起 / 缩小）后消失'
    if cN < 0.6 * c0: return '淡出'
    return '一帧内消失（硬切）'


def motion(obs, fps):
    P = np.array([(o[1]['cx'], o[1]['cy']) for o in obs]); A = np.array([o[1]['area'] for o in obs])
    if len(P) < 4: return {}
    v = np.hypot(*np.diff(P, axis=0).T)
    med = np.median(v[v > 1e-4]) if (v > 1e-4).any() else 0
    jumps = [int(obs[i + 1][0]) for i in np.nonzero((v > 4 * max(med, 1e-4)) & (v > 0.02))[0]]
    moving = v > max(0.002, med * 0.5)
    notes = []
    if moving.any():
        i0 = int(np.argmax(moving)); i1 = len(moving) - 1 - int(np.argmax(moving[::-1]))
        seg = v[i0:i1 + 1]
        if len(seg) >= 6:
            k = max(2, len(seg) // 5)
            notes.append('起步' + ('有缓出' if seg[:k].mean() < 0.7 * seg.max() else '没有缓出（一下子就快）'))
            notes.append('停下' + ('有缓入' if seg[-k:].mean() < 0.7 * seg.max() else '没有缓入（急停）'))
            cv = seg.std() / max(1e-6, seg.mean())
            if cv < 0.15: notes.append('全程匀速（机械感）')
        d = np.diff(P, axis=0); ang = np.arctan2(d[:, 1], d[:, 0])
        turn = np.abs(np.angle(np.exp(1j * np.diff(ang))))[moving[1:] & moving[:-1]]
        if len(turn) > 6 and (turn > 2.0).mean() > 0.25: notes.append('方向频繁来回（抖）')
    da = np.abs(np.diff(A)) / np.maximum(A[:-1], 1e-6)
    pops = [int(obs[i + 1][0]) for i in np.nonzero(da > 0.35)[0]]
    return dict(travel=float(np.hypot(*(P[-1] - P[0]))), max_speed=float(v.max()), jumps=jumps, size_pops=pops, notes=notes)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('video'); ap.add_argument('--start', type=float, default=0); ap.add_argument('--end', type=float); ap.add_argument('--out')
    a = ap.parse_args(); out = a.out or a.video.rsplit('.', 1)[0]
    F, fps = frames_of(a.video, a.start, a.end)
    tr = track([blobs(f) for f in F])
    tr.sort(key=lambda t: t['obs'][0][0])
    L = [f"片段 {a.start:.2f}–{a.start + len(F) / fps:.2f}s，{len(F)} 帧，追踪到 {len(tr)} 个演员（面积 > 0.4% 画面、存在 ≥ 3 帧）", '']
    for i, t in enumerate(tr):
        s, e = t['obs'][0][0], t['obs'][-1][0]; mo = motion(t['obs'], fps)
        b = t['obs'][len(t['obs']) // 2][1]
        L.append(f"■ A{i}  {a.start + s / fps:.2f}s → {a.start + e / fps:.2f}s（{e - s + 1} 帧），大小约 {b['area']:.1%} 画面，位置 ({b['cx']:.2f}, {b['cy']:.2f})")
        L.append(f"   入场：{classify_in(t['obs'], fps)}  ｜  离场：{classify_out(t['obs'], fps, len(F))}")
        if mo:
            L.append(f"   移动距离 {mo['travel']:.2f} 画宽，最快 {mo['max_speed']:.3f}/帧" + ('；' + '，'.join(mo['notes']) if mo['notes'] else ''))
            if mo['jumps']: L.append(f"   ⚠ 跳位：{', '.join(f'{a.start + j / fps:.2f}s' for j in mo['jumps'][:8])}")
            if mo['size_pops']: L.append(f"   ⚠ 大小突变：{', '.join(f'{a.start + j / fps:.2f}s' for j in mo['size_pops'][:8])}")
    txt = '\n'.join(L); open(out + '_actors.md', 'w', encoding='utf8').write(txt + '\n'); print(txt)
    # 泳道图
    n = len(F); LW, RH, TW = 60, 70, 96; TH = TW * H // W
    img = Image.new('RGB', (LW + 1200 + 2 * (TW + 8), 30 + RH * max(1, len(tr))), '#111'); d = ImageDraw.Draw(img)
    X = lambda f: LW + 1200 * f / max(1, n - 1)
    for s in range(0, n, int(fps)): d.line([(X(s), 20), (X(s), img.height)], fill='#2a2a2a'); d.text((X(s) + 2, 4), f'{a.start + s / fps:.0f}s', fill='#777')
    for i, t in enumerate(tr):
        y = 26 + i * RH; s, e = t['obs'][0][0], t['obs'][-1][0]
        d.text((4, y + 20), f'A{i}', fill='#FF2E88')
        ys = [y + 50 - 40 * o[1]['cx'] for o in t['obs']]
        d.line([(X(o[0]), yy) for o, yy in zip(t['obs'], ys)], fill='#29E0FF', width=2)          # 横向位置
        d.line([(X(o[0]), y + 60 - 50 * min(1, o[1]['area'] * 4)) for o in t['obs']], fill='#F29A1F')  # 大小
        mo = motion(t['obs'], fps)
        for j in (mo.get('jumps', []) if mo else []): d.line([(X(j), y + 2), (X(j), y + 62)], fill='#ff4444', width=2)
        for k, fr in enumerate((s, e)):
            th = Image.fromarray(F[fr].astype(np.uint8)).resize((TW, TH)); x = LW + 1208 + k * (TW + 8)
            img.paste(th, (x, y)); bx = t['obs'][0 if k == 0 else -1][1]['box']
            d.rectangle([x + bx[0] * TW / W, y + bx[1] * TH / H, x + bx[2] * TW / W, y + bx[3] * TH / H], outline='#FF2E88')
    img.save(out + '_actors.jpg', quality=88)
