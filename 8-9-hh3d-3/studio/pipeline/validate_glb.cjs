// Internal fixed-slot Khronos stage. Host first performs independent GLB/PNG
// admission and hash/ownership checks. This script is not arbitrary-file intake.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

function need(value, code) {
  if (!value) throw new Error(code);
}
function sha(bytes) {
  return crypto.createHash('sha256').update(bytes).digest('hex');
}
function readBounded(filename, limit) {
  const entry = fs.lstatSync(filename);
  need(entry.isFile() && !entry.isSymbolicLink() && entry.nlink === 1, 'REGULAR_INPUT_REQUIRED');
  const fd = fs.openSync(filename, 'r');
  try {
    const before = fs.fstatSync(fd);
    need(before.dev === entry.dev && before.ino === entry.ino && before.nlink === 1 &&
         before.isFile() && before.size >= 0 && before.size <= limit, 'INPUT_BOUND_OR_IDENTITY');
    const data = Buffer.alloc(before.size);
    let offset = 0;
    while (offset < data.length) {
      const count = fs.readSync(fd, data, offset, data.length - offset, offset);
      need(count > 0, 'INPUT_SHORT_READ');
      offset += count;
    }
    const after = fs.fstatSync(fd);
    need(after.dev === before.dev && after.ino === before.ino && after.size === before.size &&
         after.mtimeMs === before.mtimeMs && after.nlink === 1, 'INPUT_CHANGED');
    return data;
  } finally {
    fs.closeSync(fd);
  }
}

async function main() {
  need(process.argv.length === 3 && process.version === 'v24.10.0', 'RUNTIME_OR_ARGS');
  const root = path.resolve(process.argv[2]);
  need(fs.realpathSync(root).toLowerCase() === root.toLowerCase(), 'STAGE_ROOT_ALIAS');
  const lockPath = path.join(root, 'gltf-validator.lock.json');
  const lockBytes = readBounded(lockPath, 16384);
  const lock = JSON.parse(lockBytes.toString('utf8'));
  need(lock.name === 'gltf-validator' && lock.version === '2.0.0-dev.3.10' &&
       Object.keys(lock.files).length === 9, 'DEPENDENCY_LOCK');
  for (const [relative, expected] of Object.entries(lock.files)) {
    need(/^package\/[a-zA-Z0-9_.-]+$/.test(relative) && /^[0-9a-f]{64}$/.test(expected), 'DEPENDENCY_PATH');
    const bytes = readBounded(path.join(root, 'dependency', relative), 1048576);
    need(sha(bytes) === expected, 'DEPENDENCY_HASH');
  }
  const bytes = readBounded(path.join(root, 'fixture.glb'), 1048576);
  const expected = JSON.parse(readBounded(path.join(root, 'admission.json'), 4096).toString('utf8'));
  need(expected.schema === 'HH-GT05-VALIDATOR-INPUT-1' && expected.artifact_sha256 === sha(bytes), 'INPUT_BINDING');
  const validator = require(path.join(root, 'dependency', 'package', 'index.js'));
  need(validator.version() === lock.version, 'VALIDATOR_VERSION');
  let externalRequested = false;
  const result = await validator.validateBytes(new Uint8Array(bytes), {
    uri: 'fixture.glb', format: 'glb', writeTimestamp: false, maxIssues: 64,
    externalResourceFunction: () => {
      externalRequested = true;
      return Promise.reject(new Error('EXTERNAL_RESOURCE_FORBIDDEN'));
    },
  });
  const report = {schema: 'HH-GT05-KHRONOS-1', artifact_sha256: sha(bytes),
    validator_version: validator.version(), dependency_lock_sha256: sha(lockBytes),
    external_resource_requested: externalRequested, formal_acceptance: false, result};
  const encoded = JSON.stringify(report);
  need(Buffer.byteLength(encoded) <= 262144, 'REPORT_CAP');
  fs.writeFileSync(path.join(root, 'validator.json'), encoded + '\n', {flag: 'wx'});
  need(!externalRequested && result.issues && result.issues.numErrors === 0 &&
       result.issues.numWarnings === 0 && result.issues.truncated === false, 'KHRONOS_ISSUES');
  process.stdout.write('GT05_KHRONOS_COMPLETE ' + JSON.stringify({artifact_sha256: sha(bytes),
    report_sha256: sha(Buffer.from(encoded + '\n'))}) + '\n');
}
main().catch(error => {
  const code = error instanceof Error && /^[A-Z0-9_]+$/.test(error.message) ? error.message : 'VALIDATOR_FAILED';
  process.stderr.write(code + '\n');
  process.exitCode = 17;
});
