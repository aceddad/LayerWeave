// v10 的全部段落（段落名 → 页面）
import type React from 'react';
import {Intro9, A1_9, A2_9} from './s1';
import {B1_9, Chorus1_9, Interlude1_9} from './s2';
import {A3_9, B2_9, Chorus2_9} from './s3';
import {Interlude2_9, C9, Chorus3_9, Fill9, Outro9} from './s4';

export const V10_PAGES: Record<string, React.FC> = {'前奏': Intro9, 'A1': A1_9, 'A2': A2_9, 'B1': B1_9, '副歌一': Chorus1_9, '间奏一': Interlude1_9,
  'A3': A3_9, 'B2': B2_9, '副歌二': Chorus2_9, '间奏二': Interlude2_9, 'C 段': C9, '副歌三': Chorus3_9, '鼓的过门': Fill9, '尾声': Outro9};
