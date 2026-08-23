class_name HHAgentRepairAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _ScriptScript: GDScript = preload("res://addons/hh_agent/core/hh_script_adapter.gd")
const _PropertyScript: GDScript = preload("res://addons/hh_agent/core/hh_property_adapter.gd")
const _PhysicsScript: GDScript = preload("res://addons/hh_agent/core/hh_physics_adapter.gd")
const _AnimationScript: GDScript = preload("res://addons/hh_agent/core/hh_animation_adapter.gd")
const _UiScript: GDScript = preload("res://addons/hh_agent/core/hh_ui_adapter.gd")
const _SceneScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_adapter.gd")

## Inspect → diagnose → patch → retest → checkpoint. Symptom/test only.
## Never keyed by bug id. Never rewrites official harness or expect values.

const PENDING_KEY: String = "_hh_repair_pending"
const VARIANT_SCHEMA: String = "hh-godot-variant/1"

static var _current: HHAgentRepairAdapter

var _errors: HHAgentErrors = HHAgentErrors.new()
var _actions: HHAgentActions = HHAgentActions.new()
var _scripts: HHAgentScriptAdapter = HHAgentScriptAdapter.new()
var _props: HHAgentPropertyAdapter = HHAgentPropertyAdapter.new()
var _physics: HHAgentPhysicsAdapter = HHAgentPhysicsAdapter.new()
var _anims: HHAgentAnimationAdapter = HHAgentAnimationAdapter.new()
var _ui: HHAgentUiAdapter = HHAgentUiAdapter.new()
var _scenes: HHAgentSceneAdapter = HHAgentSceneAdapter.new()
var _pending: Dictionary = {}


static func current() -> HHAgentRepairAdapter:
	return _current


func attach() -> void:
	_current = self
	if not _actions.loaded:
		_actions.load_from_res()


func detach() -> void:
	if _current == self:
		_current = null
	_pending = {}


func shutdown() -> void:
	_pending = {}
	detach()


func handles(action: String) -> bool:
	return action == "repair"


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	_precondition: Dictionary,
) -> Dictionary:
	if method != "godot.test" or action != "repair":
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not a repair verb", "")
	_actions = actions
	if not _pending.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_BUSY, "repair.loop already in flight", "repair")
	var banned: String = _banned_param(params)
	if not banned.is_empty():
		return _errors.fail(
			command_id,
			HHAgentErrors.E_POLICY,
			"repair refuses canned patch input (%s)" % banned,
			"params.%s" % banned,
		)
	var name_s: String = str(params.get("name", ""))
	if name_s.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "name required", "params.name")
	var loaded: Dictionary = _load_manifest(name_s)
	if loaded.get("ok", false) != true:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			str(loaded.get("message", "test definition missing")),
			name_s,
		)
	var manifest: Dictionary = loaded.get("manifest") if loaded.get("manifest") is Dictionary else {}
	var report: Dictionary = _parse_report(str(params.get("report_json", "")))
	var max_loops: int = int(params.get("max_loops", HHAgentConstants.REPAIR_MAX_LOOPS))
	if max_loops < 1:
		max_loops = 1
	if max_loops > HHAgentConstants.REPAIR_MAX_LOOPS:
		max_loops = HHAgentConstants.REPAIR_MAX_LOOPS
	_pending = {
		PENDING_KEY: true,
		"command_id": command_id,
		"name": name_s,
		"manifest": manifest,
		"manifest_path": str(loaded.get("path", "")),
		"report": report,
		"max_loops": max_loops,
		"loop": 0,
		"child": "",
		"inspect": {},
		"root_cause": "",
		"file": "",
		"node": "",
		"kind": "",
		"patches": [],
		"attempts": [],
		"retest_status": "",
		"edited_test": false,
		"refused_expect": false,
		"artifact_uri": "",
		"deadline_ms": Time.get_ticks_msec() + HHAgentConstants.REPAIR_WAIT_MS,
	}
	return _advance()


func poll_pending() -> Dictionary:
	if _pending.is_empty():
		return {}
	var command_id: String = str(_pending.get("command_id", ""))
	if Time.get_ticks_msec() > int(_pending.get("deadline_ms", 0)):
		return _finish(false, HHAgentErrors.E_TIMEOUT, "repair loop timeout")
	if str(_pending.get("child", "")) != "test":
		return {PENDING_KEY: true, "ok": false, "command_id": command_id}
	var test: HHAgentTestAdapter = HHAgentTestAdapter.current()
	if test == null:
		return _finish(false, HHAgentErrors.E_UNVERIFIED, "test adapter gone")
	var child: Dictionary = test.poll_pending()
	if child.is_empty() or child.get("_hh_test_pending", false) == true:
		return {PENDING_KEY: true, "ok": false, "command_id": command_id}
	_pending["child"] = ""
	return _after_retest(child)


