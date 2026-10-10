"""自动摄影表：把一段视频的帧按"是不是同一张画 / 同一个姿势"分成连续的簇。

思路（2026-10-03 调查）：
- 动漫去重/补帧工具的做法：逐帧比较，差异低于阈值的连续帧算同一张画，簇长 = 停几拍（mpdecimate、MultiPassDedup）
- 视频摘要的 KTS（Kernel Temporal Segmentation）：用帧与帧两两之间的距离，动态规划求最优分段（段内尽量一致，每多一段罚 λ），
  比只看相邻帧稳，不会被缓慢漂移骗过
- 这里比较的是"线条结构"（边缘图 + 轮廓），不是颜色：光影、发光变化不算动作，姿势变了才算新的一张

用法：
  python xsheet.py <视频.mp4> [--penalty 1.0] [--out 前缀]
输出：<前缀>_xsheet.jpg（每簇代表帧 + 停几拍），<前缀>_xsheet.json（簇表），终端打印摘要
"""
import argparse, json
import av, numpy as np
from PIL import Image, ImageDraw, ImageFilter


def features(frames, w=160):
    """每帧 → 结构特征：缩小的边缘图 + 剪影（亮于背景的区域），各自归一化后拼起来"""
    out = []
    for a in frames:
        im = Image.fromarray(a).convert('L')
        h = int(w * im.height / im.width)
        small = im.resize((w, h), Image.BILINEAR)
        edge = np.asarray(small.filter(ImageFilter.FIND_EDGES), np.float32) / 255
        sil = (np.asarray(small, np.float32) > 40).astype(np.float32)          # 人物剪影
        sil = np.asarray(Image.fromarray((sil * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5)), np.float32) / 255
        out.append(np.concatenate([edge.ravel(), sil.ravel() * 0.5]))
    return np.stack(out)


def dist_matrix(F):
    """帧 i 与帧 j 的距离（平均绝对差，乘 100 方便读）"""
    n = len(F)
    D = np.zeros((n, n), np.float32)
    for i in range(n):
        D[i] = np.abs(F - F[i]).mean(1) * 100
    return D


def kts(D, penalty):
    """KTS 风格的动态规划：段代价 = 段内两两距离的平均 × 段长；总代价 = Σ段代价 + penalty × 段数"""
    n = len(D)
    S = np.zeros((n + 1, n + 1), np.float64)                                    # 二维前缀和，O(1) 取任意方块之和
    S[1:, 1:] = np.cumsum(np.cumsum(D, 0), 1)
    def cost(i, j):                                                             # 段 [i, j)
        L = j - i
        if L <= 1: return 0.0
        blk = S[j, j] - S[i, j] - S[j, i] + S[i, i]
        return blk / L                                                         # = 段长 × 段内平均两两距离 / 2 的量级
    best = np.full(n + 1, np.inf); best[0] = 0; prev = np.zeros(n + 1, int)
    for j in range(1, n + 1):
        for i in range(max(0, j - 48), j):                                     # 一张画最多停 2 秒
            c = best[i] + cost(i, j) + penalty
            if c < best[j]: best[j], prev[j] = c, i
    cuts, j = [], n
    while j > 0: cuts.append((prev[j], j)); j = prev[j]
    return cuts[::-1]


def analyze(path, penalty=1.0):
    frames = [f.to_ndarray(format='rgb24') for f in av.open(path).decode(video=0)]
    F = features(frames)
    D = dist_matrix(F)
    segs = kts(D, penalty)
    rows = []
    for k, (a, b) in enumerate(segs):
        inner = float(D[a:b, a:b].mean()) if b - a > 1 else 0.0               # 段内还在动多少（"抖"）
        jump = float(D[b - 1, b]) if b < len(frames) else 0.0                   # 到下一张的跳变
        rows.append(dict(id=k, start=int(a), end=int(b - 1), hold=int(b - a), rep=int((a + b - 1) // 2), inner=round(inner, 2), jump=round(jump, 2)))
    return frames, D, rows


def summary(rows, n):
    holds = [r['hold'] for r in rows]
    hist = {h: holds.count(h) for h in sorted(set(holds))}
    # 衔接诊断：某两张画之间的跳变，明显大于前后几次跳变 → 这里缺中间帧
    jumps = [r['jump'] for r in rows[:-1]]
    bad = []
    for k, j in enumerate(jumps):
        around = [x for x in jumps[max(0, k - 3):k] + jumps[k + 1:k + 4]]
        ref = float(np.median(around)) if around else 0
        if j > 1.0 and j > 2.0 * max(ref, 0.3): bad.append(dict(after=rows[k]['end'], jump=j, typical=round(ref, 2)))
    return dict(frames=n, drawings=len(rows), avg_hold=round(n / len(rows), 2), hold_histogram={str(k): v for k, v in hist.items()},
                still_but_moving=sum(1 for r in rows if r['hold'] >= 3 and r['inner'] > 0.8), rough_joins=bad)


def sheet(frames, rows, out, W=200):
    cols = 10; H = int(W * frames[0].shape[0] / frames[0].shape[1])
    s = Image.new('RGB', (W * cols, (H + 14) * ((len(rows) + cols - 1) // cols)), '#222'); d = ImageDraw.Draw(s)
    for k, r in enumerate(rows):
        x, y = (k % cols) * W, (k // cols) * (H + 14)
        s.paste(Image.fromarray(frames[r['rep']]).resize((W, H)), (x, y))
        d.text((x + 3, y + H), f"#{k} f{r['start']}-{r['end']} x{r['hold']}", fill='yellow' if r['hold'] > 1 else '#aaa')
    s.save(out, quality=88)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('video'); ap.add_argument('--penalty', type=float, default=1.0); ap.add_argument('--out')
    a = ap.parse_args()
    out = a.out or a.video.rsplit('.', 1)[0]
    frames, D, rows = analyze(a.video, a.penalty)
    sm = summary(rows, len(frames))
    sheet(frames, rows, out + '_xsheet.jpg')
    json.dump(dict(summary=sm, clusters=rows), open(out + '_xsheet.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    print(json.dumps(sm, ensure_ascii=False))
    print('consecutive structure diff:', ' '.join(f'{D[i-1, i]:.1f}' for i in range(1, len(frames))))
