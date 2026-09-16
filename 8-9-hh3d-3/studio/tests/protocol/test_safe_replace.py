"""Protected namespace tests; no claim about an unrestricted shared folder."""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from host.core.limits import SafetyViolation
from host.core.safe_open import FileIdentity, capabilities
from host.core.safe_replace import FileVersion, ProtectedFileRoot, SafeReplaceError, MAX_BYTES


@unittest.skipUnless(os.name == "nt", "Windows NTFS protected namespace required")
class ProtectedReplaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gt02-replace-")
        self.base = Path(self.tmp.name)
        self.files = ProtectedFileRoot.create(self.base)

    def tearDown(self):
        self.files.close()
        self.tmp.cleanup()

    def test_create_replace_has_new_identity_and_complete_bytes(self):
        first = self.files.create_new("asset.txt", b"original")
        second = self.files.atomic_replace("asset.txt", b"replacement", expected=first)
        self.assertFalse(first.identity.same_file(second.identity))
        self.assertEqual(second.sha256, hashlib.sha256(b"replacement").hexdigest())
        self.assertEqual(self.files.read("asset.txt"), (second, b"replacement"))
        self.assertEqual(sorted(p.name for p in self.files.root.iterdir()), [".writer", "asset.txt"])
        self.assertFalse(capabilities()["safe_write"])
        self.assertFalse(capabilities()["atomic_replace"])

    def test_exact_unicode_empty_and_max_size(self):
        for name, data in (("Café.txt", b""), ("𐀀.txt", b"x"), ("longer name.txt", b"a" * MAX_BYTES)):
            first = self.files.create_new(name, b"before")
            after = self.files.atomic_replace(name, data, expected=first)
            self.assertEqual(self.files.read(name), (after, data))

    def test_stale_or_wrong_target_version_rejects_before_staging(self):
        first = self.files.create_new("a.txt", b"before")
        second = self.files.atomic_replace("a.txt", b"after", expected=first)
        wrong = self.files.create_new("b.txt", b"after")
        for expected in (first, wrong, replace(second, sha256="0" * 64),
                         replace(second, identity=replace(second.identity, size=999))):
            with self.subTest(expected=expected), mock.patch.object(self.files._api, "write_flush", side_effect=AssertionError("no write")):
                with self.assertRaisesRegex(SafeReplaceError, "SAFE_TARGET_CONFLICT") as caught:
                    self.files.atomic_replace("a.txt", b"bad", expected=expected)
                self.assertFalse(caught.exception.outcome_unknown)
        self.assertEqual(self.files.read("a.txt"), (second, b"after"))

    def test_missing_target_does_not_turn_replace_into_create(self):
        first = self.files.create_new("a.txt", b"before")
        with self.assertRaisesRegex(SafeReplaceError, "PATH_NOT_FOUND"):
            self.files.atomic_replace("absent.txt", b"bad", expected=first)
        self.assertFalse((self.files.root / "absent.txt").exists())

    def test_invalid_paths_data_and_expected_do_not_write(self):
        first = self.files.create_new("a.txt", b"before")
        for name in ("../outside.txt", "a.txt:stream", "NUL", ".writer", ".hh-stage-one", "dir/file.txt", "A.txt"):
            with self.subTest(name=name), self.assertRaises(SafetyViolation):
                self.files.atomic_replace(name, b"bad", expected=first)
        for data in (b"a" * (MAX_BYTES + 1), bytearray(b"a"), "a", None):
            with self.subTest(data_type=type(data).__name__), self.assertRaises(SafetyViolation):
                self.files.atomic_replace("a.txt", data, expected=first)
        for expected in (None, asdict(first), replace(first, sha256="x" * 64)):
            with self.assertRaisesRegex(SafeReplaceError, "SAFE_EXPECTED_VERSION_REQUIRED"):
                self.files.atomic_replace("a.txt", b"bad", expected=expected)
        self.assertEqual(self.files.read("a.txt"), (first, b"before"))

    def test_existing_create_never_overwrites(self):
        first = self.files.create_new("a.txt", b"before")
        with self.assertRaisesRegex(SafeReplaceError, "DESTINATION_EXISTS"):
            self.files.create_new("a.txt", b"bad")
        self.assertEqual(self.files.read("a.txt"), (first, b"before"))

    def test_one_of_two_same_parent_cas_contenders_wins(self):
        first = self.files.create_new("a.txt", b"before")
        barrier = threading.Barrier(3)
        outcomes = []
        def worker(data):
            barrier.wait(timeout=5)
            try:
                result = self.files.atomic_replace("a.txt", data, expected=first)
            except SafeReplaceError as error:
                outcomes.append((error.code, data))
            else:
                outcomes.append(("OK", data, result))
        workers = [threading.Thread(target=worker, args=(data,), daemon=True) for data in (b"one", b"two")]
        for worker in workers:
            worker.start()
        barrier.wait(timeout=5)
        for worker in workers:
            worker.join(timeout=10)
            self.assertFalse(worker.is_alive())
        self.assertEqual(sorted(row[0] for row in outcomes), ["OK", "SAFE_TARGET_CONFLICT"])
        winner = next(row for row in outcomes if row[0] == "OK")
        self.assertEqual(self.files.read("a.txt"), (winner[2], winner[1]))

    def test_second_process_cannot_acquire_writer_guard(self):
        config = {"root": str(self.files.root), "identity": asdict(self.files.root_identity)}
        script = """import json,sys
from host.core.safe_open import FileIdentity
from host.core.safe_replace import ProtectedFileRoot,SafeReplaceError
c=json.loads(sys.stdin.read())
try: r=ProtectedFileRoot.reopen_readonly(c['root'],FileIdentity(**c['identity']))
except SafeReplaceError as e:
 assert e.code == 'SAFE_REPLACE_OPEN_DENIED', e.code
 print('SECOND_WRITER_DENIED')
else:
 r.close()
 raise AssertionError('guard acquired')
"""
        result = subprocess.run([sys.executable, "-B", "-c", script], input=json.dumps(config),
                                text=True, capture_output=True, timeout=15, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "SECOND_WRITER_DENIED")

    def test_held_root_and_ancestors_cannot_be_renamed(self):
        with self.assertRaises(OSError):
            self.files.root.rename(self.base / "moved")
        self.files.create_new("a.txt", b"still-works")

    def test_hardlinked_target_rejects_and_outside_bytes_stay_unchanged(self):
        first = self.files.create_new("a.txt", b"before")
        alias = self.base / "outside-alias"
        os.link(self.files.root / "a.txt", alias)
        try:
            with self.assertRaisesRegex(SafetyViolation, "HARDLINK_UNSAFE"):
                self.files.atomic_replace("a.txt", b"bad", expected=first)
            self.assertEqual(alias.read_bytes(), b"before")
        finally:
            alias.unlink()

    def test_owner_swap_before_open_is_detected_and_preserves_contender(self):
        first = self.files.create_new("a.txt", b"before")
        original = self.files._api.open_file
        attacked = False
        def race(path, **options):
            nonlocal attacked
            if options.get("target") and not attacked:
                attacked = True
                # Deliberate trusted-owner mutation, before the CAS check.
                path.unlink()
                path.write_bytes(b"owner-change")
            return original(path, **options)
        with mock.patch.object(self.files._api, "open_file", side_effect=race):
            with self.assertRaises(SafetyViolation):
                self.files.atomic_replace("a.txt", b"bad", expected=first)
        self.assertTrue(attacked)
        self.assertEqual((self.files.root / "a.txt").read_bytes(), b"owner-change")

    def test_namespace_flush_failure_after_replace_preserves_unknown_result(self):
        first = self.files.create_new("a.txt", b"before")
        flush = self.files._api.flush_directory
        calls = 0
        def fail_after(path, identity, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise SafetyViolation("INJECTED_FLUSH")
            return flush(path, identity, **kwargs)
        with mock.patch.object(self.files._api, "flush_directory", side_effect=fail_after):
            with self.assertRaises(SafeReplaceError) as caught:
                self.files.atomic_replace("a.txt", b"after", expected=first)
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertEqual((self.files.root / "a.txt").read_bytes(), b"after")
        with self.assertRaisesRegex(SafeReplaceError, "RECONCILIATION_REQUIRED"):
            self.files.atomic_replace("a.txt", b"must-not-retry", expected=first)

    def test_rename_failure_keeps_original_bytes_and_blocks_retry(self):
        first = self.files.create_new("a.txt", b"before")
        with mock.patch.object(self.files._api, "rename", side_effect=SafetyViolation("INJECTED_RENAME")):
            with self.assertRaises(SafeReplaceError) as caught:
                self.files.atomic_replace("a.txt", b"after", expected=first)
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertEqual((self.files.root / "a.txt").read_bytes(), b"before")
        self.assertEqual(list(self.files.root.glob(".hh-stage-*")), [])

    def test_lying_rename_cannot_ack_without_final_path(self):
        first = self.files.create_new("a.txt", b"before")
        with mock.patch.object(self.files._api, "rename", return_value=None):
            with self.assertRaises(SafeReplaceError) as caught:
                self.files.atomic_replace("a.txt", b"after", expected=first)
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertEqual((self.files.root / "a.txt").read_bytes(), b"before")

    def test_failed_close_keeps_owner_and_closes_other_operation_handle(self):
        first = self.files.create_new("a.txt", b"before")
        close, inspect = self.files._api.close, self.files._api.inspect
        failed = []
        def fail_stage(handle):
            try:
                current = inspect(handle, self.files.root / "a.txt")
            except SafetyViolation:
                return close(handle)
            if not first.identity.same_file(current):
                failed.append(handle)
                raise SafetyViolation("REAL_HANDLE_STILL_OPEN")
            return close(handle)
        baseline = len(self.files._api._owned_handles)
        with mock.patch.object(self.files._api, "close", side_effect=fail_stage):
            with self.assertRaises(SafeReplaceError) as caught:
                self.files.atomic_replace("a.txt", b"after", expected=first)
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertEqual(len(failed), 1)
        self.assertIn(failed[0], self.files._api._owned_handles)
        self.assertEqual(len(self.files._api._owned_handles), baseline + 1)
        self.files.close()
        self.assertFalse(self.files._api._owned_handles)

    def test_reopen_reads_known_version_but_cannot_resume_mutations(self):
        first = self.files.create_new("a.txt", b"before")
        root, identity = self.files.root, self.files.root_identity
        self.files.close()
        self.files = ProtectedFileRoot.reopen_readonly(root, identity)
        self.assertEqual(self.files.read("a.txt"), (first, b"before"))
        with self.assertRaisesRegex(SafeReplaceError, "REQUIRES_RECONCILIATION"):
            self.files.atomic_replace("a.txt", b"after", expected=first)
        with self.assertRaisesRegex(SafeReplaceError, "REQUIRES_RECONCILIATION"):
            self.files.create_new("new.txt", b"no")

    def test_reopen_wrong_identity_rejects(self):
        root, identity = self.files.root, self.files.root_identity
        self.files.close()
        with self.assertRaisesRegex(SafeReplaceError, "SAFE_ROOT_IDENTITY_CHANGED"):
            ProtectedFileRoot.reopen_readonly(root, replace(identity, file_id="0" * 32))

    def test_constructor_failure_keeps_cleanup_owner_until_real_close(self):
        from host.core.safe_replace import _ReplaceApi
        original = _ReplaceApi.open_file
        native_close = _ReplaceApi.close
        opened = []
        def fail_guard(api, path, **options):
            if path.name == ".writer":
                raise SafetyViolation("INJECTED_GUARD_OPEN")
            handle = original(api, path, **options)
            opened.append(handle)
            return handle
        def fail_file_close(api, handle):
            if handle in opened:
                raise SafetyViolation("REAL_CLOSE_REFUSED")
            return native_close(api, handle)
        with mock.patch.object(_ReplaceApi, "open_file", fail_guard), mock.patch.object(_ReplaceApi, "close", fail_file_close):
            with self.assertRaisesRegex(SafeReplaceError, "INIT_CLEANUP_UNCERTAIN") as caught:
                ProtectedFileRoot.create(self.base)
        owner = caught.exception.cleanup_owner
        self.assertIsNotNone(owner)
        self.assertEqual(owner._api._owned_handles, set(opened))
        owner.close()
        self.assertFalse(owner._api._owned_handles)

    def test_actual_process_cuts_keep_old_or_new_and_reopen_never_replays(self):
        script = r'''from dataclasses import asdict
import json,os,sys
from host.core.safe_replace import ProtectedFileRoot
c=json.loads(sys.stdin.read()); f=ProtectedFileRoot.create(c['parent'])
first=f.create_new('a.txt',b'before')
print(json.dumps({'root':str(f.root),'identity':asdict(f.root_identity),'first':asdict(first)}),flush=True)
def cut():
 print('SAFE_REPLACE_CUT_ARMED '+c['phase'],flush=True)
 os._exit(79)
if c['phase']=='pending':
 original=f._api.pending
 def pending(h,v):
  original(h,v)
  if v: cut()
 f._api.pending=pending
elif c['phase']=='written':
 original=f._api.write_flush
 def written(h,d):
  original(h,d); cut()
 f._api.write_flush=written
elif c['phase']=='unpending':
 original=f._api.pending
 def unpending(h,v):
  original(h,v)
  if not v: cut()
 f._api.pending=unpending
elif c['phase']=='renamed':
 original=f._api.rename
 def renamed(h,p,**kw):
  original(h,p,**kw); cut()
 f._api.rename=renamed
elif c['phase']=='barrier':
 original=f._api.flush_directory; count=0
 def barrier(p,i,**kw):
  global count
  original(p,i,**kw); count+=1
  if count==2: cut()
 f._api.flush_directory=barrier
f.atomic_replace('a.txt',b'after',expected=first)
raise AssertionError('cut not reached')
'''
        for phase in ("pending", "written", "unpending", "renamed", "barrier"):
            with self.subTest(phase=phase):
                result = subprocess.run([sys.executable, "-B", "-c", script],
                    input=json.dumps({"parent": str(self.base), "phase": phase}),
                    text=True, capture_output=True, timeout=15, cwd=ROOT)
                self.assertEqual(result.returncode, 79, result.stderr)
                self.assertEqual(result.stderr, "")
                rows = result.stdout.splitlines()
                self.assertEqual(rows[1], "SAFE_REPLACE_CUT_ARMED " + phase)
                config = json.loads(rows[0])
                expected = b"after" if phase in ("renamed", "barrier") else b"before"
                with ProtectedFileRoot.reopen_readonly(config["root"], FileIdentity(**config["identity"])) as reopened:
                    version, actual = reopened.read("a.txt")
                    self.assertEqual(actual, expected)
                    before = sorted((p.name, p.read_bytes()) for p in reopened.root.iterdir() if p.name != ".writer")
                    with self.assertRaisesRegex(SafeReplaceError, "REQUIRES_RECONCILIATION"):
                        reopened.atomic_replace("a.txt", b"must-not-replay", expected=version)
                    after = sorted((p.name, p.read_bytes()) for p in reopened.root.iterdir() if p.name != ".writer")
                    self.assertEqual(before, after)
                    stages = list(reopened.root.glob(".hh-stage-*"))
                    self.assertEqual(len(stages), 1 if phase == "unpending" else 0)


if __name__ == "__main__":
    unittest.main()
