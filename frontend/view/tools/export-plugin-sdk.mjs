// 从实际 host.ts 生成并收集可达的 .d.ts；插件仓库固定引用该快照，不依赖宿主源码。
import ts from 'typescript';
import {mkdtempSync, readFileSync, mkdirSync, writeFileSync, copyFileSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {dirname, join, relative, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = join(frontend, 'src');
const hostText = readFileSync(join(source, 'plugin/host.ts'), 'utf8');
const api = Number(/PLUGIN_API = (\d+)/.exec(hostText)?.[1]);
if (!api) throw new Error('host.api 未声明');
const sdkRoot = resolve(frontend, '../../src/layerweave/tool/builtin/view/sdk');
const target = resolve(sdkRoot, `host-api-${api}`);
if (!target.startsWith(sdkRoot + '/') && !target.startsWith(sdkRoot + '\\')) throw new Error('SDK 目标越界');
const temporary = mkdtempSync(join(tmpdir(), 'layerweave-sdk-'));
try {
  const configFile = ts.readConfigFile(join(frontend, 'tsconfig.json'), ts.sys.readFile);
  const config = ts.parseJsonConfigFileContent(configFile.config, ts.sys, frontend);
  const program = ts.createProgram([join(source, 'plugin/host.ts')], {...config.options, noEmit: false, allowJs: false, checkJs: false,
    declaration: true, emitDeclarationOnly: true, rootDir: source, outDir: temporary});
  const result = program.emit();
  const errors = [...ts.getPreEmitDiagnostics(program), ...result.diagnostics].filter((d) => d.category === ts.DiagnosticCategory.Error);
  if (errors.length) throw new Error(ts.formatDiagnosticsWithColorAndContext(errors, {getCurrentDirectory: () => frontend, getCanonicalFileName: (f) => f, getNewLine: () => '\n'}));
  const selected = new Set();
  const collect = (path) => {
    if (selected.has(path)) return;
    selected.add(path);
    const content = readFileSync(path, 'utf8');
    for (const match of content.matchAll(/(?:from\s+|import\s*\()['"](\.[^'"]+)['"]/g)) {
      let next = resolve(dirname(path), match[1]);
      if (!next.endsWith('.d.ts')) next += '.d.ts';
      collect(next);
    }
  };
  collect(join(temporary, 'plugin/host.d.ts'));
  collect(join(temporary, 'model/model.d.ts'));
  collect(join(temporary, 'types.d.ts'));
  rmSync(target, {recursive: true, force: true}); // 此目录仅含本脚本生成的接口快照。
  for (const path of selected) {
    const destination = join(target, relative(temporary, path));
    mkdirSync(dirname(destination), {recursive: true}); copyFileSync(path, destination);
  }
  writeFileSync(join(target, 'index.d.ts'), "export type {PluginHost, ViewSnapshot, ViewPlugin, PluginFactory} from './plugin/host';\nexport type {Model, ObjWithLayer, Item, Track, Segment} from './model/model';\nexport type {Board, Obj, Layer, Root, ProjectData} from './types';\n");
  const version = JSON.parse(readFileSync(join(frontend, 'package.json'), 'utf8')).version;
  writeFileSync(join(target, 'snapshot.json'), JSON.stringify({host_api: api, view_version: version, entry: 'index.d.ts', files: selected.size + 1}, null, 2) + '\n');
  console.log(`host.api ${api}: ${selected.size + 1} declaration files -> ${target}`);
} finally {
  if (!resolve(temporary).startsWith(resolve(tmpdir()))) throw new Error('临时目录越界');
  rmSync(temporary, {recursive: true, force: true});
}
