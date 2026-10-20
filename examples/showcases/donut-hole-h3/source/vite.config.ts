import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';

// 素材在 ../assets/public：/h3/视频/镜NN.mp4（H3 生成的片段）、/h3/svg/NN.svg（纯代码镜头）、/v9/编号.webp（几张静帧），
// /音频/歌曲.mp3 与 /音频/歌词_日中.srt 需自备（见 README）
export default defineConfig({
  plugins: [react()],
  publicDir: '../assets/public',
  server: {port: 5199, strictPort: true},
});
