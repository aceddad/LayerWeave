"""卡点表：把 Demucs 分轨后的每一轨变成"事件"，标上时间、帧号、小节:拍、强弱，供做动画时卡点 / 跟节奏。

python cues.py <分轨文件夹> [--fps 24] [--out 前缀]

每轨提取：
- drums  → kick（<150Hz）/ snare（150–2kHz 起音）/ hat（>6kHz）三条
- bass   → 音符起点（起音）+ 包络
- other  → 和声/旋律乐器起点（合成器、钢琴、弦乐都在这一轨）+ 包络
- vocals → 字/音节起点、乐句开头（前面空 > 0.4s）、长音（持续 > 0.5s 且中间没有新起音）
- 6 轨模型（htdemucs_6s）多出的 guitar / piano 也会按旋律乐器处理
拍网格：用底鼓真实起音拟合 BPM 与第 0 拍（比按混音估的准）
输出：<前缀>_cues.csv（time, frame, stem, kind, strength, bar, beat, sixteenth）、<前缀>_cues.json（含每轨逐帧包络，可用来"跟节奏"驱动动画）
"""
import argparse, csv, json, os
import numpy as np, librosa
from scipy.signal import butter, sosfiltfilt, hilbert

SR = 22050


def band(y, lo=None, hi=None):
    if lo and hi: sos = butter(4, [lo, hi], btype='bandpass', fs=SR, output='sos')
    elif hi: sos = butter(4, hi, btype='lowpass', fs=SR, output='sos')
    else: sos = butter(4, lo, btype='highpass', fs=SR, output='sos')
    return sosfiltfilt(sos, y)


def onsets(y, delta=0.07, hop=128):
    env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=hop)
    fr = librosa.onset.onset_detect(onset_envelope=env, sr=SR, hop_length=hop, delta=delta, units='frames')
    t = librosa.frames_to_time(fr, sr=SR, hop_length=hop)
    s = env[fr] / (np.percentile(env[fr], 95) + 1e-9) if len(fr) else np.array([])
    return t, np.clip(s, 0, 1)


def envelope(y, fps):
    hop = SR // fps
    r = librosa.feature.rms(y=y, frame_length=hop * 2, hop_length=hop)[0]
    return r / (np.percentile(r, 99) + 1e-9)


def attack_times(y, approx):
    """把检测到的起音峰值往前推到真实起音（包络升到 20%）"""
    env = np.abs(hilbert(y)); env = np.convolve(env, np.ones(22) / 22, mode='same')
    out = []
    for t in approx:
        a, b = int(max(0, t - 0.06) * SR), int((t + 0.03) * SR); seg = env[a:b]
        if len(seg) < 4: out.append(t); continue
        pk = int(np.argmax(seg)); lo = seg[:pk + 1].min(); thr = lo + (seg[pk] - lo) * 0.2
        st = np.nonzero(seg[:pk + 1] >= thr)[0]
        out.append((a + st[0]) / SR if len(st) else t)
    return np.array(out)


def fit_grid(kick_t):
    """用底鼓起音拟合十六分音符网格 → BPM、第 0 拍。先由间隔估一个大概的 BPM，再在 ±2% 范围里细搜 BPM 和相位，取平均误差最小的"""
    ioi = np.diff(np.sort(kick_t)); ioi = ioi[(ioi > 0.2) & (ioi < 1.2)]
    beat = float(np.median(ioi)) if len(ioi) else 0.5
    for k in (1, 2):
        if 0.35 < beat / k < 0.75: beat = beat / k; break
    def err(bpm):
        six = 60 / bpm / 4
        ph = np.angle(np.exp(2j * np.pi * kick_t / six).mean())             # 圆形平均求最佳相位
        b0 = (ph / (2 * np.pi)) * six % six
        d = (kick_t - b0 + six / 2) % six - six / 2
        return float(np.abs(d).mean()), b0
    bpms = np.arange(60 / beat * 0.98, 60 / beat * 1.02, 0.002)
    best = min((err(b)[0], b) for b in bpms)[1]
    _, b0 = err(best)
    beat = 60 / best; six = beat / 4
    near = lambda grid_t0, period: np.abs((kick_t - grid_t0 + period / 2) % period - period / 2) < 0.03
    # 拍头：4 个十六分相位里，底鼓落在"拍"上最多的那个
    b0 = max((near(b0 + k * six, beat).sum(), b0 + k * six) for k in range(4))[1] % beat
    # 小节头：4 拍里，底鼓落在"小节第一拍"上最多的那个
    bar = beat * 4
    b0 = max((near(b0 + k * beat, bar).sum(), b0 + k * beat) for k in range(4))[1] % bar
    return float(best), float(b0)


