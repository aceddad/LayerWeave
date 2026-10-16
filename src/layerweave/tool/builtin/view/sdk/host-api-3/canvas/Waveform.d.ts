export declare const waveformLevels: (rms: number[]) => number[];
export declare function peaksFor(url: string): Promise<number[] | null>;
export declare function waveformSize(width: number, height: number, dpr: number): {
    width: number;
    height: number;
};
export declare function drawWaveform(c: CanvasRenderingContext2D, values: number[] | null, w: number, h: number, dpr: number): void;
export declare function Waveform({ url, className }: {
    url: string;
    className?: string;
}): import("react").JSX.Element;
export declare function WaveMark({ at }: {
    at: number | null;
}): import("react").JSX.Element | null;
