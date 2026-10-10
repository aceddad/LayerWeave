"""给 Claude 看视频用的"带范围的关键帧拼图"。
固定间隔抽帧时，每张图只是一个瞬间：不知道它持续多久、前后怎么接，两张抽帧之间的突兀切换会被漏掉。
这里按内容抽：把视频切成"状态"（画面不变或缓慢变化的一段）和"过渡"（状态之间），
每个状态一张关键帧，标出它管辖的帧范围；每个过渡标出帧数、类型（硬切 / 快切 / 淡化 / 运动），并附过渡中间的小图。

python review.py <视频> [--start 秒] [--end 秒] [--out 前缀] [--sens 1.0]
输出：前缀_review_N.jpg（每页 12 个状态）、前缀_review.md
"""
import argparse
import av, numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FW, FH = 96, 54           # 特征分辨率
TW, TH = 240, 135         # 关键帧缩略图
SW, SH = 80, 45           # 过渡小图


def load(path, t0, t1):
    c = av.open(path); c.streams.video[0].thread_type = 'AUTO'; fps = float(c.streams.video[0].average_rate)
    feats, thumbs = [], []
    for i, f in enumerate(c.decode(video=0)):
        t = i / fps
        if t < t0: continue
        if t1 and t >= t1: break
        im = f.to_image()
        th = im.resize((TW, TH), Image.BILINEAR); thumbs.append(th)
        g = th.convert('L').resize((FW, FH), Image.BILINEAR)
        L = np.asarray(g, np.float32) / 255
        E = np.asarray(g.filter(ImageFilter.FIND_EDGES), np.float32) / 255
        feats.append(np.concatenate([E.ravel(), L.ravel() * 0.5]))
    return np.stack(feats), thumbs, fps


def segment(F, sens):
    n = len(F)
    step = np.array([0.0] + [np.abs(F[i] - F[i - 1]).mean() * 100 for i in range(1, n)])
    lum = np.array([0.0] + [np.abs(F[i, FW * FH:] - F[i - 1, FW * FH:]).mean() * 200 for i in range(1, n)])
    move = max(0.25, np.percentile(step, 40) * 2.0) / sens       # 一帧内变化超过它 = 在"过渡"
    drift = 1.6 / sens                                           # 状态内累计漂移超过它 = 换一个状态
    states, i = [], 0
    while i < n:
        if step[i] > move and i > 0: i += 1; continue
        a = i; anchor = F[i]
        while i + 1 < n and step[i + 1] <= move and np.abs(F[i + 1] - anchor).mean() * 100 < drift: i += 1
        if i - a + 1 >= 3 or a == 0 or i == n - 1: states.append([a, i])
        i += 1
    # 合并：中间没有过渡帧、而且几乎一样的相邻状态
    trans = []
    for (a0, b0), (a1, b1) in zip(states, states[1:]):
        k = a1 - b0 - 1                                          # 过渡帧数
        jump = np.abs(F[a1] - F[b0]).mean() * 100
        seg = step[b0 + 1:a1 + 1]; lseg = lum[b0 + 1:a1 + 1]
        if k <= 0: kind = '硬切' if jump > move * 3 else '缓变（无明显过渡）'
        elif k <= 3: kind = '快切'
        elif lseg.mean() > 0.8 * seg.mean() * 2: kind = '淡化 / 闪光（亮度主导）'
        else: kind = '运动过渡（结构主导）'
        pk = int(np.argmax(seg)) if len(seg) else 0
        shape = ''
        if k >= 5:
            pos = pk / max(1, len(seg) - 1)
            shape = '，先快后慢' if pos < 0.3 else ('，先慢后快' if pos > 0.7 else '，中间最快')
            if seg.max() > 3 * max(seg.mean(), 1e-3): shape += '，中途有一下突跳'
        trans.append(dict(frm=b0 + 1, to=a1 - 1, frames=max(0, k), kind=kind + shape, jump=round(float(jump), 2)))
    return states, trans, move


def onion(frames):
    """洋葱皮：过渡里的各帧叠在一起，只画"和第一帧不同"的地方，早 = 青、晚 = 品红；底图是第一帧（压暗）"""
    A = [np.asarray(f, np.float32) for f in frames]
    base = A[0] * 0.35
    out = base.copy()
    n = len(A)
    for i, a in enumerate(A[1:], 1):
        u = i / max(1, n - 1)
        col = np.array([41, 224, 255]) * (1 - u) + np.array([255, 46, 136]) * u
        diff = np.abs(a - A[0]).sum(-1, keepdims=True) / 255
        m = np.clip((diff - 0.12) * 3, 0, 1) * 0.75
        lum = a.mean(-1, keepdims=True) / 255
        out = out * (1 - m) + (col * (0.4 + 0.6 * lum)) * m
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def heat(frames):
    """变化热力图：逐帧差累加，哪里变得多哪里亮（黑→紫→橙→白）"""
    A = [np.asarray(f.convert('L'), np.float32) for f in frames]
    acc = sum(np.abs(A[i] - A[i - 1]) for i in range(1, len(A))) if len(A) > 1 else A[0] * 0
    acc = acc / (np.percentile(acc, 99.5) + 1e-6)
    x = np.clip(acc, 0, 1)[..., None]
    rgb = np.concatenate([np.clip(x * 2, 0, 1) * 255, np.clip(x * 2 - 0.6, 0, 1) * 255, (np.clip(x * 3, 0, 1) - np.clip(x * 3 - 1, 0, 1) * 0.6) * 200 + x * 55], -1)
    return Image.fromarray(rgb.clip(0, 255).astype(np.uint8))


