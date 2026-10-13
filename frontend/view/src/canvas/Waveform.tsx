// 音频波形：画每一小段的平均能量（RMS），按分贝对整首最响处归一，按文件缓存。
// 现在的流行曲响度大、峰值处处顶满，按峰值画会是一整条色块，看不出段落起伏。
// 先问服务端要算好的 800 段（/wave，几十 KB）；服务端算不了（没有 ffmpeg）才自己下载整个文件解码——分轨常是几十 MB 的 WAV
import {useEffect, useRef} from 'react';

const peaks = new Map<string, Promise<number[] | null>>();
let audio: AudioContext | null = null;

export const pendingWaves = () => [...peaks.values()];

// 按分贝画：整首最响处为顶，往下 18 dB 铺满高度（流行曲段落之间常常只差几 dB）
const toDb = (rms: number[]) => {
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

function peaksFor(url: string) {
  if (!peaks.has(url)) {
    const server = url.startsWith('/media/') ? fetch(url.replace('/media/', '/wave/')).then((r) => (r.ok ? r.json() : null)) : Promise.resolve(null);
    peaks.set(url, server.catch(() => null).then((got) => (got?.rms?.length ? got.rms as number[] : decodeHere(url))).then(toDb).catch(() => null));
  }
  return peaks.get(url)!;
}

export function Waveform({url, mark, className}: {url: string; mark?: number | null; className?: string}) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    let alive = true;
    peaksFor(url).then((values) => {
      const canvas = ref.current;
      if (!alive || !canvas) return;
      const w = (canvas.width = canvas.clientWidth || 160), h = (canvas.height = canvas.clientHeight || 40);
      const c = canvas.getContext('2d')!;
      c.clearRect(0, 0, w, h);
      if (!values) { c.fillStyle = '#ffffff88'; c.fillText('无法解码', 4, h / 2); return; }
      c.fillStyle = 'rgba(255,255,255,.75)';
      for (let x = 0; x < w; x++) { const p = values[Math.floor((x / w) * values.length)]; c.fillRect(x, h / 2 - (p * h) / 2, 1, Math.max(1, p * h)); }
      if (mark != null) { c.fillStyle = '#ff4f7a'; c.fillRect(mark * w, 0, 2, h); }
    });
    return () => { alive = false; };
  }, [url, mark]);
  return <canvas ref={ref} className={className ?? 'wave'} />;
}
