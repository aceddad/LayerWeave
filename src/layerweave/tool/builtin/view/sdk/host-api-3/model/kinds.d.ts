import type { Obj } from '../types';
export type ObjKind = 'image' | 'video' | 'audio' | 'file' | 'text' | 'other';
export declare const kindOf: (o: Obj) => ObjKind;
export declare const KIND_LABEL: Record<string, string>;
export declare const lastAt: (o: Obj, secUnit: boolean) => number | "end";
