"""Authenticated coordinator for one prepared immutable replay.

No paths, scripts, executables or alternate traces arrive through the wire.
Durable command intent precedes launch; runtime completion is a separate
lookup. Stop latches before persistence/drain and a new connection cannot resume.
Inspection is explicitly retained completed evidence, not a live debugger.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time

from studio.host.core.journal import Journal, JournalError, JournalLimits
from studio.host.core.limits import SafetyViolation
from studio.host.core.transport import epoch_ms
from studio.protocol.core import Request, Response, Status, canonical_bytes
from . import contract, inspector, native_runner as native
from .backend import PreparedPlay, BackendError
from .session import ReplaySession, ReplaySessionError


def need(value, code):
    if not value:
        raise SafetyViolation(code)


class ReplayService:
    """Fresh owner only. Persisted pending state never opens a writable restart."""
    def __init__(self, backend: PreparedPlay, *, project_id='fixture.gt06'):
        need(type(backend) is PreparedPlay and backend.status()['phase'] == 'PREPARED', 'REPLAY_PREPARED_BACKEND_REQUIRED')
        self.backend, self.project_id = backend, project_id
        self._binding = canonical_bytes(backend.binding)
        self.prepared = contract.PreparedRuntime(backend.binding, tuple(c['label'] for c in backend.trace.value['captures']))
        self._deadline = epoch_ms() + 120_000
        self.sessions = ReplaySession(project_id, backend.root, catalog_digest=contract.CATALOG_DIGEST,
            binding=backend.binding, owner_deadline_ms=self._deadline)
        parent = backend.root / 'service'
        parent.mkdir(exist_ok=False)
        self._journal = Journal(parent / 'commands.jsonl', limits=JournalLimits(max_records=512, max_pending_commands=2))
        self._guard = threading.RLock()
        self._work = threading.Lock()
        self._jobs, self._leases, self._uncertain = {}, {}, {}
        self._view = None
        self._stop_persistence = 'NOT_REQUESTED'
        self._stop_thread = None
        self._launch_thread = None
        self._closed = False
        self._shutdown = threading.Event()
        self._watchdog = threading.Thread(target=self._expire, name='hh-replay-owner-expiry', daemon=True)
        self._watchdog.start()

    @property
    def binding(self):
        return json.loads(self._binding)

    def _expire(self):
        while not self._shutdown.wait(.05):
            if epoch_ms() >= self._deadline:
                self.sessions.halt()
                self.backend.stop()
                return

    def _auth(self, body, operation, authorization, catalog_digest, fields):
        need(type(body) is dict and set(body) == set(fields), 'REPLAY_ENVELOPE')
        grant = self.sessions.authorize(authorization, operation, project_id=body.get('project_id'),
            catalog_digest=catalog_digest, binding=self.binding)
        with self._guard:
            need(not self._closed, 'REPLAY_SERVICE_CLOSED')
        return grant

    def discover(self, body, *, authorization, catalog_digest):
        grant = self.sessions.authenticate(authorization)
        need(type(body) is dict and set(body) == {'project_id'} and body['project_id'] == self.project_id
            and catalog_digest == contract.CATALOG_DIGEST, 'REPLAY_DISCOVERY_BINDING')
        need(not self._closed, 'REPLAY_SERVICE_CLOSED')
        enabled = contract.OPERATIONS & frozenset(grant.operations)
        if self.sessions.status()['stopped']:
            enabled = frozenset()
        return contract.discovery(self.project_id, runtime_enabled=enabled).as_dict()

    def lease(self, body, *, authorization, catalog_digest):
        # A lease itself has no effect authority. Every command also needs its
        # separately scoped current grant, registered lease and exact snapshot.
        grant = self.sessions.authenticate(authorization)
        need(type(body) is dict and set(body) == {'project_id', 'ttl_ms'}
            and body['project_id'] == self.project_id and catalog_digest == contract.CATALOG_DIGEST,
            'REPLAY_LEASE_ENVELOPE')
        need(bool(contract.OPERATIONS & frozenset(grant.operations))
            and not self.sessions.status()['stopped'] and not self._closed, 'REPLAY_STOPPED')
        ttl = body['ttl_ms']
        need(type(ttl) is int and 0 < ttl <= 30_000, 'REPLAY_LEASE_TTL')
        need(self._work.acquire(blocking=False), 'REPLAY_WORK_BUSY')
        try:
            need(len(self._leases) < 64, 'REPLAY_LEASE_CAP')
            lease = self._journal.acquire_lease(project_id=self.project_id,
                target=self.prepared.binding['runtime_instance_id'], owner=grant.session_id,
                now_ms=epoch_ms(), ttl_ms=min(ttl, self._deadline - epoch_ms()))
            lease_id = 'lease.' + secrets.token_hex(16)
            with self._guard:
                self._leases[lease_id] = (lease, grant)
            return {'lease_id': lease_id, 'fencing_epoch': lease.fencing_epoch, 'expires_ms': lease.expires_ms,
                'expected_revision': self.prepared.revision, 'binding': self.binding, 'public_ack': False}
        finally:
            self._work.release()

    @staticmethod
    def _receipt(command_id, status, code, **facts):
        return Response(Status(status), code, command_id, postconditions={'public_ack': False, **facts}).as_dict()

    def submit(self, body, *, authorization, catalog_digest):
        request = Request.from_dict(body)
        grant = self.sessions.authorize(authorization, request.operation, project_id=request.project_id,
            catalog_digest=catalog_digest, binding=self.binding)
        self.sessions.validate_public_identifier(request.command_id)
        need(not self._closed, 'REPLAY_SERVICE_CLOSED')
        need(self._work.acquire(blocking=False), 'REPLAY_WORK_BUSY')
        permit = None
        admitted_here = False
        try:
            with self._guard:
                previous = self._jobs.get(request.command_id)
                if previous:
                    need(previous['digest'] == request.digest, 'REPLAY_COMMAND_ID_COLLISION')
                    return self._lookup_receipt(request.command_id)
                lease_row = self._leases.get(request.lease_id)
            need(lease_row is not None and lease_row[1] is grant, 'REPLAY_LEASE_REQUIRED')
            lease = lease_row[0]
            need(lease.owner == grant.session_id, 'REPLAY_LEASE_REQUIRED')
            self._journal.check_lease(lease, now_ms=epoch_ms())
            request = contract.validate_request(body, contract.ReplayContext(self.project_id, self.prepared,
                request.lease_id, lease.fencing_epoch, lease.expires_ms, epoch_ms(),
                runtime_enabled=contract.OPERATIONS, stopped=self.sessions.status()['stopped']))
            need(request.operation != 'play.start' or self.backend.status()['phase'] == 'PREPARED', 'REPLAY_ALREADY_LAUNCHED')
            permit = self.sessions.reserve(grant, command_id=request.command_id, request_digest=request.digest,
                operation=request.operation, deadline_ms=request.deadline_ms)
            pending = self._receipt(request.command_id, 'ACCEPTED_PENDING', 'REPLAY_ADMITTED', next_action='lookup_same_command_id')
            self.sessions.encode_output(pending)
            self._journal.append_command(project_id=self.project_id, command_id=request.command_id,
                digest=request.digest, receipt=pending, now_ms=epoch_ms(), pending=True)
            with self._guard:
                self._jobs[request.command_id] = {'digest': request.digest, 'request': request, 'grant': grant}
                admitted_here = True
            # No journal lock survives into engine or image I/O.
            self._journal.check_lease(lease, now_ms=epoch_ms())
            self.sessions.start_effect(permit)
            if request.operation == 'play.start':
                self.backend.start()
                self.sessions.finish_effect(permit, known=True)
                permit = None
                self._launch_thread = threading.Thread(target=self._complete_launch,
                    args=(request, grant), name='hh-replay-completion', daemon=True)
                try:
                    self._launch_thread.start()
                except BaseException:
                    self.sessions.halt()
                    self.backend.stop()
                    raise
                return pending
            if request.operation == 'play.inspect':
                view = self._retained_view()
                facts = {'observation': inspector.query_view(view, dict(request.payload)), 'historical': True}
            else:
                need(self.backend.status()['phase'] == 'COMPLETED', 'REPLAY_CAPTURE_PENDING')
                self._retained_view()
                report = self._bound_report()
                row = report['captures'][request.payload['label']]
                png = native.read_regular(self.backend.project / 'out' / (request.payload['label'] + '.png'), 1024 * 1024)
                need(native.sha(png) == row['sha256'], 'REPLAY_CAPTURE_CHANGED')
                facts = {'artifact': contract.artifact_reference(kind='capture', sha256=row['sha256'], size_bytes=len(png)),
                    'label': row['label'], 'observed_tick': row['observed_tick'], 'phase': row['phase'],
                    'binding': self.binding, 'process': self.backend.status()['process'], 'historical': True}
            self.sessions.finish_effect(permit, known=True)
            permit = None
            self.sessions.check_delivery(grant, operation=request.operation, deadline_ms=request.deadline_ms)
            reply = self._receipt(request.command_id, 'COMMITTED', 'REPLAY_RETAINED_RESULT', **facts)
            self.sessions.encode_output(reply)
            self._journal.finish_command(project_id=self.project_id, command_id=request.command_id,
                status='COMMITTED', receipt=reply, now_ms=epoch_ms())
            return reply
        except BaseException:
            if permit is not None:
                state = self.sessions.permit_status(permit)
                if state == 'RESERVED':
                    self.sessions.cancel_reserved(permit)
                elif state == 'STARTED':
                    self.sessions.finish_effect(permit, known=False)
                    self.backend.stop()
            if admitted_here:
                self._record_unknown(request.command_id)
            raise
        finally:
            self._work.release()

    def _retained_view(self):
        need(self.backend.status()['phase'] == 'COMPLETED', 'REPLAY_INSPECTION_PENDING')
        if self._view is None:
            root = self.backend.root
            raw = native.read_regular(root / 'capture.json')
            need(self.backend._result == json.loads(raw), 'REPLAY_CAPTURE_ANCHOR_CHANGED')
            self._view = inspector.register_view(native.read_regular(self.backend.project / 'out/report.json'),
                native_capture_raw=raw, native_capture_sha256=native.sha(raw), trace=self.backend.trace,
                binding=self.binding, process_raw=native.read_regular(root / 'process-metrics.json'),
                project=self.backend.project, config_speed=3.0)
        return self._view

    def _bound_report(self):
        capture_raw = native.read_regular(self.backend.root / 'capture.json')
        need(self.backend._result == json.loads(capture_raw), 'REPLAY_CAPTURE_ANCHOR_CHANGED')
        raw = native.read_regular(self.backend.project / 'out/report.json')
        need(native.sha(raw) == self.backend._result['report_sha256'], 'REPLAY_REPORT_CHANGED')
        return json.loads(raw)

    def _complete_launch(self, request, grant):
        try:
            while not self.backend._done.wait(.025):
                if epoch_ms() >= request.deadline_ms or self.sessions.status()['stopped']:
                    self.backend.stop()
            state = self.backend.status()
            try:
                self.sessions.check_delivery(grant, operation='play.start', deadline_ms=request.deadline_ms)
                valid = state['phase'] == 'COMPLETED'
            except ReplaySessionError:
                valid = False
            if valid:
                root = self.backend.root
                capture_raw = native.read_regular(root / 'capture.json')
                capture = json.loads(capture_raw)
                need(capture == self.backend._result, 'REPLAY_CAPTURE_ANCHOR_CHANGED')
                self._bound_report()
                reply = self._receipt(request.command_id, 'COMMITTED', 'REPLAY_NATIVE_COMPLETED',
                    binding=self.binding, process=state['process'],
                    native_capture_sha256=native.sha(capture_raw),
                    artifact=contract.artifact_reference(kind='observation', sha256=capture['report_sha256'],
                        size_bytes=(self.backend.project / 'out/report.json').stat().st_size))
                status = 'COMMITTED'
            else:
                status = 'CANCELED' if state['phase'] in ('STOPPED', 'STOPPED_AFTER_COMPLETION') else 'UNKNOWN'
                reply = self._receipt(request.command_id, status, 'REPLAY_NOT_ACKNOWLEDGED',
                    observed_phase=state['phase'], next_action='inspect_retained_evidence_do_not_replay')
            self.sessions.encode_output(reply)
            self._journal.finish_command(project_id=self.project_id, command_id=request.command_id,
                status=status, receipt=reply, now_ms=epoch_ms())
        except BaseException:
            self.sessions.halt()
            self.backend.stop()
            self._record_unknown(request.command_id)

    def _record_unknown(self, command_id):
        unknown = self._receipt(command_id, 'UNKNOWN', 'REPLAY_RECONCILE_REQUIRED',
            next_action='lookup_same_command_id_do_not_replay', terminal_persistence='UNCONFIRMED')
        # Publish a bounded in-memory observation before disk I/O. A failed
        # writer must not leave lookup advertising a still-running command.
        with self._guard:
            self._uncertain[command_id] = canonical_bytes(unknown)
        try:
            durable = self._receipt(command_id, 'UNKNOWN', 'REPLAY_RECONCILE_REQUIRED',
                next_action='lookup_same_command_id_do_not_replay', terminal_persistence='DURABLE')
            self._journal.finish_command(project_id=self.project_id, command_id=command_id,
                status='UNKNOWN', receipt=durable, now_ms=epoch_ms())
        except BaseException:
            # An earlier finish may already be durable. Lookup below prefers
            # that immutable terminal receipt; never overwrite it on a retry.
            self.sessions.halt()
            self.backend.stop()

    def _lookup_receipt(self, command_id):
        with self._guard:
            overlay = self._uncertain.get(command_id)
        try:
            receipt = self._journal.lookup(project_id=self.project_id, command_id=command_id,
                now_ms=epoch_ms())['receipt']
        except BaseException:
            if overlay is not None:
                return json.loads(overlay)
            raise
        if receipt['status'] == 'ACCEPTED_PENDING' and overlay is not None:
            return json.loads(overlay)
        return receipt

    def lookup(self, body, *, authorization, catalog_digest):
        self._auth(body, 'control.lookup', authorization, catalog_digest, {'project_id', 'command_id'})
        self.sessions.validate_public_identifier(body['command_id'])
        try:
            receipt = self._lookup_receipt(body['command_id'])
        except JournalError as error:
            need(error.code == 'COMMAND_NOT_FOUND', error.code)
            return self._receipt(body['command_id'], 'UNKNOWN', 'REPLAY_COMMAND_NOT_FOUND')
        if receipt['status'] == 'ACCEPTED_PENDING':
            return {**receipt, 'postconditions': {**receipt['postconditions'], 'runtime': self.backend.status()}}
        return receipt

    def stop(self, body, *, authorization, catalog_digest):
        grant = self._auth(body, 'control.stop', authorization, catalog_digest, {'project_id', 'command_id'})
        self.sessions.validate_public_identifier(body['command_id'])
        self.sessions.stop(grant)
        observed = self.backend.stop()
        with self._guard:
            if self._stop_thread is None:
                self._stop_persistence = 'PENDING'
                self._stop_thread = threading.Thread(target=self._persist_stop, args=(body['command_id'],),
                    name='hh-replay-stop-persistence', daemon=True)
                self._stop_thread.start()
            return {'stopped': True, 'draining': observed['draining'], 'stop_persistence': self._stop_persistence,
                    'runtime_instance_id': self.binding['runtime_instance_id'], 'public_ack': False}

    def _persist_stop(self, command_id):
        try:
            digest = 'sha256:' + hashlib.sha256(canonical_bytes({'operation': 'control.stop', 'binding': self.binding})).hexdigest()
            self._journal.append_command(project_id=self.project_id, command_id=command_id, digest=digest,
                receipt=self._receipt(command_id, 'COMMITTED', 'REPLAY_STOP_LATCHED', stopped=True), now_ms=epoch_ms())
            self._stop_persistence = 'DURABLE'
        except BaseException:
            self._stop_persistence = 'UNKNOWN'

    def close(self):
        self.sessions.halt()
        self.backend.close()
        for thread in (self._launch_thread, self._stop_thread):
            if thread is not None and thread.ident is not None:
                thread.join(3)
                need(not thread.is_alive(), 'REPLAY_SERVICE_DRAIN_HELD')
        need(self._work.acquire(timeout=3), 'REPLAY_SERVICE_WORK_HELD')
        try:
            if self._view is not None:
                inspector.close_view(self._view)
                self._view = None
            self._closed = True
        finally:
            self._work.release()
        self._shutdown.set()
        self._watchdog.join(1)
        need(not self._watchdog.is_alive(), 'REPLAY_WATCHDOG_HELD')
