"""Pure S50 adapter/component tamper tests; no engine or native owner calls."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
path = Path(__file__).with_name('verify_evidence.py')
spec = importlib.util.spec_from_file_location('s50_audit_under_test', path)
audit = importlib.util.module_from_spec(spec); spec.loader.exec_module(audit)
H = audit.H
source = audit.COMPONENTS / 'source/studio'
sys.path.insert(0, str(source.parent))
validation = H.module('s50_audit_test_validation', source / 'godot-addon/validation_owner.py')
closure = H.read(audit.COMPONENTS / 'source-closure.json')
row = H.read(audit.COMPONENTS / 'component-0.json')
factory = validation.factory
bundle = factory.compose(factory.DEFAULT_SCENE, factory.DEFAULT_SCRIPT,
    scene_revision='sha256:' + H.digest(factory.DEFAULT_SCENE), engine_sha256=validation.executor.BINARY_SHA256)


class ComponentAuditTests(unittest.TestCase):
    def test_pinned_helper_and_explicit_package_bindings(self):
        self.assertEqual(H.sha(audit.LEGACY), audit.LEGACY_SHA256)
        self.assertEqual(H.PACKAGE.name, '20260917-gt03-s50-editor-01')
        self.assertEqual(H.PROFILE.name, '20260917-gt03-s50-profile-01')
        self.assertEqual(H.HOST_DEATH.name, '20260917-gt03-s50-host-death-01')

    def test_changed_dependency_rejected_before_import(self):
        with tempfile.TemporaryDirectory(prefix='hh-s50-audit-test-') as name:
            path = Path(name) / 'changed.py'; path.write_bytes(audit.LEGACY.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'dependency hash changed'):
                audit.load_legacy(path)

    def test_actual_descriptor_metadata_baseline(self):
        _, names, ids = audit.descriptor(row['descriptor'], bundle)
        self.assertEqual((len(names), len(ids)), (12, 12))

    def test_missing_file_or_manifest_rejected(self):
        for part in ('files', 'manifest'):
            value = deepcopy(row['descriptor'])
            if part == 'manifest': del value['manifest']
            else: del value['files']['scripts/fixture_actor.gd.uid']
            with self.assertRaises(ValueError): audit.descriptor(value, bundle)

    def test_native_alias_wrong_volume_size_and_hash_rejected(self):
        changes = (lambda d: d['manifest'].update(name=next(iter(d['files'].values()))['name']),
                   lambda d: d['manifest'].update(file_id=next(iter(d['files'].values()))['file_id']),
                   lambda d: d['manifest'].update(file_id=d['root_identity']['file_id']),
                   lambda d: d['manifest'].update(volume='0'),
                   lambda d: d['manifest'].update(size_bytes=True),
                   lambda d: d['files']['scripts/fixture_actor.gd.uid'].update(sha256='0' * 64))
        for change in changes:
            value = deepcopy(row['descriptor']); change(value)
            with self.assertRaises(ValueError): audit.descriptor(value, bundle)

    def test_native_root_typed_and_uint64_bounds(self):
        for value in (True, '01', str(2**64), '-1'):
            descriptor = deepcopy(row['descriptor']); descriptor['root_identity']['volume'] = value
            with self.assertRaises(ValueError): audit.descriptor(descriptor, bundle)

    def test_summary_does_not_accept_selector_semantic_or_integer_boolean_claims(self):
        original = H.read(audit.COMPONENTS / 'components.json')
        audit.component_summary(original)
        for key, value in (('semantic_scene_revision_verified', True), ('selected_state_verified', True),
                           ('readonly_reopen_verified', 1), ('components', True), ('temporary_removed', False)):
            changed = deepcopy(original); changed[key] = value
            with self.assertRaises(ValueError): audit.component_summary(changed)

    def test_actual_raw_component_package_baseline(self):
        result = audit.verify_components(closure['files'], closure['source_closure_sha256'])
        self.assertEqual(result['components'], 2)
        self.assertFalse(result['independent_live_root_verification'])
        self.assertFalse(result['public_ack'])

    def test_registered_receipt_evidence_hash_cannot_be_substituted(self):
        original_read = H.read
        def read(path):
            value = original_read(path)
            if Path(path) == audit.COMPONENTS / 'component-0.json':
                value['validation_receipt']['evidence_sha256'] = '0' * 64
            return value
        with patch.object(H, 'read', read), self.assertRaisesRegex(ValueError, 'receipt data differs'):
            audit.verify_components(closure['files'], closure['source_closure_sha256'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
