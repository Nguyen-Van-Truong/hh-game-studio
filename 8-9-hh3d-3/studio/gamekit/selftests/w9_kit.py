"""W9 selftest: install gameplay kits, round-trip save/settings/rebind, recover a backup after a crash, replay, remove."""

from __future__ import annotations

import json
import os
import secrets
import shutil
from pathlib import Path

from .. import common as C
from .. import kit as K
from .. import scene as S
from . import Ctx

_MAIN = """[gd_scene format=3]

[node name="Main" type="Node2D"]
"""

_DRIVE = r"""extends SceneTree

var _done: bool = false


func _process(_delta: float) -> bool:
	if _done:
		return true
	_done = true
	var result: Dictionary = {"ok": false, "user_dir": OS.get_user_data_dir()}
	_run(result)
	print("HHGK_RESULT " + JSON.stringify(result))
	quit(0)
	return true


func _run(result: Dictionary) -> void:
	var save: Node = root.get_node_or_null("HHSave")
	var settings: Node = root.get_node_or_null("HHSettings")
	var rebind: Node = root.get_node_or_null("HHRebind")
	if save == null or settings == null or rebind == null:
		result["detail"] = "missing autoload"
		return
	var err: int = int(save.call("save_game", "slot1", {"hp": 3, "pos": [1, 2]}))
	var loaded: Variant = save.call("load_game", "slot1")
	var want: String = JSON.stringify({"hp": 3, "pos": [1, 2]}, "", true, true)
	result["save_err"] = err
	result["save_match"] = loaded is Dictionary and JSON.stringify(loaded, "", true, true) == want
	var slots: Variant = save.call("list_slots")
	var listed: Array = []
	if slots is PackedStringArray:
		for slot_name: String in slots:
			listed.append(slot_name)
	result["slots"] = listed
	_migrate_check(save, result)
	var err2: int = int(save.call("save_game", "slot1", {"hp": 3, "pos": [1, 2]}))
	result["resave_err"] = err2
	result["backup_rotate_err"] = int(save.call("save_game", "slot1", {"hp": 3, "pos": [1, 2]}))
	settings.call("set_bus_volume", "Music", 0.25)
	result["settings_err"] = int(settings.call("save_settings"))
	var key: InputEventKey = InputEventKey.new()
	key.keycode = KEY_J
	rebind.call("remap", "ui_accept", key)
	result["rebind_err"] = int(rebind.call("save_bindings"))
	var names: Array = []
	for i: int in AudioServer.bus_count:
		names.append(AudioServer.get_bus_name(i))
	result["bus_count"] = AudioServer.bus_count
	result["bus_names"] = names
	var pause_scene: PackedScene = load("res://addons/hh_kits/pause/pause_menu.tscn") as PackedScene
	var pause_menu: Node = pause_scene.instantiate()
	root.add_child(pause_menu)
	pause_menu.call("toggle")
	result["paused"] = paused
	pause_menu.call("resume")
	result["resumed"] = not paused
	var rebind_scene: PackedScene = load("res://addons/hh_kits/rebind/rebind_menu.tscn") as PackedScene
	var menu: Node = rebind_scene.instantiate()
	root.add_child(menu)
	menu.call("build")
	result["rebind_built"] = menu.get_node_or_null("Actions") != null
	result["ok"] = true


func _migrate(version: int, data: Dictionary) -> Dictionary:
	var copy: Dictionary = data.duplicate(true)
	copy["migrated_from"] = version
	return copy


func _migrate_check(save: Node, result: Dictionary) -> void:
	var text: String = FileAccess.get_file_as_string("user://saves/slot1.json")
	var parsed: Variant = JSON.parse_string(text)
	if not (parsed is Dictionary):
		result["migrated"] = false
		return
	var body: Dictionary = parsed
	body["version"] = 0
	var fa: FileAccess = FileAccess.open("user://saves/slot1.json", FileAccess.WRITE)
	if fa == null:
		result["migrated"] = false
		return
	fa.store_string(JSON.stringify(body))
	fa.close()
	save.set("migrate", Callable(self, "_migrate"))
	var migrated: Variant = save.call("load_game", "slot1")
	result["migrated"] = migrated is Dictionary and int((migrated as Dictionary).get("migrated_from", -1)) == 0 and int((migrated as Dictionary).get("hp", -1)) == 3
"""

