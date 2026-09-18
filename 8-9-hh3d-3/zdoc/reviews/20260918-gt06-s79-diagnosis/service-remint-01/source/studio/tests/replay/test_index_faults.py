"""Derived-index fault boundaries with real journals and bounded local fixtures.

ReplayService uses a fake backend; command-host cases use actual loopback HTTP
and a synthetic observer. These tests never launch an engine or a campaign.
"""
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from studio.host.core.journal import Journal, JournalError
from studio.host.core.limits import SafetyViolation
from studio.host.replay import disk_journal_index, service
from studio.host.replay.verified_journal import VerifiedJournal
from studio.protocol.core import Status
# Import modules, not their TestCase classes: unittest must not rediscover the
# fixture suites as additional tests belonging to this module.
from studio.tests.replay import test_benchmark_commands as command_fixtures
from studio.tests.replay import test_service as service_fixtures


class _ConnectionFault:
    """Inject once at one SQLite boundary around a real owned connection."""
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
        if not self.fired and self.close_sql is not None and sql.startswith(self.close_sql):
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


def _records(path):
    return [json.loads(line)['record'] for line in path.read_bytes().splitlines()]


def _cleanup_journal(journal):
    # Test hygiene when an earlier assertion prevents consuming the deliberately
    # armed one-shot close fault. Assertions below independently prove cleanup.
    try:
        journal.close()
    except JournalError:
        journal.close()


class IndexFaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hh-index-fault-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'commands.jsonl'
        self.journal = VerifiedJournal(self.path)
        self.addCleanup(self._close_and_check_scratch)

    def _close_and_check_scratch(self):
        _cleanup_journal(self.journal)
        self.assertIsNone(self.journal._index_store)
        self.assertEqual(list(self.path.parent.glob('.hh-index-*')), [])

    def append(self, command='command.one'):
        return self.journal.append_command(project_id='p', command_id=command,
            digest='sha256:' + 'a' * 64, receipt={'value': command}, now_ms=1)

    def lookup(self, command='command.one'):
        return self.journal.lookup(project_id='p', command_id=command, now_ms=2)

    def assert_unknown(self, error):
        self.assertEqual(error.code, 'JOURNAL_INDEX_UNAVAILABLE')
        self.assertTrue(error.outcome_unknown)
        self.assertIsNone(self.journal._verified_hash)

    def test_commit_failure_after_fsync_rebuilds_without_duplicate_append(self):
        index = self.journal._index_store
        private_dir = index._dir
        fault = _ConnectionFault(index._db, execute_sql='COMMIT')
        index._db = fault
        with self.assertRaises(JournalError) as caught:
            self.append()
        self.assertTrue(fault.fired)
        self.assert_unknown(caught.exception)
        durable = self.path.read_bytes()
        self.assertEqual([row['command_id'] for row in _records(self.path)], ['command.one'])
        self.assertEqual(self.lookup()['receipt'], {'value': 'command.one'})
        self.assertIsNot(self.journal._index_store, index)
        self.assertFalse(private_dir.exists())
        self.assertIsNone(index._db)
        self.assertTrue(self.append()['replayed'])
        self.assertEqual(self.path.read_bytes(), durable)

    def test_failed_connection_close_retains_owner_and_retry_releases_scratch(self):
        self.append()
        durable = self.path.read_bytes()
        index = self.journal._index_store
        private_dir = index._dir
        fault = _ConnectionFault(index._db, fail_close=True)
        index._db = fault
        with self.assertRaises(JournalError) as caught:
            self.journal.close()
        self.assertTrue(fault.fired)
        self.assert_unknown(caught.exception)
        self.assertIs(caught.exception.cleanup_owner, self.journal)
        self.assertIs(self.journal._index_store, index)
        self.assertIs(index._db, fault)
        self.assertTrue(private_dir.exists())
        with self.assertRaises(JournalError) as blocked:
            self.lookup()
        self.assert_unknown(blocked.exception)
        self.journal.close()
        self.assertIsNone(self.journal._index_store)
        self.assertIsNone(index._db)
        self.assertFalse(private_dir.exists())
        self.assertEqual(self.path.read_bytes(), durable)
        self.assertTrue(self.path.with_name(self.path.name + '.guard').exists())

    def test_failed_unlink_retains_closed_database_owner_until_retry(self):
        self.append()
        durable = self.path.read_bytes()
        index = self.journal._index_store
        private_dir = index._dir
        original = Path.unlink

        def fail_owned(path, *args, **kwargs):
            if path.parent == private_dir:
                raise PermissionError('injected scratch unlink failure')
            return original(path, *args, **kwargs)

        with patch.object(Path, 'unlink', fail_owned):
            with self.assertRaises(JournalError) as caught:
                self.journal.close()
        self.assert_unknown(caught.exception)
        self.assertIs(caught.exception.cleanup_owner, self.journal)
        self.assertIsNone(index._db)
        self.assertIs(self.journal._index_store, index)
        self.assertTrue(private_dir.exists())
        with self.assertRaises(JournalError):
            self.lookup()
        self.journal.close()
        self.assertIsNone(self.journal._index_store)
        self.assertFalse(private_dir.exists())
        self.assertEqual(self.path.read_bytes(), durable)

    def test_failed_rebuild_discards_partial_index_and_recovers_both_commands(self):
        self.append()
        old_dir = self.journal._index_store._dir
        external = Journal(self.path)
        external.append_command(project_id='p', command_id='command.two',
            digest='sha256:' + 'a' * 64, receipt={'value': 'command.two'}, now_ms=1)
        durable = self.path.read_bytes()
        original = disk_journal_index.sqlite3.connect
        faults = []

        def fail_rebuild(*args, **kwargs):
            fault = _ConnectionFault(original(*args, **kwargs),
                execute_sql='INSERT INTO commands VALUES (?,?,?,?)')
            faults.append(fault)
            return fault

        with patch.object(disk_journal_index.sqlite3, 'connect', side_effect=fail_rebuild):
            with self.assertRaises(JournalError) as caught:
                self.lookup('command.two')
        self.assertEqual(len(faults), 1)
        self.assertTrue(faults[0].fired)
        self.assert_unknown(caught.exception)
        self.assertFalse(old_dir.exists())
        failed_index = self.journal._index_store
        self.assertIsNotNone(failed_index)
        failed_dir = failed_index._dir
        self.assertEqual(self.lookup('command.two')['receipt'], {'value': 'command.two'})
        self.assertEqual(self.lookup()['receipt'], {'value': 'command.one'})
        self.assertIsNot(self.journal._index_store, failed_index)
        self.assertIsNone(failed_index._db)
        self.assertFalse(failed_dir.exists())
        self.assertEqual(self.path.read_bytes(), durable)

    def test_cursor_close_failure_after_fsync_preserves_unknown_and_rebuilds(self):
        index = self.journal._index_store
        private_dir = index._dir
        fault = _ConnectionFault(index._db, close_sql='INSERT INTO commands')
        index._db = fault
        with self.assertRaises(JournalError) as caught:
            self.append()
        self.assertTrue(fault.fired)
        self.assert_unknown(caught.exception)
        durable = self.path.read_bytes()
        self.assertEqual(len(_records(self.path)), 1)
        self.assertEqual(self.lookup()['receipt'], {'value': 'command.one'})
        self.assertFalse(private_dir.exists())
        self.assertIsNone(index._db)
        self.assertTrue(self.append()['replayed'])
        self.assertEqual(self.path.read_bytes(), durable)

    def test_cursor_close_failure_on_lookup_invalidates_verified_generation(self):
        self.append()
        durable = self.path.read_bytes()
        index = self.journal._index_store
        private_dir = index._dir
        fault = _ConnectionFault(index._db, close_sql='SELECT c.value')
        index._db = fault
        with self.assertRaises(JournalError) as caught:
            self.lookup()
        self.assertTrue(fault.fired)
        self.assert_unknown(caught.exception)
        self.assertEqual(self.lookup()['receipt'], {'value': 'command.one'})
        self.assertIsNot(self.journal._index_store, index)
        self.assertFalse(private_dir.exists())
        self.assertIsNone(index._db)
        self.assertEqual(self.path.read_bytes(), durable)


