"""Real Windows staging handles in wholly owned temporary fixtures.

These tests do not advertise safe-write or certify an AppContainer sandbox.
Failures are injected at real handle I/O boundaries; partial files are retained
until the test closes handles and cleans its own entire fixture.
"""
from __future__ import annotations

import dataclasses
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from host.core.limits import SafetyViolation
from host.core.private_store import MAX_BLOB_BYTES, PrivateBlobStore, PrivateStoreError
from host.core.safe_open import FileIdentity, capabilities


@unittest.skipUnless(os.name == "nt", "Windows NTFS handle fixture required")
class PrivateStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gt02-private-test-")
        self.base = Path(self.temp.name).resolve()
        self.store = PrivateBlobStore.create(self.base)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_empty_binary_and_maximum_bytes_round_trip(self):
        for data in (b"", b"\x00\xff\r\n\xe1\xbb\x87", b"a" * MAX_BLOB_BYTES):
            with self.subTest(size=len(data)):
                blob = self.store.put_bytes(data)
                self.assertEqual(blob.identity.size, len(data))
                self.assertEqual(blob.sha256, hashlib.sha256(data).hexdigest())
                self.assertEqual(self.store.read_blob(blob), data)
                self.assertEqual((self.store.root / blob.object_id).stat().st_nlink, 1)
        self.assertFalse(capabilities()["safe_write"])
        self.assertFalse(capabilities()["atomic_replace"])

    def test_oversized_or_untyped_data_reject_before_create(self):
        before = sorted(p.name for p in self.store.root.iterdir())
        for data in (b"a" * (MAX_BLOB_BYTES + 1), "hello", bytearray(b"hello"), None):
            with self.subTest(kind=type(data).__name__), self.assertRaisesRegex(PrivateStoreError, "PRIVATE_BLOB_LIMIT"):
                self.store.put_bytes(data)
        self.assertEqual(sorted(p.name for p in self.store.root.iterdir()), before)

    def test_collision_preserves_original_and_does_not_poison(self):
        original = self.store.put_bytes(b"original")
        fixed = mock.Mock(hex=original.object_id.removeprefix("blob-"))
        with mock.patch("host.core.private_store.uuid.uuid4", return_value=fixed):
            with self.assertRaisesRegex(PrivateStoreError, "DESTINATION_EXISTS") as raised:
                self.store.put_bytes(b"contender")
        self.assertFalse(raised.exception.outcome_unknown)
        self.assertEqual(self.store.read_blob(original), b"original")

    def test_no_second_writer_and_root_rename_blocked(self):
        with self.assertRaisesRegex(SafetyViolation, "PRIVATE_OPEN_DENIED"):
            PrivateBlobStore.reopen(self.store.root, self.store.root_identity)
        with self.assertRaises(OSError):
            self.store.root.rename(self.base / "moved")
        self.assertTrue(self.store.root.is_dir())
        blob = self.store.put_bytes(b"still-writable")
        self.assertEqual(self.store.read_blob(blob), b"still-writable")

    def test_second_process_cannot_acquire_writer_guard(self):
        config = {"root": str(self.store.root), "identity": dataclasses.asdict(self.store.root_identity)}
        script = """import json, sys
from host.core.private_store import PrivateBlobStore, PrivateStoreError
from host.core.safe_open import FileIdentity
c = json.loads(sys.stdin.read())
try:
    s = PrivateBlobStore.reopen(c['root'], FileIdentity(**c['identity']))
except PrivateStoreError as exc:
    assert exc.code == 'PRIVATE_OPEN_DENIED', exc.code
    assert not exc.outcome_unknown
    print('PRIVATE_SECOND_WRITER_DENIED')
else:
    s.close()
    raise AssertionError('second writer acquired guard')
"""
        result = subprocess.run([sys.executable, "-B", "-c", script], input=json.dumps(config),
                                text=True, capture_output=True, cwd=ROOT, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "PRIVATE_SECOND_WRITER_DENIED")
        self.assertEqual(result.stderr, "")
        self.assertEqual(list(self.store.root.glob("blob-*")), [])

    def test_fresh_process_reopen_uses_saved_root_and_blob_identity(self):
        blob = self.store.put_bytes(b"fresh-process-proof")
        config = {"root": str(self.store.root), "root_identity": dataclasses.asdict(self.store.root_identity), "blob": dataclasses.asdict(blob)}
        self.store.close()
        script = (
            "import json,sys; from host.core.private_store import PrivateBlobStore,StagedBlob; "
            "from host.core.safe_open import FileIdentity; c=json.loads(sys.stdin.read()); "
            "b=c['blob']; b['identity']=FileIdentity(**b['identity']); "
            "s=PrivateBlobStore.reopen(c['root'],FileIdentity(**c['root_identity'])); "
            "assert s.read_blob(StagedBlob(**b))==b'fresh-process-proof'; s.close(); "
            "print('PRIVATE_STORE_FRESH_PROCESS_READBACK_OK')"
        )
        result = subprocess.run([sys.executable, "-B", "-c", script], input=json.dumps(config),
                                text=True, capture_output=True, cwd=ROOT, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "PRIVATE_STORE_FRESH_PROCESS_READBACK_OK")
        self.assertEqual(result.stderr, "")

    def test_wrong_root_and_changed_blob_identity_reject(self):
        blob = self.store.put_bytes(b"original")
        root, identity = self.store.root, self.store.root_identity
        self.store.close()
        with self.assertRaisesRegex(SafetyViolation, "PRIVATE_ROOT_IDENTITY_CHANGED"):
            PrivateBlobStore.reopen(root, dataclasses.replace(identity, file_id="0" * 32))
        target = root / blob.object_id
        target.rename(root / "kept-original")
        # Same bytes and inherited ACL are insufficient: changed FileId denies.
        target.write_bytes(b"original")
        with PrivateBlobStore.reopen(root, identity) as reopened:
            with self.assertRaises(SafetyViolation):
                reopened.read_blob(blob)

    def test_blob_name_injection_and_hash_mismatch_reject(self):
        blob = self.store.put_bytes(b"original")
        for name in ("../outside", "NUL", "x:stream", "BLOB-" + "a" * 32, "blob-" + "a" * 32 + "/child"):
            with self.subTest(name=name), self.assertRaisesRegex(SafetyViolation, "PRIVATE_BLOB_INVALID"):
                self.store.read_blob(dataclasses.replace(blob, object_id=name))
        with self.assertRaisesRegex(SafetyViolation, "PRIVATE_READBACK_MISMATCH"):
            self.store.read_blob(dataclasses.replace(blob, sha256="0" * 64))

    def test_quota_survives_reopen_and_rejects_before_creation(self):
        for _ in range(8):
            self.store.put_bytes(b"a" * MAX_BLOB_BYTES)
        root, identity = self.store.root, self.store.root_identity
        self.store.close()
        with PrivateBlobStore.reopen(root, identity) as reopened:
            with self.assertRaisesRegex(SafetyViolation, "PRIVATE_STAGE_QUOTA"):
                reopened.put_bytes(b"x")
        self.assertEqual(len(list(root.glob("blob-*"))), 8)
        # Object count also bounds empty-file amplification; shrink the limit
        # for this boundary test without changing the production defaults.
        with mock.patch("host.core.private_store.MAX_STAGED_OBJECTS", 2):
            with PrivateBlobStore.create(self.base) as limited:
                limited.put_bytes(b"")
                limited.put_bytes(b"")
                with self.assertRaisesRegex(SafetyViolation, "PRIVATE_STAGE_QUOTA"):
                    limited.put_bytes(b"")

    def test_changed_root_or_blob_acl_rejects(self):
        blob = self.store.put_bytes(b"original")
        api = self.store._api
        function = api.adv.SetFileSecurityW
        function.argtypes, function.restype = [W.LPCWSTR, W.DWORD, C.c_void_p], W.BOOL
        original = api.sddl
        for path, action in ((self.store.root / blob.object_id, lambda: self.store.read_blob(blob)),
                             (self.store.root, lambda: self.store.put_bytes(b"forbidden")),
                             (self.store.root / ".writer", lambda: self.store.put_bytes(b"forbidden"))):
            with self.subTest(target=path.name):
                # Synthetic same-account tamper, not an AppContainer claim.
                api.sddl = original + "(A;;FR;;;BA)"
                with api.descriptor() as descriptor:
                    self.assertTrue(function(str(path), 0x80000004, descriptor))
                api.sddl = original
                with self.assertRaisesRegex(SafetyViolation, "PRIVATE_ACL_CHANGED"):
                    action()
                with api.descriptor() as descriptor:
                    self.assertTrue(function(str(path), 0x80000004, descriptor))
        self.assertEqual(self.store.read_blob(blob), b"original")
        self.assertEqual(len(list(self.store.root.glob("blob-*"))), 1)

    def test_impersonation_refuses_init_and_existing_instance(self):
        adv = self.store._api.adv
        adv.ImpersonateSelf.argtypes, adv.ImpersonateSelf.restype = [C.c_int], W.BOOL
        adv.RevertToSelf.argtypes, adv.RevertToSelf.restype = [], W.BOOL
        before = {p.name for p in self.base.iterdir()}
        self.assertTrue(adv.ImpersonateSelf(2))
        try:
            with self.assertRaisesRegex(PrivateStoreError, "BROKER_IMPERSONATION_UNSUPPORTED"):
                PrivateBlobStore.create(self.base)
            with self.assertRaisesRegex(PrivateStoreError, "BROKER_IMPERSONATION_UNSUPPORTED"):
                self.store.put_bytes(b"must-not-write-while-impersonating")
        finally:
            self.assertTrue(adv.RevertToSelf())
        self.assertEqual({p.name for p in self.base.iterdir()}, before)
        self.assertEqual(list(self.store.root.glob("blob-*")), [])

    def test_native_short_write_success_is_still_uncertain(self):
        native = self.store._api.dll.WriteFile
        def short(handle, buffer, length, count, overlapped):
            return native(handle, buffer, 3, count, overlapped)
        with mock.patch.object(self.store._api.dll, "WriteFile", side_effect=short):
            with self.assertRaisesRegex(PrivateStoreError, "PRIVATE_STAGE_UNCERTAIN") as raised:
                self.store.put_bytes(b"original")
        self.assertTrue(raised.exception.outcome_unknown)
        staged = list(self.store.root.glob("blob-*"))
        self.assertEqual(len(staged), 1)
        self.assertEqual(staged[0].read_bytes(), b"ori")

    def test_junction_replaced_root_cannot_authorize_outside_write(self):
        from test_safe_open import WindowsSafeOpenTests
        from host.core.safe_open import SafeFileAccess
        root, identity = self.store.root, self.store.root_identity
        self.store.close()
        root.rename(self.base / "preserved-root")
        outside = self.base / "outside"
        outside.mkdir()
        sentinel = outside / "sentinel"
        sentinel.write_bytes(b"outside-original")
        fixture = WindowsSafeOpenTests()
        fixture.base, fixture.api = self.base, SafeFileAccess(self.base)
        fixture.junction(root, outside)
        try:
            with self.assertRaises(SafetyViolation):
                PrivateBlobStore.reopen(root, identity)
            self.assertEqual(sentinel.read_bytes(), b"outside-original")
            self.assertEqual([p.name for p in outside.iterdir()], ["sentinel"])
        finally:
            os.rmdir(root)  # Remove only the owned junction, never its target.

    def test_hardlink_alias_after_close_is_rejected(self):
        blob = self.store.put_bytes(b"original")
        root, identity = self.store.root, self.store.root_identity
        self.store.close()
        alias = self.base / "outside-alias"
        os.link(root / blob.object_id, alias)
        with PrivateBlobStore.reopen(root, identity) as reopened:
            with self.assertRaisesRegex(SafetyViolation, "HARDLINK_UNSAFE"):
                reopened.read_blob(blob)
        self.assertEqual(alias.read_bytes(), b"original")

    def test_write_partial_flush_and_readback_failures_never_return_blob(self):
        self.store.close()
        for phase in ("write-before", "write-partial", "flush", "readback"):
            with self.subTest(phase=phase), PrivateBlobStore.create(self.base) as store:
                original_write = store._api.write
                def partial(handle, data):
                    original_write(handle, data[:3])
                    raise PrivateStoreError("PRIVATE_SHORT_WRITE")
                method = {"write-before": "write", "write-partial": "write", "flush": "flush", "readback": "read"}[phase]
                behavior = partial if phase == "write-partial" else PrivateStoreError("INJECTED_IO_FAILURE")
                with mock.patch.object(store._api, method, side_effect=behavior):
                    with self.assertRaises(PrivateStoreError) as raised:
                        store.put_bytes(b"original")
                self.assertTrue(raised.exception.outcome_unknown)
                with self.assertRaisesRegex(PrivateStoreError, "RECONCILIATION_REQUIRED"):
                    store.put_bytes(b"must-not-retry")
                staged = list(store.root.glob("blob-*"))
                self.assertEqual(len(staged), 1)
                expected = b"" if phase == "write-before" else (b"ori" if phase == "write-partial" else b"original")
                self.assertEqual(staged[0].read_bytes(), expected)

    def test_close_failure_keeps_uncertain_status(self):
        original = self.store._api.close
        def closed_but_failed(handle):
            original(handle)
            raise PrivateStoreError("PRIVATE_CLOSE_FAILED")
        with mock.patch.object(self.store._api, "close", side_effect=closed_but_failed):
            with self.assertRaisesRegex(PrivateStoreError, "PRIVATE_CLOSE_UNCERTAIN") as raised:
                self.store.put_bytes(b"fully-written-but-no-receipt")
        self.assertTrue(raised.exception.outcome_unknown)
        self.assertEqual(len(list(self.store.root.glob("blob-*"))), 1)
        with self.assertRaisesRegex(PrivateStoreError, "RECONCILIATION_REQUIRED"):
            self.store.put_bytes(b"retry")

    def test_failed_native_close_retains_guard_root_and_ancestor_for_retry(self):
        for kind in ("root", "guard", "ancestor"):
            with self.subTest(kind=kind):
                store = PrivateBlobStore.create(self.base)
                target = {"root": store._root_handle, "guard": store._guard_handle,
                          "ancestor": store._ancestor_records[-1][0]}[kind]
                native_close = store._api.dll.CloseHandle
                info = store._api.dll.GetHandleInformation
                info.argtypes, info.restype = [W.HANDLE, C.POINTER(W.DWORD)], W.BOOL
                flags = W.DWORD()
                def refuse(handle):
                    return False if handle == target else native_close(handle)
                try:
                    with mock.patch.object(store._api.dll, "CloseHandle", side_effect=refuse):
                        with self.assertRaisesRegex(PrivateStoreError, "CLOSE_UNCERTAIN"):
                            store.close()
                        self.assertIn(target, store._api._owned_handles)
                        self.assertTrue(info(target, C.byref(flags)))  # Still really open.
                    store.close()
                    self.assertEqual(store._api._owned_handles, set())
                    self.assertFalse(info(target, C.byref(flags)))
                finally:
                    store.close()

    def test_failed_native_blob_close_remains_owned_until_cleanup(self):
        api, blocked = self.store._api, []
        native_close, original_write = api.dll.CloseHandle, api.write
        def remember(handle, data):
            blocked.append(handle)
            original_write(handle, data)
        def refuse(handle):
            return False if handle in blocked else native_close(handle)
        with mock.patch.object(api, "write", side_effect=remember), mock.patch.object(api.dll, "CloseHandle", side_effect=refuse):
            with self.assertRaisesRegex(PrivateStoreError, "PRIVATE_CLOSE_UNCERTAIN"):
                self.store.put_bytes(b"live-handle-must-remain-owned")
            self.assertIn(blocked[0], api._owned_handles)
            with self.assertRaisesRegex(PrivateStoreError, "PRIVATE_CLOSE_UNCERTAIN"):
                self.store.close()
        self.store.close()
        self.assertEqual(api._owned_handles, set())

    def test_constructor_partial_root_and_cleanup_failure_keep_provenance(self):
        from host.core.private_store import _StoreApi
        before = {p.name for p in self.base.iterdir()}
        with mock.patch.object(_StoreApi, "ntfs", side_effect=PrivateStoreError("PRIVATE_FILESYSTEM_UNSUPPORTED")):
            with self.assertRaisesRegex(PrivateStoreError, "PRIVATE_FILESYSTEM_UNSUPPORTED") as refused:
                PrivateBlobStore.create(self.base)
        self.assertFalse(refused.exception.outcome_unknown)
        self.assertEqual({p.name for p in self.base.iterdir()}, before)
        with mock.patch.object(_StoreApi, "check_security", side_effect=PrivateStoreError("PRIVATE_ACL_CHANGED")):
            with self.assertRaisesRegex(PrivateStoreError, "PRIVATE_INIT_UNCERTAIN") as partial:
                PrivateBlobStore.create(self.base)
        self.assertTrue(partial.exception.outcome_unknown)
        owner = partial.exception.cleanup_owner
        self.assertIsNotNone(owner)
        self.assertTrue(owner.root.is_dir())
        self.assertEqual(owner._api._owned_handles, set())
        native = _StoreApi.close
        def fail_owned(api, handle):
            if hasattr(api, "expected_security") and handle in api._owned_handles:
                raise PrivateStoreError("PRIVATE_CLOSE_FAILED")
            native(api, handle)
        with mock.patch.object(_StoreApi, "ntfs", side_effect=PrivateStoreError("INJECTED_REFUSAL")), \
                mock.patch.object(_StoreApi, "close", new=fail_owned):
            with self.assertRaisesRegex(PrivateStoreError, "PRIVATE_INIT_CLEANUP_UNCERTAIN") as cleanup:
                PrivateBlobStore.create(self.base)
        owner = cleanup.exception.cleanup_owner
        self.assertTrue(owner._api._owned_handles)
        owner.close()
        self.assertEqual(owner._api._owned_handles, set())

    def test_api_constructor_token_close_failure_keeps_cleanup_owner(self):
        from host.core.private_store import _StoreApi
        retained = []
        def fail_token(api, handle):
            self.assertIn(handle, api._owned_handles)
            retained.append(handle)
            raise PrivateStoreError("PRIVATE_CLOSE_FAILED")
        with mock.patch.object(_StoreApi, "close", new=fail_token):
            with self.assertRaisesRegex(PrivateStoreError, "PRIVATE_API_INIT_CLEANUP_UNCERTAIN") as caught:
                PrivateBlobStore.create(self.base)
        api = caught.exception.cleanup_api
        self.assertIsNotNone(api)
        self.assertTrue(api._owned_handles)
        self.assertEqual(api._owned_handles, set(retained))
        info = api.dll.GetHandleInformation
        info.argtypes, info.restype = [W.HANDLE, C.POINTER(W.DWORD)], W.BOOL
        for handle in api._owned_handles:
            self.assertTrue(info(handle, C.byref(W.DWORD())))
        api.close_owned()
        self.assertEqual(api._owned_handles, set())


if __name__ == "__main__":
    unittest.main(verbosity=2)
