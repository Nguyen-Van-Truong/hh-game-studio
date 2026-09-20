"""Bounded host-only request-lifetime diagnostic; no acceptance or engine run."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
REPO = PROJECT.parent


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stamp():
    return datetime.now(timezone.utc).isoformat()


def need(condition, code):
    if not condition:
        raise RuntimeError(code)


def child(out):
    sys.path.insert(0, str(PROJECT))
    from studio.host.core.transport import _Listener
    from studio.tests.replay.benchmark_commands import CommandProducer
    from studio.tests.replay.test_benchmark_commands import SyntheticObserver

    # Bind once, before baseline. A pseudo-handle owns no closable kernel handle.
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    get_count = kernel.GetProcessHandleCount
    get_count.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    get_count.restype = wintypes.BOOL
    pseudo = wintypes.HANDLE(-1)
    count_slot = wintypes.DWORD()

    def handle_count():
        need(bool(get_count(pseudo, ctypes.byref(count_slot))), 'HANDLE_COUNT_UNAVAILABLE')
        return int(count_slot.value)

    handle_count()
    source_paths = {Path(__file__).resolve(), Path(sys.modules['socketserver'].__file__).resolve()}
    for module in tuple(sys.modules.values()):
        name = getattr(module, '__file__', None)
        if name:
            path = Path(name).resolve()
            if path.is_relative_to(PROJECT / 'studio') and path.suffix == '.py':
                source_paths.add(path)
    source_before = {str(path): digest(path) for path in sorted(source_paths)}
    write(out / 'source-before.json', source_before)

    events, samples, batches = [], [], []
    thread_ids = set()
    joined_live_threads = 0
    active = {}
    lock = threading.Lock()
    sequence = 0
    phase = 'baseline'
    all_credentials = []
    producers = []
    partial = None
    original_process = _Listener.process_request
    original_thread = _Listener.process_request_thread

    def event(kind, row, **extra):
        events.append(dict(kind=kind, seq=row['seq'], fd=row['fd'],
                           control=row['control'], phase=row['phase'],
                           mono_ns=time.perf_counter_ns(), active_count=len(active), **extra))

    def process(listener, request, client_address):
        nonlocal sequence
        key = id(request)  # Numeric lookup only; never retain a socket object.
        with lock:
            sequence += 1
            row = dict(seq=sequence, fd=request.fileno(), control=listener.control, phase=phase)
            need(key not in active, 'DUPLICATE_ACTIVE_SOCKET_ID')
            active[key] = row
            event('process_request_start', row)
        try:
            return original_process(listener, request, client_address)
        finally:
            with lock:
                # A synchronous connection-cap rejection has no request thread.
                # Normal rows end exclusively after original_thread returns.
                if key in active and request.fileno() == -1 and not row.get('thread_entered'):
                    active.pop(key)
                    event('synchronous_request_closed', row, fd_after=-1)

    def request_thread(listener, request, client_address):
        key = id(request)
        with lock:
            row = active[key]
            row['thread_entered'] = True
            # Numeric-only registry: retaining Thread objects changes Windows
            # lock/event lifetimes and contaminated the preserved first run.
            thread_ids.add(threading.get_ident())
            event('process_request_thread_enter', row)
        outcome = 'returned'
        try:
            return original_thread(listener, request, client_address)
        except BaseException:
            outcome = 'raised'
            raise
        finally:
            with lock:
                active.pop(key)
                event('process_request_thread_return', row, fd_after=request.fileno(), outcome=outcome)

    def sample(label, producer=None):
        # Counter and lifecycle snapshot serialized with wrapper event writes.
        with lock:
            row = dict(label=label, phase=phase, mono_ns=time.perf_counter_ns(),
                       actual_held_handles=handle_count(), active_count=len(active),
                       active_sequences=sorted(item['seq'] for item in active.values()),
                       request_threads_alive=sum(thread.is_alive() for thread in threading.enumerate()
                           if thread.ident in thread_ids and thread.name != 'gt02-fixture'),
                       fixed_host_threads_alive=(None if producer is None else
                           sum(thread.is_alive() for thread in producer.host._threads)))
        samples.append(row)
        return row

    def await_active(expected, timeout=2):
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            with lock:
                if len(active) == expected:
                    return
            time.sleep(0.001)
        raise RuntimeError('ACTIVE_COUNT_DEADLINE')

    def join_workers():
        nonlocal joined_live_threads
        # Threads that already terminated own no live work to join. Retain only
        # currently live own request threads, after counter sampling, until join.
        for thread in threading.enumerate():
            if thread is threading.main_thread() or thread.name == 'gt02-fixture':
                continue
            thread.join(timeout=2)
            joined_live_threads += 1
        need(not any(thread is not threading.main_thread() and thread.name != 'gt02-fixture'
                     for thread in threading.enumerate()), 'REQUEST_THREAD_JOIN_DEADLINE')

    _Listener.process_request = process
    _Listener.process_request_thread = request_thread
    started = time.perf_counter()
    status, error_code = 'COMPLETED_DIAGNOSTIC', None
    try:
        sample('pre_host')
        phase = 'normal_setup'
        normal = CommandProducer(out / 'normal-work', 'gt06-s129-host-normal', observer=SyntheticObserver())
        producers.append(normal)
        sample('normal_host_started', normal)
        for index in range(3):
            phase = 'normal_group_' + str(index)
            report = normal.run_diagnostic()
            # Take immediate sample before deriving or serializing the report.
            sample('group_immediate', normal)
            all_credentials.append(normal.credential.bearer)
            await_active(0)
            sample('group_active_zero', normal)
            time.sleep(0.05)
            sample('group_settle_50ms', normal)
            time.sleep(0.15)
            sample('group_settle_200ms', normal)
            batches.append(dict(index=index, status=report['status'],
                mode=report['mode'], complete_command_mix=report['complete_command_mix'],
                commands_by_kind={key: len(value) for key, value in report['latency_ms'].items()},
                effect_count_before=report['effect_count_before'], effect_count_after=report['effect_count_after'],
                cancel_status=report['cancel']['status'], cancel_no_effect=report['cancel']['no_effect'],
                producer_observation_kind=report['observation_kind'],
                producer_held_handles_SYNTHETIC=report['memory_after']['counters']['held_handles']['value']))
        phase = 'normal_close'
        close_start = time.perf_counter_ns()
        normal.close()
        normal_close_ms = (time.perf_counter_ns() - close_start) / 1_000_000
        sample('normal_close_returned', normal)
        join_workers()
        sample('normal_joined', normal)

        phase = 'partial_setup'
        injected = CommandProducer(out / 'partial-work', 'gt06-s129-host-partial', observer=SyntheticObserver())
        producers.append(injected)
        sample('partial_host_started', injected)
        phase = 'partial_request_injected'
        partial = socket.create_connection(('127.0.0.1', injected.host.port), timeout=2)
        # Controlled incomplete header, no authentication and no request body.
        partial.sendall(b'POST /v1/discovery HTTP/1.1\r\nHost: 127.0.0.1\r\n')
        await_active(1)
        sample('partial_active_before_close', injected)
        phase = 'partial_close'
        close_start = time.perf_counter_ns()
        injected.close()
        partial_close_ms = (time.perf_counter_ns() - close_start) / 1_000_000
        partial_after_close = sample('partial_close_returned_client_open', injected)
        partial.close()
        partial = None
        sample('partial_client_closed', injected)
        await_active(0)
        sample('partial_active_zero', injected)
        join_workers()
        sample('partial_joined', injected)
        time.sleep(0.2)
        sample('partial_postclose_settle_200ms', injected)
    except BaseException as error:
        status, error_code = 'DIAGNOSTIC_ERROR', type(error).__name__
    finally:
        if partial is not None:
            partial.close()
            partial = None
        for producer in producers:
            try:
                producer.close()
            except Exception as error:
                status, error_code = 'CLEANUP_ERROR', type(error).__name__
        try:
            await_active(0)
            join_workers()
        except Exception as error:
            status, error_code = 'CLEANUP_ERROR', type(error).__name__
        _Listener.process_request = original_process
        _Listener.process_request_thread = original_thread

    source_after = {str(path): digest(path) for path in sorted(source_paths)}
    source_stable = source_before == source_after
    write(out / 'source-after.json', source_after)
    result = dict(schema='hh3d.s129.host-quiescence.diagnostic.v1', utc=stamp(),
        status=status, error_type=error_code, pid=os.getpid(), python=sys.version,
        elapsed_seconds=time.perf_counter() - started, source_stable=source_stable,
        source_file_count=len(source_before), source_before_sha256=digest(out / 'source-before.json'),
        source_after_sha256=digest(out / 'source-after.json'), formal_acceptance=False,
        engine_started=False, benchmark_dataset=False, request_lifetime_wrappers=True,
        actual_counter='GetProcessHandleCount, prebound, current-process pseudo-handle',
        producer_observer='existing SyntheticObserver: RSS=1000000, held_handles=10; not actual counters',
        normal_close_ms=locals().get('normal_close_ms'), partial_close_ms=locals().get('partial_close_ms'),
        partial_request_outlived_close=(locals().get('partial_after_close', {}).get('active_count', 0) > 0),
        batches=batches, samples=samples, request_events=events,
        active_requests_final=len(active),
        request_threads_created=sum(row['kind'] == 'process_request_thread_enter' for row in events),
        request_threads_returned=sum(row['kind'] == 'process_request_thread_return' for row in events),
        live_extra_threads_explicitly_joined=joined_live_threads,
        retained_thread_objects=False,
        fixed_threads_alive_final=sum(thread.is_alive() for producer in producers for thread in producer.host._threads),
        own_client_socket_closed=partial is None,
        extra_threads_final=[thread.name for thread in threading.enumerate() if thread is not threading.main_thread()])
    raw = json.dumps(result, indent=2, sort_keys=True) + '\n'
    need(not any(secret in raw for secret in all_credentials), 'SECRET_IN_RESULT')
    for path in out.rglob('*'):
        if path.is_file():
            blob = path.read_bytes()
            need(not any(secret.encode() in blob for secret in all_credentials), 'SECRET_IN_ARTIFACT')
    (out / 'result.json').write_text(raw, encoding='utf-8')
    print(json.dumps(dict(status=status, elapsed_seconds=result['elapsed_seconds'],
                         request_threads_created=result['request_threads_created'], active_requests_final=len(active))))
    return 0 if status == 'COMPLETED_DIAGNOSTIC' and source_stable else 2


def supervise(out):
    out.mkdir(exist_ok=False)
    launch = [sys.executable, '-B', str(Path(__file__).resolve()), '--child', '--out', str(out)]
    start = time.perf_counter()
    record = dict(schema='hh3d.s129.host-quiescence.supervisor.v1', started_utc=stamp(),
                  command=launch, timeout_seconds=45, exit_kind='UNKNOWN', actual_exit_code=None,
                  git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip())
    with (out / 'stdout.txt').open('wb') as stdout, (out / 'stderr.txt').open('wb') as stderr:
        proc = subprocess.Popen(launch, cwd=REPO, stdout=stdout, stderr=stderr)
        record['child_pid'] = proc.pid
        try:
            code = proc.wait(timeout=45)
            record.update(actual_exit_code=code, exit_kind='NATURAL_WAIT_RETURN')
        except subprocess.TimeoutExpired:
            proc.kill()
            record.update(actual_exit_code=proc.wait(timeout=5), exit_kind='SUPERVISOR_TIMEOUT_KILLED')
        record.update(ended_utc=stamp(), elapsed_seconds=time.perf_counter() - start,
                      child_reaped=proc.poll() is not None)
    record.update(stdout_sha256=digest(out / 'stdout.txt'), stderr_sha256=digest(out / 'stderr.txt'),
                  script_sha256=digest(Path(__file__).resolve()))
    write(out / 'supervisor.json', record)
    print(json.dumps(record, indent=2))
    return 0 if record['actual_exit_code'] == 0 and record['exit_kind'] == 'NATURAL_WAIT_RETURN' else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--child', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(child(args.out) if args.child else supervise(args.out))
