# 视图前端开发

从本目录运行：

```sh
npm ci
npm test
npm run build
```

`npm run build` 检查 TypeScript、运行测试、生成 SDK、复制语言资源并编译网页。提交源码和对应的 `src/layerweave/tool/builtin/view/web`、`sdk`、`locales` 产物；不要手改生成文件。官方插件在独立仓库构建。

- 计算逻辑放在 src/model，组件放在 canvas、side、tree 等对应目录；不让纯模型依赖浏览器状态。
- 语言词典的手写来源是 src/i18n/zh.json 与 en.json。翻译软件文案，保留用户内容和机器字段。
- 语言切换保留草稿、组件身份与媒体缓存，不触发重新解码。
- 改动 host 接口时同步生成 SDK 和兼容说明。旧插件可继续使用已声明的接口。
- 保持截图的 record=0 和实际就绪约定；性能测量不与其他浏览器测量并行执行。

数据结构与完整验证方法见[视图开发说明](../../src/layerweave/tool/builtin/view/DEVELOPMENT.md)，插件接口见[协议](../../src/layerweave/tool/builtin/view/PLUGINS.md)。
