"""Fail-closed semantic/native evidence boundary; no engine execution."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from studio.tests.godot import run_saved_room_builder as builder


class SavedRoomEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.recipe = builder.build_recipe()
        self.recipe_bytes = json.dumps(self.recipe).encode()
        self.scene_bytes = b'Only exact native output bytes may be adopted.'
        expected = self.recipe['expected_snapshot']
        empty = {'asset_resources': expected.get('asset_resources', []),
                 'nodes': [], 'resources': []}
        self.observation = {
            'schema': 'hh-o2-saved-room-native-1', 'authority': 0,
            'runtime_authorized': False, 'public_ack': False, 'pid': 73,
            'failures': [], 'checks': {key: True for key in builder.expected_checks(self.recipe)},
            'snapshots': {'before': empty, 'after_undo': empty,
                **{key: deepcopy(expected) for key in ('prepared', 'after_do', 'after_redo', 'after_reload')}},
            'recipe_sha256': builder.sha(self.recipe_bytes), 'room_sha256': builder.sha(self.scene_bytes),
        }

    def verify(self, value=None, *, scene=None, pid=73):
        builder.verify_observation(value or self.observation, self.recipe, self.recipe_bytes,
                                   self.scene_bytes if scene is None else scene, pid)

    def test_complete_semantics(self):
        self.verify()

    def test_pass_banner_cannot_replace_undo_or_reload(self):
        for key in ('after_undo', 'after_reload'):
            value = deepcopy(self.observation)
            value['passed'] = True
            value['snapshots'].pop(key)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'BUILDER_SEMANTICS'):
                self.verify(value)

    def test_changed_shape_or_layer_after_reload_rejects(self):
        for target in ('nodes', 'resources'):
            value = deepcopy(self.observation)
            value['snapshots']['after_reload'][target][-1]['properties']['size'] = [1, 1]
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'BUILDER_SEMANTICS'):
                self.verify(value)

    def test_empty_snapshot_keeps_declared_asset_inventory(self):
        value = deepcopy(self.observation)
        value['snapshots']['before'] = {'nodes': [], 'resources': []}
        with self.assertRaisesRegex(ValueError, 'BUILDER_SEMANTICS'):
            self.verify(value)

    def test_missing_or_false_native_property_check_rejects(self):
        for mutation in ('missing', 'false', 'extra'):
            value = deepcopy(self.observation)
            if mutation == 'missing':
                value['checks'].pop('set_avatar_velocity')
            elif mutation == 'false':
                value['checks']['set_avatar_velocity'] = False
            else:
                value['checks']['made_up'] = True
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'BUILDER_NATIVE_CHECKS'):
                self.verify(value)

    def test_saved_bytes_and_actual_pid_are_bound(self):
        with self.assertRaisesRegex(ValueError, 'BUILDER_NATIVE_BYTES'):
            self.verify(scene=self.scene_bytes + b'\n')
        with self.assertRaisesRegex(ValueError, 'BUILDER_NATIVE_BINDING'):
            self.verify(pid=74)

    def test_historical_source_retains_original_hash_without_requiring_live_producer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'source').mkdir()
            frozen = root / 'source/producer.py'
            frozen.write_bytes(b'old source\n')
            (root / 'producer.py').write_bytes(b'new source\n')
            files = {'producer.py': builder.sha(frozen.read_bytes())}
            with mock.patch.object(builder, 'STUDIO', root):
                builder.verify_source_binding(root, files, require_current_source=False)
                with self.assertRaisesRegex(ValueError, 'BUILDER_BOUND_HASH'):
                    builder.verify_source_binding(root, files, require_current_source=True)
                frozen.write_bytes(b'tampered old source\n')
                with self.assertRaisesRegex(ValueError, 'BUILDER_BOUND_HASH'):
                    builder.verify_source_binding(root, files, require_current_source=False)


if __name__ == '__main__':
    unittest.main()
