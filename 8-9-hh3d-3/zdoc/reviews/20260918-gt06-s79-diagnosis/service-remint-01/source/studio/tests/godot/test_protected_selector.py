"""Actual native storage transitions; no engine, admission or public ACK claim."""
from dataclasses import FrozenInstanceError, replace
import copy
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_protected_bundle as base

module, codec = base.module, base.codec
ProtectedFileRoot = base.ProtectedFileRoot


def selection(generation):
    return {'generation': generation, 'identity': 'sha256:' + format(generation + 10, '064x')}


@unittest.skipUnless(os.name == 'nt', 'actual Windows NTFS ProtectedFileRoot required')
class ProtectedSelectorNativeTests(unittest.TestCase):
    setUp = base.ProtectedBundleNativeTests.setUp
    new_files = base.ProtectedBundleNativeTests.new_files
    new_store = base.ProtectedBundleNativeTests.new_store
    cleanup = base.ProtectedBundleNativeTests.cleanup
    entries = base.ProtectedBundleNativeTests.entries

    def staged(self, command='cmd.a', variant=0, owner=None):
        owner = owner or self.store
        files = dict(self.bundle.files)
        files[codec.SCRIPT_PATH] = ('extends Node3D\n@export var fixture_value: int = %d\n' % variant).encode()
        bundle = codec.create_bundle(files, scene_revision=self.bundle.scene_revision,
                                     engine_sha256=self.bundle.engine_sha256)
        receipt = owner.stage(owner.prepare(command, bundle))
        return receipt, bundle

    def initialize(self, owner=None):
        owner = owner or self.store
        bundle_receipt, bundle = self.staged(owner=owner)
        intent = owner.prepare_selection(bundle_receipt, selection(0), expected=None)
        return bundle_receipt, bundle, intent, owner.select(intent)

    def test_initialize_cas_old_bundle_readback_and_readonly_reopen(self):
        self.assertIsNone(self.store.inspect_selection())
        first, first_bundle, _, first_selection = self.initialize()
        second, second_bundle = self.staged('cmd.b', 42)
        intent = self.store.prepare_selection(second, selection(1), expected=first_selection.snapshot)
        with mock.patch.object(self.files, 'atomic_replace', wraps=self.files.atomic_replace) as cas, \
             mock.patch.object(self.files, 'confirm_barrier', wraps=self.files.confirm_barrier) as barrier:
            selected = self.store.select(intent)
        cas.assert_called_once_with('active.json', intent.source_bytes, expected=first_selection.version)
        barrier.assert_called_once_with('active.json', selected.version)
        self.assertIs(self.store.inspect_selection(), selected.snapshot)
        self.assertNotEqual(selected.version.identity.file_id, first_selection.version.identity.file_id)
        self.assertEqual(self.store.readback(first), first_bundle)
        self.assertEqual(self.store.readback(second), second_bundle)
        self.assertEqual(len(self.entries()), 25)
        root, identity = self.store.root, self.store.root_identity
        self.store.close()
        native = ProtectedFileRoot.reopen_readonly(root, identity)
        self.unowned.append(native)
        reopened = self.new_store(native)
        snapshot = reopened.inspect_selection()
        self.assertEqual((snapshot.source_bytes, snapshot.version), (selected.source_bytes, selected.version))
        self.assertEqual(reopened.read_descriptor(first_selection.descriptor), first_bundle)
        self.assertEqual(reopened.read_descriptor(snapshot.descriptor), second_bundle)
        self.assertIsNone(reopened.lookup_selection('cmd.b'))
        self.assertEqual(reopened.selection_snapshot(), ())
        for call in (lambda: reopened.prepare_selection(second, selection(2), expected=snapshot),
                     lambda: reopened.select(intent),
                     lambda: reopened.cancel_unused_prepare(self.store._records['cmd.a'].intent)):
            with self.assertRaisesRegex(module.ProtectedBundleError, 'READONLY'):
                call()
        self.assertTrue(native._readonly)

    def test_prepare_selection_has_no_writes_and_is_registered_immutable_canonical(self):
        receipt, _ = self.staged()
        with mock.patch.object(self.files, 'create_new', wraps=self.files.create_new) as create, \
             mock.patch.object(self.files, 'atomic_replace', wraps=self.files.atomic_replace) as cas:
            intent = self.store.prepare_selection(receipt, selection(0), expected=None)
            self.assertIs(self.store.prepare_selection(receipt, selection(0), expected=None), intent)
            self.assertEqual((create.call_count, cas.call_count), (0, 0))
        value = module.parse_json(intent.source_bytes)
        self.assertEqual(set(value), {'schema', 'command_id', 'selection', 'parent_selection', 'descriptor', 'descriptor_sha256'})
        self.assertEqual(module.canonical_bytes(value), intent.source_bytes)
        self.assertIsNone(value['parent_selection'])
        self.assertEqual(value['descriptor']['root_identity'], module._root_value(self.store.root_identity))
        with self.assertRaises(FrozenInstanceError):
            intent.command_id = 'changed'
        with self.assertRaisesRegex(module.ProtectedBundleError, 'REGISTERED_INTENT'):
            self.store.select(replace(intent))
        self.assertNotIn('active.json', self.entries())
        selected = self.store.select(intent)
        self.assertFalse(selected.public_ack)
        self.assertFalse(selected.engine_effects_verified)
        self.assertTrue(selected.namespace_durability_verified)
        self.assertEqual(self.store.selection_snapshot()[0].attempted_writes, 1)

    def test_lost_response_duplicate_is_historical_receipt_without_republication(self):
        first, _, intent_a, selected_a = self.initialize()
        second, _ = self.staged('cmd.b', 1)
        intent_b = self.store.prepare_selection(second, selection(1), expected=selected_a.snapshot)
        selected_b = self.store.select(intent_b)
        with mock.patch.object(self.files, 'create_new', wraps=self.files.create_new) as create, \
             mock.patch.object(self.files, 'atomic_replace', wraps=self.files.atomic_replace) as cas:
            self.assertIs(self.store.select(intent_a), selected_a)
            self.assertIs(self.store.select(intent_b), selected_b)
            self.assertIs(self.store.lookup_selection('cmd.a'), selected_a)
            self.assertIs(self.store.prepare_selection(first, selection(0), expected=None), intent_a)
            self.assertEqual((create.call_count, cas.call_count), (0, 0))
        self.assertIs(self.store.inspect_selection(), selected_b.snapshot)
        self.assertNotEqual(selected_a.selection, self.store.inspect_selection().selection)

    def test_wrong_copied_and_stale_expected_snapshot_are_ordinary_rejections(self):
        _, _, _, selected_a = self.initialize()
        second, _ = self.staged('cmd.b', 1)
        with self.assertRaisesRegex(module.ProtectedBundleError, 'REGISTERED_SNAPSHOT'):
            self.store.prepare_selection(second, selection(1), expected=replace(selected_a.snapshot))
        with self.assertRaisesRegex(module.ProtectedBundleError, 'EXPECTED_CHANGED'):
            self.store.prepare_selection(second, selection(0), expected=None)
        intent_b = self.store.prepare_selection(second, selection(1), expected=selected_a.snapshot)
        selected_b = self.store.select(intent_b)
        third, _ = self.staged('cmd.c', 2)
        with self.assertRaisesRegex(module.ProtectedBundleError, 'EXPECTED_CHANGED'):
            self.store.prepare_selection(third, selection(1), expected=selected_a.snapshot)
        self.assertIs(self.store.inspect_selection(), selected_b.snapshot)

    def test_wrong_owner_and_intent_value_tampering_reject_before_effect(self):
        receipt, _ = self.staged()
        other = self.new_store(self.new_files())
        with self.assertRaisesRegex(module.ProtectedBundleError, 'REGISTERED_OBJECT'):
            other.prepare_selection(receipt, selection(0), expected=None)
        intent = self.store.prepare_selection(receipt, selection(0), expected=None)
        original = intent.source_bytes
        object.__setattr__(intent, 'source_bytes', original + b' ')
        with self.assertRaisesRegex(module.ProtectedBundleError, 'REGISTERED_OBJECT_CHANGED'):
            self.store.select(intent)
        self.assertNotIn('active.json', self.entries())
        object.__setattr__(intent, 'source_bytes', original)
        result = self.store.select(intent)
        original_snapshot = result.snapshot
        object.__setattr__(result, 'snapshot', replace(original_snapshot))
        with self.assertRaisesRegex(module.ProtectedBundleError, 'REGISTERED_SNAPSHOT'):
            self.store.lookup_selection('cmd.a')
        object.__setattr__(result, 'snapshot', original_snapshot)
        self.assertIs(self.store.lookup_selection('cmd.a'), result)

    def test_changed_selection_under_same_command_conflicts_without_effect(self):
        receipt, _ = self.staged()
        intent = self.store.prepare_selection(receipt, selection(0), expected=None)
        changed = selection(0); changed['identity'] = 'sha256:' + 'f' * 64
        with self.assertRaisesRegex(module.ProtectedBundleError, 'COMMAND_CONFLICT'):
            self.store.prepare_selection(receipt, changed, expected=None)
        self.assertNotIn('active.json', self.entries())
        self.assertIsNotNone(self.store.select(intent))

    def test_closed_selector_schema_types_hashes_and_canonical_bytes(self):
        receipt, _ = self.staged()
        intent = self.store.prepare_selection(receipt, selection(0), expected=None)
        original = module.parse_json(intent.source_bytes)
        variants = []
        for field, value in (('schema', 'unknown'), ('command_id', '../bad'), ('descriptor_sha256', '0' * 64)):
            bad = copy.deepcopy(original); bad[field] = value; variants.append(bad)
        for value in (True, -1, 1.5):
            bad = copy.deepcopy(original); bad['selection']['generation'] = value; variants.append(bad)
        bad = copy.deepcopy(original); bad['selection']['identity'] = '0' * 64; variants.append(bad)
        bad = copy.deepcopy(original); bad['extra'] = True; variants.append(bad)
        bad = copy.deepcopy(original); bad['selection']['generation'] = 1; variants.append(bad)
        bad = copy.deepcopy(original); bad['parent_selection'] = selection(0); variants.append(bad)
        bad = copy.deepcopy(original); bad['descriptor']['root_identity']['file_id'] = '0' * 32; variants.append(bad)
        for index, value in enumerate(variants):
            with self.subTest(variant=index):
                with self.assertRaises(module.ProtectedBundleError):
                    self.store._parse_selector(module.canonical_bytes(value))
        for raw in (intent.source_bytes + b' ', b'x' * 16385):
            with self.assertRaises(module.ProtectedBundleError):
                self.store._parse_selector(raw)
        with self.assertRaisesRegex(module.ProtectedBundleError, 'SELECTION_INVALID'):
            self.store.prepare_selection(receipt, selection(2**53), expected=None)
        self.assertNotIn('active.json', self.entries())
        self.assertIsNotNone(self.store.select(intent))

    def test_snapshot_json_properties_are_detached(self):
        _, _, _, selected = self.initialize()
        selected.selection['generation'] = 99
        selected.descriptor['manifest']['name'] = '../x'
        self.assertEqual(selected.selection, selection(0))
        self.assertEqual(self.store.inspect_selection().source_bytes, selected.source_bytes)

    def test_native_effect_return_loss_holds_initialization_and_replacement(self):
        for initializing in (True, False):
            owner = self.new_store(self.new_files())
            files = owner._files
            if initializing:
                receipt, _ = self.staged(owner=owner)
                expected, next_selection, method = None, selection(0), 'create_new'
            else:
                _, _, _, selected = self.initialize(owner)
                receipt, _ = self.staged('cmd.b', 1, owner)
                expected, next_selection, method = selected.snapshot, selection(1), 'atomic_replace'
            intent = owner.prepare_selection(receipt, next_selection, expected=expected)
            native = getattr(files, method)
            def lose_return(*args, **kwargs):
                native(*args, **kwargs)
                raise OSError('after native selector effect, before returned version')
            with mock.patch.object(files, method, side_effect=lose_return) as call:
                with self.assertRaises(module.ProtectedBundleError) as caught:
                    owner.select(intent)
                self.assertTrue(caught.exception.outcome_unknown)
                self.assertIs(caught.exception.cleanup_owner, owner)
                with self.assertRaisesRegex(module.ProtectedBundleError, 'HELD'):
                    owner.select(intent)
                self.assertEqual(call.call_count, 1)
            attempt, = owner.selection_snapshot()[-1:]
            self.assertEqual((attempt.status, attempt.attempted_writes, attempt.returned_version), ('UNKNOWN', 1, None))
            self.assertIn('active.json', self.entries(files))

    def test_post_effect_barrier_and_complete_bundle_readback_failures_hold(self):
        for cut in ('barrier', 'bundle_readback', 'selector_readback'):
            owner = self.new_store(self.new_files()); files = owner._files
            receipt, _ = self.staged(owner=owner)
            intent = owner.prepare_selection(receipt, selection(0), expected=None)
            native = files.confirm_barrier
            def fail(name, version):
                native(name, version)
                if cut == 'barrier':
                    raise OSError('after actual selector barrier')
                target = 'active.json' if cut == 'selector_readback' else receipt.files[0][1]
                (files.root / target).write_bytes(b'changed after actual selector barrier')
            with mock.patch.object(files, 'confirm_barrier', side_effect=fail):
                with self.assertRaisesRegex(module.ProtectedBundleError, 'SELECTION_UNKNOWN') as caught:
                    owner.select(intent)
            self.assertTrue(caught.exception.outcome_unknown)
            attempt, = owner.selection_snapshot()
            self.assertEqual((attempt.status, attempt.attempted_writes), ('UNKNOWN', 1))
            self.assertIsNotNone(attempt.returned_version)
            with self.assertRaisesRegex(module.ProtectedBundleError, 'HELD'):
                owner.lookup_selection('cmd.a')

    def test_external_selector_change_before_cas_is_detected_without_second_write(self):
        _, _, _, selected = self.initialize()
        receipt, _ = self.staged('cmd.b', 1)
        intent = self.store.prepare_selection(receipt, selection(1), expected=selected.snapshot)
        (self.files.root / 'active.json').write_bytes(b'tampered')
        with mock.patch.object(self.files, 'atomic_replace', wraps=self.files.atomic_replace) as cas:
            with self.assertRaisesRegex(module.ProtectedBundleError, 'SELECTION_UNKNOWN') as caught:
                self.store.select(intent)
            self.assertEqual(cas.call_count, 0)
        self.assertFalse(caught.exception.outcome_unknown)
        self.assertEqual(self.store.selection_snapshot()[-1].attempted_writes, 0)

    def test_cancel_unused_intent_retains_tombstone_and_releases_reservation(self):
        intent = self.store.prepare('cmd.cancel', self.bundle)
        with mock.patch.object(self.files, 'create_new', wraps=self.files.create_new) as create:
            canceled = self.store.cancel_unused_prepare(intent)
            self.assertIs(self.store.cancel_unused_prepare(intent), canceled)
            self.assertEqual(create.call_count, 0)
        attempt, = self.store.snapshot()
        self.assertEqual((attempt.status, attempt.reserved_files, attempt.reserved_bytes), ('CANCELED_NO_WRITES', 0, 0))
        self.assertEqual(attempt.names, intent.names)
        self.assertFalse(canceled.public_ack)
        with self.assertRaisesRegex(module.ProtectedBundleError, 'CANCELED'):
            self.store.stage(intent)
        with self.assertRaisesRegex(module.ProtectedBundleError, 'CANCELED'):
            self.store.prepare('cmd.cancel', self.bundle)
        with self.assertRaisesRegex(module.ProtectedBundleError, 'REGISTERED_OBJECT'):
            self.store.cancel_unused_prepare(replace(intent))
        self.assertIsNone(self.store.lookup('cmd.cancel'))
        second = self.store.prepare('cmd.next', self.bundle)
        self.assertTrue(set(dict(intent.names).values()).isdisjoint(dict(second.names).values()))
        self.assertIsNotNone(self.store.stage(second))

    def test_canceled_ids_and_names_stay_bounded_and_unavailable(self):
        for index in range(module.MAX_ATTEMPTS):
            self.store.cancel_unused_prepare(self.store.prepare('cmd.cancel.%d' % index, self.bundle))
        with self.assertRaisesRegex(module.ProtectedBundleError, 'ATTEMPT_LIMIT'):
            self.store.prepare('cmd.overflow', self.bundle)
        self.assertEqual(len(self.store.snapshot()), 64)
        self.assertEqual(self.entries(), set())

    def test_cancellation_rejects_changed_payload_and_tombstoned_name_reuse(self):
        intent = self.store.prepare('cmd.cancel', self.bundle)
        self.store.cancel_unused_prepare(intent)
        changed_files = dict(self.bundle.files); changed_files[codec.SCRIPT_PATH] += b'changed\n'
        changed = codec.create_bundle(changed_files, scene_revision=self.bundle.scene_revision,
                                      engine_sha256=self.bundle.engine_sha256)
        with self.assertRaisesRegex(module.ProtectedBundleError, 'COMMAND_CONFLICT'):
            self.store.prepare('cmd.cancel', changed)
        with mock.patch.object(module.uuid, 'uuid4', return_value=base.uuid.UUID(hex=intent.names[0][1][4:])):
            with self.assertRaisesRegex(module.ProtectedBundleError, 'NAME_COLLISION'):
                self.store.prepare('cmd.collision', self.bundle)
        self.assertEqual(self.entries(), set())

    def test_cancel_after_stage_or_started_failure_never_releases_objects(self):
        intent = self.store.prepare('cmd.complete', self.bundle)
        self.store.stage(intent)
        with self.assertRaisesRegex(module.ProtectedBundleError, 'CANCEL_NOT_UNUSED'):
            self.store.cancel_unused_prepare(intent)
        files = self.new_files(); owner = self.new_store(files)
        intent = owner.prepare('cmd.started', self.bundle)
        native = files.create_new
        def lost(name, raw):
            native(name, raw)
            raise OSError('unreturned file')
        with mock.patch.object(files, 'create_new', side_effect=lost):
            with self.assertRaisesRegex(module.ProtectedBundleError, 'STAGE_UNKNOWN'):
                owner.stage(intent)
        with self.assertRaisesRegex(module.ProtectedBundleError, 'HELD'):
            owner.cancel_unused_prepare(intent)
        attempt, = owner.snapshot()
        self.assertEqual((attempt.reserved_files, attempt.attempted_writes), (12, 1))

    def test_unexpected_planned_file_blocks_cancellation_and_retains_owner(self):
        intent = self.store.prepare('cmd.cancel', self.bundle)
        self.files.create_new(intent.names[0][1], b'ownership violation')
        with self.assertRaisesRegex(module.ProtectedBundleError, 'CANCEL_UNVERIFIED') as caught:
            self.store.cancel_unused_prepare(intent)
        self.assertIs(caught.exception.cleanup_owner, self.store)
        self.assertEqual(self.store.snapshot()[0].status, 'UNKNOWN')
        self.assertEqual(self.store.snapshot()[0].reserved_files, 12)

    def test_close_failure_retains_selector_attempt_and_cleanup_owner(self):
        self.initialize()
        with mock.patch.object(self.files, 'close', side_effect=OSError('injected close failure')):
            with self.assertRaises(module.ProtectedBundleError) as caught:
                self.store.close()
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertIs(caught.exception.cleanup_owner, self.store)
        self.assertEqual(self.store.selection_snapshot()[0].status, 'UNKNOWN')
        self.store.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
