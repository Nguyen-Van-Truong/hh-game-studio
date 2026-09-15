"""Real Windows handles, crash cuts and retained-owner recovery for event log."""
from __future__ import annotations

import dataclasses
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

    @staticmethod
    def _config(log):
        return {'root': str(log.root), 'binding': dataclasses.asdict(log.binding())}

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