FONT_PATH = None          # --font 指定；否则按常见中文字体依次尝试
FONT_CANDIDATES = [
    r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf',                       # Windows
    '/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/Hiragino Sans GB.ttc',   # macOS
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',                            # Linux
    '/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc',
]


def load_font(size):
    for path in ([FONT_PATH] if FONT_PATH else []) + FONT_CANDIDATES:
        try: return ImageFont.truetype(path, size)
        except Exception: continue
    return ImageFont.load_default()   # 找不到中文字体时，图里的中文标注会显示成方块；文字报告不受影响


def render(states, trans, thumbs, fps, t0, out, per_page=12):
    font = load_font(13)
    pages = []
    for p in range(0, len(states), per_page):
        S = states[p:p + per_page]; cols = 3
        cellW = TW + 4 * (SW + 2) + 30; cellH = TH + 110
        img = Image.new('RGB', (cols * cellW + 10, ((len(S) + cols - 1) // cols) * cellH + 10), '#101114'); d = ImageDraw.Draw(img)
        for j, (a, b) in enumerate(S):
            k = p + j; x, y = 6 + (j % cols) * cellW, 6 + (j // cols) * cellH
            img.paste(thumbs[(a + b) // 2], (x, y))
            dur = (b - a + 1) / fps
            d.text((x, y + TH + 2), f'S{k}  f{a}–{b}  {t0 + a / fps:.2f}–{t0 + (b + 1) / fps:.2f}s', fill='#FF2E88', font=font)
            d.text((x, y + TH + 18), f'持续 {b - a + 1} 帧 / {dur:.2f}s', fill='#ddd', font=font)
            if k < len(trans):
                tr = trans[k]; tx = x + TW + 8
                if tr['frames'] > 0:
                    idx = np.linspace(tr['frm'], tr['to'], min(4, tr['frames'])).round().astype(int)
                    for m, fi in enumerate(idx): img.paste(thumbs[fi].resize((SW, SH)), (tx + m * (SW + 2), y + 20))
                # 变换本身：洋葱皮（从前一状态最后一帧到后一状态第一帧）+ 变化热力图
                seq = thumbs[max(0, tr['frm'] - 1):tr['to'] + 2]
                if len(seq) >= 2:
                    ow = (4 * (SW + 2) - 4) // 2
                    img.paste(onion(seq).resize((ow, ow * 9 // 16)), (tx, y + 20 + SH + 22))
                    img.paste(heat(seq).resize((ow, ow * 9 // 16)), (tx + ow + 4, y + 20 + SH + 22))
                col = '#ff5a5a' if tr['kind'].startswith('硬切') or '突跳' in tr['kind'] else '#29E0FF'
                d.text((tx, y + 2), f"→ {tr['frames']} 帧过渡", fill=col, font=font)
                d.text((tx, y + 20 + SH + 4), tr['kind'], fill=col, font=font)
                d.text((tx, y + TH + 90), '洋葱皮(青→品红=早→晚)  |  变化热力图', fill='#888', font=font)
        name = f'{out}_review_{p // per_page + 1}.jpg'; img.save(name, quality=86); pages.append(name)
    return pages


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('video'); ap.add_argument('--start', type=float, default=0); ap.add_argument('--end', type=float)
    ap.add_argument('--out'); ap.add_argument('--sens', type=float, default=1.0)
    ap.add_argument('--font', help='图上中文标注用的字体文件；省略时自动尝试常见中文字体')
    a = ap.parse_args(); out = a.out or a.video.rsplit('.', 1)[0]
    FONT_PATH = a.font
    F, thumbs, fps = load(a.video, a.start, a.end)
    states, trans, thr = segment(F, a.sens)
    L = [f'{a.start:.2f}–{a.start + len(F) / fps:.2f}s，{len(F)} 帧 → {len(states)} 个状态（变化阈值 {thr:.2f}）', '']
    for k, (s0, s1) in enumerate(states):
        L.append(f'S{k}  f{s0}–{s1}（{a.start + s0 / fps:.2f}–{a.start + (s1 + 1) / fps:.2f}s，{s1 - s0 + 1} 帧）')
        if k < len(trans):
            t = trans[k]; L.append(f"   → {t['frames']} 帧过渡：{t['kind']}（前后差 {t['jump']}）")
    open(out + '_review.md', 'w', encoding='utf8').write('\n'.join(L) + '\n')
    pages = render(states, trans, thumbs, fps, a.start, out)
    print('\n'.join(L)); print(pages)
