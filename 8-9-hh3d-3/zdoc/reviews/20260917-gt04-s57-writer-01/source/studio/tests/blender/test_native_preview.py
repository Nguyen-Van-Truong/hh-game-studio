"""Native preview contract with inert doubles only: no bpy, engine or Journal."""
import copy
from contextlib import nullcontext
import importlib.util
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, STUDIO / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ui = load("gt04_preview_ui", "blender-addon/ui_adapter.py")
q = ui.queue_module
ipc = load("gt04_preview_ipc", "blender-addon/ipc_client.py")
from studio.host.blender import ui_host

CONTEXT = {"mode": "OBJECT", "active_id": None, "selected_ids": []}
BEFORE = {"revision": "sha256:" + "a" * 64, "context": CONTEXT,
          "snapshot": {"schema": "HH-BLENDER-FIXTURE-SCENE-1", "objects": [],
                       "units": {"system": "METRIC", "scale_length": 1.0}},
          "public_ack": False, "undo_supported": True}
PAYLOADS = {
    "mesh.create_box": {"object_id": "box", "size": [1, 2, 3]},
    "object.transform.set": {"object_id": "box", "location": [1, -2, 3],
                             "rotation": [.25, 0, -.5], "scale": [1, 2, .5]},
    "material.set_principled": {"object_id": "box", "material_id": "copper",
                               "base_color": [.25, .5, .75], "metallic": .5, "roughness": .25},
    "history.undo": {}, "history.redo": {},
}


def command(operation="mesh.create_box", key="preview-apply", **changes):
    value = {"schema": q.SCHEMA, "command_id": key, "operation": operation,
             "expected_revision": BEFORE["revision"], "expected_context": copy.deepcopy(CONTEXT),
        "payload": copy.deepcopy(PAYLOADS.get(operation, {}))}
    value.update(changes)
    return value


def fake_ui(*, objects=None, materials=None, before=None):
    owner = object.__new__(ui.UIAdapter)
    owner._held = False
    owner._stopped = False
    owner._commands = {}
    owner._history = []
    owner._cursor = 0
    owner._pending = None
    owner._operator_error = None
    owner._operator_result = None
    current = copy.deepcopy(before or BEFORE)
    owner._baseline = copy.deepcopy(current)
    owner.inspect = Mock(side_effect=lambda: copy.deepcopy(current))
    owner._objects = Mock(return_value={} if objects is None else objects)
    owner._view = lambda: nullcontext()
    owner._mode = Mock(side_effect=AssertionError("preview must not change mode"))
    owner._restore_context = Mock(side_effect=AssertionError("preview must not mutate selection"))
    owner.bpy = SimpleNamespace(data=SimpleNamespace(materials=materials or []),
                                ops=Mock(side_effect=AssertionError("no native operator")))
    return owner


def object_with_material(material=None):
    return SimpleNamespace(data=SimpleNamespace(materials=[] if material is None else [material]))


