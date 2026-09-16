"""Pure issuer/shape tests; actual editor integration is a separate probe."""
from dataclasses import replace
import importlib.util
import copy
from pathlib import Path
import sys
import threading
import time
import unittest
import types
from unittest.mock import Mock, patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
spec = importlib.util.spec_from_file_location('s52_editor_owner_test', STUDIO / 'godot-addon/editor_owner.py')
owner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = owner
spec.loader.exec_module(owner)


def inert():
    result = owner.EditorOwner.__new__(owner.EditorOwner)
    result._mutex = threading.RLock()
    result._healthy = Mock()
    result._stopped = False
    result._held = False
    result._pending = None
    result._intents = {}
    result._records = {}
    return result


class EditorOwnerPureTests(unittest.TestCase):
    def test_intent_scratch_is_fixed_generated_name(self):
        intent = owner.EditorEffectIntent('1' * 32, 'save', 'sha256:' + '2' * 64, 'capture', 1, 'sha256:' + '3' * 64, 1000)
        self.assertEqual(intent.scratch_name, 'capture-' + '1' * 32 + '.tscn')

    def test_copied_receipt_cannot_be_registered(self):
        instance = inert()
        receipt = owner.EditorCaptureReceipt('save', 'sha256:' + '2' * 64, 'capture-' + '1' * 32,
            'editor-' + '3' * 32, '4' * 64, 'sha256:' + '5' * 64)
        instance._records[receipt.observation_id] = (receipt, (), b'', None, None, None)
        with self.assertRaisesRegex(owner.EditorOwnerError, 'REGISTERED_RECEIPT'):
            instance._receipt(replace(receipt))

    def test_unregistered_receipt_rejected(self):
        instance = inert()
        with self.assertRaisesRegex(owner.EditorOwnerError, 'RECEIPT_TYPE'):
            instance._receipt({'public_ack': False, 'kind': 'capture'})

    def test_copied_intent_rejected_before_effect(self):
        instance = inert()
        intent = owner.EditorEffectIntent('1' * 32, 'save', 'sha256:' + '2' * 64, 'capture', 1, 'sha256:' + '3' * 64, int(time.time() * 1000) + 1000)
        instance._pending = intent
        with self.assertRaisesRegex(owner.EditorOwnerError, 'REGISTERED_INTENT'):
            instance.capture(replace(intent))
        self.assertFalse(instance._held)

    def test_expired_intent_rejected_before_send(self):
        instance = inert()
        intent = owner.EditorEffectIntent('1' * 32, 'save', 'sha256:' + '2' * 64, 'capture', 1, 'sha256:' + '3' * 64, 1)
        instance._pending = intent
        instance._intents[intent.intent_id] = (intent, owner.canonical_bytes({name: getattr(intent, name) for name in intent.__slots__}), {})
        with self.assertRaisesRegex(owner.EditorOwnerError, 'DEADLINE_OR_STOPPED'):
            instance.capture(intent)

    def test_semantic_hash_and_complete_count(self):
        state = {'nodes': [{'stable_id': 'root'}]}
        value = {'ok': True, 'scene_path': 'res://scenes/fixture.tscn', 'generation': 1,
                 'offset': 0, 'total': 1, 'state': state, 'revision': 'sha256:' + owner._sha(owner.canonical_bytes(state))}
        self.assertEqual(owner._semantic(value), owner.canonical_bytes(state))
        for patch in ({'generation': True}, {'total': 2}, {'revision': 'sha256:' + '0' * 64}, {'offset': 1}):
            with self.subTest(patch=patch), self.assertRaises(owner.EditorOwnerError):
                owner._semantic({**value, **patch})

    def test_bad_admission_has_no_ipc(self):
        instance = inert()
        instance._exchange = Mock()
        with self.assertRaises(owner.EditorOwnerError):
            instance.prepare_effect('../save', 'sha256:' + '2' * 64, 'capture', expected_generation=1,
                expected_revision='sha256:' + '3' * 64, deadline_ms=int(time.time() * 1000) + 1000)
        instance._exchange.assert_not_called()

    def test_adoption_same_semantics_still_requires_registered_root_generation_and_files(self):
        instance = inert()
        receipt = owner.EditorAdoptionReceipt('save', 'sha256:' + '2' * 64, 'adoption-' + '1' * 32,
            'editor-' + '3' * 32, 'sha256:' + '4' * 64, 'sha256:' + '5' * 64)
        bundle = object()
        facts = {'generation_after': 2, 'root_after': '1234', 'working_files': {'scene': {'sha256': '6' * 64}}}
        instance._receipt = Mock(return_value=(receipt, None, owner.canonical_bytes(facts), None, None, bundle))
        actual = {'revision': receipt.semantic_revision, 'generation': 2, 'root_instance_id': '1234',
                  'working_files': facts['working_files']}
        instance.inspect = Mock(return_value=actual)
        self.assertEqual(instance.observation(receipt, bundle), facts)
        for patch in ({'generation': 3}, {'root_instance_id': '1235'}, {'working_files': {}}):
            instance.inspect.return_value = {**actual, **patch}
            with self.subTest(patch=patch), self.assertRaisesRegex(owner.EditorOwnerError, 'NO_LONGER_CURRENT'):
                instance.observation(receipt, bundle)

    def test_interrupt_after_capture_send_retains_unknown_owner(self):
        instance = inert()
        intent = owner.EditorEffectIntent('1' * 32, 'save', 'sha256:' + '2' * 64, 'capture', 1,
            'sha256:' + '3' * 64, int(time.time() * 1000) + 1000)
        instance._intent = Mock()
        instance._exchange = Mock(side_effect=KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt) as caught:
            instance.capture(intent)
        self.assertIs(caught.exception.cleanup_owner, instance)
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertTrue(instance._held)
        self.assertIsNone(instance._pending)

    def test_generation_seed_rejected_before_any_native_resource(self):
        for value in (True,0,-1,1.5,2147483648,'2'):
            with self.subTest(value=value),self.assertRaisesRegex(owner.EditorOwnerError,'GENERATION_SEED'):
                owner.EditorOwner(None,None,editor_binary=None,initial_generation=value)

    def test_retirement_generation_overflow_has_no_ipc_or_close(self):
        instance=inert();instance._exchange=Mock();instance.close=Mock()
        with self.assertRaisesRegex(owner.EditorOwnerError,'GENERATION_OVERFLOW'):
            instance.retire_for_replacement('replace.one','sha256:'+'1'*64,
                retirement_intent_id='retire.one',expected_snapshot={'generation':2147483647},
                deadline_ms=int(time.time()*1000)+1000)
        instance._exchange.assert_not_called();instance.close.assert_not_called()

    def test_native_close_proof_requires_exact_exit_and_checked_job(self):
        cleanup={'closed':True,'held':False,'logs_overflow':False,
            'actual_process_exit':{'pid':123,'exit_code':0},'wrapper_exit_code':0,
            'job':{'configured':True,'assigned':True,'closed':True,'zero_observed':True,
                'tainted':False,'handle_retained':False,'close_uncertain':False,'create_uncertain':False,
                'active_count':0,'failed_operations':[],'native_error':None}}
        owner.EditorOwner._clean_closed(cleanup,123)
        for patch in ({'actual_process_exit':{'pid':123,'exit_code':False}},
                      {'wrapper_exit_code':False},{'actual_process_exit':None},
                      {'job':{**cleanup['job'],'active_count':False}},
                      {'job':{**cleanup['job'],'zero_observed':False}},
                      {'job':{**cleanup['job'],'tainted':True}}):
            with self.subTest(patch=patch),self.assertRaises(owner.EditorOwnerError):
                owner.EditorOwner._clean_closed({**cleanup,**patch},123)

    def test_copied_retirement_is_not_authority_to_start_successor(self):
        instance=inert();instance._closed=True
        receipt=owner.EditorRetirementReceipt('replace.one','sha256:'+'1'*64,'retired-one','editor-one',2)
        instance._records[receipt.observation_id]=(receipt,tuple(getattr(receipt,k) for k in receipt.__slots__),
            b'{}',None,None,None)
        with self.assertRaisesRegex(owner.EditorOwnerError,'REGISTERED_RETIREMENT'):
            instance.retirement_observation(replace(receipt))

    def test_live_previous_owner_cannot_prove_retirement(self):
        instance=inert();instance._closed=False
        receipt=owner.EditorRetirementReceipt('replace.one','sha256:'+'1'*64,'retired-one','editor-one',2)
        with self.assertRaisesRegex(owner.EditorOwnerError,'REGISTERED_RETIREMENT'):
            instance.retirement_observation(receipt)


