import { spawn, spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { createReadStream, createWriteStream } from 'node:fs';
import { access, mkdir, mkdtemp, readFile, rename, rm } from 'node:fs/promises';
import { homedir } from 'node:os';
import path from 'node:path';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';

const metadata = JSON.parse(await readFile(new URL('../package.json', import.meta.url), 'utf8'));
const runtime = JSON.parse(await readFile(new URL('../runtime.json', import.meta.url), 'utf8'));

export function cacheRoot(env = process.env) {
  return path.resolve(env.LAYERWEAVE_CACHE_DIR || path.join(env.LOCALAPPDATA || path.join(homedir(), 'AppData', 'Local'), 'LayerWeave', 'cache'));
}

async function exists(file) {
  try { await access(file); return true; } catch { return false; }
}

export async function download(url, output, sha256) {
  if (process.platform === 'win32' && url.startsWith('https:')) {
    // Use the Windows proxy and certificate settings; do not disable TLS checks.
    const powershell = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe');
    await new Promise((resolve, reject) => {
      const child = spawn(powershell, ['-NoProfile', '-NonInteractive', '-Command',
        "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); Invoke-WebRequest -UseBasicParsing -TimeoutSec 120 -Uri $env:LAYERWEAVE_UV_URL -OutFile $env:LAYERWEAVE_UV_OUTPUT"],
      { env: { ...process.env, LAYERWEAVE_UV_URL: url, LAYERWEAVE_UV_OUTPUT: output }, stdio: ['ignore', 'ignore', 'pipe'], windowsHide: true });
      let error = '';
      child.stderr.setEncoding('utf8');
      child.stderr.on('data', chunk => { error += chunk; });
      child.once('error', reject);
      child.once('close', code => code === 0 ? resolve() : reject(new Error(`uv download failed: ${error.trim()}`)));
    });
  } else {
    const response = await fetch(url, { signal: AbortSignal.timeout(120_000) });
    if (!response.ok) throw new Error(`Download failed: HTTP ${response.status} (${url})`);
    await pipeline(Readable.fromWeb(response.body), createWriteStream(output));
  }
  const hash = createHash('sha256');
  for await (const chunk of createReadStream(output)) hash.update(chunk);
  if (hash.digest('hex') !== sha256) throw new Error('uv archive checksum mismatch; retry the command.');
}

function usableUv(command) {
  const result = spawnSync(command, ['--version'], { encoding: 'utf8', windowsHide: true, timeout: 10_000 });
  const version = /^uv (\d+)\.(\d+)\./.exec(result.stdout || '');
  return result.status === 0 && version && (Number(version[1]) > 0 || Number(version[2]) >= 9);
}

export async function prepareUv(env = process.env) {
  if (env.LAYERWEAVE_UV) {
    if (!usableUv(env.LAYERWEAVE_UV)) throw new Error('LAYERWEAVE_UV must point to uv >= 0.9.');
    return env.LAYERWEAVE_UV;
  }
  if (usableUv('uv')) return 'uv';
  const spec = runtime.targets[`${process.platform}-${process.arch}`];
  if (!spec) throw new Error('This npm preview supports Windows x64. Use the Python/uv distribution on other platforms.');
  const parent = path.join(cacheRoot(env), 'runtime');
  const directory = path.join(parent, `uv-${runtime.version}`);
  const executable = path.join(directory, 'uv.exe');
  if (await exists(executable)) return executable;
  await mkdir(parent, { recursive: true });
  const staging = await mkdtemp(path.join(parent, '.uv-'));
  try {
    console.error(`LayerWeave: preparing uv ${runtime.version} in ${directory}`);
    const archive = path.join(staging, 'uv.zip');
    await download(spec.url, archive, spec.sha256);
    const extracted = path.join(staging, 'unpacked');
    const powershell = path.join(env.SystemRoot || 'C:\\Windows', 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe');
    const result = spawnSync(powershell, ['-NoProfile', '-NonInteractive', '-Command',
      "$ErrorActionPreference='Stop'; Expand-Archive -LiteralPath $env:LAYERWEAVE_UV_ARCHIVE -DestinationPath $env:LAYERWEAVE_UV_EXTRACT"],
    { env: { ...env, LAYERWEAVE_UV_ARCHIVE: archive, LAYERWEAVE_UV_EXTRACT: extracted }, encoding: 'utf8', windowsHide: true });
    if (result.status !== 0) throw new Error(`Cannot extract uv: ${result.stderr || result.error?.message}`);
    if (!(await exists(path.join(extracted, 'uv.exe')))) throw new Error('Downloaded uv archive is missing uv.exe.');
    try { await rename(extracted, directory); }
    catch (error) { if (!(await exists(executable))) throw error; }
    return executable;
  } finally {
    // Only remove the unique staging directory created by this invocation.
    await rm(staging, { recursive: true, force: true });
  }
}

export function commandArgs(argv, env = process.env) {
  const extra = argv[0] === 'mcp' ? '[mcp]' : '';
  const requirement = env.LAYERWEAVE_PYTHON_PACKAGE || `layerweave${extra}==${metadata.layerweave.pythonVersion}`;
  return ['tool', 'run', '--no-config', '--managed-python', '--python', '3.11', '--from', requirement, 'layerweave', ...argv];
}

export function forward(command, args, env = process.env) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { env, stdio: 'inherit', windowsHide: true });
    let stopping;
    let timer;
    const handlers = new Map();
    const cleanup = () => {
      clearTimeout(timer);
      for (const [signal, handler] of handlers) process.removeListener(signal, handler);
    };
    for (const signal of ['SIGINT', 'SIGTERM']) {
      const handler = () => {
        if (stopping) return;
        stopping = signal;
        if (process.platform !== 'win32') child.kill(signal);
        // Windows console Ctrl+C reaches uv and Python too. Allow their normal
        // shutdown first; terminate only this child tree if it does not exit.
        timer = setTimeout(() => {
          if (process.platform === 'win32' && child.pid) {
            spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore', windowsHide: true });
          } else child.kill('SIGKILL');
        }, 5000).unref();
      };
      handlers.set(signal, handler);
      process.on(signal, handler);
    }
    child.once('error', error => { cleanup(); reject(error); });
    child.once('close', (code, signal) => {
      cleanup();
      resolve(stopping === 'SIGINT' ? 130 : stopping === 'SIGTERM' ? 143 : code ?? (signal ? 1 : 0));
    });
  });
}

export async function main(argv) {
  const uv = await prepareUv();
  const root = cacheRoot();
  const env = { ...process.env, PYTHONUTF8: '1',
    UV_CACHE_DIR: process.env.UV_CACHE_DIR || path.join(root, 'uv'),
    UV_PYTHON_INSTALL_DIR: process.env.UV_PYTHON_INSTALL_DIR || path.join(root, 'python') };
  return forward(uv, commandArgs(argv), env);
}