class PreviewValidationParity(unittest.TestCase):
    def both_reject(self, owner, value, message):
        checked = q.parse(q.c.canonical(value))
        for operation in (owner._preview, owner._dispatch_checked):
            with self.subTest(method=operation.__name__), self.assertRaisesRegex(q.c.Rejected, message):
                operation(checked)
        self.assertIsNone(owner._pending)
        owner._mode.assert_not_called()
        owner._restore_context.assert_not_called()
        self.assertEqual(owner.bpy.ops.mock_calls, [])

    def test_stale_revision_and_context_rejected_by_same_apply_preconditions(self):
        self.both_reject(fake_ui(), command(expected_revision="sha256:" + "0" * 64), "STALE_REVISION")
        context = {"mode": "OBJECT", "active_id": "box", "selected_ids": ["box"]}
        self.both_reject(fake_ui(), command(expected_context=context), "CONTEXT_DRIFT")

    def test_object_missing_collision_and_capacity_match_apply(self):
        self.both_reject(fake_ui(objects={"box": object_with_material()}), command(), "OBJECT_ID_OR_CAPACITY")
        self.both_reject(fake_ui(objects={"obj" + str(i): object_with_material() for i in range(16)}),
                         command(), "OBJECT_ID_OR_CAPACITY")
        for operation in ("object.transform.set", "material.set_principled"):
            self.both_reject(fake_ui(), command(operation), "OBJECT_MISSING")

    def test_material_ownership_duplicate_and_capacity_match_apply(self):
        material = {ui.base.materials.STABLE_ID: "other"}
        self.both_reject(fake_ui(objects={"box": object_with_material(material)}),
                         command("material.set_principled"), "MATERIAL_ID_CONFLICT")
        for materials in ([{ui.base.materials.STABLE_ID: "copper"}],
                          [{ui.base.materials.STABLE_ID: "m" + str(i)} for i in range(4)]):
            self.both_reject(fake_ui(objects={"box": object_with_material()}, materials=materials),
                             command("material.set_principled"), "MATERIAL_ID_OR_CAPACITY")

    def test_history_capacity_and_missing_target_match_apply(self):
        owner = fake_ui()
        owner._history = [(copy.deepcopy(BEFORE), copy.deepcopy(BEFORE))] * 16
        owner._cursor = 16
        self.both_reject(owner, command(), "HISTORY_CAPACITY")
        for operation in ("history.undo", "history.redo"):
            self.both_reject(fake_ui(), command(operation), "NO_OWNED_HISTORY")

    def test_history_target_is_returned_only_after_exact_history_guard(self):
        target = {**copy.deepcopy(BEFORE), "revision": "sha256:" + "b" * 64}
        for operation, history, cursor in (("history.undo", [(target, BEFORE)], 1),
                                            ("history.redo", [(BEFORE, target)], 0)):
            owner = fake_ui()
            owner._history = copy.deepcopy(history)
            owner._cursor = cursor
            old = copy.deepcopy((owner._commands, owner._history, owner._cursor, owner._baseline))
            result = owner._preview(command(operation))
            self.assertEqual(result["history_target"], target)
            self.assertEqual((owner._commands, owner._history, owner._cursor, owner._baseline), old)
            owner._mode.assert_not_called()
            self.assertEqual(owner.bpy.ops.mock_calls, [])
            mismatch = {**copy.deepcopy(BEFORE), "revision": "sha256:" + "c" * 64}
            owner._history = [(target, mismatch)] if operation == "history.undo" else [(mismatch, target)]
            self.both_reject(owner, command(operation), "HISTORY_STATE_DRIFT")

    def test_all_edit_previews_are_truthful_requested_values_without_apply_or_after_revision(self):
        for operation in ("mesh.create_box", "object.transform.set", "material.set_principled"):
            objects = {} if operation == "mesh.create_box" else {"box": object_with_material()}
            owner = fake_ui(objects=objects)
            value = command(operation)
            result = owner._preview(value)
            self.assertEqual(result["before"], BEFORE)
            self.assertEqual(result["requested_changes"], value["payload"])
            self.assertEqual(result["command_digest"], q.c.digest(value))
            self.assertEqual(result["schema"], q.PREVIEW_SCHEMA)
            self.assertIsNone(result["history_target"])
            self.assertEqual(result["affected_files"], [])
            self.assertTrue(result["no_effect"])
            self.assertFalse(result["apply_id_reserved"])
            self.assertFalse(result["public_ack"])
            self.assertFalse(result["scene_state_durable"])
            self.assertNotIn("after_revision", result)
            self.assertEqual(owner._commands, {})
            self.assertEqual(owner._history, [])
            self.assertIsNone(owner._pending)
            self.assertEqual(owner.bpy.ops.mock_calls, [])

    def test_edit_mode_preview_does_not_use_apply_mode_transition(self):
        state = copy.deepcopy(BEFORE)
        state["context"] = {"mode": "EDIT_MESH", "active_id": "box", "selected_ids": ["box"]}
        owner = fake_ui(objects={"box": object_with_material()}, before=state)
        value = command("object.transform.set", expected_context=state["context"])
        result = owner._preview(value)
        self.assertEqual(result["before"]["context"], state["context"])
        owner._mode.assert_not_called()
        owner._restore_context.assert_not_called()


