// 外壳：1920×1080 舞台按窗口缩放；先预载全部图再允许播放；按段落分派页面。
// 键盘：空格 播放/暂停；← → 前后 2 秒；PageUp / PageDown 上一段/下一段。地址 ?t=秒 从某一刻开始；?clean 截帧用（不显示播放键）。
import React, {useEffect, useState} from 'react';
import {TimeProvider, useAudioClock} from './core/clock';
import {DUR, SECTIONS, sectionAt} from './core/time';
import {loadCues} from './ui/kit';
import {V10_PAGES} from './v10';
import {V9_IMAGES} from './v10/kit';

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
  useEffect(() => {
    let n = 0;
    V9_IMAGES.forEach((src) => { const i = new Image(); i.onload = i.onerror = () => setDone(++n); i.src = src; });
  }, []);
  return done / V9_IMAGES.length;
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
      const i = SECTIONS.indexOf(sectionAt(t));
      if (e.code === 'Space') { e.preventDefault(); if (ready >= 1) toggle(); }
      if (e.code === 'ArrowRight') seek(t + 2);
      if (e.code === 'ArrowLeft') seek(t - 2);
      if (e.code === 'PageDown' && SECTIONS[i + 1]) seek(SECTIONS[i + 1].begin + 0.01);
      if (e.code === 'PageUp' && i > 0) seek(SECTIONS[i - 1].begin + 0.01);
    };
    addEventListener('keydown', onKey);
    return () => removeEventListener('keydown', onKey);
  });
  (window as unknown as {seek: (x: number) => void}).seek = seek;
  const Page = V10_PAGES[sectionAt(t).name];
  const g = Math.floor(Math.min(t, 203.83) * 12);
  const left = (innerWidth - 1920 * k) / 2, top = (innerHeight - 1080 * k) / 2;
  return (
    <div className="stage" style={{transform: `translate(${left}px, ${top}px) scale(${k})`}}>
      <TimeProvider t={t}>{Page && <Page />}</TimeProvider>
      <div className="grain" style={{transform: `translate(${(Math.sin(g * 7.1) * 20).toFixed(0)}px, ${(Math.cos(g * 3.3) * 20).toFixed(0)}px)`}} />
      {!clean && error && (
        <div style={{position: 'absolute', left: 0, right: 0, bottom: 120, textAlign: 'center', zIndex: 60}}>
          <span style={{display: 'inline-block', padding: '14px 26px', background: 'rgba(20,10,10,.85)', color: '#ffd9c8', font: '500 26px/1.4 sans-serif', borderRadius: 6}}>{error}</span>
        </div>
      )}
      {!clean && !error && !playing && t === start && (
        <div className="gate" onClick={() => ready >= 1 && toggle()}><div>{ready >= 1 ? '▶' : `${Math.round(ready * 100)}%`}</div></div>
      )}
      {!clean && <div className="dev">{t.toFixed(2)} / {DUR.toFixed(2)}s · 空格播放 ←→ PgUp/PgDn</div>}
    </div>
  );
};
