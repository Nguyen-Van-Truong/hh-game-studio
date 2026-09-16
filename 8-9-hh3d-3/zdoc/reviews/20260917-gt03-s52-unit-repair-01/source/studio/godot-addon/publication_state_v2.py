"""Pure, bounded Godot publication history; no storage, engine or public ACK.

Every engine/lease/file field is a caller attestation. Native descriptors name
ProtectedFileRoot files, never PrivateBlobStore blobs. This reducer establishes
only internal consistency. A durable owner must independently verify effects,
append/barrier/custody and actual engine readback before issuing any public ACK.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re
from typing import Iterable

from studio.protocol.core import ValidationError, canonical_bytes, parse_json

SCHEMA = 'hh-godot-publication-event-2'
SCENE_PATH = 'scenes/fixture.tscn'
SCRIPT_PATH = 'scripts/fixture_actor.gd'
MAX_EVENT_BYTES = 12 * 1024  # Leave room inside the native 16 KiB event body.
MAX_EVENTS = 256
MAX_COMMANDS = 64
MAX_SNAPSHOT_BYTES = 512 * 1024
_SAFE = 2**53 - 1
PROFILE = 'hh-godot-managed-fixture-1'
BUNDLE_SCHEMA = 'hh-godot-fixture-bundle-2'
FILE_PROFILE = {
    SCENE_PATH: ('managed_scene', 1024 * 1024),
    SCRIPT_PATH: ('managed_script', 16 * 1024),
    SCRIPT_PATH + '.uid': ('managed_uid', 128),
    'project.godot': ('trusted_config', 16 * 1024),
    'addons/hh_studio/plugin.cfg': ('trusted_addon', 4 * 1024),
    'addons/hh_studio/plugin.gd': ('trusted_addon', 128 * 1024),
    'addons/hh_studio/plugin.gd.uid': ('trusted_uid', 128),
    'addons/hh_studio/scene_commands.gd': ('trusted_addon', 128 * 1024),
    'addons/hh_studio/scene_commands.gd.uid': ('trusted_uid', 128),
    'addons/hh_studio/jcs_godot.gd': ('trusted_addon', 128 * 1024),
    'addons/hh_studio/jcs_godot.gd.uid': ('trusted_uid', 128),
}
PATHS = tuple(sorted(FILE_PROFILE))
_PATHS = set(PATHS)
TRUSTED_PATHS = tuple(p for p in PATHS if FILE_PROFILE[p][0].startswith('trusted_'))
MAX_MANIFEST_BYTES = 16 * 1024
MAX_BUNDLE_BYTES = 2 * 1024 * 1024
MAX_HISTORY_BYTES = MAX_EVENTS * MAX_EVENT_BYTES

_HASH = re.compile(r'[0-9a-f]{64}\Z')
_REVISION = re.compile(r'sha256:[0-9a-f]{64}\Z')
_ID = re.compile(r'[a-z][a-z0-9._-]{0,63}\Z')
_PROJECT = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z')
_HEXID = re.compile(r'[0-9a-f]{32}\Z')
_COMMON = {'schema', 'sequence', 'kind', 'project_id', 'observed_ms'}
_COMMAND = {'command_id', 'digest'}
_FIELDS = {
    'CONFIG': {'engine_sha256', 'source_closure_sha256', 'content_root_identity', 'initial'},
    'PREPARED': _COMMAND | {'operation', 'candidate_id', 'before_project_revision',
        'before_scene_revision', 'expected_files', 'parent_selection', 'admission',
        'checkpoint_sha256', 'script_input', 'planned_names'},
    'STAGED': _COMMAND | {'candidate'},
    'VALIDATED': _COMMAND | {'observation'},
    'ACTIVATING': _COMMAND | {'current', 'selection'},
    'READBACK': _COMMAND | {'observation', 'selection'},
    'COMMITTED': _COMMAND | {'readback_event_sha256', 'after_project_revision', 'selection'},
    'FAILED': _COMMAND | {'reason', 'publication_not_started', 'staging_may_exist'},
    'UNKNOWN': _COMMAND | {'reason'},
    'STOP': {'reason'},
}
_NEXT = {'STAGED': 'PREPARED', 'VALIDATED': 'STAGED', 'ACTIVATING': 'VALIDATED',
         'READBACK': 'ACTIVATING', 'COMMITTED': 'READBACK'}
_EARLY = {'PREPARED', 'STAGED', 'VALIDATED'}


class PublicationError(ValidationError):
    def __init__(self, code: str):
        super().__init__(code, 'pure complete-profile Godot publication history v2')


def _need(condition: object, code: str = 'PUBLICATION_INVALID_HISTORY') -> None:
    if not condition:
        raise PublicationError(code)


def _shape(value: object, fields: set[str]) -> None:
    _need(type(value) is dict and set(value) == fields, 'PUBLICATION_INVALID_SHAPE')


def _integer(value: object, lower: int = 0, upper: int = _SAFE) -> None:
    _need(type(value) is int and lower <= value <= upper, 'PUBLICATION_INVALID_INTEGER')


def _matches(value: object, pattern: re.Pattern) -> None:
    _need(type(value) is str and pattern.fullmatch(value) is not None, 'PUBLICATION_INVALID_IDENTIFIER')


def _hash(value: object, *, revision: bool = False) -> None:
    _matches(value, _REVISION if revision else _HASH)


def _digest(value: dict) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _identity(value: object) -> None:
    _shape(value, {'volume', 'file_id'})
    _matches(value['volume'], re.compile(r'0|[1-9][0-9]{0,19}\Z'))
    _need(int(value['volume']) < 2**64, 'PUBLICATION_INVALID_VOLUME')
    _matches(value['file_id'], _HEXID)


def _file(value: object, maximum: int) -> None:
    _shape(value, {'sha256', 'size_bytes'})
    _hash(value['sha256'])
    _integer(value['size_bytes'], 0, maximum)


def _files(value: object) -> None:
    _shape(value, _PATHS)
    for path in PATHS:
        entry = value[path]
        _shape(entry, {'sha256', 'size_bytes', 'role'})
        _file({key: entry[key] for key in ('sha256', 'size_bytes')}, FILE_PROFILE[path][1])
        _need(entry['size_bytes'] > 0 and entry['role'] == FILE_PROFILE[path][0], 'PUBLICATION_FILE_PROFILE')
    _need(sum(row['size_bytes'] for row in value.values()) <= MAX_BUNDLE_BYTES, 'PUBLICATION_BUNDLE_LIMIT')


def _selection(value: object) -> None:
    _shape(value, {'generation', 'identity'})
    _integer(value['generation'])
    _hash(value['identity'], revision=True)


def bundle_manifest(files: dict, scene_revision: str, engine_sha256: str) -> dict:
    """Reconstruct canonical codec-v2 metadata; no content or engine inspection."""
    _files(files)
    _hash(scene_revision, revision=True)
    _hash(engine_sha256)
    trusted = {'profile': PROFILE, 'files': {path: files[path] for path in TRUSTED_PATHS}}
    body = {'schema': BUNDLE_SCHEMA, 'profile': PROFILE, 'files': files,
            'trusted_source_revision': 'sha256:' + _digest(trusted),
            'caller_observations': {'scene_revision': scene_revision, 'engine_sha256': engine_sha256}}
    return {**body, 'project_revision': 'sha256:' + _digest(body)}


def project_revision(files: dict, scene_revision: str, engine_sha256: str) -> str:
    return bundle_manifest(files, scene_revision, engine_sha256)['project_revision']


def _content(candidate: dict) -> dict:
    manifest = candidate['bundle_manifest']
    return {'candidate_id': candidate['candidate_id'],
            'project_revision': manifest['project_revision'],
            **manifest['caller_observations'], 'files': manifest['files'],
            'manifest': candidate['descriptor']['manifest']}


def selection_identity(project_id: str, command_id: str, digest: str,
                       parent: dict, candidate: dict) -> str:
    """Derive an intent identity, never a native selection receipt."""
    _matches(project_id, _PROJECT); _matches(command_id, _ID)
    _hash(digest, revision=True); _selection(parent)
    _shape(candidate, {'candidate_id', 'descriptor', 'bundle_manifest', 'scene_observation'})
    _matches(candidate['candidate_id'], re.compile(r'candidate-[0-9a-f]{32}\Z'))
    _integer(parent['generation'], 0, _SAFE - 1)
    # Bind the complete declared descriptor, including every native identity.
    return 'sha256:' + _digest({'schema': 'hh-godot-selection-intent-2', 'project_id': project_id,
        'command_id': command_id, 'digest': digest, 'parent': parent,
        'generation': parent['generation'] + 1, 'candidate_id': candidate['candidate_id'],
        'descriptor_sha256': _digest(candidate['descriptor']),
        'bundle_manifest_sha256': _digest(candidate['bundle_manifest'])})


def _native_file(value: object, maximum: int, root: dict) -> None:
    _shape(value, {'name', 'volume', 'file_id', 'size_bytes', 'sha256'})
    _matches(value['name'], re.compile(r'obj-[0-9a-f]{32}\Z'))
    _identity({'volume': value['volume'], 'file_id': value['file_id']})
    _need(value['volume'] == root['volume'] and value['file_id'] != root['file_id'],
          'PUBLICATION_CONTENT_ROOT_MISMATCH')
    _file({'sha256': value['sha256'], 'size_bytes': value['size_bytes']}, maximum)
    _need(value['size_bytes'] > 0, 'PUBLICATION_EMPTY_FILE')


def _metadata(candidate: dict) -> dict:
    return candidate['bundle_manifest']['files']


def _fresh_observation(value: dict, state: dict, prepared: dict, candidate: dict) -> None:
    _shape(value, {'observation_id', 'editor_session_id', 'editor_generation', 'observed_ms',
                  'project_revision', 'scene_revision', 'engine_sha256', 'source_closure_sha256'})
    _matches(value['observation_id'], _ID); _matches(value['editor_session_id'], _ID)
    _integer(value['editor_generation'], 1, 2147483647); _integer(value['observed_ms'])
    admission = prepared['admission']; content = _content(candidate)
    _need(value['editor_session_id'] != admission['editor_session_id']
          and admission['admitted_ms'] <= value['observed_ms'] <= state['last_observed_ms']
          and value['observed_ms'] < min(admission['deadline_ms'], admission['lease_expires_ms']),
          'PUBLICATION_FRESH_SCENE_OBSERVATION_REQUIRED')
    _need(value['source_closure_sha256'] == state['source_closure_sha256']
          and all(value[key] == content[key] for key in ('project_revision', 'scene_revision', 'engine_sha256')),
          'PUBLICATION_OBSERVATION_MISMATCH')
    _need(value['observation_id'] not in state['observation_ids'], 'PUBLICATION_OBSERVATION_REUSED')
    state['observation_ids'].append(value['observation_id'])


def _candidate(value: object, state: dict, prepared: dict) -> None:
    _shape(value, {'candidate_id', 'descriptor', 'bundle_manifest', 'scene_observation'})
    _need(value['candidate_id'] == prepared['candidate_id'], 'PUBLICATION_CANDIDATE_MISMATCH')
    manifest = value['bundle_manifest']
    _shape(manifest, {'schema', 'profile', 'files', 'trusted_source_revision', 'caller_observations', 'project_revision'})
    _shape(manifest['caller_observations'], {'scene_revision', 'engine_sha256'})
    scene = manifest['caller_observations']['scene_revision']
    _need(manifest['caller_observations']['engine_sha256'] == state['engine_sha256'], 'PUBLICATION_ENGINE_MISMATCH')
    _need(manifest == bundle_manifest(manifest['files'], scene, state['engine_sha256']), 'PUBLICATION_PROJECT_REVISION_MISMATCH')
    raw_manifest = canonical_bytes(manifest)
    _need(len(raw_manifest) <= MAX_MANIFEST_BYTES
          and len(raw_manifest) + sum(row['size_bytes'] for row in manifest['files'].values()) <= MAX_BUNDLE_BYTES,
          'PUBLICATION_BUNDLE_LIMIT')
    descriptor = value['descriptor']
    _shape(descriptor, {'root_identity', 'project_revision', 'files', 'manifest'})
    _identity(descriptor['root_identity'])
    _need(descriptor['root_identity'] == state['content_root_identity'], 'PUBLICATION_CONTENT_ROOT_MISMATCH')
    _need(descriptor['project_revision'] == manifest['project_revision'], 'PUBLICATION_PROJECT_REVISION_MISMATCH')
    _shape(descriptor['files'], _PATHS)
    native = {**descriptor['files'], '@manifest': descriptor['manifest']}
    for path, item in native.items():
        _native_file(item, MAX_MANIFEST_BYTES if path == '@manifest' else FILE_PROFILE[path][1], state['content_root_identity'])
        _need(item['name'] == prepared['planned_names'][path], 'PUBLICATION_PLANNED_NAME_MISMATCH')
        metadata = {'sha256': hashlib.sha256(raw_manifest).hexdigest(), 'size_bytes': len(raw_manifest)} if path == '@manifest' else manifest['files'][path]
        _need(all(item[key] == metadata[key] for key in ('sha256', 'size_bytes')), 'PUBLICATION_DESCRIPTOR_MISMATCH')
    _need(len({item['file_id'] for item in native.values()}) == 12, 'PUBLICATION_FILE_ALIAS')
    metadata = manifest['files']; before = prepared['expected_files']
    changed = SCRIPT_PATH if prepared['operation'] == 'script_text.replace' else SCENE_PATH
    _need(all(metadata[path] == before[path] for path in PATHS if path != changed), 'PUBLICATION_UNRELATED_FILE_CHANGED')
    if changed == SCRIPT_PATH:
        _need({key: metadata[SCRIPT_PATH][key] for key in ('sha256', 'size_bytes')} == prepared['script_input'], 'PUBLICATION_SCRIPT_MISMATCH')
        _fresh_observation(value['scene_observation'], state, prepared, value)
    else:
        _need(value['scene_observation'] is None, 'PUBLICATION_UNEXPECTED_SCENE_OBSERVATION')
        _need(scene == prepared['before_scene_revision'], 'PUBLICATION_SCENE_REVISION_MISMATCH')


def _observation(value: object, state: dict, command: dict) -> None:
    _shape(value, {'observation_id', 'editor_session_id', 'editor_generation', 'observed_ms', 'candidate_id',
        'project_revision', 'scene_revision', 'engine_sha256', 'source_closure_sha256',
        'manifest_sha256', 'files', 'parse_status', 'import_status', 'exit_code', 'tree_drained', 'logs_clean'})
    for key in ('observation_id', 'editor_session_id'):
        _matches(value[key], _ID)
    _integer(value['editor_generation'], 1, 2147483647)
    _integer(value['observed_ms'])
    _need(command['prepared']['observed_ms'] <= value['observed_ms'] <= state['last_observed_ms'], 'PUBLICATION_OBSERVATION_TIME')
    scene_observation = command['candidate']['scene_observation']
    same_candidate_observation = (command['phase'] == 'STAGED' and scene_observation is not None
                                  and value['observation_id'] == scene_observation['observation_id'])
    if same_candidate_observation:
        _need(all(value[key] == item for key, item in scene_observation.items()),
              'PUBLICATION_OBSERVATION_MISMATCH')
    else:
        _need(value['observation_id'] not in state['observation_ids'], 'PUBLICATION_OBSERVATION_REUSED')
    if command['phase'] == 'STAGED':
        admission = command['prepared']['admission']
        _need(value['observed_ms'] < min(admission['deadline_ms'], admission['lease_expires_ms']),
              'PUBLICATION_DEADLINE_EXPIRED')
    else:
        _need(value['observed_ms'] >= command['activating_observed_ms'],
              'PUBLICATION_READBACK_BEFORE_ACTIVATION')
    _files(value['files'])
    candidate = _content(command['candidate'])
    for key in ('candidate_id', 'project_revision', 'scene_revision', 'engine_sha256'):
        _need(value[key] == candidate[key], 'PUBLICATION_OBSERVATION_MISMATCH')
    _need(value['source_closure_sha256'] == state['source_closure_sha256']
          and value['manifest_sha256'] == candidate['manifest']['sha256']
          and value['files'] == candidate['files'], 'PUBLICATION_OBSERVATION_MISMATCH')
    _need(value['parse_status'] == 'PASS' and value['import_status'] == 'PASS'
          and type(value['exit_code']) is int and value['exit_code'] == 0
          and value['tree_drained'] is True and value['logs_clean'] is True,
          'PUBLICATION_VERIFICATION_NOT_PASS')
    if not same_candidate_observation:
        state['observation_ids'].append(value['observation_id'])


def _event_bytes(event: dict | bytes) -> bytes:
    _need(type(event) in (dict, bytes), 'PUBLICATION_EVENT_REQUIRED')
    if type(event) is bytes:
        _need(len(event) <= MAX_EVENT_BYTES, 'PUBLICATION_EVENT_LIMIT')
        value = parse_json(event)
        raw = canonical_bytes(value)
        _need(raw == event, 'PUBLICATION_NONCANONICAL_EVENT')
    else:
        raw = canonical_bytes(event)
    _need(len(raw) <= MAX_EVENT_BYTES, 'PUBLICATION_EVENT_LIMIT')
    return raw


def _finish(state: dict, command: dict, status: str, reason: str) -> None:
    prepared = command['prepared']
    declared = command.get('candidate')
    candidate = _content(declared) if declared is not None else None
    committed = status == 'COMMITTED'
    receipt = {'schema': 'hh-godot-publication-observation-2', 'status': status, 'reason': reason,
        'command_id': command['command_id'], 'digest': command['digest'], 'operation': prepared['operation'],
        'candidate_id': prepared['candidate_id'],
        'before_project_revision': prepared['before_project_revision'],
        'after_project_revision': candidate['project_revision'] if committed else state['last_good']['project_revision'],
        'before_scene_revision': prepared['before_scene_revision'],
        'scene_revision': candidate['scene_revision'] if committed else state['last_good']['scene_revision'],
        'engine_sha256': state['engine_sha256'], 'source_closure_sha256': state['source_closure_sha256'],
        'selection': command['selection'] if committed else state['last_good']['selection'],
        'files': candidate['files'] if committed else state['last_good']['files'],
        'admission': prepared['admission'], 'checkpoint_sha256': prepared['checkpoint_sha256'],
        'validation_event_sha256': command.get('validation_event_sha256'),
        'readback_event_sha256': command.get('readback_event_sha256'),
        'content_root_identity': state['content_root_identity'],
        'candidate_descriptor_sha256': _digest(declared['descriptor']) if declared is not None else None,
        'staging_may_exist': command.get('staging_may_exist', True),
        'durable_owner_required': True, 'engine_effects_verified': False, 'public_ack': False}
    if committed:
        state['last_good'] = {'project_revision': candidate['project_revision'], 'scene_revision': candidate['scene_revision'],
                             'files': candidate['files'], 'selection': command['selection']}
    command.clear()
    command.update(command_id=receipt['command_id'], digest=receipt['digest'], phase=status,
                   receipt=receipt, receipt_sha256=_digest(receipt))
    state['pending_command_id'] = None


def _hold(state: dict, command: dict, reason: str) -> None:
    if command['phase'] != 'UNKNOWN':
        command['uncertain_phase'] = command['phase']
        command['phase'] = 'UNKNOWN'
        command['reason'] = reason
    state['held'] = True


def _step(state: dict | None, event: dict, raw: bytes) -> dict:
    _need(type(event) is dict and type(event.get('kind')) is str and event['kind'] in _FIELDS,
          'PUBLICATION_EVENT_KIND')
    kind = event['kind']
    _shape(event, _COMMON | _FIELDS[kind])
    _need(event['schema'] == SCHEMA, 'PUBLICATION_SCHEMA_MISMATCH')
    _matches(event['project_id'], _PROJECT)
    _integer(event['sequence'], 1, MAX_EVENTS)
    _integer(event['observed_ms'])
    if state is None:
        _need(kind == 'CONFIG' and event['sequence'] == 1, 'PUBLICATION_CONFIG_REQUIRED')
        _hash(event['engine_sha256'])
        _hash(event['source_closure_sha256'])
        _identity(event['content_root_identity'])
        initial = event['initial']
        _shape(initial, {'project_revision', 'scene_revision', 'files', 'selection'})
        _selection(initial['selection'])
        _need(initial['project_revision'] == project_revision(initial['files'], initial['scene_revision'], event['engine_sha256']),
              'PUBLICATION_PROJECT_REVISION_MISMATCH')
        return {'project_id': event['project_id'], 'engine_sha256': event['engine_sha256'],
            'source_closure_sha256': event['source_closure_sha256'], 'content_root_identity': event['content_root_identity'],
            'event_count': 1, 'last_observed_ms': event['observed_ms'], 'last_good': initial,
            'pending_command_id': None, 'stopped': False, 'held': False,
            'highest_fencing_epoch': 0, 'lease_id': None, 'lease_expires_ms': None,
            'commands': [], 'used_names': [], 'observation_ids': []}
    _need(kind != 'CONFIG', 'PUBLICATION_CONFIG_ALREADY_SET')
    _need(event['project_id'] == state['project_id'], 'PUBLICATION_PROJECT_MISMATCH')
    _need(event['sequence'] == state['event_count'] + 1, 'PUBLICATION_EVENT_SEQUENCE')
    _need(event['observed_ms'] >= state['last_observed_ms'], 'PUBLICATION_CLOCK_REGRESSION')
    state['event_count'], state['last_observed_ms'] = event['sequence'], event['observed_ms']
    if kind == 'STOP':
        _need(not state['stopped'], 'PUBLICATION_ALREADY_STOPPED')
        _need(event['reason'] in ('USER_STOP', 'DEADLINE', 'OWNER_SHUTDOWN'), 'PUBLICATION_INVALID_REASON')
        state['stopped'] = True
        pending = next((c for c in state['commands'] if c['command_id'] == state['pending_command_id']), None)
        if pending is not None:
            if pending['phase'] in _EARLY:
                _finish(state, pending, 'FAILED', 'STOPPED_BEFORE_ACTIVATION')
            else:
                _hold(state, pending, 'STOPPED_AFTER_POSSIBLE_EFFECT')
        return state
    _matches(event['command_id'], _ID)
    _hash(event['digest'], revision=True)
    existing = next((c for c in state['commands'] if c['command_id'] == event['command_id']), None)
    if existing is not None:
        _need(existing['digest'] == event['digest'], 'PUBLICATION_COMMAND_CONFLICT')
    if kind == 'PREPARED':
        _need(existing is None, 'PUBLICATION_DUPLICATE_EVENT')
        _need(not state['stopped'], 'PUBLICATION_STOPPED')
        _need(not state['held'] and state['pending_command_id'] is None, 'PUBLICATION_PENDING_OR_HELD')
        _need(len(state['commands']) < MAX_COMMANDS, 'PUBLICATION_COMMAND_LIMIT')
        # Reserve STAGED/VALIDATED/ACTIVATING/READBACK/COMMITTED plus one STOP.
        _need(event['sequence'] + 6 <= MAX_EVENTS, 'PUBLICATION_EVENT_CAPACITY')
        _need(event['operation'] in ('scene.save', 'script_text.replace'), 'PUBLICATION_OPERATION')
        _matches(event['candidate_id'], re.compile(r'candidate-[0-9a-f]{32}\Z'))
        _need(all(c['receipt']['candidate_id'] != event['candidate_id'] for c in state['commands']),
              'PUBLICATION_CANDIDATE_REUSED')
        names = event['planned_names']
        _shape(names, _PATHS | {'@manifest'})
        for name in names.values():
            _matches(name, re.compile(r'obj-[0-9a-f]{32}\Z'))
        used_names = {name for batch in state['used_names'] for name in batch}
        _need(len(set(names.values())) == 12 and not set(names.values()).intersection(used_names),
              'PUBLICATION_PLANNED_NAME_REUSED')
        _hash(event['before_scene_revision'], revision=True)
        _hash(event['checkpoint_sha256'])
        _files(event['expected_files'])
        _selection(event['parent_selection'])
        _need(event['before_project_revision'] == state['last_good']['project_revision']
              and event['expected_files'] == state['last_good']['files']
              and event['parent_selection'] == state['last_good']['selection'], 'PUBLICATION_STALE_BASE')
        admission = event['admission']
        _shape(admission, {'lease_id', 'fencing_epoch', 'admitted_ms', 'deadline_ms', 'lease_expires_ms',
                           'editor_session_id', 'editor_generation'})
        for key in ('lease_id', 'editor_session_id'):
            _matches(admission[key], _ID)
        for key in ('admitted_ms', 'deadline_ms', 'lease_expires_ms'):
            _integer(admission[key])
        _integer(admission['fencing_epoch'], 1)
        _integer(admission['editor_generation'], 1, 2147483647)
        _need(admission['admitted_ms'] == event['observed_ms']
              and admission['admitted_ms'] < admission['deadline_ms'] <= min(admission['lease_expires_ms'], admission['admitted_ms'] + 30000),
              'PUBLICATION_INVALID_ADMISSION')
        fence = admission['fencing_epoch']
        _need(fence >= state['highest_fencing_epoch'] and (fence != state['highest_fencing_epoch']
              or (admission['lease_id'] == state['lease_id']
                  and admission['lease_expires_ms'] == state['lease_expires_ms'])), 'PUBLICATION_STALE_FENCE')
        if event['operation'] == 'script_text.replace':
            _file(event['script_input'], 16 * 1024)
            _need(event['script_input']['size_bytes'] > 0, 'PUBLICATION_EMPTY_FILE')
        else:
            _need(event['script_input'] is None, 'PUBLICATION_UNEXPECTED_SCRIPT_INPUT')
        state['highest_fencing_epoch'], state['lease_id'] = fence, admission['lease_id']
        state['lease_expires_ms'] = admission['lease_expires_ms']
        # Keep each admitted 12-name group separate: the shared canonical JSON
        # protocol bounds every array to 256 items, even for internal snapshots.
        state['used_names'].append(list(names.values()))
        state['commands'].append({'command_id': event['command_id'], 'digest': event['digest'],
                                  'phase': kind, 'prepared': event})
        state['pending_command_id'] = event['command_id']
        return state
    _need(existing is not None and state['pending_command_id'] == event['command_id'], 'PUBLICATION_COMMAND_NOT_PENDING')
    command = existing
    _need(not state['held'] and command['phase'] != 'UNKNOWN', 'PUBLICATION_RECOVERY_REQUIRED')
    _need(not state['stopped'], 'PUBLICATION_STOPPED')
    phase = command['phase']
    if kind == 'UNKNOWN':
        reasons = {'PREPARED': ('STAGING_UNCERTAIN',), 'STAGED': ('VALIDATION_UNCERTAIN',),
                   'VALIDATED': ('ACTIVATION_UNCERTAIN',), 'ACTIVATING': ('ACTIVATION_UNCERTAIN', 'READBACK_UNCERTAIN'),
                   'READBACK': ('READBACK_UNCERTAIN', 'TERMINAL_UNCERTAIN')}
        _need(event['reason'] in reasons.get(phase, ()), 'PUBLICATION_INVALID_REASON')
        _hold(state, command, event['reason'])
    elif kind == 'FAILED':
        _need(phase in _EARLY and event['publication_not_started'] is True, 'PUBLICATION_EFFECT_MAY_HAVE_STARTED')
        _need(event['reason'] in ('VALIDATION_FAILED', 'CANCELED', 'PRECONDITION_FAILED', 'STAGING_FAILED'),
              'PUBLICATION_INVALID_REASON')
        _need(type(event['staging_may_exist']) is bool and (phase == 'PREPARED' or event['staging_may_exist']),
              'PUBLICATION_STAGING_OBSERVATION')
        command['staging_may_exist'] = event['staging_may_exist']
        _finish(state, command, 'FAILED', event['reason'])
    else:
        _need(phase == _NEXT[kind], 'PUBLICATION_PHASE_ORDER')
        prepared = command['prepared']
        if kind == 'STAGED':
            _candidate(event['candidate'], state, prepared)
            command['candidate'] = event['candidate']
        elif kind in ('VALIDATED', 'READBACK'):
            _observation(event['observation'], state, command)
            if kind == 'VALIDATED':
                command['validation'] = event['observation']
                command['validation_event_sha256'] = hashlib.sha256(raw).hexdigest()
            else:
                _selection(event['selection'])
                _need(event['selection'] == command['selection'], 'PUBLICATION_SELECTION_MISMATCH')
                _need(event['observation']['observation_id'] != command['validation']['observation_id']
                      and event['observation']['editor_session_id'] != command['validation']['editor_session_id'],
                      'PUBLICATION_FRESH_READBACK_REQUIRED')
                command['readback_event_sha256'] = hashlib.sha256(raw).hexdigest()
        elif kind == 'ACTIVATING':
            current = event['current']
            _shape(current, {'project_revision', 'scene_revision', 'files', 'selection', 'lease_id',
                             'fencing_epoch', 'editor_session_id', 'editor_generation'})
            _files(current['files'])
            _selection(current['selection'])
            _integer(current['fencing_epoch'], 1)
            _integer(current['editor_generation'], 1, 2147483647)
            admission = prepared['admission']
            _need(current['project_revision'] == prepared['before_project_revision']
                  and current['scene_revision'] == prepared['before_scene_revision']
                  and current['files'] == prepared['expected_files']
                  and current['selection'] == prepared['parent_selection'], 'PUBLICATION_STALE_BASE')
            _need(all(current[k] == admission[k] for k in ('lease_id', 'fencing_epoch', 'editor_session_id', 'editor_generation')),
                  'PUBLICATION_STALE_AUTHORITY')
            _need(event['observed_ms'] < min(admission['deadline_ms'], admission['lease_expires_ms']),
                  'PUBLICATION_DEADLINE_EXPIRED')
            expected = {'generation': prepared['parent_selection']['generation'] + 1,
                        'identity': selection_identity(state['project_id'], command['command_id'], command['digest'],
                                                       prepared['parent_selection'], command['candidate'])}
            _selection(event['selection'])
            _need(event['selection'] == expected, 'PUBLICATION_SELECTION_MISMATCH')
            command['selection'] = event['selection']
            command['activating_observed_ms'] = event['observed_ms']
        else:
            _selection(event['selection'])
            _need(event['readback_event_sha256'] == command['readback_event_sha256']
                  and event['after_project_revision'] == _content(command['candidate'])['project_revision']
                  and event['selection'] == command['selection'], 'PUBLICATION_COMMIT_MISMATCH')
            _finish(state, command, 'COMMITTED', 'CALLER_ATTESTATIONS_CONSISTENT')
            return state
        command['phase'] = kind
    return state


@dataclass(frozen=True, slots=True)
class PublicationState:
    """Immutable validated history. Construction replays; no trusted snapshot import."""
    events: tuple[bytes, ...]
    _snapshot: bytes = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _need(type(self.events) is tuple and 1 <= len(self.events) <= MAX_EVENTS, 'PUBLICATION_HISTORY_LIMIT')
        _need(sum(len(raw) for raw in self.events if type(raw) is bytes) <= MAX_HISTORY_BYTES, 'PUBLICATION_HISTORY_LIMIT')
        state = None
        for raw in self.events:
            _need(type(raw) is bytes, 'PUBLICATION_CANONICAL_HISTORY_REQUIRED')
            checked = _event_bytes(raw)
            state = _step(state, parse_json(checked), checked)
        snapshot = canonical_bytes(state)
        _need(len(snapshot) <= MAX_SNAPSHOT_BYTES, 'PUBLICATION_SNAPSHOT_LIMIT')
        object.__setattr__(self, '_snapshot', snapshot)

    @property
    def event_count(self) -> int:
        return len(self.events)

    def snapshot(self) -> dict:
        """Detached consistency projection; not live file/engine observations."""
        return parse_json(self._snapshot)


def reduce_event(state: PublicationState | None, event: dict | bytes) -> PublicationState:
    _need(state is None or type(state) is PublicationState, 'PUBLICATION_STATE_REQUIRED')
    history = () if state is None else state.events
    _need(len(history) < MAX_EVENTS, 'PUBLICATION_HISTORY_LIMIT')
    return PublicationState((*history, _event_bytes(event)))


def replay(events: Iterable[dict | bytes]) -> PublicationState:
    """Bound input consumption; replay never resumes an effect or clears Stop."""
    history = []
    for event in events:
        _need(len(history) < MAX_EVENTS, 'PUBLICATION_HISTORY_LIMIT')
        history.append(_event_bytes(event))
    return PublicationState(tuple(history))


def lookup(state: PublicationState, command_id: str, digest: str | None = None) -> dict | None:
    """Read-only duplicate lookup. Never append a retry PREPARED event."""
    _need(type(state) is PublicationState, 'PUBLICATION_STATE_REQUIRED')
    _matches(command_id, _ID)
    if digest is not None:
        _hash(digest, revision=True)
    snapshot = state.snapshot()
    command = next((c for c in snapshot['commands'] if c['command_id'] == command_id), None)
    if command is None:
        return None
    _need(digest is None or command['digest'] == digest, 'PUBLICATION_COMMAND_CONFLICT')
    result = {'command_id': command_id, 'digest': command['digest'], 'phase': command['phase'],
              'execution_permitted': False, 'durable_owner_required': True,
              'engine_effects_verified': False, 'public_ack': False,
              'receipt': command.get('receipt'), 'receipt_sha256': command.get('receipt_sha256')}
    if command['phase'] == 'UNKNOWN':
        result.update(held=True, uncertain_phase=command['uncertain_phase'], reason=command['reason'])
    return result
