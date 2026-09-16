"""Fixed trusted GUI program: event-loop queue, native history, owned file save/reopen."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
import traceback

import bpy

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ui = load("gt04_native_ui", HERE.parents[1] / "blender-addon/ui_adapter.py")
support = load("gt04_native_support", HERE / "blender_probe.py")
c = ui.c
ROWS = []
OWNER = None


def check(label, passed):
    ROWS.append({"label": label, "passed": passed is True})
    print("GT04_UI_CHECK " + json.dumps(ROWS[-1]), flush=True)
    if passed is not True:
        raise RuntimeError(label)


def make(owner, key, operation, payload=None):
    state = owner.inspect()
    return {"schema": ui.queue_module.SCHEMA, "command_id": key, "operation": operation,
            "expected_revision": state["revision"], "expected_context": state["context"], "payload": payload or {}}


def queued(owner, command, *, ttl_ms=5000, expected="COMPLETED"):
    raw = c.canonical(command)
    row = owner.queue.submit(raw, ttl_ms=ttl_ms)
    while row["state"] == "PENDING":
        yield
        row = owner.queue.result(command["command_id"])
    if row["state"] != expected:
        raise RuntimeError("queue result " + json.dumps(row))
    return row


def edit(root):
    global OWNER
    # Only the fresh factory scene owned by this process is cleared.
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in (bpy.data.meshes, bpy.data.cameras, bpy.data.lights, bpy.data.materials,
                       bpy.data.images, bpy.data.worlds, bpy.data.brushes):
        for item in list(collection):
            collection.remove(item)
    bpy.context.scene.unit_settings.system = "METRIC"
    OWNER = owner = ui.UIAdapter()
    initial = owner.inspect()
    check("empty_owned_ui_fixture", initial["snapshot"]["objects"] == [])
    checkpoint = support.save_new(root, "checkpoint.blend")
    check("native_gui_checkpoint", checkpoint["size_bytes"] > 0)
    create = make(owner, "create-anchor", "mesh.create_box", {"object_id": "anchor", "size": [1, 2, 3]})
    owner.queue.submit(c.canonical(create))
    check("enqueue_has_no_native_effect", owner.inspect() == initial)
    created = yield from queued(owner, create)
    check("timer_create_native_mesh", len(owner.inspect()["snapshot"]["objects"]) == 1)
    check("create_restores_context", owner.inspect()["context"] == initial["context"])
    undo = make(owner, "undo-create", "history.undo")
    undone = yield from queued(owner, undo)
    check("native_undo_removes_mesh", owner.inspect() == initial and not bpy.data.meshes)
    check("duplicate_undo_original_receipt", owner.queue.submit(c.canonical(undo)) == undone)
    check("duplicate_undo_no_second_effect", owner.inspect() == initial)
    yield from queued(owner, make(owner, "redo-create", "history.redo"))
    check("native_redo_restores_mesh", owner.inspect() == created["result"]["after"])
    check("duplicate_create_original_receipt", owner.queue.submit(c.canonical(create)) == created)
    check("duplicate_create_no_extra_mesh", len(bpy.data.objects) == 1 and len(bpy.data.meshes) == 1)
    with owner._view():
        anchor = owner._objects()["anchor"]
        anchor.select_set(True)
        bpy.context.view_layer.objects.active = anchor
    selected = owner.inspect()["context"]
    yield from queued(owner, make(owner, "create-second", "mesh.create_box", {"object_id": "second", "size": [0.1, 0.2, 0.3]}))
    check("create_preserves_active_selection", owner.inspect()["context"] == selected)
    before = owner.inspect()
    transformed = yield from queued(owner, make(owner, "transform-anchor", "object.transform.set",
                  {"object_id": "anchor", "location": [2, -3, 4], "rotation": [0.1, 0.2, 0.3], "scale": [1, 2, 0.5]}))
    check("transform_native_readback", owner.inspect()["snapshot"]["objects"][0]["location"] == [2, -3, 4])
    check("transform_restores_context", owner.inspect()["context"] == selected)
    yield from queued(owner, make(owner, "undo-transform", "history.undo"))
    check("native_undo_exact_transform", owner.inspect() == before)
    yield from queued(owner, make(owner, "redo-transform", "history.redo"))
    check("native_redo_exact_transform", owner.inspect() == transformed["result"]["after"])
    with owner._view():
        owner._mode("EDIT")
    edit_before = owner.inspect()
    check("inspect_keeps_edit_mesh", edit_before["context"]["mode"] == "EDIT_MESH")
    edited = yield from queued(owner, make(owner, "edit-transform", "object.transform.set",
                  {"object_id": "anchor", "location": [3, -2, 5], "rotation": [0.2, 0.3, 0.4], "scale": [1, 2, 0.5]}))
    check("edit_transform_restores_context", owner.inspect()["context"] == edit_before["context"])
    yield from queued(owner, make(owner, "undo-edit", "history.undo"))
    check("native_undo_edit_transform", owner.inspect() == edit_before)
    yield from queued(owner, make(owner, "redo-edit", "history.redo"))
    check("native_redo_edit_transform", owner.inspect() == edited["result"]["after"])
    with owner._view():
        owner._mode("OBJECT")
    current = owner.inspect()
    expired = make(owner, "expired-create", "mesh.create_box", {"object_id": "expired", "size": [1, 1, 1]})
    # Let the real monotonic deadline elapse while the owned consumer is
    # unregistered; no fake clock or blocking sleep in Blender's UI thread.
    bpy.app.timers.unregister(owner._timer)
    owner.queue.submit(c.canonical(expired), ttl_ms=1)
    resume_at = time.monotonic() + 0.03
    while time.monotonic() < resume_at:
        yield
    bpy.app.timers.register(owner._timer, first_interval=0.01, persistent=False)
    yield from queued(owner, expired, ttl_ms=1, expected="EXPIRED")
    check("queue_deadline_no_effect", owner.inspect() == current)
    stale = make(owner, "stale-create", "mesh.create_box", {"object_id": "stale", "size": [1, 1, 1]})
    stale["expected_revision"] = initial["revision"]
    row = yield from queued(owner, stale, expected="REJECTED")
    check("stale_revision_rejected_no_effect", row["reason"] == "STALE_REVISION" and owner.inspect() == current)
    pending = make(owner, "stopped-create", "mesh.create_box", {"object_id": "stopped", "size": [1, 1, 1]})
    owner.queue.submit(c.canonical(pending))
    owner.stop()
    yield
    check("stop_cancels_queued_no_effect", owner.queue.result("stopped-create")["state"] == "CANCELLED" and owner.inspect() == current)
    check("stop_preserves_receipt", owner.queue.submit(c.canonical(create)) == created)
    saved = support.save_new(root, "fixture.blend")
    check("native_gui_save_exact_revision", owner.inspect() == current and saved["size_bytes"] > 0)
    check("no_public_ack", created["public_ack"] is False and created["result"]["public_ack"] is False)
    expected = {"snapshot": current["snapshot"], "revision": current["revision"], "context": current["context"],
                "saved": saved, "checkpoint": checkpoint}
    with (root / "expected.json").open("x", encoding="utf-8") as handle:
        json.dump(expected, handle, sort_keys=True, indent=2)
    owner.close()
    check("owned_timer_unregistered", not bpy.app.timers.is_registered(owner._timer))
    return expected


def reopen(root, checkpoint=False):
    global OWNER
    expected = json.loads((root / "expected.json").read_text(encoding="utf-8"))
    artifact = expected["checkpoint" if checkpoint else "saved"]
    path = root / artifact["name"]
    check("reopen_exact_file_hash", support.hash_file(path) == artifact["sha256"] and path.stat().st_size == artifact["size_bytes"])
    check("native_gui_open_finished", bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False, use_scripts=False) == {"FINISHED"})
    OWNER = owner = ui.UIAdapter()
    state = owner.inspect()
    if checkpoint:
        check("checkpoint_exact_empty_scene", not state["snapshot"]["objects"])
    else:
        check("reopen_exact_semantic_revision", state["revision"] == expected["revision"])
        check("reopen_exact_mesh_transform", state["snapshot"] == expected["snapshot"])
        check("reopen_exact_active_selection", state["context"] == expected["context"])
    owner.close()
    check("reopen_no_public_ack", state["public_ack"] is False)
    return {"revision": state["revision"], "snapshot": state["snapshot"], "saved": artifact}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("edit", "reopen", "checkpoint"), required=True)
    parser.add_argument("--owned-root", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    root = support.safe_root(args.owned_root)
    report = {"schema": "HH-GT04-UI-PROBE-1", "phase": args.phase, "version": bpy.app.version_string,
              "actual_blender_gui": True, "ok": False, "public_ack": False, "acceptance": False}
    generator = None

    def finish():
        if OWNER is not None:
            OWNER.close()
        report["checks"] = ROWS
        with (root / (args.phase + "-result.json")).open("x", encoding="utf-8") as handle:
            json.dump(report, handle, sort_keys=True, indent=2)
        print("GT04_UI_RESULT " + json.dumps(report, sort_keys=True), flush=True)
        bpy.ops.wm.quit_blender()

    def step():
        nonlocal generator
        try:
            if generator is None:
                check("actual_pinned_gui", not bpy.app.background and bpy.app.version[:3] == (5, 2, 1))
                check("actual_window_event_loop", threading.current_thread() is threading.main_thread() and len(bpy.context.window_manager.windows) == 1)
                check("automatic_python_disabled", bpy.context.preferences.filepaths.use_scripts_auto_execute is False)
                if args.phase != "edit":
                    report.update(result=reopen(root, args.phase == "checkpoint"), ok=True)
                    finish()
                    return None
                generator = edit(root)
            next(generator)
            return 0.03
        except StopIteration as end:
            report.update(result=end.value, ok=True)
            finish()
            return None
        except BaseException as exc:
            report["failure"] = type(exc).__name__ + ": " + str(exc)
            traceback.print_exc()
            finish()
            return None

    bpy.app.timers.register(step, first_interval=0.5, persistent=False)


if __name__ == "__main__":
    main()
