class_name HHAgentRuntimeAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _PlayScript: GDScript = preload("res://addons/hh_agent/core/hh_play_adapter.gd")

## Editor-side runtime reads. Debugger-channel paging only. Never walk
## the edited scene root as the game tree. remote_tree=true only after a
## Play-proven debugger reply.

const PENDING_KEY: String = "_hh_runtime_pending"
const CROCKFORD: String = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

static var _current: HHAgentRuntimeAdapter

var _errors: HHAgentErrors = HHAgentErrors.new()
var _pending: Dictionary = {}
var _last_send_ms: int = 0


static func current() -> HHAgentRuntimeAdapter:
	return _current


func attach() -> void:
	_current = self


func detach() -> void:
	if _current == self:
		_current = null
	_pending = {}


func shutdown() -> void:
	_pending = {}
	detach()


func begin_query(
	command_id: String,
	action: String,
	params: Dictionary,
	post: String,
) -> Dictionary:
	if (
		action != "tree"
		and action != "node"
		and action != "state"
		and action != "time"
		and action != "assert"
	):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"runtime observation requires Play process (R6)",
			"",
		)
	if not EditorInterface.is_playing_scene():
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"runtime observation requires Play process (R6)",
			"play",
		)
	var play: HHAgentPlayAdapter = HHAgentPlayAdapter.current()
	if play == null:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"runtime observation requires Play process (R6)",
			"play",
		)
	var stale: Dictionary = play.stale_run_reject(command_id, params)
	if not stale.is_empty():
		return stale
	var run_id: String = play.current_run_id()
	if run_id.is_empty():
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"runtime query missing Play run_id",
			"run_id",
		)
	var now: int = Time.get_ticks_msec()
	if _last_send_ms > 0 and now - _last_send_ms < HHAgentConstants.RUNTIME_RATE_MIN_MS:
		return _errors.fail(command_id, HHAgentErrors.E_BUSY, "runtime query rate limited", "runtime")
	var dbg: HHAgentRuntimeDebugger = HHAgentRuntimeDebugger.current()
	if dbg == null:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"runtime debugger plugin is not registered",
			"runtime",
		)
	var token: String = _mint_token()
	var limit: int = _limit_of(params)
	var offset: int = _offset_of(params)
	var payload: Dictionary = {
		"op": action,
		"token": token,
		"run_id": run_id,
		"detail": str(params.get("detail", "short")),
		"limit": limit,
		"offset": offset,
		"cursor": str(params.get("cursor", "")),
		"node_path": str(params.get("node_path", ".")),
		"key": str(params.get("key", "")),
		"kind": str(params.get("kind", "")),
		"compare_op": str(params.get("op", "")),
		"signal": str(params.get("signal", "")),
	}
	if params.has("value_int"):
		payload["value_int"] = int(params.get("value_int"))
	if params.has("value_bool"):
		payload["value_bool"] = params.get("value_bool") == true
	if params.has("value_string"):
		payload["value_string"] = str(params.get("value_string", ""))
	_pending = {
		PENDING_KEY: true,
		"command_id": command_id,
		"post": post,
		"action": action,
		"token": token,
		"run_id": run_id,
		"payload": payload,
		"sent": false,
		"sends": 0,
		"sent_ms": 0,
		"deadline_ms": now + HHAgentConstants.RUNTIME_QUERY_WAIT_MS,
	}
	_try_send()
	return {PENDING_KEY: true, "ok": false, "command_id": command_id}


