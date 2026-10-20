// 外壳：1920×1080 舞台按窗口缩放；预载静帧后允许播放；全曲一个页面（H3 演示）。
// 键盘：空格 播放/暂停；← → 前后 2 秒。地址 ?t=秒 从某一刻开始；?clean 截帧用（不显示播放键）。
import React, {useEffect, useState} from 'react';
import {TimeProvider, useAudioClock} from './core/clock';
import {DUR} from './core/time';
import {loadCues} from './ui/kit';
import {H3Film} from './h3';

const IMAGES = ['0006', '0007', '0031', '0032', '0033', '0034', '0047'].map((k) => `/v9/${k}.webp`);
function useFit() {
  const [k, setK] = useState(1);
  useEffect(() => {
    const f = () => setK(Math.min(innerWidth / 1920, innerHeight / 1080));
    f(); addEventListener('resize', f); return () => removeEventListener('resize', f);
  }, []);
  return k;
}
function usePreload() {
  const [done, setDone] = useState(0);
  useEffect(() => { let n = 0; IMAGES.forEach((s) => { const i = new Image(); i.onload = i.onerror = () => setDone(++n); i.src = s; }); }, []);
  return done / IMAGES.length;
}

export const App: React.FC = () => {
  const qs = new URLSearchParams(location.search);
  const start = +(qs.get('t') ?? 0);
  const clean = qs.has('clean');
  const {t, seek, toggle, playing, error} = useAudioClock('/音频/歌曲.mp3', start);
  const k = useFit();
  const ready = usePreload();
  useEffect(() => {
    if (ready < 1) return;
    Promise.all([loadCues(), document.fonts.ready]).then(() => { (window as unknown as {__ready: boolean}).__ready = true; });
  }, [ready]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code === 'Space') { e.preventDefault(); if (ready >= 1) toggle(); }
      if (e.code === 'ArrowRight') seek(t + 2);
      if (e.code === 'ArrowLeft') seek(t - 2);
    };
    addEventListener('keydown', onKey);
    return () => removeEventListener('keydown', onKey);
  });
  (window as unknown as {seek: (x: number) => void}).seek = seek;
  const left = (innerWidth - 1920 * k) / 2, top = (innerHeight - 1080 * k) / 2;
  return (
    <div className="stage" style={{transform: `translate(${left}px, ${top}px) scale(${k})`}}>
      <TimeProvider t={t}><H3Film /></TimeProvider>
      {!clean && error && (
        <div style={{position: 'absolute', left: 0, right: 0, bottom: 120, textAlign: 'center', zIndex: 60}}>
          <span style={{display: 'inline-block', padding: '14px 26px', background: 'rgba(20,10,10,.85)', color: '#ffd9c8', font: '500 26px/1.4 sans-serif', borderRadius: 6}}>{error}</span>
        </div>
      )}
      {!clean && !error && !playing && t === start && (
        <div className="gate" onClick={() => ready >= 1 && toggle()}><div>{ready >= 1 ? '▶' : `${Math.round(ready * 100)}%`}</div></div>
      )}
      {!clean && <div className="dev">{t.toFixed(2)} / {DUR.toFixed(2)}s · 空格播放 ←→</div>}
    </div>
  );
};
