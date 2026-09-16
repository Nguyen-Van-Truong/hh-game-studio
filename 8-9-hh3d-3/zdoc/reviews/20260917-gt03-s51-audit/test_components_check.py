"""Read-only auditor rejection tests; no evidence writes or native process."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock

AUDIT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('s51_components_check_tests', AUDIT / 'components_check.py')
checker = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = checker
spec.loader.exec_module(checker)
ROOT = AUDIT.parent / '20260917-gt03-s51-components-01'


class ComponentAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = checker.verify(ROOT)
        cls.read = staticmethod(checker.H.read)

    def reject(self, relative, change, pattern):
        path = (ROOT / relative).resolve()
        def altered(current):
            value = self.read(current)
            if Path(current).resolve() == path:
                value = copy.deepcopy(value)
                change(value)
            return value
        with mock.patch.object(checker.H, 'read', side_effect=altered):
            with self.assertRaisesRegex(ValueError, pattern):
                checker.verify(ROOT)

    def test_actual_package_passes_with_scope_limits_explicit(self):
        self.assertEqual(self.summary['components'], 2)
        self.assertEqual(self.summary['native_descriptor_files'], 24)
        for key in ('original_validation_raw_facts_verified', 'full_semantic_jcs_binding_verified',
                    'selector_chain_host_verified', 'readonly_reopen_host_verified'):
            self.assertIs(self.summary[key], True)
        for key in ('public_ack', 'selected_state_verified', 'live_editor_adoption_verified',
                    'authenticated_publication_verified', 'independent_live_root_verification',
                    'selector_native_versions_persisted', 'final_host_completion_upper_bound_available'):
            self.assertIs(self.summary[key], False)

    def test_changed_source_map_cannot_hide_behind_same_closure_label(self):
        self.reject('source-closure.json',
            lambda value: value['files'].__setitem__('godot-addon/validation_owner.py', '0' * 64),
            'independent source closure')

    def test_integer_booleans_cannot_pass_host_exit_or_summary(self):
        self.reject('capture.json', lambda value: value['host'].__setitem__('exit_code', False), 'host exit')
        self.reject('capture.json', lambda value: value['result'].__setitem__('components', True), 'final native')

    def test_new_authority_claim_is_rejected(self):
        self.reject('component-0.json', lambda value: value.__setitem__('live_editor_adoption_verified', True),
                    'authority overclaim')
        self.reject('capture.json', lambda value: value['result'].__setitem__('selected_state_verified', True),
                    'final native')

    def test_original_receipt_fields_are_independently_recomputed(self):
        for key in ('engine_sha256', 'source_release_sha256', 'evidence_sha256', 'run_id'):
            with self.subTest(field=key):
                self.reject('component-0.json',
                    lambda value, key=key: value['validation_receipt'].__setitem__(key, 'f' * 64),
                    'original issued receipt')

    def test_final_manifest_cannot_be_relabelled_without_raw_semantic_state(self):
        self.reject('component-0.json', lambda value:
            value['final_manifest']['caller_observations'].__setitem__('scene_revision', 'sha256:' + 'e' * 64),
            'exact semantic remanifest')

    def test_caller_rehashed_semantic_payload_does_not_replace_actual_output(self):
        def changed(value):
            semantic = value['observation']['semantic']
            semantic['state']['nodes'][0]['name'] = 'CallerReplacement'
            # Matching labels elsewhere still cannot replace native stdout.
            semantic['revision'] = 'sha256:' + '1' * 64
            value['semantic_observation']['semantic'] = copy.deepcopy(semantic)
            value['semantic_receipt']['scene_revision'] = semantic['revision']
        self.reject('component-0.json', changed, 'raw full semantic observation')

    def test_cross_bundle_native_identity_alias_rejected(self):
        first = self.read(ROOT / 'component-0.json')
        identity = next(iter(first['descriptor']['files'].values()))['file_id']
        self.reject('component-1.json', lambda value:
            next(iter(value['descriptor']['files'].values())).__setitem__('file_id', identity),
            'cross-component native identity')

    def test_selector_parent_and_boolean_generation_rejected(self):
        self.reject('component-1.json', lambda value:
            value['selector']['parent_selection'].__setitem__('identity', 'sha256:' + '2' * 64),
            'selector bytes/parent/generation')
        self.reject('component-0.json', lambda value:
            value['selector']['selection'].__setitem__('generation', False),
            'selector bytes/parent/generation')

    def test_timestamp_types_order_and_native_bounds_are_checked(self):
        state = {'container_state': {'StartedAt': '2026-09-16T19:00:00Z',
                                    'FinishedAt': '2026-09-16T19:00:02.000000001Z'}}
        start = checker.epoch_ms(state['container_state']['StartedAt'])
        end = checker.epoch_ms(state['container_state']['FinishedAt'])
        good = {'validation_started_ms': start - 1, 'validation_completed_ms': end + 1}
        self.assertEqual(checker.interval(good, state, start - 2), (start - 1, end + 1))
        for change in ({'validation_started_ms': True}, {'validation_started_ms': start + 1},
                       {'validation_completed_ms': end - 1}, {'validation_started_ms': start - 3},
                       {'validation_completed_ms': 9007199254740992}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                checker.interval({**good, **change}, state, start - 2)

    def test_changed_actual_native_exit_cannot_hide_behind_pass_flags(self):
        row = self.read(ROOT / 'component-0.json')
        run_id = row['validation_receipt']['run_id']
        directory = next(path for path in (ROOT / 'validation').iterdir()
            if self.read(path / 'executor/result.json')['run_id'] == run_id)
        relative = (directory / 'executor/result.json').relative_to(ROOT)
        self.reject(relative, lambda value: value['container_state'].__setitem__('ExitCode', False),
                    'actual final state differs')


if __name__ == '__main__':
    unittest.main(verbosity=2)
