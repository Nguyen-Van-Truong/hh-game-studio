"""Fixed real run_child startup/failure/cleanup smoke. Coordinator launch only.

No benchmark workload or engine implementation is replaced. The sole failure
stimulus replaces run_batch(0) after run_child has verified native READY. A
transparent cleanup spy retains references for independent post-finally reads.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import sys
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
STUDIO = ROOT / 'studio'
RUN_ID = 'gt06-s81-cleanup-probe-01'
RUN = STUDIO / '.local/reviews' / RUN_ID
CHILD = RUN / 'child'
WALL_SECONDS = 120
INJECTED_CODE = 'S81_EXPECTED_CLEANUP_SMOKE'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def require(value, code):
    if not value:
        raise RuntimeError(code)


def api():
    sys.path.insert(0, str(ROOT))
    from studio.tests.replay import run_benchmark_campaign as campaign
    from studio.tests.replay.benchmark_job import BenchmarkProcess, verify_capture, write
    campaign.load_fixture()  # Include the dynamically loaded trusted fixture closure.
    return campaign, BenchmarkProcess, verify_capture, write


def outer(expected):
    campaign, Owner, verify_capture, write = api()
    source = campaign.source_files()
    require(campaign.closure(source) == expected, 'PROBE_EXPECTED_SOURCE_CLOSURE')
    RUN.mkdir(exist_ok=False)
    execution = {'studio/' + name: digest for name, digest in source.items()}
    execution[Path(__file__).resolve().relative_to(ROOT).as_posix()] = sha(Path(__file__))
    for name, digest in execution.items():
        raw = (ROOT / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == digest, 'PROBE_FREEZE_CHANGED')
        destination = RUN / 'source' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(raw)
        require(sha(destination) == digest, 'PROBE_FREEZE_COPY_MISMATCH')
    request = {'schema': 'HH-GT06-CHILD-CLEANUP-PROBE-1', 'run_id': RUN_ID,
        'source_files': source, 'source_closure_sha256': expected,
        'execution_files': execution, 'execution_closure_sha256': campaign.closure(execution),
        'profile_sha256': campaign.profile.PROFILE_SHA256, 'wall_seconds': WALL_SECONDS,
        'stimulus': 'Injected CommandError at run_batch(0) after native READY; no HTTP/native batch executes',
        'observer': 'Transparent _finish_child_cleanup wrapper retains original objects and then calls original exactly once',
        'formal_acceptance': False, 'full_benchmark': False, 'effects_claimed': False}
    write(RUN / 'probe-request.json', request)
    executable = Path(sys.executable).with_name('python.exe')
    require(executable.is_file(), 'PROBE_PYTHON_MISSING')
    argv = [str(executable), '-B', str(Path(__file__).resolve()), '--owned-child']
    write(RUN / 'probe-invocation.json', {'argv': argv, 'cwd': str(RUN),
        'expected_source_closure': expected, 'execution_closure': campaign.closure(execution),
        'source_file_count': len(source), 'runner': 'BenchmarkProcess(campaign_host=True)',
        'watchdog_seconds': WALL_SECONDS, 'existing_owner_profile_unchanged': True,
        'formal_acceptance': False, 'full_benchmark': False})
    owner = failure = cleanup_failure = capture = None
    started = time.monotonic()
    try:
        owner = Owner(argv, cwd=RUN, output=RUN / 'probe-owner', source_root=ROOT,
            source_files=execution, binary_sha256=sha(executable), campaign_host=True)
        while owner.tick(stop=time.monotonic() - started >= WALL_SECONDS) is None:
            time.sleep(.02)
        capture = owner.finish()
        verify_capture(RUN / 'probe-owner', sha(RUN / 'probe-owner/capture.json'),
            source_root=ROOT, expected_source_files=execution,
            expected_binary_sha256=sha(executable), expected_campaign_host=True)
    except BaseException as error:
        failure = error
        owner = owner or getattr(error, 'cleanup_owner', None)
    finally:
        if owner is not None:
            try:
                owner.close()
            except BaseException as error:
                cleanup_failure = error
    after = {name: sha(ROOT / name) for name in execution}
    child = read(CHILD / 'probe-result.json') if (CHILD / 'probe-result.json').is_file() else None
    clean = (failure is None and cleanup_failure is None and execution == after and capture is not None
        and child is not None and child.get('status') == 'CLEANUP_SMOKE_VERIFIED'
        and capture['actual_process_exit']['pid'] == child['observer_pid'])
    report = {'schema': 'HH-GT06-CHILD-CLEANUP-PROBE-OUTER-1',
        'status': 'CLEANUP_SMOKE_VERIFIED' if clean else 'FAILED', 'formal_acceptance': False,
        'full_benchmark': False, 'effects_claimed': False, 'run_id': RUN_ID,
        'source_unchanged': execution == after, 'source_after': after,
        'elapsed_seconds': time.monotonic() - started,
        'failure_code': getattr(failure, 'code', type(failure).__name__) if failure else None,
        'cleanup_failure_type': type(cleanup_failure).__name__ if cleanup_failure else None,
        'owner_closed': owner.closed if owner else None,
        'owner_job': owner.job.snapshot() if owner and owner.job else None,
        'owner_wrapper_handle': owner.process_handle_snapshot() if owner else None,
        'actual_observer_process_exit': capture['actual_process_exit'] if capture else None,
        'actual_observer_exit_is_not_injected_body_success': True,
        'capture_ref': campaign.reference(RUN, RUN / 'probe-owner/capture.json') if capture else None,
        'child_result_ref': campaign.reference(RUN, CHILD / 'probe-result.json') if child else None}
    write(RUN / 'probe-outer-result.json', report)
    print(json.dumps(report), flush=True)
    return 0 if clean else 1


def child():
    campaign, _Owner, _verify_capture, write = api()
    from studio.tests.replay.benchmark_commands import CommandError
    from studio.tests.replay.benchmark_job import HELD_OWNERS
    from studio.host.replay.process_probe import HELD_PROBES
    request = read(RUN / 'probe-request.json')
    require(request['run_id'] == RUN_ID and request['wall_seconds'] == WALL_SECONDS, 'PROBE_REQUEST')
    source = campaign.source_files()
    require(source == request['source_files'], 'PROBE_CHILD_SOURCE_CLOSURE')
    require(all(sha(ROOT / name) == digest for name, digest in request['execution_files'].items()),
            'PROBE_CHILD_EXECUTION_CHANGED')
    CHILD.mkdir(exist_ok=False)
    context = {'run_id': RUN_ID + '.r00.a01', 'index': 0, 'attempt': 1,
        'source_files': source, 'source_closure_sha256': campaign.closure(source),
        'profile_sha256': campaign.profile.PROFILE_SHA256,
        # This is a bounded diagnostic request, not a ten-run campaign claim.
        'campaign_sha256': sha(RUN / 'probe-request.json')}
    write(CHILD / 'context.json', context)
    write(CHILD / 'source-files.json', source)
    profile_raw = json.dumps(campaign.asdict(campaign.profile.PROFILE), sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode()
    campaign.write(CHILD / 'benchmark-profile.json', profile_raw)
    require(sha(CHILD / 'benchmark-profile.json') == campaign.profile.PROFILE_SHA256, 'PROBE_PROFILE_BYTES')
    campaign.write(CHILD / 'toolchain.lock.json', campaign.read_regular(STUDIO / 'toolchain.lock.json'))
    original_batch = campaign.CampaignProducer.run_batch
    original_cleanup = campaign._finish_child_cleanup
    kept = {}
    primary = CommandError(INJECTED_CODE)
    original_cause = RuntimeError('fixed synthetic cleanup stimulus')
    calls = 0

    def inject(producer, index):
        nonlocal calls
        calls += 1
        require(index == 0 and calls == 1, 'PROBE_INJECTION_SLOT')
        ready_path = CHILD / 'project/benchmark/out/ready-00.json'
        ready = read(ready_path)
        require(ready['run_id'] == context['run_id'] and ready['batch_index'] == 0
            and ready['source_closure_sha256'] == context['source_closure_sha256']
            and ready['profile_sha256'] == context['profile_sha256'], 'PROBE_READY_BINDING')
        require(producer.host.fixture.effect_count == 0 and producer.effects == 0, 'PROBE_PRE_EFFECT')
        require(all(thread.is_alive() for thread in producer.host._threads)
            and producer.host._main.socket.fileno() >= 0 and producer.host._control.socket.fileno() >= 0
            and producer.observer.probe.handle is not None
            and producer.journal._index_store is not None, 'PROBE_REAL_PRODUCER_NOT_STARTED')
        primary.cleanup_owner = producer
        write(CHILD / 'injection.json', {'run_id': context['run_id'], 'code': INJECTED_CODE,
            'batch': index, 'ready': campaign.reference(CHILD, ready_path),
            'real_host_threads_alive': [thread.is_alive() for thread in producer.host._threads],
            'real_observer_probe_open': True, 'real_journal_index_open': True,
            'real_listeners_open': True, 'commands_executed': 0, 'native_batches_executed': 0,
            'formal_acceptance': False, 'effects_claimed': False})
        raise primary from original_cause

    def cleanup_spy(*args, **kwargs):
        require(not kept, 'PROBE_CLEANUP_CALLED_TWICE')
        kept.update({name: kwargs[name] for name in ('producer', 'probe', 'owner', 'thread', 'primary')})
        producer = kwargs['producer']
        kept['index'] = producer.journal._index_store if producer is not None else None
        return original_cleanup(*args, **kwargs)

    caught = None
    campaign.CampaignProducer.run_batch, campaign._finish_child_cleanup = inject, cleanup_spy
    try:
        campaign.run_child(CHILD)
    except BaseException as error:
        caught = error
    finally:
        campaign.CampaignProducer.run_batch, campaign._finish_child_cleanup = original_batch, original_cleanup
    require(caught is primary and primary.__cause__ is original_cause and calls == 1,
            'PROBE_ORIGINAL_PRIMARY_NOT_PRESERVED')
    require(not getattr(primary, 'cleanup_errors', ()), 'PROBE_CLEANUP_ERRORS')
    producer, probe, owner = (kept[name] for name in ('producer', 'probe', 'owner'))
    require(kept['primary'] is primary and not kept['thread'].is_alive(), 'PROBE_PRIMARY_OR_HEARTBEAT')
    index = kept['index']
    direct = {'producer_closed': producer.closed, 'producer_failed': producer.failed,
        'host_stopped': producer.host._stopped.is_set(), 'host_closing': producer.host._closing.is_set(),
        'host_threads_alive': [thread.is_alive() for thread in producer.host._threads],
        'listener_filenos': [producer.host._main.socket.fileno(), producer.host._control.socket.fileno()],
        'host_probe_released': producer.observer.probe.handle is None,
        'host_probe_close_uncertain': producer.observer.probe.close_uncertain,
        'editor_probe_released': probe.handle is None, 'editor_probe_close_uncertain': probe.close_uncertain,
        'journal_cache_closed': producer.journal._cache_closed,
        'journal_index_detached': producer.journal._index_store is None,
        'retained_index_database_closed': index._db is None,
        'retained_index_directory_released': index._dir is None,
        'editor_owner_closed': owner.closed, 'editor_job': owner.job.snapshot(),
        'editor_wrapper_handle': owner.process_handle_snapshot(),
        'editor_helper_pid': owner.process.pid, 'editor_helper_exit': owner.process.returncode,
        'held_owner_count': len(HELD_OWNERS), 'held_probe_count': len(HELD_PROBES)}
    require(all(direct[name] is True for name in ['producer_closed', 'producer_failed', 'host_stopped',
        'host_closing', 'host_probe_released', 'editor_probe_released', 'journal_cache_closed',
        'journal_index_detached', 'retained_index_database_closed', 'retained_index_directory_released',
        'editor_owner_closed']), 'PROBE_RETAINED_RESOURCE')
    require(direct['host_threads_alive'] == [False, False, False] and direct['listener_filenos'] == [-1, -1]
        and direct['host_probe_close_uncertain'] is False and direct['editor_probe_close_uncertain'] is False
        and direct['held_owner_count'] == direct['held_probe_count'] == 0, 'PROBE_HELD_OR_UNCERTAIN')
    job, handle = direct['editor_job'], direct['editor_wrapper_handle']
    require(job['closed'] is True and job['zero_observed'] is True and job['active_count'] == 0
        and all(not job[name] for name in ['handle_retained', 'tainted', 'create_uncertain',
                                         'close_uncertain', 'failed_operations', 'native_error'])
        and handle == {'required': True, 'closed': True, 'close_uncertain': False, 'handle_retained': False},
        'PROBE_EDITOR_JOB_OR_WRAPPER_HELD')
    terminal = read(CHILD / 'child-terminal-cleanup.json')
    observed = terminal['observations']
    require(terminal['run_id'] == context['run_id'] and terminal['source_closure_sha256'] == context['source_closure_sha256']
        and terminal['profile_sha256'] == context['profile_sha256']
        and terminal['context'] == campaign.reference(CHILD, CHILD / 'context.json')
        and terminal['primary_error'] == {'stage': 'body', 'type': 'CommandError', 'code': INJECTED_CODE}
        and terminal['errors'] == [] and terminal['completed_batches'] == 0
        and terminal['phase'] == {'batch': 0, 'phase': 'commands'} and terminal['formal_acceptance'] is False,
        'PROBE_TERMINAL_BINDING')
    expected_probe = {'present': True, 'handle_retained': False, 'close_uncertain': False}
    require(observed['heartbeat_alive'] is False and observed['editor_probe'] == expected_probe
        and observed['producer']['observer_probe'] == expected_probe
        and observed['producer']['closed'] is producer.closed
        and observed['producer']['host'] == {'stopped': True, 'closing': True,
            'threads_alive': [False, False, False], 'main_socket_closed': True, 'control_socket_closed': True}
        and observed['producer']['journal'] == {'cache_closed': True, 'index_retained': False,
            'database_retained': False, 'directory_retained': False}
        and observed['editor_owner']['closed'] is owner.closed
        and observed['editor_owner']['job'] == job and observed['editor_owner']['wrapper_process_handle'] == handle
        and observed['editor_owner']['helper_pid'] == owner.process.pid
        and observed['editor_owner']['helper_exit_code'] == owner.process.returncode == 2,
        'PROBE_TERMINAL_DIRECT_STATE_MISMATCH')
    require(not os.path.lexists(CHILD / 'editor-host/process-exit.json')
        and observed['editor_target']['actual_target_exit'] is None
        and observed['editor_target']['missing_reason'] == 'TARGET_EXIT_NOT_RECORDED'
        and terminal['host_actual_exit'] is None and terminal['supervisor_actual_exit'] is None,
        'PROBE_MISSING_EXIT_PROMOTED')
    imported = campaign.native_job.verify_captured_stage(CHILD / 'import-host', sha(CHILD / 'import-host/capture.json'))
    require(imported['actual_process_exit'] == observed['import_target']['actual_target_exit'], 'PROBE_IMPORT_EXIT')
    for lane in ['import-host', 'editor-host']:
        require(not (CHILD / lane / 'stderr.txt').read_bytes().strip()
            and not re.search(rb'\b(?:WARNING|ERROR)\b|ObjectDB instances leaked|HH_GT06_BENCHMARK_FAILED',
                              (CHILD / lane / 'stdout.txt').read_bytes()), 'PROBE_NATIVE_LOGS')
    cleanup_paths = list((CHILD / 'editor-host').glob('cleanup-*.json'))
    require(len(cleanup_paths) == 1, 'PROBE_EDITOR_CLEANUP_COUNT')
    cleanup = read(cleanup_paths[0])
    require(cleanup['job'] == job and cleanup['wrapper_process_handle'] == handle
        and cleanup['wrapper_exit_code'] == 2 and cleanup['completed'] is False, 'PROBE_EDITOR_CLEANUP_RECEIPT')
    failure = read(CHILD / 'child-failure.json')
    require(failure['code'] == INJECTED_CODE and failure['completed_batches'] == 0
        and failure['completed'] is False and failure['formal_acceptance'] is False, 'PROBE_CHILD_FAILURE_LOST')
    absent = ['child-result.json', 'command-00.json', 'batch-capture-00.json', 'sample-preview-00.json',
              'project/benchmark/input/start-00.json', 'project/benchmark/out/batch-00.json',
              'project/benchmark/out/index.json']
    require(all(not os.path.lexists(CHILD / name) for name in absent), 'PROBE_UNEXPECTED_BATCH_WORK')
    require(producer.host.fixture.effect_count == producer.effects == 0, 'PROBE_UNEXPECTED_EFFECT')
    require(campaign.source_files() == source, 'PROBE_SOURCE_CHANGED')
    require(all(sha(ROOT / name) == digest for name, digest in request['execution_files'].items()), 'PROBE_EXECUTION_CHANGED')
    result = {'schema': 'HH-GT06-CHILD-CLEANUP-PROBE-RESULT-1', 'status': 'CLEANUP_SMOKE_VERIFIED',
        'run_id': context['run_id'], 'observer_pid': os.getpid(), 'formal_acceptance': False,
        'full_benchmark': False, 'effects_claimed': False, 'injected_primary_preserved': True,
        'original_cause_preserved': True, 'source_unchanged': True,
        'source_closure_sha256': context['source_closure_sha256'], 'direct_after_finally': direct,
        'editor_actual_exit': None, 'editor_helper_exit': 2,
        'import_actual_exit': imported['actual_process_exit'], 'confirmed_absences': absent,
        'refs': {name: campaign.reference(CHILD, CHILD / name) for name in [
            'injection.json', 'context.json', 'child-failure.json', 'child-terminal-cleanup.json',
            'import-host/capture.json', 'editor-host/cleanup-001.json']}}
    write(CHILD / 'probe-result.json', result)
    print(json.dumps({'status': result['status'], 'run_id': context['run_id'],
        'formal_acceptance': False, 'editor_actual_exit': None, 'editor_helper_exit': 2}), flush=True)
    return 0


if __name__ == '__main__':
    if sys.argv[1:] == ['--owned-child']:
        raise SystemExit(child())
    if len(sys.argv) == 3 and sys.argv[1] == '--expected-source-closure' and re.fullmatch('[0-9a-f]{64}', sys.argv[2]):
        raise SystemExit(outer(sys.argv[2]))
    raise SystemExit('Use --expected-source-closure SHA256 after coordinator engine lease and source freeze. No probe was launched.')
