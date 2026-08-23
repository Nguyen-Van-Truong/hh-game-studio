class_name HHAgentTestAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _PlayScript: GDScript = preload("res://addons/hh_agent/core/hh_play_adapter.gd")

## Test manifest / Play runner / evidence bundle. Drives existing
## play/runtime/input adapters. Never stamps pass without Play + files.
## Retry that fails then passes stays fail/flaky — never a silent pass.

const PENDING_KEY: String = "_hh_test_pending"
const CROCKFORD: String = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
const STATUS_PASS: String = "pass"
const STATUS_FAIL: String = "fail"
const STATUS_INFRA: String = "infra_error"

static var _current: HHAgentTestAdapter

var _errors: HHAgentErrors = HHAgentErrors.new()
var _actions: HHAgentActions = HHAgentActions.new()
var _pending: Dictionary = {}
var _last_by_name: Dictionary = {}


static func current() -> HHAgentTestAdapter:
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
	return (
		action == "define"
		or action == "run"
		or action == "assert"
		or action == "report"
		or action == "evidence"
		or action == "baseline"
	)


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	_precondition: Dictionary,
) -> Dictionary:
	if method != "godot.test" or not handles(action):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not a test verb", "")
	_actions = actions
	if action == "define":
		return _define(command_id, params)
	if action == "baseline":
		return _baseline(command_id, params)
	if action == "assert":
		return _assert_live(command_id, params)
	if action == "report":
		return _report(command_id, params)
	if action == "evidence":
		return _evidence(command_id, params)
	return _run_begin(command_id, params)


func poll_pending() -> Dictionary:
	if _pending.is_empty():
		return {}
	var command_id: String = str(_pending.get("command_id", ""))
	var now: int = Time.get_ticks_msec()
	if now > int(_pending.get("deadline_ms", 0)):
		return _finish_status(
			STATUS_FAIL,
			HHAgentErrors.E_TIMEOUT,
			"test.run timeout",
			"timeout",
		)
	var child: String = str(_pending.get("child", ""))
	if child == "play":
		var play: HHAgentPlayAdapter = HHAgentPlayAdapter.current()
		if play == null:
			return _finish_status(STATUS_INFRA, HHAgentErrors.E_UNVERIFIED, "play adapter gone", "infra")
		var play_r: Dictionary = play.poll_pending()
		if play_r.is_empty() or play_r.get("_hh_play_pending", false) == true:
			return {PENDING_KEY: true, "command_id": command_id}
		_pending["child"] = ""
		return _after_child(play_r)
	if child == "runtime":
		var runtime: HHAgentRuntimeAdapter = HHAgentRuntimeAdapter.current()
		if runtime == null:
			return _finish_status(STATUS_INFRA, HHAgentErrors.E_UNVERIFIED, "runtime adapter gone", "infra")
		if not EditorInterface.is_playing_scene() and str(_step_kind()) != "stop":
			_pending["child"] = ""
			return _after_child(
				_errors.fail(command_id, HHAgentErrors.E_CONFLICT, "Play stopped before runtime reply", "play")
			)
		var rt_r: Dictionary = runtime.poll_pending()
		if rt_r.is_empty() or rt_r.get("_hh_runtime_pending", false) == true:
			return {PENDING_KEY: true, "command_id": command_id}
		_pending["child"] = ""
		return _after_child(rt_r)
	return _kick()


func _define(command_id: String, params: Dictionary) -> Dictionary:
	var name_s: String = str(params.get("name", ""))
	if name_s.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "name required", "params.name")
	var dest: String = str(params.get("path", ""))
	if dest.is_empty():
		dest = "res://%s/%s.hh-test.json" % [HHAgentConstants.TEST_FIXTURE_DIR, name_s]
	var jail: Dictionary = _jail(command_id, dest)
	if jail.get("ok", false) != true:
		return jail
	var body: Dictionary = params.duplicate(true)
	body["schema"] = HHAgentConstants.TEST_SCHEMA
	body["name"] = name_s
	var wrote: Dictionary = _atomic_write_json(str(jail.get("abs", "")), body)
	if wrote.get("ok", false) != true:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			str(wrote.get("message", "could not persist test manifest")),
			dest,
		)
	var last: String = "res://%s/manifests/%s.hh-test.json" % [HHAgentConstants.TEST_DIR, name_s]
	var last_jail: Dictionary = _jail(command_id, last)
	if last_jail.get("ok", false) == true:
		_atomic_write_json(str(last_jail.get("abs", "")), body)
	return _errors.ok_changed(
		command_id,
		_checks("test_definition_saved"),
		{
			"name": name_s,
			"path": dest,
			"abs_path": str(jail.get("abs", "")),
			"test_definition_saved": true,
			"schema": HHAgentConstants.TEST_SCHEMA,
		},
		true,
	)


func _baseline(command_id: String, params: Dictionary) -> Dictionary:
	if params.get("reviewed", false) != true:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"baseline update requires explicit reviewed action",
			"params.reviewed",
		)
	var name_s: String = str(params.get("name", ""))
	var want_hash: String = str(params.get("hash", "")).to_lower()
	var src: String = str(params.get("path", ""))
	if src.is_empty():
		src = _last_screenshot_uri(name_s)
	if src.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "baseline source screenshot missing", "path")
	var src_jail: Dictionary = _jail_shot(command_id, src)
	if src_jail.get("ok", false) != true:
		return src_jail
	var abs_src: String = str(src_jail.get("abs", ""))
	if not FileAccess.file_exists(abs_src):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "baseline source file missing", src)
	var got_hash: String = FileAccess.get_sha256(abs_src).to_lower()
	if got_hash.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "could not hash baseline source", src)
	if want_hash.length() >= 8 and not got_hash.begins_with(want_hash) and want_hash != got_hash:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"baseline hash does not match the source file (refusing invented hash)",
			"params.hash",
		)
	var dest: String = "res://%s/baselines/%s.png" % [HHAgentConstants.TEST_FIXTURE_DIR, name_s]
	var dest_jail: Dictionary = _jail(command_id, dest)
	if dest_jail.get("ok", false) != true:
		return dest_jail
	if not _copy_file(abs_src, str(dest_jail.get("abs", ""))):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "could not copy reviewed baseline", dest)
	var rec: Dictionary = {
		"name": name_s,
		"hash": got_hash,
		"reviewed": true,
		"invented": false,
		"path": dest,
		"source": src,
	}
	_atomic_write_json(str(dest_jail.get("abs", "")).get_basename() + ".json", rec)
	return _errors.ok_changed(command_id, _checks("baseline_hash_saved"), rec, true)