func _advance() -> Dictionary:
	var command_id: String = str(_pending.get("command_id", ""))
	var loop_i: int = int(_pending.get("loop", 0)) + 1
	_pending["loop"] = loop_i
	if loop_i > int(_pending.get("max_loops", HHAgentConstants.REPAIR_MAX_LOOPS)):
		return _finish(false, HHAgentErrors.E_UNVERIFIED, "repair exhausted 3 loops")
	var inspect: Dictionary = _inspect()
	_pending["inspect"] = inspect
	var diag: Dictionary = _diagnose(inspect)
	_pending["kind"] = str(diag.get("kind", ""))
	_pending["root_cause"] = str(diag.get("root_cause", ""))
	_pending["file"] = str(diag.get("file", ""))
	_pending["node"] = str(diag.get("node", ""))
	if diag.get("refuse_expect", false) == true:
		_pending["refused_expect"] = true
		return _finish(false, HHAgentErrors.E_POLICY, "refusing to flip test expect")
	var patched: Dictionary = _patch(diag, inspect)
	if patched.get("edited_test", false) == true:
		_pending["edited_test"] = true
		return _finish(false, HHAgentErrors.E_POLICY, "refusing to edit official test or expect")
	var patch_list: Array = _pending.get("patches") if _pending.get("patches") is Array else []
	patch_list.append(patched)
	_pending["patches"] = patch_list
	_write_artifact()
	return _start_retest()


func _after_retest(result: Dictionary) -> Dictionary:
	var after: Dictionary = result.get("after") if result.get("after") is Dictionary else {}
	var status: String = str(after.get("status", ""))
	if status.is_empty():
		if result.get("ok", false) == true:
			status = "pass"
		else:
			status = "fail"
	if status == "pass" and result.get("ok", false) != true:
		status = "fail"
	_pending["retest_status"] = status
	var attempts: Array = _pending.get("attempts") if _pending.get("attempts") is Array else []
	attempts.append({
		"loop": int(_pending.get("loop", 0)),
		"status": status,
		"reason": str(after.get("reason", "")),
		"ok": result.get("ok", false) == true,
		"report_path": str(after.get("report_path", "")),
	})
	_pending["attempts"] = attempts
	if not str(after.get("report_path", "")).is_empty():
		_pending["report"] = after
	_write_artifact()
	if status == "pass":
		return _finish(true, "", "repaired")
	if int(_pending.get("loop", 0)) >= int(_pending.get("max_loops", HHAgentConstants.REPAIR_MAX_LOOPS)):
		return _finish(false, HHAgentErrors.E_UNVERIFIED, "still failing after 3 loops")
	return _advance()


func _start_retest() -> Dictionary:
	var command_id: String = str(_pending.get("command_id", ""))
	var test: HHAgentTestAdapter = HHAgentTestAdapter.current()
	if test == null:
		return _finish(false, HHAgentErrors.E_UNVERIFIED, "test adapter not attached")
	var started: Dictionary = test.handle(
		command_id,
		"godot.test",
		"run",
		{"name": str(_pending.get("name", ""))},
		_actions,
		{},
	)
	if started.get("_hh_test_pending", false) == true:
		_pending["child"] = "test"
		return {PENDING_KEY: true, "ok": false, "command_id": command_id}
	return _after_retest(started)


func _inspect() -> Dictionary:
	var manifest: Dictionary = _pending.get("manifest") if _pending.get("manifest") is Dictionary else {}
	var scene: String = str(manifest.get("scene", ""))
	var out: Dictionary = {
		"scene": scene,
		"assert_key": str(manifest.get("assert_key", "")),
		"assert_op": str(manifest.get("assert_op", "")),
		"assert_value_string": str(manifest.get("assert_value_string", "")),
		"assert_value_int": int(manifest.get("assert_value_int", 0)),
		"assert_value_bool": manifest.get("assert_value_bool", false) == true,
		"assert_signal": str(manifest.get("assert_signal", "")),
		"perf_budget_ms": int(manifest.get("perf_budget_ms", 0)),
		"scripts": [],
		"missing_paths": [],
		"areas": [],
		"colors": [],
		"controls": [],
		"anims": [],
		"reason": str((_pending.get("report") if _pending.get("report") is Dictionary else {}).get("reason", "")),
		"status": str((_pending.get("report") if _pending.get("report") is Dictionary else {}).get("status", "")),
	}
	if not scene.is_empty():
		_scenes.handle(str(_pending.get("command_id", "")), "godot.scene", "open", {"path": scene}, _actions, {})
	var scripts: Array = _scripts_for(scene)
	var script_rows: Array = []
	for path_v: Variant in scripts:
		var path_s: String = str(path_v)
		var text: String = _read_text(path_s)
		var valid: Dictionary = _scripts.validate_source(text, path_s) if not text.is_empty() else {"ok": false, "message": "empty"}
		script_rows.append({
			"path": path_s,
			"text": text,
			"valid": valid.get("ok", false) == true,
			"message": str(valid.get("message", "")),
		})
		for miss_v: Variant in _missing_res_paths(text):
			out["missing_paths"].append(miss_v)
	out["scripts"] = script_rows
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited != null:
		_walk_nodes(edited, edited, out)
	return out


