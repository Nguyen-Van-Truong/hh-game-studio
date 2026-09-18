"""Preserve S81 failure without importing runtime, running tests or mutating raw.

Adapted from the S80 collector in s81-admission/failure, with S81's 51-file
closure, 16 captures and child-terminal-cleanup. Run once with python -B.
All outputs use exclusive creation; all raw bytes are inventoried twice.
"""
from pathlib import Path
import collections
import datetime
import hashlib
import json
import os
import re
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
CAMPAIGN = ROOT / 'studio/.local/reviews/gt06-s81-campaign-01'
SUPERVISOR = CAMPAIGN.with_name(CAMPAIGN.name + '-supervisor')
ATTEMPT = CAMPAIGN / 'run-00-attempt-01'
CHECKPOINT = 'b3862a10'
HEAD = 'd1254bf8fbc18585a19cb41153581ec832280425'
EXPECTED = 'e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f'
PROFILE = '0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85'


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def plain(path):
    assert path.exists(), str(path)
    for part in [path, *path.parents]:
        info = part.lstat()
        assert not part.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400, str(part)


def digest(path):
    plain(path)
    before = path.stat()
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            value.update(block)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), str(path)
    return value.hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(name, value):
    path = OUT / name
    assert path.resolve().is_relative_to(OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    plain(path.parent)
    data = value if isinstance(value, bytes) else (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(data)


def inventory(base):
    plain(base)
    rows = []
    for path in sorted(base.rglob('*')):
        plain(path)
        if path.is_file():
            stat = path.stat()
            value = digest(path)
            assert (stat.st_size, stat.st_mtime_ns) == (path.stat().st_size, path.stat().st_mtime_ns)
            rows.append(dict(path=path.relative_to(base).as_posix(), bytes=stat.st_size,
                             sha256=value, mtime_ns=stat.st_mtime_ns))
    return rows


def closure(files):
    return hashlib.sha256(''.join(p + '\0' + files[p] + '\n' for p in sorted(files)).encode()).hexdigest()


def git_digest(commit, path):
    result = subprocess.run(['git', 'show', f'{commit}:8-9-hh3d-3/studio/{path}'], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    assert result.returncode == 0, (commit, path)
    return hashlib.sha256(result.stdout).hexdigest()


def verify_ref(ref):
    path = ATTEMPT / ref['file']
    assert path.resolve().is_relative_to(ATTEMPT)
    assert path.stat().st_size == ref['size_bytes'] and digest(path) == ref['sha256'], ref['file']


def secret_screen(data, name):
    # This is an explicit pattern/key screen, not a universal absence proof.
    assert not re.search(rb'(?i)(?:Bearer\s+[a-z0-9_\-.]{12,}|-----BEGIN[^\r\n]*PRIVATE KEY-----|sk-[a-zA-Z0-9]{20,})', data), name
    if name.endswith('.json'):
        def walk(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    assert not re.search(r'(?:^|_)(?:token|secret|password|credential|authorization|api_key)(?:$|_)', key, re.I), (name, key)
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
        walk(json.loads(data))


started = utc()
scheduler = read(OUT / 'observations/scheduler-terminal.stdout.txt')
assert (scheduler['state'], scheduler['last_task_result'], scheduler['instances']) == (3, 1, [])
processes = read(OUT / 'observations/processes.stdout.txt')
assert (OUT / 'observations/git-head.stdout.txt').read_text().strip() == HEAD
raw = dict(campaign=inventory(CAMPAIGN), supervisor=inventory(SUPERVISOR))
maps = {kind: {r['path']: r for r in rows} for kind, rows in raw.items()}
campaign = read(CAMPAIGN / 'campaign.json')
context = read(ATTEMPT / 'context.json')
failure = read(ATTEMPT / 'child-failure.json')
terminal = read(ATTEMPT / 'child-terminal-cleanup.json')
sources = campaign['source_files']
assert sources == context['source_files'] == read(ATTEMPT / 'source-files.json')
assert len(sources) == 51 and closure(sources) == EXPECTED
assert campaign['source_closure_sha256'] == context['source_closure_sha256'] == terminal['source_closure_sha256'] == EXPECTED
assert digest(CAMPAIGN / 'campaign.json') == context['campaign_sha256']
assert digest(CAMPAIGN / 'benchmark-profile.json') == digest(ATTEMPT / 'benchmark-profile.json') == PROFILE
assert campaign['profile_sha256'] == context['profile_sha256'] == terminal['profile_sha256'] == PROFILE
profile = read(ATTEMPT / 'benchmark-profile.json')
assert (campaign['run_count'], campaign['batches_per_run'], profile['warmup_batches'], profile['measured_batches']) == (10, 35, 5, 30)
assert failure['code'] == terminal['primary_error']['code'] == 'CAMPAIGN_RETAINED_COUNTER_GROWTH'
assert failure['completed_batches'] == terminal['completed_batches'] == 16
assert failure['phase'] == terminal['phase'] == {'batch': 15, 'phase': 'joint_observation'}

source_rows = []
for name, expected in sorted(sources.items()):
    row = dict(path=name, expected_sha256=expected)
    for label, base in [('campaign_frozen', CAMPAIGN / 'source/studio'),
                        ('attempt_frozen', ATTEMPT / 'source/studio'), ('live_at_preservation', ROOT / 'studio')]:
        row[label + '_sha256'] = digest(base / name)
        row[label + '_matches'] = row[label + '_sha256'] == expected
    for label, commit in [('checkpoint', CHECKPOINT), ('admission_head', HEAD)]:
        row[label + '_git_blob_sha256'] = git_digest(commit, name)
        row[label + '_git_blob_matches'] = row[label + '_git_blob_sha256'] == expected
    assert all(value for key, value in row.items() if key.endswith('_matches')), name
    source_rows.append(row)
project_rows = []
for map_name in ['initial-project-files.json', 'editor-snapshot.json']:
    for name, expected in sorted(read(ATTEMPT / map_name).items()):
        actual = digest(ATTEMPT / 'project' / name)
        project_rows.append(dict(map=map_name, path=name, expected_sha256=expected, actual_sha256=actual,
                                 matches=actual == expected))
project_mismatches = [row for row in project_rows if not row['matches']]
assert len(project_mismatches) == 2 and all(row['path'] == 'scenes/fixture.tscn' for row in project_mismatches)
binary_rows = []
for role in ['host-owner', 'editor-host', 'import-host']:
    invocation = read(ATTEMPT / role / 'invocation.json')
    actual = digest(Path(invocation['argv'][0]))
    assert actual == invocation['binary_sha256']
    binary_rows.append(dict(role=role, path=invocation['argv'][0], expected_sha256=invocation['binary_sha256'], actual_sha256=actual))
assert digest(ATTEMPT / 'toolchain.lock.json') == campaign['toolchain_sha256']

# Preserve all supervisor files and every direct run/owner record plus benchmark
# protocol input/output. Source/project/cache copies remain solely in raw roots.
selected = set(p for p in CAMPAIGN.iterdir() if p.is_file())
selected.update(p for p in ATTEMPT.iterdir() if p.is_file())
for role in ['host-owner', 'editor-host', 'import-host']:
    selected.update(p for p in (ATTEMPT / role).iterdir() if p.is_file())
selected.update(p for p in (ATTEMPT / 'project/benchmark').rglob('*') if p.is_file())
selected.add(ATTEMPT / 'project/scenes/fixture.tscn')
selected.update(p for p in SUPERVISOR.rglob('*') if p.is_file())
for source in sorted(selected):
    secret_screen(source.read_bytes(), source.name)

slots = []
for index in range(10):
    for attempt in range(1, 4):
        path = CAMPAIGN / f'run-{index:02d}-attempt-{attempt:02d}'
        slots.append(dict(path=path.relative_to(CAMPAIGN).as_posix(), exists=os.path.lexists(path),
                          stop_request_lexists=os.path.lexists(path / 'stop-request.json'),
                          run_capture_exists=os.path.lexists(path / 'run-capture.json')))
assert sum(s['exists'] for s in slots) == 1
assert not any(s['stop_request_lexists'] or s['run_capture_exists'] for s in slots)
stop_paths = [dict(root=kind, path=r['path']) for kind, rows in raw.items()
              for r in rows if Path(r['path']).name == 'stop-request.json']
assert not stop_paths and not os.path.lexists(SUPERVISOR / 'stop-request.json')

host_exit = read(ATTEMPT / 'host-owner/process-exit.json')
editor_start = read(ATTEMPT / 'editor-host/process-start.json')
host_cleanup = read(ATTEMPT / 'host-owner/cleanup-001.json')
editor_cleanup = read(ATTEMPT / 'editor-host/cleanup-001.json')
import_capture = read(ATTEMPT / 'import-host/capture.json')
parent_failure = read(ATTEMPT / 'parent-failure.json')
assert host_exit == {'pid': 4132, 'exit_code': 1}
assert editor_start == {'pid': 48332}
assert import_capture['actual_process_exit'] == {'pid': 34776, 'exit_code': 0}
assert parent_failure['owned_tree_zero'] and parent_failure['owner_closed'] and parent_failure['cleanup_error'] is None
cleanup_checks = []
for role, record in [('host', host_cleanup), ('editor', editor_cleanup), ('import', import_capture)]:
    job = record['job']
    clean = job['assigned'] and job['configured'] and job['active_count'] == 0 and job['zero_observed'] and job['closed'] and not any(
        job[k] for k in ['handle_retained', 'tainted', 'create_uncertain', 'close_uncertain', 'failed_operations', 'native_error'])
    wrapper = record.get('wrapper_process_handle')
    handles = wrapper['closed'] and not wrapper['handle_retained'] and not wrapper['close_uncertain'] if wrapper else None
    assert clean and handles is not False
    cleanup_checks.append(dict(role=role, job_zero_closed_without_uncertainty=clean,
                              wrapper_handle_closed_without_uncertainty=handles,
                              note='Import capture has no explicit wrapper_process_handle receipt' if wrapper is None else None))
for name, expected in import_capture['artifacts'].items():
    assert digest(ATTEMPT / 'import-host' / name) == expected
verify_ref(terminal['context'])
obs = terminal['observations']
for role in ['editor_target', 'import_target']:
    verify_ref(obs[role]['start'])
    if obs[role]['exit']:
        verify_ref(obs[role]['exit'])
assert obs['editor_target']['actual_target_exit'] is None and obs['editor_target']['exit'] is None
assert obs['editor_target']['natural_exit_not_inferred'] and obs['editor_target']['missing_reason'] == 'TARGET_EXIT_NOT_RECORDED'
assert obs['editor_owner']['helper_pid'] == 22376 and obs['editor_owner']['helper_exit_code'] == editor_cleanup['wrapper_exit_code'] == 2
assert obs['editor_owner']['closed'] and not any(obs['editor_owner']['drain_threads_alive'])
assert obs['editor_owner']['job'] == editor_cleanup['job']
assert obs['editor_owner']['wrapper_process_handle'] == editor_cleanup['wrapper_process_handle']
assert terminal['errors'] == [] and not obs['heartbeat_alive']
producer = obs['producer']
assert producer['present'] and producer['closed'] and producer['failed']
assert all(producer['host'][k] for k in ['closing', 'control_socket_closed', 'main_socket_closed', 'stopped'])
assert not any(producer['host']['threads_alive'])
assert producer['journal']['cache_closed'] and not any(producer['journal'][k] for k in ['database_retained', 'directory_retained', 'index_retained'])
for probe in [obs['editor_probe'], producer['observer_probe']]:
    assert probe['present'] and not probe['handle_retained'] and not probe['close_uncertain']
assert terminal['host_actual_exit'] is None and terminal['supervisor_actual_exit'] is None

supervisor_start = read(SUPERVISOR / 'start.json')
supervisor_return = read(SUPERVISOR / 'return.json')
request = read(SUPERVISOR / 'request.json')
registration = read(SUPERVISOR / 'task-registration.json')
task_start = read(SUPERVISOR / 'task-start.json')
assert digest(SUPERVISOR / 'request.json') == supervisor_start['request_sha256'] == registration['request_sha256'] == task_start['request_sha256']
assert digest(SUPERVISOR / 'task-definition.xml') == (SUPERVISOR / 'task-definition.sha256').read_text().strip() == registration['task_definition_sha256'] == task_start['task_definition_sha256']
assert request['script_sha256'] == supervisor_start['supervisor_script_sha256'] == sources['tests/replay/run_campaign_task.py']
assert supervisor_return['returned_exit_code'] == 1 and supervisor_return['actual_process_exit_not_yet_observed']
owned_pids = [4132, 48332, 34776, 22376, supervisor_start['pid']]
matched_processes = [p for p in processes if p['ProcessId'] in owned_pids]
assert matched_processes == []
absent_names = ['editor-host/process-exit.json', 'editor-host/capture.json', 'host-owner/capture.json',
                'child-result.json', 'cleanup.json', 'assembly-manifest.json', 'assembled-run.json', 'run-capture.json',
                'command-16.json', 'batch-capture-16.json', 'joint-16.json', 'sample-preview-16.json',
                'project/benchmark/out/index.json', 'project/benchmark/input/start-16.json',
                'project/benchmark/input/ack-16.json', 'project/benchmark/out/batch-16.json']
absent = {name: not os.path.lexists(ATTEMPT / name) for name in absent_names}
campaign_absent = {name: not os.path.lexists(CAMPAIGN / name) for name in ['campaign-capture.json', 'dataset.json', 'summary.json']}
assert all(absent.values()) and all(campaign_absent.values())

samples = [read(p) for p in sorted(ATTEMPT.glob('sample-preview-*.json'))]
assert [s['index'] for s in samples] == list(range(16))
assert len(list(ATTEMPT.glob('batch-capture-*.json'))) == 16
baseline = samples[4]['memory']
assert baseline['editor']['objects']['value'] == 71128 and samples[15]['memory']['editor']['objects']['value'] == 71130
screens, references, prefix = [], [], []
for index, sample in enumerate(samples):
    capture = read(ATTEMPT / f'batch-capture-{index:02d}.json')
    assert capture['index'] == index
    assert sample['evidence_sha256'] == digest(ATTEMPT / f'batch-capture-{index:02d}.json')
    for kind, ref in capture.items():
        if kind != 'index':
            verify_ref(ref)
            references.append(dict(batch=index, kind=kind, **ref))
    command = read(ATTEMPT / f'command-{index:02d}.json')
    native = read(ATTEMPT / f'project/benchmark/out/batch-{index:02d}.json')
    joint = read(ATTEMPT / f'joint-{index:02d}.json')
    assert command['index'] == native['index'] == joint['index'] == index
    assert command['complete_command_mix'] and len(command['commands']) == 1000
    counts = dict(collections.Counter(row['kind'] for row in command['commands']))
    assert counts == {'inspect': 500, 'rejected': 300, 'admitted': 200}, counts
    assert len(native['cycles']) == len(sample['cycles']) == 100
    assert all(cycle['saved_file_sha256'] == project_mismatches[0]['actual_sha256'] for cycle in native['cycles'])
    assert joint['source_closure_sha256'] == EXPECTED and joint['profile_sha256'] == PROFILE
    assert joint['processes'] == sample['processes'] == samples[0]['processes']
    assert native['pid'] == 48332
    assert sample['warmup'] == (index < 5)
    cancel = command['cancel']
    assert cancel['status'] == cancel['terminal_status'] == 'CANCELED'
    assert cancel['no_effect'] is True and cancel['terminal_response']['postconditions']['no_effect'] is True
    assert cancel['terminal_response']['code'] == 'CANCELED_BEFORE_APPLY'
    assert cancel['command_id'] == sample['stop_target_instance_id']
    assert cancel['receipt_ms'] == sample['stop_receipt_ms']
    prefix.append(dict(index=index, commands=len(command['commands']), command_mix=counts, native_cycles=len(native['cycles']),
                       stop_target=cancel['command_id'], cancel_status=cancel['status'], no_effect=True))
    breaches = []
    for role, names in [('host', ['held_handles', 'rss_bytes']), ('editor', ['rss_bytes', 'held_handles', 'objects', 'resources'])]:
        for name in names:
            value, reference = sample['memory'][role][name]['value'], baseline[role][name]['value']
            exceeded = value * 100 > reference * 110 if name == 'rss_bytes' else value > reference
            if index >= 5 and exceeded:
                breaches.append(dict(role=role, metric=name, value=value, baseline=reference))
    if index >= 5 and sample['max_status_gap_ms'] > 2000:
        breaches.append(dict(metric='max_status_gap_ms', value=sample['max_status_gap_ms'], limit=2000))
    screens.append(dict(index=index, warmup=sample['warmup'], memory=sample['memory'],
                        max_status_gap_ms=sample['max_status_gap_ms'], stop_receipt_ms=sample['stop_receipt_ms'],
                        screen_breaches=breaches))
assert len(references) == 96 and len({r['stop_target'] for r in prefix}) == 16

copies = []
for source in sorted(selected):
    kind = 'campaign' if source.is_relative_to(CAMPAIGN) else 'supervisor'
    base = CAMPAIGN if kind == 'campaign' else SUPERVISOR
    relative = source.relative_to(base).as_posix()
    expected = maps[kind][relative]
    destination = f'raw/{kind}/{relative}'
    data = source.read_bytes()
    assert len(data) == expected['bytes'] and hashlib.sha256(data).hexdigest() == expected['sha256']
    write(destination, data)
    assert digest(OUT / destination) == expected['sha256']
    copies.append(dict(path=destination, raw_root=kind, raw_path=relative, bytes=len(data), sha256=expected['sha256']))
copy_keys = {(r['raw_root'], r['raw_path']) for r in copies}
excluded = [dict(root=kind, path=r['path'], bytes=r['bytes'], sha256=r['sha256'],
                 reason='Raw locator only: frozen source, immutable project source, generated cache or retained diagnostic state; no bulky duplicate')
            for kind, rows in raw.items() for r in rows if (kind, r['path']) not in copy_keys]
assert all(('supervisor', r['path']) in copy_keys for r in raw['supervisor'])
assert raw == dict(campaign=inventory(CAMPAIGN), supervisor=inventory(SUPERVISOR)), 'Raw bytes, path set or mtimes changed'

write('raw-locator-hashmaps.json', dict(created_utc=utc(), roots=dict(campaign=str(CAMPAIGN), supervisor=str(SUPERVISOR)), files=raw,
    scope='Complete original file inventories, including caches and frozen source; originals retained read-only in place',
    hash_domain='SHA256 of exact file bytes; each row also binds size and mtime_ns; no path normalization of content',
    method='1 MiB stream reads, stable size/mtime, reject reparse points; full second inventory equals first'))
write('preserved-byte-manifest.json', dict(created_utc=utc(), files=copies, excluded_from_copy=excluded,
    scope='Exact unmodified evidence copies; all supervisor outputs; all direct campaign/run/owner records and benchmark protocol artifacts',
    source_and_cache_copy_policy='No frozen source trees or cache copied. One 294-byte serialized project scene is copied because its bytes differ from the initial/editor maps; all original files remain hash-addressed in raw inventory',
    secret_screen='No sensitive JSON key names or bearer/private-key/sk patterns found in selected files; limited pattern screen, not universal proof'))
write('source-map-verification.json', dict(created_utc=utc(), checkpoint=CHECKPOINT, admission_head=HEAD, source_files=51,
    source_closure_sha256=EXPECTED, profile_sha256=PROFILE,
    closure_algorithm='sha256(UTF8(concat(path + NUL + lowercase_file_sha256 + LF for path in sorted(map))))',
    files=source_rows, project_files=project_rows, binaries=binary_rows,
    all_frozen_checkpoint_head_and_live_match=True, all_project_maps_match=False,
    project_map_mismatches=project_mismatches,
    project_mismatch_scope='Serialized scenes/fixture.tscn matches all 1600 native cycle saved_file_sha256 records; this byte difference is not established as the retained-counter cause',
    campaign_context_source_map_profile_and_toolchain_bindings_match=True))
gaps = [
    'Editor 48332 natural/native exit is absent; helper 22376 exit 2 is distinct and never substituted.',
    'Supervisor return.json is a pre-exit returned-code record; no actual supervisor process-exit receipt. Scheduler state3/result1/no instances is separate.',
    'Import capture has Job zero/closed and actual exit0 but no explicit wrapper_process_handle receipt or helper PID inventory.',
    'Host wrapper return1 and closed handle are present; durable host helper PID inventory is absent.',
    '16 batch captures (5 warmup + 11 measured) include the failed retained-counter sample; 0 complete/full PASS runs. 19 measured batches missing from this attempted run; 10 fresh complete runs remain required.',
    'The +2 ObjectDB retained-counter cause is not established by this forensic packet.',
    'scenes/fixture.tscn differs from both initial-project and editor-snapshot maps; its actual hash matches all 1600 native cycle saved-file receipts. Exact scene bytes are retained, without an unchanged-project claim.',
    'Source/cache/project originals excluded from copies are required for full raw replay verification; this is not a standalone portable full raw archive.',
    'No engine run, test execution, independent acceptance critic or GT-06 acceptance performed by this preservation task.'
]
write('terminal-facts.json', dict(schema='HH-GT06-S82-S81-FAILURE-PRESERVATION-1', observed_utc=utc(), authority=0,
    formal_acceptance=False, campaign_status='FAILED_PARTIAL', failure=failure, completed_full_runs=0,
    scheduler=scheduler, scheduler_is_not_actual_exit=True, process_snapshot_is_not_natural_exit=True,
    recorded_pids=owned_pids, recorded_pids_present_in_snapshot=matched_processes,
    native_engine_processes_in_snapshot=[p for p in processes if any(n in p['Name'].lower() for n in ['godot', 'blender'])],
    host_actual_target_exit=host_exit, editor_actual_target_start=editor_start, editor_actual_target_exit=None,
    editor_helper_pid=22376, editor_helper_exit_code=2, host_cleanup=host_cleanup, editor_cleanup=editor_cleanup,
    import_capture=import_capture, parent_failure=parent_failure, child_terminal_cleanup=terminal,
    supervisor_start=supervisor_start, supervisor_return=supervisor_return, supervisor_actual_target_exit=None,
    cleanup_static_checks=cleanup_checks, fixed_attempt_slots=slots, stop_latch_raw_paths=stop_paths,
    supervisor_stop_request_lexists=False, confirmed_attempt_absences=absent, confirmed_campaign_absences=campaign_absent,
    next_native_ready_exists=(ATTEMPT / 'project/benchmark/out/ready-16.json').is_file(), gaps=gaps))
write('completeness-and-screen.json', dict(created_utc=utc(), formal_acceptance=False,
    scope='Failure-prefix integrity and retained-counter/status screens only; no benchmark PASS or latency acceptance',
    captured_batch_indexes=list(range(16)), warmup_batches=5, measured_captures_including_failed_batch=11,
    completed_full_runs=0, required_full_runs=10, missing_measured_batches_this_attempt=19,
    baseline_batch=4, failure_batch=15, samples=screens, prefix_records=prefix,
    batch_references=references, operator_stop_slots_checked=30, operator_stop_latches_present=0))
write('verification.json', dict(created_utc=utc(), started_utc=started, status='PRESERVATION_VERIFIED', formal_acceptance=False,
    raw_files=sum(map(len, raw.values())), raw_bytes=sum(r['bytes'] for rows in raw.values() for r in rows),
    raw_root_counts={k: len(v) for k, v in raw.items()}, raw_before_after_equal=True,
    exact_copies=len(copies), copied_bytes=sum(r['bytes'] for r in copies), excluded_copy_files=len(excluded),
    supervisor_files_copied=len(raw['supervisor']), source_files=51, source_closure_sha256=EXPECTED,
    profile_sha256=PROFILE, batch_reference_count=96, command_rows=16000, native_cycle_rows=1600,
    per_batch_cancel_receipts=16, operator_stop_slots=30, completed_full_runs=0, gaps=gaps))
print(json.dumps(dict(status='PRESERVATION_VERIFIED', raw_files=sum(map(len, raw.values())), copies=len(copies),
    source_files=51, captured_batches=16, complete_runs=0, measured_screen_breaches=[s for s in screens if s['screen_breaches']])))
