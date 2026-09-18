"""Regression checks for boundaries that previously rejected valid evidence."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_gt02_candidate import redact_golden_stream, source_manifest
from host.core.redaction import Redactor
from host.core.limits import SafetyViolation


class CandidateEvidenceTests(unittest.TestCase):
    def test_source_freeze_rejects_line_endings_git_would_rewrite(self):
        with tempfile.TemporaryDirectory(prefix="gt02-source-lf-") as directory:
            studio = Path(directory)
            path = studio / "toolchain.lock.json"
            path.write_bytes(b"{}\r\n")
            with self.assertRaisesRegex(ValueError, "SOURCE_TEXT_NOT_LF"):
                source_manifest(studio)
            path.write_bytes(b"{}\n")
            self.assertEqual(set(source_manifest(studio)), {"toolchain.lock.json"})

    def test_unicode_separators_do_not_split_public_vector_record(self):
        # A real large Godot result contained Unicode line separators inside
        # strings. Preserve the exact result while scrubbing diagnostics.
        row = {"canonical": "\u0085\u2028\u2029" + "x" * 70_000}
        marker = "HH_GT02_JCS " + json.dumps({"rows": [row], "rejected": {}}, ensure_ascii=False)
        raw = "token=fixture-secret\n" + marker + "\n"
        clean = redact_golden_stream(raw, Redactor(secrets=["fixture-secret"]))
        self.assertEqual(clean, "[REDACTED]\n" + marker + "\n")
        self.assertNotIn("fixture-secret", clean)

    def test_oversized_diagnostic_still_fails_closed(self):
        with self.assertRaises(SafetyViolation):
            redact_golden_stream("x" * 70_000, Redactor())


if __name__ == "__main__":
    unittest.main()