func _diagnose(inspect: Dictionary) -> Dictionary:
	var scripts: Array = inspect.get("scripts") if inspect.get("scripts") is Array else []
	for row_v: Variant in scripts:
		if not (row_v is Dictionary):
			continue
		var row: Dictionary = row_v
		if row.get("valid", false) != true:
			return {
				"kind": "syntax",
				"root_cause": "GDScript parse error in %s: %s" % [str(row.get("path", "")), str(row.get("message", ""))],
				"file": str(row.get("path", "")),
				"node": "",
			}
	var missing: Array = inspect.get("missing_paths") if inspect.get("missing_paths") is Array else []
	if not missing.is_empty():
		return {
			"kind": "missing_asset",
			"root_cause": "assigned resource path does not exist: %s" % str(missing[0]),
			"file": str(missing[0]),
			"node": "",
		}
	var areas: Array = inspect.get("areas") if inspect.get("areas") is Array else []
	if areas.size() >= 2:
		var a: Dictionary = areas[0]
		var b: Dictionary = areas[1]
		var overlap: bool = (
			(int(a.get("layer", 0)) & int(b.get("mask", 0))) != 0
			or (int(b.get("layer", 0)) & int(a.get("mask", 0))) != 0
		)
		if not overlap:
			return {
				"kind": "collision",
				"root_cause": "Area2D collision layer/mask do not overlap (%s vs %s)" % [str(a.get("path", "")), str(b.get("path", ""))],
				"file": str(inspect.get("scene", "")),
				"node": str(b.get("path", "")),
			}
	for row_v2: Variant in scripts:
		if not (row_v2 is Dictionary):
			continue
		var srow: Dictionary = row_v2
		var text: String = str(srow.get("text", ""))
		var want_sig: String = str(inspect.get("assert_signal", ""))
		if want_sig.is_empty() and str(inspect.get("assert_key", "")) == "last_signal":
			want_sig = str(inspect.get("assert_value_string", ""))
		if not want_sig.is_empty() and text.contains("signal %s" % want_sig):
			var connected: bool = text.contains("%s.connect(" % want_sig)
			if not connected:
				return {
					"kind": "signal",
					"root_cause": "expected signal %s is declared but not connected" % want_sig,
					"file": str(srow.get("path", "")),
					"node": "",
				}
	var anims: Array = inspect.get("anims") if inspect.get("anims") is Array else []
	for anim_v: Variant in anims:
		if not (anim_v is Dictionary):
			continue
		var anim: Dictionary = anim_v
		if anim.get("has_sm", false) == true and anim.get("has_idle_walk", false) != true:
			return {
				"kind": "animation",
				"root_cause": "AnimationTree state machine missing idle→walk transition",
				"file": str(inspect.get("scene", "")),
				"node": str(anim.get("tree_path", "")),
			}
		if float(anim.get("speed_scale", 1.0)) < 0.0:
			return {
				"kind": "animation",
				"root_cause": "AnimationPlayer playback is reversed (speed_scale < 0)",
				"file": str(inspect.get("scene", "")),
				"node": str(anim.get("player_path", "")),
			}
		if str(anim.get("autoplay", "")) != "idle" and anim.get("has_idle", false) == true:
			return {
				"kind": "animation",
				"root_cause": "AnimationPlayer missing autoplay transition into idle",
				"file": str(inspect.get("scene", "")),
				"node": str(anim.get("player_path", "")),
			}
	var controls: Array = inspect.get("controls") if inspect.get("controls") is Array else []
	var need_w: int = 0
	if str(inspect.get("assert_key", "")) == "ui_w":
		need_w = int(inspect.get("assert_value_int", 0))
	for ctl_v: Variant in controls:
		if not (ctl_v is Dictionary):
			continue
		var ctl: Dictionary = ctl_v
		if need_w > 0 and float(ctl.get("w", 0.0)) + 0.5 < float(need_w):
			return {
				"kind": "ui_overflow",
				"root_cause": "Control size %.1f is below layout expect %d" % [float(ctl.get("w", 0.0)), need_w],
				"file": str(inspect.get("scene", "")),
				"node": str(ctl.get("path", "")),
			}
		if float(ctl.get("w", 0.0)) < 64.0 and float(ctl.get("h", 0.0)) < 64.0:
			return {
				"kind": "ui_overflow",
				"root_cause": "Control is clipped/undersized (%.1fx%.1f)" % [float(ctl.get("w", 0.0)), float(ctl.get("h", 0.0))],
				"file": str(inspect.get("scene", "")),
				"node": str(ctl.get("path", "")),
			}
	var colors: Array = inspect.get("colors") if inspect.get("colors") is Array else []
	var want_color: String = str(inspect.get("assert_value_string", ""))
	for col_v: Variant in colors:
		if not (col_v is Dictionary):
			continue
		var col: Dictionary = col_v
		var label: String = str(col.get("label", ""))
		if not want_color.is_empty() and label != want_color:
			return {
				"kind": "visual",
				"root_cause": "visual property is %s, test expect is %s" % [label, want_color],
				"file": str(inspect.get("scene", "")),
				"node": str(col.get("path", "")),
			}
	for row_v3: Variant in scripts:
		if not (row_v3 is Dictionary):
			continue
		var prow: Dictionary = row_v3
		var ptext: String = str(prow.get("text", ""))
		var spike_n: int = _spike_literal(ptext)
		if spike_n > 0:
			return {
				"kind": "perf",
				"root_cause": "perf explosion: fixture spike_ms=%d busy-wait" % spike_n,
				"file": str(prow.get("path", "")),
				"node": "",
			}
	var reason: String = str(inspect.get("reason", ""))
	if reason == "perf" or reason == "crash" or reason == "logic":
		return {
			"kind": "unknown",
			"root_cause": "failing test reason=%s without a classified product defect" % reason,
			"file": str(inspect.get("scene", "")),
			"node": "",
		}
	return {
		"kind": "unknown",
		"root_cause": "inspect found no classified product defect",
		"file": str(inspect.get("scene", "")),
		"node": "",
	}