func _assert_live(command_id: String, params: Dictionary) -> Dictionary:
	if not EditorInterface.is_playing_scene():
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"test.assert requires a proven Play process (R6)",
			"play",
		)
	var live: HHAgentRuntimeAdapter = HHAgentRuntimeAdapter.current()
	if live == null:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"test.assert requires Play runtime adapter",
			"runtime",
		)
	var payload: Dictionary = params.duplicate(true)
	if not payload.has("kind"):
		payload["kind"] = "property"
	if not payload.has("value_string") and payload.has("expect"):
		payload["value_string"] = str(payload.get("expect", ""))
	if not payload.has("op"):
		payload["op"] = "eq"
	return live.begin_query(command_id, "assert", payload, "assertion_recorded")


func _report(command_id: String, params: Dictionary) -> Dictionary:
	var loaded: Dictionary = _load_last(str(params.get("name", "")), str(params.get("path", "")))
	if loaded.get("ok", false) != true:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			str(loaded.get("message", "test report missing")),
			str(loaded.get("path", "")),
		)
	var report: Dictionary = loaded.get("report") if loaded.get("report") is Dictionary else {}
	if report.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "test report JSON empty", str(loaded.get("path", "")))
	var after: Dictionary = report.duplicate(true)
	after["report_path"] = str(loaded.get("path", ""))
	after["html_path"] = str(loaded.get("html", ""))
	return _errors.ok_read(command_id, _checks("test_report_present"), after)


func _evidence(command_id: String, params: Dictionary) -> Dictionary:
	var name_s: String = str(params.get("name", ""))
	var hours: int = int(params.get("retention_hours", 0))
	if hours > 0:
		_apply_retention(hours)
	var loaded: Dictionary = _load_last(name_s, "")
	if loaded.get("ok", false) != true:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			str(loaded.get("message", "evidence index missing")),
			name_s,
		)
	var index: Array = loaded.get("index") if loaded.get("index") is Array else []
	var op: String = str(params.get("op", "list"))
	if op == "get":
		var uri: String = str(params.get("uri", ""))
		var jail: Dictionary = _jail(command_id, uri)
		if jail.get("ok", false) != true:
			return jail
		var abs_p: String = str(jail.get("abs", ""))
		if not FileAccess.file_exists(abs_p):
			return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "artifact missing", uri)
		var bytes: PackedByteArray = FileAccess.get_file_as_bytes(abs_p)
		return _errors.ok_read(command_id, _checks("evidence_index_present"), {
			"name": name_s,
			"op": "get",
			"uri": uri,
			"bytes": bytes.size(),
			"hash": FileAccess.get_sha256(abs_p),
			"text": bytes.get_string_from_utf8() if uri.ends_with(".json") or uri.ends_with(".html") else "",
			"index": index,
		})
	return _errors.ok_read(command_id, _checks("evidence_index_present"), {
		"name": name_s,
		"op": "list",
		"index": index,
		"report_path": str(loaded.get("path", "")),
		"html_path": str(loaded.get("html", "")),
		"retention_hours": hours if hours > 0 else HHAgentConstants.TEST_RETENTION_HOURS,
	})


func _run_begin(command_id: String, params: Dictionary) -> Dictionary:
	if not _pending.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_BUSY, "test.run already in flight", "test")
	var name_s: String = str(params.get("name", ""))
	var loaded: Dictionary = _load_manifest(name_s)
	if loaded.get("ok", false) != true:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			str(loaded.get("message", "test definition missing")),
			name_s,
		)
	var manifest: Dictionary = loaded.get("manifest") if loaded.get("manifest") is Dictionary else {}
	if not _filter_allows(manifest, params):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "suite filter excluded this test", name_s)
	var scene: String = _scene_of(manifest)
	if scene.is_empty() and not EditorInterface.is_playing_scene():
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"test.run requires Play process or a setup/run scene",
			"play",
		)
	var retry_max: int = int(params.get("retry_max", manifest.get("retry_max", 0)))
	if retry_max < 0:
		retry_max = 0
	if retry_max > 3:
		retry_max = 3
	var timeout_ms: int = int(manifest.get("timeout_ms", HHAgentConstants.TEST_WAIT_MS))
	if timeout_ms < 100:
		timeout_ms = 100
	var token: String = _mint_ulid()
	_pending = {
		PENDING_KEY: true,
		"command_id": command_id,
		"name": name_s,
		"manifest": manifest,
		"params": params.duplicate(true),
		"attempt": 0,
		"retry_max": retry_max,
		"flaky_is_not_pass": manifest.get("flaky_is_not_pass", true) != false,
		"first_status": "",
		"first_reason": "",
		"token": token,
		"run_dir": "res://%s/runs/%s" % [HHAgentConstants.TEST_DIR, token],
		"deadline_ms": Time.get_ticks_msec() + timeout_ms,
		"child": "",
		"index": 0,
		"plan": [],
		"events": [],
		"step_results": [],
		"play_proven": false,
		"run_id": "",
		"last_after": {},
		"screenshot_uri": "",
		"perf_uri": "",
		"reason": "",
		"retention_hours": int(params.get("retention_hours", HHAgentConstants.TEST_RETENTION_HOURS)),
	}
	_pending["plan"] = _build_plan(manifest, scene)
	_note_event("run_begin", {"name": name_s, "scene": scene, "attempt": 0})
	return _kick()


func _kick() -> Dictionary:
	var command_id: String = str(_pending.get("command_id", ""))
	while true:
		var plan: Array = _pending.get("plan") if _pending.get("plan") is Array else []
		var index: int = int(_pending.get("index", 0))
		if index >= plan.size():
			return _finish_attempt(STATUS_PASS, "", "ok")
		var step_v: Variant = plan[index]
		if not (step_v is Dictionary):
			_pending["index"] = index + 1
			continue
		var step: Dictionary = step_v
		var started: Dictionary = _start_step(step)
		if started.get(PENDING_KEY, false) == true:
			return {PENDING_KEY: true, "ok": false, "command_id": command_id}
		if started.get("_hh_play_pending", false) == true:
			_pending["child"] = "play"
			return {PENDING_KEY: true, "ok": false, "command_id": command_id}
		if started.get("_hh_runtime_pending", false) == true:
			_pending["child"] = "runtime"
			return {PENDING_KEY: true, "ok": false, "command_id": command_id}
		var nxt: Dictionary = _on_step_result(step, started)
		if nxt.get("done", false) == true:
			return nxt.get("result") if nxt.get("result") is Dictionary else started
		_pending["index"] = index + 1
	return {PENDING_KEY: true, "ok": false, "command_id": command_id}


