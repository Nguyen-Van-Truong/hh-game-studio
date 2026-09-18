"""S79 independent engine-free fault probes. Review draft; runtime is unchanged.

Run from 8-9-hh3d-3:
  python -B zdoc/reviews/20260918-gt06-s79-diagnosis/index_fault_probe.py

The desired-contract assertions intentionally fail on the reviewed S78 source.
Only temporary files are written; no engine is imported or launched.
"""
from pathlib import Path
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from studio.host.core.journal import Journal, JournalError
from studio.host.replay.disk_journal_index import DiskIndexError
from studio.host.replay.verified_journal import VerifiedJournal
from studio.tests.replay.test_service import ReplayServiceTests, FakePreparedPlay
from studio.tests.replay.test_benchmark_commands import CommandProducerTests
from studio.protocol.core import Status


class ConnectionFault:
    """Wrap a real connection; inject once at a single SQLite boundary."""
    def __init__(self, real, *, execute_sql=None, close_sql=None, fail_close=False):
        self.real = real
        self.execute_sql, self.close_sql = execute_sql, close_sql
        self.fail_close = fail_close
        self.fired = False

    def execute(self, sql, args=()):
        if not self.fired and sql == self.execute_sql:
            self.fired = True
            raise sqlite3.OperationalError('injected execute failure')
        cursor = self.real.execute(sql, args)
        if not self.fired and sql.startswith(self.close_sql or '\0'):
            self.fired = True
            class CursorFault:
                def fetchone(self):
                    return cursor.fetchone()

                def close(self):
                    cursor.close()
                    raise sqlite3.OperationalError('injected cursor close failure')
            return CursorFault()
        return cursor

    def close(self):
        if not self.fired and self.fail_close:
            self.fired = True
            raise sqlite3.OperationalError('injected connection close failure')
        return self.real.close()


def emit(name, **values):
    print('INDEX_PROBE ' + json.dumps({'case': name, **values}, sort_keys=True), flush=True)


class IndexBoundaryProbes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='s79-index-probe-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'commands.jsonl'
        self.journal = VerifiedJournal(self.path)
        self.addCleanup(self.journal.close)

    def append(self, command='command.one'):
        return self.journal.append_command(project_id='p', command_id=command,
            digest='sha256:' + 'a' * 64, receipt={'value': command}, now_ms=1)

    def lookup(self, command='command.one'):
        return self.journal.lookup(project_id='p', command_id=command, now_ms=2)

    def test_commit_error_after_append_is_unknown_and_rebuilds_exactly_once(self):
        index = self.journal._index_store
        index._db = ConnectionFault(index._db, execute_sql='COMMIT')
        with self.assertRaises(JournalError) as caught:
            self.append()
        self.assertEqual(caught.exception.code, 'JOURNAL_INDEX_UNAVAILABLE')
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertIsNone(self.journal._verified_hash)
        self.assertEqual(len(self.path.read_bytes().splitlines()), 1)
        self.assertEqual(self.lookup()['receipt']['value'], 'command.one')
        self.assertIsNot(self.journal._index_store, index)
        self.assertTrue(self.append()['replayed'])
        self.assertEqual(len(self.path.read_bytes().splitlines()), 1)
        emit('post_fsync_commit', unknown=True, rebuilt=True, authoritative_rows=1)

    def test_failed_connection_close_retains_owner_and_retry_releases_it(self):
        self.append()
        index = self.journal._index_store
        private_dir = index._dir
        index._db = ConnectionFault(index._db, fail_close=True)
        with self.assertRaises(JournalError) as caught:
            self.journal.close()
        self.assertIs(caught.exception.cleanup_owner, self.journal)
        self.assertIs(self.journal._index_store, index)
        self.assertTrue(private_dir.exists())
        with self.assertRaises(JournalError):
            self.lookup()
        self.journal.close()
        self.assertFalse(private_dir.exists())
        self.assertTrue(self.path.exists())
        emit('connection_close_retry', owner_retained=True, scratch_removed=True, journal_retained=True)

    def test_failed_unlink_retains_owner_and_retry_releases_it(self):
        self.append()
        index = self.journal._index_store
        private_dir = index._dir
        original = Path.unlink

        def fail_owned(path, *args, **kwargs):
            if path.parent == private_dir:
                raise PermissionError('injected owned scratch unlink failure')
            return original(path, *args, **kwargs)

        with patch.object(Path, 'unlink', fail_owned):
            with self.assertRaises(JournalError) as caught:
                self.journal.close()
        self.assertIs(caught.exception.cleanup_owner, self.journal)
        self.assertIsNone(index._db)
        self.assertIs(self.journal._index_store, index)
        self.journal.close()
        self.assertFalse(private_dir.exists())
        self.assertTrue(self.path.exists())
        emit('unlink_retry', owner_retained=True, scratch_removed=True, journal_retained=True)

    def test_failed_rebuild_keeps_unverified_state_and_recovers(self):
        self.append()
        external = Journal(self.path)
        external.append_command(project_id='p', command_id='command.two',
            digest='sha256:' + 'a' * 64, receipt={'value': 'command.two'}, now_ms=1)
        from studio.host.replay import disk_journal_index as module
        original = module.sqlite3.connect

        def fail_rebuild(*args, **kwargs):
            return ConnectionFault(original(*args, **kwargs), execute_sql='INSERT INTO commands VALUES (?,?,?,?)')

        with patch.object(module.sqlite3, 'connect', side_effect=fail_rebuild):
            with self.assertRaises(JournalError) as caught:
                self.lookup('command.two')
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertIsNone(self.journal._verified_hash)
        self.assertIsNotNone(self.journal._index_store)
        self.assertEqual(self.lookup('command.two')['receipt']['value'], 'command.two')
        self.assertEqual(len(self.path.read_bytes().splitlines()), 2)
        emit('rebuild_failure', unknown=True, recovered=True, authoritative_rows=2)

    def test_cursor_close_error_after_fsync_must_keep_unknown_provenance(self):
        index = self.journal._index_store
        index._db = ConnectionFault(index._db, close_sql='INSERT INTO commands')
        try:
            self.append()
        except Exception as error:
            observed = error
        else:
            self.fail('fault did not fire')
        emit('post_fsync_cursor_close', exception=type(observed).__name__,
            outcome_unknown=getattr(observed, 'outcome_unknown', None),
            authoritative_rows=len(self.path.read_bytes().splitlines()),
            hash_poisoned=self.journal._verified_hash is None)
        self.assertIsInstance(observed, JournalError)
        self.assertTrue(observed.outcome_unknown)

    def test_cursor_close_error_on_lookup_must_invalidate_generation(self):
        self.append()
        index = self.journal._index_store
        index._db = ConnectionFault(index._db, close_sql='SELECT c.value')
        try:
            self.lookup()
        except Exception as error:
            observed = error
        else:
            self.fail('fault did not fire')
        emit('lookup_cursor_close', exception=type(observed).__name__,
            outcome_unknown=getattr(observed, 'outcome_unknown', None),
            hash_poisoned=self.journal._verified_hash is None)
        self.assertIsInstance(observed, JournalError)
        self.assertIsNone(self.journal._verified_hash)