func begin_input(
	command_id: String,
	action: String,
	params: Dictionary,
	post: String,
) -> Dictionary:
	if (
		action != "action"
		and action != "key"
		and action != "mouse"
		and action != "touch"
		and action != "sequence"
		and action != "release_all"
	):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"not a proven Play input verb",
			"",
		)
	if not EditorInterface.is_playing_scene():
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"play.input requires a proven Play process (is_playing_scene)",
			"play",
		)
	var play: HHAgentPlayAdapter = HHAgentPlayAdapter.current()
	if play == null:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"play.input requires a proven Play process (R6)",
			"play",
		)
	var stale: Dictionary = play.stale_run_reject(command_id, params)
	if not stale.is_empty():
		return stale
	var run_id: String = play.current_run_id()
	if run_id.is_empty():
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"play.input missing Play run_id bind",
			"run_id",
		)
	if not _pending.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_BUSY, "runtime/input channel busy", "input")
	var replay_fail: Dictionary = _replay_header_fail(command_id, params, run_id)
	if not replay_fail.is_empty():
		return replay_fail
	if params.get("editor_foreground", false) == true:
		DisplayServer.window_move_to_foreground()
	var token: String = _mint_token()
	var payload: Dictionary = params.duplicate(true)
	payload["op"] = action
	payload["token"] = token
	payload["run_id"] = run_id
	var now: int = Time.get_ticks_msec()
	var wait_ms: int = HHAgentConstants.INPUT_WAIT_MS
	if action == "sequence":
		wait_ms = HHAgentConstants.INPUT_WAIT_MS + 8000
	_pending = {
		PENDING_KEY: true,
		"kind": "input",
		"command_id": command_id,
		"post": post,
		"action": action,
		"token": token,
		"run_id": run_id,
		"payload": payload,
		"sent": false,
		"sends": 0,
		"sent_ms": 0,
		"deadline_ms": now + wait_ms,
		"steal_until": (
			now + HHAgentConstants.INPUT_STEAL_MS
			if params.get("editor_foreground", false) == true
			else 0
		),
	}
	if int(_pending.get("steal_until", 0)) <= now:
		_try_send()
	return {PENDING_KEY: true, "ok": false, "command_id": command_id}


func begin_time(
	command_id: String,
	action: String,
	params: Dictionary,
	post: String,
) -> Dictionary:
	if action != "freeze" and action != "step":
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"not a proven Play freeze/step verb",
			"",
		)
	if not EditorInterface.is_playing_scene():
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"runtime freeze/step requires a proven Play process (is_playing_scene)",
			"play",
		)
	var play: HHAgentPlayAdapter = HHAgentPlayAdapter.current()
	if play == null:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"runtime freeze/step requires a proven Play process (R6)",
			"play",
		)
	var stale: Dictionary = play.stale_run_reject(command_id, params)
	if not stale.is_empty():
		return stale
	var run_id: String = play.current_run_id()
	if run_id.is_empty():
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"runtime freeze/step missing Play run_id bind",
			"run_id",
		)
	if not _pending.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_BUSY, "runtime/input channel busy", "runtime")
	var token: String = _mint_token()
	var payload: Dictionary = params.duplicate(true)
	payload["op"] = action
	payload["token"] = token
	payload["run_id"] = run_id
	var now: int = Time.get_ticks_msec()
	var wait_ms: int = HHAgentConstants.TIME_WAIT_MS
	if action == "step" and params.has("timeout_ms"):
		wait_ms = maxi(wait_ms, int(params.get("timeout_ms")) + 4000)
	_pending = {
		PENDING_KEY: true,
		"kind": "time",
		"command_id": command_id,
		"post": post,
		"action": action,
		"token": token,
		"run_id": run_id,
		"payload": payload,
		"sent": false,
		"sends": 0,
		"sent_ms": 0,
		"deadline_ms": now + wait_ms,
	}
	_try_send()
	return {PENDING_KEY: true, "ok": false, "command_id": command_id}


func begin_capture(
	command_id: String,
	action: String,
	params: Dictionary,
	post: String,
) -> Dictionary:
	if action != "screenshot" and action != "perf":
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"not a proven Play screenshot/perf verb",
			"",
		)
	if not EditorInterface.is_playing_scene():
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"runtime screenshot/perf requires a proven Play process (is_playing_scene)",
			"play",
		)
	var play: HHAgentPlayAdapter = HHAgentPlayAdapter.current()
	if play == null:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"runtime screenshot/perf requires a proven Play process (R6)",
			"play",
		)
	var stale: Dictionary = play.stale_run_reject(command_id, params)
	if not stale.is_empty():
		return stale
	var run_id: String = play.current_run_id()
	if run_id.is_empty():
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"runtime screenshot/perf missing Play run_id bind",
			"run_id",
		)
	if not _pending.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_BUSY, "runtime/input channel busy", "runtime")
	var token: String = _mint_token()
	var payload: Dictionary = params.duplicate(true)
	payload["op"] = action
	payload["token"] = token
	payload["run_id"] = run_id
	var now: int = Time.get_ticks_msec()
	var wait_ms: int = HHAgentConstants.CAPTURE_WAIT_MS
	if action == "perf":
		wait_ms = HHAgentConstants.PERF_WAIT_MS
	_pending = {
		PENDING_KEY: true,
		"kind": "capture",
		"command_id": command_id,
		"post": post,
		"action": action,
		"token": token,
		"run_id": run_id,
		"payload": payload,
		"sent": false,
		"sends": 0,
		"sent_ms": 0,
		"deadline_ms": now + wait_ms,
	}
	_try_send()
	return {PENDING_KEY: true, "ok": false, "command_id": command_id}


