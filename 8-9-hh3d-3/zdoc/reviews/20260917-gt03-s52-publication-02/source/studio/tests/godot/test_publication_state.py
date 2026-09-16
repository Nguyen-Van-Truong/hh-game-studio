"""Pure publication-history tests. All engine/file observations are synthetic."""
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
SPEC = importlib.util.spec_from_file_location('gt03_publication_state', STUDIO / 'godot-addon/publication_state.py')
publication = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = publication
SPEC.loader.exec_module(publication)
from studio.protocol.core import ValidationError, canonical_bytes


def digest(label):
    return hashlib.sha256(label.encode()).hexdigest()


def revision(label):
    return 'sha256:' + digest(label)


def configuration():
    files = {publication.SCENE_PATH: {'sha256': digest('scene-old'), 'size_bytes': 100},
             publication.SCRIPT_PATH: {'sha256': digest('script-old'), 'size_bytes': 15}}
    engine, scene = digest('engine'), revision('scene-semantic-old')
    return {'schema': publication.SCHEMA, 'sequence': 1, 'kind': 'CONFIG', 'project_id': 'test-project',
            'observed_ms': 100, 'engine_sha256': engine, 'source_closure_sha256': digest('closure'),
            'store_identity': {'volume': '12', 'file_id': 'a' * 32},
            'initial': {'project_revision': publication.project_revision(files, scene, engine),
                        'scene_revision': scene, 'files': files,
                        'selection': {'generation': 0, 'identity': revision('initial-selection')}}}


def event(state, kind, **fields):
    snapshot = state.snapshot()
    return {'schema': publication.SCHEMA, 'sequence': state.event_count + 1, 'kind': kind,
            'project_id': snapshot['project_id'], 'observed_ms': snapshot['last_observed_ms'] + 1, **fields}


def prepared(state, identifier='cmd.save.1', operation='scene.save'):
    snapshot = state.snapshot()
    before = snapshot['last_good']
    now = snapshot['last_observed_ms'] + 1
    return event(state, 'PREPARED', command_id=identifier, digest=revision(identifier), operation=operation,
        candidate_id='candidate-' + digest(identifier)[:32], before_project_revision=before['project_revision'],
        before_scene_revision=before['scene_revision'], expected_files=before['files'], parent_selection=before['selection'],
        admission={'lease_id': 'lease.one', 'fencing_epoch': 1, 'admitted_ms': now,
                   'deadline_ms': now + 1000, 'lease_expires_ms': 10000,
                   'editor_session_id': 'editor.live', 'editor_generation': 1},
        checkpoint_sha256=digest('checkpoint-' + identifier),
        script_input={'sha256': digest('new-script'), 'size_bytes': 32} if operation == 'script_text.replace' else None)


def staged_candidate(state):
    snapshot = state.snapshot()
    request = snapshot['commands'][-1]['prepared']
    identity = snapshot['store_identity']
    metadata = {publication.SCENE_PATH: {'sha256': digest(request['candidate_id']), 'size_bytes': 140},
                publication.SCRIPT_PATH: request['script_input'] or request['expected_files'][publication.SCRIPT_PATH]}
    files = {}
    for index, (path, info) in enumerate(metadata.items(), start=1):
        files[path] = {'object_id': 'blob-' + f'{index:032x}', 'volume': identity['volume'],
                       'file_id': f'{index + 10:032x}', **info}
    scene = request['before_scene_revision'] if request['operation'] == 'scene.save' else revision('new-script-semantic')
    return {'candidate_id': request['candidate_id'], 'project_revision': publication.project_revision(metadata, scene, snapshot['engine_sha256']),
            'scene_revision': scene, 'engine_sha256': snapshot['engine_sha256'], 'files': files,
            'manifest': {'object_id': 'blob-' + '3'.zfill(32), 'volume': identity['volume'], 'file_id': '13'.zfill(32),
                         'size_bytes': 1000, 'sha256': digest('candidate-manifest')}}