class ServiceAdmissionProbe(unittest.TestCase):
    def test_pending_index_failure_must_halt_admission_and_report_unknown(self):
        fixture = ReplayServiceTests(methodName='test_close_drains_workers_and_rejects_further_routes')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        owner = fixture.owner
        index = owner._journal._index_store
        index._db = ConnectionFault(index._db, execute_sql='COMMIT')
        before = len(owner._journal.path.read_bytes().splitlines())
        with self.assertRaises(JournalError) as caught:
            owner.submit(fixture.request('command.first'), **fixture.auth())
        self.assertTrue(caught.exception.outcome_unknown)
        after = len(owner._journal.path.read_bytes().splitlines())
        # A repair may reconcile the one durable pending intent with an UNKNOWN
        # terminal. It must never append a second admission for the same ID.
        first_rows = [json.loads(line)['record'] for line in owner._journal.path.read_bytes().splitlines()
                      if json.loads(line)['record'].get('command_id') == 'command.first']
        self.assertEqual(sum(row['status'] == 'ACCEPTED_PENDING' for row in first_rows), 1)
        self.assertTrue(all(row['status'] == 'UNKNOWN' for row in first_rows[1:]))
        receipt = fixture.lookup('command.first')
        stopped = owner.sessions.status()['stopped']
        starts_before = fixture.backend.starts
        try:
            next_status = owner.submit(fixture.request('command.next'), **fixture.auth())['status']
        except Exception as error:
            next_status = getattr(error, 'code', type(error).__name__)
        emit('service_uncertain_admission', journal_error=caught.exception.code,
            durable_rows_added=after - before, first_lookup_status=receipt['status'],
            sessions_stopped_after_failure=stopped,
            overlay_present='command.first' in owner._uncertain,
            jobs_present='command.first' in owner._jobs,
            backend_starts_after_failure=starts_before,
            backend_starts_after_next_id=fixture.backend.starts,
            next_id_status=next_status)
        self.assertTrue(stopped, 'uncertain durable admission must halt new effects')
        self.assertEqual(receipt['status'], 'UNKNOWN')
        self.assertEqual(fixture.backend.starts, starts_before)

    def test_watchdog_start_failure_must_close_or_return_journal_owner(self):
        from studio.host.replay import service
        created = []
        original = service.Journal

        def capture_journal(*args, **kwargs):
            journal = original(*args, **kwargs)
            created.append(journal)
            self.addCleanup(journal.close)
            return journal

        temp = tempfile.TemporaryDirectory(prefix='s79-index-constructor-')
        self.addCleanup(temp.cleanup)
        with patch.object(service, 'PreparedPlay', FakePreparedPlay), \
                patch.object(service, 'Journal', side_effect=capture_journal), \
                patch.object(service.threading.Thread, 'start', side_effect=RuntimeError('injected start failure')):
            with self.assertRaises(RuntimeError) as caught:
                service.ReplayService(FakePreparedPlay(Path(temp.name)))
        journal = created[0]
        held = journal._index_store is not None and journal._index_store._db is not None
        emit('service_constructor_thread_start', journal_connection_live=held,
            cleanup_owner_returned=getattr(caught.exception, 'cleanup_owner', None) is not None,
            cache_closed=journal._cache_closed)
        self.assertTrue(journal._cache_closed or getattr(caught.exception, 'cleanup_owner', None) is not None)

    def test_constructor_cleanup_failure_must_return_retryable_service_owner(self):
        from studio.host.replay import service
        created = []
        original = service.Journal
        temp = tempfile.TemporaryDirectory(prefix='s79-index-held-constructor-')
        self.addCleanup(temp.cleanup)

        def capture_journal(*args, **kwargs):
            journal = original(*args, **kwargs)
            journal._index_store._db = ConnectionFault(journal._index_store._db, fail_close=True)
            created.append(journal)
            return journal

        with patch.object(service, 'PreparedPlay', FakePreparedPlay), \
                patch.object(service, 'Journal', side_effect=capture_journal), \
                patch.object(service.threading.Thread, 'start', side_effect=RuntimeError('injected start failure')):
            with self.assertRaises(RuntimeError) as caught:
                service.ReplayService(FakePreparedPlay(Path(temp.name)))
        journal = created[0]
        def cleanup_journal():
            try:
                journal.close()
            except JournalError:
                journal.close()
        self.addCleanup(cleanup_journal)
        owner = getattr(caught.exception, 'cleanup_owner', None)
        emit('service_constructor_cleanup_held', cleanup_owner_returned=owner is not None,
            index_owner_retained=journal._index_store is not None)
        self.assertIsInstance(owner, service.ReplayService)
        self.assertIs(owner._journal, journal)
        owner.close()
        self.assertIsNone(journal._index_store)


