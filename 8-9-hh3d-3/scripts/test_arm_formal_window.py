import contextlib
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import arm_formal_window as arm


class ArmTests(unittest.TestCase):
    def setUp(self):
        self.at = datetime(2026, 10, 2, 3, tzinfo=timezone.utc)
        self.config = {'start': self.at.isoformat(), 'end': (self.at + timedelta(hours=4)).isoformat(),
                       'source': 'a' * 64, 'profile': arm.PROFILE, 'campaign_id': 'gt06-o4-formal-10',
                       'arm_sha256': hashlib.sha256(arm.HERE.read_bytes()).hexdigest()}
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.request = self.root / 'request.json'

    def observation(self, at=None):
        at = at or self.at
        return {'source': self.config['source'], 'profile': arm.PROFILE,
                'observed_at': (at - timedelta(seconds=60)).isoformat(), 'finished_at': at.isoformat(),
                **dict.fromkeys(('lock_absent', 'scheduler_idle', 'budget_available', 'preflight_pass', 'cpu_minute_pass'), True)}

    def save_request(self):
        arm.write(self.request, self.config)

    def invoke(self, action):
        with patch.object(sys, 'argv', [str(arm.HERE), action, str(self.request)]), \
             patch.object(arm, 'now', return_value=self.at), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return arm.main()

    def dry_run(self):
        with patch.object(arm, 'fresh_probe', return_value=self.observation()):
            self.assertEqual(self.invoke('--dry-run'), 0)

    def test_ready_and_last_start(self):
        for minutes, seconds, expected in ((0, 0, 'DISPATCH'), (30, 0, 'DISPATCH'), (30, 1, 'TOO_LATE')):
            at = self.at + timedelta(minutes=minutes, seconds=seconds)
            self.assertEqual(arm.decision(self.config, self.observation(at), at), expected)
        self.config['end'] = (self.at + timedelta(hours=3)).isoformat()
        self.assertEqual(arm.decision(self.config, self.observation(), self.at), 'WINDOW_TOO_SHORT')

    def test_before_window_requires_all_gates_and_fresh_observation(self):
        at = self.at - timedelta(seconds=1)
        self.assertEqual(arm.decision(self.config, self.observation(at), at), 'BEFORE_WINDOW')
        for key in ('lock_absent', 'scheduler_idle', 'budget_available', 'preflight_pass', 'cpu_minute_pass'):
            for value in (False, None, 1):
                with self.subTest(key=key, value=value):
                    self.assertEqual(arm.decision(self.config, {**self.observation(at), key: value}, at), key.upper() + '_NOT_PASS')
        for key in ('source', 'profile'):
            self.assertEqual(arm.decision(self.config, {**self.observation(at), key: 'changed'}, at), 'SOURCE_OR_PROFILE_CHANGED')
        for finished in (None, (at - timedelta(seconds=151)).isoformat(), (at + timedelta(seconds=1)).isoformat()):
            self.assertEqual(arm.decision(self.config, {**self.observation(at), 'finished_at': finished}, at), 'OBSERVATION_NOT_FRESH')

    def test_invalid_request_id_window_and_hashes(self):
        arm.validate_config(self.config)
        for changes in ({'campaign_id': 'gt06-o4-formal-10/../other'}, {'campaign_id': 'gt06-o4-formal-10\n'},
                        {'source': 'frozen'}, {'arm_sha256': '0' * 64},
                        {'start': '2026-10-02T03:00:00'}, {'end': self.config['start']}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                arm.validate_config({**self.config, **changes})

    def test_successful_dry_run_then_dispatch_polls_selected_campaign(self):
        self.save_request()
        self.dry_run()
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.assertEqual(self.invoke('--validate'), 0)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        terminal = {'schema': 'HH-GT06-TASK-STATUS-1', 'task_path': '\\HHStudio.GT06.gt06-o4-formal-10',
                    'campaign_id': 'gt06-o4-formal-10', 'mode': 'campaign', 'state': 3,
                    'last_task_result': 1, 'instances': [], 'formal_acceptance': False}
        with patch.object(arm, 'fresh_probe', return_value=self.observation()) as probe, \
             patch.object(arm, 'keep_awake', return_value=contextlib.nullcontext()) as awake, \
             patch.object(arm.subprocess, 'run', side_effect=[subprocess.CompletedProcess([], 0),
                        subprocess.CompletedProcess([], 0, json.dumps(terminal).encode())]) as launcher:
            self.assertEqual(self.invoke('--run'), 0)
        awake.assert_called_once()
        self.assertEqual(probe.call_args.kwargs['own_arm_task'], 'HHStudio.GT06.arm-formal10-20261002')
        self.assertEqual(launcher.call_count, 2)
        dispatch, status = [call.args[0] for call in launcher.call_args_list]
        self.assertEqual(dispatch[-6:], ['-Command', 'register-run', '-CampaignId', 'gt06-o4-formal-10', '-Mode', 'campaign'])
        self.assertEqual(status[-4:], ['-Command', 'status', '-CampaignId', 'gt06-o4-formal-10'])
        self.assertEqual(json.loads((self.root / 'campaign-terminal-scheduler.json').read_bytes()), terminal)
        receipt = json.loads((self.root / 'campaign-status-receipt-01.json').read_bytes())
        self.assertEqual(receipt['return_code'], 0)
        self.assertEqual(receipt['stderr'], '')
        self.assertFalse(receipt['campaign_success'])

    def test_status_validation_rejects_malformed_and_mismatched_rows(self):
        valid = {'schema': arm.STATUS_SCHEMA, 'task_path': '\\HHStudio.GT06.gt06-o4-formal-10',
                 'campaign_id': 'gt06-o4-formal-10', 'mode': 'campaign', 'state': 3,
                 'last_task_result': 1, 'instances': []}
        arm.validate_status(valid, 'gt06-o4-formal-10')
        for field, value in (('schema', 'wrong'), ('campaign_id', 'gt06-o4-formal-09'),
                             ('task_path', '\\wrong'), ('mode', 'probe'), ('instances', {}),
                             ('last_task_result', '1')):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    arm.validate_status({**valid, field: value}, 'gt06-o4-formal-10')

    def test_nonzero_status_poll_retains_raw_receipt_and_does_not_retry(self):
        self.save_request()
        self.dry_run()
        result = subprocess.CompletedProcess([], 7, b'{"bad":true}', b'status failure')
        with patch.object(arm, 'fresh_probe', return_value=self.observation()), \
             patch.object(arm, 'keep_awake', return_value=contextlib.nullcontext()), \
             patch.object(arm.subprocess, 'run', side_effect=[subprocess.CompletedProcess([], 0), result]) as launcher:
            self.assertEqual(self.invoke('--run'), 1)
        self.assertEqual(launcher.call_count, 2)
        receipt = json.loads((self.root / 'campaign-status-receipt-01.json').read_bytes())
        self.assertEqual(receipt['return_code'], 7)
        self.assertEqual(receipt['stdout'], '{"bad":true}')
        self.assertEqual(receipt['stderr'], 'status failure')
        self.assertEqual(receipt['error'], 'CAMPAIGN_STATUS_NONZERO')

    def test_failed_dry_run_before_window_cannot_arm(self):
        self.config['start'] = (self.at + timedelta(hours=1)).isoformat()
        self.config['end'] = (self.at + timedelta(hours=5)).isoformat()
        self.save_request()
        with patch.object(arm, 'fresh_probe', return_value={**self.observation(), 'preflight_pass': False}), \
             patch.object(arm.subprocess, 'run') as launcher:
            self.assertEqual(self.invoke('--dry-run'), 1)
            self.assertEqual(self.invoke('--run'), 1)
        launcher.assert_not_called()
        self.assertFalse((self.root / 'dry-run-success.json').exists())
        self.assertFalse((self.root / 'arm-claim.json').exists())
        decision = json.loads(next(self.root.glob('dry-run-*-decision.json')).read_bytes())
        self.assertEqual(decision['decision'], 'PREFLIGHT_PASS_NOT_PASS')

    def test_missing_or_changed_dry_run_receipt_blocks_run(self):
        self.save_request()
        with patch.object(arm.subprocess, 'run') as launcher:
            self.assertEqual(self.invoke('--run'), 1)
            self.dry_run()
            self.request.write_bytes(self.request.read_bytes() + b'\n')
            self.assertEqual(self.invoke('--validate'), 1)
            self.assertEqual(self.invoke('--run'), 1)
        launcher.assert_not_called()
        self.assertEqual(len(list(self.root.glob('arm-failure-*.json'))), 2)

    def test_status_timeout_never_retries_dispatch_and_failures_are_per_attempt(self):
        self.save_request()
        self.dry_run()
        with patch.object(arm, 'fresh_probe', return_value=self.observation()), \
             patch.object(arm, 'keep_awake', return_value=contextlib.nullcontext()), \
             patch.object(arm.subprocess, 'run', side_effect=[subprocess.CompletedProcess([], 0),
                        subprocess.TimeoutExpired('status', 30)]) as launcher:
            self.assertEqual(self.invoke('--run'), 1)
            original = (self.root / 'dispatch-claim.json').read_bytes()
            self.assertEqual(self.invoke('--run'), 1)
        self.assertEqual(launcher.call_count, 2)
        self.assertEqual((self.root / 'dispatch-claim.json').read_bytes(), original)
        self.assertEqual(len(list(self.root.glob('arm-failure-*.json'))), 2)

    def test_probe_failure_has_attempt_receipt(self):
        with patch.object(arm, 'fresh_probe', side_effect=RuntimeError('FRESH_PROBE_EXIT_1')):
            self.assertEqual(arm.check(self.config, self.root, 'attempt-01'), 'PROBE_FAILED')
        self.assertEqual(json.loads((self.root / 'attempt-01-failure.json').read_bytes())['reason'], 'FRESH_PROBE_EXIT_1')

    def test_scheduler_excludes_only_own_arm_and_detects_other_gt06_tasks(self):
        own = arm.arm_task_name(self.config)
        rows = [{'name': own, 'task_path': '\\' + own}, {'name': 'OtherTask', 'task_path': '\\OtherTask'}]
        with patch.object(arm.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps(rows).encode())):
            self.assertTrue(arm.scheduler_idle(own))
            self.assertFalse(arm.scheduler_idle())
        rows.append({'name': 'HHStudio.GT06.gt06-o6-soak-other', 'task_path': '\\HHStudio.GT06.gt06-o6-soak-other'})
        with patch.object(arm.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps(rows).encode())):
            self.assertFalse(arm.scheduler_idle(own))

    def test_scheduler_inventory_failure_is_not_idle(self):
        for result in (subprocess.CompletedProcess([], 1, b''), subprocess.CompletedProcess([], 0, b'{}')):
            with patch.object(arm.subprocess, 'run', return_value=result), self.assertRaises(RuntimeError):
                arm.scheduler_idle()


if __name__ == '__main__':
    unittest.main()