func _after_child(result: Dictionary) -> Dictionary:
	var plan: Array = _pending.get("plan") if _pending.get("plan") is Array else []
	var index: int = int(_pending.get("index", 0))
	var step: Dictionary = {}
	if index < plan.size() and plan[index] is Dictionary:
		step = plan[index]
	var nxt: Dictionary = _on_step_result(step, result)
	if nxt.get("done", false) == true:
		return nxt.get("result") if nxt.get("result") is Dictionary else result
	_pending["index"] = index + 1
	return _kick()


func _start_step(step: Dictionary) -> Dictionary:
	var command_id: String = str(_pending.get("command_id", ""))
	var kind: String = str(step.get("kind", ""))
	var play: HHAgentPlayAdapter = HHAgentPlayAdapter.current()
	var runtime: HHAgentRuntimeAdapter = HHAgentRuntimeAdapter.current()
	if kind == "stop":
		if play == null:
			return _errors.ok_changed(command_id, _checks("play_process_stopped"), {"playing": false}, true)
		return play.handle(command_id, "godot.play", "stop", {"reason": "test"}, _actions, {})
	if kind == "start":
		if play == null:
			return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "play adapter not attached", "play")
		if EditorInterface.is_playing_scene():
			var stopped: Dictionary = play.handle(command_id, "godot.play", "stop", {"reason": "test"}, _actions, {})
			if stopped.get("_hh_play_pending", false) == true:
				_pending["child"] = "play"
				_pending["restart_after_stop"] = true
				return stopped
		var scene: String = str(step.get("scene", ""))
		var mode: String = str(step.get("mode", "debug"))
		return play.handle(command_id, "godot.play", "start", {"scene": scene, "mode": mode}, _actions, {})
	if runtime == null:
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "runtime adapter not attached", "runtime")
	if not EditorInterface.is_playing_scene():
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "Play is not running", "play")
	var run_id: String = str(_pending.get("run_id", ""))
	if kind == "tree":
		return runtime.begin_query(command_id, "tree", {"run_id": run_id, "detail": "short"}, "remote_tree_snapshot")
	if kind == "freeze":
		return runtime.begin_time(
			command_id,
			"freeze",
			{"frozen": true, "reason": "test", "seed": 4242, "physics_ticks": 60, "frame": 0, "run_id": run_id},
			"runtime_frozen_matches",
		)
	if kind == "step":
		var step_params: Dictionary = {"frames": int(step.get("frames", 2)), "run_id": run_id}
		if step.has("until"):
			step_params["until"] = step.get("until")
		if step.has("timeout_ms"):
			step_params["timeout_ms"] = int(step.get("timeout_ms"))
		return runtime.begin_time(command_id, "step", step_params, "runtime_stepped_frames")
	if kind == "input":
		return runtime.begin_input(
			command_id,
			"action",
			{
				"action_name": str(step.get("action_name", "ui_accept")),
				"phase": str(step.get("phase", "press")),
				"run_id": run_id,
			},
			"input_action_injected",
		)
	if kind == "assert":
		var ap: Dictionary = step.duplicate(true)
		ap.erase("kind")
		ap["kind"] = str(step.get("assert_kind", step.get("kind", "property")))
		if ap.get("kind", "") == "assert":
			ap["kind"] = "property"
		ap["run_id"] = run_id
		return runtime.begin_query(command_id, "assert", ap, "assertion_recorded")
	if kind == "screenshot":
		var shot: Dictionary = {
			"scale": 1,
			"target": "game",
			"stable_frames": 2,
			"region_x": 40,
			"region_y": 40,
			"region_w": 256,
			"region_h": 256,
			"mask_x": 40,
			"mask_y": 40,
			"mask_w": 8,
			"mask_h": 8,
			"tolerance": 0.12,
			"run_id": run_id,
		}
		if step.get("compare", false) == true:
			shot["compare"] = true
			shot["baseline"] = str(step.get("baseline", "panel"))
		if step.get("update_baseline", false) == true:
			shot["update_baseline"] = true
			shot["reviewed"] = step.get("reviewed", false) == true
			shot["baseline"] = str(step.get("baseline", "panel"))
		return runtime.begin_capture(command_id, "screenshot", shot, "screenshot_artifact_present")
	if kind == "perf":
		var perf: Dictionary = {
			"detail": "short",
			"warmup_frames": 1 if step.get("inject_spike", false) == true else 4,
			"samples": 6 if step.get("inject_spike", false) == true else 8,
			"run_id": run_id,
		}
		if step.has("budget_ms"):
			perf["budget_ms"] = int(step.get("budget_ms"))
		if step.get("inject_spike", false) == true:
			perf["inject_spike"] = true
		return runtime.begin_capture(command_id, "perf", perf, "perf_counters_present")
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "unknown test step %s" % kind, "test")


