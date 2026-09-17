"""Bounded native STAGED-death supplement over unchanged S63 runtime."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parents[2] / 'studio'
sys.path.insert(0, str(STUDIO.parent))
sys.path.insert(0, str(STUDIO / 'tests/pipeline'))
import run_snapshot_probe as probe
from run_unit_suite import source_files, sha, write
from studio.pipeline.snapshot_owner import SnapshotOwner
from studio.pipeline import snapshot_state as model
from studio.protocol.core import canonical_bytes


def child(output):
    owner, provider, request, lease = probe.setup(output)
    original = owner._append

    def append(kind, **fields):
        value = original(kind, **fields)
        if kind == 'STAGED':
            probe.need(owner._state['phase'] == 'STAGED', 'cut wrong phase')
            ready = {'pid': os.getpid(), 'phase': 'STAGED', 'storage_id': owner.storage_id,
                     'request': request, 'provider_calls': provider.calls,
                     'files': sorted(p.name for p in owner.files.root.iterdir())}
            with (output / 'ready.json').open('xb') as stream:
                stream.write(canonical_bytes(ready))
                stream.flush()
                os.fsync(stream.fileno())
            os._exit(86)
        return value

    with patch.object(owner, '_append', append):
        owner.publish(request, lease, deadline_ms=probe.epoch_ms() + 30000)
    raise AssertionError('STAGED_CUT_NOT_REACHED')


def worker(output):
    invocation = json.loads((output / 'invocation.json').read_bytes())
    probe.need(source_files(STUDIO) == invocation['source_files'], 'source drift')
    from studio.pipeline.run_validation import owned_run
    previous = owned_run(invocation['native_run_id']) / 'success'
    before = probe.graph(previous)
    probe.need(before == invocation['last_good_graph'] and bool(before), 'last-good precondition')
    process = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
        '--child', str(output)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        stdout, stderr = process.communicate(timeout=30)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
    (output / 'child-stdout.txt').write_bytes(stdout)
    (output / 'child-stderr.txt').write_bytes(stderr)
    probe.need(process.returncode == 86 and not stdout and not stderr, 'unexpected child exit')
    ready = json.loads((output / 'ready.json').read_bytes())
    expected_names = sorted(['.writer', model.MANIFEST, *model.NAMES])
    probe.need(ready['pid'] == process.pid and ready['phase'] == 'STAGED'
               and ready['provider_calls'] == 1 and ready['files'] == expected_names, 'cut binding')
    prefix_before = probe.graph(output)
    owner = SnapshotOwner.reopen(ready['storage_id'])
    try:
        raw = owner.lookup_bytes(ready['request']['command_id'], sha(canonical_bytes(ready['request'])))
        reply = json.loads(raw)
        probe.need(reply['status'] == 'UNKNOWN' and owner._state['phase'] == 'STAGED', 'prefix status')
        manifest, payloads = owner._read_bundle(owner._state)
        probe.need(payloads == probe.StorageFixtureProvider(ready['request']['expected_source_sha256']).payloads,
                   'native staged payload readback')
        probe.need(not (owner.files.root / model.SELECTOR).exists(), 'unexpected selector')
        try:
            owner.read_selected()
        except model.SnapshotError as error:
            probe.need(error.code == 'SNAPSHOT_NOT_COMMITTED', 'wrong selected rejection')
        else:
            raise AssertionError('STAGED_PUBLISHED_AS_ACTIVE')
    finally:
        owner.close()
    probe.need(prefix_before == probe.graph(output), 'readonly recovery changed prefix')
    probe.need(before == probe.graph(previous), 'last-good changed')
    probe.need(source_files(STUDIO) == invocation['source_files'], 'source drift')
    observed = {'schema': 'HH-GT05-STAGED-CUT-1', 'phase': 'STAGED', 'child_pid': process.pid,
        'child_exit': process.returncode, 'ready_sha256': sha((output / 'ready.json').read_bytes()),
        'recovery_status': reply['status'], 'native_payload_readback': True, 'selector_absent': True,
        'readonly_prefix_unchanged': True, 'last_good_unchanged': True,
        'last_good_graph': before, 'synthetic_storage_only': True, 'asset_validation_proven': False,
        'public_ack': False, 'formal_acceptance': False}
    write(output / 'observed.json', observed)
    print('GT05_STAGED_CUT ' + json.dumps({'observed_sha256': sha((output / 'observed.json').read_bytes()),
                                         'phase': 'STAGED', 'child_exit': 86}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id')
    parser.add_argument('--unit-run-id')
    parser.add_argument('--native-run-id')
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--child', type=Path)
    args = parser.parse_args()
    if args.child:
        return child(args.child)
    if args.worker:
        return worker(args.worker)
    from studio.pipeline.run_validation import owned_run
    output = owned_run(args.run_id)
    output.mkdir(exist_ok=False)
    files = source_files(STUDIO)
    unit = owned_run(args.unit_run_id) / 'source-closure.json'
    native = owned_run(args.native_run_id)
    probe.need(files == json.loads(unit.read_bytes())['files'], 'unit source mismatch')
    probe.need(files == json.loads((native / 'source-closure.json').read_bytes())['files'], 'native source mismatch')
    script = Path(__file__).resolve()
    source = script.read_bytes()
    (output / 'driver.snapshot').write_bytes(source)
    write(output / 'invocation.json', {'source_files': files, 'driver_sha256': sha(source),
        'python_sha256': sha(Path(sys.executable).read_bytes()), 'timeout_seconds': 45,
        'unit_run_id': args.unit_run_id, 'native_run_id': args.native_run_id,
        'last_good_run': args.native_run_id + '/success',
        'last_good_graph': probe.graph(native / 'success')})
    path = STUDIO / 'build/bootstrap/run_fixture.py'
    spec = importlib.util.spec_from_file_location('gt05_staged_owned_runner', path)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    host = runner.run_process([sys.executable, '-B', str(script), '--worker', str(output)],
        cwd=STUDIO, output=output, timeout=45, label='staged')
    stable = source_files(STUDIO) == files and script.read_bytes() == source
    passed = stable and host['exit_code'] == host['wrapper_exit_code'] == 0 and host['tree_verified'] and not host['timed_out']
    if passed:
        raw = (output / 'observed.json').read_bytes()
        markers = [json.loads(line.removeprefix('GT05_STAGED_CUT '))
            for line in (output / host['stdout']).read_text(encoding='utf-8').splitlines()
            if line.startswith('GT05_STAGED_CUT ')]
        passed = markers == [{'observed_sha256': sha(raw), 'phase': 'STAGED', 'child_exit': 86}]
    result = {'host': host, 'source_unchanged': stable, 'passed': passed, 'formal_acceptance': False}
    write(output / 'capture.json', result)
    print(json.dumps(result))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
