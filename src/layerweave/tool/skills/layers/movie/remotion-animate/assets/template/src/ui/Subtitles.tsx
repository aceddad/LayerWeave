import {useEffect, useState} from 'react';
import {continueRender, delayRender, staticFile} from 'remotion';
import {prog} from '../time';

// 字幕层：渲染时读取 public/media/subtitles.srt。代码里不写任何字幕内容。
// mode = 'placeholder' 时把每个字换成占位符，只用来检查排版（也可以改用涂黑字体，见 text-redacted-layout）。
export type SubtitleMode = 'off' | 'on' | 'placeholder';
type Cue = {start: number; end: number; text: string};

const SRT = 'media/subtitles.srt';
let CUES: Cue[] | null = null;
let loading: Promise<void> | null = null;

const sec = (s: string) => {
  const [h, m, rest] = s.trim().split(':');
  const [ss, ms] = rest.split(/[,.]/);
  return +h * 3600 + +m * 60 + +ss + +(ms ?? 0) / 1000;
};

const load = () =>
  (loading ??= fetch(staticFile(SRT))
    .then((r) => (r.ok ? r.text() : ''))
    .then((raw) => {
      CUES = raw.replace(/^﻿/, '').trim().split(/\r?\n\s*\r?\n/).filter(Boolean).map((block) => {
        const lines = block.split(/\r?\n/);
        const k = lines.findIndex((l) => l.includes('-->'));
        const [a, z] = lines[k].split('-->');
        return {start: sec(a), end: sec(z), text: lines.slice(k + 1).join('\n').trim()};
      });
    }));

const hide = (text: string) => text.replace(/[A-Z]/g, 'X').replace(/[a-z0-9]/g, 'x').replace(/[㐀-鿿]/g, '□');

export const Subtitles: React.FC<{t: number; mode: SubtitleMode}> = ({t, mode}) => {
  const [handle] = useState(() => (mode === 'off' ? null : delayRender('subtitles')));
  const [cues, setCues] = useState<Cue[] | null>(CUES);
  useEffect(() => {
    if (!handle) return;
    load().then(() => {
      setCues(CUES);
      continueRender(handle);
    });
  }, [handle]);
  if (mode === 'off' || !cues) return null;
  const cue = cues.find((c) => t >= c.start && t < c.end);
  if (!cue) return null;
  const fade = Math.min(prog(t, cue.start, cue.start + 0.15), 1 - prog(t, cue.end - 0.15, cue.end));
  return (
    <div style={{position: 'absolute', left: 0, right: 0, bottom: 90, textAlign: 'center', color: '#fff', fontSize: 52,
      opacity: fade, whiteSpace: 'pre-line', textShadow: '0 2px 8px rgba(0,0,0,.8)'}}>
      {mode === 'placeholder' ? hide(cue.text) : cue.text}
    </div>
  );
};
