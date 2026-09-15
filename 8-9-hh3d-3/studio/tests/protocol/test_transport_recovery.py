"""Real socket cut points, archive lookup and lifetime credential protection."""
from __future__ import annotations

import base64
from contextlib import contextmanager, nullcontext
from dataclasses import replace
import hashlib
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))
from studio.host.core.journal import Journal, JournalError, JournalLimits
from studio.host.core.limits import SafetyViolation
from studio.host.core.transport import (ArchivedResult, FixtureClient, FixtureFaults,
    LoopbackFixtureHost, SessionAuthority, TransportLimits, epoch_ms)
from studio.protocol.core import Response, Status, canonical_bytes


ALL_SCOPES = frozenset({'fixture.read', 'fixture.write', 'control.stop', 'control.cancel'})
CUTS = ('before_dispatch', 'after_dispatch', 'before_reply', 'after_reply')


@contextmanager
def fixture(*, journal_limits=None, transport_limits=TransportLimits()):
    with tempfile.TemporaryDirectory(prefix='gt02-recovery-') as directory:
        root = Path(directory)
        faults = FixtureFaults()
        journal = Journal(root / 'journal.jsonl', limits=journal_limits)
        with LoopbackFixtureHost('project.fixture', root, journal, faults=faults,
                                 limits=transport_limits) as host:
            credential = host.sessions.issue(scopes=ALL_SCOPES)
            client = FixtureClient(host.port, host.control_port, credential)
            try:
                yield root, host, client, credential
            finally:
                if faults.readback_gate is not None:
                    faults.readback_gate.set()


def observed_state(root, host):
    with host._lock:
        return {'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in root.rglob('*') if p.is_file()},
                'fixture': host.fixture.snapshot(), 'queue': len(host._queue),
                'jobs': len(host._jobs), 'stopped': host._stopped.is_set()}


