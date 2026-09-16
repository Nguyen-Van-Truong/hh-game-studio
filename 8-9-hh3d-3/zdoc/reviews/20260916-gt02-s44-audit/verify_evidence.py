"""S44 coordinator verification. Evidence integrity is not gate acceptance."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
STUDIO = ROOT / 'studio'
AUDIT = Path(__file__).resolve().parent
PACK = ROOT / 'zdoc/reviews/20260916-gt02-s44-02'
IPC = ROOT / 'zdoc/reviews/20260916-gt02-s44-native/run-02'
BOUNDARY = ROOT / 'zdoc/reviews/20260916-gt02-s44-boundary/run-06'
CLOSURE = '6730c6f54cd682920b7585d139835088ae60f893f68fff8cd24662e268716964'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def confined(base, name):
    path = base.joinpath(*name.split('/'))
    path.resolve().relative_to(base.resolve())
    return path


def host_ok(folder, run):
    host = read(confined(folder, run['host']))
    assert run['exit_code'] == run['wrapper_exit_code'] == host['exit_code'] == 0
    assert run['tree_verified'] is True and run['timed_out'] is False


def native_ok(folder, source):
    host_ok(folder, read(folder/'capture.json')['host'])
    raw = read(folder/'native-stdout.txt')
    assert raw['runtime_closure']['source_closure_sha256'] == CLOSURE
    assert raw['runtime_closure']['files'] == source['files']
    assert raw['safe_write'] is False and raw['acceptance'] is False
    assert raw['profile_absent_after'] is True and raw['owned_temp_removed'] is True
    assert raw['delete_profile_hresult'] == 0
    for lane in ('compile', 'link'):
        row = raw['compiler'][lane]
        assert row['host_exit'] == row['wait_result'] == row['job_active'] == 0
        assert row['helper_cleanup'] == 'owned_build_job_after_root_exit'
        assert row['stderr'] == ''
    assert (folder/'native-stderr.txt').read_bytes() == b''
    return raw


def verify():
    manifest = read(AUDIT/'diagnostic-manifest.json')
    for relative, digest in manifest['files'].items():
        assert sha(confined(ROOT, relative)) == digest, relative
    source, candidate = read(PACK/'source-closure.json'), read(PACK/'candidate.json')
    assert candidate['status'] == 'CANDIDATE' and candidate['acceptance_ready'] is False
    assert candidate['source_unchanged'] is True and candidate['acceptance'] == 'NOT_REVIEWED'
    assert candidate['source_closure_sha256'] == source['source_closure_sha256'] == CLOSURE
    assert len(source['files']) == 90 and len(candidate['artifacts']) == 9
    rows = []
    for relative, digest in sorted(source['files'].items()):
        assert re.fullmatch('[0-9a-f]{64}', digest)
        assert sha(confined(STUDIO, relative)) == digest, relative
        rows.append(f'8-9-hh3d-3/studio/{relative}\0{digest}\n')
    assert hashlib.sha256(''.join(rows).encode()).hexdigest() == CLOSURE
    excluded = {'__pycache__', '.godot', '.local', 'evidence'}
    actual = {'toolchain.lock.json'}
    for folder in ('protocol', 'host/core', 'tests/protocol', 'tests/bootstrap', 'build/bootstrap', 'fixtures'):
        actual.update(p.relative_to(STUDIO).as_posix() for p in (STUDIO/folder).rglob('*')
                      if p.is_file() and not set(p.relative_to(STUDIO).parts) & excluded)
    assert actual == set(source['files'])
    for name, digest in candidate['artifacts'].items():
        assert sha(confined(PACK, name)) == digest, name
    for lane in candidate['lanes']:
        run, summary = lane['host'], lane['summary']
        host_ok(PACK, run)
        assert lane['passed'] is True and summary['failures'] == summary['errors'] == 0
        assert len(summary['test_ids']) == len(set(summary['test_ids'])) == summary['tests_run']
        out = confined(PACK, run['stdout']).read_text(encoding='utf-8')
        marker = [json.loads(x.removeprefix('HH_GT02_TEST_RESULT ')) for x in out.split('\n')
                  if x.startswith('HH_GT02_TEST_RESULT ')]
        assert marker == [summary]
    assert [(l['suite'], l['summary']['tests_run'], l['summary']['skips']) for l in candidate['lanes']] == [
        ('protocol', 326, 4), ('bootstrap', 56, 0)]

    # Reconstruct Python rows from the frozen generator, without launching tools.
    spec = importlib.util.spec_from_file_location('s44_golden', STUDIO/'tests/protocol/test_golden_vectors.py')
    golden = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(golden)
    golden.GoldenVectorTests.setUpClass()
    expected = golden.GoldenVectorTests.expected
    assert len(expected) == 2396
    records = [read(p) for p in sorted((PACK/'golden').glob('*.json'))]
    assert len(records) == 2
    for record in records:
        assert record['host_exit'] == 0 and record['stderr'] == ''
        assert record['test_source_sha256'] == source['files']['tests/protocol/test_golden_vectors.py']
        if 'rows' in record:
            assert record['rows'] == expected
        else:
            parsed = [json.loads(line.removeprefix('HH_GT02_JCS ')) for line in record['stdout'].split('\n')
                      if line.startswith('HH_GT02_JCS ')]
            assert len(parsed) == 1 and parsed[0]['rows'] == expected
            assert record['leftover_before'] == record['leftover_after'] == []
            assert record['source_unchanged'] is True

    ipc = native_ok(IPC, source)
    assert ipc['marker'] == 'S44_FILE_SELECTOR_IPC_DIAGNOSTIC_COMPLETE' and ipc['diagnostic_complete'] is True
    for key in ('runtime_snapshot_used', 'runtime_source_unchanged', 'runtime_snapshot_unchanged', 'runtime_snapshot_removed'):
        assert ipc[key] is True
    assert sha(IPC/'ipc_probe.py') == ipc['source_sha256']
    assert sha(IPC/'boundary_child.c') == ipc['native_source_sha256']
    for item in ipc['loaded_runtime_modules'].values():
        assert item['sha256'] == source['files'][item['relative']]
    for key in ('remaining_endpoint_owners', 'remaining_io_owners', 'remaining_event_owners'):
        assert ipc[key] == 0
    wrong = ipc['wrong_client']
    assert wrong['rejection'] == 'PIPE_CLIENT_MISMATCH' and wrong['dispatcher_called'] is False
    assert wrong['job_active'] == 0 and wrong['job_pids'] == []
    modes = {'submit': ('COMMITTED', True), 'drop_reply': ('COMMITTED', True),
             'wrong_token': ('REJECTED', False), 'stale_lease': ('REJECTED', False),
             'cancel': ('CANCELED', False), 'stop': ('CANCELED', False), 'stop_selected': ('UNKNOWN', True)}
    assert len(ipc['cases']) == 7 and {c['mode'] for c in ipc['cases']} == set(modes)
    for case in ipc['cases']:
        assert 'error' not in case and case['host_exit'] == case['final_host_exit'] == 61
        assert case['final_job_active'] == 0 and case['final_job_pids'] == []
        assert case['primary_token_verified'] is True and case['inherit_handles'] is False
        status, changed = modes[case['mode']]
        assert case['work_receipt']['status'] == status and case['file_changed'] is changed
        assert (case['baseline_file'] != case['final_file']) is changed
        if changed:
            assert case['baseline_file']['identity']['file_id'] != case['final_file']['identity']['file_id']
        native = case['native']
        assert native['complete'] == 'S39_NATIVE_COMPLETE'
        assert all(native[key] == 5 for key in ('pipe_write_dac_error', 'pipe_write_owner_error',
                   'second_instance_error', 'private_read_error', 'private_write_error', 'events_access_error'))
        if case['mode'] in ('submit', 'drop_reply'):
            assert case['consumer_adoptions'] == case['snapshot']['generation'] == 2
            assert case['control_dispatch'] == case['work_receipt']
            if case['mode'] == 'submit':
                assert case['native_retry_dispatch'] == case['work_receipt']
            else:
                assert case['work_transport_error'] == 'PIPE_IO_FAILED'
        elif case['mode'] == 'stop_selected':
            assert case['restore_receipt']['status'] == 'UNKNOWN'
            assert case['restore_receipt']['postconditions']['restored'] is True
            assert case['restored_snapshot']['generation'] == 3
            assert case['restored_snapshot']['ready'] is True
        else:
            assert case['consumer_adoptions'] == case['snapshot']['generation'] == 1

    boundary = native_ok(BOUNDARY, source)
    assert boundary['marker'] == 'S44_REPLACE_BOUNDARY_COMPLETE' and boundary['complete'] is True
    for key in ('snapshot_used', 'source_unchanged', 'snapshot_unchanged', 'snapshot_removed', 'outside_alias_absent'):
        assert boundary[key] is True
    assert boundary['token_is_appcontainer'] == 1 and boundary['token_package_matches'] is True
    assert boundary['capabilities'] == 0 and boundary['integrity_sid'] == 'S-1-16-4096'
    assert boundary['host_exit'] == boundary['final_host_exit'] == 67
    assert boundary['final_job_active'] == 0 and boundary['final_job_pids'] == []
    for name in ('replace_probe.py', 'boundary_child.c', 'compile_native.py'):
        assert sha(BOUNDARY/name) == boundary['diagnostic_sources'][name]
    attack = boundary['native']
    assert attack['complete'] == 'S44_NATIVE_COMPLETE' and attack['scratch_control'] is True
    assert attack['loops'] == 32 and attack['attempts'] == 288
    assert attack['allowed'] == attack['unexpected_errors'] == 0
    replacements = boundary['replacements']
    assert len(replacements) == 20 and all(r['old_id'] != r['new_id'] for r in replacements)
    assert all(a['new_id'] == b['old_id'] for a, b in zip(replacements, replacements[1:]))
    return {'schema': 'hh-gt02-s44-coordinator-verification-v1', 'status': 'COORDINATOR_LOGIC_VERIFIED',
            'source_closure_sha256': CLOSURE, 'source_files': 90, 'candidate_artifacts': 9,
            'protocol': {'run': 326, 'passed': 322, 'skipped': 4}, 'bootstrap': {'run': 56, 'passed': 56},
            'golden_rows_per_consumer': 2396, 'native_ipc_cases': 7, 'native_replacements': 20,
            'denied_attempts': 288, 'formal_acceptance': False,
            'limits': ['public safe_write/atomic_replace disabled', 'readonly recovery cannot resume mutation',
                       'witness custody/production supervisor incomplete', 'no power-loss or engine consumer proof',
                       'independent critic reports are separate; coordinator does not supply signatures']}


if __name__ == '__main__':
    if not __debug__:
        raise SystemExit('OPTIMIZED_VERIFICATION_FORBIDDEN')
    result = verify()
    (AUDIT/'verification.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result))
