"""Pure marker/formula checks; no engine, process, inventory or Docker calls."""
import copy
import json
import unittest

from studio.tests.replay import run_save_phase_diagnostic as diagnostic


class SavePhaseTests(unittest.TestCase):
    def fixture(self, signal=16000, preview_mode='stock'):
        binding = {'run_id': 'synthetic', 'source_closure_sha256': 'a' * 64,
                   'profile_sha256': 'b' * 64}
        batch = {'run_id': 'synthetic', 'pid': 123, 'index': 0, 'max_status_gap_ms': 20,
            'raw_timings': [{'index': 0, 'save': {'start_us': 1000, 'end_us': 21000},
                             'save_signal_mono_us': signal}]}
        rows = [{**binding, 'pid': 123, 'batch': 0, 'cycle': 0, 'start_us': 1000,
                 'preview_mode': preview_mode,
                 'return_kind': 'Error' if preview_mode == 'stock' else 'void',
                 'live_batch': 0, 'live_cycle': 0, 'live_phase': 7,
                 'event': event, 'monotonic_us': when, 'result': result}
                for event, when, result in [('return', 11000, 0 if preview_mode == 'stock' else None),
                                           ('signal', signal, None)]]
        return binding, batch, rows

    def raw(self, rows):
        beats = [{'run_id': 'synthetic', 'pid': 123, 'monotonic_us': value,
                  'batch': 0, 'cycle': 0, 'phase': 'SAVE_WAIT'} for value in (500, 20500)]
        return ''.join(prefix + json.dumps(row) + '\n' for prefix, values in
            ((diagnostic.MARKER, rows), ('HH_GT06_BENCHMARK_HEARTBEAT ', beats)) for row in values).encode()

    def test_pairing_and_disjoint_formula_allow_signal_before_return(self):
        for signal in (16000, 6000):
            with self.subTest(signal=signal):
                binding, batch, rows = self.fixture(signal)
                if signal < 11000:
                    rows.reverse()  # A synchronous callback is logged before return.
                report = diagnostic.summarize(self.raw(rows), batch, binding, 123, cycles=1)
                save = report['saves'][0]
                self.assertEqual(save['total_save_ms'], 20)
                self.assertEqual(save['call_ms'], 10)
                self.assertEqual(save['signal_minus_return_ms'], (signal - 11000) / 1000)
                self.assertEqual(save['total_save_ms'], save['call_ms'] +
                                 save['after_return_to_signal_ms'] + save['after_both_to_end_ms'])
                self.assertEqual(report['largest_heartbeat_gap']['gap_ms'], 20)
        path = diagnostic.STUDIO / 'tests/replay/benchmark_native.gd'
        original = path.read_bytes()
        patched = diagnostic.patched_driver(original)
        self.assertEqual(path.read_bytes(), original)
        self.assertIn(b'        _cycle_limit = 100\n', patched)
        self.assertEqual(patched.count(b'print("HH_GT06_SAVE_PHASE '), 1)

    def test_missing_wrong_binding_and_duplicate_markers_rejected(self):
        binding, batch, rows = self.fixture()
        cases = [rows[:1], rows + [rows[0]]]
        for field, value in [('run_id', 'other'), ('source_closure_sha256', 'c' * 64),
                             ('profile_sha256', 'c' * 64), ('pid', 124), ('batch', 1),
                             ('cycle', 1), ('start_us', 999)]:
            changed = copy.deepcopy(rows)
            changed[0][field] = value
            cases.append(changed)
        for changed in cases:
            with self.subTest(rows=changed), self.assertRaises(diagnostic.campaign.BenchmarkJobError):
                diagnostic.summarize(self.raw(changed), batch, binding, 123, cycles=1)

    def test_return_drift_is_not_joined_to_a_different_cycle(self):
        binding, batch, rows = self.fixture()
        for field in ('live_batch', 'live_cycle'):
            changed = copy.deepcopy(rows)
            changed[0][field] = 1
            with self.subTest(field=field), self.assertRaisesRegex(
                    diagnostic.campaign.BenchmarkJobError, 'CALL_IDENTITY_DRIFT'):
                diagnostic.summarize(self.raw(changed), batch, binding, 123, cycles=1)

    def test_preview_variant_preserves_error_or_void_return_semantics(self):
        path = diagnostic.STUDIO / 'tests/replay/benchmark_native.gd'
        original = path.read_bytes()
        variants = {mode: diagnostic.patched_driver(original, mode) for mode in diagnostic.PREVIEW_MODES}
        self.assertEqual(path.read_bytes(), original)
        self.assertNotEqual(variants['stock'], variants['off'])
        self.assertIn(b'    var result: Error = EditorInterface.save_scene()\n', variants['stock'])
        self.assertIn(b'    if result != OK:\n        _fail("BENCHMARK_SAVE_CALL")\n', variants['stock'])
        self.assertIn(b'    EditorInterface.save_scene_as(SCENE, false)\n', variants['off'])
        self.assertIn(b'_diagnostic_save_phase("return", diagnostic_return_us, null,', variants['off'])
        self.assertNotIn(b'var result: Error = EditorInterface.save_scene()', variants['off'])
        self.assertNotIn(b'BENCHMARK_SAVE_CALL', variants['off'])
        readback = original.split(b'func _wait_save() -> void:\n', 1)[1].split(b'func _on_adapter_ready', 1)[0]
        for mode, patched in variants.items():
            with self.subTest(mode=mode):
                self.assertIn(readback, patched)
                binding, batch, rows = self.fixture(preview_mode=mode)
                report = diagnostic.summarize(self.raw(rows), batch, binding, 123, cycles=1, preview_mode=mode)
                self.assertEqual(report['preview_mode'], mode)
                self.assertEqual(report['return_kind'], 'Error' if mode == 'stock' else 'void')
                self.assertEqual(report['saves'][0]['return_result'], 0 if mode == 'stock' else None)
                for field, value in [('preview_mode', 'off' if mode == 'stock' else 'stock'),
                                     ('return_kind', 'void' if mode == 'stock' else 'Error'),
                                     ('result', None if mode == 'stock' else 0)]:
                    changed = copy.deepcopy(rows)
                    changed[0][field] = value
                    with self.subTest(field=field), self.assertRaises(diagnostic.campaign.BenchmarkJobError):
                        diagnostic.summarize(self.raw(changed), batch, binding, 123, cycles=1, preview_mode=mode)


if __name__ == '__main__':
    unittest.main()
