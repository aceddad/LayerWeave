export type Kind = 'object' | 'layer';
export interface Ref {
    kind: Kind;
    project: number;
    id: number;
}
export interface Bind {
    id: number;
    tips: string;
    source: Ref;
    target: Ref;
}
export interface Media {
    kind: 'image' | 'video' | 'audio' | 'file';
    source: string;
    available: boolean;
    url: string | null;
}
export interface Obj {
    id: number;
    name: string;
    type: string;
    begin: number;
    end: number;
    tips: string;
    text: string | null;
    media: Media | null;
    information: Record<string, any>;
}
export interface Layer {
    id: number;
    name: string;
    type: string;
    father: number | null;
    depth: number | null;
    root: number | null;
    axis: Record<string, any> | null;
    tips: string;
    objects: Obj[];
    role: 'note' | null;
    hidden: boolean;
}
export interface Root {
    id: number;
    name: string;
    axis: Record<string, any>;
    unit: string;
    key: string | null;
    extent: [number, number];
}
export interface ProjectData {
    project: {
        id: number;
        name: string;
        tips: string;
    };
    roots: Root[];
    layers: Layer[];
    binds: Bind[];
    folds?: FoldRow[];
    noteReads?: Record<string, Record<string, number>>;
}
export type ViewChange = {
    id: number;
    operation_id?: string;
    change_id?: number;
    undo_of?: string | null;
} & ({
    kind: 'object';
    before_layer: number | null;
    after_layer: number | null;
    after: Obj | null;
} | {
    kind: 'bind';
    after: Bind | null;
} | {
    kind: 'project';
    after: ProjectSummary;
} | {
    kind: 'view_layer';
    after: FoldRow | null;
} | {
    kind: 'view_note';
    after: Record<string, number> | null;
});
export type ProjectPage = {
    next_cursor: number;
    has_more: boolean;
} & ({
    mode: 'snapshot';
    data: ProjectData | null;
} | {
    mode: 'delta';
    changes: ViewChange[];
});
export interface FoldRow {
    layer: number;
    user: string;
    user_tips: string;
    ai: string;
    ai_tips: string;
}
export interface ProjectSummary {
    id: number;
    name: string;
    tips: string;
}
export interface RootStyle {
    pps: number | null;
    lane_height: number | null;
}
export interface Board {
    rows: number[][];
    x: number | null;
    y: number | null;
    pps: number | null;
    styles?: Record<number, RootStyle>;
    tempPps?: number;
}
export interface Layout {
    boards: Board[];
    serial: number | string;
}
export interface ChangeRecord {
    name?: string;
    layer?: number;
    begin?: number;
    end?: number;
    text?: string;
    source?: string;
}
export interface ChangeItem {
    kind: 'object' | 'layer' | 'bind' | 'project';
    id: number;
    action: 'create' | 'update' | 'delete';
    before: ChangeRecord | null;
    after: ChangeRecord | null;
    fields?: string[];
    information?: {
        key: string;
        before: string | null;
        after: string | null;
    }[];
}
export interface ChangeOp {
    operation_id: string;
    at: string;
    undo_of: string | null;
    items: ChangeItem[];
}
export type View = string;
export interface PluginRow {
    localizations?: import('./i18n/types').Localizations;
    language_warnings?: string[];
    problem_ui?: import('./i18n/types').UiMessage;
    name: string;
    id: string;
    label: string;
    version?: string | null;
    source: 'managed' | 'link';
    path: string;
    on: boolean;
    problem: string | null;
    about: string;
    url?: string;
}
export interface PluginList {
    plugins: PluginRow[];
    file: string;
    folder: string;
    problem: string | null;
    catalog: string;
    recommended: {
        id: string;
        label: string;
        description: string;
    }[];
    aliases: Record<string, string>;
    migration_pending: boolean;
    migration_issues: {
        problem: string;
    }[];
}
export interface MarketItem {
    localizations?: import('./i18n/types').Localizations;
    id: string;
    label: string;
    description: string;
    version: string;
    compatible: boolean;
    supported: boolean;
    installed_version?: string | null;
    problem?: string | null;
}
export interface PluginResult extends PluginList {
    manifest?: {
        id: string;
        version: string;
        label: string;
        description: string;
        requires: unknown;
        params: Record<string, {
            type: string;
            description: string;
            default?: unknown;
            required?: boolean;
        }>;
    } | null;
    localizations?: import('./i18n/types').Localizations;
    usage?: string;
    language_warnings?: string[];
    recorded?: boolean;
    text: string;
    status?: string;
    items?: MarketItem[];
    issues?: {
        message: string;
    }[];
    version?: string;
    id?: string;
}
export declare const SIDES: string[];
export type Side = string;
export type WalkDirection = 'both' | 'out' | 'in';
export interface WalkVia {
    bind: number;
    other: string;
    arrow: 'from' | 'to';
    tips: string;
}
export interface WalkStep {
    ref: string;
    kind: 'object' | 'layer';
    project: number;
    id: number;
    depth: number;
    status: 'found' | 'missing' | 'other_project';
    name: string;
    type: string;
    layer: {
        id: number;
        name: string;
        type: string;
    } | null;
    root: number | null;
    unit: string;
    begin: number | null;
    end: number | null;
    text: string | null;
    source: string | null;
    note: {
        author: string;
        status: 'open' | 'done' | null;
        reply: boolean;
        span: {
            begin: number;
            end: number;
        } | null;
    } | null;
    via: WalkVia[];
}
export interface WalkResult {
    start: string;
    direction: WalkDirection;
    depth: number;
    max_nodes: number;
    steps: WalkStep[];
    loops: number;
    beyond: number;
    skipped: number;
    text: string;
}
