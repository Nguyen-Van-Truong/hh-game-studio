"""One bounded Python-only differential; synthetic pending lookup, no engine.

Uses a COPY of retained S181 history. No acceptance counters or full workload.
The synthetic pending response is deliberately not evidence of live admission.
"""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
RUN = 'gt06-s182-poll-contention-01'
OUT = ROOT / 'studio/.local/reviews' / RUN
SOURCE = ROOT / 'studio/.local/reviews/gt06-s181-formal-01/run-00-attempt-01/commands/commands.jsonl'


def save(name, value):
    with (OUT/name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def child():
    from studio.host.replay.verified_journal import VerifiedJournal
    from studio.host.core.transport import epoch_ms, _response
    from studio.protocol.core import Status
    from studio.tests.replay.benchmark_transport import BenchmarkFixtureClient, BenchmarkFixtureHost
    from studio.tests.replay.benchmark_http_phases import (
        PhaseRecorder, observed_journal_type, observed_host_type, observed_client_type,
    )
    work = OUT/'journal-copy'
    work.mkdir()
    target = work/'commands.jsonl'
    shutil.copy2(SOURCE, target)
    recorder = PhaseRecorder(event_capacity=8192, active_capacity=64)
    journal = host = None
    report = {'run_id': RUN, 'authority': 0, 'formal_acceptance': False,
              'engine_started': False, 'synthetic_pending_response': True,
              'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(), 'rows': []}
    try:
        journal = observed_journal_type(VerifiedJournal, recorder)(target)
        host = observed_host_type(BenchmarkFixtureHost, recorder)('benchmark.commands', work, journal)
        host.start()
        credential = host.sessions.issue(scopes=frozenset({'fixture.read'}), ttl_ms=120_000)
        client = observed_client_type(BenchmarkFixtureClient, recorder)(host.port, host.control_port, credential)
        pending_id = 's182.synthetic.pending'
        host._pending_snapshot = {pending_id: (_response(Status.ACCEPTED_PENDING, 'QUEUED', pending_id), epoch_ms()+120_000)}
        # Reversed order in the second round reduces one-way warm-cache bias.
        for interval in [None, .001, .010, .010, .001, None]:
            ready, go, done = threading.Event(), threading.Event(), threading.Event()
            result = {'poll_sleep_seconds': interval, 'samples': [], 'polls': 0, 'poll_failures': []}

            def verify():
                ready.set()
                go.wait()
                try:
                    for _ in range(3):
                        cpu, wall = time.thread_time_ns(), time.perf_counter_ns()
                        # Unchanged original full-file hash, fsync and identity checks.
                        with journal._writer_lock():
                            journal._reload()
                        result['samples'].append({'wall_ms': (time.perf_counter_ns()-wall)/1e6,
                                                  'thread_cpu_ms': (time.thread_time_ns()-cpu)/1e6})
                except BaseException as error:
                    result['worker_error'] = type(error).__name__ + ':' + str(error)
                finally:
                    done.set()

            worker = threading.Thread(target=verify, name='s182-verifier')
            worker.start()
            if not ready.wait(2):
                raise RuntimeError('VERIFIER_NOT_READY')
            go.set()
            deadline = time.monotonic()+20
            while not done.is_set():
                if time.monotonic() >= deadline:
                    raise RuntimeError('DIFFERENTIAL_TIMEOUT')
                if interval is None:
                    done.wait(.1)
                else:
                    receipt = client.lookup(pending_id)
                    result['polls'] += 1
                    if receipt.status is not Status.ACCEPTED_PENDING:
                        result['poll_failures'].append(receipt.code)
                    time.sleep(interval)
            worker.join(1)
            result['worker_alive_after_join'] = worker.is_alive()
            assert not worker.is_alive() and 'worker_error' not in result
            report['rows'].append(result)
    finally:
        if host is not None:
            host.close()
            report['host_threads_alive_after_close'] = [t.is_alive() for t in host._threads]
        if journal is not None:
            journal.close()
            report['journal_closed'] = journal._cache_closed and journal._index_store is None
        report['source_unchanged'] = hashlib.sha256(SOURCE.read_bytes()).hexdigest() == report['source_sha256']
        report['copy_unchanged'] = hashlib.sha256(target.read_bytes()).hexdigest() == report['source_sha256']
        save('result.json', report)


def main():
    if '--child' in sys.argv:
        child()
        return
    OUT.mkdir(parents=False, exist_ok=False)
    with (OUT/'stdout.txt').open('xb') as stdout, (OUT/'stderr.txt').open('xb') as stderr:
        child_process = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--child'],
                                         stdout=stdout, stderr=stderr)
        timed_out = False
        try:
            code = child_process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            timed_out = True
            child_process.kill()
            code = child_process.wait(timeout=10)
        save('process-exit.json', {'pid': child_process.pid, 'actual_exit': code,
                                  'timeout': timed_out, 'formal_acceptance': False})
    print(json.dumps({'run_id': RUN, 'actual_exit': code, 'timeout': timed_out, 'result': str(OUT/'result.json')}))
    if code:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
