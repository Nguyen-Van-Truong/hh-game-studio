"""Reviewer UX regressions without Tk, HTTP or engine execution."""
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.reviewer.model import (CaptureMetadata, EventKind, HistoricalSummary,
    MAX_HISTORY, NextAction, ObservationRow, Phase, ReviewerEvent, ReviewerState,
    UiAction, UiCode, cleanup_held, closed, enabled_actions, reduce)


def begin(state, action, number):
    return reduce(state, ReviewerEvent(action, state.phase, UiCode.QUEUED,
                                      request_id=number, kind=EventKind.REQUESTED))


def reply(state, action, number, phase, code, **fields):
    return reduce(state, ReviewerEvent(action, phase, code, request_id=number, **fields))


class ReviewerModelTests(unittest.TestCase):
    def test_local_no_command_before_play_keeps_play_available(self):
        state = begin(ReviewerState(), UiAction.LOOKUP, 1)
        state = reply(state, UiAction.LOOKUP, 1, Phase.READY, UiCode.NO_COMMAND)
        self.assertEqual(state.phase, Phase.READY)
        self.assertIn(UiAction.PLAY, enabled_actions(state))

    def test_local_no_command_cannot_regress_locally_admitted_play(self):
        for response_arrived in (False, True):
            with self.subTest(response_arrived=response_arrived):
                state = begin(ReviewerState(), UiAction.LOOKUP, 1)
                state = begin(state, UiAction.PLAY, 2)
                if response_arrived:
                    state = reply(state, UiAction.PLAY, 2, Phase.RUNNING, UiCode.RUNNING)
                before = state.phase
                state = reply(state, UiAction.LOOKUP, 1, Phase.READY, UiCode.NO_COMMAND)
                self.assertEqual(state.phase, before)
                self.assertNotIn(UiAction.PLAY, enabled_actions(state))

    def test_ready_play_is_queued_and_cannot_be_submitted_twice(self):
        state = ReviewerState()
        self.assertIn(UiAction.PLAY, enabled_actions(state))
        state = begin(state, UiAction.PLAY, 1)
        self.assertEqual(state.phase, Phase.QUEUED)
        self.assertTrue(state.started)
        self.assertIs(begin(state, UiAction.PLAY, 2), state)
        state = reply(state, UiAction.PLAY, 1, Phase.RUNNING, UiCode.RUNNING)
        self.assertNotIn(UiAction.PLAY, enabled_actions(state))
        self.assertIsNone(state.progress)

    def test_stop_latches_before_io_and_late_start_result_never_resumes(self):
        state = begin(begin(ReviewerState(), UiAction.PLAY, 1), UiAction.STOP, 2)
        self.assertTrue(state.stop_latched)
        self.assertEqual(state.phase, Phase.DRAINING)
        state = reply(state, UiAction.PLAY, 1, Phase.RUNNING, UiCode.RUNNING, progress=10)
        self.assertEqual(state.phase, Phase.DRAINING)
        self.assertIsNone(state.progress)
        state = reply(state, UiAction.STOP, 2, Phase.STOPPED, UiCode.STOPPED, stop_confirmed=True)
        self.assertEqual(state.phase, Phase.STOPPED)
        self.assertNotIn(UiAction.PLAY, enabled_actions(state))

    def test_reconnect_only_lookup_and_server_ready_cannot_reenable_play(self):
        state = begin(ReviewerState(), UiAction.PLAY, 1)
        state = reply(state, UiAction.PLAY, 1, Phase.DISCONNECTED, UiCode.DISCONNECTED,
                      kind=EventKind.DISCONNECTED)
        self.assertEqual(state.next_action, NextAction.LOOKUP)
        self.assertFalse(state.connected)
        state = begin(state, UiAction.LOOKUP, 2)
        state = reply(state, UiAction.LOOKUP, 2, Phase.READY, UiCode.READY)
        self.assertEqual(state.phase, Phase.UNKNOWN)
        self.assertEqual(state.code, UiCode.INVALID_RESPONSE)
        self.assertNotIn(UiAction.PLAY, enabled_actions(state))

    def test_unknown_and_rejected_keep_safe_next_action_without_automatic_replay(self):
        for phase, code, next_action in ((Phase.UNKNOWN, UiCode.UNKNOWN, NextAction.LOOKUP),
                                        (Phase.REJECTED, UiCode.REJECTED, NextAction.REVIEW_ERROR)):
            state = begin(ReviewerState(), UiAction.PLAY, 1)
            state = reply(state, UiAction.PLAY, 1, phase, code, next_action=NextAction.PLAY)
            self.assertEqual(state.next_action, next_action)
            self.assertNotIn(UiAction.PLAY, enabled_actions(state))

    def test_stop_latch_survives_disconnect_and_lookup_completion(self):
        state = begin(ReviewerState(), UiAction.STOP, 1)
        state = reply(state, UiAction.STOP, 1, Phase.DISCONNECTED, UiCode.DISCONNECTED,
                      kind=EventKind.DISCONNECTED)
        state = begin(state, UiAction.LOOKUP, 2)
        state = reply(state, UiAction.LOOKUP, 2, Phase.COMMITTED, UiCode.COMPLETED)
        self.assertTrue(state.stop_latched)
        self.assertEqual(state.phase, Phase.DRAINING)
        self.assertEqual(state.code, UiCode.DRAINING)
        self.assertNotIn(UiAction.INSPECT, enabled_actions(state))

    def test_work_slot_is_bounded_and_stop_has_independent_capacity(self):
        state = ReviewerState(phase=Phase.COMMITTED, code=UiCode.COMPLETED, started=True)
        state = begin(state, UiAction.INSPECT, 1)
        self.assertIs(begin(state, UiAction.CAPTURE, 2), state)
        state = begin(state, UiAction.LOOKUP, 3)
        self.assertIn(UiAction.STOP, enabled_actions(state))
        state = begin(state, UiAction.STOP, 4)
        self.assertEqual(len(state.pending), 3)
        self.assertTrue(state.stop_latched)

    def test_duplicate_or_stale_callbacks_do_not_replace_state(self):
        state = begin(ReviewerState(), UiAction.PLAY, 1)
        state = reply(state, UiAction.PLAY, 1, Phase.COMMITTED, UiCode.COMPLETED, progress=100)
        late = reply(state, UiAction.PLAY, 1, Phase.RUNNING, UiCode.RUNNING, progress=2)
        self.assertEqual(late.phase, Phase.COMMITTED)
        self.assertEqual(late.progress, 100)
        self.assertEqual(late.dropped_updates, 1)

    def test_lookup_completion_cannot_be_undone_by_delayed_launch_response(self):
        state = begin(begin(ReviewerState(), UiAction.PLAY, 1), UiAction.LOOKUP, 2)
        state = reply(state, UiAction.LOOKUP, 2, Phase.COMMITTED, UiCode.COMPLETED)
        state = reply(state, UiAction.PLAY, 1, Phase.RUNNING, UiCode.RUNNING)
        self.assertEqual(state.phase, Phase.COMMITTED)
        self.assertTrue(state.completed)
        self.assertNotIn(UiAction.PLAY, enabled_actions(state))

    def test_retained_page_and_capture_are_immutable_bounded_and_preserved(self):
        row = ObservationRow(165, 'PAUSED', 140, 165, (1.5, 0.0, 0.0))
        capture = CaptureMetadata('menu', 1, 'MENU', 'a' * 64, 1000)
        summary = HistoricalSummary(rows=(row,), total_matches=50, has_next=True, capture=capture)
        with self.assertRaises(FrozenInstanceError):
            summary.has_next = False
        state = ReviewerState(phase=Phase.COMMITTED, code=UiCode.COMPLETED, started=True)
        state = begin(state, UiAction.INSPECT, 1)
        state = reply(state, UiAction.INSPECT, 1, Phase.COMMITTED, UiCode.INSPECTION_READY, historical=summary)
        state = begin(state, UiAction.LOOKUP, 2)
        state = reply(state, UiAction.LOOKUP, 2, Phase.COMMITTED, UiCode.COMPLETED)
        self.assertIs(state.historical, summary)
        with self.assertRaises(ValueError):
            HistoricalSummary(rows=(row,) * 9, total_matches=50)

    def test_no_raw_error_message_secret_url_or_arbitrary_capture_label_is_accepted(self):
        for kwargs in ({'code': 'Bearer secret'}, {'phase': 'https://private'}, {'progress': True},
                       {'request_id': -1}, {'next_action': 'start_again'}):
            base = dict(action=UiAction.PLAY, phase=Phase.UNKNOWN, code=UiCode.UNKNOWN)
            with self.assertRaises(ValueError):
                ReviewerEvent(**(base | kwargs))
        for label in ('../outside', 'Authorization', 'arbitrary_capture'):
            with self.assertRaises(ValueError):
                CaptureMetadata(label, 0, 'MENU', 'a' * 64, 100)
        with self.assertRaises(ValueError):
            HistoricalSummary(report_sha256='Bearer secret')

    def test_progress_numeric_limits_and_history_retention_are_bounded(self):
        for progress in (-1, 101, 1.5):
            with self.assertRaises(ValueError):
                ReviewerEvent(UiAction.PLAY, Phase.RUNNING, UiCode.RUNNING, progress=progress)
        state = ReviewerState(phase=Phase.UNKNOWN, code=UiCode.UNKNOWN, started=True)
        for number in range(1, 40):
            state = begin(state, UiAction.LOOKUP, number)
            state = reply(state, UiAction.LOOKUP, number, Phase.UNKNOWN, UiCode.UNKNOWN)
        self.assertEqual(len(state.history), MAX_HISTORY)
        self.assertFalse(state.pending)

    def test_cleanup_hold_never_claims_closed_and_closed_state_is_idempotent(self):
        state = cleanup_held(ReviewerState())
        self.assertEqual(state.phase, Phase.UNKNOWN)
        self.assertTrue(state.stop_latched)
        pending = begin(state, UiAction.LOOKUP, 1)
        with self.assertRaises(ValueError):
            closed(pending)
        final = closed(state)
        self.assertFalse(enabled_actions(final))
        self.assertIs(begin(final, UiAction.PLAY, 1), final)


if __name__ == '__main__':
    unittest.main()
