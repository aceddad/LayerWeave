export interface ImageLease {
    url: string;
    promise: Promise<HTMLImageElement | null>;
    release: () => void;
}
export declare class ImageCache {
    private loader;
    private unusedLimit;
    private unusedBytes;
    private entries;
    private serial;
    constructor(loader?: (src: string) => Promise<HTMLImageElement | null>, unusedLimit?: number, unusedBytes?: number);
    get size(): number;
    private get;
    acquire(url: string): ImageLease;
    load(url: string): Promise<HTMLImageElement | null>;
    private trim;
}
export declare const decodedImages: ImageCache;
