"""Owned durable storage for the pure Godot publication reducer, never an ACK.

This trusted local API admits no worker paths, callbacks or engine methods.
The caller owns the provisioning parent. Engine/file attestations in records
remain attestations; storing them does not verify their claimed effects.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib.util
from pathlib import Path
import re
import sys
import threading

from studio.protocol.core import canonical_bytes, parse_json
from studio.host.core.custody import WitnessCustody, identity_from
from studio.host.core.custody_registry import RegistryCustody
from studio.host.core.limits import SafetyViolation, SafePathResolver
from studio.host.core.private_events import PrivateEventLog, EventBinding, EventRecord
from studio.host.core.private_store import PrivateBlobStore
from studio.host.core.safe_replace import ProtectedFileRoot

_STATE_PATH = Path(__file__).with_name('publication_state.py').resolve()
_STATE_BYTES = _STATE_PATH.read_bytes()
_STATE_SHA256 = hashlib.sha256(_STATE_BYTES).hexdigest()
_STATE_MODULE = '_hh_gt03_publication_state_' + hashlib.sha256(
    str(_STATE_PATH).encode('utf-8') + b'\0' + _STATE_BYTES).hexdigest()
if _STATE_MODULE not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_STATE_MODULE, _STATE_PATH)
    _module = importlib.util.module_from_spec(_spec)
    _module._publication_source_sha256 = _STATE_SHA256
    sys.modules[_STATE_MODULE] = _module
    try:
        # Execute the exact bytes used in the cache key, not a second file read.
        exec(compile(_STATE_BYTES, str(_STATE_PATH), 'exec'), _module.__dict__)
    except BaseException:
        del sys.modules[_STATE_MODULE]
        raise
state_model = sys.modules[_STATE_MODULE]
if (getattr(state_model, '__file__', None) != str(_STATE_PATH)
        or getattr(state_model, '_publication_source_sha256', None) != _STATE_SHA256):
    raise ImportError('publication reducer source binding mismatch')


class PublicationJournalError(SafetyViolation):
    def __init__(self, code: str, *, outcome_unknown: bool = False, cleanup_owner=None):
        self.outcome_unknown = outcome_unknown
        self.cleanup_owner = cleanup_owner
        super().__init__(code)


def _need(condition, code):
    if not condition:
        raise PublicationJournalError(code)


def _same_binding(left, right):
    return (type(left) is EventBinding and type(right) is EventBinding
            and left.root.same_file(right.root) and left.stream.same_file(right.stream)
            and left.witnessed == right.witnessed)


def _store_identity(store):
    return {'volume': str(store.root_identity.volume), 'file_id': store.root_identity.file_id}


class PublicationJournal:
    """One lifecycle owner and lock for all native roots, custody and history.

    create() takes a pure CONFIG dictionary without store_identity, which is
    bound to the newly minted native blob root. reopen() is permanently
    read-only, even for complete history. No method stages, selects or runs code.
    """
    def __init__(self):
        raise TypeError('use PublicationJournal.create or PublicationJournal.reopen')

    @classmethod
    def _owner(cls, storage_id, project_id, *, readonly):
        _need(type(storage_id) is str and re.fullmatch('[0-9a-f]{32}', storage_id),
              'PUBLICATION_STORAGE_ID_REQUIRED')
        owner = object.__new__(cls)
        owner._mutex = threading.RLock()
        owner._storage_id, owner._project_id = storage_id, project_id
        owner._readonly, owner._held, owner._closed = readonly, False, False
        owner._registry = owner._custody = owner._files = owner._blobs = owner._log = None
        owner._state = owner._head = owner._extra_cleanup = None
        return owner

    @classmethod
    def create(cls, parent: str | Path, *, storage_id: str, config: dict):
        _need(type(config) is dict and 'store_identity' not in config, 'PUBLICATION_CONFIG_INPUT')
        config = parse_json(canonical_bytes(config))
        # Validate before provisioning writes. Only the subsequently checked
        # native root identity is substituted after the resources are created.
        state_model.reduce_event(None, {**config, 'store_identity': {'volume': '0', 'file_id': '0' * 32}})
        SafePathResolver(parent)  # validate original spelling before pathlib normalization/provisioning
        parent = Path(parent)
        _need(parent.is_absolute() and parent.is_dir(), 'PUBLICATION_OWNED_PARENT_REQUIRED')
        owner = cls._owner(storage_id, config['project_id'], readonly=False)
        try:
            owner._registry = RegistryCustody.create(storage_id)
            owner._custody = WitnessCustody(owner._registry, storage_id=storage_id,
                                          project_id=owner._project_id, create=True)
            owner._files = ProtectedFileRoot.create(parent)
            owner._blobs = PrivateBlobStore.create(parent)
            owner._log = PrivateEventLog.create(parent)
            owner._custody.activate(file_root=owner._files.root, file_identity=owner._files.root_identity,
                blob_root=owner._blobs.root, blob_identity=owner._blobs.root_identity,
                event_root=owner._log.root, event_binding=owner._log.binding())
            owner._custody.confirm_current()
            owner._log.bind_custody(owner._custody)
            owner._head = owner._log.binding().witnessed
            _need(owner._head.sequence == 1, 'PUBLICATION_NEW_LOG_NOT_EMPTY')
            config['store_identity'] = _store_identity(owner._blobs)
            owner.append(config)
            return owner
        except BaseException as exc:
            owner._init_failure(exc)

    @classmethod
    def reopen(cls, storage_id: str, *, project_id: str):
        owner = cls._owner(storage_id, project_id, readonly=True)
        try:
            owner._registry = RegistryCustody.reopen(storage_id)
            owner._custody = WitnessCustody(owner._registry, storage_id=storage_id, project_id=project_id)
            record = owner._custody.record
            # These exact protected record paths/identities are validated by
            # WitnessCustody and rechecked by the native retained-handle APIs.
            owner._files = ProtectedFileRoot.reopen_readonly(record['files']['path'], identity_from(record['files']['identity']))
            owner._blobs = PrivateBlobStore.reopen(record['blobs']['path'], identity_from(record['blobs']['identity']))
            owner._custody.confirm_current()  # after acquiring the writer guard
            owner._log = PrivateEventLog.reopen(record['events']['path'], owner._custody.binding)
            owner._log.bind_custody(owner._custody)  # rejects history ahead of custody
            owner._head = owner._custody.binding.witnessed
            owner._state = owner._fold_verified()
            return owner
        except BaseException as exc:
            owner._init_failure(exc)

    def _init_failure(self, cause):
        self._held = True
        extra = getattr(cause, 'cleanup_owner', None)
        if extra is not None and extra is not self and extra not in (self._log, self._blobs, self._files, self._registry):
            self._extra_cleanup = extra
        # Native constructors may retain a low-level API before an owner exists.
        if self._extra_cleanup is None:
            self._extra_cleanup = getattr(cause, 'cleanup_api', None)
        try:
            self.close()
        except BaseException as cleanup_error:
            raise PublicationJournalError('PUBLICATION_INIT_CLEANUP_REQUIRED', outcome_unknown=True,
                                          cleanup_owner=self) from cleanup_error
        raise PublicationJournalError('PUBLICATION_JOURNAL_OPEN_FAILED', outcome_unknown=True,
                                      cleanup_owner=self) from cause

    @contextmanager
    def _locked(self):
        if not self._mutex.acquire(timeout=2):
            raise PublicationJournalError('PUBLICATION_JOURNAL_BUSY', outcome_unknown=True, cleanup_owner=self)
        try:
            _need(not self._closed, 'PUBLICATION_JOURNAL_CLOSED')
            if self._held:
                raise PublicationJournalError('PUBLICATION_JOURNAL_HELD', outcome_unknown=True, cleanup_owner=self)
            yield
        finally:
            self._mutex.release()

    def _verify_owners(self):
        _need(type(self._registry) is RegistryCustody and type(self._custody) is WitnessCustody
              and type(self._files) is ProtectedFileRoot and type(self._blobs) is PrivateBlobStore
              and type(self._log) is PrivateEventLog, 'PUBLICATION_EXACT_NATIVE_OWNERS_REQUIRED')
        # Internal read/verify APIs only: validate retained native handles,
        # guards, ancestors and ACLs rather than trusting cached root IDs.
        # Acquire each core owner's mutex; no mutation/rearm is performed.
        for resource, options in ((self._files, {'mutation': False}), (self._blobs, {})):
            _need(resource._mutex.acquire(timeout=2), 'PUBLICATION_NATIVE_ROOT_BUSY')
            try:
                resource._check(**options)
            finally:
                resource._mutex.release()
        self._custody.confirm_current()
        record = self._custody.record
        _need(record['storage_id'] == self._storage_id == self._registry.local_id
              and record['project_id'] == self._project_id, 'PUBLICATION_CUSTODY_IDENTITY_MISMATCH')
        for key, resource in (('files', self._files), ('blobs', self._blobs)):
            _need(str(resource.root) == record[key]['path']
                  and resource.root_identity.same_file(identity_from(record[key]['identity'])),
                  'PUBLICATION_ROOT_IDENTITY_MISMATCH')
        _need(str(self._log.root) == record['events']['path'], 'PUBLICATION_EVENT_ROOT_MISMATCH')
        binding = self._log.binding()  # native identity + fresh flush + complete chain scan
        _need(_same_binding(binding, self._custody.binding), 'PUBLICATION_CUSTODY_HEAD_MISMATCH')
        _need(binding.witnessed == self._head, 'PUBLICATION_HEAD_CONFLICT')
        return binding

    def _fold_verified(self):
        binding = self._verify_owners()
        def collect(events, record):
            _need(type(record) is EventRecord, 'PUBLICATION_NATIVE_RECORD_REQUIRED')
            event = parse_json(record.event)
            if record.head.sequence == 1:
                expected = {'kind': 'GENESIS', 'store_id': self._log.root.name,
                    'volume': str(binding.stream.volume), 'file_id': binding.stream.file_id,
                    'root_file_id': binding.root.file_id}
                _need(not events and event == expected, 'PUBLICATION_NATIVE_GENESIS_MISMATCH')
                return events
            _need(len(events) < state_model.MAX_EVENTS, 'PUBLICATION_HISTORY_LIMIT')
            return (*events, record.event)
        head, events = self._log.fold((), collect)
        _need(head == self._head, 'PUBLICATION_HEAD_CONFLICT')
        _need(head.sequence == len(events) + 1, 'PUBLICATION_NATIVE_SEQUENCE_MISMATCH')
        state = state_model.replay(events)
        snapshot = state.snapshot()
        _need(snapshot['project_id'] == self._project_id
              and snapshot['store_identity'] == _store_identity(self._blobs), 'PUBLICATION_CONFIG_IDENTITY_MISMATCH')
        self._verify_owners()
        return state

    def _poison(self, cause):
        self._held = True
        raise PublicationJournalError('PUBLICATION_JOURNAL_RECOVERY_REQUIRED', outcome_unknown=True,
                                      cleanup_owner=self) from cause

    def _refresh(self):
        observed = self._fold_verified()
        _need(self._state is not None and observed.events == self._state.events, 'PUBLICATION_HISTORY_CONFLICT')
        return observed

    def append(self, event: dict | bytes) -> dict:
        with self._locked():
            _need(not self._readonly, 'PUBLICATION_REOPEN_READ_ONLY')
            # Pure validation happens before native append, including shape,
            # sequence, phase, command digest, project CAS and bounded capacity.
            prospective = state_model.reduce_event(self._state, event)
            checked = parse_json(prospective.events[-1])
            try:
                _need(prospective.snapshot()['store_identity'] == _store_identity(self._blobs),
                      'PUBLICATION_CONFIG_IDENTITY_MISMATCH')
                if self._state is None:
                    self._verify_owners()
                else:
                    self._refresh()
                # Keep enough native capacity for all remaining bounded typed
                # events. This reserves log capacity, never staging blob space.
                reserve = state_model.MAX_EVENTS - prospective.event_count
                head = self._log.append(checked, self._head, reserve_records=reserve,
                                        reserve_bytes=reserve * (state_model.MAX_EVENT_BYTES + 512))
                self._head = head
                observed = self._fold_verified()
                _need(observed.events == prospective.events, 'PUBLICATION_APPEND_READBACK_MISMATCH')
                self._state = observed
                return self._report(observed)
            except BaseException as exc:
                self._poison(exc)

    def _report(self, state):
        snapshot = state.snapshot()
        snapshot.update(journal_read_only=self._readonly, journal_held=self._held or snapshot['held'],
                        journal_event_sequence=self._head.sequence, public_ack=False,
                        engine_effects_verified=False, execution_permitted=False)
        return snapshot

    def snapshot(self) -> dict:
        with self._locked():
            try:
                return self._report(self._refresh())
            except BaseException as exc:
                self._poison(exc)

    def lookup(self, command_id: str, digest: str | None = None) -> dict | None:
        with self._locked():
            try:
                state = self._refresh()
            except BaseException as exc:
                self._poison(exc)
            return state_model.lookup(state, command_id, digest)

    def close(self) -> None:
        if not self._mutex.acquire(timeout=2):
            raise PublicationJournalError('PUBLICATION_CLOSE_BUSY', outcome_unknown=True, cleanup_owner=self)
        try:
            self._closed = True
            # Stop at the first failed close, retaining that exact owner and all
            # ancestors. A retry continues here; no unsafe best-effort release.
            for name in ('_extra_cleanup', '_log', '_blobs', '_files', '_registry'):
                resource = getattr(self, name)
                if resource is None:
                    continue
                try:
                    if name == '_extra_cleanup' and not hasattr(resource, 'close'):
                        resource.close_owned()
                    else:
                        resource.close()
                except BaseException as exc:
                    self._held = True
                    raise PublicationJournalError('PUBLICATION_CLOSE_UNCERTAIN', outcome_unknown=True,
                                                  cleanup_owner=self) from exc
                setattr(self, name, None)
        finally:
            self._mutex.release()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
