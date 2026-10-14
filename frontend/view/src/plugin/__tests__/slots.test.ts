// 画布格子找谁来画（ViewPlugin.block），以及样板插件「字数」照接口给出三个栏位
import * as React from 'react';
import {describe, expect, it} from 'vitest';
import example, {FAST, count, perSecond} from '../../../example-plugin/plugin.js';
import {kindOf} from '../../model/kinds';
import {fmt, isSec} from '../../model/units';
import type {Obj} from '../../types';
import type {LoadedPlugin, PluginHost} from '../host';
import {painterFor} from '../plan';

const obj = (patch: Partial<Obj>): Obj => ({id: 1, name: '', type: 'Text', begin: 0, end: 2, tips: '', text: null, media: null, information: {}, ...patch});
const draw = () => {};
const plugin = (name: string, block?: LoadedPlugin['block']): LoadedPlugin => ({name, label: name, block});

describe('画布格子找谁来画', () => {
  it('先按类型名，再按种类；都有人认时清单里排在前面的画', () => {
    const plugins = [plugin('a', {kinds: ['text'], draw}), plugin('b', {types: ['Lyric'], kinds: ['text', 'image'], draw}), plugin('c')];
    expect(painterFor(plugins, obj({text: '你好'}))?.name).toBe('a');
    expect(painterFor(plugins, obj({type: 'Lyric', text: '你好'}))?.name).toBe('b');
    expect(painterFor(plugins, obj({media: {kind: 'image'} as Obj['media']}))?.name).toBe('b');
    expect(painterFor(plugins, obj({media: {kind: 'audio'} as Obj['media']}))).toBeNull();
  });

  it('插件列表换了（开关、去掉）就重新查表；没有插件时不查', () => {
    const one = [plugin('a', {kinds: ['text'], draw})];
    expect(painterFor(one, obj({text: 'x'}))?.name).toBe('a');
    expect(painterFor([plugin('z')], obj({text: 'x'}))).toBeNull();
    expect(painterFor([], obj({text: 'x'}))).toBeNull();
  });
});

describe('样板插件「字数」', () => {
  it('数字数不算空白；每秒几个字只在单位是秒、对象有长度时算', () => {
    expect(count(' 你 好\n世界 ')).toBe(4);
    expect(count(null)).toBe(0);
    expect(perSecond(obj({text: '一二三四', begin: 1, end: 3}), true)).toBe(2);
    expect(perSecond(obj({text: '一二三四', begin: 1, end: 3}), false)).toBeNull();
    expect(perSecond(obj({text: '一二三四', begin: 1, end: 1}), true)).toBeNull();
  });

  it('照接口给出侧栏、对象详情、格子；格子按每秒字数画一条，单位不是秒时不画', () => {
    const styles: string[] = [];
    const host = {React, addStyle: (css: string) => styles.push(css), util: {kindOf, isSec, fmt}} as unknown as PluginHost;
    const p = example(host);
    expect([p.label, p.handles, typeof p.side, typeof p.objectDetail, p.block?.kinds]).toEqual(['字数', ['text'], 'function', 'function', ['text']]);
    expect(styles).toHaveLength(1);
    const rects: number[][] = [];
    const ctx = {fillStyle: '', fillRect: (...a: number[]) => rects.push(a)} as unknown as CanvasRenderingContext2D;
    const layer = {} as never;
    p.block!.draw(ctx, obj({text: '一'.repeat(FAST * 2), begin: 0, end: 4}), {width: 200, height: 40, unit: '秒', layer});   // 每秒 4 个：半条
    p.block!.draw(ctx, obj({text: '一'.repeat(FAST * 4), begin: 0, end: 1}), {width: 200, height: 40, unit: '秒', layer});   // 太快：整条
    p.block!.draw(ctx, obj({text: '一二三', begin: 0, end: 48}), {width: 200, height: 40, unit: '帧', layer});              // 不是秒：不画
    expect(rects).toEqual([[0, 34, 100, 6], [0, 34, 200, 6]]);
  });
});
