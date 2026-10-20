// 歌词：运行时读 srt（代码里不写原文）。srt 放在 assets/public/音频/歌词_日中.srt，需自备。
type Cue = {start: number; end: number; ja: string; zh: string};
let CUES: Cue[] = [];
let loading: Promise<void> | null = null;
const sec = (s: string) => { const [h, m, r] = s.trim().split(':'); return +h * 3600 + +m * 60 + parseFloat(r.replace(',', '.')); };
export function loadCues() {
  return (loading ??= fetch('/音频/歌词_日中.srt').then((r) => (r.ok ? r.text() : '')).then((raw) => {
    CUES = raw.replace(/^\uFEFF/, '').trim().split(/\r?\n\s*\r?\n/).filter((b) => b.includes('-->')).map((b) => {
      const l = b.split(/\r?\n/).filter((x) => x.trim());
      const [a, z] = l[1].split('-->');
      return {start: sec(a), end: sec(z), ja: (l[2] ?? '').trim(), zh: (l[3] ?? '').trim()};
    });
  }));
}
export const cues = () => CUES;