func _on_step_result(step: Dictionary, result: Dictionary) -> Dictionary:
	if _pending.get("restart_after_stop", false) == true:
		_pending["restart_after_stop"] = false
		var scene: String = _scene_of(_pending.get("manifest") if _pending.get("manifest") is Dictionary else {})
		var mode: String = "debug"
		var man: Dictionary = _pending.get("manifest") if _pending.get("manifest") is Dictionary else {}
		if man.has("mode"):
			mode = str(man.get("mode"))
		var play: HHAgentPlayAdapter = HHAgentPlayAdapter.current()
		var command_id: String = str(_pending.get("command_id", ""))
		if play == null:
			return _done(_finish_status(STATUS_INFRA, HHAgentErrors.E_UNVERIFIED, "play adapter gone after stop", "infra"))
		var started: Dictionary = play.handle(
			command_id,
			"godot.play",
			"start",
			{"scene": scene, "mode": mode},
			_actions,
			{},
		)
		if started.get("_hh_play_pending", false) == true:
			_pending["child"] = "play"
			return {"done": false}
		return _on_step_result({"kind": "start", "scene": scene, "mode": mode}, started)
	var kind: String = str(step.get("kind", ""))
	var after: Dictionary = result.get("after") if result.get("after") is Dictionary else {}
	_pending["last_after"] = after
	_note_event("step", {"kind": kind, "ok": result.get("ok", false) == true})
	var steps_v: Variant = _pending.get("step_results", [])
	if steps_v is Array:
		(steps_v as Array).append({"kind": kind, "ok": result.get("ok", false) == true})
	if kind == "start":
		if result.get("ok", false) != true or after.get("playing", false) != true:
			return _done(_finish_status(
				STATUS_INFRA,
				_err_code(result, HHAgentErrors.E_UNVERIFIED),
				"Play did not start: %s" % _err_msg(result),
				"infra",
			))
		_pending["play_proven"] = true
		_pending["run_id"] = str(after.get("run_id", ""))
		return {"done": false}
	if kind == "stop":
		return {"done": false}
	if not EditorInterface.is_playing_scene() and kind != "stop":
		return _done(_finish_status(
			STATUS_INFRA,
			HHAgentErrors.E_CONFLICT,
			"Play process stopped unexpectedly (%s)" % _play_stop_reason(),
			"crash",
		))
	if kind == "tree":
		if result.get("ok", false) != true or str(after.get("source", "")) != "hh_agent_runtime":
			if _looks_like_crash():
				return _done(_finish_status(
					STATUS_INFRA,
					HHAgentErrors.E_CONFLICT,
					"Play crash/hang before runtime tree: %s" % _err_msg(result),
					"crash",
				))
			return _done(_finish_status(
				STATUS_INFRA,
				_err_code(result, HHAgentErrors.E_UNVERIFIED),
				"runtime.tree failed: %s" % _err_msg(result),
				"infra",
			))
		_pending["play_proven"] = true
		return {"done": false}
	if kind == "freeze":
		if result.get("ok", false) != true:
			return _done(_finish_status(
				STATUS_INFRA,
				_err_code(result, HHAgentErrors.E_UNVERIFIED),
				"runtime.freeze failed: %s" % _err_msg(result),
				"infra",
			))
		return {"done": false}
	if kind == "step":
		if _err_code(result, "") == HHAgentErrors.E_TIMEOUT or _err_msg(result).contains("missed event"):
			return _done(_finish_attempt(
				STATUS_FAIL,
				HHAgentErrors.E_TIMEOUT,
				"timeout",
			))
		if result.get("ok", false) != true:
			return _done(_finish_attempt(
				STATUS_FAIL,
				_err_code(result, HHAgentErrors.E_UNVERIFIED),
				"timeout" if _err_code(result, "") == HHAgentErrors.E_TIMEOUT else "logic",
			))
		return {"done": false}
	if kind == "input":
		if result.get("ok", false) != true:
			return _done(_finish_attempt(
				STATUS_FAIL,
				_err_code(result, HHAgentErrors.E_UNVERIFIED),
				"logic",
			))
		return {"done": false}
	if kind == "assert":
		if result.get("ok", false) != true or after.get("matched", false) != true:
			return _done(_finish_attempt(
				STATUS_FAIL,
				HHAgentErrors.E_UNVERIFIED,
				"logic",
			))
		if str(after.get("source", "")) != "hh_agent_runtime":
			return _done(_finish_status(
				STATUS_INFRA,
				HHAgentErrors.E_UNVERIFIED,
				"assert reply is not from hh_agent_runtime",
				"infra",
			))
		return {"done": false}
	if kind == "screenshot":
		var path_s: String = str(after.get("path", ""))
		if not path_s.is_empty():
			_pending["screenshot_uri"] = path_s
			_copy_into_run(path_s, "screenshot.png")
		if step.get("compare", false) == true:
			if result.get("ok", false) == true:
				return {"done": false}
			if _err_msg(result).contains("visual diff"):
				_copy_into_run(path_s, "visual_fail.png")
				return _done(_finish_attempt(
					STATUS_FAIL,
					HHAgentErrors.E_UNVERIFIED,
					"visual",
				))
			if _err_msg(result).contains("missing baseline"):
				return _done(_finish_attempt(
					STATUS_FAIL,
					HHAgentErrors.E_UNVERIFIED,
					"visual",
				))
			return _done(_finish_attempt(
				STATUS_FAIL,
				_err_code(result, HHAgentErrors.E_UNVERIFIED),
				"visual",
			))
		if step.get("update_baseline", false) == true and result.get("ok", false) != true:
			return _done(_finish_attempt(
				STATUS_FAIL,
				_err_code(result, HHAgentErrors.E_UNVERIFIED),
				"visual",
			))
		if result.get("ok", false) != true:
			_note_event("screenshot_alternative", {"message": _err_msg(result)})
		return {"done": false}
	if kind == "perf":
		_write_run_json("perf.json", after)
		_pending["perf_uri"] = "%s/perf.json" % str(_pending.get("run_dir", ""))
		if step.get("inject_spike", false) == true:
			if result.get("ok", false) == true:
				return _done(_finish_attempt(
					STATUS_FAIL,
					HHAgentErrors.E_UNVERIFIED,
					"perf",
				))
			if _err_msg(result).to_lower().contains("perf regression"):
				return _done(_finish_attempt(
					STATUS_FAIL,
					HHAgentErrors.E_UNVERIFIED,
					"perf",
				))
			return _done(_finish_attempt(
				STATUS_FAIL,
				_err_code(result, HHAgentErrors.E_UNVERIFIED),
				"perf",
			))
		if result.get("ok", false) != true:
			_note_event("perf_alternative", {"message": _err_msg(result)})
		return {"done": false}
	return {"done": false}


func _finish_attempt(status: String, code: String, reason: String) -> Dictionary:
	var attempt: int = int(_pending.get("attempt", 0))
	var retry_max: int = int(_pending.get("retry_max", 0))
	var first: String = str(_pending.get("first_status", ""))
	if status == STATUS_PASS and first == STATUS_FAIL:
		_pending["flaky"] = true
		return _finish_status(
			STATUS_FAIL,
			HHAgentErrors.E_UNVERIFIED,
			"flaky; retry must not become pass",
			"flaky",
		)
	if (
		status == STATUS_FAIL
		and reason != "timeout"
		and reason != "flaky"
		and attempt < retry_max
		and _pending.get("flaky_is_not_pass", true) != false
	):
		_pending["first_status"] = STATUS_FAIL
		_pending["first_reason"] = reason
		_pending["attempt"] = attempt + 1
		_pending["index"] = 0
		_pending["child"] = ""
		_note_event("retry", {"attempt": attempt + 1, "first_reason": reason})
		var manifest: Dictionary = _pending.get("manifest") if _pending.get("manifest") is Dictionary else {}
		_pending["plan"] = _build_plan(manifest, _scene_of(manifest))
		return _kick()
	var message: String = "test %s" % reason
	if reason == "logic":
		message = "state assertion failed"
	elif reason == "visual":
		message = "visual diff failed"
	elif reason == "perf":
		message = "perf regression"
	elif reason == "timeout":
		message = "step-until missed event: predicate never matched"
	if code.is_empty():
		code = HHAgentErrors.E_TIMEOUT if reason == "timeout" else HHAgentErrors.E_UNVERIFIED
	return _finish_status(status, code, message, reason)