class TransportRecoveryTests(unittest.TestCase):
    def test_reload_fsync_failure_preserves_pending_and_requires_reconciliation(self):
        self.check_fsync_failure(terminal_bytes=False)

    def test_terminal_fsync_failure_is_unknown_over_socket_until_recovery_barrier(self):
        self.check_fsync_failure(terminal_bytes=True)

    def check_fsync_failure(self, *, terminal_bytes):
        """Distinguish failed pre-append reload from a cached terminal record."""
        from studio.host.core import journal as journal_module

        with fixture() as (_, host, client, _):
            host.faults.readback_gate = threading.Event()
            request = client.request('terminal-fsync.socket', value=43,
                                     lease=client.lease())
            self.assertIs(client.submit(request).status, Status.ACCEPTED_PENDING)
            self.assertTrue(host.faults.applied.wait(1))
            pending_size = host.journal.path.stat().st_size
            real_fsync = journal_module.os.fsync
            failed_sizes = []

            def fail_at_barrier(fd):
                size = host.journal.path.stat().st_size
                if not terminal_bytes or size > pending_size:
                    failed_sizes.append(size)
                    raise OSError('injected-fsync')
                return real_fsync(fd)

            with mock.patch.object(journal_module.os, 'fsync', side_effect=fail_at_barrier):
                host.faults.readback_gate.set()
                deadline = time.monotonic() + 2
                while not host._stopped.is_set() and time.monotonic() < deadline:
                    time.sleep(.005)
                self.assertTrue(host._stopped.is_set())
                lookup = client.lookup(request.command_id)
                retry = client.submit(request)
                self.assertIs(lookup.status, Status.UNKNOWN)
                self.assertEqual(lookup.code, 'JOURNAL_DURABILITY_UNCONFIRMED')
                self.assertEqual(lookup.command_id, request.command_id)
                self.assertIs(retry.status, Status.UNKNOWN)
                self.assertEqual(retry.code, 'JOURNAL_DURABILITY_UNCONFIRMED')
                archive = client.lookup_archive(request.command_id)
                self.assertIs(archive.status, Status.UNKNOWN)
                self.assertEqual(archive.code, 'JOURNAL_DURABILITY_UNCONFIRMED')
                with self.assertRaisesRegex(JournalError, 'JOURNAL_DURABILITY_UNCONFIRMED'):
                    Journal(host.journal.path)
            self.assertTrue(failed_sizes)
            self.assertEqual(all(size > pending_size for size in failed_sizes), terminal_bytes)
            recovered = Journal(host.journal.path)
            expected_status = 'COMMITTED' if terminal_bytes else 'ACCEPTED_PENDING'
            self.assertEqual(recovered.lookup(project_id='project.fixture',
                                               command_id=request.command_id,
                                               now_ms=epoch_ms())['status'], expected_status)
            lookup = client.lookup(request.command_id)
            retry = client.submit(request)
            if terminal_bytes:
                self.assertIs(lookup.status, Status.COMMITTED)
            else:
                self.assertIs(lookup.status, Status.UNKNOWN)
                self.assertEqual(lookup.code, 'RECOVERY_REQUIRED')
            self.assertEqual(retry, lookup)
            self.assertEqual(host.fixture.effect_count, 1)

    def test_unreadable_history_never_rejects_an_already_applied_command(self):
        for fault in ('lock', 'guard_directory', 'guard_hardlink', 'bytes', 'records', 'legacy_lock'):
            with self.subTest(fault=fault), fixture() as (_, host, client, _):
                request = client.request('history.unavailable', value=47, lease=client.lease())
                self.assertIs(client.submit(request).status, Status.ACCEPTED_PENDING)
                committed = self.terminal(client, request.command_id)
                self.assertIs(committed.status, Status.COMMITTED)
                limits = host.journal.limits
                competitor = Journal(host.journal.path)
                legacy = host.journal.path.with_name(host.journal.path.name + '.lock')
                guard = host.journal.path.with_name(host.journal.path.name + '.guard')
                saved_guard = guard.with_name('saved.guard')
                guard_alias = guard.with_name('alias.guard')
                if fault == 'lock':
                    host.journal.limits = replace(limits, lock_timeout_ms=30)
                    expected = 'JOURNAL_LOCKED'
                elif fault == 'guard_directory':
                    guard.rename(saved_guard)
                    guard.mkdir()
                    expected = 'JOURNAL_LOCK_FAILED'
                elif fault == 'guard_hardlink':
                    os.link(guard, guard_alias)
                    expected = 'JOURNAL_LOCK_UNSAFE'
                elif fault == 'bytes':
                    host.journal.limits = replace(limits, max_bytes=1)
                    expected = 'JOURNAL_FULL'
                elif fault == 'records':
                    host.journal.limits = replace(limits, max_records=1)
                    expected = 'JOURNAL_RECORD_LIMIT'
                else:
                    legacy.write_text('{', encoding='utf-8')
                    expected = 'JOURNAL_LEGACY_LOCK_RECOVERY_REQUIRED'
                before = host.journal.path.read_bytes()
                try:
                    with competitor._writer_lock() if fault == 'lock' else nullcontext():
                        for response in (client.lookup(request.command_id), client.submit(request),
                                         client.cancel(request.command_id),
                                         client.lookup_archive(request.command_id)):
                            self.assertIs(response.status, Status.UNKNOWN)
                            self.assertEqual(response.code, expected)
                            self.assertEqual(response.command_id, request.command_id)
                            self.assertNotIn('no_effect', response.postconditions)
                finally:
                    host.journal.limits = limits
                    if fault == 'legacy_lock':
                        legacy.unlink()
                    elif fault == 'guard_directory':
                        guard.rmdir()
                        saved_guard.rename(guard)
                    elif fault == 'guard_hardlink':
                        guard_alias.unlink()
                self.assertEqual(host.journal.path.read_bytes(), before)
                self.assertEqual(client.lookup(request.command_id), committed)
                self.assertEqual(client.submit(request), committed)
                self.assertEqual(host.fixture.effect_count, 1)

    def test_fence_cannot_change_between_validation_and_effect(self):
        with fixture() as (_, host, client, _):
            lease = client.lease()
            competitor = Journal(host.journal.path,
                limits=replace(host.journal.limits, lock_timeout_ms=30))
            observed = []
            original = host.sessions.apply_authorization

            @contextmanager
            def interleave(session):
                with original(session):
                    try:
                        competitor.acquire_lease(project_id=host.project_id,
                            target='fixture.counter', owner=lease.lease_id,
                            now_ms=epoch_ms(), ttl_ms=60_000)
                    except JournalError as error:
                        observed.append(error.code)
                    else:
                        observed.append('FENCE_CHANGED_BEFORE_EFFECT')
                    yield

            with mock.patch.object(host.sessions, 'apply_authorization', interleave):
                request = client.request('fence.atomic', value=41, lease=lease)
                self.assertIs(client.submit(request).status, Status.ACCEPTED_PENDING)
                terminal = self.terminal(client, request.command_id)
            self.assertEqual(observed, ['JOURNAL_LOCKED'])
            self.assertIs(terminal.status, Status.COMMITTED)
            self.assertEqual(host.fixture.effect_count, 1)

    def terminal(self, client, command_id):
        end = time.monotonic() + 3
        while time.monotonic() < end:
            result = client.lookup(command_id)
            if result.status is not Status.ACCEPTED_PENDING:
                return result
            time.sleep(.005)
        self.fail('bounded terminal lookup expired')

    def arm(self, host, route, cut):
        host.faults.disconnect_observed.clear()
        host.faults.disconnect_once = (route, cut)

    def assert_cut(self, host, cut, result, delivered_status):
        self.assertTrue(host.faults.disconnect_observed.wait(1))
        self.assertIs(result.status, delivered_status if cut == 'after_reply' else Status.UNKNOWN)
        if cut != 'after_reply':
            self.assertEqual(result.code, 'CONNECTION_LOST_LOOKUP')
            self.assertEqual(result.postconditions['next_action'], 'lookup')

    def test_pending_ack_socket_cuts_preserve_lookup_and_one_effect(self):
        for cut in CUTS:
            with self.subTest(cut=cut), fixture() as (root, host, client, _):
                request = client.request('cut.submit', value=37, lease=client.lease(), delay_ms=40)
                before = observed_state(root, host)
                self.arm(host, '/v1/commands', cut)
                reply = client.submit(request)
                self.assert_cut(host, cut, reply, Status.ACCEPTED_PENDING)
                if cut == 'before_dispatch':
                    self.assertEqual(client.lookup(request.command_id).code, 'COMMAND_NOT_FOUND')
                    self.assertEqual(observed_state(root, host), before)
                    # Only after the explicit lookup proves no admission may
                    # this test deliberately send the same command again.
                    self.assertIs(client.submit(request).status, Status.ACCEPTED_PENDING)
                else:
                    self.assertEqual(host.faults.disconnected_status, 'ACCEPTED_PENDING')
                committed = self.terminal(client, request.command_id)
                self.assertIs(committed.status, Status.COMMITTED)
                self.assertEqual(client.submit(request), committed)
                self.assertEqual(host.fixture.effect_count, 1)

    def test_committed_lookup_ack_socket_cuts_return_original_receipt(self):
        for cut in CUTS:
            with self.subTest(cut=cut), fixture() as (root, host, client, _):
                request = client.request('cut.committed', value=12, lease=client.lease())
                client.submit(request)
                committed = self.terminal(client, request.command_id)
                self.assertIs(committed.status, Status.COMMITTED)
                before = observed_state(root, host)
                self.arm(host, '/v1/lookup', cut)
                reply = client.lookup(request.command_id)
                self.assert_cut(host, cut, reply, Status.COMMITTED)
                self.assertEqual(client.lookup(request.command_id), committed)
                self.assertEqual(client.submit(request), committed)
                self.assertEqual(observed_state(root, host), before)

    def test_cancel_ack_socket_cuts_do_not_duplicate_or_apply(self):
        for cut in CUTS:
            with self.subTest(cut=cut), fixture() as (_, host, client, _):
                request = client.request('cut.cancel', value=11, lease=client.lease(), delay_ms=1000)
                self.assertIs(client.submit(request).status, Status.ACCEPTED_PENDING)
                self.arm(host, '/v1/cancel', cut)
                reply = client.cancel(request.command_id)
                self.assert_cut(host, cut, reply, Status.CANCELED)
                looked_up = client.lookup(request.command_id)
                if cut == 'before_dispatch':
                    self.assertIs(looked_up.status, Status.ACCEPTED_PENDING)
                    self.assertIs(client.cancel(request.command_id).status, Status.CANCELED)
                else:
                    self.assertIs(looked_up.status, Status.CANCELED)
                canceled = self.terminal(client, request.command_id)
                self.assertIs(canceled.status, Status.CANCELED)
                self.assertEqual(client.submit(request), canceled)
                self.assertEqual(host.fixture.effect_count, 0)

    def test_stop_ack_socket_cuts_preserve_stopped_state_on_reconnect(self):
        for cut in CUTS:
            with self.subTest(cut=cut), fixture() as (_, host, client, credential):
                request = client.request('cut.stop.work', value=9, lease=client.lease(), delay_ms=1000)
                client.submit(request)
                self.arm(host, '/v1/stop', cut)
                reply = client.stop('cut.stop')
                self.assert_cut(host, cut, reply, Status.ACCEPTED_PENDING)
                if cut == 'before_dispatch':
                    self.assertEqual(client.lookup('cut.stop').code, 'COMMAND_NOT_FOUND')
                    self.assertFalse(host._stopped.is_set())
                    client.stop('cut.stop')
                stopped = self.terminal(client, 'cut.stop')
                self.assertEqual(stopped.code, 'STOPPED')
                self.assertEqual(client.stop('cut.stop'), stopped)
                self.assertIs(self.terminal(client, request.command_id).status, Status.CANCELED)
                replacement = host.sessions.rotate(credential)
                connected = FixtureClient(host.port, host.control_port, replacement)
                self.assertEqual(connected.submit(connected.request('cut.stop.new')).code, 'HOST_STOPPED')
                self.assertEqual(host.fixture.effect_count, 0)

    def test_capacity_reserves_terminal_record_and_bytes_before_mutation(self):
        for kind in ('records', 'bytes'):
            with self.subTest(kind=kind), fixture() as (root, host, client, _):
                lease = client.lease()
                if kind == 'records':
                    host.journal.limits = replace(host.journal.limits, max_records=2)
                    expected = 'JOURNAL_RECORD_LIMIT'
                else:
                    # Enough for a small PENDING row, insufficient for the
                    # terminal obligation: reject the whole admission.
                    host.journal.limits = replace(host.journal.limits,
                        max_bytes=host.journal.path.stat().st_size + 1000)
                    expected = 'JOURNAL_FULL'
                before = observed_state(root, host)
                result = client.submit(client.request('capacity.reject', value=37, lease=lease))
                self.assertIs(result.status, Status.REJECTED)
                self.assertEqual(result.code, expected)
                self.assertEqual(client.lookup('capacity.reject').code, 'COMMAND_NOT_FOUND')
                self.assertEqual(observed_state(root, host), before)

    def test_exact_terminal_record_capacity_can_complete_after_admission(self):
        with fixture(journal_limits=JournalLimits(max_records=3)) as (_, host, client, _):
            request = client.request('capacity.exact', value=37, lease=client.lease())
            self.assertIs(client.submit(request).status, Status.ACCEPTED_PENDING)
            result = self.terminal(client, request.command_id)
            self.assertIs(result.status, Status.COMMITTED)
            self.assertEqual(host.fixture.effect_count, 1)
            self.assertEqual(len(host.journal._records), 3)

    def test_expired_archive_is_authenticated_read_only_and_retains_original_receipt(self):
        with fixture(journal_limits=JournalLimits(retry_horizon_ms=150)) as (root, host, client, credential):
            request = client.request('archive.committed', value=17, lease=client.lease())
            client.submit(request)
            original = self.terminal(client, request.command_id)
            self.assertIs(original.status, Status.COMMITTED)
            self.assertEqual(client.lookup_archive(request.command_id).code, 'ARCHIVE_NOT_EXPIRED')
            time.sleep(.17)
            host.journal.compact(now_ms=epoch_ms())
            host.journal = Journal(host.journal.path, limits=host.journal.limits)
            before = observed_state(root, host)
            archive = client.lookup_archive(request.command_id)
            self.assertIsInstance(archive, ArchivedResult)
            self.assertEqual(archive.receipt, original)
            self.assertEqual(archive.original_receipt, original)
            self.assertIs(archive.original_status, Status.COMMITTED)
            self.assertTrue(archive.archived)
            self.assertFalse(archive.execution_permitted)
            self.assertEqual(client.submit(request).code, 'RETRY_HORIZON_EXPIRED')
            self.assertEqual(client.lookup(request.command_id).code, 'RETRY_HORIZON_EXPIRED')
            denied = host.sessions.issue(scopes=frozenset({'control.stop'}))
            outsider = FixtureClient(host.port, host.control_port, denied)
            self.assertEqual(outsider.lookup_archive(request.command_id).code, 'SCOPE_DENIED')
            bad_project = FixtureClient(host.port, host.control_port, replace(credential, project_id='other'))
            self.assertEqual(bad_project.lookup_archive(request.command_id).code, 'PROJECT_MISMATCH')
            missing_auth = FixtureClient(host.port, host.control_port, replace(credential, bearer='invalid'))
            self.assertEqual(missing_auth.lookup_archive(request.command_id).code, 'AUTH_REQUIRED')
            wrong_listener = client._call('/v1/archive', {'project_id':'project.fixture', 'command_id':request.command_id})
            self.assertEqual(wrong_listener['code'], 'UNSUPPORTED_ROUTE')
            self.assertEqual(observed_state(root, host), before)

    def test_expired_pending_archive_never_promotes_intent_to_committed(self):
        with fixture(journal_limits=JournalLimits(retry_horizon_ms=60)) as (_, host, client, _):
            host.faults.readback_gate = threading.Event()
            request = client.request('archive.pending')
            self.assertIs(client.submit(request).status, Status.ACCEPTED_PENDING)
            self.assertTrue(host.faults.applied.wait(1))
            time.sleep(.08)
            host.journal.compact(now_ms=epoch_ms())
            archive = client.lookup_archive(request.command_id)
            self.assertIsInstance(archive, ArchivedResult)
            self.assertIs(archive.original_status, Status.ACCEPTED_PENDING)
            self.assertIs(archive.original_receipt.status, Status.ACCEPTED_PENDING)
            self.assertIs(archive.receipt.status, Status.UNKNOWN)
            self.assertFalse(archive.execution_permitted)
            self.assertEqual(client.submit(request).code, 'RETRY_HORIZON_EXPIRED')
            self.assertEqual(host.fixture.effect_count, 0)

    def test_old_credentials_and_encoded_variants_never_enter_metadata_or_output(self):
        for action in ('rotate', 'revoke', 'expire'):
            with self.subTest(action=action), fixture() as (root, host, _, _):
                old = host.sessions.issue(scopes=ALL_SCOPES, ttl_ms=20 if action == 'expire' else 60_000)
                if action == 'rotate':
                    current = host.sessions.rotate(old)
                else:
                    if action == 'revoke':
                        host.sessions.revoke(old)
                    else:
                        time.sleep(.03)
                    current = host.sessions.issue(scopes=ALL_SCOPES)
                client = FixtureClient(host.port, host.control_port, current)
                before = observed_state(root, host)
                variants = {old.bearer, base64.b64encode(old.bearer.encode()).decode(),
                            base64.b64encode(old.bearer.encode()).decode().rstrip('='),
                            base64.urlsafe_b64encode(old.bearer.encode()).decode().rstrip('=')}
                captured = bytearray()
                for value in variants:
                    # No secret is included in assertion messages or test IDs.
                    body = client.request('placeholder').as_dict()
                    body['command_id'] = 'cmd.' + value
                    response = Response.from_dict(client._call('/v1/commands', body))
                    self.assertIs(response.status, Status.REJECTED)
                    self.assertIn(response.code, {'SENSITIVE_IDENTIFIER_FORBIDDEN', 'INVALID_COMMAND_ID', 'INVALID_FIELD'})
                    captured.extend(canonical_bytes(response.as_dict()))
                    for control in (client.stop, client.cancel, client.lookup, client.lookup_archive):
                        result = control('cmd.' + value)
                        self.assertIs(result.status, Status.REJECTED)
                        captured.extend(canonical_bytes(result.as_dict()))
                # JSON escapes decode before the public-identifier gate.
                body = client.request('cmd.' + old.bearer).as_dict()
                raw = json.dumps(body).replace(old.bearer, ''.join('\\u%04x' % ord(c) for c in old.bearer)).encode()
                connection = http.client.HTTPConnection('127.0.0.1', host.port, timeout=2)
                try:
                    connection.request('POST', '/v1/commands', raw, {'Content-Type':'application/json',
                        'Authorization':'Bearer ' + current.bearer})
                    captured.extend(connection.getresponse().read())
                finally:
                    connection.close()
                self.assertEqual(observed_state(root, host), before)
                captured.extend(b''.join(host.diagnostics))
                captured.extend(host.journal.path.read_bytes() if host.journal.path.exists() else b'')
                captured.extend(host.sessions.encode_output({'public': list(variants)}))
                for value in variants:
                    self.assertFalse(value.encode() in captured, 'issued credential leaked across an output boundary')

    def test_credential_history_budget_never_forgets_and_rotation_failure_is_atomic(self):
        with tempfile.TemporaryDirectory(prefix='gt02-history-') as directory:
            authority = SessionAuthority('p', Path(directory), TransportLimits(max_session_history=2))
            first = authority.issue()
            second = authority.rotate(first)
            with self.assertRaisesRegex(SafetyViolation, 'CREDENTIAL_HISTORY_LIMIT'):
                authority.rotate(second)
            authority.authenticate('Bearer ' + second.bearer)
            authority.revoke(second)
            with self.assertRaisesRegex(SafetyViolation, 'CREDENTIAL_HISTORY_LIMIT'):
                authority.issue()
            for credential in (first, second):
                with self.assertRaisesRegex(SafetyViolation, 'SENSITIVE_IDENTIFIER_FORBIDDEN'):
                    authority.validate_public_identifier('cmd.' + credential.bearer)
            self.assertEqual(len(authority._issued), 2)

    def test_queued_read_authorization_is_rechecked_after_rotation_revoke_and_expiry(self):
        for action in ('rotate', 'revoke', 'expire'):
            with self.subTest(action=action), fixture() as (_, host, client, _):
                host.faults.readback_gate = threading.Event()
                client.submit(client.request('read.blocker'))
                self.assertTrue(host.faults.applied.wait(1))
                reader = host.sessions.issue(ttl_ms=30 if action == 'expire' else 60_000)
                read_client = FixtureClient(host.port, host.control_port, reader)
                request = read_client.request('read.invalidated')
                self.assertIs(read_client.submit(request).status, Status.ACCEPTED_PENDING)
                if action == 'rotate':
                    host.sessions.rotate(reader)
                elif action == 'revoke':
                    host.sessions.revoke(reader)
                else:
                    time.sleep(.04)
                host.faults.readback_gate.set()
                self.assertEqual(self.terminal(client, request.command_id).code, 'SESSION_INVALIDATED')
                self.assertEqual(host.fixture.effect_count, 0)


if __name__ == '__main__':
    unittest.main()
