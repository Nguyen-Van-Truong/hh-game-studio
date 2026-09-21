"""Fixed private slots and bounded real GLB decoding, with no native process."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import stat
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pipeline import admission_worker as worker


def tiny_glb():
    binary = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
    document = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": len(binary)}],
                "bufferViews": [{"buffer": 0, "byteLength": len(binary)}],
                "accessors": [{"bufferView": 0, "componentType": 5126, "type": "VEC3", "count": 3,
                               "min": [0, 0, 0], "max": [1, 1, 0]}],
                "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}], "nodes": [{"mesh": 0}]}
    text = json.dumps(document, separators=(",", ":")).encode()
    text += b" " * (-len(text) % 4)
    chunks = struct.pack("<II", len(text), 0x4E4F534A) + text + struct.pack("<II", len(binary), 0x004E4942) + binary
    return struct.pack("<4sII", b"glTF", 2, len(chunks) + 12) + chunks


class AdmissionWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gt05-admission-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.raw = tiny_glb()
        (self.root / "fixture.glb").write_bytes(self.raw)
        (self.root / "expected.json").write_text(json.dumps({"artifact_sha256": hashlib.sha256(self.raw).hexdigest()}),
                                                  encoding="utf-8")

    def rejects(self, code):
        with self.assertRaises(worker.AdmissionRejected) as caught:
            worker.run_admission(self.root)
        self.assertEqual(str(caught.exception), code)

    def no_outputs(self):
        self.assertFalse((self.root / "preflight.json").exists())
        self.assertFalse((self.root / "semantic.json").exists())

    def test_real_admission_output_hashes_and_exact_single_marker(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = worker.main([str(self.root)])
        self.assertEqual((code, stderr.getvalue()), (0, ""))
        lines = stdout.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith(worker.MARKER))
        marker = json.loads(lines[0][len(worker.MARKER):])
        preflight = (self.root / "preflight.json").read_bytes()
        semantic = (self.root / "semantic.json").read_bytes()
        self.assertEqual(marker, {"artifact_sha256": hashlib.sha256(self.raw).hexdigest(),
                                  "preflight_sha256": hashlib.sha256(preflight).hexdigest(),
                                  "semantic_sha256": hashlib.sha256(semantic).hexdigest()})
        self.assertTrue(preflight.endswith(b"\n") and semantic.endswith(b"\n"))
        report = json.loads(preflight)
        self.assertEqual(report["core_semantics"]["mesh_triangles"], [1])
        self.assertEqual(report["decoded_scalars"], 9)
        self.assertFalse(report["formal_acceptance"] or report["public_ack"])
        self.assertEqual(report["semantic_sha256"], hashlib.sha256(semantic[:-1]).hexdigest())
        self.assertEqual(json.loads(semantic)["accessors"][0]["values"][1], [1.0, 0.0, 0.0])
        self.assertEqual((self.root / "fixture.glb").read_bytes(), self.raw)

    def test_script_entry_point_accepts_one_root_without_package_context(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", [worker.__file__, str(self.root)]), patch.object(sys, "path", list(sys.path)), \
                redirect_stdout(stdout), redirect_stderr(stderr), self.assertRaises(SystemExit) as exited:
            runpy.run_path(worker.__file__, run_name="__main__")
        self.assertEqual(exited.exception.code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertTrue(stdout.getvalue().startswith(worker.MARKER))

    def test_wrong_hash_rejects_before_inspection(self):
        (self.root / "expected.json").write_text(json.dumps({"artifact_sha256": "0" * 64}), encoding="utf-8")
        with patch.object(worker, "inspect_asset", side_effect=AssertionError("must verify input")):
            self.rejects("ADMISSION_ARTIFACT_HASH")
        self.no_outputs()

    def test_oversized_glb_and_expected_are_rejected_before_any_open_read(self):
        for name, limit in (("fixture.glb", worker.MAX_GLB_BYTES), ("expected.json", worker.MAX_EXPECTED_BYTES)):
            with self.subTest(name=name):
                path = self.root / name
                saved = path.read_bytes()
                path.write_bytes(b"x" * (limit + 1))
                with patch.object(Path, "open", side_effect=AssertionError("oversize must be pre-read")):
                    self.rejects("ADMISSION_INPUT_SIZE_LIMIT")
                path.write_bytes(saved)
        self.no_outputs()

    def test_expected_strict_fields_unicode_duplicates_and_nonfinite(self):
        hash_ = hashlib.sha256(self.raw).hexdigest()
        cases = ((json.dumps({"artifact_sha256": hash_, "path": "../outside.glb"}).encode(), "ADMISSION_EXPECTED_FIELDS"),
                 ((f'{{"artifact_sha256":"{hash_}","artifact_sha256":"{hash_}"}}').encode(), "ADMISSION_EXPECTED_DUPLICATE_KEY"),
                 (b'{"artifact_sha256":NaN}', "ADMISSION_EXPECTED_NONFINITE"),
                 (b'{"artifact_sha256":true}', "ADMISSION_EXPECTED_FIELDS"),
                 (b'{"artifact_sha256":"\\ud800"}', "ADMISSION_EXPECTED_FIELDS"),
                 (b'[]', "ADMISSION_EXPECTED_FIELDS"), (b'\xff', "ADMISSION_EXPECTED_JSON"),
                 (json.dumps({"artifact_sha256": hash_.upper()}).encode(), "ADMISSION_EXPECTED_FIELDS"),
                 (b'{', "ADMISSION_EXPECTED_JSON"))
        for raw, code in cases:
            with self.subTest(code=code, raw=raw[:32]):
                (self.root / "expected.json").write_bytes(raw)
                self.rejects(code)
        self.no_outputs()

    def test_fixed_inputs_cannot_be_renamed_or_supplied_through_extra_arguments(self):
        (self.root / "fixture.glb").rename(self.root / "elsewhere.glb")
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = worker.main([str(self.root)])
        self.assertEqual((code, stdout.getvalue(), stderr.getvalue()), (17, "", "ADMISSION_FAILED\n"))
        for args in ([], [str(self.root), "elsewhere.glb"], [str(self.root), "--output=elsewhere.json"]):
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                self.assertEqual(worker.main(args), 17)
            self.assertEqual((stdout.getvalue(), stderr.getvalue()), ("", "ADMISSION_ARGUMENTS\n"))
        self.no_outputs()

    def test_existing_either_output_rejects_before_inspection_without_overwrite(self):
        for name in ("preflight.json", "semantic.json"):
            with self.subTest(name=name):
                target = self.root / name
                target.write_bytes(b"existing evidence")
                with patch.object(worker, "inspect_asset", side_effect=AssertionError("exclusive slots")):
                    self.rejects("ADMISSION_OUTPUT_EXISTS")
                self.assertEqual(target.read_bytes(), b"existing evidence")
                self.assertFalse((self.root / ("semantic.json" if name == "preflight.json" else "preflight.json")).exists())
                target.unlink()

    def test_late_duplicate_output_is_detected_before_writing_pair(self):
        inspect = worker.inspect_asset

        def intervening_write(raw):
            (self.root / "semantic.json").write_bytes(b"other owner")
            return inspect(raw)

        with patch.object(worker, "inspect_asset", side_effect=intervening_write):
            self.rejects("ADMISSION_OUTPUT_EXISTS")
        self.assertFalse((self.root / "preflight.json").exists())
        self.assertEqual((self.root / "semantic.json").read_bytes(), b"other owner")

    def test_outputs_have_explicit_limits_before_creation(self):
        self.assertEqual((worker.MAX_PREFLIGHT_BYTES, worker.MAX_SEMANTIC_BYTES), (1_048_576, 16_777_216))
        for name in ("MAX_PREFLIGHT_BYTES", "MAX_SEMANTIC_BYTES"):
            with self.subTest(name=name), patch.object(worker, name, 1):
                self.rejects("ADMISSION_OUTPUT_SIZE_LIMIT")
            self.no_outputs()
        self.assertEqual(worker._encoded({"a": 1}, 8), b'{"a":1}\n')
        with self.assertRaisesRegex(worker.AdmissionRejected, "^ADMISSION_OUTPUT_SIZE_LIMIT$"):
            worker._encoded({"a": 1}, 7)

    def test_input_changed_during_inspection_has_no_outputs(self):
        inspect = worker.inspect_asset

        def mutate(raw):
            (self.root / "fixture.glb").write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
            return inspect(raw)

        with patch.object(worker, "inspect_asset", side_effect=mutate):
            self.rejects("ADMISSION_STAGED_INPUT_CHANGED")
        self.no_outputs()

    def test_expected_changed_during_inspection_has_no_outputs(self):
        inspect = worker.inspect_asset

        def mutate(raw):
            (self.root / "expected.json").write_bytes(b"{}")
            return inspect(raw)

        with patch.object(worker, "inspect_asset", side_effect=mutate):
            self.rejects("ADMISSION_STAGED_INPUT_CHANGED")
        self.no_outputs()

    def test_hardlinked_input_is_rejected_before_open(self):
        alias = self.root / "alias.glb"
        os.link(self.root / "fixture.glb", alias)
        with patch.object(Path, "open", side_effect=AssertionError("hard link must not open")):
            self.rejects("ADMISSION_REGULAR_SINGLE_LINK_REQUIRED")
        self.no_outputs()

    def test_directory_and_simulated_reparse_inputs_are_rejected_before_open(self):
        path = self.root / "fixture.glb"
        path.unlink()
        path.mkdir()
        with patch.object(Path, "open", side_effect=AssertionError("directory must not open")):
            self.rejects("ADMISSION_REGULAR_SINGLE_LINK_REQUIRED")
        for mode, attributes in ((stat.S_IFREG, 0x400), (stat.S_IFLNK, 0), (stat.S_IFIFO, 0)):
            info = SimpleNamespace(st_mode=mode, st_file_attributes=attributes, st_nlink=1, st_size=10)
            with patch.object(Path, "lstat", return_value=info), patch.object(Path, "open", side_effect=AssertionError("unsafe open")):
                with self.assertRaisesRegex(worker.AdmissionRejected, "^ADMISSION_REGULAR_SINGLE_LINK_REQUIRED$"):
                    worker._read_bounded(path, worker.MAX_GLB_BYTES)

    def test_relative_parent_network_alias_and_reparse_roots_rejected(self):
        for root in (Path("relative"), self.root / "..", Path("//server/share/private"), self.root / "alias."):
            with self.subTest(root=root), self.assertRaises(worker.AdmissionRejected):
                worker.run_admission(root)
        info = SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        with patch.object(Path, "lstat", return_value=info), self.assertRaisesRegex(worker.AdmissionRejected,
                "^ADMISSION_ROOT_DIRECTORY_OR_REPARSE$"):
            worker.run_admission(self.root)

    def test_errors_are_sanitized_and_never_emit_success_marker(self):
        with patch.object(worker, "inspect_asset", side_effect=RuntimeError("private candidate path or secret")):
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                self.assertEqual(worker.main([str(self.root)]), 17)
        self.assertEqual((stdout.getvalue(), stderr.getvalue()), ("", "ADMISSION_FAILED\n"))
        self.no_outputs()


if __name__ == "__main__":
    unittest.main()