func _finish_status(status: String, code: String, message: String, reason: String) -> Dictionary:
	var command_id: String = str(_pending.get("command_id", ""))
	var name_s: String = str(_pending.get("name", ""))
	_pending["reason"] = reason
	if status == STATUS_PASS and _pending.get("flaky", false) == true:
		status = STATUS_FAIL
		message = "flaky; retry must not become pass"
		reason = "flaky"
		code = HHAgentErrors.E_UNVERIFIED
	if status == STATUS_PASS and _pending.get("play_proven", false) != true:
		status = STATUS_INFRA
		message = "refusing pass without proven Play"
		reason = "infra"
		code = HHAgentErrors.E_UNVERIFIED
	_ensure_stopped()
	var bundle: Dictionary = _write_bundle(status, reason, message)
	var after: Dictionary = bundle.duplicate(true)
	after["name"] = name_s
	after["status"] = status
	after["reason"] = reason
	after["flaky"] = _pending.get("flaky", false) == true or reason == "flaky"
	after["play_proven"] = _pending.get("play_proven", false) == true
	after["run_id"] = str(_pending.get("run_id", ""))
	after["attempt"] = int(_pending.get("attempt", 0)) + 1
	after["retry_max"] = int(_pending.get("retry_max", 0))
	_last_by_name[name_s] = after.duplicate(true)
	_pending = {}
	if status == STATUS_PASS:
		return _errors.ok_changed(command_id, _checks("test_run_recorded"), after, true)
	return _errors.fail_after(command_id, code, message, "test", after)


func _write_bundle(status: String, reason: String, message: String) -> Dictionary:
	var run_res: String = str(_pending.get("run_dir", "res://%s/runs/unknown" % HHAgentConstants.TEST_DIR))
	var jail: Dictionary = _jail(str(_pending.get("command_id", "")), "%s/report.json" % run_res)
	if jail.get("ok", false) != true:
		return {"report_path": "", "html_path": "", "evidence_index": [], "hashes": {}, "invented_hashes": false}
	var run_abs: String = str(jail.get("abs", "")).get_base_dir()
	DirAccess.make_dir_recursive_absolute(run_abs)
	var hashes: Dictionary = _compute_hashes()
	var logs: Array = _copy_logs()
	var state: Dictionary = _pending.get("last_after") if _pending.get("last_after") is Dictionary else {}
	var events: Array = _pending.get("events") if _pending.get("events") is Array else []
	_atomic_write_json("%s/hashes.json" % run_abs, hashes)
	_atomic_write_json("%s/logs.json" % run_abs, {"items": logs, "stop_reason": _play_stop_reason()})
	_atomic_write_json("%s/state.json" % run_abs, state)
	_atomic_write_json("%s/events.json" % run_abs, {"items": events})
	var index: Array = []
	_index_add(index, "%s/hashes.json" % run_res, "hashes", "%s/hashes.json" % run_abs)
	_index_add(index, "%s/logs.json" % run_res, "logs", "%s/logs.json" % run_abs)
	_index_add(index, "%s/state.json" % run_res, "state", "%s/state.json" % run_abs)
	_index_add(index, "%s/events.json" % run_res, "event", "%s/events.json" % run_abs)
	var shot: String = str(_pending.get("screenshot_uri", ""))
	if not shot.is_empty():
		_copy_into_run(shot, "screenshot.png")
	var copied_shot: String = "%s/screenshot.png" % run_abs
	if FileAccess.file_exists(copied_shot):
		_index_add(index, "%s/screenshot.png" % run_res, "screenshot", copied_shot)
	var fail_shot: String = "%s/visual_fail.png" % run_abs
	if FileAccess.file_exists(fail_shot):
		_index_add(index, "%s/visual_fail.png" % run_res, "diff", fail_shot)
	var perf_abs: String = "%s/perf.json" % run_abs
	if FileAccess.file_exists(perf_abs):
		_index_add(index, "%s/perf.json" % run_res, "perf", perf_abs)
	var report: Dictionary = {
		"schema": HHAgentConstants.TEST_SCHEMA,
		"name": str(_pending.get("name", "")),
		"status": status,
		"reason": reason,
		"message": message,
		"flaky": _pending.get("flaky", false) == true or reason == "flaky",
		"play_proven": _pending.get("play_proven", false) == true,
		"run_id": str(_pending.get("run_id", "")),
		"attempt": int(_pending.get("attempt", 0)) + 1,
		"retry_max": int(_pending.get("retry_max", 0)),
		"hashes": hashes,
		"invented_hashes": false,
		"engine": str(hashes.get("engine", "")),
		"evidence_index": index,
		"report_path": "%s/report.json" % run_res,
		"html_path": "%s/report.html" % run_res,
	}
	_atomic_write_json("%s/report.json" % run_abs, report)
	_atomic_write_text("%s/report.html" % run_abs, _html_report(report, index))
	_index_add(index, "%s/report.json" % run_res, "report", "%s/report.json" % run_abs)
	_index_add(index, "%s/report.html" % run_res, "html", "%s/report.html" % run_abs)
	_atomic_write_json("%s/evidence.json" % run_abs, {"index": index})
	_index_add(index, "%s/evidence.json" % run_res, "evidence", "%s/evidence.json" % run_abs)
	report["evidence_index"] = index
	_atomic_write_json("%s/report.json" % run_abs, report)
	var last_res: String = "res://%s/last/%s.json" % [HHAgentConstants.TEST_DIR, str(_pending.get("name", ""))]
	var last_jail: Dictionary = _jail(str(_pending.get("command_id", "")), last_res)
	if last_jail.get("ok", false) == true:
		_atomic_write_json(str(last_jail.get("abs", "")), {
			"report_path": "%s/report.json" % run_res,
			"html_path": "%s/report.html" % run_res,
			"evidence_path": "%s/evidence.json" % run_res,
			"status": status,
			"name": str(_pending.get("name", "")),
		})
	_apply_retention(int(_pending.get("retention_hours", HHAgentConstants.TEST_RETENTION_HOURS)))
	return report


func _html_report(report: Dictionary, index: Array) -> String:
	var lines: PackedStringArray = PackedStringArray()
	var name_s: String = _esc(str(report.get("name", "")))
	var status: String = _esc(str(report.get("status", "")))
	lines.append("<!DOCTYPE html><html><head><meta charset=\"utf-8\"><title>HH test %s</title></head><body>" % name_s)
	lines.append("<h1>status=%s reason=%s</h1>" % [status, _esc(str(report.get("reason", "")))])
	lines.append("<p>play_proven=%s flaky=%s run_id=%s</p>" % [
		_esc(str(report.get("play_proven", false))),
		_esc(str(report.get("flaky", false))),
		_esc(str(report.get("run_id", ""))),
	])
	if index.is_empty():
		lines.append("<p>NO_FILE_URIS — do not treat this page as a pass.</p>")
	else:
		lines.append("<h2>evidence file URIs</h2><ul>")
		var i: int = 0
		while i < index.size():
			var item_v: Variant = index[i]
			i += 1
			if not (item_v is Dictionary):
				continue
			var item: Dictionary = item_v
			var uri: String = _esc(str(item.get("uri", "")))
			lines.append("<li><a href=\"%s\">%s</a> kind=%s bytes=%s hash=%s</li>" % [
				uri,
				uri,
				_esc(str(item.get("kind", ""))),
				_esc(str(item.get("bytes", 0))),
				_esc(str(item.get("hash", ""))),
			])
		lines.append("</ul>")
	lines.append("</body></html>")
	return "\n".join(lines)


