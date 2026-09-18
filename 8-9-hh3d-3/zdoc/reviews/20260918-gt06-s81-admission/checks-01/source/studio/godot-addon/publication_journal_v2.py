"""Owned complete-bundle journal with durable bootstrap, never a public ACK.

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

_STATE_PATH = Path(__file__).with_name('publication_state_v2.py').resolve()
_STATE_BYTES = _STATE_PATH.read_bytes()
_STATE_SHA256 = hashlib.sha256(_STATE_BYTES).hexdigest()
_STATE_MODULE = '_hh_gt03_publication_state_v2_' + hashlib.sha256(
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

_STORE_PATH = Path(__file__).with_name('protected_bundle.py').resolve()
_STORE_BYTES = _STORE_PATH.read_bytes()
_STORE_KEY = '_hh_gt03_journal_store_' + hashlib.sha256(str(_STORE_PATH).encode() + b'\0' + _STORE_BYTES).hexdigest()
if _STORE_KEY not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_STORE_KEY, _STORE_PATH)
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_STORE_KEY] = _module
    try:
        exec(compile(_STORE_BYTES, str(_STORE_PATH), 'exec'), _module.__dict__)
    except BaseException:
        del sys.modules[_STORE_KEY]
        raise
store_model = sys.modules[_STORE_KEY]
bundle_codec = store_model.bundle_codec
BOOT_SCHEMA = 'hh-godot-publication-bootstrap-1'
BOOT_COMMAND = 'bootstrap.initial'
_BOOT_KINDS = ('BOOTSTRAP_PREPARED', 'BOOTSTRAP_SELECTING', 'BOOTSTRAP_SELECTED')


def _version(version):
    return {'volume': str(version.identity.volume), 'file_id': version.identity.file_id,
            'size_bytes': version.identity.size, 'sha256': version.sha256}


class PublicationJournalV2Error(SafetyViolation):
    def __init__(self, code: str, *, outcome_unknown: bool = False, cleanup_owner=None):
        self.outcome_unknown = outcome_unknown
        self.cleanup_owner = cleanup_owner
        super().__init__(code)


def _need(condition, code):
    if not condition:
        raise PublicationJournalV2Error(code)


def _same_binding(left, right):
    return (type(left) is EventBinding and type(right) is EventBinding
            and left.root.same_file(right.root) and left.stream.same_file(right.stream)
            and left.witnessed == right.witnessed)


def _store_identity(store):
    return {'volume': str(store.root_identity.volume), 'file_id': store.root_identity.file_id}


class PublicationJournalV2:
    """One lifecycle owner and lock for all native roots, custody and history.

    create() persists a bootstrap intent before actual complete bundle and
    selector effects. CONFIG follows verified selection. Native byte effects
    are verified; supplied scene/engine facts remain attestations. Reopen is
    permanently readonly. This object never runs an engine or grants auth.
    """
    def __init__(self):
        raise TypeError('use PublicationJournalV2.create or PublicationJournalV2.reopen')

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
        owner._store = None
        owner._bootstrap = ()
        owner._intents = {}
        owner._bundles = {}
        return owner

    @classmethod
    def create(cls, parent: str | Path, *, storage_id: str, config: dict, initial_bundle):
        _need(type(config) is dict and 'content_root_identity' not in config, 'PUBLICATION_CONFIG_INPUT')
        config = parse_json(canonical_bytes(config))
        # Validate before provisioning writes. Only the subsequently checked
        # native root identity is substituted after the resources are created.
        state_model.reduce_event(None, {**config, 'content_root_identity': {'volume': '0', 'file_id': '0' * 32}})
        _need(type(initial_bundle) is bundle_codec.CompleteFixtureBundle, 'PUBLICATION_EXACT_BUNDLE_REQUIRED')
        initial_bundle = bundle_codec.decode_bundle(initial_bundle.manifest_bytes, initial_bundle.files)
        _need(config['initial'] == {'project_revision': initial_bundle.project_revision,
            'scene_revision': initial_bundle.scene_revision, 'files': parse_json(initial_bundle.manifest_bytes)['files'],
            'selection': config['initial']['selection']} and config['initial']['selection']['generation'] == 0
            and config['engine_sha256'] == initial_bundle.engine_sha256, 'PUBLICATION_INITIAL_BUNDLE_MISMATCH')
        SafePathResolver(parent)  # validate original spelling before pathlib normalization/provisioning
        parent = Path(parent)
        _need(parent.is_absolute() and parent.is_dir(), 'PUBLICATION_OWNED_PARENT_REQUIRED')
        owner = cls._owner(storage_id, config['project_id'], readonly=False)
        try:
            owner._registry = RegistryCustody.create(storage_id)
            owner._custody = WitnessCustody(owner._registry, storage_id=storage_id,
                                          project_id=owner._project_id, create=True)
            owner._files = ProtectedFileRoot.create(parent)
            owner._store = store_model.ProtectedBundleStore(owner._files)
            owner._blobs = PrivateBlobStore.create(parent)
            owner._log = PrivateEventLog.create(parent)
            owner._custody.activate(file_root=owner._files.root, file_identity=owner._files.root_identity,
                blob_root=owner._blobs.root, blob_identity=owner._blobs.root_identity,
                event_root=owner._log.root, event_binding=owner._log.binding())
            owner._custody.confirm_current()
            owner._log.bind_custody(owner._custody)
            owner._head = owner._log.binding().witnessed
            _need(owner._head.sequence == 1, 'PUBLICATION_NEW_LOG_NOT_EMPTY')
            config['content_root_identity'] = _store_identity(owner._files)
            intent = owner._store.prepare(BOOT_COMMAND, initial_bundle)
            owner._boot_append({'schema': BOOT_SCHEMA, 'kind': _BOOT_KINDS[0], 'config': config,
                'bundle_manifest': parse_json(initial_bundle.manifest_bytes), 'planned_names': dict(intent.names)})
            receipt = owner._store.stage(intent)
            selector = owner._store.prepare_selection(receipt, config['initial']['selection'], expected=None)
            owner._boot_append({'schema': BOOT_SCHEMA, 'kind': _BOOT_KINDS[1],
                                'selector': parse_json(selector.source_bytes)})
            selected = owner._store.select(selector)
            current = owner._store.inspect_selection()
            _need(current is not None and current.source_bytes == selector.source_bytes
                  and current.version == selected.version, 'PUBLICATION_BOOTSTRAP_READBACK')
            owner._boot_append({'schema': BOOT_SCHEMA, 'kind': _BOOT_KINDS[2],
                'selector_sha256': hashlib.sha256(current.source_bytes).hexdigest(),
                'selector_version': _version(current.version)})
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
            owner._store = store_model.ProtectedBundleStore(owner._files)
            owner._blobs = PrivateBlobStore.reopen(record['blobs']['path'], identity_from(record['blobs']['identity']))
            owner._custody.confirm_current()  # after acquiring the writer guard
            owner._log = PrivateEventLog.reopen(record['events']['path'], owner._custody.binding)
            owner._log.bind_custody(owner._custody)  # rejects history ahead of custody
            owner._head = owner._custody.binding.witnessed
            records = owner._native_events()
            _need(len(records) >= 4, 'PUBLICATION_BOOTSTRAP_INCOMPLETE')
            owner._bootstrap = tuple(records[:3])
            owner._state = owner._fold_verified()
            return owner
        except BaseException as exc:
            owner._init_failure(exc)

    def _init_failure(self, cause):
        self._held = True
        extra = getattr(cause, 'cleanup_owner', None)
        if extra is not None and extra is not self and extra not in (self._log, self._blobs, self._files, self._store, self._registry):
            self._extra_cleanup = extra
        # Native constructors may retain a low-level API before an owner exists.
        if self._extra_cleanup is None:
            self._extra_cleanup = getattr(cause, 'cleanup_api', None)
        try:
            self.close()
        except BaseException as cleanup_error:
            if not isinstance(cause, Exception):
                cause.cleanup_owner = self
                raise cause from cleanup_error
            raise PublicationJournalV2Error('PUBLICATION_INIT_CLEANUP_REQUIRED', outcome_unknown=True,
                                          cleanup_owner=self) from cleanup_error
        if not isinstance(cause, Exception):
            raise cause
        raise PublicationJournalV2Error('PUBLICATION_JOURNAL_OPEN_FAILED', outcome_unknown=True,
                                      cleanup_owner=self) from cause

    @contextmanager
    def _locked(self):
        if not self._mutex.acquire(timeout=2):
            raise PublicationJournalV2Error('PUBLICATION_JOURNAL_BUSY', outcome_unknown=True, cleanup_owner=self)
        try:
            _need(not self._closed, 'PUBLICATION_JOURNAL_CLOSED')
            if self._held:
                raise PublicationJournalV2Error('PUBLICATION_JOURNAL_HELD', outcome_unknown=True, cleanup_owner=self)
            yield
        finally:
            self._mutex.release()

    def _verify_owners(self):
        _need(type(self._registry) is RegistryCustody and type(self._custody) is WitnessCustody
              and type(self._files) is ProtectedFileRoot and type(self._blobs) is PrivateBlobStore
              and type(self._log) is PrivateEventLog, 'PUBLICATION_EXACT_NATIVE_OWNERS_REQUIRED')
        _need(type(self._store) is store_model.ProtectedBundleStore
              and self._store.root_identity == self._files.root_identity, 'PUBLICATION_EXACT_BUNDLE_OWNER_REQUIRED')
        with self._store._mutex:
            self._store._healthy()
            self._store._inventory()
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

    def _native_events(self):
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
            _need(len(events) < state_model.MAX_EVENTS + 3, 'PUBLICATION_HISTORY_LIMIT')
            return (*events, record.event)
        head, events = self._log.fold((), collect)
        _need(head == self._head, 'PUBLICATION_HEAD_CONFLICT')
        _need(head.sequence == len(events) + 1, 'PUBLICATION_NATIVE_SEQUENCE_MISMATCH')
        return events

    def _boot_append(self, value):
        _need(self._state is None and len(self._bootstrap) < 3
              and value['kind'] == _BOOT_KINDS[len(self._bootstrap)], 'PUBLICATION_BOOTSTRAP_ORDER')
        self._verify_owners()
        raw = canonical_bytes(value)
        prospective = (*self._bootstrap, raw)
        reserve = state_model.MAX_EVENTS + 3 - len(prospective)
        self._head = self._log.append(value, self._head, reserve_records=reserve,
                                      reserve_bytes=reserve * (state_model.MAX_EVENT_BYTES + 512))
        _need(self._native_events() == prospective, 'PUBLICATION_BOOTSTRAP_APPEND_READBACK')
        self._bootstrap = prospective

    def _verify_bootstrap(self):
        _need(len(self._bootstrap) == 3, 'PUBLICATION_BOOTSTRAP_INCOMPLETE')
        prepared, selecting, selected = map(parse_json, self._bootstrap)
        shapes = ({'schema', 'kind', 'config', 'bundle_manifest', 'planned_names'},
                  {'schema', 'kind', 'selector'}, {'schema', 'kind', 'selector_sha256', 'selector_version'})
        for index, (value, shape) in enumerate(zip((prepared, selecting, selected), shapes)):
            _need(set(value) == shape and value['schema'] == BOOT_SCHEMA
                  and value['kind'] == _BOOT_KINDS[index], 'PUBLICATION_BOOTSTRAP_SCHEMA')
        config = prepared['config']
        state_model.reduce_event(None, config)
        selector = selecting['selector']
        descriptor = selector['descriptor']
        baseline = self._store.read_descriptor(descriptor)
        _need(parse_json(baseline.manifest_bytes) == prepared['bundle_manifest']
              and config['content_root_identity'] == _store_identity(self._files)
              and config['initial']['project_revision'] == baseline.project_revision
              and config['initial']['scene_revision'] == baseline.scene_revision
              and config['initial']['files'] == prepared['bundle_manifest']['files']
              and config['engine_sha256'] == baseline.engine_sha256, 'PUBLICATION_BOOTSTRAP_BUNDLE_MISMATCH')
        expected_names = {path: row['name'] for path, row in descriptor['files'].items()}
        expected_names['@manifest'] = descriptor['manifest']['name']
        _need(prepared['planned_names'] == expected_names and len(set(expected_names.values())) == 12,
              'PUBLICATION_BOOTSTRAP_NAMES')
        raw = canonical_bytes(selector)
        _need(selector['schema'] == 'hh-godot-active-selection-1'
              and selector['command_id'] == BOOT_COMMAND and selector['parent_selection'] is None
              and selector['selection'] == config['initial']['selection']
              and selector['selection']['generation'] == 0
              and selector['descriptor_sha256'] == hashlib.sha256(canonical_bytes(descriptor)).hexdigest()
              and set(selector) == {'schema', 'command_id', 'parent_selection', 'selection', 'descriptor_sha256', 'descriptor'},
              'PUBLICATION_BOOTSTRAP_SELECTOR')
        version = selected['selector_version']
        _need(type(version) is dict and set(version) == {'volume', 'file_id', 'size_bytes', 'sha256'}
              and version['volume'] == str(self._files.root_identity.volume)
              and type(version['file_id']) is str and re.fullmatch('[0-9a-f]{32}', version['file_id'])
              and type(version['size_bytes']) is int and version['size_bytes'] == len(raw)
              and version['sha256'] == selected['selector_sha256'] == hashlib.sha256(raw).hexdigest(),
              'PUBLICATION_BOOTSTRAP_SELECTOR_VERSION')
        # This journal version owns bootstrap selection only. Reopening an
        # internally consistent event history does not adopt a different or
        # missing active file. A future ordinary publisher must durably extend
        # the expected-selector chain before this invariant can change.
        current = self._store.inspect_selection()
        _need(current is not None and current.source_bytes == raw and _version(current.version) == version,
              'PUBLICATION_SELECTED_STATE_CHANGED')
        return config

    def _fold_verified(self):
        records = self._native_events()
        _need(records[:3] == self._bootstrap, 'PUBLICATION_BOOTSTRAP_HISTORY_MISMATCH')
        config = self._verify_bootstrap()
        events = records[3:]
        _need(events and events[0] == canonical_bytes(config), 'PUBLICATION_BOOTSTRAP_CONFIG_MISMATCH')
        state = state_model.replay(events)
        snapshot = state.snapshot()
        _need(snapshot['project_id'] == self._project_id
              and snapshot['content_root_identity'] == _store_identity(self._files), 'PUBLICATION_CONFIG_IDENTITY_MISMATCH')
        self._verify_owners()
        return state

    def _poison(self, cause):
        self._held = True
        if not isinstance(cause, Exception):
            cause.cleanup_owner = self
            raise cause
        raise PublicationJournalV2Error('PUBLICATION_JOURNAL_RECOVERY_REQUIRED', outcome_unknown=True,
                                      cleanup_owner=self) from cause

    @contextmanager
    def _store_operations(self):
        """Keep uncertain child cleanup under the one outer lifecycle owner."""
        try:
            yield
        except BaseException as exc:
            if (not isinstance(exc, Exception) or getattr(exc, 'outcome_unknown', False)
                    or getattr(exc, 'cleanup_owner', None) is not None
                    or (self._store is not None and self._store._held)):
                self._poison(exc)
            raise

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
            if checked['kind'] == 'PREPARED':
                _need(checked['command_id'] != BOOT_COMMAND and checked['command_id'] in self._intents,
                      'PUBLICATION_OWNED_PREPARATION_REQUIRED')
                intent = self._intents[checked['command_id']]
                _need(dict(intent.names) == checked['planned_names'], 'PUBLICATION_OWNED_PREPARATION_REQUIRED')
            if checked['kind'] == 'STAGED':
                intent = self._intents.get(checked['command_id'])
                _need(intent is not None, 'PUBLICATION_OWNED_PREPARATION_REQUIRED')
                with self._store_operations():
                    receipt = self._store.lookup(checked['command_id'], intent.project_revision)
                    _need(receipt is not None and self._store.descriptor(receipt) == checked['candidate']['descriptor'],
                          'PUBLICATION_OWNED_STAGE_REQUIRED')
            try:
                _need(prospective.snapshot()['content_root_identity'] == _store_identity(self._files),
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

    def prepare(self, event: dict, bundle) -> dict:
        """Reserve actual names and persist PREPARED before any bundle writes.

        Admission fields are internal attestations, not authenticated authority.
        The caller must validate and bind semantic candidate metadata first.
        """
        with self._locked():
            _need(not self._readonly, 'PUBLICATION_REOPEN_READ_ONLY')
            _need(type(event) is dict and event.get('kind') == 'PREPARED' and 'planned_names' not in event,
                  'PUBLICATION_PREPARE_INPUT')
            _need(event.get('command_id') != BOOT_COMMAND, 'PUBLICATION_RESERVED_COMMAND')
            original = self.lookup(event['command_id'], event['digest'])
            _need(original is None, 'PUBLICATION_LOOKUP_BEFORE_RETRY')
            with self._store_operations():
                intent = self._store.prepare(event['command_id'], bundle)
            checked = {**event, 'planned_names': dict(intent.names)}
            try:
                prospective = state_model.reduce_event(self._state, checked)
                request = prospective.snapshot()['commands'][-1]['prepared']
                metadata = parse_json(bundle.manifest_bytes)['files']
                changed = bundle_codec.SCENE_PATH if request['operation'] == 'scene.save' else bundle_codec.SCRIPT_PATH
                _need(all(metadata[path] == request['expected_files'][path] for path in bundle_codec.PATHS if path != changed),
                      'PUBLICATION_BUNDLE_UNEXPECTED_CHANGE')
                _need(bundle.engine_sha256 == self._state.snapshot()['engine_sha256'], 'PUBLICATION_BUNDLE_ENGINE')
                if request['operation'] == 'scene.save':
                    _need(bundle.scene_revision == request['before_scene_revision'], 'PUBLICATION_BUNDLE_SCENE')
                else:
                    _need(all(metadata[changed][key] == value for key, value in request['script_input'].items()),
                          'PUBLICATION_BUNDLE_SCRIPT')
            except BaseException as cause:
                try:
                    with self._store_operations():
                        self._store.cancel_unused_prepare(intent)
                except BaseException as cleanup_error:
                    if not isinstance(cause, Exception):
                        self._held = True
                        cause.cleanup_owner = self
                        raise cause from cleanup_error
                    raise
                raise
            self._intents[event['command_id']] = intent
            self._bundles[event['command_id']] = bundle
            return self.append(checked)

    def stage_prepared(self, command_id: str, digest: str, *, observed_ms: int, scene_observation=None) -> dict:
        """Actual complete file/barrier readback followed by durable STAGED."""
        with self._locked():
            _need(not self._readonly, 'PUBLICATION_REOPEN_READ_ONLY')
            command = self.lookup(command_id, digest)
            _need(command is not None and command['phase'] == 'PREPARED', 'PUBLICATION_STAGE_PHASE')
            intent = self._intents.get(command_id)
            _need(intent is not None, 'PUBLICATION_OWNED_PREPARATION_REQUIRED')
            snapshot = self._state.snapshot()
            request = next(row['prepared'] for row in snapshot['commands'] if row['command_id'] == command_id)
            _need(type(observed_ms) is int and snapshot['last_observed_ms'] <= observed_ms <= 9007199254740991,
                  'PUBLICATION_STAGE_TIME')
            if request['operation'] == 'scene.save':
                _need(scene_observation is None, 'PUBLICATION_STAGE_SCENE_OBSERVATION')
            else:
                # Pure preflight before the first native stage attempt. Native
                # FileIDs are deliberately absent until real descriptor readback.
                bundle = self._bundles[command_id]
                state_model._fresh_observation(scene_observation,
                    {**snapshot, 'last_observed_ms': observed_ms}, request,
                    {'candidate_id': request['candidate_id'], 'descriptor': {'manifest': {}},
                     'bundle_manifest': parse_json(bundle.manifest_bytes)})
            try:
                receipt = self._store.stage(intent)
                bundle = self._store.readback(receipt)
                event = {'schema': state_model.SCHEMA, 'kind': 'STAGED', 'sequence': self._state.event_count + 1,
                    'project_id': self._project_id, 'observed_ms': observed_ms, 'command_id': command_id, 'digest': digest,
                    'candidate': {'candidate_id': request['candidate_id'], 'descriptor': self._store.descriptor(receipt),
                        'bundle_manifest': parse_json(bundle.manifest_bytes), 'scene_observation': scene_observation}}
                return self.append(event)
            except BaseException as exc:
                self._poison(exc)

    def selected_bytes(self):
        """Read current native selection; no new validation or write authority."""
        with self._locked():
            try:
                self._refresh()
                return self._store.inspect_selection()
            except BaseException as exc:
                self._poison(exc)

    def _report(self, state):
        snapshot = state.snapshot()
        snapshot.update(bootstrap_bytes_verified=True, journal_read_only=self._readonly, journal_held=self._held or snapshot['held'],
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
            raise PublicationJournalV2Error('PUBLICATION_CLOSE_BUSY', outcome_unknown=True, cleanup_owner=self)
        try:
            self._closed = True
            # Stop at the first failed close, retaining that exact owner and all
            # ancestors. A retry continues here; no unsafe best-effort release.
            for name in ('_extra_cleanup', '_log', '_blobs', '_store', '_files', '_registry'):
                resource = getattr(self, name)
                if resource is None:
                    continue
                try:
                    if name == '_extra_cleanup' and hasattr(resource, 'close_owned'):
                        resource.close_owned()
                    else:
                        resource.close()
                except BaseException as exc:
                    self._held = True
                    raise PublicationJournalV2Error('PUBLICATION_CLOSE_UNCERTAIN', outcome_unknown=True,
                                                  cleanup_owner=self) from exc
                setattr(self, name, None)
                if name == '_store':
                    self._files = None  # Store owned the native close; discard read-only alias.
        finally:
            self._mutex.release()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
