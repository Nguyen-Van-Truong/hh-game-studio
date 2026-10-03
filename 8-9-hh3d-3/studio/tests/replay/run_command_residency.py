"""Resident command batches for scaling diagnostics; no native benchmark claim.

One fixed host, exact 1000-command mix per batch, no journal reset/restart.
Raw batches are persisted immediately. This isolates scaling before a costly
ten-run combined editor campaign. Failure preserves its completed prefix.
The optional minimum duration extends active work beyond the first 35 batches,
up to the producer's diagnostic limit; it never credits idle parent padding.
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

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay.benchmark_commands import CommandProducer, MAX_BATCHES, MAX_DIAGNOSTIC_BATCHES
from studio.tests.replay.benchmark_job import BenchmarkProcess, HELD_OWNERS, write, require
from studio.tests.replay.measure_window import measurement_window
from studio.tests.replay import benchmark_environment as environment
from studio.tests.replay import run_benchmark_campaign as campaign_module
from studio.tests.replay.run_benchmark_campaign import (
    environment_preflight, require_environment_preflight, environment_snapshot,
    wait_owned_run, read_regular, source_files as campaign_source_files)
from studio.tests.replay.run_native_benchmark import closure
from studio.tests.replay.run_watchdog_soak import SOAK_SCHEMA
from studio.host.replay.perf import summarize as frame_statistics


def source_files():
    # Use the formal campaign closure, including the scheduler and quiet-chain
    # entrypoints.  A host soak must be comparable to the subsequent formal;
    # silently using the smaller native-import closure would make the chain
    # freeze ambiguous and fail closed only after an expensive run.
    campaign_module.load_fixture()
    return campaign_source_files()


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
    attempt('journal_timings', lambda: write(root / 'journal-timings.json', {**binding,
        'schema_id': 'hh-studio.gt06-journal-timings',
        'observation': (producer.journal_timing_snapshot() if producer is not None
                        and hasattr(producer, 'journal_timing_snapshot') else None),
        'scope': 'direct bounded journal operation timings; diagnostic only'}))
    return errors


def child(run_id, *, minimum_seconds=0):
    require(type(minimum_seconds) is int and minimum_seconds >= 0,
            'RESIDENCY_MINIMUM_SECONDS')
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
    active_started = None
    active_ended = None
    active_elapsed = 0
    batch_limit = MAX_DIAGNOSTIC_BATCHES if minimum_seconds else MAX_BATCHES

    def heartbeat():
        while not stop.wait(1):
            print('HH_GT06_RESIDENCY_RUNNING ' + json.dumps({'run_id': run_id, 'batch': progress['batch']}), flush=True)

    thread = threading.Thread(target=heartbeat, daemon=True)
    try:
        producer = CommandProducer(root / 'commands', run_id,
                                   **({'max_batches': batch_limit} if minimum_seconds else {}))
        thread.start()
        while len(summaries) < MAX_BATCHES or active_elapsed < minimum_seconds:
            require(len(summaries) < batch_limit, 'RESIDENCY_MINIMUM_UNMET')
            index = len(summaries)
            progress['batch'] = index
            report = producer.run_batch(index)
            write(root / f'batch-{index:02d}.json', report)
            started, ended = report['started_mono_us'], report['ended_mono_us']
            require(type(started) is int and type(ended) is int and 0 <= started <= ended
                    and (active_ended is None or started >= active_ended),
                    'RESIDENCY_ACTIVE_CLOCK')
            require(not summaries or report['host_process'] == summaries[0]['host_process'],
                    'RESIDENCY_HOST_CHANGED')
            if active_started is None:
                active_started = started
            active_ended = ended
            # The first/last raw command timestamps exclude setup, final GC,
            # cleanup, source copying and parent lifetime from the duration.
            active_elapsed = (active_ended - active_started) / 1_000_000
            if hasattr(producer, 'journal_timing_batch'):
                direct = producer.journal_timing_batch()
                write(root / f'journal-timing-{index:02d}.json', direct)
                del direct
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
            if index >= MAX_BATCHES:
                summary['scope'] = 'diagnostic extension; outside first-35 O6.3 metrics'
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
            'minimum_seconds': minimum_seconds, 'active_elapsed_seconds': active_elapsed,
            'active_started_mono_us': active_started, 'active_ended_mono_us': active_ended,
            'cleanup_errors': [_error(stage, error) for stage, error in errors],
            'formal_acceptance': False})
        raise failure
    write(root / 'result.json', {'completed': True, 'run_id': run_id, 'source_closure_sha256': closure(before),
        'batches': summaries, 'completed_batches': len(summaries),
        'minimum_seconds': minimum_seconds, 'active_elapsed_seconds': active_elapsed,
        'active_started_mono_us': active_started, 'active_ended_mono_us': active_ended,
        'metric_batch_count': MAX_BATCHES,
        'diagnostic_extension': {'first_batch_index': MAX_BATCHES,
            'batch_count': len(summaries) - MAX_BATCHES, 'max_batches': batch_limit,
            'scope': 'same producer/PID and command mix; extra raw batches excluded from first-35 O6.3 metrics'},
        'source_unchanged': True, 'full_benchmark': False, 'formal_acceptance': False,
        'scope': 'host-only command batches; first 35 retain O6.3 metrics; no editor/native cycles'})


def run(run_id, *, minimum_seconds=0):
    require(type(minimum_seconds) is int and minimum_seconds >= 0,
            'RESIDENCY_MINIMUM_SECONDS')
    with measurement_window(run_id, 'GT06 host-only command residency diagnostic',
                            safe_to_release=lambda: not HELD_OWNERS):
        with environment.KeepAwake():
            return _run_in_window(run_id, minimum_seconds=minimum_seconds)


def _run_in_window(run_id, *, minimum_seconds=0):
    require(type(minimum_seconds) is int and minimum_seconds >= 0,
            'RESIDENCY_MINIMUM_SECONDS')
    require(re.fullmatch(r'gt06-[a-z0-9-]{1,35}', run_id) is not None, 'RESIDENCY_RUN_ID')
    root = STUDIO / '.local/reviews' / run_id
    root.mkdir(exist_ok=False)
    owner = None
    watchdog = None
    before = source_files()
    try:
        preflight = environment_preflight()
        write(root / 'environment-preflight-before.json', preflight)
        require_environment_preflight(preflight)
        owner = BenchmarkProcess([sys.executable, '-B', str(Path(__file__).resolve()), '--child', '--run-id', run_id,
                                  '--minimum-seconds', str(minimum_seconds)],
            cwd=root, output=root / 'owner', source_root=STUDIO, source_files=before,
            binary_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest())
        binding = {'run_id': run_id, 'source_closure_sha256': closure(before),
                   'campaign_sha256': hashlib.sha256(run_id.encode()).hexdigest()}
        write(root / 'soak-context.json', {'schema': SOAK_SCHEMA, **binding,
            'duration_seconds': minimum_seconds, 'source_files': before,
            'formal_acceptance': False, 'godot_started': False, 'docker_create_started': False,
            'scope': 'watchdog covering active host command residency; O9.5 combined soak'})
        watchdog = environment.Watchdog(root,
            lambda: environment_snapshot(job_handle=owner.job._handle, docker_inventory=[]), binding, write,
            docker_probe=environment.running_containers)
        wait_owned_run(owner, root, **binding, watchdog=watchdog)
        watchdog.close()
        capture = owner.finish()
        environment.verify_watchdog(root, read_regular,
                                   elapsed_seconds=capture['elapsed_seconds'], expected_binding=binding,
                                   require_docker_inventory=True)
        # Gating replay above must have no policy failures. Observer replay is
        # only valid for a Watchdog that was explicitly created in
        # observation_only mode; ordinary residency intentionally has no
        # environment-events.jsonl stream. Calling the observer verifier on
        # that mode turns a completed run into a verifier FileNotFoundError.
        if getattr(watchdog, 'observation_only', False):
            environment.verify_watchdog(root, read_regular,
                                       elapsed_seconds=capture['elapsed_seconds'], expected_binding=binding,
                                       require_docker_inventory=True, observation_only=True)
        require((root / 'result.json').is_file(), 'RESIDENCY_RESULT_MISSING')
        result_raw = read_regular(root / 'result.json', 4 * 1024**2)
        result = json.loads(result_raw)
        require(result.get('completed') is True and result.get('run_id') == run_id
                and result.get('source_closure_sha256') == closure(before)
                and result.get('source_unchanged') is True and result.get('formal_acceptance') is False,
                'RESIDENCY_RESULT_BINDING')
        active_elapsed = result.get('active_elapsed_seconds')
        require(type(active_elapsed) in (int, float) and minimum_seconds <= active_elapsed
                <= capture['elapsed_seconds'] and result.get('minimum_seconds') == minimum_seconds,
                'RESIDENCY_MINIMUM_UNMET')
        event_stream = getattr(watchdog, 'event_stream', None)
        require(watchdog.stream.closed and
                (event_stream is None or event_stream.closed),
                'RESIDENCY_WATCHDOG_STREAM_HELD')
        write(root / 'soak-result.json', {'schema': SOAK_SCHEMA, **binding,
            'actual_exit_code': capture['actual_process_exit']['exit_code'],
            'elapsed_seconds': capture['elapsed_seconds'], 'active_elapsed_seconds': active_elapsed,
            'minimum_seconds': minimum_seconds, 'completed_batches': result['completed_batches'],
            'owner_capture_sha256': hashlib.sha256(read_regular(root / 'owner/capture.json', 1024**2)).hexdigest(),
            'result_sha256': hashlib.sha256(result_raw).hexdigest(),
            'sample_stream_closed': watchdog.stream.closed,
            'event_stream_closed': event_stream is None or event_stream.closed,
            'watchdog_observation_only': bool(getattr(watchdog, 'observation_only', False)),
            'verified_watchdog': True, 'formal_acceptance': False, 'error_code': None,
            'scope': 'O9.5 combined host/watchdog diagnostic; O9.1d duration credit requires active elapsed >=1800'})
        print(json.dumps({'completed': True, 'run_id': run_id, 'host': capture, 'full_benchmark': False}), flush=True)
        return 0
    except BaseException as error:
        if owner is not None:
            owner.close()
        write(root / 'owner-failure.json', {'completed': False, 'code': getattr(error, 'code', type(error).__name__),
              'classification': environment.failure_classification(error, root),
              'job': owner.job.snapshot() if owner and owner.job else None, 'formal_acceptance': False})
        print(json.dumps({'completed': False, 'code': getattr(error, 'code', type(error).__name__), 'run_id': run_id}), flush=True)
        return 1
    finally:
        if watchdog is not None:
            watchdog.close()
        if owner is not None:
            owner.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--child', action='store_true')
    parser.add_argument('--minimum-seconds', type=int, default=0)
    args = parser.parse_args(argv)
    if args.child:
        child(args.run_id, minimum_seconds=args.minimum_seconds)
        return 0
    else:
        return run(args.run_id, minimum_seconds=args.minimum_seconds)


if __name__ == '__main__':
    raise SystemExit(main())
