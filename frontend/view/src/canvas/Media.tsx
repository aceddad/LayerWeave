// 图片、视频画面的小部件：服务端有 ffmpeg 时视频画面由它抽帧（结果稳定，截图也拍得到），没有时交给浏览器解码
import {frameUrl} from '../api';
import {DECODE, LAZY} from '../params';
import type {Obj} from '../types';

export function Img({src}: {src: string}) {
  return <img loading={LAZY} decoding={DECODE} src={src} alt="" />;
}

export function Frame({project, o, at, frames}: {project: number; o: Obj; at: number | 'end'; frames: boolean}) {
  if (frames) return <Img src={frameUrl(project, o.id, at)} />;
  return <video muted preload="metadata" src={`${o.media!.url}#t=${at === 'end' ? 9999 : at}`} />;
}
