"""Fail-closed semantic/native evidence boundary; no engine execution."""
from copy import deepcopy
import json
import unittest

from studio.tests.godot import run_saved_arena_builder as builder


class SavedArenaEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.recipe = builder.build_recipe()
        self.recipe_bytes = json.dumps(self.recipe).encode()
        self.scene_bytes = b'Only exact native output bytes may be adopted.'
        empty = {'nodes': [], 'resources': []}
        expected = self.recipe['expected_snapshot']
        self.observation = {
            'schema': 'hh-o2-saved-arena-native-1', 'authority': 0,
            'runtime_authorized': False, 'public_ack': False, 'pid': 73,
            'failures': [], 'checks': {key: True for key in builder.expected_checks(self.recipe)},
            'snapshots': {'before': empty, 'after_undo': empty,
                **{key: deepcopy(expected) for key in ('prepared', 'after_do', 'after_redo', 'after_reload')}},
            'recipe_sha256': builder.sha(self.recipe_bytes), 'arena_sha256': builder.sha(self.scene_bytes),
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

    def test_missing_or_false_native_property_check_rejects(self):
        for mutation in ('missing', 'false', 'extra'):
            value = deepcopy(self.observation)
            if mutation == 'missing':
                value['checks'].pop('set_player_collision_mask')
            elif mutation == 'false':
                value['checks']['set_player_collision_mask'] = False
            else:
                value['checks']['made_up'] = True
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'BUILDER_NATIVE_CHECKS'):
                self.verify(value)

    def test_saved_bytes_and_actual_pid_are_bound(self):
        with self.assertRaisesRegex(ValueError, 'BUILDER_NATIVE_BYTES'):
            self.verify(scene=self.scene_bytes + b'\n')
        with self.assertRaisesRegex(ValueError, 'BUILDER_NATIVE_BINDING'):
            self.verify(pid=74)


if __name__ == '__main__':
    unittest.main()
