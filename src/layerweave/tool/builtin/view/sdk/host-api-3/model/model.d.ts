import type { Translate } from '../i18n/types';
import type { Board, Layer, Obj, ProjectData, Root } from '../types';
export declare const NAMES: number, HEAD: number, RULER: number, ROW: number, LANE: number, MIN_LANE: number, PAD: number, GAP: number, STRIP: number, FOLD: number, AUTO_TRACK_WIDTH: number;
export interface Segment {
    root: number;
    offset: number;
    begin: number;
    end: number;
}
export interface Part {
    layer: Layer;
    seg: Segment;
}
export interface Track {
    key: string;
    parent: string | null;
    name: string;
    type: string;
    tips: string;
    depth: number;
    parts: Part[];
    hasChildren: boolean;
}
export interface Item {
    o: Obj;
    layer: Layer;
    offset: number;
    begin: number;
    end: number;
    lane: number;
    laneHeight?: number;
}
export interface FoldMark {
    by: string;
    tips: string;
}
export interface FoldInfo extends FoldMark {
    layers: number[];
    below: number;
    objects: number;
}
export interface TrackLayout {
    track: Track;
    height: number;
    laneHeight: number;
    items: Item[];
    gaps: {
        from: number;
        to: number;
    }[];
    fold: FoldInfo | null;
    other: FoldMark | null;
}
export interface SectionLayout {
    row: number[];
    index: number;
    segments: Segment[];
    tracks: TrackLayout[];
    strip: boolean;
    height: number;
    top: number;
}
export interface BoardLayout {
    board: Board;
    key: number;
    a: number;
    e: number;
    pps: number;
    unit: string;
    precision: number;
    tracksWidth: number;
    width: number;
    height: number;
    sections: SectionLayout[];
}
export interface ViewOptions {
    viewer?: 'user' | 'ai';
    only: Set<number> | null;
    showHidden: boolean;
    canvasWidth: number;
}
export type ObjWithLayer = Obj & {
    layer: Layer;
};
export declare const keyOf: (b: Board) => number;
export declare const rootsOf: (b: Board) => number[];
export declare function lanes(items: {
    begin: number;
    end: number;
}[]): number[];
export declare class Model {
    readonly data: ProjectData;
    readonly opts: ViewOptions;
    readonly roots: Map<number, Root>;
    readonly layers: Map<number, Layer>;
    readonly objects: Map<number, ObjWithLayer>;
    readonly own: Map<number, FoldMark>;
    readonly other: Map<number, FoldMark>;
    private trackCache;
    constructor(data: ProjectData, opts: ViewOptions, previous?: Model);
    get project(): number;
    root(id: number): Root | undefined;
    layer(id: number): Layer | undefined;
    object(id: number): ObjWithLayer | undefined;
    unitOfRoot(id: number | null | undefined): string;
    precisionOf(id: number | null | undefined): number | null;
    nameOf(id: number, tr?: Translate): string;
    allObjects(): ObjWithLayer[];
    segments(row: number[]): Segment[];
    segmentAt(row: number[], t: number): Segment | null;
    extent(b: Board): [number, number];
    pps(b: Board): number;
    boardHidden(b: Board): boolean;
    rowTracks(row: number[]): Track[];
    foldOf(t: Track): FoldMark | null;
    otherFoldOf(t: Track): FoldMark | null;
    visibleTracks(row: number[]): Track[];
    below(t: Track, row: number[]): Track[];
    trackLayout(track: Track, row: number[], board?: Board): TrackLayout;
    boardLayout(b: Board): BoardLayout | null;
    private layoutCache;
    private computeLayout;
    boardOf(boards: Board[], rootId: number | null | undefined): Board | undefined;
    offsetOf(boards: Board[], rootId: number): number;
}
export declare function adoptOrphans(data: ProjectData): ProjectData;
