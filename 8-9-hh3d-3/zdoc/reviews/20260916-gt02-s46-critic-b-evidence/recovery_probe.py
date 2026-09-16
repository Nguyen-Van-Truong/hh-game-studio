"""Independent bounded critic checks; real storage, substituted pipe frame I/O."""
import json
import threading
import unittest
from unittest import mock

from test_managed_service import ManagedServiceTests, SafetyViolation
from test_managed_fixture import ManagedFixtureTests


class CriticDeadline(ManagedServiceTests):
    def test_reader_after_expiry_cannot_issue_lease_during_blocked_phase(self):
        self.start(session_timeout_ms=900)
        request = self.request()
        entered = threading.Event()
        original = self.owner.selector.stage

        def blocked(*args, **kwargs):
            entered.set()
            if not self.release.wait(3):
                raise AssertionError('critic phase gate expired')
            return original(*args, **kwargs)

        with mock.patch.object(self.owner.selector, 'stage', side_effect=blocked):
            self.send('/v1/commands', request)
            self.assertTrue(entered.wait(2))
            pending = self.replies['work'].get(timeout=2)
            self.assertEqual(pending['status'], 'ACCEPTED_PENDING')
            before = self.owner.log.binding().witnessed
            rotated = self.broker.sessions.rotate(self.credential)
            self.wait_for(lambda: self.service.status()['session_ended'])
            self.assertEqual(self.service.status()['reason'], 'SERVICE_SESSION_EXPIRED')
            self.assertGreater(self.service.status()['live_threads'], 0)
            with self.assertRaises(SafetyViolation):
                self.broker.sessions.authenticate('Bearer ' + rotated.bearer)
            self.credential = rotated
            self.send('/v1/lease', {'project_id':'project.fixture', 'ttl_ms':1000})
            self.assertEqual(self.owner.log.binding().witnessed, before)
            self.assertTrue(self.replies['work'].empty())
            self.assertTrue(self.broker._hold.is_set())
            self.release.set()
            self.wait_for(lambda: self.service.status()['live_threads'] == 0)
            self.assertEqual(self.owner.selector.lookup('cmd.service')['phase'], 'STAGED')
            self.assertIsNone(self.owner.selector.snapshot()['selected'])
            self.assertEqual(self.owner.consumer.adoption_count, 0)
        self.service.close()
        self.assertTrue(self.service.status()['closed'])
        print('HH_CRITIC_B_LATE_READER ' + json.dumps({
            'post_expiry_new_lease':False, 'rotated_credential_revoked':True,
            'admitted_stage_finished_once':True, 'adoption_count':0,
            'threads_after_close':0}), flush=True)


SELECTIONS = {
    ManagedFixtureTests: [
        'test_terminal_restart_rearms_fresh_command_and_keeps_original_receipts',
        'test_stop_restart_keeps_write_hold_and_never_resumes',
        'test_pending_restart_preserves_file_and_denies_fresh_admission',
        'test_custody_failure_after_terminal_write_is_unknown_then_confirms_once',
        'test_whole_record_loss_below_durable_witness_is_rejected',
        'test_actual_process_exit_reopens_only_from_durable_storage_id',
        'test_poisoned_custody_retries_remain_unknown_without_writes',
        'test_restart_fences_unexpired_old_lease_before_new_session',
        'test_rearm_refuses_orphan_namespace_without_overwriting_or_deleting',
        'test_second_owner_cannot_change_custody_while_guard_is_owned',
    ],
    ManagedServiceTests: [
        'test_late_read_cannot_dispatch_before_watchdog_observes_expiry',
        'test_lost_accepted_reply_holds_after_admitted_phase_without_replay',
        'test_control_failure_revokes_rotated_session_and_stops_work',
        'test_close_timeout_retains_entire_chain_until_blocked_phase_finishes',
        'test_endpoint_close_failure_preserves_owner_and_retries_same_handle',
        'test_bootstrap_delivery_failure_keeps_cleanup_owner_without_readers',
        'test_partial_thread_start_failure_drains_the_started_thread',
        'test_deadline_revokes_admission_even_while_phase_pump_is_blocked',
    ],
    CriticDeadline: ['test_reader_after_expiry_cannot_issue_lease_during_blocked_phase'],
}
suite = unittest.TestSuite(cls(name) for cls, names in SELECTIONS.items() for name in names)
result = unittest.TextTestRunner(verbosity=2).run(suite)
print('HH_CRITIC_B_TEST_RESULT ' + json.dumps({'run':result.testsRun,
    'failures':len(result.failures), 'errors':len(result.errors), 'skips':len(result.skipped)}), flush=True)
raise SystemExit(0 if result.wasSuccessful() and result.testsRun == 19 and not result.skipped else 1)
