"""No-engine S129 regression tests; real copied PSS code, fake native API only."""
from copy import deepcopy
import ctypes as C
import hashlib
import importlib.util
import ntpath
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
ADAPTER_PATH = (BASE.parent / '20260920-gt06-s128-host-attribution' / 'owned' /
                'gt06-s128-host-attribution-01' / 'pss_adapter.py')
ADAPTER_SHA256 = '797398a54cac5f7c772df7ec9c5ad988fe9e54c26c3c10e172a768e39dc25c76'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


h = load('s129_helper_under_test', BASE / 'post_failure_handles.py')
p = load('s129_copied_pss_contract', ADAPTER_PATH)


class FakeKernel:
    """Exercise _Native.identity itself without DLLs or live process handles."""
    def __init__(self, probe, executable):
        self.probe, self.executable = probe, executable

    def GetProcessId(self, handle):
        return self.probe.pid

    def GetProcessTimes(self, handle, created, exited, kernel, user):
        start = int(self.probe.process_start.split(':')[1])
        target = C.cast(created, C.POINTER(p.FileTime)).contents
        target.low, target.high = start & 0xffffffff, start >> 32
        return 1

    def QueryFullProcessImageNameW(self, handle, flags, buffer, size):
        buffer.value = self.executable
        C.cast(size, C.POINTER(p.DWORD)).contents.value = len(self.executable)
        return 1


class FakeApi:
    current = 99

    def __init__(self, probe, executable):
        self.native = object.__new__(p._Native)
        self.native.k = FakeKernel(probe, executable)
        self.closed = []

    def identity(self, handle):
        return self.native.identity(handle)

    def require_live(self, handle):
        pass

    def count(self, handle):
        return 10

    def open_owned(self, pid):
        return 11

    def capture(self, handle):
        return 12

    def captured_count(self, snapshot):
        return 0

    def marker(self):
        return 13

    def walk(self, snapshot, marker):
        return None

    def free_marker(self, value):
        self.closed.append(('marker', value))
        return 0

    def free_snapshot(self, value):
        self.closed.append(('snapshot', value))
        return 0

    def close_process(self, value):
        self.closed.append(('process', value))
        return 0


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, duration):
        self.now += duration


def identities():
    return {'editor': {'pid': 100, 'process_start': 'windows:134343343434343434'},
            'host': {'pid': 200, 'process_start': 'windows:134343343434343435'}}


def probe_for(role):
    # Real ProcessProbe has no executable attribute.
    return SimpleNamespace(**identities()[role], handle=7, close_uncertain=False)


def counters():
    return {'host_mono_us': 123456, 'rss_bytes': {'value': 1000, 'unavailable_reason': None},
            'held_handles': {'value': 10, 'unavailable_reason': None},
            'visible_window_handles': ['42']}


