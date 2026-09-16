"""Authenticated owned-fixture scene/script coordinator (GT-03 candidate).

Only registered editor/validator owners can supply observations. Journal v5
owns native selected bytes. No artist-project path, arbitrary operation,
general GDScript or recovered writable owner is enabled by this module.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import importlib.util
from pathlib import Path
import re
import sys
import threading
import uuid

from studio.protocol.core import Request, Response, Status, canonical_bytes, parse_json
from studio.host.core.transport import epoch_ms
from studio.host.core.limits import SafetyViolation

HERE = Path(__file__).resolve().parent


def _load(name):
    path = HERE / (name + '.py')
    raw = path.read_bytes()
    key = '_hh_publication_owner_' + hashlib.sha256(str(path).encode() + b'\0' + raw).hexdigest()
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        try:
            exec(compile(raw, str(path), 'exec'), module.__dict__)
        except BaseException:
            del sys.modules[key]
            raise
    return sys.modules[key]


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


class PublicationOwnerError(SafetyViolation):
    def __init__(self, code, *, cleanup_owner=None):
        self.cleanup_owner = cleanup_owner
        super().__init__(code)


def _need(condition, code):
    if not condition:
        raise PublicationOwnerError(code)


class GodotPublicationOwner:
    """One live project/editor and one serialized save, independent Stop lane."""
    def __init__(self):
        raise TypeError('use create')

    @classmethod
    def create(cls, parent: Path, *, project_id: str, initial_bundle, editor_binary: Path,
               source_closure_sha256: str):
        _need(parent.is_absolute() and parent.is_dir(), 'GODOT_OWNED_PARENT_REQUIRED')
        _need(type(source_closure_sha256) is str and re.fullmatch('[0-9a-f]{64}', source_closure_sha256),
              'GODOT_SOURCE_CLOSURE_REQUIRED')
        owner = object.__new__(cls)
        owner._lock = threading.RLock()
        owner._work = threading.Lock()
        owner._closed = owner._held = False
        owner._jobs, owner._leases, owner._read_leases = {}, {}, {}
        owner._stop_thread = None
        owner._stop_persistence = 'NOT_REQUESTED'
        owner._editor = owner._validator = owner._journal = None
        owner._retired_editors, owner._cleanup_owners = [], []
        owner._editor_binary = editor_binary
        owner.project_id = project_id
        owner.contract = _load('contract')
        owner.auth_model = _load('publication_session')
        owner.editor_model = _load('editor_owner')
        owner.validation_model = _load('validation_owner')
        owner.journal_model = _load('publication_journal_v5')
        owner.sessions = owner.auth_model.PublicationSession(project_id, parent, owner.contract.CATALOG_DIGEST)
        owner._source_release = owner.validation_model.source_release()
        owner._source_closure_sha256 = source_closure_sha256
        owner.storage_id = uuid.uuid4().hex
        try:
            validation_parent, editor_parent, storage_parent = (parent / x for x in ('validation', 'editor', 'storage'))
            for directory in (validation_parent, editor_parent, storage_parent):
                directory.mkdir(exist_ok=False)
            owner._editor_parent = editor_parent
            owner._validator = owner.validation_model.ValidationOwner(validation_parent)
            initial_receipt = owner._validator.validate('bootstrap.validation', initial_bundle)
            initial, receipt = owner._validator.bind_semantics(initial_receipt, initial_bundle)
            observation = owner._validator.semantic_observation(receipt, initial)
            owner._editor = owner.editor_model.EditorOwner(editor_parent, initial, editor_binary=editor_binary)
            inspected = owner._editor.inspect()
            _need(canonical_bytes(inspected['state']) == owner.validation_model.comparator.semantic_state_bytes(
                observation['semantic']), 'GODOT_INITIAL_EDITOR_SEMANTICS')
            _need(inspected['revision'] == initial.scene_revision, 'GODOT_INITIAL_EDITOR_REVISION')
            owner._journal = owner.journal_model.PublicationJournalV5.create(storage_parent,
                storage_id=owner.storage_id, config={
                    'schema': owner.journal_model.state_model.SCHEMA, 'kind':'CONFIG', 'sequence':1,
                    'project_id':project_id, 'observed_ms':epoch_ms(),
                    'validator_engine_sha256':initial.engine_sha256,
                    'editor_engine_sha256':owner._editor.identity['engine_sha256'],
                    'source_closure_sha256':source_closure_sha256,
                    'validation_source_release_sha256':owner._source_release[1]}, initial_bundle=initial)
            owner._initial_receipt = receipt
            owner._same_release()
            return owner
        except BaseException as exc:
            retained = getattr(exc,'cleanup_owner',None)
            if retained is not None and retained is not owner:
                owner._cleanup_owners.append(retained)
            try:
                owner.close()
            except BaseException as close_exc:
                raise PublicationOwnerError('GODOT_CREATE_CLEANUP_REQUIRED', cleanup_owner=owner) from close_exc
            raise

    def _same_release(self):
        _need(self.validation_model.source_release() == self._source_release, 'GODOT_SOURCE_CHANGED')

    def _qualify_script(self, raw):
        profile = self.validation_model.factory._sibling('script_profile')
        try:
            return profile.validate_script(raw)
        except profile.ScriptProfileError as error:
            # User input outside the advertised declarative profile is a
            # pre-admission rejection, with no exception text on the wire.
            raise PublicationOwnerError('GODOT_SCRIPT_PROFILE_REJECTED') from error

    def _auth(self, body, operation, authorization, catalog_digest, keys=None):
        _need(type(body) is dict and (keys is None or set(body) == keys), 'GODOT_INVALID_ENVELOPE')
        grant = self.sessions.authorize(authorization, operation,
            project_id=body.get('project_id'), catalog_digest=catalog_digest)
        _need(not self._closed, 'GODOT_OWNER_CLOSED')
        return grant

    def discover(self, body, *, authorization, catalog_digest):
        self._auth(body, 'scene.inspect', authorization, catalog_digest, {'project_id'})
        self._same_release()
        implemented = self.auth_model.READ_OPERATIONS | self.auth_model.EDIT_OPERATIONS | frozenset({'scene.save', 'script_text.replace'})
        enabled = implemented if not self._held else frozenset()
        if self.sessions.status()['stopped'] and not self._held:
            enabled = frozenset({'scene.inspect','scene.preview'})
        return self.contract.discovery(self.project_id, implemented=implemented,
                                       runtime_enabled=enabled)

    def lease(self, body, *, authorization, catalog_digest):
        keys = set(body) if type(body) is dict else set()
        _need(keys in ({'project_id','ttl_ms'},{'project_id','ttl_ms','access'}),'GODOT_INVALID_ENVELOPE')
        grant = self.sessions.authenticate(authorization)
        # A writer lease carries no extra operation grant. Every phase still
        # checks the exact requested operation against its registered grant.
        writable = frozenset({'scene.save','script_text.replace',
            'scene.node.create','scene.node.update','scene.node.remove','scene.undo','scene.redo'})
        readable = frozenset({'scene.inspect','scene.preview'})
        access = body.get('access','write' if writable.intersection(grant.operations) else 'read')
        _need(access in ('read','write'),'GODOT_INVALID_LEASE_ACCESS')
        allowed = (writable if access=='write' else readable).intersection(grant.operations)
        _need(bool(allowed),'GODOT_OPERATION_FORBIDDEN')
        self._auth(body,sorted(allowed)[0],authorization,catalog_digest)
        with self._lock:
            if access == 'read':
                lease = self.sessions.read_lease(grant,ttl_ms=body['ttl_ms'])
                self._read_leases[grant.session_id] = lease
                return asdict(lease)
            _need(not self._held, 'GODOT_OWNER_HELD')
            lease = self.sessions.lease(grant, ttl_ms=body['ttl_ms'])
            self._leases = {grant.session_id:lease}
            return asdict(lease)

    def inspect(self):
        """Trusted local observation; public inspection uses strict Request."""
        current = self._editor.inspect()
        bundle = self._journal.read_selected_bundle()
        current.update(project_revision=bundle.project_revision,
                       selected_files=parse_json(bundle.manifest_bytes)['files'])
        return current

    def _context(self, inspected, lease):
        nodes = []
        for row in inspected['state']['nodes']:
            nodes.append(self.contract.NodeState(row['stable_id'], row['parent_id'] or None,
                row['node_type'], row['name'], tuple(row['position']), tuple(row['rotation_degrees']),
                tuple(row['scale']), tuple(row['box_size']) if 'box_size' in row else None))
        hashes = {path:row['sha256'] for path,row in inspected['working_files'].items()}
        return self.contract.ValidationContext(self.project_id, inspected['revision'],
            inspected['project_revision'], inspected['generation'], lease.lease_id, lease.fencing_epoch,
            lease.expires_ms, epoch_ms(), tuple(nodes), tuple((p,hashes[p]) for p in
            (self.contract.SCENE_PATH,self.contract.SCRIPT_PATH)), can_undo=inspected['can_undo'],
            can_redo=inspected['can_redo'], stopped=self.sessions.status()['stopped'])

    def submit(self, body, *, authorization, catalog_digest):
        request = Request.from_dict(body)
        _need(request.operation in ('scene.inspect','scene.preview','scene.save','script_text.replace',
              'scene.node.create','scene.node.update','scene.node.remove','scene.undo','scene.redo'),
              'GODOT_OPERATION_NOT_ENABLED')
        grant = self._auth(body, request.operation, authorization, catalog_digest)
        self.sessions.validate_public_identifier(request.command_id)
        # Dedupe before deadline/current lease checks. Old registered results
        # remain readable after response loss, but a changed digest is rejected.
        with self._lock:
            previous = self._jobs.get(request.command_id)
            if previous:
                _need(previous['digest'] == request.digest, 'GODOT_COMMAND_CONFLICT')
            else:
                _need(not self._held, 'GODOT_OWNER_HELD')
                lease = self._leases.get(grant.session_id)
                if request.operation in ('scene.inspect','scene.preview'):
                    read_lease = self._read_leases.get(grant.session_id)
                    if read_lease is not None and read_lease.lease_id == request.lease_id:
                        lease = read_lease
                _need(lease is not None, 'GODOT_LEASE_REQUIRED')
                _need(len(self._jobs) < 64,'GODOT_COMMAND_LIMIT')
                _need(self._work.acquire(blocking=False), 'GODOT_OWNER_BUSY')
        if previous:
            return self._reply(request.command_id, previous)
        try:
            self._same_release()
            before = self.inspect()
            validated = self.contract.validate_request(request, self._context(before, lease))
            if request.operation == 'scene.inspect':
                return Response(Status.COMMITTED, 'GODOT_SCENE_INSPECTED', request.command_id,
                                postconditions=before)
            if request.operation == 'scene.preview':
                preview = validated.preview
                if request.payload['operation'] == 'script_text.replace':
                    proposed = request.payload['payload']['text'].encode('utf-8')
                    self._qualify_script(proposed)
                    selected = self._journal.read_selected_bundle()
                    preview = self.contract.script_preview(selected.files[self.contract.SCRIPT_PATH],validated)
                    preview['script_profile'] = 'hh-godot-declarative-1'
                return Response(Status.COMMITTED,'GODOT_PREVIEW_READY',request.command_id,
                                postconditions=preview)
            if request.operation == 'script_text.replace':
                self._qualify_script(request.payload['text'].encode('utf-8'))
                _need(before['generation'] < 2**31-1,'GODOT_EDITOR_GENERATION_EXHAUSTED')
            self.sessions.check(grant, lease, deadline_ms=request.deadline_ms, operation=request.operation)
            self.sessions.check_command_budget()
            editing = request.operation in self.auth_model.EDIT_OPERATIONS
            # Every admitted edit must retain a validation attempt for its save.
            _need(len(self._validator.snapshot()['attempts']) < self.validation_model.MAX_RUNS,
                  'GODOT_VALIDATION_BUDGET_EXHAUSTED')
            # Keep a capture+adopt pair for saving after an unsaved edit.
            # Reject before admission, never consume the final save capacity.
            required = 4 if editing else 2
            _need(len(self._editor._intents) + required <= self.editor_model.MAX_EFFECTS,
                  'GODOT_EDITOR_EFFECT_BUDGET_EXHAUSTED')
            record = {'digest':request.digest, 'status':'UNKNOWN', 'code':'GODOT_ADMISSION_NOT_DURABLE'}
            with self._lock:
                self._jobs[request.command_id] = record
            return (self._edit if editing else self._save)(request, grant, lease, before, validated, record)
        finally:
            self._work.release()

    def _phase(self, request, grant, lease, phase, effect):
        # effect is a private owner method invocation, never a wire callback.
        permit = self.sessions.reserve_phase(grant, lease, command_id=request.command_id,
            digest=request.digest, phase=phase, deadline_ms=request.deadline_ms, operation=request.operation)
        try:
            self.sessions.start_effect(permit)
        except BaseException:
            try:
                self.sessions.cancel_reserved(permit)
            except SafetyViolation:
                pass  # A concurrent Stop may already have cancelled it.
            raise
        try:
            result = effect()
        except BaseException:
            self.sessions.finish_effect(permit, known=False)
            raise
        self.sessions.finish_effect(permit, known=True)
        return result

    def _edit(self, request, grant, lease, before, validated, record):
        """Retain native history; persist a checkpoint and exact historical ACK.

        The receipt commits an observed editor-session effect. It does not
        claim that selected project files or unsaved live state were persisted.
        """
        command, digest = request.command_id, request.digest
        durable = admission_attempted = False
        try:
            intent = self._editor.prepare_effect(command,digest,'capture',
                expected_generation=before['generation'],expected_revision=before['revision'],
                deadline_ms=min(request.deadline_ms,epoch_ms()+10_000))
            admitted = epoch_ms()
            admission_attempted = True
            self._journal.edit_prepared(command,digest,operation=request.operation,
                projection=validated.projection,expected_revision=before['revision'],
                editor=self._editor.identity,editor_generation=before['generation'],
                root_instance_id=self._instance(before['root_instance_id']),
                admission={'session_id':grant.session_id,'catalog_digest':grant.catalog_digest,
                    'lease_id':lease.lease_id,'fencing_epoch':lease.fencing_epoch,'admitted_ms':admitted,
                    'deadline_ms':request.deadline_ms,'lease_expires_ms':lease.expires_ms},
                scratch_name=intent.scratch_name,lease_owner=grant.session_id,observed_ms=admitted)
            durable = True
            self._update_record(record,status='ACCEPTED_PENDING',code='GODOT_EDIT_PENDING')
            captured = self._phase(request,grant,lease,'capture',lambda:self._editor.capture(intent))
            capture = self._editor.observation(captured)
            self._fact_identity(capture)
            _need(capture['working_files'] == before['working_files']
                  and self._editor.captured_semantic(captured) == canonical_bytes(before['state']),
                  'GODOT_EDIT_CHECKPOINT_CHANGED')
            scene = self._editor.capture_bytes(captured)
            self._phase(request,grant,lease,'stage',lambda:self._journal.edit_checkpoint(
                command,digest,capture=capture,scene_bytes=scene,observed_ms=epoch_ms()))
            # Preparation is part of the admitted edit phase. A concurrent Stop
            # before this phase sends no prepare/consume RPC to the engine.
            def apply():
                prepared = self._editor.prepare_edit(command,digest,validated.projection,captured,
                    deadline_ms=min(request.deadline_ms,epoch_ms()+10_000))
                return self._editor.apply_edit(prepared)
            edited = self._phase(request,grant,lease,'edit',apply)
            def finalize():
                observed = self._editor.observation(edited)
                self._fact_identity(observed)
                _need(observed['working_files'] == before['working_files']
                      and observed['generation_after'] == before['generation']
                      and observed['root_after'] == before['root_instance_id']
                      and observed['files_saved'] is False and observed['live_state_durable'] is False,
                      'GODOT_EDIT_CONTEXT_CHANGED')
                self._same_release()
                return self._journal.edit_committed(command,digest,observation=observed,observed_ms=epoch_ms())
            self._phase(request,grant,lease,'commit',finalize)
            self._remember_response(command,record)
            return self._reply(command,record)
        except BaseException as exc:
            retained = getattr(exc,'cleanup_owner',None)
            if retained is not None and retained is not self and retained is not self._editor:
                if not any(resource is retained for resource in self._cleanup_owners):
                    self._cleanup_owners.append(retained)
            self._held = True
            self.sessions.halt()
            self._last_error = exc
            uncertain = durable or admission_attempted or getattr(exc,'outcome_unknown',False)
            cause = getattr(exc,'code','GODOT_EDIT_INTERNAL_ERROR')
            if type(cause) is not str or not re.fullmatch('[A-Z][A-Z0-9_]{0,63}',cause):
                cause = 'GODOT_EDIT_INTERNAL_ERROR'
            self._update_record(record,status='UNKNOWN' if uncertain else 'REJECTED',
                code='GODOT_EDIT_RECONCILE_REQUIRED' if uncertain else 'GODOT_EDIT_NOT_ADMITTED',
                durable_response_sha256=None,postconditions={'request_digest':digest,
                    'public_ack':False,'failure_code':cause,'next_action':'lookup.reconcile'})
            if durable:
                try:
                    persisted = self._journal.lookup(command,digest)
                    if persisted is None or persisted['phase'] not in ('COMMITTED','FAILED','UNKNOWN'):
                        self._journal.unknown(command,digest,reason='owner.effect.uncertain',observed_ms=epoch_ms())
                    self._remember_response(command,record)
                except BaseException:
                    pass  # Preserve owned resources and native evidence for recovery.
            if isinstance(exc,(KeyboardInterrupt,SystemExit)):
                raise
            return self._reply(command,record)

    def _save(self, request, grant, lease, before, validated, record):
        command, digest = request.command_id, request.digest
        replacing = request.operation == 'script_text.replace'
        script_bytes = request.payload['text'].encode('utf-8') if replacing else None
        script_change = ({'path':self.contract.SCRIPT_PATH,
            'expected_sha256':request.payload['expected_sha256'],
            'sha256':_sha(script_bytes),'size_bytes':len(script_bytes)} if replacing else None)
        durable = False
        admission_attempted = False
        try:
            intent = self._editor.prepare_effect(command, digest, 'capture',
                expected_generation=before['generation'], expected_revision=before['revision'],
                deadline_ms=min(request.deadline_ms,epoch_ms()+10_000))
            admitted = epoch_ms()
            admission_attempted = True
            self._journal.capture_prepared(command, digest, expected_revision=before['revision'],
                operation=request.operation, script_change=script_change,
                editor=self._editor.identity, editor_generation=before['generation'],
                root_instance_id=self._instance(before['root_instance_id']),
                admission={'session_id':grant.session_id, 'catalog_digest':grant.catalog_digest,
                    'lease_id':lease.lease_id, 'fencing_epoch':lease.fencing_epoch, 'admitted_ms':admitted,
                    'deadline_ms':request.deadline_ms, 'lease_expires_ms':lease.expires_ms},
                scratch_name=intent.scratch_name, observed_ms=admitted)
            durable = True
            self._update_record(record,status='ACCEPTED_PENDING',code='GODOT_SAVE_PENDING')
            captured = self._phase(request,grant,lease,'capture',lambda:self._editor.capture(intent))
            capture_raw = self._editor.observation(captured)
            capture = self._capture_facts(capture_raw,intent,before)
            self._journal.captured(command,digest,capture,observed_ms=epoch_ms())
            current_bundle = self._journal.read_selected_bundle()
            raw = self._editor.capture_bytes(captured)
            candidate = self.validation_model.factory.compose(raw,
                script_bytes if replacing else current_bundle.files[self.contract.SCRIPT_PATH],
                scene_revision=before['revision'],
                engine_sha256=current_bundle.engine_sha256)
            self.sessions.check(grant,lease,deadline_ms=request.deadline_ms,operation=request.operation)
            original = self._validator.validate(command,candidate)
            final, semantic_receipt = self._validator.bind_semantics(original,candidate)
            semantic = self._validator.semantic_observation(semantic_receipt,final)
            semantic_bytes = self.validation_model.comparator.semantic_state_bytes(semantic['semantic'])
            _need(self._editor.captured_semantic(captured) == canonical_bytes(before['state']),
                  'GODOT_CAPTURE_VALIDATION_MISMATCH')
            if replacing:
                _need(final.files[self.contract.SCENE_PATH] == raw
                      and final.files[self.contract.SCRIPT_PATH] == script_bytes,
                      'GODOT_SCRIPT_BUNDLE_CHANGED')
            else:
                _need(semantic_bytes == canonical_bytes(before['state']),
                      'GODOT_CAPTURE_VALIDATION_MISMATCH')
            self.sessions.check(grant,lease,deadline_ms=request.deadline_ms,operation=request.operation)
            self._journal.prepare(command,digest,final,observed_ms=epoch_ms())
            self._phase(request,grant,lease,'stage',
                lambda:self._journal.stage_prepared(command,digest,observed_ms=epoch_ms()))
            self._validator.semantic_observation(semantic_receipt,final)
            self._journal.validated(command,digest,asdict(semantic_receipt),observed_ms=epoch_ms())
            ready = self.inspect()
            _need(all(ready[k] == before[k] for k in ('revision','generation','root_instance_id','state','working_files',
                      'project_revision')), 'GODOT_EDITOR_CHANGED_DURING_VALIDATION')
            command_state = self._journal.lookup(command,digest)
            current = self.journal_model.state_model.activation_current(command_state['capture_prepared'])
            old_editor = self._editor
            retired = None
            if replacing:
                retire_id = 'retire.' + uuid.uuid4().hex
                retire_deadline = min(request.deadline_ms,epoch_ms()+10_000)
                self._journal.retire_prepared(command,digest,current=current,
                    retirement_intent_id=retire_id,deadline_ms=retire_deadline,observed_ms=epoch_ms())
                # Keep ownership even if Stop/revocation wins just after the
                # retirement effect, before its phase can report completion.
                self._retired_editors.append(old_editor)
                retired = self._phase(request,grant,lease,'retire',lambda:
                    old_editor.retire_for_replacement(command,digest,
                        retirement_intent_id=retire_id,expected_snapshot=before,deadline_ms=retire_deadline))
                facts = old_editor.retirement_observation(retired)
                self._journal.retired(command,digest,self._retirement_facts(retired,facts),observed_ms=epoch_ms())
            self._journal.prepare_activation(command,digest,current=current,observed_ms=epoch_ms())
            self._phase(request,grant,lease,'select',
                lambda:self._journal.select_prepared(command,digest,observed_ms=epoch_ms()))
            selected = self._journal.read_selected_bundle()
            _need(selected == final, 'GODOT_SELECTED_BUNDLE_MISMATCH')
            selection = self._journal.selection_facts()
            self.sessions.check(grant,lease,deadline_ms=request.deadline_ms,operation=request.operation)
            if replacing:
                def open_generation():
                    successor, receipt = self.editor_model.EditorOwner.open_selected_generation(
                        old_editor,retired,self._editor_parent,selected,editor_binary=self._editor_binary,
                        selection=selection['selector']['selection'],semantic_bytes=semantic_bytes)
                    self._editor = successor
                    return receipt
                adopted = self._phase(request,grant,lease,'adopt',open_generation)
                adoption = self._fresh_adoption_facts(adopted,
                    self._editor.observation(adopted,selected),selected,selection)
            else:
                adoption_intent = self._editor.prepare_effect(command,digest,'adopt',
                    expected_generation=before['generation'],expected_revision=before['revision'],
                    deadline_ms=min(request.deadline_ms,epoch_ms()+10_000))
                adopted = self._phase(request,grant,lease,'adopt',
                    lambda:self._editor.adopt(adoption_intent,selected,selection['selector']['selection']))
                adoption = self._adoption_facts(self._editor.observation(adopted,selected),selected,selection)
            def finalize():
                self._editor.observation(adopted,selected)
                self._validator.semantic_observation(semantic_receipt,selected)
                self._same_release()
                self._journal.readback(command,digest,adoption,observed_ms=epoch_ms())
                return self._journal.commit(command,digest,observed_ms=epoch_ms())
            terminal = self._phase(request,grant,lease,'commit',finalize)
            receipt = terminal['receipt']
            _need(receipt['status'] == 'COMMITTED', 'GODOT_DURABLE_COMMIT_REQUIRED')
            self._remember_response(command,record)
            return self._reply(command,record)
        except BaseException as exc:
            cleanup_owner = getattr(exc,'cleanup_owner',None)
            if cleanup_owner is not None and cleanup_owner is not self:
                if not any(resource is cleanup_owner for resource in self._cleanup_owners):
                    self._cleanup_owners.append(cleanup_owner)
            self._held = True
            self.sessions.halt()
            uncertain = durable or admission_attempted or getattr(exc,'outcome_unknown',False)
            cause = getattr(exc,'code','GODOT_SAVE_INTERNAL_ERROR')
            if type(cause) is not str or not re.fullmatch('[A-Z][A-Z0-9_]{0,63}',cause):
                cause = 'GODOT_SAVE_INTERNAL_ERROR'
            self._last_error = exc  # Trusted local diagnostic; never serialize exception text.
            self._update_record(record,status='UNKNOWN' if uncertain else 'REJECTED',
                durable_response_sha256=None,
                code='GODOT_SAVE_RECONCILE_REQUIRED' if uncertain else 'GODOT_SAVE_NOT_ADMITTED',
                postconditions={'request_digest':digest,'public_ack':False,'failure_code':cause,
                                'next_action':'lookup.reconcile'})
            if durable:
                try:
                    persisted = self._journal.lookup(command,digest)
                    if persisted is None or persisted['phase'] not in ('COMMITTED','FAILED','UNKNOWN'):
                        self._journal.unknown(command,digest,reason='owner.effect.uncertain',observed_ms=epoch_ms())
                    self._remember_response(command,record)
                except BaseException:
                    pass  # Keep the entire owner and native receipts for readonly recovery.
            if isinstance(exc,(KeyboardInterrupt,SystemExit)):
                raise
            return self._reply(command,record)

    @staticmethod
    def _instance(value):
        _need(type(value) is str and re.fullmatch('[1-9][0-9]{0,15}',value)
              and int(value) <= 2**53-1,'GODOT_INSTANCE_RANGE')
        return int(value)

    def _fact_identity(self, facts):
        identity = {'session_id':facts['editor_session_id'], 'pid':facts['editor_pid'],
            'creation_filetime':facts['editor_creation_time'],'root_identity':facts['project_root_identity'],
            'engine_sha256':facts['editor_engine_sha256'],'installed_source_sha256':facts['source_release_sha256']}
        _need(identity == self._editor.identity,'GODOT_EDITOR_IDENTITY_CHANGED')
        return identity

    def _capture_facts(self, facts, intent, before):
        _need(facts['working_files'] == before['working_files'],'GODOT_CAPTURE_WORKING_FILES_CHANGED')
        files = parse_json(canonical_bytes(before['selected_files']))
        _need(all({k:row[k] for k in ('sha256','size_bytes')} == facts['working_files'][path]
                  for path,row in files.items()),'GODOT_WORKING_SELECTION_MISMATCH')
        files[self.contract.SCENE_PATH].update(sha256=facts['scene_sha256'],size_bytes=facts['scene_size_bytes'])
        return {'capture_id':facts['observation_id'],'scratch_name':intent.scratch_name,
            'editor':self._fact_identity(facts),'generation_before':facts['generation_before'],
            'generation_after':facts['generation_after'],'root_instance_id':self._instance(facts['root_before']),
            'effect_started_ms':facts['effect_started_ms'],'effect_completed_ms':facts['effect_completed_ms'],
            'semantic_revision':facts['semantic_revision'],'semantic_sha256':facts['semantic_sha256'],
            'files':files,'scene_sha256':facts['scene_sha256'],'scene_size_bytes':facts['scene_size_bytes']}

    def _adoption_facts(self, facts, bundle, selection):
        files = parse_json(bundle.manifest_bytes)['files']
        _need(all({k:row[k] for k in ('sha256','size_bytes')} == facts['working_files'][path]
                  for path,row in files.items()),'GODOT_ADOPTED_WORKING_FILES_MISMATCH')
        _need(facts['selection'] == selection['selector']['selection']
              and facts['can_undo'] is False and facts['can_redo'] is False,'GODOT_ADOPTION_HISTORY')
        return {'mode':'same_editor','adoption_id':facts['observation_id'],'context_kind':'live_editor',
            'editor':self._fact_identity(facts),'generation_before':facts['generation_before'],
            'generation_after':facts['generation_after'],
            'root_instance_id_before':self._instance(facts['root_before']),
            'root_instance_id_after':self._instance(facts['root_after']),
            'effect_started_ms':facts['effect_started_ms'],'effect_completed_ms':facts['effect_completed_ms'],
            'semantic_revision':facts['semantic_revision'],'semantic_sha256':facts['semantic_sha256'],
            'project_revision':facts['project_revision'],'manifest_sha256':facts['manifest_sha256'],
            'files':files,'selection':facts['selection'],'selector_version':selection['selector_version'],
            'scene_path':'res://scenes/fixture.tscn','history_boundary':facts['history_boundary']}

    @staticmethod
    def _retirement_facts(receipt, facts):
        before, cleanup = facts['before'], facts['cleanup']
        job = cleanup['job']
        return {'observation_id':receipt.observation_id,'observation_sha256':_sha(canonical_bytes(facts)),
            'command_id':facts['command_id'],'request_digest':facts['request_digest'],
            'retirement_intent_id':facts['retirement_intent_id'],'editor':facts['editor'],
            'before_generation':before['generation'],
            'before_root_instance_id':GodotPublicationOwner._instance(before['root_instance_id']),
            'before_revision':before['revision'],'before_snapshot_sha256':_sha(canonical_bytes(before)),
            'effect_started_ms':facts['effect_started_ms'],'effect_completed_ms':facts['effect_completed_ms'],
            'close_completed_ms':facts['close_completed_ms'],'next_generation':facts['next_generation'],
            'actual_exit_code':cleanup['actual_process_exit']['exit_code'],
            'wrapper_exit_code':cleanup['wrapper_exit_code'],'job_active_count':job['active_count'],
            'job_zero_observed':job['zero_observed'],'job_closed':job['closed'],'job_tainted':job['tainted'],
            'handles_retained':job['handle_retained'],'public_ack':facts['public_ack']}

    def _fresh_adoption_facts(self, receipt, facts, bundle, selection):
        files = parse_json(bundle.manifest_bytes)['files']
        _need(facts['new_editor'] == self._editor.identity,'GODOT_EDITOR_IDENTITY_CHANGED')
        _need(set(files) == set(facts['working_files']) and all(
            {k:row[k] for k in ('sha256','size_bytes')} == facts['working_files'][path]
            for path,row in files.items()),'GODOT_ADOPTED_WORKING_FILES_MISMATCH')
        _need(facts['selection'] == selection['selector']['selection'],'GODOT_SELECTED_BUNDLE_MISMATCH')
        keys = ('command_id','request_digest','old_editor','new_editor','generation_before','generation_after',
            'retirement_observation_id','retirement_sha256','semantic_revision','semantic_sha256',
            'project_revision','manifest_sha256','selection','effect_started_ms','observed_ms',
            'history_boundary','public_ack')
        return {**{key:facts[key] for key in keys},'mode':'fresh_editor','observation_id':receipt.observation_id,
            'root_before':self._instance(facts['root_before']),'root_after':self._instance(facts['root_after']),
            'selector_version':selection['selector_version'],'files':files}

    def _remember_response(self, command_id, record):
        raw = self._journal.lookup_response(command_id,record['digest'])
        _need(type(raw) is bytes,'GODOT_DURABLE_RESPONSE_REQUIRED')
        response = Response.from_dict(parse_json(raw))
        _need(canonical_bytes(response.as_dict()) == raw and response.command_id == command_id
              and response.postconditions.get('request_digest') == record['digest']
              and response.status in (Status.COMMITTED,Status.REJECTED,Status.UNKNOWN),
              'GODOT_DURABLE_RESPONSE_MISMATCH')
        self._update_record(record,status=response.status.value,code=response.code,
            postconditions=response.postconditions,durable_response_sha256=_sha(raw))

    def _reply(self, command_id, record):
        # Receipt verification can wait on native storage. Retain the journal
        # owner and snapshot the record without blocking Stop's bookkeeping.
        # The journal's own lock/closed guard serializes concurrent cleanup.
        with self._lock:
            record = dict(record)
            journal = self._journal
        if record.get('durable_response_sha256') or record['status'] == 'COMMITTED':
            try:
                raw = journal.lookup_response(command_id,record['digest'])
                _need(type(raw) is bytes and _sha(raw) == record.get('durable_response_sha256'),
                      'GODOT_DURABLE_RESPONSE_MISMATCH')
                response = Response.from_dict(parse_json(raw))
                _need(canonical_bytes(response.as_dict()) == raw and response.command_id == command_id
                      and response.postconditions.get('request_digest') == record['digest'],
                      'GODOT_DURABLE_RESPONSE_MISMATCH')
                if response.status == Status.COMMITTED:
                    durable = journal.lookup(command_id,record['digest'])
                    _need(durable is not None and durable['phase'] == 'COMMITTED'
                          and durable['receipt_sha256'] == response.postconditions['durable_receipt_sha256'],
                          'GODOT_DURABLE_RECEIPT_MISMATCH')
                return response
            except Exception:
                with self._lock:
                    self._held = True
                self.sessions.halt()
                return Response(Status.UNKNOWN,'GODOT_DURABLE_RECEIPT_UNAVAILABLE',command_id,
                    postconditions={'request_digest':record['digest'],'public_ack':False,
                                    'next_action':'lookup.reconcile'})
        return Response(Status(record['status']),record['code'],command_id,
            postconditions=record.get('postconditions',{'request_digest':record['digest'],'public_ack':False}))

    def _update_record(self, record, **fields):
        with self._lock:
            record.update(fields)

    def lookup(self, body, *, authorization, catalog_digest):
        self._auth(body,'control.lookup',authorization,catalog_digest,{'project_id','command_id'})
        command = body['command_id']; self.sessions.validate_public_identifier(command)
        with self._lock:
            record = self._jobs.get(command)
        if record:
            return self._reply(command,record)
        return Response(Status.UNKNOWN,'GODOT_COMMAND_NOT_FOUND',command)

    def stop(self, body, *, authorization, catalog_digest):
        grant = self._auth(body,'control.stop',authorization,catalog_digest,{'project_id','command_id'})
        self.sessions.validate_public_identifier(body['command_id'])
        # Latch before queuing persistence; never wait for disk on the control
        # listener. The owned drain waits for the current effect's accounting.
        stopped = self.sessions.stop(grant)
        with self._lock:
            _need(not self._closed,'GODOT_OWNER_CLOSED')
            if getattr(self,'_stop_thread',None) is None:
                self._stop_persistence = 'PENDING'
                self._stop_thread = threading.Thread(target=self._persist_stop,
                    name='hh-godot-durable-stop',daemon=True)
                try:
                    self._stop_thread.start()
                except BaseException:
                    self._stop_persistence = 'UNKNOWN'
                    self._held = True
                    raise
            return {**stopped,'stop_persistence':self._stop_persistence}

    def _persist_stop(self):
        acquired = self._work.acquire(timeout=95)
        try:
            _need(acquired,'GODOT_STOP_DRAIN_TIMEOUT')
            self._same_release()
            if not self._journal.snapshot()['stopped']:
                self._journal.stop(reason='owner.stop',observed_ms=epoch_ms())
            _need(self._journal.snapshot()['stopped'] is True,'GODOT_STOP_NOT_DURABLE')
            with self._lock:
                self._stop_persistence = 'DURABLE'
        except BaseException as error:
            with self._lock:
                self._stop_persistence = 'UNKNOWN'
                self._stop_error = error
                self._held = True
        finally:
            if acquired:self._work.release()

    def close(self):
        with self._lock:
            self._closed = True
            stop_thread = getattr(self,'_stop_thread',None)
        self.sessions.halt()
        if stop_thread is not None and stop_thread.ident is not None:
            stop_thread.join(timeout=2)
            if stop_thread.is_alive():
                raise PublicationOwnerError('GODOT_STOP_DRAIN_REQUIRED',cleanup_owner=self)
        if not self._work.acquire(timeout=2):
            raise PublicationOwnerError('GODOT_OWNER_WORK_DRAIN_REQUIRED',cleanup_owner=self)
        try:
            for resources in (self._cleanup_owners,self._retired_editors):
                while resources:
                    try:
                        resources[0].close()
                    except BaseException as exc:
                        self._held = True
                        raise PublicationOwnerError('GODOT_CLOSE_DRAIN_REQUIRED',cleanup_owner=self) from exc
                    resources.pop(0)
            for name in ('_editor','_validator','_journal'):
                resource = getattr(self,name,None)
                if resource is not None:
                    try:
                        resource.close()
                    except BaseException as exc:
                        self._held = True
                        raise PublicationOwnerError('GODOT_CLOSE_DRAIN_REQUIRED',cleanup_owner=self) from exc
                    setattr(self,name,None)
        finally:
            self._work.release()
