// 视图插件的接口：插件是一个编译好的 ES 模块，默认导出一个函数 (host) => ViewPlugin。
// 视图管一份本机插件清单（view/plugins.py；view_plugin 命令和顶栏「插件」小窗改它），页面按清单用 import() 载入（plugin/registry.ts）。
// 插件只拿到这里给的东西：React（和视图共用一份，插件不要自己打包）、读项目的钩子、几个动作、画图的小部件和工具函数。
// 写入照旧只有视图自己的两种（批注、折叠）；插件不碰数据库。改这里就是改插件接口：只加不改，改了要在 TOOL_TYPES.md 写明
import * as React from 'react';
import {useShallow} from 'zustand/react/shallow';
import {selectObject, startWalk} from '../actions';
import {Frame, Img, Thumb} from '../canvas/Media';
import {markReady} from '../capture';
import {kindOf, lastAt} from '../model/kinds';
import type {Model, ObjWithLayer} from '../model/model';
import {keyOf, lanes, rootsOf} from '../model/model';
import {fmt, fmtSpan, isSec} from '../model/units';
import {CAPTURE, FULL, numParam} from '../params';
import {useModel, useStore} from '../store';
import {toast} from '../sync';
import type {Board, Layer, Obj} from '../types';

// 接口版本：插件可以按它判断宿主够不够新。1：页面、跳转点；2：加了侧栏、对象详情、画布格子
export const PLUGIN_API = 2;

export interface ViewSnapshot {
  model: Model | null; boards: Board[]; project: number | null; frames: boolean;
  playhead: number | null; selected: number | null;
}

export interface PluginHost {
  api: number;
  React: typeof React;
  capture: boolean;        // 截图页面：画完要调 markReady()
  full: boolean;           // 截整页（--full-page）：页面不要限高
  useView(): ViewSnapshot;
  selectObject(id: number): void;          // 选中对象，切回画布并飞过去
  startWalk(ref: string): void;            // 侧栏"沿着读"从这里开始（"object:16"）
  toast(text: string): void;
  markReady(): void;
  addStyle(css: string): void;             // 插件自己的样式；插件关掉、去掉时跟着拿掉
  numParam(name: string): number | null;   // 地址参数（截图、复制链接用的那些）
  components: {Img: typeof Img; Thumb: typeof Thumb; Frame: typeof Frame};
  util: {kindOf: typeof kindOf; lastAt: typeof lastAt; isSec: typeof isSec; fmt: typeof fmt; fmtSpan: typeof fmtSpan;
         lanes: typeof lanes; keyOf: typeof keyOf; rootsOf: typeof rootsOf};
}

// 画布格子里画东西：视图给一块 canvas（设备像素，按镜头停下时的缩放），排进和缩略图同一个重画队列（每帧最多画 8 毫秒）。
// 只在格子大小变了、镜头停下换了缩放、对象变了时才再画；平移、拖动时不画。格子太小（只画色块的那一档）时不画
export interface BlockBox {
  width: number; height: number;   // canvas 的像素
  unit: string;                    // 这个对象所在的根的单位（isSec(unit) 判断是不是秒）
  layer: Layer;                    // 对象所在的层
}
export interface BlockPainter {
  kinds?: string[];                // 按 kindOf 认：image、video、audio、text、file、other
  types?: string[];                // 按对象的类型名认（o.type），工具包自己登记的新类型用这个
  // 画进 ctx（已经清空）。要等图片之类的就返回 Promise，截图会等它画完
  draw(ctx: CanvasRenderingContext2D, o: Obj, box: BlockBox): void | Promise<void>;
}

// 插件能放东西的位置（栏位）。每个位置都包在出错保护里：插件出错只在它自己那块写一句，不影响别的
export interface ViewPlugin {
  name?: string;                         // 不用写：名字由清单定（view_plugin add --name），也是地址里的 view=、side=
  label: string;                         // 顶栏标签、侧栏标签上的字
  title?: string;                        // 标签的说明
  handles?: string[];                    // 管哪些种类的对象（kindOf）：项目里一个都没有时不显示它的页面和侧栏；对象详情只给这些种类的对象
  page?: React.ComponentType;            // 顶栏：专用页面
  side?: React.ComponentType;            // 侧栏：一个标签（和「此刻」「批注」并排），点开是这个组件
  objectDetail?: React.ComponentType<{object: ObjWithLayer; model: Model}>;   // 对象详情里的一段（侧栏「此刻」里选中的对象）；没话说就返回 null
  block?: BlockPainter;                  // 画布上：某类对象的格子里画什么（换掉默认的缩略图、画面、波形）
  jumpPoints?: (model: Model, board: Board) => number[];   // 键盘 [ ] 在这些时刻之间跳（画板时间）
}

export type PluginFactory = (host: PluginHost) => ViewPlugin;
export type LoadedPlugin = ViewPlugin & {name: string};   // 载入以后：名字是清单里的

// styles：这个插件加的样式，插件拿下来时一起拿掉
export function makeHost(styles: HTMLStyleElement[] = []): PluginHost {
  return {
    api: PLUGIN_API, React, capture: CAPTURE, full: FULL,
    useView: () => {
      const model = useModel();
      const s = useStore(useShallow((st) => ({boards: st.boards, project: st.project, frames: st.frames, playhead: st.playhead, selected: st.selected})));
      return {model, ...s};
    },
    selectObject: (id) => selectObject(id), startWalk, toast: (text) => toast(text), markReady,
    addStyle: (css) => { const el = document.createElement('style'); el.textContent = css; document.head.appendChild(el); styles.push(el); },
    numParam,
    components: {Img, Thumb, Frame},
    util: {kindOf, lastAt, isSec, fmt, fmtSpan, lanes, keyOf, rootsOf},
  };
}