class QueuePreviewTests(unittest.TestCase):
    def setUp(self):
        self.monotonic = 0.0
        self.wall = 1000
        self.apply = Mock(return_value={"applied": True})
        self.callback = Mock(side_effect=lambda value: {"command_id": value["command_id"], "requested": value["payload"]})
        self.queue = q.CommandQueue(self.apply, preview=self.callback,
                                    clock=lambda: self.monotonic, lease_clock=lambda: self.wall)
        self.lease = {"fencing_epoch": 1, "expires_ms": 10000}
        self.queue.arm_lease(self.lease)

    def preview(self, value=None, **changes):
        options = {"lease": self.lease, "deadline_ms": 1500, **changes}
        return self.queue.preview(q.c.canonical(value or command()), **options)

    def test_preview_does_not_dispatch_reserve_id_or_consume_queue_and_apply_still_runs_once(self):
        raw = q.c.canonical(command())
        first = self.preview()
        first["requested"]["size"][0] = 999
        self.assertEqual(self.preview()["requested"]["size"], [1, 2, 3])
        self.assertEqual(self.queue._rows, {})
        self.assertEqual(list(self.queue._pending), [])
        self.apply.assert_not_called()
        self.queue.submit(raw, lease=self.lease, deadline_ms=1500)
        self.queue.tick()
        self.queue.submit(raw, lease=self.lease, deadline_ms=1)
        self.queue.tick()
        self.apply.assert_called_once()
        self.assertEqual(self.queue.result("preview-apply")["state"], "COMPLETED")

    def test_typed_invalid_commands_fail_preview_and_submit_before_callbacks(self):
        for payload in ({"object_id": "../escape", "size": [1, 2, 3]},
                        {"object_id": "box", "size": [True, 2, 3]},
                        {"object_id": "box", "size": [0, 2, 3]},
                        {"object_id": "box", "size": [1, 2, 3], "script": "x"}):
            raw = q.c.canonical(command(payload=payload))
            for action in (self.queue.preview, self.queue.submit):
                with self.subTest(payload=payload, action=action.__name__), self.assertRaises(q.c.Rejected):
                    action(raw, lease=self.lease, deadline_ms=1500)
        self.callback.assert_not_called()
        self.apply.assert_not_called()
        self.assertEqual(self.queue._rows, {})

    def test_unarmed_missing_stale_or_expired_fence_rejects_before_callback(self):
        for lease in (None, {"fencing_epoch": 2, "expires_ms": 10000},
                      {"fencing_epoch": True, "expires_ms": 10000}):
            with self.subTest(lease=lease), self.assertRaises(q.c.Rejected):
                self.preview(lease=lease)
        self.wall = 10000
        with self.assertRaisesRegex(q.c.Rejected, "WRITER_FENCED_OR_EXPIRED"):
            self.preview()
        self.queue._lease = None
        with self.assertRaisesRegex(q.c.Rejected, "PREVIEW_WRITER_LEASE_REQUIRED"):
            self.preview()
        self.callback.assert_not_called()

    def test_deadline_and_ttl_are_strict_and_past_deadline_never_inspects(self):
        for value in (None, True, False, 0, -1, 2**53, 1500.0, "1500", [], {}):
            with self.subTest(value=value), self.assertRaises(q.c.Rejected):
                self.preview(deadline_ms=value)
        for value in (0, 5001, True, 1.0):
            with self.subTest(ttl=value), self.assertRaises(q.c.Rejected):
                self.preview(ttl_ms=value)
        with self.assertRaisesRegex(q.c.Rejected, "COMMAND_DEADLINE"):
            self.preview(deadline_ms=1000)
        self.callback.assert_not_called()

    def test_wall_clock_advance_and_rollback_cannot_publish_expired_preview(self):
        def forward(value):
            self.wall = 1500
            return {}
        self.queue._preview_callback = forward
        with self.assertRaisesRegex(q.c.Rejected, "COMMAND_DEADLINE"):
            self.preview()
        self.wall = 1000
        def rollback(value):
            self.wall = 1
            self.monotonic = .5
            return {}
        self.queue._preview_callback = rollback
        with self.assertRaisesRegex(q.c.Rejected, "PREVIEW_DEADLINE"):
            self.preview()
        self.assertEqual(self.queue._rows, {})
        self.apply.assert_not_called()

    def test_stop_and_rotated_fence_rechecked_after_inspection(self):
        def rotate(value):
            self.queue.arm_lease({"fencing_epoch": 2, "expires_ms": 10000})
            return {}
        self.queue._preview_callback = rotate
        with self.assertRaisesRegex(q.c.Rejected, "WRITER_FENCED_OR_EXPIRED"):
            self.preview()
        self.lease = {"fencing_epoch": 2, "expires_ms": 10000}
        def stop(value):
            self.queue.stop()
            return {}
        self.queue._preview_callback = stop
        with self.assertRaisesRegex(q.c.Rejected, "STOPPED"):
            self.preview()
        self.queue._preview_callback = self.callback
        with self.assertRaisesRegex(q.c.Rejected, "STOPPED"):
            self.preview()
        self.callback.assert_not_called()

    def test_existing_apply_id_is_not_approved_as_new_preview(self):
        self.queue.submit(q.c.canonical(command()), lease=self.lease, deadline_ms=1500)
        with self.assertRaisesRegex(q.c.Rejected, "PREVIEW_APPLY_ID_EXISTS"):
            self.preview()
        self.callback.assert_not_called()

    def test_output_cap_no_truncation_and_no_missing_callback_fallback(self):
        self.queue._preview_callback = lambda value: {"large": "x" * q.MAX_PREVIEW_BYTES}
        with self.assertRaisesRegex(q.c.Rejected, "PREVIEW_OUTPUT_LIMIT"):
            self.preview()
        self.queue._preview_callback = None
        with self.assertRaisesRegex(q.c.Rejected, "PREVIEW_OPERATION_UNSUPPORTED"):
            self.preview()
        self.apply.assert_not_called()

    def test_inspect_save_and_export_preview_are_explicitly_unsupported(self):
        cases = [command(operation="scene.inspect", expected_revision=None, expected_context=None, payload={})]
        # Construct from the unchanged command envelope without adding operations to PAYLOADS.
        cases = [dict(command(), operation="scene.inspect", expected_revision=None, expected_context=None, payload={}),
                 dict(command(), operation="checkpoint.save", payload={"slot": "checkpoint"}),
                 dict(command(), operation="export.prepare", payload={"slot": "export"})]
        for value in cases:
            with self.subTest(operation=value["operation"]), self.assertRaisesRegex(q.c.Rejected, "PREVIEW_OPERATION_UNSUPPORTED"):
                self.preview(value)
        self.callback.assert_not_called()

    def test_main_thread_guard_precedes_callback(self):
        result = []
        def action():
            try:
                self.preview()
            except q.c.Rejected as error:
                result.append(str(error))
        thread = threading.Thread(target=action)
        thread.start()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, ["MAIN_THREAD_REQUIRED"])
        self.callback.assert_not_called()


