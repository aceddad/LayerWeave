// 音频波形：画每一小段的平均能量（RMS），按分贝对整首最响处归一，按文件缓存。
// 现在的流行曲响度大、峰值处处顶满，按峰值画会是一整条色块，看不出段落起伏。
// 先问服务端要算好的 800 段（/wave，几十 KB）；服务端算不了（没有 ffmpeg）才自己下载整个文件解码——分轨常是几十 MB 的 WAV
import {useEffect, useRef} from 'react';
import {paintQueue} from './mediaQueue';

const peaks = new Map<string, Promise<number[] | null>>();
let audio: AudioContext | null = null;

// 按分贝画：整首最响处为顶，往下 18 dB 铺满高度（流行曲段落之间常常只差几 dB）
export const waveformLevels = (rms: number[]) => {
  const top = Math.max(...rms) || 1;
  return rms.map((v) => Math.min(1, Math.max(0.04, (20 * Math.log10(Math.max(v, 1e-6) / top) + 18) / 18)));
};

function decodeHere(url: string) {
  return fetch(url).then((r) => r.arrayBuffer()).then((buf) => (audio ??= new AudioContext()).decodeAudioData(buf)).then((decoded) => {
    const data = decoded.getChannelData(0), n = 800, size = Math.floor(data.length / n) || 1, out: number[] = [];
    for (let i = 0; i < n; i++) {
      let sum = 0, count = 0;
      for (let j = i * size; j < (i + 1) * size && j < data.length; j++) { sum += data[j] * data[j]; count++; }
      out.push(Math.sqrt(sum / Math.max(1, count)));
    }
    return out;
  });
}

export function peaksFor(url: string) {
  if (!peaks.has(url)) {
    const server = url.startsWith('/media/') ? fetch(url.replace('/media/', '/wave/')).then((r) => (r.ok ? r.json() : null)) : Promise.resolve(null);
    peaks.set(url, server.catch(() => null).then((got) => (got?.rms?.length ? got.rms as number[] : decodeHere(url))).then(waveformLevels).catch(() => null));
  }
  return peaks.get(url)!;
}

// 与原逐格波形相同的采样尺寸：只用 CSS 尺寸和 DPR，不乘镜头缩放。
export function waveformSize(width: number, height: number, dpr: number) {
  return {width: Math.min(4096, Math.round(width * dpr)) || 160, height: Math.min(512, Math.round(height * dpr)) || 40};
}

// 原算法由画板共享表面和侧栏/一览的独立 canvas 复用；透明度仍由媒体外层控制。
export function drawWaveform(c: CanvasRenderingContext2D, values: number[] | null, w: number, h: number, dpr: number) {
  c.clearRect(0, 0, w, h);
  if (!values) { c.fillStyle = '#ffffff88'; c.font = `${10 * dpr}px sans-serif`; c.fillText('无法解码', 4, h / 2); return; }
  c.fillStyle = 'rgba(255,255,255,.75)';
  const bar = Math.max(1, Math.round(dpr));
  for (let x = 0; x < w; x += bar) { const p = values[Math.floor((x / w) * values.length)]; c.fillRect(x, h / 2 - (p * h) / 2, bar, Math.max(1, p * h)); }
}

// 尺寸由 ResizeObserver 告诉（排版完才回调）。原来每次画之前读 clientWidth，会逼浏览器当场把整页排一遍；
// 播放头的位置还画在波形里，点一下画板，此刻面板里每条音频都要这样重画一次（手书：一次 158 毫秒，2026-10-14 量的）。
// 现在波形只在文件或尺寸变了时画；播放头是盖在上面的一条线（WaveMark）
export function Waveform({url, className}: {url: string; className?: string}) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    let alive = true, values: number[] | null | undefined, w = 0, h = 0;
    const draw = () => {
      if (!alive || values === undefined || !w || !h) return;
      canvas.width = w;
      canvas.height = h;
      const c = canvas.getContext('2d')!;
      canvas.dataset.mediaState = values ? 'ready' : 'failed';
      drawWaveform(c, values, w, h, devicePixelRatio);
    };
    const observer = new ResizeObserver(([entry]) => {
      const box = entry.devicePixelContentBoxSize?.[0];
      const {width: nw, height: nh} = waveformSize(box ? box.inlineSize : entry.contentRect.width * devicePixelRatio,
        box ? box.blockSize : entry.contentRect.height * devicePixelRatio, 1);
      if (nw === w && nh === h) return;
      w = nw; h = nh;
      paintQueue.schedule(draw, draw);
    });
    try { observer.observe(canvas, {box: 'device-pixel-content-box'}); } catch { observer.observe(canvas); }
    paintQueue.track(peaksFor(url).then((got) => { if (alive) { values = got; paintQueue.schedule(draw, draw); } }), draw);
    return () => { alive = false; paintQueue.cancel(draw); observer.disconnect(); };
  }, [url]);
  return <canvas ref={ref} className={className ?? 'wave'} />;
}

// 波形上的播放头：一条盖在上面的竖线，按比例放（0–1），挪它不用重画波形
export function WaveMark({at}: {at: number | null}) {
  return at == null ? null : <i className="wave-mark" style={{left: `${Math.max(0, Math.min(1, at)) * 100}%`}} />;
}