class ReplayServiceIndexFaultTests(unittest.TestCase):
    def _constructor_fixture(self):
        temp = tempfile.TemporaryDirectory(prefix='hh-index-constructor-')
        self.addCleanup(temp.cleanup)
        backend = service_fixtures.FakePreparedPlay(Path(temp.name))
        return backend

    def _capture_journal(self, created, *, fail_close=False):
        original = service.Journal

        def construct(*args, **kwargs):
            journal = original(*args, **kwargs)
            index = journal._index_store
            created.append((journal, index, index._dir))
            self.addCleanup(_cleanup_journal, journal)
            if fail_close:
                index._db = _ConnectionFault(index._db, fail_close=True)
            return journal

        return construct

    def _assert_released(self, journal, index, private_dir):
        self.assertTrue(journal._cache_closed)
        self.assertIsNone(journal._index_store)
        self.assertIsNone(index._db)
        self.assertIsNone(index._dir)
        self.assertFalse(private_dir.exists())
        self.assertEqual(list(private_dir.parent.glob('.hh-index-*')), [])

    def test_uncertain_pending_admission_halts_and_never_starts_backend(self):
        fixture = service_fixtures.ReplayServiceTests()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        owner = fixture.owner
        index = owner._journal._index_store
        old_dir = index._dir
        fault = _ConnectionFault(index._db, execute_sql='COMMIT')
        index._db = fault
        request = fixture.request('command.first')
        with self.assertRaises(JournalError) as caught:
            owner.submit(request, **fixture.auth())
        self.assertTrue(fault.fired)
        self.assertEqual(caught.exception.code, 'JOURNAL_INDEX_UNAVAILABLE')
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertEqual(fixture.backend.starts, 0)
        self.assertGreaterEqual(fixture.backend.stops, 1)
        self.assertTrue(owner.sessions.status()['stopped'])
        self.assertFalse(owner.sessions.status()['draining'])
        self.assertNotIn('command.first', owner._jobs)
        self.assertIn('command.first', owner._uncertain)
        first_rows = [row for row in _records(owner._journal.path)
                      if row.get('command_id') == 'command.first']
        self.assertEqual(sum(row['status'] == 'ACCEPTED_PENDING' for row in first_rows), 1)
        self.assertLessEqual(len(first_rows), 2)
        self.assertTrue(all(row['status'] == 'UNKNOWN' for row in first_rows[1:]))
        receipt = fixture.lookup('command.first')
        self.assertEqual(receipt['status'], 'UNKNOWN')
        self.assertEqual(receipt['command_id'], 'command.first')
        self.assertFalse(receipt['postconditions']['public_ack'])
        durable = owner._journal.path.read_bytes()
        for denied in (request, fixture.request('command.next')):
            with self.assertRaises(SafetyViolation) as blocked:
                owner.submit(denied, **fixture.auth())
            self.assertEqual(blocked.exception.code, 'REPLAY_STOPPED')
        self.assertEqual(fixture.backend.starts, 0)
        self.assertEqual(owner._journal.path.read_bytes(), durable)
        self.assertEqual(fixture.lookup('command.first'), receipt)
        self.assertFalse(old_dir.exists())
        current_index = owner._journal._index_store
        current_dir = current_index._dir
        owner.close()
        self._assert_released(owner._journal, current_index, current_dir)
        self.assertEqual(fixture.backend.starts, 0)

    def test_watchdog_start_failure_closes_allocated_journal(self):
        backend = self._constructor_fixture()
        created = []
        failure = RuntimeError('injected watchdog start failure')
        with patch.object(service, 'PreparedPlay', service_fixtures.FakePreparedPlay), \
                patch.object(service, 'Journal', side_effect=self._capture_journal(created)), \
                patch.object(service.threading.Thread, 'start', side_effect=failure):
            with self.assertRaises(RuntimeError) as caught:
                service.ReplayService(backend)
        self.assertIs(caught.exception, failure)
        self.assertEqual(len(created), 1)
        self._assert_released(*created[0])
        self.assertEqual(backend.starts, 0)
        self.assertGreaterEqual(backend.closes, 1)
        self.assertIsNone(getattr(caught.exception, 'cleanup_owner', None))

    def test_watchdog_start_and_close_failure_return_retryable_service_owner(self):
        backend = self._constructor_fixture()
        created = []
        failure = RuntimeError('injected watchdog start failure')
        with patch.object(service, 'PreparedPlay', service_fixtures.FakePreparedPlay), \
                patch.object(service, 'Journal', side_effect=self._capture_journal(created, fail_close=True)), \
                patch.object(service.threading.Thread, 'start', side_effect=failure):
            with self.assertRaises(RuntimeError) as caught:
                service.ReplayService(backend)
        self.assertIs(caught.exception, failure)
        journal, index, private_dir = created[0]
        owner = getattr(caught.exception, 'cleanup_owner', None)
        self.assertIsInstance(owner, service.ReplayService)
        self.addCleanup(owner.close)
        self.assertIs(owner._journal, journal)
        self.assertIs(journal._index_store, index)
        self.assertIsNotNone(index._db)
        self.assertTrue(private_dir.exists())
        self.assertTrue(owner.sessions.status()['stopped'])
        self.assertEqual(backend.starts, 0)
        owner.close()
        self._assert_released(journal, index, private_dir)
        self.assertEqual(backend.starts, 0)

    def test_journal_constructor_cleanup_owner_survives_service_cleanup_failure(self):
        backend = self._constructor_fixture()
        original_connect = disk_journal_index.sqlite3.connect
        original_close = disk_journal_index.DiskJournalIndex.close
        retained = []
        close_calls = []

        def fail_initialization(*args, **kwargs):
            return _ConnectionFault(original_connect(*args, **kwargs),
                execute_sql='INSERT INTO meta VALUES (?,?)')

        def hold_close(index):
            if not retained:
                retained.append((index, index._dir))
                self.addCleanup(original_close, index)
            close_calls.append(index)
            # Hold ownership through the disk constructor, journal constructor,
            # and service constructor cleanup. The explicit retry is then real.
            if len(close_calls) <= 3:
                index._closing = True
                error = disk_journal_index.DiskIndexError('INDEX_CLOSE_FAILED')
                error.cleanup_owner = index
                raise error
            return original_close(index)

        with patch.object(service, 'PreparedPlay', service_fixtures.FakePreparedPlay), \
                patch.object(disk_journal_index.sqlite3, 'connect', side_effect=fail_initialization), \
                patch.object(disk_journal_index.DiskJournalIndex, 'close', hold_close):
            with self.assertRaises(JournalError) as caught:
                service.ReplayService(backend)
        self.assertEqual(caught.exception.code, 'JOURNAL_INDEX_UNAVAILABLE')
        self.assertTrue(caught.exception.outcome_unknown)
        owner = getattr(caught.exception, 'cleanup_owner', None)
        self.assertIsInstance(owner, service.ReplayService)
        self.addCleanup(owner.close)
        index, private_dir = retained[0]
        self.assertEqual(close_calls, [index, index, index])
        journal = owner._journal
        self.assertIs(journal._index_store, index)
        self.assertIsNotNone(index._db)
        self.assertTrue(private_dir.exists())
        self.assertTrue(owner.sessions.status()['stopped'])
        self.assertEqual(backend.starts, 0)
        owner.close()
        self._assert_released(journal, index, private_dir)
        self.assertEqual(backend.starts, 0)


