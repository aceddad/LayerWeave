把素材放在这里，代码里用 `staticFile('media/文件名')` 引用：

- 音轨：文件名写进 `src/time.ts` 的 `MUSIC`；没有音轨时把 `MUSIC` 设为 `null`。
- 字幕：`subtitles.srt`。渲染时由 `src/ui/Subtitles.tsx` 读取，代码里不写字幕内容。
- 图片、字体等其他素材也放在 `public/` 下。
