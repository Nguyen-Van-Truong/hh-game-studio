"""One bounded S108 full-workload prefix; observations are never acceptance."""
from __future__ import annotations

import argparse
import hashlib
import json
import ntpath
import os
from pathlib import Path
import re
import sys
import time
import types

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CORE_ORIGINAL = 'zdoc/reviews/20260919-gt06-s106-handle-boundary/owned_handles.py'
CORE_SHA256 = '956a1c56d215693fb5828e04b74db04fba45a57bfb0bde12bf76a11c21dcc1a0'
LOCAL_PINS = {
    'native_probe.py': '25282d0d302ba43c3d94fc653d0084a849dad5530b255f66e0f2a89ceb4b873a',
    'thread_probe.py': '8d31839b238c087eb59477d8031868c0df3b5fb34293152fbdc005be4a95a2c8',
    'clock_join.py': 'c59263b51a32045926d5f8e29df0d163b3429a79aef387631dabd9a9af6c5f85',
}
RUN_ID = re.compile(r'gt06-s108-save-[a-z0-9][a-z0-9-]{0,30}\Z')
OUTER_SECONDS = 1200
LIMIT_BATCHES = 7
MAX_SAMPLES = 8000
WINDOW_MARKER = 'HH_GT06_S108_MAIN_WINDOW '
LIMITATIONS = [
    'DIAGNOSTIC_ONLY_ORIGINAL_PROFILE_AND_GATES_NO_FORMAL_DATASET',
    'OBSERVER_OVERHEAD_RETAINED_NO_SUBTRACTION',
    'ENCLOSING_CPU_ACCOUNTING_IS_NOT_EXACT_SAVE_CPU_OR_WAIT_CAUSE',
    'CLOCK_BOUND_UNCERTAINTY_AND_SAMPLE_CADENCE_LIMIT_ATTRIBUTION',
    'NO_PSS_NO_POST_IDLE_SERIES_NO_AUTOMATIC_RETRY',
    'EXISTING_BOUNDARY_TEARDOWN_CAN_LEAVE_EDITOR_ACTUAL_EXIT_UNKNOWN',
    'OUTER_RUNNER_ACTUAL_EXIT_REQUIRES_PASSIVE_EXTERNAL_OBSERVER',
    'IMPORT_WRAPPER_NATIVE_CLOSE_BOOL_NOT_IN_ORIGINAL_CAPTURE',
]


def _core():
    path = HERE / 'core.py' if (HERE / 'core.py').is_file() else REPO / CORE_ORIGINAL
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CORE_SHA256:
        raise RuntimeError('S108_CORE_PIN')
    module = types.ModuleType('_s108_core')
    module.__file__ = str(path)
    sys.modules[module.__name__] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


c = _core()


def diagnostic_error_record(error):
    """Retain bounded native failure facts without exception text or handles."""
    value = c.error_record(error)
    for key in ('winerror', 'thread_exit_code'):
        observed = getattr(error, key, None)
        if type(observed) is int and 0 <= observed < 2**32:
            value[key] = observed
    cleanup = getattr(error, 'cleanup_error', None)
    if cleanup is not None:
        detail = c.error_record(cleanup)
        for key in ('winerror', 'thread_exit_code'):
            observed = getattr(cleanup, key, None)
            if type(observed) is int and 0 <= observed < 2**32:
                detail[key] = observed
        value['first_cleanup_error'] = detail
    return value


def check(repo=REPO):
    pins, save_overlay, historical = c.checked_pins(repo)
    local = {name: c.read(HERE / name) for name in LOCAL_PINS}
    c.need({name: c.sha(raw) for name, raw in local.items()} == LOCAL_PINS, 'S108_HELPER_PIN')
    native = c.frozen_module(HERE / 'native_probe.py', local['native_probe.py'], '_s108_native')
    base = c.read(repo / 'studio/tests/replay/benchmark_native.gd')
    overlay = native.build_overlay(base, save_overlay)
    c.need(type(overlay) is bytes and overlay and c.sha(base) == c.NATIVE_SHA, 'S108_OVERLAY')
    # Loading has no native API side effects; the sampler opens only on construction.
    sampler = c.frozen_module(HERE / 'thread_probe.py', local['thread_probe.py'], '_s108_sampler')
    c.need(callable(sampler.ThreadProbe), 'S108_SAMPLER_API')
    return pins, overlay, historical, local