def retired_owner():
    old = object.__new__(owner.EditorOwner)
    old._mutex = threading.RLock()
    old._successor_reserved = False
    receipt = object()
    facts = {'next_generation': 2}

    def observed(candidate):
        owner._need(candidate is receipt, 'EDITOR_REGISTERED_RETIREMENT_REQUIRED')
        return facts

    old.retirement_observation = Mock(side_effect=observed)
    return old, receipt, facts


class EditorSuccessorGuardTests(unittest.TestCase):
    def test_exact_receipt_reservation_is_single_use(self):
        old, receipt, facts = retired_owner()
        self.assertIs(old._reserve_successor(receipt), facts)
        with self.assertRaisesRegex(owner.EditorOwnerError, 'SUCCESSOR_ALREADY_ATTEMPTED'):
            old._reserve_successor(receipt)

    def test_foreign_receipt_does_not_consume_reservation(self):
        old, receipt, facts = retired_owner()
        with self.assertRaisesRegex(owner.EditorOwnerError, 'REGISTERED_RETIREMENT'):
            old._reserve_successor(object())
        self.assertFalse(old._successor_reserved)
        self.assertIs(old._reserve_successor(receipt), facts)

    def test_concurrent_reservation_has_exactly_one_winner(self):
        old, receipt, _ = retired_owner()
        ready = threading.Barrier(3)
        results = []

        def attempt():
            ready.wait(timeout=2)
            try:
                old._reserve_successor(receipt)
                results.append('reserved')
            except owner.EditorOwnerError as error:
                results.append(error.code)

        threads = [threading.Thread(target=attempt, daemon=True) for _ in range(2)]
        for thread in threads:
            thread.start()
        ready.wait(timeout=2)
        for thread in threads:
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
        self.assertCountEqual(results, ['reserved', 'EDITOR_SUCCESSOR_ALREADY_ATTEMPTED'])

    def test_native_launch_attempt_failure_cannot_implicitly_retry(self):
        old, receipt, _ = retired_owner()
        semantic = owner.canonical_bytes({'nodes': []})
        bundle = owner.factory.compose(owner.factory.DEFAULT_SCENE, owner.factory.DEFAULT_SCRIPT,
            scene_revision='sha256:' + owner._sha(semantic), engine_sha256='a' * 64)
        old._files = dict(bundle.files)
        selection = {'generation': 1, 'identity': 'sha256:' + 'b' * 64}
        with patch.object(owner.EditorOwner, '__init__', side_effect=owner.EditorOwnerError('TEST_LAUNCH_FAILED')) as init:
            with self.assertRaisesRegex(owner.EditorOwnerError, 'TEST_LAUNCH_FAILED'):
                owner.EditorOwner.open_selected_generation(old, receipt, None, bundle,
                    editor_binary=None, selection=selection, semantic_bytes=semantic)
            with self.assertRaisesRegex(owner.EditorOwnerError, 'SUCCESSOR_ALREADY_ATTEMPTED'):
                owner.EditorOwner.open_selected_generation(old, receipt, None, bundle,
                    editor_binary=None, selection=selection, semantic_bytes=semantic)
            self.assertEqual(init.call_count, 1)

    def test_invalid_preflight_does_not_consume_reservation_or_launch(self):
        old, receipt, _ = retired_owner()
        with patch.object(owner.EditorOwner, '__init__') as init:
            with self.assertRaisesRegex(owner.EditorOwnerError, 'BUNDLE_TYPE'):
                owner.EditorOwner.open_selected_generation(old, receipt, None, object(),
                    editor_binary=None, selection={}, semantic_bytes=b'{}')
            init.assert_not_called()
            self.assertFalse(old._successor_reserved)



