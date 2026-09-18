"""Windows handle proof on disposable roots; unsupported paths are not PASS.

The outside sentinel is always a sibling inside the same disposable sandbox.
Race hooks invoke real OS rename/link operations at use-time boundaries, never
write to user files, and verify that API calls leave the outside tree unchanged.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import struct
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from host.core.limits import SafePathResolver, SafetyViolation
from host.core.safe_open import SafeFileAccess, capabilities


class ResolverTests(unittest.TestCase):
    def test_boolean_cannot_unlock_resolve_only_write(self):
        with tempfile.TemporaryDirectory(prefix="gt02-resolver-") as tmp:
            resolver = SafePathResolver(tmp, safe_open_supported=True)
            resolver.safe_open_supported = True
            with self.assertRaisesRegex(SafetyViolation, "UNSUPPORTED_SAFE_OPEN"):
                resolver.resolve("new.txt", for_write=True)
            self.assertFalse((Path(tmp) / "new.txt").exists())

    def test_every_component_rejects_aliases_devices_and_ads(self):
        with tempfile.TemporaryDirectory(prefix="gt02-paths-") as tmp:
            resolver = SafePathResolver(tmp)
            for path in ("dir:stream/file", "NUL/data", "safe/COM1.txt", "safe/LPT¹",
                         "dir./file", "dir /file", "a\n/file", "a*/file", "./file", "../file",
                         "C:/file", "\\\\server\\share", "file:stream", "safe/CONIN$",
                         "a//b", "a\\..\\b", "bad\ud800name"):
                with self.subTest(path=repr(path)), self.assertRaises(SafetyViolation):
                    resolver.resolve(path)

    def test_case_alias_and_unicode(self):
        with tempfile.TemporaryDirectory(prefix="gt02-case-") as tmp:
            root = Path(tmp)
            (root / "Café File.txt").write_bytes(b"ok")
            resolver = SafePathResolver(root)
            self.assertEqual(resolver.resolve("Café File.txt").name, "Café File.txt")
            with self.assertRaisesRegex(SafetyViolation, "CASE_ALIAS"):
                resolver.resolve("CAFÉ FILE.TXT")

    def test_dangling_link_rejects_when_host_allows_link_creation(self):
        with tempfile.TemporaryDirectory(prefix="gt02-dangling-") as tmp:
            root = Path(tmp)
            resolver = SafePathResolver(root)
            link = root / "dangling"
            try:
                link.symlink_to(root / "absent")
            except (OSError, NotImplementedError):
                self.skipTest("symbolic-link creation unavailable; Windows junction is tested separately")
            with self.assertRaisesRegex(SafetyViolation, "REPARSE_OR_SYMLINK"):
                resolver.resolve("dangling")

    def test_global_capability_does_not_claim_generic_mutation(self):
        value = capabilities()
        self.assertFalse(value["safe_write"])
        self.assertFalse(value["atomic_replace"])

    @unittest.skipIf(os.name == "nt", "non-Windows negative capability")
    def test_linux_does_not_fall_back_to_realpath(self):
        with tempfile.TemporaryDirectory(prefix="gt02-linux-") as tmp:
            with self.assertRaisesRegex(SafetyViolation, "UNSUPPORTED_SAFE_OPEN_LINUX"):
                SafeFileAccess(tmp, safe_open_supported=True)


@unittest.skipUnless(os.name == "nt", "Windows handle/API evidence requires Windows")
class WindowsSafeOpenTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gt02-win-safe-")
        self.base = Path(self.temporary.name)
        self.root = self.base / "project"
        self.outside = self.base / "outside"
        self.root.mkdir()
        self.outside.mkdir()
        (self.outside / "sentinel.txt").write_bytes(b"outside-original")
        self.api = SafeFileAccess(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def outside_snapshot(self):
        return {item.name: item.read_bytes() for item in self.outside.iterdir() if item.is_file()}

    def junction(self, path: Path, target: Path):
        """Create a real NTFS mount-point reparse only inside the sandbox."""
        path.relative_to(self.base)
        target.relative_to(self.base)
        path.mkdir()
        dll = self.api._api.dll
        dll.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
                                       wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                       ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        dll.DeviceIoControl.restype = wintypes.BOOL
        handle = dll.CreateFileW(str(path), 0x40000000, 0, None, 3, 0x02200000, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        substitute = ("\\??\\" + str(target)).encode("utf-16-le")
        printable = str(target).encode("utf-16-le")
        body = struct.pack("<HHHH", 0, len(substitute), len(substitute) + 2, len(printable))
        body += substitute + b"\0\0" + printable + b"\0\0"
        data = struct.pack("<IHH", 0xA0000003, len(body), 0) + body
        buffer, count = ctypes.create_string_buffer(data), wintypes.DWORD()
        try:
            ok = dll.DeviceIoControl(handle, 0x900A4, buffer, len(data), None, 0, ctypes.byref(count), None)
            self.assertTrue(ok, f"junction fixture failure, winerror={ctypes.get_last_error()}")
        finally:
            dll.CloseHandle(handle)

    def test_real_handle_read_identity_and_unicode(self):
        (self.root / "Café Folder").mkdir()
        (self.root / "Café Folder" / "hello file.txt").write_bytes(b"verified-content")
        identity = self.api.probe("Café Folder/hello file.txt")
        self.assertEqual(identity.size, len(b"verified-content"))
        self.assertEqual(identity, self.api.probe("Café Folder/hello file.txt"))
        self.assertEqual(self.api.read_bytes("Café Folder/hello file.txt"), b"verified-content")
        self.assertTrue(self.api.capabilities()["read_identity"])
        self.assertFalse(self.api.capabilities()["atomic_create_new"])
        self.assertFalse(self.api.capabilities()["atomic_replace"])
        self.assertEqual(list(self.root.rglob(".gt02-stage-*")), [])

    def test_existing_destination_and_generic_write_are_unsupported(self):
        destination = self.root / "existing.txt"
        destination.write_bytes(b"original")
        for operation in (lambda: self.api.create_new("existing.txt", b"changed"),
                          lambda: self.api.write_bytes("existing.txt", b"changed"),
                          lambda: self.api.open_for_write("existing.txt"),
                          lambda: self.api.atomic_replace("existing.txt", b"changed")):
            with self.assertRaisesRegex(SafetyViolation, "UNSUPPORTED_SAFE"):
                operation()
        self.assertEqual(destination.read_bytes(), b"original")
        self.assertEqual(list(self.root.glob(".gt02-stage-*")), [])

    def test_size_caps_reject_without_side_effects(self):
        (self.root / "file").write_bytes(b"1234")
        with self.assertRaisesRegex(SafetyViolation, "SIZE_LIMIT"):
            self.api.read_bytes("file", max_bytes=3)
        self.assertEqual((self.root / "file").read_bytes(), b"1234")

    def test_hardlink_rejected_from_metadata(self):
        linked = self.root / "hard.txt"
        os.link(self.outside / "sentinel.txt", linked)
        before = self.outside_snapshot()
        with self.assertRaisesRegex(SafetyViolation, "HARDLINK_UNSAFE"):
            self.api.read_bytes("hard.txt")
        with self.assertRaises(SafetyViolation):
            self.api.create_new("hard.txt", b"changed")
        self.assertEqual(before, self.outside_snapshot())

    def test_junction_and_root_reparse_reject_without_outside_effects(self):
        junction = self.root / "jump"
        self.junction(junction, self.outside)
        before = self.outside_snapshot()
        try:
            with self.assertRaisesRegex(SafetyViolation, "REPARSE_OR_SYMLINK"):
                self.api.read_bytes("jump/sentinel.txt")
            with self.assertRaisesRegex(SafetyViolation, "REPARSE_OR_SYMLINK"):
                SafeFileAccess(junction)
        finally:
            junction.rmdir()
        self.assertEqual(before, self.outside_snapshot())

    def test_root_identity_swap_after_construction_rejects(self):
        renamed = self.base / "original-project"
        self.root.rename(renamed)
        self.root.mkdir()
        (self.root / "file.txt").write_bytes(b"replacement")
        with self.assertRaisesRegex(SafetyViolation, "ROOT_IDENTITY_CHANGED"):
            self.api.read_bytes("file.txt")

    def test_ancestor_swap_between_resolve_and_open_is_rejected(self):
        folder, saved = self.root / "folder", self.root / "saved"
        folder.mkdir()
        (folder / "sentinel.txt").write_bytes(b"inside")
        original = self.api._api.open
        changed = False
        attempted = False
        blocked = False
        before = self.outside_snapshot()

        def race(path, **options):
            nonlocal changed, attempted, blocked
            if path == folder and not attempted:
                attempted = True
                try:
                    folder.rename(saved)
                except OSError as error:
                    self.assertEqual(error.winerror, 32)
                    blocked = True
                else:
                    changed = True
                    self.junction(folder, self.outside)
            return original(path, **options)

        try:
            with mock.patch.object(self.api._api, "open", race):
                try:
                    result = self.api.read_bytes("folder/sentinel.txt")
                except SafetyViolation as error:
                    self.assertTrue(changed)
                    self.assertEqual(error.code, "REPARSE_OR_SYMLINK")
                else:
                    self.assertTrue(blocked, "an admitted read requires a proven blocked swap")
                    self.assertEqual(result, b"inside")
        finally:
            if changed:
                folder.rmdir()
                saved.rename(folder)
        self.assertTrue(attempted)
        self.assertTrue(changed or blocked)
        self.assertEqual(before, self.outside_snapshot())
        self.assertEqual((folder / "sentinel.txt").read_bytes(), b"inside")

    def test_locked_ancestors_and_file_block_concurrent_rename_delete(self):
        folder = self.root / "folder"
        folder.mkdir()
        target = folder / "file.txt"
        target.write_bytes(b"safe")
        original = self.api._api.read
        results = []
        before = self.outside_snapshot()

        def attack_during_read(handle, cap):
            def attacker():
                for _ in range(16):
                    for operation in (lambda: folder.rename(self.root / "moved"),
                                      lambda: target.unlink()):
                        try:
                            operation()
                        except OSError:
                            results.append("denied")
                        else:
                            results.append("UNSAFE")

            thread = threading.Thread(target=attacker, daemon=True)
            thread.start()
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(results, ["denied"] * 32)
            return original(handle, cap)

        with mock.patch.object(self.api._api, "read", attack_during_read):
            self.assertEqual(self.api.read_bytes("folder/file.txt"), b"safe")
        self.assertEqual(before, self.outside_snapshot())
        self.assertEqual((folder / "file.txt").read_bytes(), b"safe")

    def test_parent_handle_blocks_rename_before_final_file_is_open(self):
        folder, moved = self.root / "empty-parent", self.root / "moved-parent"
        folder.mkdir()
        observed = []
        with self.api._parents(folder):
            try:
                folder.rename(moved)
            except OSError as error:
                observed.append(error.winerror)
            else:
                moved.rename(folder)
                observed.append("RENAME_ALLOWED")
        self.assertEqual(observed, [32])

    def test_exclusive_handle_hardlink_counterexample_keeps_mutation_disabled(self):
        """Proof of the GAP: share=0 does NOT lock out a new hardlink."""
        stage = self.root / "diagnostic-empty-stage"
        alias = self.outside / "diagnostic-alias"
        before = self.outside_snapshot()
        dll = self.api._api.dll
        handle = dll.CreateFileW(str(stage), 0xC0010000, 0, None, 1, 0x00200000, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        try:
            os.link(stage, alias)
            with self.assertRaisesRegex(SafetyViolation, "HARDLINK_UNSAFE"):
                self.api._api.inspect(handle, stage)
            # Deliberately no WriteFile: actual data writes could reach alias.
            with self.assertRaisesRegex(SafetyViolation, "UNSUPPORTED_SAFE_OPEN_WINDOWS"):
                self.api.create_new("cannot-enable.txt", b"forbidden")
        finally:
            dll.CloseHandle(handle)
            if alias.exists():
                alias.unlink()
            stage.unlink()
        self.assertEqual(before, self.outside_snapshot())

    def test_final_file_swap_to_hardlink_between_resolve_and_open_rejects(self):
        target = self.root / "file.txt"
        target.write_bytes(b"inside")
        original = self.api._api.open
        before = self.outside_snapshot()
        link_blocked = False

        def race(path, **options):
            nonlocal link_blocked
            if path == target:
                target.unlink()
                try:
                    os.link(self.outside / "sentinel.txt", target)
                except OSError as error:
                    self.assertEqual(error.winerror, 32)
                    link_blocked = True
            return original(path, **options)

        with mock.patch.object(self.api._api, "open", race):
            with self.assertRaises(SafetyViolation) as caught:
                self.api.read_bytes("file.txt")
        self.assertEqual(caught.exception.code, "PATH_NOT_FOUND" if link_blocked else "HARDLINK_UNSAFE")
        self.assertEqual(before, self.outside_snapshot())

    def test_every_mutation_rejects_before_io_even_during_junction_swaps(self):
        junction = self.root / "changing"
        before = self.outside_snapshot()
        for _ in range(16):
            self.junction(junction, self.outside)
            try:
                with mock.patch.object(self.api._api, "open", side_effect=AssertionError("must not open")):
                    for operation in (lambda: self.api.create_new("changing/new.txt", b"bad"),
                                      lambda: self.api.open_for_write("changing/new.txt"),
                                      lambda: self.api.write_bytes("changing/new.txt", b"bad"),
                                      lambda: self.api.atomic_replace("changing/sentinel.txt", b"bad")):
                        with self.assertRaisesRegex(SafetyViolation, "UNSUPPORTED_SAFE_OPEN_WINDOWS"):
                            operation()
            finally:
                junction.rmdir()
        self.assertEqual(before, self.outside_snapshot())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_reads_and_rejections_release_native_handles(self):
        dll = self.api._api.dll
        dll.GetCurrentProcess.argtypes, dll.GetCurrentProcess.restype = [], wintypes.HANDLE
        dll.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        dll.GetProcessHandleCount.restype = wintypes.BOOL

        def count():
            value = wintypes.DWORD()
            self.assertTrue(dll.GetProcessHandleCount(dll.GetCurrentProcess(), ctypes.byref(value)))
            return value.value

        (self.root / "file").write_bytes(b"safe")
        baseline = count()
        for _ in range(32):
            self.assertEqual(self.api.read_bytes("file"), b"safe")
            with self.assertRaisesRegex(SafetyViolation, "SIZE_LIMIT"):
                self.api.read_bytes("file", max_bytes=1)
        self.assertEqual(count(), baseline)

    def test_windows_short_name_alias_is_rejected_when_available(self):
        path = self.root / "long filename requiring an alias.txt"
        path.write_bytes(b"safe")
        dll = self.api._api.dll
        dll.GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        dll.GetShortPathNameW.restype = wintypes.DWORD
        buffer = ctypes.create_unicode_buffer(32768)
        length = dll.GetShortPathNameW(str(path), buffer, len(buffer))
        self.assertTrue(length and length < len(buffer))
        alias = Path(buffer.value).name
        if alias == path.name:
            self.skipTest("8.3 alias creation is disabled on this volume")
        with self.assertRaisesRegex(SafetyViolation, "PATH_ALIAS_OR_INVALID"):
            self.api.read_bytes(alias)


if __name__ == "__main__":
    unittest.main()
