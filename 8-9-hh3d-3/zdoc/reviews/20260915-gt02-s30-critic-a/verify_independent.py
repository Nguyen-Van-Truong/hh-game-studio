"""Read-only S30 artifact audit; no engine/full-suite execution."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
PRODUCT = Path(__file__).resolve().parents[3]
STUDIO = PRODUCT / 'studio'
PACKAGE = PRODUCT / 'zdoc/reviews/20260915-gt02-s30-01'
OUT = Path(__file__).resolve().parent
EXPECTED = '60799065f406fbb3b13d2dc0df093477210927f86e84b54175dfd36351521a1a'
sys.path.insert(0, str(PRODUCT))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))

def verify():
    c = read_json(PACKAGE / 'candidate.json')
    m = read_json(PACKAGE / 'source-closure.json')
    files = m['files']
    assert len(files) == 62
    assert all(digest(STUDIO / key) == value for key, value in files.items())
    observed = {'toolchain.lock.json'}
    for folder in ('protocol', 'host/core', 'tests/protocol', 'tests/bootstrap', 'build/bootstrap', 'fixtures'):
        for path in (STUDIO / folder).rglob('*'):
            relative = path.relative_to(STUDIO)
            if path.is_file() and not set(relative.parts) & {'__pycache__', '.godot', '.local', 'evidence'}:
                assert not path.is_symlink()
                assert not getattr(path.stat(follow_symlinks=False), 'st_file_attributes', 0) & 0x400
                observed.add(relative.as_posix())
    assert observed == set(files), (observed - set(files), set(files) - observed)
    closure = hashlib.sha256(''.join(sorted(
        f'8-9-hh3d-3/studio/{key}\0{value}\n' for key, value in files.items())).encode('utf-8')).hexdigest()
    assert closure == EXPECTED == m['source_closure_sha256'] == c['source_closure_sha256']
    assert c['source_unchanged'] is True
    assert c['status'] == 'CANDIDATE' and c['acceptance_ready'] is False
    artifacts = c['artifacts']
    assert len(artifacts) == 9
    assert set(artifacts) == {p.relative_to(PACKAGE).as_posix() for p in PACKAGE.rglob('*') if p.is_file() and p.name != 'candidate.json'}
    for name, expected in artifacts.items():
        assert digest(PACKAGE / name) == expected, name
    start = datetime.fromisoformat(c['started_utc'])
    end = datetime.fromisoformat(c['completed_utc'])
    lanes = []
    for lane in c['lanes']:
        host = lane['host']
        actual_host = read_json(PACKAGE / host['host'])
        assert actual_host['exit_code'] == host['exit_code'] == host['wrapper_exit_code'] == 0
        assert actual_host['target_pid'] == host['target_pid']
        assert host['tree_verified'] is True and host['timed_out'] is False
        assert host['ownership'] == 'gated_job_kill_on_close'
        assert start <= datetime.fromisoformat(host['started_at']) <= datetime.fromisoformat(actual_host['started_at']) <= end
        stdout = (PACKAGE / host['stdout']).read_text(encoding='utf-8')
        markers = [line.removeprefix('HH_GT02_TEST_RESULT ') for line in stdout.split('\n') if line.startswith('HH_GT02_TEST_RESULT ')]
        assert len(markers) == 1
        summary = json.loads(markers[0])
        assert summary == lane['summary']
        assert summary['tests_run'] == len(summary['test_ids']) == len(set(summary['test_ids']))
        assert summary['failures'] == summary['errors'] == 0
        stderr = (PACKAGE / host['stderr']).read_text(encoding='utf-8')
        assert re.search(rf'Ran {summary["tests_run"]} tests? in ', stderr)
        assert (stderr.rstrip().endswith('OK') if not summary['skips'] else stderr.rstrip().endswith(f'OK (skipped={summary["skips"]})'))
        assert not lane['missing_required_evidence'] and lane['passed'] is True
        lanes.append({'suite': lane['suite'], 'tests_run': summary['tests_run'], 'passes': summary['tests_run'] - summary['skips'], 'skipped': summary['skipped'], 'host_exit': actual_host['exit_code'], 'tree_verified': True})
    spec = importlib.util.spec_from_file_location('critic_golden_source', STUDIO / 'tests/protocol/test_golden_vectors.py')
    golden = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(golden)
    golden.GoldenVectorTests.setUpClass()
    # Execute only the pure-Python vector case, never the Node/Godot tests.
    golden.GoldenVectorTests('test_python_vectors').test_python_vectors()
    expected_rows = golden.GoldenVectorTests.expected
    assert len(expected_rows) == 2396
    node = read_json(next((PACKAGE / 'golden').glob('*node*.json')))
    godot = read_json(next((PACKAGE / 'golden').glob('*godot*.json')))
    rows = [line.removeprefix('HH_GT02_JCS ') for line in godot['stdout'].split('\n') if line.startswith('HH_GT02_JCS ')]
    assert len(rows) == 1
    parsed = json.loads(rows[0])
    assert node['rows'] == parsed['rows'] == expected_rows
    assert len(parsed['rejected']) == 9 and all(value['ok'] is False for value in parsed['rejected'].values())
    for row in expected_rows:
        raw = row['canonical'].encode('utf-8')
        assert raw.hex() == row['utf8_hex']
        assert 'sha256:' + hashlib.sha256(raw).hexdigest() == row['sha256']
    for record in (node, godot):
        assert start <= datetime.fromisoformat(record['timestamp_utc']) <= end
        assert record['host_exit'] == 0 and record['stderr'] == '' and record['seed'] == 8785
        assert record['test_source_sha256'] == files['tests/protocol/test_golden_vectors.py']
        assert record['scope'] == 'serializer_conformance_only'
    assert godot['source_unchanged'] is True and godot['leftover_before'] == godot['leftover_after'] == []
    assert godot['raw_wire_parser_conformance'] is False
    for name in ('golden_consumer.gd', 'jcs_godot.gd'):
        assert godot['source_hashes'][name] == files['protocol/' + name]
    fixture = {'cases': [], 'binary64': [{'id': case['id'], 'bits': case['bits']} for case in golden.GoldenVectorTests.data['binary64']]}
    for case in golden.GoldenVectorTests.data['cases']:
        entry = {'id': case['id'], 'input': golden._tagged_fixture(case['input'])}
        if 'request_body' in case:
            entry['request_body'] = golden._tagged_fixture(case['request_body'])
        fixture['cases'].append(entry)
    assert godot['source_hashes']['vectors.json'] == hashlib.sha256(json.dumps(fixture).encode('utf-8')).hexdigest()
    generated_project = 'config_version=5\n[application]\nconfig/name="GT02 JCS"\n'.replace('\n', '\r\n').encode('utf-8')
    assert godot['source_hashes']['project.godot'] == hashlib.sha256(generated_project).hexdigest()
    diagnostics = '\n'.join(line for line in godot['stdout'].split('\n') if not line.startswith('HH_GT02_JCS ')) + godot['stderr']
    assert not re.search(r'\b(?:error|warning|leaked)\b', diagnostics, re.IGNORECASE)
    pin = read_json(STUDIO / 'toolchain.lock.json')['godot']
    assert godot['console_sha256'] == pin['console_sha256'] and godot['gui_sha256'] == pin['gui_sha256']
    assert node['consumer_sha256'] == hashlib.sha256(golden.NODE_CONSUMER.encode('utf-8')).hexdigest()
    # Git clean-filter bytes must match the exact frozen bytes as well.
    git_rows = []
    for name in files:
        path = STUDIO / name
        result = subprocess.run(['git', 'hash-object', '--path=' + '8-9-hh3d-3/studio/' + name, '--stdin'],
            input=path.read_bytes(), cwd=PRODUCT.parent, capture_output=True, timeout=10)
        assert result.returncode == 0
        raw = path.read_bytes()
        expected_git = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        assert result.stdout.decode().strip() == expected_git, name
        git_rows.append(name)
    return {'verified_utc': datetime.now(timezone.utc).isoformat(), 'source_closure_sha256': closure,
        'source_files': len(files), 'git_clean_bytes_checked': len(git_rows), 'artifacts_checked': len(artifacts),
        'lanes': lanes, 'matching_canonical_rows': len(expected_rows), 'godot_negative_rows': len(parsed['rejected']),
        'godot_generated_inputs_reconstructed': ['vectors.json', 'project.godot'],
        'engine_rerun': False, 'raw_wire_scope': 'Python host only', 'status': 'PASS'}

if __name__ == '__main__':
    result = verify()
    (OUT / 'verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