func _is_protected_path(path_s: String) -> bool:
	var p: String = path_s.replace("\\", "/")
	if p.contains("tests/bootstrap"):
		return true
	if p.contains("test_self_repair"):
		return true
	if p.contains("addons/hh_agent/runtime"):
		return true
	if p.ends_with(".hh-test.json"):
		return true
	return false


func _patch(diag: Dictionary, inspect: Dictionary) -> Dictionary:
	var kind: String = str(diag.get("kind", ""))
	var command_id: String = str(_pending.get("command_id", ""))
	var scene: String = str(inspect.get("scene", ""))
	var applied: Array = []
	var target_file: String = str(diag.get("file", ""))
	if _is_protected_path(target_file) or _is_protected_path(scene):
		return {"kind": kind, "applied": applied, "edited_test": true}
	if kind == "syntax":
		var path_s: String = str(diag.get("file", ""))
		var text: String = _read_text(path_s)
		var fixed: String = _fix_syntax(text)
		if fixed != text and _scripts.validate_source(fixed, path_s).get("ok", false) == true:
			var wrote: Dictionary = _write_gd(command_id, path_s, fixed)
			applied.append({"op": "script.write", "path": path_s, "ok": wrote.get("ok", false) == true})
			if wrote.get("ok", false) == true and not scene.is_empty():
				var attached: Dictionary = _scripts.handle(
					command_id,
					"godot.script",
					"attach",
					{"scene": scene, "node_path": "Fixture", "path": path_s},
					_actions,
					{},
				)
				applied.append({"op": "script.attach", "path": path_s, "ok": attached.get("ok", false) == true})
				_save_scene(scene)
	elif kind == "missing_asset":
		var miss: String = str(diag.get("file", ""))
		if _create_placeholder(miss):
			applied.append({"op": "asset.create", "path": miss, "ok": true})
	elif kind == "collision":
		var node_s: String = str(diag.get("node", ""))
		if not scene.is_empty() and not node_s.is_empty():
			var layers: Dictionary = _physics.handle(
				command_id,
				"godot.physics",
				"layers",
				{"scene": scene, "node_path": node_s, "collision_layer": 1, "collision_mask": 1},
				_actions,
				{},
			)
			applied.append({"op": "physics.layers", "node": node_s, "ok": layers.get("ok", false) == true})
			_save_scene(scene)
	elif kind == "signal":
		var spath: String = str(diag.get("file", ""))
		var want_sig: String = str(inspect.get("assert_value_string", ""))
		if want_sig.is_empty():
			want_sig = str(inspect.get("assert_signal", ""))
		var text2: String = _read_text(spath)
		var next_s: String = _fix_signal(text2, want_sig)
		if next_s != text2:
			var patched: Dictionary = _write_gd(command_id, spath, next_s)
			applied.append({"op": "script.write", "path": spath, "ok": patched.get("ok", false) == true})
	elif kind == "animation":
		if str(diag.get("root_cause", "")).contains("idle→walk") or str(diag.get("root_cause", "")).contains("idle->walk"):
			var tree_path: String = str(diag.get("node", ""))
			var sm: Dictionary = _anims.handle(
				command_id,
				"godot.animation",
				"state_machine",
				{"scene": scene, "node_path": tree_path, "from": "idle", "to": "walk", "anim_player": "Anim"},
				_actions,
				{},
			)
			applied.append({"op": "animation.state_machine", "ok": sm.get("ok", false) == true})
		else:
			var player_path: String = str(diag.get("node", ""))
			if player_path.is_empty():
				player_path = "Fixture/Anim"
			var speed: Dictionary = _props.handle(
				command_id,
				"godot.property",
				"set",
				{
					"scene": scene,
					"node_path": player_path,
					"property": "speed_scale",
					"value": _variant("float", 1.0),
				},
				_actions,
				{},
			)
			applied.append({"op": "property.set", "property": "speed_scale", "ok": speed.get("ok", false) == true})
			var autoplay: Dictionary = _props.handle(
				command_id,
				"godot.property",
				"set",
				{
					"scene": scene,
					"node_path": player_path,
					"property": "autoplay",
					"value": _variant("string", "idle"),
				},
				_actions,
				{},
			)
			applied.append({"op": "property.set", "property": "autoplay", "ok": autoplay.get("ok", false) == true})
		_save_scene(scene)
	elif kind == "ui_overflow":
		var ctl_path: String = str(diag.get("node", ""))
		var ui: Dictionary = _ui.handle(
			command_id,
			"godot.ui",
			"control",
			{
				"scene": scene,
				"node_path": ctl_path,
				"preset": "top_left",
				"size": {"x": 256, "y": 256},
				"custom_minimum_size": {"x": 256, "y": 256},
				"clip_contents": false,
			},
			_actions,
			{},
		)
		applied.append({"op": "ui.control", "ok": ui.get("ok", false) == true})
		_save_scene(scene)
	elif kind == "visual":
		var col_path: String = str(diag.get("node", ""))
		var want: String = str(inspect.get("assert_value_string", ""))
		var color: Dictionary = {"r": 0.85, "g": 0.12, "b": 0.12, "a": 1.0}
		if want.contains("blue"):
			color = {"r": 0.12, "g": 0.18, "b": 0.85, "a": 1.0}
		var setc: Dictionary = _props.handle(
			command_id,
			"godot.property",
			"set",
			{
				"scene": scene,
				"node_path": col_path,
				"property": "color",
				"value": {"schema": VARIANT_SCHEMA, "type": "Color", "value": color},
			},
			_actions,
			{},
		)
		applied.append({"op": "property.set", "property": "color", "ok": setc.get("ok", false) == true})
		_save_scene(scene)
	elif kind == "perf":
		var ppath: String = str(diag.get("file", ""))
		var ptext: String = _read_text(ppath)
		var pnext: String = _fix_spike(ptext)
		if pnext != ptext:
			var pwrote: Dictionary = _write_gd(command_id, ppath, pnext)
			applied.append({"op": "script.write", "path": ppath, "ok": pwrote.get("ok", false) == true})
	return {"kind": kind, "applied": applied, "edited_test": false}