def validate_context(context, root):
    c.need(context['schema'] == 'gt06-s108-save-attribution-context-v1'
           and RUN_ID.fullmatch(context['run_id']) and root.name == context['run_id'], 'S108_CONTEXT_RUN')
    c.need(type(context['index']) is int and context['index'] == 0
           and type(context['attempt']) is int and context['attempt'] == 1, 'S108_CONTEXT_SLOT')
    c.need(len(context['source_files']) == 53 and c.closure(context['source_files']) == c.SOURCE_SHA
           and context['source_closure_sha256'] == c.SOURCE_SHA
           and context['profile_sha256'] == c.PROFILE_SHA, 'S108_BASE_PIN')
    c.need(context['core_sha256'] == CORE_SHA256 and context['local_helper_pins'] == LOCAL_PINS
           and context['historical_helper_pins'] == c.HELPER_PINS
           and context['diagnostic_closure_sha256'] == c.closure(context['diagnostic_files'])
           and context['campaign_sha256'] == c.binding_hash(context), 'S108_CONTEXT_HASH')
    c.need(context['limit_batches'] == LIMIT_BATCHES and context['sample_batches'] == [5, 6]
           and context['outer_seconds'] == OUTER_SECONDS and context['max_thread_samples'] == MAX_SAMPLES
           and context['http_commands_per_batch'] == 1000 and context['native_cycles_per_batch'] == 100
           and context['formal_acceptance'] is False and context['eligible_for_dataset'] is False, 'S108_SCOPE')


def supplemental_binding(context):
    return {'schema_id': 'hh-studio.s108-save-attribution-context', 'schema_version': '1.0.0',
            'run_id': context['run_id'], 'base_source_closure_sha256': c.SOURCE_SHA,
            'profile_sha256': c.PROFILE_SHA, 'generated_overlay_sha256': context['generated_overlay_sha256'],
            'diagnostic_closure_sha256': context['diagnostic_closure_sha256']}


def freeze(run_id, pins, overlay, historical, local):
    c.need(RUN_ID.fullmatch(run_id), 'S108_RUN_ID')
    root = REPO / 'studio/.local/reviews' / run_id
    owned = HERE / 'owned' / run_id
    c.need(not os.path.lexists(root) and not os.path.lexists(owned), 'S108_FRESH_RUN_REQUIRED')
    root.mkdir(parents=True)
    owned.mkdir(parents=True)
    values = {'run_probe.py': c.read(Path(__file__)), 'core.py': c.read(REPO / CORE_ORIGINAL),
              'overlay.gd': overlay, **local}
    values.update({'historical-' + Path(name).name: raw for name, raw in historical.items()})
    paths, files = {}, {}
    for name, raw in values.items():
        path = owned / name
        c.write_new(path, raw)
        relative = path.relative_to(REPO).as_posix()
        paths[name], files[relative] = relative, c.sha(raw)
    context = {'schema': 'gt06-s108-save-attribution-context-v1', 'run_id': run_id, 'index': 0, 'attempt': 1,
               'source_files': pins['sources'], 'source_closure_sha256': c.SOURCE_SHA,
               'profile_sha256': c.PROFILE_SHA, 'core_sha256': CORE_SHA256,
               'local_helper_pins': LOCAL_PINS, 'historical_helper_pins': c.HELPER_PINS,
               'generated_overlay_sha256': c.sha(overlay), 'diagnostic_files': files,
               'diagnostic_paths': paths, 'diagnostic_closure_sha256': c.closure(files),
               'godot_executable': str(pins['executable']), 'godot_sha256': pins['godot_sha256'],
               'python_sha256': pins['python_sha256'], 'limit_batches': LIMIT_BATCHES,
               'sample_batches': [5, 6], 'outer_seconds': OUTER_SECONDS, 'max_thread_samples': MAX_SAMPLES,
               'http_commands_per_batch': 1000, 'native_cycles_per_batch': 100,
               'formal_acceptance': False, 'eligible_for_dataset': False}
    context['campaign_sha256'] = c.binding_hash(context)
    validate_context(context, root)
    c.write_new(root / 'context.json', context)
    c.write_new(root / 'source-files.json', pins['sources'])
    return root, context