_CHECK = r"""extends SceneTree

var _done: bool = false


func _process(_delta: float) -> bool:
	if _done:
		return true
	_done = true
	var result: Dictionary = {"ok": false, "user_dir": OS.get_user_data_dir()}
	var save: Node = root.get_node_or_null("HHSave")
	var settings: Node = root.get_node_or_null("HHSettings")
	if save == null or settings == null:
		result["detail"] = "missing autoload"
		print("HHGK_RESULT " + JSON.stringify(result))
		quit(0)
		return true
	var loaded: Variant = save.call("load_game", "slot1")
	result["loaded_empty"] = loaded is Dictionary and (loaded as Dictionary).is_empty()
	result["backup_hp"] = int((loaded as Dictionary).get("hp", -1)) if loaded is Dictionary else -1
	result["music"] = float(settings.call("get_bus_volume", "Music"))
	var found: bool = false
	var events: Array = InputMap.action_get_events(&"ui_accept")
	for ev: Variant in events:
		if ev is InputEventKey:
			var key: InputEventKey = ev as InputEventKey
			if key != null and (key.keycode == KEY_J or key.physical_keycode == KEY_J):
				found = true
	result["key_j"] = found
	result["ok"] = true
	print("HHGK_RESULT " + JSON.stringify(result))
	quit(0)
	return true
"""

_RECOVER = r"""extends SceneTree

var _done: bool = false


func _process(_delta: float) -> bool:
	if _done:
		return true
	_done = true
	var result: Dictionary = {"ok": false, "user_dir": OS.get_user_data_dir()}
	_run(result)
	print("HHGK_RESULT " + JSON.stringify(result))
	quit(0)
	return true


func _run(result: Dictionary) -> void:
	var save: Node = root.get_node_or_null("HHSave")
	var settings: Node = root.get_node_or_null("HHSettings")
	var rebind: Node = root.get_node_or_null("HHRebind")
	if save == null or settings == null or rebind == null:
		result["detail"] = "missing autoload"
		return
	_save_crash(save, result)
	_settings_crash(settings, result)
	_rebind_crash(rebind, result)
	result["ok"] = true


func _save_crash(save: Node, result: Dictionary) -> void:
	var payload: Dictionary = {"flag": "kept", "hp": 7}
	var want: String = JSON.stringify(payload, "", true, true)
	result["save_err"] = int(save.call("save_game", "a", payload))
	result["marker_err"] = _plant("user://saves/.a.json.bak")
	result["resave_err"] = int(save.call("save_game", "a", payload))
	result["stale_bak_replaced"] = FileAccess.file_exists("user://saves/.a.json.bak")
	result["final_before_corruption"] = FileAccess.file_exists("user://saves/a.json")
	result["save_corrupt"] = _corrupt("user://saves/a.json")
	var loaded: Variant = save.call("load_game", "a")
	result["bak_match"] = loaded is Dictionary and JSON.stringify(loaded, "", true, true) == want
	result["save_final_exists"] = FileAccess.file_exists("user://saves/a.json")
	result["save_bak_exists"] = FileAccess.file_exists("user://saves/.a.json.bak")
	var slots: Variant = save.call("list_slots")
	var listed: Array = []
	var bak_listed: bool = false
	if slots is PackedStringArray:
		for slot_name: String in slots:
			listed.append(slot_name)
			if slot_name.begins_with(".") or slot_name.find("bak") >= 0:
				bak_listed = true
	result["slots"] = listed
	result["bak_not_listed"] = not bak_listed


func _settings_crash(settings: Node, result: Dictionary) -> void:
	settings.call("set_bus_volume", "Music", 0.25)
	result["settings_err"] = int(settings.call("save_settings"))
	result["settings_marker_err"] = _plant("user://.settings.cfg.bak")
	result["settings_resave"] = int(settings.call("save_settings"))
	result["settings_stale_removed"] = not FileAccess.file_exists("user://.settings.cfg.bak")
	settings.call("set_bus_volume", "Music", 0.9)
	result["settings_rename"] = _crash_rename("user://settings.cfg", "user://.settings.cfg.bak")
	result["settings_load"] = int(settings.call("load_settings"))
	result["music"] = float(settings.call("get_bus_volume", "Music"))
	result["settings_final_missing"] = not FileAccess.file_exists("user://settings.cfg")
	result["settings_bak_exists"] = FileAccess.file_exists("user://.settings.cfg.bak")


func _rebind_crash(rebind: Node, result: Dictionary) -> void:
	result["rebind_marker_err"] = _plant("user://.input_map.cfg.bak")
	result["rebind_resave"] = int(rebind.call("save_bindings"))
	result["rebind_stale_removed"] = not FileAccess.file_exists("user://.input_map.cfg.bak")
	var other: InputEventKey = InputEventKey.new()
	other.keycode = KEY_K
	rebind.call("remap", "ui_accept", other)
	result["rebind_rename"] = _crash_rename("user://input_map.cfg", "user://.input_map.cfg.bak")
	result["rebind_load"] = int(rebind.call("load_bindings"))
	var found_j: bool = false
	var found_k: bool = false
	var events: Array = InputMap.action_get_events(&"ui_accept")
	for ev: Variant in events:
		if ev is InputEventKey:
			var key: InputEventKey = ev as InputEventKey
			if key != null and (key.keycode == KEY_J or key.physical_keycode == KEY_J):
				found_j = true
			if key != null and (key.keycode == KEY_K or key.physical_keycode == KEY_K):
				found_k = true
	result["rebind_restored"] = found_j and not found_k
	result["rebind_final_missing"] = not FileAccess.file_exists("user://input_map.cfg")
	result["rebind_bak_exists"] = FileAccess.file_exists("user://.input_map.cfg.bak")


func _plant(res_path: String) -> int:
	var fa: FileAccess = FileAccess.open(res_path, FileAccess.WRITE)
	if fa == null:
		return int(FileAccess.get_open_error())
	fa.store_string("stale")
	fa.flush()
	fa.close()
	return 0


func _corrupt(res_path: String) -> int:
	var fa: FileAccess = FileAccess.open(res_path, FileAccess.WRITE)
	if fa == null:
		return int(FileAccess.get_open_error())
	fa.store_string("{corrupt")
	fa.flush()
	fa.close()
	return 0


func _crash_rename(final_res: String, bak_res: String) -> int:
	var final_abs: String = ProjectSettings.globalize_path(final_res)
	var bak_abs: String = ProjectSettings.globalize_path(bak_res)
	var err: Error = DirAccess.rename_absolute(final_abs, bak_abs)
	return int(err)
"""


