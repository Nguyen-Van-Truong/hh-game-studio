from __future__ import annotations

import os
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from host.core.limits import SafetyViolation
from host.core.safe_create import SafeCreateOnly, SafeCreateError, SafeCreateApi, _RenameInfo


@unittest.skipUnless(os.name == "nt", "Windows handle primitive required")
class SafeCreateOnlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gt02-safe-create-")
        self.base = Path(self.tmp.name)
        self.root = self.base / "project"
        self.root.mkdir()
        self.outside = self.base / "outside"
        self.outside.mkdir()
        self.api = SafeCreateOnly(self.root)

    def tearDown(self):
        self.api.close()
        self.tmp.cleanup()

    def test_create_flush_publish_and_readback(self):
        identity = self.api.create_new("fresh.txt", b"immutable-bytes")
        self.assertEqual((self.root / "fresh.txt").read_bytes(), b"immutable-bytes")
        self.assertEqual(identity.size, len(b"immutable-bytes"))
        self.assertEqual(list(self.root.glob(".hh-stage-*")), [])

    def test_existing_destination_rejects_without_change(self):
        destination = self.root / "existing.txt"
        destination.write_bytes(b"original")
        with self.assertRaisesRegex(SafetyViolation, "DESTINATION_EXISTS"):
            self.api.create_new("existing.txt", b"replacement")
        self.assertEqual(destination.read_bytes(), b"original")

    def test_reparse_and_traversal_reject_without_write(self):
        for relative in ("../outside.txt", "dir:stream", "NUL/data"):
            with self.subTest(relative=relative), self.assertRaises(SafetyViolation):
                self.api.create_new(relative, b"forbidden")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_later_alias_does_not_change_published_bytes(self):
        self.api.create_new("stable.txt", b"stable")
        outside = self.outside / "stable-alias"
        try:
            os.link(self.root / "stable.txt", outside)
            self.assertEqual(outside.read_bytes(), b"stable")
            self.assertEqual((self.root / "stable.txt").read_bytes(), b"stable")
        finally:
            if outside.exists():
                outside.unlink()

    def test_pending_blocks_alias_at_write_boundary(self):
        original = self.api._api.write_flush
        outside = self.outside / "alias"
        attempts = []
        def race(handle, data):
            stage = next(self.root.glob(".hh-stage-*"))
            try:
                os.link(stage, outside)
            except OSError as error:
                attempts.append(error.winerror)
            else:
                self.fail("hardlink admitted during mutable phase")
            original(handle, data)
        with mock.patch.object(self.api._api, "write_flush", side_effect=race):
            self.api.create_new("value.txt", b"safe")
        self.assertEqual(attempts, [5])
        self.assertFalse(outside.exists())
        self.assertEqual((self.root / "value.txt").read_bytes(), b"safe")

    def test_alias_before_pending_rejects_before_bytes_written(self):
        original = self.api._api.pending
        outside = self.outside / "alias"
        attacked = False
        def race(handle, pending):
            nonlocal attacked
            if pending and not attacked:
                attacked = True
                os.link(next(self.root.glob(".hh-stage-*")), outside)
            return original(handle, pending)
        with mock.patch.object(self.api._api, "pending", side_effect=race):
            with self.assertRaises(SafeCreateError) as caught:
                self.api.create_new("value.txt", b"must-not-leak")
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertTrue(attacked)
        self.assertEqual(outside.read_bytes(), b"")
        self.assertFalse((self.root / "value.txt").exists())

    def test_rename_collision_preserves_other_writer(self):
        original = self.api._api.rename
        def race(handle, destination):
            destination.write_bytes(b"other-writer")
            return original(handle, destination)
        with mock.patch.object(self.api._api, "rename", side_effect=race):
            with self.assertRaises(SafeCreateError) as caught:
                self.api.create_new("collision.txt", b"new-data")
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertEqual((self.root / "collision.txt").read_bytes(), b"other-writer")
        with self.assertRaisesRegex(SafeCreateError, "RECONCILIATION_REQUIRED"):
            self.api.create_new("retry.txt", b"no")

    def test_rename_success_without_postcondition_is_unknown(self):
        with mock.patch.object(self.api._api, "rename", return_value=None):
            with self.assertRaises(SafeCreateError) as caught:
                self.api.create_new("absent.txt", b"bytes")
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertFalse((self.root / "absent.txt").exists())

    def test_flush_failure_after_publish_is_unknown_and_blocks_retry(self):
        original = self.api._api.flush_parent
        calls = 0
        def failing(path, identity):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise SafetyViolation("INJECTED_FLUSH_FAILURE")
            return original(path, identity)
        with mock.patch.object(self.api._api, "flush_parent", side_effect=failing):
            with self.assertRaises(SafeCreateError) as caught:
                self.api.create_new("published.txt", b"uncertain")
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertEqual((self.root / "published.txt").read_bytes(), b"uncertain")
        with self.assertRaisesRegex(SafeCreateError, "RECONCILIATION_REQUIRED"):
            self.api.create_new("again.txt", b"no")

    def test_root_identity_change_rejects(self):
        self.root.rename(self.base / "old-root")
        self.root.mkdir()
        with self.assertRaisesRegex(SafetyViolation, "ROOT_IDENTITY_CHANGED"):
            self.api.create_new("forbidden.txt", b"no")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_unicode_names_and_zero_length_have_exact_postconditions(self):
        names = ["empty.txt", "Café.txt", "longer name.txt", "a.txt"]
        for index, name in enumerate(names):
            value = b"x" * index
            result = self.api.create_new(name, value)
            self.assertEqual(result.size, index)
            self.assertEqual((self.root / name).read_bytes(), value)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), sorted(names))

    def test_pending_blocks_link_from_native_preopened_zero_access_handle(self):
        """The attacker opens BEFORE pending; it need not reopen by pathname."""
        ntdll = C.WinDLL("ntdll")
        ntdll.NtSetInformationFile.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, W.ULONG, C.c_int]
        ntdll.NtSetInformationFile.restype = C.c_long
        alias = self.outside / "preopened-alias"
        pending, write = self.api._api.pending, self.api._api.write_flush
        attacker = []
        outcomes = []
        def before_pending(handle, value):
            if value and not attacker:
                stage = next(self.root.glob(".hh-stage-*"))
                other = self.api._api.dll.CreateFileW(str(stage), 0, 7, None, 3, 0x00200000, None)
                self.assertNotEqual(other, C.c_void_p(-1).value)
                attacker.append(other)
            return pending(handle, value)
        def link_from(handle):
            # FileLinkInformation has the same ABI layout as rename info.
            encoded = ("\\??\\" + str(alias)).encode("utf-16-le")
            buffer = C.create_string_buffer(C.sizeof(_RenameInfo) + len(encoded) + 2)
            header = _RenameInfo.from_buffer(buffer)
            header.flags, header.root, header.length = 0, None, len(encoded)
            C.memmove(C.addressof(buffer) + _RenameInfo.name.offset, encoded, len(encoded))
            status = C.create_string_buffer(2 * C.sizeof(C.c_void_p))
            return ntdll.NtSetInformationFile(handle, status, buffer, len(buffer), 11)
        def at_write(handle, data):
            result = link_from(attacker[0])
            outcomes.append(result & 0xffffffff)
            self.assertIn(result & 0xffffffff, (0xc0000022, 0xc0000056))
            self.assertFalse(alias.exists())
            return write(handle, data)
        try:
            with mock.patch.object(self.api._api, "pending", side_effect=before_pending), mock.patch.object(self.api._api, "write_flush", side_effect=at_write):
                self.api.create_new("proof.txt", b"private-bytes")
        finally:
            for handle in attacker:
                self.api._api.dll.CloseHandle(handle)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual((self.root / "proof.txt").read_bytes(), b"private-bytes")
        self.assertFalse(alias.exists())
        # Same syscall/buffer with a non-pending file must actually succeed.
        # Otherwise a malformed test could mistake INVALID_PARAMETER for safety.
        control = self.api._api.dll.CreateFileW(str(self.root / "proof.txt"), 0, 7, None, 3, 0x00200000, None)
        self.assertNotEqual(control, C.c_void_p(-1).value)
        try:
            self.assertEqual(link_from(control), 0)
            self.assertEqual(alias.read_bytes(), b"private-bytes")
        finally:
            self.api._api.dll.CloseHandle(control)
            if alias.exists():
                alias.unlink()

    def test_constructor_failure_retains_real_unclosed_handles_for_retry(self):
        original = SafeCreateApi.close
        retained = []
        def refuse(api, handle):
            retained.append(handle)
            raise SafeCreateError("REAL_CLOSE_REFUSED", outcome_unknown=True)
        with mock.patch.object(SafeCreateApi, "close", refuse):
            with self.assertRaisesRegex(SafeCreateError, "INIT_CLEANUP_UNCERTAIN") as caught:
                SafeCreateOnly(self.root)
        owner = caught.exception.cleanup_owner
        self.assertIsNotNone(owner)
        self.assertTrue(retained)
        self.assertTrue(owner._api.owned)
        owner.close()
        self.assertFalse(owner._api.owned)
        self.assertIs(SafeCreateApi.close, original)

    def test_operation_ancestor_close_failure_poisons_and_retains_owner(self):
        close = self.api._api.close
        failures = []
        def refuse_directory(handle):
            try:
                self.api._api.inspect(handle, self.root, directory=True)
            except SafetyViolation:
                return close(handle)
            failures.append(handle)
            raise SafeCreateError("REAL_DIRECTORY_CLOSE_REFUSED", outcome_unknown=True)
        with mock.patch.object(self.api._api, "close", side_effect=refuse_directory):
            with self.assertRaises(SafeCreateError) as caught:
                self.api.create_new("uncertain.txt", b"value")
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertTrue(failures)
        self.assertTrue(self.api._api.owned)
        with self.assertRaisesRegex(SafeCreateError, "RECONCILIATION_REQUIRED"):
            self.api.create_new("retry.txt", b"no")
        self.api.close()
        self.assertFalse(self.api._api.owned)


if __name__ == "__main__":
    unittest.main()
