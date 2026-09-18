from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from host.core.limits import (  # noqa: E402
    DEFAULT_LIMITS,
    SafePathResolver,
    SafetyViolation,
    canonical_json,
    parse_json_utf8,
    payload_digest,
    validate_envelope,
)


class LimitsTests(unittest.TestCase):
    def envelope(self) -> dict:
        payload = {"name": "café", "n": 1}
        return {
            "schema_version": "hh-studio-0.1",
            "command_id": "cmd-1",
            "project_id": "project-1",
            "operation": "fixture.inspect",
            "lease_id": "lease-1", "fencing_epoch": 1, "expected_revision": "rev-1",
            "target": {"path": "main.tscn"},
            "payload": payload,
            "payload_hash": payload_digest("fixture.inspect", {"path": "main.tscn"}, payload, "hh-studio-0.1"),
            "deadline_ms": 1_000,
        }

    def test_valid_and_hash_binds_schema_operation_target(self):
        result = validate_envelope(self.envelope(), now_ms=0)
        self.assertEqual(result["command_id"], "cmd-1")
        altered = self.envelope()
        altered["target"] = {"path": "other.tscn"}
        self.assertEqual(validate_envelope(altered, now_ms=0)["target"], {"path": "other.tscn"})

    def test_missing_wrong_deadline_and_large_integer_reject(self):
        bad = self.envelope()
        del bad["payload_hash"]
        with self.assertRaisesRegex(SafetyViolation, "MISSING_FIELD"):
            validate_envelope(bad, now_ms=0)
        bad = self.envelope()
        bad["deadline_ms"] = 99_000_000
        with self.assertRaisesRegex(SafetyViolation, "DEADLINE_OUT_OF_RANGE"):
            validate_envelope(bad, now_ms=0)
        with self.assertRaisesRegex(SafetyViolation, "INTEGER_REQUIRES_DECIMAL_STRING"):
            canonical_json({"large": 1 << 60})

    def test_duplicate_invalid_utf8_and_nonfinite_reject(self):
        with self.assertRaisesRegex(SafetyViolation, "DUPLICATE_KEY"):
            parse_json_utf8(b'{"a":1,"a":2}')
        with self.assertRaisesRegex(SafetyViolation, "INVALID_UTF8"):
            parse_json_utf8(b"\xff")
        with self.assertRaisesRegex(SafetyViolation, "NON_FINITE_NUMBER"):
            parse_json_utf8(b'{"a":NaN}')

    def test_canonical_json_is_stable_and_preserves_unicode(self):
        self.assertEqual(canonical_json({"b": 2, "a": "é"}), '{"a":"é","b":2}'.encode())
        # NFC/NFD are distinct wire payloads; domain validation owns names.
        self.assertNotEqual(canonical_json({"x": "é"}), canonical_json({"x": "e\u0301"}))

    def test_path_resolver_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ok.txt").write_text("ok", encoding="utf-8")
            resolver = SafePathResolver(root)
            self.assertEqual(resolver.resolve("ok.txt", require_existing=True).name, "ok.txt")
            for path in ("../outside", "foo/../outside", "C:\\outside", "\\\\server\\share", r"\\.\NUL", "x:stream"):
                with self.assertRaises(SafetyViolation):
                    resolver.resolve(path)
            with self.assertRaisesRegex(SafetyViolation, "UNSUPPORTED_SAFE_OPEN"):
                resolver.resolve("new.txt", for_write=True)

    def test_symlink_is_rejected_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.txt"
            target.write_text("ok", encoding="utf-8")
            link = root / "link.txt"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlink unavailable on this host")
            with self.assertRaisesRegex(SafetyViolation, "REPARSE_OR_SYMLINK"):
                SafePathResolver(root).resolve("link.txt", require_existing=True)


if __name__ == "__main__":
    unittest.main()