def _userdata(name: str) -> Path:
    return Path(os.environ.get("APPDATA", "")) / "Godot" / "app_userdata" / name


def _remove_userdata(name: str) -> None:
    path = _userdata(name)
    root = Path(os.environ.get("APPDATA", "")) / "Godot" / "app_userdata"
    if path.name != name:
        return
    if os.path.normcase(str(path.parent)) != os.path.normcase(str(root)):
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def _run_script(project: C.Project, script: Path) -> C.ProcessRun:
    return C.run_godot(project.root, script, headless=True, timeout=60)


def _after_drive(ctx: Ctx, project: C.Project, name: str, result: dict) -> None:
    ctx.check("save roundtrip", result.get("save_match") is True and result.get("save_err") == 0, result=result)
    ctx.check("slot listed", "slot1" in (result.get("slots") or []), slots=result.get("slots"))
    ctx.check("migrate hook", result.get("migrated") is True, result=result)
    ctx.check("settings saved", result.get("settings_err") == 0, result=result)
    ctx.check("rebind saved", result.get("rebind_err") == 0, result=result)
    ctx.check(
        "three audio buses",
        result.get("bus_count") == 3 and result.get("bus_names") == ["Master", "Music", "SFX"],
        buses=result.get("bus_names"),
    )
    ctx.check("pause menu toggles", result.get("paused") is True and result.get("resumed") is True, result=result)
    ctx.check("rebind menu builds", result.get("rebind_built") is True, result=result)
    save_path = _userdata(name) / "saves" / "slot1.json"
    ctx.check("save file in userdata", save_path.is_file(), path=str(save_path))
    if not save_path.is_file():
        return
    raw = json.loads(save_path.read_text(encoding="utf-8"))
    ctx.check(
        "save envelope",
        int(raw.get("version", 0)) == 1 and len(str(raw.get("sha256", ""))) == 64 and raw.get("data", {}).get("hp") in (3, 3.0),
        raw=raw,
    )
    text = save_path.read_text(encoding="utf-8")
    if '"hp": 3' in text:
        save_path.write_text(text.replace('"hp": 3', '"hp": 4', 1), encoding="utf-8", newline="\n")
    elif '"hp":3' in text:
        save_path.write_text(text.replace('"hp":3', '"hp":4', 1), encoding="utf-8", newline="\n")
    else:
        ctx.check("save file has hp field", False, text=text[:400])
        return
    check = ctx.root / "w9_check.gd"
    check.write_text(_CHECK, encoding="utf-8", newline="\n")
    second = ctx.guard("second process", lambda: _run_script(project, check))
    again = second.result if isinstance(second, C.ProcessRun) else None
    ctx.check(
        "second process finished",
        isinstance(second, C.ProcessRun) and second.exit_code == 0 and isinstance(again, dict),
        exit=None if not isinstance(second, C.ProcessRun) else second.exit_code,
        errors=None if not isinstance(second, C.ProcessRun) else second.errors[:8],
        tail="" if not isinstance(second, C.ProcessRun) else (second.stdout + second.stderr)[-800:],
    )
    if isinstance(again, dict):
        music = again.get("music")
        ctx.check("corrupt save loads last-good backup", again.get("loaded_empty") is False and again.get("backup_hp") == 3,
                  result=again)
        ctx.check("music volume restored", isinstance(music, (int, float)) and abs(float(music) - 0.25) < 1e-4, music=music)
        ctx.check("rebind survived restart", again.get("key_j") is True, result=again)
    _backup_recovery(ctx, project, name)