def observation(state, kind):
    snapshot = state.snapshot()
    candidate = snapshot['commands'][-1]['candidate']
    return {'observation_id': kind + '.observation', 'editor_session_id': kind + '.session', 'editor_generation': 1,
            'candidate_id': candidate['candidate_id'], 'project_revision': candidate['project_revision'],
            'scene_revision': candidate['scene_revision'], 'engine_sha256': candidate['engine_sha256'],
            'source_closure_sha256': snapshot['source_closure_sha256'], 'manifest_sha256': candidate['manifest']['sha256'],
            'files': {path: {'sha256': value['sha256'], 'size_bytes': value['size_bytes']} for path, value in candidate['files'].items()},
            'parse_status': 'PASS', 'import_status': 'PASS', 'exit_code': 0, 'tree_drained': True, 'logs_clean': True}


def next_event(state):
    snapshot = state.snapshot()
    command = snapshot['commands'][-1]
    common = {'command_id': command['command_id'], 'digest': command['digest']}
    phase = command['phase']
    if phase == 'PREPARED':
        return event(state, 'STAGED', **common, candidate=staged_candidate(state))
    if phase == 'STAGED':
        return event(state, 'VALIDATED', **common, observation=observation(state, 'validation'))
    if phase == 'VALIDATED':
        request = command['prepared']
        current = {'project_revision': request['before_project_revision'], 'scene_revision': request['before_scene_revision'],
                   'files': request['expected_files'], 'selection': request['parent_selection'],
                   **{k: request['admission'][k] for k in ('lease_id', 'fencing_epoch', 'editor_session_id', 'editor_generation')}}
        selected = {'generation': request['parent_selection']['generation'] + 1,
                    'identity': publication.selection_identity(snapshot['project_id'], command['command_id'], command['digest'],
                                                              request['parent_selection'], command['candidate'])}
        return event(state, 'ACTIVATING', **common, current=current, selection=selected)
    if phase == 'ACTIVATING':
        return event(state, 'READBACK', **common, observation=observation(state, 'reopen'), selection=command['selection'])
    if phase == 'READBACK':
        return event(state, 'COMMITTED', **common, readback_event_sha256=command['readback_event_sha256'],
                     after_project_revision=command['candidate']['project_revision'], selection=command['selection'])
    raise AssertionError('no next phase')