func poll_pending() -> Dictionary:
	if _pending.is_empty():
		return {}
	var command_id: String = str(_pending.get("command_id", ""))
	var now: int = Time.get_ticks_msec()
	if now > int(_pending.get("deadline_ms", 0)):
		var kind: String = str(_pending.get("kind", "runtime"))
		return _fail_pending(
			command_id,
			HHAgentErrors.E_TIMEOUT,
			(
				"play.input debugger reply timed out"
				if kind == "input"
				else (
					"runtime freeze/step debugger reply timed out"
					if kind == "time"
					else (
						"runtime screenshot/perf debugger reply timed out"
						if kind == "capture"
						else "runtime debugger reply timed out (no remote tree invented)"
					)
				)
			),
		)
	if not EditorInterface.is_playing_scene():
		return _fail_pending(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"Play stopped before runtime reply",
		)
	var steal_until: int = int(_pending.get("steal_until", 0))
	if steal_until > 0 and now < steal_until:
		return {PENDING_KEY: true, "command_id": command_id}
	var dbg: HHAgentRuntimeDebugger = HHAgentRuntimeDebugger.current()
	if dbg == null:
		return _fail_pending(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"runtime debugger plugin gone",
		)
	var token: String = str(_pending.get("token", ""))
	var reply: Dictionary = dbg.take_reply(token)
	if reply.is_empty():
		var sent_ms: int = int(_pending.get("sent_ms", 0))
		var sends: int = int(_pending.get("sends", 0))
		var kind: String = str(_pending.get("kind", ""))
		if not _pending.get("sent", false):
			_try_send()
		elif (
			kind != "input"
			and kind != "time"
			and kind != "capture"
			and sent_ms > 0
			and now - sent_ms >= HHAgentConstants.RUNTIME_RESEND_MS
			and sends < HHAgentConstants.RUNTIME_MAX_RESEND
		):
			_try_send()
		return {PENDING_KEY: true, "command_id": command_id}
	if str(_pending.get("kind", "")) == "input":
		return _finish_input(command_id, reply)
	if str(_pending.get("kind", "")) == "time":
		return _finish_time(command_id, reply)
	if str(_pending.get("kind", "")) == "capture":
		return _finish_capture(command_id, reply)
	return _finish(command_id, reply)


func _try_send() -> void:
	var dbg: HHAgentRuntimeDebugger = HHAgentRuntimeDebugger.current()
	if dbg == null:
		return
	var payload_v: Variant = _pending.get("payload", {})
	if typeof(payload_v) != TYPE_DICTIONARY:
		return
	var payload: Dictionary = payload_v
	var sent: bool = dbg.send_payload("%s:req" % HHAgentConstants.RUNTIME_CAPTURE, [JSON.stringify(payload)])
	if sent:
		_pending["sent"] = true
		_pending["sent_ms"] = Time.get_ticks_msec()
		_pending["sends"] = int(_pending.get("sends", 0)) + 1
		_last_send_ms = int(_pending["sent_ms"])


