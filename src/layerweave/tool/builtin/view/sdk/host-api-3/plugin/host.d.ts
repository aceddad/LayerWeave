import * as React from 'react';
import { Frame, Img, Thumb } from '../canvas/Media';
import { Waveform } from '../canvas/Waveform';
import { mediaUrl } from '../canvas/mediaUrl';
import { Pager, pageSlice } from './Pager';
import { kindOf, lastAt } from '../model/kinds';
import type { Model, ObjWithLayer } from '../model/model';
import { keyOf, lanes, rootsOf } from '../model/model';
import { fmt, fmtSpan, isSec } from '../model/units';
import type { Board } from '../types';
export declare const PLUGIN_API = 3;
export interface ViewSnapshot {
    model: Model | null;
    boards: Board[];
    project: number | null;
    frames: boolean;
    playhead: number | null;
    selected: number | null;
    picked: number[];
}
export interface PluginHost {
    api: number;
    React: typeof React;
    capture: boolean;
    full: boolean;
    useView(): ViewSnapshot;
    selectObject(id: number): void;
    startWalk(ref: string): void;
    toast(text: string): void;
    markReady(): void;
    addStyle(css: string): void;
    numParam(name: string): number | null;
    components: {
        Img: typeof Img;
        Thumb: typeof Thumb;
        Frame: typeof Frame;
        Waveform: typeof Waveform;
        Pager: typeof Pager;
    };
    util: {
        kindOf: typeof kindOf;
        lastAt: typeof lastAt;
        isSec: typeof isSec;
        fmt: typeof fmt;
        fmtSpan: typeof fmtSpan;
        lanes: typeof lanes;
        keyOf: typeof keyOf;
        rootsOf: typeof rootsOf;
        mediaUrl: typeof mediaUrl;
        pageSlice: typeof pageSlice;
    };
}
export interface ViewPlugin {
    name?: string;
    label: string;
    title?: string;
    handles?: string[];
    page?: React.ComponentType;
    side?: React.ComponentType;
    objectDetail?: React.ComponentType<{
        object: ObjWithLayer;
        model: Model;
    }>;
    jumpPoints?: (model: Model, board: Board) => number[];
}
export type PluginFactory = (host: PluginHost) => ViewPlugin;
export type LoadedPlugin = ViewPlugin & {
    name: string;
};
export declare function makeHost(styles?: HTMLStyleElement[]): PluginHost;
