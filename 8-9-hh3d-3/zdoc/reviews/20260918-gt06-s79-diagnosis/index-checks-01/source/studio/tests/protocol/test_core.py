import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2].parent))
from studio.protocol import (  # noqa: E402
    Request, Response, Status, ValidationError, canonical_bytes,
    canonical_json, parse_json, resolve_project_path,
)


def payload_hash(payload):
    return "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest()


class ProtocolCoreTests(unittest.TestCase):
    def request(self, **changes):
        payload = {"text": "ok"}
        data = {
            "command_id": "cmd-1", "schema_version": "hh-studio-0.1",
            "project_id": "project-a", "operation": "scene.inspect",
            "lease_id": "lease-1", "fencing_epoch": 0,
            "expected_revision": "rev-1", "target": {"path": "main.tscn"},
            "payload": payload, "payload_hash": payload_hash(payload), "deadline_ms": 1000,
        }
        data.update(changes)
        return data

    def test_canonical_and_duplicate_reject(self):
        self.assertEqual(canonical_json({"z": 1, "a": 2}), '{"a":2,"z":1}')
        with self.assertRaisesRegex(ValidationError, "DUPLICATE_KEY"):
            parse_json('{"a":1,"a":2}')
        with self.assertRaisesRegex(ValidationError, "INVALID_NUMBER"):
            parse_json('{"a":NaN}')

    def test_jcs_number_vectors_and_utf16_key_order(self):
        # RFC 8785 Appendix B / ECMAScript-compatible rendering.
        self.assertEqual(canonical_json({"n": -0.0}), '{"n":0}')
        self.assertEqual(canonical_json({"n": 1e-7}), '{"n":1e-7}')
        self.assertEqual(canonical_json({"n": 1e20}), '{"n":100000000000000000000}')
        self.assertEqual(canonical_json({"\U00010000": 1, "\uffff": 2}), '{"𐀀":1,"￿":2}')

    def test_unicode_and_large_integer_reject(self):
        with self.assertRaisesRegex(ValidationError, "INVALID_UNICODE"):
            canonical_json({"x": "\ud800"})
        with self.assertRaisesRegex(ValidationError, "INTEGER_REQUIRES_DECIMAL_STRING"):
            canonical_json({"x": 9_007_199_254_740_992})

    def test_request_hash_digest_and_schema(self):
        req = Request.from_dict(self.request())
        self.assertTrue(req.digest.startswith("sha256:"))
        self.assertEqual(Request.from_dict(req.as_dict()).digest, req.digest)
        with self.assertRaisesRegex(ValidationError, "DIGEST_MISMATCH"):
            Request.from_dict({**req.as_dict(), "digest": "sha256:" + "0" * 64})
        with self.assertRaisesRegex(ValidationError, "PAYLOAD_HASH_MISMATCH"):
            Request.from_dict(self.request(payload_hash="sha256:bad"))
        with self.assertRaisesRegex(ValidationError, "UNSUPPORTED_SCHEMA"):
            Request.from_dict(self.request(schema_version="9.0"))
        with self.assertRaisesRegex(ValidationError, "UNKNOWN_FIELD"):
            Request.from_dict(self.request(unexpected=True))

    def test_forbidden_secret_and_invalid_target(self):
        p = {"api_token": "redacted"}
        with self.assertRaisesRegex(ValidationError, "SECRET_FIELD_FORBIDDEN"):
            Request.from_dict(self.request(payload=p, payload_hash=payload_hash(p)))
        with self.assertRaisesRegex(ValidationError, "INVALID_TARGET"):
            Request.from_dict(self.request(target={"path": "a", "stable_id": "b"}))

    def test_response_status(self):
        response = Response("COMMITTED", "OK", "cmd-1", postconditions={"revision": "r2"})
        self.assertEqual(response.as_dict()["status"], "COMMITTED")
        with self.assertRaisesRegex(ValidationError, "INVALID_STATUS"):
            Response("DONE", "OK", "cmd-1")

    def test_path_root_traversal_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ok").mkdir()
            self.assertEqual(resolve_project_path(root, "ok/file.txt"), root / "ok/file.txt")
            with self.assertRaisesRegex(ValidationError, "PATH_OUTSIDE_ROOT"):
                resolve_project_path(root, "../outside")
            link = root / "link"
            try:
                link.symlink_to(root / "ok", target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            with self.assertRaisesRegex(ValidationError, "REPARSE_OR_SYMLINK"):
                resolve_project_path(root, "link/x")


if __name__ == "__main__":
    unittest.main()
