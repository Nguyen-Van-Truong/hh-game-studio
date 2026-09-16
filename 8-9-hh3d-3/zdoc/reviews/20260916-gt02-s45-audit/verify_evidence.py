"""S45 coordinator verification. Evidence integrity is not gate acceptance."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
STUDIO = ROOT / 'studio'
AUDIT = Path(__file__).resolve().parent
PACK = ROOT / 'zdoc/reviews/20260916-gt02-s45-02'
NATIVE = ROOT / 'zdoc/reviews/20260916-gt02-s45-registry-native/run-02'
CLOSURE = '26a225b45f8283796448512987595fd962cad204e6c57164c3929ee7a067c243'


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


def verify():
    manifest = read(AUDIT/'diagnostic-manifest.json')
    for relative, digest in manifest['files'].items():
        assert sha(confined(ROOT, relative)) == digest, relative
    source, candidate = read(PACK/'source-closure.json'), read(PACK/'candidate.json')
    assert candidate['status'] == 'CANDIDATE' and candidate['acceptance_ready'] is False
    assert candidate['source_unchanged'] is True and candidate['acceptance'] == 'NOT_REVIEWED'
    assert candidate['source_closure_sha256'] == source['source_closure_sha256'] == CLOSURE
    assert len(source['files']) == 97 and len(candidate['artifacts']) == 9
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
        ('protocol', 375, 4), ('bootstrap', 56, 0)]

    # Reconstruct Python rows from the frozen generator, without launching tools.
    spec = importlib.util.spec_from_file_location('s45_golden', STUDIO/'tests/protocol/test_golden_vectors.py')
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

    host_ok(NATIVE, read(NATIVE/'capture.json')['host'])
    native = read(NATIVE/'registry-native-stdout.txt')
    assert native['runtime_closure']['source_closure_sha256'] == CLOSURE
    assert native['runtime_closure']['files'] == source['files']
    assert native['marker'] == 'S45_REGISTRY_BOUNDARY_VERIFIED'
    for key in ('snapshot_used','file_writer_guard_held','token_package_matches','protected_state_verified',
                'positive_control_read_write_verified','profile_absent_after','owned_temp_removed',
                'source_unchanged','snapshot_unchanged','snapshot_removed','complete'):
        assert native[key] is True, key
    assert native['safe_write'] is False and native['acceptance'] is False
    assert native['token_is_appcontainer'] == 1 and native['capabilities'] == 0
    assert native['integrity_sid'] == 'S-1-16-4096'
    assert native['host_exit'] == native['final_host_exit'] == 89
    assert native['final_job_active'] == 0 and native['final_job_pids'] == []
    assert native['owned_registry_leaves_removed'] == 2 and native['delete_profile_hresult'] == 0
    attack = native['native']
    assert attack['complete'] == 'S45_REGISTRY_BOUNDARY_COMPLETE'
    assert attack['loops'] == 5 and attack['attempts'] == attack['denied'] == 45
    assert attack['allowed'] == attack['unexpected'] == 0 and attack['control_read_write'] is True
    assert len(native['custody_updates']) == len(set(native['custody_updates'])) == 12
    assert (NATIVE/'registry-native-stderr.txt').read_bytes() == b''
    for lane in ('compile','link'):
        row = native['compiler'][lane]
        assert row['host_exit'] == row['wait_result'] == row['job_active'] == 0
        assert row['helper_cleanup'] == 'owned_build_job_after_root_exit'
    for relative,digest in native['diagnostic_sources'].items():
        path=ROOT/'zdoc/reviews'/relative.replace(chr(92),'/')
        assert sha(path) == digest
    for name in ('registry_probe.py','boundary_child.c'):
        assert sha(NATIVE/name) == sha(NATIVE.parent/name)
    return {'schema':'hh-gt02-s45-coordinator-verification-v1','status':'COORDINATOR_LOGIC_VERIFIED',
            'source_closure_sha256':CLOSURE,'source_files':97,'candidate_artifacts':9,
            'protocol':{'run':375,'passed':371,'skipped':4},'bootstrap':{'run':56,'passed':56},
            'golden_rows_per_consumer':2396,'registry_denied_attempts':45,'registry_broker_updates':12,
            'formal_acceptance':False,'limits':['public scoped dispatch/lifecycle incomplete',
            'native registry proof is not managed selector IPC proof',
            'ambiguous pending and Stop roots stay held; no power-loss claim',
            'S44 reviews do not apply to S45 acceptance']}


if __name__ == '__main__':
    if not __debug__: raise SystemExit('OPTIMIZED_VERIFICATION_FORBIDDEN')
    result=verify()
    (AUDIT/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
