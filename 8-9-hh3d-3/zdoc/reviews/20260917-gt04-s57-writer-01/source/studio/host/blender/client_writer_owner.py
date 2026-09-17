"""Explicitly constructed GT04 client integration candidate for unsaved edits.

The common ledger is the only public command intent/receipt store. The existing
durable session supplies native writer fencing, not a second command journal.
Save/export and durable public ACK remain unavailable on this owner.
"""
from dataclasses import replace
import re
import threading

from studio.host.core.journal import JournalError
from studio.host.core.limits import SafetyViolation
from studio.host.core.transport import epoch_ms
from studio.protocol.core import Response, Status, ValidationError, canonical_bytes, parse_json
from .client_owner import BlenderClientOwner, digest, shape
from .client_session import need
from .client_writer_session import BlenderWriterClientSession
from .client_ledger import BlenderClientLedger
from .durable_session import DurableBlenderSession
from . import client_write_catalog as catalog
from .client_preview import actual_diff, normalize_preview
from .publication_owner import BlenderPublicationOwner
from . import publication_state

queue = catalog.queue
SUPPORTED = catalog.EDIT_OPERATIONS | {catalog.READ}


def response(status, code, key, **details):
    return Response(status, code, key, postconditions={
        'public_ack': False, 'ledger_receipt_only': True, 'scene_state_durable': False,
        'durable_publication': False, **details})


