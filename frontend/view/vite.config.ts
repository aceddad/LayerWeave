// LayerWeave 视图网页的构建配置：编译结果直接写进 Python 工具包的 web/，由 view.server 提供；用的人不需要 Node。
// 开发时 npm run dev，接口转给本机已经在跑的视图服务（默认 8765 端口）。
import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import {fileURLToPath} from 'node:url';
import thirdPartyNotices from './tools/third-party-notices.mjs';

const backend = process.env.LAYERWEAVE_VIEW ?? 'http://127.0.0.1:8765';

export default defineConfig({
  plugins: [react(), thirdPartyNotices(), {name: 'stable-html-newlines', transformIndexHtml: (html) => html.replace(/\r\n?/g, '\n')}],
  base: './',
  build: {
    outDir: fileURLToPath(new URL('../../src/layerweave/tool/builtin/view/web', import.meta.url)),
    emptyOutDir: true,
    assetsDir: 'assets',
    chunkSizeWarningLimit: 1200,
  },
  server: {
    proxy: Object.fromEntries(['/api', '/media', '/frame'].map((path) => [path, backend])),
  },
});
