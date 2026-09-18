"""One custody-bound GT05 staged snapshot, with read-only crash reconciliation.

The installed provider validates actual captures, complete catalog/payload
bindings and all GT05 gates. No caller paths, completion flags, active editor,
general GLB intake or GT04 profile extensions enter this API.
"""
from __future__ import annotations

import threading
import time
import uuid

from studio.protocol.core import canonical_bytes, parse_json
from studio.host.core.custody import WitnessCustody, identity_from, identity_value
from studio.host.core.custody_registry import RegistryCustody
from studio.host.core.private_events import PrivateEventLog
from studio.host.core.private_store import PrivateBlobStore
from studio.host.core.safe_replace import ProtectedFileRoot
from studio.host.core.limits import SafePathResolver
from studio.host.core.journal import Journal, JournalError, Lease
from studio.host.blender.deadline import AbsoluteDeadline
from . import snapshot_state as model
from .snapshot_state import VerifiedSnapshot, SnapshotError

need = model.need


def epoch_ms():
    return int(time.time() * 1000)


def version(value):
    return {'identity': identity_value(value.identity), 'sha256': value.sha256}


class SnapshotOwner:
    def __init__(self):
        self.registry = self.custody = self.files = self.store = self.log = None
        self.journal = self.provider = self.current_source = None
        self._mutex = threading.RLock()
        self._stop = threading.Event()
        self._validating = threading.Event()
        self._pending = None
        self._held = self._closed = False
        self._readonly = True
        self._head = None
        self._state = {}
        self._extra = []

    @classmethod
    def create(cls, parent, *, journal, provider, current_source):
        need(type(journal) is Journal and callable(provider) and callable(current_source), 'SNAPSHOT_TRUSTED_OWNER_REQUIRED')
        source = current_source()
        model.hash_value(source)
        SafePathResolver(parent)
        owner = cls()
        owner.journal, owner.provider, owner.current_source = journal, provider, current_source
        try:
            RegistryCustody.provision_base()
            owner.storage_id = uuid.uuid4().hex
            owner.registry = RegistryCustody.create(owner.storage_id)
            owner.custody = WitnessCustody(owner.registry, storage_id=owner.storage_id, project_id=model.PROJECT, create=True)
            owner.files = ProtectedFileRoot.create(parent)
            owner.store = PrivateBlobStore.create(parent)
            owner.log = PrivateEventLog.create(parent)
            owner.custody.activate(file_root=owner.files.root, file_identity=owner.files.root_identity,
                                   blob_root=owner.store.root, blob_identity=owner.store.root_identity,
                                   event_root=owner.log.root, event_binding=owner.log.binding())
            owner.log.bind_custody(owner.custody)
            owner._readonly = False
            owner._head = owner.log.binding().witnessed
            owner._append('CONFIG', storage_id=owner.storage_id, profile=model.PROFILE, source_sha256=source)
            return owner
        except BaseException as error:
            owner._failed_init(error)

    @classmethod
    def reopen(cls, storage_id):
        owner = cls()
        owner.storage_id = storage_id
        try:
            owner.registry = RegistryCustody.reopen(storage_id)
            owner.custody = WitnessCustody(owner.registry, storage_id=storage_id, project_id=model.PROJECT)
            record = owner.custody.record
            need(record['phase'] == 'READY', 'SNAPSHOT_PROVISIONING_INCOMPLETE')
            owner.files = ProtectedFileRoot.reopen_readonly(record['files']['path'], identity_from(record['files']['identity']))
            owner.custody.confirm_current()
            owner.store = PrivateBlobStore.reopen(record['blobs']['path'], identity_from(record['blobs']['identity']))
            owner.log = PrivateEventLog.reopen(record['events']['path'], owner.custody.binding)
            owner.log.bind_custody(owner.custody)
            owner._head = owner.log.binding().witnessed
            owner._refresh()
            if owner._state['phase'] == 'TERMINAL':
                owner.read_selected()
            else:
                owner._read_prefix(owner._state)
            return owner
        except BaseException as error:
            owner._failed_init(error)

    def _failed_init(self, error):
        extra = getattr(error, 'cleanup_owner', None) or getattr(error, 'cleanup_api', None)
        if extra is not None and extra is not self:
            self._extra.append(extra)
        try:
            self.close()
        except BaseException:
            pass
        raise SnapshotError('SNAPSHOT_OPEN_HELD', outcome_unknown=True, cleanup_owner=self) from error

    def _owners(self):
        need(not self._closed, 'SNAPSHOT_CLOSED')
        self.custody.confirm_current()
        record = self.custody.record
        need(record['storage_id'] == self.storage_id and record['project_id'] == model.PROJECT, 'SNAPSHOT_CUSTODY_BINDING')
        for key, resource in (('files', self.files), ('blobs', self.store)):
            need(str(resource.root) == record[key]['path'] and resource.root_identity.same_file(identity_from(record[key]['identity'])),
                 'SNAPSHOT_ROOT_BINDING')
            with resource._mutex:
                resource._check(**({'mutation': False} if key == 'files' else {}))
        binding, saved = self.log.binding(), self.custody.binding
        need(str(self.log.root) == record['events']['path'] and binding.root.same_file(saved.root)
             and binding.stream.same_file(saved.stream) and binding.witnessed == saved.witnessed == self._head,
             'SNAPSHOT_CUSTODY_HEAD')

    def _refresh(self):
        self._owners()

        def fold(state, row):
            if row.head.sequence == 1:
                binding = self.custody.binding
                need(parse_json(row.event) == {'kind': 'GENESIS', 'store_id': self.log.root.name,
                     'volume': str(binding.stream.volume), 'file_id': binding.stream.file_id,
                     'root_file_id': binding.root.file_id}, 'SNAPSHOT_GENESIS_BINDING')
                return state
            need(row.head.sequence <= model.MAX_HISTORY, 'SNAPSHOT_HISTORY_CAP')
            return model.reduce(state, parse_json(row.event))

        head, state = self.log.fold({}, fold)
        need(head == self._head and state and state['config']['storage_id'] == self.storage_id, 'SNAPSHOT_HISTORY_BINDING')
        self._state = state
        return state

    def _append(self, kind, *, phase_guard=None, **fields):
        need(not self._readonly, 'SNAPSHOT_READONLY')
        event = dict(schema=model.SCHEMA, kind=kind, **fields)
        expected = model.reduce(self._state, event)
        try:
            self._owners()
            reserve = model.MAX_HISTORY - self._head.sequence - 1
            need(reserve >= 0, 'SNAPSHOT_HISTORY_CAP')
            if phase_guard is not None:
                phase_guard()
            self._head = self.log.append(event, self._head, reserve_records=reserve, reserve_bytes=reserve * 17000)
            need(self._refresh() == expected, 'SNAPSHOT_EVENT_READBACK')
        except BaseException as error:
            self._held = True
            raise SnapshotError('SNAPSHOT_EVENT_UNKNOWN', outcome_unknown=True, cleanup_owner=self) from error

    def _authorize(self, request, lease, budget):
        budget.check()
        need(not self._readonly and not self._held and not self._stop.is_set() and not self._state['stopped'],
             'SNAPSHOT_READONLY_OR_HELD')
        need(type(lease) is Lease and lease.project_id == model.PROJECT and lease.target == model.TARGET, 'SNAPSHOT_WRITER_REQUIRED')
        self._owners()
        self.journal.check_lease(lease, now_ms=epoch_ms())
        source = self.current_source()
        model.hash_value(source)
        self.journal.check_revision(expected_revision=request['expected_source_sha256'], current_revision=source)
        need(source == self._state['config']['source_sha256'], 'SNAPSHOT_SOURCE_CHANGED')
        budget.check()
        need(not self._stop.is_set(), 'SNAPSHOT_STOPPED')

    def _put(self, name, raw, check):
        check()
        stored = self.store.put_bytes(raw)
        check()
        need(self.store.read_blob(stored) == raw, 'SNAPSHOT_BLOB_READBACK')
        check()
        durable = self.files.create_new(name, raw)
        check()
        observed, data = self.files.read(name)
        need(observed == durable and data == raw, 'SNAPSHOT_PROTECTED_READBACK')
        self.files.confirm_barrier(name, observed)
        return {'object_id': stored.object_id, 'identity': identity_value(stored.identity),
                'sha256': stored.sha256, 'file_version': version(durable)}

    def _read_protected(self, name, value):
        staged = model.blob(value)
        observed, raw = self.files.read(name)
        need(version(observed) == value['file_version'] and model.sha(raw) == value['sha256']
             and self.store.read_blob(staged) == raw, 'SNAPSHOT_PROTECTED_VERSION_CHANGED')
        self.files.confirm_barrier(name, observed)
        return raw

    def _read_bundle(self, state):
        staged, intent = state['staged'], state['intent']
        raw = self._read_protected(model.MANIFEST, staged['manifest'])
        actual = parse_json(raw)
        info = model.metadata(canonical_bytes(actual.get('metadata')))
        data = {name: self._read_protected(name, staged['artifacts'][name]) for name in model.NAMES}
        expected = model.manifest(state['config'], intent['request'], data, intent['proof']['evidence'], info)
        need(raw == canonical_bytes(expected) and model.sha(raw) == intent['proof']['manifest_sha256']
             and model.sha(canonical_bytes(info)) == intent['proof']['metadata_sha256'], 'SNAPSHOT_MANIFEST_BINDING')
        return actual, data

    def _read_selected(self, state):
        need(state['phase'] == 'TERMINAL', 'SNAPSHOT_NOT_COMMITTED')
        actual, raw = self.files.read(model.SELECTOR)
        need(version(actual) == state['terminal']['selector_version'] and raw == canonical_bytes(state['selector']),
             'SNAPSHOT_SELECTOR_CHANGED')
        self.files.confirm_barrier(model.SELECTOR, actual)
        return self._read_bundle(state)

    def _read_prefix(self, state):
        if state['phase'] not in ('STAGED', 'SELECTING'):
            return
        self._read_bundle(state)
        names = {entry.name for entry in self.files.root.iterdir()}
        expected = {'.writer', model.MANIFEST, *model.NAMES}
        if state['phase'] == 'SELECTING' and model.SELECTOR in names:
            # A selector may exist after a crash, but no terminal recorded its
            # identity. Verify available bytes/barrier and still return UNKNOWN.
            observed, raw = self.files.read(model.SELECTOR)
            need(raw == canonical_bytes(state['selector']), 'SNAPSHOT_UNCOMMITTED_SELECTOR_CHANGED')
            self.files.confirm_barrier(model.SELECTOR, observed)
            expected.add(model.SELECTOR)
        need(names == expected, 'SNAPSHOT_PREFIX_NAMESPACE')

    def read_selected(self):
        with self._mutex:
            return self._read_selected(self._refresh())

    def _lookup_global(self, command_id, digest):
        if self.journal is None:
            return None
        try:
            found = self.journal.lookup(project_id=model.PROJECT, command_id=command_id, now_ms=epoch_ms())
        except JournalError as error:
            if error.code == 'COMMAND_NOT_FOUND' and not error.outcome_unknown:
                return None
            raise
        receipt = found['receipt']
        need(type(receipt) is dict and receipt.get('schema') == model.SCHEMA
             and receipt.get('command_id') == command_id, 'SNAPSHOT_JOURNAL_BINDING')
        model.hash_value(receipt.get('request_sha256'))
        storage_id = receipt.get('storage_id')
        need(type(storage_id) is str and len(storage_id) == 32 and all(c in '0123456789abcdef' for c in storage_id),
             'SNAPSHOT_JOURNAL_BINDING')
        need(digest is None or receipt.get('request_sha256') == digest, 'SNAPSHOT_COMMAND_CONFLICT')
        need(found['status'] in ('ACCEPTED_PENDING', 'COMMITTED'), 'SNAPSHOT_JOURNAL_BINDING')
        if found['status'] == 'ACCEPTED_PENDING':
            need(canonical_bytes(receipt) == canonical_bytes(model.unknown(storage_id, command_id,
                 receipt['request_sha256'], 'RESERVED')), 'SNAPSHOT_JOURNAL_BINDING')
        if storage_id == self.storage_id:
            # A reservation followed by a crash before private INTENT is unresolved.
            need(found['status'] == 'ACCEPTED_PENDING', 'SNAPSHOT_JOURNAL_BINDING')
            return canonical_bytes(model.unknown(self.storage_id, command_id, receipt['request_sha256'], 'RESERVED'))
        # The ledger is a routing/dedupe record, not a substitute for custody and
        # protected bytes. A reopened owner never regains mutation authority.
        other = type(self).reopen(storage_id)
        try:
            raw = other.lookup_bytes(command_id, receipt['request_sha256'])
            if found['status'] == 'COMMITTED':
                need(raw == canonical_bytes(receipt), 'SNAPSHOT_JOURNAL_BINDING')
            return raw if raw is not None else canonical_bytes(model.unknown(storage_id, command_id,
                                                                             receipt['request_sha256'], 'RESERVED'))
        finally:
            other.close()

    def lookup_bytes(self, command_id, request_sha256=None):
        model.identifier(command_id)
        if request_sha256 is not None:
            model.hash_value(request_sha256)
        with self._mutex:
            state = self._refresh()
            intent = state.get('intent')
            if intent is not None and intent['request']['command_id'] == command_id:
                need(request_sha256 is None or request_sha256 == intent['request_sha256'], 'SNAPSHOT_COMMAND_CONFLICT')
                if state['phase'] == 'TERMINAL':
                    self._read_selected(state)
                    return canonical_bytes(state['terminal']['response'])
                self._read_prefix(state)
                return canonical_bytes(model.unknown(self.storage_id, command_id, intent['request_sha256'], state['phase']))
            if self._pending is not None and self._pending[0] == command_id:
                need(request_sha256 is None or request_sha256 == self._pending[1], 'SNAPSHOT_COMMAND_CONFLICT')
                return canonical_bytes(model.unknown(self.storage_id, command_id, self._pending[1], 'VALIDATING'))
            return self._lookup_global(command_id, request_sha256)

    def publish(self, request, lease, *, deadline_ms):
        request = model.validate_request(request)
        digest, key = model.sha(canonical_bytes(request)), request['command_id']
        need(type(deadline_ms) is int, 'SNAPSHOT_DEADLINE_REQUIRED')
        budget = AbsoluteDeadline(deadline_ms, host_deadline=time.monotonic() + max(0, deadline_ms - epoch_ms()) / 1000)
        check = lambda: self._authorize(request, lease, budget)
        with self._mutex:
            previous = self.lookup_bytes(key, digest)
            if previous is not None:
                return previous
            need(not self._readonly, 'SNAPSHOT_READONLY')
            need(self._state['phase'] == 'EMPTY' and self._pending is None, 'SNAPSHOT_ONE_CANDIDATE_CAPACITY')
            check()
            self._pending = (key, digest)
            self._validating.set()
        try:
            # Potentially heavy captured-evidence verification is outside the
            # publisher lock. Stop signals the installed provider immediately.
            provider_request = parse_json(canonical_bytes(request))
            verify = getattr(self.provider, 'verify', None)
            candidate = (verify(provider_request, deadline_ms=deadline_ms, stop=self._stop)
                         if callable(verify) else self.provider(provider_request))
            payloads, evidence, info = model.verified(candidate)
            need(candidate.source_sha256 == request['expected_source_sha256'], 'SNAPSHOT_PROVIDER_SOURCE')
            with self._mutex:
                check()
                manifest_raw = canonical_bytes(model.manifest(self._state['config'], request, payloads, evidence, info))
                proof = model.proof(candidate, manifest_raw)
                self.files.check_mutation_available()
                need({p.name for p in self.files.root.iterdir()} == {'.writer'}
                     and {p.name for p in self.store.root.iterdir()} == {'.writer'}, 'SNAPSHOT_INITIAL_NAMESPACE')
                check()
                reserved = False
                try:
                    # Core journal reserves a terminal record before admission.
                    claim = self.journal.append_command(project_id=model.PROJECT, command_id=key,
                        digest='sha256:' + digest, receipt=model.unknown(self.storage_id, key, digest, 'RESERVED'),
                        now_ms=epoch_ms(), pending=True)
                    if claim['replayed']:
                        return self._lookup_global(key, digest)
                    reserved = True
                    check()
                    self._append('INTENT', phase_guard=check, request=request, request_sha256=digest, lease_epoch=lease.fencing_epoch, proof=proof)
                    artifacts = {name: self._put(name, payloads[name], check) for name in model.NAMES}
                    staged = self._put(model.MANIFEST, manifest_raw, check)
                    check()
                    self._append('STAGED', phase_guard=check, command_id=key, request_sha256=digest, manifest=staged, artifacts=artifacts)
                    check()
                    self._read_bundle(self._state)
                    check()
                    selected = model.selection(self._state)
                    self._append('SELECTING', phase_guard=check, selector=selected)
                    check()
                    durable = self.files.create_new(model.SELECTOR, canonical_bytes(selected))
                    check()
                    actual, raw = self.files.read(model.SELECTOR)
                    need(actual == durable and raw == canonical_bytes(selected), 'SNAPSHOT_SELECTOR_READBACK')
                    self.files.confirm_barrier(model.SELECTOR, actual)
                    self._read_bundle(self._state)
                    check()
                    result = model.response(self._state)
                    self._append('TERMINAL', phase_guard=check, response=result,
                                 response_sha256=model.sha(canonical_bytes(result)), selector_version=version(actual))
                    # The witnessed terminal and selector/barriers precede both
                    # the global completion record and the returned exact bytes.
                    self._read_selected(self._refresh())
                    self.journal.finish_command(project_id=model.PROJECT, command_id=key, status='COMMITTED', receipt=result, now_ms=epoch_ms())
                    return canonical_bytes(result)
                except BaseException as error:
                    if reserved or getattr(error, 'outcome_unknown', False):
                        self._held = True
                        raise SnapshotError('SNAPSHOT_OUTCOME_UNKNOWN', outcome_unknown=True, cleanup_owner=self) from error
                    raise
        finally:
            with self._mutex:
                self._pending = None
                self._validating.clear()

    def request_stop(self):
        self._stop.set()
        callback = getattr(self.provider, 'request_stop', None)
        if callback is not None:
            callback()

    def stop(self):
        self.request_stop()
        with self._mutex:
            need(not self._readonly, 'SNAPSHOT_READONLY')
            self._refresh()
            if not self._state['stopped']:
                self._append('STOP')
        return {'stopped': True, 'public_ack': False}

    def close(self):
        self.request_stop()
        with self._mutex:
            if self._validating.is_set():
                raise SnapshotError('SNAPSHOT_VERIFIER_ACTIVE', outcome_unknown=True, cleanup_owner=self)
            for name in ('log', 'store', 'files', 'registry'):
                resource = getattr(self, name)
                if resource is None:
                    continue
                try:
                    resource.close()
                except BaseException as error:
                    raise SnapshotError('SNAPSHOT_CLOSE_HELD', outcome_unknown=True, cleanup_owner=self) from error
                setattr(self, name, None)
            pending = []
            for resource in self._extra:
                try:
                    resource.close_owned() if hasattr(resource, 'close_owned') else resource.close()
                except BaseException:
                    pending.append(resource)
            self._extra = pending
            if pending:
                raise SnapshotError('SNAPSHOT_EXTRA_CLEANUP_HELD', outcome_unknown=True, cleanup_owner=self)
            self._closed = True
