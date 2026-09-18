"""Actual Windows protected-store tests with SYNTHETIC source and no engine."""
from dataclasses import replace
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
SPEC = importlib.util.spec_from_file_location('gt03_test_bundle_staging', STUDIO/'godot-addon/bundle_staging.py')
staging = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = staging
SPEC.loader.exec_module(staging)
codec = staging.bundle_codec
from studio.host.core.private_store import PrivateBlobStore, PrivateStoreError, StagedBlob
from studio.host.core.safe_open import FileIdentity
from studio.host.core.limits import SafetyViolation


def synthetic_bundle(*, scene_size=None):
    """Explicit synthetic values, never imported UID/release/engine evidence."""
    files = {path: b'# SYNTHETIC staging test only\n' for path in codec.PATHS}
    for index, path in enumerate(codec.PATHS):
        if path.endswith('.uid'):
            files[path] = ('uid://synthetic' + str(index) + '\n').encode()
    files[codec.SCENE_PATH] = b'[gd_scene format=3]\n' if scene_size is None else b'a' * scene_size
    files[codec.SCRIPT_PATH] = b'extends Node3D\n'
    return codec.create_bundle(files, scene_revision='sha256:' + hashlib.sha256(b'synthetic scene').hexdigest(),
                               engine_sha256=hashlib.sha256(b'synthetic engine, not executed').hexdigest())


class StagingModuleTests(unittest.TestCase):
    def test_codec_loaded_from_exact_sibling_bytes(self):
        self.assertEqual(Path(codec.__file__).resolve(), (STUDIO/'godot-addon/bundle_v2.py').resolve())
        self.assertEqual(codec._bundle_source_sha256,
                         hashlib.sha256((STUDIO/'godot-addon/bundle_v2.py').read_bytes()).hexdigest())
        with tempfile.TemporaryDirectory(prefix='hh-gt03-codec-binding-') as name:
            folder = Path(name)
            (folder/'bundle_staging.py').write_bytes((STUDIO/'godot-addon/bundle_staging.py').read_bytes())
            (folder/'bundle_v2.py').write_bytes((STUDIO/'godot-addon/bundle_v2.py').read_bytes() + b'\nCOPY_MARKER = True\n')
            spec = importlib.util.spec_from_file_location('gt03_staging_other_snapshot', folder/'bundle_staging.py')
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            self.assertIsNot(module.bundle_codec, codec)
            self.assertTrue(module.bundle_codec.COPY_MARKER)
            self.assertFalse(hasattr(codec, 'COPY_MARKER'))

    def test_no_duck_typed_store(self):
        with self.assertRaises(staging.BundleStagingError):
            staging.BundleStager(object())


