"""Independent read-only byte verification; writes a new observation only."""
from pathlib import Path
import datetime
import hashlib
import json

root = Path(__file__).resolve().parent
load = lambda p: json.loads(p.read_bytes())

def digest(p):
    start = p.stat()
    value = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            value.update(block)
    end = p.stat()
    assert (start.st_size, start.st_mtime_ns) == (end.st_size, end.st_mtime_ns)
    return value.hexdigest()

inventory = load(root / 'raw-locator-hashmaps.json')
raw_count = 0
for key, rows in inventory['files'].items():
    base = Path(inventory['roots'][key])
    expected_names = {r['path'] for r in rows}
    actual_names = {p.relative_to(base).as_posix() for p in base.rglob('*') if p.is_file()}
    assert actual_names == expected_names, (key, 'inventory names changed')
    for row in rows:
        p = base / row['path']
        assert p.stat().st_size == row['bytes'] and p.stat().st_mtime_ns == row['mtime_ns']
        assert digest(p) == row['sha256']
        raw_count += 1
copies = load(root / 'preserved-byte-manifest.json')['files'] + load(root / 'preserved-byte-manifest-supplement.json')['files']
assert len({r['path'] for r in copies}) == len(copies)
for row in copies:
    p = root / row['path']
    assert p.stat().st_size == row['bytes'] and digest(p) == row['sha256']
source = load(root / 'source-map-verification.json')
mapping = {r['path']: r['expected_sha256'] for r in source['files']}
calculated = hashlib.sha256(''.join(p + '\0' + mapping[p] + '\n' for p in sorted(mapping)).encode()).hexdigest()
assert calculated == source['frozen_source_closure_sha256']
assert all(r['campaign_frozen_matches'] and r['attempt_frozen_matches'] and r['checkpoint_git_blob_matches'] for r in source['files'])
facts = load(root / 'terminal-facts.json')
assert facts['editor_actual_target_exit'] is None
assert facts['editor_cleanup']['wrapper_exit_code'] == 2
assert facts['host_actual_target_exit'] == {'pid': 34988, 'exit_code': 1}
assert facts['import_capture']['actual_process_exit'] == {'pid': 45648, 'exit_code': 0}
assert not facts['recorded_pids_present_in_snapshot']
assert not any(row['stop_request_lexists'] for row in facts['fixed_attempt_slots'])
prefix = []
raw_attempt = Path(inventory['roots']['campaign']) / 'run-00-attempt-01'
for index in range(15):
    command = load(raw_attempt / f'command-{index:02d}.json')
    cancel = command['cancel']
    assert cancel['status'] == cancel['terminal_status'] == 'CANCELED'
    assert cancel['no_effect'] is True and cancel['terminal_response']['postconditions']['no_effect'] is True
    assert len(command['commands']) == 1000 and command['complete_command_mix'] is True
    prefix.append({'index': index, 'command_count': len(command['commands']),
                   'cancel_target': cancel['command_id'], 'cancel_status': cancel['status'], 'no_effect': cancel['no_effect']})
assert len({r['cancel_target'] for r in prefix}) == 15
profile = raw_attempt / 'benchmark-profile.json'
assert profile.read_bytes() == (raw_attempt.parent / 'benchmark-profile.json').read_bytes()
partial = load(raw_attempt / 'child-failure.json')['partial_command']
report = {'schema': 'HH-GT06-S81-PRESERVATION-INDEPENDENT-1',
    'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'status': 'PRESERVATION_VERIFIED', 'formal_acceptance': False,
    'scope': 'Independent collector byte checks and Stop receipt inspection, not a native test or final critic verdict.',
    'raw_files': raw_count, 'copies': len(copies), 'source_files': len(mapping),
    'source_closure': calculated, 'profile_sha256': digest(profile), 'all_raw_hashes_and_mtimes_unchanged': True,
    'prefix_commands': sum(row['command_count'] for row in prefix), 'prefix_native_cycles': 1500,
    'completed_batches': 15, 'warmup_batches': 5, 'measured_batches': 10, 'complete_runs': 0,
    'per_batch_cancel_receipts': prefix, 'operator_stop_slots_absent': 30,
    'failed_partial_command_rows': len(partial['commands']), 'failed_partial_last_command': partial['commands'][-1],
    'missing_editor_natural_exit_preserved': True, 'editor_wrapper_exit_is_not_native_exit': True}
with (root / 'verification-independent.json').open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({k: report[k] for k in ['status', 'raw_files', 'copies', 'source_files', 'completed_batches', 'complete_runs']}))
