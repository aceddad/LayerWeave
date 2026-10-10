// 音频波形：浏览器自己解码，峰值按文件缓存
import {useEffect, useRef} from 'react';

const peaks = new Map<string, Promise<number[] | null>>();
let audio: AudioContext | null = null;

export const pendingWaves = () => [...peaks.values()];

function peaksFor(url: string) {
  if (!peaks.has(url)) {
    peaks.set(url, fetch(url).then((r) => r.arrayBuffer()).then((buf) => (audio ??= new AudioContext()).decodeAudioData(buf)).then((decoded) => {
      const data = decoded.getChannelData(0), n = 400, size = Math.floor(data.length / n) || 1, out: number[] = [];
      for (let i = 0; i < n; i++) {
        let m = 0;
        for (let j = i * size; j < (i + 1) * size && j < data.length; j++) m = Math.max(m, Math.abs(data[j]));
        out.push(m);
      }
      return out;
    }).catch(() => null));
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