func _finish(command_id: String, reply: Dictionary) -> Dictionary:
	var post: String = str(_pending.get("post", "remote_tree_snapshot"))
	var want_run: String = str(_pending.get("run_id", ""))
	var want_token: String = str(_pending.get("token", ""))
	_pending = {}
	if not EditorInterface.is_playing_scene():
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"Play is not running; refusing invented remote tree",
			"play",
		)
	if str(reply.get("token", "")) != want_token:
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "runtime reply token mismatch", "token")
	if str(reply.get("run_id", "")) != want_run:
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "runtime reply run_id mismatch", "run_id")
	if reply.get("ok", false) != true:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			str(reply.get("message", "runtime probe failed")),
			"runtime",
		)
	if reply.get("tree_kind", "") != "remote" or reply.get("remote_tree", false) != true:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"runtime reply missing remote tree labels",
			"runtime",
		)
	if str(reply.get("source", "")) != "hh_agent_runtime":
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"runtime reply is not from hh_agent_runtime",
			"runtime",
		)
	var after: Dictionary = reply.duplicate(true)
	after["run_id"] = want_run
	after["game_tree_source"] = "hh_agent_runtime"
	if after.has("items") and after.get("items") is Array:
		if (after.get("items") as Array).size() > HHAgentConstants.MAX_PAGE:
			return _errors.fail(
				command_id,
				HHAgentErrors.E_UNVERIFIED,
				"runtime page exceeded MAX_PAGE",
				"limit",
			)
	if int(after.get("limit", 0)) > HHAgentConstants.MAX_PAGE:
		after["limit"] = HHAgentConstants.MAX_PAGE
	var checks: PackedStringArray = PackedStringArray()
	checks.append(post)
	return _errors.ok_read(command_id, checks, after)


func _fail_pending(command_id: String, code: String, message: String) -> Dictionary:
	_pending = {}
	return _errors.fail(command_id, code, message, "runtime")


func _finish_input(command_id: String, reply: Dictionary) -> Dictionary:
	var post: String = str(_pending.get("post", "input_action_injected"))
	var want_run: String = str(_pending.get("run_id", ""))
	var want_token: String = str(_pending.get("token", ""))
	var verb: String = str(_pending.get("action", ""))
	_pending = {}
	if not EditorInterface.is_playing_scene():
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"Play stopped before input reply",
			"play",
		)
	if str(reply.get("token", "")) != want_token:
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "input reply token mismatch", "token")
	if str(reply.get("run_id", "")) != want_run:
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "input reply run_id mismatch", "run_id")
	if str(reply.get("source", "")) != "hh_agent_runtime":
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"input reply is not from Play hh_agent_runtime",
			"input",
		)
	if reply.get("ok", false) != true:
		var code: String = str(reply.get("code", HHAgentErrors.E_UNVERIFIED))
		if code.is_empty():
			code = HHAgentErrors.E_UNVERIFIED
		return _errors.fail(
			command_id,
			code,
			str(reply.get("message", "Play input inject failed")),
			"input",
		)
	if reply.get("injected", false) != true and reply.get("released", false) != true:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"Play process did not confirm injected input",
			"input",
		)
	if verb != "release_all" and reply.get("seen", false) != true:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"Play process _input did not see the event",
			"input",
		)
	var after: Dictionary = reply.duplicate(true)
	after["run_id"] = want_run
	after["playing"] = true
	after["is_playing_scene"] = true
	after["playing_scene"] = _normalize_res(str(EditorInterface.get_playing_scene()))
	after["game_tree_source"] = "hh_agent_runtime"
	after["header"] = _live_header(want_run)
	after["send_input"] = false
	after["rpa"] = false
	var checks: PackedStringArray = PackedStringArray()
	checks.append(post)
	return _errors.ok_changed(command_id, checks, after, true)