def grid_pos(t, bpm, b0):
    six = 60 / bpm / 4
    n = int(np.round((t - b0) / six))
    return n // 16 + 1, (n % 16) // 4 + 1, n % 4 + 1                         # 小节、拍、十六分（从 1 起）


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('stems'); ap.add_argument('--fps', type=int, default=24); ap.add_argument('--out')
    a = ap.parse_args(); out = a.out or os.path.join(a.stems, 'song')
    names = [n[:-4] for n in sorted(os.listdir(a.stems)) if n.endswith('.wav')]
    Y = {n: librosa.load(os.path.join(a.stems, n + '.wav'), sr=SR, mono=True)[0] for n in names}
    ev, envs = [], {}
    # 鼓
    if 'drums' in Y:
        d = Y['drums']
        for kind, sig, dl in (('kick', band(d, hi=150), 0.12), ('snare', band(d, 150, 2000), 0.1), ('hat', band(d, lo=6000), 0.08)):
            t, s = onsets(sig, dl); t = attack_times(sig, t)
            keep = s > 0.15
            ev += [('drums', kind, ti, si) for ti, si in zip(t[keep], s[keep])]
            envs['drums_' + kind] = envelope(sig, a.fps)
    kick = np.array(sorted(t for st, k, t, s in ev if k == 'kick' and s > 0.4))
    bpm, b0 = fit_grid(kick) if len(kick) > 8 else (120.0, 0.0)
    # 旋律 / 和声 / 贝斯
    for n in names:
        if n in ('drums', 'vocals'): continue
        t, s = onsets(Y[n], 0.1); keep = s > 0.2
        ev += [(n, 'note', ti, si) for ti, si in zip(t[keep], s[keep])]
        envs[n] = envelope(Y[n], a.fps)
    # 人声
    if 'vocals' in Y:
        v = Y['vocals']; t, s = onsets(v, 0.08); env = envelope(v, a.fps); envs['vocals'] = env
        alive = lambda x: env[min(len(env) - 1, int(x * a.fps))] > 0.12
        t = np.array([x for x in t if alive(x + 0.05)]); s = s[:len(t)] if len(t) else s
        ev += [('vocals', 'syllable', ti, 1.0) for ti in t]
        if len(t):
            starts = t[np.r_[True, np.diff(t) > 0.4]]
            ev += [('vocals', 'phrase', ti, 1.0) for ti in starts]
            for i in range(len(t)):                                         # 长音：下一个字隔得久，且这段时间声音一直在
                nxt = t[i + 1] if i + 1 < len(t) else t[i] + 3
                fa, fb = int(t[i] * a.fps), int(min(nxt, t[i] + 4) * a.fps)
                held = np.nonzero(env[fa:fb] < 0.12)[0]
                L = (held[0] if len(held) else fb - fa) / a.fps
                if L > 0.5: ev.append(('vocals', f'hold {L:.2f}s', t[i], 1.0))
    ev.sort(key=lambda e: e[2])
    with open(out + '_cues.csv', 'w', newline='', encoding='utf8') as f:
        w = csv.writer(f); w.writerow(['time', 'frame', 'stem', 'kind', 'strength', 'bar', 'beat', 'sixteenth'])
        for st, k, t, s in ev:
            bar, bt, sx = grid_pos(t, bpm, b0)
            w.writerow([f'{t:.3f}', int(round(t * a.fps)), st, k, f'{s:.2f}', bar, bt, sx])
    json.dump(dict(bpm=bpm, beat0=b0, fps=a.fps, events=[dict(stem=st, kind=k, t=round(float(t), 3), s=round(float(s), 2)) for st, k, t, s in ev],
                   envelopes={k: [round(float(x), 3) for x in v] for k, v in envs.items()}),
              open(out + '_cues.json', 'w', encoding='utf8'))
    cnt = {}
    for st, k, *_ in ev: key = st + '/' + (k if not k.startswith('hold') else 'hold'); cnt[key] = cnt.get(key, 0) + 1
    print(f'BPM {bpm:.3f}  beat0 {b0:.3f}s'); print(cnt)
