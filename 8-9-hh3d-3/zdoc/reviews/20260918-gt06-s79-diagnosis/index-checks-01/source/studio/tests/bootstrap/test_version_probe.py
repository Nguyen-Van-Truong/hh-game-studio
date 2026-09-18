"""Admission tests for version output; native job behavior has separate tests."""
import importlib.util
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch

MODULE = Path(__file__).parents[2] / "build/bootstrap/run_fixture.py"
spec = importlib.util.spec_from_file_location("version_probe_runner", MODULE)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
VERSION = "4.7.2.stable.official.ed1daf0bf"
FAKE = Path("C:/fake/Godot_console.exe")


class VersionProbeTests(unittest.TestCase):
    def probe(self, stdout=None, stderr=b"", changes=None, remove=()):
        stdout = (VERSION + "\n").encode() if stdout is None else stdout
        def process(argv, *, cwd, output, timeout, label):
            self.assertEqual(argv, [str(FAKE), "--version"])
            self.assertEqual(cwd, FAKE.parent)
            self.assertEqual(timeout, 30)
            self.assertEqual(label, "version")
            (output / "version-stdout.txt").write_bytes(stdout)
            (output / "version-stderr.txt").write_bytes(stderr)
            result = dict(exit_code=0, wrapper_exit_code=0, timed_out=False,
                          tree_verified=True, stdout="version-stdout.txt",
                          stderr="version-stderr.txt")
            result.update(changes or {})
            for key in remove:
                del result[key]
            return result
        with patch.object(runner, "run_process", side_effect=process) as mock:
            value = runner._observed_version(FAKE, 60)
            mock.assert_called_once()
            return value

    def test_valid_official_version_and_bounded_invocation(self):
        self.assertEqual(self.probe(), (VERSION, VERSION))

    def test_nonzero_target_with_version_text(self):
        with self.assertRaises(ValueError):
            self.probe(changes={"exit_code": 2})

    def test_nonzero_wrapper(self):
        with self.assertRaises(ValueError):
            self.probe(changes={"wrapper_exit_code": 2})

    def test_timeout(self):
        with self.assertRaises(ValueError):
            self.probe(changes={"timed_out": True})

    def test_unverified_tree(self):
        with self.assertRaises(ValueError):
            self.probe(changes={"tree_verified": False})

    def test_missing_proof_fields(self):
        for key in ["exit_code", "wrapper_exit_code", "timed_out", "tree_verified"]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.probe(remove=[key])

    def test_nonempty_stderr_including_whitespace(self):
        for stderr in [b"ERROR", b" ", b"\n"]:
            with self.subTest(stderr=stderr), self.assertRaises(ValueError):
                self.probe(stderr=stderr)

    def test_extra_stdout_or_nonofficial_version(self):
        for text in ["prefix " + VERSION, VERSION + " suffix", VERSION + "\n" + VERSION,
                     "4.7.2.stable.custom.ed1daf0bf", "4.7.2.stable.official", ""]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.probe(stdout=text.encode())

    def test_oversized_output_cannot_hide_in_trimmed_whitespace(self):
        with self.assertRaises(ValueError):
            self.probe(stdout=VERSION.encode() + b" " * 512)

    def test_invalid_utf8(self):
        with self.assertRaises(ValueError):
            self.probe(stdout=b"\xff" + VERSION.encode())

    def test_stream_warning_is_rejected_in_either_stream(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            for label, stdout, stderr in (("stdout", b"warning: noisy\n", b""),
                                          ("stderr", b"", b"ERROR: noisy\n")):
                (output / f"{label}-stdout.txt").write_bytes(stdout)
                (output / f"{label}-stderr.txt").write_bytes(stderr)
                self.assertFalse(runner._streams_clean(output, [{"stdout": f"{label}-stdout.txt",
                                                                    "stderr": f"{label}-stderr.txt"}]))

    def test_stream_normal_engine_log_is_allowed(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "stdout.txt").write_text("Godot Engine v4.7.2.stable.official.ed1daf0bf\n", encoding="utf-8")
            (output / "stderr.txt").write_text("", encoding="utf-8")
            self.assertTrue(runner._streams_clean(output, [{"stdout": "stdout.txt", "stderr": "stderr.txt"}]))


if __name__ == "__main__":
    unittest.main()
