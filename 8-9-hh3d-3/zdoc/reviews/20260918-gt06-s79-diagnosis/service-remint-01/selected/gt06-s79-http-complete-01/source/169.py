"""Prevent clean-exit or wrong-case false positives in the native probe driver."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_snapshot_probe import verify_case, sha


class ProbeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='hh-gt05-probe-evidence-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.host = {'exit_code': 0, 'wrapper_exit_code': 0, 'tree_verified': True,
                     'timed_out': False, 'stdout': 'stdout.txt'}
        (self.root / 'stdout.txt').write_bytes(b'')

    def test_clean_exit_without_observation_is_not_pass(self):
        self.assertFalse(verify_case(self.root, 'success', self.host))

    def test_only_exact_case_and_observation_marker_pass(self):
        report = {'case': 'success', 'passed': True, 'synthetic_storage_only': True,
            'asset_validation_proven': False, 'formal_acceptance': False, 'public_ack': False}
        raw = json.dumps(report).encode()
        (self.root / 'observed.json').write_bytes(raw)
        self.assertFalse(verify_case(self.root, 'success', self.host))
        marker = {'case': 'success', 'observed_sha256': sha(raw), 'passed': True,
            'synthetic_storage_only': True, 'asset_validation_proven': False}
        (self.root / 'stdout.txt').write_text('GT05_SNAPSHOT_PROBE ' + json.dumps(marker) + '\n', encoding='utf-8')
        self.assertTrue(verify_case(self.root, 'success', self.host))
        self.assertFalse(verify_case(self.root, 'crash_selector', self.host))
        (self.root / 'observed.json').write_bytes(raw + b' ')
        self.assertFalse(verify_case(self.root, 'success', self.host))


if __name__ == '__main__':
    unittest.main()
