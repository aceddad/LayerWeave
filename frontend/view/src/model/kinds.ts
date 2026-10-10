import type {Obj} from '../types';

export type ObjKind = 'image' | 'video' | 'audio' | 'file' | 'text' | 'other';

export const kindOf = (o: Obj): ObjKind => (o.media ? o.media.kind : o.text != null ? 'text' : 'other');

export const KIND_LABEL: Record<string, string> = {image: '图片', video: '视频', audio: '音频', text: '文字', file: '文件', other: '其他'};

// 片段里最后一帧的时间：单位是秒时按对象长度算（片段只用了文件前一段时也对）；否则取文件的最后一帧
export const lastAt = (o: Obj, secUnit: boolean): number | 'end' => (secUnit && o.end > o.begin ? Math.max(0, o.end - o.begin - 0.04) : 'end');
