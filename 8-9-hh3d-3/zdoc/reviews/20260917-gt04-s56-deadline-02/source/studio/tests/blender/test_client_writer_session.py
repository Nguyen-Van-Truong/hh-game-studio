"""Pure writer registration/lifecycle models; no native process or journal I/O.

Exact production object types contain explicitly inert process and journal
doubles. Passing these tests cannot prove native effects, persistence or ACKs.
"""
import copy
import hashlib
from pathlib import Path
import sys
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.blender import client_writer_session as module
from studio.host.blender import client_catalog as readonly
from studio.host.blender import client_write_catalog as catalog
from studio.host.blender.client_writer_session import BlenderWriterClientSession, BlenderWriteLease
from studio.host.blender.durable_session import DurableBlenderSession, PROJECT, TARGET
from studio.host.blender.ui_host import BlenderUIHost
from studio.host.blender.writer_journal import BlenderWriterJournal
from studio.host.core.journal import Lease, JournalError
from studio.host.core.limits import SafetyViolation
from studio.host.core.transport import epoch_ms
from studio.protocol.core import canonical_bytes


class WriterSessionTests(unittest.TestCase):
    def setUp(self):
        self.source = {'inert-model.py': 'a' * 64}
        self.source_hash = 'sha256:' + hashlib.sha256(canonical_bytes(self.source)).hexdigest()
        self.sources = patch.object(module, 'source_files', return_value=self.source)
        self.sources.start(); self.addCleanup(self.sources.stop)
        self.host = object.__new__(BlenderUIHost)
        host = self.host
        host._process = Mock(); host._process.poll.return_value = None
        host._job = Mock(); host._job.active_count.return_value = 2
        host._job.snapshot.return_value = {'assigned': True, 'configured': True, 'tainted': False,
            'closed': False, 'handle_retained': True, 'active_count': 2}
        host.pid = 123; host._session = 'a' * 32; host._source = copy.deepcopy(self.source)
        host._closed = host._held = host._stopped = host._recovery_readonly = False
        host._deadline = time.monotonic() + 90; host.directory = Path('inert-owned-writer').absolute()
        self.native = object.__new__(DurableBlenderSession)
        self.native.host = host; self.native.directory = host.directory / 'journal'
        self.native._held = self.native._stopped = False
        self.journal = object.__new__(BlenderWriterJournal)
        self.journal.path = self.native.directory / 'blender-journal.jsonl'
        self.current = None
        self.journal.check_running = Mock()
        def current_lease(lease, *, now_ms):
            if self.current != lease or lease.expires_ms <= now_ms:
                raise JournalError('STALE_LEASE')
        self.journal.check_lease = Mock(side_effect=current_lease)
        self.native.journal = self.journal
        self.session = self.construct()
        self.credential = self.session.issue(operations=catalog.OPERATIONS)
        self.auth = 'Bearer ' + self.credential.bearer
        self.grant = self.session.authenticate(self.auth)
        self.label = self.session.writer_label(self.grant)
        self.native_lease = Lease(PROJECT, TARGET, self.label, 1, epoch_ms() + 20000)
        self.current = self.native_lease
        self.lease = self.session.register_writer(self.grant, self.native_lease)

    def construct(self, **changes):
        args = dict(project_id='blender.test', source_sha256=self.source_hash, owner_deadline_ms=epoch_ms() + 85000)
        args.update(changes)
        return BlenderWriterClientSession.from_durable(self.native, **args)

    def options(self, **changes):
        args = dict(operation='mesh.create_box', deadline_ms=epoch_ms() + 4000)
        args.update(changes)
        return args

    def start(self):
        return self.session.start_write(self.grant, self.lease, **self.options())

    def test_exact_native_objects_and_duplicate_host_registration(self):
        for value in (SimpleNamespace(host=self.host), {'host': self.host}, self.host.pid):
            with self.subTest(kind=type(value)), self.assertRaisesRegex(SafetyViolation, 'EXACT_DURABLE'):
                BlenderWriterClientSession.from_durable(value, source_sha256=self.source_hash, owner_deadline_ms=epoch_ms()+1000)
        with self.assertRaisesRegex(SafetyViolation, 'ALREADY_REGISTERED'):
            self.construct()
        with self.assertRaisesRegex(TypeError, 'from_durable'):
            BlenderWriterClientSession()

    def test_default_grant_is_readonly_and_empty_fixture_scopes(self):
        credential = self.session.issue()
        grant = self.session.authenticate('Bearer ' + credential.bearer)
        self.assertEqual(credential.scopes, frozenset())
        self.assertEqual(frozenset(grant.operations), readonly.OPERATIONS)
        with self.assertRaisesRegex(SafetyViolation, 'WRITER_GRANT_REQUIRED'):
            self.session.writer_label(grant)
        self.session.read_lease(grant, ttl_ms=1000)

    def test_current_native_lease_identity_and_random_public_label(self):
        self.assertEqual(self.lease.lease_id, 'write.' + self.label.removeprefix('client-writer-'))
        self.assertNotIn(str(self.host.pid), self.lease.lease_id[:6])
        self.assertIs(self.session.register_writer(self.grant, self.native_lease), self.lease)
        permit = self.start()
        self.assertIs(self.session.begin_write_effect(permit), self.native_lease)
        self.assertIs(self.journal.check_lease.call_args.args[0], self.native_lease)
        self.session.finish_write(permit)

    def test_current_journal_is_required_at_registration_and_before_effect(self):
        self.current = Lease(PROJECT, TARGET, self.label, 2, epoch_ms() + 20000)
        for operation in (lambda: self.session.register_writer(self.grant, self.native_lease),
                          lambda: self.session.check_write(self.grant, self.lease, **self.options())):
            with self.assertRaisesRegex(JournalError, 'STALE_LEASE'):
                operation()

    def test_fence_is_rechecked_after_preparation(self):
        permit = self.start()
        self.current = Lease(PROJECT, TARGET, self.label, 2, epoch_ms() + 20000)
        with self.assertRaisesRegex(JournalError, 'STALE_LEASE'):
            self.session.begin_write_effect(permit)
        self.session.finish_write(permit)

    def test_copied_tampered_and_lease_shaped_values_are_not_authority(self):
        for value in (copy.copy(self.lease), SimpleNamespace(**self.lease.__dict__), self.native_lease):
            with self.subTest(kind=type(value)), self.assertRaisesRegex(SafetyViolation, 'WRITE_LEASE_REQUIRED'):
                self.session.check_write(self.grant, value, **self.options())
        with self.assertRaisesRegex(SafetyViolation, 'NATIVE_LEASE_REQUIRED'):
            self.session.register_writer(self.grant, copy.copy(self.native_lease))
        with self.assertRaisesRegex(SafetyViolation, 'NATIVE_LEASE_REQUIRED'):
            self.session.register_writer(self.grant, SimpleNamespace(**self.native_lease.__dict__))
        object.__setattr__(self.lease, 'expires_ms', self.lease.expires_ms + 1)
        with self.assertRaisesRegex(SafetyViolation, 'WRITE_LEASE_REQUIRED'):
            self.session.resolve_writer_lease(self.grant, self.lease.lease_id, self.lease.fencing_epoch)

    def test_native_lease_field_mutation_is_rejected(self):
        object.__setattr__(self.native_lease, 'fencing_epoch', 9)
        with self.assertRaisesRegex(SafetyViolation, 'NATIVE_LEASE_CHANGED'):
            self.session.check_write(self.grant, self.lease, **self.options())

    def test_copied_and_tampered_grants_are_rejected(self):
        with self.assertRaisesRegex(SafetyViolation, 'GRANT_REQUIRED'):
            self.session.writer_label(copy.copy(self.grant))
        object.__setattr__(self.grant, 'project_id', 'other')
        with self.assertRaisesRegex(SafetyViolation, 'GRANT_REQUIRED'):
            self.session.check_write(self.grant, self.lease, **self.options())

    def test_other_public_session_cannot_import_registered_native_writer(self):
        credential = self.session.issue(operations=catalog.OPERATIONS)
        grant = self.session.authenticate('Bearer ' + credential.bearer)
        self.assertNotEqual(self.session.writer_label(grant), self.label)
        with self.assertRaisesRegex(SafetyViolation, 'NATIVE_LEASE_REQUIRED'):
            self.session.register_writer(grant, self.native_lease)
        with self.assertRaisesRegex(SafetyViolation, 'WRITE_LEASE_REQUIRED'):
            self.session.resolve_writer_lease(grant, self.lease.lease_id, self.lease.fencing_epoch)

    def test_source_project_catalog_and_owner_binding_are_checked(self):
        for name, value in (('project_id', 'other'), ('catalog_digest', 'sha256:'+'0'*64),
                            ('source_sha256', 'sha256:'+'0'*64)):
            before = getattr(self.session, name); setattr(self.session, name, value)
            try:
                with self.subTest(field=name), self.assertRaisesRegex(SafetyViolation, 'BINDING_CHANGED'):
                    self.session.check_write(self.grant, self.lease, **self.options())
            finally:
                setattr(self.session, name, before)
        self.host._source = {'changed.py': 'b'*64}
        with self.assertRaisesRegex(SafetyViolation, 'SOURCE_CHANGED'):
            self.session.check_write(self.grant, self.lease, **self.options())

    def test_host_process_job_generation_and_native_session_replacement_are_rejected(self):
        for target, name, value in ((self.host, '_process', Mock()), (self.host, '_job', Mock()),
                                   (self.host, '_session', 'b'*32), (self.native, 'host', object()),
                                   (self.native, 'journal', object()), (self.host, 'pid', True)):
            before = getattr(target, name); setattr(target, name, value)
            try:
                with self.subTest(field=name), self.assertRaises(SafetyViolation):
                    self.session.check_write(self.grant, self.lease, **self.options())
            finally:
                setattr(target, name, before)

    def test_closed_held_stopped_recovery_and_dead_native_owner_are_denied(self):
        for target, name in ((self.host, '_closed'), (self.host, '_held'), (self.host, '_stopped'),
                             (self.host, '_recovery_readonly'), (self.native, '_held'), (self.native, '_stopped')):
            setattr(target, name, True)
            try:
                with self.subTest(field=name), self.assertRaises(SafetyViolation):
                    self.session.check_write(self.grant, self.lease, **self.options())
            finally:
                setattr(target, name, False)
        self.host._process.poll.return_value = 0
        with self.assertRaisesRegex(SafetyViolation, 'LIVE_OWNER'):
            self.session.check_write(self.grant, self.lease, **self.options())

    def test_invalid_ids_fence_deadlines_and_read_as_write_are_denied(self):
        for lease_id, fence in ((self.lease.lease_id, True), (self.lease.lease_id, 0), ('write.forged', 1)):
            with self.subTest(fence=fence), self.assertRaisesRegex(SafetyViolation, 'WRITE_LEASE_REQUIRED'):
                self.session.resolve_writer_lease(self.grant, lease_id, fence)
        for deadline in (True, epoch_ms()-1, epoch_ms()+catalog.MAX_UI_MS+1000):
            with self.subTest(deadline=deadline), self.assertRaisesRegex(SafetyViolation, 'DEADLINE_EXPIRED'):
                self.session.check_write(self.grant, self.lease, **self.options(deadline_ms=deadline))
        with self.assertRaisesRegex(SafetyViolation, 'WRITER_OPERATION_REQUIRED'):
            self.session.check_write(self.grant, self.lease, **self.options(operation=catalog.READ))

    def test_partial_write_grant_cannot_authorize_other_operation(self):
        credential = self.session.issue(operations=frozenset({'mesh.create_box'}))
        grant = self.session.authenticate('Bearer '+credential.bearer)
        label = self.session.writer_label(grant)
        native = Lease(PROJECT, TARGET, label, 2, epoch_ms()+10000); self.current = native
        lease = self.session.register_writer(grant, native)
        with self.assertRaisesRegex(SafetyViolation, 'OPERATION_FORBIDDEN'):
            self.session.check_write(grant, lease, **self.options(operation='history.undo'))

    def test_public_lease_expiry_never_extends_native_or_credential_horizon(self):
        self.assertLessEqual(self.lease.expires_ms, self.native_lease.expires_ms)
        self.assertLessEqual(self.lease.expires_ms, self.credential.expires_ms)
        self.assertLessEqual(self.lease.expires_ms, self.session._owner_deadline_ms)
        future = self.lease.expires_ms + 1
        with patch.object(module, 'epoch_ms', return_value=future):
            with self.assertRaisesRegex(SafetyViolation, 'DEADLINE_EXPIRED'):
                self.session.resolve_writer_lease(self.grant, self.lease.lease_id, self.lease.fencing_epoch)

    def test_rotation_invalidates_label_lease_and_prepared_permit(self):
        permit = self.start(); credential = self.session.rotate(self.credential)
        with self.assertRaises(SafetyViolation): self.session.authenticate(self.auth)
        grant = self.session.authenticate('Bearer '+credential.bearer)
        self.assertNotEqual(self.session.writer_label(grant), self.label)
        with self.assertRaises(SafetyViolation): self.session.begin_write_effect(permit)
        with self.assertRaises(SafetyViolation): self.session.resolve_writer_lease(grant, self.lease.lease_id, 1)
        self.session.finish_write(permit)

    def test_stop_preserves_controls_but_denies_prepared_effect(self):
        permit = self.start(); result = self.session.stop(self.grant)
        self.assertTrue(result['write_draining']); self.assertEqual(result['write_phase'], 'PREPARED')
        self.assertFalse(result['public_ack'])
        with self.assertRaisesRegex(SafetyViolation, 'STOPPED'): self.session.begin_write_effect(permit)
        for operation in ('control.lookup', 'control.stop'):
            self.session.authorize(self.auth, operation, project_id='blender.test', catalog_digest=catalog.CATALOG_DIGEST)
        self.session.finish_write(permit)

    def test_revoke_reports_dispatching_and_finish_does_not_require_auth(self):
        permit = self.start(); self.session.begin_write_effect(permit)
        result = self.session.revoke(self.credential)
        self.assertTrue(result['write_draining']); self.assertEqual(result['write_phase'], 'DISPATCHING')
        with self.assertRaises(SafetyViolation): self.session.check_write_permit(permit)
        self.session.finish_write(permit)
        self.assertIsNone(self.session._write_active)

    def test_permit_is_opaque_one_use_and_session_owned(self):
        permit = self.start()
        with self.assertRaisesRegex(SafetyViolation, 'PERMIT_REQUIRED'):
            self.session.begin_write_effect(copy.copy(permit))
        self.session.begin_write_effect(permit)
        with self.assertRaisesRegex(SafetyViolation, 'ALREADY_DISPATCHING'):
            self.session.begin_write_effect(permit)
        self.session.finish_write(permit)
        with self.assertRaisesRegex(SafetyViolation, 'PERMIT_REQUIRED'):
            self.session.finish_write(permit)

    def test_single_active_read_or_write(self):
        read = self.session.read_lease(self.grant, ttl_ms=5000)
        permit = self.start()
        with self.assertRaisesRegex(SafetyViolation, 'WRITER_BUSY'): self.start()
        with self.assertRaisesRegex(SafetyViolation, 'WRITER_BUSY'):
            self.session.start_read(self.grant, read, deadline_ms=epoch_ms()+1000)
        self.session.finish_write(permit)
        reading = self.session.start_read(self.grant, read, deadline_ms=epoch_ms()+1000)
        with self.assertRaisesRegex(SafetyViolation, 'WRITER_BUSY'): self.start()
        self.session.finish_read(reading)

    def test_unknown_outcome_holds_fresh_writes_and_keeps_controls(self):
        permit = self.start(); self.session.begin_write_effect(permit)
        self.session.finish_write(permit, outcome_known=False)
        with self.assertRaisesRegex(SafetyViolation, 'WRITER_HELD'): self.start()
        self.session.authorize(self.auth, 'control.lookup', project_id='blender.test', catalog_digest=catalog.CATALOG_DIGEST)
        self.session.stop(self.grant)

    def test_stop_overtaking_journal_read_cannot_authorize_effect(self):
        self._overtake(self.start(), 'stop')

    def test_revoke_overtaking_journal_read_cannot_authorize_effect(self):
        self._overtake(self.start(), 'revoke')

    def _overtake(self, permit, action):
        entered = threading.Event(); release = threading.Event(); outcomes = []
        def blocked(lease, *, now_ms):
            entered.set()
            if not release.wait(2): raise AssertionError('model did not release journal read')
        self.journal.check_lease.side_effect = blocked
        def run():
            try: outcomes.append(self.session.begin_write_effect(permit))
            except BaseException as error: outcomes.append(error)
        thread = threading.Thread(target=run); thread.start()
        try:
            self.assertTrue(entered.wait(1))
            begin = time.monotonic()
            getattr(self.session, action)(self.grant if action == 'stop' else self.credential)
            self.assertLess(time.monotonic()-begin, .5, 'session mutex held across native journal read')
        finally:
            release.set(); thread.join(2)
        self.assertFalse(thread.is_alive()); self.assertEqual(len(outcomes), 1)
        self.assertIsInstance(outcomes[0], SafetyViolation)
        self.assertEqual(self.session._write_active['phase'], 'PREPARED')
        self.session.finish_write(permit)

    def test_registration_rechecks_revocation_after_journal_read(self):
        original = self.journal.check_lease.side_effect
        def revoke(lease, *, now_ms):
            original(lease, now_ms=now_ms); self.session.revoke(self.credential)
        self.journal.check_lease.side_effect = revoke
        with self.assertRaisesRegex(SafetyViolation, 'GRANT_REQUIRED'):
            self.session.register_writer(self.grant, self.native_lease)

    def test_native_stop_overtaking_journal_read_denies_fresh_authorization(self):
        permit = self.start()
        def stop(lease, *, now_ms):
            self.native._stopped = True
        self.journal.check_lease.side_effect = stop
        with self.assertRaisesRegex(SafetyViolation, 'OWNER_HELD_OR_STOPPED'):
            self.session.begin_write_effect(permit)
        self.assertEqual(self.session._write_active['phase'], 'PREPARED')
        self.session.finish_write(permit)

    def test_publication_never_redacts_success_under_the_original_result_hash(self):
        future_bearer = 'z'*43
        value = {'status': 'COMMITTED', 'code': 'BLENDER_WRITE_CONFIRMED',
                 'postconditions': {'name': future_bearer}}
        raw = canonical_bytes(value)
        self.assertEqual(self.session.encode_output(value), raw)
        with patch('studio.host.core.transport.secrets.token_urlsafe', return_value=future_bearer):
            self.session.issue()
        with self.assertRaisesRegex(SafetyViolation, 'SENSITIVE_OBSERVATION'):
            self.session.encode_output(value)
        self.assertEqual(canonical_bytes(value), raw)

    def test_old_secrets_remain_redacted_and_forbidden_as_public_ids(self):
        self.session.rotate(self.credential)
        self.assertNotIn(self.credential.bearer, self.session.encode_output({'message': self.credential.bearer}).decode())
        with self.assertRaises(SafetyViolation): self.session.validate_public_identifier(self.credential.bearer)


if __name__ == '__main__':
    unittest.main()