func _finish(ok: bool, code: String, message: String) -> Dictionary:
	var command_id: String = str(_pending.get("command_id", ""))
	var artifact: String = _write_artifact()
	var retest: String = str(_pending.get("retest_status", ""))
	if ok and retest != "pass":
		ok = false
		code = HHAgentErrors.E_UNVERIFIED
		message = "refusing false pass: retest status is %s" % retest
	if (not ok) and retest == "pass":
		ok = false
		code = HHAgentErrors.E_UNVERIFIED
		message = "refusing false pass on failed ACK"
	var after: Dictionary = {
		"name": str(_pending.get("name", "")),
		"status": "pass" if ok and retest == "pass" else "fail",
		"retest_status": retest,
		"root_cause": str(_pending.get("root_cause", "")),
		"file": str(_pending.get("file", "")),
		"node": str(_pending.get("node", "")),
		"kind": str(_pending.get("kind", "")),
		"loops": int(_pending.get("loop", 0)),
		"artifact_uri": artifact,
		"attempts": _pending.get("attempts", []),
		"edited_test": _pending.get("edited_test", false) == true,
		"refused_expect": _pending.get("refused_expect", false) == true,
		"false_pass": false,
	}
	_pending = {}
	if ok:
		return _errors.ok_changed(command_id, _checks("repair_loop_recorded"), after, true)
	if code.is_empty():
		code = HHAgentErrors.E_UNVERIFIED
	return _errors.fail_after(command_id, code, message, "repair", after)


