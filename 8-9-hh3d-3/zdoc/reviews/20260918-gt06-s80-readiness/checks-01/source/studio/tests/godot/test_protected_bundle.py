"""Focused actual Windows immutable-bundle storage tests; no Godot or Docker."""
from dataclasses import FrozenInstanceError, replace
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock
import uuid

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
SPEC = importlib.util.spec_from_file_location('gt03_protected_bundle_tests', STUDIO/'godot-addon/protected_bundle.py')
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)
codec = module.bundle_codec
from studio.host.core.safe_replace import ProtectedFileRoot, SafeReplaceError


def synthetic_bundle(*, scene_size=None):
    # These bytes test storage only, not profile eligibility or engine behavior.
    files = {path: b'# synthetic protected-bundle fixture\n' for path in codec.PATHS}
    for index, path in enumerate(codec.PATHS):
        if path.endswith('.uid'):
            files[path] = ('uid://synthetic' + str(index) + '\n').encode()
    files[codec.SCENE_PATH] = b'[gd_scene format=3]\n' if scene_size is None else b'x' * scene_size
    files[codec.SCRIPT_PATH] = b'extends Node3D\n'
    return codec.create_bundle(files, scene_revision='sha256:' + '1' * 64, engine_sha256='2' * 64)


class ModuleTests(unittest.TestCase):
    def test_factory_and_historical_stager_use_identical_source_bound_codec(self):
        self.assertIs(codec, module.fixture_profile.staging.bundle_codec)
        self.assertEqual(codec._bundle_source_sha256,
                         hashlib.sha256((STUDIO/'godot-addon/bundle_v2.py').read_bytes()).hexdigest())

    def test_exact_native_owner_required(self):
        with self.assertRaisesRegex(module.ProtectedBundleError, 'EXACT_ROOT_REQUIRED'):
            module.ProtectedBundleStore(object())