func _build_plan(manifest: Dictionary, scene: String) -> Array:
	var plan: Array = []
	var mode: String = str(manifest.get("mode", "debug"))
	if scene.is_empty():
		scene = _scene_of(manifest)
	plan.append({"kind": "start", "scene": scene, "mode": mode})
	plan.append({"kind": "tree"})
	plan.append({"kind": "freeze"})
	var step: Dictionary = {"kind": "step", "frames": maxi(1, int(manifest.get("step_frames", 2)))}
	if manifest.has("until_key"):
		var until: Dictionary = {
			"key": str(manifest.get("until_key")),
			"op": str(manifest.get("until_op", "eq")),
		}
		if manifest.has("until_value_bool"):
			until["value_bool"] = manifest.get("until_value_bool") == true
		if manifest.has("until_value_int"):
			until["value_int"] = int(manifest.get("until_value_int"))
		if manifest.has("until_value_string"):
			until["value_string"] = str(manifest.get("until_value_string"))
		if manifest.has("assert_node_path"):
			until["node_path"] = str(manifest.get("assert_node_path"))
		step["until"] = until
		step["timeout_ms"] = int(manifest.get("step_timeout_ms", 2000))
	plan.append(step)
	if manifest.has("input_action"):
		plan.append({
			"kind": "input",
			"action_name": str(manifest.get("input_action")),
			"phase": str(manifest.get("input_phase", "press")),
		})
	if manifest.has("assert_kind") or manifest.has("assert_key"):
		var a: Dictionary = {
			"kind": "assert",
			"assert_kind": str(manifest.get("assert_kind", "property")),
			"node_path": str(manifest.get("assert_node_path", "Fixture")),
			"key": str(manifest.get("assert_key", "")),
			"op": str(manifest.get("assert_op", "eq")),
		}
		if manifest.has("assert_value_string"):
			a["value_string"] = str(manifest.get("assert_value_string"))
		if manifest.has("assert_value_int"):
			a["value_int"] = int(manifest.get("assert_value_int"))
		if manifest.has("assert_value_bool"):
			a["value_bool"] = manifest.get("assert_value_bool") == true
		if manifest.has("assert_signal"):
			a["signal"] = str(manifest.get("assert_signal"))
		plan.append(a)
	if (
		manifest.get("visual_compare", false) == true
		or manifest.get("visual_update_baseline", false) == true
	):
		plan.append({
			"kind": "screenshot",
			"compare": manifest.get("visual_compare", false) == true,
			"update_baseline": manifest.get("visual_update_baseline", false) == true,
			"reviewed": manifest.get("visual_reviewed", false) == true,
			"baseline": str(manifest.get("visual_baseline", "panel")),
		})
	elif true:
		plan.append({"kind": "screenshot", "compare": false})
	if manifest.has("perf_budget_ms") or manifest.get("perf_inject_spike", false) == true:
		var perf: Dictionary = {"kind": "perf", "inject_spike": manifest.get("perf_inject_spike", false) == true}
		if manifest.has("perf_budget_ms"):
			perf["budget_ms"] = int(manifest.get("perf_budget_ms"))
		plan.append(perf)
	if manifest.get("teardown_stop", true) != false:
		plan.append({"kind": "stop"})
	return plan


func _scene_of(manifest: Dictionary) -> String:
	var scene: String = str(manifest.get("scene", ""))
	if not scene.is_empty():
		return scene
	return ""


func _filter_allows(manifest: Dictionary, params: Dictionary) -> bool:
	var name_s: String = str(manifest.get("name", ""))
	var filter_v: Variant = params.get("filter", manifest.get("filter", []))
	if filter_v is Array and not (filter_v as Array).is_empty():
		if not (filter_v as Array).has(name_s):
			return false
	var suite: String = str(params.get("suite", ""))
	if not suite.is_empty() and str(manifest.get("suite", "")) != suite:
		return false
	return true


func _load_manifest(name_s: String) -> Dictionary:
	var candidates: PackedStringArray = PackedStringArray()
	candidates.append("res://%s/%s.hh-test.json" % [HHAgentConstants.TEST_FIXTURE_DIR, name_s])
	candidates.append("res://%s/manifests/%s.hh-test.json" % [HHAgentConstants.TEST_DIR, name_s])
	candidates.append("res://%s/%s.hh-test.json" % [HHAgentConstants.REPAIR_FIXTURE_DIR, name_s])
	candidates.append("res://%s/%s/%s.hh-test.json" % [HHAgentConstants.REPAIR_FIXTURE_DIR, name_s, name_s])
	candidates.append("res://.hh-test.json")
	var i: int = 0
	while i < candidates.size():
		var path_s: String = candidates[i]
		i += 1
		if not FileAccess.file_exists(path_s):
			continue
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path_s))
		if parsed is Dictionary and str((parsed as Dictionary).get("name", "")) == name_s:
			return {"ok": true, "manifest": parsed, "path": path_s}
		if parsed is Dictionary and path_s.ends_with(".hh-test.json") and str((parsed as Dictionary).get("name", "")).is_empty():
			var body: Dictionary = parsed
			body["name"] = name_s
			return {"ok": true, "manifest": body, "path": path_s}
	return {"ok": false, "message": "test definition missing for %s" % name_s}