@unittest.skipUnless(os.name == 'nt', 'requires actual Windows NTFS native protected store')
class BundleStagingNativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hh-gt03-bundle-staging-')
        self.base = Path(self.temp.name).resolve()
        self.stores, self.owners = [], []
        self.addCleanup(self.cleanup)
        self.store = self.new_store()
        self.owner = self.new_owner(self.store)
        self.bundle = synthetic_bundle()

    def new_store(self):
        try:
            store = PrivateBlobStore.create(self.base)
        except PrivateStoreError as exc:
            if exc.cleanup_owner is not None:
                self.stores.append(exc.cleanup_owner)
            if exc.cleanup_api is not None:
                self.addCleanup(exc.cleanup_api.close_owned)
            raise
        self.assertEqual(store.root.parent, self.base)
        self.stores.append(store)
        return store

    def new_owner(self, store):
        owner = staging.BundleStager(store)
        self.owners.append(owner)
        return owner

    def cleanup(self):
        # Close failure is a real test failure and must not discard cleanup
        # ownership. Native close() retains its registry for retry.
        for owner in reversed(self.owners):
            owner.close()
        for store in reversed(self.stores):
            store.close()
        self.assertEqual(Path(self.temp.name).resolve(), self.base)
        self.temp.cleanup()

    def native_blob_count(self, store=None):
        return len([path for path in (store or self.store).root.iterdir() if path.name != '.writer'])

    def test_stage_actual_twelve_blobs_readback_retry_and_no_public_claim(self):
        receipt = self.owner.stage('cmd.stage', self.bundle)
        self.assertEqual(self.native_blob_count(), 12)
        self.assertEqual(len(receipt.files), 11)
        self.assertIs(self.owner.lookup('cmd.stage', self.bundle.project_revision), receipt)
        self.assertIs(self.owner.stage('cmd.stage', codec.decode_bundle(
            self.bundle.manifest_bytes, self.bundle.files)), receipt)
        self.assertEqual(self.native_blob_count(), 12)
        result = self.owner.readback(receipt)
        self.assertEqual(result.files, self.bundle.files)
        self.assertEqual(result.manifest_bytes, self.bundle.manifest_bytes)
        for path, descriptor in receipt.files:
            self.assertIs(type(descriptor), StagedBlob)
            self.assertEqual(descriptor.identity.size, len(self.bundle.files[path]))
            self.assertEqual(descriptor.sha256, hashlib.sha256(self.bundle.files[path]).hexdigest())
        self.assertFalse(receipt.public_ack)
        self.assertFalse(receipt.engine_effects_verified)
        self.assertFalse(receipt.namespace_durability_verified)
        attempt, = self.owner.snapshot()
        self.assertEqual(attempt.reserved_objects, 12)
        self.assertEqual(attempt.reserved_bytes, len(self.bundle.manifest_bytes) + sum(map(len, self.bundle.files.values())))
        self.assertEqual(attempt.attempted_puts, 12)

    def test_changed_same_id_is_no_effect_conflict_and_original_remains_available(self):
        receipt = self.owner.stage('cmd.same', self.bundle)
        other = codec.replace_script(self.bundle, b'extends Node3D\n# changed\n',
            expected_project_revision=self.bundle.project_revision,
            expected_script_sha256=self.bundle.script_sha256, expected_uid_sha256=self.bundle.uid_sha256)
        with mock.patch.object(self.store, 'put_bytes', wraps=self.store.put_bytes) as put:
            with self.assertRaisesRegex(staging.BundleStagingError, 'BUNDLE_STAGE_COMMAND_CONFLICT'):
                self.owner.stage('cmd.same', other)
            with self.assertRaisesRegex(staging.BundleStagingError, 'BUNDLE_STAGE_COMMAND_CONFLICT'):
                self.owner.lookup('cmd.same', other.project_revision)
            self.assertEqual(put.call_count, 0)
        self.assertIs(self.owner.lookup('cmd.same'), receipt)
        self.assertEqual(self.owner.readback(receipt), self.bundle)
        self.assertEqual(self.native_blob_count(), 12)
        self.assertIsNone(self.owner.lookup('cmd.absent'))

    def test_forged_receipt_copy_wrong_command_and_other_owner_reject_before_io(self):
        receipt = self.owner.stage('cmd.receipt', self.bundle)
        foreign = self.new_owner(self.new_store())
        with mock.patch.object(self.store, 'read_blob', wraps=self.store.read_blob) as read:
            for fake in (replace(receipt), replace(receipt, command_id='cmd.fake'),
                         replace(receipt, project_revision='sha256:' + '0' * 64),
                         replace(receipt, manifest=replace(receipt.manifest, sha256='0' * 64))):
                with self.subTest(fake=fake.command_id), self.assertRaises(staging.BundleStagingError):
                    self.owner.readback(fake)
            self.assertEqual(read.call_count, 0)
        with self.assertRaises(staging.BundleStagingError):
            foreign.readback(receipt)
        self.assertEqual(self.owner.readback(receipt), self.bundle)

    def test_exact_native_type_and_one_lifecycle_owner_even_across_module_loads(self):
        with self.assertRaisesRegex(staging.BundleStagingError, 'ALREADY_OWNED'):
            staging.BundleStager(self.store)
        spec = importlib.util.spec_from_file_location('gt03_staging_second_import', STUDIO/'godot-addon/bundle_staging.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        with self.assertRaisesRegex(module.BundleStagingError, 'ALREADY_OWNED'):
            module.BundleStager(self.store)

    def test_invalid_command_or_foreign_codec_instance_has_no_effect(self):
        for command in ('', '../bad', 'x' * 129, True):
            with self.subTest(command=command), self.assertRaises(staging.BundleStagingError):
                self.owner.stage(command, self.bundle)
        spec = importlib.util.spec_from_file_location('gt03_independent_codec_class', STUDIO/'godot-addon/bundle_v2.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        foreign = module.decode_bundle(self.bundle.manifest_bytes, self.bundle.files)
        with self.assertRaisesRegex(staging.BundleStagingError, 'EXACT_BUNDLE_REQUIRED'):
            self.owner.stage('cmd.foreign', foreign)
        self.assertEqual(self.native_blob_count(), 0)
        self.assertEqual(self.owner.snapshot(), ())
        self.assertIsNone(self.owner.lookup('cmd.absent'))

    def test_unrecognized_native_inventory_holds_before_put(self):
        # Represents unknown external/native history, not a quota shortfall.
        (self.store.root/'unexpected-entry').write_bytes(b'unknown')
        with mock.patch.object(self.store, 'put_bytes', wraps=self.store.put_bytes) as put:
            with self.assertRaisesRegex(staging.BundleStagingError, 'INVENTORY_UNVERIFIED'):
                self.owner.stage('cmd.inventory', self.bundle)
            self.assertEqual(put.call_count, 0)
        self.assertEqual(self.owner.snapshot(), ())
        with self.assertRaisesRegex(staging.BundleStagingError, 'HELD'):
            self.owner.lookup('cmd.inventory')

    def test_closed_native_owner_is_detected_fresh_and_holds(self):
        self.owner.stage('cmd.closed', self.bundle)
        self.store.close()  # Deliberate ownership violation, not production usage.
        with self.assertRaisesRegex(staging.BundleStagingError, 'OWNER_UNVERIFIED'):
            self.owner.lookup('cmd.closed')
        with self.assertRaisesRegex(staging.BundleStagingError, 'HELD'):
            self.owner.stage('cmd.next', self.bundle)
        self.assertEqual(self.owner.snapshot()[0].status, 'STAGED_BYTES_READ_BACK')

    def test_count_quota_reserves_all_twelve_before_any_put(self):
        # Deliberately preload before transfer to a NEW owner, not through an
        # externally shared store while that owner is live.
        store = self.new_store()
        for _ in range(53):
            store.put_bytes(b'x')
        owner = self.new_owner(store)
        with mock.patch.object(store, 'put_bytes', wraps=store.put_bytes) as put:
            with self.assertRaisesRegex(staging.BundleStagingError, 'BUNDLE_STAGE_QUOTA') as error:
                owner.stage('cmd.full', self.bundle)
            self.assertFalse(error.exception.outcome_unknown)
            self.assertEqual(put.call_count, 0)
        self.assertEqual(self.native_blob_count(store), 53)
        self.assertIsNone(owner.lookup('cmd.full'))
        self.assertEqual(owner.snapshot(), ())

    def test_exact_remaining_twelve_object_slots_are_admitted(self):
        store = self.new_store()
        for _ in range(52):
            store.put_bytes(b'x')
        owner = self.new_owner(store)
        receipt = owner.stage('cmd.last12', self.bundle)
        self.assertEqual(self.native_blob_count(store), 64)
        self.assertEqual(owner.readback(receipt), self.bundle)
        with self.assertRaisesRegex(staging.BundleStagingError, 'BUNDLE_STAGE_QUOTA'):
            owner.stage('cmd.more', self.bundle)
        self.assertIs(owner.lookup('cmd.last12'), receipt)

    def test_byte_quota_reserves_manifest_and_all_files_before_first_put(self):
        store = self.new_store()
        for _ in range(7):
            store.put_bytes(b'x' * (1024 * 1024))
        owner = self.new_owner(store)
        large = synthetic_bundle(scene_size=1024 * 1024)
        with mock.patch.object(store, 'put_bytes', wraps=store.put_bytes) as put:
            with self.assertRaisesRegex(staging.BundleStagingError, 'BUNDLE_STAGE_QUOTA'):
                owner.stage('cmd.toobig', large)
            self.assertEqual(put.call_count, 0)
        # Only scene bytes would fit exactly; UID/trusted/manifest bytes must
        # count too. Known rejection still permits this smaller valid request.
        receipt = owner.stage('cmd.small', self.bundle)
        self.assertEqual(owner.readback(receipt), self.bundle)

    def test_post_put_error_preserves_unreturned_orphan_and_never_retries(self):
        for cut in (1, 6, 12):
            with self.subTest(cut=cut):
                store = self.new_store()
                owner = self.new_owner(store)
                original = store.put_bytes
                calls = 0
                def failing_put(raw):
                    nonlocal calls
                    calls += 1
                    result = original(raw)
                    if calls == cut:
                        raise OSError('injected AFTER actual native put')
                    return result
                with mock.patch.object(store, 'put_bytes', side_effect=failing_put):
                    with self.assertRaises(staging.BundleStagingError) as error:
                        owner.stage('cmd.cut', self.bundle)
                    self.assertTrue(error.exception.outcome_unknown)
                    self.assertIs(error.exception.cleanup_owner, owner)
                    with self.assertRaisesRegex(staging.BundleStagingError, 'HELD'):
                        owner.stage('cmd.cut', self.bundle)
                    self.assertEqual(calls, cut)
                attempt, = owner.snapshot()
                self.assertEqual(attempt.status, 'UNKNOWN')
                self.assertEqual(attempt.reserved_objects, 12)
                self.assertEqual(attempt.attempted_puts, cut)
                self.assertEqual(len(attempt.descriptors), cut - 1)
                self.assertEqual(self.native_blob_count(store), cut)

    def test_post_read_error_holds_at_immediate_and_complete_set_readback(self):
        for cut in (1, 24):
            with self.subTest(cut=cut):
                store = self.new_store()
                owner = self.new_owner(store)
                original = store.read_blob
                calls = 0
                def failing_read(blob):
                    nonlocal calls
                    calls += 1
                    result = original(blob)
                    if calls == cut:
                        raise OSError('injected AFTER actual native read')
                    return result
                with mock.patch.object(store, 'read_blob', side_effect=failing_read):
                    with self.assertRaises(staging.BundleStagingError) as error:
                        owner.stage('cmd.readcut', self.bundle)
                    self.assertTrue(error.exception.outcome_unknown)
                attempt, = owner.snapshot()
                self.assertEqual(attempt.status, 'UNKNOWN')
                self.assertEqual(len(attempt.descriptors), 1 if cut == 1 else 12)
                with self.assertRaisesRegex(staging.BundleStagingError, 'HELD'):
                    owner.lookup('cmd.readcut')

    def test_actual_changed_script_truncated_uid_and_manifest_are_detected(self):
        for target in (codec.SCRIPT_PATH, codec.UID_PATH, staging.MANIFEST_KEY):
            with self.subTest(target=target):
                store = self.new_store()
                owner = self.new_owner(store)
                receipt = owner.stage('cmd.tamper', self.bundle)
                descriptor = receipt.manifest if target == staging.MANIFEST_KEY else dict(receipt.files)[target]
                # Simulates an out-of-boundary same-account change between
                # trusted reads; it is never a publication write path.
                (store.root/descriptor.object_id).write_bytes(b'x' * (descriptor.identity.size - 1))
                with self.assertRaisesRegex(staging.BundleStagingError, 'READBACK_UNVERIFIED'):
                    owner.readback(receipt)
                with self.assertRaisesRegex(staging.BundleStagingError, 'HELD'):
                    owner.stage('cmd.aftertamper', self.bundle)

    def test_native_reopen_full_readback_and_wrong_root_or_identity_fail(self):
        receipt = self.owner.stage('cmd.reopen', self.bundle)
        root, identity = self.store.root, self.store.root_identity
        self.owner.close()
        reopened = PrivateBlobStore.reopen(root, identity)
        self.stores.append(reopened)
        files = {path: reopened.read_blob(blob) for path, blob in receipt.files}
        result = codec.decode_bundle(reopened.read_blob(receipt.manifest), files)
        self.assertEqual(result, self.bundle)
        foreign = self.new_store()
        with self.assertRaises(SafetyViolation):
            foreign.read_blob(receipt.manifest)
        wrong = replace(receipt.manifest, identity=FileIdentity(identity.volume, '0' * 32,
                                                               receipt.manifest.identity.size))
        with self.assertRaises(SafetyViolation):
            reopened.read_blob(wrong)
        with self.assertRaises(SafetyViolation):
            reopened.read_blob(replace(receipt.manifest, sha256='0' * 64))
        # Reopened native reads do not register the historical receipt in a
        # newly constructed lifecycle owner, or create durable retry authority.
        new_owner = self.new_owner(reopened)
        with self.assertRaises(staging.BundleStagingError):
            new_owner.readback(receipt)

    def test_close_failure_retains_exact_cleanup_owner_for_retry(self):
        with mock.patch.object(self.store, 'close', side_effect=OSError('injected close failure')):
            with self.assertRaises(staging.BundleStagingError) as error:
                self.owner.close()
        self.assertTrue(error.exception.outcome_unknown)
        self.assertIs(error.exception.cleanup_owner, self.owner)
        self.assertIs(self.store._hh_gt03_bundle_stager_owner, self.owner)
        self.owner.close()
        self.assertIsNone(self.store._hh_gt03_bundle_stager_owner)

    def test_parallel_same_command_has_one_batch_and_same_receipt(self):
        barrier = threading.Barrier(3)
        results, errors = [], []
        def worker():
            try:
                barrier.wait(timeout=5)
                results.append(self.owner.stage('cmd.parallel', self.bundle))
            except BaseException as exc:
                errors.append(exc)
        workers = [threading.Thread(target=worker) for _ in range(2)]
        for worker_thread in workers:
            worker_thread.start()
        barrier.wait(timeout=5)
        for worker_thread in workers:
            worker_thread.join(timeout=20)
            self.assertFalse(worker_thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertIs(results[0], results[1])
        self.assertEqual(self.native_blob_count(), 12)


if __name__ == '__main__':
    unittest.main()
