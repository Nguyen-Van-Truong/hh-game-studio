"""Owned scene.save journal and real selector CAS; no authentication/public ACK.

The outer publication owner validates registered editor/validator receipts and
live effect grants. This journal owns all durable files/logs and generates
native staging/selection facts itself. Reopen is permanently readonly.
"""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path
import sys
import time
import uuid

from studio.protocol.core import canonical_bytes, parse_json
from studio.host.core.custody import WitnessCustody
from studio.host.core.custody_registry import RegistryCustody
from studio.host.core.limits import SafePathResolver
from studio.host.core.private_events import PrivateEventLog
from studio.host.core.private_store import PrivateBlobStore
from studio.host.core.safe_replace import ProtectedFileRoot


def _load(filename):
    path = Path(__file__).with_name(filename).resolve(); raw = path.read_bytes()
    key = '_hh_journal_v3_' + hashlib.sha256(str(path).encode() + b'\0' + raw).hexdigest()
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec); sys.modules[key] = module
        try:
            exec(compile(raw, str(path), 'exec'), module.__dict__)
        except BaseException:
            del sys.modules[key]
            raise
    return sys.modules[key]


state_model = _load('publication_state_v3.py')
base = _load('publication_journal_v2.py')
store_model = base.store_model
bundle_codec = store_model.bundle_codec
PublicationJournalV3Error = base.PublicationJournalV2Error
_need = base._need
_version = base._version
_identity = base._store_identity
BOOT_SCHEMA, BOOT_COMMAND, _BOOT_KINDS = base.BOOT_SCHEMA, base.BOOT_COMMAND, base._BOOT_KINDS
CONFIG_FIELDS = {'schema', 'kind', 'sequence', 'project_id', 'observed_ms', 'validator_engine_sha256',
    'editor_engine_sha256', 'source_closure_sha256', 'validation_source_release_sha256'}


