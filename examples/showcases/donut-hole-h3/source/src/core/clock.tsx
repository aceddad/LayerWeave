// 时钟：开发时跟着音频走（可暂停、拖动）；截帧时由脚本调用 seek。组件只用 useT() 拿时刻，不自己计时。
// 音频读不到（没放歌曲文件）或浏览器拒绝播放时，error 给出原因，外壳负责显示。
import React, {createContext, useContext, useEffect, useRef, useState} from 'react';
import {DUR} from './time';

export const TimeContext = createContext(0);
export const useT = () => useContext(TimeContext);

export type Clock = {t: number; playing: boolean; toggle: () => void; seek: (t: number) => void; error: string};

export function useAudioClock(src: string, start = 0): Clock {
  const audio = useRef<HTMLAudioElement | null>(null);
  const [t, setT] = useState(start);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState('');
  const manual = useRef(start);
  useEffect(() => {
    const a = new Audio(src);
    a.preload = 'auto';
    audio.current = a;
    a.addEventListener('loadedmetadata', () => { a.currentTime = manual.current; setError(''); });
    a.addEventListener('error', () => { setError(`读不到音频 ${decodeURI(src)}：请把歌曲放到 assets/public${decodeURI(src)}（见 README）`); setPlaying(false); });
    a.addEventListener('ended', () => setPlaying(false));
    let raf = 0;
    const loop = () => { if (!a.paused) setT(a.currentTime); raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop);
    return () => { cancelAnimationFrame(raf); a.pause(); };
  }, [src]);
  const seek = (x: number) => {
    const v = Math.min(DUR, Math.max(0, x));
    manual.current = v;
    if (audio.current && audio.current.readyState > 0) audio.current.currentTime = v;
    setT(v);
  };
  const toggle = () => {
    const a = audio.current;
    if (!a) return;
    if (a.paused) {
      if (a.readyState === 0 && a.error) return;
      a.currentTime = t;
      a.play().then(() => setPlaying(true)).catch((e: Error) => { setPlaying(false); setError(`播放失败：${e.message}`); });
    } else { a.pause(); setPlaying(false); }
  };
  return {t, playing, toggle, seek, error};
}

export const TimeProvider: React.FC<{t: number; children: React.ReactNode}> = ({t, children}) => (
  <TimeContext.Provider value={t}>{children}</TimeContext.Provider>
);
