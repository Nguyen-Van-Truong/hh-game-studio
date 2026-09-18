"""Real Windows handles, crash cuts and retained-owner recovery for event log."""
from __future__ import annotations

import dataclasses
from contextlib import contextmanager, ExitStack
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock
import uuid
import weakref

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from host.core.limits import SafetyViolation
from host.core.private_store import PrivateStoreError
from host.core.private_events import (PrivateEventLog, EventLogError, EventHead, EventBinding,
                                      MAX_EVENT_BYTES, pending_event_cleanup)
from host.core.safe_open import FileIdentity, capabilities


@unittest.skipUnless(os.name == 'nt', 'Windows NTFS retained-handle fixture required')
class PrivateEventTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gt02-events-test-')
        self.base = Path(self.temp.name).resolve()
        self.log = PrivateEventLog.create(self.base)

    def tearDown(self):
        self.log.close()
        self.temp.cleanup()

    def test_custody_rejects_callbacks_and_subclasses_without_writes(self):
        from host.core.custody import WitnessCustody

        class DerivedCustody(WitnessCustody):
            pass

        before = self.log.binding()
        for value in (None, object(), lambda binding: None, DerivedCustody.__new__(DerivedCustody)):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaisesRegex(EventLogError, 'EVENT_CUSTODY_REQUIRED'):
                    self.log.bind_custody(value)
                self.assertEqual(self.log.binding(), before)

    def test_bound_append_persists_real_custody_and_reopen_preserves_identity(self):
        from host.core.custody import WitnessCustody, decode_record

        with self._custody() as (registry, custody):
            before = registry.read()
            with mock.patch.object(custody, 'persist_binding', wraps=custody.persist_binding) as persist:
                self.log.bind_custody(custody)
                persist.assert_not_called()
                self.assertEqual(registry.read(), before)
                head = self.log.append({'kind': 'INTENT'}, custody.binding.witnessed)
                persist.assert_called_once()
            self.assertEqual(custody.binding.witnessed, head)
            self.assertEqual(decode_record(registry.read())['events']['binding']['witnessed'], dataclasses.asdict(head))
            with self.assertRaisesRegex(EventLogError, 'EVENT_CUSTODY_ALREADY_BOUND'):
                self.log.bind_custody(custody)
            root, binding = self.log.root, custody.binding
            self.log.close()
            # Read the actual registry again; mutable stream size at reopen
            # must not be confused with its stable volume/FileID identity.
            reopened_custody = WitnessCustody(registry, storage_id=registry.local_id, project_id='events-test')
            self.log = PrivateEventLog.reopen(root, reopened_custody.binding)
            self.assertNotEqual(binding.stream.size, self.log.binding().stream.size)
            self.log.bind_custody(reopened_custody)
            next_head = self.log.append({'kind': 'NEXT'}, head)
            self.assertEqual(reopened_custody.binding.witnessed, next_head)

    def test_stale_or_wrong_custody_cannot_attach_or_advance_itself(self):
        with self._custody() as (registry, custody):
            raw = registry.read()
            # An unrelated valid stream is not authority for this log.
            with PrivateEventLog.create(self.base) as other:
                with self.assertRaisesRegex(EventLogError, 'EVENT_CUSTODY_BINDING_MISMATCH'):
                    other.bind_custody(custody)
            self.log.append({'kind': 'AHEAD'}, self.log.binding().witnessed)
            with mock.patch.object(custody, 'persist_binding', side_effect=AssertionError('bind must not advance')):
                with self.assertRaisesRegex(EventLogError, 'EVENT_CUSTODY_BINDING_MISMATCH'):
                    self.log.bind_custody(custody)
            self.assertEqual(registry.read(), raw)
            self.assertEqual(custody.binding.witnessed.sequence, 1)
            self.assertEqual(self.log.binding().witnessed.sequence, 2)

    def test_custody_failure_after_event_flush_is_unknown_and_no_automatic_rebind(self):
        with self._custody() as (registry, custody):
            self.log.bind_custody(custody)
            saved, raw = custody.binding, registry.read()
            flushes, flush = [], self.log._api.flush
            def recorded_flush(handle):
                flush(handle)
                flushes.append(handle)
            def fail_custody(binding):
                # This callback is a test-only fault injection into the exact
                # custody type, not a callback accepted by the product API.
                self.assertGreaterEqual(flushes.count(self.log._handle), 3)
                self.assertEqual(self.log._index[-1][2], binding.witnessed)
                self.assertEqual(self.log._inspect().size, binding.witnessed.size)
                raise RuntimeError('injected unexpected custody failure')
            with mock.patch.object(self.log._api, 'flush', side_effect=recorded_flush), \
                 mock.patch.object(custody, 'persist_binding', side_effect=fail_custody):
                with self.assertRaisesRegex(EventLogError, 'EVENT_APPEND_UNCERTAIN') as caught:
                    self.log.append({'kind': 'UNACKNOWLEDGED'}, saved.witnessed)
            self.assertTrue(caught.exception.outcome_unknown)
            self.assertEqual(registry.read(), raw)
            with self.assertRaisesRegex(EventLogError, 'EVENT_RECOVERY_REQUIRED'):
                self.log.append({'kind': 'NO_RETRY'}, saved.witnessed)
            root = self.log.root
            self.log.close()
            retained = (root / '.events').read_bytes()
            self.log = PrivateEventLog.reopen(root, saved)
            self.assertEqual(self.log.binding().witnessed.sequence, 2)
            self.assertEqual(json.loads(self.log.read(2).event), {'kind': 'UNACKNOWLEDGED'})
            with self.assertRaisesRegex(EventLogError, 'EVENT_CUSTODY_BINDING_MISMATCH'):
                self.log.bind_custody(custody)
            self.log.close()
            self.assertEqual((root / '.events').read_bytes(), retained)
            self.assertEqual(registry.read(), raw)

    def test_custody_barrier_retains_log_lock_until_acknowledgment(self):
        with self._custody() as (_, custody):
            self.log.bind_custody(custody)
            parent = custody.binding.witnessed
            entered, release, appended, read_done = (threading.Event() for _ in range(4))
            persist, results, errors = custody.persist_binding, [], []
            def delayed(binding):
                entered.set()
                if not release.wait(5):
                    raise RuntimeError('test custody wait timed out')
                persist(binding)
            def append():
                try:
                    results.append(self.log.append({'kind': 'INTENT'}, parent))
                    appended.set()
                except BaseException as exc:
                    errors.append(type(exc).__name__)
            def read():
                try:
                    results.append(self.log.binding().witnessed)
                except BaseException as exc:
                    errors.append(type(exc).__name__)
                finally:
                    read_done.set()
            writer = threading.Thread(target=append, daemon=True)
            reader = threading.Thread(target=read, daemon=True)
            with mock.patch.object(custody, 'persist_binding', side_effect=delayed):
                writer.start()
                try:
                    self.assertTrue(entered.wait(5))
                    reader.start()
                    self.assertFalse(read_done.wait(.05))
                    self.assertFalse(appended.is_set())
                    self.assertEqual(custody.binding.witnessed, parent)
                finally:
                    release.set()
                    writer.join(5)
                    if reader.ident is not None:
                        reader.join(5)
            self.assertFalse(writer.is_alive() or reader.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0], results[1])
            self.assertEqual(custody.binding.witnessed, results[0])

    def test_native_custody_flush_failure_prevents_append_ack(self):
        from host.core.custody import CustodyError
        from host.core.custody_registry import CustodyError as RegistryError

        with self._custody() as (registry, custody):
            self.log.bind_custody(custody)
            saved = custody.binding
            flush, calls = registry._api.flush, 0
            def fail_after_state_set(handle):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise RegistryError('CUSTODY_FLUSH_FAILED')
                flush(handle)
            with mock.patch.object(registry._api, 'flush', side_effect=fail_after_state_set):
                with self.assertRaisesRegex(EventLogError, 'EVENT_APPEND_UNCERTAIN') as caught:
                    self.log.append({'kind': 'CUSTODY_FLUSH_UNKNOWN'}, saved.witnessed)
            self.assertTrue(caught.exception.outcome_unknown)
            self.assertEqual(calls, 2)
            with self.assertRaisesRegex(CustodyError, 'CUSTODY_RECONCILIATION_REQUIRED'):
                custody.binding
            with self.assertRaisesRegex(EventLogError, 'EVENT_RECOVERY_REQUIRED'):
                self.log.binding()
            root = self.log.root
            self.log.close()
            with PrivateEventLog.reopen(root, saved) as reopened:
                self.assertEqual(json.loads(reopened.read(2).event), {'kind': 'CUSTODY_FLUSH_UNKNOWN'})

    def test_actual_exit_after_event_flush_before_custody_keeps_ahead_hold(self):
        from host.core.custody import WitnessCustody
        from host.core.custody_registry import RegistryCustody

        with self._custody() as (registry, custody):
            saved, root = custody.binding, self.log.root
            config = {'root': str(root), 'binding': dataclasses.asdict(saved), 'local_id': registry.local_id}
            self.log.close()
            registry.close()
            script = self._imports() + """
import os
from host.core.custody import WitnessCustody
from host.core.custody_registry import RegistryCustody
registry = RegistryCustody.reopen(c['local_id'])
custody = WitnessCustody(registry, storage_id=c['local_id'], project_id='events-test')
log = PrivateEventLog.reopen(c['root'], custody.binding)
log.bind_custody(custody)
def cut(new_binding):
    assert log._index[-1][2] == new_binding.witnessed
    print('EVENT_CUSTODY_CUT_AFTER_FLUSH', flush=True)
    os._exit(91)
custody.persist_binding = cut
log.append({'kind':'CUSTODY_CRASH_UNACKNOWLEDGED'}, custody.binding.witnessed)
raise AssertionError('cut was not reached')
"""
            result = self._child(script, config)
            self.assertEqual(result.returncode, 91, result.stderr)
            self.assertEqual(result.stdout.strip(), 'EVENT_CUSTODY_CUT_AFTER_FLUSH')
            self.assertEqual(result.stderr, '')
            with RegistryCustody.reopen(config['local_id']) as recovered_registry:
                recovered = WitnessCustody(recovered_registry, storage_id=config['local_id'], project_id='events-test')
                self.assertEqual(recovered.binding.witnessed, saved.witnessed)
                self.log = PrivateEventLog.reopen(root, recovered.binding)
                self.assertEqual(self.log.binding().witnessed.sequence, 2)
                self.assertEqual(json.loads(self.log.read(2).event), {'kind': 'CUSTODY_CRASH_UNACKNOWLEDGED'})
                with self.assertRaisesRegex(EventLogError, 'EVENT_CUSTODY_BINDING_MISMATCH'):
                    self.log.bind_custody(recovered)
            print('HH_GT02_EVENT_CUSTODY_CUT ' + json.dumps({
                'host_exit': result.returncode, 'custody_sequence': saved.witnessed.sequence,
                'reopened_sequence': self.log.binding().witnessed.sequence, 'automatic_bind': False}), flush=True)

    def test_failed_close_retains_custody_owner_until_real_cleanup(self):
        from host.core.private_events import _CUSTODY_OWNERS

        with self._custody() as (_, custody):
            self.log.bind_custody(custody)
            native_close, handle = self.log._api.close, self.log._handle
            def fail_stream(value):
                if value == handle:
                    raise PrivateStoreError('PRIVATE_CLOSE_FAILED')
                native_close(value)
            with mock.patch.object(self.log._api, 'close', side_effect=fail_stream):
                with self.assertRaisesRegex(EventLogError, 'EVENT_CLOSE_UNCERTAIN'):
                    self.log.close()
            self.assertIs(_CUSTODY_OWNERS.get(id(custody)), self.log)
            self.log.close()
            self.assertNotIn(id(custody), _CUSTODY_OWNERS)

    def test_genesis_append_immutable_records_and_disk_index(self):
        initial = self.log.binding()
        self.assertEqual(initial.witnessed.sequence, 1)
        event = {'kind': 'INTENT', 'text': 'a\u0085b\u2028c\nệ'}
        head = self.log.append(event, initial.witnessed)
        event['text'] = 'changed-by-caller'
        record = self.log.read(2)
        self.assertEqual(record.head, head)
        self.assertEqual(json.loads(record.event)['text'], 'a\u0085b\u2028c\nệ')
        self.assertNotIn(b'changed-by-caller', record.event)
        self.assertEqual(len(self.log._index), 2)
        self.assertTrue(all(type(row[0]) is int and type(row[1]) is int for row in self.log._index))
        self.assertFalse(capabilities()['safe_write'])

    def test_same_parent_concurrent_append_has_one_winner(self):
        parent = self.log.binding().witnessed
        barrier, results = threading.Barrier(3), []
        def work(number):
            barrier.wait(timeout=5)
            try:
                results.append(self.log.append({'candidate': number}, parent))
            except EventLogError as exc:
                results.append(exc.code)
        threads = [threading.Thread(target=work, args=(n,), daemon=True) for n in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait(timeout=5)
        for thread in threads:
            thread.join(timeout=5)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(sum(type(item) is EventHead for item in results), 1)
        self.assertEqual(results.count('EVENT_HEAD_CONFLICT'), 1)
        self.assertEqual(self.log.binding().witnessed.sequence, 2)

    def test_invalid_and_reserved_capacity_refuse_before_write(self):
        head = self.log.binding().witnessed
        with mock.patch.object(self.log, '_write_at', wraps=self.log._write_at) as writer:
            for value in ([], {'x': 'a' * MAX_EVENT_BYTES}, {'x': float('nan')}):
                with self.subTest(value_type=type(value).__name__), self.assertRaises(SafetyViolation):
                    self.log.append(value, head)
            with mock.patch('host.core.private_events.MAX_RECORDS', 3):
                with self.assertRaisesRegex(EventLogError, 'EVENT_CAPACITY'):
                    self.log.append({'kind': 'INTENT'}, head, reserve_records=2)
                self.log.append({'kind': 'INTENT'}, head, reserve_records=1)
            self.assertEqual(writer.call_count, 1)
        self.assertEqual(self.log.binding().witnessed.sequence, 2)

    def test_second_process_cannot_acquire_guard(self):
        config = self._config(self.log)
        script = self._imports() + """
try:
    log = PrivateEventLog.reopen(c['root'], binding)
except EventLogError as exc:
    assert exc.code == 'EVENT_RECOVERY_REQUIRED' and exc.outcome_unknown
    print('SECOND_WRITER_DENIED')
else:
    log.close()
    raise AssertionError('second writer admitted')
"""
        result = self._child(script, config)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'SECOND_WRITER_DENIED')

    def test_fresh_process_reopen_reads_then_appends_from_pinned_head(self):
        self.log.append({'kind': 'INTENT', 'id': 'one'}, self.log.binding().witnessed)
        config = self._config(self.log)
        self.log.close()
        script = self._imports() + """
with PrivateEventLog.reopen(c['root'], binding) as log:
    assert json.loads(log.read(2).event) == {'kind':'INTENT','id':'one'}
    head = log.append({'kind':'SELECT','id':'one'}, log.binding().witnessed)
    assert head.sequence == 3
print('FRESH_PROCESS_CHAIN_OK')
"""
        result = self._child(script, config)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'FRESH_PROCESS_CHAIN_OK')
        with PrivateEventLog.reopen(config['root'], self._binding(config)) as reopened:
            self.assertEqual(reopened.binding().witnessed.sequence, 3)

    def test_write_and_flush_failures_preserve_history_and_uncertainty(self):
        for mode in ('before', 'partial', 'full_then_error', 'flush_before', 'flush_after'):
            with self.subTest(mode=mode):
                log = PrivateEventLog.create(self.base)
                binding, path = log.binding(), log.root / '.events'
                write, flush = log._api.write, log._api.flush
                calls = 0
                def bad_write(handle, data):
                    if mode == 'partial':
                        write(handle, data[:7])
                    elif mode == 'full_then_error':
                        write(handle, data)
                    raise PrivateStoreError('PRIVATE_WRITE_FAILED')
                def bad_flush(handle):
                    nonlocal calls
                    calls += 1
                    # The first barrier validates preexisting history; second
                    # follows the actual newly appended record.
                    if calls == 2:
                        if mode == 'flush_after':
                            flush(handle)
                        raise PrivateStoreError('PRIVATE_FLUSH_FAILED')
                    flush(handle)
                try:
                    target, failure = ('flush', bad_flush) if mode.startswith('flush') else ('write', bad_write)
                    with mock.patch.object(log._api, target, side_effect=failure):
                        with self.assertRaisesRegex(EventLogError, 'EVENT_APPEND_UNCERTAIN') as raised:
                            log.append({'kind': 'INTENT'}, binding.witnessed)
                    self.assertTrue(raised.exception.outcome_unknown)
                    with self.assertRaisesRegex(EventLogError, 'EVENT_RECOVERY_REQUIRED'):
                        log.binding()
                finally:
                    log.close()
                retained = path.read_bytes()
                if mode == 'partial':
                    with self.assertRaisesRegex(EventLogError, 'EVENT_RECOVERY_REQUIRED'):
                        PrivateEventLog.reopen(log.root, binding)
                    self.assertEqual(path.read_bytes(), retained)
                else:
                    with PrivateEventLog.reopen(log.root, binding) as reopened:
                        self.assertEqual(reopened.binding().witnessed.sequence, 1 if mode == 'before' else 2)

    def test_reload_barrier_failure_never_exposes_page_cache(self):
        self.log.append({'kind': 'INTENT'}, self.log.binding().witnessed)
        config = self._config(self.log)
        self.log.close()
        script = self._imports() + """
from unittest import mock
from host.core.private_store import _StoreApi, PrivateStoreError
with mock.patch.object(_StoreApi, 'flush', side_effect=PrivateStoreError('PRIVATE_FLUSH_FAILED')):
    try:
        PrivateEventLog.reopen(c['root'], binding)
    except EventLogError as exc:
        assert exc.outcome_unknown and exc.code == 'EVENT_RECOVERY_REQUIRED'
        assert not pending_event_cleanup()
    else:
        raise AssertionError('page cache exposed without durability barrier')
print('RELOAD_BARRIER_DENIED')
"""
        result = self._child(script, config)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'RELOAD_BARRIER_DENIED')

    def test_process_exit_at_write_and_flush_cuts_reconciles_complete_chain_only(self):
        for mode in ('before_write', 'partial_write', 'after_write', 'after_flush'):
            with self.subTest(mode=mode):
                log = PrivateEventLog.create(self.base)
                config = self._config(log)
                config['cut'] = mode
                log.close()
                script = self._imports() + """
import os
log = PrivateEventLog.reopen(c['root'], binding)
write, flush = log._write_at, log._api.flush
calls = 0
def cut_write(offset, frame):
    if c['cut'] == 'before_write':
        os._exit(73)
    if c['cut'] == 'partial_write':
        write(offset, frame[:7])
        os._exit(73)
    write(offset, frame)
    if c['cut'] == 'after_write':
        os._exit(73)
def cut_flush(handle):
    global calls
    calls += 1
    flush(handle)
    if calls == 2 and c['cut'] == 'after_flush':
        os._exit(73)
log._write_at, log._api.flush = cut_write, cut_flush
print('EVENT_CUT_ARMED', flush=True)
log.append({'kind':'INTENT','id':'cut'}, binding.witnessed)
raise AssertionError('cut not reached')
"""
                result = self._child(script, config)
                self.assertEqual(result.returncode, 73, result.stderr)
                self.assertEqual(result.stdout.strip(), 'EVENT_CUT_ARMED')
                self.assertEqual(result.stderr, '')
                path = Path(config['root']) / '.events'
                retained = path.read_bytes()
                if mode == 'partial_write':
                    with self.assertRaisesRegex(EventLogError, 'EVENT_RECOVERY_REQUIRED'):
                        PrivateEventLog.reopen(config['root'], self._binding(config))
                else:
                    with PrivateEventLog.reopen(config['root'], self._binding(config)) as reopened:
                        self.assertEqual(reopened.binding().witnessed.sequence, 1 if mode == 'before_write' else 2)
                self.assertEqual(path.read_bytes(), retained)

    def test_truncated_tampered_and_whole_suffix_loss_require_recovery(self):
        initial = self.log.binding()
        self.log.append({'kind': 'SELECT'}, initial.witnessed)
        latest = self.log.binding()
        path, root = self.log.root / '.events', self.log.root
        self.log.close()
        original = path.read_bytes()
        variants = [original[:-1], original[:initial.witnessed.size],
                    original[:10] + bytes([original[10] ^ 1]) + original[11:], b'']
        for damaged in variants:
            with self.subTest(size=len(damaged)):
                path.write_bytes(damaged)
                with self.assertRaisesRegex(EventLogError, 'EVENT_RECOVERY_REQUIRED'):
                    PrivateEventLog.reopen(root, latest)
                self.assertEqual(path.read_bytes(), damaged)
        # Honest limit: an earlier witness does not detect removal of a later,
        # whole valid suffix. Durable receipt/high-water custody is caller work.
        path.write_bytes(original[:initial.witnessed.size])
        with PrivateEventLog.reopen(root, initial) as reopened:
            self.assertEqual(reopened.binding().witnessed.sequence, 1)
        path.write_bytes(original)

    def test_record_order_and_noncanonical_checksums_do_not_authorize_history(self):
        self.log.append({'kind': 'A'}, self.log.binding().witnessed)
        self.log.append({'kind': 'B'}, self.log.binding().witnessed)
        binding, root = self.log.binding(), self.log.root
        boundaries = [0] + [row[2].size for row in self.log._index]
        self.log.close()
        path = root / '.events'
        original = path.read_bytes()
        records = [original[a:b] for a, b in zip(boundaries, boundaries[1:])]
        path.write_bytes(records[0] + records[2] + records[1])
        with self.assertRaisesRegex(EventLogError, 'EVENT_RECOVERY_REQUIRED'):
            PrivateEventLog.reopen(root, binding)
        # Recomputed hash still must obey canonical encoding / strict sequence.
        size = int.from_bytes(records[1][:4], 'little')
        body = records[1][4:4+size] + b' '
        altered = len(body).to_bytes(4, 'little') + body + hashlib.sha256(body).digest()
        path.write_bytes(records[0] + altered + records[2])
        with self.assertRaisesRegex(EventLogError, 'EVENT_RECOVERY_REQUIRED'):
            PrivateEventLog.reopen(root, binding)
        path.write_bytes(original)

    def test_live_alias_attempt_and_reopen_alias_or_extra_entry_never_authorize_write(self):
        binding = self.log.binding()
        outside = self.base / 'outside-hardlink'
        try:
            os.link(self.log.root / '.events', outside)
        except OSError as exc:
            # This tested access/flag combination denies the live link with
            # sharing violation. Do not infer all Windows handles do so.
            self.assertEqual(exc.winerror, 32)
        else:
            with mock.patch.object(self.log, '_write_at', wraps=self.log._write_at) as writer:
                with self.assertRaisesRegex(EventLogError, 'EVENT_RECOVERY_REQUIRED'):
                    self.log.append({'kind': 'bad'}, binding.witnessed)
                writer.assert_not_called()
        self.log.close()
        original = (self.log.root / '.events').read_bytes()
        if not outside.exists():
            os.link(self.log.root / '.events', outside)
        with self.assertRaisesRegex(EventLogError, 'EVENT_RECOVERY_REQUIRED'):
            PrivateEventLog.reopen(self.log.root, binding)
        self.assertEqual(outside.read_bytes(), original)
        outside.unlink()
        with PrivateEventLog.reopen(self.log.root, binding) as reopened:
            extra = reopened.root / 'unexpected'
            extra.write_bytes(b'foreign')
            with self.assertRaisesRegex(EventLogError, 'EVENT_RECOVERY_REQUIRED'):
                reopened.binding()

    def test_missing_or_wrong_stream_identity_never_autocreates(self):
        binding, root = self.log.binding(), self.log.root
        self.log.close()
        path = root / '.events'
        original = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(EventLogError, 'EVENT_RECOVERY_REQUIRED'):
            PrivateEventLog.reopen(root, binding)
        self.assertFalse(path.exists())
        path.write_bytes(original)
        with self.assertRaisesRegex(EventLogError, 'EVENT_RECOVERY_REQUIRED'):
            PrivateEventLog.reopen(root, binding)

    def test_failed_close_retains_stream_and_ancestors_for_exact_retry(self):
        handle, close = self.log._handle, self.log._api.close
        def fail_stream(value):
            if value == handle:
                raise PrivateStoreError('PRIVATE_CLOSE_FAILED')
            close(value)
        with mock.patch.object(self.log._api, 'close', side_effect=fail_stream):
            with self.assertRaisesRegex(EventLogError, 'EVENT_CLOSE_UNCERTAIN'):
                self.log.close()
        self.assertIn(self.log, pending_event_cleanup())
        self.assertIn(handle, self.log._api._owned_handles)
        self.assertFalse(self.log._store._closed)
        self.log.close()
        self.assertNotIn(self.log, pending_event_cleanup())
        self.assertEqual(self.log._api._owned_handles, set())

    def test_registry_retains_dropped_caller_and_enforces_owner_cap(self):
        other = PrivateEventLog.create(self.base)
        reference = weakref.ref(other)
        del other
        gc.collect()
        self.assertIsNotNone(reference())
        with mock.patch('host.core.private_events.MAX_OPEN_LOGS', len(pending_event_cleanup())):
            before = set(self.base.iterdir())
            with self.assertRaisesRegex(EventLogError, 'EVENT_OWNER_LIMIT'):
                PrivateEventLog.create(self.base)
            self.assertEqual(set(self.base.iterdir()), before)
        reference().close()
        gc.collect()
        self.assertIsNone(reference())

    def test_constructor_write_and_close_failure_keep_cleanup_owner(self):
        from host.core.private_store import _StoreApi
        original_write, original_close = _StoreApi.write, _StoreApi.close
        failed = []
        def write(api, handle, data):
            failed.append(handle)
            original_write(api, handle, data[:7])
            raise PrivateStoreError('PRIVATE_WRITE_FAILED')
        def close(api, handle):
            if handle in failed:
                raise PrivateStoreError('PRIVATE_CLOSE_FAILED')
            original_close(api, handle)
        with mock.patch.object(_StoreApi, 'write', write), mock.patch.object(_StoreApi, 'close', close):
            with self.assertRaisesRegex(EventLogError, 'EVENT_INIT_CLEANUP_UNCERTAIN') as caught:
                PrivateEventLog.create(self.base)
        owner = caught.exception.cleanup_owner
        self.assertIn(owner, pending_event_cleanup())
        self.assertFalse(owner._store._closed)
        self.assertIn(owner._handle, owner._api._owned_handles)
        owner.close()
        self.assertNotIn(owner, pending_event_cleanup())
        self.assertEqual((owner.root / '.events').stat().st_size, 7)

    def test_api_constructor_token_close_failure_transfers_to_event_cleanup_owner(self):
        import ctypes as C
        from ctypes import wintypes as W
        from host.core.private_store import _StoreApi

        original_close, retained = _StoreApi.close, {}
        before = set(self.base.iterdir())
        def refuse_token(api, handle):
            if not retained:
                # The first _StoreApi.close occurs on the actual process
                # token in _owner_sid, before a blob-store root is minted.
                retained.update(api=api, handle=handle)
            if api is retained['api'] and handle == retained['handle']:
                raise PrivateStoreError('PRIVATE_CLOSE_FAILED')
            original_close(api, handle)
        owner = None
        try:
            with mock.patch.object(_StoreApi, 'close', refuse_token):
                with self.assertRaisesRegex(EventLogError, 'EVENT_INIT_CLEANUP_UNCERTAIN') as caught:
                    PrivateEventLog.create(self.base)
                owner = caught.exception.cleanup_owner
                self.assertTrue(caught.exception.outcome_unknown)
                self.assertIsNone(owner._store)
                self.assertIs(owner._init_cleanup_api, retained['api'])
                self.assertIn(owner, pending_event_cleanup())
                with self.assertRaisesRegex(EventLogError, 'EVENT_CLOSE_UNCERTAIN'):
                    owner.close()
                self.assertIn(owner, pending_event_cleanup())
                self.assertIn(retained['handle'], retained['api']._owned_handles)
                info = retained['api'].dll.GetHandleInformation
                info.argtypes, info.restype = [W.HANDLE, C.POINTER(W.DWORD)], W.BOOL
                flags = W.DWORD()
                self.assertTrue(info(retained['handle'], C.byref(flags)))
                with mock.patch('host.core.private_events.MAX_OPEN_LOGS', len(pending_event_cleanup())):
                    with self.assertRaisesRegex(EventLogError, 'EVENT_OWNER_LIMIT'):
                        PrivateEventLog.create(self.base)
            # Only the top-level cleanup owner is needed after native refusal
            # ends. No cause-chain lookup or direct API cleanup is required.
            owner.close()
            self.assertIsNone(owner._init_cleanup_api)
            self.assertNotIn(owner, pending_event_cleanup())
            self.assertEqual(retained['api']._owned_handles, set())
            self.assertFalse(info(retained['handle'], C.byref(flags)))
            self.assertEqual(C.get_last_error(), 6)  # ERROR_INVALID_HANDLE
            self.assertEqual(set(self.base.iterdir()), before)
        finally:
            # Preserve clean fixtures even when a future regression trips an
            # assertion before transfer or after partial cleanup.
            if owner is not None:
                owner.close()
            if retained:
                retained['api'].close_owned()

    def test_post_append_readback_failure_quarantines_complete_record(self):
        binding = self.log.binding()
        read = self.log._read_at
        def altered(offset, size):
            data = read(offset, size)
            # Full-frame verification after successful append/scan, not parser.
            if offset == binding.witnessed.size and size > 36 and data[:1] != b'{':
                return data[:-1] + bytes([data[-1] ^ 1])
            return data
        with mock.patch.object(self.log, '_read_at', side_effect=altered):
            with self.assertRaisesRegex(EventLogError, 'EVENT_APPEND_UNCERTAIN'):
                self.log.append({'kind': 'INTENT'}, binding.witnessed)
        with self.assertRaisesRegex(EventLogError, 'EVENT_RECOVERY_REQUIRED'):
            self.log.read(2)
        self.log.close()
        with PrivateEventLog.reopen(self.log.root, binding) as reopened:
            self.assertEqual(json.loads(reopened.read(2).event), {'kind': 'INTENT'})

    def test_final_eof_readback_rejects_unexpected_tail_after_chain_validation(self):
        for operation in ('read', 'append'):
            with self.subTest(operation=operation):
                log = PrivateEventLog.create(self.base)
                binding, inspect = log.binding(), log._inspect
                calls = 0
                def changed():
                    nonlocal calls
                    calls += 1
                    if calls == (3 if operation == 'read' else 5):
                        log._write_at(log._index[-1][2].size, b'!')
                    return inspect()
                try:
                    with mock.patch.object(log, '_inspect', side_effect=changed):
                        with self.assertRaises(EventLogError) as caught:
                            if operation == 'read':
                                log.read(1)
                            else:
                                log.append({'kind': 'INTENT'}, binding.witnessed)
                    self.assertTrue(caught.exception.outcome_unknown)
                finally:
                    log.close()
                damaged = (log.root / '.events').read_bytes()
                self.assertTrue(damaged.endswith(b'!'))
                with self.assertRaisesRegex(EventLogError, 'EVENT_RECOVERY_REQUIRED'):
                    PrivateEventLog.reopen(log.root, binding)
                self.assertEqual((log.root / '.events').read_bytes(), damaged)

    def test_reader_waits_for_append_flush_and_validated_snapshot(self):
        parent = self.log.binding().witnessed
        at_flush, release, read_done = threading.Event(), threading.Event(), threading.Event()
        flush, results, errors = self.log._api.flush, [], []
        calls = 0
        def delayed(handle):
            nonlocal calls
            calls += 1
            if calls == 2:
                at_flush.set()
                if not release.wait(5):
                    raise RuntimeError('fixture flush wait timed out')
            flush(handle)
        def append():
            try:
                results.append(self.log.append({'kind': 'INTENT'}, parent))
            except BaseException as exc:
                errors.append(type(exc).__name__)
        def read():
            try:
                results.append(self.log.binding().witnessed)
            except BaseException as exc:
                errors.append(type(exc).__name__)
            finally:
                read_done.set()
        writer, reader = threading.Thread(target=append, daemon=True), threading.Thread(target=read, daemon=True)
        with mock.patch.object(self.log._api, 'flush', side_effect=delayed):
            writer.start()
            try:
                self.assertTrue(at_flush.wait(5))
                reader.start()
                self.assertFalse(read_done.wait(.05))
            finally:
                release.set()
                writer.join(5)
                if reader.ident is not None:
                    reader.join(5)
        self.assertFalse(writer.is_alive() or reader.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0].sequence, 2)

    @staticmethod
    def _config(log):
        return {'root': str(log.root), 'binding': dataclasses.asdict(log.binding())}

    @contextmanager
    def _custody(self):
        """Real registry and native roots, with exact unique-leaf cleanup."""
        from host.core.custody import WitnessCustody
        from host.core.custody_registry import RegistryCustody, BASE_PATH
        from host.core.private_store import PrivateBlobStore
        from host.core.safe_replace import ProtectedFileRoot
        import winreg

        RegistryCustody.provision_base()
        local_id = uuid.uuid4().hex
        key_path = BASE_PATH + '\\' + local_id
        parent = self.base / ('custody-files-' + local_id)
        parent.mkdir()
        with ExitStack() as stack:
            files = stack.enter_context(ProtectedFileRoot.create(parent))
            blobs = stack.enter_context(PrivateBlobStore.create(self.base))
            registry = RegistryCustody.create(local_id)
            def remove_owned_leaf():
                # create() succeeded for this unique ID; verify the exact
                # marker before deleting only that leaf, never shared parents.
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                                    winreg.KEY_QUERY_VALUE | winreg.KEY_WOW64_64KEY) as key:
                    marker, kind = winreg.QueryValueEx(key, 'Format')
                self.assertEqual((marker, kind), (b'hh-registry-custody-1\0' + local_id.encode(), winreg.REG_BINARY))
                winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, key_path, winreg.KEY_WOW64_64KEY, 0)
            stack.callback(remove_owned_leaf)
            stack.callback(registry.close)
            custody = WitnessCustody(registry, storage_id=local_id, project_id='events-test', create=True)
            custody.activate(file_root=files.root, file_identity=files.root_identity,
                             blob_root=blobs.root, blob_identity=blobs.root_identity,
                             event_root=self.log.root, event_binding=self.log.binding())
            yield registry, custody

    @staticmethod
    def _binding(config):
        value = config['binding']
        return EventBinding(FileIdentity(**value['root']), FileIdentity(**value['stream']),
                            EventHead(**value['witnessed']))

    @staticmethod
    def _imports():
        return """import json, sys
from host.core.private_events import PrivateEventLog, EventLogError, EventBinding, EventHead, pending_event_cleanup
from host.core.safe_open import FileIdentity
c = json.loads(sys.stdin.read())
b = c['binding']
binding = EventBinding(FileIdentity(**b['root']), FileIdentity(**b['stream']), EventHead(**b['witnessed']))
"""

    @staticmethod
    def _child(script, config):
        return subprocess.run([sys.executable, '-B', '-c', script], input=json.dumps(config),
                              capture_output=True, text=True, cwd=ROOT, timeout=15)


if __name__ == '__main__':
    unittest.main(verbosity=2)
