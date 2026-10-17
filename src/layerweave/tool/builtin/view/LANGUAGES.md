# 中英语言包

视图 0.29.0 起提供中文和英文。顶栏的“中文 / English”即时切换，不刷新页面；批注草稿、对象选择、画板位置和插件的当前状态保留。语言只影响软件界面，不翻译项目名称、正文、批注、署名、路径或轴单位数据。

初始化顺序为 URL 的 `lang=zh/en`、浏览器保存的选择、中文。只有手动切换会保存浏览器偏好；链接中的语言不会覆盖已有偏好。复制链接带上当前语言，“复制文字版”也使用当前语言。

```sh
python -X utf8 -m layerweave.tool.builtin.view.screenshot DATABASE PROJECT_ID output.png --lang en
python -X utf8 -m layerweave.tool.builtin.view.screenshot DATABASE PROJECT_ID output.png --link "http://127.0.0.1:8765/?project=1&lang=en"
```

编号与路径替换为实际值。截图的显式 `--lang` 优先于链接；二者都没有时使用中文，不读取用户浏览器偏好。`lang` 是宿主保留参数，插件不能通过 `--param lang=...` 覆盖。CLI/help 和开发文档使用中文。

## 修改宿主文案

唯一手写词典为 `frontend/view/src/i18n/zh.json` 与 `en.json`。构建将它们复制到本包的 `locales/`，供 Python 的复制文字和可展示错误使用；不要手改复制文件。

键使用语义名称，值为完整句子，变量用 `{name}`。两份词典的键与占位符保持一致；插值仅执行一次，不解析用户内容或 HTML。组件调用 `useI18n()` 订阅语言，再通过返回的 `t` 翻译；事件回调可以使用 `tr` 读取当前语言。持续展示的通知保存 `ui(key, values, detail)`，在呈现时用 `renderMessage` 翻译。

纯模型辅助函数接收可选翻译函数，默认中文，不依赖浏览器语言状态。不要把翻译后的文字用于条件判断、身份、查询或媒体缓存键。Python `ViewError` 保留中文异常字符串，并通过 HTTP 的可选 `ui` 字段传递消息键、参数和原始详情。未知外部异常保留原始内容，页面显示翻译后的概要。

## 插件提供自己的语言包

插件仍是独立选装包。host.api 保持 3；使用 `host.t` / `host.useI18n` 的插件需要声明视图最低版本 0.29.0。旧插件可继续运行，缺翻译时显示原文，不因切换语言而自动安装或升级。

在现有 plugin.json 中加入以下字段（其余身份、入口和参数声明照常保留）：

```json
{
  "requires": {"view": ">=0.29.0", "host_api": [3]},
  "languages": ["zh", "en"],
  "locales": {"zh": "locales/zh.json", "en": "locales/en.json"}
}
```

例如 `locales/en.json`：

```json
{
  "messages": {"page.count": "Items: {count}"},
  "display": {
    "label": "My plugin",
    "title": "Browse items",
    "description": "Browse project items one page at a time.",
    "params": {"page": "Page number, starting at 1."}
  },
  "usage": "README.en.md"
}
```

`messages` 放界面词条；`display` 与 `usage` 可省略。`display.params` 只替换原参数的说明，不改变类型、默认值或必填规则。原 manifest 不被翻译覆盖，身份与包一致性仍按原声明检查。语言与说明路径都相对于插件根目录。

```ts
export default function plugin(host) {
  function Page() {
    const {locale, t} = host.useI18n();
    const [count, setCount] = host.React.useState(1);
    return host.React.createElement('button', {onClick: () => setCount(count + 1)},
      t('page.count', {count}));
  }
  return {label: '我的插件', page: Page};
}
```

普通回调用 `host.t(key, values)`；工厂函数中不要调用 Hook。每个插件只能访问自己的词典；按选定语言、中文、键名回退。显示元数据缺失则回退原 manifest/工厂值。切换语言不重新调用工厂、不重新挂载组件或样式，不应触发媒体 effect；把解码错误保存为键，展示时再翻译。

视图 HTTP 清单带 `localizations`，普通 CLI 清单不附整份词典。插件详情带各语言的 `usage_text`；市场目录只附翻译后的简介。发布脚本收集明确声明的语言文件与说明，验证它们存在；运行时某份语言文件丢失或损坏会提示并回退，不阻断其他可用代码。

验证方法：宿主运行 `npm run build`、Python 回归与 `python -X utf8 -m tests.packaging.check_wheel`；插件运行自己的构建、词条占位符检查和浏览器测试。英文页面允许保留中文用户数据；不能以“页面没有汉字”判断翻译完成。
