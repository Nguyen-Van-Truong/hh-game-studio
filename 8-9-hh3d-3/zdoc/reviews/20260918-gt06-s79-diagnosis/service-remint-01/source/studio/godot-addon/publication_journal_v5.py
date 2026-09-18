"""V5 editor checkpoints and receipts in the existing protected publication log.

The outer owner verifies registered editor observations and authority. This
owner verifies their bindings and persists/readbacks actual private blobs.
No event replay restores a volatile editor or grants writable reopen.
"""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path
import sys
from studio.protocol.core import canonical_bytes, parse_json
from studio.host.core.custody import identity_from, identity_value
from studio.host.core.private_store import StagedBlob


def _load(filename):
    path = Path(__file__).with_name(filename).resolve(); raw = path.read_bytes()
    key = '_hh_journal_v5_' + hashlib.sha256(str(path).encode()+b'\0'+raw).hexdigest()
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key,path)
        module = importlib.util.module_from_spec(spec); sys.modules[key] = module
        try: exec(compile(raw,str(path),'exec'),module.__dict__)
        except BaseException:
            del sys.modules[key]
            raise
    return sys.modules[key]


state_model = _load('publication_state_v5.py')
base = _load('publication_journal_v4.py')
store_model, bundle_codec = base.store_model, base.bundle_codec
PublicationJournalV5Error = base.PublicationJournalV4Error
_need, _version, _identity = base._need, base._version, base._identity


