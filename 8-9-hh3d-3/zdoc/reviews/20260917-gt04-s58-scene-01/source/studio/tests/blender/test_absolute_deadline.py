"""Private absolute deadline seam; in-memory doubles only, no native owners."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


sys.dont_write_bytecode = True
STUDIO = Path(__file__).resolve().parents[2]
if str(STUDIO.parent) not in sys.path:
    sys.path.insert(0, str(STUDIO.parent))


def load(name, relative):
    path = STUDIO / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


q = load("gt04_absolute_deadline_queue", "blender-addon/ui_queue.py")
ipc = load("gt04_absolute_deadline_ipc", "blender-addon/ipc_client.py")
from studio.host.blender import ui_host


MAX_DEADLINE = 2**53 - 1
INVALID_DEADLINES = (True, False, 0, -1, 2**53, 1.5, "1100", [], {})


def command(key="deadline-command", operation="mesh.create_box"):
    value = {
        "schema": q.SCHEMA,
        "command_id": key,
        "operation": operation,
        "expected_revision": "sha256:" + "1" * 64,
        "expected_context": {"mode": "OBJECT", "active_id": None, "selected_ids": []},
        "payload": {"object_id": "one", "size": [1, 1, 1]},
    }
    if operation == "scene.inspect":
        value.update(expected_revision=None, expected_context=None, payload={})
    return q.c.canonical(value)


class QueueAbsoluteDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.monotonic = 0.0
        self.wall_ms = 1000
        self.effects = []
        self.owner = q.CommandQueue(
            lambda value: self.effects.append(value["command_id"]) or {"revision": "observed"},
            clock=lambda: self.monotonic,
            lease_clock=lambda: self.wall_ms,
        )

    def arm_writer(self, epoch=1):
        lease = {"fencing_epoch": epoch, "expires_ms": 10000}
        self.owner.arm_lease(lease)
        return lease

    def assert_expired_without_effect(self, key="deadline-command", reason=None):
        self.owner.tick()
        row = self.owner.result(key)
        self.assertEqual(row["state"], "EXPIRED")
        self.assertFalse(row["public_ack"])
        if reason is not None:
            self.assertEqual(row["reason"], reason)
        self.assertEqual(self.effects, [])

    def test_invalid_deadlines_do_not_reserve_a_receipt_or_enqueue(self):
        for deadline in INVALID_DEADLINES:
            with self.subTest(deadline=deadline), self.assertRaisesRegex(q.c.Rejected, "ABSOLUTE_DEADLINE_LIMIT"):
                self.owner.submit(command(), deadline_ms=deadline)
        self.assertEqual(self.owner._rows, {})
        self.assertEqual(len(self.owner._pending), 0)
        self.assertEqual(self.effects, [])

    def test_deadline_is_private_envelope_metadata_not_native_command_field(self):
        value = json.loads(command())
        value["deadline_ms"] = 1100
        with self.assertRaises(q.c.Rejected):
            self.owner.submit(q.c.canonical(value))
        self.assertEqual(self.owner._rows, {})

    def test_new_command_expired_before_admission_never_enqueues(self):
        for deadline in (999, 1000):
            with self.subTest(deadline=deadline), self.assertRaisesRegex(q.c.Rejected, "COMMAND_DEADLINE"):
                self.owner.submit(command(), deadline_ms=deadline)
        self.owner.tick()
        self.assertEqual(self.owner._rows, {})
        self.assertEqual(len(self.owner._pending), 0)
        self.assertEqual(self.effects, [])

    def test_absolute_deadline_includes_wait_in_queue(self):
        self.owner.submit(command(), ttl_ms=5000, deadline_ms=1100)
        self.monotonic = .1
        self.wall_ms = 1100
        self.assert_expired_without_effect()

    def test_wall_clock_forward_jump_expires_before_monotonic_bound(self):
        self.owner.submit(command(), ttl_ms=5000, deadline_ms=1100)
        self.monotonic = .01
        self.wall_ms = 9000
        self.assert_expired_without_effect(reason="COMMAND_DEADLINE")

    def test_wall_clock_rollback_cannot_extend_original_remaining_time(self):
        self.owner.submit(command(), ttl_ms=5000, deadline_ms=1100)
        self.wall_ms = 100
        self.monotonic = .1
        self.assert_expired_without_effect(reason="QUEUE_DEADLINE")

    def test_ttl_is_still_a_shorter_monotonic_limit(self):
        self.owner.submit(command(), ttl_ms=20, deadline_ms=10000)
        self.wall_ms = 1010
        self.monotonic = .02
        self.assert_expired_without_effect(reason="QUEUE_DEADLINE")

    def test_absolute_boundary_is_rechecked_after_lease_validation(self):
        lease = self.arm_writer()
        self.owner.submit(command(), lease=lease, deadline_ms=1100)
        original_check = self.owner._check_lease

        def crossing_check(value, **options):
            original_check(value, **options)
            self.wall_ms = 1100

        self.owner._check_lease = crossing_check
        self.assert_expired_without_effect(reason="COMMAND_DEADLINE")

    def test_valid_just_before_boundary_dispatches_exactly_once(self):
        raw = command()
        pending = self.owner.submit(raw, deadline_ms=1100)
        self.assertEqual(pending["state"], "PENDING")
        self.assertEqual(self.effects, [])
        self.wall_ms = 1099
        self.monotonic = .099
        self.owner.tick()
        complete = self.owner.result("deadline-command")
        self.assertEqual(complete["state"], "COMPLETED")
        self.assertEqual(complete["result"], {"revision": "observed"})
        self.wall_ms = 2000
        self.assertEqual(self.owner.submit(raw, deadline_ms=1100), complete)
        self.owner.tick()
        self.assertEqual(self.effects, ["deadline-command"])

    def test_duplicate_pending_receipt_does_not_renew_absolute_deadline(self):
        raw = command()
        original = self.owner.submit(raw, ttl_ms=5000, deadline_ms=1100)
        self.wall_ms = 1050
        self.monotonic = .05
        self.assertEqual(self.owner.submit(raw, ttl_ms=5000, deadline_ms=9000), original)
        self.wall_ms = 100
        self.monotonic = .1
        self.assert_expired_without_effect()

    def test_duplicate_with_expired_envelope_can_still_lookup_pending_receipt(self):
        raw = command()
        original = self.owner.submit(raw, deadline_ms=1100)
        self.wall_ms = 1100
        self.assertEqual(self.owner.submit(raw, deadline_ms=1100), original)
        self.assert_expired_without_effect(reason="COMMAND_DEADLINE")

    def test_duplicate_with_earlier_deadline_does_not_change_original_admission(self):
        raw = command()
        original = self.owner.submit(raw, deadline_ms=1100)
        self.assertEqual(self.owner.submit(raw, deadline_ms=1), original)
        self.monotonic = .05
        self.wall_ms = 1050
        self.owner.tick()
        self.assertEqual(self.owner.result("deadline-command")["state"], "COMPLETED")
        self.assertEqual(self.effects, ["deadline-command"])

    def test_expired_receipt_cannot_be_revived_with_a_new_deadline(self):
        raw = command()
        self.owner.submit(raw, deadline_ms=1100)
        self.wall_ms = 1100
        self.assert_expired_without_effect()
        expired = self.owner.result("deadline-command")
        self.assertEqual(self.owner.submit(raw, deadline_ms=9000), expired)
        self.owner.tick()
        self.assertEqual(self.effects, [])
        self.assertEqual(len(self.owner._pending), 0)

    def test_deadline_change_does_not_hide_conflicting_command_payload(self):
        raw = command()
        self.owner.submit(raw, deadline_ms=1100)
        changed = json.loads(raw)
        changed["payload"]["size"] = [2, 2, 2]
        with self.assertRaisesRegex(q.c.Rejected, "COMMAND_CONFLICT"):
            self.owner.submit(q.c.canonical(changed), deadline_ms=9000)
        self.assertEqual(self.effects, [])

    def test_stop_drains_deadline_and_legacy_entries_and_preserves_receipts(self):
        first, second = command("absolute"), command("legacy")
        self.owner.submit(first, deadline_ms=1100)
        self.owner.submit(second)
        self.wall_ms = 1100
        self.owner.stop()
        self.owner.tick()
        for key in ("absolute", "legacy"):
            row = self.owner.result(key)
            self.assertEqual((row["state"], row["reason"]), ("CANCELLED", "STOPPED"))
        self.assertEqual(self.owner.submit(first, deadline_ms=1100), self.owner.result("absolute"))
        with self.assertRaisesRegex(q.c.Rejected, "STOPPED"):
            self.owner.submit(command("new"), deadline_ms=1100)
        self.assertEqual(len(self.owner._pending), 0)
        self.assertEqual(self.effects, [])

    def test_fence_rejection_precedes_absolute_expiry_after_dequeue(self):
        lease = self.arm_writer()
        self.owner.submit(command(), lease=lease, deadline_ms=1100)
        self.arm_writer(epoch=2)
        self.wall_ms = 1100
        self.owner.tick()
        row = self.owner.result("deadline-command")
        self.assertEqual((row["state"], row["reason"]), ("REJECTED", "WRITER_FENCED_OR_EXPIRED"))
        self.assertEqual(self.effects, [])

    def test_monotonic_expiry_precedes_fence_check(self):
        lease = self.arm_writer()
        self.owner.submit(command(), ttl_ms=20, lease=lease, deadline_ms=1100)
        self.arm_writer(epoch=2)
        self.monotonic = .02
        self.assert_expired_without_effect(reason="QUEUE_DEADLINE")

    def test_read_only_lease_exemption_does_not_exempt_absolute_deadline(self):
        self.arm_writer()
        self.owner.submit(command(operation="scene.inspect"), deadline_ms=1100)
        self.wall_ms = 1100
        self.assert_expired_without_effect(reason="COMMAND_DEADLINE")

    def test_max_safe_integer_and_legacy_none_are_accepted(self):
        self.owner.submit(command("maximum"), deadline_ms=MAX_DEADLINE)
        self.owner.submit(command("legacy"), deadline_ms=None)
        self.owner.tick()
        self.owner.tick()
        self.assertEqual(self.effects, ["maximum", "legacy"])


class IPCAbsoluteDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.queue = Mock()
        self.queue.submit.return_value = {"state": "PENDING", "public_ack": False}
        self.channel = Mock()
        self.client = object.__new__(ipc.Client)
        self.client.welcomed = {"control", "data"}
        self.client.owner = SimpleNamespace(queue=self.queue)
        self.client.ui = SimpleNamespace(c=q.c)
        self.client.channels = {"data": self.channel}

    def body(self, **extra):
        return dict(command=json.loads(command()), ttl_ms=5000, **extra)

    def dispatch(self, body):
        self.client.dispatch("data", {"kind": "submit", "body": body, "sequence": 7})

    def test_explicit_null_and_non_integer_envelopes_are_rejected_before_queue(self):
        for deadline in (None,) + INVALID_DEADLINES:
            with self.subTest(deadline=deadline):
                self.dispatch(self.body(deadline_ms=deadline))
                self.assertEqual(self.channel.queue.call_args.args, ("reply", {
                    "request_sequence": 7, "ok": False,
                    "reason": "COMMAND_REJECTED", "public_ack": False,
                }))
        self.queue.submit.assert_not_called()

    def test_unknown_or_missing_envelope_fields_fail_closed(self):
        bodies = [self.body(deadline_ms=1100, unexpected=True),
                  {"command": json.loads(command()), "deadline_ms": 1100}]
        for body in bodies:
            with self.subTest(body=body), self.assertRaisesRegex(ipc.IPCError, "IPC_FIELDS"):
                self.dispatch(body)
        self.queue.submit.assert_not_called()
        self.channel.queue.assert_not_called()

    def test_exact_deadline_and_lease_forwarded_without_native_payload_change(self):
        lease = {"fencing_epoch": 2, "expires_ms": 10000}
        self.dispatch(self.body(deadline_ms=MAX_DEADLINE, lease=lease))
        self.queue.submit.assert_called_once_with(
            command(), ttl_ms=5000, lease=lease, deadline_ms=MAX_DEADLINE)
        self.assertTrue(self.channel.queue.call_args.args[1]["ok"])

    def test_absent_deadline_preserves_legacy_submit_call(self):
        self.dispatch(self.body())
        self.queue.submit.assert_called_once_with(command(), ttl_ms=5000, lease=None)

    def test_actual_queue_rejects_late_ipc_arrival_without_effect(self):
        effects = []
        self.client.owner.queue = q.CommandQueue(
            lambda value: effects.append(value), clock=lambda: 0, lease_clock=lambda: 1100)
        self.dispatch(self.body(deadline_ms=1100))
        self.client.owner.queue.tick()
        self.assertFalse(self.channel.queue.call_args.args[1]["ok"])
        self.assertEqual(self.client.owner.queue._rows, {})
        self.assertEqual(effects, [])


class HostAbsoluteDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.owner = object.__new__(ui_host.BlenderUIHost)
        self.owner._stopped = False
        self.owner._source = {"fixture": "unchanged"}
        self.owner._check_project = Mock()
        self.owner._ask = Mock(return_value={"state": "COMPLETED", "public_ack": False})
        self.source_patch = patch.object(ui_host, "source_files", return_value=self.owner._source)
        self.source_patch.start()
        self.addCleanup(self.source_patch.stop)

    def test_submit_forwards_exact_absolute_deadline_independently_of_ttl(self):
        value = json.loads(command())
        lease = {"fencing_epoch": 3, "expires_ms": 10000}
        self.owner.submit(value, ttl_ms=23, lease=lease, deadline_ms=MAX_DEADLINE)
        self.owner._ask.assert_called_once_with("data", "submit", {
            "command": value, "ttl_ms": 23, "lease": lease, "deadline_ms": MAX_DEADLINE,
        })

    def test_submit_omits_absent_deadline_from_legacy_wire_body(self):
        value = json.loads(command())
        self.owner.submit(value, deadline_ms=None)
        self.owner._ask.assert_called_once_with("data", "submit", {"command": value, "ttl_ms": 5000})

    def test_submit_invalid_deadline_is_rejected_before_project_or_transport(self):
        for deadline in INVALID_DEADLINES:
            with self.subTest(deadline=deadline), self.assertRaisesRegex(ui_host.HostError, "ABSOLUTE_DEADLINE_LIMIT"):
                self.owner.submit(json.loads(command()), deadline_ms=deadline)
        self.owner._check_project.assert_not_called()
        self.owner._ask.assert_not_called()

    def test_execute_forwards_original_deadline_once_and_only_polls_result(self):
        value = json.loads(command())
        lease = {"fencing_epoch": 3, "expires_ms": 10000}
        complete = {"state": "COMPLETED", "public_ack": False}
        self.owner._ask.side_effect = [{"state": "PENDING"}, {"state": "PENDING"}, complete]
        with patch.object(ui_host, "time", SimpleNamespace(monotonic=lambda: 1, sleep=lambda delay: None)):
            actual = self.owner.execute(value, timeout=4, lease=lease, deadline_ms=123456789)
        self.assertEqual(actual, complete)
        calls = self.owner._ask.call_args_list
        self.assertEqual(calls[0].args, ("data", "submit", {
            "command": value, "ttl_ms": 5000, "lease": lease, "deadline_ms": 123456789,
        }))
        self.assertEqual([call.args for call in calls[1:]], [
            ("control", "result", {"command_id": "deadline-command"}),
            ("control", "result", {"command_id": "deadline-command"}),
        ])

    def test_execute_legacy_call_omits_deadline(self):
        value = json.loads(command())
        self.owner.execute(value)
        self.owner._ask.assert_called_once_with("data", "submit", {"command": value, "ttl_ms": 5000})


if __name__ == "__main__":
    unittest.main()
