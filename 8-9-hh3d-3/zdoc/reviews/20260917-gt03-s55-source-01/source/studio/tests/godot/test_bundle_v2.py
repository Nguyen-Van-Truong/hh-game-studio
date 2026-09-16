"""Pure codec tests. All source/UID/engine observations here are SYNTHETIC."""
from dataclasses import FrozenInstanceError
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
SPEC = importlib.util.spec_from_file_location('gt03_test_bundle_v2', STUDIO/'godot-addon/bundle_v2.py')
codec = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = codec
SPEC.loader.exec_module(codec)
from studio.protocol.core import ValidationError, canonical_bytes, parse_json


def synthetic_files(module=codec):
    """Test data only; these UID values were not generated/imported by Godot."""
    files = {path: b'# SYNTHETIC codec fixture, not approved release\n' for path in module.PATHS}
    for index, path in enumerate(module.PATHS):
        if path.endswith('.uid'):
            files[path] = ('uid://synthetic' + str(index) + '\n').encode()
    files[module.SCENE_PATH] = b'[gd_scene format=3]\n[node name="Synthetic" type="Node3D"]\n'
    files[module.SCRIPT_PATH] = b'extends Node3D\n'
    return files


def synthetic_bundle(module=codec, files=None):
    return module.create_bundle(synthetic_files(module) if files is None else files,
        scene_revision='sha256:' + hashlib.sha256(b'synthetic semantic observation').hexdigest(),
        engine_sha256=hashlib.sha256(b'synthetic engine, never executed').hexdigest())


