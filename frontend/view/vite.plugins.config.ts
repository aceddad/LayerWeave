// 视图插件的构建：plugins/<名字>/index.tsx → src/layerweave/tool/builtin/view/plugins/<名字>/plugin.js（ES 模块，默认导出 (host) => ViewPlugin）。
// 不打包 React：JSX 编译成 h(...)，h 和 Fragment 在插件被加载时从宿主给的 host.React 拿（见 plugins/cuts/index.tsx）。
// npm run build 先构建网页、再构建插件；视图包的 component.toml 里 [[view_plugins]] 登记每个插件的入口
import {defineConfig} from 'vite';
import {existsSync, readdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const here = fileURLToPath(new URL('.', import.meta.url));
const names = readdirSync(`${here}plugins`, {withFileTypes: true})
  .filter((d) => d.isDirectory() && existsSync(`${here}plugins/${d.name}/index.tsx`)).map((d) => d.name);

export default defineConfig({
  esbuild: {jsx: 'transform', jsxFactory: 'h', jsxFragment: 'Fragment'},
  publicDir: false,
  build: {
    outDir: fileURLToPath(new URL('../../src/layerweave/tool/builtin/view/plugins', import.meta.url)),
    emptyOutDir: true,
    lib: {
      entry: Object.fromEntries(names.map((name) => [name, `${here}plugins/${name}/index.tsx`])),
      formats: ['es'],
      fileName: (_format, name) => `${name}/plugin.js`,
    },
  },
});