def history(operation='scene.save'):
    rows = [configuration()]
    state = publication.replay(rows)
    rows.append(prepared(state, operation=operation))
    state = publication.reduce_event(state, rows[-1])
    for _ in range(5):
        rows.append(next_event(state))
        state = publication.reduce_event(state, rows[-1])
    return rows


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.rows = history()

    def state(self, count=7):
        return publication.replay(self.rows[:count])

    def assert_reject(self, code, function, *args):
        with self.assertRaises(ValidationError) as raised:
            function(*args)
        self.assertEqual(raised.exception.code, code)

    def test_every_phase_cut_replay_keeps_same_observation_without_execution(self):
        phases = ('CONFIG', 'PREPARED', 'STAGED', 'VALIDATED', 'ACTIVATING', 'READBACK', 'COMMITTED')
        for count, phase in enumerate(phases, 1):
            with self.subTest(phase=phase):
                state = self.state(count)
                reopened = publication.replay(state.events)
                self.assertEqual(state, reopened)
                self.assertEqual(state.snapshot(), reopened.snapshot())
                self.assertEqual(state.event_count, count)
                result = publication.lookup(reopened, 'cmd.save.1')
                if count == 1:
                    self.assertIsNone(result)
                else:
                    self.assertEqual(result['phase'], phase)
                    self.assertFalse(result['execution_permitted'])
                    self.assertFalse(result['public_ack'])
                    self.assertEqual(reopened.snapshot()['pending_command_id'], None if phase == 'COMMITTED' else 'cmd.save.1')
                if count < 7:
                    self.assertEqual(state.snapshot()['last_good'], self.rows[0]['initial'])

    def test_committed_receipt_binds_pair_and_reply_loss_lookup_is_identical(self):
        state = self.state()
        original = publication.lookup(state, 'cmd.save.1', revision('cmd.save.1'))
        reopened = publication.replay(state.events)
        self.assertEqual(publication.lookup(reopened, 'cmd.save.1', revision('cmd.save.1')), original)
        receipt = original['receipt']
        self.assertEqual(receipt['before_project_revision'], self.rows[0]['initial']['project_revision'])
        self.assertEqual(receipt['after_project_revision'], self.rows[2]['candidate']['project_revision'])
        self.assertEqual(receipt['files'], self.rows[5]['observation']['files'])
        self.assertEqual(receipt['selection'], self.rows[4]['selection'])
        self.assertEqual(receipt['admission'], self.rows[1]['admission'])
        self.assertEqual(original['receipt_sha256'], hashlib.sha256(canonical_bytes(receipt)).hexdigest())
        self.assertTrue(receipt['durable_owner_required'])
        self.assertFalse(receipt['public_ack'])

    def test_lookup_detached_and_same_id_conflict_or_duplicate_event_never_reexecutes(self):
        state = self.state()
        result = publication.lookup(state, 'cmd.save.1')
        expected = deepcopy(result)
        result['receipt']['files'].clear()
        self.assertEqual(publication.lookup(state, 'cmd.save.1'), expected)
        self.assert_reject('PUBLICATION_COMMAND_CONFLICT', publication.lookup, state, 'cmd.save.1', revision('different'))
        duplicate = prepared(state)
        self.assert_reject('PUBLICATION_DUPLICATE_EVENT', publication.reduce_event, state, duplicate)
        duplicate['digest'] = revision('different')
        self.assert_reject('PUBLICATION_COMMAND_CONFLICT', publication.reduce_event, state, duplicate)

    def test_snapshot_history_and_input_ownership_are_immutable(self):
        inputs = deepcopy(self.rows)
        state = publication.replay(inputs)
        inputs[0]['initial']['files'].clear()
        state.snapshot()['commands'].clear()
        self.assertEqual(state, self.state())
        self.assertTrue(all(type(raw) is bytes for raw in state.events))
        with self.assertRaises(FrozenInstanceError):
            state.events = ()
        self.assert_reject('PUBLICATION_CANONICAL_HISTORY_REQUIRED', publication.PublicationState, tuple(self.rows))

    def test_direct_construction_revalidates_history(self):
        raw = list(self.state().events)
        value = deepcopy(self.rows[5])
        value['observation']['files'][publication.SCRIPT_PATH]['sha256'] = digest('tampered')
        raw[5] = canonical_bytes(value)
        self.assert_reject('PUBLICATION_OBSERVATION_MISMATCH', publication.PublicationState, tuple(raw))

    def test_script_replacement_binds_new_text_digest_without_text_or_execution(self):
        rows = history('script_text.replace')
        result = publication.lookup(publication.replay(rows), 'cmd.save.1')['receipt']
        self.assertEqual(result['files'][publication.SCRIPT_PATH], rows[1]['script_input'])
        self.assertNotEqual(result['before_project_revision'], result['after_project_revision'])
        self.assertEqual(set(rows[1]['script_input']), {'sha256', 'size_bytes'})
        changed = deepcopy(rows[2])
        changed['candidate']['files'][publication.SCRIPT_PATH]['sha256'] = digest('other')
        self.assert_reject('PUBLICATION_PROJECT_REVISION_MISMATCH', publication.reduce_event, publication.replay(rows[:2]), changed)

    def test_project_revision_matches_bundle_codec_metadata(self):
        spec = importlib.util.spec_from_file_location('gt03_state_test_bundle', STUDIO / 'godot-addon/bundle.py')
        codec = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = codec
        spec.loader.exec_module(codec)
        bundle = codec.create_bundle(b'scene', b'script', scene_revision=revision('semantic'), engine_sha256=digest('engine'))
        files = {path: {'sha256': hashlib.sha256(data).hexdigest(), 'size_bytes': len(data)} for path, data in bundle.files.items()}
        self.assertEqual(publication.project_revision(files, bundle.scene_revision, bundle.engine_sha256), bundle.project_revision)

    def test_all_early_stop_cuts_terminally_cancel_and_keep_last_good(self):
        for count in (1, 2, 3, 4):
            with self.subTest(count=count):
                state = self.state(count)
                stopped = publication.reduce_event(state, event(state, 'STOP', reason='USER_STOP'))
                snapshot = stopped.snapshot()
                self.assertTrue(snapshot['stopped'])
                self.assertFalse(snapshot['held'])
                self.assertIsNone(snapshot['pending_command_id'])
                self.assertEqual(snapshot['last_good'], self.rows[0]['initial'])
                self.assertEqual(publication.replay(stopped.events), stopped)
                if count > 1:
                    receipt = publication.lookup(stopped, 'cmd.save.1')['receipt']
                    self.assertEqual(receipt['status'], 'FAILED')
                    self.assertEqual(receipt['reason'], 'STOPPED_BEFORE_ACTIVATION')
                self.assert_reject('PUBLICATION_STOPPED', publication.reduce_event, stopped, prepared(stopped, 'cmd.next'))

    def test_stop_after_possible_effect_holds_without_auto_resume(self):
        for count in (5, 6):
            with self.subTest(count=count):
                state = self.state(count)
                stopped = publication.reduce_event(state, event(state, 'STOP', reason='USER_STOP'))
                result = publication.lookup(stopped, 'cmd.save.1')
                self.assertEqual(result['phase'], 'UNKNOWN')
                self.assertTrue(result['held'])
                self.assertIsNone(result['receipt'])
                self.assertEqual(stopped.snapshot()['pending_command_id'], 'cmd.save.1')
                self.assertEqual(publication.replay(stopped.events), stopped)
                continued = deepcopy(self.rows[count])
                continued['sequence'] = stopped.event_count + 1
                continued['observed_ms'] += 10
                self.assert_reject('PUBLICATION_RECOVERY_REQUIRED', publication.reduce_event, stopped, continued)

    def test_stop_after_committed_preserves_historical_receipt(self):
        state = self.state()
        prior = publication.lookup(state, 'cmd.save.1')
        stopped = publication.reduce_event(state, event(state, 'STOP', reason='USER_STOP'))
        self.assertEqual(publication.lookup(stopped, 'cmd.save.1'), prior)
        self.assert_reject('PUBLICATION_ALREADY_STOPPED', publication.reduce_event, stopped, event(stopped, 'STOP', reason='USER_STOP'))

    def test_unknown_phase_cuts_are_held_and_do_not_allow_new_work(self):
        reasons = {2: 'STAGING_UNCERTAIN', 3: 'VALIDATION_UNCERTAIN', 4: 'ACTIVATION_UNCERTAIN',
                   5: 'READBACK_UNCERTAIN', 6: 'TERMINAL_UNCERTAIN'}
        for count, reason in reasons.items():
            with self.subTest(count=count):
                state = self.state(count)
                unknown = publication.reduce_event(state, event(state, 'UNKNOWN', command_id='cmd.save.1',
                    digest=revision('cmd.save.1'), reason=reason))
                self.assertTrue(unknown.snapshot()['held'])
                self.assertEqual(publication.replay(unknown.events), unknown)
                self.assert_reject('PUBLICATION_PENDING_OR_HELD', publication.reduce_event, unknown, prepared(unknown, 'cmd.next'))
                stopped = publication.reduce_event(unknown, event(unknown, 'STOP', reason='OWNER_SHUTDOWN'))
                self.assertTrue(stopped.snapshot()['held'])
                self.assertEqual(publication.lookup(stopped, 'cmd.save.1')['reason'], reason)

    def test_known_pre_activation_failure_can_admit_distinct_new_command(self):
        for count in (2, 3, 4):
            state = self.state(count)
            failed = publication.reduce_event(state, event(state, 'FAILED', command_id='cmd.save.1', digest=revision('cmd.save.1'),
                reason='VALIDATION_FAILED', publication_not_started=True, staging_may_exist=True))
            self.assertEqual(publication.lookup(failed, 'cmd.save.1')['phase'], 'FAILED')
            following = publication.reduce_event(failed, prepared(failed, 'cmd.next'))
            self.assertEqual(following.snapshot()['pending_command_id'], 'cmd.next')

    def test_false_no_effect_after_activation_is_rejected(self):
        state = self.state(5)
        failed = event(state, 'FAILED', command_id='cmd.save.1', digest=revision('cmd.save.1'),
                       reason='CANCELED', publication_not_started=True, staging_may_exist=True)
        self.assert_reject('PUBLICATION_EFFECT_MAY_HAVE_STARTED', publication.reduce_event, state, failed)
        self.assertEqual(state.snapshot()['commands'][-1]['phase'], 'ACTIVATING')

    def test_mismatched_readback_never_reaches_committed(self):
        state = self.state(5)
        for field, replacement in (('engine_sha256', digest('other-engine')), ('project_revision', revision('other-project')),
                                   ('scene_revision', revision('other-scene')), ('source_closure_sha256', digest('other-source')),
                                   ('manifest_sha256', digest('other-manifest'))):
            value = deepcopy(self.rows[5])
            value['observation'][field] = replacement
            with self.subTest(field=field):
                self.assert_reject('PUBLICATION_OBSERVATION_MISMATCH', publication.reduce_event, state, value)
        self.assertIsNone(publication.lookup(state, 'cmd.save.1')['receipt'])
        jumped = deepcopy(self.rows[6]); jumped['sequence'] = 6
        self.assert_reject('PUBLICATION_PHASE_ORDER', publication.reduce_event, state, jumped)

    def test_parser_or_process_failure_flags_cannot_validate(self):
        for key, bad in (('parse_status', 'FAIL'), ('import_status', 'NOT_RUN'), ('exit_code', 1),
                         ('exit_code', False), ('tree_drained', False), ('logs_clean', False)):
            value = deepcopy(self.rows[3]); value['observation'][key] = bad
            with self.subTest(field=key, value=bad):
                self.assert_reject('PUBLICATION_VERIFICATION_NOT_PASS', publication.reduce_event, self.state(3), value)

    def test_reopen_cannot_reuse_validation_session_or_observation(self):
        for field in ('editor_session_id', 'observation_id'):
            value = deepcopy(self.rows[5])
            value['observation'][field] = self.rows[3]['observation'][field]
            self.assert_reject('PUBLICATION_FRESH_READBACK_REQUIRED', publication.reduce_event, self.state(5), value)

    def test_stale_live_scene_project_files_and_authority_at_activation_reject(self):
        for key, bad, code in (('scene_revision', revision('manual-edit'), 'PUBLICATION_STALE_BASE'),
                               ('project_revision', revision('script-only-change'), 'PUBLICATION_STALE_BASE'),
                               ('lease_id', 'lease.late', 'PUBLICATION_STALE_AUTHORITY'),
                               ('fencing_epoch', 2, 'PUBLICATION_STALE_AUTHORITY'),
                               ('editor_generation', 2, 'PUBLICATION_STALE_AUTHORITY'),
                               ('editor_session_id', 'editor.restarted', 'PUBLICATION_STALE_AUTHORITY')):
            value = deepcopy(self.rows[4]); value['current'][key] = bad
            self.assert_reject(code, publication.reduce_event, self.state(4), value)
        value = deepcopy(self.rows[4]); value['current']['files'][publication.SCRIPT_PATH]['sha256'] = digest('owner-script')
        self.assert_reject('PUBLICATION_STALE_BASE', publication.reduce_event, self.state(4), value)
        value = deepcopy(self.rows[4]); value['observed_ms'] = self.rows[1]['admission']['deadline_ms']
        self.assert_reject('PUBLICATION_DEADLINE_EXPIRED', publication.reduce_event, self.state(4), value)

    def test_expired_deadline_after_effect_does_not_rewrite_admission_or_imply_retry(self):
        value = deepcopy(self.rows[6]); value['observed_ms'] = 20000
        state = publication.reduce_event(self.state(6), value)
        receipt = publication.lookup(state, 'cmd.save.1')['receipt']
        self.assertEqual(receipt['admission'], self.rows[1]['admission'])
        self.assertFalse(publication.lookup(state, 'cmd.save.1')['execution_permitted'])

    def test_one_pending_and_stale_before_pair_are_rejected(self):
        self.assert_reject('PUBLICATION_PENDING_OR_HELD', publication.reduce_event, self.state(2), prepared(self.state(2), 'cmd.second'))
        state = self.state()
        value = prepared(state, 'cmd.second'); value['before_project_revision'] = self.rows[0]['initial']['project_revision']
        self.assert_reject('PUBLICATION_STALE_BASE', publication.reduce_event, state, value)

    def test_lease_fence_rollback_and_same_epoch_rebinding_reject(self):
        state = self.state()
        value = prepared(state, 'cmd.second')
        value['admission']['fencing_epoch'] = 0
        self.assert_reject('PUBLICATION_INVALID_INTEGER', publication.reduce_event, state, value)
        for key, bad in (('lease_id', 'lease.other'), ('lease_expires_ms', 10001)):
            value = prepared(state, 'cmd.second'); value['admission'][key] = bad
            self.assert_reject('PUBLICATION_STALE_FENCE', publication.reduce_event, state, value)
        value = prepared(state, 'cmd.second'); value['admission'].update(lease_id='lease.new', fencing_epoch=2)
        self.assertEqual(publication.reduce_event(state, value).snapshot()['highest_fencing_epoch'], 2)

    def test_wrong_engine_store_alias_and_content_revision_fail_closed(self):
        changes = (
            ('PUBLICATION_ENGINE_MISMATCH', lambda c: c.update(engine_sha256=digest('wrong'))),
            ('PUBLICATION_PROJECT_REVISION_MISMATCH', lambda c: c.update(project_revision=revision('wrong'))),
            ('PUBLICATION_STORE_MISMATCH', lambda c: c['manifest'].update(volume='13')),
            ('PUBLICATION_BLOB_ALIAS', lambda c: c['manifest'].update(object_id=c['files'][publication.SCENE_PATH]['object_id'])),
            ('PUBLICATION_BLOB_ALIAS', lambda c: c['manifest'].update(file_id=c['files'][publication.SCENE_PATH]['file_id'])),
        )
        for code, change in changes:
            value = deepcopy(self.rows[2]); change(value['candidate'])
            self.assert_reject(code, publication.reduce_event, self.state(2), value)

    def test_two_file_allowlist_and_byte_bounds(self):
        for path in ('../outside.gd', 'scenes/other.tscn', 'res://scenes/fixture.tscn'):
            value = deepcopy(self.rows[2]); value['candidate']['files'][path] = value['candidate']['files'].pop(publication.SCENE_PATH)
            self.assert_reject('PUBLICATION_INVALID_SHAPE', publication.reduce_event, self.state(2), value)
        for path, limit in ((publication.SCENE_PATH, 1024 * 1024), (publication.SCRIPT_PATH, 16384)):
            value = deepcopy(self.rows[2]); value['candidate']['files'][path]['size_bytes'] = limit + 1
            self.assert_reject('PUBLICATION_INVALID_INTEGER', publication.reduce_event, self.state(2), value)

    def test_exact_fields_reject_script_bytes_and_schema_typos(self):
        value = deepcopy(self.rows[1]); value['script_bytes'] = 'not an allowed field'
        self.assert_reject('PUBLICATION_INVALID_SHAPE', publication.reduce_event, self.state(1), value)
        value = deepcopy(self.rows[0]); value['schema'] = 'another-version'
        self.assert_reject('PUBLICATION_SCHEMA_MISMATCH', publication.replay, [value])
        value = deepcopy(self.rows[4]); value['current']['unrecognized'] = True
        self.assert_reject('PUBLICATION_INVALID_SHAPE', publication.reduce_event, self.state(4), value)

    def test_all_numeric_booleans_reject_even_when_equal_to_one(self):
        for count, path in ((0, ('sequence',)), (1, ('admission', 'fencing_epoch')), (1, ('admission', 'editor_generation')),
                            (4, ('current', 'fencing_epoch')), (4, ('selection', 'generation')),
                            (5, ('selection', 'generation')), (6, ('selection', 'generation'))):
            value = deepcopy(self.rows[count])
            target = value
            for key in path[:-1]: target = target[key]
            target[path[-1]] = True
            self.assert_reject('PUBLICATION_INVALID_INTEGER', publication.reduce_event, None if count == 0 else self.state(count), value)

    def test_tampered_selection_and_commit_readback_hash_reject(self):
        for count in (4, 5, 6):
            value = deepcopy(self.rows[count]); value['selection']['identity'] = revision('tampered-selection')
            expected = 'PUBLICATION_COMMIT_MISMATCH' if count == 6 else 'PUBLICATION_SELECTION_MISMATCH'
            self.assert_reject(expected, publication.reduce_event, self.state(count), value)
        value = deepcopy(self.rows[6]); value['readback_event_sha256'] = digest('forged')
        self.assert_reject('PUBLICATION_COMMIT_MISMATCH', publication.reduce_event, self.state(6), value)

    def test_reordered_missing_duplicated_events_and_wrong_project_reject(self):
        value = deepcopy(self.rows[2]); value['sequence'] = 2
        self.assert_reject('PUBLICATION_COMMAND_NOT_PENDING', publication.reduce_event, self.state(1), value)
        self.assert_reject('PUBLICATION_EVENT_SEQUENCE', publication.replay, self.rows[:2] + self.rows[3:])
        self.assert_reject('PUBLICATION_EVENT_SEQUENCE', publication.replay, self.rows[:2] + [self.rows[1]])
        value = deepcopy(self.rows[2]); value['project_id'] = 'different-project'
        self.assert_reject('PUBLICATION_PROJECT_MISMATCH', publication.reduce_event, self.state(2), value)
        value = deepcopy(self.rows[2]); value['observed_ms'] = 1
        self.assert_reject('PUBLICATION_CLOCK_REGRESSION', publication.reduce_event, self.state(2), value)

    def test_noncanonical_duplicate_json_fields_and_oversized_events_reject(self):
        self.assert_reject('PUBLICATION_NONCANONICAL_EVENT', publication.replay, [json.dumps(self.rows[0]).encode()])
        raw = canonical_bytes(self.rows[0])
        with self.assertRaises(ValidationError):
            publication.replay([raw[:-1] + b',"kind":"CONFIG"}'])
        self.assert_reject('PUBLICATION_EVENT_LIMIT', publication.replay, [b' ' * (publication.MAX_EVENT_BYTES + 1)])
        self.assert_reject('PUBLICATION_EVENT_REQUIRED', publication.replay, [bytearray(raw)])

    def test_same_content_new_command_has_new_selection_identity(self):
        state = self.state()
        new = prepared(state, 'cmd.second')
        state = publication.reduce_event(state, new)
        value = next_event(state)
        # Identical serialized content is allowed; generation still advances.
        value['candidate'] = deepcopy(self.rows[2]['candidate'])
        value['candidate']['candidate_id'] = new['candidate_id']
        state = publication.reduce_event(state, value)
        for _ in range(4): state = publication.reduce_event(state, next_event(state))
        first = publication.lookup(state, 'cmd.save.1')['receipt']
        second = publication.lookup(state, 'cmd.second')['receipt']
        self.assertEqual(first['after_project_revision'], second['after_project_revision'])
        self.assertEqual(second['selection']['generation'], first['selection']['generation'] + 1)
        self.assertNotEqual(first['selection']['identity'], second['selection']['identity'])

    def test_bounded_command_retention_does_not_make_old_id_new(self):
        state = self.state(1)
        for index in range(publication.MAX_COMMANDS):
            identifier = 'cmd.fail.' + str(index)
            state = publication.reduce_event(state, prepared(state, identifier))
            state = publication.reduce_event(state, event(state, 'FAILED', command_id=identifier, digest=revision(identifier),
                reason='CANCELED', publication_not_started=True, staging_may_exist=False))
        self.assert_reject('PUBLICATION_COMMAND_LIMIT', publication.reduce_event, state, prepared(state, 'cmd.overflow'))
        self.assertEqual(publication.lookup(state, 'cmd.fail.0')['phase'], 'FAILED')
        self.assert_reject('PUBLICATION_DUPLICATE_EVENT', publication.reduce_event, state, prepared(state, 'cmd.fail.0'))

    def test_event_capacity_preserves_room_for_completion_and_stop(self):
        state = self.state(1)
        for index in range(42):
            state = publication.reduce_event(state, prepared(state, 'cmd.save.' + str(index)))
            for _ in range(5): state = publication.reduce_event(state, next_event(state))
        self.assertEqual(state.event_count, 253)
        self.assert_reject('PUBLICATION_EVENT_CAPACITY', publication.reduce_event, state, prepared(state, 'cmd.overflow'))
        stopped = publication.reduce_event(state, event(state, 'STOP', reason='USER_STOP'))
        self.assertTrue(stopped.snapshot()['stopped'])

    def test_pure_replay_performs_no_filesystem_or_process_operation(self):
        with mock.patch('builtins.open', side_effect=AssertionError('unexpected I/O')), \
             mock.patch('subprocess.Popen', side_effect=AssertionError('unexpected process')):
            state = publication.replay(self.rows)
            self.assertEqual(publication.lookup(state, 'cmd.save.1')['phase'], 'COMMITTED')


if __name__ == '__main__':
    unittest.main()