class Collector:
    """Bounded in-memory hooks; unchanged gates always precede diagnostic stop."""
    def __init__(self, root, context, campaign, thread_factory, overlay, *, clock_ns=time.perf_counter_ns):
        self.root, self.context, self.campaign = root, context, campaign
        self.thread_factory, self.overlay, self.clock_ns = thread_factory, overlay, clock_ns
        self.probe = self.thread_probe = None
        self.startup = self.active = None
        self.publications, self.anchors, self.windows, self.gates, self.errors = [], [], [], [], []
        self.close_receipt = None
        self.originals = {key: getattr(campaign, key) for key in
                          ('prepare', 'open_probe', 'publish', 'NativeLog', 'screen_sample')}

    def issue(self, stage, error):
        c.need(len(self.errors) < 32, 'S108_ERROR_LIMIT')
        self.errors.append({'stage': stage, **diagnostic_error_record(error)})

    def attach(self, log):
        raw = c.read(log.owner.output / 'stdout.txt', 4 * 1024**2)
        markers = [c.decode(line[len(WINDOW_MARKER):]) for line in raw.decode('utf-8').splitlines()
                   if line.startswith(WINDOW_MARKER)]
        c.need(len(markers) == 1 and self.probe is not None, 'S108_WINDOW_MARKER')
        value = markers[0]
        c.need(value['schema_id'] == 'hh-studio.s108-main-window' and value['schema_version'] == '1.0.0'
               and value['formal_acceptance'] is False and value['eligible_for_dataset'] is False
               and value['run_id'] == self.context['run_id'] and value['pid'] == self.probe.pid
               and value['base_source_sha256'] == c.NATIVE_SHA
               and value['source_closure_sha256'] == c.SOURCE_SHA
               and value['profile_sha256'] == c.PROFILE_SHA
               and value['generated_overlay_sha256'] == self.context['generated_overlay_sha256']
               and value['diagnostic_closure_sha256'] == self.context['diagnostic_closure_sha256']
               and value['context_sha256'] == c.sha(c.read(self.root / 'project/benchmark/s108-context.json')),
               'S108_WINDOW_BINDING')
        c.need(type(value['hwnd']) is int and value['hwnd'] > 0 and value['window_id'] == 0
               and value['display_server'] == 'Windows' and value['main_thread'] is True
               and value['logical_thread'] == 'godot_editor_main' and value['windows_thread_id'] is None,
               'S108_MAIN_WINDOW')
        self.startup = value
        identity = {'pid': self.probe.pid, 'process_start': self.probe.process_start,
                    'executable': self.context['godot_executable']}
        try:
            self.thread_probe = self.thread_factory(self.probe, identity, value['hwnd'], max_samples=MAX_SAMPLES)
        except BaseException as error:
            self.thread_probe = getattr(error, 'cleanup_owner', None)
            raise

    def sample(self):
        if self.active in (5, 6) and self.thread_probe is not None and not self.errors:
            try:
                self.thread_probe.sample(self.active)
            except BaseException as error:
                self.issue('thread_sample', error)

    def prepare(self, project, factory, trusted, binding):
        initial = self.originals['prepare'](project, factory, trusted, binding)
        target = project / 'addons/hh_benchmark/benchmark_native.gd'
        c.need(c.sha(c.read(target)) == c.NATIVE_SHA, 'S108_GENERATED_BASE_PIN')
        c.need(c.sha(self.overlay) == self.context['generated_overlay_sha256'], 'S108_OVERLAY_PIN')
        temporary = target.with_name(target.name + '.s108-overlay')
        c.write_new(temporary, self.overlay)
        temporary.replace(target)
        c.need(c.read(target) == self.overlay, 'S108_OVERLAY_READBACK')
        initial['addons/hh_benchmark/benchmark_native.gd'] = c.sha(self.overlay)
        sidecar = project / 'benchmark/s108-context.json'
        c.write_new(sidecar, supplemental_binding(self.context))
        initial['benchmark/s108-context.json'] = c.sha(c.read(sidecar))
        return initial

    def open_probe(self, owner, executable):
        self.probe = self.originals['open_probe'](owner, executable)
        return self.probe

    def publish(self, path, payload):
        kind = {'hh-studio.native-cycle-batch-start': 'START', 'hh-studio.native-cycle-batch-ack': 'ACK'}[payload['schema_id']]
        index = payload['batch_index']
        c.need(type(index) is int and 0 <= index < LIMIT_BATCHES
               and len(self.publications) < 14, 'S108_PUBLICATION_BOUND')
        row = {'kind': kind, 'batch': index, 'path': path.relative_to(self.root).as_posix(),
               'published_payload': dict(payload), 'host_before_publish_us': self.clock_ns() // 1000,
               'completed': False}
        self.publications.append(row)
        # This timestamp precedes any original fsync/rename; its return value is
        # deliberately NOT used as the lower clock bound.
        try:
            result = self.originals['publish'](path, payload)
        except BaseException:
            self.active = None
            raise
        row.update(host_after_publish_us=self.clock_ns() // 1000, publish_return_host_us=result, completed=True)
        if kind == 'START' and index in (5, 6):
            self.active = index
            self.windows.append({'batch': index, 'host_start_publish_us': row['host_before_publish_us'],
                                 'host_start_return_us': row['host_after_publish_us'], 'host_batch_return_us': None})
            self.windows[-1]['host_start_return_us'] = row['host_after_publish_us']
            self.sample()
        return result

    def after_wait(self, log, suffix, index, value, received_us):
        if suffix == 'BATCH' and index in (5, 6):
            self.active = None
            self.windows[-1]['host_batch_return_us'] = received_us
        if suffix == 'READY' and index == 0:
            self.attach(log)
        if suffix == 'ACK':
            matching = [row for row in self.publications if row['kind'] == 'ACK' and row['batch'] == index]
            c.need(len(matching) == 1 and matching[0]['completed'], 'S108_ACK_PUBLICATION')
            row = matching[0]
            self.anchors.append({'kind': 'ACK', 'batch': index,
                'host_before_publish_us': row['host_before_publish_us'],
                'host_after_publish_us': row['host_after_publish_us'],
                'publish_return_host_us': row['publish_return_host_us'],
                'host_after_receipt_us': received_us, 'native_observed_us': value['ack_observed_mono_us'],
                'receipt': dict(value), 'publication_path': row['path']})

    def screen(self, sample, baseline):
        primary = None
        try:
            self.originals['screen_sample'](sample, baseline)
        except BaseException as error:
            primary = error
        try:
            index = sample['index']
            c.need(index == len(self.gates) and 0 <= index < LIMIT_BATCHES, 'S108_GATE_ORDER')
            self.gates.append({'index': index, 'result': 'FAILED' if primary else 'PASSED',
                               'error': c.error_record(primary) if primary else None,
                               'sample_path': f'sample-preview-{index:02d}.json',
                               'baseline_path': 'sample-preview-04.json' if index >= 5 else None,
                               'recorded_perf_ns': self.clock_ns()})
        except BaseException as error:
            self.issue('gate_record', error)
        if primary is not None:
            primary.s108_instrumentation_errors = tuple(self.errors)
            raise primary
        if self.errors:
            raise c.DiagnosticError('S108_INSTRUMENTATION_FAILED')
        if sample['index'] == LIMIT_BATCHES - 1:
            raise c.DiagnosticError('S108_PREFIX_BOUNDARY')

    def install(self):
        collector = self
        original = self.originals['NativeLog']
        class ObservedLog(original):
            def poll(self):
                code = super().poll()
                collector.sample()
                return code

            def wait(self, suffix, index, timeout):
                try:
                    value = super().wait(suffix, index, timeout)
                except BaseException:
                    if suffix == 'BATCH':
                        collector.active = None
                    raise
                received = collector.clock_ns() // 1000
                try:
                    collector.after_wait(self, suffix, index, value, received)
                except BaseException as error:
                    collector.issue('native_' + suffix.lower(), error)
                    if suffix == 'READY':
                        raise
                return value
        for name in ('prepare', 'open_probe', 'publish'):
            setattr(self.campaign, name, getattr(self, name))
        self.campaign.NativeLog, self.campaign.screen_sample = ObservedLog, self.screen

    def restore(self):
        for key, value in self.originals.items():
            setattr(self.campaign, key, value)

    def finish(self, primary, *, writer=c.write_new):
        """Called only after run_child's unchanged finally has returned."""
        self.active = None
        if self.thread_probe is not None:
            try:
                self.close_receipt = self.thread_probe.close()
            except BaseException as error:
                self.issue('thread_close', error)
                self.close_receipt = getattr(self.thread_probe, 'close_receipt', None)
        raw = {'schema': 'gt06-s108-save-attribution-raw-v1', 'run_id': self.context['run_id'],
               'source_closure_sha256': c.SOURCE_SHA, 'profile_sha256': c.PROFILE_SHA,
               'diagnostic_closure_sha256': self.context['diagnostic_closure_sha256'],
               'context': c.ref(self.root, self.root / 'context.json'),
               'primary_error': c.error_record(primary) if primary else None,
               'startup': self.startup, 'publications': self.publications, 'anchors': self.anchors,
               'native_windows': self.windows, 'gates': self.gates,
               'thread_identity': getattr(self.thread_probe, 'identity', None),
               'thread_samples': getattr(self.thread_probe, 'records', []),
               'thread_errors': getattr(self.thread_probe, 'errors', []),
               'thread_close': self.close_receipt, 'collector_errors': self.errors,
               'thread_cleanup': {'present': self.thread_probe is not None,
                    'closed': getattr(self.thread_probe, 'closed', False),
                    'handle_retained': getattr(self.thread_probe, 'handle', None) is not None,
                    'close_uncertain': getattr(self.thread_probe, 'close_uncertain', False)},
               'recorded_after_original_cleanup': True, 'formal_acceptance': False,
               'eligible_for_dataset': False, 'limitations': LIMITATIONS}
        writer(self.root / 'attribution-raw.json', raw)
        c.need(c.decode(c.read(self.root / 'attribution-raw.json')) == raw, 'S108_RAW_READBACK')
        if self.errors:
            raise c.DiagnosticError('S108_INSTRUMENTATION_FAILED')
        return raw


def execute_child(root, context, campaign, sampler, overlay, *, writer=c.write_new):
    observer = Collector(root, context, campaign, sampler.ThreadProbe, overlay)
    primary, final_errors = None, []
    observer.install()
    try:
        campaign.run_child(root)
        raise c.DiagnosticError('S108_CHILD_UNEXPECTED_RETURN')
    except BaseException as error:
        primary = error
    finally:
        observer.restore()
        try:
            observer.finish(primary, writer=writer)
        except BaseException as error:
            final_errors.append(c.error_record(error))
            if primary is None:
                primary = error
    if primary is not None:
        primary.s108_finalization_errors = final_errors
        # Console receipt survives a failed raw-file writer without replacing
        # the original exception. No arbitrary exception text or secrets.
        print('HH_GT06_S108_TERMINAL ' + json.dumps({'primary': c.error_record(primary),
              'collector_errors': observer.errors, 'finalization_errors': final_errors}), flush=True)
        raise primary


def child(root):
    root = root.resolve()
    studio, repo = root.parents[2], root.parents[3]
    context = c.decode(c.read(root / 'context.json'))
    validate_context(context, root)
    c.verify_files(repo, context['diagnostic_files'])
    c.verify_files(repo, context['historical_helper_pins'])
    c.verify_files(studio, context['source_files'])
    sys.path.insert(0, str(repo))
    from studio.tests.replay import run_benchmark_campaign as campaign
    campaign.load_fixture()
    c.need(campaign.source_files() == context['source_files'], 'S108_CHILD_SOURCE_SET')
    path = repo / context['diagnostic_paths']['thread_probe.py']
    sampler = c.frozen_module(path, c.read(path), '_s108_frozen_thread')
    overlay = c.read(repo / context['diagnostic_paths']['overlay.gd'])
    c.need(c.sha(overlay) == context['generated_overlay_sha256'], 'S108_OVERLAY_PIN')
    execute_child(root, context, campaign, sampler, overlay)


def validate_batches(root, context, count, campaign):
    c.need(type(count) is int and 1 <= count <= LIMIT_BATCHES, 'S108_BATCH_COUNT')
    c.need(sorted(path.name for path in root.glob('batch-capture-*.json'))
           == [f'batch-capture-{i:02d}.json' for i in range(count)]
           and sorted(path.name for path in root.glob('sample-preview-*.json'))
           == [f'sample-preview-{i:02d}.json' for i in range(count)], 'S108_BATCH_SET')
    identities, rows = None, []
    for index in range(count):
        path = root / f'batch-capture-{index:02d}.json'
        capture = c.decode(c.read(path))
        c.need(set(capture) == {'index', 'native', 'command', 'joint', 'ack', 'ready', 'start'}
               and capture['index'] == index, 'S108_BATCH_SHAPE')
        bound = {key: campaign.read_artifact(root, value) for key, value in capture.items() if key != 'index'}
        joint = bound['joint'].value
        c.need(identities is None or identities == joint['processes'], 'S108_PAIR_CHANGED')
        identities = joint['processes']
        c.need(len(bound['command'].value['commands']) == 1000
               and len(bound['native'].value['cycles']) == 100, 'S108_WORKLOAD')
        sample = campaign.assemble_sample(bound['native'], bound['command'], bound['joint'],
            run_id=context['run_id'], index=index, processes=identities,
            source_closure_sha256=c.SOURCE_SHA, barrier_receipt=joint['barrier_receipt'],
            ack=bound['ack'], ready=bound['ready'], start=bound['start'])
        sample_path = root / f'sample-preview-{index:02d}.json'
        c.need(c.decode(c.read(sample_path)) == sample, 'S108_SAMPLE_READBACK')
        rows.append({'index': index, 'capture': c.ref(root, path), 'sample': c.ref(root, sample_path),
                     'baseline': c.ref(root, root / 'sample-preview-04.json') if index >= 5 else None,
                     'http_commands': 1000, 'native_cycles': 100})
    return {'count': count, 'rows': rows, 'processes': identities}


def validate_raw(root, context, raw, failure, batches, campaign):
    count = batches['count']
    c.need(raw['run_id'] == context['run_id'] and raw['context'] == c.ref(root, root / 'context.json')
           and raw['diagnostic_closure_sha256'] == context['diagnostic_closure_sha256']
           and raw['source_closure_sha256'] == c.SOURCE_SHA and raw['profile_sha256'] == c.PROFILE_SHA
           and raw['primary_error']['code'] == failure['code'] and raw['collector_errors'] == []
           and raw['thread_errors'] == [] and raw['recorded_after_original_cleanup'] is True
           and raw['formal_acceptance'] is False and raw['eligible_for_dataset'] is False, 'S108_RAW_BINDING')
    c.need(len(raw['gates']) == len(raw['anchors']) == count
           and len(raw['publications']) == count * 2, 'S108_MARKER_COUNT')
    expected_error = None
    baseline = None
    for index, gate in enumerate(raw['gates']):
        sample = c.decode(c.read(root / f'sample-preview-{index:02d}.json'))
        error = None
        try:
            campaign.screen_sample(sample, baseline)
        except BaseException as observed:
            error = c.error_record(observed)
        c.need(gate['index'] == index and gate['sample_path'] == f'sample-preview-{index:02d}.json'
               and gate['baseline_path'] == ('sample-preview-04.json' if index >= 5 else None)
               and gate['result'] == ('FAILED' if error else 'PASSED') and gate['error'] == error,
               'S108_ORIGINAL_GATE_BINDING')
        c.need(error is None or index == count - 1, 'S108_CONTINUED_AFTER_GATE_FAILURE')
        if error:
            expected_error = error['code']
        if index == 4:
            baseline = sample['memory']
        anchor = raw['anchors'][index]
        joint = c.decode(c.read(root / f'joint-{index:02d}.json'))
        c.need(anchor['kind'] == 'ACK' and anchor['batch'] == index
               and anchor['receipt'] == joint['barrier_receipt']
               and anchor['native_observed_us'] == joint['barrier_receipt']['ack_observed_mono_us']
               and anchor['host_before_publish_us'] <= anchor['publish_return_host_us']
               <= anchor['host_after_publish_us'] <= anchor['host_after_receipt_us'], 'S108_ACK_ANCHOR')
        for position, kind in enumerate(('START', 'ACK')):
            row = raw['publications'][index * 2 + position]
            path = f'project/benchmark/input/{kind.lower()}-{index:02d}.json'
            c.need(row['kind'] == kind and row['batch'] == index and row['path'] == path
                   and row['completed'] is True and row['published_payload'] == c.decode(c.read(root / path)),
                   'S108_PUBLICATION_BINDING')
        c.need(anchor['publication_path'] == raw['publications'][index * 2 + 1]['path']
               and all(anchor[key] == raw['publications'][index * 2 + 1][key] for key in
                       ('host_before_publish_us', 'host_after_publish_us', 'publish_return_host_us')),
               'S108_ANCHOR_PUBLICATION_BINDING')
    c.need(failure['code'] == (expected_error or 'S108_PREFIX_BOUNDARY')
           and (expected_error is not None or count == LIMIT_BATCHES), 'S108_TERMINAL_GATE')
    identity = raw['thread_identity']
    c.need(identity['pid'] == batches['processes']['editor']['pid']
           and identity['process_start'] == batches['processes']['editor']['process_start']
           and identity['executable'] == ntpath.normcase(ntpath.normpath(context['godot_executable']))
           and identity['hwnd'] == raw['startup']['hwnd']
           and type(identity['tid']) is int and identity['tid'] > 0
           and type(identity['thread_created_100ns']) is int and identity['thread_created_100ns'] > 0,
           'S108_THREAD_PAIR')
    c.need(raw['thread_close'] is not None, 'S108_THREAD_CLOSE_MISSING')
    c.need(raw['thread_close']['status'] == 'CLOSED' and raw['thread_close']['native_close_result'] is True
           and raw['thread_cleanup'] == {'present': True, 'closed': True, 'handle_retained': False,
                                         'close_uncertain': False}, 'S108_THREAD_HELD')
    c.need(len(raw['thread_samples']) <= MAX_SAMPLES, 'S108_SAMPLE_BOUND')
    expected_windows = list(range(5, count))
    c.need([row['batch'] for row in raw['native_windows']] == expected_windows, 'S108_NATIVE_WINDOWS')
    for window in raw['native_windows']:
        c.need(window['host_start_publish_us'] <= window['host_start_return_us']
               <= window['host_batch_return_us'], 'S108_NATIVE_WINDOW_ORDER')
    c.need(all(row['batch'] in expected_windows for row in raw['thread_samples']), 'S108_SAMPLE_WINDOW')
    for batch in expected_windows:
        c.need(any(row['batch'] == batch for row in raw['thread_samples']), 'S108_MISSING_THREAD_SAMPLES')
    previous = None
    for index, row in enumerate(raw['thread_samples']):
        window = next(window for window in raw['native_windows'] if window['batch'] == row['batch'])
        c.need(row['index'] == index and all(row[key] == identity[key] for key in
                   ('pid', 'process_start', 'tid', 'thread_created_100ns'))
               and row['schema'] == 'gt06-s108-thread-cpu-sample-v1'
               and row['formal_acceptance'] is False and row['eligible_for_dataset'] is False
               and window['host_start_publish_us'] * 1000 <= row['sample_started_perf_ns']
               <= row['host_before_ns'] <= row['host_after_ns'] <= row['sample_ended_perf_ns']
               < (window['host_batch_return_us'] + 1) * 1000
               and row['times_api_duration_ns'] == row['host_after_ns'] - row['host_before_ns']
               and row['sample_duration_ns'] == row['sample_ended_perf_ns'] - row['sample_started_perf_ns'],
               'S108_SAMPLE_BINDING')
        c.need(previous is None or (row['sample_started_perf_ns'] - previous['sample_started_perf_ns'] >= 50_000_000
               and row['kernel_100ns'] >= previous['kernel_100ns'] and row['user_100ns'] >= previous['user_100ns']),
               'S108_SAMPLE_CADENCE_OR_COUNTERS')
        previous = row
    return {'raw': c.ref(root, root / 'attribution-raw.json'), 'anchor_count': count,
            'thread_sample_count': len(raw['thread_samples']), 'gates': raw['gates']}


def summarize(root, context, owner_result, campaign, postflight=()):
    result = {'schema': 'gt06-s108-save-attribution-result-v1', 'run_id': context['run_id'],
              'status': 'INCOMPLETE', 'capture_status': 'INCOMPLETE', 'owner': owner_result,
              'errors': list(postflight), 'formal_acceptance': False, 'eligible_for_dataset': False,
              'source_closure_sha256': c.SOURCE_SHA, 'profile_sha256': c.PROFILE_SHA,
              'diagnostic_closure_sha256': context['diagnostic_closure_sha256'], 'limitations': LIMITATIONS,
              'outer_runner_actual_exit': {'status': 'UNKNOWN', 'reason': 'PASSIVE_OBSERVER_REQUIRED'},
              'actual_exits': {}, 'lifecycle': None}
    for role in ('host-owner', 'editor-host', 'import-host'):
        try:
            result['actual_exits'][role] = c.target_exit(root, role)
        except BaseException as error:
            result['actual_exits'][role] = {'status': 'UNKNOWN', 'error': c.error_record(error)}
    try:
        validate_context(context, root)
        failure = c.decode(c.read(root / 'child-failure.json'))
        result['child_failure'] = failure
        c.need(failure['run_id'] == context['run_id'] and failure['completed'] is False
               and failure['formal_acceptance'] is False
               and failure['phase']['batch'] == failure['completed_batches'] - 1, 'S108_FAILURE_BINDING')
        result['batches'] = validate_batches(root, context, failure['completed_batches'], campaign)
        raw = c.decode(c.read(root / 'attribution-raw.json'))
        result['capture'] = validate_raw(root, context, raw, failure, result['batches'], campaign)
        result['capture_status'] = 'COMPLETE'
        c.need(owner_result['primary_error'] is None and owner_result['cleanup_errors'] == []
               and owner_result['helper_exit_observed_by_tick'] == 1 and not postflight, 'S108_OWNER_FAILURE')
        result['lifecycle'] = c.validate_lifecycle(root, context, failure)
        identities = result['batches']['processes']
        c.need(result['actual_exits']['host-owner']['start']['pid'] == identities['host']['pid']
               and result['actual_exits']['editor-host']['start']['pid'] == identities['editor']['pid'],
               'S108_LIFECYCLE_PAIR')
        result['status'] = ('BOUNDARY_CAPTURED' if failure['code'] == 'S108_PREFIX_BOUNDARY'
                            else 'ORIGINAL_GATE_FAILURE_CAPTURED')
    except BaseException as error:
        result['errors'].append(c.error_record(error))
    if owner_result['primary_error']:
        code = owner_result['primary_error']['code']
        if code == 'BENCHMARK_STOPPED':
            result['status'] = 'STOPPED'
        elif code == 'S106_OUTER_TIMEOUT':
            result['status'] = 'TIMED_OUT'
    return result


def selected_capture_paths(root):
    """Enumerate only bounded evidence slots, never journals/cache/private data."""
    names = ['context.json', 'source-files.json', 'initial-project-files.json', 'editor-snapshot.json',
             'editor-identity.json', 'import-observation.json', 'http-phases-final.json', 'child-failure.json',
             'child-terminal-cleanup.json', 'attribution-raw.json', 'diagnostic-result.json']
    for index in range(LIMIT_BATCHES):
        names += [f'{prefix}-{index:02d}.json' for prefix in ('command', 'joint', 'batch-capture', 'sample-preview')]
        names += [f'project/benchmark/input/{kind}-{index:02d}.json' for kind in ('start', 'ack')]
        names += [f'project/benchmark/out/{kind}-{index:02d}.json' for kind in ('batch', 'ready')]
    names += ['project/benchmark/out/ready-07.json', 'project/benchmark/s108-context.json']
    paths = {root / name for name in names if (root / name).is_file()}
    for role in ('host-owner', 'editor-host', 'import-host'):
        directory = root / role
        if directory.is_dir():
            for path in directory.iterdir():
                if path.is_file() and (path.suffix == '.json' or path.name in ('stdout.txt', 'stderr.txt')):
                    paths.add(path)
    initial = root / 'initial-project-files.json'
    if initial.is_file():
        for name in c.decode(c.read(initial)):
            c.need(not Path(name).is_absolute() and not Path(name).drive and '..' not in Path(name).parts,
                   'S108_PROJECT_PATH')
            path = root / 'project' / name
            if path.is_file():
                paths.add(path)
    c.need(len(paths) <= 240, 'S108_CAPTURE_FILE_BOUND')
    return sorted(paths)


def run(run_id):
    pins, overlay, historical, local = check()
    root, context = freeze(run_id, pins, overlay, historical, local)
    from studio.tests.replay.benchmark_job import BenchmarkProcess
    sources = {'studio/' + name: digest for name, digest in context['source_files'].items()}
    sources.update(context['diagnostic_files'])
    sources[(root / 'context.json').relative_to(REPO).as_posix()] = c.sha(c.read(root / 'context.json'))
    argv = [sys.executable, '-B', str(REPO / context['diagnostic_paths']['run_probe.py']), '--child', str(root)]
    factory = lambda: BenchmarkProcess(argv, cwd=root, output=root / 'host-owner', source_root=REPO,
                                       source_files=sources, binary_sha256=pins['python_sha256'], campaign_host=True)
    owner_result, _owner = c.own_run(factory, root, context, pins['campaign'].stop_requested, OUTER_SECONDS)
    postflight = []
    for expected in (sources, c.HELPER_PINS):
        try:
            c.verify_files(REPO, expected)
        except BaseException as error:
            postflight.append(c.error_record(error))
    result = summarize(root, context, owner_result, pins['campaign'], postflight)
    c.write_new(root / 'diagnostic-result.json', result)
    c.write_new(root / 'capture-manifest.json', {'schema': 'gt06-s108-capture-manifest-v1', 'run_id': run_id,
        'formal_acceptance': False, 'eligible_for_dataset': False, 'diagnostic_files': context['diagnostic_files'],
        'base_source_files': context['source_files'],
        'files': [pins['campaign'].reference(root, path) for path in selected_capture_paths(root)],
        'exclusions': ['.godot', 'localappdata', 'temp', 'commands journals and command stores', 'unlisted caches']})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--launch', action='store_true')
    group.add_argument('--child', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--run-id')
    args = parser.parse_args(argv)
    if args.child is not None:
        child(args.child)
        raise c.DiagnosticError('S108_CHILD_UNEXPECTED_RETURN')
    c.need(type(args.run_id) is str and RUN_ID.fullmatch(args.run_id), 'S108_RUN_ID')
    if args.check:
        pins, overlay, _historical, _local = check()
        result = {'status': 'STATIC_PINS_VERIFIED', 'run_id': args.run_id, 'engine_started': False,
                  'source_closure_sha256': c.SOURCE_SHA, 'profile_sha256': c.PROFILE_SHA,
                  'source_file_count': len(pins['sources']), 'generated_overlay_sha256': c.sha(overlay),
                  'local_helper_pins': LOCAL_PINS, 'formal_acceptance': False, 'eligible_for_dataset': False}
    else:
        result = run(args.run_id)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] in ('STATIC_PINS_VERIFIED', 'BOUNDARY_CAPTURED', 'ORIGINAL_GATE_FAILURE_CAPTURED') else 3


if __name__ == '__main__':
    raise SystemExit(main())
