"""Unadvertised, registered writer authority for one exact live native owner.

This layer never dispatches Blender work or persists public receipts. The owner
must persist its client-ledger intent, recheck revision/context, consume an
effect permit, and use the original absolute deadline and exact native Lease.
Native fencing/cancellation and terminal ledger persistence remain mandatory.
"""
from dataclasses import asdict, dataclass
import hashlib
import re
import secrets
import threading
import time
import weakref

from studio.host.core.journal import Lease
from studio.host.core.transport import epoch_ms
from studio.protocol.core import canonical_bytes
from .client_session import BlenderClientSession, need
from .durable_session import DurableBlenderSession, PROJECT, TARGET
from .ui_host import BlenderUIHost, BLENDER_SHA256, source_files
from .writer_journal import BlenderWriterJournal
from . import client_write_catalog as catalog

_REGISTER = threading.Lock()
_SESSIONS = weakref.WeakKeyDictionary()


@dataclass(frozen=True)
class BlenderWriteLease:
    session_id: str
    lease_id: str
    fencing_epoch: int
    expires_ms: int


class _WritePermit:
    __slots__ = ()


class BlenderWriterClientSession(BlenderClientSession):
    def __init__(self, *args, **kwargs):
        raise TypeError('use BlenderWriterClientSession.from_durable')

    @classmethod
    def from_durable(cls, durable, *, project_id=PROJECT, source_sha256, owner_deadline_ms):
        need(type(durable) is DurableBlenderSession, 'BLENDER_EXACT_DURABLE_REQUIRED')
        host = durable.host
        need(type(host) is BlenderUIHost, 'BLENDER_EXACT_HOST_REQUIRED')
        need(type(durable.journal) is BlenderWriterJournal, 'BLENDER_EXACT_WRITER_JOURNAL_REQUIRED')
        need(type(source_sha256) is str and re.fullmatch(r'sha256:[0-9a-f]{64}', source_sha256),
             'BLENDER_INVALID_SOURCE')
        need(type(owner_deadline_ms) is int, 'BLENDER_OWNER_DEADLINE_REQUIRED')
        self = object.__new__(cls)
        self._durable, self._host, self._journal = durable, host, durable.journal
        self._process, self._job = host._process, host._job
        self._source = canonical_bytes(host._source)
        self.source_sha256 = source_sha256
        need(source_sha256 == 'sha256:' + hashlib.sha256(self._source).hexdigest(), 'BLENDER_SOURCE_CHANGED')
        self._pin = canonical_bytes({'pid': host.pid, 'generation': host._session, 'binary_sha256': BLENDER_SHA256})
        self._native_deadline = host._deadline
        self._directory = host.directory
        self._journal_path = durable.journal.path
        # The public epoch horizon cannot extend the exact native monotonic one.
        end_ms = epoch_ms() + int((host._deadline - time.monotonic()) * 1000)
        BlenderClientSession.__init__(self, project_id, host.directory,
            owner_deadline_ms=min(owner_deadline_ms, end_ms),
            catalog_digest=catalog.CATALOG_DIGEST, catalog_profile=catalog)
        self._binding = (self.project_id, self.catalog_digest, self.source_sha256, self._owner_deadline_ms)
        self._writer_labels = {}
        self._writer_leases = {}
        self._write_active = None
        self._write_held = False
        self._check_native()
        self._journal.check_running()
        with _REGISTER:
            registered = _SESSIONS.get(host)
            need(registered is None or registered() is None, 'BLENDER_WRITER_HOST_ALREADY_REGISTERED')
            _SESSIONS[host] = weakref.ref(self)
        return self

    def _check_binding(self):
        need(self._catalog is catalog and
             (self.project_id, self.catalog_digest, self.source_sha256, self._owner_deadline_ms) == self._binding,
             'BLENDER_WRITER_BINDING_CHANGED')

    def _check_native_identity(self):
        """In-memory identity/latches only; safe for the final authorization lock."""
        self._check_binding()
        host, durable = self._host, self._durable
        need(type(durable) is DurableBlenderSession and durable.host is host and durable.journal is self._journal
             and type(self._journal) is BlenderWriterJournal and type(host) is BlenderUIHost
             and host._process is self._process and host._job is self._job,
             'BLENDER_WRITER_OWNER_CHANGED')
        need(host.directory == self._directory and durable.directory == self._directory / 'journal'
             and self._journal.path == self._journal_path == durable.directory / 'blender-journal.jsonl',
             'BLENDER_WRITER_OWNER_CHANGED')
        need(host._process is not None and not host._closed, 'BLENDER_LIVE_OWNER_REQUIRED')
        need(type(host.pid) is int and host.pid > 0 and type(host._session) is str
             and re.fullmatch(r'[0-9a-f]{32}', host._session)
             and canonical_bytes({'pid': host.pid, 'generation': host._session, 'binary_sha256': BLENDER_SHA256}) == self._pin
             and host._deadline == self._native_deadline, 'BLENDER_OWNER_IDENTITY_CHANGED')
        need(not host._held and not host._stopped and not durable._held and not durable._stopped
             and not getattr(host, '_recovery_readonly', False), 'BLENDER_WRITER_OWNER_HELD_OR_STOPPED')
        need(time.monotonic() < self._native_deadline, 'BLENDER_OWNER_EXPIRED')
        need(canonical_bytes(host._source) == self._source, 'BLENDER_SOURCE_CHANGED')

    def _check_native(self):
        """All potentially blocking process/source checks run without _mutex."""
        self._check_native_identity()
        host = self._host
        need(host._process.poll() is None, 'BLENDER_LIVE_OWNER_REQUIRED')
        active = host._job.active_count()
        job = host._job.snapshot()
        need(job['assigned'] is True and job['configured'] is True and job['tainted'] is False
             and job['closed'] is False and job['handle_retained'] is True and type(active) is int
             and active >= 2 and job['active_count'] == active, 'BLENDER_LIVE_JOB_REQUIRED')
        need(self._source == canonical_bytes(source_files()), 'BLENDER_SOURCE_CHANGED')

    def _check_writer(self, grant, operation=None):
        self._check_binding()
        self._check_grant(grant, operation)
        need(bool(set(grant.operations) & catalog.WRITE_OPERATIONS), 'BLENDER_WRITER_GRANT_REQUIRED')
        need(operation is None or operation in catalog.WRITE_OPERATIONS, 'BLENDER_WRITER_OPERATION_REQUIRED')
        need(not self._stopped.is_set(), 'BLENDER_STOPPED')
        need(not self._write_held, 'BLENDER_WRITER_HELD')
        need(epoch_ms() < self._owner_deadline_ms, 'BLENDER_OWNER_EXPIRED')
        self._check_native_identity()

    def writer_label(self, grant):
        """Trusted owner uses this random name when acquiring its native lease.

        Knowing the name grants no authority. register_writer also requires the
        exact registered public grant and an actual journal-current native Lease.
        """
        with self._mutex:
            self._check_writer(grant)
            row = self._writer_labels.get(grant.session_id)
            if row is None:
                row = (grant, 'client-writer-' + secrets.token_hex(16))
                need(all(value[1] != row[1] for value in self._writer_labels.values()), 'BLENDER_WRITER_LABEL_CONFLICT')
                self._writer_labels[grant.session_id] = row
            need(row[0] is grant, 'BLENDER_WRITER_GRANT_REQUIRED')
            return row[1]

    def _check_native_lease(self, native, raw):
        need(type(native) is Lease and canonical_bytes(asdict(native)) == raw, 'BLENDER_NATIVE_LEASE_CHANGED')
        self._check_native()
        self._journal.check_running()
        self._journal.check_lease(native, now_ms=epoch_ms())
        need(canonical_bytes(asdict(native)) == raw, 'BLENDER_NATIVE_LEASE_CHANGED')

    def register_writer(self, grant, native_lease):
        """Bind a lease returned by the trusted durable owner; no native arming."""
        with self._mutex:
            self._check_writer(grant)
            label = self._writer_labels.get(grant.session_id)
            need(label is not None and label[0] is grant, 'BLENDER_WRITER_LABEL_REQUIRED')
            need(type(native_lease) is Lease and native_lease.project_id == PROJECT and native_lease.target == TARGET
                 and native_lease.owner == label[1] and type(native_lease.fencing_epoch) is int
                 and native_lease.fencing_epoch > 0 and type(native_lease.expires_ms) is int,
                 'BLENDER_NATIVE_LEASE_REQUIRED')
            raw = canonical_bytes(asdict(native_lease))
        self._check_native_lease(native_lease, raw)
        with self._mutex:
            self._check_writer(grant)
            need(self._writer_labels.get(grant.session_id) is label, 'BLENDER_WRITER_LABEL_REQUIRED')
            need(canonical_bytes(asdict(native_lease)) == raw and epoch_ms() < native_lease.expires_ms,
                 'BLENDER_NATIVE_LEASE_CHANGED')
            old = self._writer_leases.get(grant.session_id)
            if old is not None and old['native_raw'] == raw:
                need(old['native'] is native_lease, 'BLENDER_NATIVE_LEASE_REQUIRED')
                self._check_write_lease(grant, old['lease'])
                return old['lease']
            need(self._write_active is None and self._active is None, 'BLENDER_WRITER_BUSY')
            need(self._lease_count < 32, 'BLENDER_LEASE_LIMIT')
            lease = BlenderWriteLease(grant.session_id, 'write.' + label[1].removeprefix('client-writer-'),
                native_lease.fencing_epoch, min(native_lease.expires_ms, self._owner_deadline_ms,
                    self._grants[grant.session_id][2].credential.expires_ms, epoch_ms() + catalog.MAX_LEASE_MS))
            self._writer_leases[grant.session_id] = {'lease': lease, 'raw': canonical_bytes(asdict(lease)),
                'native': native_lease, 'native_raw': raw, 'grant': grant}
            self._lease_count += 1
            return lease

    def _check_write_lease(self, grant, lease):
        row = self._writer_leases.get(grant.session_id)
        need(type(lease) is BlenderWriteLease and row is not None and row['lease'] is lease and row['grant'] is grant
             and row['raw'] == canonical_bytes(asdict(lease)), 'BLENDER_WRITE_LEASE_REQUIRED')
        need(type(row['native']) is Lease and row['native_raw'] == canonical_bytes(asdict(row['native'])),
             'BLENDER_NATIVE_LEASE_CHANGED')
        need(epoch_ms() < lease.expires_ms, 'BLENDER_DEADLINE_EXPIRED')
        return row

    def resolve_writer_lease(self, grant, lease_id, fencing_epoch):
        with self._mutex:
            self._check_writer(grant)
            row = self._writer_leases.get(grant.session_id)
            need(row is not None and type(lease_id) is str and type(fencing_epoch) is int
                 and row['lease'].lease_id == lease_id and row['lease'].fencing_epoch == fencing_epoch,
                 'BLENDER_WRITE_LEASE_REQUIRED')
            self._check_write_lease(grant, row['lease'])
            return row['lease']

    def _check_write_local(self, grant, lease, operation, deadline_ms):
        self._check_writer(grant, operation)
        row = self._check_write_lease(grant, lease)
        # Export is a separate bounded publication owner, not a UI queue step.
        maximum = catalog.MAX_LEASE_MS if operation in catalog.WRITE_OPERATIONS-catalog.EDIT_OPERATIONS else catalog.MAX_UI_MS
        self._check_deadline(lease, deadline_ms, maximum)
        return row

    def check_write(self, grant, lease, *, operation, deadline_ms):
        with self._mutex:
            row = self._check_write_local(grant, lease, operation, deadline_ms)
        self._check_native_lease(row['native'], row['native_raw'])
        with self._mutex:
            need(self._check_write_local(grant, lease, operation, deadline_ms) is row, 'BLENDER_WRITE_LEASE_REQUIRED')

    def start_write(self, grant, lease, *, operation, deadline_ms):
        self.check_write(grant, lease, operation=operation, deadline_ms=deadline_ms)
        with self._mutex:
            self._check_write_local(grant, lease, operation, deadline_ms)
            need(self._write_active is None and self._active is None, 'BLENDER_WRITER_BUSY')
            permit = _WritePermit()
            self._write_active = {'permit': permit, 'grant': grant, 'lease': lease, 'operation': operation,
                'deadline_ms': deadline_ms, 'phase': 'PREPARED'}
            return permit

    def _permit(self, permit):
        need(type(permit) is _WritePermit and self._write_active is not None
             and self._write_active['permit'] is permit, 'BLENDER_WRITE_PERMIT_REQUIRED')
        return self._write_active

    def check_write_permit(self, permit):
        with self._mutex:
            active = self._permit(permit)
        self.check_write(active['grant'], active['lease'], operation=active['operation'], deadline_ms=active['deadline_ms'])
        with self._mutex:
            need(self._permit(permit) is active, 'BLENDER_WRITE_PERMIT_REQUIRED')
            self._check_write_local(active['grant'], active['lease'], active['operation'], active['deadline_ms'])

    def begin_write_effect(self, permit):
        """Consume PREPARED once; return the exact native Lease, never a copy.

        Stop/revoke arriving before this transition denies fresh authorization.
        DISPATCHING is already authorized and may drain after Stop/revoke; this
        marker alone never proves whether a native effect ran or was canceled.
        """
        self.check_write_permit(permit)
        with self._mutex:
            active = self._permit(permit)
            row = self._check_write_local(active['grant'], active['lease'], active['operation'], active['deadline_ms'])
            need(active['phase'] == 'PREPARED', 'BLENDER_WRITE_ALREADY_DISPATCHING')
            active['phase'] = 'DISPATCHING'
            return row['native']

    def finish_write(self, permit, *, outcome_known=True):
        need(type(outcome_known) is bool, 'BLENDER_WRITE_OUTCOME_REQUIRED')
        with self._mutex:
            self._permit(permit)
            if not outcome_known:
                self._write_held = True
            self._write_active = None

    def start_read(self, grant, lease, *, deadline_ms):
        with self._mutex:
            need(self._write_active is None, 'BLENDER_WRITER_BUSY')
            return super().start_read(grant, lease, deadline_ms=deadline_ms)

    def _invalidate_leases(self, session_id):
        super()._invalidate_leases(session_id)
        self._writer_leases.pop(session_id, None)
        self._writer_labels.pop(session_id, None)

    def _activity(self):
        return {**super()._activity(), 'write_draining': self._write_active is not None,
                'write_phase': None if self._write_active is None else self._write_active['phase']}

    def encode_output(self, value):
        with self._mutex:
            encoded = super().encode_output(value)
            # Secret history can grow after a ledger terminal was persisted.
            # Deny changed successful bytes at the final wire boundary too.
            if type(value) is dict and (value.get('status') == 'COMMITTED'
                    or value.get('schema') == 'HH-BLENDER-CLIENT-PREVIEW-1'):
                need(encoded == canonical_bytes(value), 'BLENDER_SENSITIVE_OBSERVATION')
            return encoded
