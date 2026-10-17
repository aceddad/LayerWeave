import {create} from 'zustand';
import type {Locale} from './types';
export const useLocale = create<{locale: Locale}>(() => ({locale: 'zh'}));
export const currentLocale = () => useLocale.getState().locale;
