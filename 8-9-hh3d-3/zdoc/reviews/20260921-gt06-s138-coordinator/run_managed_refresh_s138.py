"""Fresh owned repair/replay using the verified historical S65 fault input.

Each explicit lane runs once. --verify-existing performs no process launch.
Current execution/source pins and historical fault provenance remain separate.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import re
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
STUDIO = ROOT / 'studio'
OUTPUT = BASE / 'managed-refresh-01'
FAULT = 'gt06-s65-native-04'
FAULT_SHA = 'd3469bee92f7decad37d1f937631cff467548c8751f03ca99eac029c7547b7a1'
REPAIR = 'gt06-s138-managed-repair-01'
REPLAY = 'gt06-s138-managed-replay-01'
sys.path.insert(0, str(ROOT))
from studio.host.replay import native_runner as native
from studio.host.replay import repair, repair_replay


def sha(path):
    return hashlib.sha256(native.execution_installed.binding._read(path, 256 * 1024 * 1024)).hexdigest()


def read(path):
    return json.loads(native.execution_installed.binding._read(path, 8 * 1024 * 1024))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(native.encoded(value))


def freeze():
    _, accepted = native.accepted_inputs()
    files = native.sources(accepted)
    if not (OUTPUT / 'freeze.json').exists():
        OUTPUT.mkdir(exist_ok=False)
        for name in files:
            p = OUTPUT / 'source' / name
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open('xb') as stream:
                stream.write(native.read_regular(STUDIO / name))
        write(OUTPUT / 'freeze.json', {'source_files': files,
              'source_closure_sha256': native.closure(files), 'launcher_sha256': sha(Path(__file__)),
              'python_executable': sys.executable, 'python_sha256': sha(Path(sys.executable)),
              'fault_run': FAULT, 'fault_capture_sha256': FAULT_SHA,
              'accepted_manifest_sha256': native.MANIFEST_SHA, 'formal_acceptance': False})
    proof = read(OUTPUT / 'freeze.json')
    native.need(proof['source_files'] == files and proof['source_closure_sha256'] == native.closure(files)
                and proof['launcher_sha256'] == sha(Path(__file__))
                and proof['python_executable'] == sys.executable
                and proof['python_sha256'] == sha(Path(sys.executable)), 'MANAGED_FROZEN_SOURCE_CHANGED')
    native.need(all(sha(OUTPUT / 'source' / n) == h for n, h in files.items()), 'MANAGED_SOURCE_COPY')
    return proof


def verify(lane):
    proof = freeze()
    folder = OUTPUT / lane
    invocation = read(folder / 'invocation.json')
    expected_argv = [sys.executable, '-B', str(STUDIO / 'host/replay' /
        ('repair.py' if lane == 'repair' else 'repair_replay.py')), '--run-id',
        REPAIR if lane == 'repair' else REPLAY]
    expected_argv += (['--fault-run', FAULT, '--fault-capture-sha256', FAULT_SHA] if lane == 'repair'
                     else ['--repair-run', REPAIR, '--repair-capture-sha256',
                           sha(STUDIO / '.local/reviews' / REPAIR / 'capture.json')])
    native.need(invocation['argv'] == expected_argv
                and invocation['timeout_seconds'] == (280 if lane == 'repair' else 150),
                'MANAGED_INVOCATION')
    host = read(folder / 'capture.json')['host']
    native.need(host['host'] == 'owner-host.json' and host['stdout'] == 'owner-stdout.txt'
                and host['stderr'] == 'owner-stderr.txt', 'MANAGED_FIXED_OUTER_PATHS')
    actual = read(folder / 'owner-host.json')
    native.need(host['exit_code'] == host['wrapper_exit_code'] == actual['exit_code'] == 0
                and host['target_pid'] == actual['target_pid'] and host['tree_verified']
                and not host['timed_out'], 'MANAGED_OUTER_EXIT_TREE')
    native.need(not (folder / host['stderr']).read_bytes()
                and not re.search(rb'\b(?:WARNING|ERROR)\b|\bError:',
                                  (folder / host['stdout']).read_bytes()), 'MANAGED_OUTER_LOG')
    raw = STUDIO / '.local/reviews' / (REPAIR if lane == 'repair' else REPLAY)
    if lane == 'repair':
        _, report = repair_replay.verified_repair(raw, sha(raw / 'capture.json'))
        native.need(report['fault_capture_sha256'] == FAULT_SHA
                    and report['source_closure_sha256'] == proof['source_closure_sha256'],
                    'MANAGED_REPAIR_BINDING')
        payload = {'capture_sha256': sha(raw / 'capture.json'), 'report': report}
    else:
        payload = verify_replay_chain(raw, proof['source_files'],
                                     STUDIO / '.local/reviews' / REPAIR, REPLAY)
    outer_artifacts = {name: hashlib.sha256(native.execution_installed.binding._read(
        folder / name, 8 * 1024 * 1024)).hexdigest() for name in (
            'invocation.json', 'capture.json', 'owner-host.json', 'owner-stdout.txt', 'owner-stderr.txt')}
    summary = {'lane': lane, 'actual_target': actual, 'helper_exit': host['wrapper_exit_code'],
               'tree_verified': host['tree_verified'], 'source_unchanged': True,
               'formal_acceptance': False, 'proof': payload, 'outer_artifacts': outer_artifacts}
    target = folder / 'verified.json'
    if target.exists():
        native.need(read(target) == summary, 'MANAGED_DERIVED_CHANGED')
    else:
        write(target, summary)
    return summary


def verify_replay_chain(raw, expected_sources, repair_root, expected_run_id):
    """Revalidate immutable observations, not only process completion flags."""
    result = read(raw / 'repair-replay.json')
    repair_hash = sha(repair_root / 'capture.json')
    config, receipt = repair_replay.verified_repair(repair_root, repair_hash)
    _, fault, fault_checks = repair.verified_fault(STUDIO / '.local/reviews' / FAULT, FAULT_SHA)
    native.need(result['managed_repair_proven'] is True and result['formal_acceptance'] is False
                and result['binding'] == {'repair_capture_sha256': repair_hash,
                     'fault_capture_sha256': FAULT_SHA, 'selected_config_sha256': native.sha(config)}
                and receipt['fault_capture_sha256'] == FAULT_SHA, 'MANAGED_REPLAY_BINDING')
    native.need(read(raw / 'source-files.json') == expected_sources, 'MANAGED_REPLAY_SOURCE')
    for index, (name, digest) in enumerate(expected_sources.items()):
        native.need(sha(raw / 'source' / (str(index) + Path(name).suffix)) == digest,
                    'MANAGED_REPLAY_SOURCE_COPY')
    capture = read(raw / 'capture.json')
    native.need(sha(raw / 'capture.json') == result['native_capture_sha256']
                and capture['completed_native'] is True and capture['source_unchanged'] is True
                and capture['run_id'] == expected_run_id, 'MANAGED_NATIVE_CAPTURE')
    project = raw / 'project'
    snapshot = read(raw / 'runtime-snapshot.json')
    native.need(native.closure(snapshot) == capture['binding']['runtime_snapshot_sha256'],
                'MANAGED_RUNTIME_SNAPSHOT')
    for name, digest in snapshot.items():
        native.execution_installed.binding._name(name)
        native.need(sha(project / name) == digest, 'MANAGED_RUNTIME_BYTES')
    native.need(read(project / 'input/run.json') == capture['binding']
                and capture['binding']['source_closure_sha256'] == native.closure(expected_sources)
                and capture['binding']['trace_sha256'] == fault['binding']['trace_sha256']
                and capture['binding']['glb_sha256'] == fault['binding']['glb_sha256']
                and sha(project / 'input/fixture.glb') == capture['binding']['glb_sha256']
                and native.read_regular(project / 'config/fixture_actor.gd') == config,
                'MANAGED_RUNTIME_BINDING')
    report = native.read_regular(project / 'out/report.json')
    metrics = native.read_regular(raw / 'process-metrics.json')
    native.need(native.sha(report) == capture['report_sha256']
                and native.sha(metrics) == capture['process_metrics_sha256'], 'MANAGED_OBSERVATION_HASH')
    stages = {}
    for phase in ('import', 'runtime'):
        stages[phase] = native.verify_captured_stage(raw / (phase + '-host'), capture[phase + '_capture_sha256'])
    native.need(stages['runtime']['actual_process_exit']['pid'] == capture['process']['pid'],
                'MANAGED_NATIVE_PID')
    trace = repair_replay.validate_trace(native.read_regular(project / 'input/trace.json'))
    checks = repair_replay.validate_observation(report, trace=trace, binding=capture['binding'],
        config_speed=3.0, project=project, process=json.loads(metrics))
    native.need(checks == result['replay_checks'] and fault_checks == result['fault_checks']
                and checks['all_postconditions'] is True and checks['movement_fault_observed'] is False,
                'MANAGED_REPLAY_OBSERVATION')
    native.need(result['verifier_sources'] == {name: expected_sources['host/replay/' + name]
        for name in ('repair_replay.py', 'repair.py', 'observation.py', 'trace.py')}, 'MANAGED_VERIFIER_SOURCE')
    return {'repair_replay_sha256': sha(raw / 'repair-replay.json'), 'stages': stages,
            'native_capture_sha256': result['native_capture_sha256'], 'observation': checks}


def run(lane):
    freeze()
    folder = OUTPUT / lane
    native.need(not folder.exists(), 'MANAGED_NO_RETRY')
    raw = STUDIO / '.local/reviews' / (REPAIR if lane == 'repair' else REPLAY)
    native.need(not raw.exists(), 'MANAGED_RUN_ID_REUSE')
    repair.verified_fault(STUDIO / '.local/reviews' / FAULT, FAULT_SHA)
    if lane == 'repair':
        argv = [sys.executable, '-B', str(STUDIO / 'host/replay/repair.py'), '--run-id', REPAIR,
                '--fault-run', FAULT, '--fault-capture-sha256', FAULT_SHA]
        timeout = 280
    else:
        verify('repair')
        anchor = sha(STUDIO / '.local/reviews' / REPAIR / 'capture.json')
        argv = [sys.executable, '-B', str(STUDIO / 'host/replay/repair_replay.py'), '--run-id', REPLAY,
                '--repair-run', REPAIR, '--repair-capture-sha256', anchor]
        timeout = 150
    folder.mkdir(exist_ok=False)
    write(folder / 'invocation.json', {'argv': argv, 'timeout_seconds': timeout,
          'started_utc': datetime.now(timezone.utc).isoformat(), 'formal_acceptance': False})
    spec = importlib.util.spec_from_file_location('s133_managed_owned', STUDIO / 'build/bootstrap/run_fixture.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    host = runner.run_process(argv, cwd=ROOT, output=folder, timeout=timeout, label='owner')
    write(folder / 'capture.json', {'host': host})
    return verify(lane)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lane', choices=('repair', 'replay'), required=True)
    parser.add_argument('--verify-existing', action='store_true')
    args = parser.parse_args()
    try:
        result = verify(args.lane) if args.verify_existing else run(args.lane)
        print(json.dumps({'verified': True, 'lane': args.lane,
              'actual_target': result['actual_target'], 'formal_acceptance': False}), flush=True)
        return 0
    except Exception as error:
        if OUTPUT.exists():
            for number in range(1, 1000):
                p = OUTPUT / ('failure-%04d.json' % number)
                if not p.exists():
                    write(p, {'lane': args.lane, 'error_type': type(error).__name__,
                          'code': str(error) if isinstance(error, native.ReplayError) else 'HELPER_OPERATION_FAILED',
                          'formal_acceptance': False, 'automatic_retry': False})
                    break
        raise


if __name__ == '__main__':
    raise SystemExit(main())

