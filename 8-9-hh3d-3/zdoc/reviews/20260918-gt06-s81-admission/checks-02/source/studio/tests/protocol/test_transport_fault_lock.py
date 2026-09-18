"""Real socket proof that local fault controls cannot hold a durable ACK."""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))
from studio.host.core.journal import Journal
from studio.host.core.transport import epoch_ms
from studio.tests.replay.benchmark_transport import (BenchmarkFixtureClient as FixtureClient,
    BenchmarkFixtureHost as LoopbackFixtureHost)
from studio.protocol.core import Status


@contextmanager
def fixture():
    with tempfile.TemporaryDirectory(prefix="gt02-fault-lock-") as directory:
        root = Path(directory)
        with LoopbackFixtureHost("project.fixture", root, Journal(root / "journal.jsonl")) as host:
            credential = host.sessions.issue(scopes=frozenset({"fixture.read", "fixture.write"}))
            yield host, FixtureClient(host.port, host.control_port, credential), credential


class TransportFaultLockTests(unittest.TestCase):
    def terminal(self, client, command_id):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            response = client.lookup(command_id)
            if response.status is not Status.ACCEPTED_PENDING:
                return response
            time.sleep(.001)
        self.fail("terminal lookup did not finish within its bounded test budget")

    def start_submit(self, client, request):
        done, result = threading.Event(), {}

        def run():
            try:
                result["response"] = client.submit(request)
            except BaseException as error:
                result["error"] = error
            finally:
                done.set()

        thread = threading.Thread(target=run)
        thread.start()
        return thread, done, result

    def response(self, result):
        self.assertNotIn("error", result)
        self.assertIn("response", result)
        return result["response"]

    def test_durable_pending_ack_arrives_while_terminal_persistence_holds_host_lock(self):
        for write in (False, True):
            with self.subTest(write=write), fixture() as (host, client, _):
                request = client.request("ack.held", value=17 if write else None,
                    lease=client.lease() if write else None)
                terminal_entered, release_terminal = threading.Event(), threading.Event()
                dispatch, finish = host._dispatch, host.journal.finish_command

                def gated_finish(**kwargs):
                    if kwargs["command_id"] == request.command_id:
                        terminal_entered.set()
                        if not release_terminal.wait(5):
                            raise AssertionError("test terminal gate was not released")
                    return finish(**kwargs)

                def dispatched(path, body, session, control):
                    response = dispatch(path, body, session, control)
                    if path == "/v1/commands" and body["command_id"] == request.command_id:
                        if not terminal_entered.wait(3):
                            raise AssertionError("worker did not reach terminal persistence")
                    return response

                with mock.patch.object(host.journal, "finish_command", gated_finish), \
                     mock.patch.object(host, "_dispatch", dispatched):
                    thread, done, result = self.start_submit(client, request)
                    try:
                        self.assertTrue(terminal_entered.wait(3))
                        # The worker is inside _execute's host-lock section.
                        # Releasing this gate cannot be what makes the ACK arrive.
                        self.assertFalse(release_terminal.is_set())
                        self.assertTrue(done.wait(1), "durable ACK waited for terminal journal work")
                        self.assertIs(self.response(result).status, Status.ACCEPTED_PENDING)
                        pending = host.journal.lookup(project_id=host.project_id,
                            command_id=request.command_id, now_ms=epoch_ms())
                        self.assertEqual(pending["status"], "ACCEPTED_PENDING")
                    finally:
                        release_terminal.set()
                        thread.join(3)
                    self.assertFalse(thread.is_alive())
                    committed = self.terminal(client, request.command_id)
                    self.assertIs(committed.status, Status.COMMITTED)
                    self.assertEqual(committed.postconditions["snapshot"]["effect_count"], int(write))
                    self.assertEqual(client.submit(request), committed)
                    self.assertEqual(host.fixture.effect_count, int(write))

    def test_concurrent_matching_responses_consume_disconnect_only_once(self):
        with fixture() as (host, client, credential):
            requests = [client.request("race." + str(index)) for index in range(2)]
            ids = {request.command_id for request in requests}
            rendezvous = threading.Barrier(2)
            probe = host._disconnect_probe

            def concurrent_probe(path, phase, response=None):
                if (path == "/v1/commands" and phase == "after_dispatch"
                        and response.command_id in ids):
                    rendezvous.wait(3)
                return probe(path, phase, response)

            host.arm_disconnect("/v1/commands", "after_dispatch")
            with mock.patch.object(host, "_disconnect_probe", concurrent_probe):
                calls = [self.start_submit(FixtureClient(host.port, host.control_port, credential), request)
                         for request in requests]
                try:
                    for thread, done, _ in calls:
                        self.assertTrue(done.wait(4))
                        thread.join(1)
                        self.assertFalse(thread.is_alive())
                finally:
                    rendezvous.abort()
                    for thread, _, _ in calls:
                        thread.join(4)
                responses = [self.response(result) for _, _, result in calls]
            self.assertCountEqual([response.status for response in responses],
                [Status.UNKNOWN, Status.ACCEPTED_PENDING])
            lost = next(response for response in responses if response.status is Status.UNKNOWN)
            self.assertEqual(lost.code, "CONNECTION_LOST_LOOKUP")
            for request in requests:
                committed = self.terminal(client, request.command_id)
                self.assertIs(committed.status, Status.COMMITTED)
                self.assertEqual(client.submit(request), committed)
            rows = [json.loads(line)["record"] for line in host.journal.path.read_text().splitlines()]
            for command_id in ids:
                self.assertEqual([row["status"] for row in rows if row.get("command_id") == command_id],
                    ["ACCEPTED_PENDING", "COMMITTED"])
            self.assertEqual(host.fixture.effect_count, 0)

    def test_competing_disconnect_and_submit_drop_keep_their_original_precedence(self):
        for phase in ("after_dispatch", "before_reply"):
            with self.subTest(phase=phase), fixture() as (host, client, _):
                host.arm_disconnect("/v1/commands", phase)
                host.faults.drop_submit_response_once = True  # Unchanged inherited fixture control.
                requests = [client.request("precedence." + str(index)) for index in range(3)]
                first = client.submit(requests[0])
                self.assertIs(first.status, Status.UNKNOWN)
                self.assertEqual(host.faults.disconnect_observed.is_set(), phase == "after_dispatch")
                second = client.submit(requests[1])
                self.assertIs(second.status, Status.UNKNOWN)
                self.assertTrue(host.faults.disconnect_observed.wait(1))
                self.assertEqual(host.faults.disconnected_status, "ACCEPTED_PENDING")
                self.assertIs(client.submit(requests[2]).status, Status.ACCEPTED_PENDING)
                for request in requests:
                    self.assertIs(self.terminal(client, request.command_id).status, Status.COMMITTED)
                self.assertEqual(host.fixture.effect_count, 0)

    def test_fault_armed_midflight_is_consumed_at_the_matching_reply_hook(self):
        with fixture() as (host, client, _):
            request = client.request("arm.midflight")
            before_reply, release_reply = threading.Event(), threading.Event()
            probe = host._disconnect_probe

            def gated_probe(path, phase, response=None):
                if path == "/v1/commands" and phase == "before_reply":
                    before_reply.set()
                    if not release_reply.wait(5):
                        raise AssertionError("test reply gate was not released")
                return probe(path, phase, response)

            with mock.patch.object(host, "_disconnect_probe", gated_probe):
                thread, done, result = self.start_submit(client, request)
                try:
                    self.assertTrue(before_reply.wait(3))
                    host.arm_disconnect("/v1/commands", "before_reply")
                    release_reply.set()
                    self.assertTrue(done.wait(3))
                finally:
                    release_reply.set()
                    thread.join(3)
                self.assertFalse(thread.is_alive())
                self.assertIs(self.response(result).status, Status.UNKNOWN)
                self.assertTrue(host.faults.disconnect_observed.wait(1))
            self.assertIs(self.terminal(client, request.command_id).status, Status.COMMITTED)
            self.assertIs(client.submit(client.request("arm.next")).status, Status.ACCEPTED_PENDING)


if __name__ == "__main__":
    unittest.main()
