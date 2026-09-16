"""Pure rejection and issuer bookkeeping; native validation is a separate run."""
import copy
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
spec = importlib.util.spec_from_file_location('s51_validation_owner_test', STUDIO/'godot-addon/validation_owner.py')
owner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = owner
spec.loader.exec_module(owner)
factory = owner.factory
SAVED = json.loads(Path(__file__).with_name('fixtures').joinpath('validation-run-semantic-baseline.json').read_bytes())
SCRIPT = (b'extends Node3D\n@export var fixture_value: int = 9\n'
    b'@export var move_speed: float = 2.25\n@export var turn_speed: float = 90.0\n'
    b'@export var enabled: bool = false\n')


def candidate():
    return factory.compose(factory.DEFAULT_SCENE, SCRIPT,
        scene_revision='sha256:'+hashlib.sha256(factory.DEFAULT_SCENE).hexdigest(),
        engine_sha256=owner.executor.BINARY_SHA256)


class ValidationFactTests(unittest.TestCase):
    def test_saved_native_facts_compare_but_do_not_mint_receipt(self):
        observation, comparison = owner.evaluate_run(SAVED['result'], SAVED['stdout'], SAVED['stderr'], candidate())
        self.assertIs(type(observation), dict)
        self.assertFalse(comparison['public_ack'])
        self.assertFalse(comparison['process_attribution_proven'])

    def test_wrong_pin_is_rejected(self):
        bundle = factory.compose(factory.DEFAULT_SCENE, SCRIPT,
            scene_revision='sha256:'+'1'*64, engine_sha256='2'*64)
        with self.assertRaisesRegex(owner.ValidationOwnerError, 'ENGINE_PIN'):
            owner.evaluate_run(SAVED['result'], SAVED['stdout'], SAVED['stderr'], bundle)

    def test_raw_phase_order_and_single_marker_required(self):
        raw = SAVED['stdout']
        marker = next(line for line in raw.splitlines() if line.startswith('HH_PROFILE_READBACK '))
        for bad in (raw + '\n' + marker, raw.replace('HH_PROFILE_PHASE_END parse 0','HH_PROFILE_PHASE_END parse 1'),
                    raw.replace('HH_PROFILE_PHASE_BEGIN readback','HH_PROFILE_PHASE_BEGIN import')):
            with self.subTest(raw=bad[-30:]), self.assertRaises(owner.ValidationOwnerError):
                owner.evaluate_run(SAVED['result'], bad, '', candidate())

    def test_no_clean_flag_can_hide_invalid_native_or_job_fact(self):
        changes = [('owned_removed', False), ('owner_record_retained', True),
                   ('profile_harness_sha256', '0'*64), ('errors', ['failure'])]
        for key, value in changes:
            result = copy.deepcopy(SAVED['result']); result[key] = value
            with self.subTest(key=key), self.assertRaises(owner.ValidationOwnerError):
                owner.evaluate_run(result, SAVED['stdout'], '', candidate())
        for target, key, value in (('container_state','ExitCode',False),
            ('container_state','Pid',False), ('container_state','OOMKilled',True),
            ('admission','released',False), ('admission','maximum_active',True)):
            result = copy.deepcopy(SAVED['result']); result[target][key] = value
            with self.subTest(target=target,key=key), self.assertRaises(owner.ValidationOwnerError):
                owner.evaluate_run(result, SAVED['stdout'], '', candidate())
        result = copy.deepcopy(SAVED['result'])
        result['command_host']['job_owner']['closed'] = False
        result['commandhost'] = result['command_host']
        with self.assertRaises(owner.ValidationOwnerError):
            owner.evaluate_run(result, SAVED['stdout'], '', candidate())

    def test_changed_input_map_and_logs_rejected(self):
        result = copy.deepcopy(SAVED['result'])
        result['snapshot_hashes_after']['scripts/fixture_actor.gd'] = 'f'*64
        with self.assertRaises(owner.ValidationOwnerError):
            owner.evaluate_run(result, SAVED['stdout'], '', candidate())
        with self.assertRaisesRegex(owner.ValidationOwnerError, 'LOG_ERROR'):
            owner.evaluate_run(SAVED['result'], SAVED['stdout'], 'WARNING: unclean', candidate())