def fixture():
    actor = object.__new__(owner.EditorOwner)
    actor._mutex = threading.RLock()
    actor._healthy = Mock()
    actor._pending = None
    actor._stopped = actor._held = False
    actor._intents, actor._records = {}, {}
    actor._edit_commands = set()
    actor._session, actor._pid, actor._creation = 'editor-one', 100, '1234'
    actor._root_identity = types.SimpleNamespace(volume=1, file_id='1' * 32)
    actor._source = {'draft': '1' * 64}
    state = {'nodes': [{'stable_id': 'root', 'position': [0, 0, 0]}]}
    revision = 'sha256:' + owner._sha(owner.canonical_bytes(state))
    before = {'ok': True, 'scene_path': 'res://scenes/fixture.tscn', 'offset': 0, 'total': 1,
        'revision': revision, 'generation': 1, 'root_instance_id': '123',
        'working_files': {'scene': {'sha256': '2' * 64, 'size_bytes': 20}}, 'state': state,
        'history_id': 5, 'can_undo': False, 'can_redo': False}
    checkpoint = owner.EditorCaptureReceipt('edit.one', 'sha256:' + '3' * 64,
        'capture-one', actor._session, '4' * 64, revision)
    captured = {'semantic_revision': revision, 'generation_after': 1, 'root_after': '123',
        'working_files': before['working_files'], 'semantic_state': state}
    actor._receipt = Mock(return_value=(checkpoint, None, owner.canonical_bytes(captured)))
    actor.capture_bytes = Mock(return_value=b'checkpoint')
    actor.inspect = Mock(return_value=copy.deepcopy(before))
    actor._verify_snapshot = Mock(side_effect=lambda value: owner.canonical_bytes(value['state']))
    actor._exchange = Mock(return_value={'before': copy.deepcopy(before)})
    projection = {'operation': 'scene.node.update', 'command_id': 'edit.one',
        'expected_generation': 1, 'expected_revision': revision, 'target_stable_id': 'root',
        'payload': {'expected_generation': 1, 'changes': {'position': [1, 2, 3]}}}
    return actor, checkpoint, projection, before