func _load_last(name_s: String, path_s: String) -> Dictionary:
	var report_res: String = path_s
	if report_res.is_empty():
		var mem_v: Variant = _last_by_name.get(name_s, {})
		if mem_v is Dictionary and str((mem_v as Dictionary).get("report_path", "")) != "":
			report_res = str((mem_v as Dictionary).get("report_path", ""))
		else:
			var ptr: String = "res://%s/last/%s.json" % [HHAgentConstants.TEST_DIR, name_s]
			if FileAccess.file_exists(ptr):
				var ptr_v: Variant = JSON.parse_string(FileAccess.get_file_as_string(ptr))
				if ptr_v is Dictionary:
					report_res = str((ptr_v as Dictionary).get("report_path", ""))
	if report_res.is_empty() or not FileAccess.file_exists(report_res):
		return {"ok": false, "message": "last test report missing", "path": report_res}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(report_res))
	if not (parsed is Dictionary):
		return {"ok": false, "message": "report JSON unreadable", "path": report_res}
	var report: Dictionary = parsed
	var html: String = str(report.get("html_path", report_res.replace("report.json", "report.html")))
	var index: Array = report.get("evidence_index") if report.get("evidence_index") is Array else []
	var ev: String = report_res.replace("report.json", "evidence.json")
	if FileAccess.file_exists(ev):
		var ev_v: Variant = JSON.parse_string(FileAccess.get_file_as_string(ev))
		if ev_v is Dictionary and (ev_v as Dictionary).get("index") is Array:
			index = (ev_v as Dictionary).get("index")
	return {"ok": true, "report": report, "path": report_res, "html": html, "index": index}


func _compute_hashes() -> Dictionary:
	var project_abs: String = ProjectSettings.globalize_path("res://project.godot")
	var project_hash: String = ""
	if FileAccess.file_exists(project_abs):
		project_hash = FileAccess.get_sha256(project_abs)
	var engine: String = _godot_string()
	var tools: Dictionary = {}
	_hash_tool(tools, "hh_agent_runtime.gd", "res://addons/hh_agent/runtime/hh_agent_runtime.gd")
	_hash_tool(tools, "hh_test_adapter.gd", "res://addons/hh_agent/core/hh_test_adapter.gd")
	_hash_tool(tools, "hh_play_adapter.gd", "res://addons/hh_agent/core/hh_play_adapter.gd")
	return {
		"project_hash": project_hash,
		"project_hash_files": ["res://project.godot"],
		"project_hash_source": "sha256" if not project_hash.is_empty() else "unproven",
		"commit": _git_head(),
		"engine": engine,
		"tool_hashes": tools,
		"invented": false,
	}


func _hash_tool(out: Dictionary, key: String, res_path: String) -> void:
	var abs_p: String = ProjectSettings.globalize_path(res_path)
	if FileAccess.file_exists(abs_p):
		var digest: String = FileAccess.get_sha256(abs_p)
		if digest.is_empty():
			out[key] = {"status": "unproven"}
		else:
			out[key] = digest
	else:
		out[key] = {"status": "unproven"}


func _git_head() -> Dictionary:
	var root: String = _find_git(ProjectSettings.globalize_path("res://"))
	if root.is_empty():
		return {"value": "", "source": "unproven"}
	var out: Array = []
	var code: int = OS.execute("git", PackedStringArray(["-C", root, "rev-parse", "HEAD"]), out, true, false)
	if code != 0 or out.is_empty():
		return {"value": "", "source": "unproven"}
	var head: String = str(out[0]).strip_edges()
	if head.length() < 7:
		return {"value": "", "source": "unproven"}
	return {"value": head, "source": "git"}


func _find_git(start: String) -> String:
	var cur: String = start.replace("\\", "/").rstrip("/")
	var i: int = 0
	while i < 8 and not cur.is_empty():
		if DirAccess.dir_exists_absolute("%s/.git" % cur) or FileAccess.file_exists("%s/.git" % cur):
			return cur
		var slash: int = cur.rfind("/")
		if slash <= 2:
			break
		cur = cur.substr(0, slash)
		i += 1
	return ""


func _godot_string() -> String:
	var info: Dictionary = Engine.get_version_info()
	var hash_s: String = str(info.get("hash", ""))
	if hash_s.length() > 9:
		hash_s = hash_s.substr(0, 9)
	return "%s.%s.%s.%s.%s.%s" % [
		str(info.get("major", 0)),
		str(info.get("minor", 0)),
		str(info.get("patch", 0)),
		str(info.get("status", "")),
		str(info.get("build", "")),
		hash_s,
	]


func _copy_logs() -> Array:
	var play: HHAgentPlayAdapter = HHAgentPlayAdapter.current()
	if play == null:
		return []
	return play.snapshot_logs()


func _looks_like_crash() -> bool:
	var reason: String = _play_stop_reason()
	if reason == "crash" or reason == "hang" or reason == "error":
		return true
	if not EditorInterface.is_playing_scene():
		return true
	var logs: Array = _copy_logs()
	var i: int = 0
	while i < logs.size():
		var item_v: Variant = logs[i]
		i += 1
		if not (item_v is Dictionary):
			continue
		var msg: String = str((item_v as Dictionary).get("message", "")).to_lower()
		if msg.contains("hh_r6w6_crash") or msg.contains("get_path") or msg.contains("crash"):
			return true
	return false


func _play_stop_reason() -> String:
	var play: HHAgentPlayAdapter = HHAgentPlayAdapter.current()
	if play == null:
		return ""
	return play.last_stop_reason()


func _ensure_stopped() -> void:
	if EditorInterface.is_playing_scene():
		EditorInterface.stop_playing_scene()


func _copy_into_run(src_res: String, dest_name: String) -> void:
	if src_res.is_empty():
		return
	var src_abs: String = ProjectSettings.globalize_path(src_res)
	if not FileAccess.file_exists(src_abs):
		return
	var run_res: String = str(_pending.get("run_dir", ""))
	if run_res.is_empty():
		return
	var dest_abs: String = ProjectSettings.globalize_path("%s/%s" % [run_res, dest_name])
	_copy_file(src_abs, dest_abs)


func _write_run_json(name_s: String, body: Dictionary) -> void:
	var run_res: String = str(_pending.get("run_dir", ""))
	if run_res.is_empty():
		return
	var dest: String = ProjectSettings.globalize_path("%s/%s" % [run_res, name_s])
	_atomic_write_json(dest, body)


func _index_add(index: Array, uri: String, kind: String, abs_p: String) -> void:
	var bytes: int = 0
	var digest: String = ""
	if FileAccess.file_exists(abs_p):
		bytes = FileAccess.get_file_as_bytes(abs_p).size()
		digest = FileAccess.get_sha256(abs_p)
	index.append({"uri": uri, "kind": kind, "bytes": bytes, "hash": digest})


func _last_screenshot_uri(name_s: String) -> String:
	var mem_v: Variant = _last_by_name.get(name_s, {})
	if mem_v is Dictionary:
		var idx_v: Variant = (mem_v as Dictionary).get("evidence_index", [])
		if idx_v is Array:
			var i: int = (idx_v as Array).size() - 1
			while i >= 0:
				var item_v: Variant = (idx_v as Array)[i]
				i -= 1
				if item_v is Dictionary and str((item_v as Dictionary).get("kind", "")) == "screenshot":
					return str((item_v as Dictionary).get("uri", ""))
	return ""