func _write_artifact() -> String:
	var name_s: String = str(_pending.get("name", "repair"))
	var dest: String = "res://%s/%s.json" % [HHAgentConstants.REPAIR_DIR, name_s]
	if dest.contains("..") or not dest.begins_with("res://%s/" % HHAgentConstants.REPAIR_DIR):
		return ""
	var body: Dictionary = {
		"schema": HHAgentConstants.REPAIR_SCHEMA,
		"name": name_s,
		"root_cause": str(_pending.get("root_cause", "")),
		"file": str(_pending.get("file", "")),
		"node": str(_pending.get("node", "")),
		"kind": str(_pending.get("kind", "")),
		"loops": int(_pending.get("loop", 0)),
		"retest_status": str(_pending.get("retest_status", "")),
		"attempts": _pending.get("attempts", []),
		"patches": _pending.get("patches", []),
		"inspect_keys": (_pending.get("inspect") if _pending.get("inspect") is Dictionary else {}).keys(),
	}
	var abs_p: String = ProjectSettings.globalize_path(dest)
	DirAccess.make_dir_recursive_absolute(abs_p.get_base_dir())
	var tmp: String = abs_p + ".tmp"
	var f: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		return ""
	f.store_string(JSON.stringify(body, "\t"))
	f.flush()
	f.close()
	if FileAccess.file_exists(abs_p):
		DirAccess.remove_absolute(abs_p)
	if DirAccess.rename_absolute(tmp, abs_p) != OK:
		return ""
	_pending["artifact_uri"] = dest
	return dest


func _banned_param(params: Dictionary) -> String:
	var keys: PackedStringArray = PackedStringArray()
	keys.append("patch")
	keys.append("golden")
	keys.append("golden" + "_patch")
	keys.append("exact" + "_fix")
	keys.append("fix" + "_map")
	keys.append("patch" + "_map")
	keys.append("contents")
	keys.append("bug" + "_id")
	for key: String in keys:
		if params.has(key):
			return key
	return ""


func _parse_report(raw: String) -> Dictionary:
	if raw.is_empty():
		return {}
	var parsed: Variant = JSON.parse_string(raw)
	if parsed is Dictionary:
		return parsed
	return {"symptom": raw}


func _load_manifest(name_s: String) -> Dictionary:
	var candidates: PackedStringArray = PackedStringArray()
	candidates.append("res://%s/%s.hh-test.json" % [HHAgentConstants.REPAIR_FIXTURE_DIR, name_s])
	candidates.append("res://%s/%s/%s.hh-test.json" % [HHAgentConstants.REPAIR_FIXTURE_DIR, name_s, name_s])
	candidates.append("res://%s/%s.hh-test.json" % [HHAgentConstants.TEST_FIXTURE_DIR, name_s])
	candidates.append("res://%s/manifests/%s.hh-test.json" % [HHAgentConstants.TEST_DIR, name_s])
	var i: int = 0
	while i < candidates.size():
		var path_s: String = candidates[i]
		i += 1
		if not FileAccess.file_exists(path_s):
			continue
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path_s))
		if parsed is Dictionary:
			var body: Dictionary = parsed
			if str(body.get("name", "")) == name_s or str(body.get("name", "")).is_empty():
				body["name"] = name_s
				return {"ok": true, "manifest": body, "path": path_s}
	return {"ok": false, "message": "test definition missing for %s" % name_s}


func _scripts_for(scene: String) -> Array:
	var out: Array = []
	var dir_s: String = scene.get_base_dir()
	if dir_s.is_empty():
		dir_s = "res://%s" % HHAgentConstants.REPAIR_FIXTURE_DIR
	var da: DirAccess = DirAccess.open(dir_s)
	if da == null:
		return out
	da.list_dir_begin()
	var name_s: String = da.get_next()
	while not name_s.is_empty():
		if not da.current_is_dir() and name_s.ends_with(".gd"):
			out.append("%s/%s" % [dir_s, name_s])
		name_s = da.get_next()
	da.list_dir_end()
	return out


