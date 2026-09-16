"""Offline S51 adapter/parity corruption tests. No native process invocation."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
path = Path(__file__).with_name('verify_evidence.py')
spec = importlib.util.spec_from_file_location('s51_audit_under_test', path)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
H = audit.H


class AdapterTests(unittest.TestCase):
    def test_pinned_helper_and_explicit_final_package_bindings(self):
        self.assertEqual(H.sha(audit.LEGACY), audit.LEGACY_SHA256)
        self.assertEqual(H.PACKAGE.name, '20260917-gt03-s51-editor-01')
        self.assertEqual(H.LINUX.name, '20260917-gt03-s51-linux-01')
        self.assertEqual(H.PROFILE.name, '20260917-gt03-s51-profile-01')
        self.assertEqual(H.HOST_DEATH.name, '20260917-gt03-s51-host-death-01')
        self.assertEqual(audit.SEMANTIC.name, '20260917-gt03-s51-semantic-04')
        self.assertEqual(audit.EXPECTED_TESTS, 471)

    def test_changed_dependency_rejected_before_import(self):
        with tempfile.TemporaryDirectory(prefix='hh-s51-audit-test-') as name:
            path = Path(name) / 'changed.py'
            path.write_bytes(audit.LEGACY.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'dependency hash changed'): audit.load_legacy(path)

    def test_diagnostic_origin_drift_is_not_final_semantic_proof(self):
        capture = {'source_closure_sha256': audit.EXPECTED_CLOSURE, 'passed': True,
                   'snapshot_unchanged': True, 'origin_source_unchanged': False, 'windows_binary_unchanged': True}
        with patch.object(H, 'source_copy', return_value=(Path('unused'), {})), \
                patch.object(H, 'read', return_value=capture), \
                self.assertRaisesRegex(ValueError, 'origin_source_unchanged'):
            audit.verify_semantic({}, audit.EXPECTED_CLOSURE)

    def test_old_diagnostic_closure_cannot_be_relabelled_final(self):
        capture = {'source_closure_sha256': 'cd03592ff99c1d4b38055f04175a30383b6e1a449a55166600812fa77570fbdd'}
        with patch.object(H, 'source_copy', return_value=(Path('unused'), {})), \
                patch.object(H, 'read', return_value=capture), \
                self.assertRaisesRegex(ValueError, 'source mismatch'):
            audit.verify_semantic({}, audit.EXPECTED_CLOSURE)

    def test_mandatory_semantic_inventory_cannot_be_omitted(self):
        with patch.object(H, 'inventory', return_value={'capture.json': 'a' * 64}), \
                self.assertRaisesRegex(ValueError, 'mandatory S51 package'):
            audit.principal_inventory(audit.SEMANTIC, {})

    def test_duplicate_keys_and_bool_integer_substitution_remain_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate JSON'): H.parse('{"passed":true,"passed":true}')
        self.assertFalse(H.exact({'exit_code': False}, {'exit_code': 0}))


class SemanticArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = H.read(H.PACKAGE / 'source-closure.json')
        cls.source, _ = H.source_copy(audit.SEMANTIC, cls.manifest['files'], audit.EXPECTED_CLOSURE)
        sys.path.insert(0, str(cls.source.parent))
        cls.comparator = H.module('s51_audit_test_comparator', cls.source / 'godot-addon/profile_readback.py')
        cls.case = audit.SEMANTIC / 'defaults_override'
        codec = cls.comparator.factory.bundle_codec
        cls.bundle = codec.decode_bundle((cls.case / 'manifest.json').read_bytes(),
            {name: H.inside(cls.case / 'input', name).read_bytes() for name in codec.PATHS})
        cls.semantic = H.read(cls.case / 'linux-observation.json')['observation']['semantic']

    def verify_editor(self):
        return audit.editor_parity(self.case, self.bundle, self.semantic, self.source, self.comparator)

    def test_actual_final_six_case_package_recomputed(self):
        result = audit.verify_semantic(self.manifest['files'], audit.EXPECTED_CLOSURE)
        self.assertEqual(result['cases'], 6)
        self.assertIs(result['exact_jcs_parity'], True)
        self.assertIs(result['public_ack'], False)
        self.assertIs(result['selected_state_verified'], False)

    def test_actual_baseline_editor_raw_capture(self):
        self.assertTrue(self.verify_editor()['passed'])

    def test_failed_actual_host_exit_overrides_saved_pass(self):
        original = H.read
        def read(path):
            value = original(path)
            if Path(path) == self.case / 'editor-host.json': value['exit_code'] = 1
            return value
        with patch.object(H, 'read', read), self.assertRaisesRegex(ValueError, 'actual host exit'):
            self.verify_editor()

    def test_exact_jcs_artifact_cannot_gain_even_one_byte(self):
        original = Path.read_bytes
        def read(path):
            raw = original(path)
            return raw + b'\n' if path == self.case / 'editor-state.jcs' else raw
        with patch.object(Path, 'read_bytes', read), self.assertRaisesRegex(ValueError, 'canonical bytes changed'):
            self.verify_editor()

    def test_overlay_substitution_cannot_hide_behind_unchanged_flag(self):
        original = H.read
        def read(path):
            value = original(path)
            if Path(path) == self.case / 'editor-inputs.json':
                value['files']['addons/hh_studio/plugin.cfg'] = '0' * 64
            return value
        with patch.object(H, 'read', read), self.assertRaisesRegex(ValueError, 'trusted overlay'):
            self.verify_editor()

    def changed_report(self, change, message):
        original_read, original_text = H.read, Path.read_text
        changed = deepcopy(original_read(self.case / 'editor-observation.json'))
        change(changed['observation'])
        def read(path):
            return deepcopy(changed) if Path(path) == self.case / 'editor-observation.json' else original_read(path)
        def text(path, *args, **kwargs):
            raw = original_text(path, *args, **kwargs)
            if path == self.case / 'editor-engine.log':
                rows = raw.splitlines()
                rows = [('HH_EDITOR_SEMANTIC ' + H.json.dumps(changed['observation']))
                        if line.startswith('HH_EDITOR_SEMANTIC ') else line for line in rows]
                return '\n'.join(rows) + '\n'
            return raw
        with patch.object(H, 'read', read), patch.object(Path, 'read_text', text), \
                self.assertRaisesRegex(ValueError, message):
            self.verify_editor()

    def test_self_consistent_log_with_wrong_pid_is_rejected(self):
        self.changed_report(lambda value: value.update(pid=value['pid'] + 1), 'native context/PID')

    def test_isolated_context_cannot_claim_live_editor(self):
        self.changed_report(lambda value: value.update(context_kind='isolated_candidate'), 'native context/PID')

    def test_rehashed_tiny_float_difference_still_breaks_exact_parity(self):
        def change(value):
            snapshot = value['snapshot']
            snapshot['state']['nodes'][0]['rotation_degrees'][0] = 1e-13
            snapshot['revision'] = 'sha256:' + H.digest(self.comparator.factory.bundle_codec.canonical_bytes(snapshot['state']))
        self.changed_report(change, 'exact JCS mismatch')


if __name__ == '__main__': unittest.main(verbosity=2)
