"""S106 owned handle-boundary diagnostic; never benchmark acceptance.

No runtime/profile/gate changes. Frozen diagnostic modules stay outside studio
so the existing imported-source scanner continues to see exactly base53.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import ntpath
import os
from pathlib import Path
import re
import stat
import sys
import time
import types

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SOURCE_SHA = '7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467'
PROFILE_SHA = '0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85'
OVERLAY_SHA = 'bb137f32f1fae3730cc139f03fc6902813b3742d5a08d437e957e291cfe0ec46'
NATIVE_SHA = '13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95'
HELPER_PINS = {
    'zdoc/reviews/20260919-gt06-s103-status-gap/owned_prefix.py':
        '19b85ac8abfb22e68184322da2baeff17be3843550e3607471fcff0078734899',
    'zdoc/reviews/20260919-gt06-s103-status-gap/native_probe.py':
        '47dd4957deb2f1dc7995b0a30aecf424ef7ebe6c55d239f437fa9865d9583855',
    'zdoc/reviews/20260919-gt06-s102-observability/preflight.py':
        'ad4e2d15cbcb3f890f22a7d2be339aee6b726c62a9c339dfac4478fdaf21e998',
    'zdoc/reviews/20260919-gt06-s105-handles/pss_adapter.py':
        '797398a54cac5f7c772df7ec9c5ad988fe9e54c26c3c10e172a768e39dc25c76',
}
RUN_ID = re.compile(r'gt06-s106-handles-[a-z0-9][a-z0-9-]{0,30}\Z')
SCREEN_CODES = {'CAMPAIGN_COUNTER_UNAVAILABLE', 'CAMPAIGN_RSS_GROWTH',
                'CAMPAIGN_RETAINED_COUNTER_GROWTH', 'CAMPAIGN_STATUS_GAP'}
LIMITATIONS = [
    'DIAGNOSTIC_ONLY_NO_F13_F14_DATASET_OR_ACCEPTANCE',
    'PSS_AFTER_COMPLETED_SAMPLE_CAN_PERTURB_NEXT_READY_AND_STATUS_GAP',
    'NO_TIMING_SUBTRACTION_OR_GATE_RELAXATION',
    'NO_POST_IDLE_SERIES_EXISTING_TEARDOWN_IS_UNCHANGED',
    'FORCED_EDITOR_BOUNDARY_MAY_LEAVE_ACTUAL_EDITOR_EXIT_UNKNOWN',
    'PSS_NATIVE_CALLS_HAVE_SOFT_15S_BUDGET_EXTERNAL_OWNER_DEADLINE_IS_HARD_BOUND',
    'NUMERIC_HANDLES_ARE_NOT_OBJECT_IDENTITY_NO_LEAK_OR_ROOT_CAUSE_CLAIM',
]


class DiagnosticError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def need(condition, code):
    if not condition:
        raise DiagnosticError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def closure(files):
    return sha(''.join(k + '\0' + files[k] + '\n' for k in sorted(files)).encode())


def read(path, cap=128 * 1024**2):
    path = Path(path)
    for part in (path, *path.parents):
        info = part.lstat()
        need(not stat.S_ISLNK(info.st_mode)
             and not getattr(info, 'st_file_attributes', 0) & 0x400, 'S106_REPARSE')
    info = path.stat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
         and 0 < info.st_size <= cap, 'S106_FILE_SHAPE')
    raw = path.read_bytes()
    need(len(raw) == info.st_size, 'S106_FILE_CHANGED')
    return raw


def decode(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, 'S106_DUPLICATE_KEY')
            value[key] = item
        return value
    def constant(value):
        raise DiagnosticError('S106_NONFINITE_JSON')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def write_new(path, value):
    path = Path(path)
    raw = value if isinstance(value, bytes) else encoded(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    need(not os.path.lexists(path), 'S106_EVIDENCE_EXISTS')
    temporary = path.with_name(path.name + '.s106-tmp')
    with temporary.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    # Windows rename rejects an existing destination. Evidence never replaces.
    temporary.rename(path)
    need(read(path) == raw, 'S106_EVIDENCE_READBACK')


def ref(root, path):
    raw = read(path)
    return {'file': Path(path).relative_to(root).as_posix(),
            'sha256': sha(raw), 'size_bytes': len(raw)}


def error_record(error):
    code = getattr(error, 'code', None)
    if not isinstance(code, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
        code = 'S106_UNEXPECTED_EXCEPTION'
    return {'code': code, 'type': type(error).__name__}


def verify_files(base, files):
    need(type(files) is dict and bool(files), 'S106_FILE_MAP')
    for name, digest in files.items():
        need(type(name) is str and name and not Path(name).is_absolute()
             and not Path(name).drive and '\\' not in name and ':' not in name
             and all(p not in ('', '.', '..') for p in name.split('/')),
             'S106_FILE_PATH')
        need(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest), 'S106_HASH')
        need(sha(read(base / name)) == digest, 'S106_FILE_DRIFT')


def frozen_module(path, raw, name):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def checked_pins(repo):
    """No launch: execute reused helpers from already verified byte strings."""
    helper_bytes = {name: read(repo / name) for name in HELPER_PINS}
    need({name: sha(raw) for name, raw in helper_bytes.items()} == HELPER_PINS,
         'S106_HELPER_PIN')
    def load_helper(path, name):
        relative = Path(path).resolve().relative_to(repo.resolve()).as_posix()
        need(relative in helper_bytes, 'S106_UNPINNED_HELPER')
        return frozen_module(path, helper_bytes[relative], name)
    prefix = load_helper(repo / next(iter(HELPER_PINS)), '_s106_pinned_prefix')
    prefix._load_module = load_helper
    pins = prefix.verify_pins()
    overlay = prefix.generated_overlay()
    need(pins['source_closure_sha256'] == SOURCE_SHA and len(pins['sources']) == 53
         and closure(pins['sources']) == SOURCE_SHA
         and pins['profile_sha256'] == PROFILE_SHA and sha(overlay) == OVERLAY_SHA,
         'S106_BASE_PINS')
    verify_files(repo, HELPER_PINS)
    return pins, overlay, helper_bytes


def binding_hash(context):
    return sha(encoded({k: v for k, v in context.items() if k != 'campaign_sha256'}))


def validate_context(context, root):
    need(context['schema'] == 'gt06-s106-handle-boundary-context-v1'
         and RUN_ID.fullmatch(context['run_id']) and root.name == context['run_id'],
         'S106_CONTEXT_RUN')
    need(type(context['index']) is int and context['index'] == 0
         and type(context['attempt']) is int and context['attempt'] == 1,
         'S106_CONTEXT_SLOT')
    need(type(context['limit_batches']) is int and context['limit_batches'] in (1, 6)
         and context['capture_boundaries'] == ([0] if context['limit_batches'] == 1 else [4, 5]),
         'S106_CONTEXT_BOUNDARIES')
    need(context['source_closure_sha256'] == SOURCE_SHA
         and len(context['source_files']) == 53 and closure(context['source_files']) == SOURCE_SHA
         and context['profile_sha256'] == PROFILE_SHA
         and context['generated_overlay_sha256'] == OVERLAY_SHA
         and context['helper_original_pins'] == HELPER_PINS,
         'S106_CONTEXT_PINS')
    need(context['diagnostic_closure_sha256'] == closure(context['diagnostic_files'])
         and context['campaign_sha256'] == binding_hash(context), 'S106_CONTEXT_HASH')
    need(context['formal_acceptance'] is False and context['eligible_for_dataset'] is False,
         'S106_CONTEXT_SCOPE')


def capture_valid(capture, identity, executable):
    need(capture.get('status') == 'OBSERVED' and capture.get('binding_verified') is True
         and capture.get('errors') == []
         and capture.get('cleanup', {}).get('all_released') is True
         and capture.get('cleanup', {}).get('held_resources') == [], 'S106_PSS_UNKNOWN')
    observed = capture.get('identity') or {}
    need(all(observed.get(k) == identity[k] for k in ('pid', 'process_start'))
         and observed.get('executable') == ntpath.normcase(ntpath.normpath(executable)),
         'S106_PSS_IDENTITY')
    need(type(capture.get('handles_captured')) is int
         and capture['handles_captured'] == len(capture.get('entries', [])),
         'S106_PSS_ENTRY_COUNT')


class GateObserver:
    """Preserve original screen outcome; instrumentation has separate receipts."""
    def __init__(self, root, context, original, adapter, *, writer=write_new):
        self.root, self.context, self.original, self.adapter = root, context, original, adapter
        self.writer, self.probe, self.seen = writer, None, []

    def __call__(self, sample, baseline):
        primary = None
        try:
            self.original(sample, baseline)
        except BaseException as error:
            primary = error
        index = sample.get('index')
        errors = []
        try:
            need(type(index) is int and index == len(self.seen)
                 and index < self.context['limit_batches'], 'S106_BATCH_ORDER')
            self.seen.append(index)
            if index in self.context['capture_boundaries'] or primary is not None:
                sample_path = self.root / f'sample-preview-{index:02d}.json'
                need(decode(read(sample_path)) == sample, 'S106_SAMPLE_READBACK')
                sample_ref = ref(self.root, sample_path)
                baseline_ref = None
                if index == 5:
                    baseline_path = self.root / 'sample-preview-04.json'
                    need(decode(read(baseline_path))['memory'] == baseline, 'S106_BASELINE_BINDING')
                    baseline_ref = ref(self.root, baseline_path)
                else:
                    need(baseline is None, 'S106_UNEXPECTED_BASELINE')
                gate = {
                    'schema': 'gt06-s106-original-gate-v1', 'run_id': self.context['run_id'],
                    'index': index, 'result': 'FAILED' if primary is not None else 'PASSED',
                    'error': error_record(primary) if primary is not None else None,
                    'context': ref(self.root, self.root / 'context.json'),
                    'sample': sample_ref, 'baseline': baseline_ref,
                    'recorded_perf_ns': time.perf_counter_ns(),
                    'formal_acceptance': False, 'eligible_for_dataset': False,
                }
                gate_path = self.root / 'gates' / f'batch-{index:02d}.json'
                self.writer(gate_path, gate)
                need(decode(read(gate_path)) == gate, 'S106_GATE_READBACK')
                if index in self.context['capture_boundaries']:
                    need(self.probe is not None, 'S106_PROBE_MISSING')
                    identity = sample['processes']['editor']
                    need(identity == {'pid': self.probe.pid, 'process_start': self.probe.process_start},
                         'S106_SAMPLE_PROCESS_BINDING')
                    started = time.perf_counter_ns()
                    capture = self.adapter.capture_owned(self.probe)
                    payload = {
                        'schema': 'gt06-s106-gate-snapshot-v1', 'run_id': self.context['run_id'],
                        'index': index, 'source_closure_sha256': SOURCE_SHA, 'profile_sha256': PROFILE_SHA,
                        'diagnostic_closure_sha256': self.context['diagnostic_closure_sha256'],
                        'context': gate['context'], 'original_gate': ref(self.root, gate_path),
                        'sample': sample_ref, 'baseline': baseline_ref,
                        'capture_started_perf_ns': started, 'capture': capture,
                        'formal_acceptance': False, 'eligible_for_dataset': False,
                    }
                    path = self.root / 'pss' / f'batch-{index:02d}.json'
                    self.writer(path, payload)
                    need(decode(read(path)) == payload, 'S106_SNAPSHOT_READBACK')
                    capture_valid(capture, identity, self.context['godot_executable'])
        except BaseException as error:
            errors.append(error)
            try:
                self.writer(self.root / 'instrumentation' / f'batch-{index}.json', {
                    'schema': 'gt06-s106-instrumentation-error-v1', 'run_id': self.context['run_id'],
                    'index': index, 'primary_gate_error': error_record(primary) if primary else None,
                    'error': error_record(error), 'formal_acceptance': False, 'eligible_for_dataset': False})
            except BaseException as receipt_error:
                errors.append(receipt_error)
        if primary is not None:
            primary.s106_instrumentation_errors = tuple(errors)
            raise primary
        if errors:
            errors[0].s106_instrumentation_errors = tuple(errors[1:])
            raise errors[0]
        if index == self.context['limit_batches'] - 1:
            raise DiagnosticError('S106_PREFIX_BOUNDARY')


def child(root):
    root = root.resolve()
    studio, repo = root.parents[2], root.parents[3]
    context = decode(read(root / 'context.json'))
    validate_context(context, root)
    verify_files(repo, context['diagnostic_files'])
    verify_files(studio, context['source_files'])
    sys.path.insert(0, str(repo))
    from studio.tests.replay import run_benchmark_campaign as campaign
    campaign.load_fixture()  # Populate exact imported base53 before source equality.
    need(campaign.source_files() == context['source_files'], 'S106_CHILD_SOURCE_SET')
    adapter_path = repo / context['diagnostic_paths']['pss_adapter.py']
    adapter = frozen_module(adapter_path, read(adapter_path), '_s106_frozen_pss')
    overlay = read(repo / context['diagnostic_paths']['overlay.gd'])
    need(sha(overlay) == OVERLAY_SHA, 'S106_OVERLAY_PIN')
    observer = GateObserver(root, context, campaign.screen_sample, adapter)
    original_prepare, original_probe, original_screen = campaign.prepare, campaign.open_probe, campaign.screen_sample
    def prepare(project, factory, trusted, binding):
        initial = original_prepare(project, factory, trusted, binding)
        target = project / 'addons/hh_benchmark/benchmark_native.gd'
        need(sha(read(target)) == NATIVE_SHA, 'S106_GENERATED_BASE_PIN')
        temporary = target.with_name(target.name + '.s106-overlay')
        write_new(temporary, overlay)
        temporary.replace(target)
        need(read(target) == overlay, 'S106_OVERLAY_READBACK')
        initial['addons/hh_benchmark/benchmark_native.gd'] = OVERLAY_SHA
        return initial
    def open_probe(owner, executable):
        probe = original_probe(owner, executable)
        observer.probe = probe
        return probe
    campaign.prepare, campaign.open_probe, campaign.screen_sample = prepare, open_probe, observer
    try:
        campaign.run_child(root)
    finally:
        campaign.prepare, campaign.open_probe, campaign.screen_sample = original_prepare, original_probe, original_screen


def wait_owner(owner, root, context, stop_reader, timeout_seconds, *, clock=time.monotonic, sleep=time.sleep):
    started = clock()
    def stopping():
        return stop_reader(root, run_id=context['run_id'],
                           source_closure_sha256=context['source_closure_sha256'],
                           campaign_sha256=context['campaign_sha256'])
    while True:
        stop = stopping()
        code = owner.tick(stop=stop)
        if code is not None:
            need(not stopping(), 'BENCHMARK_STOPPED')
            return code
        need(clock() - started <= timeout_seconds, 'S106_OUTER_TIMEOUT')
        sleep(.05)


def own_run(factory, root, context, stop_reader, timeout_seconds, *, wait=wait_owner):
    """Constructor/Stop/close failures are separate; never replace primary."""
    owner, primary, helper_exit = None, None, None
    errors = []
    try:
        need(not stop_reader(root, run_id=context['run_id'],
                             source_closure_sha256=context['source_closure_sha256'],
                             campaign_sha256=context['campaign_sha256']), 'BENCHMARK_STOPPED')
        owner = factory()
        helper_exit = wait(owner, root, context, stop_reader, timeout_seconds)
    except BaseException as error:
        primary = error
        owner = owner or getattr(error, 'cleanup_owner', None)
    finally:
        if owner is not None:
            try:
                owner.close()
            except BaseException as error:
                errors.append(error)
    return {'primary_error': error_record(primary) if primary is not None else None,
            'cleanup_errors': [error_record(e) for e in errors], 'helper_exit_observed_by_tick': helper_exit,
            'timed_out': primary is not None and getattr(primary, 'code', None) == 'S106_OUTER_TIMEOUT'}, owner


def clean_job(job):
    return (type(job) is dict and job.get('closed') is True and job.get('zero_observed') is True
            and job.get('active_count') == 0 and job.get('handle_retained') is False
            and job.get('tainted') is False and job.get('create_uncertain') is False
            and job.get('close_uncertain') is False and job.get('failed_operations') == [])


def clean_handle(value):
    return (type(value) is dict and value.get('closed') is True
            and value.get('handle_retained') is False and value.get('close_uncertain') is False)


def target_exit(root, role):
    start_path, exit_path = root / role / 'process-start.json', root / role / 'process-exit.json'
    start = decode(read(start_path)) if start_path.is_file() else None
    actual = decode(read(exit_path)) if exit_path.is_file() else None
    if start is not None:
        need(set(start) == {'pid'} and type(start['pid']) is int and start['pid'] > 0, 'S106_TARGET_START')
    if actual is not None:
        need(start is not None and set(actual) == {'pid', 'exit_code'}
             and type(actual['pid']) is int and actual['pid'] == start['pid']
             and type(actual['exit_code']) is int, 'S106_TARGET_EXIT')
    return {'start': start, 'actual_exit': actual,
            'start_ref': ref(root, start_path) if start is not None else None,
            'exit_ref': ref(root, exit_path) if actual is not None else None,
            'status': 'OBSERVED' if actual is not None else 'UNKNOWN'}


def validate_lifecycle(root, context, failure):
    terminal = decode(read(root / 'child-terminal-cleanup.json'))
    need(terminal['run_id'] == context['run_id'] and terminal['source_closure_sha256'] == SOURCE_SHA
         and terminal['profile_sha256'] == PROFILE_SHA
         and terminal['context'] == ref(root, root / 'context.json') and terminal['errors'] == []
         and terminal['completed_batches'] == failure['completed_batches']
         and terminal['primary_error']['code'] == failure['code'], 'S106_TERMINAL_BINDING')
    observed = terminal['observations']
    need(observed['heartbeat_alive'] is False and 'constructor_owner' not in observed, 'S106_HEARTBEAT_HELD')
    for probe in (observed['editor_probe'], observed['producer']['observer_probe']):
        need(probe == {'present': True, 'handle_retained': False, 'close_uncertain': False}, 'S106_PROBE_HELD')
    imported = observed['import_observer']
    need(imported == {'present': True, 'closed': True, 'thread_alive': False, 'handle_retained': False,
                     'handle_close_uncertain': False, 'probe_handles_released': True,
                     'global_held_probe_count': 0, 'error_count': 0}, 'S106_IMPORT_OBSERVER_HELD')
    producer = observed['producer']
    host, journal = producer['host'], producer['journal']
    need(producer['present'] is True and producer['closed'] is True
         and host['stopped'] is True and host['closing'] is True
         and host['main_socket_closed'] is True and host['control_socket_closed'] is True
         and all(v is False for v in host['threads_alive'])
         and journal == {'cache_closed': True, 'index_retained': False,
                         'database_retained': False, 'directory_retained': False}, 'S106_PRODUCER_HELD')
    editor = observed['editor_owner']
    need(editor['present'] is True and editor['closed'] is True and clean_job(editor['job'])
         and clean_handle(editor['wrapper_process_handle'])
         and all(v is False for v in editor['drain_threads_alive'])
         and type(editor['helper_exit_code']) is int, 'S106_EDITOR_OWNER_HELD')
    cleanups = sorted((root / 'host-owner').glob('cleanup-*.json'))
    need(bool(cleanups), 'S106_HOST_CLEANUP_MISSING')
    owner = decode(read(cleanups[-1]))
    need(owner['closed'] is True and clean_job(owner['job'])
         and clean_handle(owner['wrapper_process_handle'])
         and type(owner['wrapper_exit_code']) is int, 'S106_HOST_OWNER_HELD')
    exits = {role: target_exit(root, role) for role in ('host-owner', 'editor-host', 'import-host')}
    need(exits['host-owner']['actual_exit'] is not None and exits['editor-host']['start'] is not None
         and exits['import-host']['actual_exit'] is not None
         and exits['import-host']['actual_exit']['exit_code'] == 0, 'S106_LIFECYCLE_MISSING')
    need(exits['host-owner']['actual_exit']['exit_code'] == 1
         and owner['wrapper_exit_code'] == 1, 'S106_EXPECTED_EXCEPTION_EXIT')
    imported_capture = decode(read(root / 'import-host/capture.json'))
    need(imported_capture['actual_process_exit'] == exits['import-host']['actual_exit']
         and imported_capture['wrapper_exit_code'] == 0 and clean_job(imported_capture['job']),
         'S106_IMPORT_CLEANUP')
    return {'cleanup_status': 'RECORDED_JOB_PROBE_THREAD_RELEASES_VERIFIED', 'actual_exits': exits,
            'host_helper_exit': owner['wrapper_exit_code'], 'editor_helper_exit': editor['helper_exit_code'],
            'import_helper_exit': imported_capture['wrapper_exit_code'],
            'import_wrapper_process_handle': {'status': 'UNKNOWN', 'reason': 'NOT_IN_IMPORT_CAPTURE'},
            'outer_runner_actual_exit': {'status': 'UNKNOWN', 'actual_exit': None,
                                         'reason': 'NOT_OBSERVABLE_BY_SELF_RESULT'},
            'editor_actual_exit_status': exits['editor-host']['status'],
            'natural_editor_exit_proven': False,
            'terminal': ref(root, root / 'child-terminal-cleanup.json'), 'host_cleanup': ref(root, cleanups[-1])}


def validate_batches(root, context, count):
    """Reconstruct every batch from the unchanged assembler and exact raw refs."""
    from studio.tests.replay import run_benchmark_campaign as campaign
    need(type(count) is int and 1 <= count <= 6, 'S106_BATCH_COUNT')
    names = [f'batch-capture-{i:02d}.json' for i in range(count)]
    need(sorted(p.name for p in root.glob('batch-capture-*.json')) == names, 'S106_BATCH_CAPTURE_SET')
    need(sorted(p.name for p in root.glob('sample-preview-*.json'))
         == [f'sample-preview-{i:02d}.json' for i in range(count)], 'S106_SAMPLE_SET')
    rows, identities = [], None
    for index in range(count):
        path = root / names[index]
        capture = decode(read(path))
        need(set(capture) == {'index', 'native', 'command', 'joint', 'ack', 'ready', 'start'}
             and type(capture['index']) is int and capture['index'] == index, 'S106_BATCH_CAPTURE_SHAPE')
        bound = {key: campaign.read_artifact(root, value) for key, value in capture.items() if key != 'index'}
        joint = bound['joint'].value
        processes = joint['processes']
        need(identities is None or identities == processes, 'S106_BATCH_PAIR_CHANGED')
        identities = processes
        need(len(bound['command'].value['commands']) == 1000
             and len(bound['native'].value['cycles']) == 100, 'S106_BATCH_WORKLOAD')
        sample = campaign.assemble_sample(bound['native'], bound['command'], bound['joint'],
            run_id=context['run_id'], index=index, processes=processes,
            source_closure_sha256=context['source_closure_sha256'],
            barrier_receipt=joint['barrier_receipt'], ack=bound['ack'], ready=bound['ready'], start=bound['start'])
        sample_path = root / f'sample-preview-{index:02d}.json'
        need(encoded(decode(read(sample_path))) == encoded(sample), 'S106_SAMPLE_RECONSTRUCTION')
        rows.append({'index': index, 'batch': ref(root, path), 'sample': ref(root, sample_path),
                     'http_commands': 1000, 'native_cycles': 100})
    return {'count': count, 'rows': rows, 'processes': identities}


def summarize(root, context, owner_result, *, postflight_errors=()):
    """Derived report; raw failure/snapshots/exits are never rewritten."""
    result = {'schema': 'gt06-s106-handle-boundary-result-v1', 'run_id': context['run_id'],
              'status': 'INCOMPLETE', 'capture_status': 'INCOMPLETE', 'lifecycle': None,
              'formal_acceptance': False, 'eligible_for_dataset': False, 'limitations': LIMITATIONS,
              'owner': owner_result, 'errors': list(postflight_errors), 'snapshots': [],
              'engine_started': (root / 'import-host/process-start.json').is_file(),
              'source_closure_sha256': SOURCE_SHA, 'profile_sha256': PROFILE_SHA,
              'diagnostic_closure_sha256': context['diagnostic_closure_sha256']}
    result['actual_exits'] = {}
    for role in ('host-owner', 'editor-host', 'import-host'):
        try:
            result['actual_exits'][role] = target_exit(root, role)
        except BaseException as error:
            result['actual_exits'][role] = {'status': 'UNKNOWN', 'error': error_record(error)}
    result['outer_runner_actual_exit'] = {'status': 'UNKNOWN', 'actual_exit': None,
                                          'reason': 'NOT_OBSERVABLE_BY_SELF_RESULT'}
    try:
        validate_context(context, root)
        need(owner_result['primary_error'] is None and owner_result['cleanup_errors'] == []
             and not owner_result['timed_out'] and not postflight_errors, 'S106_OWNER_OR_POSTFLIGHT_FAILURE')
        failure = decode(read(root / 'child-failure.json'))
        result['child_failure'] = failure
        need(failure['run_id'] == context['run_id'] and failure['completed'] is False
             and failure['formal_acceptance'] is False, 'S106_FAILURE_BINDING')
        code, count = failure['code'], failure['completed_batches']
        need(code == 'S106_PREFIX_BOUNDARY' or code in SCREEN_CODES, 'S106_UNEXPECTED_CHILD_FAILURE')
        need(type(count) is int and count == context['limit_batches']
             and failure['phase']['batch'] == count - 1, 'S106_PREFIX_LENGTH')
        result['batches'] = validate_batches(root, context, count)
        expected = context['capture_boundaries']
        need(sorted(p.name for p in (root / 'pss').glob('*.json'))
             == [f'batch-{i:02d}.json' for i in expected], 'S106_SNAPSHOT_SET')
        need(not list((root / 'instrumentation').glob('*.json')), 'S106_INSTRUMENTATION_FAILED')
        identities = None
        for index in expected:
            sample_path = root / f'sample-preview-{index:02d}.json'
            sample = decode(read(sample_path))
            baseline_ref = ref(root, root / 'sample-preview-04.json') if index == 5 else None
            gate_path = root / 'gates' / f'batch-{index:02d}.json'
            gate, snapshot = decode(read(gate_path)), decode(read(root / 'pss' / f'batch-{index:02d}.json'))
            terminal_gate = index == context['limit_batches'] - 1
            gate_failed = terminal_gate and code in SCREEN_CODES
            need(gate['run_id'] == context['run_id'] and gate['index'] == index
                 and gate['result'] == ('FAILED' if gate_failed else 'PASSED')
                 and (gate['error']['code'] == code if gate_failed else gate['error'] is None), 'S106_GATE_OUTCOME')
            need(snapshot['run_id'] == context['run_id'] and snapshot['index'] == index
                 and snapshot['source_closure_sha256'] == SOURCE_SHA and snapshot['profile_sha256'] == PROFILE_SHA
                 and snapshot['diagnostic_closure_sha256'] == context['diagnostic_closure_sha256']
                 and snapshot['formal_acceptance'] is False and snapshot['eligible_for_dataset'] is False
                 and snapshot['context'] == gate['context'] == ref(root, root / 'context.json')
                 and snapshot['sample'] == gate['sample'] == ref(root, sample_path)
                 and snapshot['baseline'] == gate['baseline'] == baseline_ref
                 and snapshot['original_gate'] == ref(root, gate_path)
                 and snapshot['capture_started_perf_ns'] >= gate['recorded_perf_ns'], 'S106_SNAPSHOT_BINDING')
            capture_valid(snapshot['capture'], sample['processes']['editor'], context['godot_executable'])
            need(identities is None or identities == sample['processes'], 'S106_PAIR_IDENTITY')
            identities = sample['processes']
            result['snapshots'].append(ref(root, root / 'pss' / f'batch-{index:02d}.json'))
        result['capture_status'] = 'COMPLETE'
        lifecycle = validate_lifecycle(root, context, failure)
        need(lifecycle['actual_exits']['host-owner']['start']['pid'] == identities['host']['pid']
             and lifecycle['actual_exits']['editor-host']['start']['pid'] == identities['editor']['pid']
             and identities == result['batches']['processes'],
             'S106_LIFECYCLE_IDENTITY')
        tick_exit = owner_result['helper_exit_observed_by_tick']
        need(type(tick_exit) is int and tick_exit == lifecycle['host_helper_exit'], 'S106_HELPER_EXIT_BINDING')
        result['lifecycle'] = lifecycle
        result['status'] = 'BOUNDARY_CAPTURED' if code == 'S106_PREFIX_BOUNDARY' else 'ORIGINAL_GATE_FAILURE_CAPTURED'
    except BaseException as error:
        result['errors'].append(error_record(error))
    if owner_result['primary_error'] is not None:
        primary_code = owner_result['primary_error']['code']
        if primary_code == 'BENCHMARK_STOPPED':
            result['status'] = 'STOPPED'
        elif primary_code == 'S106_OUTER_TIMEOUT':
            result['status'] = 'TIMED_OUT'
    return result


def freeze(repo, run_id, limit, pins, overlay, helpers):
    need(RUN_ID.fullmatch(run_id) and limit in (1, 6), 'S106_RUN_ARGUMENTS')
    root = repo / 'studio/.local/reviews' / run_id
    frozen = HERE / 'owned' / run_id
    need(not os.path.lexists(root) and not os.path.lexists(frozen), 'S106_FRESH_RUN_REQUIRED')
    root.mkdir(parents=True)
    frozen.mkdir(parents=True)
    values = {'owned_handles.py': read(Path(__file__)), 'overlay.gd': overlay}
    values.update({Path(name).name: raw for name, raw in helpers.items()})
    files, paths = {}, {}
    for name, raw in values.items():
        target = frozen / name
        write_new(target, raw)
        relative = target.relative_to(repo).as_posix()
        files[relative], paths[name] = sha(raw), relative
    context = {
        'schema': 'gt06-s106-handle-boundary-context-v1', 'run_id': run_id, 'index': 0, 'attempt': 1,
        'source_files': pins['sources'], 'source_closure_sha256': SOURCE_SHA, 'profile_sha256': PROFILE_SHA,
        'generated_overlay_sha256': OVERLAY_SHA, 'helper_original_pins': HELPER_PINS,
        'diagnostic_files': files, 'diagnostic_paths': paths, 'diagnostic_closure_sha256': closure(files),
        'godot_executable': str(pins['executable']), 'godot_sha256': pins['godot_sha256'],
        'python_sha256': pins['python_sha256'], 'limit_batches': limit,
        'capture_boundaries': [0] if limit == 1 else [4, 5],
        'formal_acceptance': False, 'eligible_for_dataset': False,
    }
    context['campaign_sha256'] = binding_hash(context)
    validate_context(context, root)
    write_new(root / 'context.json', context)
    write_new(root / 'source-files.json', pins['sources'])
    return root, context


def run(run_id, limit):
    pins, overlay, helpers = checked_pins(REPO)
    root, context = freeze(REPO, run_id, limit, pins, overlay, helpers)
    from studio.tests.replay.benchmark_job import BenchmarkProcess
    sources = {'studio/' + name: digest for name, digest in pins['sources'].items()}
    sources.update(context['diagnostic_files'])
    sources[(root / 'context.json').relative_to(REPO).as_posix()] = sha(read(root / 'context.json'))
    argv = [sys.executable, '-B', str(REPO / context['diagnostic_paths']['owned_handles.py']), '--child', str(root)]
    factory = lambda: BenchmarkProcess(argv, cwd=root, output=root / 'host-owner', source_root=REPO,
                                       source_files=sources, binary_sha256=pins['python_sha256'], campaign_host=True)
    owner_result, owner = own_run(factory, root, context, pins['campaign'].stop_requested, 180 if limit == 1 else 1200)
    postflight = []
    for base, expected in ((REPO, sources), (REPO, HELPER_PINS)):
        try:
            verify_files(base, expected)
        except BaseException as error:
            postflight.append(error_record(error))
    result = summarize(root, context, owner_result, postflight_errors=postflight)
    write_new(root / 'diagnostic-result.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--preflight', action='store_true')
    group.add_argument('--prefix', action='store_true')
    group.add_argument('--child', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--run-id')
    args = parser.parse_args(argv)
    if args.child is not None:
        child(args.child)
        raise DiagnosticError('S106_CHILD_UNEXPECTED_RETURN')
    need(type(args.run_id) is str and RUN_ID.fullmatch(args.run_id), 'S106_RUN_ID')
    if args.check:
        pins, overlay, helpers = checked_pins(REPO)
        compile(read(Path(__file__)), str(Path(__file__)), 'exec')
        result = {'status': 'STATIC_PINS_VERIFIED', 'engine_started': False,
                  'run_id': args.run_id, 'source_closure_sha256': SOURCE_SHA,
                  'profile_sha256': PROFILE_SHA, 'generated_overlay_sha256': sha(overlay),
                  'helper_original_pins': {name: sha(raw) for name, raw in helpers.items()},
                  'source_file_count': len(pins['sources']), 'formal_acceptance': False,
                  'eligible_for_dataset': False, 'limitations': LIMITATIONS}
    else:
        result = run(args.run_id, 1 if args.preflight else 6)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] in ('STATIC_PINS_VERIFIED', 'BOUNDARY_CAPTURED', 'ORIGINAL_GATE_FAILURE_CAPTURED') else 3


if __name__ == '__main__':
    raise SystemExit(main())