func _finish_time(command_id: String, reply: Dictionary) -> Dictionary:
	var post: String = str(_pending.get("post", "runtime_frozen_matches"))
	var want_run: String = str(_pending.get("run_id", ""))
	var want_token: String = str(_pending.get("token", ""))
	var verb: String = str(_pending.get("action", ""))
	var payload_v: Variant = _pending.get("payload", {})
	var payload: Dictionary = payload_v if payload_v is Dictionary else {}
	_pending = {}
	if not EditorInterface.is_playing_scene():
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"Play stopped before freeze/step reply",
			"play",
		)
	if str(reply.get("token", "")) != want_token:
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "freeze/step reply token mismatch", "token")
	if str(reply.get("run_id", "")) != want_run:
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "freeze/step reply run_id mismatch", "run_id")
	if str(reply.get("source", "")) != "hh_agent_runtime":
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"freeze/step reply is not from Play hh_agent_runtime",
			"runtime",
		)
	if reply.get("editor_time_scale", false) == true:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"refusing editor-only Engine.time_scale paper freeze/step",
			"runtime",
		)
	if reply.get("ok", false) != true:
		var code: String = str(reply.get("code", HHAgentErrors.E_UNVERIFIED))
		if code.is_empty():
			code = HHAgentErrors.E_UNVERIFIED
		return _errors.fail(
			command_id,
			code,
			str(reply.get("message", "Play freeze/step failed")),
			"runtime",
		)
	if verb == "freeze":
		if reply.get("frozen", false) != (payload.get("frozen", true) == true):
			return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "runtime_frozen_matches failed", "runtime")
		if payload.get("frozen", true) == true:
			if reply.get("observed_frozen", false) != true:
				return _errors.fail(
					command_id,
					HHAgentErrors.E_UNVERIFIED,
					"Play fixture/probe did not observe freeze",
					"runtime",
				)
			if reply.get("paused", false) != true:
				return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "Play tree was not paused", "runtime")
	if verb == "step":
		if reply.get("stepped", false) != true:
			return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "Play process did not confirm a step", "runtime")
		if int(reply.get("frames_advanced", 0)) < 1:
			return _errors.fail(
				command_id,
				HHAgentErrors.E_UNVERIFIED,
				"step ACK requires observed frames_advanced",
				"runtime",
			)
		if payload.has("until") and reply.get("matched", false) != true:
			return _errors.fail(
				command_id,
				HHAgentErrors.E_UNVERIFIED,
				"step-until ACK requires matched predicate",
				"runtime",
			)
	var after: Dictionary = reply.duplicate(true)
	after["run_id"] = want_run
	after["playing"] = true
	after["is_playing_scene"] = true
	after["playing_scene"] = _normalize_res(str(EditorInterface.get_playing_scene()))
	after["game_tree_source"] = "hh_agent_runtime"
	after["editor_time_scale"] = false
	after["source"] = "hh_agent_runtime"
	var checks: PackedStringArray = PackedStringArray()
	checks.append(post)
	return _errors.ok_changed(command_id, checks, after, true)


func _finish_capture(command_id: String, reply: Dictionary) -> Dictionary:
	var post: String = str(_pending.get("post", "screenshot_artifact_present"))
	var want_run: String = str(_pending.get("run_id", ""))
	var want_token: String = str(_pending.get("token", ""))
	var verb: String = str(_pending.get("action", ""))
	_pending = {}
	if not EditorInterface.is_playing_scene():
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"Play stopped before screenshot/perf reply",
			"play",
		)
	if str(reply.get("token", "")) != want_token:
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "screenshot/perf reply token mismatch", "token")
	if str(reply.get("run_id", "")) != want_run:
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "screenshot/perf reply run_id mismatch", "run_id")
	if str(reply.get("source", "")) != "hh_agent_runtime":
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"screenshot/perf reply is not from Play hh_agent_runtime",
			"runtime",
		)
	if reply.get("ok", false) != true:
		var code: String = str(reply.get("code", HHAgentErrors.E_UNVERIFIED))
		if code.is_empty():
			code = HHAgentErrors.E_UNVERIFIED
		var fail_after: Dictionary = reply.duplicate(true)
		fail_after["run_id"] = want_run
		fail_after["playing"] = true
		fail_after["is_playing_scene"] = true
		fail_after["playing_scene"] = _normalize_res(str(EditorInterface.get_playing_scene()))
		fail_after["game_tree_source"] = "hh_agent_runtime"
		fail_after["source"] = "hh_agent_runtime"
		return _errors.fail_after(
			command_id,
			code,
			str(reply.get("message", "Play screenshot/perf failed")),
			"runtime",
			fail_after,
		)
	if reply.get("dummy", false) == true:
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "refusing dummy screenshot/perf ACK", "runtime")
	if verb == "screenshot":
		if reply.get("screenshot_artifact_present", false) != true:
			return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "screenshot_artifact_present failed", "runtime")
		var path_s: String = str(reply.get("path", "")).replace("\\", "/")
		if path_s.is_empty() or path_s.contains("..") or (not path_s.contains(".hh-agent/") and not path_s.contains("r6w5/")):
			return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "screenshot path is not under project artifacts", "runtime")
		if int(reply.get("bytes", 0)) < 32:
			return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "screenshot ACK requires a real captured file", "runtime")
		if not _artifact_exists(path_s):
			return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "screenshot file missing on disk after capture", "runtime")
	if verb == "perf":
		if reply.get("perf_counters_present", false) != true:
			return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "perf_counters_present failed", "runtime")
		if typeof(reply.get("hardware_manifest", {})) != TYPE_DICTIONARY:
			return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "perf ACK requires a hardware manifest", "runtime")
	var after: Dictionary = reply.duplicate(true)
	after["run_id"] = want_run
	after["playing"] = true
	after["is_playing_scene"] = true
	after["playing_scene"] = _normalize_res(str(EditorInterface.get_playing_scene()))
	after["game_tree_source"] = "hh_agent_runtime"
	after["source"] = "hh_agent_runtime"
	after["dummy"] = false
	var checks: PackedStringArray = PackedStringArray()
	checks.append(post)
	return _errors.ok_changed(command_id, checks, after, true)


