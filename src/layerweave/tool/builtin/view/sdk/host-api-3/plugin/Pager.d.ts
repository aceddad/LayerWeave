export declare function pageSlice<T>(items: T[], page: number, per: number): {
    items: T[];
    page: number;
    pages: number;
};
export declare function Pager({ total, page, per, onPage, sizes, onPer }: {
    total: number;
    page: number;
    per: number;
    onPage: (page: number) => void;
    sizes?: number[];
    onPer?: (per: number) => void;
}): import("react").JSX.Element;
