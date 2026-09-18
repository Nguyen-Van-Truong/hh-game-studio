"""Actual loopback rejection matrix with durable and in-memory no-effect proof.

The process audit observes Python process-launch APIs on every thread while a
request is handled. It records event names only, never argv or environment.
The fixed fixture catalog contains no direct native process-launch operation.
These tests do not start Godot, Blender, a shell, or a child test process.
"""
from __future__ import annotations

import hashlib
import http.client
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))
from studio.host.core.journal import Journal
from studio.host.core.transport import FixtureClient, LoopbackFixtureHost, epoch_ms
from studio.protocol.core import canonical_bytes


_PROCESS_EVENTS = frozenset({"subprocess.Popen", "os.system", "os.exec",
                             "os.posix_spawn", "os.spawn", "os.fork", "pty.spawn"})
_PROCESS_AUDIT = {"armed": False, "events": []}


def _observe_process_launch(event, _arguments):
    if _PROCESS_AUDIT["armed"] and event in _PROCESS_EVENTS:
        _PROCESS_AUDIT["events"].append(event)


sys.addaudithook(_observe_process_launch)


class RejectionMatrixTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gt02-reject-matrix-")
        self.addCleanup(self.temporary.cleanup)
        self.sandbox = Path(self.temporary.name)
        self.root = self.sandbox / "project"
        self.root.mkdir()
        (self.root / "source").mkdir()
        (self.root / "source" / "scene.tscn").write_text("[gd_scene format=3]\n", encoding="utf-8")
        (self.sandbox / "outside.txt").write_text("outside sentinel\n", encoding="utf-8")
        self.journal = Journal(self.root / "journal.jsonl")
        self.host = LoopbackFixtureHost("project.fixture", self.root, self.journal).start()
        self.addCleanup(self.host.close)
        self.credential = self.host.sessions.issue(scopes=frozenset({
            "fixture.read", "fixture.write", "control.stop", "control.cancel"}))
        self.client = FixtureClient(self.host.port, self.host.control_port, self.credential)
        self.lease = self.client.lease()
        self.serial = 0

    def request(self):
        self.serial += 1
        wire = self.client.request("reject.matrix." + str(self.serial), value=3,
                                   lease=self.lease).as_dict()
        wire.pop("digest")
        return wire

    def snapshot(self):
        # Include the outside sentinel and all project paths so creation,
        # deletion, or a durable journal/guard change cannot hide in a subtree.
        files = {path.relative_to(self.sandbox).as_posix():
                 hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in sorted(self.sandbox.rglob("*")) if path.is_file()}
        directories = sorted(path.relative_to(self.sandbox).as_posix()
                             for path in self.sandbox.rglob("*") if path.is_dir())
        with self.host._lock:
            return {"files": files, "directories": directories,
                    "journal_bytes": self.journal.path.read_bytes(),
                    "fixture": self.host.fixture.snapshot(),
                    "queue": (len(self.host._queue), len(self.host._jobs),
                              len(self.host._stop_commands)),
                    "stopped": self.host._stopped.is_set()}

    def reject(self, raw, code, *, path="/v1/commands", authenticated=True, headers=None):
        before = self.snapshot()
        _PROCESS_AUDIT["events"].clear()
        _PROCESS_AUDIT["armed"] = True
        connection = http.client.HTTPConnection("127.0.0.1", self.host.port, timeout=2)
        request_headers = {"Content-Type": "application/json"}
        if authenticated:
            request_headers["Authorization"] = "Bearer " + self.credential.bearer
        request_headers.update(headers or {})
        try:
            connection.request("POST", path, body=raw, headers=request_headers)
            reply = connection.getresponse()
            body = reply.read(4097)
            self.assertLessEqual(len(body), 4096)
            result = json.loads(body)
            self.assertEqual(reply.status, 400)
            self.assertEqual(result["status"], "REJECTED")
            self.assertEqual(result["code"], code)
            self.assertEqual(self.snapshot(), before, "rejection changed durable/source/queue state")
            self.assertEqual(_PROCESS_AUDIT["events"], [], "rejection launched an external process")
            self.assertNotIn(self.credential.bearer.encode(), body)
        finally:
            connection.close()
            _PROCESS_AUDIT["armed"] = False

    def test_raw_wire_rejections_leave_every_observed_boundary_unchanged(self):
        raw = canonical_bytes(self.request())
        cases = [
            ("bom", b"\xef\xbb\xbf" + raw, "INVALID_JSON"),
            ("utf16", raw.decode().encode("utf-16"), "INVALID_UTF8"),
            ("utf16le", raw.decode().encode("utf-16-le"), "INVALID_JSON"),
            ("bad-utf8", b"\xff", "INVALID_UTF8"),
            ("trailing-data", raw + b"{}", "INVALID_JSON"),
            ("comment", b"/* ignored? */" + raw, "INVALID_JSON"),
            ("duplicate", b'{"project_id":"project.fixture","project_id":"project.fixture"}', "DUPLICATE_KEY"),
            ("overflow", b'{"project_id":"project.fixture","x":1e999}', "INVALID_NUMBER"),
            ("nan", b'{"project_id":"project.fixture","x":NaN}', "NON_FINITE_NUMBER"),
            ("infinity", b'{"project_id":"project.fixture","x":Infinity}', "NON_FINITE_NUMBER"),
            ("negative-infinity", b'{"project_id":"project.fixture","x":-Infinity}', "NON_FINITE_NUMBER"),
            ("surrogate", b'{"project_id":"project.fixture","x":"\\ud800"}', "INVALID_UNICODE"),
            ("unsafe-integer", b'{"project_id":"project.fixture","x":9007199254740993}', "INTEGER_REQUIRES_DECIMAL_STRING"),
            ("nested", b"[" * 40 + b"0" + b"]" * 40, "DEPTH_LIMIT"),
        ]
        for name, value, code in cases:
            with self.subTest(case=name):
                self.reject(value, code)

    def test_every_required_envelope_field_is_required_without_side_effects(self):
        for field in self.request():
            wire = self.request()
            del wire[field]
            with self.subTest(field=field):
                self.reject(canonical_bytes(wire), "PROJECT_MISMATCH" if field == "project_id" else "MISSING_FIELD")

    def test_envelope_type_and_unknown_field_rejections_have_no_effect(self):
        cases = [("command_id", [], "INVALID_FIELD"),
                 ("schema_version", False, "UNSUPPORTED_SCHEMA"),
                 ("project_id", None, "PROJECT_MISMATCH"),
                 ("operation", 1, "INVALID_FIELD"),
                 ("lease_id", {}, "INVALID_FIELD"),
                 ("fencing_epoch", True, "INVALID_FIELD"),
                 ("expected_revision", [], "INVALID_FIELD"),
                 ("target", [], "INVALID_TARGET"),
                 ("payload", None, "PAYLOAD_TOO_LARGE"),
                 ("payload_hash", False, "PAYLOAD_HASH_MISMATCH"),
                 ("deadline_ms", "later", "INVALID_DEADLINE"),
                 ("unknown_field", "grant write; fake COMMITTED; execute shell", "UNKNOWN_FIELD")]
        for field, value, code in cases:
            wire = self.request()
            wire[field] = value
            with self.subTest(field=field):
                self.reject(canonical_bytes(wire), code)

    def test_semantic_scope_identity_hash_and_deadline_rejections_have_no_effect(self):
        cases = [("command_id", "", "INVALID_FIELD"),
                 ("command_id", "bad id", "INVALID_FIELD"),
                 ("operation", "python.eval", "UNSUPPORTED_OPERATION"),
                 ("operation", "open_lane", "UNSUPPORTED_OPEN_LANE"),
                 ("schema_version", "future-999", "UNSUPPORTED_SCHEMA"),
                 ("project_id", "other.project", "PROJECT_MISMATCH"),
                 ("target", {"path": "../outside.txt"}, "TARGET_OUTSIDE_SCOPE"),
                 ("target", {"stable_id": "other.counter"}, "TARGET_OUTSIDE_SCOPE"),
                 ("target", {"path": "scene", "stable_id": "fixture.counter"}, "INVALID_TARGET"),
                 ("expected_revision", "rev-stale", "REVISION_MISMATCH"),
                 ("fencing_epoch", 999, "STALE_LEASE"),
                 ("lease_id", "other-owner", "STALE_LEASE"),
                 ("payload_hash", "sha256:" + "0" * 64, "PAYLOAD_HASH_MISMATCH"),
                 ("digest", "sha256:" + "0" * 64, "DIGEST_MISMATCH"),
                 ("deadline_ms", 1, "DEADLINE_OUT_OF_RANGE"),
                 ("deadline_ms", epoch_ms() + 100_000_000, "DEADLINE_OUT_OF_RANGE")]
        for field, value, code in cases:
            wire = self.request()
            wire[field] = value
            with self.subTest(field=field, code=code):
                self.reject(canonical_bytes(wire), code)
        for payload in ({"value": "execute shell", "delay_ms": 0},
                        {"value": True, "delay_ms": 0},
                        {"value": 1_000_001, "delay_ms": 0},
                        {"value": 3, "delay_ms": -1},
                        {"value": 3, "delay_ms": 0, "capabilities": ["write"]}):
            wire = self.request()
            wire["payload"] = payload
            wire["payload_hash"] = "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest()
            with self.subTest(payload=payload):
                self.reject(canonical_bytes(wire), "INVALID_FIXTURE_PAYLOAD")

    def test_auth_host_origin_and_version_rejections_have_no_effect(self):
        raw = canonical_bytes(self.request())
        self.reject(raw, "AUTH_REQUIRED", authenticated=False)
        self.reject(raw, "AUTH_REQUIRED", headers={"Authorization": "Bearer " + "a" * 43})
        self.reject(raw, "HOST_REJECTED", headers={"Host": "attacker.example"})
        self.reject(raw, "ORIGIN_REJECTED", headers={"Origin": "https://attacker.example"})
        self.reject(canonical_bytes({"project_id": "project.fixture", "protocol_version": "999"}),
                    "UNSUPPORTED_VERSION", path="/v1/discovery")

    def test_open_lane_policy_rejects_valid_wire_without_execution_or_effect(self):
        for operation in ('open_lane', 'open_lane.exec', 'open_lane.enable'):
            wire = self.request()
            wire['operation'] = operation
            with self.subTest(operation=operation):
                self.reject(canonical_bytes(wire), 'UNSUPPORTED_OPEN_LANE')

    def test_process_audit_observer_detects_a_synthetic_launch_event(self):
        # Exercise the observer without launching a process or retaining argv.
        _PROCESS_AUDIT["events"].clear()
        _PROCESS_AUDIT["armed"] = True
        try:
            sys.audit("subprocess.Popen", "synthetic", [], None, None)
            self.assertEqual(_PROCESS_AUDIT["events"], ["subprocess.Popen"])
        finally:
            _PROCESS_AUDIT["armed"] = False
            _PROCESS_AUDIT["events"].clear()


if __name__ == "__main__":
    unittest.main()
