// Native credential files stay inside the owner's isolated Docker runtime.
// No OAuth client, token exchange, credential output, or host-profile import.
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { pathToFileURL } from 'node:url';

const files = {
  'codex-cli': [{ name: 'codex/auth.json', refresh: true }],
  'claude-cli': [
    { name: 'claude/.credentials.json', refresh: true },
    // Login account metadata only. Never export per-conversation CLI preferences.
    { name: 'claude/.claude.json', refresh: false },
    { name: 'home/.claude.json', refresh: false },
  ],
  'grok-cli': [{ name: 'grok/auth.json', refresh: true }],
};
const binaries = { 'codex-cli': 'codex', 'claude-cli': 'claude', 'grok-cli': 'grok' };

function location(root, relative, create = false) {
  if (!fs.lstatSync(root).isDirectory()) throw new Error('Invalid root');
  let current = root;
  const parts = relative.split('/');
  for (const part of parts.slice(0, -1)) {
    current = path.join(current, part);
    if (create && !fs.existsSync(current)) fs.mkdirSync(current, { mode: 0o700 });
    if (!fs.lstatSync(current).isDirectory()) throw new Error('Invalid directory');
  }
  return path.join(current, parts.at(-1));
}

function read(root, relative) {
  let descriptor;
  try {
    const target = location(root, relative);
    descriptor = fs.openSync(target, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
    const info = fs.fstatSync(descriptor);
    if (!info.isFile() || info.nlink !== 1 || info.size > 262144 || info.size === 0)
      throw new Error('Invalid native credential file');
    return fs.readFileSync(descriptor);
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  } finally {
    if (descriptor !== undefined) fs.closeSync(descriptor);
  }
}

function remove(root, relative) {
  try { fs.unlinkSync(location(root, relative)); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
}

function write(root, relative, content) {
  const target = location(root, relative, true);
  const temporary = target + '.' + randomUUID();
  let descriptor;
  try {
    descriptor = fs.openSync(temporary, 'wx', 0o600);
    fs.writeFileSync(descriptor, content);
    fs.fsyncSync(descriptor);
    fs.closeSync(descriptor);
    descriptor = undefined;
    fs.renameSync(temporary, target);
    const directory = fs.openSync(path.dirname(target), fs.constants.O_RDONLY);
    try { fs.fsyncSync(directory); } finally { fs.closeSync(directory); }
  } finally {
    if (descriptor !== undefined) fs.closeSync(descriptor);
    try { fs.unlinkSync(temporary); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
}

export function present(kind, accountRoot = '/account') {
  if (!files[kind]) throw new Error('Unsupported CLI');
  return read(accountRoot, files[kind][0].name) !== null;
}

export async function execute(kind, command, accountRoot = '/account', stateRoot = '/state') {
  if (!files[kind] || command[0] !== binaries[kind]) throw new Error('Unsupported CLI command');
  // A stale conversation copy must never substitute for the current account login.
  for (const file of files[kind]) remove(stateRoot, file.name);
  if (!present(kind, accountRoot)) throw new Error('Native login missing');
  let child;
  let timer;
  let stopping = false;
  function stop() {
    stopping = true;
    if (!child?.pid) return;
    try { process.kill(-child.pid, 'SIGTERM'); } catch (error) { if (error.code !== 'ESRCH') throw error; }
    timer = setTimeout(() => {
      try { process.kill(-child.pid, 'SIGKILL'); } catch (error) { if (error.code !== 'ESRCH') throw error; }
    }, 2500);
  }
  try {
    for (const file of files[kind]) {
      const content = read(accountRoot, file.name);
      if (content !== null) write(stateRoot, file.name, content);
    }
    const env = { ...process.env };
    for (const key of ['OPENAI_API_KEY', 'CODEX_API_KEY', 'XAI_API_KEY', 'ANTHROPIC_API_KEY',
      'ANTHROPIC_AUTH_TOKEN', 'CLAUDE_CODE_OAUTH_TOKEN', 'CODEX_ACCESS_TOKEN']) delete env[key];
    Object.assign(env, {
      HOME: path.join(stateRoot, 'home'), CODEX_HOME: path.join(stateRoot, 'codex'),
      CLAUDE_CONFIG_DIR: path.join(stateRoot, 'claude'), GROK_HOME: path.join(stateRoot, 'grok'),
    });
    child = spawn(command[0], command.slice(1), { stdio: 'inherit', env, detached: true });
    process.on('SIGTERM', stop);
    process.on('SIGINT', stop);
    return await new Promise((resolve, reject) => {
      child.once('error', reject);
      child.once('exit', (code) => resolve(stopping ? 143 : (code ?? 1)));
    });
  } finally {
    clearTimeout(timer);
    process.off('SIGTERM', stop);
    process.off('SIGINT', stop);
    if (child?.pid) {
      try { process.kill(-child.pid, 'SIGKILL'); } catch (error) { if (error.code !== 'ESRCH') throw error; }
    }
    try {
      // Persist native refresh even after a failed inference, before releasing the account lease.
      if (child) {
        for (const file of files[kind].filter((file) => file.refresh)) {
          const content = read(stateRoot, file.name);
          if (content !== null) write(accountRoot, file.name, content);
          else remove(accountRoot, file.name);
        }
      }
    } finally {
      for (const file of files[kind]) remove(stateRoot, file.name);
    }
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const [action, kind, ...command] = process.argv.slice(2);
    if (action === 'status') process.stdout.write(present(kind) ? 'present' : 'missing');
    else if (action === 'run') process.exitCode = await execute(kind, command);
    else throw new Error('Unsupported account action');
  } catch {
    // Never expose credential contents, paths, or raw exceptions.
    process.stderr.write('Native CLI account storage failed; use local cli-auth login to recover.\n');
    process.exitCode = 78;
  }
}
