"""Deterministic lock-boundary regressions, real HTTP where it matters.

No Godot launch, benchmark thresholds or acceptance samples.
"""
from contextlib import contextmanager
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.host.core.journal import Journal, JournalError, JournalLimits
from studio.host.core.limits import SafetyViolation
from studio.host.core.transport import FixtureClient, LoopbackFixtureHost, epoch_ms
from studio.protocol.core import Status


@contextmanager
def fixture(*, start=False, limits=None):
    with tempfile.TemporaryDirectory(prefix='hh-pending-boundary-') as directory:
        root = Path(directory)
        journal = Journal(root / 'journal.jsonl', **({'limits': limits} if limits else {}))
        host = LoopbackFixtureHost('project.fixture', root, journal)
        credential = host.sessions.issue(scopes=frozenset({
            'fixture.read', 'fixture.write', 'control.stop', 'control.cancel'}))
        try:
            if start:
                host.start()
            yield host, credential
        finally:
            host.close()


class ObservedLock:
    def __init__(self, lock):
        self.lock, self.waiting = lock, threading.Event()

    def __enter__(self):
        if threading.current_thread().name == 'blocked-dispatch':
            self.waiting.set()
        return self.lock.__enter__()

    def __exit__(self, *args):
        return self.lock.__exit__(*args)


class PendingLookupTests(unittest.TestCase):
    def test_queued_lease_and_stop_recheck_rotated_or_expired_session(self):
        for path in ('/v1/lease', '/v1/stop'):
            for invalidation in ('rotate', 'expire'):
                with self.subTest(path=path, invalidation=invalidation), fixture() as (host, credential):
                    session = host.sessions.authenticate('Bearer ' + credential.bearer)
                    host._lock = ObservedLock(host._lock)
                    body = {'project_id': host.project_id}
                    body.update({'ttl_ms': 1000} if path == '/v1/lease' else {'command_id': 'stop.revoked'})
                    results = []

                    def dispatch():
                        try:
                            results.append(host._dispatch(path, body, session, path == '/v1/stop'))
                        except BaseException as error:
                            results.append(error)

                    current = [epoch_ms()]
                    with patch('studio.host.core.transport.epoch_ms', side_effect=lambda: current[0]):
                        thread = threading.Thread(target=dispatch, name='blocked-dispatch')
                        with host._lock:
                            thread.start()
                            try:
                                self.assertTrue(host._lock.waiting.wait(2))
                                if invalidation == 'rotate':
                                    host.sessions.rotate(credential)
                                else:
                                    current[0] = credential.expires_ms
                            finally:
                                # Exiting this block releases the original host lock.
                                pass
                        thread.join(3)
                    self.assertFalse(thread.is_alive())
                    self.assertEqual(len(results), 1)
                    self.assertIsInstance(results[0], SafetyViolation)
                    self.assertEqual(results[0].code, 'SESSION_INVALIDATED')
                    self.assertFalse(host._stopped.is_set())
                    self.assertEqual(host._leases, {})
                    self.assertEqual(host._stop_commands, {})

    def test_pending_lookup_responds_while_terminal_persistence_is_blocked(self):
        with fixture(start=True) as (host, credential):
            client = FixtureClient(host.port, host.control_port, credential)
            request = client.request('lookup.blocked.finish')
            entered, release = threading.Event(), threading.Event()
            original = host.journal.finish_command

            def finish(**kwargs):
                entered.set()
                if not release.wait(5):
                    raise AssertionError('test release missing')
                return original(**kwargs)

            with patch.object(host.journal, 'finish_command', side_effect=finish):
                try:
                    self.assertIs(client.submit(request).status, Status.ACCEPTED_PENDING)
                    self.assertTrue(entered.wait(2))
                    self.assertIs(client.lookup(request.command_id).status, Status.ACCEPTED_PENDING)
                    self.assertFalse(release.is_set())
                finally:
                    release.set()
            # Shutdown drains the existing worker before final durable inspection.
            host.close()
            result = host._lookup(request.command_id)
            self.assertIs(result.status, Status.COMMITTED)
            self.assertNotIn(request.command_id, host._pending_snapshot)

    def test_admission_failure_does_not_publish_pending_snapshot(self):
        with fixture(start=True) as (host, credential):
            client = FixtureClient(host.port, host.control_port, credential)
            request = client.request('lookup.undurable')
            with patch.object(host.journal, 'append_command', side_effect=JournalError('JOURNAL_WRITE_FAILED')):
                result = client.submit(request)
            self.assertIs(result.status, Status.UNKNOWN)
            self.assertNotIn(request.command_id, host._pending_snapshot)
            self.assertNotIn(request.command_id, host._jobs)
            self.assertEqual(host.fixture.effect_count, 0)

    def test_expired_pending_and_orphan_keep_durable_authority(self):
        with fixture(limits=JournalLimits(retry_horizon_ms=1000)) as (host, credential):
            session = host.sessions.authenticate('Bearer ' + credential.bearer)
            # Building a request needs discovery; use the authenticated local API.
            client = FixtureClient(1, 2, credential)
            with patch.object(client, 'discover', return_value=host.discovery(session)):
                request = client.request('lookup.expiry')
            now = epoch_ms()
            with patch('studio.host.core.transport.epoch_ms', return_value=now):
                pending = host._dispatch('/v1/commands', request.as_dict(), session, False)
            self.assertIs(pending.status, Status.ACCEPTED_PENDING)
            with patch('studio.host.core.transport.epoch_ms', return_value=now + 1001):
                with self.assertRaisesRegex(JournalError, 'RETRY_HORIZON_EXPIRED'):
                    host._lookup(request.command_id)
            host._pending_snapshot = {}
            with patch('studio.host.core.transport.epoch_ms', return_value=now):
                orphan = host._lookup(request.command_id)
            self.assertEqual((orphan.status, orphan.code), (Status.UNKNOWN, 'RECOVERY_REQUIRED'))


if __name__ == '__main__':
    unittest.main()
