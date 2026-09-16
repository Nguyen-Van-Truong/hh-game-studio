"""Bounded scene.save history: isolated validation != live editor adoption.

Pure facts only. Replay executes nothing, owns no lease, and never issues a
public committed response. The native journal and authenticated owner verify
the evidence represented by these digest/identity records.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import importlib.util
from pathlib import Path
import re
import sys

from studio.protocol.core import ValidationError, canonical_bytes, parse_json

_path = Path(__file__).with_name('publication_state_v2.py').resolve()
_raw = _path.read_bytes()
_key = '_hh_publication_v3_values_' + hashlib.sha256(str(_path).encode() + b'\0' + _raw).hexdigest()
if _key not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_key, _path)
    _module = importlib.util.module_from_spec(_spec); sys.modules[_key] = _module
    try:
        exec(compile(_raw, str(_path), 'exec'), _module.__dict__)
    except BaseException:
        del sys.modules[_key]
        raise
values = sys.modules[_key]

SCHEMA = 'hh-godot-publication-event-3'
MAX_EVENT_BYTES = 12 * 1024
MAX_EVENTS = 256
MAX_COMMANDS = 64
MAX_SNAPSHOT_BYTES = 512 * 1024
PATHS, SCENE_PATH = values.PATHS, values.SCENE_PATH
FILE_PROFILE = values.FILE_PROFILE
_SAFE = 2**53 - 1
_COMMON = {'schema', 'kind', 'sequence', 'project_id', 'observed_ms'}
_CMD = {'command_id', 'digest'}
_FIELDS = {
    'CONFIG': {'validator_engine_sha256', 'editor_engine_sha256', 'source_closure_sha256',
               'validation_source_release_sha256', 'content_root_identity', 'initial'},
    'CAPTURE_PREPARED': _CMD | {'candidate_id', 'operation', 'before_project_revision', 'before_scene_revision',
        'expected_files', 'parent_selection', 'checkpoint_descriptor', 'previous_selector_version',
        'previous_selector_sha256', 'editor', 'editor_generation', 'root_instance_id', 'admission', 'scratch_name'},
    'CAPTURED': _CMD | {'capture'},
    'PREPARED': _CMD | {'planned_names', 'bundle_manifest'},
    'STAGED': _CMD | {'descriptor'},
    'VALIDATED': _CMD | {'validation'},
    'ACTIVATING': _CMD | {'current', 'selector', 'expected_selector_version'},
    'SELECTED': _CMD | {'activation_event_sha256', 'selector_sha256', 'selector_version'},
    'READBACK': _CMD | {'adoption'},
    'COMMITTED': _CMD | {'readback_event_sha256'},
    'FAILED': _CMD | {'reason'}, 'UNKNOWN': _CMD | {'reason'}, 'STOP': {'reason'},
}
_NEXT = {'CAPTURED': 'CAPTURE_PREPARED', 'PREPARED': 'CAPTURED', 'STAGED': 'PREPARED',
         'VALIDATED': 'STAGED', 'ACTIVATING': 'VALIDATED', 'SELECTED': 'ACTIVATING',
         'READBACK': 'SELECTED', 'COMMITTED': 'READBACK'}
_EARLY = {'CAPTURE_PREPARED', 'CAPTURED', 'PREPARED', 'STAGED', 'VALIDATED'}
_EDITOR_FIELDS = {'session_id', 'pid', 'creation_filetime', 'root_identity', 'engine_sha256', 'installed_source_sha256'}
_ADMISSION_FIELDS = {'session_id', 'catalog_digest', 'lease_id', 'fencing_epoch', 'admitted_ms', 'deadline_ms', 'lease_expires_ms'}


class PublicationError(ValidationError):
    def __init__(self, code):
        super().__init__(code, 'pure scene.save publication history v3')


def need(value, code='PUBLICATION_V3_INVALID'):
    if not value:
        raise PublicationError(code)


def shape(value, keys):
    need(type(value) is dict and set(value) == set(keys), 'PUBLICATION_V3_SHAPE')


def same(left, right):
    """JSON equality preserving booleans and integer types before JCS encoding."""
    if type(left) is not type(right): return False
    if type(left) is dict:
        return set(left) == set(right) and all(same(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    return left == right


def integer(value, low=0, high=_SAFE):
    need(type(value) is int and low <= value <= high, 'PUBLICATION_V3_INTEGER')


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def hash_value(value, revision=False):
    values._hash(value, revision=revision)


def identifier(value):
    values._matches(value, values._ID)


def selector_version(value, root):
    shape(value, {'volume', 'file_id', 'size_bytes', 'sha256'})
    values._identity({k: value[k] for k in ('volume', 'file_id')})
    integer(value['size_bytes'], 1, 16384); hash_value(value['sha256'])
    need(value['volume'] == root['volume'] and value['file_id'] != root['file_id'], 'PUBLICATION_V3_SELECTOR_ROOT')


def editor_identity(value, engine):
    shape(value, _EDITOR_FIELDS)
    identifier(value['session_id']); integer(value['pid'], 1, 2147483647)
    need(type(value['creation_filetime']) is str and re.fullmatch(r'[1-9][0-9]{0,19}', value['creation_filetime'])
         and int(value['creation_filetime']) < 2**64, 'PUBLICATION_V3_EDITOR_CREATION')
    values._identity(value['root_identity'])
    hash_value(value['installed_source_sha256'])
    need(value['engine_sha256'] == engine, 'PUBLICATION_V3_EDITOR_ENGINE')


def manifest(value, state):
    shape(value, {'schema', 'profile', 'files', 'trusted_source_revision', 'caller_observations', 'project_revision'})
    shape(value['caller_observations'], {'scene_revision', 'engine_sha256'})
    need(same(value, values.bundle_manifest(value['files'], value['caller_observations']['scene_revision'],
                                        state['validator_engine_sha256'])), 'PUBLICATION_V3_MANIFEST')
    need(len(canonical_bytes(value)) <= 16384 and len(canonical_bytes(value))
         + sum(row['size_bytes'] for row in value['files'].values()) <= values.MAX_BUNDLE_BYTES,
         'PUBLICATION_V3_BUNDLE_LIMIT')


def descriptor(value, bundle_manifest, state, planned=None):
    shape(value, {'root_identity', 'project_revision', 'files', 'manifest'})
    need(same(value['root_identity'], state['content_root_identity']), 'PUBLICATION_V3_CONTENT_ROOT')
    need(value['project_revision'] == bundle_manifest['project_revision'], 'PUBLICATION_V3_PROJECT_REVISION')
    shape(value['files'], PATHS)
    rows = {**value['files'], '@manifest': value['manifest']}
    raw = canonical_bytes(bundle_manifest)
    for path, row in rows.items():
        values._native_file(row, 16384 if path == '@manifest' else FILE_PROFILE[path][1], state['content_root_identity'])
        metadata = {'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw)} if path == '@manifest' else bundle_manifest['files'][path]
        need(all(row[key] == metadata[key] for key in ('sha256', 'size_bytes')), 'PUBLICATION_V3_DESCRIPTOR_BYTES')
        if planned is not None:
            need(row['name'] == planned[path], 'PUBLICATION_V3_PLANNED_NAME')
    need(len({r['name'] for r in rows.values()}) == len({r['file_id'] for r in rows.values()}) == 12,
         'PUBLICATION_V3_NATIVE_ALIAS')


def selector(value, desc, selection, parent, command_id):
    shape(value, {'schema', 'command_id', 'parent_selection', 'selection', 'descriptor_sha256', 'descriptor'})
    values._selection(selection)
    need(same(value, {'schema': 'hh-godot-active-selection-1', 'command_id': command_id,
        'parent_selection': parent, 'selection': selection, 'descriptor_sha256': digest(desc), 'descriptor': desc}),
        'PUBLICATION_V3_SELECTOR')
    need(len(canonical_bytes(value)) <= 16384, 'PUBLICATION_V3_SELECTOR_LIMIT')


def selection_identity(project_id, command_id, command_digest, parent, desc, bundle_manifest):
    return 'sha256:' + digest({'schema': 'hh-godot-selection-intent-3', 'project_id': project_id,
        'command_id': command_id, 'digest': command_digest, 'parent': parent,
        'descriptor_sha256': digest(desc), 'bundle_manifest_sha256': digest(bundle_manifest)})


def activation_current(prepared):
    return {'admission': prepared['admission'], 'editor': prepared['editor'],
        'editor_generation': prepared['editor_generation'], 'root_instance_id': prepared['root_instance_id'],
        'scene_revision': prepared['before_scene_revision'], 'project_revision': prepared['before_project_revision'],
        'files': prepared['expected_files'], 'selection': prepared['parent_selection']}


def _deadline(command, now):
    admission = command['capture_prepared']['admission']
    need(now < min(admission['deadline_ms'], admission['lease_expires_ms']), 'PUBLICATION_V3_DEADLINE')


def _fresh(state, name):
    identifier(name)
    need(name not in state['observation_ids'], 'PUBLICATION_V3_OBSERVATION_REUSED')
    state['observation_ids'].append(name)


def _capture(value, state, command):
    shape(value, {'capture_id', 'scratch_name', 'editor', 'generation_before', 'generation_after',
        'root_instance_id', 'effect_started_ms', 'effect_completed_ms', 'semantic_revision', 'semantic_sha256',
        'files', 'scene_sha256', 'scene_size_bytes'})
    p = command['capture_prepared']; _fresh(state, value['capture_id'])
    need(same(value['editor'], p['editor']) and value['scratch_name'] == p['scratch_name']
         and value['generation_before'] == value['generation_after'] == p['editor_generation']
         and value['root_instance_id'] == p['root_instance_id'], 'PUBLICATION_V3_CAPTURE_IDENTITY')
    for key in ('generation_before', 'generation_after', 'root_instance_id', 'effect_started_ms', 'effect_completed_ms'):
        integer(value[key], 1 if key in ('generation_before', 'generation_after', 'root_instance_id') else 0)
    need(p['observed_ms'] <= value['effect_started_ms'] <= value['effect_completed_ms'] <= state['last_observed_ms'],
         'PUBLICATION_V3_CAPTURE_TIME')
    _deadline(command, value['effect_started_ms'])
    hash_value(value['semantic_sha256']); hash_value(value['semantic_revision'], revision=True)
    need(value['semantic_revision'] == p['before_scene_revision'] == 'sha256:' + value['semantic_sha256'],
         'PUBLICATION_V3_CAPTURE_SEMANTICS')
    values._files(value['files']); hash_value(value['scene_sha256']); integer(value['scene_size_bytes'], 1, 1024 * 1024)
    need(all(value['files'][path] == p['expected_files'][path] for path in PATHS if path != SCENE_PATH)
         and all(value['files'][SCENE_PATH][key] == value['scene_' + key] for key in ('sha256', 'size_bytes')),
         'PUBLICATION_V3_CAPTURE_INPUTS')


def _validation(value, state, command):
    shape(value, {'command_id', 'project_revision', 'scene_revision', 'manifest_sha256', 'input_files_sha256',
        'source_release_sha256', 'validator_engine_sha256', 'observation_sha256', 'evidence_sha256', 'run_id',
        'validation_started_ms', 'validation_completed_ms', 'context_kind', 'public_ack',
        'selected_state_verified', 'live_editor_adoption_verified'})
    m = command['bundle_manifest']
    need(value['context_kind'] == 'isolated_candidate' and value['public_ack'] is False
         and value['selected_state_verified'] is False and value['live_editor_adoption_verified'] is False,
         'PUBLICATION_V3_VALIDATION_CONTEXT')
    need(value['command_id'] == command['command_id'] and value['project_revision'] == m['project_revision']
         and value['scene_revision'] == m['caller_observations']['scene_revision']
         and value['manifest_sha256'] == digest(m) and value['input_files_sha256'] == digest(m['files'])
         and value['source_release_sha256'] == state['validation_source_release_sha256']
         and value['validator_engine_sha256'] == state['validator_engine_sha256'], 'PUBLICATION_V3_VALIDATION_BINDING')
    for key in ('observation_sha256', 'evidence_sha256'):
        hash_value(value[key])
    need(type(value['run_id']) is str and re.fullmatch(r'hh-gt03-[0-9a-f]{32}', value['run_id']), 'PUBLICATION_V3_VALIDATION_RUN')
    need(value['run_id'] not in state['validation_runs'], 'PUBLICATION_V3_VALIDATION_REUSED')
    state['validation_runs'].append(value['run_id'])
    integer(value['validation_started_ms']); integer(value['validation_completed_ms'])
    need(command['capture']['effect_completed_ms'] <= value['validation_started_ms']
         <= value['validation_completed_ms'] <= state['last_observed_ms'], 'PUBLICATION_V3_VALIDATION_TIME')
    _deadline(command, state['last_observed_ms'])


def _adoption(value, state, command):
    shape(value, {'adoption_id', 'context_kind', 'editor', 'generation_before', 'generation_after',
        'root_instance_id_before', 'root_instance_id_after', 'effect_started_ms', 'effect_completed_ms',
        'semantic_revision', 'semantic_sha256', 'project_revision', 'manifest_sha256', 'files',
        'selection', 'selector_version', 'scene_path', 'history_boundary'})
    p, m = command['capture_prepared'], command['bundle_manifest']
    _fresh(state, value['adoption_id'])
    for key in ('generation_before', 'generation_after', 'root_instance_id_before', 'root_instance_id_after'):
        integer(value[key], 1)
    for key in ('effect_started_ms', 'effect_completed_ms'):
        integer(value[key])
    need(value['context_kind'] == 'live_editor' and same(value['editor'], p['editor'])
         and value['generation_before'] == p['editor_generation']
         and value['generation_after'] > value['generation_before']
         and value['root_instance_id_before'] == p['root_instance_id']
         and value['root_instance_id_after'] != value['root_instance_id_before'], 'PUBLICATION_V3_ADOPTION_IDENTITY')
    need(command['selected_observed_ms'] <= value['effect_started_ms'] <= value['effect_completed_ms']
         <= state['last_observed_ms'], 'PUBLICATION_V3_ADOPTION_TIME')
    _deadline(command, value['effect_started_ms'])
    hash_value(value['semantic_sha256']); hash_value(value['semantic_revision'], revision=True)
    values._files(value['files']); values._selection(value['selection'])
    selector_version(value['selector_version'], state['content_root_identity'])
    need(value['semantic_revision'] == m['caller_observations']['scene_revision'] == 'sha256:' + value['semantic_sha256']
         and value['project_revision'] == m['project_revision'] and value['manifest_sha256'] == digest(m)
         and same(value['files'], m['files']) and same(value['selection'], command['selector']['selection'])
         and same(value['selector_version'], command['selector_version'])
         and value['scene_path'] == 'res://scenes/fixture.tscn' and value['history_boundary'] is True,
         'PUBLICATION_V3_ADOPTION_BINDING')


def _finish(state, command, status, reason):
    p = command['capture_prepared']
    receipt = {'schema': 'hh-godot-publication-observation-3', 'command_id': command['command_id'],
        'digest': command['digest'], 'status': status, 'reason': reason, 'operation': 'scene.save',
        'before_project_revision': p['before_project_revision'], 'before_scene_revision': p['before_scene_revision'],
        'after_project_revision': state['selected']['bundle_manifest']['project_revision'],
        'selection': state['selected']['selector']['selection'], 'selector_version': state['selected']['selector_version'],
        'readback_event_sha256': command.get('readback_event_sha256'), 'public_ack': False,
        'engine_effects_verified': False, 'durable_owner_required': True}
    if status == 'COMMITTED':
        state['last_good'] = state['selected']
        receipt['scene_revision'] = command['bundle_manifest']['caller_observations']['scene_revision']
        receipt['adoption_sha256'] = digest(command['adoption'])
    command.clear(); command.update(command_id=receipt['command_id'], digest=receipt['digest'],
        phase=status, receipt=receipt, receipt_sha256=digest(receipt))
    state['pending_command_id'] = None


def _step(state, event, raw):
    need(type(event) is dict and event.get('kind') in _FIELDS, 'PUBLICATION_V3_KIND')
    kind = event['kind']; shape(event, _COMMON | _FIELDS[kind])
    need(event['schema'] == SCHEMA, 'PUBLICATION_V3_SCHEMA')
    integer(event['sequence'], 1, MAX_EVENTS); integer(event['observed_ms'])
    values._matches(event['project_id'], values._PROJECT)
    if state is None:
        need(kind == 'CONFIG' and event['sequence'] == 1, 'PUBLICATION_V3_CONFIG_FIRST')
        for key in ('validator_engine_sha256', 'editor_engine_sha256', 'source_closure_sha256', 'validation_source_release_sha256'):
            hash_value(event[key])
        values._identity(event['content_root_identity'])
        initial = event['initial']; shape(initial, {'bundle_manifest', 'selector', 'selector_version'})
        shape(initial['selector'], {'schema', 'command_id', 'parent_selection', 'selection', 'descriptor_sha256', 'descriptor'})
        manifest(initial['bundle_manifest'], event)
        desc = initial['selector']['descriptor']; descriptor(desc, initial['bundle_manifest'], event)
        selected = initial['selector']['selection']; values._selection(selected)
        need(selected['generation'] == 0, 'PUBLICATION_V3_BOOTSTRAP_GENERATION')
        selector(initial['selector'], desc, selected, None, 'bootstrap.initial')
        selector_version(initial['selector_version'], event['content_root_identity'])
        need(initial['selector_version']['file_id'] not in
             {r['file_id'] for r in (*desc['files'].values(), desc['manifest'])}, 'PUBLICATION_V3_NATIVE_ALIAS')
        need(initial['selector_version']['sha256'] == digest(initial['selector'])
             and initial['selector_version']['size_bytes'] == len(canonical_bytes(initial['selector'])),
             'PUBLICATION_V3_BOOTSTRAP_VERSION')
        return {**{key: event[key] for key in _FIELDS['CONFIG'] if key != 'initial'},
            'project_id': event['project_id'], 'last_observed_ms': event['observed_ms'], 'event_count': 1,
            'selected': initial, 'last_good': initial, 'commands': [], 'pending_command_id': None,
            'stopped': False, 'held': False, 'observation_ids': [], 'validation_runs': [],
            'scratch_names': [], 'candidate_ids': [],
            'planned_names': [row['name'] for row in (*desc['files'].values(), desc['manifest'])],
            'content_file_ids': [row['file_id'] for row in (*desc['files'].values(), desc['manifest'])],
            'highest_fencing_epoch': 0}
    need(kind != 'CONFIG' and event['sequence'] == state['event_count'] + 1
         and event['project_id'] == state['project_id'] and event['observed_ms'] >= state['last_observed_ms'],
         'PUBLICATION_V3_EVENT_ORDER')
    state['event_count'], state['last_observed_ms'] = event['sequence'], event['observed_ms']
    if kind == 'STOP':
        identifier(event['reason']); need(not state['stopped'], 'PUBLICATION_V3_DUPLICATE_STOP')
        state['stopped'] = True
        command = next((c for c in state['commands'] if c['command_id'] == state['pending_command_id']), None)
        if command:
            if command['phase'] in _EARLY:
                _finish(state, command, 'FAILED', event['reason'])
            else:
                command['uncertain_phase'] = command['phase']; command['phase'] = 'UNKNOWN'; state['held'] = True
        return state
    identifier(event['command_id']); hash_value(event['digest'], revision=True)
    command = next((c for c in state['commands'] if c['command_id'] == event['command_id']), None)
    if command:
        need(command['digest'] == event['digest'], 'PUBLICATION_COMMAND_CONFLICT')
    need(not state['held'] and not state['stopped'], 'PUBLICATION_V3_HELD_OR_STOPPED')
    if kind == 'CAPTURE_PREPARED':
        need(command is None, 'PUBLICATION_V3_DUPLICATE_COMMAND')
        need(state['pending_command_id'] is None and len(state['commands']) < MAX_COMMANDS
             and event['sequence'] + 10 <= MAX_EVENTS, 'PUBLICATION_V3_CAPACITY')
        need(event['operation'] == 'scene.save', 'PUBLICATION_V3_OPERATION')
        values._matches(event['candidate_id'], re.compile(r'candidate-[0-9a-f]{32}\Z'))
        need(event['candidate_id'] not in state['candidate_ids'], 'PUBLICATION_V3_CANDIDATE_REUSED')
        state['candidate_ids'].append(event['candidate_id'])
        m = state['selected']['bundle_manifest']
        need(event['before_project_revision'] == m['project_revision'] and same(event['expected_files'], m['files'])
             and same(event['parent_selection'], state['selected']['selector']['selection'])
             and same(event['checkpoint_descriptor'], state['selected']['selector']['descriptor'])
             and same(event['previous_selector_version'], state['selected']['selector_version'])
             and event['previous_selector_sha256'] == digest(state['selected']['selector']), 'PUBLICATION_V3_CHECKPOINT')
        hash_value(event['before_scene_revision'], revision=True)
        editor_identity(event['editor'], state['editor_engine_sha256'])
        integer(event['editor_generation'], 1, 2147483647); integer(event['root_instance_id'], 1)
        a = event['admission']; shape(a, _ADMISSION_FIELDS)
        for key in ('session_id', 'lease_id'): identifier(a[key])
        hash_value(a['catalog_digest'], revision=True)
        for key in ('fencing_epoch', 'admitted_ms', 'deadline_ms', 'lease_expires_ms'): integer(a[key], 1)
        need(a['fencing_epoch'] >= state['highest_fencing_epoch'] and a['admitted_ms'] <= event['observed_ms']
             < a['deadline_ms'] <= min(a['lease_expires_ms'], a['admitted_ms'] + 30000), 'PUBLICATION_V3_ADMISSION')
        state['highest_fencing_epoch'] = a['fencing_epoch']
        need(type(event['scratch_name']) is str and re.fullmatch(r'capture-[0-9a-f]{32}\.tscn', event['scratch_name'])
             and event['scratch_name'] not in state['scratch_names'], 'PUBLICATION_V3_SCRATCH')
        state['scratch_names'].append(event['scratch_name'])
        command = {'command_id': event['command_id'], 'digest': event['digest'], 'phase': kind, 'capture_prepared': event}
        state['commands'].append(command); state['pending_command_id'] = event['command_id']
        return state
    need(command is not None and state['pending_command_id'] == event['command_id'], 'PUBLICATION_V3_PENDING')
    if kind in ('FAILED', 'UNKNOWN'):
        identifier(event['reason'])
        if kind == 'FAILED':
            need(command['phase'] in _EARLY, 'PUBLICATION_V3_FAILURE_AFTER_EFFECT')
            _finish(state, command, 'FAILED', event['reason'])
        else:
            command['uncertain_phase'] = command['phase']; command['phase'] = 'UNKNOWN'
            command['reason'] = event['reason']; state['held'] = True
        return state
    need(command['phase'] == _NEXT[kind], 'PUBLICATION_V3_PHASE')
    p = command['capture_prepared']
    if kind == 'CAPTURED':
        _capture(event['capture'], state, command); command['capture'] = event['capture']
    elif kind == 'PREPARED':
        shape(event['planned_names'], (*PATHS, '@manifest'))
        names = list(event['planned_names'].values())
        need(all(type(n) is str and re.fullmatch(r'obj-[0-9a-f]{32}', n) for n in names)
             and len(set(names)) == 12 and not set(names).intersection(state['planned_names']), 'PUBLICATION_V3_NAMES')
        state['planned_names'].extend(names); manifest(event['bundle_manifest'], state)
        need(event['bundle_manifest']['files'] == command['capture']['files']
             and event['bundle_manifest']['caller_observations']['scene_revision'] == p['before_scene_revision'],
             'PUBLICATION_V3_FINAL_CAPTURE_BINDING')
        command['planned_names'], command['bundle_manifest'] = event['planned_names'], event['bundle_manifest']
        _deadline(command, event['observed_ms'])
    elif kind == 'STAGED':
        descriptor(event['descriptor'], command['bundle_manifest'], state, command['planned_names'])
        ids = [r['file_id'] for r in (*event['descriptor']['files'].values(), event['descriptor']['manifest'])]
        need(not set(ids).intersection(state['content_file_ids'])
             and state['selected']['selector_version']['file_id'] not in ids, 'PUBLICATION_V3_NATIVE_ALIAS')
        state['content_file_ids'].extend(ids)
        command['descriptor'] = event['descriptor']
    elif kind == 'VALIDATED':
        _validation(event['validation'], state, command); command['validation'] = event['validation']
    elif kind == 'ACTIVATING':
        need(same(event['current'], activation_current(p)), 'PUBLICATION_V3_EFFECT_GUARD')
        need(same(event['expected_selector_version'], state['selected']['selector_version']), 'PUBLICATION_V3_OLD_SELECTOR')
        next_selection = {'generation': p['parent_selection']['generation'] + 1,
            'identity': selection_identity(state['project_id'], command['command_id'], command['digest'],
                                           p['parent_selection'], command['descriptor'], command['bundle_manifest'])}
        selector(event['selector'], command['descriptor'], next_selection, p['parent_selection'], command['command_id'])
        _deadline(command, event['observed_ms'])
        command['selector'] = event['selector']; command['activation_event_sha256'] = hashlib.sha256(raw).hexdigest()
    elif kind == 'SELECTED':
        selector_version(event['selector_version'], state['content_root_identity'])
        need(event['activation_event_sha256'] == command['activation_event_sha256']
             and event['selector_sha256'] == event['selector_version']['sha256'] == digest(command['selector'])
             and event['selector_version']['size_bytes'] == len(canonical_bytes(command['selector']))
             and event['selector_version']['file_id'] != state['selected']['selector_version']['file_id'],
             'PUBLICATION_V3_SELECTED_VERSION')
        need(event['selector_version']['file_id'] not in state['content_file_ids'], 'PUBLICATION_V3_NATIVE_ALIAS')
        command['selector_version'] = event['selector_version']; command['selected_observed_ms'] = event['observed_ms']
        state['selected'] = {'bundle_manifest': command['bundle_manifest'], 'selector': command['selector'],
                             'selector_version': event['selector_version']}
    elif kind == 'READBACK':
        _adoption(event['adoption'], state, command); command['adoption'] = event['adoption']
        command['readback_event_sha256'] = hashlib.sha256(raw).hexdigest()
    else:
        need(event['readback_event_sha256'] == command['readback_event_sha256'], 'PUBLICATION_V3_READBACK_HASH')
        _finish(state, command, 'COMMITTED', 'verified')
        return state
    command['phase'] = kind
    return state


def _event_bytes(event):
    need(type(event) in (dict, bytes), 'PUBLICATION_V3_EVENT_TYPE')
    parsed = parse_json(event) if type(event) is bytes else event
    def check(value):
        need(type(value) in (dict, list, str, int, bool, type(None)), 'PUBLICATION_V3_JSON_TYPE')
        if type(value) is dict:
            need(all(type(key) is str for key in value), 'PUBLICATION_V3_JSON_TYPE')
            for item in value.values(): check(item)
        elif type(value) is list:
            for item in value: check(item)
    check(parsed)
    raw = canonical_bytes(parsed)
    need(len(raw) <= MAX_EVENT_BYTES and (type(event) is dict or event == raw), 'PUBLICATION_V3_EVENT_BYTES')
    return raw


@dataclass(frozen=True, slots=True)
class PublicationState:
    events: tuple[bytes, ...]
    _snapshot: bytes = field(init=False, repr=False)

    def __post_init__(self):
        need(type(self.events) is tuple and 1 <= len(self.events) <= MAX_EVENTS, 'PUBLICATION_V3_HISTORY')
        state = None
        for raw in self.events:
            need(type(raw) is bytes, 'PUBLICATION_V3_HISTORY')
            state = _step(state, parse_json(_event_bytes(raw)), raw)
        encoded = canonical_bytes(state)
        need(len(encoded) <= MAX_SNAPSHOT_BYTES, 'PUBLICATION_V3_SNAPSHOT_LIMIT')
        object.__setattr__(self, '_snapshot', encoded)

    @property
    def event_count(self):
        return len(self.events)

    def snapshot(self):
        return parse_json(self._snapshot)


def reduce_event(state, event):
    need(state is None or type(state) is PublicationState, 'PUBLICATION_V3_STATE_TYPE')
    return PublicationState((() if state is None else state.events) + (_event_bytes(event),))


def replay(events):
    return PublicationState(tuple(_event_bytes(event) for event in events))


def lookup(state, command_id, command_digest=None):
    identifier(command_id)
    if command_digest is not None: hash_value(command_digest, revision=True)
    command = next((c for c in state.snapshot()['commands'] if c['command_id'] == command_id), None)
    if command is None: return None
    need(command_digest is None or command_digest == command['digest'], 'PUBLICATION_COMMAND_CONFLICT')
    return {**command, 'execution_permitted': False, 'public_ack': False, 'engine_effects_verified': False,
            'durable_owner_required': True}
