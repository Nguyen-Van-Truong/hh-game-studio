"""Pure v2 history tests; native identities and engine facts are synthetic."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.protocol.core import ValidationError, canonical_bytes, parse_json


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, STUDIO / 'godot-addon' / filename)
    result = importlib.util.module_from_spec(spec); sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


publication = load('gt03_publication_state_v2_tests', 'publication_state_v2.py')
codec = load('gt03_publication_codec_v2_tests', 'bundle_v2.py')


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def revision(text):
    return 'sha256:' + digest(text)


def synthetic_files():
    return {path: (b'uid://abc123\n' if path.endswith('.uid') else ('synthetic ' + path + '\n').encode())
            for path in codec.PATHS}


def configuration():
    bundle = codec.create_bundle(synthetic_files(), scene_revision=revision('initial-scene'), engine_sha256=digest('engine'))
    return {'schema': publication.SCHEMA, 'kind': 'CONFIG', 'sequence': 1, 'project_id': 'synthetic-project',
        'observed_ms': 100, 'engine_sha256': bundle.engine_sha256, 'source_closure_sha256': digest('source'),
        'content_root_identity': {'volume': '12', 'file_id': 'a' * 32},
        'initial': {'project_revision': bundle.project_revision, 'scene_revision': bundle.scene_revision,
                    'files': parse_json(bundle.manifest_bytes)['files'],
                    'selection': {'generation': 0, 'identity': revision('initial-selection')}}}


def event(state, kind, **fields):
    snapshot = state.snapshot()
    return {'schema': publication.SCHEMA, 'kind': kind, 'sequence': state.event_count + 1,
            'project_id': snapshot['project_id'], 'observed_ms': snapshot['last_observed_ms'] + 1, **fields}


def prepared(state, identifier='cmd.one', operation='scene.save'):
    snapshot = state.snapshot(); initial = snapshot['last_good']; now = snapshot['last_observed_ms'] + 1
    return event(state, 'PREPARED', command_id=identifier, digest=revision(identifier), operation=operation,
        candidate_id='candidate-' + digest(identifier)[:32], before_project_revision=initial['project_revision'],
        before_scene_revision=initial['scene_revision'], expected_files=initial['files'], parent_selection=initial['selection'],
        checkpoint_sha256=digest('checkpoint-' + identifier),
        planned_names={path: 'obj-' + digest(identifier + path)[:32] for path in (*codec.PATHS, '@manifest')},
        script_input={'sha256': digest('new-script'), 'size_bytes': len('new-script')} if operation == 'script_text.replace' else None,
        admission={'lease_id': 'lease.one', 'fencing_epoch': 1, 'admitted_ms': now, 'deadline_ms': now + 1000,
                   'lease_expires_ms': 10000, 'editor_session_id': 'editor.live', 'editor_generation': 1})


def candidate(state):
    snapshot = state.snapshot(); request = snapshot['commands'][-1]['prepared']; root = snapshot['content_root_identity']
    metadata = deepcopy(request['expected_files'])
    if request['operation'] == 'script_text.replace':
        metadata[publication.SCRIPT_PATH].update(request['script_input'])
        scene = revision('new-script-scene')
    else:
        metadata[publication.SCENE_PATH].update(sha256=digest('saved-scene'), size_bytes=len('saved-scene'))
        scene = request['before_scene_revision']
    manifest = publication.bundle_manifest(metadata, scene, snapshot['engine_sha256'])
    raw = canonical_bytes(manifest)
    descriptor = {'root_identity': root, 'project_revision': manifest['project_revision'], 'files': {}}
    for path in (*codec.PATHS, '@manifest'):
        info = {'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw)} if path == '@manifest' else metadata[path]
        row = {'name': request['planned_names'][path], 'volume': root['volume'],
               'file_id': digest('fileid-' + request['command_id'] + path)[:32],
               **{key: info[key] for key in ('sha256', 'size_bytes')}}
        if path == '@manifest': descriptor['manifest'] = row
        else: descriptor['files'][path] = row
    scene_observation = None
    if request['operation'] == 'script_text.replace':
        scene_observation = {'observation_id': 'candidate.' + request['command_id'], 'editor_session_id': 'candidate.session',
            'editor_generation': 1, 'observed_ms': snapshot['last_observed_ms'] + 1,
            'project_revision': manifest['project_revision'], 'scene_revision': scene,
            'engine_sha256': snapshot['engine_sha256'], 'source_closure_sha256': snapshot['source_closure_sha256']}
    return {'candidate_id': request['candidate_id'], 'descriptor': descriptor,
            'bundle_manifest': manifest, 'scene_observation': scene_observation}


def observation(state, kind):
    snapshot = state.snapshot(); command = snapshot['commands'][-1]; declared = command['candidate']
    manifest = declared['bundle_manifest']
    value = {'observation_id': kind + '.' + command['command_id'], 'editor_session_id': kind + '.session',
        'editor_generation': 1, 'observed_ms': snapshot['last_observed_ms'] + 1,
        'candidate_id': declared['candidate_id'], 'project_revision': manifest['project_revision'],
        **manifest['caller_observations'], 'source_closure_sha256': snapshot['source_closure_sha256'],
        'manifest_sha256': declared['descriptor']['manifest']['sha256'], 'files': manifest['files'],
        'parse_status': 'PASS', 'import_status': 'PASS', 'exit_code': 0, 'tree_drained': True, 'logs_clean': True}
    if kind == 'validation' and declared['scene_observation'] is not None:
        value.update(declared['scene_observation'])
    return value


def next_event(state):
    snapshot = state.snapshot(); command = snapshot['commands'][-1]
    common = {'command_id': command['command_id'], 'digest': command['digest']}
    phase = command['phase']
    if phase == 'PREPARED': return event(state, 'STAGED', **common, candidate=candidate(state))
    if phase == 'STAGED': return event(state, 'VALIDATED', **common, observation=observation(state, 'validation'))
    if phase == 'VALIDATED':
        request = command['prepared']
        current = {'project_revision': request['before_project_revision'], 'scene_revision': request['before_scene_revision'],
            'files': request['expected_files'], 'selection': request['parent_selection'],
            **{key: request['admission'][key] for key in ('lease_id', 'fencing_epoch', 'editor_session_id', 'editor_generation')}}
        selected = {'generation': request['parent_selection']['generation'] + 1,
            'identity': publication.selection_identity(snapshot['project_id'], command['command_id'], command['digest'],
                                                       request['parent_selection'], command['candidate'])}
        return event(state, 'ACTIVATING', **common, current=current, selection=selected)
    if phase == 'ACTIVATING':
        return event(state, 'READBACK', **common, observation=observation(state, 'reopen'), selection=command['selection'])
    if phase == 'READBACK':
        return event(state, 'COMMITTED', **common, readback_event_sha256=command['readback_event_sha256'],
            after_project_revision=command['candidate']['descriptor']['project_revision'], selection=command['selection'])
    raise AssertionError('no next phase')


def history(operation='scene.save'):
    rows = [configuration()]; state = publication.replay(rows)
    rows.append(prepared(state, operation=operation)); state = publication.reduce_event(state, rows[-1])
    for _ in range(5):
        rows.append(next_event(state)); state = publication.reduce_event(state, rows[-1])
    return rows


class PublicationV2Tests(unittest.TestCase):
    def setUp(self):
        self.rows = history()

    def state(self, count=7):
        return publication.replay(self.rows[:count])

    def reject(self, function, *args, code=None):
        with self.assertRaises(ValidationError) as raised:
            function(*args)
        if code: self.assertEqual(raised.exception.code, code)

    def test_codec_algorithm_roles_and_project_digest_match_actual_bytes(self):
        raw_files = synthetic_files(); bundle = codec.create_bundle(raw_files, scene_revision=revision('initial-scene'), engine_sha256=digest('engine'))
        metadata = parse_json(bundle.manifest_bytes)['files']
        self.assertEqual(canonical_bytes(publication.bundle_manifest(metadata, bundle.scene_revision, bundle.engine_sha256)), bundle.manifest_bytes)
        self.assertEqual(publication.PATHS, codec.PATHS)
        self.assertEqual(publication.FILE_PROFILE, dict(codec.FILE_PROFILE))

    def test_full_scene_and_script_operations_have_inert_terminal_receipts(self):
        for operation in ('scene.save', 'script_text.replace'):
            rows = history(operation); state = publication.replay(rows)
            result = publication.lookup(state, 'cmd.one', revision('cmd.one'))
            self.assertEqual(result['phase'], 'COMMITTED')
            self.assertFalse(result['execution_permitted']); self.assertFalse(result['public_ack'])
            self.assertFalse(result['engine_effects_verified']); self.assertTrue(result['durable_owner_required'])
            self.assertEqual(result['receipt']['candidate_descriptor_sha256'], hashlib.sha256(canonical_bytes(rows[2]['candidate']['descriptor'])).hexdigest())
            self.assertEqual(len(result['receipt']['files']), 11)

    def test_every_phase_cut_replay_is_identical_and_never_executes(self):
        for operation in ('scene.save', 'script_text.replace'):
            rows = history(operation)
            for count in range(1, 8):
                state = publication.replay(rows[:count])
                self.assertEqual(publication.PublicationState(state.events).snapshot(), state.snapshot())
                result = publication.lookup(state, 'cmd.one')
                if result: self.assertFalse(result['execution_permitted'])

    def test_immutable_history_and_detached_lookup(self):
        state = self.state(); before = state.snapshot(); view = state.snapshot(); view['last_good']['files'].clear()
        found = publication.lookup(state, 'cmd.one'); found['receipt']['files'].clear()
        self.assertEqual(state.snapshot(), before)
        with self.assertRaises(FrozenInstanceError): state.events = ()
        self.reject(publication.PublicationState, tuple(self.rows))

    def test_duplicate_lookup_and_changed_digest_do_not_mutate(self):
        state = self.state(); before = state.events
        self.assertEqual(publication.lookup(state, 'cmd.one'), publication.lookup(state, 'cmd.one', revision('cmd.one')))
        self.reject(publication.lookup, state, 'cmd.one', revision('different'), code='PUBLICATION_COMMAND_CONFLICT')
        self.reject(publication.reduce_event, state, prepared(state), code='PUBLICATION_DUPLICATE_EVENT')
        self.assertEqual(state.events, before)
        self.assertEqual(publication.reduce_event(state, event(state, 'STOP', reason='USER_STOP')).snapshot()['stopped'], True)

    def test_wrong_version_unknown_fields_and_exact_metadata_shape(self):
        for index, change in ((0, lambda row: row.update(schema='hh-godot-publication-event-1')),
                              (1, lambda row: row.update(force=True)),
                              (2, lambda row: row['candidate']['descriptor'].update(blob_store=True)),
                              (2, lambda row: row['candidate']['bundle_manifest']['files'][codec.SCRIPT_PATH].update(extra=1))):
            rows = deepcopy(self.rows); change(rows[index]); self.reject(publication.replay, rows[:index + 1])

    def test_plan_must_have_exact_twelve_unique_obj_names(self):
        for change in (lambda names: names.pop('@manifest'), lambda names: names.update({'../outside': 'obj-' + '1' * 32}),
                       lambda names: names.update({'@manifest': names[codec.PATHS[0]]}),
                       lambda names: names.update({'@manifest': 'blob-' + '1' * 32})):
            row = deepcopy(self.rows[1]); change(row['planned_names']); self.reject(publication.reduce_event, self.state(1), row)

    def test_plan_names_cannot_be_reused_after_terminal_failure(self):
        state = self.state(2)
        state = publication.reduce_event(state, event(state, 'FAILED', command_id='cmd.one', digest=revision('cmd.one'),
                reason='STAGING_FAILED', publication_not_started=True, staging_may_exist=False))
        row = prepared(state, 'cmd.next'); row['planned_names'] = self.rows[1]['planned_names']
        self.reject(publication.reduce_event, state, row, code='PUBLICATION_PLANNED_NAME_REUSED')

    def test_foreign_root_volume_and_root_fileid_reject(self):
        changes = (lambda c: c['descriptor']['root_identity'].update(file_id='b' * 32),
                   lambda c: c['descriptor']['manifest'].update(volume='13'),
                   lambda c: c['descriptor']['manifest'].update(file_id='a' * 32))
        for change in changes:
            row = deepcopy(self.rows[2]); change(row['candidate']); self.reject(publication.reduce_event, self.state(2), row)

    def test_fileversions_names_hash_lengths_and_aliases_reject(self):
        changes = (lambda d: d['manifest'].update(file_id=d['files'][codec.PATHS[0]]['file_id']),
                   lambda d: d['manifest'].update(name='obj-' + 'f' * 32),
                   lambda d: d['manifest'].update(sha256='f' * 64),
                   lambda d: d['manifest'].update(size_bytes=1),
                   lambda d: d['files'][codec.SCRIPT_PATH].update(sha256='f' * 64),
                   lambda d: d['files'][codec.SCRIPT_PATH].update(size_bytes=True))
        for change in changes:
            row = deepcopy(self.rows[2]); change(row['candidate']['descriptor']); self.reject(publication.reduce_event, self.state(2), row)

    def test_metadata_role_engine_trusted_revision_and_digest_reject(self):
        changes = (lambda m: m['files'][codec.SCRIPT_PATH].update(role='trusted_addon'),
                   lambda m: m['caller_observations'].update(engine_sha256='f' * 64),
                   lambda m: m.update(trusted_source_revision=revision('wrong')),
                   lambda m: m.update(project_revision=revision('wrong')),
                   lambda m: m.update(profile='arbitrary'))
        for change in changes:
            row = deepcopy(self.rows[2]); change(row['candidate']['bundle_manifest']); self.reject(publication.reduce_event, self.state(2), row)

    def test_all_eleven_metadata_rows_are_checked(self):
        for path in codec.PATHS:
            row = deepcopy(self.rows[2]); row['candidate']['descriptor']['files'][path]['sha256'] = 'f' * 64
            self.reject(publication.reduce_event, self.state(2), row)

    def test_each_file_bound_rejects_oversize_zero_and_bool(self):
        for path in codec.PATHS:
            for number in (0, True, codec.FILE_PROFILE[path][1] + 1):
                row = deepcopy(self.rows[0]); row['initial']['files'][path]['size_bytes'] = number
                self.reject(publication.replay, [row])

    def coherent_metadata_change(self, row, path):
        c = row['candidate']; meta = c['bundle_manifest']['files']; meta[path]['sha256'] = digest('tampered-' + path)
        c['bundle_manifest'] = publication.bundle_manifest(meta, c['bundle_manifest']['caller_observations']['scene_revision'], digest('engine'))
        raw = canonical_bytes(c['bundle_manifest']); c['descriptor']['project_revision'] = c['bundle_manifest']['project_revision']
        c['descriptor']['files'][path]['sha256'] = meta[path]['sha256']
        c['descriptor']['manifest'].update(sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw))
        if c['scene_observation']: c['scene_observation']['project_revision'] = c['bundle_manifest']['project_revision']

    def test_script_replace_preserves_scene_uid_and_all_trusted_bytes(self):
        rows = history('script_text.replace'); before = publication.replay(rows[:2])
        for path in codec.PATHS:
            if path != codec.SCRIPT_PATH:
                row = deepcopy(rows[2]); self.coherent_metadata_change(row, path)
                self.reject(publication.reduce_event, before, row, code='PUBLICATION_UNRELATED_FILE_CHANGED')

    def test_scene_save_preserves_script_uid_and_all_trusted_bytes(self):
        for path in codec.PATHS:
            if path != codec.SCENE_PATH:
                row = deepcopy(self.rows[2]); self.coherent_metadata_change(row, path)
                self.reject(publication.reduce_event, self.state(2), row, code='PUBLICATION_UNRELATED_FILE_CHANGED')

    def test_script_replace_requires_explicit_fresh_full_digest_observation(self):
        rows = history('script_text.replace'); state = publication.replay(rows[:2])
        changes = (lambda c: c.update(scene_observation=None),
                   lambda c: c['scene_observation'].update(project_revision=revision('stale')),
                   lambda c: c['scene_observation'].update(editor_session_id='editor.live'),
                   lambda c: c['scene_observation'].update(observed_ms=0),
                   lambda c: c['scene_observation'].update(observed_ms=10000),
                   lambda c: c['scene_observation'].update(editor_generation=True),
                   lambda c: c['scene_observation'].update(source_closure_sha256='f' * 64))
        for change in changes:
            row = deepcopy(rows[2]); change(row['candidate']); self.reject(publication.reduce_event, state, row)

    def test_same_fresh_candidate_observation_can_supply_validation_without_second_engine_pass(self):
        rows = history('script_text.replace')
        self.assertEqual(rows[2]['candidate']['scene_observation']['observation_id'], rows[3]['observation']['observation_id'])
        self.assertEqual(len(publication.replay(rows).snapshot()['observation_ids']), 2)
        row = deepcopy(rows[3]); row['observation']['observed_ms'] += 1
        self.reject(publication.reduce_event, publication.replay(rows[:3]), row, code='PUBLICATION_OBSERVATION_MISMATCH')

    def test_scene_save_binds_live_unsaved_revision(self):
        state = self.state(1); row = prepared(state); row['before_scene_revision'] = revision('live-unsaved')
        state = publication.reduce_event(state, row)
        for _ in range(5): state = publication.reduce_event(state, next_event(state))
        self.assertEqual(state.snapshot()['last_good']['scene_revision'], revision('live-unsaved'))

    def test_native_parse_import_exit_tree_and_logs_attestations_must_pass(self):
        for key, value in (('parse_status', 'FAIL'), ('import_status', 'FAIL'), ('exit_code', True),
                           ('tree_drained', 1), ('logs_clean', False), ('manifest_sha256', 'f' * 64)):
            row = deepcopy(self.rows[3]); row['observation'][key] = value
            self.reject(publication.reduce_event, self.state(3), row)

    def test_readback_requires_new_observation_and_new_session(self):
        for key in ('observation_id', 'editor_session_id'):
            row = deepcopy(self.rows[5]); row['observation'][key] = self.rows[3]['observation'][key]
            self.reject(publication.reduce_event, self.state(5), row)

    def test_readback_timestamp_must_follow_activation_even_with_rehashed_commit(self):
        for operation in ('scene.save', 'script_text.replace'):
            rows = history(operation)
            activation_time = rows[4]['observed_ms']
            for observed_time in (activation_time - 1, activation_time, activation_time + 1):
                changed = deepcopy(rows)
                changed[5]['observation']['observed_ms'] = observed_time
                changed[6]['readback_event_sha256'] = hashlib.sha256(canonical_bytes(changed[5])).hexdigest()
                if observed_time < activation_time:
                    self.reject(publication.replay, changed, code='PUBLICATION_READBACK_BEFORE_ACTIVATION')
                else:
                    self.assertEqual(publication.lookup(publication.replay(changed), 'cmd.one')['phase'], 'COMMITTED')

    def test_scene_observation_id_cannot_recur_on_another_command(self):
        state = publication.replay(history('script_text.replace'))
        state = publication.reduce_event(state, prepared(state, 'cmd.next', 'script_text.replace'))
        row = next_event(state); row['candidate']['scene_observation']['observation_id'] = 'candidate.cmd.one'
        self.reject(publication.reduce_event, state, row, code='PUBLICATION_OBSERVATION_REUSED')

    def test_expired_lease_and_stale_fence_at_activation_reject(self):
        for change in (lambda row: row.update(observed_ms=10000),
                       lambda row: row['current'].update(fencing_epoch=2),
                       lambda row: row['current'].update(editor_generation=2),
                       lambda row: row['current'].update(lease_id='lease.other'),
                       lambda row: row['current'].update(scene_revision=revision('manual-edit'))):
            row = deepcopy(self.rows[4]); change(row); self.reject(publication.reduce_event, self.state(4), row)

    def test_terminal_after_deadline_retains_original_admission(self):
        row = deepcopy(self.rows[6]); row['observed_ms'] = 20000
        state = publication.reduce_event(self.state(6), row)
        self.assertEqual(publication.lookup(state, 'cmd.one')['receipt']['admission'], self.rows[1]['admission'])

    def test_stale_base_single_pending_and_same_epoch_rebinding_reject(self):
        self.reject(publication.reduce_event, self.state(2), prepared(self.state(2), 'cmd.other'))
        state = self.state()
        for change in (lambda row: row.update(before_project_revision=revision('old')),
                       lambda row: row['admission'].update(lease_id='lease.other'),
                       lambda row: row['admission'].update(lease_expires_ms=10001)):
            row = prepared(state, 'cmd.other'); change(row); self.reject(publication.reduce_event, state, row)

    def test_stop_at_all_phase_cuts_preserves_or_holds_without_resume(self):
        for count in range(1, 8):
            state = self.state(count); stopped = publication.reduce_event(state, event(state, 'STOP', reason='USER_STOP'))
            self.assertTrue(stopped.snapshot()['stopped'])
            found = publication.lookup(stopped, 'cmd.one')
            if 2 <= count <= 4: self.assertEqual(found['phase'], 'FAILED')
            if 5 <= count <= 6: self.assertEqual(found['phase'], 'UNKNOWN'); self.assertTrue(stopped.snapshot()['held'])
            if count == 7: self.assertEqual(found['phase'], 'COMMITTED')
            self.reject(publication.reduce_event, stopped, event(stopped, 'STOP', reason='USER_STOP'))
            self.reject(publication.reduce_event, stopped, prepared(stopped, 'cmd.other'))

    def test_unknown_each_effect_boundary_is_permanent_hold(self):
        for count, reason in ((2, 'STAGING_UNCERTAIN'), (3, 'VALIDATION_UNCERTAIN'), (4, 'ACTIVATION_UNCERTAIN'),
                              (5, 'READBACK_UNCERTAIN'), (6, 'TERMINAL_UNCERTAIN')):
            state = self.state(count)
            held = publication.reduce_event(state, event(state, 'UNKNOWN', command_id='cmd.one', digest=revision('cmd.one'), reason=reason))
            self.assertTrue(held.snapshot()['held']); self.assertFalse(publication.lookup(held, 'cmd.one')['execution_permitted'])
            self.reject(publication.reduce_event, held, prepared(held, 'cmd.other'))

    def test_failure_only_before_possible_publication(self):
        for count in (2, 3, 4):
            state = self.state(count)
            failed = publication.reduce_event(state, event(state, 'FAILED', command_id='cmd.one', digest=revision('cmd.one'),
                reason='VALIDATION_FAILED', publication_not_started=True, staging_may_exist=True))
            self.assertEqual(failed.snapshot()['last_good'], self.rows[0]['initial'])
        for count in (5, 6):
            state = self.state(count)
            self.reject(publication.reduce_event, state, event(state, 'FAILED', command_id='cmd.one', digest=revision('cmd.one'),
                reason='CANCELED', publication_not_started=True, staging_may_exist=True))

    def test_selection_descriptor_identity_and_terminal_readback_binding(self):
        for index, change in ((4, lambda row: row['selection'].update(identity=revision('wrong'))),
                              (5, lambda row: row['selection'].update(generation=7)),
                              (6, lambda row: row.update(readback_event_sha256='f' * 64)),
                              (6, lambda row: row.update(after_project_revision=revision('wrong')))):
            row = deepcopy(self.rows[index]); change(row); self.reject(publication.reduce_event, self.state(index), row)

    def test_reordered_duplicate_truncated_and_wrong_project_history(self):
        self.reject(publication.replay, self.rows[:2] + self.rows[3:])
        self.reject(publication.replay, self.rows[:2] + [self.rows[1]])
        row = deepcopy(self.rows[2]); row['project_id'] = 'wrong'; self.reject(publication.reduce_event, self.state(2), row)
        row = deepcopy(self.rows[2]); row['observed_ms'] = 0; self.reject(publication.reduce_event, self.state(2), row)

    def test_noncanonical_oversize_duplicate_json_and_bool_sequence_reject(self):
        self.reject(publication.replay, [json.dumps(self.rows[0]).encode()])
        self.reject(publication.replay, [b' ' * (publication.MAX_EVENT_BYTES + 1)])
        self.reject(publication.replay, [canonical_bytes(self.rows[0])[:-1] + b',"kind":"CONFIG"}'])
        row = deepcopy(self.rows[0]); row['sequence'] = True; self.reject(publication.replay, [row])

    def test_native_event_frame_and_complete_history_capacity_are_bounded(self):
        maximum = max(len(canonical_bytes(row)) for op in ('scene.save', 'script_text.replace') for row in history(op))
        self.assertLess(maximum, publication.MAX_EVENT_BYTES)
        envelope = {'format': 'hh-private-events-1', 'sequence': 257, 'previous': 'a' * 64,
                    'event': parse_json(max((canonical_bytes(row) for row in history('script_text.replace')), key=len))}
        self.assertLess(len(canonical_bytes(envelope)), 16 * 1024)
        self.assertLess((publication.MAX_EVENTS + 1) * (publication.MAX_EVENT_BYTES + 4096 + 36), 8 * 1024 * 1024)

    def test_terminal_command_capacity_keeps_original_ids_and_stop_room(self):
        state = self.state(1)
        for index in range(publication.MAX_COMMANDS):
            identifier = 'cmd.failed.' + str(index)
            state = publication.reduce_event(state, prepared(state, identifier))
            state = publication.reduce_event(state, event(state, 'FAILED', command_id=identifier, digest=revision(identifier),
                reason='CANCELED', publication_not_started=True, staging_may_exist=False))
        self.reject(publication.reduce_event, state, prepared(state, 'cmd.overflow'), code='PUBLICATION_COMMAND_LIMIT')
        self.assertEqual(publication.lookup(state, 'cmd.failed.0')['phase'], 'FAILED')
        self.assertTrue(publication.reduce_event(state, event(state, 'STOP', reason='USER_STOP')).snapshot()['stopped'])

    def test_event_capacity_reserves_all_success_phases_and_stop(self):
        state = self.state(1)
        for index in range(42):
            state = publication.reduce_event(state, prepared(state, 'cmd.complete.' + str(index)))
            for _ in range(5): state = publication.reduce_event(state, next_event(state))
        self.assertEqual(state.event_count, 253)
        self.reject(publication.reduce_event, state, prepared(state, 'cmd.overflow'), code='PUBLICATION_EVENT_CAPACITY')
        self.assertTrue(publication.reduce_event(state, event(state, 'STOP', reason='USER_STOP')).snapshot()['stopped'])

    def test_replay_and_lookup_perform_no_io(self):
        with mock.patch('builtins.open', side_effect=AssertionError('unexpected I/O')), \
             mock.patch('subprocess.Popen', side_effect=AssertionError('unexpected process')):
            self.assertEqual(publication.lookup(publication.replay(self.rows), 'cmd.one')['phase'], 'COMMITTED')


if __name__ == '__main__':
    unittest.main(verbosity=2)
