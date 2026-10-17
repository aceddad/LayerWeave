import type { Translate, Locale } from '../i18n/types';
export declare const isSec: (unit?: string | null) => boolean;
export declare function fmt(t: number | null | undefined, unit?: string): string;
export declare const fmtSpan: (d: number, unit: string, tr?: Translate) => string;
export declare function ago(iso: string, locale?: Locale): string;
export declare function ticks(a: number, e: number, pps: number, zoom: number, unit: string): {
    t: number;
    x: number;
    label: string;
}[];