def prepare(actor, checkpoint, projection):
    return actor.prepare_edit(checkpoint.command_id, checkpoint.request_digest,
        projection, checkpoint, deadline_ms=int(time.time() * 1000) + 10000)


class EditorEditPureTests(unittest.TestCase):
    def test_checkpoint_digest_mismatch_rejected_before_ipc(self):
        actor, checkpoint, projection, _ = fixture()
        with self.assertRaisesRegex(owner.EditorOwnerError, 'CHECKPOINT_COMMAND'):
            actor.prepare_edit(checkpoint.command_id, 'sha256:' + '5' * 64, projection,
                checkpoint, deadline_ms=int(time.time() * 1000) + 1000)
        actor._exchange.assert_not_called()

    def test_projection_mismatch_rejected_before_ipc(self):
        for change in ({'command_id': 'different'}, {'expected_generation': True},
                       {'expected_revision': 'sha256:' + '0' * 64}, {'operation': 'script_text.replace'},
                       {'payload': {'expected_generation': True, 'changes': {'position': [1, 2, 3]}}}):
            actor, checkpoint, projection, _ = fixture()
            with self.subTest(change=change), self.assertRaisesRegex(owner.EditorOwnerError, 'PROJECTION_BINDING'):
                prepare(actor, checkpoint, {**projection, **change})
            actor._exchange.assert_not_called()

    def test_stale_scene_or_root_or_working_files_rejected(self):
        for change in ({'revision': 'sha256:' + '0' * 64}, {'generation': 2},
                       {'root_instance_id': '124'}, {'working_files': {}}, {'state': {'nodes': []}}):
            actor, checkpoint, projection, before = fixture()
            actor.inspect.return_value = {**before, **change}
            with self.subTest(change=change), self.assertRaisesRegex(owner.EditorOwnerError, 'CHECKPOINT_STALE'):
                prepare(actor, checkpoint, projection)
            actor._exchange.assert_not_called()

    def test_preparation_copies_projection_bytes(self):
        actor, checkpoint, projection, _ = fixture()
        intent = prepare(actor, checkpoint, projection)
        original = copy.deepcopy(projection)
        projection['payload']['changes']['position'][0] = 999
        body = actor._exchange.call_args.args[1]
        self.assertEqual(body['projection'], original)
        self.assertEqual(actor._intents[intent.intent_id][3], owner.canonical_bytes(original))

    def test_copied_or_mutated_intent_is_not_authority(self):
        for mutation in ('copy', 'field'):
            actor, checkpoint, projection, _ = fixture()
            intent = prepare(actor, checkpoint, projection)
            actor._exchange.reset_mock()
            if mutation == 'copy':
                invalid = replace(intent)
            else:
                invalid = intent
                object.__setattr__(invalid, 'projection_sha256', '0' * 64)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(owner.EditorOwnerError, 'INTENT'):
                actor.apply_edit(invalid)
            actor._exchange.assert_not_called()

    def test_changed_registered_projection_rejected(self):
        actor, checkpoint, projection, _ = fixture()
        intent = prepare(actor, checkpoint, projection)
        record = actor._intents[intent.intent_id]
        actor._intents[intent.intent_id] = (*record[:3], b'{}', record[4])
        actor._exchange.reset_mock()
        with self.assertRaisesRegex(owner.EditorOwnerError, 'EDIT_INTENT_CHANGED'):
            actor.apply_edit(intent)
        actor._exchange.assert_not_called()

    def test_expired_or_stopped_edit_has_no_send(self):
        for cause in ('deadline', 'stop'):
            actor, checkpoint, projection, _ = fixture()
            intent = prepare(actor, checkpoint, projection)
            if cause == 'deadline':
                object.__setattr__(intent, 'deadline_ms', 1)
                row = actor._intents[intent.intent_id]
                actor._intents[intent.intent_id] = (intent,
                    owner.canonical_bytes({name: getattr(intent, name) for name in intent.__slots__}), *row[2:])
            else:
                actor._stopped = True
            actor._exchange.reset_mock()
            with self.subTest(cause=cause), self.assertRaisesRegex(owner.EditorOwnerError, 'DEADLINE_OR_STOPPED'):
                actor.apply_edit(intent)
            actor._exchange.assert_not_called()

    def test_prepare_reply_context_failure_holds_owner_and_claim(self):
        actor, checkpoint, projection, before = fixture()
        actor._exchange.return_value = {'before': {**before, 'root_instance_id': '999'}}
        with self.assertRaisesRegex(owner.EditorOwnerError, 'PREPARE_UNKNOWN') as caught:
            prepare(actor, checkpoint, projection)
        self.assertTrue(actor._held)
        self.assertIs(caught.exception.cleanup_owner, actor)
        self.assertIn(checkpoint.command_id, actor._edit_commands)

    def test_missing_effect_reply_is_unknown_and_single_use(self):
        actor, checkpoint, projection, _ = fixture()
        intent = prepare(actor, checkpoint, projection)
        actor._exchange.side_effect = OSError('reply lost')
        with self.assertRaisesRegex(owner.EditorOwnerError, 'EDIT_UNKNOWN') as caught:
            actor.apply_edit(intent)
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertIs(caught.exception.cleanup_owner, actor)
        self.assertTrue(actor._held)
        self.assertIsNone(actor._pending)
        actor._exchange.reset_mock()
        with self.assertRaisesRegex(owner.EditorOwnerError, 'REGISTERED_INTENT'):
            actor.apply_edit(intent)
        actor._exchange.assert_not_called()

    def test_verified_transition_records_in_memory_semantics(self):
        actor, checkpoint, projection, before = fixture()
        intent = prepare(actor, checkpoint, projection)
        state = copy.deepcopy(before['state'])
        state['nodes'][0]['position'] = [1, 2, 3]
        revision = 'sha256:' + owner._sha(owner.canonical_bytes(state))
        after = {**before, 'revision': revision, 'state': state, 'can_undo': True}
        actor._exchange.return_value = {'before': before, 'after': after,
            'effect_started_ms': int(time.time() * 1000), 'effect_completed_ms': int(time.time() * 1000),
            'edit_result': {'ok': True, 'code': 'SCENE_APPLIED_IN_MEMORY', 'command_id': intent.command_id,
                'operation': intent.operation, 'filesystem_mutated': False, 'generation': 1,
                'before_revision': before['revision'], 'revision': revision, 'state': state}}
        actor._register = Mock(side_effect=lambda receipt, facts: receipt)
        receipt = actor.apply_edit(intent)
        facts = actor._register.call_args.args[1]
        self.assertIs(type(receipt), owner.EditorEditReceipt)
        self.assertFalse(receipt.public_ack)
        self.assertEqual(facts['checkpoint_scene_sha256'], checkpoint.scene_sha256)
        self.assertEqual(facts['semantic_revision'], revision)
        self.assertTrue(facts['can_undo'])
        self.assertFalse(facts['files_saved'])
        self.assertFalse(facts['live_state_durable'])
        self.assertFalse(facts['history_boundary'])
        self.assertEqual(facts['generation_before'], facts['generation_after'])
        with self.assertRaisesRegex(owner.EditorOwnerError, 'COMMAND_ALREADY_PREPARED'):
            prepare(actor, checkpoint, projection)



if __name__ == '__main__':
    unittest.main()