func _artifact_exists(path_s: String) -> bool:
	var p: String = path_s.strip_edges().replace("\\", "/")
	if p.begins_with("res://"):
		var abs_p: String = ProjectSettings.globalize_path(p)
		return FileAccess.file_exists(p) or FileAccess.file_exists(abs_p)
	return FileAccess.file_exists(p)


func _replay_header_fail(command_id: String, params: Dictionary, run_id: String) -> Dictionary:
	if params.get("replay", false) != true:
		return {}
	var header_v: Variant = params.get("header", {})
	if typeof(header_v) != TYPE_DICTIONARY:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"replay mismatch: header missing",
			"params.header",
		)
	var header: Dictionary = header_v
	var engine_s: String = str(header.get("engine", ""))
	if engine_s.is_empty() or engine_s != HHAgentConstants.PINNED_GODOT:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"replay mismatch: engine header",
			"params.header.engine",
		)
	var want_run: String = str(header.get("run_id", ""))
	if not want_run.is_empty() and want_run != run_id:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"replay mismatch: run_id header",
			"params.header.run_id",
		)
	var want_project: String = str(header.get("project", ""))
	var live_project: String = _project_hash()
	if not want_project.is_empty() and not live_project.is_empty() and want_project != live_project:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"replay mismatch: project header",
			"params.header.project",
		)
	if header.has("seed") and int(header.get("seed", 0)) != 0:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"replay mismatch: seed header (seed unpinned)",
			"params.header.seed",
		)
	if header.get("fixed_step", false) == true:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"replay mismatch: fixed-step header (unpinned until later WP)",
			"params.header.fixed_step",
		)
	return {}


func _live_header(run_id: String) -> Dictionary:
	return {
		"engine": HHAgentConstants.PINNED_GODOT,
		"project": _project_hash(),
		"run_id": run_id,
		"seed": 0,
		"fixed_step": false,
		"snapshot_hashes": {},
		"snapshot_status": "Alternative",
		"seed_status": "unpinned",
		"fixed_step_status": "unpinned",
	}


func _project_hash() -> String:
	if not FileAccess.file_exists("res://project.godot"):
		return ""
	return FileAccess.get_sha256("res://project.godot")


func _normalize_res(path_s: String) -> String:
	var p: String = path_s.strip_edges().replace("\\", "/")
	if p.is_empty():
		return ""
	if p.begins_with("res://"):
		return p
	return "res://%s" % p.lstrip("/")


func _limit_of(params: Dictionary) -> int:
	var limit: int = HHAgentConstants.DEFAULT_PAGE
	if params.has("limit"):
		limit = int(params.get("limit"))
	if limit < 1:
		limit = 1
	if limit > HHAgentConstants.MAX_PAGE:
		limit = HHAgentConstants.MAX_PAGE
	return limit


func _offset_of(params: Dictionary) -> int:
	if params.has("offset"):
		return maxi(0, int(params.get("offset")))
	if params.has("cursor"):
		var raw: String = str(params.get("cursor"))
		if raw.is_valid_int():
			return maxi(0, int(raw))
	return 0


func _mint_token() -> String:
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
