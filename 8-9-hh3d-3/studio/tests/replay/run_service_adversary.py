"""Coordinator-only real HTTP adversaries, wrapped in a bounded owned process.

This driver does not change installed/native source. Its stale-capture mode
intentionally corrupts one generated PNG in its own fresh prepared project and
preserves the original bytes separately. Results are diagnostic evidence, never
formal acceptance. Tokens remain in memory and are excluded from all records.
"""
from __future__ import annotations

import argparse
import http.client
import importlib.util
import json
import os
from pathlib import Path
import re
import select
import socket
import stat
import sys
import time

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.replay import contract, native_runner as native
from studio.host.replay.backend import BackendError, PreparedPlay
from studio.host.replay.service import ReplayService
from studio.host.replay.transport import ReplayTransport
from studio.host.core.transport import epoch_ms
from studio.protocol.core import Request, Response, canonical_bytes, parse_json

MODES = ('saturated-stop', 'revoked-result', 'stale-capture')
MAX_RESPONSE_BYTES = 262144
OUTER_TIMEOUT_SECONDS = 150


def _safe_code(error):
    candidate = getattr(error, 'code', None)
    if candidate is None and type(error) is native.ReplayError:
        candidate = str(error)  # This driver raises fixed ReplayError codes only.
    return candidate if type(candidate) is str and re.fullmatch(r'[A-Z][A-Z0-9_]{0,79}', candidate) else type(error).__name__


def _validate_arguments(run_id, mode):
    native.need(type(run_id) is str and re.fullmatch(r'gt06-[a-z0-9-]{1,50}', run_id), 'ADVERSARY_RUN_ID')
    native.need(mode in MODES, 'ADVERSARY_MODE')


def _work_slots(server):
    # Read-only instrumentation of slots consumed by real accepted sockets.
    # Never acquire, release or replace the admission semaphore in this probe.
    with server._main.slots._cond:
        return server._main.slots._value


def _wait(predicate, seconds, code):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.005)
    native.need(False, code)


def _open_incomplete_work(server, credential, project_id):
    body = canonical_bytes({'project_id': project_id, 'ttl_ms': 30000})
    header = ('POST /v1/lease HTTP/1.1\r\nHost: 127.0.0.1:' + str(server.port)
        + '\r\nContent-Type: application/json\r\nContent-Length: ' + str(len(body))
        + '\r\nAuthorization: Bearer ' + credential.bearer
        + '\r\nX-HH-Catalog: ' + contract.CATALOG_DIGEST + '\r\n\r\n').encode('ascii')
    stream = socket.create_connection(('127.0.0.1', server.port), timeout=.5)
    try:
        stream.sendall(header + body[:-1])  # One missing body byte keeps reader bounded and busy.
        return stream
    except BaseException:
        stream.close()
        raise


def _mutate_owned_png(backend, output):
    expected_project = STUDIO / '.local/reviews' / backend.binding['run_id'] / 'project'
    native.need(backend.project.absolute() == expected_project.absolute(), 'ADVERSARY_PROJECT_OWNERSHIP')
    path = backend.project / 'out/menu.png'
    for component in (path, *path.parents):
        info = component.lstat()
        native.need(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                    'ADVERSARY_PNG_REPARSE')
    entry = path.stat()
    native.need(stat.S_ISREG(entry.st_mode) and entry.st_nlink == 1, 'ADVERSARY_PNG_KIND')
    original = native.read_regular(path, 1048576)
    native.need(len(original) >= 57 and original.startswith(b'\x89PNG\r\n\x1a\n'), 'ADVERSARY_PNG_PROFILE')
    native.write(output / 'original-menu.png', original)
    changed = original[:-1] + bytes([original[-1] ^ 1])
    identity = lambda v: (v.st_dev, v.st_ino, v.st_size, v.st_mtime_ns, v.st_nlink)
    with path.open('r+b') as stream:
        native.need(identity(os.fstat(stream.fileno())) == identity(entry), 'ADVERSARY_PNG_CHANGED_BEFORE_WRITE')
        stream.seek(len(original)-1)
        native.need(stream.write(changed[-1:]) == 1, 'ADVERSARY_PNG_SHORT_WRITE')
        stream.flush()
        os.fsync(stream.fileno())
    actual = native.read_regular(path, 1048576)
    native.need(actual == changed and native.sha(actual) != native.sha(original), 'ADVERSARY_PNG_MUTATION')
    return {'generated_relative_path': 'project/out/menu.png', 'original_sha256': native.sha(original),
        'mutated_sha256': native.sha(actual), 'size_bytes': len(actual),
        'mutation': 'last PNG CRC byte XOR 1 after completed native run',
        'original_copy': 'http-adversary/original-menu.png', 'restored': False}


