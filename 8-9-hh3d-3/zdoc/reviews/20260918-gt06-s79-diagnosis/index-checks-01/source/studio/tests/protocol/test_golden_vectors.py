from __future__ import annotations

import hashlib
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))
from studio.protocol import canonical_json

SEED = 8785
NODE_CONSUMER = r"""
const fs = require('node:fs'), crypto = require('node:crypto');
const data = JSON.parse(fs.readFileSync(process.argv[1], 'utf8'));
function canon(value) {
  if (Array.isArray(value)) return '[' + value.map(canon).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.keys(value).sort()
    .map(key => JSON.stringify(key) + ':' + canon(value[key])).join(',') + '}';
  return JSON.stringify(value);
}
function row(id, value) {
  const canonical = canon(value), bytes = Buffer.from(canonical, 'utf8');
  return {id, ok: true, canonical, utf8_hex: bytes.toString('hex'),
    sha256: 'sha256:' + crypto.createHash('sha256').update(bytes).digest('hex')};
}
const rows = [];
for (const entry of data.cases) {
  rows.push(row(entry.id, entry.input));
  if (entry.request_body) rows.push(row(entry.id + ':request', entry.request_body));
}
for (const entry of data.binary64) {
  rows.push(row(entry.id, Buffer.from(entry.bits, 'hex').readDoubleBE()));
}
process.stdout.write(JSON.stringify({rows}));
"""


def _expected_row(identifier: str, text: str) -> dict:
    encoded = text.encode('utf-8')
    return {'id': identifier, 'ok': True, 'canonical': text,
            'utf8_hex': encoded.hex(),
            'sha256': 'sha256:' + hashlib.sha256(encoded).hexdigest()}


def _binary_float(bits: str) -> float:
    return struct.unpack('>d', bytes.fromhex(bits))[0]


def _tagged_fixture(value):
    """Lossless values for Godot; never include the expected canonical result.

    Godot String cannot hold U+0000. Scalars/keys use codepoints, and floats
    use IEEE754 bytes so testing the serializer does not test JSON.parse.
    """
    if value is None:
        return ['null']
    if isinstance(value, bool):
        return ['boolean', value]
    if isinstance(value, int):
        return ['integer', str(value)]
    if isinstance(value, float):
        return ['binary64', struct.pack('>d', value).hex()]
    if isinstance(value, str):
        return ['string', [ord(char) for char in value]]
    if isinstance(value, list):
        return ['array', [_tagged_fixture(child) for child in value]]
    if isinstance(value, dict):
        return ['object', [[_tagged_fixture(key), _tagged_fixture(child)] for key, child in value.items()]]
    raise TypeError(type(value))


def _godot_leftovers(project: Path) -> list[int]:
    if os.name != 'nt':
        raise unittest.SkipTest('SKIP_ENVIRONMENT: locked Godot platform is Windows')
    quoted = str(project).replace("'", "''")
    script = ("$p='" + quoted + "'; @((Get-CimInstance Win32_Process | "
              "Where-Object { $_.Name -match 'Godot' -and $_.CommandLine -and "
              "$_.CommandLine.Contains($p) }).ProcessId) | ConvertTo-Json -Compress")
    result = subprocess.run(['powershell', '-NoProfile', '-Command', script],
                            capture_output=True, text=True, timeout=15, check=True)
    parsed = json.loads(result.stdout) if result.stdout.strip() else []
    return parsed if isinstance(parsed, list) else [parsed]


class GoldenVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / 'protocol/vectors/jcs-vectors.json').read_text(encoding='utf-8'))
        locked = json.loads((ROOT / 'protocol/vectors/jcs-binary64-vectors.json').read_text(encoding='utf-8'))
        cls.data['binary64'] = [dict(entry, id='rfc8785:' + entry['bits']) for entry in locked['cases']]
        # Independent random IEEE754 samples, including both signs and exponents.
        rng = random.Random(SEED)
        for index in range(256):
            bits = f'{rng.getrandbits(64):016x}'
            while not math.isfinite(_binary_float(bits)):
                bits = f'{rng.getrandbits(64):016x}'
            cls.data['binary64'].append({'id': f'seed-{SEED}:{index}', 'bits': bits,
                                        'canonical': canonical_json(_binary_float(bits))})
        # Explicit unequal-ULP power-of-two and subnormal/normal transitions.
        for base in (0x0010000000000000, 0x3ff0000000000000, 0x4000000000000000):
            for delta in (-1, 0, 1):
                bits = f'{base + delta:016x}'
                cls.data['binary64'].append({'id': 'boundary:' + bits, 'bits': bits,
                                            'canonical': canonical_json(_binary_float(bits))})
        # Every finite positive power of two exercises the asymmetric interval,
        # including all 52 powers in the subnormal domain.
        powers = [exponent << 52 for exponent in range(1, 2047)] + [1 << bit for bit in range(52)]
        for word in powers:
            bits = f'{word:016x}'
            cls.data['binary64'].append({'id': 'power-of-two:' + bits, 'bits': bits,
                                        'canonical': canonical_json(_binary_float(bits))})
        cls.expected = []
        for case in cls.data['cases']:
            cls.expected.append(_expected_row(case['id'], case['canonical']))
            if 'request_body' in case:
                cls.expected.append(_expected_row(case['id'] + ':request', case['request_body_canonical']))
        cls.expected.extend(_expected_row(case['id'], case['canonical']) for case in cls.data['binary64'])

    def test_python_vectors(self):
        for case in self.data['cases']:
            with self.subTest(case=case['id']):
                self.assertEqual(canonical_json(case['input']), case['canonical'])
                if 'payload_sha256' in case:
                    self.assertEqual(_expected_row('', case['canonical'])['sha256'], case['payload_sha256'])
                    self.assertEqual(canonical_json(case['request_body']), case['request_body_canonical'])
                    self.assertEqual(_expected_row('', case['request_body_canonical'])['sha256'], case['request_digest'])
        for case in self.data['binary64']:
            with self.subTest(case=case['id']):
                self.assertEqual(canonical_json(_binary_float(case['bits'])), case['canonical'])

    def test_node_consumer_when_available(self):
        executable = shutil.which('node')
        if not executable:
            self.skipTest('SKIP_ENVIRONMENT: Node runtime unavailable')
        version = subprocess.run([executable, '--version'], capture_output=True,
                                 text=True, encoding='utf-8', timeout=15, check=True)
        with tempfile.TemporaryDirectory(prefix='hh-gt02-node-') as directory:
            vectors = Path(directory) / 'vectors.json'
            vectors.write_text(json.dumps(self.data, ensure_ascii=False), encoding='utf-8')
            # A timeout is a failure, never an environment skip.
            result = subprocess.run([executable, '-e', NODE_CONSUMER, str(vectors)],
                                    capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(result.stdout)['rows']
        evidence = os.environ.get('HH_GT02_GOLDEN_EVIDENCE_DIR')
        if evidence:
            output = Path(evidence)
            output.mkdir(parents=True, exist_ok=True)
            record = {'format': 'hh-gt02-node-golden-host-v1', 'seed': SEED,
                      'scope': 'serializer_conformance_only',
                      'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                      'run_id': 'GT02-JCS-' + Path(directory).name,
                      'command_id': 'cmd.' + Path(directory).name,
                      'version': version.stdout.strip(), 'host_exit': result.returncode,
                      'executable_sha256': hashlib.sha256(Path(executable).read_bytes()).hexdigest(),
                      'consumer_sha256': hashlib.sha256(NODE_CONSUMER.encode()).hexdigest(),
                      'test_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      'stdout_raw_sha256': hashlib.sha256(result.stdout.encode('utf-8')).hexdigest(),
                      'rows': rows, 'stderr': result.stderr}
            (output / (Path(directory).name + '.json')).write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        self.assertEqual(rows, self.expected)

    def test_godot_consumer_when_available(self):
        lock = json.loads((ROOT / 'toolchain.lock.json').read_text(encoding='utf-8'))['godot']
        local_file = ROOT / '.local/toolchain.local.json'
        local = json.loads(local_file.read_text(encoding='utf-8')) if local_file.exists() else {}
        configured = os.environ.get('HH_STUDIO_GODOT_CONSOLE') or local.get('godot_console')
        executable = Path(configured) if configured else ROOT / '.local/tooling' / ('godot-' + lock['version']) / lock['console_executable']
        if not executable.is_file():
            self.skipTest('SKIP_ENVIRONMENT: pinned Godot console unavailable')
        self.assertEqual(executable.name, lock['console_executable'])
        self.assertEqual(hashlib.sha256(executable.read_bytes()).hexdigest(), lock['console_sha256'])
        companion = executable.with_name(lock['gui_executable'])
        self.assertTrue(companion.is_file(), 'locked Godot GUI companion missing')
        self.assertEqual(hashlib.sha256(companion.read_bytes()).hexdigest(), lock['gui_sha256'])
        version = subprocess.run([str(executable), '--version'], capture_output=True,
                                 text=True, encoding='utf-8', timeout=15, check=True)
        self.assertEqual(version.stdout.strip(), lock['observed_version'])
        with tempfile.TemporaryDirectory(prefix='hh-gt02-godot-') as directory:
            project = Path(directory).resolve()
            (project / 'project.godot').write_text('config_version=5\n[application]\nconfig/name="GT02 JCS"\n', encoding='utf-8')
            for name in ('jcs_godot.gd', 'golden_consumer.gd'):
                shutil.copyfile(ROOT / 'protocol' / name, project / name)
            fixture = {'cases': [], 'binary64': [{'id': case['id'], 'bits': case['bits']} for case in self.data['binary64']]}
            for case in self.data['cases']:
                entry = {'id': case['id'], 'input': _tagged_fixture(case['input'])}
                if 'request_body' in case:
                    entry['request_body'] = _tagged_fixture(case['request_body'])
                fixture['cases'].append(entry)
            (project / 'vectors.json').write_text(json.dumps(fixture), encoding='utf-8')
            frozen = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in project.iterdir()}
            before = _godot_leftovers(project)
            self.assertEqual(before, [], 'existing Godot worker owns the isolated path')
            command = [str(executable), '--headless', '--path', str(project), '--script', 'res://golden_consumer.gd']
            started = time.monotonic()
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                stdout, stderr = process.communicate(timeout=45)
            except subprocess.TimeoutExpired:
                # This fixed serializer has no process-spawning operation.
                # Kill through the retained Popen handle, never a reusable PID.
                # The aggregate runner additionally owns all descendants in its
                # Windows Job Object when this test is used as gate evidence.
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=10)
                self.fail('Godot timeout: killed run is not PASS')
            after = _godot_leftovers(project)
            observed = {name: hashlib.sha256((project / name).read_bytes()).hexdigest() for name in frozen}
            record = {'format': 'hh-gt02-golden-host-v1', 'seed': SEED,
                      'scope': 'serializer_conformance_only', 'raw_wire_parser_conformance': False,
                      'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                      'run_id': 'GT02-JCS-' + project.name, 'command_id': 'cmd.' + project.name,
                      'version': version.stdout.strip(), 'host_exit': process.returncode,
                      'console_sha256': lock['console_sha256'], 'gui_sha256': lock['gui_sha256'],
                      'test_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      'repro': 'python -m unittest discover -s 8-9-hh3d-3/studio/tests/protocol -p test_golden_vectors.py -v',
                      'elapsed_seconds': time.monotonic() - started,
                      'leftover_before': before, 'leftover_after': after, 'source_hashes': frozen,
                      'source_unchanged': frozen == observed, 'stdout': stdout, 'stderr': stderr}
            evidence = os.environ.get('HH_GT02_GOLDEN_EVIDENCE_DIR')
            if evidence:
                output = Path(evidence)
                output.mkdir(parents=True, exist_ok=True)
                (output / (project.name + '.json')).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
            self.assertEqual(process.returncode, 0, stdout + stderr)
            self.assertEqual(after, [], 'Godot process remained after real host wait')
            self.assertEqual(frozen, observed, 'frozen snapshot changed during Godot run')
            diagnostics = '\n'.join(line for line in stdout.split('\n') if not line.startswith('HH_GT02_JCS ')) + stderr
            self.assertNotRegex(diagnostics, r'(?i)\b(?:warning|error|leaked)\b')
            lines = [line.removeprefix('HH_GT02_JCS ') for line in stdout.split('\n') if line.startswith('HH_GT02_JCS ')]
            self.assertEqual(len(lines), 1, stdout + stderr)
            result = json.loads(lines[0])
            self.assertEqual(len(result['rows']), len(self.expected))
            for actual, expected in zip(result['rows'], self.expected):
                with self.subTest(case=expected['id']):
                    self.assertEqual(actual, expected)
            expected_rejects = {'nan': 'INVALID_NUMBER', 'infinity': 'INVALID_NUMBER',
                                'negative_infinity': 'INVALID_NUMBER',
                                'unsafe_integer': 'INTEGER_REQUIRES_DECIMAL_STRING',
                                'surrogate': 'INVALID_UNICODE', 'invalid_scalar': 'INVALID_UNICODE',
                                'invalid_key': 'INVALID_KEY', 'invalid_type': 'INVALID_TYPE',
                                'long_string': 'STRING_LIMIT'}
            self.assertEqual(result['rejected'], {key: {'ok': False, 'error': value} for key, value in expected_rejects.items()})


if __name__ == '__main__':
    unittest.main()
