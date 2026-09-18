"""Supplemental HTTP attribution on copied S93 history; never acceptance.

Wrappers call the unchanged implementation and retain no arguments, bodies,
credentials or exception text. Nested spans overlap and are not additive.
"""
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import re
import shutil
import sys
import threading
import time

BASE = Path(__file__).resolve().parent
GROUPS = 20
SLOW_NS = 50_000_000
SLOW_CAP = 16
OPERATIONS = (
    'journal.snapshot', 'journal.reload', 'journal.append', 'journal.load',
    'journal.writer_wait', 'journal.writer_held', 'host.discovery', 'host.lease',
    'host.commands', 'host.lookup', 'host.archive', 'host.cancel', 'host.stop',
    'host.other',
)
ENDPOINTS = {('/v1/' + name): ('host.' + name) for name in
             ('discovery', 'lease', 'commands', 'lookup', 'archive', 'cancel', 'stop')}
KNOWN_FAILURE_CODES = frozenset({
    'FIXED_RUN_PATH_REQUIRED', 'FROZEN_INPUT_MISMATCH', 'NEW_PRODUCER_HISTORY_REQUIRED',
    'HISTORY_COPY_MISMATCH', 'DIAGNOSTIC_POSTCONDITION',
})


def sanitized_error(error):
    rows, seen = [], set()
    while error is not None and id(error) not in seen and len(rows) < 3:
        seen.add(id(error))
        kind = type(error).__name__
        row = {'exception_class': kind if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', kind) else 'Exception',
               'frames': []}
        trace = error.__traceback__
        while trace is not None:
            name = Path(trace.tb_frame.f_code.co_filename).name
            row['frames'].append({'file': name if re.fullmatch(r'[A-Za-z0-9_.-]{1,96}', name) else 'nonstandard_filename',
                                  'line': trace.tb_lineno})
            trace = trace.tb_next
        row['frames'] = row['frames'][-16:]
        if len(error.args) == 1 and type(error.args[0]) is str and error.args[0] in KNOWN_FAILURE_CODES:
            row['known_code'] = error.args[0]
        rows.append(row)
        error = error.__cause__ or error.__context__
    return {'exception_chain': rows}


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


class Timings:
    def __init__(self):
        self.lock = threading.Lock()
        self.phase = 'initialize'
        self.rows = {name: {'count': 0, 'returned_count': 0, 'total_ns': 0,
                           'max_ns': 0, 'slow_count': 0, 'slow_samples': []}
                     for name in OPERATIONS}

    def add(self, name, start, end, returned):
        elapsed = end - start
        with self.lock:
            row = self.rows[name]
            row['count'] += 1
            row['returned_count'] += int(returned)
            row['total_ns'] += elapsed
            row['max_ns'] = max(row['max_ns'], elapsed)
            if elapsed >= SLOW_NS:
                row['slow_count'] += 1
                row['slow_samples'].append({'phase': self.phase,
                    'started_mono_ns': start, 'ended_mono_ns': end,
                    'elapsed_ns': elapsed, 'returned': returned})
                row['slow_samples'].sort(key=lambda sample: sample['elapsed_ns'], reverse=True)
                del row['slow_samples'][SLOW_CAP:]

    def measure(self, name, method, *args, **kwargs):
        start, returned = time.perf_counter_ns(), False
        try:
            result = method(*args, **kwargs)
            returned = True
            return result
        finally:
            self.add(name, start, time.perf_counter_ns(), returned)


