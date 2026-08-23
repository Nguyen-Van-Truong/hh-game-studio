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
	if action != "tree" and action != "node" and action != "state" and action != "time":
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
	}
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


func poll_pending() -> Dictionary:
	if _pending.is_empty():
		return {}
	var command_id: String = str(_pending.get("command_id", ""))
	var now: int = Time.get_ticks_msec()
	if now > int(_pending.get("deadline_ms", 0)):
		return _fail_pending(
			command_id,
			HHAgentErrors.E_TIMEOUT,
			"runtime debugger reply timed out (no remote tree invented)",
		)
	if not EditorInterface.is_playing_scene():
		return _fail_pending(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"Play stopped before runtime reply",
		)
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
		if not _pending.get("sent", false) or (
			sent_ms > 0
			and now - sent_ms >= HHAgentConstants.RUNTIME_RESEND_MS
			and sends < HHAgentConstants.RUNTIME_MAX_RESEND
		):
			_try_send()
		return {PENDING_KEY: true, "command_id": command_id}
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
