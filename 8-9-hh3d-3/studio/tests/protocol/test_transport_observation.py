"""Bounded local client observations; mocked I/O, no engines or listeners."""
from __future__ import annotations

import http.client
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))
from studio.host.core.limits import DEFAULT_LIMITS, SafetyViolation
from studio.host.core.transport import FixtureClient as AcceptedFixtureClient, SessionCredential
from studio.tests.replay.benchmark_transport import BenchmarkFixtureClient as FixtureClient


class TransportObservationTests(unittest.TestCase):
    def setUp(self):
        self.credential = SessionCredential("private.session", "private.project", 9999999999999,
            frozenset({"fixture.read"}), "private-bearer-value")
        self.client = FixtureClient(12345, 12346, self.credential)
        self.body = {"command_id": "private.command", "payload": "private.body"}
        self.connection = mock.Mock()
        self.reply = self.connection.getresponse.return_value
        self.reply.status = 200
        self.reply.read.return_value = b'{"observed":"success"}'

    def test_failure_stages_and_categories_preserve_unknown_and_do_not_retry(self):
        errors = (
            (TimeoutError, "timeout"),
            (ConnectionResetError, "connection"),
            (http.client.RemoteDisconnected, "connection"),
            (http.client.HTTPException, "http"),
            (OSError, "os"),
        )
        expected_response = {"status": "UNKNOWN", "code": "CONNECTION_LOST_LOOKUP",
            "command_id": "private.command", "result_revision": None, "result_hash": None,
            "postconditions": {"next_action": "lookup"}}
        for stage in ("request", "getresponse", "read"):
            for error_type, category in errors:
                with self.subTest(stage=stage, error=error_type.__name__):
                    self.connection.reset_mock(side_effect=True)
                    self.reply.reset_mock(side_effect=True)
                    failing = self.reply.read if stage == "read" else getattr(self.connection, stage)
                    failing.side_effect = error_type("private-exception-text")
                    with mock.patch("studio.tests.replay.benchmark_transport.http.client.HTTPConnection",
                                    return_value=self.connection) as constructor, \
                         mock.patch("studio.tests.replay.benchmark_transport.time.perf_counter_ns",
                                    side_effect=[1_000_000, 3_500_000]):
                        result = self.client._call("/v1/commands", self.body)
                    self.assertEqual(result, expected_response)
                    self.assertEqual(self.client.last_transport_failure, {
                        "endpoint": "commands", "stage": stage, "category": category, "elapsed_ms": 2.5})
                    self.assertNotIn("private", json.dumps(self.client.last_transport_failure))
                    constructor.assert_called_once_with("127.0.0.1", 12345, timeout=2.0)
                    self.connection.request.assert_called_once()
                    self.assertEqual(self.connection.getresponse.call_count, int(stage != "request"))
                    self.assertEqual(self.reply.read.call_count, int(stage == "read"))
                    self.connection.close.assert_called_once()

    def test_failure_elapsed_uses_enclosing_perf_clock_not_coarse_monotonic(self):
        from studio.tests.replay.benchmark_commands import _clock as producer_clock

        for stage in ("request", "getresponse", "read"):
            self.connection.reset_mock(side_effect=True)
            self.reply.reset_mock(side_effect=True)
            failing = self.reply.read if stage == "read" else getattr(self.connection, stage)
            failing.side_effect = TimeoutError("private exception must not be retained")
            # Windows Python 3.11 GetTickCount64 can advance 15.625 ms across
            # only 6 ms of QPC time. Both nested durations must use QPC, not a
            # looser elapsed-time validation bound for that quantization.
            with self.subTest(stage=stage), \
                 mock.patch("studio.tests.replay.benchmark_transport.http.client.HTTPConnection",
                            return_value=self.connection) as constructor, \
                 mock.patch("studio.tests.replay.benchmark_transport.time.perf_counter_ns",
                            side_effect=[1_000_000_000, 1_001_000_000, 1_004_000_000, 1_006_000_000]) as perf, \
                 mock.patch("studio.tests.replay.benchmark_transport.time.monotonic_ns",
                            side_effect=[5_000_000_000, 5_015_625_000]) as coarse:
                started = producer_clock()
                result = self.client.lookup("clock.lookup")
                ended = producer_clock()
                self.assertEqual(self.client.last_transport_failure,
                    {"endpoint": "lookup", "stage": stage, "category": "timeout", "elapsed_ms": 3.0})
                self.assertLessEqual(self.client.last_transport_failure["elapsed_ms"], (ended - started) / 1_000_000)
                self.assertEqual(perf.call_count, 4)
                coarse.assert_not_called()
                self.assertEqual((result.status.value, result.code, result.command_id),
                                 ("UNKNOWN", "CONNECTION_LOST_LOOKUP", "clock.lookup"))
                self.assertEqual(self.client.timeout, 2.0)
                constructor.assert_called_once_with("127.0.0.1", 12346, timeout=2.0)
                self.connection.close.assert_called_once_with()

    def test_endpoint_enum_does_not_retain_arbitrary_path_or_exception_fields(self):
        endpoints = {"discovery": "discovery", "lease": "lease", "commands": "commands",
            "lookup": "lookup", "archive": "archive", "cancel": "cancel", "stop": "stop",
            "private-url?token=private-query": "unknown"}
        for suffix, endpoint in endpoints.items():
            with self.subTest(endpoint=endpoint):
                error = OSError(123, "private-message", "private-filename")
                error.winerror = "private-winerror"
                self.connection.request.side_effect = error
                with mock.patch("studio.tests.replay.benchmark_transport.http.client.HTTPConnection",
                                return_value=self.connection):
                    self.client._call("/v1/" + suffix, self.body, control=True)
                observation = self.client.last_transport_failure
                self.assertEqual(set(observation), {"endpoint", "stage", "category", "elapsed_ms"})
                self.assertEqual(observation["endpoint"], endpoint)
                self.assertEqual(observation["category"], "os")
                self.assertGreaterEqual(observation["elapsed_ms"], 0)
                self.assertNotIn("private", json.dumps(observation))

    def test_observation_is_defensive_copy_and_read_only(self):
        self.connection.request.side_effect = TimeoutError("private-message")
        with mock.patch("studio.tests.replay.benchmark_transport.http.client.HTTPConnection", return_value=self.connection):
            self.client._call("/v1/commands", self.body)
        original = self.client.last_transport_failure
        changed = self.client.last_transport_failure
        changed["category"] = "forged"
        changed["secret"] = self.credential.bearer
        self.assertEqual(self.client.last_transport_failure, original)
        self.assertIsNot(self.client.last_transport_failure, original)
        with self.assertRaises(AttributeError):
            self.client.last_transport_failure = changed

    def test_next_call_clears_failure_before_request_and_success_keeps_none(self):
        self.connection.request.side_effect = TimeoutError("private-message")
        with mock.patch("studio.tests.replay.benchmark_transport.http.client.HTTPConnection", return_value=self.connection):
            self.client._call("/v1/commands", self.body)
            self.assertIsNotNone(self.client.last_transport_failure)

            def request(*args, **kwargs):
                self.assertIsNone(self.client.last_transport_failure)

            self.connection.request.side_effect = request
            with mock.patch("studio.tests.replay.benchmark_transport.time.perf_counter_ns", return_value=5_000_000) as clock:
                result = self.client._call("/v1/lookup", self.body, control=True)
            clock.assert_called_once()
        self.assertEqual(result, {"observed": "success"})
        self.assertIsNone(self.client.last_transport_failure)

    def test_protocol_rejection_does_not_reuse_previous_transport_failure(self):
        self.connection.request.side_effect = TimeoutError("private-message")
        with mock.patch("studio.tests.replay.benchmark_transport.http.client.HTTPConnection", return_value=self.connection):
            self.client._call("/v1/commands", self.body)
            self.connection.request.side_effect = None
            self.reply.status = 302
            with self.assertRaisesRegex(SafetyViolation, "UNSUPPORTED_HTTP_RESPONSE"):
                self.client._call("/v1/lookup", self.body, control=True)
        self.assertIsNone(self.client.last_transport_failure)

    def test_copied_call_preserves_accepted_wire_and_error_behavior(self):
        baseline = AcceptedFixtureClient(12345, 12346, self.credential)
        cases = [
            (None, None, 200, b'{"status":"ACCEPTED_PENDING","code":"QUEUED"}'),
            (None, None, 400, b'{"status":"REJECTED","code":"FIXTURE_REJECTION"}'),
            (None, None, 302, b'{}'),
            (None, None, 200, b'x' * (DEFAULT_LIMITS.max_result_bytes + 1)),
            (None, None, 200, b'[]'),
            (None, None, 200, b'{'),
        ]
        cases.extend((stage, error_type, 200, b'{}')
                     for stage in ("request", "getresponse", "read")
                     for error_type in (TimeoutError, ConnectionResetError, http.client.HTTPException, OSError))
        for stage, error_type, status, raw in cases:
            with self.subTest(stage=stage, error=error_type, status=status, bytes=len(raw)):
                outcomes, calls = [], []
                for client in (baseline, self.client):
                    connection = mock.Mock()
                    reply = connection.getresponse.return_value
                    reply.status, reply.read.return_value = status, raw
                    if error_type is not None:
                        failing = reply.read if stage == "read" else getattr(connection, stage)
                        failing.side_effect = error_type("private-failure")
                    with mock.patch("studio.tests.replay.benchmark_transport.http.client.HTTPConnection",
                                    return_value=connection) as constructor:
                        try:
                            outcome = ("return", client._call("/v1/lookup", self.body, control=True))
                        except Exception as error:
                            outcome = ("raise", type(error), getattr(error, "code", None))
                    outcomes.append(outcome)
                    calls.append((constructor.call_args_list, connection.mock_calls))
                self.assertEqual(outcomes[0], outcomes[1])
                self.assertEqual(calls[0], calls[1])


if __name__ == "__main__":
    unittest.main()
