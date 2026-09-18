"""Prepared supplemental HTTP probe; execute only through the owned runner."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import threading
import time
from unittest.mock import patch

sys.dont_write_bytecode = True
HISTORY_SHA256 = '4d8ecb5bacd76a57d3137e9f812c36c3a6a759d4d51d41008627e9114ee1377a'
HISTORY_BYTES = 15_586_409
HISTORY_RECORDS = 22_170
COOPERATIVE_SECONDS = 210
ENDPOINTS = {f'/v1/{name}': name for name in
             ('commands', 'lookup', 'lease', 'discovery', 'cancel', 'stop', 'archive')}


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


class ProbeError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def need(condition, code):
    if not condition:
        raise ProbeError(code)


def safe_code(error):
    code = getattr(error, 'code', None)
    return code if type(code) is str and re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', code) else type(error).__name__


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')


class Spans:
    """Fixed labels, one aggregate and three slowest spans per label."""
    def __init__(self):
        self.lock = threading.Lock()
        self.local = threading.local()
        self.rows = {}
        self.phase = 'initialize'

    def measured(self, label, function, *args, **kwargs):
        start = time.perf_counter_ns()
        try:
            return function(*args, **kwargs)
        finally:
            end = time.perf_counter_ns()
            row = {'started_mono_us': start // 1000, 'ended_mono_us': end // 1000,
                   'elapsed_ms': (end - start) / 1e6,
                   'endpoint': getattr(self.local, 'endpoint', 'none')}
            key = self.phase + '.' + label
            with self.lock:
                need(len(self.rows) < 160 or key in self.rows, 'SPAN_LABEL_BOUND')
                aggregate = self.rows.setdefault(key, {'count': 0, 'sum_ms': 0.0,
                                                       'max_ms': 0.0, 'slowest': []})
                aggregate['count'] += 1
                aggregate['sum_ms'] += row['elapsed_ms']
                aggregate['max_ms'] = max(aggregate['max_ms'], row['elapsed_ms'])
                aggregate['slowest'] = sorted(aggregate['slowest'] + [row],
                    key=lambda item: item['elapsed_ms'], reverse=True)[:3]


def loaded_closure(source, manifest):
    loaded = {}
    for name, module in tuple(sys.modules.items()):
        raw = getattr(module, '__file__', None)
        if not raw or not (name == 'studio' or name.startswith('studio.')):
            continue
        path = Path(raw).resolve(strict=True)
        try:
            relative = path.relative_to(source).as_posix()
        except ValueError:
            raise ProbeError('LOADED_MODULE_OUTSIDE_FREEZE') from None
        need(relative in manifest and digest(path) == manifest[relative], 'LOADED_MODULE_HASH')
        loaded[name] = {'path': relative, 'sha256': manifest[relative]}
    return loaded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--journal', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    need(re.fullmatch(r'[a-z][a-z0-9._-]{0,47}', args.run_id), 'RUN_ID')
    source, original = args.source_root.resolve(strict=True), args.journal.resolve(strict=True)
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    for name, expected in manifest.items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts
             and (source / name).resolve(strict=True).is_relative_to(source)
             and digest(source / name) == expected, 'FREEZE_HASH')
    need(original.stat().st_size == HISTORY_BYTES and digest(original) == HISTORY_SHA256, 'HISTORY_HASH')
    args.output.mkdir(parents=False, exist_ok=False)
    output = args.output.resolve(strict=True)
    report = {'schema_id': 'hh-studio.s81-supplemental-http-probe', 'schema_version': '1.0.0',
              'run_id': args.run_id, 'status': 'PREPARING', 'formal_acceptance': False,
              'native_acceptance': False, 'full_benchmark': False, 'engine_runs': 0,
              'started_utc': datetime.now(timezone.utc).isoformat(), 'pid': os.getpid(),
              'history_sha256': HISTORY_SHA256, 'history_bytes': HISTORY_BYTES,
              'history_records': HISTORY_RECORDS, 'failures': [],
              'source_manifest_sha256': digest(args.manifest),
              'driver_sha256': digest(Path(__file__)), 'cooperative_seconds': COOPERATIVE_SECONDS,
              'client_timeout_seconds': 2.0, 'terminal_budget_seconds': 5,
              'workload': 'Unchanged CommandProducer.run_batch(0), 1000 commands in 5/3/2 mix plus original auxiliary Cancel',
              'additional_faults_or_delays': False, 'original_cancel_delay_ms': 1000,
              'fixture_scope': 'Fresh distinct project and counter at rev-0; historical project runtime/leases are not restored',
              'phase_timing_scope': 'Supplemental wrappers; overlapping spans; fixed labels only, no headers/body/token/exception text'}
    write(output / 'prepared.json', report)
    sys.path.insert(0, str(source))
    from studio.tests.replay import benchmark_commands as benchmark
    from studio.host.replay import verified_journal
    from studio.host.core import transport
    report['loaded_module_closure_after_import'] = loaded_closure(source, manifest)
    need(benchmark.GROUPS == 100 and benchmark.TERMINAL_TIMEOUT_SECONDS == 5, 'WORKLOAD_BUDGET_CHANGED')
    need(hasattr(benchmark.FixtureClient, 'last_transport_failure'), 'FAILURE_DIAGNOSTICS_REQUIRED')
    project_id = 'gt06.s81.http.' + args.run_id
    report['project_id'] = project_id
    spans = Spans()
    deadline = time.monotonic() + COOPERATIVE_SECONDS
    producer = None
    owners = []
    final_batch = None
    actual_journal = benchmark.Journal
    actual_host = benchmark.LoopbackFixtureHost
    actual_snapshot = verified_journal.VerifiedJournal._snapshot
    actual_fsync = os.fsync
    actual_dispatch = benchmark.LoopbackFixtureHost._dispatch
    actual_disconnect = benchmark.LoopbackFixtureHost._disconnect_probe
    actual_send = benchmark.LoopbackFixtureHost._send

    def journal_factory(path):
        need(path.parent == output / 'commands' and not path.exists(), 'COPY_DESTINATION')
        shutil.copyfile(original, path)
        need(digest(path) == HISTORY_SHA256, 'COPIED_HISTORY_HASH')
        journal = actual_journal(path)
        owners.append(journal)
        try:
            need(journal._index_store._one('PRAGMA synchronous')[0] == 2, 'SQLITE_SYNC_CHANGED')
            need(journal._index_store._one('PRAGMA journal_mode')[0] == 'delete', 'SQLITE_MODE_CHANGED')
        except Exception:
            journal.close()
            raise
        return journal

    def host_factory(_project_id, path, journal):
        host = actual_host(project_id, path, journal)
        try:
            need(host.fixture.snapshot() == {'value': 0, 'revision': 'rev-0', 'effect_count': 0}, 'INITIAL_FIXTURE')
        except Exception:
            host.close()
            raise
        return host

    def snapshot(journal, *, synchronize):
        return spans.measured('journal_snapshot_' + str(synchronize).lower(),
                              actual_snapshot, journal, synchronize=synchronize)

    def fsync(fd):
        return spans.measured('canonical_fsync', actual_fsync, fd)

    def dispatch(host, path, body, session, control):
        endpoint = ENDPOINTS.get(path, 'unknown')
        spans.local.endpoint = endpoint
        return spans.measured('host_dispatch.' + endpoint, actual_dispatch, host, path, body, session, control)

    def disconnect(host, path, phase, result=None):
        endpoint = ENDPOINTS.get(path, 'unknown')
        spans.local.endpoint = endpoint
        need(phase in ('before_dispatch', 'after_dispatch', 'before_reply', 'after_reply'), 'FAULT_PHASE')
        return spans.measured('host_fault_probe.' + phase, actual_disconnect, host, path, phase, result)

    def send(host, stream, value, status=200, redactor=None):
        return spans.measured('host_send', actual_send, host, stream, value, status, redactor)

    class BoundedProducer(benchmark.CommandProducer):
        def _command(self, *call_args):
            if time.monotonic() >= deadline:
                raise benchmark.CommandError('SUPPLEMENTAL_WALL_BUDGET')
            try:
                return super()._command(*call_args)
            finally:
                row = call_args[-1]
                if (row['ordinal'] + 1) % 100 == 0:
                    print(json.dumps({'completed_or_attempted_commands': row['ordinal'] + 1,
                                      'formal_acceptance': False}), flush=True)

    try:
        with ExitStack() as stack:
            for target, name, replacement in (
                (benchmark, 'Journal', journal_factory), (benchmark, 'LoopbackFixtureHost', host_factory),
                (verified_journal.VerifiedJournal, '_snapshot', snapshot), (os, 'fsync', fsync),
                (benchmark.LoopbackFixtureHost, '_dispatch', dispatch),
                (benchmark.LoopbackFixtureHost, '_disconnect_probe', disconnect),
                (benchmark.LoopbackFixtureHost, '_send', send)):
                stack.enter_context(patch.object(target, name, replacement))
            try:
                producer = BoundedProducer(output / 'commands', args.run_id)
                spans.phase = 'http_batch'
                final_batch = producer.run_batch(0)
                need(producer.client.timeout == 2.0, 'CLIENT_TIMEOUT_CHANGED')
            except Exception as error:
                final_batch = getattr(error, 'report', final_batch)
                report['failures'].append(safe_code(error))
                if producer is None:
                    producer = getattr(error, 'cleanup_owner', None)
            finally:
                spans.phase = 'shutdown'
                if producer is not None:
                    try:
                        producer.close()
                        report['owned_cleanup'] = {
                            'producer_closed': producer.closed,
                            'host_threads_all_stopped': not any(t.is_alive() for t in producer.host._threads),
                            'main_listener_fd': producer.host._main.fileno(),
                            'control_listener_fd': producer.host._control.fileno(),
                            'observer_handle_released': producer.observer.probe.handle is None,
                            'journal_index_owner_released': producer.journal._index_store is None}
                    except Exception as error:
                        report['failures'].append('CLEANUP_' + safe_code(error))
    except Exception as error:
        report['failures'].append(safe_code(error))
    report['spans'] = spans.rows
    if final_batch is not None:
        write(output / 'command-batch.json', final_batch)
        report['batch_status'] = final_batch['status']
        report['command_count'] = len(final_batch['commands'])
        report['transport_failure'] = final_batch.get('transport_failure')
        report['command_batch_sha256'] = digest(output / 'command-batch.json')
    try:
        report['loaded_module_closure_after_shutdown'] = loaded_closure(source, manifest)
        report['source_files_unchanged'] = all(digest(source / name) == expected for name, expected in manifest.items())
        need(report['source_files_unchanged'], 'SOURCE_CHANGED')
        report['original_history_sha256_after'] = digest(original)
        need(report['original_history_sha256_after'] == HISTORY_SHA256, 'ORIGINAL_HISTORY_CHANGED')
        copied = output / 'commands/commands.jsonl'
        if copied.exists():
            with copied.open('rb') as stream:
                prefix = stream.read(HISTORY_BYTES)
                extra = stream.read()
            report['copied_prefix_sha256_after'] = hashlib.sha256(prefix).hexdigest()
            report['appended_records'] = extra.count(b'\n')
            need(report['copied_prefix_sha256_after'] == HISTORY_SHA256, 'HISTORY_PREFIX_CHANGED')
            report['copied_journal_sha256_after'] = digest(copied)
            if final_batch is not None and final_batch['status'] == 'COMPLETE':
                need(report['appended_records'] == 1403, 'APPENDED_RECORD_COUNT')
        report['private_index_directories_remaining'] = [p.name for p in (output / 'commands').glob('.hh-index-*')]
        need(not report['private_index_directories_remaining'], 'INDEX_CLEANUP_HELD')
        need(owners and all(j._index_store is None for j in owners), 'JOURNAL_OWNER_HELD')
        cleanup = report.get('owned_cleanup', {})
        need(all(cleanup.get(key) is True for key in ('producer_closed', 'host_threads_all_stopped',
                 'observer_handle_released', 'journal_index_owner_released'))
             and cleanup.get('main_listener_fd') == cleanup.get('control_listener_fd') == -1,
             'PRODUCER_CLOSE_UNPROVEN')
    except Exception as error:
        report['failures'].append(safe_code(error))
    report['status'] = 'SUPPLEMENTAL_COMPLETE' if not report['failures'] and final_batch is not None and final_batch['status'] == 'COMPLETE' else 'SUPPLEMENTAL_FAILED'
    report['ended_utc'] = datetime.now(timezone.utc).isoformat()
    write(output / 'report.json', report)
    print(json.dumps({'status': report['status'], 'commands': report.get('command_count', 0),
                      'formal_acceptance': False, 'failures': report['failures']}), flush=True)
    return 0 if report['status'] == 'SUPPLEMENTAL_COMPLETE' else 1


if __name__ == '__main__':
    raise SystemExit(main())