def errors_record(errors):
    return [{'stage': stage, 'code': getattr(error, 'code', type(error).__name__)}
            for stage, error in errors]


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.binding = {'run_id': 's129-unit-only', 'index': 18, **identities()}
        self.writes, self.apis = {}, []

    def capture(self, probe):
        api = FakeApi(probe, r'C:\Pinned\Engine.exe' if probe.pid == 100 else r'C:\Pinned\Python.exe')
        self.apis.append(api)
        return p.capture_owned(probe, _api=api, _clock=lambda: 100)

    def observe(self, role='editor', **overrides):
        probe = overrides.pop('probe', probe_for(role))
        kwargs = dict(binding=self.binding, capture=self.capture,
                      write=lambda name, row: self.writes.__setitem__(name, deepcopy(row)),
                      check_stop=lambda: None, clock=self.clock, sleep=self.clock.sleep)
        if role == 'editor':
            kwargs['sample_editor'] = lambda target: counters()
            method = h.observe
        else:
            kwargs['sample_host'] = lambda target: {'process': identities()['host'], 'counters': counters()}
            method = h.observe_host
        kwargs.update(overrides)
        return method(probe, **kwargs)

    def test_real_copied_adapter_identity_and_capture_contract_for_both_roles(self):
        self.assertEqual(hashlib.sha256(ADAPTER_PATH.read_bytes()).hexdigest(), ADAPTER_SHA256)
        for role in ('editor', 'host'):
            with self.subTest(role=role):
                self.clock.now = 0
                rows = self.observe(role)
                receipt = self.writes[f'post-failure-{role}-complete.json']
                self.assertTrue(h.validate_observation_packet(rows, receipt, binding=self.binding, role=role))
                self.assertEqual([row['offset_seconds'] for row in rows], [0, 1, 3, 5])
                for row in rows:
                    self.assertIs(row['observation_validated'], True)
                    self.assertIs(row['formal_acceptance'], False)
                    self.assertIs(row['eligible_for_dataset'], False)
                identity = rows[0]['pss']['identity']
                self.assertEqual(set(identity), {'pid', 'process_start', 'executable'})
                self.assertNotIn('creation_filetime', identity)
                self.assertEqual(identity['process_start'], self.binding[role]['process_start'])
        for api in self.apis:
            self.assertEqual(api.closed, [('marker', 13), ('snapshot', 12), ('process', 11)])

    def test_pss_identity_mismatches_never_publish_a_completed_row(self):
        mutations = [lambda identity: identity.update(pid=999),
                     lambda identity: identity.update(process_start='windows:999'),
                     lambda identity: identity.pop('process_start'),
                     lambda identity: identity.pop('executable')]
        for role in ('editor', 'host'):
            for mutate in mutations:
                with self.subTest(role=role, mutation=mutations.index(mutate)):
                    self.writes.clear()
                    def capture(probe):
                        result = self.capture(probe)
                        mutate(result['identity'])
                        return result
                    with self.assertRaises(h.ObservationError):
                        self.observe(role, capture=capture)
                    self.assertEqual(set(self.writes), {f'post-failure-{role}-error.json'})

    def test_failed_pss_status_binding_cleanup_or_errors_never_publish_row(self):
        mutations = [lambda result: result.update(status='UNKNOWN'),
                     lambda result: result.update(binding_verified=False),
                     lambda result: result['cleanup'].update(all_released=False),
                     lambda result: result.update(errors=[{'code': 'PSS_TIME_BUDGET'}])]
        for mutate in mutations:
            with self.subTest(mutation=mutations.index(mutate)):
                self.writes.clear()
                def capture(probe):
                    result = self.capture(probe)
                    mutate(result)
                    return result
                with self.assertRaisesRegex(h.ObservationError, 'S129_PSS_INCOMPLETE'):
                    self.observe(capture=capture)
                self.assertEqual(set(self.writes), {'post-failure-editor-error.json'})

    def test_second_capture_executable_drift_keeps_partial_sequence_incomplete(self):
        def capture(probe):
            result = self.capture(probe)
            if len(self.apis) == 2:
                result['identity']['executable'] = r'C:\Wrong.exe'
            return result
        with self.assertRaisesRegex(h.ObservationError, 'S129_EDITOR_EXECUTABLE'):
            self.observe(capture=capture)
        self.assertNotIn('post-failure-editor-05.json', self.writes)
        self.assertNotIn('post-failure-editor-complete.json', self.writes)
        partial = [self.writes[f'post-failure-editor-{offset:02d}.json'] for offset in (0, 1, 3)]
        self.assertEqual(self.writes['post-failure-editor-error.json']['validated_offsets'], [0, 1, 3])
        with self.assertRaises(h.ObservationError):
            h.validate_observation_packet(partial, None, binding=self.binding, role='editor')

    def test_host_counter_sample_must_match_retained_identity(self):
        bad = {'process': {**identities()['host'], 'pid': 999}, 'counters': counters()}
        with self.assertRaisesRegex(h.ObservationError, 'S129_HOST_IDENTITY'):
            self.observe('host', sample_host=lambda probe: bad)
        self.assertEqual(self.apis, [])
        self.assertEqual(set(self.writes), {'post-failure-host-error.json'})

    def test_post_capture_stop_and_wall_limit_precede_successful_write(self):
        for failure in ('stop', 'deadline', 'probe_changed'):
            with self.subTest(failure=failure):
                self.writes.clear()
                self.clock.now = 0
                probe = probe_for('editor')
                def capture(target):
                    result = self.capture(target)
                    if failure == 'deadline':
                        self.clock.now = 8
                    elif failure == 'probe_changed':
                        target.process_start = 'windows:1'
                    return result
                checks = 0
                stop = KeyboardInterrupt('unit stop')
                def check_stop():
                    nonlocal checks
                    checks += 1
                    if failure == 'stop' and checks == 2:
                        raise stop
                with self.assertRaises((h.ObservationError, KeyboardInterrupt)) as raised:
                    self.observe(probe=probe, capture=capture, check_stop=check_stop)
                if failure == 'stop':
                    self.assertIs(raised.exception, stop)
                self.assertEqual(set(self.writes), {'post-failure-editor-error.json'})

    def test_packet_rejects_missing_receipt_stale_schema_and_tampered_rows(self):
        rows = self.observe()
        receipt = self.writes['post-failure-editor-complete.json']
        for failure in ('missing', 'false', 'stale', 'missing_marker', 'wrong_binding',
                        'reordered', 'missing_pss', 'identity', 'dataset', 'elapsed'):
            with self.subTest(failure=failure):
                changed, complete = deepcopy(rows), deepcopy(receipt)
                if failure == 'missing':
                    complete = None
                elif failure == 'false':
                    complete['completed'] = False
                elif failure == 'stale':
                    changed[0]['schema'] = 'S124.post-failure-observation.1'
                elif failure == 'missing_marker':
                    del changed[0]['observation_validated']
                elif failure == 'wrong_binding':
                    complete['binding']['host']['pid'] = 999
                elif failure == 'reordered':
                    changed.reverse()
                elif failure == 'missing_pss':
                    del changed[0]['pss']
                elif failure == 'identity':
                    changed[0]['pss']['identity']['pid'] = 999
                elif failure == 'dataset':
                    complete['eligible_for_dataset'] = True
                elif failure == 'elapsed':
                    changed[0]['elapsed_seconds'] = float('nan')
                with self.assertRaises(h.ObservationError):
                    h.validate_observation_packet(changed, complete, binding=self.binding, role='editor')

    def test_completion_receipt_write_failure_cannot_return_success(self):
        error = OSError('synthetic persistence failure')
        def write(name, row):
            if name.endswith('-complete.json'):
                raise error
            self.writes[name] = deepcopy(row)
        with self.assertRaises(OSError) as raised:
            self.observe(write=write)
        self.assertIs(raised.exception, error)
        self.assertNotIn('post-failure-editor-complete.json', self.writes)
        rows = [self.writes[f'post-failure-editor-{offset:02d}.json'] for offset in h.OFFSETS]
        with self.assertRaises(h.ObservationError):
            h.validate_observation_packet(rows, self.writes['post-failure-editor-error.json'],
                                          binding=self.binding, role='editor')