class BlenderWriterClientOwner:
    def __init__(self):
        raise TypeError('use BlenderWriterClientOwner.from_session')

    @classmethod
    def from_session(cls, durable, *, project_id='blender.owned-fixture', publication=None):
        need(type(durable) is DurableBlenderSession, 'BLENDER_EXACT_DURABLE_REQUIRED')
        publication_binding = None
        if publication is not None:
            need(type(publication) is BlenderPublicationOwner and publication.session is durable
                 and publication.host is durable.host and not publication._closed
                 and not publication._readonly and not publication._held,
                 'BLENDER_EXACT_PUBLICATION_OWNER_REQUIRED')
            with publication._mutex:
                state = publication._refresh()
                need(state['phase'] == 'EMPTY' and not state['stopped']
                     and state['config']['generation'] == durable.host._session
                     and state['config']['source_sha256'] == publication_state.sha(canonical_bytes(durable.host._source)),
                     'BLENDER_PUBLICATION_BINDING')
                publication_binding = (publication.storage_id, canonical_bytes(state['config']))
        # Registration first proves the exact native host, Job, source and
        # initial observation. Its unused read issuer is replaced before any
        # credentials are returned. Keep this registered owner for the ledger.
        observed = BlenderClientOwner.from_host(durable.host, project_id=project_id)
        self = object.__new__(cls)
        self._read_owner, self._durable, self._host = observed, durable, durable.host
        self.project_id = project_id
        self.catalog_digest = catalog.CATALOG_DIGEST
        self._source_sha256 = observed._source_sha256
        self.sessions = BlenderWriterClientSession.from_durable(durable, project_id=project_id,
            source_sha256=self._source_sha256, owner_deadline_ms=observed.sessions._owner_deadline_ms)
        observed.sessions = self.sessions
        observed.catalog_digest = self.catalog_digest
        self._ledger = BlenderClientLedger.from_owner(observed)
        self._work = threading.Lock()
        self._mutex = threading.Lock()
        self._held = False
        self._stop_pending = False
        self._stop_wire = None
        self._publication = publication
        self._publication_binding = publication_binding
        self._supported = SUPPORTED | ({'export.publish'} if publication is not None else set())
        self._check_native()
        return self

    @property
    def revision(self):
        return self._read_owner.revision

    def _check_native(self, *, control=False):
        need(type(self._durable) is DurableBlenderSession and self._durable.host is self._host
             and self._read_owner._host is self._host and self._read_owner.sessions is self.sessions
             and self._read_owner.catalog_digest == self.catalog_digest == catalog.CATALOG_DIGEST,
             'BLENDER_WRITER_OWNER_CHANGED')
        if self._publication is not None:
            publisher = self._publication
            need(type(publisher) is BlenderPublicationOwner and publisher.session is self._durable
                 and publisher.host is self._host and not publisher._closed
                 and (publisher.storage_id, canonical_bytes(publisher._state['config'])) == self._publication_binding,
                 'BLENDER_PUBLICATION_BINDING')
        self._read_owner._check_native(control=control)
        if not control:
            need(not self._held and not self._durable._held and not self._durable._stopped,
                 'BLENDER_WRITER_OWNER_HELD_OR_STOPPED')
            self.sessions._check_native()

    def _hold(self):
        self._held = True
        self._read_owner._held = True

    def _auth(self, body, authorization, catalog_digest, operation=None, keys=None):
        if keys is not None:
            shape(body, keys)
        need(type(body) is dict, 'BLENDER_INVALID_ENVELOPE')
        grant = self.sessions.authenticate(authorization)
        need(body.get('project_id') == self.project_id and catalog_digest == self.catalog_digest,
             'BLENDER_GRANT_BINDING')
        if operation is not None:
            grant = self.sessions.authorize(authorization, operation,
                project_id=self.project_id, catalog_digest=catalog_digest)
        return grant

    def discover(self, body, *, authorization, catalog_digest):
        grant = self._auth(body, authorization, catalog_digest, keys={'project_id'})
        self._check_native(control=self.sessions._stopped.is_set())
        live = not self.sessions._stopped.is_set() and not self._held
        result = catalog.discovery(self.project_id, source_sha256=self._source_sha256,
            readable=live and catalog.READ in grant.operations,
            writable=live and bool(set(grant.operations) & catalog.WRITE_OPERATIONS))
        return replace(result, capabilities=tuple(item for item in result.capabilities
            if item.operation in self._supported and item.operation in grant.operations))

    def lease(self, body, *, authorization, catalog_digest):
        grant = self._auth(body, authorization, catalog_digest,
            keys={'project_id', 'access', 'ttl_ms'})
        need(body['access'] in ('read', 'write'), 'BLENDER_INVALID_LEASE')
        ttl = body['ttl_ms']
        need(type(ttl) is int and 0 < ttl <= catalog.MAX_LEASE_MS, 'BLENDER_INVALID_LEASE')
        need(self._work.acquire(blocking=False), 'BLENDER_CLIENT_BUSY')
        try:
            self._check_native()
            if body['access'] == 'read':
                lease = self.sessions.read_lease(grant, ttl_ms=ttl)
            else:
                need(bool(set(grant.operations) & (self._supported - {catalog.READ})), 'BLENDER_WRITER_GRANT_REQUIRED')
                label = self.sessions.writer_label(grant)
                try:
                    native = self._durable.acquire_writer(label, ttl_ms=ttl)
                    lease = self.sessions.register_writer(grant, native)
                except BaseException as error:
                    uncertain = (getattr(error, 'outcome_unknown', False) or self._durable._held
                        or not isinstance(error, (SafetyViolation, JournalError)))
                    if uncertain:
                        self._hold()
                        self._durable._held = True
                        failure = JournalError('BLENDER_WRITER_ADMISSION_UNKNOWN')
                        failure.outcome_unknown = True
                        raise failure from error
                    raise
            return {'lease_id': lease.lease_id, 'fencing_epoch': lease.fencing_epoch,
                'expires_ms': lease.expires_ms, 'access': body['access'], 'revision': self.revision,
                'target': {'stable_id': catalog.TARGET}, 'catalog_digest': self.catalog_digest,
                'public_ack': False, 'scene_state_durable': False}
        finally:
            self._work.release()

    def _observed(self, value):
        shape(value, {'snapshot', 'revision', 'context', 'public_ack', 'undo_supported'})
        need(value['public_ack'] is False and value['undo_supported'] is True,
             'BLENDER_NATIVE_READBACK_UNKNOWN')
        # The native revision names Blender's float-preserving JSON domain.
        # IPC uses JCS and normalizes 1.0/-0.0, so recomputing that native hash
        # from this decoded snapshot would reject valid real observations.
        need(type(value['revision']) is str and re.fullmatch(r'sha256:[0-9a-f]{64}', value['revision']),
             'BLENDER_NATIVE_REVISION_MISMATCH')
        shape(value['context'], {'mode', 'active_id', 'selected_ids'})
        need(value['context']['mode'] in ('OBJECT', 'EDIT_MESH'), 'BLENDER_NATIVE_READBACK_UNKNOWN')
        raw = canonical_bytes(value)
        need(len(raw) <= catalog.MAX_WIRE // 2, 'BLENDER_READBACK_CAP')
        return parse_json(raw)

    def _native_result(self, row, command, before):
        need(type(row) is dict and row.get('command_id') == command['command_id']
             and row.get('command_digest') == queue.c.digest(command) and row.get('public_ack') is False,
             'BLENDER_NATIVE_RESPONSE_BINDING')
        state = row.get('state')
        need(state in ('COMPLETED', 'REJECTED', 'EXPIRED', 'CANCELLED', 'HELD'),
             'BLENDER_NATIVE_RESPONSE_STATE')
        if state != 'COMPLETED':
            return state, None
        value = row.get('result')
        if command['operation'] == catalog.READ:
            after = self._observed(value)
            need(canonical_bytes(after) == canonical_bytes(before), 'BLENDER_STALE_REVISION')
        else:
            need(type(value) is dict and value.get('operation') == command['operation']
                 and value.get('before_revision') == before['revision']
                 and value.get('native_operator_finished') is True and value.get('public_ack') is False
                 and value.get('status') == 'INTERNAL_UI_READBACK', 'BLENDER_NATIVE_POSTCONDITION')
            after = self._observed(value['after'])
            need(after['context'] == before['context'], 'BLENDER_CONTEXT_DRIFT')
        return state, after

    def _success(self, request, before, after):
        observation = {'native_revision': after['revision'], 'scene': after, 'pid': self._host.pid,
            'generation': self._host._session, 'source_sha256': self._source_sha256}
        changes = (actual_diff(before, after, operation=request.operation)
                   if request.operation in catalog.EDIT_OPERATIONS else None)
        result = Response(Status.COMMITTED, 'BLENDER_CLIENT_READBACK', request.command_id,
            after['revision'], digest(canonical_bytes(observation)), {
                'observation': observation, 'hash_domain': 'jcs-observation-v1',
                'actual_diff': changes, 'affected_files': [],
                'before_revision': before['revision'], 'public_ack': False, 'ledger_receipt_only': True,
                'scene_state_durable': False, 'durable_publication': False,
                'live_edits_unsaved': request.operation != catalog.READ,
                'read_only': request.operation == catalog.READ})
        raw = canonical_bytes(result.as_dict())
        need(len(raw) <= catalog.MAX_WIRE and self.sessions.encode_output(result.as_dict()) == raw,
             'BLENDER_SENSITIVE_OBSERVATION')
        return result

    def preview(self, body, *, authorization, catalog_digest):
        """Inspect native preconditions without consuming an apply ID or intent.

        PREPARED reserves only this owner's in-flight work slot. The advisory
        response confers no authority: submit revalidates the same Request and
        obtains its own effect permit after the common ledger INTENT.
        """
        grant = self._auth(body, authorization, catalog_digest)
        request = catalog.validate_request(body, project_id=self.project_id,
                                           source_sha256=self._source_sha256)
        self.sessions._check_grant(grant, request.operation)
        need(request.operation in catalog.EDIT_OPERATIONS, 'BLENDER_PREVIEW_OPERATION_UNSUPPORTED')
        command = parse_json(catalog.translate(request, binding=self._ledger.binding,
                                               session_id=grant.session_id))
        need(self._work.acquire(blocking=False), 'BLENDER_CLIENT_BUSY')
        permit = None
        try:
            self._check_native()
            before = parse_json(self._read_owner._baseline)
            need(request.expected_revision == before['revision'], 'BLENDER_STALE_REVISION')
            need(canonical_bytes(request.payload['expected_context']) == canonical_bytes(before['context']),
                 'BLENDER_CONTEXT_DRIFT')
            lease = self.sessions.resolve_writer_lease(grant, request.lease_id, request.fencing_epoch)
            permit = self.sessions.start_write(grant, lease, operation=request.operation,
                                              deadline_ms=request.deadline_ms)
            self.sessions.check_write_permit(permit)
            row = self._host.preview(command, lease={'fencing_epoch': lease.fencing_epoch,
                'expires_ms': self._native_preview_lease(grant, lease).expires_ms},
                deadline_ms=request.deadline_ms, ttl_ms=catalog.MAX_UI_MS)
            result = normalize_preview(request, command, row, source_sha256=self._source_sha256,
                                       generation=self._host._session)
            need(canonical_bytes(row['before']) == canonical_bytes(before), 'BLENDER_STALE_REVISION')
            self._check_native()
            self.sessions.check_write_permit(permit)
            # No native or journal work under the final grant/Stop gate.
            with self.sessions._mutex:
                self.sessions._check_write_local(grant, lease, request.operation, request.deadline_ms)
                raw = canonical_bytes(result)
                need(len(raw) <= catalog.MAX_WIRE and self.sessions.encode_output(result) == raw,
                     'BLENDER_SENSITIVE_OBSERVATION')
                return result
        finally:
            try:
                if permit is not None:
                    self.sessions.finish_write(permit)
            finally:
                self._work.release()

    def _native_preview_lease(self, grant, lease):
        # Exact native lease remains private; preview does not transition the
        # reserved permit into DISPATCHING merely to recover its wire fence.
        with self.sessions._mutex:
            return self.sessions._check_write_lease(grant, lease)['native']

    def _deliver(self, grant, raw, *, fresh_read=None):
        """Authorize delivery separately from recording an already-run effect.

        The short in-memory gate linearizes delivery with revoke/rotation. No
        native call or journal flush holds the session mutex. Historical lookup
        remains valid after Stop, but a fresh read still obeys its read permit.
        """
        value = Response.from_dict(parse_json(raw))
        try:
            with self.sessions._mutex:
                self.sessions._check_grant(grant)
                if fresh_read is not None and value.status is Status.COMMITTED:
                    lease, deadline = fresh_read
                    self.sessions.check_read(grant, lease, deadline_ms=deadline)
                need(self.sessions.encode_output(value.as_dict()) == raw, 'BLENDER_SENSITIVE_OBSERVATION')
                return value
        except (SafetyViolation, ValidationError) as error:
            return response(Status.UNKNOWN, error.code, value.command_id, receipt_retained=True,
                delivery_authorized=False)

    def _record_terminal(self, admission, result):
        try:
            return self._ledger.finish(admission.permit, result)
        except Exception:
            # The true receipt may already be persisted. Never try to replace
            # it with UNKNOWN after losing an append/barrier/guard-release reply.
            self._hold()
            return None

    def _publish(self, request, command, before, native_lease, permit):
        publisher = self._publication
        need(publisher is not None, 'BLENDER_OPERATION_NOT_CONNECTED')
        raw = publisher.publish(command, native_lease, deadline_ms=request.deadline_ms,
                                phase_guard=lambda: self.sessions.check_write_permit(permit))
        result = parse_json(raw)
        with publisher._mutex:
            state = publisher._refresh()
            need(state['phase'] == 'TERMINAL' and state['intent']['request'] == command
                 and state['intent']['request_sha256'] == publication_state.sha(canonical_bytes(command))
                 and raw == canonical_bytes(state['terminal']['response']), 'BLENDER_PUBLICATION_TERMINAL_BINDING')
            if result['status'] == 'REJECTED':
                return response(Status.REJECTED, 'BLENDER_PUBLICATION_PREPARE_REJECTED', request.command_id)
            need(result['status'] == 'COMMITTED', 'BLENDER_PUBLICATION_TERMINAL_BINDING')
            manifest, artifacts = publisher.read_selected()
            need(canonical_bytes(manifest['snapshot']) == canonical_bytes(before['snapshot'])
                 and manifest['scene_revision'] == request.expected_revision
                 and manifest['generation'] == self._host._session
                 and canonical_bytes(manifest['source_files']) == canonical_bytes(self._host._source)
                 and set(artifacts) == set(publication_state.NAMES), 'BLENDER_PUBLICATION_READBACK_BINDING')
            for name, data in artifacts.items():
                need(result['artifacts'][name] == {'sha256': publication_state.sha(data), 'size_bytes': len(data)},
                     'BLENDER_PUBLICATION_ARTIFACT_BINDING')
            publication = {'storage_id': publisher.storage_id, 'generation': self._host._session,
                'source_sha256': self._source_sha256, 'native_revision': request.expected_revision,
                'receipt': result, 'receipt_sha256': digest(raw),
                'selector_version': state['terminal']['selector_version']}
        self._check_native_after_effect()
        common = Response(Status.COMMITTED, 'BLENDER_CLIENT_PUBLICATION', request.command_id,
            request.expected_revision, digest(canonical_bytes(publication)), {
                'publication': publication, 'hash_domain': 'jcs-protected-publication-v1',
                'affected_files': [*publication_state.NAMES, 'manifest.json', 'active.json'],
                'public_ack': False, 'ledger_receipt_only': True, 'scene_state_durable': False,
                'durable_publication': True, 'live_scene_recovered': False,
                'durability_scope': 'checked protected bundle; not writable GUI restart'})
        wire = canonical_bytes(common.as_dict())
        need(len(wire) <= catalog.MAX_WIRE and self.sessions.encode_output(common.as_dict()) == wire,
             'BLENDER_SENSITIVE_OBSERVATION')
        return common

    def submit(self, body, *, authorization, catalog_digest):
        grant = self._auth(body, authorization, catalog_digest)
        key = body.get('command_id', 'transport.request')
        self.sessions.validate_public_identifier(key)
        try:
            request = catalog.validate_request(body, project_id=self.project_id, source_sha256=self._source_sha256)
            self.sessions._check_grant(grant, request.operation)
            need(request.operation in self._supported, 'BLENDER_OPERATION_NOT_CONNECTED')
            native_raw = catalog.translate(request, binding=self._ledger.binding, session_id=grant.session_id)
            command = parse_json(native_raw)
        except (ValidationError, SafetyViolation, JournalError) as error:
            return response(Status.REJECTED, error.code, key)
        # Historical attempts never obtain a fresh permit, including while an
        # earlier dispatch is active. The ledger serializes its own bounded I/O.
        try:
            old = self._ledger.replay(grant, request, command)
            if old is not None:
                return self._deliver(grant, old.response)
        except (ValidationError, SafetyViolation, JournalError) as error:
            if getattr(error, 'outcome_unknown', False):
                self._hold()
            return response(Status.UNKNOWN if getattr(error, 'outcome_unknown', False)
                else Status.REJECTED, error.code, key)
        if not self._work.acquire(blocking=False):
            return response(Status.REJECTED, 'BLENDER_CLIENT_BUSY', key)
        admission = permit = None
        write = request.operation != catalog.READ
        dispatched = False
        known = True
        try:
            self._check_native()
            before = parse_json(self._read_owner._baseline)
            need(request.expected_revision == before['revision'], 'BLENDER_STALE_REVISION')
            if write:
                need(canonical_bytes(request.payload['expected_context']) == canonical_bytes(before['context']),
                     'BLENDER_CONTEXT_DRIFT')
                lease = self.sessions.resolve_writer_lease(grant, request.lease_id, request.fencing_epoch)
                permit = self.sessions.start_write(grant, lease, operation=request.operation,
                    deadline_ms=request.deadline_ms)
            else:
                lease = self.sessions.resolve_lease(grant, request.lease_id, request.fencing_epoch)
                permit = self.sessions.start_read(grant, lease, deadline_ms=request.deadline_ms)
            admission = self._ledger.begin(grant, request, command)
            if admission.replayed:
                return self._deliver(grant, admission.response)
            self._check_native()
            if write:
                native_lease = self.sessions.begin_write_effect(permit)
                fence = {'fencing_epoch': native_lease.fencing_epoch, 'expires_ms': native_lease.expires_ms}
            else:
                self.sessions.check_read(grant, lease, deadline_ms=request.deadline_ms)
                fence = None
            # The original epoch bound is forwarded through IPC and checked on
            # Blender's main thread. No relative TTL can renew this request.
            remaining = min(catalog.MAX_UI_MS, request.deadline_ms - epoch_ms())
            need(remaining > 0, 'BLENDER_DEADLINE_EXPIRED')
            dispatched = True
            if request.operation == 'export.publish':
                result = self._publish(request, command, before, native_lease, permit)
                raw = self._record_terminal(admission, result)
                if raw is None:
                    known = False
                    return response(Status.UNKNOWN, 'BLENDER_LEDGER_TERMINAL_UNKNOWN', key)
                return self._deliver(grant, raw)
            row = self._host.execute(command, timeout=remaining / 1000,
                lease=fence, deadline_ms=request.deadline_ms)
            state, after = self._native_result(row, command, before)
            if state == 'COMPLETED':
                self._check_native_after_effect()
                result = self._success(request, before, after)
                # Stop/revoke after effect do not turn a real mutation into a
                # fictitious no-effect rejection. Retain its terminal receipt;
                # the current authenticated caller controls later delivery.
                self._read_owner._baseline = canonical_bytes(after)
                self._read_owner.revision = after['revision']
            elif state == 'HELD':
                known = False
                self._hold()
                result = response(Status.UNKNOWN, 'BLENDER_NATIVE_HELD', key)
            else:
                result = response(Status.CANCELED if state == 'CANCELLED' else Status.REJECTED,
                    'BLENDER_NATIVE_' + state, key)
            raw = self._record_terminal(admission, result)
            if raw is None:
                known = False
                return response(Status.UNKNOWN, 'BLENDER_LEDGER_TERMINAL_UNKNOWN', key)
            return self._deliver(grant, raw, fresh_read=None if write else (lease, request.deadline_ms))
        except Exception as error:
            known = not dispatched and not getattr(error, 'outcome_unknown', False)
            if not known:
                self._hold()
            code = error.code if isinstance(error, (SafetyViolation, ValidationError, JournalError)) else 'BLENDER_CLIENT_UNKNOWN'
            result = response(Status.REJECTED if known else Status.UNKNOWN, code, key)
            if admission is not None and admission.permit is not None:
                raw = self._record_terminal(admission, result)
                if raw is None:
                    known = False
                    return response(Status.UNKNOWN, 'BLENDER_LEDGER_TERMINAL_UNKNOWN', key)
                return self._deliver(grant, raw)
            return result
        finally:
            try:
                if permit is not None:
                    if write:
                        self.sessions.finish_write(permit, outcome_known=known)
                    else:
                        self.sessions.finish_read(permit)
            finally:
                self._work.release()

    def _check_native_after_effect(self):
        # A completed observation can legitimately drain after Stop. Verify
        # the identity and source without requiring the stopped flag to clear.
        self._check_native(control=True)
        need(self._read_owner._source == canonical_bytes(self._host._source), 'BLENDER_SOURCE_CHANGED')
        from .ui_host import source_files
        need(self._read_owner._source == canonical_bytes(source_files()), 'BLENDER_SOURCE_CHANGED')

    def lookup(self, body, *, authorization, catalog_digest):
        grant = self._auth(body, authorization, catalog_digest, 'control.lookup', {'project_id', 'command_id'})
        try:
            return self._deliver(grant, self._ledger.lookup(grant, body['command_id']))
        except JournalError as error:
            return response(Status.UNKNOWN if error.outcome_unknown else Status.REJECTED, error.code, body['command_id'])

    def stop(self, body, *, authorization, catalog_digest):
        grant = self._auth(body, authorization, catalog_digest, 'control.stop', {'project_id', 'command_id'})
        key = body['command_id']
        self.sessions.validate_public_identifier(key)
        state = self.sessions.stop(grant)
        with self._mutex:
            if self._stop_wire is not None:
                value = parse_json(self._stop_wire)
                value['command_id'] = key
                return Response.from_dict(value)
            if self._stop_pending:
                return response(Status.ACCEPTED_PENDING, 'BLENDER_STOP_PENDING', key, **state)
            self._stop_pending = True
        try:
            self._check_native(control=True)
            # Durable Stop enters native control before waiting on its journal.
            native = self._publication.stop() if self._publication is not None else self._durable.stop()
            need(native == {'stopped': True, 'public_ack': False}, 'BLENDER_STOP_UNKNOWN')
            result = response(Status.COMMITTED, 'BLENDER_STOP_OBSERVED', key, **state)
        except Exception:
            self._hold()
            result = response(Status.UNKNOWN, 'BLENDER_STOP_UNKNOWN', key, **state)
        with self._mutex:
            self._stop_wire = canonical_bytes(result.as_dict())
            self._stop_pending = False
        return result
