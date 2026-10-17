export type Locale = 'zh' | 'en';
export type MessageValues = Record<string, string | number>;
export type Translate = (key: string, values?: MessageValues) => string;
export interface UiMessage {
    key: string;
    values?: MessageValues;
    detail?: string;
}
export interface LanguagePack {
    messages?: Record<string, string>;
    display?: {
        label?: string;
        title?: string;
        description?: string;
        params?: Record<string, string>;
    };
    usage_text?: string;
}
export type Localizations = Partial<Record<Locale, LanguagePack>>;