@unittest.skipUnless(os.name == 'nt', 'actual Windows NTFS ProtectedFileRoot required')
class ProtectedBundleNativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hh-gt03-protected-bundle-')
        self.base = Path(self.temp.name).resolve()
        self.unowned, self.owners = [], []
        self.addCleanup(self.cleanup)
        self.files = self.new_files()
        self.store = self.new_store(self.files)
        self.bundle = synthetic_bundle()

    def new_files(self):
        try:
            files = ProtectedFileRoot.create(self.base)
        except SafeReplaceError as error:
            if error.cleanup_owner is not None:
                self.unowned.append(error.cleanup_owner)
            raise
        self.unowned.append(files)
        self.assertEqual(files.root.parent, self.base)
        return files

    def new_store(self, files):
        store = module.ProtectedBundleStore(files)
        self.unowned.remove(files)
        self.owners.append(store)
        return store

    def cleanup(self):
        for store in reversed(self.owners):
            store.close()
        for files in reversed(self.unowned):
            files.close()
        # Verify the recursive TemporaryDirectory cleanup target is its exact
        # originally captured absolute root before invoking that owned cleanup.
        self.assertEqual(Path(self.temp.name).resolve(), self.base)
        self.temp.cleanup()

    def entries(self, files=None):
        return {p.name for p in (files or self.files).root.iterdir() if p.name != '.writer'}

    def staged(self, store=None, command='cmd.bundle'):
        owner = store or self.store
        return owner.stage(owner.prepare(command, self.bundle))

    def test_prepare_is_write_free_registered_immutable_and_has_all_names(self):
        before = self.entries()
        with mock.patch.object(self.files, 'create_new', wraps=self.files.create_new) as create:
            intent = self.store.prepare('cmd.prepare', self.bundle)
            self.assertEqual(create.call_count, 0)
        self.assertEqual(self.entries(), before)
        self.assertEqual(tuple(dict(intent.names)), (*codec.PATHS, '@manifest'))
        self.assertEqual(len(set(dict(intent.names).values())), 12)
        for _, name in intent.names:
            self.assertRegex(name, r'^obj-[0-9a-f]{32}$')
        self.assertIs(self.store.prepare('cmd.prepare', self.bundle), intent)
        self.assertIsNone(self.store.lookup('cmd.prepare'))
        self.assertEqual(self.store.snapshot()[0].status, 'PREPARED')
        with self.assertRaises(FrozenInstanceError):
            intent.command_id = 'changed'
        with self.assertRaisesRegex(module.ProtectedBundleError, 'PENDING'):
            self.store.prepare('cmd.second', self.bundle)

    def test_manifest_last_real_final_barrier_complete_readback_and_exact_retry(self):
        intent = self.store.prepare('cmd.actual', self.bundle)
        calls = []
        native_create, native_barrier = self.files.create_new, self.files.confirm_barrier
        def create(name, raw):
            calls.append(('create', name))
            return native_create(name, raw)
        def barrier(name, version):
            calls.append(('barrier', name))
            self.assertEqual(len(self.entries()), 12)
            return native_barrier(name, version)
        with mock.patch.object(self.files, 'create_new', side_effect=create), \
             mock.patch.object(self.files, 'confirm_barrier', side_effect=barrier):
            receipt = self.store.stage(intent)
            self.assertIs(self.store.stage(intent), receipt)
        self.assertEqual(calls, [('create', name) for _, name in intent.names] + [('barrier', intent.names[-1][1])])
        self.assertEqual(self.store.readback(receipt), self.bundle)
        self.assertIs(self.store.lookup('cmd.actual', self.bundle.project_revision), receipt)
        self.assertTrue(receipt.namespace_durability_verified)
        self.assertFalse(receipt.public_ack)
        self.assertFalse(receipt.engine_effects_verified)
        self.assertEqual(len(self.entries()), 12)
        with self.assertRaises(FrozenInstanceError):
            receipt.public_ack = True

    def test_copied_foreign_intents_and_receipts_rejected_without_holding(self):
        intent = self.store.prepare('cmd.original', self.bundle)
        other_files = self.new_files()
        other = self.new_store(other_files)
        for owner, value in ((self.store, replace(intent)), (other, intent)):
            with self.assertRaisesRegex(module.ProtectedBundleError, 'REGISTERED_OBJECT'):
                owner.stage(value)
        receipt = self.store.stage(intent)
        for owner, value in ((self.store, replace(receipt)), (other, receipt)):
            with self.assertRaisesRegex(module.ProtectedBundleError, 'REGISTERED_OBJECT'):
                owner.readback(value)
        self.assertEqual(other.snapshot(), ())
        self.assertIs(self.store.lookup('cmd.original'), receipt)

    def test_second_owner_and_inert_consumer_marker_are_not_bypassed(self):
        with self.assertRaisesRegex(module.ProtectedBundleError, 'ALREADY_OWNED'):
            module.ProtectedBundleStore(self.files)
        files = self.new_files()
        files._fixture_file_consumer = object()
        with self.assertRaisesRegex(module.ProtectedBundleError, 'ALREADY_OWNED'):
            module.ProtectedBundleStore(files)
        del files._fixture_file_consumer
        self.new_store(files)

    def test_conflicting_same_command_does_not_destroy_existing_receipt(self):
        receipt = self.staged()
        changed = codec.replace_script(self.bundle, b'extends Node3D\n# different\n',
            expected_project_revision=self.bundle.project_revision,
            expected_script_sha256=self.bundle.script_sha256, expected_uid_sha256=self.bundle.uid_sha256)
        with self.assertRaisesRegex(module.ProtectedBundleError, 'COMMAND_CONFLICT'):
            self.store.prepare('cmd.bundle', changed)
        with self.assertRaisesRegex(module.ProtectedBundleError, 'COMMAND_CONFLICT'):
            self.store.lookup('cmd.bundle', changed.project_revision)
        self.assertIs(self.store.lookup('cmd.bundle'), receipt)

    def test_lookalike_codec_instance_is_rejected_before_native_writes(self):
        spec = importlib.util.spec_from_file_location('gt03_protected_foreign_codec', STUDIO/'godot-addon/bundle_v2.py')
        foreign = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = foreign
        spec.loader.exec_module(foreign)
        value = foreign.decode_bundle(self.bundle.manifest_bytes, self.bundle.files)
        with self.assertRaisesRegex(module.ProtectedBundleError, 'EXACT_CODEC_REQUIRED'):
            self.store.prepare('cmd.foreign', value)
        self.assertEqual(self.entries(), set())

    def test_registered_object_value_tamper_cannot_change_plan_or_descriptor(self):
        intent = self.store.prepare('cmd.tampered', self.bundle)
        original = intent.names
        object.__setattr__(intent, 'names', tuple(reversed(original)))
        with self.assertRaisesRegex(module.ProtectedBundleError, 'REGISTERED_OBJECT_CHANGED'):
            self.store.stage(intent)
        self.assertEqual(self.entries(), set())
        object.__setattr__(intent, 'names', original)
        receipt = self.store.stage(intent)
        object.__setattr__(receipt, 'project_revision', 'sha256:' + '0' * 64)
        with self.assertRaisesRegex(module.ProtectedBundleError, 'REGISTERED_OBJECT_CHANGED'):
            self.store.descriptor(receipt)

    def test_changed_existing_orphan_is_detected_by_complete_inventory(self):
        files = self.new_files()
        name = 'obj-' + uuid.uuid4().hex
        files.create_new(name, b'orphan')
        owner = self.new_store(files)
        receipt = self.staged(owner)
        (files.root/name).write_bytes(b'changed orphan')
        with self.assertRaisesRegex(module.ProtectedBundleError, 'READBACK_UNVERIFIED'):
            owner.readback(receipt)

    def test_later_registered_bundle_does_not_invalidate_prior_readback(self):
        first = self.staged(command='cmd.first')
        second = self.staged(command='cmd.second')
        self.assertEqual(self.store.readback(first), self.bundle)
        self.assertEqual(self.store.readback(second), self.bundle)
        self.assertEqual(len(self.entries()), 24)

    def test_selector_and_orphans_count_toward_reserved_headroom(self):
        files = self.new_files()
        files.create_new('active.json', b'a' * 16384)
        for _ in range(49):
            files.create_new('obj-' + uuid.uuid4().hex, b'orphan')
        owner = self.new_store(files)
        receipt = self.staged(owner)
        self.assertEqual(len(self.entries(files)), 62)
        self.assertEqual(owner.readback(receipt), self.bundle)
        with self.assertRaisesRegex(module.ProtectedBundleError, 'QUOTA'):
            owner.prepare('cmd.next', self.bundle)
        self.assertIs(owner.lookup('cmd.bundle'), receipt)

    def test_count_and_byte_reservations_reject_before_any_write(self):
        for mode in ('count', 'bytes'):
            with self.subTest(mode=mode):
                files = self.new_files()
                for _ in range(51 if mode == 'count' else 7):
                    files.create_new('obj-' + uuid.uuid4().hex, b'x' * (1 if mode == 'count' else 1024 * 1024))
                owner = self.new_store(files)
                candidate = self.bundle if mode == 'count' else synthetic_bundle(scene_size=1024 * 1024 - 1024)
                with mock.patch.object(files, 'create_new', wraps=files.create_new) as create:
                    with self.assertRaisesRegex(module.ProtectedBundleError, 'QUOTA'):
                        owner.prepare('cmd.quota', candidate)
                    self.assertEqual(create.call_count, 0)
                self.assertEqual(owner.snapshot(), ())
                self.assertIsNone(owner.lookup('cmd.quota'))

    def test_unknown_names_and_oversized_selector_fail_constructor_without_transfer(self):
        for name, raw in (('unexpected', b'x'), ('active.json', b'x' * 16385)):
            files = self.new_files()
            files.create_new(name, raw)
            with self.assertRaisesRegex(module.ProtectedBundleError, 'INVENTORY_INVALID'):
                module.ProtectedBundleStore(files)
            self.assertIsNone(getattr(files, module._MARKER, None))

    def test_external_generated_name_after_prepare_is_not_silently_adopted(self):
        intent = self.store.prepare('cmd.inventory', self.bundle)
        # Deliberate same-account ownership violation to model external change.
        self.files.create_new('obj-' + uuid.uuid4().hex, b'unknown')
        with mock.patch.object(self.files, 'create_new', wraps=self.files.create_new) as create:
            with self.assertRaisesRegex(module.ProtectedBundleError, 'STAGE_UNKNOWN'):
                self.store.stage(intent)
            self.assertEqual(create.call_count, 0)
        self.assertEqual(self.store.snapshot()[0].status, 'UNKNOWN')

    def test_unreturned_native_write_at_first_middle_and_manifest_holds_without_retry(self):
        for cut in (1, 6, 12):
            with self.subTest(cut=cut):
                files = self.new_files()
                owner = self.new_store(files)
                intent = owner.prepare('cmd.cut', self.bundle)
                original, calls = files.create_new, []
                def fail(name, raw):
                    calls.append(name)
                    result = original(name, raw)
                    if len(calls) == cut:
                        raise OSError('injected after native write')
                    return result
                with mock.patch.object(files, 'create_new', side_effect=fail):
                    with self.assertRaises(module.ProtectedBundleError) as caught:
                        owner.stage(intent)
                    self.assertTrue(caught.exception.outcome_unknown)
                    self.assertIs(caught.exception.cleanup_owner, owner)
                    with self.assertRaisesRegex(module.ProtectedBundleError, 'HELD'):
                        owner.stage(intent)
                attempt, = owner.snapshot()
                self.assertEqual((attempt.status, attempt.attempted_writes, len(attempt.versions)), ('UNKNOWN', cut, cut - 1))
                self.assertEqual(self.entries(files), set(dict(intent.names).values()) if cut == 12 else set(calls))

    def test_final_barrier_failure_and_post_barrier_read_failure_never_issue_receipt(self):
        for phase in ('barrier', 'readback'):
            files = self.new_files()
            owner = self.new_store(files)
            intent = owner.prepare('cmd.barrier', self.bundle)
            original = files.confirm_barrier
            def barrier(name, version):
                original(name, version)
                if phase == 'barrier':
                    raise OSError('injected after real barrier')
                target = dict(intent.names)[codec.SCRIPT_PATH]
                (files.root/target).write_bytes(b'changed after real barrier')
            with mock.patch.object(files, 'confirm_barrier', side_effect=barrier):
                with self.assertRaisesRegex(module.ProtectedBundleError, 'STAGE_UNKNOWN'):
                    owner.stage(intent)
            attempt, = owner.snapshot()
            self.assertEqual((attempt.status, attempt.attempted_writes, len(attempt.versions)), ('UNKNOWN', 12, 12))

    def test_descriptor_is_detached_and_reopen_is_readonly_without_registered_authority(self):
        receipt = self.staged()
        descriptor = self.store.descriptor(receipt)
        self.assertEqual(set(descriptor), {'root_identity', 'project_revision', 'files', 'manifest'})
        self.assertEqual(set(descriptor['files']), set(codec.PATHS))
        dirty = copy.deepcopy(descriptor)
        dirty['files'][codec.SCRIPT_PATH]['sha256'] = '0' * 64
        self.assertEqual(self.store.descriptor(receipt), descriptor)
        root, identity = self.store.root, self.store.root_identity
        self.store.close()
        native = ProtectedFileRoot.reopen_readonly(root, identity)
        self.unowned.append(native)
        reopened = self.new_store(native)
        self.assertTrue(reopened.readonly)
        self.assertEqual(reopened.read_descriptor(descriptor), self.bundle)
        self.assertEqual(reopened.snapshot(), ())
        self.assertIsNone(reopened.lookup(receipt.command_id))
        with self.assertRaisesRegex(module.ProtectedBundleError, 'READONLY'):
            reopened.prepare('cmd.reopened', self.bundle)
        with self.assertRaisesRegex(module.ProtectedBundleError, 'REGISTERED_OBJECT'):
            reopened.readback(receipt)
        self.assertTrue(native._readonly)
        with self.assertRaisesRegex(module.ProtectedBundleError, 'DESCRIPTOR_UNVERIFIED'):
            reopened.read_descriptor(dirty)

    def test_malformed_descriptor_rejects_before_reads_and_does_not_hold(self):
        receipt = self.staged()
        descriptor = self.store.descriptor(receipt)
        variants = []
        for key, value in (('name', '../outside'), ('volume', True), ('file_id', 'x'),
                           ('size_bytes', True), ('sha256', 'x')):
            bad = copy.deepcopy(descriptor)
            bad['files'][codec.SCRIPT_PATH][key] = value
            variants.append(bad)
        bad = copy.deepcopy(descriptor); bad['manifest']['name'] = bad['files'][codec.SCRIPT_PATH]['name']; variants.append(bad)
        bad = copy.deepcopy(descriptor); bad['root_identity']['file_id'] = '0' * 32; variants.append(bad)
        bad = copy.deepcopy(descriptor); bad['files']['unknown'] = bad['manifest']; variants.append(bad)
        for bad in variants:
            with mock.patch.object(self.files, 'read', wraps=self.files.read) as read:
                with self.assertRaises(module.ProtectedBundleError):
                    self.store.read_descriptor(bad)
                self.assertEqual(read.call_count, 0)
        self.assertEqual(self.store.readback(receipt), self.bundle)

    def test_changed_native_bytes_including_orphan_invalidate_registered_readback(self):
        for target in (codec.SCRIPT_PATH, codec.UID_PATH, '@manifest'):
            files = self.new_files(); owner = self.new_store(files)
            receipt = self.staged(owner)
            name = receipt.manifest[0] if target == '@manifest' else {p: n for p, n, _ in receipt.files}[target]
            (files.root/name).write_bytes(b'tampered')
            with self.assertRaisesRegex(module.ProtectedBundleError, 'READBACK_UNVERIFIED'):
                owner.readback(receipt)
            self.assertEqual(owner.snapshot()[0].status, 'UNKNOWN')

    def test_close_failure_preserves_owner_and_attempts_for_retry(self):
        self.staged()
        with mock.patch.object(self.files, 'close', side_effect=OSError('injected close failure')):
            with self.assertRaises(module.ProtectedBundleError) as caught:
                self.store.close()
        self.assertIs(caught.exception.cleanup_owner, self.store)
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertEqual(self.store.snapshot()[0].status, 'UNKNOWN')
        self.assertIs(getattr(self.files, module._MARKER), self.store)
        self.store.close()
        self.assertIsNone(getattr(self.files, module._MARKER))

    def test_concurrent_same_intent_stages_once(self):
        intent = self.store.prepare('cmd.concurrent', self.bundle)
        barrier, replies, errors = threading.Barrier(3), [], []
        def worker():
            try:
                barrier.wait(timeout=5)
                replies.append(self.store.stage(intent))
            except BaseException as error:
                errors.append(error)
        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads: thread.start()
        barrier.wait(timeout=5)
        for thread in threads:
            thread.join(timeout=30)
            self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(replies), 2)
        self.assertIs(replies[0], replies[1])
        self.assertEqual(len(self.entries()), 12)


if __name__ == '__main__':
    unittest.main(verbosity=2)