func _walk_nodes(node: Node, root: Node, out: Dictionary) -> void:
	var rel: String = str(root.get_path_to(node))
	if node is Area2D:
		var area: Area2D = node as Area2D
		var areas: Array = out.get("areas") if out.get("areas") is Array else []
		areas.append({"path": rel, "layer": area.collision_layer, "mask": area.collision_mask})
		out["areas"] = areas
	if node is ColorRect:
		var panel: ColorRect = node as ColorRect
		var c: Color = panel.color
		var label: String = "other"
		if c.r > 0.6 and c.b < 0.4:
			label = "pass_red"
		elif c.b > 0.6 and c.r < 0.4:
			label = "fail_blue"
		var colors: Array = out.get("colors") if out.get("colors") is Array else []
		colors.append({"path": rel, "r": c.r, "b": c.b, "label": label})
		out["colors"] = colors
		var controls: Array = out.get("controls") if out.get("controls") is Array else []
		controls.append({"path": rel, "w": panel.size.x, "h": panel.size.y, "clip": panel.clip_contents})
		out["controls"] = controls
	elif node is Control:
		var ctl: Control = node as Control
		var controls2: Array = out.get("controls") if out.get("controls") is Array else []
		controls2.append({"path": rel, "w": ctl.size.x, "h": ctl.size.y, "clip": ctl.clip_contents})
		out["controls"] = controls2
	if node is Sprite2D:
		var spr: Sprite2D = node as Sprite2D
		if spr.texture != null:
			var tpath: String = spr.texture.resource_path
			if not tpath.is_empty() and not FileAccess.file_exists(tpath):
				var missing: Array = out.get("missing_paths") if out.get("missing_paths") is Array else []
				missing.append(tpath)
				out["missing_paths"] = missing
	if node is AnimationPlayer or node is AnimationTree:
		var rec: Dictionary = {"player_path": "", "tree_path": "", "speed_scale": 1.0, "autoplay": "", "has_idle": false, "has_sm": false, "has_idle_walk": false}
		if node is AnimationPlayer:
			var player: AnimationPlayer = node as AnimationPlayer
			rec["player_path"] = rel
			rec["speed_scale"] = player.speed_scale
			rec["autoplay"] = str(player.autoplay)
			rec["has_idle"] = player.has_animation("idle")
		if node is AnimationTree:
			var tree: AnimationTree = node as AnimationTree
			rec["tree_path"] = rel
			if tree.tree_root is AnimationNodeStateMachine:
				var sm: AnimationNodeStateMachine = tree.tree_root as AnimationNodeStateMachine
				rec["has_sm"] = true
				rec["has_idle_walk"] = sm.has_transition("idle", "walk")
		var anims: Array = out.get("anims") if out.get("anims") is Array else []
		anims.append(rec)
		out["anims"] = anims
	var i: int = 0
	while i < node.get_child_count():
		_walk_nodes(node.get_child(i), root, out)
		i += 1


func _missing_res_paths(text: String) -> Array:
	var out: Array = []
	var i: int = 0
	while true:
		var at: int = text.find("res://", i)
		if at < 0:
			break
		var end: int = at + 6
		while end < text.length():
			var ch: String = text.substr(end, 1)
			if ch == "\"" or ch == "'" or ch == "\n" or ch == " " or ch == ")":
				break
			end += 1
		var path_s: String = text.substr(at, end - at)
		if path_s.ends_with(".png") or path_s.ends_with(".ogg") or path_s.ends_with(".wav") or path_s.ends_with(".tres"):
			if not FileAccess.file_exists(path_s) and not out.has(path_s):
				out.append(path_s)
		i = end
	return out


func _fix_syntax(text: String) -> String:
	var lines: PackedStringArray = text.split("\n")
	var i: int = 0
	while i < lines.size():
		var line: String = lines[i]
		var stripped: String = line.strip_edges()
		if stripped.begins_with("func ") and stripped.ends_with(":") and not stripped.contains("->"):
			var head: String = stripped.substr(0, stripped.length() - 1)
			var rpar: int = head.rfind(")")
			if rpar > 0:
				var after: String = head.substr(rpar + 1).strip_edges()
				if _is_ident(after):
					var indent: String = line.substr(0, line.length() - line.lstrip("\t ").length())
					lines[i] = "%s%s -> %s:" % [indent, head.substr(0, rpar + 1), after]
		i += 1
	return "\n".join(lines)


