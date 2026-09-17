"""Independent read-only verifier; only emits new reports/seal in this folder."""
import datetime
import hashlib
import json
import os
from pathlib import Path

OUT = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(name, value):
    path = OUT / name
    assert path.resolve().is_relative_to(OUT)
    raw = value if isinstance(value, bytes) else (json.dumps(value, indent=2) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(raw)


inventory = read(OUT / 'raw-locator-hashmaps.json')
raw_count = 0
for name, rows in inventory['files'].items():
    root = Path(inventory['roots'][name])
    assert sorted(p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()) == sorted(row['path'] for row in rows)
    for row in rows:
        path = root / row['path']
        assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256']
        raw_count += 1
copies = read(OUT / 'preserved-byte-manifest.json')['files']
for row in copies:
    path = OUT / row['path']
    original = Path(inventory['roots'][row['raw_root']]) / row['raw_path']
    assert path.read_bytes() == original.read_bytes()
    assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256']

campaign_root = Path(inventory['roots']['campaign'])
attempt = campaign_root / 'run-00-attempt-02'
campaign = read(campaign_root / 'campaign.json')
context = read(attempt / 'context.json')
source = campaign['source_files']
assert source == context['source_files'] == read(attempt / 'source-files.json')
assert len(source) == 49
assert sha(campaign_root / 'campaign.json') == context['campaign_sha256']
for relative, expected in source.items():
    for base in [campaign_root / 'source/studio', attempt / 'source/studio']:
        assert sha(base / relative) == expected
closure = hashlib.sha256(''.join(name + '\0' + source[name] + '\n' for name in sorted(source)).encode()).hexdigest()
assert closure == campaign['source_closure_sha256'] == context['source_closure_sha256']

host_start = read(attempt / 'host-owner/process-start.json')
host_exit = read(attempt / 'host-owner/process-exit.json')
editor_start = read(attempt / 'editor-host/process-start.json')
import_start = read(attempt / 'import-host/process-start.json')
import_exit = read(attempt / 'import-host/process-exit.json')
import_capture = read(attempt / 'import-host/capture.json')
assert host_start['pid'] == host_exit['pid'] == 27508 and host_exit['exit_code'] == 1
assert editor_start['pid'] == 8776 and not os.path.lexists(attempt / 'editor-host/process-exit.json')
assert import_start['pid'] == import_exit['pid'] == 35564 and import_exit['exit_code'] == 0
assert import_capture['actual_process_exit'] == import_exit and import_capture['wrapper_exit_code'] == 0
for name, expected in import_capture['artifacts'].items():
    assert sha(attempt / 'import-host' / name) == expected
owner_rows = []
for role, directory, expected_wrapper in [('host', 'host-owner', 1), ('editor', 'editor-host', 2)]:
    record = read(attempt / directory / 'cleanup-001.json')
    job = record['job']
    wrapper = record['wrapper_process_handle']
    assert record['closed'] and record['wrapper_exit_code'] == expected_wrapper
    assert job['configured'] and job['assigned'] and job['closed'] and job['zero_observed'] and job['active_count'] == 0
    assert not any(job[k] for k in ['handle_retained', 'tainted', 'native_error', 'failed_operations', 'create_uncertain', 'close_uncertain'])
    assert wrapper['closed'] and not wrapper['handle_retained'] and not wrapper['close_uncertain']
    owner_rows.append({'role': role, 'job_zero_closed': True, 'job_handle_released': True,
        'wrapper_handle_released': True, 'wrapper_exit': expected_wrapper})
parent = read(attempt / 'parent-failure.json')
assert parent['owner_closed'] and parent['owned_tree_zero'] and parent['cleanup_error'] is None

references = 0
identities = None
for index in range(10):
    batch = read(attempt / f'batch-capture-{index:02d}.json')
    sample = read(attempt / f'sample-preview-{index:02d}.json')
    joint = read(attempt / f'joint-{index:02d}.json')
    assert batch['index'] == sample['index'] == joint['index'] == index
    assert joint['run_id'] == context['run_id']
    assert joint['source_closure_sha256'] == closure and joint['profile_sha256'] == context['profile_sha256']
    if identities is None:
        identities = sample['processes']
    assert sample['processes'] == joint['processes'] == identities
    assert identities['host']['pid'] == host_exit['pid'] and identities['editor']['pid'] == editor_start['pid']
    for kind, ref in batch.items():
        if kind == 'index':
            continue
        path = attempt / ref['file']
        assert path.resolve().is_relative_to(attempt)
        assert path.stat().st_size == ref['size_bytes'] and sha(path) == ref['sha256']
        references += 1
    evidence = {'profile_sha256': context['profile_sha256'], 'source_closure_sha256': closure,
        'run_id': context['run_id'], 'index': index, 'processes': identities,
        'artifacts': {key: value for key, value in batch.items() if key != 'index'},
        'barrier_receipt': joint['barrier_receipt']}
    evidence_bytes = json.dumps(evidence, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    assert sample['evidence_sha256'] == hashlib.sha256(evidence_bytes).hexdigest()
assert references == 60
assert not (attempt / 'editor-host/stderr.txt').read_bytes()
assert b'CAMPAIGN_RETAINED_COUNTER_GROWTH' in (attempt / 'host-owner/stderr.txt').read_bytes()

stop_count = 0
existing_slots = []
for index in range(10):
    for number in range(1, 4):
        slot = campaign_root / f'run-{index:02d}-attempt-{number:02d}'
        assert not os.path.lexists(slot / 'stop-request.json')
        assert not os.path.lexists(slot / 'run-capture.json')
        if os.path.lexists(slot):
            existing_slots.append(slot.name)
        stop_count += 1
assert existing_slots == ['run-00-attempt-01', 'run-00-attempt-02']
facts = read(OUT / 'terminal-facts.json')
for relative, missing in facts['confirmed_absences'].items():
    assert missing and not os.path.lexists(campaign_root / relative)
observations = 0
for path in (OUT / 'observations').glob('*.capture.json'):
    capture = read(path)
    prefix = path.name.removesuffix('.capture.json')
    assert capture['returncode'] == 0
    assert sha(path.with_name(prefix + '.stdout.txt')) == capture['stdout_sha256']
    assert sha(path.with_name(prefix + '.stderr.txt')) == capture['stderr_sha256']
    observations += 1
scheduler = read(OUT / 'observations/scheduler-terminal.stdout.txt')
assert scheduler['state'] == 3 and scheduler['last_task_result'] == 1 and scheduler['instances'] == []
assert scheduler['launch_number'] == 2 and scheduler['campaign_id'] == campaign_root.name
returned = read(Path(inventory['roots']['supervisor']) / 'return.json')
assert returned['returned_exit_code'] == 1 and returned['actual_process_exit_not_yet_observed']
result = {'verified_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'status': 'PASS',
    'scope': 'Preservation/static consistency only; no runtime or acceptance verdict', 'raw_files': raw_count,
    'exact_copies': len(copies), 'source_files': len(source), 'source_closure': closure,
    'batch_references': references, 'sample_identity_rows': 10, 'processes': identities,
    'actual_host_exit': host_exit, 'actual_editor_exit': None, 'actual_import_exit': import_exit,
    'owner_checks': owner_rows, 'read_only_observer_exit_zero_count': observations,
    'stop_slots_checked': stop_count, 'stop_latches_present': 0, 'existing_attempt_slots': existing_slots,
    'scheduler_state': 3, 'scheduler_result': 1, 'scheduler_instances': 0, 'errors': []}
write('verification-independent.json', result)
manifest_rows = [{'path': p.relative_to(OUT).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)}
                 for p in sorted(OUT.rglob('*')) if p.is_file()
                 and p.name not in ['package-manifest.json', 'package-manifest.sha256']]
write('package-manifest.json', {'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'scope': 'All files in this failure package except package-manifest.json and its detached checksum',
    'file_count': len(manifest_rows), 'total_bytes': sum(r['bytes'] for r in manifest_rows), 'files': manifest_rows})
manifest_hash = sha(OUT / 'package-manifest.json')
write('package-manifest.sha256', (manifest_hash + '  package-manifest.json\n').encode())
assert all(sha(OUT / row['path']) == row['sha256'] for row in manifest_rows)
print(json.dumps({'status': 'PASS', 'scope': result['scope'], 'sealed_files': len(manifest_rows),
    'manifest_sha256': manifest_hash, 'raw_files': raw_count, 'exact_copies': len(copies), 'batch_references': references}))
