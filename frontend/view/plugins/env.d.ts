// 插件用 ?raw 把自己的样式作为字符串打进 JS
declare module '*.css?raw' { const css: string; export default css; }
