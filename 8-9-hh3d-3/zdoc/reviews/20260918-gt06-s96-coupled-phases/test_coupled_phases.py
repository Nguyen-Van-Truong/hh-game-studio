"""Static S96 composition guards only; no engine, HTTP or helper launch."""
import importlib.util
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('s96_composition_under_test', BASE / 'coupled_phases.py')
entry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(entry)


class AckOverlayTests(unittest.TestCase):
    def setUp(self):
        self.raw = (entry.STUDIO / 'tests/replay/benchmark_native.gd').read_bytes()
        self.probe = (entry.S95 / 'object_probe_s95.gd').read_bytes()
        self.insert = b'    _s96_before_ack(digest)\n    if _failed:\n        return\n'

    def test_only_ack_hook_changes_original_native_bytes(self):
        result = entry.patch_native(self.raw, self.probe)
        base = result[:len(self.raw) + len(self.insert)]
        self.assertEqual(base.replace(self.insert, b'', 1), self.raw)
        self.assertEqual(base.count(self.insert), 1)
        old_write = self.raw.split(b'func _write_batch() -> void:\n', 1)[1].split(b'func _wait_host_ack()', 1)[0]
        new_write = base.split(b'func _write_batch() -> void:\n', 1)[1].split(b'func _wait_host_ack()', 1)[0]
        self.assertEqual(new_write, old_write)
        old_ack = self.raw.split(b'func _wait_host_ack() -> void:\n', 1)[1].split(b'func _advance_batch()', 1)[0]
        new_ack = base.split(b'func _wait_host_ack() -> void:\n', 1)[1].split(b'func _advance_batch()', 1)[0]
        self.assertEqual(new_ack.replace(self.insert, b'', 1), old_ack)
        self.assertLess(new_ack.index(b'BENCHMARK_HOST_ACK_POSTCONDITION'), new_ack.index(self.insert))
        self.assertLess(new_ack.index(b'BENCHMARK_HOST_ACK_CHANGED'), new_ack.index(self.insert))
        self.assertIn(self.insert + b'    var objects: float = Performance.get_monitor(Performance.OBJECT_COUNT)', new_ack)
        self.assertEqual(new_ack.count(b'    _heartbeat(true)\n'), 1)
        self.assertIn(b'    var observed: int = Time.get_ticks_usec()\n    if observed > int(_barrier.deadline_mono_us):', new_ack)

    def test_s96_ack_identity_and_primitive_collector_are_explicit(self):
        result = entry.patch_native(self.raw, self.probe)
        body = result[len(self.raw) + len(self.insert) + 1:]
        self.assertIn(b'if _mode != "full" or _s95_snapshot_count', body)
        self.assertIn(b'"phase": "before_ack_counter_readback"', body)
        self.assertIn(b'"trigger": "baseline_ack_batch4" if baseline else "first_ack_object_growth"', body)
        self.assertIn(b'hh-studio.gt06.s96-ack-sparse-attribution', body)
        self.assertIn(b'hh-studio.gt06.s96-ack-sparse-post', body)
        self.assertEqual(body.count(b'"ack_file_sha256": ack_file_sha256'), 2)
        self.assertNotIn(b'before_batch_counter_readback', body)
        old_primitive = self.probe.split(b'func _s95_counters()', 1)[1].split(b'func _s95_before_batch()', 1)[0]
        new_primitive = body.split(b'func _s95_counters()', 1)[1].split(b'func _s96_before_ack(', 1)[0]
        self.assertEqual(new_primitive, old_primitive)

    def test_changed_ack_readback_anchor_fails_closed(self):
        before, ack = self.raw.split(b'func _wait_host_ack() -> void:\n', 1)
        changed = before + b'func _wait_host_ack() -> void:\n' + ack.replace(
            b'    var objects: float = Performance.get_monitor(Performance.OBJECT_COUNT)\n',
            b'    var unexpected: float = 0\n', 1)
        with self.assertRaisesRegex(RuntimeError, 'S96_PATCH_ANCHOR'):
            entry.patch_native(changed, self.probe)

    def test_changed_probe_phase_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, 'S96_PROBE_GUARD'):
            entry.patch_native(self.raw, self.probe.replace(b'before_batch_counter_readback', b'unknown_phase'))


class DiagnosticSanitizationTests(unittest.TestCase):
    def test_unexpected_error_retains_class_frames_without_message(self):
        try:
            raise ValueError('secret request body must not be retained')
        except ValueError as error:
            value = entry.sanitized_error(error)
        self.assertEqual(value['exception_class'], 'ValueError')
        self.assertTrue(value['frames'])
        self.assertNotIn('secret', str(value))
        self.assertEqual(set(value), {'exception_class', 'frames'})

    def test_source_difference_is_bounded_paths_without_hashes(self):
        value = entry.source_difference({'old.py': 'secretA', 'same.py': 'a'}, {'same.py': 'b', 'new.py': 'secretB'})
        self.assertEqual(value, {'added': ['new.py'], 'missing': ['old.py'], 'changed': ['same.py']})
        self.assertNotIn('secret', str(value))


if __name__ == '__main__':
    unittest.main(verbosity=2)
