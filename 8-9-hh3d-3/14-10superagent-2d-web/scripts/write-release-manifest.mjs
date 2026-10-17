import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const sourceRoot = path.join(root, 'src');
const files = [];
function walk(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) walk(absolute);
    else if (entry.isFile()) {
      const bytes = fs.readFileSync(absolute);
      files.push({ path: path.relative(root, absolute).replaceAll('\\', '/'), sha256: crypto.createHash('sha256').update(bytes).digest('hex'), bytes: bytes.length });
    }
  }
}
walk(sourceRoot);
const manifest = { schema: 1, product: 'superagent-2d-web', generatedAt: new Date().toISOString(), git: process.env.GITHUB_SHA ?? 'local', source: files.sort((a, b) => a.path.localeCompare(b.path)), build: { vite: true, static: true } };
fs.writeFileSync(path.join(root, 'dist', 'release-manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`);
console.log(`RELEASE_MANIFEST_WRITTEN source_files=${files.length}`);
