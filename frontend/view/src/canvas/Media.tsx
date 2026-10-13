// 图片、视频画面的小部件：服务端有 ffmpeg 时视频画面由它抽帧（结果稳定，截图也拍得到），没有时交给浏览器解码
import {frameUrl, thumbUrl} from '../api';
import {DECODE, LAZY} from '../params';
import type {Obj} from '../types';

export function Img({src}: {src: string}) {
  return <img loading={LAZY} decoding={DECODE} src={src} alt="" />;
}

// 图片对象的缩略图：服务端有 ffmpeg 时按宽度缩好（缩不了的它自己送原图）；没有 ffmpeg 时直接用原图。
// 画布格子、素材网格用 320 宽，接缝页 640 宽；看单个对象详情时才用原图
export function Thumb({project, o, width, frames}: {project: number; o: Obj; width: number; frames: boolean}) {
  return <Img src={frames ? thumbUrl(project, o.id, width) : o.media!.url!} />;
}

export function Frame({project, o, at, frames}: {project: number; o: Obj; at: number | 'end'; frames: boolean}) {
  if (frames) return <Img src={frameUrl(project, o.id, at)} />;
  return <video muted preload="metadata" src={`${o.media!.url}#t=${at === 'end' ? 9999 : at}`} />;
}