class IssuerBookkeepingTests(unittest.TestCase):
    """Executor is explicitly a test double in these bookkeeping tests."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hh-validation-owner-unit-')
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.bundle = candidate()
        self.issuer = owner.ValidationOwner(self.parent)
        self.addCleanup(self.issuer.close)
        self.calls = []

    def fake_run(self, project, *, mode, output, timeout_seconds):
        self.calls.append((project, mode, output, timeout_seconds))
        self.assertEqual(mode, 'profile-validate')
        self.assertEqual({p.relative_to(project).as_posix():p.read_bytes()
                          for p in project.rglob('*') if p.is_file()}, dict(self.bundle.files))
        output.mkdir()
        result = copy.deepcopy(SAVED['result'])
        (output/'engine-stdout.txt').write_text(SAVED['stdout'], encoding='utf-8', newline='\n')
        (output/'engine-stderr.txt').write_text('', encoding='utf-8')
        (output/'result.json').write_text(json.dumps(result), encoding='utf-8')
        return result

    def mint(self, command='command.one'):
        with patch.object(owner.executor, 'run', side_effect=self.fake_run):
            return self.issuer.validate(command, self.bundle)

    def test_registered_observation_and_mutation_is_not_advertised(self):
        receipt = self.mint()
        self.assertFalse(receipt.public_ack)
        self.assertFalse(receipt.selected_state_verified)
        self.assertEqual(self.issuer.observation(receipt,self.bundle)['schema'],
                         'hh-godot-profile-readback-2')
        self.assertEqual(len(self.calls),1)

    def test_receipt_copy_foreign_issuer_and_changed_bundle_rejected(self):
        receipt = self.mint()
        with self.assertRaisesRegex(owner.ValidationOwnerError,'REGISTERED_RECEIPT'):
            self.issuer.observation(replace(receipt),self.bundle)
        other = owner.ValidationOwner(self.parent)
        self.addCleanup(other.close)
        with self.assertRaisesRegex(owner.ValidationOwnerError,'REGISTERED_RECEIPT'):
            other.observation(receipt,self.bundle)
        changed = factory.compose(factory.DEFAULT_SCENE,SCRIPT.replace(b'int = 9',b'int = 10'),
            scene_revision=self.bundle.scene_revision,engine_sha256=self.bundle.engine_sha256)
        with self.assertRaisesRegex(owner.ValidationOwnerError,'BUNDLE_MISMATCH'):
            self.issuer.observation(receipt,changed)

    def test_duplicate_never_implicitly_reruns_engine(self):
        self.mint()
        with patch.object(owner.executor,'run') as run:
            with self.assertRaisesRegex(owner.ValidationOwnerError,'ALREADY_ATTEMPTED'):
                self.issuer.validate('command.one',self.bundle)
            run.assert_not_called()

    def test_semantic_binding_preserves_inputs_original_and_one_run(self):
        receipt=self.mint();original_revision=receipt.project_revision
        final,bound=self.issuer.bind_semantics(receipt,self.bundle)
        self.assertEqual(dict(final.files),dict(self.bundle.files))
        self.assertNotEqual(final.scene_revision,self.bundle.scene_revision)
        self.assertNotEqual(final.project_revision,original_revision)
        self.assertEqual(receipt.project_revision,original_revision)
        self.assertEqual(final.scene_revision,bound.scene_revision)
        self.assertEqual(bound.context_kind,'isolated_candidate')
        self.assertFalse(bound.public_ack);self.assertFalse(bound.live_editor_adoption_verified)
        again,duplicate=self.issuer.bind_semantics(receipt,self.bundle)
        self.assertIs(again,final);self.assertIs(duplicate,bound)
        observed=self.issuer.semantic_observation(bound,final)
        self.assertEqual(observed['semantic']['revision'],final.scene_revision)
        self.assertEqual(observed['validator_engine_sha256'],owner.executor.BINARY_SHA256)
        self.assertGreater(bound.validation_started_ms,0)
        self.assertGreaterEqual(bound.validation_completed_ms,bound.validation_started_ms)
        self.assertEqual(len(self.calls),1)

    def test_semantic_binding_rejects_copies_wrong_bundle_and_foreign_issuer(self):
        receipt=self.mint();final,bound=self.issuer.bind_semantics(receipt,self.bundle)
        for wrong_receipt,wrong_bundle in ((replace(bound),final),(bound,self.bundle)):
            with self.assertRaisesRegex(owner.ValidationOwnerError,'REGISTERED_SEMANTIC'):
                self.issuer.semantic_observation(wrong_receipt,wrong_bundle)
        other=owner.ValidationOwner(self.parent);self.addCleanup(other.close)
        with self.assertRaisesRegex(owner.ValidationOwnerError,'REGISTERED_SEMANTIC'):
            other.semantic_observation(bound,final)
        with self.assertRaisesRegex(owner.ValidationOwnerError,'REGISTERED_RECEIPT'):
            self.issuer.bind_semantics(replace(receipt),self.bundle)
        self.assertEqual(len(self.calls),1)

    def test_semantic_binding_does_not_promote_legacy_property_comparison(self):
        # Synthetic legacy projection for this mocked issuer test only.
        saved=copy.deepcopy(SAVED)
        line=next(line for line in saved['stdout'].splitlines() if line.startswith('HH_PROFILE_READBACK '))
        observation=json.loads(line.removeprefix('HH_PROFILE_READBACK '))
        observation.pop('semantic');observation['schema']='hh-godot-profile-readback-1'
        saved['stdout']=saved['stdout'].replace(line,'HH_PROFILE_READBACK '+json.dumps(observation))
        with patch.dict(SAVED,saved):receipt=self.mint()
        with self.assertRaisesRegex(owner.ValidationOwnerError,'SEMANTIC_OBSERVATION_REQUIRED'):
            self.issuer.bind_semantics(receipt,self.bundle)
        self.assertEqual(len(self.calls),1)

    def test_semantic_receipt_rechecks_raw_evidence_on_every_read(self):
        receipt=self.mint();final,bound=self.issuer.bind_semantics(receipt,self.bundle)
        record=self.issuer._records[receipt.command_id]
        (record.directory/'engine-stdout.txt').write_text('changed evidence',encoding='utf-8')
        with self.assertRaisesRegex(owner.ValidationOwnerError,'EVIDENCE_CHANGED'):
            self.issuer.semantic_observation(bound,final)
        self.assertTrue(self.issuer.snapshot()['held'])
        self.assertEqual(len(self.calls),1)

    def test_registered_same_object_field_mutation_cannot_relabel_native_run(self):
        receipt=self.mint()
        for field,value in (('engine_sha256','f'*64),('source_release_sha256','f'*64),
                            ('evidence_sha256','f'*64),('run_id','invented')):
            original=getattr(receipt,field)
            try:
                object.__setattr__(receipt,field,value)
                with self.assertRaisesRegex(owner.ValidationOwnerError,'REGISTERED_RECEIPT_CHANGED'):
                    self.issuer.bind_semantics(receipt,self.bundle)
            finally:object.__setattr__(receipt,field,original)
        final,bound=self.issuer.bind_semantics(receipt,self.bundle)
        original=bound.validator_engine_sha256
        try:
            object.__setattr__(bound,'validator_engine_sha256','f'*64)
            with self.assertRaisesRegex(owner.ValidationOwnerError,'FINAL_BINDING_CHANGED'):
                self.issuer.semantic_observation(bound,final)
        finally:object.__setattr__(bound,'validator_engine_sha256',original)
        self.assertEqual(len(self.calls),1)

    def test_evidence_tampering_holds_issuer_and_prevents_revalidation(self):
        receipt = self.mint()
        directory = self.calls[0][2]
        (directory/'engine-stdout.txt').write_bytes(b'forged\n')
        with self.assertRaisesRegex(owner.ValidationOwnerError,'EVIDENCE_CHANGED'):
            self.issuer.observation(receipt,self.bundle)
        with patch.object(owner.executor,'run') as run:
            with self.assertRaisesRegex(owner.ValidationOwnerError,'OWNER_HELD'):
                self.issuer.validate('command.two',self.bundle)
            run.assert_not_called()

    def test_cancellation_is_preserved_and_owner_held(self):
        cancellation = KeyboardInterrupt('test interruption')
        with patch.object(owner.executor,'run',side_effect=cancellation):
            with self.assertRaises(KeyboardInterrupt) as caught:
                self.issuer.validate('command.one',self.bundle)
        self.assertIs(caught.exception,cancellation)
        self.assertTrue(self.issuer.snapshot()['held'])
        self.assertEqual(self.issuer.snapshot()['registered_commands'],())

    def test_engine_failure_cannot_register_a_receipt(self):
        def failure(*args,**kwargs):
            result=self.fake_run(*args,**kwargs)
            result['diagnostic_process_clean']=False
            (kwargs['output']/'result.json').write_text(json.dumps(result),encoding='utf-8')
            return result
        with patch.object(owner.executor,'run',side_effect=failure):
            with self.assertRaises(owner.ValidationOwnerError):
                self.issuer.validate('command.one',self.bundle)
        self.assertTrue(self.issuer.snapshot()['held'])
        self.assertFalse(self.issuer.snapshot()['registered_commands'])

    def test_source_change_rejected_before_new_run(self):
        with patch.object(owner,'source_release',return_value=({},'0'*64)), patch.object(owner.executor,'run') as run:
            with self.assertRaisesRegex(owner.ValidationOwnerError,'RELEASE_CHANGED'):
                self.issuer.validate('command.one',self.bundle)
            run.assert_not_called()

    def test_bounded_attempt_count(self):
        for index in range(owner.MAX_RUNS):
            self.mint('command.'+str(index))
        with patch.object(owner.executor,'run') as run:
            with self.assertRaisesRegex(owner.ValidationOwnerError,'RUN_LIMIT'):
                self.issuer.validate('command.extra',self.bundle)
            run.assert_not_called()

    def test_closed_owner_and_bad_input_rejected_without_engine(self):
        self.issuer.close()
        with patch.object(owner.executor,'run') as run:
            with self.assertRaisesRegex(owner.ValidationOwnerError,'OWNER_CLOSED'):
                self.issuer.validate('command.one',self.bundle)
            for deadline in (True,0,21):
                with self.assertRaisesRegex(owner.ValidationOwnerError,'DEADLINE'):
                    self.issuer.validate('command.one',self.bundle,timeout_seconds=deadline)
            run.assert_not_called()


if __name__=='__main__':
    unittest.main(verbosity=2)
