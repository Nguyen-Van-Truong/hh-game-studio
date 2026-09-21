"""S149 bounded host-only diagnostic; original source/gates, external PSS census."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import gc
import hashlib
import importlib.util
import json
import os
import sys
import threading
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
from studio.tests.replay import benchmark_job as job
from studio.tests.replay.benchmark_commands import CommandProducer
from studio.host.replay.process_probe import ProcessProbe

PSS = ROOT / 'zdoc/reviews/20260921-gt06-s140-memory-phases/owned/gt06-s140-memory-phase-p01/pss_adapter.py'
FREEZE = BASE / 'freeze.json'
write = job.write
need = job.require


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def utc():
    return datetime.now(timezone.utc).isoformat()


def check():
    frozen = read(FREEZE)
    for name, digest in frozen['files'].items():
        need(sha(ROOT / name) == digest, 'S149_SOURCE_PIN')
    need(sha(sys.executable) == frozen['python_sha256'], 'S149_PYTHON_PIN')
    return frozen


def screen(current, baseline, gap, index):
    counters = current['counters']
    for name in ('rss_bytes', 'held_handles'):
        need(type(counters[name]['value']) is int, 'CAMPAIGN_COUNTER_UNAVAILABLE')
    if index < 5:
        return
    reference = baseline['counters']
    need(counters['rss_bytes']['value'] * 100 <= reference['rss_bytes']['value'] * 110,
         'CAMPAIGN_RSS_GROWTH')
    need(counters['held_handles']['value'] <= reference['held_handles']['value'],
         'CAMPAIGN_RETAINED_COUNTER_GROWTH')
    need(gap <= 2000, 'CAMPAIGN_STATUS_GAP')


def bind_identity(probe, started, checkpoint):
    need(started['pid'] == probe.pid == checkpoint['process']['pid'], 'S149_PID_BINDING')
    need(probe.process_start == checkpoint['process']['process_start'], 'S149_START_BINDING')


def paths(smoke):
    run = 'gt06-s150-event-quiescence-smoke-01' if smoke else 'gt06-s150-event-quiescence-01'
    return run, ROOT / 'studio/.local/reviews' / run


def child(smoke):
    frozen = check()
    run, out = paths(smoke)
    producer = None
    primary = None
    cleanup_errors = []
    completed = 0
    baseline = None
    began = time.monotonic()
    limit = 120 if smoke else 1200

    def stop():
        need(not (out / 'stop-request.json').exists(), 'BENCHMARK_STOPPED')
        need(time.monotonic() - began < limit, 'S149_CHILD_LIMIT')

    def checkpoint(label, sample):
        target = out / ('checkpoint-' + label + '.json')
        temp = target.with_suffix('.tmp')
        write(temp, {
            'process': producer.identity, 'sample': sample, 'label': label,
            'observed_utc': utc(), 'formal_acceptance': False})
        os.replace(temp, target)
        deadline = time.monotonic() + 25
        reply = out / ('observed-' + label + '.json')
        while not reply.exists():
            stop()
            need(time.monotonic() < deadline, 'S149_CENSUS_DEADLINE')
            time.sleep(0)
        acknowledgement = read(reply)
        need(acknowledgement['label'] == label, 'S149_CENSUS_BINDING')
        need(acknowledgement['status'] == 'OBSERVED', 'S149_CENSUS_UNKNOWN')

    try:
        stop()
        producer = CommandProducer(out / 'commands', run)
        for index in range(1 if smoke else 11):
            stop()
            report = producer.run_diagnostic(index) if smoke else producer.run_batch(index)
            gap = report['max_status_gap_ms']
            write(out / f'command-{index:02d}.json', report)
            del report
            gc.collect()
            current = producer._observe()
            write(out / f'sample-{index:02d}.json', current)
            completed += 1
            print(json.dumps({'batch': index, 'sample': current['counters'], 'gap_ms': gap}), flush=True)
            gate = None
            if not smoke:
                try:
                    screen(current, baseline, gap, index)
                except job.BenchmarkJobError as error:
                    gate = error
            if index == 4:
                baseline = current
            if smoke or index == 4 or gate is not None or index == 10:
                try:
                    checkpoint(f'{index:02d}', current)
                except BaseException as error:
                    if gate is None:
                        raise
                    cleanup_errors.append({'stage': 'census', 'code': getattr(error, 'code', type(error).__name__)})
            if (not smoke) and index == 9:
                # Fresh bounded follow-up: let request/worker teardown settle without a timer handle.
                quiet_deadline = time.perf_counter() + 0.25
                while time.perf_counter() < quiet_deadline:
                    time.sleep(0)
                checkpoint('09-quiet', current)
            if gate is not None:
                raise gate
    except BaseException as error:
        primary = error
        if producer is None:
            producer = getattr(error, 'cleanup_owner', None)
        partial = getattr(error, 'report', None)
        if partial is not None:
            write(out / 'partial-command.json', partial)
    finally:
        if producer is not None:
            try:
                producer.close()
            except BaseException as error:
                cleanup_errors.append({'stage': 'producer_close', 'code': getattr(error, 'code', type(error).__name__)})
            write(out / 'http-phases-final.json', producer.phase_snapshot())
        cleanup = {
            'producer_closed': producer is None or producer.closed,
            'threads_alive': [t.name for t in threading.enumerate() if t is not threading.current_thread()],
            'probe_released': producer is None or producer.observer is None or producer.observer.probe.handle is None,
            'journal_closed': producer is None or producer.journal is None or producer.journal._cache_closed,
            'errors': cleanup_errors,
            'source_unchanged': all(sha(ROOT / p) == h for p, h in frozen['files'].items()),
        }
        write(out / 'child-cleanup.json', cleanup)
    clean = (cleanup['producer_closed'] and cleanup['probe_released'] and cleanup['journal_closed']
             and not cleanup['threads_alive'] and not cleanup['errors'] and cleanup['source_unchanged'])
    write(out / 'summary.json', {
        'authority': 0, 'formal_acceptance': False, 'eligible_for_dataset': False,
        'run_id': run, 'smoke': smoke, 'completed_batches': completed,
        'error_code': getattr(primary, 'code', type(primary).__name__) if primary else None,
        'disposition': 'FAILED' if primary or not clean else 'HOST_ONLY_BOUNDARY_CAPTURED',
        'elapsed_seconds': time.monotonic() - began, 'ended_utc': utc(),
        'limitations': 'No native/ACK/idle/assembly; external census pauses between batches; not formal acceptance.'})
    return 1 if primary or not clean else 0


def launch(smoke):
    frozen = check()
    run, out = paths(smoke)
    out.mkdir(exist_ok=False)
    pins = {**frozen['files'], FREEZE.relative_to(ROOT).as_posix(): sha(FREEZE)}
    write(out / 'freeze.json', frozen)
    spec = importlib.util.spec_from_file_location('s149_pss', PSS)
    pss = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pss)
    owner = probe = None
    errors = []
    captured = None
    processed = set()
    started = time.monotonic()
    try:
        argv = [sys.executable, '-B', str(Path(__file__).resolve()), '--child']
        if smoke:
            argv.append('--smoke')
        owner = job.BenchmarkProcess(argv, cwd=out, output=out / 'owner', source_root=ROOT,
            source_files=pins, binary_sha256=frozen['python_sha256'], campaign_host=False)
        while owner.tick(stop=(out / 'stop-request.json').exists()) is None:
            need(time.monotonic() - started < (150 if smoke else 1230), 'S149_OUTER_LIMIT')
            for path in sorted(out.glob('checkpoint-*.json')):
                if path.name in processed:
                    continue
                checkpoint = read(path)
                # process-start is emitted by the owned helper, not from a PID scan.
                actual_start = read(out / 'owner/process-start.json')
                if probe is None:
                    probe = ProcessProbe(actual_start['pid'], Path(sys.executable))
                bind_identity(probe, actual_start, checkpoint)
                observation = pss.capture_owned(probe)
                label = checkpoint['label']
                write(out / ('census-' + label + '.json'), observation)
                # Atomic publication avoids the child's polling reader seeing partial JSON.
                ack = out / ('observed-' + label + '.json')
                temp = ack.with_suffix('.tmp')
                write(temp, {'label': label, 'status': observation['status'],
                    'census_sha256': sha(out / ('census-' + label + '.json'))})
                os.replace(temp, ack)
                processed.add(path.name)
            time.sleep(0)
        captured = owner.finish()
        job.verify_capture(out / 'owner', sha(out / 'owner/capture.json'), source_root=ROOT,
            expected_source_files=pins, expected_binary_sha256=frozen['python_sha256'])
    except BaseException as error:
        if owner is None:
            owner = getattr(error, 'cleanup_owner', None)
        errors.append(getattr(error, 'code', type(error).__name__))
    finally:
        for role, resource in [('probe', probe), ('owner', owner)]:
            if resource is not None:
                try:
                    resource.close()
                except BaseException as error:
                    errors.append(role + ':' + getattr(error, 'code', type(error).__name__))
        write(out / 'result.json', {
            'authority': 0, 'formal_acceptance': False, 'eligible_for_dataset': False,
            'run_id': run, 'ended_utc': utc(), 'errors': errors, 'capture_verified': captured is not None and not errors,
            'actual_target_exit': read(out / 'owner/process-exit.json') if (out / 'owner/process-exit.json').exists() else None,
            'helper_exit': owner.process.returncode if owner and owner.process else None,
            'job': owner.job.snapshot() if owner and owner.job else None,
            'wrapper_handle': owner.process_handle_snapshot() if owner else None,
            'probe_released': probe is None or (probe.handle is None and not probe.close_uncertain),
            'census_checkpoints': sorted(processed)})
    return 0 if captured is not None and not errors else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--run', action='store_true')
    action.add_argument('--child', action='store_true')
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    if args.child:
        raise SystemExit(child(args.smoke))
    if args.run:
        raise SystemExit(launch(args.smoke))
    print(json.dumps({'checked': True, 'files': len(check()['files']), 'launched': False}))
