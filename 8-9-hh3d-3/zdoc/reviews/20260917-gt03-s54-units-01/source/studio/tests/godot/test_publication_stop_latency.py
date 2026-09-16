"""Event-controlled receipt/Stop races with inert storage; no engine proof."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
spec = importlib.util.spec_from_file_location('s54_stop_latency_owner', STUDIO / 'godot-addon/publication_owner.py')
owner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = owner
spec.loader.exec_module(owner)
from studio.protocol.core import Request, Response, Status, canonical_bytes


class PublicationStopLatencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hh-stop-latency-')
        self.addCleanup(self.temp.cleanup)
        value = self.value = object.__new__(owner.GodotPublicationOwner)
        value._lock = threading.RLock()
        value._work = threading.Lock()
        value._closed = value._held = False
        value._stop_thread = None
        value._stop_persistence = 'NOT_REQUESTED'
        value._editor = value._validator = None
        value._cleanup_owners, value._retired_editors = [], []
        value._jobs, value._leases, value._read_leases = {}, {}, {}
        value._same_release = Mock()
        value.project_id = 'project.fixture'
        session = owner._load('publication_session')
        self.catalog = 'sha256:' + '1' * 64
        value.sessions = session.PublicationSession(value.project_id, Path(self.temp.name), self.catalog)
        credential = value.sessions.issue()
        self.arguments = {'authorization': 'Bearer ' + credential.bearer, 'catalog_digest': self.catalog}
        self.request = Request(command_id='command.original', project_id=value.project_id, operation='scene.save',
            lease_id='lease.expired', fencing_epoch=1, expected_revision='sha256:' + '3' * 64,
            target={'stable_id': 'root'}, payload={}, payload_hash='sha256:' + hashlib.sha256(b'{}').hexdigest(),
            deadline_ms=1)
        self.raw = canonical_bytes(Response(Status.COMMITTED, 'GODOT_MANAGED_SCENE_SAVED', self.request.command_id,
            postconditions={'request_digest': self.request.digest, 'durable_receipt_sha256': '2' * 64,
                            'public_ack': True}).as_dict())
        self.record = {'digest': self.request.digest, 'status': 'COMMITTED',
                      'durable_response_sha256': hashlib.sha256(self.raw).hexdigest()}
        value._jobs[self.request.command_id] = self.record
        self.journal = value._journal = Mock()
        self.journal.lookup_response.return_value = self.raw
        self.journal.lookup.return_value = {'phase': 'COMMITTED', 'receipt_sha256': '2' * 64}
        self.journal.snapshot.return_value = {'stopped': False}
        self.journal.stop.side_effect = lambda **kwargs: setattr(self.journal.snapshot, 'return_value', {'stopped': True})

    def _start(self, action):
        outcome, done = [], threading.Event()
        def run():
            try:
                outcome.append(action())
            except BaseException as error:
                outcome.append(error)
            finally:
                done.set()
        thread = threading.Thread(target=run)
        thread.start()
        return thread, outcome, done

    def _join(self, worker):
        thread, outcome, done = worker
        thread.join(2)
        self.assertFalse(thread.is_alive(), 'inert worker must drain')
        self.assertTrue(done.is_set())
        self.assertEqual(len(outcome), 1)
        if isinstance(outcome[0], BaseException):
            raise outcome[0]
        return outcome[0]

    def _blocked_receipt_stop(self, replay):
        entered, release = threading.Event(), threading.Event()
        def read(*args):
            entered.set()
            if not release.wait(5):
                raise TimeoutError('inert receipt barrier')
            return self.raw
        self.journal.lookup_response.side_effect = read
        # A current worker keeps the durable Stop drain pending, independently
        # of the blocked historical response and its control listener.
        self.value._work.acquire()
        lookup = stop = None
        try:
            lookup = self._start(replay)
            self.assertTrue(entered.wait(1))
            stop = self._start(lambda: self.value.stop(
                {'project_id': self.value.project_id, 'command_id': 'control.stop'}, **self.arguments))
            self.assertTrue(stop[2].wait(1), 'Stop reply must not wait for historical receipt I/O')
            stopped = self._join(stop)
            self.assertTrue(stopped['stopped'])
            self.assertFalse(stopped['public_ack'])
            self.assertEqual(stopped['stop_persistence'], 'PENDING')
            self.journal.stop.assert_not_called()
            self.assertFalse(lookup[2].is_set())
        finally:
            release.set()
            self.value._work.release()
            if lookup is not None:
                result = self._join(lookup)
                self.assertEqual(canonical_bytes(result.as_dict()), self.raw)
            if stop is not None and stop[0].is_alive():
                self._join(stop)
            if self.value._stop_thread is not None:
                self.value._stop_thread.join(2)
                self.assertFalse(self.value._stop_thread.is_alive())
        self.assertEqual(self.value._stop_persistence, 'DURABLE')
        self.journal.stop.assert_called_once()
        self.value.close()
        self.assertIsNone(self.value._journal)

    def test_lookup_does_not_hold_owner_lock_across_receipt_io(self):
        self._blocked_receipt_stop(lambda: self.value.lookup(
            {'project_id': self.value.project_id, 'command_id': self.request.command_id}, **self.arguments))

    def test_submit_duplicate_does_not_hold_owner_lock_or_require_live_lease(self):
        self._blocked_receipt_stop(lambda: self.value.submit(self.request.as_dict(), **self.arguments))

    def test_reply_uses_record_snapshot_while_receipt_read_is_blocked(self):
        entered, release = threading.Event(), threading.Event()
        def read(*args):
            entered.set()
            if not release.wait(3):
                raise TimeoutError('inert receipt barrier')
            return self.raw
        self.journal.lookup_response.side_effect = read
        worker = self._start(lambda: self.value._reply(self.request.command_id, self.record))
        try:
            self.assertTrue(entered.wait(1))
            # A later record update cannot substitute the digest/hash used for
            # the already started verification.
            self.value._update_record(self.record, digest='sha256:' + '4' * 64,
                                      durable_response_sha256='5' * 64)
        finally:
            release.set()
            result = self._join(worker)
        self.assertEqual(canonical_bytes(result.as_dict()), self.raw)
        self.journal.lookup.assert_called_once_with(self.request.command_id, self.request.digest)

    def test_concurrent_close_retains_journal_if_its_read_is_still_owned(self):
        entered, release, native_lock = threading.Event(), threading.Event(), threading.Lock()
        closed = []
        def read(*args):
            with native_lock:
                entered.set()
                if not release.wait(3):
                    raise TimeoutError('inert receipt barrier')
                return self.raw
        def close():
            if not native_lock.acquire(timeout=.05):
                raise OSError('inert journal still owned')
            try:
                closed.append(True)
            finally:
                native_lock.release()
        self.journal.lookup_response.side_effect = read
        self.journal.close.side_effect = close
        worker = self._start(lambda: self.value._reply(self.request.command_id, self.record))
        try:
            self.assertTrue(entered.wait(1))
            with self.assertRaises(owner.PublicationOwnerError) as error:
                self.value.close()
            self.assertIs(error.exception.cleanup_owner, self.value)
            self.assertIs(self.value._journal, self.journal)
            self.assertEqual(closed, [])
        finally:
            release.set()
            result = self._join(worker)
        self.assertEqual(canonical_bytes(result.as_dict()), self.raw)
        self.value.close()
        self.assertIsNone(self.value._journal)
        self.assertEqual(closed, [True])

    def test_close_between_response_and_receipt_read_cannot_return_ack(self):
        def close_after_response(*args):
            self.value.close()
            return self.raw
        self.journal.lookup_response.side_effect = close_after_response
        self.journal.lookup.side_effect = OSError('inert journal closed')
        result = self.value._reply(self.request.command_id, self.record)
        self.assertEqual(result.status, Status.UNKNOWN)
        self.assertFalse(result.postconditions['public_ack'])
        self.assertIsNone(self.value._journal)
        self.assertTrue(self.value._held)


if __name__ == '__main__':
    unittest.main()