class IPCAndHostPreviewTests(unittest.TestCase):
    def setUp(self):
        self.queue = Mock()
        self.queue.preview.return_value = {"no_effect": True}
        self.channel = Mock()
        self.client = object.__new__(ipc.Client)
        self.client.welcomed = {"control", "data"}
        self.client.owner = SimpleNamespace(queue=self.queue)
        self.client.ui = SimpleNamespace(c=q.c)
        self.client.channels = {"data": self.channel}
        self.lease = {"fencing_epoch": 3, "expires_ms": 20000}

    def envelope(self):
        return {"command": command(), "lease": self.lease, "ttl_ms": 321, "deadline_ms": 12345}

    def test_exact_private_preview_action_forwards_original_deadline_and_fence(self):
        body = self.envelope()
        self.client.dispatch("data", {"kind": "preview", "body": body, "sequence": 7})
        self.queue.preview.assert_called_once_with(q.c.canonical(body["command"]), lease=self.lease,
                                                   ttl_ms=321, deadline_ms=12345)
        self.queue.submit.assert_not_called()
        self.assertTrue(self.channel.queue.call_args.args[1]["ok"])

    def test_preview_missing_null_or_bad_deadline_and_remote_callback_rejected(self):
        for value in (None, True, 0, 1.0):
            body = {**self.envelope(), "deadline_ms": value}
            self.client.dispatch("data", {"kind": "preview", "body": body, "sequence": 7})
            self.assertFalse(self.channel.queue.call_args.args[1]["ok"])
        for omitted in ("deadline_ms", "lease"):
            body = self.envelope()
            del body[omitted]
            self.client.dispatch("data", {"kind": "preview", "body": body, "sequence": 7})
            self.assertFalse(self.channel.queue.call_args.args[1]["ok"])
        with self.assertRaisesRegex(ipc.IPCError, "IPC_FIELDS"):
            self.client.dispatch("data", {"kind": "preview", "body": {**self.envelope(), "callback": "python"}, "sequence": 7})
        self.queue.preview.assert_not_called()
        self.queue.submit.assert_not_called()

    def test_recovery_owner_cannot_preview_mutations(self):
        self.client.recovery = {"readonly": True}
        self.client.dispatch("data", {"kind": "preview", "body": self.envelope(), "sequence": 7})
        self.assertFalse(self.channel.queue.call_args.args[1]["ok"])
        self.queue.preview.assert_not_called()

    def host(self):
        value = object.__new__(ui_host.BlenderUIHost)
        value._stopped = False
        value._source = {"source": "unchanged"}
        value._check_project = Mock()
        value._ask = Mock(return_value={"no_effect": True})
        return value

    def test_host_forwards_deadline_and_ttl_without_submit_or_result_polling(self):
        host = self.host()
        with patch.object(ui_host, "source_files", return_value=host._source):
            self.assertEqual(host.preview(command(), lease=self.lease, deadline_ms=12345, ttl_ms=321), {"no_effect": True})
        host._ask.assert_called_once_with("data", "preview", self.envelope(), timeout=1.321)

    def test_invalid_host_authority_rejected_before_project_or_ipc(self):
        for options in ({"deadline_ms": None}, {"deadline_ms": True}, {"ttl_ms": 5001},
                        {"lease": None}, {"lease": {"fencing_epoch": True, "expires_ms": 20000}}):
            host = self.host()
            arguments = {"lease": self.lease, "deadline_ms": 12345, **options}
            with self.subTest(options=options), self.assertRaises(ui_host.HostError):
                host.preview(command(), **arguments)
            host._check_project.assert_not_called()
            host._ask.assert_not_called()


if __name__ == "__main__":
    unittest.main()
