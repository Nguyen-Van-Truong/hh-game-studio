"""S95 overlay/publication guards only; no native processes or engine."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('s95_native_isolation_under_test', BASE / 'native_isolation.py')
isolation = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = isolation
SPEC.loader.exec_module(isolation)


class NativeIsolationOverlayTests(unittest.TestCase):
    def test_hook_preserves_counter_lifecycle_and_real_heartbeat_coverage_with_exact_roundtrip(self):
        raw = (isolation.STUDIO / 'tests/replay/benchmark_native.gd').read_bytes()
        helper = (BASE / 'object_probe_s95.gd').read_bytes()
        appended = b'\n' + helper.decode('utf-8-sig').split('# S95_SPARSE_HELPER_BOUNDARY\n', 1)[1].encode()
        inserted = (b'    _s95_before_batch()\n    if _failed:\n        return\n'
                    b'    ended = Time.get_ticks_usec()\n')
        batch_anchor = b'    var batch_data: Dictionary = {'
        heartbeat = b'    _heartbeat(true)\n'
        old = b'    if _mode == "diagnostic":\n        _batch_limit = 1\n        _cycle_limit = 1'
        for mode, dimensions in isolation.MODES.items():
            with self.subTest(mode=mode):
                patched = isolation.patch_driver(raw, helper, dimensions)
                section = patched.split(b'func _write_batch() -> void:\n', 1)[1].split(b'\n\nfunc _wait_host_ack()', 1)[0]
                self.assertTrue(section.startswith(b'    var ended: int = Time.get_ticks_usec()\n' + heartbeat))
                self.assertIn(inserted + b'    var objects: float = Performance.get_monitor(Performance.OBJECT_COUNT)\n', section)
                for prior in (b'    var snapshot: Dictionary = _adapter.inspect_scene()',
                              b'    var root: Node = EditorInterface.get_edited_scene_root()', b'    _barrier = {'):
                    self.assertLess(section.index(prior), section.index(inserted))
                self.assertEqual(section.count(heartbeat), 2)
                self.assertLess(section.index(b'    var memory: Dictionary = {'), section.index(heartbeat + batch_anchor))
                self.assertIn(b'"held_handles": {"value": null, "unavailable_reason": "Requires retained host process sampler"}}}\n'
                              + heartbeat + batch_anchor, section)
                self.assertEqual(patched.count(inserted), 1)
                self.assertTrue(patched.endswith(appended))
                new = (f'    if _mode == "diagnostic":\n        _batch_limit = {dimensions["batches"]}\n'
                       f'        _cycle_limit = {dimensions["cycles"]}').encode()
                restored = patched[:-len(appended)].replace(heartbeat + batch_anchor, batch_anchor, 1)
                restored = restored.replace(inserted, b'', 1).replace(new, old, 1)
                self.assertEqual(restored, raw)

    def test_changed_write_batch_prologue_fails_closed(self):
        raw = (isolation.STUDIO / 'tests/replay/benchmark_native.gd').read_bytes()
        helper = (BASE / 'object_probe_s95.gd').read_bytes()
        altered = raw.replace(b'func _write_batch() -> void:\n',
                              b'func _write_batch() -> void:\n    _heartbeat(true)\n', 1)
        with self.assertRaisesRegex(RuntimeError, 'ISOLATION_COUNTER_PATCH'):
            isolation.patch_driver(altered, helper, isolation.MODES['smoke'])


class ProcessStartPublicationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='s95-publication-test-')
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'process-start.json'
        self.clock = patch.object(isolation.time, 'monotonic', return_value=10.0)
        self.now = self.clock.start()
        self.addCleanup(self.clock.stop)
        self.publication = {}

    def poll(self, deadline=1800.0):
        return isolation.process_start_receipt(self.path, deadline, self.publication)

    def test_missing_empty_and_partial_receipt_poll_then_valid_pid(self):
        self.assertIsNone(self.poll())
        self.assertEqual(self.publication, {})
        for raw in (b'', b'{"pid":', b'   '):
            self.path.write_bytes(raw)
            with self.subTest(raw=raw):
                self.assertIsNone(self.poll())
                self.assertEqual(self.publication, {'deadline': 15.0})
        self.now.return_value = 14.5
        self.path.write_bytes(b'{"pid":1234}')
        self.assertEqual(self.poll(), {'pid': 1234})

    def test_publication_retry_is_bounded_by_existing_stage_deadline(self):
        for raw in (None, b'', b'{"pid":'):
            if self.path.exists():
                self.path.unlink()
            if raw is not None:
                self.path.write_bytes(raw)
            with self.subTest(raw=raw), self.assertRaisesRegex(RuntimeError, 'ISOLATION_PROCESS_START_TIMEOUT'):
                self.poll(9.0)

    def test_incomplete_publication_expires_without_reset_on_rewrite_or_disappearance(self):
        for initial in (b'', b'{"pid":'):
            for final in (None, b'', b'{"pid":', b'{"pid":1234}'):
                with self.subTest(initial=initial, final=final):
                    self.publication = {}
                    self.now.return_value = 10.0
                    self.path.write_bytes(initial)
                    self.assertIsNone(self.poll())
                    self.now.return_value = 14.0
                    self.path.write_bytes(b'{')
                    self.assertIsNone(self.poll())
                    self.assertEqual(self.publication, {'deadline': 15.0})
                    self.now.return_value = 15.1
                    if final is None:
                        self.path.unlink()
                    else:
                        self.path.write_bytes(final)
                    with self.assertRaisesRegex(RuntimeError, 'ISOLATION_PROCESS_START_PUBLICATION_TIMEOUT'):
                        self.poll()

    def test_absent_receipt_does_not_start_publication_grace(self):
        self.assertIsNone(self.poll())
        self.now.return_value = 30.0
        self.assertIsNone(self.poll())
        self.assertEqual(self.publication, {})
        self.path.write_bytes(b'{"pid":')
        self.assertIsNone(self.poll())
        self.assertEqual(self.publication, {'deadline': 35.0})

    def test_completed_invalid_record_is_not_retried(self):
        records = ([], {}, {'pid': True}, {'pid': 0}, {'pid': -1}, {'pid': 1.0},
                   {'pid': '1'}, {'pid': 0xffffffff}, {'pid': 1, 'extra': 2})
        for record in records:
            self.path.write_text(json.dumps(record), encoding='utf-8')
            with self.subTest(record=record), self.assertRaisesRegex(RuntimeError, 'ISOLATION_PROCESS_START_RECORD'):
                self.poll()
        self.path.write_bytes(b'{"pid":1,"pid":2}')
        with self.assertRaisesRegex(RuntimeError, 'ISOLATION_PROCESS_START_RECORD'):
            self.poll()

    def test_oversize_unsafe_and_other_io_errors_are_not_publication_retries(self):
        self.path.write_bytes(b' ' * 8193)
        with self.assertRaisesRegex(isolation.n.DiagnosticError, 'DIAGNOSTIC_FILE_SIZE'):
            self.poll()
        for error in (PermissionError('denied'), isolation.n.DiagnosticError('DIAGNOSTIC_REPARSE')):
            with self.subTest(error=type(error).__name__), patch.object(isolation, '_process_start_bytes', side_effect=error):
                with self.assertRaises(type(error)):
                    self.poll()


if __name__ == '__main__':
    unittest.main()
