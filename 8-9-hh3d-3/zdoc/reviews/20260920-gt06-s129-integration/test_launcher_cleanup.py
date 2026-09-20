"""No-engine launcher ownership regressions with copied files and injected owners.

The actual launcher and support utility are imported from byte-identical copies.
Only check()/campaign ownership operations are injected; launch(), helper copies,
freeze/context creation, durable writes, exception serialization and cleanup run.
Synthetic owner receipts are fixture data, never real process-exit evidence.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
LAUNCHER = BASE / 'post_failure_full.py'
SUPPORT = ROOT / 'zdoc/reviews/20260919-gt06-s123-lookup-repair/support.py'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ConstructorFailure(RuntimeError):
    code = 'TEST_CONSTRUCTOR_PRIMARY'


class ReceiptFailure(OSError):
    code = 'TEST_JOB_READBACK_RECEIPT'


class LauncherCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='s129-launcher-fixture-',
            dir=os.environ.get('HH_S129_LAUNCHER_TEST_ROOT'))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'hh3d'
        self.base = self.root / 'zdoc/reviews/20260920-gt06-s129-integration'
        self.base.mkdir(parents=True)
        (self.root / 'studio/.local/reviews').mkdir(parents=True)
        copied_launcher = self.base / LAUNCHER.name
        copied_launcher.write_bytes(LAUNCHER.read_bytes())
        self.assertEqual(sha(copied_launcher), sha(LAUNCHER))
        self.launcher = load(copied_launcher, 's129_cleanup_launcher_' + self._testMethodName)
        self.assertEqual(self.launcher.ROOT, self.root)

        support_path = self.root / SUPPORT.relative_to(ROOT)
        support_path.parent.mkdir(parents=True)
        support_path.write_bytes(SUPPORT.read_bytes())
        self.support = load(support_path, 's129_cleanup_support_' + self._testMethodName)
        for relative in self.launcher.HELPER_PINS:
            path = self.root / relative
            if path == support_path:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# Synthetic helper copy; never executed.\n', encoding='utf-8')
        self.launcher.HELPER_PINS = {name: sha(self.root / name)
                                   for name in self.launcher.HELPER_PINS}

        # The real launcher identifies configure frames by filename/function
        # and inspects these three locals. This pure module supplies that frame.
        job = self.root / 'studio/tests/replay/benchmark_job.py'
        job.parent.mkdir(parents=True)
        job.write_text('from types import SimpleNamespace as N\n'
            'def configure(error):\n'
            '    limits = N(basic=N(flags=1, active_limit=2, job_time=3), job_memory=4)\n'
            '    observed = N(basic=N(flags=1, active_limit=2, job_time=5), job_memory=4)\n'
            '    size = N(value=123)\n'
            '    raise error\n', encoding='utf-8')
        self.job = load(job, 's129_cleanup_job_' + self._testMethodName)
        self.sources = {job.relative_to(self.root / 'studio').as_posix(): sha(job)}
        self.events, self.job_receipts = [], []
        self.fail_receipt = False
        self.primary, self.receipt_error = ConstructorFailure(), ReceiptFailure()
        self.owner = SimpleNamespace(closed=False)

        def close():
            self.events.append('owner.close')
            self.owner.closed = True

        self.owner.close = Mock(side_effect=close)
        self.owner.tick = Mock(return_value=0)
        self.owner.finish = Mock(side_effect=self.finish)

        def write(path, value):
            if path.name == 'job-configure-readback.json':
                self.events.append('job_readback.write')
                self.job_receipts.append(deepcopy(value))
                if self.fail_receipt:
                    raise self.receipt_error
            self.support.write(path, value)

        self.util = SimpleNamespace(sha=self.support.sha, need=self.support.need,
            errors_record=self.support.errors_record, write=write)

        def owner_state(owner):
            self.assertIs(owner, self.owner)
            self.assertTrue(owner.closed)
            self.events.append('owner.observe')
            return {'present': True, 'closed': owner.closed, 'synthetic_test_owner': True}

        self.campaign = SimpleNamespace(
            profile=SimpleNamespace(PROFILE_SHA256='1' * 64),
            BenchmarkProcess=Mock(return_value=self.owner),
            stop_requested=Mock(return_value=False),
            verify_capture=Mock(side_effect=self.verify_capture),
            _editor_cleanup_state=owner_state,
            _target_exit_state=Mock(return_value={'actual_target_exit': None,
                'missing_reason': 'SYNTHETIC_TEST_NO_PROCESS', 'natural_exit_not_inferred': True}),
            source_files=Mock(side_effect=lambda: dict(self.sources)))
        self.launcher.check = Mock(return_value=(self.util, self.campaign, self.sources, support_path))
        self.run = self.root / 'studio/.local/reviews' / self.launcher.RUN_ID

    def finish(self):
        self.events.append('owner.finish')
        result = {'synthetic_test_owner': True, 'completed': True}
        (self.run / 'owned').mkdir()
        self.support.write(self.run / 'owned/capture.json', result)
        return result

    def verify_capture(self, output, expected_hash, **kwargs):
        self.events.append('capture.verify')
        self.assertEqual(expected_hash, sha(output / 'capture.json'))
        self.assertEqual(kwargs['source_root'], self.root)
        self.assertTrue(kwargs['expected_campaign_host'])
        for name, expected in kwargs['expected_source_files'].items():
            self.assertEqual(sha(self.root / name), expected)

    def launch(self):
        # Guard the test scope even if a future launcher accidentally bypasses
        # the injected campaign owner. No subprocess may be created here.
        with patch('subprocess.Popen', side_effect=AssertionError('TEST_FORBIDS_PROCESS_LAUNCH')):
            code = self.launcher.launch()
        return code, json.loads((self.run / 'result.json').read_bytes())

    def test_constructor_owner_is_closed_when_job_readback_receipt_raises(self):
        self.fail_receipt = True
        self.primary.cleanup_owner = self.owner

        def failing_constructor(*args, **kwargs):
            self.events.append('constructor.raise')
            self.job.configure(self.primary)

        self.campaign.BenchmarkProcess.side_effect = failing_constructor
        code, result = self.launch()

        self.assertEqual(code, 1)
        self.assertEqual(self.events, ['constructor.raise', 'job_readback.write',
                                       'owner.close', 'owner.observe'])
        self.owner.close.assert_called_once_with()
        self.owner.finish.assert_not_called()
        self.campaign.verify_capture.assert_not_called()
        self.assertEqual(len(self.job_receipts), 1)
        self.assertEqual(self.job_receipts[0]['requested']['job_time'], 3)
        self.assertEqual(self.job_receipts[0]['observed']['job_time'], 5)
        self.assertEqual(self.job_receipts[0]['returned_size'], 123)
        self.assertFalse((self.run / 'job-configure-readback.json').exists())
        self.assertFalse(result['owned_child_natural_exit0'])
        self.assertFalse(result['formal_acceptance'])
        self.assertFalse(result['eligible_for_dataset'])
        self.assertTrue(result['observations']['owner']['closed'])
        self.assertTrue(result['observations']['source_unchanged'])
        self.assertTrue(result['observations']['execution_unchanged'])
        errors = result['errors']
        self.assertEqual([row['stage'] for row in errors], ['parent', 'job_readback_receipt'])
        self.assertEqual(errors[0]['chain'][0]['code'], self.primary.code)
        self.assertEqual(errors[1]['chain'][0]['code'], self.receipt_error.code)
        self.assertTrue(any(frame['file'] == 'benchmark_job.py'
                            for frame in errors[0]['chain'][0]['frames']))

    def test_synthetic_natural_return_finishes_verifies_then_closes(self):
        code, result = self.launch()
        self.assertEqual(code, 0)
        self.owner.finish.assert_called_once_with()
        self.campaign.verify_capture.assert_called_once()
        self.owner.close.assert_called_once_with()
        self.assertEqual(self.events, ['owner.finish', 'capture.verify', 'owner.close', 'owner.observe'])
        self.assertEqual(result['errors'], [])
        self.assertTrue(result['owned_child_natural_exit0'])
        self.assertTrue(result['observations']['source_unchanged'])
        self.assertTrue(result['observations']['execution_unchanged'])
        self.assertFalse(result['formal_acceptance'])
        self.assertFalse(result['eligible_for_dataset'])
        self.assertEqual(self.job_receipts, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
