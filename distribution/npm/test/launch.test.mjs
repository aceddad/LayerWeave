import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { cacheRoot, commandArgs, download, forward, prepareUv } from '../lib/launch.mjs';

test('Python and npm releases pin the same runtime version, with MCP optional', async () => {
  const init = await readFile(new URL('../../../src/layerweave/__init__.py', import.meta.url), 'utf8');
  const version = /__version__ = "([^"]+)"/.exec(init)[1];
  const base = commandArgs(['demo'], {});
  assert.ok(base.includes(`layerweave==${version}`));
  assert.ok(commandArgs(['mcp', '--list'], {}).includes(`layerweave[mcp]==${version}`));
  assert.deepEqual(base.slice(-2), ['layerweave', 'demo']);
});

test('arguments and explicit local package sources remain literal', () => {
  const args = ['view', 'D:\\中文 folder\\a;test.sqlite3', '--no-browser'];
  const source = 'D:\\package folder\\release.whl';
  const actual = commandArgs(args, { LAYERWEAVE_PYTHON_PACKAGE: source });
  assert.ok(actual.includes(source));
  assert.deepEqual(actual.slice(-args.length), args);
});

test('cache is separate from the current project directory', () => {
  assert.equal(cacheRoot({ LAYERWEAVE_CACHE_DIR: 'test-cache' }), path.resolve('test-cache'));
  assert.ok(cacheRoot({ LOCALAPPDATA: 'D:\\Local' }).includes('LayerWeave'));
});

test('invalid explicit uv path produces a useful error', async () => {
  await assert.rejects(prepareUv({ LAYERWEAVE_UV: path.join(tmpdir(), 'does-not-exist-uv.exe') }), /LAYERWEAVE_UV/);
});

test('downloader checks HTTP status and checksum before accepting bytes', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'lw-npm-test-'));
  const payload = Buffer.from('synthetic uv package');
  const server = createServer((request, response) => {
    response.statusCode = request.url === '/missing' ? 404 : 200;
    response.end(payload);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const url = `http://127.0.0.1:${server.address().port}`;
  try {
    const output = path.join(root, 'download.zip');
    await assert.rejects(download(url + '/missing', output, ''), /404/);
    await assert.rejects(download(url, output, 'wrong'), /checksum mismatch/);
    await download(url, output, createHash('sha256').update(payload).digest('hex'));
    assert.deepEqual(await readFile(output), payload);
  } finally {
    await new Promise(resolve => server.close(resolve));
    await rm(root, { recursive: true, force: true });
  }
});

test('child exit status and argument boundaries survive forwarding', async () => {
  const literal = '中文 space;$(not-a-command)';
  const code = await forward(process.execPath, ['-e', `process.exit(process.argv[1] === ${JSON.stringify(literal)} ? 7 : 9)`, literal]);
  assert.equal(code, 7);
});
