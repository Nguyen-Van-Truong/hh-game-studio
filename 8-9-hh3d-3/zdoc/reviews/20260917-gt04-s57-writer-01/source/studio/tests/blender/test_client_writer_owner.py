"""Pure public writer integration with real sessions/ledger and inert backends.

MemoryJournal performs no native locking, fsync, Registry or filesystem writes.
The modeled native response is not evidence of Blender execution or durability.
"""
import copy
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import Mock, patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.blender import client_writer_owner as module
from studio.host.blender import client_owner as read_module
from studio.host.blender import client_writer_session as session_module
from studio.host.blender import client_ledger as ledger_module
from studio.host.blender import client_write_catalog as catalog
from studio.host.blender import ui_host as host_module
from studio.host.blender.client_writer_owner import BlenderWriterClientOwner
from studio.host.blender.durable_session import DurableBlenderSession, PROJECT, TARGET
from studio.host.blender.writer_journal import BlenderWriterJournal
from studio.host.blender.ui_host import BlenderUIHost
from studio.host.core.journal import Lease, JournalError
from studio.host.core.limits import SafetyViolation
from studio.host.core.transport import epoch_ms
from studio.protocol.core import Request, Response, Status, canonical_bytes, parse_json
from test_client_ledger import MemoryJournal


class WriterOwnerTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.source = {'inert-writer-integration.py': 'a'*64}
        for target in (read_module, session_module, host_module):
            replacement = patch.object(target, 'source_files', return_value=self.source)
            replacement.start(); self.addCleanup(replacement.stop)
        self.host = object.__new__(BlenderUIHost)
        host = self.host
        host._process = Mock(); host._process.poll.return_value = None
        host._job = Mock(); host._job.active_count.return_value = 2
        host._job.snapshot.return_value = {'assigned': True, 'configured': True, 'tainted': False,
            'closed': False, 'handle_retained': True, 'active_count': 2}
        host.pid = 123; host._session = 'a'*32; host._source = copy.deepcopy(self.source)
        host._closed = host._held = host._stopped = host._recovery_readonly = False
        host._deadline = time.monotonic()+90; host.directory = Path('inert-writer-owner').absolute()
        host._api = Mock()
        self.scene = {'snapshot': {'schema': 'HH-BLENDER-FIXTURE-SCENE-1', 'objects': [],
            'units': {'system': 'METRIC', 'scale_length': 1.0}},
            'context': {'mode': 'OBJECT', 'active_id': None, 'selected_ids': []},
            'public_ack': False, 'undo_supported': True}
        self._revision()
        host.submit = Mock(side_effect=lambda command, **kwargs: self._row(command, copy.deepcopy(self.scene)))
        host.execute = Mock(side_effect=self.execute)
        host.arm_lease = Mock(side_effect=lambda value: value)
        def stopped():
            host._stopped = True; self.events.append('native-stop')
            return {'stopped': True, 'public_ack': False}
        host.stop = Mock(side_effect=stopped)
        self.native = object.__new__(DurableBlenderSession)
        self.native.host = host; self.native.directory = host.directory/'journal'
        self.native._held = self.native._stopped = False
        self.native._lock = threading.RLock(); self.native.clock = epoch_ms
        self.writer_journal = object.__new__(BlenderWriterJournal)
        self.writer_journal.path = self.native.directory/'blender-journal.jsonl'
        self.native.journal = self.writer_journal
        self.current_lease = None
        self.writer_journal.acquire_immediate = Mock(side_effect=self.acquire)
        self.writer_journal.check_running = Mock()
        self.writer_journal.check_lease = Mock(side_effect=self.check_lease)
        self.writer_journal.stop_writers = Mock(side_effect=lambda **kwargs: self.events.append('journal-stop'))
        def memory(path, binding):
            self.journal = MemoryJournal(binding=binding)
            append = self.journal._append
            def observed(row):
                append(row)
                self.events.append(row['receipt'].get('state', 'CONFIG'))
            self.journal._append = observed
            return self.journal
        replacement = patch.object(ledger_module, '_ClientJournal', side_effect=memory)
        replacement.start(); self.addCleanup(replacement.stop)
        self.owner = BlenderWriterClientOwner.from_session(self.native, project_id='blender.test')
        self.credential = self.owner.sessions.issue(operations=catalog.OPERATIONS)
        self.auth = 'Bearer '+self.credential.bearer
        self.kw = {'authorization': self.auth, 'catalog_digest': catalog.CATALOG_DIGEST}
        self.grant = self.owner.sessions.authenticate(self.auth)
        self.lease = self.owner.lease({'project_id': 'blender.test', 'access': 'write', 'ttl_ms': 20000}, **self.kw)
        self.events.clear(); host.submit.reset_mock()

    def _revision(self):
        self.scene['revision'] = module.queue.c.digest(self.scene['snapshot'])

    def _row(self, command, result, state='COMPLETED'):
        return {'command_id': command['command_id'], 'command_digest': module.queue.c.digest(command),
            'public_ack': False, 'state': state, 'result': result}

    def acquire(self, *, writer, now_ms, ttl_ms):
        old = self.current_lease
        if old is not None and old.owner != writer and old.expires_ms > now_ms:
            raise JournalError('LEASE_BUSY')
        self.current_lease = Lease(PROJECT, TARGET, writer, 1 if old is None else old.fencing_epoch+1, now_ms+ttl_ms)
        return self.current_lease

    def check_lease(self, lease, *, now_ms):
        if self.current_lease != lease or lease.expires_ms <= now_ms:
            raise JournalError('STALE_LEASE')

    def execute(self, command, **kwargs):
        self.events.append('effect')
        pending = self.journal._state().get(command['command_id'])
        self.assertIsNotNone(pending, 'native boundary reached before common intent')
        self.assertIsNone(pending['response'])
        if command['operation'] == catalog.READ:
            return self._row(command, copy.deepcopy(self.scene))
        if command['expected_revision'] != self.scene['revision'] or command['expected_context'] != self.scene['context']:
            return self._row(command, None, 'REJECTED')
        before = self.scene['revision']
        arguments = command['payload']
        size = arguments['size']; key = arguments['object_id']
        self.scene['snapshot']['objects'].append({'object_id': key, 'name': key, 'mesh_name': key+'.mesh',
            'location': [0, 0, 0], 'rotation': [0, 0, 0], 'scale': [1, 1, 1],
            'vertices': [[x*size[0]/2, y*size[1]/2, z*size[2]/2]
                         for x, y, z in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
                                         (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))],
            'faces': [list(face) for face in module.queue.base.FACES]})
        self.scene['snapshot']['objects'].sort(key=lambda row: row['object_id'])
        self._revision()
        return self._row(command, {'operation': command['operation'], 'before_revision': before,
            'native_operator_finished': True, 'public_ack': False, 'status': 'INTERNAL_UI_READBACK',
            'after': copy.deepcopy(self.scene)})

    def body(self, **changes):
        payload = {'expected_context': copy.deepcopy(self.scene['context']),
                   'arguments': {'object_id': 'box', 'size': [1, 2, 3]}}
        args = dict(command_id='Client:Create/One', project_id='blender.test', operation='mesh.create_box',
            lease_id=self.lease['lease_id'], fencing_epoch=self.lease['fencing_epoch'],
            expected_revision=self.owner.revision, target={'stable_id': catalog.TARGET},
            payload=payload, deadline_ms=epoch_ms()+3500)
        args.update(changes)
        args['payload_hash'] = module.digest(canonical_bytes(args['payload']))
        return Request(**args).as_dict()

    def submit(self, body=None, **kwargs):
        return self.owner.submit(body or self.body(), **(kwargs or self.kw))

    def lookup(self, key='Client:Create/One', **kwargs):
        return self.owner.lookup({'project_id': 'blender.test', 'command_id': key}, **(kwargs or self.kw))

    def stop(self):
        return self.owner.stop({'project_id': 'blender.test', 'command_id': 'control.stop.1'}, **self.kw)

    def test_constructor_requires_exact_native_durable(self):
        with self.assertRaisesRegex(SafetyViolation, 'EXACT_DURABLE'):
            BlenderWriterClientOwner.from_session({'host': self.host})
        with self.assertRaisesRegex(TypeError, 'from_session'):
            BlenderWriterClientOwner()

    def test_unregistered_core_token_and_wrong_catalog_have_no_intent_or_effect(self):
        raw = self.owner.sessions._issuer.issue(scopes=frozenset({'fixture.write'}))
        for kwargs in ({'authorization': 'Bearer '+raw.bearer, 'catalog_digest': catalog.CATALOG_DIGEST},
                       {'authorization': self.auth, 'catalog_digest': 'sha256:'+'0'*64},
                       {'authorization': 'Bearer invalid', 'catalog_digest': catalog.CATALOG_DIGEST}):
            with self.subTest(kind=kwargs['catalog_digest']), self.assertRaises(SafetyViolation):
                self.submit(**kwargs)
        self.host.execute.assert_not_called(); self.assertEqual(len(self.journal._records), 1)

    def test_default_credential_is_readonly_and_has_no_writer_discovery_or_lease(self):
        credential = self.owner.sessions.issue()
        kwargs = dict(self.kw, authorization='Bearer '+credential.bearer)
        discovery = self.owner.discover({'project_id': 'blender.test'}, **kwargs)
        self.assertEqual([item.operation for item in discovery.capabilities], [catalog.READ])
        with self.assertRaisesRegex(SafetyViolation, 'WRITER_GRANT_REQUIRED'):
            self.owner.lease({'project_id': 'blender.test', 'access': 'write', 'ttl_ms': 1000}, **kwargs)
        self.assertEqual(self.submit(**kwargs).code, 'BLENDER_OPERATION_FORBIDDEN')
        self.host.execute.assert_not_called(); self.assertEqual(len(self.journal._records), 1)

    def test_unknown_lease_guard_exit_holds_owner_and_durable_without_rearming(self):
        armed = self.host.arm_lease.call_count
        def lost(**kwargs):
            self.acquire(**kwargs)
            raise OSError('inert guard exit failed after visible native lease append')
        self.writer_journal.acquire_immediate.side_effect = lost
        with self.assertRaisesRegex(JournalError, 'BLENDER_WRITER_ADMISSION_UNKNOWN') as caught:
            self.owner.lease({'project_id': 'blender.test', 'access': 'write', 'ttl_ms': 10000}, **self.kw)
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertEqual(self.current_lease.fencing_epoch, 2)
        self.assertTrue(self.owner._held); self.assertTrue(self.native._held)
        self.assertEqual(self.host.arm_lease.call_count, armed)
        with self.assertRaises(SafetyViolation):
            self.owner.lease({'project_id': 'blender.test', 'access': 'write', 'ttl_ms': 10000}, **self.kw)
        self.host.execute.assert_not_called()

    def test_known_lease_busy_does_not_hold_original_writer(self):
        credential = self.owner.sessions.issue(operations=catalog.OPERATIONS)
        kwargs = dict(self.kw, authorization='Bearer '+credential.bearer)
        with self.assertRaisesRegex(JournalError, 'LEASE_BUSY') as caught:
            self.owner.lease({'project_id': 'blender.test', 'access': 'write', 'ttl_ms': 10000}, **kwargs)
        self.assertFalse(caught.exception.outcome_unknown)
        self.assertFalse(self.owner._held); self.assertFalse(self.native._held)
        self.assertEqual(self.submit().status, Status.COMMITTED)

    def test_discovery_filters_grant_and_excludes_unconnected_save_export(self):
        discovery = self.owner.discover({'project_id': 'blender.test'}, **self.kw)
        self.assertEqual({item.operation for item in discovery.capabilities}, module.SUPPORTED)
        for operation in ('scene.save', 'checkpoint.save', 'export.publish'):
            payload = {'expected_context': copy.deepcopy(self.scene['context']), 'arguments': {}}
            value = self.submit(self.body(command_id=operation, operation=operation, payload=payload))
            self.assertEqual(value.status, Status.REJECTED)
            self.assertEqual(value.code, 'BLENDER_OPERATION_NOT_CONNECTED')
        self.host.execute.assert_not_called(); self.assertEqual(len(self.journal._records), 1)

    def test_real_registered_lease_intent_before_effect_and_original_absolute_deadline(self):
        body = self.body(); result = self.submit(body)
        self.assertEqual(result.status, Status.COMMITTED)
        self.assertEqual(self.events, ['INTENT', 'effect', 'TERMINAL'])
        native, = self.host.execute.call_args.args
        kwargs = self.host.execute.call_args.kwargs
        self.assertEqual(kwargs['deadline_ms'], body['deadline_ms'])
        self.assertEqual(kwargs['lease'], {'fencing_epoch': self.current_lease.fencing_epoch,
                                         'expires_ms': self.current_lease.expires_ms})
        self.assertGreater(kwargs['timeout'], 0); self.assertLessEqual(kwargs['timeout'], 3.5)
        self.assertNotEqual(native['command_id'], body['command_id'])
        saved = self.journal._state()[native['command_id']]['intent']
        self.assertEqual(ledger_module.unchunk(saved['request_chunks'], ledger_module.MAX_REQUEST_BYTES), canonical_bytes(body))
        self.assertEqual(ledger_module.unchunk(saved['native_chunks'], module.queue.c.MAX_BYTES), module.queue.c.canonical(native))
        self.assertEqual(result.result_hash, module.digest(canonical_bytes(result.postconditions['observation'])))
        self.assertFalse(result.postconditions['public_ack']); self.assertFalse(result.postconditions['scene_state_durable'])
        self.assertTrue(result.postconditions['live_edits_unsaved'])
        self.assertEqual(len(self.scene['snapshot']['objects']), 1)

    def test_exact_duplicate_own_lookup_and_retry_after_lease_deadline_do_not_dispatch(self):
        body = self.body(); original = self.submit(body); wire = canonical_bytes(original.as_dict())
        retry = dict(body, lease_id='write.expired-or-replaced', fencing_epoch=999, deadline_ms=1)
        for value in (self.submit(body), self.submit(retry), self.lookup()):
            self.assertEqual(canonical_bytes(value.as_dict()), wire)
        self.assertEqual(self.host.execute.call_count, 1); self.assertEqual(len(self.scene['snapshot']['objects']), 1)

    def test_response_loss_and_reopened_memory_history_preserve_exact_terminal(self):
        body = self.body(); first = self.submit(body)
        reopened = MemoryJournal(binding=self.owner._ledger.binding, records=self.journal._records)
        self.owner._ledger._journal = reopened
        self.assertEqual(self.submit(body), first); self.assertEqual(self.lookup(), first)
        self.assertEqual(self.host.execute.call_count, 1)

    def test_pending_history_returns_unknown_without_redispatch(self):
        body = self.body(); request = Request.from_dict(body)
        native = parse_json(catalog.translate(request, binding=self.owner._ledger.binding, session_id=self.grant.session_id))
        admission = self.owner._ledger.begin(self.grant, request, native)
        self.assertFalse(admission.replayed)
        result = self.submit(body)
        self.assertEqual(result.status, Status.UNKNOWN); self.assertFalse(result.postconditions['dispatch_permitted'])
        self.assertEqual(result, self.lookup()); self.host.execute.assert_not_called()
        self.assertEqual(len(self.journal._records), 2)

    def test_conflicting_payload_or_revision_never_reuses_old_result(self):
        body = self.body(); self.submit(body)
        payload = copy.deepcopy(body['payload']); payload['arguments']['size'] = [2, 3, 4]
        for changes in ({'payload': payload}, {'expected_revision': 'sha256:'+'0'*64}):
            retry = dict(body, **changes); retry['payload_hash'] = module.digest(canonical_bytes(retry['payload']))
            retry.pop('digest', None)
            self.assertEqual(self.submit(retry).code, 'BLENDER_LEDGER_COMMAND_CONFLICT')
        self.assertEqual(self.host.execute.call_count, 1)

    def test_history_is_session_scoped_and_credential_rotation_retains_own_lookup(self):
        body = self.body(); first = self.submit(body)
        other = self.owner.sessions.issue(operations=catalog.OPERATIONS)
        other_kw = dict(self.kw, authorization='Bearer '+other.bearer)
        self.assertEqual(self.lookup(**other_kw).code, 'BLENDER_LEDGER_COMMAND_NOT_FOUND')
        self.assertNotEqual(self.submit(body, **other_kw).status, Status.COMMITTED)
        rotated = self.owner.sessions.rotate(self.credential)
        with self.assertRaises(SafetyViolation): self.lookup()
        new_kw = dict(self.kw, authorization='Bearer '+rotated.bearer)
        self.assertEqual(self.lookup(**new_kw), first); self.assertEqual(self.submit(body, **new_kw), first)
        self.assertEqual(self.host.execute.call_count, 1)

    def _other_writer_with_new_native_fence(self):
        credential = self.owner.sessions.issue(operations=catalog.OPERATIONS)
        kwargs = dict(self.kw, authorization='Bearer '+credential.bearer)
        previous = self.current_lease
        # Advance the inert acquisition clock beyond the old native lease;
        # this avoids sleeping and actually exercises production registration
        # of the new exact Lease returned by DurableBlenderSession.
        with patch.object(self.native, 'clock', return_value=previous.expires_ms+1):
            lease = self.owner.lease({'project_id': 'blender.test', 'access': 'write', 'ttl_ms': 10000}, **kwargs)
        self.assertGreater(lease['fencing_epoch'], previous.fencing_epoch)
        return kwargs, lease

    def test_public_command_id_is_reserved_project_wide_after_terminal(self):
        first_body = self.body(); first = self.submit(first_body)
        self.assertEqual(first.status, Status.COMMITTED)
        kwargs, lease = self._other_writer_with_new_native_fence()
        payload = {'expected_context': copy.deepcopy(self.scene['context']),
                   'arguments': {'object_id': 'another_box', 'size': [2, 3, 4]}}
        reused = self.body(command_id=first_body['command_id'], lease_id=lease['lease_id'],
                           fencing_epoch=lease['fencing_epoch'], payload=payload)
        result = self.submit(reused, **kwargs)
        self.assertEqual(result.status, Status.REJECTED)
        self.assertEqual(result.code, 'BLENDER_LEDGER_COMMAND_OWNER')
        self.assertNotIn('observation', result.postconditions)
        self.assertEqual(self.host.execute.call_count, 1)
        self.assertEqual(len(self.scene['snapshot']['objects']), 1)
        self.assertEqual(len(self.journal._records), 3)
        self.assertEqual(self.lookup(**kwargs).code, 'BLENDER_LEDGER_COMMAND_NOT_FOUND')
        self.assertEqual(self.lookup(), first)
        self.assertFalse(self.owner._held); self.assertFalse(self.owner._ledger._held)
        # Rejection came from project command ownership, not a broken grant or
        # stale fence: this second writer can use its own new public command ID.
        fresh = dict(reused, command_id='Client:Create/Two')
        self.assertEqual(self.submit(fresh, **kwargs).status, Status.COMMITTED)
        self.assertEqual(self.host.execute.call_count, 2)

    def test_public_command_id_is_reserved_project_wide_while_pending(self):
        body = self.body(); request = Request.from_dict(body)
        command = parse_json(catalog.translate(request, binding=self.owner._ledger.binding,
                                               session_id=self.grant.session_id))
        self.owner._ledger.begin(self.grant, request, command)
        kwargs, lease = self._other_writer_with_new_native_fence()
        reused = dict(body, lease_id=lease['lease_id'], fencing_epoch=lease['fencing_epoch'])
        result = self.submit(reused, **kwargs)
        self.assertEqual(result.status, Status.REJECTED)
        self.assertEqual(result.code, 'BLENDER_LEDGER_COMMAND_OWNER')
        self.assertNotIn('request_digest', result.postconditions)
        self.assertNotIn('intent_sha256', result.postconditions)
        self.assertEqual(self.lookup(**kwargs).code, 'BLENDER_LEDGER_COMMAND_NOT_FOUND')
        self.assertEqual(self.lookup().code, 'BLENDER_LEDGER_UNRESOLVED_INTENT')
        self.host.execute.assert_not_called(); self.assertEqual(len(self.journal._records), 2)
        self.assertFalse(self.owner._held); self.assertFalse(self.owner._ledger._held)

    def test_wrong_lease_stale_fence_deadline_revision_and_context_precede_intent(self):
        context = {'mode': 'EDIT_MESH', 'active_id': 'box', 'selected_ids': ['box']}
        payload = copy.deepcopy(self.body()['payload']); payload['expected_context'] = context
        for changes in ({'lease_id': 'write.forged'}, {'fencing_epoch': 999}, {'deadline_ms': 1},
                        {'expected_revision': 'sha256:'+'0'*64}, {'payload': payload}):
            with self.subTest(changes=changes):
                self.assertEqual(self.submit(self.body(**changes)).status, Status.REJECTED)
        self.host.execute.assert_not_called(); self.assertEqual(len(self.journal._records), 1)

    def test_source_drift_before_dispatch_has_no_intent_or_effect(self):
        self.source['changed.py'] = 'b'*64
        result = self.submit()
        self.assertEqual(result.status, Status.REJECTED); self.assertEqual(result.code, 'BLENDER_SOURCE_CHANGED')
        self.host.execute.assert_not_called(); self.assertEqual(len(self.journal._records), 1)

    def test_job_drift_before_dispatch_has_no_intent_or_effect(self):
        self.host._job.active_count.return_value = 0
        result = self.submit()
        self.assertEqual(result.status, Status.REJECTED); self.assertEqual(result.code, 'BLENDER_LIVE_JOB_REQUIRED')
        self.host.execute.assert_not_called(); self.assertEqual(len(self.journal._records), 1)

    def test_manual_native_revision_change_is_rejected_and_not_publicly_committed(self):
        body = self.body()
        self.scene['snapshot']['objects'].append({'object_id': 'manual', 'size': [2, 2, 2]}); self._revision()
        result = self.submit(body)
        self.assertEqual(result.status, Status.REJECTED); self.assertEqual(result.code, 'BLENDER_NATIVE_REJECTED')
        self.assertEqual(len(self.scene['snapshot']['objects']), 1)

    def test_native_response_wrong_identity_is_unknown_and_holds_fresh_work(self):
        def malformed(command, **kwargs):
            row = self.execute(command, **kwargs); row['command_id'] = 'foreign-command'; return row
        self.host.execute.side_effect = malformed
        body = self.body(); result = self.submit(body)
        self.assertEqual(result.status, Status.UNKNOWN); self.assertEqual(result.code, 'BLENDER_NATIVE_RESPONSE_BINDING')
        self.assertEqual(self.submit(body), result); self.assertEqual(self.lookup(), result)
        self.assertEqual(self.submit(self.body(command_id='second')).status, Status.REJECTED)
        self.assertEqual(self.host.execute.call_count, 1); self.assertTrue(self.owner.sessions._write_held)

    def test_native_malformed_revision_cannot_be_committed(self):
        def malformed(command, **kwargs):
            row = self.execute(command, **kwargs); row['result']['after']['revision'] = 'not-a-native-revision'; return row
        self.host.execute.side_effect = malformed
        result = self.submit()
        self.assertEqual(result.status, Status.UNKNOWN); self.assertEqual(result.code, 'BLENDER_NATIVE_REVISION_MISMATCH')
        self.assertTrue(self.owner._held)

    def test_native_float_revision_survives_jcs_integer_normalization(self):
        def ipc(command, **kwargs):
            native = self.execute(command, **kwargs)
            self.assertIs(type(native['result']['after']['snapshot']['units']['scale_length']), float)
            # Actual IPC canonicalizes numbers after native revision creation.
            return parse_json(canonical_bytes(native))
        self.host.execute.side_effect = ipc
        result = self.submit()
        self.assertEqual(result.status, Status.COMMITTED)
        observation = result.postconditions['observation']
        snapshot = observation['scene']['snapshot']
        self.assertIs(type(snapshot['units']['scale_length']), int)
        self.assertNotEqual(self.scene['revision'], module.queue.c.digest(snapshot))
        self.assertEqual(result.result_revision, self.scene['revision'])
        self.assertEqual(observation['native_revision'], self.scene['revision'])
        self.assertEqual(result.result_hash, module.digest(canonical_bytes(observation)))
        self.assertEqual(result.postconditions['hash_domain'], 'jcs-observation-v1')

    def test_native_context_drift_after_effect_is_unknown(self):
        def changed(command, **kwargs):
            row = self.execute(command, **kwargs)
            row['result']['after']['context'] = {'mode': 'OBJECT', 'active_id': 'box', 'selected_ids': ['box']}
            return row
        self.host.execute.side_effect = changed
        result = self.submit()
        self.assertEqual(result.status, Status.UNKNOWN); self.assertEqual(result.code, 'BLENDER_CONTEXT_DRIFT')
        self.assertTrue(self.owner._held)

    def test_source_drift_after_effect_is_unknown_and_hold_preserves_no_replay(self):
        def changed(command, **kwargs):
            row = self.execute(command, **kwargs); self.source['changed.py'] = 'b'*64; return row
        self.host.execute.side_effect = changed
        body = self.body(); result = self.submit(body)
        self.assertEqual(result.status, Status.UNKNOWN); self.assertEqual(result.code, 'BLENDER_SOURCE_CHANGED')
        self.assertEqual(self.lookup(), result); self.assertEqual(self.submit(body), result)
        self.assertTrue(self.owner._held); self.assertEqual(self.host.execute.call_count, 1)

    def test_native_held_is_unknown_and_retained_without_repeat(self):
        self.host.execute.side_effect = lambda command, **kwargs: self._row(command, None, 'HELD')
        body = self.body(); result = self.submit(body)
        self.assertEqual(result.status, Status.UNKNOWN); self.assertEqual(result.code, 'BLENDER_NATIVE_HELD')
        self.assertEqual(self.submit(body), result); self.assertEqual(self.lookup(), result)
        self.assertTrue(self.owner._held); self.assertEqual(self.host.execute.call_count, 1)

    def test_native_exception_after_effect_is_unknown_never_rejected_no_effect(self):
        def lost(command, **kwargs):
            self.execute(command, **kwargs); raise TimeoutError('inert lost native reply')
        self.host.execute.side_effect = lost
        body = self.body(); result = self.submit(body)
        self.assertEqual(result.status, Status.UNKNOWN); self.assertEqual(self.lookup(), result)
        self.assertEqual(self.submit(body), result); self.assertEqual(len(self.scene['snapshot']['objects']), 1)
        self.assertTrue(self.owner._held); self.assertEqual(self.host.execute.call_count, 1)

    def test_terminal_append_reply_loss_preserves_true_receipt_and_holds(self):
        def fail_after_effect(command, **kwargs):
            result = self.execute(command, **kwargs); self.journal.failure = 'after'; return result
        self.host.execute.side_effect = fail_after_effect
        finish = self.owner._ledger.finish
        self.owner._ledger.finish = Mock(wraps=finish)
        body = self.body(); immediate = self.submit(body)
        self.assertEqual(immediate.status, Status.UNKNOWN)
        self.assertEqual(immediate.code, 'BLENDER_LEDGER_TERMINAL_UNKNOWN')
        self.assertEqual(self.owner._ledger.finish.call_count, 1, 'a true terminal must not be overwritten by UNKNOWN')
        self.journal.failure = None
        historical = self.lookup()
        self.assertEqual(historical.status, Status.COMMITTED)
        self.assertEqual(historical.postconditions['observation']['scene'], self.scene)
        self.assertEqual(self.submit(body), historical)
        self.assertEqual(self.submit(self.body(command_id='second')).status, Status.REJECTED)
        self.assertTrue(self.owner._held); self.assertTrue(self.owner.sessions._write_held)
        self.assertEqual(self.host.execute.call_count, 1); self.assertEqual(len(self.journal._records), 3)

    def test_intent_append_reply_loss_has_no_effect_and_retains_unknown(self):
        self.journal.failure = 'after'; body = self.body(); result = self.submit(body)
        self.assertEqual(result.status, Status.UNKNOWN); self.assertTrue(self.owner._held)
        self.journal.failure = None
        self.assertEqual(self.lookup().code, 'BLENDER_LEDGER_UNRESOLVED_INTENT')
        self.assertEqual(self.submit(body).code, 'BLENDER_LEDGER_UNRESOLVED_INTENT')
        self.host.execute.assert_not_called(); self.assertEqual(len(self.journal._records), 2)

    def test_stop_before_dispatch_blocks_fresh_work_and_keeps_controls(self):
        stopped = self.stop(); self.assertEqual(stopped.status, Status.COMMITTED)
        result = self.submit(); self.assertEqual(result.status, Status.REJECTED)
        self.host.execute.assert_not_called(); self.assertEqual(len(self.journal._records), 1)
        self.assertEqual(self.owner.discover({'project_id': 'blender.test'}, **self.kw).capabilities, ())
        self.assertEqual(self.lookup().code, 'BLENDER_LEDGER_COMMAND_NOT_FOUND')
        self.assertEqual(self.events, ['native-stop', 'journal-stop'])

    def test_stop_between_persisted_intent_and_effect_rejects_without_native_dispatch(self):
        original = self.owner._ledger.begin
        def stopped(*args):
            admitted = original(*args); self.stop(); return admitted
        self.owner._ledger.begin = stopped
        result = self.submit()
        self.assertEqual(result.status, Status.REJECTED); self.host.execute.assert_not_called()
        self.assertEqual(self.lookup(), result); self.assertEqual(len(self.journal._records), 3)

    def test_revoke_between_persisted_intent_and_effect_rejects_without_native_dispatch(self):
        original = self.owner._ledger.begin
        def revoked(*args):
            admitted = original(*args); self.owner.sessions.revoke(self.credential); return admitted
        self.owner._ledger.begin = revoked
        result = self.submit()
        self.assertEqual(result.status, Status.UNKNOWN); self.assertFalse(result.postconditions['delivery_authorized'])
        self.assertTrue(result.postconditions['receipt_retained']); self.host.execute.assert_not_called()
        self.assertEqual(len(self.journal._records), 3)
        terminal, = self.journal._state().values()
        self.assertEqual(Response.from_dict(parse_json(terminal['response'])).status, Status.REJECTED)

    def test_stop_after_observed_effect_retains_truthful_committed_receipt(self):
        def stopped(command, **kwargs):
            observed = self.execute(command, **kwargs); self.stop(); return observed
        self.host.execute.side_effect = stopped
        body = self.body(); result = self.submit(body)
        self.assertEqual(result.status, Status.COMMITTED); self.assertEqual(self.lookup(), result)
        self.assertEqual(self.submit(body), result); self.assertEqual(self.host.execute.call_count, 1)
        self.assertEqual(len(self.scene['snapshot']['objects']), 1)

    def test_revoke_after_observed_effect_does_not_relabel_mutation_as_no_effect(self):
        def revoked(command, **kwargs):
            observed = self.execute(command, **kwargs); self.owner.sessions.revoke(self.credential); return observed
        self.host.execute.side_effect = revoked
        result = self.submit()
        self.assertEqual(result.status, Status.UNKNOWN)
        self.assertFalse(result.postconditions['delivery_authorized']); self.assertTrue(result.postconditions['receipt_retained'])
        self.assertNotIn('observation', result.postconditions)
        with self.assertRaises(SafetyViolation): self.lookup()
        terminals = [entry for entry in self.journal._state().values() if entry['response'] is not None]
        self.assertEqual(len(terminals), 1)
        historical = Response.from_dict(parse_json(terminals[0]['response']))
        self.assertEqual(historical.status, Status.COMMITTED)
        self.assertEqual(historical.postconditions['observation']['scene'], self.scene)

    def test_revoke_after_terminal_append_denies_delivery_without_discarding_receipt(self):
        finish = self.journal.finish
        def revoked(*args):
            raw = finish(*args); self.owner.sessions.revoke(self.credential); return raw
        self.journal.finish = revoked
        result = self.submit()
        self.assertEqual(result.status, Status.UNKNOWN); self.assertNotIn('observation', result.postconditions)
        self.assertFalse(result.postconditions['delivery_authorized'])
        terminal, = self.journal._state().values()
        self.assertEqual(Response.from_dict(parse_json(terminal['response'])).status, Status.COMMITTED)

    def test_revoke_after_historical_lookup_read_denies_observation_delivery(self):
        self.submit(); lookup = self.owner._ledger.lookup
        def revoked(*args):
            raw = lookup(*args); self.owner.sessions.revoke(self.credential); return raw
        self.owner._ledger.lookup = revoked
        result = self.lookup()
        self.assertEqual(result.status, Status.UNKNOWN); self.assertNotIn('observation', result.postconditions)
        self.assertFalse(result.postconditions['delivery_authorized'])
        self.assertEqual(self.host.execute.call_count, 1)

    def test_concurrent_duplicate_pending_and_stop_do_not_wait_for_native_work(self):
        entered = threading.Event(); release = threading.Event(); values = []
        def blocked(command, **kwargs):
            entered.set()
            if not release.wait(2): raise AssertionError('inert work not released')
            return self._row(command, None, 'CANCELLED')
        self.host.execute.side_effect = blocked; body = self.body()
        worker = threading.Thread(target=lambda: values.append(self.submit(body))); worker.start()
        try:
            self.assertTrue(entered.wait(1))
            duplicate = self.submit(body)
            self.assertEqual(duplicate.status, Status.UNKNOWN); self.assertFalse(duplicate.postconditions['dispatch_permitted'])
            self.assertEqual(self.submit(self.body(command_id='different')).code, 'BLENDER_CLIENT_BUSY')
            begin = time.monotonic(); stopped = self.stop()
            self.assertLess(time.monotonic()-begin, .5)
            self.assertEqual(stopped.status, Status.COMMITTED)
            self.assertEqual(stopped.postconditions['write_phase'], 'DISPATCHING')
        finally:
            release.set(); worker.join(2)
        self.assertFalse(worker.is_alive()); self.assertEqual(len(values), 1)
        self.assertEqual(values[0].status, Status.CANCELED)
        self.assertEqual(self.host.execute.call_count, 1)

    def test_readonly_inspection_uses_registered_read_lease_and_common_ledger(self):
        lease = self.owner.lease({'project_id': 'blender.test', 'access': 'read', 'ttl_ms': 3000}, **self.kw)
        body = self.body(operation=catalog.READ, payload={}, lease_id=lease['lease_id'],
                         fencing_epoch=0, deadline_ms=epoch_ms()+1500)
        result = self.submit(body)
        self.assertEqual(result.status, Status.COMMITTED); self.assertTrue(result.postconditions['read_only'])
        self.assertIsNone(self.host.execute.call_args.kwargs['lease'])
        self.assertEqual(self.events, ['INTENT', 'effect', 'TERMINAL'])

    def test_fresh_read_stop_after_observation_denies_delivery_but_keeps_historical_truth(self):
        lease = self.owner.lease({'project_id': 'blender.test', 'access': 'read', 'ttl_ms': 3000}, **self.kw)
        body = self.body(operation=catalog.READ, payload={}, lease_id=lease['lease_id'],
                         fencing_epoch=0, deadline_ms=epoch_ms()+1500)
        def stopped(command, **kwargs):
            row = self.execute(command, **kwargs); self.stop(); return row
        self.host.execute.side_effect = stopped
        result = self.submit(body)
        self.assertEqual(result.status, Status.UNKNOWN); self.assertNotIn('observation', result.postconditions)
        self.assertFalse(result.postconditions['delivery_authorized'])
        historical = self.lookup(); self.assertEqual(historical.status, Status.COMMITTED)
        self.assertTrue(historical.postconditions['read_only']); self.assertEqual(self.host.execute.call_count, 1)


if __name__ == '__main__':
    unittest.main()
