"""S183: one original HTTP batch on copied S181 history, no native workload.

Diagnostic-only restore of journal bytes, not continuation of a formal process
pair. No timeout, cadence, receipt, integrity or workload changes. Source files
remain unchanged; method wrappers report wall/thread CPU and fsync boundaries.
"""
from collections import deque
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
RUN = 'gt06-s183-retained-http-01'
OUT = ROOT / 'studio/.local/reviews' / RUN
RAW = ROOT / 'studio/.local/reviews/gt06-s181-formal-01/run-00-attempt-01'
SOURCE = RAW/'commands/commands.jsonl'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    with (OUT/name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def child():
    from studio.tests.replay.benchmark_commands import CommandProducer
    from studio.host.replay.disk_journal_index import DiskJournalIndex
    pins = json.loads((RAW/'source-files.json').read_bytes())
    assert all(sha(ROOT/'studio'/name) == digest for name, digest in pins.items())
    save('context.json', {'run_id': RUN, 'authority': 0, 'formal_acceptance': False,
        'engine_started': False, 'original_gates_changed': False, 'native_commands': 0,
        'input_history_sha256': sha(SOURCE), 'input_history_bytes': SOURCE.stat().st_size,
        'source_pins': pins, 'helper_sha256': sha(Path(__file__)), 'pid': os.getpid(),
        'started_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'One stock 1000-command HTTP batch with timing wrappers and copied history; not a formal pair'})
    lock = threading.Lock()
    tail, slow = deque(maxlen=4096), deque(maxlen=64)
    counts = {}

    @contextmanager
    def measure(phase):
        start, cpu = time.perf_counter_ns(), time.thread_time_ns()
        outcome = 'raised'
        try:
            yield
            outcome = 'returned'
        finally:
            ended, cpu_end = time.perf_counter_ns(), time.thread_time_ns()
            row = {'phase': phase, 'started_ns': start, 'ended_ns': ended,
                   'wall_ms': (ended-start)/1e6, 'thread_cpu_ms': (cpu_end-cpu)/1e6,
                   'thread_id': threading.get_ident(), 'outcome': outcome}
            with lock:
                tail.append(row)
                if row['wall_ms'] >= 500:
                    slow.append(row)
                counts[phase] = counts.get(phase, 0)+1

    def wrap(bound, phase):
        def observed(*args, **kwargs):
            with measure(phase):
                return bound(*args, **kwargs)
        return observed

    gc_starts, gc_rows = {}, deque(maxlen=128)

    def gc_observe(phase, info):
        key = (threading.get_ident(), info['generation'])
        if phase == 'start':
            gc_starts[key] = time.perf_counter_ns()
        elif key in gc_starts:
            started = gc_starts.pop(key)
            gc_rows.append({'generation': info['generation'], 'started_ns': started,
                            'wall_ms': (time.perf_counter_ns()-started)/1e6})

    producer = None
    actual_fsync, actual_execute = os.fsync, DiskJournalIndex._execute
    try:
        producer = CommandProducer(OUT/'commands', RUN)
        # No request has been admitted. Revalidate the external snapshot using
        # the accepted loader, preserving all historical receipt bytes.
        with producer.journal._writer_lock():
            shutil.copyfile(SOURCE, producer.journal.path)
            producer.journal._reload()
        for name in ('_snapshot', '_append', '_reload'):
            setattr(producer.journal, name, wrap(getattr(producer.journal, name), 'journal.'+name[1:]))
        os.fsync = wrap(actual_fsync, 'fsync')

        def sql(self, statement, *args, **kwargs):
            if statement in ('BEGIN IMMEDIATE', 'COMMIT', 'ROLLBACK'):
                with measure('sqlite.'+statement):
                    return actual_execute(self, statement, *args, **kwargs)
            return actual_execute(self, statement, *args, **kwargs)

        DiskJournalIndex._execute = sql
        gc.callbacks.append(gc_observe)
        report = producer.run_batch(0)
        save('command-batch.json', report)
    except BaseException as error:
        save('failure.json', {'code': getattr(error, 'code', type(error).__name__),
                             'partial': getattr(error, 'report', None), 'formal_acceptance': False})
        raise
    finally:
        os.fsync, DiskJournalIndex._execute = actual_fsync, actual_execute
        if gc_observe in gc.callbacks:
            gc.callbacks.remove(gc_observe)
        cleanup = {'formal_acceptance': False, 'engine_started': False, 'source_history_unchanged': sha(SOURCE)==json.loads((OUT/'context.json').read_bytes())['input_history_sha256']}
        try:
            if producer is not None:
                producer.close()
                cleanup.update(closed=producer.closed, journal_closed=producer.journal._cache_closed,
                    journal_index_retained=producer.journal._index_store is not None,
                    threads_alive=[t.is_alive() for t in producer.host._threads],
                    probe_handle_retained=bool(producer.observer.probe.handle))
                save('http-phases-final.json', producer.phase_snapshot())
        finally:
            save('cleanup.json', cleanup)
            save('timing.json', {'counts': counts, 'tail': list(tail), 'slow': list(slow),
                                'gc_tail': list(gc_rows), 'authority': 0, 'formal_acceptance': False})


def main():
    if '--child' in sys.argv:
        child()
        return
    OUT.mkdir(parents=False, exist_ok=False)
    with (OUT/'stdout.txt').open('xb') as stdout, (OUT/'stderr.txt').open('xb') as stderr:
        child_process = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--child'],
                                         stdout=stdout, stderr=stderr)
        save('dispatch.json', {'pid': child_process.pid, 'started_utc': datetime.now(timezone.utc).isoformat(),
                              'python_executable': sys.executable, 'outer_budget_seconds': 300,
                              'formal_acceptance': False})
        timed_out = False
        try:
            code = child_process.wait(timeout=300)
        except subprocess.TimeoutExpired:
            timed_out = True
            child_process.kill()
            code = child_process.wait(timeout=10)
        save('process-exit.json', {'pid': child_process.pid, 'actual_exit': code,
                                  'timeout': timed_out, 'formal_acceptance': False})
    print(json.dumps({'run_id': RUN, 'actual_exit': code, 'timeout': timed_out}))
    if code:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
