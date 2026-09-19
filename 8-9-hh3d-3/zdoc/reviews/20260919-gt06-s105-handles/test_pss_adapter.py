"""Bounded adapter coverage with a fake PSS API; no target process is opened."""
import ctypes as C
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location('s105_pss', Path(__file__).with_name('pss_adapter.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class FakeApi:
    current = 99
    def __init__(self):
        self.calls, self.closed, self.walked = [], [], False
        self.changed, self.bad_count, self.cleanup_fail = False, False, False
        self.type_bytes = C.create_string_buffer('Event\0'.encode('utf-16-le'))
        self.name_bytes = C.create_string_buffer('private-namespace'.encode('utf-16-le'))
    def identity(self, handle):
        return dict(pid=8, process_start='windows:124' if self.changed and handle == 11 else 'windows:123',
                    executable='c:\\owned.exe')
    def require_live(self, handle):
        self.calls.append(('live', handle))
    def count(self, handle):
        return 10
    def open_owned(self, pid):
        self.calls.append(('open', pid))
        return 11
    def capture(self, handle):
        self.calls.append(('capture', handle))
        return 12
    def captured_count(self, snapshot):
        return 2 if self.bad_count else 1
    def marker(self):
        return 13
    def walk(self, snapshot, marker):
        if self.walked:
            return None
        self.walked = True
        row = p.HandleEntry()
        row.handle, row.flags, row.object_type = 44, 3, 4
        row.type_name, row.type_length = C.addressof(self.type_bytes), len(self.type_bytes.raw) - 1
        row.name, row.name_length = C.addressof(self.name_bytes), len(self.name_bytes.raw) - 1
        return row
    def free_marker(self, value):
        self.closed.append(('marker', value))
        return 0
    def free_snapshot(self, value):
        self.closed.append(('snapshot', value))
        return 5 if self.cleanup_fail else 0
    def close_process(self, value):
        self.closed.append(('process', value))
        return 0


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi()
        self.probe = SimpleNamespace(handle=7, pid=8, process_start='windows:123', close_uncertain=False)
        p._HELD_RESOURCES.clear()
    def tearDown(self):
        p._HELD_RESOURCES.clear()
    def capture(self, **kwargs):
        return p.capture_owned(self.probe, _api=self.api, _clock=lambda: 100, **kwargs)
    def test_layout(self):
        p._check_layout()
    def test_redacted_complete_snapshot_and_original_handle_preserved(self):
        result = self.capture()
        self.assertEqual(result['status'], 'OBSERVED')
        self.assertEqual(result['type_counts'], {'Event': 1})
        self.assertNotIn('private-namespace', json.dumps(result))
        self.assertEqual(result['entries'][0]['object_identity'], 'UNKNOWN')
        self.assertTrue(result['cleanup']['all_released'])
        self.assertEqual(self.api.closed, [('marker',13),('snapshot',12),('process',11)])
        self.assertFalse(result['formal_acceptance'])
    def test_reused_pid_rejected_before_snapshot_and_owned_extra_closed(self):
        self.api.changed = True
        result = self.capture()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['errors'][0]['code'], 'PSS_PROCESS_IDENTITY')
        self.assertNotIn(('capture', 11), self.api.calls)
        self.assertEqual(self.api.closed, [('process', 11)])
    def test_count_mismatch_is_unknown_after_cleanup(self):
        self.api.bad_count = True
        result = self.capture()
        self.assertEqual(result['errors'][0]['code'], 'PSS_CAPTURED_COUNT_MISMATCH')
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertTrue(result['cleanup']['all_released'])
    def test_cleanup_failure_latches_and_prevents_a_second_capture(self):
        self.api.cleanup_fail = True
        first = self.capture()
        self.assertFalse(first['cleanup']['all_released'])
        self.assertEqual(first['status'], 'UNKNOWN')
        calls = list(self.api.calls)
        second = self.capture()
        self.assertEqual(second['errors'][0]['code'], 'PSS_PRIOR_CLEANUP_HELD')
        self.assertEqual(self.api.calls, calls)
    def test_bare_pid_or_uncertain_original_handle_never_opens_target(self):
        for obj in (8, SimpleNamespace(handle=7,pid=8,process_start='windows:123',close_uncertain=True)):
            result = p.capture_owned(obj, _api=self.api, _clock=lambda: 100)
            self.assertEqual(result['status'], 'UNKNOWN')
            self.assertEqual(self.api.calls, [])
    def test_time_budget_prevents_opening_after_identity(self):
        values = iter([0, p.MAX_TOTAL_NS + 1, p.MAX_TOTAL_NS + 2])
        result = p.capture_owned(self.probe, _api=self.api, _clock=lambda: next(values))
        self.assertEqual(result['errors'][0]['code'], 'PSS_TIME_BUDGET')
        self.assertNotIn(('open',8), self.api.calls)
    def test_invalid_name_pointer_is_rejected(self):
        with self.assertRaises(p.PssError):
            p._name_bytes(None, 2)
        with self.assertRaises(p.PssError):
            p._name_bytes(7, 1)


if __name__ == '__main__':
    unittest.main()