func _apply_retention(hours: int) -> void:
	if hours < 1:
		return
	var root: String = ProjectSettings.globalize_path("res://%s/runs" % HHAgentConstants.TEST_DIR)
	if not DirAccess.dir_exists_absolute(root):
		return
	var cutoff: int = int(Time.get_unix_time_from_system()) - hours * 3600
	var da: DirAccess = DirAccess.open(root)
	if da == null:
		return
	da.list_dir_begin()
	var name_s: String = da.get_next()
	while name_s != "":
		if da.current_is_dir() and not name_s.begins_with("."):
			var child: String = "%s/%s" % [root, name_s]
			var stamp: int = int(FileAccess.get_modified_time(child))
			if stamp > 0 and stamp < cutoff:
				_rm_tree(child)
		name_s = da.get_next()
	da.list_dir_end()


func _rm_tree(abs_dir: String) -> void:
	var da: DirAccess = DirAccess.open(abs_dir)
	if da == null:
		return
	da.list_dir_begin()
	var name_s: String = da.get_next()
	while name_s != "":
		if name_s != "." and name_s != "..":
			var child: String = "%s/%s" % [abs_dir, name_s]
			if da.current_is_dir():
				_rm_tree(child)
			else:
				DirAccess.remove_absolute(child)
		name_s = da.get_next()
	da.list_dir_end()
	DirAccess.remove_absolute(abs_dir)


func _jail(command_id: String, res_path: String) -> Dictionary:
	var p: String = res_path.strip_edges().replace("\\", "/")
	if not p.begins_with("res://"):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "path must be res://", p)
	if p.contains(".."):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "path escapes via ..", p)
	var rest: String = p.substr(6)
	var allowed: bool = (
		rest == ".hh-test.json"
		or rest.begins_with("r6w6/")
		or rest == "r6w6"
		or rest.begins_with(".hh-agent/r6w6/")
		or rest == ".hh-agent/r6w6"
		or rest.begins_with("r6w7/")
		or rest == "r6w7"
		or rest.begins_with(".hh-agent/r6w7/")
		or rest == ".hh-agent/r6w7"
	)
	if not allowed:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_PATH,
			"test artifacts must stay under r6w6/ or r6w7/ or .hh-agent/r6w6|r6w7/",
			p,
		)
	var abs_path: String = ProjectSettings.globalize_path(p)
	var root: String = ProjectSettings.globalize_path("res://").replace("\\", "/")
	if not abs_path.replace("\\", "/").begins_with(root):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "path is outside project root", p)
	return {"ok": true, "res": p, "abs": abs_path}


func _jail_shot(command_id: String, res_path: String) -> Dictionary:
	var p: String = res_path.strip_edges().replace("\\", "/")
	if not p.begins_with("res://"):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "path must be res://", p)
	if p.contains(".."):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "path escapes via ..", p)
	var rest: String = p.substr(6)
	if not (
		rest.begins_with(".hh-agent/")
		or rest.begins_with("r6w5/")
		or rest.begins_with("r6w6/")
		or rest.begins_with("r6w7/")
	):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "screenshot is outside project artifacts", p)
	return {"ok": true, "res": p, "abs": ProjectSettings.globalize_path(p)}


func _atomic_write_json(abs_path: String, body: Dictionary) -> Dictionary:
	return _atomic_write_text(abs_path, JSON.stringify(body, "\t"))


func _atomic_write_text(abs_path: String, text: String) -> Dictionary:
	var dir_s: String = abs_path.get_base_dir()
	DirAccess.make_dir_recursive_absolute(dir_s)
	var tmp: String = abs_path + ".tmp"
	var f: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		return {"ok": false, "message": "could not open tmp"}
	f.store_string(text)
	f.flush()
	f.close()
	if FileAccess.file_exists(abs_path):
		DirAccess.remove_absolute(abs_path)
	if DirAccess.rename_absolute(tmp, abs_path) != OK:
		return {"ok": false, "message": "atomic rename failed"}
	return {"ok": true}


func _copy_file(src_abs: String, dest_abs: String) -> bool:
	if not FileAccess.file_exists(src_abs):
		return false
	var bytes: PackedByteArray = FileAccess.get_file_as_bytes(src_abs)
	if bytes.is_empty():
		return false
	DirAccess.make_dir_recursive_absolute(dest_abs.get_base_dir())
	var tmp: String = dest_abs + ".tmp"
	var f: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		return false
	f.store_buffer(bytes)
	f.flush()
	f.close()
	if FileAccess.file_exists(dest_abs):
		DirAccess.remove_absolute(dest_abs)
	return DirAccess.rename_absolute(tmp, dest_abs) == OK


func _note_event(kind: String, extra: Dictionary) -> void:
	var events_v: Variant = _pending.get("events", [])
	if not (events_v is Array):
		return
	var row: Dictionary = extra.duplicate(true)
	row["kind"] = kind
	row["ms"] = Time.get_ticks_msec()
	(events_v as Array).append(row)


func _step_kind() -> String:
	var plan: Array = _pending.get("plan") if _pending.get("plan") is Array else []
	var index: int = int(_pending.get("index", 0))
	if index < 0 or index >= plan.size():
		return ""
	var step_v: Variant = plan[index]
	if step_v is Dictionary:
		return str((step_v as Dictionary).get("kind", ""))
	return ""


func _done(result: Dictionary) -> Dictionary:
	return {"done": true, "result": result}


func _err_code(result: Dictionary, fallback: String) -> String:
	var err_v: Variant = result.get("error", {})
	if err_v is Dictionary:
		var code: String = str((err_v as Dictionary).get("code", ""))
		if not code.is_empty():
			return code
	return fallback


func _err_msg(result: Dictionary) -> String:
	var err_v: Variant = result.get("error", {})
	if err_v is Dictionary:
		return str((err_v as Dictionary).get("message", ""))
	return ""


func _esc(raw: String) -> String:
	return raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")


func _mint_ulid() -> String:
	var now_ms: int = int(Time.get_unix_time_from_system() * 1000.0)
	var chars: PackedStringArray = PackedStringArray()
	var t: int = now_ms
	var i: int = 0
	while i < 10:
		chars.append(CROCKFORD.substr(t % 32, 1))
		t = int(t / 32)
		i += 1
	var time_part: String = ""
	var r: int = chars.size() - 1
	while r >= 0:
		time_part += chars[r]
		r -= 1
	var rand_part: String = ""
	i = 0
	while i < 16:
		rand_part += CROCKFORD.substr(randi() % 32, 1)
		i += 1
	return time_part + rand_part


func _checks(post: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	out.append(post)
	return out
