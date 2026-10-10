"""读懂一段视频的时间结构：关键帧（原画）在哪、停多久、之间怎么过渡（中割有几帧、缓入缓出还是猛切）。
给 Claude 用：Claude 只能看抽帧，看不到两张抽帧之间发生了什么；这张"时间图"把它补上。

定义（借动画的概念）：
- 停住 hold：连续几帧结构几乎不变
- 关键帧 key：停住的段；或者速度降到局部低点（动作到位）；或者动作方向转折（特征空间里位移方向夹角大）
- 过渡 transition：两个关键帧之间。记录帧数、速度峰值位置 → 缓出（离开时慢）/ 缓入（到位时慢）/ 两头慢 / 匀速 / 猛切

结构特征用 xsheet.py 的 features（边缘 + 剪影），光影和调色不算动作。

用法：python keys.py <视频.mp4> [--out 前缀]
输出：<前缀>_keys.jpg（速度曲线 + 关键帧缩略图），<前缀>_keys.md（文字版时间结构），终端打印文字版
"""
import argparse, os, sys
import av, numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xsheet import features

FPS = 24


def analyze(frames, hold_thr=None, turn_cos=0.3, merge=4):
    F = features(frames)
    n = len(F)
    v = np.array([0.0] + [np.abs(F[i] - F[i - 1]).mean() * 100 for i in range(1, n)])     # 速度：相邻帧结构差
    vs = np.convolve(v, np.ones(3) / 3, mode='same')                                       # 轻微平滑，去掉编码抖动
    if hold_thr is None:
        hold_thr = max(0.12, float(np.percentile(vs, 15)) * 1.5, float(vs.max()) * 0.06)
    # 1) 停住的段
    holds, i = [], 0
    while i < n:
        if vs[i] < hold_thr:
            j = i
            while j + 1 < n and vs[j + 1] < hold_thr: j += 1
            if j - i + 1 >= 3: holds.append((i, j))
            i = j + 1
        else: i += 1
    cand = {}
    for a, b in holds: cand[(a + b) // 2] = ('hold', a, b)
    # 2) 速度局部低点（明显低于两侧的峰）
    for t in range(2, n - 2):
        if vs[t] <= vs[t - 1] and vs[t] <= vs[t + 1]:
            left, right = vs[max(0, t - 12):t].max(), vs[t + 1:t + 13].max()
            if vs[t] < 0.6 * min(left, right) and min(left, right) > hold_thr * 2:
                cand.setdefault(t, ('slow', t, t))
    # 3) 方向转折：先用 PCA 把结构特征压到最主要的几个变化方向（如"身体高度""重心前后"），
    #    高维里任意两次位移几乎都"垂直"，直接算夹角会处处是转折
    Fc = F - F.mean(0)
    U, S, _ = np.linalg.svd(Fc, full_matrices=False)
    m = int(np.searchsorted(np.cumsum(S ** 2) / (S ** 2).sum(), 0.9)) + 1         # 覆盖 90% 变化的维数
    P = U[:, :max(2, min(m, 6))] * S[:max(2, min(m, 6))]
    k = 4
    step = np.linalg.norm(np.diff(P, axis=0), axis=1)
    tiny = np.percentile(step, 50) * k * 0.5
    for t in range(k, n - k):
        d1, d2 = P[t] - P[t - k], P[t + k] - P[t]
        n1, n2 = np.linalg.norm(d1), np.linalg.norm(d2)
        if n1 < tiny or n2 < tiny: continue
        with np.errstate(invalid='ignore', divide='ignore', over='ignore'):
            c = float(d1 @ d2 / (n1 * n2))
        if c != c: continue   # 数值溢出得到 NaN 时跳过（与原行为一致，只是不再打印警告）
        if c < turn_cos and vs[t] > hold_thr:
            # 只取转折最急的那一帧（局部最小的 cos）
            cs = []
            for u in range(max(k, t - 2), min(n - k, t + 3)):
                e1, e2 = P[u] - P[u - k], P[u + k] - P[u]
                cs.append((float(e1 @ e2 / (np.linalg.norm(e1) * np.linalg.norm(e2) + 1e-9)), u))
            cand.setdefault(min(cs)[1], ('turn', min(cs)[1], min(cs)[1]))
    # 首尾总是关键帧
    cand.setdefault(0, ('start', 0, 0)); cand.setdefault(n - 1, ('end', n - 1, n - 1))
    # 合并太近的候选（保留 hold 优先）
    keys = []
    for t in sorted(cand):
        kind, a, b = cand[t]
        if keys and a - keys[-1]['b'] <= merge:
            prev = keys[-1]
            if kind == 'hold' and prev['kind'] != 'hold': keys[-1] = dict(t=t, kind=kind, a=a, b=b)
            elif prev['kind'] == 'hold' and kind == 'hold': prev['b'] = b; prev['t'] = (prev['a'] + b) // 2
            continue
        keys.append(dict(t=t, kind=kind, a=a, b=b))
    # 过渡
    trans = []
    for k0, k1 in zip(keys, keys[1:]):
        s, e = k0['b'] + 1, k1['a']
        if e <= s: continue
        seg = vs[s:e]
        pk = int(np.argmax(seg)); pos = pk / max(1, len(seg) - 1)
        mean, peak = float(seg.mean()), float(seg.max())
        if peak > 2.6 * max(mean, 1e-3) and len(seg) > 4: shape = '猛切（中间有一下特别快）'
        elif pos < 0.3: shape = '快出缓入（一离开就快，慢慢到位）'
        elif pos > 0.7: shape = '缓出快入（慢慢起步，冲到位）'
        elif seg[0] < 0.6 * peak and seg[-1] < 0.6 * peak: shape = '两头慢（缓出缓入）'
        else: shape = '匀速'
        trans.append(dict(frm=s, to=e - 1, frames=e - s, peak_at=s + pk, peak=round(peak, 2), mean=round(mean, 2), shape=shape))
    return dict(n=n, v=vs, hold_thr=hold_thr, keys=keys, trans=trans)


def report(r):
    L = [f"共 {r['n']} 帧（{r['n']/FPS:.2f} 秒），关键帧 {len(r['keys'])} 个；速度阈值 {r['hold_thr']:.2f}（低于它算停住）", '']
    kind_cn = dict(hold='停住', slow='到位（减速低点）', turn='方向转折', start='开头', end='结尾')
    ti = 0
    for k in r['keys']:
        dur = k['b'] - k['a'] + 1
        L.append(f"■ 关键帧 f{k['t']}（{k['t']/FPS:.2f}s）{kind_cn[k['kind']]}" + (f"，停 f{k['a']}–f{k['b']} 共 {dur} 帧 / {dur/FPS:.2f}s" if dur > 1 else ''))
        if ti < len(r['trans']) and r['trans'][ti]['frm'] == k['b'] + 1:
            t = r['trans'][ti]; ti += 1
            L.append(f"   ↓ 过渡 f{t['frm']}–f{t['to']}：{t['frames']} 帧 / {t['frames']/FPS:.2f}s，{t['shape']}，最快在 f{t['peak_at']}（{t['peak']}，平均 {t['mean']}）")
    return '\n'.join(L)


def chart(frames, r, out):
    n = r['n']; W = 1800; GH = 260; TW = 170
    keys = r['keys']; TH = int(TW * frames[0].shape[0] / frames[0].shape[1])
    rows = (len(keys) + 9) // 10
    img = Image.new('RGB', (W, GH + 40 + rows * (TH + 34)), '#15161a'); d = ImageDraw.Draw(img)
    v = r['v']; vm = max(1e-3, float(v.max()))
    X = lambda t: 40 + (W - 80) * t / max(1, n - 1)
    Y = lambda val: 20 + (GH - 40) * (1 - val / vm)
    for s in range(0, n, FPS):                                                        # 每秒竖线
        d.line([(X(s), 20), (X(s), GH - 20)], fill='#2a2c33'); d.text((X(s) + 3, GH - 18), f'{s // FPS}s', fill='#777')
    for t in r['trans']:                                                              # 过渡底色
        d.rectangle([X(t['frm']), 20, X(t['to']), GH - 20], fill='#1f2530')
    for k in keys:
        if k['b'] > k['a']: d.rectangle([X(k['a']), 20, X(k['b']), GH - 20], fill='#2d2433')
    d.line([(X(0), Y(r['hold_thr'])), (X(n - 1), Y(r['hold_thr']))], fill='#555')
    d.line([(X(t), Y(v[t])) for t in range(n)], fill='#29E0FF', width=2)
    for i, k in enumerate(keys):
        d.line([(X(k['t']), 20), (X(k['t']), GH - 20)], fill='#FF2E88', width=2); d.text((X(k['t']) + 3, 22), f'K{i}', fill='#FF2E88')
    for i, k in enumerate(keys):
        x, y = 40 + (i % 10) * (TW + 6), GH + 30 + (i // 10) * (TH + 34)
        img.paste(Image.fromarray(frames[k['t']]).resize((TW, TH)), (x, y))
        dur = k['b'] - k['a'] + 1
        d.text((x + 2, y + TH + 2), f"K{i} f{k['t']} {k['t']/FPS:.2f}s", fill='#FF2E88')
        d.text((x + 2, y + TH + 16), f"{k['kind']}" + (f" x{dur}" if dur > 1 else ''), fill='#bbb')
    img.save(out, quality=88)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('video'); ap.add_argument('--out'); ap.add_argument('--hold', type=float)
    a = ap.parse_args()
    out = a.out or a.video.rsplit('.', 1)[0]
    frames = [f.to_ndarray(format='rgb24') for f in av.open(a.video).decode(video=0)]
    r = analyze(frames, a.hold)
    txt = report(r)
    open(out + '_keys.md', 'w', encoding='utf8').write(txt + '\n')
    chart(frames, r, out + '_keys.jpg')
    print(txt)
