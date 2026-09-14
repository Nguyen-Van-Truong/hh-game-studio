"""Executable output-boundary checks, using only synthetic secret fixtures."""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from host.core.limits import SafetyViolation
from host.core.redaction import REDACTED, RedactedBoundary, RedactionLimits, Redactor


class RedactionTests(unittest.TestCase):
    def test_real_log_receipt_output_file_contains_only_redacted_bytes(self):
        secret = "synthetic-session-\u00e9-001"
        secret2 = "synthetic-other-password"
        source = {"authorization": secret, "message": f"parser failed near {secret}",
                  "metadata": [{"private-key": secret2}], "path": "C:\\Users\\fixture-user\\secret.txt",
                  "argv": ["app", "--password", secret2], "environment": {"ODD_VAR": secret2},
                  "capture": b"opaque-image-containing-a-secret"}
        with tempfile.TemporaryDirectory(prefix="gt02-redaction-") as tmp:
            destination = Path(tmp) / "boundary.jsonl"
            with destination.open("wb") as stream:
                boundary = RedactedBoundary(stream.write, redactor=Redactor(secrets=(secret,)))
                for kind in ("log", "receipt", "output"):
                    result = boundary.emit(kind, source)
                    self.assertEqual(result["payload"]["authorization"], REDACTED)
            raw = destination.read_bytes()
            for value in (secret, secret2, "fixture-user"):
                self.assertNotIn(value.encode(), raw)
            records = [json.loads(line) for line in raw.splitlines()]
            self.assertEqual([row["kind"] for row in records], ["log", "receipt", "output"])
            self.assertEqual(source["authorization"], secret)

    def test_registered_secret_encodings_and_parser_fragments(self):
        secret = 'synthetic"-\u00e9+secret'
        redactor = Redactor(secrets=(secret,))
        variants = (secret, json.dumps(secret)[1:-1], quote(secret, safe=""),
                    base64.b64encode(secret.encode()).decode())
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertNotIn(variant, redactor.text("invalid payload near " + variant))
        for fragment in ('{"password":"unknown arbitrary secret',
                         'Authorization: Bearer unknown-value', 'password = "value with spaces"',
                         '--access-token unknown-value'):
            self.assertEqual(redactor.text(fragment), REDACTED)

    def test_host_paths_and_registered_roots_do_not_escape(self):
        redactor = Redactor(host_paths=(r"D:\private workspace",))
        for path in (r"D:\private workspace\source.txt", r"\\server\share\file",
                     "/home/person/private/file", r"C:\Users\person\a b.txt"):
            self.assertNotIn("person", redactor.text(path))
            self.assertNotIn(path, redactor.text(path))
        self.assertEqual(redactor.redact({"relative": "src/main.py"}), {"relative": "src/main.py"})

    def test_deterministic_encoding_and_no_source_mutation(self):
        a = {"z": 1, "token": "fixture-value", "a": {"y": 2, "x": 3}}
        b = {"a": {"x": 3, "y": 2}, "token": "other-secret", "z": 1}
        redactor = Redactor()
        self.assertEqual(redactor.encode(a), redactor.encode(b))
        self.assertEqual(a["token"], "fixture-value")
        self.assertEqual(redactor.encode({"number": 1e-7}), b'{"number":1e-7}')

    def test_registration_bounded_and_repr_does_not_expose_secrets(self):
        redactor = Redactor(secrets=("secret-fixture",))
        self.assertNotIn("secret-fixture", repr(redactor))
        with self.assertRaisesRegex(SafetyViolation, "REGISTRATION_LIMIT"):
            Redactor(secrets=(str(n) for n in range(10000)))
        with self.assertRaisesRegex(SafetyViolation, "INVALID_REDACTION_REGISTRATION"):
            Redactor(secrets=("",))

    def test_sensitive_containers_are_omitted_without_serializing(self):
        class Hostile:
            def __repr__(self):
                raise AssertionError("repr must not be called")
        value = {"argv": Hostile(), "env": Hostile(), "capture": Hostile(), "password": Hostile()}
        self.assertTrue(all(item == REDACTED for item in Redactor().redact(value).values()))
        with self.assertRaisesRegex(SafetyViolation, "UNSUPPORTED_TYPE"):
            Redactor().encode({"other": Hostile()})

    def test_cycles_depth_nodes_strings_and_output_caps_reject_before_sink(self):
        cyclic = []
        cyclic.append(cyclic)
        nested: object = 1
        for _ in range(25):
            nested = [nested]
        cases = [(Redactor(), cyclic, "CYCLE"), (Redactor(), nested, "DEPTH_LIMIT"),
                 (Redactor(limits=RedactionLimits(max_nodes=3)), [1, 2, 3, 4], "NODE_LIMIT"),
                 (Redactor(limits=RedactionLimits(max_text_chars=4)), "abcdef", "TEXT_LIMIT"),
                 (Redactor(limits=RedactionLimits(max_output_bytes=1)), {}, "OUTPUT_LIMIT"),
                 (Redactor(limits=RedactionLimits(max_total_text_chars=3)), ["aa", "bb"], "TOTAL_TEXT_LIMIT")]
        for redactor, payload, code in cases:
            with self.subTest(code=code):
                sink = io.BytesIO()
                with self.assertRaises(SafetyViolation):
                    RedactedBoundary(sink.write, redactor=redactor).emit("output", payload)
                self.assertEqual(sink.getvalue(), b"")
                with self.assertRaisesRegex(SafetyViolation, code):
                    redactor.encode(payload)

    def test_invalid_unicode_and_binary_do_not_echo_input(self):
        redactor = Redactor()
        self.assertEqual(redactor.text(b"secret\xff"), "[REDACTED:INVALID_UTF8]")
        self.assertEqual(redactor.text("secret\ud800"), "[REDACTED:INVALID_UNICODE]")
        with self.assertRaisesRegex(SafetyViolation, "UNSUPPORTED_TYPE"):
            redactor.encode(b"opaque secret")

    def test_nonfinite_unknown_keys_and_redacted_collision_fail_closed(self):
        for payload, code in ((float("nan"), "INVALID_NUMBER"), ({1: "x"}, "INVALID_KEY"),
                              ({"secret-a": 1, "secret-b": 2}, "KEY_COLLISION")):
            with self.subTest(code=code), self.assertRaisesRegex(SafetyViolation, code):
                Redactor(secrets=("secret-a", "secret-b")).encode(payload)

    def test_no_recursive_secret_marker_expansion(self):
        value = Redactor(secrets=("A", "R", "E")).text("AAA")
        self.assertEqual(value, REDACTED * 3)

    def test_sink_error_does_not_leak_exception_detail(self):
        def bad_sink(_):
            raise OSError("synthetic secret path")
        with self.assertRaises(SafetyViolation) as caught:
            RedactedBoundary(bad_sink, redactor=Redactor()).emit("log", {"code": "ERROR"})
        self.assertEqual(str(caught.exception), "OUTPUT_SINK_FAILED")
        with self.assertRaisesRegex(SafetyViolation, "OUTPUT_SINK_FAILED"):
            RedactedBoundary(lambda _: 1, redactor=Redactor()).emit("log", {})


if __name__ == "__main__":
    unittest.main()