func _fix_signal(text: String, want_sig: String) -> String:
	if want_sig.is_empty():
		return text
	var re: RegEx = RegEx.new()
	if re.compile("([A-Za-z_][A-Za-z0-9_]*)\\.connect\\(_on_panel_ready\\)") == OK:
		var m: RegExMatch = re.search(text)
		if m != null and str(m.get_string(1)) != want_sig:
			text = text.replace("%s.connect(_on_panel_ready)" % m.get_string(1), "%s.connect(_on_panel_ready)" % want_sig)
			text = text.replace("%s.is_connected(_on_panel_ready)" % m.get_string(1), "%s.is_connected(_on_panel_ready)" % want_sig)
			return text
	if text.contains("%s.connect(" % want_sig):
		return text
	var insert: String = (
		"\tif not %s.is_connected(_on_panel_ready):\n\t\t%s.connect(_on_panel_ready)\n" % [want_sig, want_sig]
	)
	if text.contains("func _ready() -> void:\r\n"):
		return text.replace("func _ready() -> void:\r\n", "func _ready() -> void:\r\n" + insert.replace("\n", "\r\n"))
	if text.contains("func _ready() -> void:\n"):
		return text.replace("func _ready() -> void:\n", "func _ready() -> void:\n" + insert)
	return text


func _fix_spike(text: String) -> String:
	var re: RegEx = RegEx.new()
	if re.compile("var spike_ms:\\s*int\\s*=\\s*[1-9][0-9]*") != OK:
		return text
	return re.sub(text, "var spike_ms: int = 0", false)


func _spike_literal(text: String) -> int:
	var re: RegEx = RegEx.new()
	if re.compile("var spike_ms:\\s*int\\s*=\\s*([0-9]+)") != OK:
		return 0
	var m: RegExMatch = re.search(text)
	if m == null:
		return 0
	return int(m.get_string(1))


func _create_placeholder(res_path: String) -> bool:
	if not res_path.begins_with("res://") or res_path.contains(".."):
		return false
	if not res_path.begins_with("res://%s/" % HHAgentConstants.REPAIR_FIXTURE_DIR):
		return false
	var abs_p: String = ProjectSettings.globalize_path(res_path)
	DirAccess.make_dir_recursive_absolute(abs_p.get_base_dir())
	if res_path.ends_with(".png"):
		var img: Image = Image.create(8, 8, false, Image.FORMAT_RGBA8)
		img.fill(Color(0.9, 0.2, 0.2, 1.0))
		return img.save_png(res_path) == OK
	var f: FileAccess = FileAccess.open(res_path, FileAccess.WRITE)
	if f == null:
		return false
	f.store_string("ok")
	f.close()
	return true


func _write_gd(command_id: String, res_path: String, contents: String) -> Dictionary:
	var wrote: Dictionary = _scripts.handle(
		command_id,
		"godot.script",
		"write",
		{"path": res_path, "contents": contents},
		_actions,
		{},
	)
	if wrote.get("ok", false) == true:
		return wrote
	if not res_path.begins_with("res://%s/" % HHAgentConstants.REPAIR_FIXTURE_DIR):
		return wrote
	if _is_protected_path(res_path):
		return wrote
	var abs_p: String = ProjectSettings.globalize_path(res_path)
	DirAccess.make_dir_recursive_absolute(abs_p.get_base_dir())
	var tmp: String = abs_p + ".tmp"
	var f: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		return wrote
	f.store_string(contents)
	f.flush()
	f.close()
	if FileAccess.file_exists(abs_p):
		DirAccess.remove_absolute(abs_p)
	if DirAccess.rename_absolute(tmp, abs_p) != OK:
		return wrote
	if ResourceLoader.has_cached(res_path):
		var loaded: Resource = ResourceLoader.load(res_path, "", ResourceLoader.CACHE_MODE_REUSE)
		if loaded is GDScript:
			var gd: GDScript = loaded as GDScript
			gd.source_code = contents
			gd.reload()
	return _errors.ok_changed(command_id, _checks("script_disk_equals_write"), {"path": res_path, "fallback": true}, true)


func _save_scene(scene: String) -> void:
	if scene.is_empty():
		return
	_scenes.handle(str(_pending.get("command_id", "")), "godot.scene", "save", {"path": scene}, _actions, {})


func _read_text(res_path: String) -> String:
	if res_path.is_empty() or not FileAccess.file_exists(res_path):
		return ""
	return FileAccess.get_file_as_string(res_path)


func _variant(kind: String, value: Variant) -> Dictionary:
	return {"schema": VARIANT_SCHEMA, "type": kind, "value": value}


func _is_ident(text: String) -> bool:
	if text.is_empty():
		return false
	var i: int = 0
	while i < text.length():
		var ch: String = text.substr(i, 1)
		var ok: bool = (ch >= "A" and ch <= "Z") or (ch >= "a" and ch <= "z") or ch == "_"
		if i > 0:
			ok = ok or (ch >= "0" and ch <= "9")
		if not ok:
			return false
		i += 1
	return true


func _checks(post: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	out.append(post)
	return out
