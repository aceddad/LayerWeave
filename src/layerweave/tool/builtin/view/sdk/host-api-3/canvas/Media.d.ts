import type { Obj } from '../types';
import type { ImageLease } from './imageCache';
export declare function Img({ src }: {
    src: string;
}): import("react").JSX.Element;
export declare function Thumb({ project, o, width, frames }: {
    project: number;
    o: Obj;
    width: number;
    frames: boolean;
}): import("react").JSX.Element;
export declare function Frame({ project, o, at, frames }: {
    project: number;
    o: Obj;
    at: number | 'end';
    frames: boolean;
}): import("react").JSX.Element;
export declare const loadImage: (src: string) => Promise<HTMLImageElement | null>;
export declare const acquireImage: (src: string) => ImageLease;
export declare const legacyPaintState: () => {
    state: string;
    error?: string;
}[];
export declare function CanvasImg({ src }: {
    src: string;
}): import("react").JSX.Element;
export declare function BlockThumb({ project, o, width, frames }: {
    project: number;
    o: Obj;
    width: number;
    frames: boolean;
}): import("react").JSX.Element;
export declare function BlockFrame({ project, o, at, frames }: {
    project: number;
    o: Obj;
    at: number | 'end';
    frames: boolean;
}): import("react").JSX.Element;
