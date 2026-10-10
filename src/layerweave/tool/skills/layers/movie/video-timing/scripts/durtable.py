"""时长表：告诉看视频的 AI 每一段画面持续了多久、每次切换用了多久。
只在"干净渲染、只有主体在变"的画面上可信；画面别处同时有东西在动、有颗粒、或是 AI 生成视频时，会报成"全是变化"。

python durtable.py <视频> [--start 秒 --end 秒] [--json 输出.json] [--ffmpeg ffmpeg路径] [--tmp-dir 临时目录]
需要 ffmpeg：默认在 PATH 里找，也可用 --ffmpeg 或环境变量 FFMPEG 指定。
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile
import av, numpy as np

FF = os.environ.get('FFMPEG') or shutil.which('ffmpeg')
TMPDIR = tempfile.gettempdir()   # 只有截取片段时用；可用 --tmp-dir 指到空间充足的盘
SLOW_BLOCK = 1.0      # 细微变化：8×8 块平均差最大值 ≥ 1.0（mpdecimate lo 每像素 5 的 1/5）
MIN_HOLD = 3


def extract(path, start, end):
    """先把要看的一段无损截出来，保证 ffmpeg 与 PyAV 的帧号一致"""
    if start is None and end is None: return path, False
    tmp = os.path.join(TMPDIR, f'durtable_seg_{os.getpid()}.mp4')     # 临时目录可用 --tmp-dir 指到空间充足的盘
    args = [FF, '-hide_banner', '-loglevel', 'error', '-y']
    if start is not None: args += ['-ss', str(start)]
    if end is not None: args += ['-to', str(end)]
    subprocess.run(args + ['-i', path, '-an', '-c:v', 'libx264', '-qp', '0', '-pix_fmt', 'yuv420p', tmp], check=True)
    return tmp, True


def keepdrop(path):
    err = subprocess.run([FF, '-hide_banner', '-loglevel', 'debug', '-i', path, '-vf', 'mpdecimate', '-map', '0:v:0', '-f', 'null', '-'],
                         capture_output=True, text=True, encoding='utf8', errors='replace').stderr
    with av.open(path) as c0: fps = float(c0.streams.video[0].average_rate)
    ts = [(float(m.group(2)), m.group(1)) for m in re.finditer(r'\b(keep|drop|never_drop) pts:\S+ pts_time:([\d.]+)', err)]
    t0 = ts[0][0] if ts else 0
    out = {}
    for t, k in ts: out[int(round((t - t0) * fps))] = 'keep' if k != 'drop' else 'drop'
    n = max(out) + 1 if out else 0
    return [out.get(i, 'keep') for i in range(n)], fps


def subtle(path, n):
    """每帧和前一帧的 8×8 块平均差的最大值"""
    c = av.open(path); c.streams.video[0].thread_type = 'AUTO'
    prev = None; out = []
    for f in c.decode(video=0):  # noqa
        g = f.to_ndarray(format='gray').astype(np.float32)
        if prev is None: out.append(0.0)
        else:
            h, w = g.shape[0] // 8 * 8, g.shape[1] // 8 * 8
            d = np.abs(g[:h, :w] - prev[:h, :w]).reshape(h // 8, 8, w // 8, 8).mean((1, 3))
            out.append(float(d.max()))
        prev = g
        if len(out) >= n: break
    c.close()
    return out


def build(kd, sub):
    n = len(kd)
    keeps = [i for i in range(n) if kd[i] == 'keep'] or [0]
    draws = []
    for k, s in enumerate(keeps):
        e = (keeps[k + 1] - 1) if k + 1 < len(keeps) else n - 1
        drops = list(range(s + 1, e + 1))
        slow = len(drops) >= 2 and sum(sub[i] >= SLOW_BLOCK for i in drops) >= 0.5 * len(drops)
        draws.append(dict(start=s, end=e, frames=e - s + 1, slow=slow))
    segs = []
    for d in draws:
        kind = '缓慢变化' if d['slow'] else ('停留' if d['frames'] >= MIN_HOLD else '变化')
        if segs and segs[-1]['kind'] == kind and kind in ('缓慢变化', '变化'):
            segs[-1]['end'] = d['end']; segs[-1]['frames'] += d['frames']; segs[-1]['drawings'] += 1
        else:
            segs.append(dict(kind=kind, start=d['start'], end=d['end'], frames=d['frames'], drawings=1))
    return segs


def report(segs, fps, t0=0.0):
    L = []
    for k, s in enumerate(segs):
        extra = f"（{s['drawings']} 张画）" if s['kind'] != '停留' else ''
        L.append(f"{s['kind']:4} f{s['start']}–{s['end']}  {t0 + s['start'] / fps:.2f}–{t0 + (s['end'] + 1) / fps:.2f}s  {s['frames']} 帧 / {s['frames'] / fps:.2f}s{extra}")
        if s['kind'] == '停留' and k + 1 < len(segs) and segs[k + 1]['kind'] == '停留':
            L.append('     ↓ 硬切（0 帧过渡）')
    return '\n'.join(L)


def run(path, start=None, end=None):
    p, tmp = extract(path, start, end)
    kd, fps = keepdrop(p)
    sub = subtle(p, len(kd))
    segs = build(kd, sub)
    if tmp: os.remove(p)
    return segs, fps, kd, sub


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('video'); ap.add_argument('--start', type=float); ap.add_argument('--end', type=float); ap.add_argument('--json')
    ap.add_argument('--ffmpeg', help='ffmpeg 可执行文件；省略时用环境变量 FFMPEG 或 PATH 里的 ffmpeg')
    ap.add_argument('--tmp-dir', help='截取片段时的临时目录；省略时用系统临时目录')
    a = ap.parse_args()
    FF = a.ffmpeg or FF
    TMPDIR = a.tmp_dir or TMPDIR
    if not FF:
        sys.exit('找不到 ffmpeg：请安装并加入 PATH，或用 --ffmpeg / 环境变量 FFMPEG 指定')
    segs, fps, kd, sub = run(a.video, a.start, a.end)
    print(report(segs, fps, a.start or 0.0))
    if a.json: json.dump(dict(segments=segs, keepdrop=kd, subtle=sub), open(a.json, 'w', encoding='utf8'), ensure_ascii=False)
