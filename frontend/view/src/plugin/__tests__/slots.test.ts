// 样板插件「字数」照接口给出两个栏位
import * as React from 'react';
import {describe, expect, it} from 'vitest';
import example, {FAST, count, perSecond} from '../../../example-plugin/plugin.js';
import {kindOf} from '../../model/kinds';
import {fmt, isSec} from '../../model/units';
import type {Obj} from '../../types';
import type {PluginHost} from '../host';

const obj = (patch: Partial<Obj>): Obj => ({id: 1, name: '', type: 'Text', begin: 0, end: 2, tips: '', text: null, media: null, information: {}, ...patch});

describe('样板插件「字数」', () => {
  it('数字数不算空白；每秒几个字只在单位是秒、对象有长度时算', () => {
    expect(count(' 你 好\n世界 ')).toBe(4);
    expect(count(null)).toBe(0);
    expect(perSecond(obj({text: '一二三四', begin: 1, end: 3}), true)).toBe(2);
    expect(perSecond(obj({text: '一二三四', begin: 1, end: 3}), false)).toBeNull();
    expect(perSecond(obj({text: '一二三四', begin: 1, end: 1}), true)).toBeNull();
  });

  it('照接口给出侧栏和对象详情，不再有画布格子', () => {
    const styles: string[] = [];
    const host = {React, addStyle: (css: string) => styles.push(css), util: {kindOf, isSec, fmt}} as unknown as PluginHost;
    const p = example(host);
    expect([p.label, p.handles, typeof p.side, typeof p.objectDetail, 'block' in p]).toEqual(['字数', ['text'], 'function', 'function', false]);
    expect(styles).toHaveLength(1);
  });
});
