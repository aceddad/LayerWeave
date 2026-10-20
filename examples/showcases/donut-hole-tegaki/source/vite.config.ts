import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';

// 素材在 ../assets/public：/v9/编号.webp（画的零件），/音频/歌曲.mp3 与 /音频/歌词_日中.srt（需自备，见 README）
export default defineConfig({
  plugins: [react()],
  publicDir: '../assets/public',
  server: {port: 5199, strictPort: true},
});
