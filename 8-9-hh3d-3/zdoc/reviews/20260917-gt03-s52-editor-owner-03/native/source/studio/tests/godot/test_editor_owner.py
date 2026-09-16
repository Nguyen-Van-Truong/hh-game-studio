"""Pure issuer/shape tests; actual editor integration is a separate probe."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import Mock

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


if __name__ == '__main__':
    unittest.main()