class BundleV2Tests(unittest.TestCase):
    def setUp(self):
        self.bundle = synthetic_bundle()

    def reject_manifest(self, mutate):
        value = parse_json(self.bundle.manifest_bytes)
        mutate(value)
        with self.assertRaises(ValidationError):
            codec.decode_bundle(canonical_bytes(value), self.bundle.files)

    def test_exact_profile_roundtrip_is_immutable_copy(self):
        files = {path: bytearray(raw) for path, raw in synthetic_files().items()}
        bundle = synthetic_bundle(files=files)
        before = bundle.manifest_bytes
        files[codec.SCRIPT_PATH][:] = b'changed'
        self.assertEqual(bundle.manifest_bytes, before)
        self.assertEqual(bundle.files[codec.SCRIPT_PATH], b'extends Node3D\n')
        with self.assertRaises(TypeError):
            bundle.files[codec.SCRIPT_PATH] = b'x'
        with self.assertRaises(FrozenInstanceError):
            bundle.manifest_bytes = b'x'
        decoded = codec.decode_bundle(bundle.manifest_bytes, bundle.files)
        self.assertEqual(decoded, bundle)
        self.assertEqual(len(bundle.files), 11)
        self.assertLess(len(bundle.manifest_bytes), codec.MAX_MANIFEST_BYTES)

    def test_revision_independent_of_mapping_order(self):
        reversed_files = dict(reversed(list(self.bundle.files.items())))
        self.assertEqual(synthetic_bundle(files=reversed_files).manifest_bytes, self.bundle.manifest_bytes)

    def test_each_missing_path_rejected(self):
        for path in codec.PATHS:
            with self.subTest(path=path), self.assertRaises(codec.BundleError):
                synthetic_bundle(files={key: raw for key, raw in self.bundle.files.items() if key != path})

    def test_extra_alias_traversal_or_cache_path_rejected(self):
        for path in ('Scenes/fixture.tscn', 'scenes/../fixture.tscn', '.godot/cache',
                     '/scenes/fixture.tscn', 'scenes\\fixture.tscn', 'scripts/other.gd'):
            with self.subTest(path=path), self.assertRaises(codec.BundleError):
                synthetic_bundle(files={**self.bundle.files, path: b'x'})
        files = dict(self.bundle.files)
        files['Scenes/fixture.tscn'] = files.pop(codec.SCENE_PATH)
        with self.assertRaises(codec.BundleError):
            synthetic_bundle(files=files)

    def test_uid_config_addon_changes_bind_project_while_semantic_stays_same(self):
        for path in (codec.UID_PATH, 'project.godot', 'addons/hh_studio/plugin.gd',
                     'addons/hh_studio/jcs_godot.gd.uid'):
            changed = dict(self.bundle.files)
            changed[path] = b'uid://changed42\n' if path.endswith('.uid') else changed[path] + b'# changed\n'
            other = synthetic_bundle(files=changed)
            with self.subTest(path=path):
                self.assertEqual(other.scene_revision, self.bundle.scene_revision)
                self.assertNotEqual(other.project_revision, self.bundle.project_revision)
                self.assertEqual(other.trusted_source_revision == self.bundle.trusted_source_revision,
                                 path == codec.UID_PATH)

    def test_script_replacement_preserves_all_other_source_and_trusted_revision(self):
        result = codec.replace_script(self.bundle, b'extends Node3D\n# replacement\n',
            expected_project_revision=self.bundle.project_revision,
            expected_script_sha256=self.bundle.script_sha256, expected_uid_sha256=self.bundle.uid_sha256)
        self.assertNotEqual(result.project_revision, self.bundle.project_revision)
        self.assertEqual(result.trusted_source_revision, self.bundle.trusted_source_revision)
        self.assertEqual(result.scene_revision, self.bundle.scene_revision)
        self.assertEqual(result.engine_sha256, self.bundle.engine_sha256)
        for path in codec.PATHS:
            if path != codec.SCRIPT_PATH:
                self.assertEqual(result.files[path], self.bundle.files[path])

    def test_all_three_replacement_preconditions_are_required(self):
        fields = dict(expected_project_revision=self.bundle.project_revision,
            expected_script_sha256=self.bundle.script_sha256, expected_uid_sha256=self.bundle.uid_sha256)
        for name in fields:
            changed = dict(fields)
            changed[name] = ('sha256:' if 'revision' in name else '') + '0' * 64
            with self.subTest(name=name), self.assertRaises(codec.BundleError):
                codec.replace_script(self.bundle, b'new', **changed)
            changed = dict(fields)
            del changed[name]
            with self.assertRaises(TypeError):
                codec.replace_script(self.bundle, b'new', **changed)

    def test_declared_profile_is_data_not_release_attestation(self):
        # Self-consistent different trusted bytes are legal codec data. A real
        # factory must separately compare to the pinned release before execution.
        files = dict(self.bundle.files)
        files['addons/hh_studio/plugin.gd'] = b'# arbitrary declared trusted source\n'
        result = synthetic_bundle(files=files)
        self.assertNotEqual(result.trusted_source_revision, self.bundle.trusted_source_revision)
        self.assertFalse(hasattr(result, 'trusted_release_verified'))
        self.assertFalse(hasattr(result, 'engine_effects_verified'))

    def test_role_and_metadata_are_not_caller_authority(self):
        self.reject_manifest(lambda value: value['files'][codec.SCRIPT_PATH].update(role='trusted_addon'))
        self.reject_manifest(lambda value: value['files'][codec.SCRIPT_PATH].update(size_bytes=True))
        self.reject_manifest(lambda value: value['files'][codec.SCRIPT_PATH].update(size_bytes=999))
        self.reject_manifest(lambda value: value['files'][codec.SCRIPT_PATH].update(sha256='0' * 64))

    def test_unknown_fields_and_wrong_profile_rejected(self):
        self.reject_manifest(lambda value: value.update(extra=True))
        self.reject_manifest(lambda value: value.update(schema='hh-godot-fixture-bundle-1'))
        self.reject_manifest(lambda value: value.update(profile='other-profile'))
        self.reject_manifest(lambda value: value['caller_observations'].update(verified=True))
        self.reject_manifest(lambda value: value['files'][codec.SCRIPT_PATH].update(editable=True))

    def test_corrupt_revisions_and_observations_rejected(self):
        self.reject_manifest(lambda value: value.update(project_revision='sha256:' + '0' * 64))
        self.reject_manifest(lambda value: value.update(trusted_source_revision='sha256:' + '0' * 64))
        self.reject_manifest(lambda value: value['caller_observations'].update(scene_revision=''))
        self.reject_manifest(lambda value: value['caller_observations'].update(engine_sha256='x'))

    def test_content_bytes_cannot_bypass_manifest_via_direct_constructor(self):
        files = dict(self.bundle.files)
        files[codec.UID_PATH] = b'uid://different\n'
        with self.assertRaises(codec.BundleError):
            codec.CompleteFixtureBundle(self.bundle.manifest_bytes, files)

    def test_canonical_manifest_required_and_oversize_rejected(self):
        value = parse_json(self.bundle.manifest_bytes)
        for raw in (json.dumps(value, indent=2).encode(), self.bundle.manifest_bytes + b'\n',
                    b' ' * (codec.MAX_MANIFEST_BYTES + 1), b'', b'{"schema":1,"schema":2}'):
            with self.subTest(length=len(raw)), self.assertRaises(ValidationError):
                codec.decode_bundle(raw, self.bundle.files)

    def test_every_per_file_cap_before_manifest_creation(self):
        for path, (_, limit) in codec.FILE_PROFILE.items():
            with self.subTest(path=path), self.assertRaises(codec.BundleError):
                synthetic_bundle(files={**self.bundle.files, path: b'a' * (limit + 1)})

    def test_empty_invalid_utf8_and_non_builtin_buffers_rejected(self):
        for raw in (b'', b'\xff', memoryview(b'hello'), 'text'):
            with self.subTest(raw=repr(raw)), self.assertRaises(codec.BundleError):
                synthetic_bundle(files={**self.bundle.files, codec.SCRIPT_PATH: raw})

    def test_uid_lexical_screening_only_bounded_ascii_one_lf(self):
        for raw in (b'uid://ABC\n', b'uid://abc', b'uid://abc\r\n', b'uid://abc\n\n',
                    b'uid://abc/def\n', 'uid://café\n'.encode(), b'uid://\n'):
            with self.subTest(raw=repr(raw)), self.assertRaises(codec.BundleError):
                synthetic_bundle(files={**self.bundle.files, codec.UID_PATH: raw})

    def test_two_file_v1_mapping_is_not_an_implicit_migration(self):
        spec = importlib.util.spec_from_file_location('gt03_test_bundle_v1_compat', STUDIO/'godot-addon/bundle.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        old = module.create_bundle(b'scene', b'script', scene_revision=self.bundle.scene_revision,
                                   engine_sha256=self.bundle.engine_sha256)
        self.assertEqual(module.decode_bundle(old.manifest_bytes, old.files), old)
        with self.assertRaises(codec.BundleError):
            codec.decode_bundle(old.manifest_bytes, old.files)


if __name__ == '__main__':
    unittest.main()
