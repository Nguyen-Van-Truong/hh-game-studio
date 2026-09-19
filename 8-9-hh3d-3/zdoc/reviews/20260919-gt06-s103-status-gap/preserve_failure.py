"""Seal terminal S102; preserve all raw bytes, distinguish portable subset."""
from pathlib import Path
import hashlib
import json
import stat

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
RAW = ROOT / 'studio/.local/reviews/gt06-s102-campaign-01'
PACK = BASE / 'failure'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def regular(path):
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode) and info.st_nlink == 1
    assert not getattr(info, 'st_file_attributes', 0) & 0x400
    data = path.read_bytes()
    assert len(data) == info.st_size and path.stat().st_mtime_ns == info.st_mtime_ns
    return data


def main():
    assert not PACK.exists(), 'Do not overwrite evidence'
    child = RAW / 'run-00-attempt-01'
    failure, terminal, parent = (read(child / name) for name in
        ('child-failure.json', 'child-terminal-cleanup.json', 'parent-failure.json'))
    assert failure['code'] == 'CAMPAIGN_STATUS_GAP' and failure['phase']['batch'] == 6
    assert parent['owned_tree_zero'] and parent['owner_closed'] and parent['cleanup_error'] is None
    assert terminal['errors'] == []
    status = read(BASE / 'scheduler-terminal-01.json')
    assert status['scheduler']['state'] == 3 and status['scheduler']['last_task_result'] == 1
    assert not status['scheduler']['instances'] and all(not p['live'] for p in status['owned_processes'])
    pins = read(RAW / 'campaign.json')
    for name, digest in pins['source_files'].items():
        assert sha(regular(ROOT / 'studio' / name)) == digest, name
    stops = [f'run-{i:02d}-attempt-{a:02d}/stop-request.json'
             for i in range(10) for a in range(1, 4)]
    stop_present = [name for name in stops if (RAW / name).exists()]
    files, portable, excluded = {}, {}, {}
    PACK.mkdir()
    for domain, folder in [('raw', RAW), ('supervisor', RAW.with_name(RAW.name + '-supervisor'))]:
        for path in sorted(folder.rglob('*')):
            if not path.is_file():
                continue
            data = regular(path)
            name = domain + '/' + path.relative_to(folder).as_posix()
            target = PACK / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(data)
            assert target.read_bytes() == data
            row = {'sha256': sha(data), 'size_bytes': len(data),
                   'source': path.relative_to(ROOT).as_posix()}
            files[name] = row
            reason = None
            if path.suffix == '.jsonl' or 'commands' in path.parts:
                reason = 'LOCAL_JOURNAL_OR_COMMAND_STORE'
            elif any(part in path.parts for part in ('__pycache__', '.godot', 'appdata', 'localappdata')):
                reason = 'LOCAL_GENERATED_CACHE'
            if reason:
                excluded[name] = dict(row, reason=reason)
            else:
                portable[name] = row
    command = read(child / 'command-06.json')
    sample = read(child / 'sample-preview-06.json')
    joint = read(child / 'joint-06.json')
    phases = read(child / 'http-phases-final.json')['observation']
    value = {'schema': 'HH-S103-S102-STATUS-GAP-FAILURE-1', 'authority': 0,
        'formal_acceptance': False, 'eligible_for_dataset': False,
        'source_closure_sha256': pins['source_closure_sha256'], 'profile_sha256': pins['profile_sha256'],
        'source_files_current_bytes_verified': pins['source_files'],
        'failure': failure, 'host_max_status_gap_ms': command['max_status_gap_ms'],
        'joint_max_status_gap_ms': sample['max_status_gap_ms'],
        'native_barrier_max_status_gap_ms': joint['barrier_receipt']['max_status_gap_ms'],
        'http_transport_failures': phases['transport_failures_observed'],
        'http_first_failure_available': phases['first_failure'] is not None,
        'host_actual_exit': read(child / 'host-owner/process-exit.json'),
        'editor_actual_exit': None, 'editor_exit_missing_reason': 'TARGET_EXIT_NOT_RECORDED',
        'editor_helper_exit': terminal['observations']['editor_owner']['helper_exit_code'],
        'supervisor_actual_exit': None, 'supervisor_exit_missing_reason': 'NO_INDEPENDENT_EXIT_RECEIPT',
        'stop_fixed_slots': len(stops), 'stop_present': stop_present,
        'raw_files': files, 'portable_files': portable, 'local_excluded': excluded,
        'scope': 'Seven captured batches (including failed b6), no full run or accepted sample. Raw and portable domains distinct.'}
    output = PACK / 'manifest.json'
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
    for name, row in files.items():
        assert sha(regular(PACK / name)) == row['sha256']
    print(json.dumps({'raw': len(files), 'portable': len(portable), 'excluded': len(excluded),
        'manifest_sha256': sha(output.read_bytes()), 'host_gap': value['host_max_status_gap_ms'],
        'native_gap': value['native_barrier_max_status_gap_ms']}))


if __name__ == '__main__':
    main()