class BenchmarkIndexFaultTests(unittest.TestCase):
    def _prepare(self):
        temp = tempfile.TemporaryDirectory(prefix='hh-index-http-')
        self.addCleanup(temp.cleanup)
        observer = command_fixtures.SyntheticObserver()
        producer = command_fixtures.benchmark.CommandProducer(
            Path(temp.name) / 'commands', 'test.index.fault', observer=observer)
        self.addCleanup(producer.close)
        lease = producer._connect_batch()
        request = producer.client.request('command.index.fault', value=1, lease=lease)
        return producer, request, lease

    def _assert_halted_and_reconciled(self, producer, request, lease):
        reply = producer.client.submit(request)
        self.assertIs(reply.status, Status.UNKNOWN)
        self.assertEqual(reply.command_id, request.command_id)
        self.assertEqual(reply.code, 'JOURNAL_INDEX_UNAVAILABLE')
        self.assertFalse(reply.postconditions['accepting_work'])
        self.assertTrue(producer.host._stopped.is_set())
        self.assertEqual(producer.host.fixture.effect_count, 0)
        lookup = producer.client.lookup(request.command_id)
        self.assertIs(lookup.status, Status.UNKNOWN)
        self.assertEqual(lookup.command_id, request.command_id)
        self.assertEqual(lookup.code, 'RECOVERY_REQUIRED')
        self.assertEqual(lookup.postconditions['request_digest'], request.digest)
        durable = producer.journal.path.read_bytes()
        pending = [row for row in _records(producer.journal.path)
                   if row.get('command_id') == request.command_id]
        self.assertEqual([row['status'] for row in pending], ['ACCEPTED_PENDING'])
        self.assertEqual(producer.client.submit(request), lookup)
        next_request = producer.client.request('command.index.next', value=2, lease=lease)
        rejected = producer.client.submit(next_request)
        self.assertIs(rejected.status, Status.REJECTED)
        self.assertEqual(rejected.code, 'HOST_STOPPED')
        self.assertEqual(producer.host.fixture.effect_count, 0)
        self.assertEqual(producer.journal.path.read_bytes(), durable)
        index = producer.journal._index_store
        private_dir = index._dir
        producer.close()
        self.assertTrue(producer.closed)
        self.assertTrue(producer.observer.closed)
        self.assertIsNone(producer.journal._index_store)
        self.assertIsNone(index._db)
        self.assertFalse(private_dir.exists())
        self.assertEqual(list(private_dir.parent.glob('.hh-index-*')), [])
        self.assertEqual(producer.journal.path.read_bytes(), durable)

    def test_actual_command_http_commit_failure_stops_admission(self):
        producer, request, lease = self._prepare()
        index = producer.journal._index_store
        old_dir = index._dir
        fault = _ConnectionFault(index._db, execute_sql='COMMIT')
        index._db = fault
        self._assert_halted_and_reconciled(producer, request, lease)
        self.assertTrue(fault.fired)
        self.assertIsNone(index._db)
        self.assertFalse(old_dir.exists())

    def test_actual_command_http_cursor_close_failure_stops_admission(self):
        producer, request, lease = self._prepare()
        index = producer.journal._index_store
        old_dir = index._dir
        fault = _ConnectionFault(index._db, close_sql='INSERT INTO commands')
        index._db = fault
        self._assert_halted_and_reconciled(producer, request, lease)
        self.assertTrue(fault.fired)
        self.assertIsNone(index._db)
        self.assertFalse(old_dir.exists())
