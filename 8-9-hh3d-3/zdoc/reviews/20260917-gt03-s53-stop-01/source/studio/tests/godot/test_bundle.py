"""Behavior checks for inert two-file bundles; no Godot or script execution."""
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
SPEC = importlib.util.spec_from_file_location('gt03_bundle', STUDIO/'godot-addon/bundle.py')
bundle = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bundle
SPEC.loader.exec_module(bundle)
from studio.protocol.core import ValidationError, canonical_bytes, parse_json


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.scene = b'[gd_scene format=3]\n[node name="Fixture" type="Node3D"]\n'
        self.script = b'extends Node3D\n'
        self.observation = 'sha256:' + '1' * 64
        self.engine = '2' * 64
        self.value = self.create()

    def create(self, scene=None, script=None, **observations):
        return bundle.create_bundle(self.scene if scene is None else scene,
            self.script if script is None else script,
            scene_revision=observations.get('scene_revision', self.observation),
            engine_sha256=observations.get('engine_sha256', self.engine))

    def replace(self, script, **preconditions):
        return bundle.replace_script(self.value, script,
            expected_project_revision=preconditions.get('expected_project_revision', self.value.project_revision),
            expected_script_sha256=preconditions.get('expected_script_sha256', self.value.script_sha256))

    def assert_code(self, code, function, *args, **kwargs):
        with self.assertRaises(ValidationError) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)

    def test_roundtrip_exact_two_files_lengths_and_hashes(self):
        result = bundle.decode_bundle(self.value.manifest_bytes, self.value.files)
        self.assertEqual(result, self.value)
        self.assertEqual(set(result.files), {'scenes/fixture.tscn', 'scripts/fixture_actor.gd'})
        manifest = parse_json(result.manifest_bytes)
        self.assertEqual(manifest['schema'], 'hh-godot-fixture-bundle-1')
        for path, expected in result.files.items():
            self.assertEqual(manifest['files'][path], {
                'sha256': hashlib.sha256(expected).hexdigest(), 'size_bytes': len(expected)})
        self.assertEqual(result.scene_revision, self.observation)
        self.assertEqual(result.engine_sha256, self.engine)

    def test_shared_canonical_manifest_and_revision_bind_both_files(self):
        manifest = parse_json(self.value.manifest_bytes)
        self.assertEqual(canonical_bytes(manifest), self.value.manifest_bytes)
        revision = manifest.pop('project_revision')
        self.assertEqual(revision, 'sha256:' + hashlib.sha256(canonical_bytes(manifest)).hexdigest())
        self.assertNotEqual(self.create(scene=self.scene+b'\n').project_revision, revision)
        self.assertNotEqual(self.create(script=self.script+b'\n').project_revision, revision)
        self.assertNotEqual(self.create(scene_revision='sha256:'+'3'*64).project_revision, revision)
        self.assertNotEqual(self.create(engine_sha256='4'*64).project_revision, revision)
        self.assertEqual(self.create().project_revision, revision)

    def test_immutable_copies_detach_mutable_input_and_mapping(self):
        scene, script = bytearray(self.scene), bytearray(self.script)
        original = self.create(scene=scene, script=script)
        manifest = bytearray(original.manifest_bytes)
        files = {bundle.SCENE_PATH: scene, bundle.SCRIPT_PATH: script}
        decoded = bundle.decode_bundle(manifest, files)
        scene.clear(); script.clear(); manifest.clear(); files.clear()
        self.assertEqual(decoded, original)
        self.assertIs(type(decoded.scene_bytes), bytes)
        self.assertIs(type(decoded.script_bytes), bytes)
        self.assertIs(type(decoded.manifest_bytes), bytes)
        with self.assertRaises(TypeError):
            decoded.files[bundle.SCENE_PATH] = b'changed'
        with self.assertRaises(FrozenInstanceError):
            decoded.script_bytes = b'changed'

    def test_replacement_preserves_scene_and_observations_without_mutating_prior(self):
        before = self.value
        newer = self.replace('extends Node3D\n# Việt Nam\n'.encode())
        self.assertEqual(before, self.create())
        self.assertEqual(newer.scene_bytes, before.scene_bytes)
        self.assertEqual(newer.scene_revision, before.scene_revision)
        self.assertEqual(newer.engine_sha256, before.engine_sha256)
        self.assertNotEqual(newer.script_sha256, before.script_sha256)
        self.assertNotEqual(newer.project_revision, before.project_revision)
        self.assertEqual(bundle.decode_bundle(newer.manifest_bytes, newer.files), newer)

    def test_replacement_rejects_stale_project_even_when_old_script_matches(self):
        other_scene = self.create(scene=self.scene+b'\n')
        self.assertEqual(other_scene.script_sha256, self.value.script_sha256)
        self.assert_code('BUNDLE_STALE_PROJECT', self.replace, b'new script',
                         expected_project_revision=other_scene.project_revision)

    def test_replacement_rejects_stale_script_without_changing_bundle(self):
        self.assert_code('BUNDLE_STALE_SCRIPT', self.replace, b'new script',
                         expected_script_sha256='3'*64)
        self.assertEqual(self.value, self.create())

    def test_old_preconditions_cannot_replace_new_bundle_and_same_bytes_are_stable(self):
        newer = self.replace(b'changed')
        self.assert_code('BUNDLE_STALE_PROJECT', bundle.replace_script, newer, b'again',
            expected_project_revision=self.value.project_revision,
            expected_script_sha256=self.value.script_sha256)
        self.assertEqual(self.replace(self.script), self.value)

    def test_utf8_multibyte_limits_are_bytes_and_exact_boundary_is_accepted(self):
        scene = ('é'*(bundle.MAX_SCENE_BYTES//2)).encode()
        script = ('é'*(bundle.MAX_SCRIPT_BYTES//2)).encode()
        maximum = self.create(scene=scene, script=script)
        self.assertEqual(len(maximum.scene_bytes), 1048576)
        self.assertEqual(len(maximum.script_bytes), 16384)
        self.assert_code('BUNDLE_SIZE_LIMIT', self.create, scene=scene+b'x')
        self.assert_code('BUNDLE_SIZE_LIMIT', self.create, script=script+b'x')
        self.assert_code('BUNDLE_SIZE_LIMIT', self.replace, script+b'x')

    def test_strict_utf8_rejects_invalid_sequences_without_replacement_decoding(self):
        for raw in (b'\xff', b'\xc0\xaf', b'\xed\xa0\x80', b'\xe2\x82'):
            with self.subTest(raw=raw):
                self.assert_code('BUNDLE_INVALID_UTF8', self.create, scene=raw)
                self.assert_code('BUNDLE_INVALID_UTF8', self.create, script=raw)
                self.assert_code('BUNDLE_INVALID_UTF8', self.replace, raw)

    def test_valid_utf8_is_preserved_without_normalization_or_godot_parsing(self):
        raw = '\ufeff@tool\r\nnot valid Godot syntax\x00e\u0301'.encode()
        self.assertEqual(self.create(scene=b'', script=raw).script_bytes, raw)
        self.assertNotEqual(self.create(script='é'.encode()).project_revision,
                            self.create(script='e\u0301'.encode()).project_revision)
        self.assertEqual(self.create(scene=b'', script=b'').scene_bytes, b'')

    def test_nonbytes_content_and_manifest_are_rejected_without_coercion(self):
        for invalid in ('extends Node3D', None, 42, [], memoryview(b'bytes')):
            with self.subTest(value=repr(invalid)):
                self.assert_code('BUNDLE_BYTES_REQUIRED', bundle.create_bundle, self.scene, invalid,
                    scene_revision=self.observation, engine_sha256=self.engine)
        self.assert_code('BUNDLE_BYTES_REQUIRED', bundle.decode_bundle,
                         self.value.manifest_bytes.decode(), self.value.files)

    def test_path_aliases_traversal_case_extra_missing_and_wrong_container_are_rejected(self):
        for alias in ('../scenes/fixture.tscn', 'Scenes/fixture.tscn',
                      'scenes\\fixture.tscn', 'res://scenes/fixture.tscn',
                      '/scenes/fixture.tscn', 'C:/scenes/fixture.tscn',
                      'scenes/fixture.tscn:stream', 'scenes/./fixture.tscn'):
            with self.subTest(alias=alias):
                self.assert_code('BUNDLE_INVALID_PATHS', bundle.decode_bundle,
                    self.value.manifest_bytes, {alias: self.scene, bundle.SCRIPT_PATH: self.script})
        for files in ({}, {bundle.SCENE_PATH:self.scene}, {**self.value.files, 'extra':b''}, [], None):
            self.assert_code('BUNDLE_INVALID_PATHS', bundle.decode_bundle, self.value.manifest_bytes, files)

    def test_changed_content_or_length_is_rejected(self):
        self.assert_code('BUNDLE_LENGTH_MISMATCH', bundle.decode_bundle, self.value.manifest_bytes,
            {**self.value.files, bundle.SCRIPT_PATH:self.script+b'\n'})
        changed = b'X'+self.script[1:]
        self.assert_code('BUNDLE_CONTENT_MISMATCH', bundle.decode_bundle, self.value.manifest_bytes,
            {**self.value.files, bundle.SCRIPT_PATH:changed})
        self.assert_code('BUNDLE_CONTENT_MISMATCH', bundle.FixtureBundle,
            self.value.manifest_bytes, self.scene, changed)

    def test_unknown_manifest_fields_are_rejected_at_each_level(self):
        for target in ('root', 'files', 'entry', 'observations'):
            value = parse_json(self.value.manifest_bytes)
            node = {'root':value, 'files':value['files'], 'entry':value['files'][bundle.SCENE_PATH],
                    'observations':value['caller_observations']}[target]
            node['extra'] = False
            self.assert_code('BUNDLE_INVALID_SHAPE', bundle.decode_bundle, canonical_bytes(value), self.value.files)

    def test_missing_manifest_fields_and_wrong_shapes_are_rejected(self):
        for field in ('schema', 'files', 'caller_observations', 'project_revision'):
            value = parse_json(self.value.manifest_bytes); del value[field]
            self.assert_code('BUNDLE_INVALID_SHAPE', bundle.decode_bundle, canonical_bytes(value), self.value.files)
        for invalid in ([], None, True, 'manifest'):
            self.assert_code('BUNDLE_INVALID_SHAPE', bundle.decode_bundle, canonical_bytes(invalid), self.value.files)
        value = parse_json(self.value.manifest_bytes); value['files'][bundle.SCENE_PATH] = []
        self.assert_code('BUNDLE_INVALID_SHAPE', bundle.decode_bundle, canonical_bytes(value), self.value.files)

    def test_schema_revision_and_boolean_length_tampering_are_rejected(self):
        for mutate, code in (
            (lambda v: v.update(schema='hh-godot-fixture-bundle-2'), 'BUNDLE_UNSUPPORTED_SCHEMA'),
            (lambda v: v.update(project_revision='sha256:'+'f'*64), 'BUNDLE_REVISION_MISMATCH'),
            (lambda v: v['files'][bundle.SCENE_PATH].update(size_bytes=True), 'BUNDLE_LENGTH_MISMATCH'),
            (lambda v: v['files'][bundle.SCENE_PATH].update(size_bytes=-1), 'BUNDLE_LENGTH_MISMATCH'),
            (lambda v: v['caller_observations'].update(engine_sha256='f'*64), 'BUNDLE_REVISION_MISMATCH')):
            value = parse_json(self.value.manifest_bytes); mutate(value)
            self.assert_code(code, bundle.decode_bundle, canonical_bytes(value), self.value.files)

    def test_noncanonical_duplicate_invalid_and_oversize_manifests_are_rejected(self):
        value = parse_json(self.value.manifest_bytes)
        self.assert_code('BUNDLE_NONCANONICAL_MANIFEST', bundle.decode_bundle,
                         json.dumps(value, indent=2).encode(), self.value.files)
        self.assert_code('BUNDLE_NONCANONICAL_MANIFEST', bundle.decode_bundle,
                         self.value.manifest_bytes+b'\n', self.value.files)
        self.assert_code('DUPLICATE_KEY', bundle.decode_bundle, b'{"schema":0,"schema":1}', self.value.files)
        self.assert_code('INVALID_JSON', bundle.decode_bundle, b'\xff', self.value.files)
        self.assert_code('BUNDLE_SIZE_LIMIT', bundle.decode_bundle,
                         b' '*(bundle.MAX_MANIFEST_BYTES+1), self.value.files)

    def test_hash_format_is_exact_for_observations_and_preconditions(self):
        for invalid in ('', 'A'*64, 'sha256:'+'a'*64, 'a'*63, 7, None):
            self.assert_code('BUNDLE_INVALID_HASH', self.create, engine_sha256=invalid)
            self.assert_code('BUNDLE_INVALID_HASH', self.replace, self.script, expected_script_sha256=invalid)
        for invalid in ('a'*64, 'sha256:'+'A'*64, 'sha256:'+'a'*63, None):
            self.assert_code('BUNDLE_INVALID_HASH', self.create, scene_revision=invalid)
            self.assert_code('BUNDLE_INVALID_HASH', self.replace, self.script, expected_project_revision=invalid)

    def test_codec_has_no_file_process_or_engine_effect(self):
        with (mock.patch('builtins.open', side_effect=AssertionError('file effect')),
              mock.patch.object(Path, 'open', side_effect=AssertionError('path effect')),
              mock.patch('subprocess.Popen', side_effect=AssertionError('process effect'))):
            created = self.create(script=b'@tool\nthis is not valid GDScript')
            decoded = bundle.decode_bundle(created.manifest_bytes, created.files)
            changed = bundle.replace_script(decoded, b'also unparsed',
                expected_project_revision=decoded.project_revision,
                expected_script_sha256=decoded.script_sha256)
        self.assertEqual(changed.script_bytes, b'also unparsed')


if __name__ == '__main__':
    unittest.main()
