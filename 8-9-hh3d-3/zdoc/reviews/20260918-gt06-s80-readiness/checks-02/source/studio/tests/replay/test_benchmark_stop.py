"""Fixed-slot operator Stop binds the run and cannot turn interruption into PASS."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.tests.replay import run_benchmark_campaign as campaign
from studio.tests.replay.benchmark_job import BenchmarkJobError
from studio.tests.replay.run_native_benchmark import DiagnosticError


class CampaignStopTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='gt06-stop-contract-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.expected = {'run_id': 'gt06-stop.r00.a01',
            'source_closure_sha256': 'a' * 64, 'campaign_sha256': 'b' * 64}
        self.request = {'schema': 'HH-GT06-CAMPAIGN-STOP-1', **self.expected,
            'reason': 'OPERATOR_STOP'}

    def put(self, value):
        (self.root / 'stop-request.json').write_bytes(
            value if type(value) is bytes else json.dumps(value).encode())

    def test_absent_request_keeps_running_and_exact_request_latches_stop(self):
        self.assertFalse(campaign.stop_requested(self.root, **self.expected))
        self.put(self.request)
        owner = Mock()
        owner.tick.side_effect = BenchmarkJobError('BENCHMARK_STOPPED')
        with self.assertRaisesRegex(BenchmarkJobError, 'BENCHMARK_STOPPED'):
            campaign.wait_owned_run(owner, self.root, **self.expected)
        owner.tick.assert_called_once_with(stop=True)
        owner.finish.assert_not_called()

    def test_stale_run_source_campaign_and_extra_fields_are_rejected(self):
        for field in ('run_id', 'source_closure_sha256', 'campaign_sha256', 'schema', 'reason', 'unexpected'):
            with self.subTest(field=field):
                changed = deepcopy(self.request)
                changed[field] = 'different'
                self.put(changed)
                with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_STOP_BINDING'):
                    campaign.stop_requested(self.root, **self.expected)

    def test_duplicate_and_oversized_control_never_pass(self):
        raw = json.dumps(self.request).encode()
        self.put(raw[:-1] + b',"reason":"OPERATOR_STOP"}')
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_STOP_DUPLICATE_KEY'):
            campaign.stop_requested(self.root, **self.expected)
        self.put(b' ' * 4097)
        with self.assertRaisesRegex(DiagnosticError, 'DIAGNOSTIC_FILE_SIZE'):
            campaign.stop_requested(self.root, **self.expected)

    def test_natural_exit_is_observed_without_sending_stop(self):
        owner = Mock()
        owner.tick.side_effect = [None, 0]
        with patch.object(campaign.time, 'sleep') as pause:
            campaign.wait_owned_run(owner, self.root, **self.expected)
        self.assertEqual(owner.tick.call_count, 2)
        self.assertTrue(all(call.kwargs == {'stop': False} for call in owner.tick.call_args_list))
        pause.assert_called_once_with(.05)
        owner.finish.assert_not_called()


if __name__ == '__main__':
    unittest.main()
