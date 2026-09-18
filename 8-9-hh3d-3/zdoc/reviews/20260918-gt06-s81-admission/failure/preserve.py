"""Preserve failed S80 raw bytes. No engine, test, control action or raw writes.

Run once with python -B. Outputs use exclusive creation; original raw inputs are
stream-hashed with stat checks before/after, then completely re-inventoried.
"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
CAMPAIGN = ROOT / 'studio/.local/reviews/gt06-s80-campaign-01'
SUPERVISOR = CAMPAIGN.with_name(CAMPAIGN.name + '-supervisor')
ATTEMPT = CAMPAIGN / 'run-00-attempt-01'
SOURCE_CHECKPOINT = 'f75a5d08'
EXPECTED_CLOSURE = '1dc889ef923dee9b53c6faeeb1d6fd781acc3a89a4b860b531b55fc3a124cf8f'

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def digest(path):
    before = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), str(path)
    return h.hexdigest()

def read(path):
    return json.loads(path.read_bytes())

def write(name, value):
    path = OUT / name
    assert path.resolve().is_relative_to(OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = value if isinstance(value, bytes) else (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(raw)

def inventory(base):
    rows = []
    for path in sorted(base.rglob('*')):
        info = path.lstat()
        assert not path.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400, str(path)
        if path.is_file():
            value = digest(path)
            after = path.stat()
            assert (info.st_size, info.st_mtime_ns) == (after.st_size, after.st_mtime_ns), str(path)
            rows.append({'path': path.relative_to(base).as_posix(), 'bytes': after.st_size,
                         'sha256': value, 'mtime_ns': after.st_mtime_ns})
    return rows

def closure(files):
    return hashlib.sha256(''.join(name + '\0' + files[name] + '\n' for name in sorted(files)).encode()).hexdigest()

started = utc()
scheduler = read(OUT / 'observations/scheduler-terminal.stdout.txt')
assert scheduler['state'] == 3 and scheduler['last_task_result'] == 1 and scheduler['instances'] == []
processes = read(OUT / 'observations/processes.stdout.txt')
raw = {'campaign': inventory(CAMPAIGN), 'supervisor': inventory(SUPERVISOR)}
write('raw-locator-hashmaps.json', {'created_utc': utc(), 'algorithm': 'sha256',
    'scope': 'Complete exact-byte inventories of both original raw roots; no exclusions, caches included. Originals remain read-only in place.',
    'method': 'Stream SHA256 in 1 MiB blocks; size/mtime before-after every read; complete second inventory compared after copying.',
    'roots': {'campaign': str(CAMPAIGN), 'supervisor': str(SUPERVISOR)}, 'files': raw})

selected = set(p for p in CAMPAIGN.iterdir() if p.is_file())
selected.update(p for p in ATTEMPT.iterdir() if p.is_file())
for directory in ['host-owner', 'editor-host', 'import-host']:
    selected.update(p for p in (ATTEMPT / directory).iterdir() if p.is_file())
selected.update(p for p in (ATTEMPT / 'project/benchmark').rglob('*') if p.is_file())
for base in [CAMPAIGN / 'source', ATTEMPT / 'source']:
    selected.update(p for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
selected.update(p for p in SUPERVISOR.iterdir() if p.is_file())
copies = []
maps = {kind: {r['path']: r for r in rows} for kind, rows in raw.items()}
for source in sorted(selected):
    kind = 'campaign' if source.is_relative_to(CAMPAIGN) else 'supervisor'
    base = CAMPAIGN if kind == 'campaign' else SUPERVISOR
    relative = source.relative_to(base).as_posix()
    expected = maps[kind][relative]
    destination = 'raw/' + kind + '/' + relative
    data = source.read_bytes()
    assert len(data) == expected['bytes'] and hashlib.sha256(data).hexdigest() == expected['sha256']
    write(destination, data)
    assert digest(OUT / destination) == expected['sha256']
    copies.append({'path': destination, 'raw_root': kind, 'raw_path': relative,
                   'bytes': len(data), 'sha256': expected['sha256']})
write('preserved-byte-manifest.json', {'created_utc': utc(),
    'scope': 'Exact unmodified selected input bytes. Source snapshots, all completed-batch artifacts and failure records retained; caches stay in raw inventory only.',
    'files': copies})

campaign = read(CAMPAIGN / 'campaign.json')
context = read(ATTEMPT / 'context.json')
failure = read(ATTEMPT / 'child-failure.json')
sources = campaign['source_files']
assert sources == context['source_files'] == read(ATTEMPT / 'source-files.json')
assert closure(sources) == campaign['source_closure_sha256'] == EXPECTED_CLOSURE
assert len(sources) == 50
source_rows = []
for name, expected in sorted(sources.items()):
    row = {'path': name, 'expected_sha256': expected}
    for key, base in [('campaign_frozen', CAMPAIGN / 'source/studio'),
                      ('attempt_frozen', ATTEMPT / 'source/studio'), ('live_at_preservation', ROOT / 'studio')]:
        path = base / name
        row[key + '_sha256'] = digest(path) if path.is_file() else None
        row[key + '_matches'] = row[key + '_sha256'] == expected
    result = subprocess.run(['git', 'show', f'{SOURCE_CHECKPOINT}:8-9-hh3d-3/studio/{name}'],
                            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    row['checkpoint_git_show_exit'] = result.returncode
    row['checkpoint_git_blob_sha256'] = hashlib.sha256(result.stdout).hexdigest() if result.returncode == 0 else None
    row['checkpoint_git_blob_matches'] = row['checkpoint_git_blob_sha256'] == expected
    assert row['campaign_frozen_matches'] and row['attempt_frozen_matches'] and row['checkpoint_git_blob_matches']
    source_rows.append(row)
initial_project = read(ATTEMPT / 'initial-project-files.json')
project_rows = [{'path': name, 'expected_sha256': expected,
                 'actual_sha256': digest(ATTEMPT / 'project' / name)} for name, expected in sorted(initial_project.items())]
assert all(r['expected_sha256'] == r['actual_sha256'] for r in project_rows)
binary_rows = []
for role in ['host-owner', 'editor-host', 'import-host']:
    invocation = read(ATTEMPT / role / 'invocation.json')
    binary = Path(invocation['argv'][0])
    row = {'role': role, 'binary_path': str(binary), 'expected_sha256': invocation['binary_sha256'], 'actual_sha256': digest(binary)}
    assert row['expected_sha256'] == row['actual_sha256']
    binary_rows.append(row)
write('source-map-verification.json', {'created_utc': utc(), 'source_checkpoint': SOURCE_CHECKPOINT,
    'frozen_source_closure_sha256': closure(sources), 'source_file_count': len(sources),
    'closure_algorithm': 'sha256(concat(sorted(path + NUL + sha256 + LF)))',
    'git_verification': 'Exact bytes captured from git show checkpoint:8-9-hh3d-3/studio/path; no imports or engine execution.',
    'context_source_map_equal': True, 'attempt_source_map_equal': True,
    'campaign_sha256_matches_context': digest(CAMPAIGN / 'campaign.json') == context['campaign_sha256'],
    'all_frozen_files_match': True, 'all_checkpoint_git_blobs_match': True,
    'all_live_files_match_at_preservation': all(r['live_at_preservation_matches'] for r in source_rows),
    'files': source_rows, 'immutable_project_files': project_rows, 'binaries': binary_rows})

slots = []
for index in range(10):
    for attempt in range(1, 4):
        path = CAMPAIGN / f'run-{index:02d}-attempt-{attempt:02d}'
        slots.append({'path': path.relative_to(CAMPAIGN).as_posix(), 'exists': os.path.lexists(path),
            'stop_request_lexists': os.path.lexists(path / 'stop-request.json'),
            'run_capture_exists': (path / 'run-capture.json').is_file()})
missing = {name: not os.path.lexists(ATTEMPT / name) for name in [
    'editor-host/process-exit.json', 'editor-host/capture.json', 'host-owner/capture.json',
    'child-result.json', 'cleanup.json', 'assembly-manifest.json', 'assembled-run.json', 'run-capture.json',
    'command-15.json', 'batch-capture-15.json', 'joint-15.json', 'sample-preview-15.json',
    'project/benchmark/out/index.json', 'project/benchmark/input/start-15.json',
    'project/benchmark/input/ack-15.json', 'project/benchmark/out/batch-15.json']}
campaign_missing = {name: not os.path.lexists(CAMPAIGN / name) for name in ['campaign-capture.json', 'dataset.json', 'summary.json']}
host_exit = read(ATTEMPT / 'host-owner/process-exit.json')
editor_start = read(ATTEMPT / 'editor-host/process-start.json')
host_cleanup = read(ATTEMPT / 'host-owner/cleanup-001.json')
editor_cleanup = read(ATTEMPT / 'editor-host/cleanup-001.json')
import_capture = read(ATTEMPT / 'import-host/capture.json')
parent_failure = read(ATTEMPT / 'parent-failure.json')
supervisor_start = read(SUPERVISOR / 'start.json')
cleanup_checks = []
for role, record in [('host', host_cleanup), ('editor', editor_cleanup), ('import', import_capture)]:
    job = record['job']
    clean = job['assigned'] and job['configured'] and job['active_count'] == 0 and job['zero_observed'] and job['closed'] and not any(
        job[k] for k in ['handle_retained', 'tainted', 'create_uncertain', 'close_uncertain', 'failed_operations', 'native_error'])
    wrapper = record.get('wrapper_process_handle')
    handles = wrapper['closed'] and not wrapper['handle_retained'] and not wrapper['close_uncertain'] if wrapper else None
    cleanup_checks.append({'role': role, 'job_zero_closed_without_uncertainty': clean,
        'wrapper_handle_closed_without_uncertainty': handles,
        'note': 'No explicit wrapper_process_handle receipt in import capture' if wrapper is None else None})
assert all(r['job_zero_closed_without_uncertainty'] and r['wrapper_handle_closed_without_uncertainty'] is not False for r in cleanup_checks)
assert parent_failure['owned_tree_zero'] and parent_failure['owner_closed'] and parent_failure['cleanup_error'] is None
for name, expected in import_capture['artifacts'].items():
    assert digest(ATTEMPT / 'import-host' / name) == expected
pids = [host_exit['pid'], editor_start['pid'], import_capture['actual_process_exit']['pid'], supervisor_start['pid']]
facts = {'schema': 'HH-GT06-S81-FAILURE-PRESERVATION-1', 'observed_utc': utc(), 'formal_acceptance': False,
    'authority': 0, 'campaign_status': 'FAILED_PARTIAL', 'scheduler': scheduler,
    'scheduler_capture': 'observations/scheduler-terminal.capture.json',
    'process_snapshot_capture': 'observations/processes.capture.json',
    'process_snapshot_is_observation_not_natural_exit': True,
    'recorded_target_and_supervisor_pids': pids,
    'recorded_pids_present_in_snapshot': [p for p in processes if p['ProcessId'] in pids],
    'native_engine_processes_in_snapshot': [p for p in processes if any(n in p['Name'].lower() for n in ['godot', 'blender'])],
    'python_processes_in_snapshot': [p for p in processes if 'python' in p['Name'].lower()],
    'child_failure_code': failure['code'], 'child_failure_phase': failure['phase'],
    'completed_batches': failure['completed_batches'], 'warmup_batches_completed': 5,
    'captured_measured_batches': failure['completed_batches'] - 5, 'completed_full_runs': 0,
    'partial_command_count': len(failure['partial_command']['commands']),
    'host_actual_target_exit': host_exit, 'editor_actual_target_start': editor_start,
    'editor_actual_target_exit': None, 'editor_actual_exit_missing_reason': 'process-exit.json absent; helper wrapper exit 2 is distinct',
    'host_cleanup': host_cleanup, 'editor_cleanup': editor_cleanup, 'import_capture': import_capture,
    'parent_failure': parent_failure, 'supervisor_start': supervisor_start,
    'supervisor_return': read(SUPERVISOR / 'return.json'), 'supervisor_actual_target_exit': None,
    'helper_pid_inventory': None, 'helper_pid_inventory_reason': 'No durable helper PID inventory is present. Helper return codes and wrapper-handle cleanup receipts are recorded above.',
    'final_producer_probe_handle_inventory': None, 'final_producer_probe_handle_inventory_reason': 'No durable final producer/probe handle inventory in this failed run. Do not infer success-only cleanup.json.',
    'cleanup_static_checks': cleanup_checks, 'fixed_attempt_slots': slots,
    'supervisor_stop_request_lexists': os.path.lexists(SUPERVISOR / 'stop-request.json'),
    'confirmed_attempt_absences': missing, 'confirmed_campaign_absences': campaign_missing,
    'next_native_ready_exists': (ATTEMPT / 'project/benchmark/out/ready-15.json').is_file(),
    'raw_file_count': sum(map(len, raw.values())), 'raw_total_bytes': sum(r['bytes'] for rows in raw.values() for r in rows),
    'preserved_input_file_count': len(copies), 'preserved_input_bytes': sum(r['bytes'] for r in copies),
    'started_utc': started, 'finished_utc': utc()}
assert not facts['recorded_pids_present_in_snapshot'] and not facts['native_engine_processes_in_snapshot']
write('terminal-facts.json', facts)

samples = [read(p) for p in sorted(ATTEMPT.glob('sample-preview-*.json'))]
assert [s['index'] for s in samples] == list(range(15))
baseline = samples[4]['memory']
screens = []
for sample in samples:
    breaches = []
    for role, names in [('host', ['held_handles', 'rss_bytes']), ('editor', ['rss_bytes', 'held_handles', 'objects', 'resources'])]:
        for name in names:
            value, reference = sample['memory'][role][name]['value'], baseline[role][name]['value']
            exceeded = value * 100 > reference * 110 if name == 'rss_bytes' else value > reference
            if sample['index'] >= 5 and exceeded:
                breaches.append({'role': role, 'metric': name, 'value': value, 'baseline': reference})
    if sample['index'] >= 5 and sample['max_status_gap_ms'] > 2000:
        breaches.append({'metric': 'max_status_gap_ms', 'value': sample['max_status_gap_ms'], 'limit': 2000})
    screens.append({'index': sample['index'], 'warmup': sample['warmup'], 'memory': sample['memory'],
        'max_status_gap_ms': sample['max_status_gap_ms'], 'stop_receipt_ms': sample['stop_receipt_ms'],
        'stop_target_instance_id': sample['stop_target_instance_id'], 'applicable_screen_breaches': breaches})
references = []
for path in sorted(ATTEMPT.glob('batch-capture-*.json')):
    for kind, ref in read(path).items():
        if kind == 'index':
            continue
        target = ATTEMPT / ref['file']
        assert target.resolve().is_relative_to(ATTEMPT)
        assert digest(target) == ref['sha256'] and target.stat().st_size == ref['size_bytes']
        references.append({'capture': path.name, 'kind': kind, **ref, 'verified': True})
assert len(references) == 90
write('completeness-and-screen.json', {'observed_utc': utc(),
    'scope': 'Failed-run partial-prefix preservation and static checks only; no full-run PASS, no cause claim, no critic verdict.',
    'recorded_failure': failure['code'], 'recorded_phase': failure['phase'], 'source_closure': closure(sources),
    'captured_batch_indexes': list(range(15)), 'warmup_batches': 5, 'collected_measured_batches': 10,
    'completed_full_runs': 0, 'required_full_runs': 10, 'missing_measured_this_run': 20,
    'baseline_batch_index': 4, 'samples': screens, 'operator_stop_slots_checked': len(slots),
    'operator_stop_latches_present': sum(s['stop_request_lexists'] for s in slots),
    'per_batch_stop_targets_unique': len({s['stop_target_instance_id'] for s in samples}) == 15,
    'per_batch_stop_receipts': 15, 'preserved_partial_data_is_accepted': False})

assert raw['campaign'] == inventory(CAMPAIGN) and raw['supervisor'] == inventory(SUPERVISOR), 'raw inventory changed'
assert all(digest(OUT / r['path']) == r['sha256'] for r in copies)
assert all(missing.values()) and all(campaign_missing.values()) and not any(s['stop_request_lexists'] for s in slots)
write('verification.json', {'verified_utc': utc(), 'status': 'PRESERVATION_VERIFIED', 'formal_acceptance': False,
    'scope': 'Forensic bytes and static checks only; no native run, test, final critic signature or GT-06 acceptance.',
    'raw_files_rehashed': facts['raw_file_count'], 'raw_before_after_equal': True,
    'exact_copies_reverified': len(copies), 'batch_references_verified': len(references),
    'completed_batch_capture_count': len(samples), 'source_closure_recomputed': closure(sources),
    'source_git_checkpoint_blobs_verified': 50, 'stop_slots_checked': len(slots), 'errors': [],
    'batch_references': references})
print(json.dumps({'raw_files': facts['raw_file_count'], 'raw_bytes': facts['raw_total_bytes'],
    'copies': len(copies), 'copy_bytes': facts['preserved_input_bytes'], 'source_files': len(sources),
    'source_closure': closure(sources), 'failure': failure['code'], 'complete_prefix_batches': len(samples),
    'measured_prefix_batches': len(samples)-5, 'batch_references_verified': len(references),
    'owned_pids_present': facts['recorded_pids_present_in_snapshot'], 'partial_command_count': facts['partial_command_count'],
    'measured_screen_breaches': [s for s in screens if s['applicable_screen_breaches']]}))