class BindingTests(unittest.TestCase):
    def test_pure_binding_validates_host_and_editor_independently_without_mutation(self):
        binding = identities()
        saved = deepcopy(binding)
        h.validate_roles(binding, editor=identities()['editor'], host=identities()['host'])
        self.assertEqual(binding, saved)
        for role in ('editor', 'host'):
            for key, value in (('pid', 999), ('process_start', 'windows:1')):
                with self.subTest(role=role, key=key):
                    actual = identities()
                    actual[role][key] = value
                    with self.assertRaisesRegex(h.ObservationError, f'S129_{role.upper()}_IDENTITY'):
                        h.validate_roles(binding, **actual)

    def test_executable_normalization_and_mismatch(self):
        binding = identities()
        binding['host']['executable'] = r'C:\Tools\Python.exe'
        observed = {**identities()['host'], 'executable': 'c:/TOOLS/python.exe'}
        result = h.validate_role_binding(binding, 'host', observed, require_executable=True)
        self.assertEqual(result['executable'], ntpath.normcase(r'C:\Tools\Python.exe'))
        observed['executable'] = r'C:\Wrong.exe'
        with self.assertRaisesRegex(h.ObservationError, 'S129_HOST_EXECUTABLE'):
            h.validate_role_binding(binding, 'host', observed, require_executable=True)


class PrimaryError(RuntimeError):
    def __init__(self, code='CAMPAIGN_RETAINED_COUNTER_GROWTH'):
        super().__init__(code)
        self.code = code


class Boundary(RuntimeError):
    pass


