"""Read-only raw audit; exclusive new portable evidence writes. No runtime imports."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path.cwd() / '8-9-hh3d-3'
RAW = ROOT / 'studio/.local/reviews/gt06-s81-cleanup-probe-01'
OUT = Path(__file__).resolve().parent
assert OUT == ROOT / 'zdoc/reviews/20260918-gt06-s81-admission/native-cleanup-probe/evidence'


def now():
    return datetime.now(timezone.utc).isoformat()


def fingerprint(path):
    before = path.stat()
    assert not path.is_symlink() and not getattr(before, 'st_file_attributes', 0) & 0x400
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), path
    return {'sha256': digest.hexdigest(), 'size_bytes': before.st_size, 'mtime_ns': before.st_mtime_ns}


def inventory(root):
    result = {}
    for path in sorted(root.rglob('*')):
        assert not path.is_symlink() and not getattr(path.lstat(), 'st_file_attributes', 0) & 0x400
        if path.is_file():
            result[path.relative_to(root).as_posix()] = fingerprint(path)
    return result


def write(name, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    data = value.encode('utf-8') if isinstance(value, str) else (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
    with path.open('xb') as handle:
        handle.write(data)


def read(name):
    return json.loads((RAW / name).read_bytes())


def closure(files):
    return hashlib.sha256(''.join(name + '\0' + files[name] + '\n' for name in sorted(files)).encode()).hexdigest()


def clean_job(job):
    assert job['closed'] is True and job['zero_observed'] is True and job['active_count'] == 0
    assert job['assigned'] is True and job['configured'] is True
    assert all(not job[key] for key in ('handle_retained', 'tainted', 'create_uncertain',
                                      'close_uncertain', 'failed_operations', 'native_error'))


def clean_handle(handle):
    assert handle == {'required': True, 'closed': True, 'close_uncertain': False, 'handle_retained': False}


started = now()
before = inventory(RAW)
request = read('probe-request.json')
outer = read('probe-outer-result.json')
capture = read('probe-owner/capture.json')
result = read('child/probe-result.json')
terminal = read('child/child-terminal-cleanup.json')
context = read('child/context.json')
failure = read('child/child-failure.json')
injection = read('child/injection.json')
ready = read('child/project/benchmark/out/ready-00.json')
imported = read('child/import-host/capture.json')
editor_cleanup = read('child/editor-host/cleanup-001.json')
outer_cleanup = read('probe-owner/cleanup-001.json')
source = read('child/source-files.json')
execution = request['execution_files']
assert source == context['source_files'] == request['source_files']
assert closure(source) == context['source_closure_sha256'] == request['source_closure_sha256']
assert closure(execution) == request['execution_closure_sha256']
assert context['campaign_sha256'] == before['probe-request.json']['sha256']
assert {f'studio/{name}': digest for name, digest in source.items()}.items() <= execution.items()
assert execution == outer['source_after'] == capture['source_files']
source_before = {name: fingerprint(ROOT / name) for name in execution}
for name, digest in execution.items():
    assert source_before[name]['sha256'] == before['source/' + name]['sha256'] == digest, name

refs = []


def check_refs(value, base, record, trail=''):
    if isinstance(value, dict):
        if {'file', 'sha256', 'size_bytes'} <= value.keys():
            name = (Path(base) / value['file']).as_posix()
            assert '..' not in Path(name).parts and not Path(name).is_absolute()
            assert before[name]['sha256'] == value['sha256'] and before[name]['size_bytes'] == value['size_bytes']
            refs.append({'record': record, 'field': trail, 'raw_file': name, **value})
        for key, item in value.items():
            check_refs(item, base, record, trail + '/' + key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            check_refs(item, base, record, trail + '/' + str(index))


for record, base in [('probe-outer-result.json', ''), ('child/probe-result.json', 'child'),
                     ('child/child-terminal-cleanup.json', 'child'), ('child/injection.json', 'child')]:
    check_refs(read(record), base, record)
for record in ['probe-owner/capture.json', 'child/import-host/capture.json']:
    for name, digest in read(record)['artifacts'].items():
        target = (Path(record).parent / name).as_posix()
        assert before[target]['sha256'] == digest
        refs.append({'record': record, 'field': '/artifacts/' + name, 'raw_file': target, 'sha256': digest})
assert capture['invocation_sha256'] == before['probe-owner/invocation.json']['sha256']
for record in [outer, result]:
    assert record['status'] == 'CLEANUP_SMOKE_VERIFIED'
    assert record['formal_acceptance'] is False and record['full_benchmark'] is False and record['effects_claimed'] is False
    assert record['source_unchanged'] is True
for record in [terminal, context, ready]:
    assert record['run_id'] == result['run_id'] == 'gt06-s81-cleanup-probe-01.r00.a01'
    assert record['source_closure_sha256'] == request['source_closure_sha256']
    assert record['profile_sha256'] == request['profile_sha256'] == before['child/benchmark-profile.json']['sha256']
assert result['injected_primary_preserved'] is True and result['original_cause_preserved'] is True
assert terminal['primary_error'] == {'stage': 'body', 'type': 'CommandError', 'code': 'S81_EXPECTED_CLEANUP_SMOKE'}
assert terminal['errors'] == [] and terminal['completed_batches'] == 0 and terminal['formal_acceptance'] is False
assert terminal['phase'] == {'batch': 0, 'phase': 'commands'}
assert failure['code'] == injection['code'] == terminal['primary_error']['code']
assert failure['completed'] is False and failure['completed_batches'] == 0 and failure['formal_acceptance'] is False
assert injection['commands_executed'] == injection['native_batches_executed'] == 0
assert injection['real_host_threads_alive'] == [True, True, True]
assert all(injection[key] is True for key in ('real_listeners_open', 'real_observer_probe_open', 'real_journal_index_open'))
assert all(not (RAW / 'child' / name).exists() for name in result['confirmed_absences'])
assert 'child/editor-host/process-exit.json' not in before
assert result['editor_actual_exit'] is None
observed, direct = terminal['observations'], result['direct_after_finally']
assert observed['editor_target']['actual_target_exit'] is None and observed['editor_target']['exit'] is None
assert observed['editor_target']['missing_reason'] == 'TARGET_EXIT_NOT_RECORDED'
assert terminal['host_actual_exit'] is None and terminal['supervisor_actual_exit'] is None
assert terminal['self_exit_missing_reason'] == 'NOT_OBSERVABLE_BY_CHILD_TERMINAL_RECORD'
observer_exit = read('probe-owner/process-exit.json')
import_exit = read('child/import-host/process-exit.json')
editor_start = read('child/editor-host/process-start.json')
assert observer_exit == outer['actual_observer_process_exit'] == capture['actual_process_exit'] == {'pid': result['observer_pid'], 'exit_code': 0}
assert read('probe-owner/process-start.json')['pid'] == observer_exit['pid']
assert import_exit == imported['actual_process_exit'] == result['import_actual_exit'] == observed['import_target']['actual_target_exit']
assert import_exit['exit_code'] == 0 and read('child/import-host/process-start.json')['pid'] == import_exit['pid']
assert ready['pid'] == editor_start['pid'] and ready['batch_index'] == 0
assert observed['editor_owner']['helper_pid'] == direct['editor_helper_pid']
assert observed['editor_owner']['helper_exit_code'] == direct['editor_helper_exit'] == result['editor_helper_exit'] == editor_cleanup['wrapper_exit_code'] == 2
assert capture['wrapper_exit_code'] == outer_cleanup['wrapper_exit_code'] == imported['wrapper_exit_code'] == 0
assert capture['natural_tree_exit'] is True and imported['natural_tree_exit'] is True
assert capture['active_at_wrapper_exit'] == capture['active_before_cleanup'] == imported['active_at_wrapper_exit'] == imported['active_before_cleanup'] == 0
for job in [capture['job'], outer['owner_job'], outer_cleanup['job'], imported['job'],
            editor_cleanup['job'], observed['editor_owner']['job'], direct['editor_job']]:
    clean_job(job)
for handle in [capture['wrapper_process_handle'], outer['owner_wrapper_handle'], outer_cleanup['wrapper_process_handle'],
               editor_cleanup['wrapper_process_handle'], observed['editor_owner']['wrapper_process_handle'], direct['editor_wrapper_handle']]:
    clean_handle(handle)
assert outer['owner_closed'] is True and outer['cleanup_failure_type'] is None and outer['failure_code'] is None
assert observed['heartbeat_alive'] is False and observed['editor_owner']['closed'] is True
assert observed['editor_owner']['drain_threads_alive'] == [False, False]
producer = observed['producer']
assert producer['closed'] is True and producer['failed'] is True
assert producer['host'] == {'stopped': True, 'closing': True, 'threads_alive': [False, False, False], 'main_socket_closed': True, 'control_socket_closed': True}
assert producer['journal'] == {'cache_closed': True, 'index_retained': False, 'database_retained': False, 'directory_retained': False}
assert observed['editor_probe'] == producer['observer_probe'] == {'present': True, 'handle_retained': False, 'close_uncertain': False}
assert direct['host_threads_alive'] == [False, False, False] and direct['listener_filenos'] == [-1, -1]
assert direct['held_owner_count'] == direct['held_probe_count'] == 0
for key in ('producer_closed', 'producer_failed', 'host_stopped', 'host_closing', 'host_probe_released',
            'editor_probe_released', 'journal_cache_closed', 'journal_index_detached',
            'retained_index_database_closed', 'retained_index_directory_released', 'editor_owner_closed'):
    assert direct[key] is True
assert direct['host_probe_close_uncertain'] is False and direct['editor_probe_close_uncertain'] is False
for lane in ['probe-owner', 'child/import-host', 'child/editor-host']:
    assert not (RAW / lane / 'stderr.txt').read_bytes().strip()
    assert not re.search(rb'\b(?:WARNING|ERROR)\b|ObjectDB instances leaked|HH_GT06_BENCHMARK_FAILED', (RAW / lane / 'stdout.txt').read_bytes())
assert request['wall_seconds'] == 120 and outer['elapsed_seconds'] < 120

selected = {name for name in before if name.startswith('source/')}
selected.update(name for name in before if len(Path(name).parts) == 1 and name.endswith('.json'))
for lane in ['probe-owner', 'child/import-host', 'child/editor-host']:
    selected.update(name for name in before if Path(name).parent.as_posix() == lane)
selected.update(name for name in before if Path(name).parent.as_posix() == 'child' and name.endswith('.json'))
initial = read('child/initial-project-files.json')
for name, digest in initial.items():
    target = 'child/project/' + name
    assert before[target]['sha256'] == digest
    selected.add(target)
selected.add('child/project/benchmark/out/ready-00.json')
for name in sorted(selected):
    assert not any(part in ('.godot', '__pycache__', 'appdata', 'localappdata') for part in Path(name).parts)
    assert Path(name).suffix.lower() not in ('.exe', '.dll', '.res', '.png', '.pyc')
    target = OUT / 'copies' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    digest, count = hashlib.sha256(), 0
    with (RAW / name).open('rb') as src, target.open('xb') as dst:
        for block in iter(lambda: src.read(1024 * 1024), b''):
            dst.write(block)
            digest.update(block)
            count += len(block)
    assert digest.hexdigest() == before[name]['sha256'] and count == before[name]['size_bytes']
    assert fingerprint(target)['sha256'] == before[name]['sha256']

known_pids = sorted({observer_exit['pid'], import_exit['pid'], editor_start['pid'], direct['editor_helper_pid']})
command = '$rows = @(Get-CimInstance Win32_Process -Filter "' + ' OR '.join('ProcessId=' + str(pid) for pid in known_pids) + '" | Select-Object ProcessId,ParentProcessId,Name,CreationDate); ConvertTo-Json -Depth 5 -InputObject $rows -Compress'
process_scan = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command], capture_output=True, text=True, timeout=30, check=True)
assert not process_scan.stderr.strip()
live = json.loads(process_scan.stdout)
write('known-process-observation.json', {'observed_utc': now(), 'scope': 'Read-only PID presence query; PID absence does not manufacture target exit.',
                                      'queried_pids': known_pids, 'present': live, 'query_exit': process_scan.returncode})
after = inventory(RAW)
source_after = {name: fingerprint(ROOT / name) for name in execution}
assert before == after, 'Raw changed during collection'
assert source_before == source_after, 'Execution source changed during collection'
raw_bytes = sum(item['size_bytes'] for item in before.values())
copy_bytes = sum(before[name]['size_bytes'] for name in selected)
write('.gitattributes', '* -text\n')
write('raw-inventory.json', {'schema': 'HH-GT06-S81-CLEANUP-RAW-INVENTORY-1', 'raw_root': RAW.relative_to(ROOT).as_posix(),
                          'started_utc': started, 'finished_utc': now(), 'before_after_equal': True,
                          'file_count': len(before), 'total_bytes': raw_bytes, 'files_before': before, 'files_after': after})
write('selected-manifest.json', {'schema': 'HH-GT06-S81-CLEANUP-SELECTED-1', 'file_count': len(selected), 'total_bytes': copy_bytes,
                               'copy_policy': 'Original root/child/owner receipts and logs; frozen execution source; initial project map plus native READY. No .godot, isolated-user generated caches, binaries, or generated benchmark UID copied.',
                               'files': {name: {key: before[name][key] for key in ('sha256', 'size_bytes')} for name in sorted(selected)},
                               'inventory_only': sorted(set(before) - selected)})
write('verification.json', {'schema': 'HH-GT06-S81-CLEANUP-INDEPENDENT-AUDIT-1', 'observed_utc': now(), 'status': 'SUPPLEMENTAL_CLEANUP_EVIDENCE_VERIFIED',
                         'formal_acceptance': False, 'full_benchmark': False, 'effects_claimed': False,
                         'runtime_file_count': len(source), 'execution_file_count': len(execution),
                         'runtime_closure_sha256': closure(source), 'execution_closure_sha256': closure(execution),
                         'execution_before': source_before, 'execution_after': source_after,
                         'checked_references': refs, 'checked_reference_count': len(refs),
                         'editor_actual_exit': None, 'editor_target_pid': editor_start['pid'],
                         'editor_helper_pid': direct['editor_helper_pid'], 'editor_helper_exit': 2,
                         'outer_target_exit': observer_exit, 'outer_helper_exit': capture['wrapper_exit_code'], 'outer_helper_pid': None,
                         'import_target_exit': import_exit, 'import_helper_exit': imported['wrapper_exit_code'], 'import_helper_pid': None,
                         'outer_shell_exit': None, 'outer_shell_exit_limitation': 'Coordinator reported 0; shell receipt not present in this raw root.',
                         'known_pids_present_at_collection': live,
                         'limitations': ['Offline audit cross-binds the in-process observations to the preserved driver and independently captured observer exit; it cannot recreate historical Python object identity.',
                                         'Import capture has no independent wrapper-process-handle receipt; do not infer one.',
                                         'Editor target exit is missing after forced cleanup; helper exit 2 is separate.',
                                         'Outer cleanup receipt completed=false is its post-close bookkeeping field; actual observer completion is bound in capture.json.']})
summary = f'''# Completed supplemental native cleanup smoke

AUTHORITY=0. This packet preserves one real cleanup smoke, not a benchmark PASS, GT-06 acceptance, critic verdict, command-effect proof or campaign completion.

The real child reached native READY at batch 0, then its first command-batch call deliberately raised `CommandError(S81_EXPECTED_CLEANUP_SMOKE)` from the original `RuntimeError("fixed synthetic cleanup stimulus")`. Zero command batches, native batches and effects are claimed. The original `child-failure.json` remains failed with zero completed batches; no child success or batch result exists. The hash-bound driver checked original exception/cause identity in process before reporting `CLEANUP_SMOKE_VERIFIED` and returning 0. Offline collection verified its preserved bytes, receipts, bindings and recorded outcome; it does not independently recreate historical object identity.

| Process | Actual target result | Separate helper result |
| --- | --- | --- |
| Outer diagnostic observer | PID {observer_exit['pid']}, exit 0 | exit 0; PID not recorded |
| Pinned import | PID {import_exit['pid']}, exit 0 | exit 0; PID not recorded |
| Real editor | PID {editor_start['pid']}; actual/natural exit **null**, no exit receipt | PID {direct['editor_helper_pid']}, exit 2 after forced cleanup |

The coordinator reported root shell exit 0; this raw directory contains no independent shell receipt. That reported value is not substituted for any target or helper exit. The child terminal record leaves its own host/supervisor exits null because those were unobservable from inside the child; the outer target exit is independently present in `probe-owner/process-exit.json`.

The outer observer and import captures show natural tree termination. Outer/editor/import Jobs each recorded active count 0, zero observed and closed, without retained/tainted/uncertain state. Outer/editor wrapper handles were recorded released. Import capture has no separate wrapper-handle receipt, so that observation remains unavailable. Editor cleanup remains `completed=false`, `BENCHMARK_CLOSED_BEFORE_FINISH`; the outer post-close cleanup receipt also uses `completed=false`, while its independently bound capture records actual observer completion.

The persisted terminal artifact matches the retained-object observations after original cleanup: heartbeat and editor drain threads stopped; three host threads stopped; both listeners at fileno -1; producer closed/failed; host/editor probe handles released without uncertainty; journal cache closed and index detached; retained SQLite index object's DB and directory handles released; held owner/probe counts zero. Terminal cleanup errors are empty. The PID presence snapshot found {len(live)} of the four known target/helper PIDs present at collection. Absence does not synthesize missing exit bytes.

Raw inventory: **{len(before)} files / {raw_bytes:,} bytes**, streamed twice with matching content/size/mtime and unchanged membership. Portable exact copies: **{len(selected)} files / {copy_bytes:,} bytes**. Inventory includes all generated cache bytes; copies exclude `.godot`, isolated-user generated caches, binaries and the generated benchmark UID. Initial project file hashes all remain equal because no command or native batch ran. **{len(refs)} artifact references** were independently checked against bytes; stderr is empty for all three logged lanes, with no warning/error/leak/failure marker in their stdout.

Runtime source: **{len(source)} files**, closure `{closure(source)}`. Execution source plus probe driver: **{len(execution)} files**, closure `{closure(execution)}`. All frozen source copies, request/context/capture maps and current execution files agree before/after collection. Profile SHA-256 is `{request['profile_sha256']}`. The observed interval was {outer['elapsed_seconds']:.3f}s under the 120s supplemental watchdog.

No unexpected collection mismatch was found. Missing target/helper identity details and the absent import wrapper-handle receipt above are explicit evidence limits. No source/raw files, engine processes, tests or scheduled tasks were changed by this collector.

See `raw-inventory.json`, `selected-manifest.json`, `verification.json`, `known-process-observation.json` and the byte-for-byte `copies/` tree. `package-manifest.json` seals all packet files except itself.
'''
write('summary.md', summary)
packet = inventory(OUT)
write('package-manifest.json', {'schema': 'HH-GT06-S81-CLEANUP-PORTABLE-PACKET-1', 'created_utc': now(),
                              'file_count': len(packet), 'total_bytes': sum(value['size_bytes'] for value in packet.values()),
                              'files': {name: {key: row[key] for key in ('sha256', 'size_bytes')} for name, row in packet.items()}})
print(json.dumps({'raw_files': len(before), 'raw_bytes': raw_bytes, 'copied_files': len(selected), 'copied_bytes': copy_bytes,
                  'artifact_refs': len(refs), 'package_files': len(packet), 'package_manifest_sha256': fingerprint(OUT / 'package-manifest.json')['sha256'],
                  'known_pids_present': live, 'runtime_closure': closure(source)}))
