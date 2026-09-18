"""Owned native storage integration for GT05; synthetic bytes, not asset approval.

The fixed provider deliberately supplies storage-test bytes. This probe proves
the adapter's actual protected-storage/journal behavior only; the complete
producer/validator/Godot provider needs separate integration evidence.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from studio.protocol.core import canonical_bytes
from studio.host.core.journal import Journal
from studio.pipeline import snapshot_state as model
from studio.pipeline.snapshot_owner import SnapshotOwner, epoch_ms
from studio.pipeline.producer.contract import asset_catalog
from run_unit_suite import source_files, sha, write

CRASH = ('intent', 'artifact', 'manifest', 'selecting', 'selector', 'before_witness', 'terminal')
CASES = ('success', 'stop_before_intent', 'stop_after_selector', 'write_failure', *('crash_' + x for x in CRASH))
CRASH_EXIT = 86


def need(value, message):
    if not value:
        raise AssertionError(message)


class StorageFixtureProvider:
    def __init__(self, digest):
        self.digest, self.calls, self.stopped = digest, 0, False
        self.payloads = {name: ('SYNTHETIC_STORAGE_TEST_ONLY:' + name).encode() for name in model.NAMES}
        info = {'schema': 'HH-GT05-SNAPSHOT-METADATA-1', 'timestamp': '2026-09-17T00:00:00Z',
            'binaries': {name: digest for name in ('blender', 'godot', 'python', 'node')},
            'semantic': {'sha256': digest, 'hash_domain': 'sha256:exact-file-bytes'},
            'license': 'original-fixture', 'creator': 'synthetic-storage-test-only', 'attribution': '',
            'catalog': asset_catalog()}
        info.update({name: digest for name in ('profile_sha256', 'naming_sha256', 'toolchain_sha256',
            'import_preset_sha256', 'tolerances_sha256', 'exporter_sha256', 'validator_sha256')})
        self.value = model.VerifiedSnapshot(digest, tuple(self.payloads.items()),
            tuple((name, digest) for name in model.EVIDENCE), canonical_bytes(info))

    def __call__(self, request):
        self.calls += 1
        return self.value

    def request_stop(self):
        self.stopped = True


def setup(output):
    digest = sha(canonical_bytes(source_files(STUDIO)))
    journal = Journal(output / 'journal.jsonl')
    lease = journal.acquire_lease(project_id=model.PROJECT, target=model.TARGET,
        owner='native-storage-probe', now_ms=epoch_ms(), ttl_ms=60000)
    provider = StorageFixtureProvider(digest)
    owner = SnapshotOwner.create(output, journal=journal, provider=provider, current_source=lambda: digest)
    request = {'schema': model.SCHEMA, 'profile': model.PROFILE,
        'command_id': 'snapshot.probe', 'expected_source_sha256': digest}
    return owner, provider, request, lease


def chain(error):
    rows = []
    while error is not None:
        rows.append({'type': type(error).__name__, 'code': getattr(error, 'code', str(error))})
        error = error.__cause__
    return rows


def graph(output):
    return {path.relative_to(output).as_posix(): sha(path.read_bytes())
        for parent in output.iterdir() if parent.is_dir() and parent.name.startswith(('hh-files-', 'hh-private-'))
        for path in parent.rglob('*') if path.is_file()}


def reopened(output, storage_id, request, expected_status):
    before = graph(output)
    owner = None
    try:
        try:
            owner = SnapshotOwner.reopen(storage_id)
        except model.SnapshotError as error:
            need(expected_status == 'HELD' and error.outcome_unknown, 'unexpected reopen failure')
            failures = chain(error)
            need(any(row['code'] == 'EVENT_CUSTODY_BINDING_MISMATCH' for row in failures), 'wrong custody failure')
            error.cleanup_owner.close()
            return {'status': 'HELD', 'errors': failures}
        need(expected_status != 'HELD', 'unwitnessed history accepted')
        raw = owner.lookup_bytes(request['command_id'], model.sha(canonical_bytes(request)))
        need(raw is not None and json.loads(raw)['status'] == expected_status, 'readonly status')
        if expected_status == 'COMMITTED':
            manifest, payloads = owner.read_selected()
            need(payloads == StorageFixtureProvider(request['expected_source_sha256']).payloads,
                 'readonly payload bytes')
            need(manifest['public_ack'] is False and manifest['editor_activation'] is False, 'scope')
        else:
            try:
                owner.read_selected()
            except model.SnapshotError as error:
                need(error.code == 'SNAPSHOT_NOT_COMMITTED', 'incomplete read rejected for wrong reason')
            else:
                raise AssertionError('incomplete snapshot selected')
        return {'status': expected_status, 'receipt_sha256': sha(raw)}
    finally:
        if owner is not None:
            owner.close()
        need(before == graph(output), 'readonly reopen changed protected bytes')


def crash_child(output, case):
    owner, provider, request, lease = setup(output)

    def cut():
        ready = {'case': case, 'pid': os.getpid(), 'storage_id': owner.storage_id,
            'request': request, 'phase': owner._state['phase'], 'provider_calls': provider.calls}
        raw = canonical_bytes(ready)
        with (output / 'ready.json').open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os._exit(CRASH_EXIT)  # Real death skips every Python finally/close.

    append, create, persist = owner._append, owner.files.create_new, owner.custody.persist_binding

    def append_hook(kind, **fields):
        value = append(kind, **fields)
        if (kind, case) in (('INTENT', 'intent'), ('SELECTING', 'selecting'), ('TERMINAL', 'terminal')):
            cut()
        return value

    def create_hook(name, raw):
        value = create(name, raw)
        if (name, case) in ((model.NAMES[0], 'artifact'), (model.MANIFEST, 'manifest'), (model.SELECTOR, 'selector')):
            cut()
        return value

    def persist_hook(binding):
        if case == 'before_witness' and binding.witnessed.sequence == 6:
            cut()
        return persist(binding)

    with patch.object(owner, '_append', append_hook), patch.object(owner.files, 'create_new', create_hook), \
            patch.object(owner.custody, 'persist_binding', persist_hook):
        owner.publish(request, lease, deadline_ms=epoch_ms() + 30000)
    raise AssertionError('crash cut was not reached')


def worker(output, case):
    if case.startswith('crash_'):
        cut = case.removeprefix('crash_')
        process = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
            '--crash-child', cut, '--output', str(output)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            stdout, stderr = process.communicate(timeout=30)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        (output / 'child-stdout.txt').write_bytes(stdout)
        (output / 'child-stderr.txt').write_bytes(stderr)
        need(process.returncode == CRASH_EXIT and not stdout and not stderr,
             'crash child exit or diagnostics')
        ready = json.loads((output / 'ready.json').read_bytes())
        need(ready['case'] == cut and ready['provider_calls'] == 1 and ready['pid'] == process.pid,
             'crash point binding')
        expected = 'COMMITTED' if cut == 'terminal' else 'HELD' if cut == 'before_witness' else 'UNKNOWN'
        recovery = reopened(output, ready['storage_id'], ready['request'], expected)
        result = {'case': case, 'child_exit': process.returncode, 'ready': ready, 'recovery': recovery}
    else:
        owner, provider, request, lease = setup(output)
        storage_id = owner.storage_id
        result = {'case': case, 'storage_id': storage_id}
        try:
            if case == 'success':
                raw = owner.publish(request, lease, deadline_ms=epoch_ms() + 30000)
                need(json.loads(raw)['status'] == 'COMMITTED', 'native publish')
                need(owner.read_selected()[1] == provider.payloads, 'actual protected payload')
                need(owner.publish(request, lease, deadline_ms=epoch_ms() + 30000) == raw
                     and provider.calls == 1, 'exact retry repeated provider')
                result['receipt_sha256'] = sha(raw)
            elif case == 'stop_before_intent':
                owner.stop()
                try:
                    owner.publish(request, lease, deadline_ms=epoch_ms() + 30000)
                except model.SnapshotError as error:
                    need(not error.outcome_unknown and provider.calls == 0, 'pre-intent Stop executed provider')
                else:
                    raise AssertionError('stopped owner published')
                need(set(p.name for p in owner.files.root.iterdir()) == {'.writer'}, 'Stop wrote artifact')
                result['stopped_before_provider'] = True
            else:
                create = owner.files.create_new
                fired = []

                def hook(name, raw):
                    if case == 'write_failure' and name == model.NAMES[0]:
                        fired.append(name)
                        raise OSError('injected-storage-io-failure')
                    value = create(name, raw)
                    if case == 'stop_after_selector' and name == model.SELECTOR:
                        fired.append(name)
                        owner.request_stop()
                    return value

                with patch.object(owner.files, 'create_new', hook):
                    try:
                        owner.publish(request, lease, deadline_ms=epoch_ms() + 30000)
                    except model.SnapshotError as error:
                        need(error.outcome_unknown and error.code == 'SNAPSHOT_OUTCOME_UNKNOWN', 'post-intent status')
                        result['errors'] = chain(error)
                    else:
                        raise AssertionError('faulted publication returned success')
                need(fired == [model.NAMES[0] if case == 'write_failure' else model.SELECTOR], 'fault hook not reached')
                need(owner._state['phase'] == ('INTENT' if case == 'write_failure' else 'SELECTING'), 'wrong fault phase')
                if case == 'write_failure':
                    need(any(row == {'type': 'OSError', 'code': 'injected-storage-io-failure'}
                             for row in result['errors']), 'wrong failure cause')
                else:
                    need(provider.stopped and owner._stop.is_set(), 'Stop callback not reached')
                result['fault_hooks'] = fired
                need(json.loads(owner.lookup_bytes(request['command_id']))['status'] == 'UNKNOWN', 'unknown lookup')
                if case == 'stop_after_selector':
                    owner.stop()
                result['provider_calls'] = provider.calls
        finally:
            owner.close()
        if case != 'stop_before_intent':
            result['recovery'] = reopened(output, storage_id, request, 'COMMITTED' if case == 'success' else 'UNKNOWN')
    result.update(passed=True, synthetic_storage_only=True, asset_validation_proven=False,
                  public_ack=False, formal_acceptance=False)
    write(output / 'observed.json', result)
    print('GT05_SNAPSHOT_PROBE ' + json.dumps({'case': case,
        'observed_sha256': sha((output / 'observed.json').read_bytes()), 'passed': True,
        'synthetic_storage_only': True, 'asset_validation_proven': False}), flush=True)


def verify_case(output, case, host):
    if not (host['exit_code'] == host['wrapper_exit_code'] == 0 and host['tree_verified'] and not host['timed_out']):
        return False
    path = output / 'observed.json'
    if not path.is_file() or not 0 < path.stat().st_size <= 128 * 1024:
        return False
    raw = path.read_bytes()
    result = json.loads(raw)
    expected = {'case': case, 'observed_sha256': sha(raw), 'passed': True,
        'synthetic_storage_only': True, 'asset_validation_proven': False}
    markers = [json.loads(line[len('GT05_SNAPSHOT_PROBE '):])
        for line in (output / host['stdout']).read_text(encoding='utf-8').splitlines()
        if line.startswith('GT05_SNAPSHOT_PROBE ')]
    return (markers == [expected] and result.get('case') == case and result.get('passed') is True
        and result.get('synthetic_storage_only') is True and result.get('asset_validation_proven') is False
        and result.get('formal_acceptance') is False and result.get('public_ack') is False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id')
    parser.add_argument('--case', choices=CASES, action='append')
    parser.add_argument('--worker', choices=CASES)
    parser.add_argument('--crash-child', choices=CRASH)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.crash_child:
        return crash_child(args.output, args.crash_child)
    if args.worker:
        return worker(args.output, args.worker)
    from studio.pipeline.run_validation import owned_run
    output = owned_run(args.run_id)
    output.mkdir(exist_ok=False)
    before = source_files(STUDIO)
    frozen = output / 'source/studio'
    for name, digest in before.items():
        raw = (STUDIO / name).read_bytes()
        need(sha(raw) == digest, 'source drift during freeze')
        target = frozen / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    path = frozen / 'build/bootstrap/run_fixture.py'
    spec = importlib.util.spec_from_file_location('gt05_snapshot_owned_runner', path)
    runner = importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(), str(path), 'exec'), runner.__dict__)
    write(output / 'source-closure.json', {'files': before, 'source_closure_sha256': runner.source_closure_sha256(before)})
    results = []
    previous_complete = None
    for case in args.case or CASES:
        lane = output / case
        lane.mkdir()
        host = runner.run_process([sys.executable, '-B', str(frozen / 'tests/pipeline/run_snapshot_probe.py'),
            '--worker', case, '--output', str(lane)], cwd=frozen, output=lane, timeout=45, label='native')
        passed = verify_case(lane, case, host)
        if case == 'success' and passed:
            previous_complete = (lane, graph(lane))
        preserved = (previous_complete is None or graph(previous_complete[0]) == previous_complete[1])
        passed = passed and preserved
        results.append({'case': case, 'host': host, 'passed': passed})
        results[-1]['previous_completed_snapshot_unchanged'] = preserved
        write(output / (case + '-capture.json'), results[-1])
        if not passed:
            break
    stable = source_files(STUDIO) == source_files(frozen) == before
    passed = stable and len(results) == len(args.case or CASES) and all(row['passed'] for row in results)
    result = {'runs': results, 'source_unchanged': stable, 'passed': passed,
        'synthetic_storage_only': True, 'asset_validation_proven': False, 'formal_acceptance': False}
    write(output / 'capture.json', result)
    print(json.dumps(result))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
