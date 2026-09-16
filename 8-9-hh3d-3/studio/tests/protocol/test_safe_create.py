from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from host.core.limits import SafetyViolation
from host.core.safe_create import SafeCreateOnly, SafeCreateError


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


if __name__ == "__main__":
    unittest.main()
