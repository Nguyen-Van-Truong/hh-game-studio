"""Compose the fixed fault -> managed editor repair -> immutable native replay."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.replay import native_runner as native
from studio.host.replay.repair import verified_fault
from studio.host.replay.observation import validate_observation
from studio.host.replay.trace import validate_trace


def verifier_sources():
    return {name: native.sha(native.read_regular(STUDIO / ('host/replay/' + name)))
        for name in ('repair_replay.py', 'repair.py', 'observation.py', 'trace.py')}


def verified_repair(root: Path, expected_hash: str):
    raw = native.read_regular(root / 'capture.json')
    native.need(native.sha(raw) == expected_hash, 'REPLAY_REPAIR_CAPTURE_HASH')
    capture = json.loads(raw)
    host = capture['host']
    native.need(capture['completed'] is True and capture['source_unchanged'] is True
        and host['exit_code'] == host['wrapper_exit_code'] == 0
        and host['timed_out'] is False and host['tree_verified'] is True, 'REPLAY_REPAIR_INCOMPLETE')
    for name, digest in capture['artifacts'].items():
        native.need(type(name) is str and name == Path(name).name and '/' not in name
                    and '\\' not in name and ':' not in name, 'REPLAY_REPAIR_ARTIFACT_PATH')
        native.need(native.sha(native.read_regular(root / name)) == digest, 'REPLAY_REPAIR_ARTIFACT_HASH')
    needed = {'repair.json', 'selected-config.gd', 'selected-manifest.json', 'native-readback.json',
        'response-wire.json', 'request.json', 'events.json', 'before-script.json', 'after.json',
        'editor-close-0.json', 'editor-close-1.json', 'repair-host.json', 'source-files.json', 'repair-stdout.txt',
        'repair-terminal-cleanup.json'}
    native.need(needed <= set(capture['artifacts']), 'REPLAY_REPAIR_ARTIFACT_SET')
    report = json.loads(native.read_regular(root / 'repair.json'))
    cleanup = json.loads(native.read_regular(root / 'repair-terminal-cleanup.json'))
    native.need(cleanup['schema'] == 'HH-GT06-REPAIR-CLEANUP-1'
                and cleanup['primary'] is None and cleanup['cleanup_clean'] is True
                and cleanup['owner_closed'] is True and cleanup['transport_closed'] is True
                and cleanup['cleanup_errors'] == 0, 'REPLAY_REPAIR_CLEANUP')
    # Empty stderr is normal, so the producer's nonempty-artifact map omits it.
    # Still read and check the actual file, including reparse protection.
    stderr_path = root / 'repair-stderr.txt'
    for part in (stderr_path, *stderr_path.parents):
        info = part.lstat()
        native.need(not part.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
                    'REPLAY_REPAIR_LOG_PATH')
    native.need(stderr_path.is_file() and stderr_path.stat().st_size == 0, 'REPLAY_REPAIR_LOG_ERROR')
    stdout = native.read_regular(root / 'repair-stdout.txt')
    native.need(not re.search(rb'\b(?:WARNING|ERROR)\b|\bError:', stdout), 'REPLAY_REPAIR_LOG_ERROR')
    markers = [json.loads(row.split(' ', 1)[1]) for row in stdout.decode('utf-8').splitlines()
        if row.startswith('HH_GT06_REPAIR_COMPLETE ')]
    native.need(len(markers) == 1 and markers[0] == report, 'REPLAY_REPAIR_MARKER')
    actual_host = json.loads(native.read_regular(root / 'repair-host.json'))
    native.need(actual_host['exit_code'] == 0 and actual_host['target_pid'] == host['target_pid'], 'REPLAY_REPAIR_HOST')
    source_map = json.loads(native.read_regular(root / 'source-files.json'))
    native.need(native.closure(source_map) == capture['source_closure_sha256'] == report['source_closure_sha256'],
                'REPLAY_REPAIR_SOURCE')
    for index, (name, digest) in enumerate(source_map.items()):
        native.need(native.sha(native.read_regular(root / 'source' / (str(index) + Path(name).suffix))) == digest,
                    'REPLAY_REPAIR_SOURCE_BYTES')
    config = native.read_regular(root / 'selected-config.gd')
    native.need(config == native.configuration('3.0') and native.sha(config) == report['selected_config_sha256'],
                'REPLAY_REPAIR_SELECTED_BYTES')
    readback = json.loads(native.read_regular(root / 'native-readback.json'))['script']
    native.need(readback['source_sha256'] == readback['disk_sha256'] == native.sha(config)
                and readback['defaults']['move_speed']['value'] == 3.0, 'REPLAY_REPAIR_NATIVE_CONFIG')
    response_raw = native.read_regular(root / 'response-wire.json')
    response = json.loads(response_raw)
    native.need(native.sha(response_raw) == report['response_sha256'] and response['status'] == 'COMMITTED'
                and response['code'] == 'GODOT_MANAGED_SCRIPT_REPLACED'
                and response['postconditions']['public_ack'] is True, 'REPLAY_REPAIR_COMMITTED')
    native.need(report['managed_script_repaired'] is True, 'REPLAY_REPAIR_NOT_OBSERVED')
    return config, report


def run(run_id, repair_id, expected_repair_hash):
    before = verifier_sources()
    for value in (run_id, repair_id):
        native.need(re.fullmatch('gt06-[a-z0-9-]{1,80}', value), 'REPLAY_REPAIR_RUN_ID')
    repair_root = STUDIO / '.local/reviews' / repair_id
    config, receipt = verified_repair(repair_root, expected_repair_hash)
    fault_id = receipt['fault_binding']['run_id']
    native.need(re.fullmatch('gt06-[a-z0-9-]{1,80}', fault_id), 'REPLAY_REPAIR_FAULT_RUN_ID')
    fault_root = STUDIO / '.local/reviews' / fault_id
    _, fault_capture, fault_checks = verified_fault(fault_root, receipt['fault_capture_sha256'])
    trace = validate_trace(native.read_regular(fault_root / 'project/input/trace.json'))
    binding = {'repair_capture_sha256': expected_repair_hash,
        'selected_config_sha256': native.sha(config), 'fault_capture_sha256': receipt['fault_capture_sha256']}
    result = native.run(run_id, speed='3.0', seed=trace.value['seed'], config_bytes=config, repair_binding=binding)
    root = STUDIO / '.local/reviews' / run_id
    native.need(result['binding']['trace_sha256'] == fault_capture['binding']['trace_sha256']
                and result['binding']['glb_sha256'] == fault_capture['binding']['glb_sha256'], 'REPLAY_REPAIR_INPUT_CHANGED')
    project = root / 'project'
    checks = validate_observation(native.read_regular(project / 'out/report.json'), trace=trace,
        binding=result['binding'], config_speed=3.0, project=project,
        process=json.loads(native.read_regular(root / 'process-metrics.json')))
    native.need(checks['all_postconditions'] is True and checks['movement_fault_observed'] is False,
                'REPLAY_REPAIR_POSTCONDITION')
    native.need(verifier_sources() == before, 'REPLAY_REPAIR_VERIFIER_CHANGED')
    proof = {'schema': 'HH-GT06-REPAIR-REPLAY-1', 'managed_repair_proven': True,
        'formal_acceptance': False, 'binding': binding,
        'native_capture_sha256': native.sha(native.read_regular(root / 'capture.json')),
        'verifier_sources': before,
        'fault_checks': fault_checks, 'replay_checks': checks}
    native.write(root / 'repair-replay.json', proof)
    print(json.dumps({'managed_repair_proven': True, 'formal_acceptance': False, 'run_id': run_id}))
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--repair-run', required=True)
    parser.add_argument('--repair-capture-sha256', required=True)
    args = parser.parse_args()
    run(args.run_id, args.repair_run, args.repair_capture_sha256)
