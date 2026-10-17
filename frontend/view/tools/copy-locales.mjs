import {mkdir, copyFile} from 'node:fs/promises';
const target = new URL('../../../src/layerweave/tool/builtin/view/locales/', import.meta.url);
await mkdir(target, {recursive: true});
for (const lang of ['zh', 'en']) await copyFile(new URL(`../src/i18n/${lang}.json`, import.meta.url), new URL(`${lang}.json`, target));