class PublicationJournalV5(base.PublicationJournalV4):
    """Reuse V4 create/reopen owners and exact bootstrap; add typed edit records."""
    def _event(self, kind, observed_ms, **fields):
        event = super()._event(kind,observed_ms,**fields)
        if kind.startswith('EDIT_'): event['schema'] = state_model.EDIT_SCHEMA
        return event

    def _read_edit_blob(self, descriptor):
        state_model.blob_descriptor(descriptor,1048576)
        blob = StagedBlob(descriptor['object_id'],identity_from(descriptor['identity']),descriptor['sha256'])
        return self._blobs.read_blob(blob)

    def _put_edit_blob(self, raw):
        blob = self._blobs.put_bytes(raw)
        _need(self._blobs.read_blob(blob)==raw,'PUBLICATION_EDIT_BLOB_READBACK')
        return {'object_id':blob.object_id,'identity':identity_value(blob.identity),'sha256':blob.sha256}

    def _verify_edit_blobs(self, snapshot):
        for command in snapshot['commands']:
            if 'checkpoint' not in command: continue
            p, checkpoint = command['edit_prepared'],command['checkpoint']
            scene = self._read_edit_blob(checkpoint['scene_blob'])
            capture_raw = self._read_edit_blob(checkpoint['capture_blob'])
            capture = parse_json(capture_raw)
            _need(capture_raw==canonical_bytes(capture) and hashlib.sha256(scene).hexdigest()==capture['scene_sha256']
                  and len(scene)==capture['scene_size_bytes'],'PUBLICATION_EDIT_CHECKPOINT_BYTES')
            summary = state_model.capture_summary(capture,p,checkpoint['observed_ms'])
            _need(state_model.same(summary,checkpoint['capture']),'PUBLICATION_EDIT_CAPTURE_BLOB_BINDING')
            if 'edit_observation' in command:
                raw = self._read_edit_blob(command['observation_blob']); observation = parse_json(raw)
                _need(raw==canonical_bytes(observation),'PUBLICATION_EDIT_OBSERVATION_CANONICAL')
                summary = state_model.observation_summary(observation,command,snapshot['last_observed_ms'])
                _need(state_model.same(summary,command['edit_observation']),'PUBLICATION_EDIT_OBSERVATION_BLOB_BINDING')

    def _fold_verified(self):
        records = self._native_events()
        _need(records[:3]==self._bootstrap,'PUBLICATION_BOOTSTRAP_HISTORY_MISMATCH')
        config = self._verify_bootstrap(); events = records[3:]
        _need(events and events[0]==canonical_bytes(config),'PUBLICATION_BOOTSTRAP_CONFIG_MISMATCH')
        state = state_model.replay(events); snapshot = state.snapshot()
        _need(snapshot['project_id']==self._project_id and snapshot['content_root_identity']==_identity(self._files),
              'PUBLICATION_CONFIG_IDENTITY_MISMATCH')
        current = self._store.inspect_selection(); expected = snapshot['selected']
        _need(current is not None and current.source_bytes==canonical_bytes(expected['selector'])
              and _version(current.version)==expected['selector_version'],'PUBLICATION_SELECTED_STATE_CHANGED')
        _need(self._store.read_descriptor(expected['selector']['descriptor']).manifest_bytes
              ==canonical_bytes(expected['bundle_manifest']),'PUBLICATION_SELECTED_BUNDLE_CHANGED')
        self._verify_edit_blobs(snapshot); self._verify_owners()
        return state

    def _append_event(self,event,*,after_selector_effect=False):
        prospective = state_model.reduce_event(self._state,event)
        checked = parse_json(prospective.events[-1])
        try:
            if self._state is None or after_selector_effect: self._verify_owners()
            else: self._refresh()
            reserve = state_model.MAX_EVENTS-prospective.event_count
            self._head = self._log.append(checked,self._head,reserve_records=reserve,
                reserve_bytes=reserve*(state_model.MAX_EVENT_BYTES+512))
            observed = self._fold_verified()
            _need(observed.events==prospective.events,'PUBLICATION_APPEND_READBACK_MISMATCH')
            self._state = observed
            return self._report(observed)
        except BaseException as error: self._poison(error)

    def append(self,event):
        raise PublicationJournalV5Error('PUBLICATION_V5_TYPED_METHOD_REQUIRED')

    def prepare(self,command_id,command_digest,bundle,*,observed_ms):
        # V4's typed implementation with this reducer; no mutable module globals.
        with self._locked():
            self._writable(); self._command(command_id,command_digest,'CAPTURED')
            with self._store_operations(): intent = self._store.prepare(command_id,bundle)
            event = self._event('PREPARED',observed_ms,command_id=command_id,digest=command_digest,
                planned_names=dict(intent.names),bundle_manifest=parse_json(bundle.manifest_bytes))
            try: state_model.reduce_event(self._state,event)
            except BaseException as cause:
                try:
                    with self._store_operations(): self._store.cancel_unused_prepare(intent)
                except BaseException as cleanup_error:
                    if not isinstance(cause,Exception):
                        self._held=True; cause.cleanup_owner=self
                        raise cause from cleanup_error
                    raise
                raise
            self._intents[command_id]=intent; self._bundles[command_id]=bundle
            self._append_event(event)
            return self.lookup(command_id,command_digest)

    def prepare_activation(self,command_id,command_digest,*,current,observed_ms):
        with self._locked():
            self._writable(); command=self._command(command_id,command_digest)
            phase='RETIRED' if command['capture_prepared']['operation']=='script_text.replace' else 'VALIDATED'
            _need(command['phase']==phase,'PUBLICATION_V5_COMMAND_PHASE')
            parent=command['capture_prepared']['parent_selection']
            selection={'generation':parent['generation']+1,'identity':state_model.selection_identity(
                self._project_id,command_id,command_digest,parent,command['descriptor'],command['bundle_manifest'])}
            proposed={'schema':'hh-godot-active-selection-1','command_id':command_id,'parent_selection':parent,
                'selection':selection,'descriptor_sha256':state_model.digest(command['descriptor']),'descriptor':command['descriptor']}
            event=self._event('ACTIVATING',observed_ms,command_id=command_id,digest=command_digest,current=current,
                selector=proposed,expected_selector_version=self._state.snapshot()['selected']['selector_version'])
            state_model.reduce_event(self._state,event)
            with self._store_operations():
                receipt=self._store.lookup(command_id,command['bundle_manifest']['project_revision'])
                expected=self._store.inspect_selection(); intent=self._store.prepare_selection(receipt,selection,expected=expected)
            try:
                _need(intent.source_bytes==canonical_bytes(proposed) and _version(expected.version)==event['expected_selector_version'],
                      'PUBLICATION_SELECTION_INTENT_CHANGED')
                self._append_event(event)
            except BaseException as error: self._poison(error)
            self._selection_intents[command_id]=intent
            return self.lookup(command_id,command_digest)

    def edit_prepared(self,command_id,command_digest,*,operation,projection,expected_revision,editor,editor_generation,
                      root_instance_id,admission,scratch_name,lease_owner,observed_ms):
        with self._locked():
            self._writable()
            try: state=self._refresh()
            except BaseException as error: self._poison(error)
            prior=state_model.lookup(state,command_id,command_digest)
            if prior is not None: return prior
            projection_hash,projection_size=state_model.projection_binding(projection,command_id,operation,expected_revision,editor_generation)
            selected=state.snapshot()['selected']
            event=self._event('EDIT_INTENT',observed_ms,command_id=command_id,digest=command_digest,
                operation=operation,projection_sha256=projection_hash,projection_size_bytes=projection_size,
                before_project_revision=selected['bundle_manifest']['project_revision'],before_scene_revision=expected_revision,
                expected_files=selected['bundle_manifest']['files'],parent_selection=selected['selector']['selection'],
                previous_selector_version=selected['selector_version'],previous_selector_sha256=state_model.digest(selected['selector']),
                editor=editor,editor_generation=editor_generation,root_instance_id=root_instance_id,
                admission=admission,scratch_name=scratch_name,lease_owner=lease_owner)
            self._append_event(event)
            return self.lookup(command_id,command_digest)

    def edit_checkpoint(self,command_id,command_digest,*,capture,scene_bytes,observed_ms):
        with self._locked():
            self._writable(); command=self._command(command_id,command_digest,'EDIT_INTENT')
            state_model.integer(observed_ms)
            _need(observed_ms>=self._state.snapshot()['last_observed_ms'],'PUBLICATION_EDIT_CHECKPOINT_TIME')
            summary=state_model.capture_summary(capture,command['edit_prepared'],observed_ms)
            _need(type(scene_bytes) is bytes and 1<=len(scene_bytes)<=state_model.MAX_SCENE_BYTES
                  and len(scene_bytes)==summary['scene_size_bytes'] and hashlib.sha256(scene_bytes).hexdigest()==summary['scene_sha256'],
                  'PUBLICATION_EDIT_CHECKPOINT_BYTES')
            raw=canonical_bytes(capture)
            try:
                scene_blob=self._put_edit_blob(scene_bytes); capture_blob=self._put_edit_blob(raw)
                self._append_event(self._event('EDIT_READY',observed_ms,command_id=command_id,digest=command_digest,
                    scene_blob=scene_blob,capture_blob=capture_blob,capture=summary))
                return self.lookup(command_id,command_digest)
            except BaseException as error: self._poison(error)

    def edit_committed(self,command_id,command_digest,*,observation,response=None,observed_ms):
        with self._locked():
            self._writable(); command=self._command(command_id,command_digest)
            if command['phase']=='COMMITTED':
                _need('edit_prepared' in command,'PUBLICATION_EDIT_COMMAND_REQUIRED')
                return command
            _need(command['phase']=='EDIT_READY','PUBLICATION_EDIT_COMMAND_PHASE')
            state_model.integer(observed_ms)
            _need(observed_ms>=self._state.snapshot()['last_observed_ms'],'PUBLICATION_EDIT_COMMIT_TIME')
            summary=state_model.observation_summary(observation,command,observed_ms)
            raw=canonical_bytes(observation)
            try:
                descriptor=self._put_edit_blob(raw)
                pending={**command,'edit_observation':summary,'observation_blob':descriptor}
                expected=state_model.terminal_plan(self._state.snapshot(),pending)['response']
                if response is None: response=expected
                _need(state_model.same(response,expected),'PUBLICATION_EDIT_ORIGINAL_RESPONSE_MISMATCH')
                self._append_event(self._event('EDIT_COMMITTED',observed_ms,command_id=command_id,digest=command_digest,
                    observation_blob=descriptor,observation=summary,response=response))
                return self.lookup(command_id,command_digest)
            except BaseException as error: self._poison(error)

    def _terminal(self,kind,command_id,command_digest,reason,observed_ms):
        with self._locked():
            self._writable(); command=self._command(command_id,command_digest)
            if 'edit_prepared' not in command:
                return super()._terminal(kind,command_id,command_digest,reason,observed_ms)
            response=state_model.terminal_plan(self._state.snapshot(),command,kind,reason)['response']
            self._append_event(self._event('EDIT_'+kind,observed_ms,command_id=command_id,digest=command_digest,
                reason=reason,response=response))
            return self.lookup(command_id,command_digest)

    def checkpoint_bytes(self,command_id,command_digest):
        with self._locked():
            command=self._command(command_id,command_digest)
            _need('checkpoint' in command,'PUBLICATION_EDIT_CHECKPOINT_REQUIRED')
            try: return self._read_edit_blob(command['checkpoint']['scene_blob'])
            except BaseException as error: self._poison(error)

    def lookup_response(self,command_id,command_digest):
        with self._locked():
            try: state=self._refresh()
            except BaseException as error: self._poison(error)
            return state_model.lookup_response(state,command_id,command_digest)
