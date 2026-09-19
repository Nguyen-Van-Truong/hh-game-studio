"""Negative controls for the offline S118 reader; never touches a live run."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

READER = Path(__file__).parents[1] / '20260919-gt06-s118-import-boundary/read_lookup_terminal.py'
spec = importlib.util.spec_from_file_location('s118_reader', READER)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class ReaderControls(unittest.TestCase):
    def test_missing_terminal_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, 'TERMINAL_REQUIRED'):
                reader.summarize(Path(root))

    def test_available_false_stays_unknown(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            (path / 'result.json').write_text(json.dumps({'run_id': 'r', 'observations': {}, 'formal_acceptance': False}), encoding='utf8')
            report = reader.summarize(path)
            self.assertEqual('UNKNOWN', report['correlation']['status'])

    def test_mismatched_identity_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            (path / 'result.json').write_text(json.dumps({'run_id': 'r', 'observations': {'target': {'actual_target_exit': {'pid': 2}}}}), encoding='utf8')
            (path / 'freeze.json').write_text(json.dumps({'run_id': 'r', 'source_closure': 'a', 'profile_sha256': 'p'}), encoding='utf8')
            (path / 'timing-summary.json').write_text(json.dumps({'run_id': 'r', 'pid': 1, 'timings': {}}), encoding='utf8')
            (path / 'attempt').mkdir()
            (path / 'attempt/http-phases-final.json').write_text(json.dumps({'available': True, 'run_id': 'r.r00.a01', 'source_closure_sha256': 'a', 'profile_sha256': 'p', 'observation': {}}), encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'RUN_PID_SOURCE_BINDING'):
                reader.summarize(path)


if __name__ == '__main__':
    unittest.main()