class PublicationJournalV3(base.PublicationJournalV2):
    """Reuse exact v2 native lifecycle ownership, with an independent v3 fold."""
    @classmethod
    def _owner(cls, storage_id, project_id, *, readonly):
        owner = super()._owner(storage_id, project_id, readonly=readonly)
        owner._selection_intents = {}
        return owner

    @classmethod
    def create(cls, parent, *, storage_id, config, initial_bundle):
        state_model.shape(config, CONFIG_FIELDS)
        config = parse_json(canonical_bytes(config))
        _need(config['schema'] == state_model.SCHEMA and config['kind'] == 'CONFIG'
              and type(config['sequence']) is int and config['sequence'] == 1, 'PUBLICATION_V3_CONFIG_INPUT')
        state_model.values._matches(config['project_id'], state_model.values._PROJECT)
        state_model.integer(config['observed_ms'])
        for key in ('validator_engine_sha256', 'editor_engine_sha256', 'source_closure_sha256', 'validation_source_release_sha256'):
            state_model.hash_value(config[key])
        _need(type(initial_bundle) is bundle_codec.CompleteFixtureBundle, 'PUBLICATION_EXACT_BUNDLE_REQUIRED')
        initial_bundle = bundle_codec.decode_bundle(initial_bundle.manifest_bytes, initial_bundle.files)
        _need(initial_bundle.engine_sha256 == config['validator_engine_sha256'], 'PUBLICATION_INITIAL_ENGINE_MISMATCH')
        SafePathResolver(parent); parent = Path(parent)
        _need(parent.is_absolute() and parent.is_dir(), 'PUBLICATION_OWNED_PARENT_REQUIRED')
        owner = cls._owner(storage_id, config['project_id'], readonly=False)
        try:
            owner._registry = RegistryCustody.create(storage_id)
            owner._custody = WitnessCustody(owner._registry, storage_id=storage_id, project_id=owner._project_id, create=True)
            owner._files = ProtectedFileRoot.create(parent)
            owner._store = store_model.ProtectedBundleStore(owner._files)
            owner._blobs = PrivateBlobStore.create(parent)
            owner._log = PrivateEventLog.create(parent)
            owner._custody.activate(file_root=owner._files.root, file_identity=owner._files.root_identity,
                blob_root=owner._blobs.root, blob_identity=owner._blobs.root_identity,
                event_root=owner._log.root, event_binding=owner._log.binding())
            owner._custody.confirm_current(); owner._log.bind_custody(owner._custody)
            owner._head = owner._log.binding().witnessed
            _need(owner._head.sequence == 1, 'PUBLICATION_NEW_LOG_NOT_EMPTY')
            config['content_root_identity'] = _identity(owner._files)
            intent = owner._store.prepare(BOOT_COMMAND, initial_bundle)
            owner._boot_append({'schema': BOOT_SCHEMA, 'kind': _BOOT_KINDS[0], 'config': config,
                'bundle_manifest': parse_json(initial_bundle.manifest_bytes), 'planned_names': dict(intent.names)})
            receipt = owner._store.stage(intent)
            selected = {'generation': 0, 'identity': 'sha256:' + hashlib.sha256(initial_bundle.manifest_bytes).hexdigest()}
            selector_intent = owner._store.prepare_selection(receipt, selected, expected=None)
            owner._boot_append({'schema': BOOT_SCHEMA, 'kind': _BOOT_KINDS[1], 'selector': parse_json(selector_intent.source_bytes)})
            selected_receipt = owner._store.select(selector_intent)
            actual = owner._store.inspect_selection()
            _need(actual is selected_receipt.snapshot, 'PUBLICATION_BOOTSTRAP_READBACK')
            owner._boot_append({'schema': BOOT_SCHEMA, 'kind': _BOOT_KINDS[2],
                'selector_sha256': hashlib.sha256(actual.source_bytes).hexdigest(), 'selector_version': _version(actual.version)})
            config['initial'] = {'bundle_manifest': parse_json(initial_bundle.manifest_bytes),
                'selector': parse_json(actual.source_bytes), 'selector_version': _version(actual.version)}
            owner._append_event(config)
            return owner
        except BaseException as error:
            owner._init_failure(error)

    def _verify_bootstrap(self):
        _need(len(self._bootstrap) == 3, 'PUBLICATION_BOOTSTRAP_INCOMPLETE')
        prepared, selecting, selected = map(parse_json, self._bootstrap)
        shapes = ({'schema', 'kind', 'config', 'bundle_manifest', 'planned_names'},
                  {'schema', 'kind', 'selector'}, {'schema', 'kind', 'selector_sha256', 'selector_version'})
        for index, (value, fields) in enumerate(zip((prepared, selecting, selected), shapes)):
            _need(type(value) is dict and set(value) == fields and value['schema'] == BOOT_SCHEMA
                  and value['kind'] == _BOOT_KINDS[index], 'PUBLICATION_BOOTSTRAP_SCHEMA')
        selector = selecting['selector']; descriptor = selector['descriptor']
        bundle = self._store.read_descriptor(descriptor)
        _need(parse_json(bundle.manifest_bytes) == prepared['bundle_manifest'], 'PUBLICATION_BOOTSTRAP_BUNDLE_MISMATCH')
        names = {path: row['name'] for path, row in descriptor['files'].items()}
        names['@manifest'] = descriptor['manifest']['name']
        _need(prepared['planned_names'] == names, 'PUBLICATION_BOOTSTRAP_NAMES')
        _need(selected['selector_sha256'] == hashlib.sha256(canonical_bytes(selector)).hexdigest(), 'PUBLICATION_BOOTSTRAP_SELECTOR')
        config = {**prepared['config'], 'initial': {'bundle_manifest': prepared['bundle_manifest'],
            'selector': selector, 'selector_version': selected['selector_version']}}
        state_model.reduce_event(None, config)
        return config

    def _fold_verified(self):
        records = self._native_events()
        _need(records[:3] == self._bootstrap, 'PUBLICATION_BOOTSTRAP_HISTORY_MISMATCH')
        config = self._verify_bootstrap(); events = records[3:]
        _need(events and events[0] == canonical_bytes(config), 'PUBLICATION_BOOTSTRAP_CONFIG_MISMATCH')
        state = state_model.replay(events); snapshot = state.snapshot()
        _need(snapshot['project_id'] == self._project_id and snapshot['content_root_identity'] == _identity(self._files),
              'PUBLICATION_CONFIG_IDENTITY_MISMATCH')
        current = self._store.inspect_selection(); expected = snapshot['selected']
        _need(current is not None and current.source_bytes == canonical_bytes(expected['selector'])
              and _version(current.version) == expected['selector_version'], 'PUBLICATION_SELECTED_STATE_CHANGED')
        _need(self._store.read_descriptor(expected['selector']['descriptor']).manifest_bytes
              == canonical_bytes(expected['bundle_manifest']), 'PUBLICATION_SELECTED_BUNDLE_CHANGED')
        self._verify_owners()
        return state

    def _append_event(self, event, *, after_selector_effect=False):
        prospective = state_model.reduce_event(self._state, event)
        checked = parse_json(prospective.events[-1])
        try:
            if self._state is None or after_selector_effect:
                # During CAS->SELECTED the durable chain intentionally still
                # names the old selector. Do not pretend a normal refresh passed.
                self._verify_owners()
            else:
                self._refresh()
            reserve = state_model.MAX_EVENTS - prospective.event_count
            self._head = self._log.append(checked, self._head, reserve_records=reserve,
                reserve_bytes=reserve * (state_model.MAX_EVENT_BYTES + 512))
            observed = self._fold_verified()
            _need(observed.events == prospective.events, 'PUBLICATION_APPEND_READBACK_MISMATCH')
            self._state = observed
            return self._report(observed)
        except BaseException as error:
            self._poison(error)

    def append(self, event):
        raise PublicationJournalV3Error('PUBLICATION_V3_TYPED_METHOD_REQUIRED')

    def _event(self, kind, observed_ms, **fields):
        state_model.integer(observed_ms)
        return {'schema': state_model.SCHEMA, 'kind': kind, 'sequence': self._state.event_count + 1,
                'project_id': self._project_id, 'observed_ms': observed_ms, **fields}

    def _command(self, command_id, command_digest, phase=None):
        command = self.lookup(command_id, command_digest)
        _need(command is not None and (phase is None or command['phase'] == phase), 'PUBLICATION_V3_COMMAND_PHASE')
        return command

    def _writable(self):
        _need(not self._readonly, 'PUBLICATION_REOPEN_READ_ONLY')

    def capture_prepared(self, command_id, command_digest, *, expected_revision, editor, editor_generation,
                         root_instance_id, admission, scratch_name, observed_ms):
        with self._locked():
            self._writable()
            try: state = self._refresh()
            except BaseException as error: self._poison(error)
            prior = state_model.lookup(state, command_id, command_digest)
            if prior is not None: return prior
            selected = state.snapshot()['selected']
            event = self._event('CAPTURE_PREPARED', observed_ms, command_id=command_id, digest=command_digest,
                operation='scene.save', candidate_id='candidate-' + uuid.uuid4().hex,
                before_project_revision=selected['bundle_manifest']['project_revision'], before_scene_revision=expected_revision,
                expected_files=selected['bundle_manifest']['files'], parent_selection=selected['selector']['selection'],
                checkpoint_descriptor=selected['selector']['descriptor'], previous_selector_version=selected['selector_version'],
                previous_selector_sha256=hashlib.sha256(canonical_bytes(selected['selector'])).hexdigest(),
                editor=editor, editor_generation=editor_generation, root_instance_id=root_instance_id,
                admission=admission, scratch_name=scratch_name)
            self._append_event(event)
            return self.lookup(command_id, command_digest)

    def captured(self, command_id, command_digest, capture_facts, *, observed_ms):
        return self._attested('CAPTURED', 'capture', capture_facts, command_id, command_digest, observed_ms)

    def _attested(self, kind, key, facts, command_id, command_digest, observed_ms):
        with self._locked():
            self._writable(); self._command(command_id, command_digest)
            self._append_event(self._event(kind, observed_ms, command_id=command_id, digest=command_digest, **{key: facts}))
            return self.lookup(command_id, command_digest)

    def prepare(self, command_id, command_digest, bundle, *, observed_ms):
        with self._locked():
            self._writable(); self._command(command_id, command_digest, 'CAPTURED')
            with self._store_operations():
                intent = self._store.prepare(command_id, bundle)
            event = self._event('PREPARED', observed_ms, command_id=command_id, digest=command_digest,
                planned_names=dict(intent.names), bundle_manifest=parse_json(bundle.manifest_bytes))
            try:
                state_model.reduce_event(self._state, event)
            except BaseException as cause:
                try:
                    with self._store_operations(): self._store.cancel_unused_prepare(intent)
                except BaseException as cleanup_error:
                    if not isinstance(cause, Exception):
                        self._held = True; cause.cleanup_owner = self
                        raise cause from cleanup_error
                    raise
                raise
            self._intents[command_id] = intent; self._bundles[command_id] = bundle
            self._append_event(event)
            return self.lookup(command_id, command_digest)

    def stage_prepared(self, command_id, command_digest, *, observed_ms):
        with self._locked():
            self._writable(); self._command(command_id, command_digest, 'PREPARED')
            state_model.integer(observed_ms)
            _need(observed_ms >= self._state.snapshot()['last_observed_ms'], 'PUBLICATION_V3_STAGE_TIME')
            intent = self._intents.get(command_id)
            _need(intent is not None, 'PUBLICATION_OWNED_PREPARATION_REQUIRED')
            try:
                receipt = self._store.stage(intent)
                descriptor = self._store.descriptor(receipt)
                self._append_event(self._event('STAGED', max(observed_ms, time.time_ns() // 1_000_000),
                    command_id=command_id, digest=command_digest, descriptor=descriptor))
                return self.lookup(command_id, command_digest)
            except BaseException as error:
                self._poison(error)

    def validated(self, command_id, command_digest, semantic_receipt_dict, *, observed_ms):
        return self._attested('VALIDATED', 'validation', semantic_receipt_dict, command_id, command_digest, observed_ms)

    def prepare_activation(self, command_id, command_digest, *, current, observed_ms):
        with self._locked():
            self._writable(); command = self._command(command_id, command_digest, 'VALIDATED')
            parent = command['capture_prepared']['parent_selection']
            selection = {'generation': parent['generation'] + 1, 'identity': state_model.selection_identity(
                self._project_id, command_id, command_digest, parent, command['descriptor'], command['bundle_manifest'])}
            proposed = {'schema': 'hh-godot-active-selection-1', 'command_id': command_id,
                'parent_selection': parent, 'selection': selection,
                'descriptor_sha256': state_model.digest(command['descriptor']), 'descriptor': command['descriptor']}
            event = self._event('ACTIVATING', observed_ms, command_id=command_id, digest=command_digest,
                current=current, selector=proposed,
                expected_selector_version=self._state.snapshot()['selected']['selector_version'])
            # Invalid current facts must not consume the store's one pending intent.
            state_model.reduce_event(self._state, event)
            with self._store_operations():
                receipt = self._store.lookup(command_id, command['bundle_manifest']['project_revision'])
                expected = self._store.inspect_selection()
                intent = self._store.prepare_selection(receipt, selection, expected=expected)
            try:
                _need(intent.source_bytes == canonical_bytes(proposed)
                      and _version(expected.version) == event['expected_selector_version'], 'PUBLICATION_SELECTION_INTENT_CHANGED')
                self._append_event(event)
            except BaseException as error: self._poison(error)
            self._selection_intents[command_id] = intent
            return self.lookup(command_id, command_digest)

    def select_prepared(self, command_id, command_digest, *, observed_ms):
        """Caller must immediately precede this with its live STARTED gate."""
        with self._locked():
            self._writable(); command = self._command(command_id, command_digest, 'ACTIVATING')
            state_model.integer(observed_ms)
            _need(observed_ms >= self._state.snapshot()['last_observed_ms'], 'PUBLICATION_V3_SELECT_TIME')
            state_model._deadline(command, observed_ms)
            intent = self._selection_intents.get(command_id)
            _need(intent is not None and intent.source_bytes == canonical_bytes(command['selector']),
                  'PUBLICATION_OWNED_SELECTION_REQUIRED')
            try:
                receipt = self._store.select(intent)
                self._append_event(self._event('SELECTED', max(observed_ms, time.time_ns() // 1_000_000),
                    command_id=command_id, digest=command_digest, activation_event_sha256=command['activation_event_sha256'],
                    selector_sha256=hashlib.sha256(receipt.source_bytes).hexdigest(), selector_version=_version(receipt.version)),
                    after_selector_effect=True)
                return self.lookup(command_id, command_digest)
            except BaseException as error:
                self._poison(error)

    def readback(self, command_id, command_digest, adoption_facts, *, observed_ms):
        return self._attested('READBACK', 'adoption', adoption_facts, command_id, command_digest, observed_ms)

    def commit(self, command_id, command_digest, *, observed_ms):
        with self._locked():
            self._writable(); command = self._command(command_id, command_digest)
            if command['phase'] == 'COMMITTED': return command
            _need(command['phase'] == 'READBACK', 'PUBLICATION_V3_COMMAND_PHASE')
            self._append_event(self._event('COMMITTED', observed_ms, command_id=command_id, digest=command_digest,
                                          readback_event_sha256=command['readback_event_sha256']))
            return self.lookup(command_id, command_digest)

    def failed(self, command_id, command_digest, *, reason, observed_ms):
        return self._attested('FAILED', 'reason', reason, command_id, command_digest, observed_ms)

    def unknown(self, command_id, command_digest, *, reason, observed_ms):
        return self._attested('UNKNOWN', 'reason', reason, command_id, command_digest, observed_ms)

    def stop(self, *, reason, observed_ms):
        with self._locked():
            self._writable(); self._refresh()
            return self._append_event(self._event('STOP', observed_ms, reason=reason))

    def selection_facts(self):
        with self._locked():
            try:
                self._refresh(); actual = self._store.inspect_selection()
                return {'selector': parse_json(actual.source_bytes), 'selector_version': _version(actual.version)}
            except BaseException as error: self._poison(error)

    def read_selected_bundle(self):
        with self._locked():
            try:
                self._refresh(); actual = self._store.inspect_selection()
                return self._store.read_descriptor(actual.descriptor)
            except BaseException as error: self._poison(error)

    def _report(self, state):
        value = state.snapshot()
        value.update(bootstrap_bytes_verified=True, journal_read_only=self._readonly,
            journal_held=self._held or value['held'], journal_event_sequence=self._head.sequence,
            public_ack=False, engine_effects_verified=False, execution_permitted=False)
        return value

    def lookup(self, command_id, command_digest=None):
        with self._locked():
            try: state = self._refresh()
            except BaseException as error: self._poison(error)
            return state_model.lookup(state, command_id, command_digest)
