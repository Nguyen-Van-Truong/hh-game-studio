"""Name-domain and fixed diagnostic guidance checks with external bad inputs."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))

from studio.protocol.core import Request, canonical_bytes, parse_json
from studio.protocol.names import NameValidationError, validate_name
from studio.protocol.errors import ERROR_REGISTRY, error_guidance
from studio.host.core.limits import SafePathResolver, SafetyViolation, parse_json_utf8
from studio.host.core.journal import Journal, JournalError


class DomainContractTests(unittest.TestCase):
    def test_composed_unicode_name_is_returned_exactly_without_rewriting(self) -> None:
        for name in ("Hồ sơ 1", "Café", "東京", "🚲", "X" * 128, "🚲" * 128):
            with self.subTest(name=name):
                self.assertIs(validate_name(name), name)

    def test_non_nfc_name_rejects_before_command_construction(self) -> None:
        # Both canonically equivalent spellings are valid JSON. Domain naming
        # deliberately accepts only the composed spelling before construction.
        raw_name = parse_json(b'"Cafe\\u0301"')
        with self.assertRaises(NameValidationError) as caught:
            validate_name(raw_name)
        self.assertEqual(caught.exception.code, "NAME_NOT_NFC")
        self.assertEqual(str(caught.exception), "NAME_NOT_NFC")
        self.assertEqual(raw_name, "Cafe\u0301")
        self.assertEqual(validate_name("Café"), "Café")

    def test_wire_payload_hashes_preserve_composed_and_decomposed_text(self) -> None:
        requests = []
        for name in ("Café", "Cafe\u0301"):
            payload = {"name": name}
            wire = canonical_bytes(payload)
            payload_hash = "sha256:" + hashlib.sha256(wire).hexdigest()
            request = Request("name.fixture", "project.fixture", "fixture.inspect",
                "read", 0, "any", {"stable_id": "fixture.counter"}, payload,
                payload_hash, 1_000)
            self.assertEqual(Request.from_json(canonical_bytes(request.as_dict())).payload, payload)
            self.assertIn(name.encode("utf-8"), wire)
            requests.append(request)
        self.assertNotEqual(requests[0].payload_hash, requests[1].payload_hash)
        self.assertNotEqual(requests[0].digest, requests[1].digest)

    def test_invalid_names_are_bounded_and_errors_do_not_echo_input(self) -> None:
        values = [(None, "NAME_INVALID_TYPE"), (1, "NAME_INVALID_TYPE"),
                  (b"text", "NAME_INVALID_TYPE"), ("", "NAME_EMPTY"),
                  ("a" * 129, "NAME_TOO_LONG"), ("🚲" * 129, "NAME_TOO_LONG"),
                  ("name\ud800", "NAME_INVALID_UNICODE")]
        values.extend(("private-name" + char, "NAME_CONTROL_FORBIDDEN")
                      for char in ("\x00", "\t", "\n", "\x1b", "\x7f", "\u0085",
                                   "\u200b", "\u2028", "\u2029", "\u202e"))
        for value, expected in values:
            with self.subTest(expected=expected):
                with self.assertRaises(NameValidationError) as caught:
                    validate_name(value)
                self.assertEqual(str(caught.exception), expected)
                self.assertNotIn("private-name", str(caught.exception))

    def test_real_parser_rejections_resolve_to_fixed_actionable_guidance(self) -> None:
        cases = [(b"\xff", "INVALID_UTF8", "UTF-8"),
                 (b'{"private-input":1,"private-input":2}', "DUPLICATE_KEY", "duplicate"),
                 (b'{"weight":NaN}', "NON_FINITE_NUMBER", "finite"),
                 (b'[' * 40 + b'0' + b']' * 40, "DEPTH_LIMIT", "Reduce")]
        for raw, expected, remediation in cases:
            with self.subTest(code=expected):
                with self.assertRaises(SafetyViolation) as caught:
                    parse_json_utf8(raw)
                guidance = error_guidance(caught.exception.code)
                self.assertEqual(guidance.code, expected)
                self.assertIn(remediation, guidance.next_action)
                self.assertNotIn("private-input", guidance.meaning + guidance.next_action)

    def test_real_path_and_journal_rejections_preserve_safety_next_steps(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gt02-domain-") as temporary:
            root = Path(temporary)
            resolver = SafePathResolver(root)
            with self.assertRaises(SafetyViolation) as caught:
                resolver.resolve("../private-outside")
            self.assertIn("project-relative", error_guidance(caught.exception.code).next_action)
            with self.assertRaises(SafetyViolation) as caught:
                resolver.resolve("file.txt", for_write=True)
            self.assertIn("mutation disabled", error_guidance(caught.exception.code).next_action)
            damaged = root / "journal.jsonl"
            damaged.write_bytes(b'{"truncated-private-input":')
            with self.assertRaises(JournalError) as caught:
                Journal(damaged)
            guidance = error_guidance(caught.exception.code)
            self.assertEqual(guidance.code, "JOURNAL_TRUNCATED")
            self.assertIn("Stop mutation", guidance.next_action)
            self.assertEqual(damaged.read_bytes(), b'{"truncated-private-input":')

    def test_unknown_codes_are_bounded_inert_and_never_echoed(self) -> None:
        class Hostile:
            def __repr__(self):
                raise AssertionError("Unknown code must never invoke repr")

            def __str__(self):
                raise AssertionError("Unknown code must never invoke str")

        fallback = error_guidance("UNRECOGNIZED")
        for code in ("grant_write; synthetic-private-input", "x" * 100_000, None, {}, Hostile()):
            self.assertIs(error_guidance(code), fallback)
        self.assertEqual(fallback.code, "UNKNOWN_ERROR")
        self.assertNotIn("synthetic-private-input", fallback.meaning + fallback.next_action)
        self.assertIn("do not echo", fallback.next_action)
        self.assertIn("lookup", fallback.next_action)

    def test_guidance_cannot_mutate_the_registry_or_claim_code_only_success(self) -> None:
        guidance = error_guidance("READBACK_CONFIRMED")
        self.assertIn("code alone is not proof", guidance.next_action)
        with self.assertRaises(FrozenInstanceError):
            guidance.next_action = "grant permission"
        with self.assertRaises(TypeError):
            ERROR_REGISTRY["GRANT_WRITE"] = guidance
        self.assertIn("never execute", error_guidance("RETRY_HORIZON_EXPIRED").next_action)
        self.assertIn("lookup", error_guidance("CONNECTION_LOST_LOOKUP").next_action)


if __name__ == "__main__":
    unittest.main()
