// 页面地址上的参数：截图工具（view_screenshot）靠它们指定拍什么，见 view/README.md 的截图约定
export const params = new URLSearchParams(location.search);

export const RECORD = params.get('record') !== '0';          // 截图页面不记录状态、不改排版、不写批注
export const CAPTURE = params.get('capture') === '1';
export const SOLO = CAPTURE && params.has('board');           // 截某一块画板时只画那一块
export const FULL = CAPTURE && params.get('full') === '1';    // 截整页：接缝、素材页不限高度
export const LAZY = CAPTURE ? 'eager' : 'lazy';               // 截图时图片立刻加载
export const DECODE = CAPTURE ? 'sync' : 'async';

export const numParam = (name: string): number | null => (params.has(name) ? Number(params.get(name)) : null);