class GateTests(unittest.TestCase):
    def setUp(self):
        self.primary = PrimaryError()
        self.binding = identities()
        self.sample = {'index': 18, 'memory': {role: {'held_handles': {'value': 11}}
                                              for role in ('editor', 'host')}}
        self.baseline = {role: {'held_handles': {'value': 10}} for role in ('editor', 'host')}
        self.writes = {}

    def original_failure(self, sample, baseline):
        raise self.primary

    def observer(self, **overrides):
        kwargs = dict(original=self.original_failure, boundary=Boundary, limit=2,
                      stop_at_boundary=False, binding=lambda sample: self.binding,
                      probe=lambda: probe_for('editor'), host_probe=lambda: probe_for('host'),
                      observe_fn=Mock(), observe_host_fn=Mock(), error_record=errors_record,
                      write=lambda name, row: self.writes.__setitem__(name, deepcopy(row)))
        kwargs.update(overrides)
        return h.GateObserver(**kwargs)

    def assert_primary(self, observer):
        try:
            observer(self.sample, self.baseline)
        except BaseException as error:
            self.assertIs(error, self.primary)
            trace, names = error.__traceback__, []
            while trace is not None:
                names.append(trace.tb_frame.f_code.co_name)
                trace = trace.tb_next
            self.assertIn('original_failure', names)
        else:
            self.fail('original gate exception was swallowed')
        self.assertEqual(observer.gates, [])

    def test_stop_false_returns_naturally_through_full_35_row_boundary(self):
        marker = object()
        original = Mock(return_value=marker)
        observer = self.observer(original=original, limit=35, binding=Mock(side_effect=AssertionError))
        for index in range(35):
            self.assertIs(observer({'index': index}, {}), marker)
        self.assertEqual(len(observer.gates), 35)
        self.assertEqual(original.call_count, 35)
        self.assertEqual(self.writes, {})
        observer.observe_fn.assert_not_called()
        observer.observe_host_fn.assert_not_called()

    def test_stop_true_raises_boundary_only_after_original_gate_passes(self):
        original = Mock()
        observer = self.observer(original=original, stop_at_boundary=True)
        observer({'index': 0}, {})
        with self.assertRaisesRegex(Boundary, 'S129_PREFIX_BOUNDARY'):
            observer({'index': 1}, {})
        self.assertEqual(original.call_count, 2)
        self.assertEqual(observer.gates, [{'index': 0, 'original_gate': 'PASSED'},
                                          {'index': 1, 'original_gate': 'PASSED'}])

    def test_original_failure_wins_at_boundary_and_dispatches_only_growing_roles(self):
        for growing in (('editor',), ('host',), ('editor', 'host'), ()):
            with self.subTest(growing=growing):
                for role in ('editor', 'host'):
                    self.sample['memory'][role]['held_handles']['value'] = 11 if role in growing else 10
                observer = self.observer(stop_at_boundary=True, limit=1)
                self.assert_primary(observer)
                self.assertEqual(observer.observe_fn.call_count, int('editor' in growing))
                self.assertEqual(observer.observe_host_fn.call_count, int('host' in growing))
                self.assertIn('original-gate-failure.json', self.writes)

    def test_joint_host_mismatch_blocks_all_supplemental_observations(self):
        self.binding['host']['process_start'] = 'windows:1'
        observer = self.observer()
        self.assert_primary(observer)
        observer.observe_fn.assert_not_called()
        observer.observe_host_fn.assert_not_called()
        self.assertEqual(self.writes['post-failure-error.json']['errors'][0]['code'], 'S129_HOST_IDENTITY')

    def test_binding_receipt_probe_and_observer_failures_preserve_primary(self):
        broken = Mock(side_effect=KeyboardInterrupt('supplemental interruption'))
        cases = [dict(binding=broken), dict(probe=broken), dict(host_probe=broken),
                 dict(observe_fn=broken), dict(observe_host_fn=broken), dict(write=broken),
                 dict(error_record=broken)]
        for overrides in cases:
            with self.subTest(seam=next(iter(overrides))):
                self.assert_primary(self.observer(**overrides))

    def test_original_receipt_is_written_before_binding_or_supplemental_work(self):
        def binding(sample):
            self.assertIn('original-gate-failure.json', self.writes)
            raise ValueError('binding unavailable')
        self.assert_primary(self.observer(binding=binding))
        self.assertIn('post-failure-error.json', self.writes)

    def test_other_primary_codes_do_not_trigger_counter_observers(self):
        self.primary = PrimaryError('CAMPAIGN_STATUS_GAP')
        observer = self.observer()
        self.assert_primary(observer)
        observer.observe_fn.assert_not_called()
        observer.observe_host_fn.assert_not_called()

    def test_boundary_flag_requires_explicit_boolean(self):
        for value in (None, 0, 1, 'False'):
            with self.subTest(value=value), self.assertRaisesRegex(h.ObservationError, 'S129_BOUNDARY_FLAG'):
                self.observer(stop_at_boundary=value)


if __name__ == '__main__':
    unittest.main(verbosity=2)
