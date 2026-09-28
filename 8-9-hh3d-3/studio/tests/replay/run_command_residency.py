"""35 resident command batches for scaling diagnostics; no native benchmark claim.

One fixed host, exact 1000-command mix per batch, no journal reset/restart.
Raw batches are persisted immediately. This isolates scaling before a costly
ten-run combined editor campaign. Failure preserves its completed prefix.
"""
from __future__ import annotations
import argparse
import gc
import hashlib
import json
from pathlib import Path
import re
import sys
import threading
import time

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay.benchmark_commands import CommandProducer
from studio.tests.replay.benchmark_job import BenchmarkProcess, write, require
from studio.tests.replay.run_native_benchmark import source_files as imported_source_files, closure
from studio.host.replay.perf import summarize as frame_statistics


def source_files():
    files = imported_source_files()
    # The scheduler imports its entry module only in the parent. Pin the same
    # launch surface explicitly in both interpreters, including direct runs.
    for name in ('run_command_residency.py', 'run_campaign_task.py', 'campaign_task.ps1'):
        path = STUDIO / 'tests/replay' / name
        files[path.relative_to(STUDIO).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def _error(stage, error):
    code = getattr(error, 'code', None)
    return {'stage': stage, 'type': type(error).__name__,
            'code': code if type(code) is str and re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', code) else None}


def _diagnostic_codes(producer):
    codes = []
    if producer is not None and producer.host is not None:
        for raw in producer.host.diagnostics:
            try:
                value = json.loads(raw)
                code = value['payload']['code']
                valid = (type(value) is dict and set(value) == {'kind', 'payload'}
                         and value['kind'] == 'log' and set(value['payload']) == {'code'}
                         and type(code) is str and re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', code))
            except (TypeError, ValueError, KeyError):
                valid = False
            codes.append(code if valid else 'INVALID_DIAGNOSTIC_SHAPE')
    return codes


def finalize(root, run_id, before, producer, stop, thread):
    """Attempt all cleanup before independent, single-use observation writes."""
    errors = []

    def attempt(stage, action):
        try:
            action()
        except BaseException as error:
            errors.append((stage, error))

    stop.set()
    if thread.ident is not None:
        attempt('heartbeat_join', lambda: thread.join(2))
    if producer is not None:
        attempt('producer_close', producer.close)
    attempt('heartbeat_closed', lambda: require(not thread.is_alive(), 'RESIDENCY_HEARTBEAT_HELD'))
    binding = {'schema_version': '1.0.0', 'run_id': run_id,
               'source_closure_sha256': closure(before), 'formal_acceptance': False}

    def phases():
        observation = producer.phase_snapshot() if producer is not None else None
        write(root / 'http-phases-final.json', {**binding,
            'schema_id': 'hh-studio.residency-observation', 'kind': 'http',
            'available': observation is not None, 'observation': observation,
            'scope': 'bounded command-only phase window; no acceptance override'})

    attempt('http_observation', phases)
    attempt('host_diagnostics', lambda: write(root / 'host-diagnostics.json', {**binding,
        'schema_id': 'hh-studio.residency-diagnostics', 'codes': _diagnostic_codes(producer)}))
    return errors


def child(run_id):
    root = STUDIO / '.local/reviews' / run_id
    before = source_files()
    write(root / 'source-files.json', before)
    for name, digest in before.items():
        raw = (STUDIO / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == digest, 'RESIDENCY_SOURCE_CHANGED')
        destination = root / 'source' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    producer = None
    stop = threading.Event()
    progress = {'batch': 0}
    summaries = []
    primary = None

    def heartbeat():
        while not stop.wait(1):
            print('HH_GT06_RESIDENCY_RUNNING ' + json.dumps({'run_id': run_id, 'batch': progress['batch']}), flush=True)

    thread = threading.Thread(target=heartbeat, daemon=True)
    try:
        producer = CommandProducer(root / 'commands', run_id)
        thread.start()
        for index in range(35):
            progress['batch'] = index
            report = producer.run_batch(index)
            write(root / f'batch-{index:02d}.json', report)
            summary = {'index': index, 'host_process': report['host_process'],
                'elapsed_ms': (report['ended_mono_us'] - report['started_mono_us']) / 1000,
                'commands': len(report['commands']), 'journal_bytes': report['journal_bytes'],
                'max_status_gap_ms': report['max_status_gap_ms'], 'memory_during_batch': report['memory_after'],
                'inspect': frame_statistics(report['latency_ms']['inspect']),
                'cancel_receipt_ms': report['cancel']['receipt_ms']}
            del report
            gc.collect()
            summary['memory_after_release'] = producer._observe()
            summary['phase'] = 'command_only_post_batch_gc_no_native_editor'
            summaries.append(summary)
            write(root / f'summary-{index:02d}.json', summary)
            print('HH_GT06_RESIDENCY_BATCH ' + json.dumps({'index': index,
                'elapsed_ms': summary['elapsed_ms'], 'rss_bytes': summary['memory_after_release']['counters']['rss_bytes']['value']}), flush=True)
    except BaseException as error:
        primary = error
        producer = producer or getattr(error, 'cleanup_owner', None)
    finally:
        errors = finalize(root, run_id, before, producer, stop, thread)
    try:
        require(source_files() == before, 'RESIDENCY_SOURCE_CHANGED')
    except BaseException as error:
        errors.append(('source_verify', error))
    if primary is not None or errors:
        failure = primary if primary is not None else errors[0][1]
        write(root / 'failure.json', {'completed': False, 'run_id': run_id,
            'source_closure_sha256': closure(before),
            'code': getattr(failure, 'code', type(failure).__name__),
            'completed_batches': len(summaries), 'partial_batch': getattr(primary, 'report', None),
            'cleanup_errors': [_error(stage, error) for stage, error in errors],
            'formal_acceptance': False})
        raise failure
    write(root / 'result.json', {'completed': True, 'run_id': run_id, 'source_closure_sha256': closure(before),
        'batches': summaries, 'source_unchanged': True, 'full_benchmark': False, 'formal_acceptance': False,
        'scope': '35 command-only batches; no editor/native cycles; separate scaling diagnostic'})


def run(run_id):
    require(re.fullmatch(r'gt06-[a-z0-9-]{1,35}', run_id) is not None, 'RESIDENCY_RUN_ID')
    root = STUDIO / '.local/reviews' / run_id
    root.mkdir(exist_ok=False)
    owner = None
    before = source_files()
    try:
        owner = BenchmarkProcess([sys.executable, '-B', str(Path(__file__).resolve()), '--child', '--run-id', run_id],
            cwd=root, output=root / 'owner', source_root=STUDIO, source_files=before,
            binary_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest())
        while owner.tick() is None:
            time.sleep(.05)
        capture = owner.finish()
        require((root / 'result.json').is_file(), 'RESIDENCY_RESULT_MISSING')
        print(json.dumps({'completed': True, 'run_id': run_id, 'host': capture, 'full_benchmark': False}), flush=True)
        return 0
    except BaseException as error:
        if owner is not None:
            owner.close()
        write(root / 'owner-failure.json', {'completed': False, 'code': getattr(error, 'code', type(error).__name__),
              'job': owner.job.snapshot() if owner and owner.job else None, 'formal_acceptance': False})
        print(json.dumps({'completed': False, 'code': getattr(error, 'code', type(error).__name__), 'run_id': run_id}), flush=True)
        return 1
    finally:
        if owner is not None:
            owner.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--child', action='store_true')
    args = parser.parse_args()
    if args.child:
        child(args.run_id)
    else:
        raise SystemExit(run(args.run_id))