class BenchmarkTransportProbes(unittest.TestCase):
    def prepare(self):
        fixture = CommandProducerTests(methodName='test_cleanup_held_is_retained_and_retry_is_explicit')
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        producer = fixture.producer
        lease = producer._connect_batch()
        return producer, producer.client.request('command.index.fault', value=1, lease=lease)

    def test_actual_benchmark_transport_commit_error_halts_and_reconciles(self):
        producer, request = self.prepare()
        index = producer.journal._index_store
        index._db = ConnectionFault(index._db, execute_sql='COMMIT')
        reply = producer.client.submit(request)
        lookup = producer.client.lookup(request.command_id)
        emit('benchmark_commit_failure', submit_status=reply.status.value, submit_code=reply.code,
            admission_stopped=producer.host._stopped.is_set(),
            lookup_status=lookup.status.value, lookup_code=lookup.code,
            effects=producer.host.fixture.effect_count)
        self.assertIs(reply.status, Status.UNKNOWN)
        self.assertEqual(reply.code, 'JOURNAL_INDEX_UNAVAILABLE')
        self.assertTrue(producer.host._stopped.is_set())
        self.assertIs(lookup.status, Status.UNKNOWN)
        self.assertEqual(lookup.code, 'RECOVERY_REQUIRED')
        self.assertEqual(producer.host.fixture.effect_count, 0)

    def test_actual_benchmark_transport_cursor_close_error_must_halt(self):
        producer, request = self.prepare()
        index = producer.journal._index_store
        index._db = ConnectionFault(index._db, close_sql='INSERT INTO commands')
        reply = producer.client.submit(request)
        lookup = producer.client.lookup(request.command_id)
        emit('benchmark_cursor_close_failure', submit_status=reply.status.value, submit_code=reply.code,
            admission_stopped=producer.host._stopped.is_set(),
            lookup_status=lookup.status.value, lookup_code=lookup.code,
            effects=producer.host.fixture.effect_count)
        self.assertIs(reply.status, Status.UNKNOWN)
        self.assertTrue(producer.host._stopped.is_set())
        self.assertEqual(reply.code, 'JOURNAL_INDEX_UNAVAILABLE')


if __name__ == '__main__':
    manifest = {}
    for relative in ('host/replay/disk_journal_index.py', 'host/replay/verified_journal.py',
                     'host/replay/service.py', 'host/core/journal.py'):
        manifest[relative] = hashlib.sha256((ROOT / 'studio' / relative).read_bytes()).hexdigest()
    emit('source', files=manifest)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls)
                               for cls in (IndexBoundaryProbes, ServiceAdmissionProbe, BenchmarkTransportProbes))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    emit('result', tests=result.testsRun, failures=len(result.failures), errors=len(result.errors))
    sys.exit(not result.wasSuccessful())
