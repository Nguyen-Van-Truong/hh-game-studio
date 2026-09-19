import copy
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('post_failure', Path(__file__).with_name('post_failure_handles.py'))
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class GateError(RuntimeError):
    def __init__(self, code='CAMPAIGN_RETAINED_COUNTER_GROWTH'):
        super().__init__(code)
        self.code = code


class Tests(unittest.TestCase):
    def setUp(self):
        self.sample = {'index': 5, 'memory': {'editor': {'held_handles': {'value': 560}}}}
        self.baseline = {'editor': {'held_handles': {'value': 555}}}
        self.events = []
        self.error = GateError()
        self.original = lambda *_: self.fail_gate()

    def fail_gate(self):
        self.events.append('gate')
        raise self.error

    def make(self, **changes):
        args = dict(original=self.original, boundary=RuntimeError, limit=7,
                    binding=lambda sample: {'editor': {'pid': 12, 'process_start': 'windows:34'}},
                    probe=lambda: 'retained',
                    observe_fn=lambda *_: self.events.append('observe'),
                    write=lambda name, row: self.events.append(name),
                    error_record=lambda errors: [stage for stage, error in errors])
        args.update(changes)
        return module.GateObserver(**args)

    def test_receipt_precedes_capture_and_primary_is_identical(self):
        with self.assertRaises(GateError) as caught:
            self.make()(self.sample, self.baseline)
        self.assertIs(caught.exception, self.error)
        self.assertEqual(self.events, ['gate', 'original-gate-failure.json', 'observe'])

    def test_receipt_failure_prevents_capture(self):
        def write(*args):
            raise OSError('unavailable')
        with self.assertRaises(GateError) as caught:
            self.make(write=write)(self.sample, self.baseline)
        self.assertIs(caught.exception, self.error)
        self.assertEqual(self.events, ['gate'])

    def test_capture_error_never_replaces_primary(self):
        def capture(*args):
            raise ValueError('capture failure')
        with self.assertRaises(GateError) as caught:
            self.make(observe_fn=capture)(self.sample, self.baseline)
        self.assertIs(caught.exception, self.error)
        self.assertIn('post-failure-error.json', self.events)

    def test_stop_during_observer_never_replaces_primary(self):
        def stopped(*args):
            raise KeyboardInterrupt()
        with self.assertRaises(GateError) as caught:
            self.make(observe_fn=stopped)(self.sample, self.baseline)
        self.assertIs(caught.exception, self.error)

    def test_other_failure_has_no_capture(self):
        self.error = GateError('CAMPAIGN_STATUS_GAP')
        with self.assertRaises(GateError):
            self.make()(self.sample, self.baseline)
        self.assertNotIn('observe', self.events)

    def test_no_handle_growth_has_no_capture(self):
        self.sample['memory']['editor']['held_handles']['value'] = 555
        with self.assertRaises(GateError):
            self.make()(self.sample, self.baseline)
        self.assertNotIn('observe', self.events)

    def test_passed_prefix_has_no_capture_and_stops(self):
        gate = self.make(original=lambda *_: None, limit=2)
        gate(self.sample, self.baseline)
        with self.assertRaisesRegex(RuntimeError, 'S124_PREFIX_BOUNDARY'):
            gate(self.sample, self.baseline)
        self.assertEqual(self.events, [])
        self.assertEqual(len(gate.gates), 2)

    def observe_args(self):
        self.now = 0
        self.records = []
        def sleep(amount):
            self.now += amount
        args = dict(binding={'editor': {'pid': 12, 'process_start': 'windows:34'}},
            sample_editor=lambda probe: {'held_handles': {'value': 555}},
            capture=lambda probe: {'status': 'OBSERVED', 'binding_verified': True,
                'identity': {'pid': 12, 'creation_filetime': 34}, 'cleanup': {'all_released': True}},
            write=lambda name, row: self.records.append((name, copy.deepcopy(row))),
            check_stop=lambda: None, clock=lambda: self.now, sleep=sleep)
        return args

    def test_post_failure_window_offsets_and_two_captures(self):
        rows = module.observe('retained', **self.observe_args())
        self.assertEqual([r['offset_seconds'] for r in rows], [0, 1, 3, 5])
        self.assertEqual(['pss' in r for r in rows], [True, False, False, True])
        self.assertEqual(self.now, 5)

    def test_unknown_snapshot_is_retained_then_stops(self):
        args = self.observe_args()
        args['capture'] = lambda probe: {'status': 'UNKNOWN', 'cleanup': {'all_released': False}}
        with self.assertRaisesRegex(module.ObservationError, 'PSS_INCOMPLETE'):
            module.observe('retained', **args)
        self.assertEqual(len(self.records), 1)

    def test_identity_mismatch_stops(self):
        args = self.observe_args()
        args['binding']['editor']['pid'] = 13
        with self.assertRaisesRegex(module.ObservationError, 'PSS_IDENTITY'):
            module.observe('retained', **args)

    def test_stop_prevents_native_capture(self):
        args = self.observe_args()
        def stop():
            raise RuntimeError('BENCHMARK_STOPPED')
        args['check_stop'] = stop
        with self.assertRaisesRegex(RuntimeError, 'BENCHMARK_STOPPED'):
            module.observe('retained', **args)
        self.assertEqual(self.records, [])

    def test_slow_native_capture_is_retained_and_no_second_call(self):
        args = self.observe_args()
        original = args['capture']
        def slow(probe):
            self.now += 9
            return original(probe)
        args['capture'] = slow
        with self.assertRaisesRegex(module.ObservationError, 'WALL_LIMIT'):
            module.observe('retained', **args)
        self.assertEqual(len(self.records), 1)


if __name__ == '__main__':
    unittest.main()