def _backup_recovery(ctx: Ctx, project: C.Project, name: str) -> None:
    script = ctx.root / "w9_backup.gd"
    script.write_text(_RECOVER, encoding="utf-8", newline="\n")
    run = ctx.guard("backup recovery", lambda: _run_script(project, script))
    result = run.result if isinstance(run, C.ProcessRun) else None
    warnings = run.warnings if isinstance(run, C.ProcessRun) else []
    ctx.check(
        "backup recovery finished",
        isinstance(run, C.ProcessRun) and run.exit_code == 0 and isinstance(result, dict) and result.get("ok") is True and not run.errors,
        exit=None if not isinstance(run, C.ProcessRun) else run.exit_code,
        errors=None if not isinstance(run, C.ProcessRun) else run.errors[:8],
        warnings=warnings[:8],
        tail="" if not isinstance(run, C.ProcessRun) else (run.stdout + run.stderr)[-1200:],
    )
    if not isinstance(result, dict):
        return
    ctx.check(
        "save backup restores slot a",
        result.get("save_err") == 0
        and result.get("marker_err") == 0
        and result.get("resave_err") == 0
        and result.get("stale_bak_replaced") is True
        and result.get("final_before_corruption") is True
        and result.get("save_corrupt") == 0
        and result.get("bak_match") is True
        and result.get("save_final_exists") is True
        and result.get("save_bak_exists") is True,
        result=result,
    )
    slots = result.get("slots") or []
    ctx.check(
        "list_slots ignores backup",
        result.get("bak_not_listed") is True and "a" in slots and "slot1" in slots,
        slots=slots,
    )
    music = result.get("music")
    ctx.check(
        "settings backup restores value",
        result.get("settings_err") == 0
        and result.get("settings_marker_err") == 0
        and result.get("settings_resave") == 0
        and result.get("settings_stale_removed") is True
        and result.get("settings_rename") == 0
        and result.get("settings_load") == 0
        and result.get("settings_final_missing") is True
        and result.get("settings_bak_exists") is True
        and isinstance(music, (int, float))
        and abs(float(music) - 0.25) < 1e-4,
        music=music,
        result=result,
    )
    ctx.check(
        "rebind backup restores binding",
        result.get("rebind_marker_err") == 0
        and result.get("rebind_resave") == 0
        and result.get("rebind_stale_removed") is True
        and result.get("rebind_rename") == 0
        and result.get("rebind_load") == 0
        and result.get("rebind_restored") is True
        and result.get("rebind_final_missing") is True
        and result.get("rebind_bak_exists") is True,
        result=result,
    )
    noise = [w for w in warnings if "backup" not in w.lower()]
    ctx.check(
        "backup load warns",
        any("HHSave" in w for w in warnings)
        and any("HHSettings" in w for w in warnings)
        and any("HHRebind" in w for w in warnings)
        and not noise,
        warnings=warnings[:8],
    )
    user = _userdata(name)
    ctx.check(
        "backup files sit in userdata",
        (user / "saves" / ".a.json.bak").is_file()
        and (user / "saves" / "a.json").is_file()
        and (user / ".settings.cfg.bak").is_file()
        and not (user / "settings.cfg").is_file()
        and (user / ".input_map.cfg.bak").is_file()
        and not (user / "input_map.cfg").is_file(),
    )


