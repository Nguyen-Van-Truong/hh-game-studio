"""Real socket GT-02 fixture tests; no Godot, Blender or external network."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import http.client
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))
from studio.host.core.journal import Journal, JournalLimits
from studio.host.core.limits import SafetyViolation
from studio.host.core.transport import (FixtureClient, FixtureFaults, FixtureState,
    LoopbackFixtureHost, SessionAuthority, TransportLimits, epoch_ms)
from studio.protocol.core import Request, Status, canonical_bytes


ALL_SCOPES = frozenset({"fixture.read", "fixture.write", "control.stop", "control.cancel"})


class TransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="gt02-transport-")
        self.root = Path(self.temp.name)
        self.faults = FixtureFaults()
        self.journal = Journal(self.root / "journal.jsonl")
        self.host = LoopbackFixtureHost("project.fixture", self.root, self.journal,
            faults=self.faults, limits=TransportLimits(max_connections=2, max_pending=3),
            allowed_origins=frozenset({"http://127.0.0.1:12345"}))
        self.host.start()
        self.credential = self.host.sessions.issue(scopes=ALL_SCOPES)
        self.client = FixtureClient(self.host.port, self.host.control_port, self.credential)

    def tearDown(self) -> None:
        if self.faults.readback_gate is not None:
            self.faults.readback_gate.set()
        self.host.close()
        self.temp.cleanup()

    def raw(self, body: bytes, *, path: str = "/v1/discovery", headers=None,
            control: bool = False, auth: bool = True) -> tuple[int, dict]:
        port = self.host.control_port if control else self.host.port
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        defaults = {"Content-Type": "application/json"}
        if auth:
            defaults["Authorization"] = "Bearer " + self.credential.bearer
        defaults.update(headers or {})
        try:
            connection.request("POST", path, body=body, headers=defaults)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def discovery_body(self) -> bytes:
        return canonical_bytes({"project_id": "project.fixture", "protocol_version": "1.0"})

    def terminal(self, command_id: str, timeout: float = 3) -> object:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            result = self.client.lookup(command_id)
            if result.status is not Status.ACCEPTED_PENDING:
                return result
            time.sleep(0.01)
        self.fail("command did not reach an explicit terminal/unknown state")

    def assert_no_effect(self) -> None:
        self.assertEqual(self.host.fixture.snapshot(), {"value": 0, "revision": "rev-0", "effect_count": 0})

    def test_authenticated_discovery_and_typed_fixture_roundtrip(self) -> None:
        discovery = self.client.discover()
        self.assertEqual(discovery.project_id, "project.fixture")
        self.assertTrue(discovery.supports("fixture.set"))
        self.assertFalse(discovery.supports("python.eval"))
        self.assertEqual(discovery.limits["max_pending"], 3)
        request = self.client.request("set.1", value=17, lease=self.client.lease())
        self.assertIs(self.client.submit(request).status, Status.ACCEPTED_PENDING)
        result = self.terminal("set.1")
        self.assertIs(result.status, Status.COMMITTED)
        snapshot = result.postconditions["snapshot"]
        self.assertEqual(snapshot["value"], 17)
        self.assertEqual(result.result_hash, "sha256:" + hashlib.sha256(canonical_bytes(snapshot)).hexdigest())
        self.assertEqual(self.journal.lookup(project_id="project.fixture", command_id="set.1", now_ms=epoch_ms())["status"], "COMMITTED")
        self.assertEqual(self.client.submit(request), result)
        self.assertEqual(self.host.fixture.effect_count, 1)

    def test_read_only_default_session_cannot_mutate_or_stop(self) -> None:
        readonly = self.host.sessions.issue()
        client = FixtureClient(self.host.port, self.host.control_port, readonly)
        self.assertTrue(client.discover().supports("fixture.inspect"))
        self.assertFalse(client.discover().supports("fixture.set"))
        self.assertEqual(client.stop("stop.denied").code, "SCOPE_DENIED")
        self.assertEqual(client.submit(client.request("write.denied", value=7)).code, "UNSUPPORTED_OPERATION")
        self.assertIs(client.submit(client.request("inspect.1")).status, Status.ACCEPTED_PENDING)
        self.assertIs(self.terminal("inspect.1").status, Status.COMMITTED)
        self.assert_no_effect()

    def test_auth_required_for_every_read_write_and_control_route(self) -> None:
        for path in ("/v1/discovery", "/v1/commands", "/v1/lease", "/v1/lookup", "/v1/stop", "/v1/cancel"):
            with self.subTest(path=path):
                status, data = self.raw(self.discovery_body(), path=path,
                    control=path in {"/v1/lookup", "/v1/stop", "/v1/cancel"}, auth=False)
                self.assertEqual(status, 400)
                self.assertEqual(data["code"], "AUTH_REQUIRED")
        for value in ("Bearer short", "Basic abc", "Bearer " + "a" * 43, "bearer " + self.credential.bearer):
            self.assertEqual(self.raw(self.discovery_body(), headers={"Authorization": value})[1]["code"], "AUTH_REQUIRED")
        self.assert_no_effect()

    def test_expiry_rotation_revocation_and_session_cap(self) -> None:
        short = self.host.sessions.issue(ttl_ms=30)
        short_client = FixtureClient(self.host.port, self.host.control_port, short)
        time.sleep(0.04)
        with self.assertRaisesRegex(SafetyViolation, "SESSION_EXPIRED"):
            short_client.discover()
        replacement = self.host.sessions.rotate(self.credential)
        with self.assertRaisesRegex(SafetyViolation, "AUTH_REQUIRED"):
            self.client.discover()
        rotated = FixtureClient(self.host.port, self.host.control_port, replacement)
        self.assertTrue(rotated.discover().supports("fixture.set"))
        self.host.sessions.revoke(replacement)
        with self.assertRaisesRegex(SafetyViolation, "AUTH_REQUIRED"):
            rotated.discover()
        authority = SessionAuthority("project.fixture", self.root, TransportLimits(max_sessions=1))
        issued = authority.issue()
        self.assertNotIn(issued.bearer, repr(issued))
        with self.assertRaisesRegex(SafetyViolation, "SESSION_LIMIT"):
            authority.issue()
        for ttl in (True, 0, 1_000_000):
            with self.assertRaisesRegex(SafetyViolation, "INVALID_SESSION_POLICY"):
                authority.issue(ttl_ms=ttl)
        self.assert_no_effect()

    def test_host_origin_encoding_route_and_project_reject_before_effect(self) -> None:
        cases = [({"Host": "attacker.example"}, "HOST_REJECTED"),
                 ({"Host": "localhost:" + str(self.host.port)}, "HOST_REJECTED"),
                 ({"Origin": "https://attacker.example"}, "ORIGIN_REJECTED"),
                 ({"Origin": "null"}, "ORIGIN_REJECTED"),
                 ({"Content-Encoding": "gzip"}, "UNSUPPORTED_ENCODING"),
                 ({"Transfer-Encoding": "chunked"}, "UNSUPPORTED_ENCODING"),
                 ({"Content-Type": "text/plain"}, "UNSUPPORTED_CONTENT_TYPE")]
        for headers, code in cases:
            self.assertEqual(self.raw(self.discovery_body(), headers=headers)[1]["code"], code)
        allowed_status, allowed = self.raw(self.discovery_body(), headers={"Origin": "http://127.0.0.1:12345"})
        self.assertEqual(allowed_status, 200)
        self.assertEqual(allowed["project_id"], "project.fixture")
        self.assertEqual(self.raw(self.discovery_body(), path="http://127.0.0.1/private",
            headers={"Host": "127.0.0.1:" + str(self.host.port)})[1]["code"], "UNSUPPORTED_ROUTE")
        self.assertEqual(self.raw(self.discovery_body(), path="/v1/discovery?x=1")[1]["code"], "UNSUPPORTED_ROUTE")
        wrong = canonical_bytes({"project_id": "other.project", "protocol_version": "1.0"})
        self.assertEqual(self.raw(wrong)[1]["code"], "PROJECT_MISMATCH")
        self.assert_no_effect()

    def test_preauth_byte_caps_duplicate_headers_and_compression_rejection(self) -> None:
        self.assertEqual(self.raw(b"", auth=False,
            headers={"Content-Length": str(self.host.limits.max_body_bytes + 1)})[1]["code"], "ENVELOPE_TOO_LARGE")
        self.assertEqual(self.raw(b"", auth=False,
            headers={"X-Pad": "x" * 9000})[1]["code"], "HEADER_TOO_LARGE")
        prefix = (f"POST /v1/discovery HTTP/1.1\r\nHost: 127.0.0.1:{self.host.port}\r\n"
                  "Content-Type: application/json\r\nContent-Length: 0\r\nContent-Length: 1\r\n\r\n")
        with socket.create_connection(("127.0.0.1", self.host.port), timeout=2) as stream:
            stream.sendall(prefix.encode())
            reply = http.client.HTTPResponse(stream)
            reply.begin()
            self.assertEqual(json.loads(reply.read())["code"], "INVALID_HEADER")
        self.assert_no_effect()

    def test_invalid_wire_catalog_payload_root_revision_and_deadline_have_no_effect(self) -> None:
        lease = self.client.lease()
        valid = self.client.request("reject.base", value=3, lease=lease).as_dict()
        cases = [({"operation": "python.eval"}, "UNSUPPORTED_OPERATION"),
                 ({"schema_version": "unknown"}, "UNSUPPORTED_SCHEMA"),
                 ({"target": {"path": "../outside"}}, "TARGET_OUTSIDE_SCOPE"),
                 ({"expected_revision": "rev-9"}, "REVISION_MISMATCH"),
                 ({"fencing_epoch": 99}, "STALE_LEASE"),
                 ({"deadline_ms": epoch_ms() - 1}, "DEADLINE_OUT_OF_RANGE"),
                 ({"payload_hash": "sha256:" + "0" * 64}, "PAYLOAD_HASH_MISMATCH"),
                 ({"project_id": "wrong.project"}, "PROJECT_MISMATCH"),
                 ({"arbitrary_code": "print(1)"}, "UNKNOWN_FIELD")]
        for index, (changes, code) in enumerate(cases):
            body = dict(valid, command_id="reject." + str(index))
            body.update(changes)
            body.pop("digest", None)
            response = self.raw(canonical_bytes(body), path="/v1/commands")[1]
            self.assertEqual(response["code"], code, body)
        duplicate = b'{"project_id":"project.fixture","project_id":"project.fixture"}'
        self.assertEqual(self.raw(duplicate)[1]["code"], "DUPLICATE_KEY")
        self.assertEqual(self.raw(b'{"project_id":"project.fixture","x":NaN}')[1]["code"], "NON_FINITE_NUMBER")
        self.assert_no_effect()

    def test_same_id_changed_payload_conflicts_and_cannot_apply_twice(self) -> None:
        lease = self.client.lease()
        first = self.client.request("same.id", value=3, lease=lease)
        self.client.submit(first)
        self.assertIs(self.terminal("same.id").status, Status.COMMITTED)
        other = self.client.request("same.id", value=8, lease=lease)
        self.assertEqual(self.client.submit(other).code, "COMMAND_ID_PAYLOAD_CONFLICT")
        expired_replay = replace(first, deadline_ms=1, lease_id="obsolete", fencing_epoch=777)
        self.assertIs(self.client.submit(expired_replay).status, Status.COMMITTED)
        self.assertEqual(self.host.fixture.effect_count, 1)
        self.assertEqual(self.host.fixture.value, 3)

    def test_lost_submit_response_is_unknown_lookup_resolves_without_duplicate(self) -> None:
        self.faults.drop_submit_response_once = True
        request = self.client.request("lost.response", value=41, lease=self.client.lease())
        result = self.client.submit(request)
        self.assertIs(result.status, Status.UNKNOWN)
        self.assertEqual(result.code, "CONNECTION_LOST_LOOKUP")
        committed = self.terminal(request.command_id)
        self.assertIs(committed.status, Status.COMMITTED)
        self.assertEqual(self.client.submit(request), committed)
        self.assertEqual(self.host.fixture.effect_count, 1)

    def test_cancel_before_effect_and_deadline_before_effect(self) -> None:
        lease = self.client.lease()
        request = self.client.request("cancel.early", value=10, lease=lease, delay_ms=500)
        self.client.submit(request)
        self.assertIs(self.client.cancel(request.command_id).status, Status.CANCELED)
        self.assertIs(self.terminal(request.command_id).status, Status.CANCELED)
        self.assertIs(self.client.submit(request).status, Status.CANCELED)
        deadline = self.client.request("deadline.early", value=11, lease=lease, delay_ms=150, timeout_ms=50)
        self.client.submit(deadline)
        self.assertEqual(self.terminal(deadline.command_id).code, "DEADLINE_BEFORE_APPLY")
        self.assert_no_effect()

    def test_cancel_and_deadline_after_write_are_not_false_cancellation(self) -> None:
        self.faults.readback_gate = threading.Event()
        request = self.client.request("cancel.late", value=22, lease=self.client.lease(), timeout_ms=80)
        self.assertIs(self.client.submit(request).status, Status.ACCEPTED_PENDING)
        self.assertTrue(self.faults.applied.wait(1))
        time.sleep(0.1)
        result = self.client.cancel(request.command_id)
        self.assertIs(result.status, Status.UNKNOWN)
        self.assertEqual(result.code, "CANCEL_TOO_LATE_LOOKUP")
        self.faults.readback_gate.set()
        self.assertIs(self.terminal(request.command_id).status, Status.COMMITTED)
        self.assertEqual(self.host.fixture.effect_count, 1)

    def test_stop_has_reserved_capacity_under_connection_and_work_queue_flood(self) -> None:
        self.faults.readback_gate = threading.Event()
        lease = self.client.lease()
        first = self.client.request("flood.active", value=1, lease=lease)
        self.client.submit(first)
        self.assertTrue(self.faults.applied.wait(1))
        for index in range(2):
            req = self.client.request("flood.pending." + str(index))
            self.assertIs(self.client.submit(req).status, Status.ACCEPTED_PENDING)
        self.assertEqual(self.client.submit(self.client.request("flood.excess")).code, "QUEUE_FULL")
        sockets = []
        try:
            for _ in range(2):
                stream = socket.create_connection(("127.0.0.1", self.host.port), timeout=1)
                stream.sendall(b"POST /v1/discovery HTTP/1.1\r\n")
                sockets.append(stream)
            # Wait for both accepted connections to occupy the bounded slots.
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                if self.host._main.slots._value == 0:
                    break
                time.sleep(0.005)
            self.assertEqual(self.host._main.slots._value, 0)
            start = time.monotonic()
            stop = self.client.stop("stop.flood")
            elapsed = time.monotonic() - start
            self.assertIs(stop.status, Status.ACCEPTED_PENDING)
            self.assertLess(elapsed, 0.5)
        finally:
            for stream in sockets:
                stream.close()
        self.faults.readback_gate.set()
        self.assertIs(self.terminal(first.command_id).status, Status.COMMITTED)
        for index in range(2):
            self.assertIs(self.terminal("flood.pending." + str(index)).status, Status.CANCELED)
        self.assertEqual(self.terminal("stop.flood").code, "STOPPED")
        replacement = self.host.sessions.rotate(self.credential)
        reconnected = FixtureClient(self.host.port, self.host.control_port, replacement)
        self.assertEqual(reconnected.submit(reconnected.request("after.reconnect")).code, "HOST_STOPPED")
        self.assertEqual(self.host.fixture.effect_count, 1)

    def test_queued_revision_and_lease_are_checked_again_before_apply(self) -> None:
        lease = self.client.lease()
        first = self.client.request("revision.first", value=1, lease=lease, delay_ms=100)
        second = self.client.request("revision.stale", value=2, lease=lease)
        self.client.submit(first)
        self.client.submit(second)
        self.assertIs(self.terminal(first.command_id).status, Status.COMMITTED)
        self.assertEqual(self.terminal(second.command_id).code, "REVISION_MISMATCH")
        lease = self.client.lease(ttl_ms=40)
        third = self.client.request("lease.expires", value=3, lease=lease, delay_ms=100)
        self.client.submit(third)
        self.assertEqual(self.terminal(third.command_id).code, "STALE_LEASE")
        self.assertEqual(self.host.fixture.effect_count, 1)

    def test_orphan_pending_returns_unknown_and_replay_never_applies(self) -> None:
        request = self.client.request("orphan.pending", value=7, lease=self.client.lease())
        pending = {"status": "ACCEPTED_PENDING", "code": "QUEUED", "command_id": request.command_id,
                   "postconditions": {"request_digest": request.digest}}
        self.journal.append_command(project_id="project.fixture", command_id=request.command_id,
            digest=request.digest, receipt=pending, now_ms=epoch_ms(), pending=True)
        self.assertEqual(self.client.lookup(request.command_id).code, "RECOVERY_REQUIRED")
        self.assertIs(self.client.submit(request).status, Status.UNKNOWN)
        self.assert_no_effect()

    def test_actual_wire_and_retained_diagnostics_do_not_echo_credentials_or_paths(self) -> None:
        body = json.dumps({"project_id": "project.fixture", "protocol_version": "1.0",
                           "parser_error": self.credential.bearer, "source": str(self.root)}).encode()
        status, result = self.raw(body)
        self.assertEqual(status, 400)
        captured = json.dumps(result).encode() + b"".join(self.host.diagnostics)
        self.assertNotIn(self.credential.bearer.encode(), captured)
        self.assertNotIn(str(self.root).encode(), captured)
        self.assertEqual(result["code"], "INVALID_ENVELOPE")
        for index in range(40):
            self.host._diagnostic("PARSER_REJECTED")
        self.assertEqual(len(self.host.diagnostics), self.host.limits.max_diagnostics)
        self.assert_no_effect()

    def test_journal_full_rejects_admission_without_mutation(self) -> None:
        self.journal.limits = JournalLimits(max_bytes=200)
        inspect = self.client.request("journal.full")
        result = self.client.submit(inspect)
        self.assertIs(result.status, Status.REJECTED)
        self.assertEqual(result.code, "JOURNAL_FULL")
        self.assert_no_effect()

    def test_queued_rotation_revoke_and_expiry_are_rechecked_before_apply(self) -> None:
        for index, action in enumerate(("rotate", "revoke", "expire")):
            credential = self.host.sessions.issue(scopes=ALL_SCOPES, ttl_ms=60 if action == "expire" else 60_000)
            client = FixtureClient(self.host.port, self.host.control_port, credential)
            lease = client.lease(ttl_ms=250)
            request = client.request("auth.queued." + str(index), value=9, lease=lease, delay_ms=120)
            self.assertIs(client.submit(request).status, Status.ACCEPTED_PENDING)
            if action == "rotate":
                self.host.sessions.rotate(credential)
            elif action == "revoke":
                self.host.sessions.revoke(credential)
            self.assertEqual(self.terminal(request.command_id).code, "SESSION_INVALIDATED")
            time.sleep(0.14)  # Let the independent fixture lease expire before the next owner.
        self.assert_no_effect()

    def test_repeated_cancel_cannot_grow_queue_while_worker_waits_for_readback(self) -> None:
        self.faults.readback_gate = threading.Event()
        self.client.submit(self.client.request("cancel.flood.active", value=1, lease=self.client.lease()))
        self.assertTrue(self.faults.applied.wait(1))
        for index in range(12):
            request = self.client.request("cancel.flood." + str(index))
            self.assertIs(self.client.submit(request).status, Status.ACCEPTED_PENDING)
            self.assertIs(self.client.cancel(request.command_id).status, Status.CANCELED)
            self.assertLessEqual(len(self.host._queue), self.host.limits.max_pending)
        self.assertEqual(len(self.host._queue), 0)
        self.faults.readback_gate.set()
        self.assertIs(self.terminal("cancel.flood.active").status, Status.COMMITTED)

    def test_stop_closes_admission_even_when_journal_cannot_persist(self) -> None:
        self.journal.limits = JournalLimits(max_bytes=200)
        stop = self.client.stop("stop.storage.full")
        self.assertIs(stop.status, Status.UNKNOWN)
        self.assertEqual(stop.code, "STOP_DURABILITY_UNKNOWN")
        self.assertFalse(stop.postconditions["accepting_work"])
        self.assertEqual(self.client.submit(self.client.request("after.failed.stop")).code, "HOST_STOPPED")
        self.assert_no_effect()

    def test_live_credentials_cannot_be_persisted_as_command_or_control_identifiers(self) -> None:
        other = self.host.sessions.issue()
        for identifier in (self.credential.bearer, "cmd." + other.bearer):
            result = self.client.submit(self.client.request(identifier))
            self.assertEqual(result.code, "SENSITIVE_IDENTIFIER_FORBIDDEN")
            self.assertEqual(self.client.stop(identifier).code, "SENSITIVE_IDENTIFIER_FORBIDDEN")
        raw = self.journal.path.read_bytes() if self.journal.path.exists() else b""
        self.assertNotIn(self.credential.bearer.encode(), raw)
        self.assertNotIn(other.bearer.encode(), raw)
        self.assert_no_effect()

    def test_readback_failure_is_unknown_stops_host_and_does_not_replay_effect(self) -> None:
        self.host.limits = replace(self.host.limits, readback_timeout_ms=80)
        self.faults.readback_gate = threading.Event()
        request = self.client.request("readback.unknown", value=99, lease=self.client.lease())
        self.assertIs(self.client.submit(request).status, Status.ACCEPTED_PENDING)
        result = self.terminal(request.command_id)
        self.assertIs(result.status, Status.UNKNOWN)
        self.assertEqual(result.code, "RECOVERY_REQUIRED")
        self.assertIs(self.client.submit(request).status, Status.UNKNOWN)
        self.assertEqual(self.client.submit(self.client.request("after.readback.failure")).code, "HOST_STOPPED")
        self.assertEqual(self.host.fixture.effect_count, 1)
        self.assertEqual(self.host.fixture.value, 99)


if __name__ == "__main__":
    unittest.main()
