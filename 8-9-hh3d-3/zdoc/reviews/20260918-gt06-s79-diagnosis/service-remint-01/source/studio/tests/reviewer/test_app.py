"""Bounded worker and close logic; fake Tk shell, no HTTP or engines."""
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.reviewer.app import BoundedWorkers, ReviewerWindow
from studio.reviewer.model import (EventKind, Phase, ReviewerEvent, UiAction, UiCode,
                                   enabled_actions)


class FakeButton:
    def focus_set(self): pass


class FakeRoot:
    def __init__(self):
        self.destroyed = False
        self.callbacks = []
    def title(self, value): pass
    def minsize(self, *value): pass
    def protocol(self, *value): pass
    def bind(self, *value): pass
    def after(self, delay, callback):
        self.callbacks.append((delay, callback))
        return len(self.callbacks)
    def destroy(self):
        self.destroyed = True


class BlockingClient:
    def __init__(self):
        self.entered = {action: threading.Event() for action in UiAction}
        self.release = {action: threading.Event() for action in UiAction}
        self.calls = []
        self.thread_ids = []
        self.failure = False

    def perform(self, action):
        self.calls.append(action)
        self.thread_ids.append(threading.get_ident())
        self.entered[action].set()
        self.release[action].wait(2)
        if self.failure:
            raise RuntimeError('Authorization: Bearer must-never-reach-the-view')
        phase = Phase.DRAINING if action is UiAction.STOP else Phase.RUNNING
        return ReviewerEvent(action, phase, UiCode.DRAINING if action is UiAction.STOP else UiCode.RUNNING)

    def release_all(self):
        for event in self.release.values():
            event.set()


