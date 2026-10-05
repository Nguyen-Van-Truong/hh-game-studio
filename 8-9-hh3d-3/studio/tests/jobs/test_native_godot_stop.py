"""Godot queue Stop lifecycle with inert storage; no native engine evidence."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))

spec = importlib.util.spec_from_file_location(
    'gt07_native_godot_stop_owner', STUDIO / 'godot-addon/publication_owner.py')
owner_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = owner_module
spec.loader.exec_module(owner_module)
session_module = owner_module._load('publication_session')

from studio.host.jobs.native_dispatch import NativeDispatchError, NativeOwnerDispatcher
from studio.host.jobs.queue_owner import QueueOwner


class NativeGodotStopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gt07-godot-stop-')
        self.addCleanup(self.temp.cleanup)
        self.owner = object.__new__(owner_module.GodotPublicationOwner)
        self.owner._lock = threading.RLock()
        self.owner._attachment_lock = threading.RLock()
        self.owner._work = threading.Lock()
        self.owner.sessions = session_module.PublicationSession(
            'project.fixture', Path(self.temp.name), 'sha256:' + '1' * 64)
        self.owner._held = self.owner._closed = False
        self.owner._stop_thread = None
        self.owner._stop_persistence = 'NOT_REQUESTED'
        self.owner._same_release = Mock()
        self.owner._retired_editors = []
        self.owner._cleanup_owners = []
        self.owner._editor = Mock(spec=['close'])
        self.owner._validator = Mock(spec=['close'])
        self.journal = Mock(spec=['snapshot', 'stop', 'close'])
        self.journal.snapshot.return_value = {'stopped': False}
        self.owner._journal = self.journal

        # Exercise the real dispatcher lifecycle without native QueueOwner
        # storage. Work admission/receipt validation has separate tests.
        self.queue = object.__new__(QueueOwner)
        self.queue._lifecycle = threading.RLock()
        self.queue._dispatcher = None
        self.queue.broker = Mock(spec=['stop'])
        self.queue.broker.stop.return_value = SimpleNamespace(stopped=True)
        self.dispatch = NativeOwnerDispatcher(self.queue)
        self.owner._queue_dispatcher = self.dispatch
        self.binding = object()
        self.dispatch._owners['godot-inert'] = self.owner
        self.dispatch._bindings['inert-binding'] = self.binding
        self.release = threading.Event()
        self.workers = []
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.release.set()
        for worker in self.workers:
            worker.join(3)
            self.assertFalse(worker.is_alive(), 'Stop caller did not finish')
        thread = self.owner._stop_thread
        if thread is not None:
            thread.join(3)
            self.assertFalse(thread.is_alive(), 'Stop persistence did not finish')
        if not self.dispatch._closed:
            self.dispatch.close()
        if not self.owner._closed:
            self.owner.close()

    def block_persistence(self):
        entered = threading.Event()

        def persist(**_):
            entered.set()
            if not self.release.wait(5):
                raise TimeoutError('inert Stop barrier was not released')
            self.journal.snapshot.return_value = {'stopped': True}

        self.journal.stop.side_effect = persist
        return entered

    def test_stop_returns_while_pending_then_drain_requires_durable_readback(self):
        entered = self.block_persistence()
        returned = threading.Event()
        results, errors = [], []

        def stop():
            try:
                results.append(self.dispatch.stop())
            except BaseException as error:
                errors.append(error)
            finally:
                returned.set()

        worker = threading.Thread(target=stop, daemon=True)
        self.workers.append(worker)
        worker.start()
        self.assertTrue(returned.wait(1), 'Stop waited for owner persistence')
        self.assertTrue(entered.wait(1))
        self.assertEqual(errors, [])
        self.assertTrue(results[0].stopped)
        self.assertTrue(self.owner.sessions.status()['stopped'])
        self.assertFalse(self.release.is_set())
        self.assertEqual(self.owner._stop_persistence, 'PENDING')
        with self.assertRaisesRegex(NativeDispatchError, 'NATIVE_STOP_DRAIN_REQUIRED'):
            self.dispatch.drain_stop(timeout=0)
        self.assertIs(self.owner._queue_dispatcher, self.dispatch)

        self.release.set()
        self.dispatch.drain_stop(timeout=2)
        self.assertEqual(self.owner._stop_persistence, 'DURABLE')
        self.assertTrue(self.journal.snapshot()['stopped'])
        self.assertFalse(self.owner._stop_thread.is_alive())
        self.journal.stop.assert_called_once()
        self.queue.broker.stop.assert_called_once()

    def test_unknown_owner_stop_cannot_become_durable_queue_completion(self):
        self.journal.stop.side_effect = OSError('inert Stop persistence failure')
        self.assertTrue(self.dispatch.stop().stopped)
        with self.assertRaisesRegex(NativeDispatchError, 'NATIVE_STOP_UNKNOWN'):
            self.dispatch.drain_stop(timeout=2)
        self.assertEqual(self.owner._stop_persistence, 'UNKNOWN')
        self.assertTrue(self.owner._held)
        self.assertFalse(self.owner._stop_thread.is_alive())
        self.assertIs(self.owner._journal, self.journal)
        self.assertIs(self.owner._queue_dispatcher, self.dispatch)
        self.journal.close.assert_not_called()

    def test_durable_label_does_not_replace_current_journal_stop_readback(self):
        def persist(**_):
            self.journal.snapshot.return_value = {'stopped': True}

        self.journal.stop.side_effect = persist
        self.dispatch.stop()
        self.dispatch.drain_stop(timeout=2)
        self.assertEqual(self.owner._stop_persistence, 'DURABLE')

        self.journal.snapshot.return_value = {'stopped': False}
        with self.assertRaisesRegex(NativeDispatchError, 'NATIVE_STOP_UNKNOWN'):
            self.dispatch.drain_stop(timeout=0)
        self.assertIs(self.owner._queue_dispatcher, self.dispatch)
        self.journal.close.assert_not_called()

    def test_close_keeps_owner_and_queue_bound_until_stop_thread_finishes(self):
        entered = self.block_persistence()
        self.dispatch.stop()
        self.assertTrue(entered.wait(1))
        with self.assertRaisesRegex(NativeDispatchError, 'NATIVE_STOP_DRAIN_REQUIRED'):
            self.dispatch.close()
        self.assertIs(self.owner._queue_dispatcher, self.dispatch)
        self.assertIs(self.queue._dispatcher, self.dispatch)
        self.assertIs(self.dispatch._bindings['inert-binding'], self.binding)
        self.assertFalse(self.dispatch._closed)
        self.assertFalse(self.dispatch._phase.locked())
        self.owner._editor.close.assert_not_called()
        self.journal.close.assert_not_called()

        self.release.set()
        self.dispatch.drain_stop(timeout=2)
        self.dispatch.close()
        self.assertTrue(self.dispatch._closed)
        self.assertIsNone(self.owner._queue_dispatcher)
        self.assertIsNone(self.queue._dispatcher)
        self.assertEqual(self.dispatch._bindings, {})
        self.owner.close()
        self.journal.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
