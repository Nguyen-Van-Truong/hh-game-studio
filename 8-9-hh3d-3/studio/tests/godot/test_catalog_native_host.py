"""Fail-closed readback checks; no engine or authored oracle enters the host."""
from __future__ import annotations

import copy
import unittest

from studio.tests.godot import test_registered_authoring_owner as owner_fixture
from studio.tests.godot import run_registered_authoring_probe as runner
from studio.protocol.core import canonical_bytes

native = runner._NATIVE


class CatalogNativeHostTests(unittest.TestCase):
    def setUp(self):
        # Reuse the real admitted-owner fixture without duplicating its tests.
        fixture = owner_fixture.RegisteredOwnerTests(methodName='runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.addCleanup(fixture.tearDown)
        actor = fixture.actor()
        transaction = actor.prepare(fixture.requests, inventory=fixture.inventory)
        self.data = native.make_input(transaction, fixture.admission, fixture.recipe['root'],
                                      runner._OWNER._NODE.load_catalog(),
                                      {'mesh.avatar': {'path': 'assets/avatar.glb'}})
        self.rows, self.snapshot = native.expected_readbacks(self.data)
        self.assertEqual(self.snapshot, fixture.recipe['expected_snapshot'])
        self.raw = canonical_bytes(self.data)
        self.scene = b'captured scene bytes'
        self.observation = {
            'schema': native.OBSERVATION_SCHEMA, 'authority': 0, 'public_ack': False,
            'failures': [], 'pid': 42, 'input_sha256': native.sha(self.raw),
            'transaction_digest': transaction.digest, 'command_ids': list(transaction.command_ids),
            'commands': self.rows, 'snapshots': {'after_apply': self.snapshot, 'after_reload': self.snapshot},
            'checks': dict.fromkeys(('undo', 'redo', 'save', 'reload'), True),
            'scene_sha256': native.sha(self.scene)}

    def verify(self, value):
        native.verify_observation(self.data, value, input_raw=self.raw, scene_raw=self.scene, pid=42)

    def test_transaction_readbacks_are_reduced_without_a_builder(self):
        self.assertNotIn('expected_snapshot', self.data)
        self.assertNotIn('recipe', self.data)
        self.verify(self.observation)
        changed = copy.deepcopy(self.data)
        command = changed['transaction']['commands'][0]
        command['projection']['payload']['name'] = 'NewAvatar'
        command['projection_sha256'] = 'sha256:' + native.sha(canonical_bytes(command['projection']))
        body = {k: v for k, v in changed['transaction'].items() if k != 'transaction_digest'}
        changed['transaction']['transaction_digest'] = 'sha256:' + native.sha(canonical_bytes(body))
        rows, snapshot = native.expected_readbacks(changed)
        self.assertEqual(rows[0]['readback']['name'], 'NewAvatar')
        self.assertEqual(snapshot['nodes'][1]['name'], 'NewAvatar')

    def test_missing_or_tampered_native_rows_cannot_pass(self):
        mutations = (
            lambda v: v['commands'].pop(),
            lambda v: v['commands'][0].update(verified=False),
            lambda v: v['commands'][0].update(projection_sha256='sha256:' + '0' * 64),
            lambda v: v['commands'][0]['readback'].update(name='Other'),
            lambda v: v['snapshots']['after_reload']['nodes'].pop(),
            lambda v: v['checks'].update(reload=False),
            lambda v: v['checks'].pop('save'),
            lambda v: v.update(scene_sha256='0' * 64),
            lambda v: v.update(pid=43),
            lambda v: v.update(failures=['actual native failure']))
        for index, mutate in enumerate(mutations):
            value = copy.deepcopy(self.observation)
            mutate(value)
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.verify(value)

    def test_transaction_and_projection_tampering_reject_before_execution(self):
        for field in ('command_ids', 'transaction_digest'):
            data = copy.deepcopy(self.data)
            data['transaction'][field] = [] if field == 'command_ids' else 'sha256:' + '0' * 64
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'CATALOG_TRANSACTION_DIGEST'):
                native.expected_readbacks(data)

    def test_float_tolerance_cannot_hide_types_or_nonfinite_values(self):
        self.assertTrue(native.semantic_equal([1.0000001], [1]))
        for value in ([True], [float('nan')], [float('inf')], ['1'], [1.1]):
            with self.subTest(value=value):
                self.assertFalse(native.semantic_equal(value, [1]))
        self.assertFalse(native.semantic_equal({'x': 1, 'extra': 2}, {'x': 1}))


if __name__ == '__main__':
    unittest.main()