def main():
    run = Path(sys.argv[1]).resolve()
    if run.parent != BASE or run.name != 'run-01':
        raise ValueError('FIXED_RUN_PATH_REQUIRED')
    source, history = run / 'source', run / 'history.jsonl'
    freeze = json.loads((run / 'freeze.json').read_text(encoding='utf-8'))
    output = run / 'child'
    output.mkdir(exist_ok=False)
    source_before = {name: sha(source / name) for name in freeze['source_files']}
    history_before = sha(history)
    if (source_before != freeze['source_files'] or history_before != freeze['history_sha256']
            or sha(Path(__file__)) != freeze['probe_sha256']):
        raise ValueError('FROZEN_INPUT_MISMATCH')
    sys.path.insert(0, str(source))
    from studio.tests.replay import benchmark_commands as b

    timing = Timings()
    journal_type, host_type = b.Journal, b.LoopbackFixtureHost

    class Journal(journal_type):
        def _snapshot(self, *, synchronize):
            return timing.measure('journal.snapshot', super()._snapshot, synchronize=synchronize)

        def _reload(self):
            return timing.measure('journal.reload', super()._reload)

        def _append(self, record):
            return timing.measure('journal.append', super()._append, record)

        def _load(self):
            return timing.measure('journal.load', super()._load)

        @contextmanager
        def _writer_lock(self):
            start, acquired, returned = time.perf_counter_ns(), None, False
            try:
                with super()._writer_lock():
                    acquired = time.perf_counter_ns()
                    yield
                returned = True
            finally:
                end = time.perf_counter_ns()
                timing.add('journal.writer_wait', start, acquired or end, acquired is not None)
                if acquired is not None:
                    timing.add('journal.writer_held', acquired, end, returned)

    class Host(host_type):
        def _dispatch(self, path, body, session, control):
            return timing.measure(ENDPOINTS.get(path, 'host.other'),
                                  super()._dispatch, path, body, session, control)

    def journal(path):
        if path != output / 'commands' / 'commands.jsonl' or path.exists():
            raise ValueError('NEW_PRODUCER_HISTORY_REQUIRED')
        shutil.copyfile(history, path)
        if sha(path) != history_before:
            raise ValueError('HISTORY_COPY_MISMATCH')
        return Journal(path)

    def host(_project, path, value):
        return Host('gt06.s95.http-attribution', path, value)

    producer = None
    report = {'schema': 'HH-GT06-S95-HTTP-ATTRIBUTION-1',
              'formal_acceptance': False, 'eligible_for_dataset': False,
              'engine_runs': 0, 'completed': False, 'closed': False,
              'groups_requested': GROUPS, 'groups_completed': 0,
              'current_source_closure_sha256': freeze['current_source_closure_sha256'],
              'source_before': source_before, 'history_before_sha256': history_before,
              'scope': 'New project and producer over copied history; twenty ten-command HTTP diagnostics, not an S93 replay or benchmark',
              'instrumentation': {'slow_threshold_ns': SLOW_NS, 'slow_cap_per_operation': SLOW_CAP,
                  'slow_selection': 'largest observed spans', 'spans_overlap': True,
                  'writer_wait': 'entry through original mutex and OS writer guard acquisition',
                  'writer_held': 'original acquired guard through release, including nested instrumentation',
                  'policy_changed': False, 'timeout_retry_fsync_lock_unchanged': True},
              'batches': []}
    try:
        with ExitStack() as stack:
            stack.enter_context(patch.object(b, 'Journal', journal))
            stack.enter_context(patch.object(b, 'LoopbackFixtureHost', host))
            producer = b.CommandProducer(output / 'commands', 'gt06.s95.http-attribution')
            for index in range(GROUPS):
                timing.phase = 'http'
                try:
                    row = producer.run_diagnostic()
                except b.CommandError as error:
                    if error.report is not None:
                        write(output / f'command-{index:02d}.json', error.report)
                    raise
                write(output / f'command-{index:02d}.json', row)
                if (len(row['commands']) != 10 or row['effect_count_after'] != 2 * (index + 1)
                        or row['cancel']['no_effect'] is not True):
                    raise ValueError('DIAGNOSTIC_POSTCONDITION')
                report['batches'].append({'index': index, 'commands': len(row['commands']),
                    'max_status_gap_ms': row['max_status_gap_ms'],
                    'effect_count_after': row['effect_count_after']})
                report['groups_completed'] += 1
            report['completed'] = True
    except BaseException as error:
        # Constructor cleanup may retain an owner; keep only sanitized context.
        producer = producer or getattr(error, 'cleanup_owner', None)
        report['execution_failed'] = True
        report['execution_diagnostic'] = sanitized_error(error)
    finally:
        timing.phase = 'close'
        if producer is not None:
            try:
                producer.close()
                report['closed'] = producer.closed
            except BaseException as error:
                report['cleanup_failed'] = True
                report['cleanup_diagnostic'] = sanitized_error(error)
            report['threads_alive'] = [thread.is_alive() for thread in producer.host._threads] if producer.host else []
            if producer.host is not None:
                report['host_cleanup'] = {
                    'closing': producer.host._closing.is_set(),
                    'stopped': producer.host._stopped.is_set(),
                    'main_socket_closed': producer.host._main.socket.fileno() == -1,
                    'control_socket_closed': producer.host._control.socket.fileno() == -1}
            if producer.observer is not None:
                report['observer_cleanup'] = {
                    'handle_retained': producer.observer.probe.handle is not None,
                    'close_uncertain': producer.observer.probe.close_uncertain}
            if producer.journal is not None:
                report['journal_cleanup'] = {
                    'cache_closed': producer.journal._cache_closed,
                    'index_retained': producer.journal._index_store is not None}
        report['source_after'] = {name: sha(source / name) for name in freeze['source_files']}
        report['history_after_sha256'] = sha(history)
        report['source_unchanged'] = report['source_after'] == source_before
        report['history_unchanged'] = report['history_after_sha256'] == history_before
        report['producer_history_sha256'] = sha(output / 'commands' / 'commands.jsonl') if (output / 'commands' / 'commands.jsonl').is_file() else None
        report['loaded_modules'] = {}
        report['loaded_source_matches_freeze'] = True
        for name, module in list(sys.modules.items()):
            raw = getattr(module, '__file__', None)
            if name.startswith('studio.') and raw:
                path = Path(raw).resolve()
                try:
                    relative = path.relative_to(source).as_posix()
                    digest = sha(path)
                    report['loaded_modules'][name] = {'path': relative, 'sha256': digest}
                    if freeze['source_files'].get(relative) != digest:
                        report['loaded_source_matches_freeze'] = False
                except ValueError:
                    report['loaded_source_matches_freeze'] = False
        report['timings'] = timing.rows
        write(output / 'report.json', report)
    return 0 if (report['completed'] and report['closed'] and not any(report.get('threads_alive', []))
                 and report['source_unchanged'] and report['history_unchanged']
                 and report['loaded_source_matches_freeze']) else 1


if __name__ == '__main__':
    try:
        code = main()
    except BaseException as error:
        diagnostic = {'status': 'HTTP_ATTRIBUTION_INCOMPLETE', **sanitized_error(error)}
        try:
            write(BASE / 'run-01' / 'child-unexpected-error.json', diagnostic)
        except OSError:
            pass
        print(json.dumps(diagnostic, sort_keys=True), flush=True)
        code = 1
    raise SystemExit(code)