def run(run_id, mode):
    """Child lane; coordinator may also wrap this entry point externally."""
    _validate_arguments(run_id, mode)
    driver_sha = native.sha(Path(__file__).read_bytes())
    backend = owner = server = None
    held_sockets, secrets_in_memory, checks = [], [], []
    output = None
    result = None
    try:
        try:
            backend = PreparedPlay.prepare(run_id)
        except BackendError as error:
            backend = error.cleanup_owner
            raise
        output = backend.root / 'http-adversary'
        output.mkdir(exist_ok=False)
        owner = ReplayService(backend)
        credential = owner.sessions.issue(ttl_ms=110000)
        secrets_in_memory.append(credential.bearer.encode('ascii'))
        server = ReplayTransport(owner).start()
        sequence = 0

        def record(name, value):
            raw = value if type(value) is bytes else native.encoded(value)
            native.need(not any(secret in raw for secret in secrets_in_memory), 'ADVERSARY_SECRET_OUTPUT')
            native.write(output / name, raw)

        def check(label, value, **facts):
            row = {'label': label, 'passed': value is True, **facts}
            checks.append(row)
            record('check-' + str(len(checks)).zfill(3) + '.json', row)
            native.need(value is True, label)

        def call(path, body, *, using=None, record_pending=False):
            nonlocal sequence
            selected = credential if using is None else using
            port = server.stop_port if path == '/v1/stop' else server.control_port if path == '/v1/lookup' else server.port
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=22)
            try:
                started = time.perf_counter_ns()
                connection.request('POST', path, canonical_bytes(body), {'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + selected.bearer, 'X-HH-Catalog': contract.CATALOG_DIGEST})
                response = connection.getresponse()
                raw = response.read(MAX_RESPONSE_BYTES+1)
                elapsed = (time.perf_counter_ns()-started)/1000000
                native.need(len(raw) <= MAX_RESPONSE_BYTES and not any(secret in raw for secret in secrets_in_memory),
                            'ADVERSARY_RESPONSE_CAP_OR_SECRET')
                parsed = parse_json(raw)
                if record_pending or path != '/v1/lookup' or parsed.get('status') != 'ACCEPTED_PENDING':
                    record('http-' + str(sequence) + '.json', {'route': path, 'body': body,
                        'http_status': response.status, 'response': parsed, 'elapsed_ms': elapsed})
                    sequence += 1
                return response.status, parsed, elapsed
            finally:
                connection.close()

        code, lease, _ = call('/v1/lease', {'project_id': owner.project_id, 'ttl_ms': 30000})
        check('ADVERSARY_BOUND_LEASE', code == 200 and lease['binding'] == backend.binding)
        binding = backend.binding
        preconditions = {'expected_generation': binding['generation'],
            'expected_snapshot_sha256': binding['runtime_snapshot_sha256'],
            'expected_source_sha256': binding['source_closure_sha256']}

        def request(command_id, operation, payload):
            return Request(command_id, owner.project_id, operation, lease['lease_id'], lease['fencing_epoch'],
                lease['expected_revision'], {'stable_id': binding['runtime_instance_id']}, payload,
                'sha256:' + native.sha(canonical_bytes(payload)), min(lease['expires_ms'], epoch_ms()+19000))

        def terminal(using):
            deadline = time.monotonic()+27
            polls = 0
            while time.monotonic() < deadline:
                code, receipt, _ = call('/v1/lookup', {'project_id': owner.project_id,
                    'command_id': start.command_id}, using=using)
                native.need(code == 200, 'ADVERSARY_LOOKUP_AUTHENTICATED')
                polls += 1
                if receipt['status'] != 'ACCEPTED_PENDING':
                    Response.from_dict(receipt)
                    check('ADVERSARY_TERMINAL_BOUNDED', True, polls=polls)
                    return receipt
                time.sleep(.1)
            native.need(False, 'ADVERSARY_TERMINAL_TIMEOUT')

        start = request('adversary.play', 'play.start', {**preconditions, 'trace_sha256': binding['trace_sha256']})
        code, pending, _ = call('/v1/commands', start.as_dict())
        process = backend.status()['process']
        check('ADVERSARY_NATIVE_RUNNING', code == 200 and Response.from_dict(pending).status.value == 'ACCEPTED_PENDING'
            and backend.status()['phase'] == 'RUNNING' and type(process) is dict)
        initial_process_start = native.read_regular(backend.root / 'runtime-host/process-start.json')
        initial_worker = backend._thread
        controller = credential
        mutation = None

        if mode == 'saturated-stop':
            _wait(lambda: _work_slots(server) == 2, .5, 'ADVERSARY_WORK_INITIAL_DRAIN')
            for _ in range(2):
                held_sockets.append(_open_incomplete_work(server, credential, owner.project_id))
            _wait(lambda: _work_slots(server) == 0, .35, 'ADVERSARY_WORK_NOT_SATURATED')
            check('ADVERSARY_REAL_WORK_SATURATION', _work_slots(server) == 0
                and not select.select(held_sockets, [], [], 0)[0] and backend.status()['phase'] == 'RUNNING',
                sockets=2, request_timeout_ms=server.limits.request_timeout_ms)
            code, live_lookup, lookup_ms = call('/v1/lookup', {'project_id': owner.project_id,
                'command_id': start.command_id}, record_pending=True)
            check('ADVERSARY_LOOKUP_DURING_WORK_SATURATION', code == 200
                and live_lookup['status'] == 'ACCEPTED_PENDING' and lookup_ms < 1000 and _work_slots(server) == 0,
                elapsed_ms=lookup_ms)
            check('ADVERSARY_WORK_HELD_BEFORE_STOP', not select.select(held_sockets, [], [], 0)[0]
                and _work_slots(server) == 0 and backend.status()['phase'] == 'RUNNING')
            code, stopped, stop_ms = call('/v1/stop', {'project_id': owner.project_id, 'command_id': 'adversary.stop'})
            check('ADVERSARY_STOP_DURING_WORK_SATURATION', code == 200 and stopped['stopped'] is True
                and stop_ms < 1000 and _work_slots(server) == 0, elapsed_ms=stop_ms)
            for stream in held_sockets:
                stream.close()
            held_sockets.clear()
            _wait(lambda: _work_slots(server) == 2, 1.2, 'ADVERSARY_WORK_FINAL_DRAIN')
            code, denied, _ = call('/v1/commands', start.as_dict())
            check('ADVERSARY_RECONNECT_CANNOT_RESUME', code == 400 and denied.get('status') == 'REJECTED'
                and denied.get('code') == 'REPLAY_STOPPED')
            receipt = terminal(controller)
            check('ADVERSARY_STOP_NOT_COMMITTED', receipt['status'] == 'CANCELED')

        elif mode == 'revoked-result':
            # Credential issuance/revocation is a trusted owner event. Every
            # subsequent lookup/effect attempt uses real loopback HTTP.
            check('ADVERSARY_REVOKE_WHILE_RUNNING', backend.status()['phase'] == 'RUNNING')
            owner.sessions.revoke(credential)
            controller = owner.sessions.issue(operations=frozenset({'control.lookup', 'control.stop'}), ttl_ms=100000)
            secrets_in_memory.append(controller.bearer.encode('ascii'))
            check('ADVERSARY_CONTROL_ONLY_GRANT', backend.status()['phase'] == 'RUNNING')
            code, denied, _ = call('/v1/lookup', {'project_id': owner.project_id, 'command_id': start.command_id})
            check('ADVERSARY_REVOKED_BEARER_DENIED', code == 400 and denied.get('status') == 'REJECTED')
            code, denied, _ = call('/v1/commands', start.as_dict(), using=controller)
            check('ADVERSARY_CONTROL_CANNOT_REPLAY', code == 400 and denied.get('code') == 'REPLAY_OPERATION_FORBIDDEN')
            receipt = terminal(controller)
            check('ADVERSARY_REVOKED_RESULT_NOT_COMMITTED', receipt['status'] == 'UNKNOWN'
                and receipt.get('postconditions', {}).get('public_ack') is False
                and 'do_not_replay' in receipt.get('postconditions', {}).get('next_action', '')
                and backend.status()['phase'] == 'COMPLETED')
            code, denied, _ = call('/v1/commands', start.as_dict())
            check('ADVERSARY_REVOKED_RECONNECT_DENIED', code == 400 and denied.get('status') == 'REJECTED')
            code, still_unknown, _ = call('/v1/lookup', {'project_id': owner.project_id,
                'command_id': start.command_id}, using=controller)
            check('ADVERSARY_CONTROL_LOOKUP_STABLE_UNKNOWN', code == 200 and still_unknown == receipt)

        else:
            receipt = terminal(controller)
            check('ADVERSARY_INITIAL_NATIVE_COMMITTED', receipt['status'] == 'COMMITTED'
                and receipt['code'] == 'REPLAY_NATIVE_COMPLETED')
            code, lease, _ = call('/v1/lease', {'project_id': owner.project_id, 'ttl_ms': 30000})
            check('ADVERSARY_CAPTURE_LEASE', code == 200)
            original = request('adversary.capture.original', 'play.capture', {**preconditions, 'label': 'menu'})
            code, captured, _ = call('/v1/commands', original.as_dict())
            old_hash = native.sha(native.read_regular(backend.project / 'out/menu.png', 1048576))
            check('ADVERSARY_PRIMED_RETAINED_CAPTURE', code == 200 and captured['status'] == 'COMMITTED'
                and captured.get('postconditions', {}).get('artifact', {}).get('sha256') == old_hash
                and owner._view is not None)
            mutation = _mutate_owned_png(backend, output)
            record('intentional-capture-mutation.json', mutation)
            fresh = request('adversary.capture.tampered', 'play.capture', {**preconditions, 'label': 'menu'})
            code, rejected, _ = call('/v1/commands', fresh.as_dict())
            check('ADVERSARY_FRESH_STALE_CAPTURE_REJECTED', code == 400 and rejected.get('status') == 'REJECTED'
                and rejected.get('code') == 'REPLAY_CAPTURE_CHANGED' and 'artifact' not in rejected.get('postconditions', {}))
            code, unknown, _ = call('/v1/lookup', {'project_id': owner.project_id, 'command_id': fresh.command_id})
            check('ADVERSARY_STALE_CAPTURE_UNKNOWN', code == 200 and unknown['status'] == 'UNKNOWN'
                and unknown.get('postconditions', {}).get('public_ack') is False
                and 'artifact' not in unknown.get('postconditions', {}))
            code, again, _ = call('/v1/commands', fresh.as_dict())
            check('ADVERSARY_STALE_RETRY_CANNOT_REPLAY', code == 400 and again.get('status') == 'REJECTED')

        check('ADVERSARY_NO_SECOND_RUNTIME', backend._thread is initial_worker
            and backend.status()['process'] == process
            and native.read_regular(backend.root / 'runtime-host/process-start.json') == initial_process_start)
        if mode != 'saturated-stop':
            code, stopped, _ = call('/v1/stop', {'project_id': owner.project_id,
                'command_id': 'adversary.stop'}, using=controller)
            check('ADVERSARY_FINAL_STOP', code == 200 and stopped['stopped'] is True)
        owner.close()
        owner = None
        backend.close()
        runtime_capture = json.loads(native.read_regular(backend.root / 'runtime-host/capture.json'))
        job = runtime_capture['job']
        process_start_raw = native.read_regular(backend.root / 'runtime-host/process-start.json')
        check('ADVERSARY_OWNED_PROCESS_BINDING',
            native.sha(process_start_raw) == runtime_capture['artifacts']['process-start.json']
            and json.loads(process_start_raw)['pid'] == process['pid'])
        check('ADVERSARY_OWNED_TREE_DRAINED', job['closed'] is True and job['zero_observed'] is True
            and job['tainted'] is False and job['handle_retained'] is False and job['active_count'] == 0)
        if mode != 'saturated-stop':
            check('ADVERSARY_NATURAL_EXIT', runtime_capture['actual_process_exit']['pid'] == process['pid']
                  and runtime_capture['actual_process_exit']['exit_code'] == 0)
        check('ADVERSARY_COMPLETION_SCOPE', runtime_capture['completed'] is (mode != 'saturated-stop'))
        server.close()
        server = None
        check('ADVERSARY_SOURCE_UNCHANGED', all(native.sha(native.read_regular(native.STUDIO / name)) == digest
            for name, digest in backend.source.items()))
        check('ADVERSARY_DRIVER_UNCHANGED', native.sha(Path(__file__).read_bytes()) == driver_sha)
        result = {'schema': 'HH-GT06-HTTP-ADVERSARY-1', 'run_id': run_id, 'mode': mode, 'checks': checks,
            'binding': binding, 'process': process, 'driver_sha256': driver_sha,
            'runtime_capture_sha256': native.sha(native.read_regular(backend.root / 'runtime-host/capture.json')),
            'source_unchanged': True, 'capture_mutation': mutation, 'formal_acceptance': False,
            'scope': 'bounded hostile HTTP timing/authorization/artifact evidence; not a performance benchmark'}
        record('result.json', result)
        print('HH_GT06_ADVERSARY_COMPLETE ' + json.dumps({'run_id': run_id, 'mode': mode,
            'checks': len(checks), 'result_sha256': native.sha(native.encoded(result))}), flush=True)
        return result
    finally:
        failures = []
        for stream in held_sockets:
            try:
                stream.close()
            except BaseException as error:
                failures.append(error)
        for resource in (owner, backend, server):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as error:
                    failures.append(error)
        if failures:
            raise failures[0]


def bounded_run(run_id, mode):
    """Parent captures real child exit/tree and binds the child's result marker."""
    _validate_arguments(run_id, mode)
    driver_path = Path(__file__).resolve()
    driver_sha = native.sha(native.read_regular(driver_path))
    output = STUDIO / '.local/reviews' / (run_id + '-outer')
    output.mkdir(exist_ok=False)
    spec = importlib.util.spec_from_file_location('gt06_adversary_owned_runner', STUDIO / 'build/bootstrap/run_fixture.py')
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)
    host = runner.run_process([sys.executable, '-B', str(driver_path), '--child', '--run-id', run_id, '--mode', mode],
        cwd=STUDIO, output=output, timeout=OUTER_TIMEOUT_SECONDS, label='adversary')
    result_path = STUDIO / '.local/reviews' / run_id / 'http-adversary/result.json'
    stdout = (output / 'adversary-stdout.txt').read_bytes()
    stderr = (output / 'adversary-stderr.txt').read_bytes()
    passed = (host['exit_code'] == host['wrapper_exit_code'] == 0 and host['tree_verified'] is True
        and host['timed_out'] is False and not stderr and not re.search(rb'\b(?:WARNING|ERROR)\b|\bError:', stdout)
        and native.sha(native.read_regular(driver_path)) == driver_sha)
    result_sha = None
    failure_code = None
    if passed:
        try:
            raw = native.read_regular(result_path)
            result = json.loads(raw)
            markers = [json.loads(row.split(' ', 1)[1]) for row in stdout.decode('utf-8').splitlines()
                if row.startswith('HH_GT06_ADVERSARY_COMPLETE ')]
            result_sha = native.sha(raw)
            passed = (result['run_id'] == run_id and result['mode'] == mode and result['driver_sha256'] == driver_sha
                and result['source_unchanged'] is True and all(row['passed'] is True for row in result['checks'])
                and len(markers) == 1 and markers[0] == {'run_id': run_id, 'mode': mode,
                    'checks': len(result['checks']), 'result_sha256': result_sha})
            if not passed:
                failure_code = 'ADVERSARY_RESULT_OR_MARKER'
        except Exception as error:
            passed, failure_code = False, _safe_code(error)
    capture = {'schema': 'HH-GT06-HTTP-ADVERSARY-CAPTURE-1', 'run_id': run_id, 'mode': mode,
        'completed': passed, 'host': host, 'driver_sha256': driver_sha, 'result_sha256': result_sha,
        'stdout_sha256': native.sha(stdout), 'stderr_sha256': native.sha(stderr),
        'failure_code': failure_code, 'formal_acceptance': False}
    native.write(output / 'capture.json', capture)
    print(json.dumps({'completed': passed, 'run_id': run_id, 'mode': mode,
        'capture_sha256': native.sha(native.encoded(capture))}), flush=True)
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--mode', required=True, choices=MODES)
    parser.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        try:
            run(args.run_id, args.mode)
            return 0
        except BaseException as error:
            # Never print exception repr/tracebacks that could contain headers.
            safe_run = args.run_id if re.fullmatch(r'gt06-[a-z0-9-]{1,50}', args.run_id) else 'invalid'
            print('HH_GT06_ADVERSARY_FAILED ' + json.dumps({'run_id': safe_run, 'mode': args.mode,
                'code': _safe_code(error)}), flush=True)
            return 1
    return bounded_run(args.run_id, args.mode)


if __name__ == '__main__':
    raise SystemExit(main())
