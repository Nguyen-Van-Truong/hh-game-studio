"""Cross-module contract tests for the single GT-02 wire profile."""
from __future__ import annotations
import hashlib, json, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))
from studio.protocol import Request, ValidationError, canonical_bytes, canonical_json
from studio.protocol.core import MAX_DEPTH
from studio.host.core.limits import SafetyViolation, payload_digest, validate_envelope, parse_json_utf8

def envelope(payload=None, **changes):
    payload = {"text": "ok"} if payload is None else payload
    target = {"path": "main.tscn"}
    data = {"command_id":"cmd-integration-1", "schema_version":"hh-studio-0.1",
            "project_id":"project-a", "operation":"fixture.inspect", "lease_id":"lease-1",
            "fencing_epoch":1, "expected_revision":"rev-1", "target":target, "payload":payload,
            "payload_hash":payload_digest("fixture.inspect", target, payload, "hh-studio-0.1"), "deadline_ms":10_000}
    data.update(changes)
    return data

class ProtocolIntegrationTests(unittest.TestCase):
    def test_same_envelope_is_accepted_by_typed_and_host_layers(self):
        wire = envelope(); request = Request.from_dict(wire); checked = validate_envelope(wire, now_ms=0)
        self.assertEqual(request.project_id, checked["project_id"]); self.assertEqual(request.payload_hash, checked["payload_hash"])

    def test_unknown_fields_fail_closed_in_both_layers(self):
        wire = envelope(unexpected="typo")
        with self.assertRaisesRegex(ValidationError, "UNKNOWN_FIELD"): Request.from_dict(wire)
        with self.assertRaisesRegex(SafetyViolation, "UNKNOWN_FIELD"): validate_envelope(wire, now_ms=0)

    def test_schema_target_and_digest_mismatch_fail_closed(self):
        with self.assertRaisesRegex(ValidationError, "UNSUPPORTED_SCHEMA"): Request.from_dict(envelope(schema_version="studio.command.v1"))
        bad = envelope(target={"path":"other.tscn"})
        self.assertEqual(validate_envelope(bad, now_ms=0)["target"], {"path":"other.tscn"})
        altered = envelope(payload={"text":"changed"}, payload_hash="sha256:" + "0" * 64)
        with self.assertRaisesRegex(ValidationError, "PAYLOAD_HASH_MISMATCH"): Request.from_dict(altered)

    def test_depth_cap_is_enforced_by_both_layers(self):
        value = "leaf"
        for _ in range(MAX_DEPTH + 1): value = {"nested": value}
        with self.assertRaisesRegex(ValidationError, "DEPTH_LIMIT"): canonical_json(value)
        with self.assertRaisesRegex(SafetyViolation, "DEPTH_LIMIT"): parse_json_utf8(json.dumps(value, separators=(",", ":")).encode())

    def test_digest_prefix_and_payload_hash_are_canonical(self):
        payload = {"text":"ok"}
        self.assertEqual(payload_digest("fixture.inspect", {"path":"main.tscn"}, payload, "hh-studio-0.1"), "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest())

if __name__ == "__main__": unittest.main()
