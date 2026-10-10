// 只对 Studio 和 npx remotion 命令生效；scripts/*.mjs 走 Node API，参数在脚本里传。
import {Config} from '@remotion/cli/config';

Config.setVideoImageFormat('jpeg');
Config.setOverwriteOutput(true);

// 渲染用的浏览器：本机已有 Chrome Headless Shell 时，用环境变量指定，不把本机路径写进源码。
if (process.env.REMOTION_BROWSER_EXECUTABLE) {
  Config.setBrowserExecutable(process.env.REMOTION_BROWSER_EXECUTABLE);
}
