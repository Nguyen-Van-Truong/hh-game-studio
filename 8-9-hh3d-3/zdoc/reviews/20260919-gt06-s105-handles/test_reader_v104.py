"""Reader regression and hostile-boundary coverage; no engine invocation."""
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


legacy_tests = load('s105_legacy_reader_tests', HERE.parent /
    '20260919-gt06-s103-status-gap/test_read_native_save.py')
reader = load('s105_reader_v104', HERE.parent /
    '20260919-gt06-s104-closeout/save-boundary/read_native_save_v104.py')
legacy_tests.reader = reader


class ReaderV104Tests(legacy_tests.NativeSaveReaderTests):
    def payload(self, event):
        return (reader.ENTER + json.dumps(self.enter()) + '\n' +
                reader.COMPLETE + json.dumps(event) + '\n').encode()

    def test_nested_frame_progression_keeps_lifecycle_unknown(self):
        event = self.complete()
        event.update(save_process_exit_frame=15, signal_frame=14,
                     next_process_entry_frame=16, next_process_exit_frame=16)
        result = self.write_case(self.payload(event))
        self.assertEqual(result['reader_version'], 's104-frame-order-v1')
        self.assertEqual(result['classification'], 'OBSERVED_NATIVE_INTERVALS')
        self.assertEqual(result['lifecycle']['state'], 'UNKNOWN')
        self.assertFalse(result['formal_acceptance'])
        self.assertFalse(result['eligible_for_dataset'])

    def test_regressed_save_exit_frame_is_rejected(self):
        event = self.complete()
        event['save_process_exit_frame'] = 9
        with self.assertRaisesRegex(reader.EvidenceError, 'frame boundary order'):
            self.write_case(self.payload(event))

    def test_next_dispatch_and_signal_frame_bounds_stay_strict(self):
        for delta in ({'next_process_entry_frame': 10},
                      {'next_process_exit_frame': 12}, {'signal_frame': 12}):
            with self.subTest(delta=delta):
                with self.assertRaisesRegex(reader.EvidenceError, 'frame boundary order'):
                    self.write_case(self.payload({**self.complete(), **delta}))

    def test_reversed_timestamps_still_rejected(self):
        event = self.complete()
        event['call_return_us'] = 129
        with self.assertRaisesRegex(reader.EvidenceError, 'save/process boundary order'):
            self.write_case(self.payload(event))


if __name__ == '__main__':
    unittest.main()