def run(ctx: Ctx) -> None:
    name = f"w9{os.getpid()}{secrets.token_hex(2)}"
    project = ctx.project(
        name,
        {"main.tscn": _MAIN},
        main_scene="res://main.tscn",
        settings='[display]\n\nwindow/size/viewport_width=640\nwindow/size/viewport_height=360\n',
    )
    try:
        _body(ctx, project, name)
    finally:
        _remove_userdata(name)


def _body(ctx: Ctx, project: C.Project, name: str) -> None:
    rows = K.list_kits()
    names = {kit["name"] for kit in rows}
    ctx.check(
        "list has the five kits",
        names == {"save", "settings", "rebind", "pause", "audio"} and all(kit.get("license") == "self-made" for kit in rows),
    )
    commands = [
        ("save", "w9.add.save"),
        ("settings", "w9.add.settings"),
        ("rebind", "w9.add.rebind"),
        ("pause", "w9.add.pause"),
        ("audio", "w9.add.audio"),
    ]
    for kit_name, command_id in commands:
        receipt = ctx.guard(f"add {kit_name}", lambda kit_name=kit_name, command_id=command_id: K.add_kit(project, kit_name, command_id))
        ctx.check(
            f"{kit_name} committed",
            isinstance(receipt, dict) and receipt.get("status") == "COMMITTED" and receipt.get("readback") == "FRESH_PROCESS_MATCH"
            and receipt.get("license") == "self-made",
            status=None if not isinstance(receipt, dict) else receipt.get("status"),
            license=None if not isinstance(receipt, dict) else receipt.get("license"),
        )
    expected = [
        "res://addons/hh_kits/save/hh_save.gd",
        "res://addons/hh_kits/settings/hh_settings.gd",
        "res://addons/hh_kits/rebind/hh_rebind.gd",
        "res://addons/hh_kits/rebind/rebind_menu.gd",
        "res://addons/hh_kits/rebind/rebind_menu.tscn",
        "res://addons/hh_kits/pause/pause_menu.gd",
        "res://addons/hh_kits/pause/pause_menu.tscn",
        "res://default_bus_layout.tres",
    ]
    missing = [res for res in expected if not project.res_to_path(res).is_file()]
    ctx.check("kit files exist", not missing, missing=missing)
    project_text = (project.root / "project.godot").read_text(encoding="utf-8")
    ctx.check(
        "project settings kept",
        f'config/name="{name}"' in project_text and "640" in project_text and "HHSave" in project_text and "HHSettings" in project_text and "HHRebind" in project_text,
        excerpt=project_text[:500],
    )
    layout = project.res_to_path("res://default_bus_layout.tres").read_text(encoding="utf-8")
    ctx.check("bus layout names Music and SFX", K.audio_layout_ok(layout), layout=layout[:400])
    clean = ctx.guard("scene check", lambda: S.check(project))
    ctx.check(
        "scene check clean",
        isinstance(clean, dict) and clean.get("clean") is True and not clean.get("godot_warnings"),
        problems=None if not isinstance(clean, dict) else clean.get("problems"),
        errors=None if not isinstance(clean, dict) else clean.get("godot_errors"),
        warnings=None if not isinstance(clean, dict) else clean.get("godot_warnings"),
    )

    drive = ctx.root / "w9_drive.gd"
    drive.write_text(_DRIVE, encoding="utf-8", newline="\n")
    first = ctx.guard("drive save settings rebind", lambda: _run_script(project, drive))
    result = first.result if isinstance(first, C.ProcessRun) else None
    ctx.check(
        "drive script finished",
        isinstance(first, C.ProcessRun) and first.exit_code == 0 and isinstance(result, dict) and not first.warnings,
        exit=None if not isinstance(first, C.ProcessRun) else first.exit_code,
        errors=None if not isinstance(first, C.ProcessRun) else first.errors[:8],
        warnings=None if not isinstance(first, C.ProcessRun) else first.warnings[:8],
        tail="" if not isinstance(first, C.ProcessRun) else (first.stdout + first.stderr)[-800:],
    )
    if isinstance(result, dict):
        _after_drive(ctx, project, name, result)

    replayed = ctx.guard("replay add", lambda: K.add_kit(project, "save", "w9.add.save"))
    ctx.check(
        "same command_id replays",
        isinstance(replayed, dict) and replayed.get("replayed") is True and replayed.get("command_id") == "w9.add.save",
    )
    ctx.expect_error("different request same command_id is CONFLICT", "CONFLICT", K.add_kit, project, "settings", "w9.add.save")
    ctx.check("conflict left the save script", project.res_to_path("res://addons/hh_kits/save/hh_save.gd").is_file())

    removed = ctx.guard("remove save", lambda: K.remove_kit(project, "save", "w9.rm.save"))
    ctx.check(
        "remove committed",
        isinstance(removed, dict)
        and removed.get("status") == "COMMITTED"
        and removed.get("readback") == "FRESH_PROCESS_MATCH"
        and removed.get("forced") is False
        and removed.get("modified") == [],
        status=None if not isinstance(removed, dict) else removed.get("status"),
    )
    after = (project.root / "project.godot").read_text(encoding="utf-8")
    ctx.check("HHSave autoload removed", "HHSave" not in after and not project.res_to_path("res://addons/hh_kits/save/hh_save.gd").exists())
    ctx.check("other autoloads kept", "HHSettings" in after and "HHRebind" in after, excerpt=after[:600])
    layout_path = project.res_to_path("res://default_bus_layout.tres")
    kit_layout = layout_path.read_bytes()
    voiced = kit_layout + b'bus/3/name = &"Voice"\n'
    layout_path.write_bytes(voiced)
    ctx.expect_error("extra bus blocks audio remove", "CONFLICT", K.remove_kit, project, "audio", "w9.rm.audio.voice")
    ctx.check("layout with extra bus kept", layout_path.read_bytes() == voiced)
    layout_path.write_bytes(kit_layout)
    removed_audio = ctx.guard("remove audio", lambda: K.remove_kit(project, "audio", "w9.rm.audio"))
    ctx.check(
        "audio kit removed",
        isinstance(removed_audio, dict) and removed_audio.get("status") == "COMMITTED"
        and not project.res_to_path("res://default_bus_layout.tres").exists(),
        status=None if not isinstance(removed_audio, dict) else removed_audio.get("status"),
    )
    _guard_edited_save(ctx, project)


