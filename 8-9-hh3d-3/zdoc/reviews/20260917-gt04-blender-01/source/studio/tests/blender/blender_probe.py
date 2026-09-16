"""Fixed trusted Blender program, run only from the frozen host fixture runner."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import sys
import threading

import bpy

ADDON = Path(__file__).resolve().parents[2] / "blender-addon"
spec = importlib.util.spec_from_file_location("gt04_owned_adapter", ADDON / "adapter.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
c = adapter.contract
ROWS = []


def check(label, passed):
    if type(passed) is not bool:
        raise RuntimeError("nonboolean check")
    ROWS.append({"label": label, "passed": passed})
    print("GT04_CHECK " + json.dumps(ROWS[-1]), flush=True)
    if not passed:
        raise RuntimeError("check did not hold: " + label)


def rejected(label, action, reason):
    try:
        action()
    except c.Rejected as exc:
        check(label, reason in str(exc))
    else:
        check(label, False)


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_root(raw):
    root = Path(raw).absolute()
    if ".." in Path(raw).parts or not root.is_dir():
        raise RuntimeError("fresh fixture root missing")
    for part in (root, *root.parents):
        if part.is_symlink() or getattr(part.lstat(), "st_file_attributes", 0) & 0x400:
            raise RuntimeError("reparse fixture path")
    return root


def save_new(root, name):
    if name not in ("checkpoint.blend", "fixture.blend"):
        raise RuntimeError("unknown fixed artifact")
    target = root / name
    staged = root / ("stage-" + name)
    if target.exists() or staged.exists():
        raise RuntimeError("refuse existing artifact")
    result = bpy.ops.wm.save_as_mainfile(filepath=str(staged), check_existing=False, copy=True)
    if result != {"FINISHED"} or not staged.is_file():
        raise RuntimeError("save did not complete")
    # Exclusive publication within this caller-owned fresh fixture, not a
    # protected GT02 store or a claim about attacker-writable directories.
    os.link(staged, target)
    staged.unlink()
    return {"name": name, "size_bytes": target.stat().st_size, "sha256": hash_file(target)}


def make(owner, command_id, operation, payload):
    state = owner.inspect()
    return {"schema": c.SCHEMA, "command_id": command_id, "operation": operation,
            "expected_revision": state["revision"], "expected_context": state["context"], "payload": payload}


def issue(owner, command):
    return owner.execute(c.canonical(command))


def edit(root):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for collection in (bpy.data.brushes, bpy.data.materials, bpy.data.images, bpy.data.worlds):
        for item in list(collection):
            collection.remove(item)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    owner = adapter.FixtureAdapter()
    initial = owner.inspect()
    check("empty_owned_fixture", initial["snapshot"]["objects"] == [])
    checkpoint = save_new(root, "checkpoint.blend")
    check("fresh_checkpoint", checkpoint["size_bytes"] > 0)
    cmd = make(owner, "create-anchor", "mesh.create_box", {"object_id": "anchor", "size": [1, 2, 3]})
    receipt = issue(owner, cmd)
    check("create_native_mesh", len(owner.inspect()["snapshot"]["objects"]) == 1)
    check("create_preserves_empty_selection", owner.inspect()["context"] == initial["context"])
    check("duplicate_create_original_receipt", issue(owner, cmd) == receipt)
    check("duplicate_create_no_extra_object", len(bpy.data.objects) == 1)
    conflict = json.loads(c.canonical(cmd))
    conflict["payload"]["size"] = [2, 2, 2]
    rejected("conflicting_id_no_effect", lambda: issue(owner, conflict), "COMMAND_CONFLICT")
    stale = make(owner, "stale-create", "mesh.create_box", {"object_id": "stale", "size": [1, 1, 1]})
    stale["expected_revision"] = initial["revision"]
    rejected("stale_revision_no_effect", lambda: issue(owner, stale), "STALE_REVISION")
    check("rejections_preserve_revision", owner.inspect()["revision"] == receipt["after"]["revision"])
    anchor = bpy.data.objects["GT04_anchor"]
    anchor.select_set(True)
    bpy.context.view_layer.objects.active = anchor
    before_mode = owner.inspect()
    drift = make(owner, "context-drift", "mesh.create_box", {"object_id": "drift", "size": [1, 1, 1]})
    owner._mode("EDIT")
    rejected("mode_drift_rejected", lambda: issue(owner, drift), "CONTEXT_DRIFT")
    edit_context = owner.inspect()["context"]
    check("inspect_restores_edit_mode", edit_context == {"mode": "EDIT_MESH", "active_id": "anchor", "selected_ids": ["anchor"]})
    second = make(owner, "create-second", "mesh.create_box", {"object_id": "second", "size": [0.1, 0.2, 0.3]})
    issue(owner, second)
    check("create_from_edit_restores_context", owner.inspect()["context"] == edit_context)
    transform = make(owner, "transform-anchor", "object.transform.set", {"object_id": "anchor", "location": [2, -3, 4], "rotation": [0.1, 0.2, 0.3], "scale": [1, 2, 0.5]})
    transformed = issue(owner, transform)
    check("transform_from_edit_restores_context", owner.inspect()["context"] == edit_context)
    check("transform_native_readback", transformed["after"]["snapshot"]["objects"][0]["location"] == [2, -3, 4])
    check("duplicate_transform_original_receipt", issue(owner, transform) == transformed)
    # Synchronous short-lived thread does not access bpy: entry guard rejects it.
    thread_errors = []
    def wrong_thread():
        try:
            owner.inspect()
        except c.Rejected as exc:
            thread_errors.append(str(exc))
    thread = threading.Thread(target=wrong_thread)
    thread.start()
    thread.join(2)
    check("thread_access_rejected_before_bpy", not thread.is_alive() and thread_errors == ["MAIN_THREAD_REQUIRED"])
    owner._mode("OBJECT")
    drift = make(owner, "manual-drift", "object.transform.set", {"object_id": "anchor", "location": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]})
    anchor.location.x = 5
    bpy.context.view_layer.update()
    rejected("manual_transform_invalidates_revision", lambda: issue(owner, drift), "STALE_REVISION")
    check("manual_change_preserved", anchor.location.x == 5)
    repair = make(owner, "known-transform", "object.transform.set", {"object_id": "anchor", "location": [2, -3, 4], "rotation": [0.1, 0.2, 0.3], "scale": [1, 2, 0.5]})
    issue(owner, repair)
    # Profile rejects unsupported in-memory dependencies before any operation.
    text = bpy.data.texts.new("unapproved")
    rejected("embedded_text_rejected", owner.inspect, "UNSUPPORTED_DEPENDENCY")
    bpy.data.texts.remove(text)
    duplicate = bpy.data.objects["GT04_second"]
    duplicate[adapter.STABLE_ID] = "anchor"
    rejected("duplicate_stable_id_rejected", owner.inspect, "UNSUPPORTED_OBJECT")
    duplicate[adapter.STABLE_ID] = "second"
    pending = make(owner, "after-stop", "mesh.create_box", {"object_id": "stopped", "size": [1, 1, 1]})
    owner.stop()
    rejected("stop_rejects_new_mutation", lambda: issue(owner, pending), "STOPPED")
    check("stop_keeps_original_receipt", issue(owner, transform) == transformed)
    final = owner.inspect()
    check("no_public_ack", final["public_ack"] is False and transformed["public_ack"] is False)
    saved = save_new(root, "fixture.blend")
    check("save_fresh_owned_fixture", saved["size_bytes"] > 0 and saved["sha256"] != checkpoint["sha256"])
    check("save_preserves_semantic_revision", owner.inspect()["revision"] == final["revision"])
    expected = {"snapshot": final["snapshot"], "revision": final["revision"], "saved": saved, "checkpoint": checkpoint}
    with (root / "expected.json").open("x", encoding="utf-8") as handle:
        json.dump(expected, handle, sort_keys=True, indent=2)
    return expected


def reopen(root, checkpoint=False):
    expected = json.loads((root / "expected.json").read_text(encoding="utf-8"))
    artifact = expected["checkpoint" if checkpoint else "saved"]
    path = root / artifact["name"]
    check("reopen_exact_file_hash", hash_file(path) == artifact["sha256"] and path.stat().st_size == artifact["size_bytes"])
    result = bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False, use_scripts=False)
    check("reopen_native_finished", result == {"FINISHED"})
    owner = adapter.FixtureAdapter()
    state = owner.inspect()
    if checkpoint:
        check("checkpoint_reopens_empty", state["snapshot"]["objects"] == [])
    else:
        check("reopen_exact_scene_revision", state["revision"] == expected["revision"])
        check("reopen_exact_mesh_transform", state["snapshot"] == expected["snapshot"])
        check("reopen_two_stable_meshes", [row["object_id"] for row in state["snapshot"]["objects"]] == ["anchor", "second"])
    check("reopen_no_external_dependencies", not bpy.data.libraries and not bpy.data.texts and not bpy.data.materials and not bpy.data.images)
    check("reopen_no_public_ack", state["public_ack"] is False)
    return {"revision": state["revision"], "snapshot": state["snapshot"], "saved": artifact}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("edit", "reopen", "checkpoint"), required=True)
    parser.add_argument("--owned-root", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    root = safe_root(args.owned_root)
    check("actual_pinned_background", bpy.app.background and bpy.app.version[:3] == (5, 2, 1))
    check("automatic_python_disabled", bpy.context.preferences.filepaths.use_scripts_auto_execute is False)
    result = edit(root) if args.phase == "edit" else reopen(root, args.phase == "checkpoint")
    report = {"schema": "HH-GT04-NATIVE-PROBE-1", "phase": args.phase, "version": bpy.app.version_string,
              "actual_blender": True, "ok": True, "checks": ROWS, "public_ack": False, "acceptance": False,
              "result": result}
    with (root / (args.phase + "-result.json")).open("x", encoding="utf-8") as handle:
        json.dump(report, handle, sort_keys=True, indent=2)
    print("GT04_RESULT " + json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