class ReviewerAppTests(unittest.TestCase):
    def setUp(self):
        self.client = BlockingClient()
        self.addCleanup(self.client.release_all)
        build = patch.object(ReviewerWindow, '_build', lambda window: setattr(window, 'buttons', {UiAction.PLAY: FakeButton()}))
        render = patch.object(ReviewerWindow, '_render', lambda window: None)
        build.start()
        render.start()
        self.addCleanup(build.stop)
        self.addCleanup(render.stop)

    def window(self, **options):
        return ReviewerWindow(FakeRoot(), self.client, **options)

    def until(self, predicate, pump=lambda: None):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            pump()
            if predicate():
                return
            threading.Event().wait(.005)
        self.fail('bounded asynchronous result did not arrive')

    def test_network_is_off_main_thread_with_independent_priority_stop(self):
        window = self.window()
        for action in (UiAction.PLAY, UiAction.LOOKUP, UiAction.STOP):
            self.assertTrue(window.dispatch(action))
            self.assertTrue(self.client.entered[action].wait(1))
        self.assertEqual(window.workers.active, 3)
        self.assertTrue(window.state.stop_latched)
        self.assertEqual(window.state.phase, Phase.DRAINING)
        self.assertNotIn(threading.get_ident(), self.client.thread_ids)
        self.assertFalse(window.dispatch(UiAction.LOOKUP))
        self.assertFalse(window.dispatch(UiAction.PLAY))
        self.client.release_all()
        self.until(lambda: not window.workers.active, window.pump)
        self.assertEqual(len(self.client.calls), 3)

    def test_receipts_are_retained_until_taken_and_work_cannot_flood_mailbox(self):
        workers = BoundedWorkers(self.client)
        for number, action in enumerate((UiAction.PLAY, UiAction.LOOKUP, UiAction.STOP), 1):
            self.assertTrue(workers.submit(action, number))
        self.client.release_all()
        self.until(lambda: workers._outbox.qsize() == 3)
        for action in UiAction:
            self.assertFalse(workers.submit(action, 10))
        events = workers.take()
        self.assertEqual({event.request_id for event in events}, {1, 2, 3})
        self.assertEqual(workers.active, 0)
        self.assertFalse(workers.take())

    def test_exception_text_never_enters_event_or_state(self):
        self.client.failure = True
        window = self.window()
        window.dispatch(UiAction.PLAY)
        self.client.release_all()
        self.until(lambda: window.state.phase is Phase.DISCONNECTED, window.pump)
        self.assertNotIn('Bearer', repr(window.state))
        self.assertNotIn('must-never', repr(window.state))
        self.assertNotIn(UiAction.PLAY, enabled_actions(window.state))

    def test_automatic_lookup_does_not_spawn_multiple_pending_lookups_or_restart(self):
        window = self.window()
        window.dispatch(UiAction.PLAY)
        window._last_lookup = 0
        self.client.release[UiAction.PLAY].set()
        self.until(lambda: self.client.entered[UiAction.LOOKUP].is_set(), window.pump)
        for _ in range(20):
            window.pump()
        self.assertTrue(self.client.entered[UiAction.LOOKUP].wait(1))
        self.assertEqual(self.client.calls.count(UiAction.LOOKUP), 1)
        self.assertEqual(self.client.calls.count(UiAction.PLAY), 1)
        self.client.release_all()
        self.until(lambda: not window.workers.active, window.pump)

    def test_automatic_lookup_waits_for_initial_play_response(self):
        window = self.window()
        window.dispatch(UiAction.PLAY)
        for _ in range(20):
            window.pump()
        self.assertNotIn(UiAction.LOOKUP, self.client.calls)
        self.assertEqual(window.state.phase, Phase.QUEUED)
        self.assertTrue(window.dispatch(UiAction.STOP))
        self.assertTrue(self.client.entered[UiAction.STOP].wait(1))
        self.client.release_all()
        self.until(lambda: not window.workers.active, window.pump)

    def test_close_does_not_replace_drained_slow_lookup_with_another(self):
        cleaned = threading.Event()
        window = self.window(on_close=lambda: cleaned.set() or True)
        window.dispatch(UiAction.LOOKUP)
        self.assertTrue(self.client.entered[UiAction.LOOKUP].wait(1))
        window.close()
        self.assertTrue(self.client.entered[UiAction.STOP].wait(1))
        # Completing after a polling interval previously scheduled a fresh
        # lookup before cleanup got its chance, indefinitely under slow I/O.
        self.client.release_all()
        self.until(lambda: window.workers._outbox.qsize() == 2)
        window._last_lookup = time.monotonic() - 2
        self.until(lambda: window.root.destroyed, window.pump)
        self.assertTrue(cleaned.is_set())
        self.assertEqual(self.client.calls.count(UiAction.LOOKUP), 1)

    def test_close_requests_stop_and_waits_for_workers_before_cleanup_callback(self):
        cleaned = threading.Event()
        callback_threads = []

        def cleanup():
            callback_threads.append(threading.get_ident())
            cleaned.set()
            return True

        window = self.window(on_close=cleanup)
        window.dispatch(UiAction.PLAY)
        window.close()
        self.assertTrue(window.state.stop_latched)
        self.assertTrue(self.client.entered[UiAction.STOP].wait(1))
        window.pump()
        self.assertFalse(cleaned.is_set())
        self.assertFalse(window.root.destroyed)
        self.client.release_all()
        self.until(lambda: window.root.destroyed, window.pump)
        self.assertTrue(cleaned.is_set())
        self.assertNotIn(threading.get_ident(), callback_threads)
        count = len(self.client.calls)
        window.close()
        window.pump()
        self.assertEqual(len(self.client.calls), count)
        self.assertEqual(window.state.phase, Phase.CLOSED)

    def test_cleanup_failure_retains_window_and_reconnect_never_plays(self):
        window = self.window(on_close=lambda: False)
        self.client.release_all()
        window.close()
        self.until(lambda: window.state.code is UiCode.CLEANUP_HELD, window.pump)
        self.assertFalse(window.root.destroyed)
        self.assertIn(UiAction.LOOKUP, enabled_actions(window.state))
        self.assertNotIn(UiAction.PLAY, enabled_actions(window.state))
        self.assertTrue(window.dispatch(UiAction.LOOKUP))
        self.until(lambda: not window.workers.active, window.pump)
        self.assertNotIn(UiAction.PLAY, self.client.calls)

    def test_cleanup_timeout_retains_owner_and_does_not_launch_duplicate_cleanup(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        calls = []

        def cleanup():
            calls.append(True)
            entered.set()
            release.wait(2)
            return True

        window = self.window(on_close=cleanup)
        self.client.release_all()
        window.close()
        self.until(entered.is_set, window.pump)
        window._check_close(time.monotonic() + 31)
        self.assertFalse(window.root.destroyed)
        self.assertEqual(window.state.phase, Phase.UNKNOWN)
        window.close()
        window.pump()
        self.assertEqual(len(calls), 1)
        release.set()
        self.until(lambda: window.root.destroyed, window.pump)
        self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
