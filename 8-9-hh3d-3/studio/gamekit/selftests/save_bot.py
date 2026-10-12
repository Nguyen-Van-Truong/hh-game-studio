"""Focused native smoke: retained saves, corruption recovery, and 3D bot coverage."""

from __future__ import annotations

import json
import os
import secrets
import shutil
from pathlib import Path

from .. import bot as B
from .. import common as C
from . import Ctx

_SAVE_DRIVE = r'''extends SceneTree

func _initialize() -> void:
	var script: Script = load("res://hh_save.gd") as Script
	var saver: Node = script.new()
	root.add_child(saver)
	var checks: Dictionary = {}
	var prior: Dictionary = {"hp": 7, "label": "làng cũ", "position": [1, 2, 3]}
	checks["first_save"] = int(saver.call("save_game", "main", prior)) == OK
	checks["second_save"] = int(saver.call("save_game", "main", {"hp": 9})) == OK
	checks["backup_kept"] = FileAccess.file_exists("user://saves/.main.json.bak")
	var live: Variant = saver.call("load_game", "main")
	checks["latest_loaded"] = live is Dictionary and int(live.get("hp", -1)) == 9
	checks["corrupt_live_written"] = _write("user://saves/main.json", "{truncated") == OK
	var recovered: Variant = saver.call("load_game", "main")
	checks["corrupt_primary_recovers_prior"] = recovered is Dictionary and JSON.stringify(recovered, "", true, true) == JSON.stringify(prior, "", true, true)
	checks["replacement_of_corrupt_live"] = int(saver.call("save_game", "main", {"hp": 11})) == OK
	checks["second_corruption_written"] = _write("user://saves/main.json", "{truncated") == OK
	var recovered_again: Variant = saver.call("load_game", "main")
	checks["corrupt_not_rotated_into_backup"] = recovered_again is Dictionary and int(recovered_again.get("hp", -1)) == 7
	checks["remove_live"] = DirAccess.remove_absolute(ProjectSettings.globalize_path("user://saves/main.json")) == OK
	var missing: Variant = saver.call("load_game", "main")
	checks["missing_primary_recovers_prior"] = missing is Dictionary and int(missing.get("hp", -1)) == 7
	checks["delete_slot"] = int(saver.call("delete_slot", "main")) == OK
	checks["delete_removes_backup"] = not FileAccess.file_exists("user://saves/.main.json.bak") and not FileAccess.file_exists("user://saves/main.json")
	var deleted: Variant = saver.call("load_game", "main")
	checks["deleted_slot_not_revived"] = deleted is Dictionary and deleted.is_empty()
	checks["save_after_delete"] = int(saver.call("save_game", "main", {"hp": 13})) == OK
	checks["backup_rotate"] = int(saver.call("save_game", "main", {"hp": 15})) == OK
	var raw: Variant = JSON.parse_string(FileAccess.get_file_as_string("user://saves/main.json"))
	raw["version"] = 2
	checks["newer_version_written"] = _write("user://saves/main.json", JSON.stringify(raw)) == OK
	var newer: Variant = saver.call("load_game", "main")
	checks["newer_version_not_silently_rolled_back"] = newer is Dictionary and newer.is_empty()
	checks["invalid_data_rejected"] = int(saver.call("save_game", "invalid", {"value": Vector3.ONE})) == ERR_INVALID_DATA
	checks["invalid_data_no_file"] = not FileAccess.file_exists("user://saves/invalid.json")
	var all_ok: bool = true
	for key: Variant in checks:
		all_ok = all_ok and bool(checks[key])
	print("HHGK_RESULT " + JSON.stringify({"ok": all_ok, "checks": checks, "user_dir": OS.get_user_data_dir()}))
	quit(0 if all_ok else 1)


func _write(path: String, text: String) -> Error:
	var fa: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if fa == null:
		return FileAccess.get_open_error()
	fa.store_string(text)
	fa.close()
	return OK
'''

_MOVE = '''extends Node3D

func _physics_process(delta: float) -> void:
	if Input.is_action_pressed("move_forward"):
		position.z += 60.0 * delta
'''

_SCENE = '''[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://move.gd" id="1"]

[node name="World" type="Node3D"]

[node name="Player" type="Node3D" parent="."]
script = ExtResource("1")
'''


def run(ctx: Ctx) -> None:
    name = f"savebot{os.getpid()}{secrets.token_hex(3)}"
    save_project = ctx.project(name, {
        "main.tscn": '[gd_scene format=3]\n[node name="Main" type="Node"]\n',
        "hh_save.gd": (C.GAMEKIT_DIR / "kits/save/hh_save.gd").read_bytes(),
        "drive.gd": _SAVE_DRIVE,
    }, main_scene="res://main.tscn")
    try:
        native = C.run_godot(save_project.root, save_project.root / "drive.gd", headless=True, timeout=30)
        result = native.result or {}
        ctx.check("save native exit and errors", native.exit_code == 0 and not native.timed_out and not native.errors,
                  process=native.summary(), tail=(native.stdout + native.stderr)[-2000:])
        for check, ok in (result.get("checks") or {}).items():
            ctx.check(str(check), ok is True)
        ctx.check("save native checks reported", len(result.get("checks") or {}) >= 20)
    finally:
        # Only the unique test project name under Godot's normal user-data root is removed.
        userdata_root = Path(os.environ.get("APPDATA", "")) / "Godot" / "app_userdata"
        userdata = userdata_root / name
        if os.name == "nt" and C.is_within(userdata.resolve(), userdata_root.resolve()) and userdata.name == name:
            shutil.rmtree(userdata, ignore_errors=True)
    bot_project = ctx.project(name + "bot", {"main.tscn": _SCENE, "move.gd": _MOVE},
                              main_scene="res://main.tscn",
                              settings='[input]\nmove_forward={"deadzone": 0.5, "events": []}\n')
    output = ctx.root / "bot-report.json"
    report = B.run_bot(bot_project, frames=30, seed=7, actions="move_forward", track="Player",
                       stuck_frames=5, stuck_dist=0.5, cell=1, out=str(output))
    ctx.check("3D bot completed", report.get("ok") is True and report.get("process", {}).get("exit_code") == 0,
              report=report)
    ctx.check("3D ground plane", report.get("plane") == "xz" and report.get("coverage", 0) >= 25 and not report.get("stuck"),
              plane=report.get("plane"), coverage=report.get("coverage"), bbox=report.get("bbox"))
    ctx.check("bot --out persisted full report", output.is_file() and json.loads(output.read_text(encoding="utf-8")) == report)