def _guard_edited_save(ctx: Ctx, project: C.Project) -> None:
    """A game edit must survive remove, then --force may delete it."""
    readded = ctx.guard("reinstall save", lambda: K.add_kit(project, "save", "w9.add.save.edit"))
    ctx.check(
        "save reinstalled",
        isinstance(readded, dict) and readded.get("status") == "COMMITTED",
        status=None if not isinstance(readded, dict) else readded.get("status"),
    )
    save_gd = project.res_to_path("res://addons/hh_kits/save/hh_save.gd")
    save_gd.write_bytes(save_gd.read_bytes() + b"\n# game edit\n")
    project_bytes = (project.root / "project.godot").read_bytes()
    edited = save_gd.read_bytes()
    err = ctx.expect_error(
        "modified save refuses remove",
        "CONFLICT",
        K.remove_kit,
        project,
        "save",
        "w9.rm.save.keep",
    )
    ctx.check(
        "conflict left bytes unchanged",
        (project.root / "project.godot").read_bytes() == project_bytes and save_gd.read_bytes() == edited,
    )
    ctx.check(
        "conflict made no checkpoint",
        not (project.state / "checkpoints" / "w9.rm.save.keep").exists(),
    )
    ctx.check(
        "conflict names the edited file",
        err is not None
        and err.extra.get("modified") == ["res://addons/hh_kits/save/hh_save.gd"]
        and "keep them or pass --force" in err.detail,
        detail=None if err is None else err.detail,
    )
    forced = ctx.guard(
        "force remove edited save",
        lambda: K.remove_kit(project, "save", "w9.rm.save.force", force=True),
    )
    after = (project.root / "project.godot").read_text(encoding="utf-8")
    ctx.check(
        "force remove committed",
        isinstance(forced, dict)
        and forced.get("status") == "COMMITTED"
        and forced.get("forced") is True
        and forced.get("modified") == ["res://addons/hh_kits/save/hh_save.gd"]
        and not save_gd.exists()
        and "HHSave" not in after,
        status=None if not isinstance(forced, dict) else forced.get("status"),
        forced=None if not isinstance(forced, dict) else forced.get("forced"),
        modified=None if not isinstance(forced, dict) else forced.get("modified"),
    )
