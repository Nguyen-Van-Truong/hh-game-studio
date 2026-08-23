class_name HHAgentPlayAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")

## Play/debug process lifecycle. EditorInterface play_* only — never spawn a
## second Godot, never quit-after CLI, Movie Maker, or the editor process id
## as play PID (that PID is the editor). A11: Play is a separate process.
## Never return get_edited_scene_root() as the game tree. Never invent
## playing=true. debug = start + EditorDebuggerSession attached. There is no
## dedicated debug-scene API. Catalog: register in actions.json. Generated
## plugin-validator.json / mcp-tools.json are coordinator-owned
## (`npm run generate`).

const CROCKFORD: String = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
const EVIDENCE_ROOT: String = "res://.hh-agent/evidence"
const PENDING_KEY: String = "_hh_play_pending"
const LOG_KIND_PARSER: String = "PARSER"
const LOG_KIND_RUNTIME: String = "runtime"
const LOG_KIND_IMPORT: String = "import"

static var _current: HHAgentPlayAdapter

var _errors: HHAgentErrors = HHAgentErrors.new()
var _path_line_re: RegEx = RegEx.new()
var _run_id: String = ""
var _previous_run_id: String = ""
var _dead_run_ids: Dictionary = {}
var _scene: String = ""
var _mode: String = "play"
var _playing_expected: bool = false
var _debugger_attached: bool = false
var _session_id: int = -1
var _last_beat_ms: int = 0
var _play_ack_ms: int = 0
var _run_started_unix: int = 0
var _hang_fired: bool = false
var _stop_reason: String = ""
var _logs: Array[Dictionary] = []
var _pending: Dictionary = {}
var _held_inputs: PackedStringArray = PackedStringArray()
var _log_seen: Dictionary = {}
var _session_seen: Dictionary = {}
var _last_editor_log: String = ""
var _last_debug_panel: String = ""
var _file_log_offsets: Dictionary = {}
var _on_runtime_autoload: Callable
var _off_runtime_autoload: Callable


static func current() -> HHAgentPlayAdapter:
	return _current


func set_runtime_autoload_hooks(on_hook: Callable, off_hook: Callable) -> void:
	_on_runtime_autoload = on_hook
	_off_runtime_autoload = off_hook


func current_run_id() -> String:
	return _run_id


func stale_run_reject(command_id: String, params: Dictionary) -> Dictionary:
	return _reject_stale(command_id, params)


func attach() -> void:
	_current = self
	_session_seen.clear()
	ProjectSettings.set_setting("debug/file_logging/enable_file_logging", true)
	if _path_line_re.compile("(res://[^\\s:)]+):(\\d+)") != OK:
		push_warning("hh_agent: play path:line regex failed")


func detach() -> void:
	if _current == self:
		_current = null


func shutdown() -> void:
	_cancel_pending("play adapter shutdown")
	if _playing_expected and EditorInterface.is_playing_scene():
		EditorInterface.stop_playing_scene()
		_release_all()
	_drop_runtime_autoload()
	detach()


func handles(action: String) -> bool:
	return action == "start" or action == "stop" or action == "restart" or action == "debug"


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	_precondition: Dictionary,
) -> Dictionary:
	if method != "godot.play" or not handles(action):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not a play apply verb", "")
	var def: Dictionary = actions.lookup(method, action)
	var post: String = str(def.get("postcondition", ""))
	if post.is_empty():
		post = _fallback_post(action)
	var stale: Dictionary = _reject_stale(command_id, params)
	if not stale.is_empty():
		return stale
	if action == "stop":
		return _stop(command_id, params, post)
	if action == "restart":
		return _restart(command_id, params, post)
	if action == "debug":
		return _start(command_id, params, "debug", post)
	return _start(command_id, params, str(params.get("mode", "play")), post)


func poll_pending() -> Dictionary:
	if _pending.is_empty():
		return {}
	var command_id: String = str(_pending.get("command_id", ""))
	var post: String = str(_pending.get("post", ""))
	var verb: String = str(_pending.get("verb", ""))
	var deadline: int = int(_pending.get("deadline_ms", 0))
	var now: int = Time.get_ticks_msec()
	if deadline > 0 and now > deadline:
		return _fail_pending(command_id, HHAgentErrors.E_TIMEOUT, _pending_timeout_message())
	var phase: String = str(_pending.get("phase", ""))
	if phase == "stop" or phase == "stop_then_start":
		if EditorInterface.is_playing_scene():
			return {PENDING_KEY: true, "command_id": command_id}
		_release_all()
		_playing_expected = false
		if phase == "stop":
			return _finish_stop(command_id, post)
		_begin_run(str(_pending.get("scene", "")), str(_pending.get("mode", "play")), true)
		_collect_parse_errors(_scene)
		_invoke_play(_scene)
		_pending["phase"] = "start"
		_pending["deadline_ms"] = now + HHAgentConstants.PLAY_START_WAIT_MS
		return {PENDING_KEY: true, "command_id": command_id}
	if phase == "start" or phase == "debug_wait":
		_scrape_all_logs()
		if not EditorInterface.is_playing_scene():
			return {PENDING_KEY: true, "command_id": command_id}
		var live_scene: String = _normalize_res(str(EditorInterface.get_playing_scene()))
		if not _scenes_match(_scene, live_scene):
			return {PENDING_KEY: true, "command_id": command_id}
		var need_debug: bool = _mode == "debug" or verb == "debug"
		if need_debug and not _debugger_attached:
			_pending["phase"] = "debug_wait"
			return {PENDING_KEY: true, "command_id": command_id}
		return _finish_start(command_id, post, verb)
	return {PENDING_KEY: true, "command_id": command_id}


func tick_watchdog() -> void:
	if _playing_expected:
		_scrape_all_logs()
	var playing: bool = EditorInterface.is_playing_scene()
	if not _playing_expected:
		return
	if not playing:
		_on_unexpected_stop()
		return
	if _hang_fired:
		return
	if _play_ack_ms <= 0:
		return
	var now: int = Time.get_ticks_msec()
	if now - _play_ack_ms < HHAgentConstants.PLAY_HANG_GRACE_MS:
		return
	var beat: int = _last_beat_ms
	if beat <= 0:
		beat = _play_ack_ms
	if now - beat < HHAgentConstants.PLAY_HANG_MS:
		return
	_hang_fired = true
	_stop_reason = "hang"
	_ingest_text(LOG_KIND_RUNTIME, "watchdog hang: no debugger heartbeat", _scene, 0, [])
	if EditorInterface.is_playing_scene():
		EditorInterface.stop_playing_scene()
	_release_all()
	_playing_expected = false
	_debugger_attached = false
	_emit_event("play.stopped", {"reason": "hang", "code": HHAgentErrors.E_TIMEOUT})


func note_session_setup(session_id: int, active: bool) -> void:
	_session_id = session_id
	if active:
		note_session_started(session_id)


func note_session_started(session_id: int) -> void:
	_session_id = session_id
	_debugger_attached = true
	_last_beat_ms = Time.get_ticks_msec()


func note_session_stopped(session_id: int) -> void:
	if session_id == _session_id:
		_debugger_attached = false


func note_debugger_message(message: String, data: Array, _session_id: int) -> void:
	_last_beat_ms = Time.get_ticks_msec()
	if message == "performance" or message.begins_with("performance:"):
		return
	var text: String = _message_text(message, data)
	if text.is_empty():
		return
	var kind: String = _classify_text(text)
	var loc: Dictionary = _extract_loc(text, data)
	var stack: Array = _extract_stack(data)
	_ingest_text(kind, text, str(loc.get("path", "")), int(loc.get("line", 0)), stack)


func status_read(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var stale: Dictionary = _reject_stale(command_id, params)
	if not stale.is_empty():
		return stale
	var playing: bool = EditorInterface.is_playing_scene()
	var again: bool = EditorInterface.is_playing_scene()
	if playing != again:
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "play flag changed during readback", "")
	var live_scene: String = ""
	if playing:
		live_scene = _normalize_res(str(EditorInterface.get_playing_scene()))
	return _errors.ok_read(command_id, _checks(post), _status_after(playing, live_scene))


func logs_read(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var stale: Dictionary = _reject_stale(command_id, params)
	if not stale.is_empty():
		return stale
	_scrape_all_logs()
	_rescan_recent_file_logs()
	_scrape_debugger_panel()
	if _run_id.is_empty() and _logs.is_empty():
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"play logs require a Play run (R6)",
			"",
		)
	var limit: int = int(params.get("limit", 50))
	if limit < 1:
		limit = 1
	if limit > HHAgentConstants.MAX_PAGE:
		limit = HHAgentConstants.MAX_PAGE
	var start: int = maxi(0, _logs.size() - limit)
	var items: Array = []
	var i: int = start
	while i < _logs.size():
		items.append((_logs[i] as Dictionary).duplicate(true))
		i += 1
	return _errors.ok_read(command_id, _checks(post), {
		"run_id": _run_id,
		"tree_kind": "editor",
		"remote_tree": false,
		"items": items,
		"total": _logs.size(),
		"source": "play_log_ring",
	})


func _start(command_id: String, params: Dictionary, mode: String, post: String) -> Dictionary:
	var scene: String = _normalize_res(str(params.get("scene", "")))
	if scene.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "scene required", "params.scene")
	if mode != "play" and mode != "debug":
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "mode must be play|debug", "params.mode")
	if EditorInterface.is_playing_scene() or _playing_expected:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_BUSY,
			"play already running; stop or restart",
			"play",
		)
	_begin_run(scene, mode, false)
	_collect_parse_errors(scene)
	_invoke_play(scene)
	if _playing_now_matches(scene) and (mode != "debug" or _debugger_attached):
		return _finish_start(command_id, post, "debug" if mode == "debug" else "start")
	_pending = {
		PENDING_KEY: true,
		"command_id": command_id,
		"post": post,
		"verb": "debug" if mode == "debug" else "start",
		"phase": "start",
		"scene": scene,
		"mode": mode,
		"deadline_ms": Time.get_ticks_msec() + HHAgentConstants.PLAY_START_WAIT_MS,
	}
	return {PENDING_KEY: true, "ok": false, "command_id": command_id}


func _restart(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var scene: String = _normalize_res(str(params.get("scene", "")))
	if scene.is_empty():
		scene = _scene
	if scene.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "scene required", "params.scene")
	if EditorInterface.is_playing_scene():
		EditorInterface.stop_playing_scene()
	_release_all()
	_playing_expected = false
	if EditorInterface.is_playing_scene():
		_pending = {
			PENDING_KEY: true,
			"command_id": command_id,
			"post": post,
			"verb": "restart",
			"phase": "stop_then_start",
			"scene": scene,
			"mode": "play",
			"deadline_ms": Time.get_ticks_msec() + HHAgentConstants.PLAY_START_WAIT_MS,
		}
		return {PENDING_KEY: true, "ok": false, "command_id": command_id}
	_begin_run(scene, "play", true)
	_collect_parse_errors(scene)
	_invoke_play(scene)
	if _playing_now_matches(scene):
		return _finish_start(command_id, post, "restart")
	_pending = {
		PENDING_KEY: true,
		"command_id": command_id,
		"post": post,
		"verb": "restart",
		"phase": "start",
		"scene": scene,
		"mode": "play",
		"deadline_ms": Time.get_ticks_msec() + HHAgentConstants.PLAY_START_WAIT_MS,
	}
	return {PENDING_KEY: true, "ok": false, "command_id": command_id}


func _stop(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var reason: String = str(params.get("reason", "user"))
	_stop_reason = reason
	if EditorInterface.is_playing_scene():
		EditorInterface.stop_playing_scene()
	_release_all()
	if EditorInterface.is_playing_scene():
		_pending = {
			PENDING_KEY: true,
			"command_id": command_id,
			"post": post,
			"verb": "stop",
			"phase": "stop",
			"deadline_ms": Time.get_ticks_msec() + HHAgentConstants.PLAY_START_WAIT_MS,
		}
		return {PENDING_KEY: true, "ok": false, "command_id": command_id}
	_playing_expected = false
	_debugger_attached = false
	return _finish_stop(command_id, post)


func _begin_run(scene: String, mode: String, restart: bool) -> void:
	if restart and not _run_id.is_empty():
		_dead_run_ids[_run_id] = true
		_previous_run_id = _run_id
	elif not _run_id.is_empty():
		_dead_run_ids[_run_id] = true
		_previous_run_id = _run_id
	_run_id = _mint_ulid()
	_scene = scene
	_mode = mode
	_playing_expected = true
	_debugger_attached = false
	_hang_fired = false
	_play_ack_ms = 0
	_run_started_unix = int(Time.get_unix_time_from_system())
	_last_beat_ms = 0
	_stop_reason = ""
	_logs.clear()
	_log_seen.clear()
	_file_log_offsets.clear()
	_prime_log_cursors()
	_snapshot_file_log_offsets()
	_ensure_evidence_dir(_run_id)


func _invoke_play(scene: String) -> void:
	var main: String = _normalize_res(str(ProjectSettings.get_setting("application/run/main_scene", "")))
	var current: String = ""
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited != null:
		current = _normalize_res(str(edited.scene_file_path))
	if not main.is_empty() and _scenes_match(scene, main):
		EditorInterface.play_main_scene()
	elif not current.is_empty() and _scenes_match(scene, current):
		EditorInterface.play_current_scene()
	else:
		EditorInterface.play_custom_scene(scene)


func _finish_start(command_id: String, post: String, verb: String) -> Dictionary:
	_pending = {}
	if not EditorInterface.is_playing_scene():
		return _unverified_play(command_id, "is_playing_scene is false after Play")
	var live_scene: String = _normalize_res(str(EditorInterface.get_playing_scene()))
	if not _scenes_match(_scene, live_scene):
		return _unverified_play(
			command_id,
			"get_playing_scene bind mismatch want=%s got=%s" % [_scene, live_scene],
		)
	_playing_expected = true
	_play_ack_ms = Time.get_ticks_msec()
	_scrape_all_logs()
	_emit_event("play.started", {"verb": verb, "scene": live_scene})
	var after: Dictionary = _status_after(true, live_scene)
	after["changed"] = true
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _finish_stop(command_id: String, post: String) -> Dictionary:
	_pending = {}
	if EditorInterface.is_playing_scene():
		return _unverified_play(command_id, "is_playing_scene still true after stop")
	if not _run_id.is_empty():
		_dead_run_ids[_run_id] = true
	_rescan_recent_file_logs()
	_scrape_debugger_panel()
	_drop_runtime_autoload()
	_emit_event("play.stopped", {"reason": _stop_reason})
	var after: Dictionary = _status_after(false, "")
	after["changed"] = true
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _fail_pending(command_id: String, code: String, message: String) -> Dictionary:
	_pending = {}
	_playing_expected = false
	if EditorInterface.is_playing_scene() and not _scenes_match(_scene, _normalize_res(str(EditorInterface.get_playing_scene()))):
		EditorInterface.stop_playing_scene()
		_release_all()
	if not EditorInterface.is_playing_scene():
		_drop_runtime_autoload()
	return _errors.fail(command_id, code, message, "play")


func _unverified_play(command_id: String, message: String) -> Dictionary:
	var diag: String = message
	if _is_headless():
		diag = "%s; headless_play=unproven Alternative" % message
	_playing_expected = EditorInterface.is_playing_scene()
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, diag, "play")


func _pending_timeout_message() -> String:
	var playing: bool = EditorInterface.is_playing_scene()
	var live: String = _normalize_res(str(EditorInterface.get_playing_scene())) if playing else ""
	var head: String = "proven" if playing and _is_headless() else ("unproven" if _is_headless() else "n/a")
	return (
		"Play did not satisfy is_playing_scene+get_playing_scene "
		+ "(playing=%s scene=%s want=%s debugger=%s headless_play=%s). Alternative: exclusive GUI Godot --editor"
	) % [str(playing), live, _scene, str(_debugger_attached), head]


func _status_after(playing: bool, live_scene: String) -> Dictionary:
	var headless: bool = _is_headless()
	var head_label: String = "unproven"
	if playing and headless:
		head_label = "proven"
	elif headless:
		head_label = "unproven"
	elif playing:
		head_label = "n/a"
	return {
		"playing": playing,
		"is_playing_scene": playing,
		"scene": _scene,
		"playing_scene": live_scene,
		"run_id": _run_id,
		"previous_run_id": _previous_run_id,
		"previous_alive": (
			not _previous_run_id.is_empty()
			and not _dead_run_ids.has(_previous_run_id)
			and _previous_run_id == _run_id
		),
		"mode": _mode,
		"tree_kind": "editor",
		"remote_tree": false,
		"game_tree_source": "is_playing_scene",
		"debugger_attached": _debugger_attached and playing,
		"headless_play": head_label,
		"play_pid": 0,
		"pid_source": "unproven",
		"stop_reason": _stop_reason,
		"evidence": "%s/%s" % [EVIDENCE_ROOT, _run_id] if not _run_id.is_empty() else "",
		"runtime_autoload": ProjectSettings.has_setting(
			"autoload/%s" % HHAgentConstants.RUNTIME_AUTOLOAD_NAME
		),
	}


func _reject_stale(command_id: String, params: Dictionary) -> Dictionary:
	if not params.has("run_id"):
		return {}
	var want: String = str(params.get("run_id", ""))
	if want.is_empty():
		return {}
	if want == _run_id:
		return {}
	if _dead_run_ids.has(want) or (not _previous_run_id.is_empty() and want == _previous_run_id):
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "stale run_id", "params.run_id")
	return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "unknown run_id", "params.run_id")


func _playing_now_matches(scene: String) -> bool:
	if not EditorInterface.is_playing_scene():
		return false
	return _scenes_match(scene, _normalize_res(str(EditorInterface.get_playing_scene())))


func _collect_parse_errors(scene: String) -> void:
	if scene.is_empty() or not ResourceLoader.exists(scene):
		return
	var packed: Resource = ResourceLoader.load(scene, "", ResourceLoader.CACHE_MODE_REUSE)
	if packed == null or not (packed is PackedScene):
		return
	var inst: Node = (packed as PackedScene).instantiate()
	if inst == null:
		return
	_scan_node_scripts(inst)
	inst.free()


func _scan_node_scripts(node: Node) -> void:
	var scr: Script = node.get_script()
	if scr is GDScript:
		var gd: GDScript = scr as GDScript
		var path_s: String = str(gd.resource_path)
		var probe: GDScript = GDScript.new()
		probe.source_code = gd.source_code
		if not path_s.is_empty():
			probe.take_over_path(path_s)
		var err: Error = probe.reload()
		if err != OK:
			_ingest_text(
				LOG_KIND_PARSER,
				"PARSER GDScript parse failed: %s" % error_string(err),
				path_s,
				1,
				[],
			)
	var i: int = 0
	while i < node.get_child_count():
		_scan_node_scripts(node.get_child(i))
		i += 1


func _scrape_all_logs() -> void:
	_scrape_editor_log()
	_scrape_file_logs()


func _scrape_editor_log() -> void:
	var base: Control = EditorInterface.get_base_control()
	if base == null:
		return
	var text: String = _editor_log_text(base)
	if text.is_empty() or text == _last_editor_log:
		return
	var prev: String = _last_editor_log
	_last_editor_log = text
	var delta: String = ""
	if prev.is_empty():
		delta = text
	elif text.begins_with(prev):
		delta = text.substr(prev.length())
	else:
		return
	if not delta.strip_edges().is_empty():
		_ingest_log_text_block(delta)


func _editor_log_text(root: Node) -> String:
	var founds: Array = root.find_children("*", "EditorLog", true, false)
	if founds.is_empty():
		var walked: Node = _find_by_class(root, "EditorLog")
		if walked != null:
			founds.append(walked)
	var buf: PackedStringArray = PackedStringArray()
	var i: int = 0
	while i < founds.size():
		var log_node: Node = founds[i] as Node
		if log_node != null:
			_collect_log_labels(log_node, buf)
		i += 1
	return "\n".join(buf)


func _collect_log_labels(node: Node, buf: PackedStringArray) -> void:
	if node is RichTextLabel:
		var rtl: RichTextLabel = node as RichTextLabel
		var raw: String = rtl.get_text()
		if raw.is_empty():
			raw = rtl.get_parsed_text()
		if not raw.is_empty():
			buf.append(raw)
	elif node is ItemList:
		var list: ItemList = node as ItemList
		var n: int = 0
		while n < list.item_count:
			buf.append(list.get_item_text(n))
			n += 1
	var i: int = 0
	while i < node.get_child_count():
		_collect_log_labels(node.get_child(i), buf)
		i += 1


func _find_by_class(node: Node, class_s: String) -> Node:
	if node.get_class() == class_s:
		return node
	var i: int = 0
	while i < node.get_child_count():
		var hit: Node = _find_by_class(node.get_child(i), class_s)
		if hit != null:
			return hit
		i += 1
	return null


func _godot_log_paths() -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	_append_dated_logs("user://logs", out)
	var dirs: PackedStringArray = PackedStringArray()
	var configured: String = str(ProjectSettings.get_setting("debug/file_logging/log_path", "user://logs/godot.log"))
	if configured.is_empty():
		configured = "user://logs/godot.log"
	if configured.begins_with("user://") or configured.begins_with("res://"):
		out.append(ProjectSettings.globalize_path(configured).replace("\\", "/"))
		dirs.append(ProjectSettings.globalize_path(configured.get_base_dir()).replace("\\", "/"))
	else:
		out.append(configured.replace("\\", "/"))
		dirs.append(configured.replace("\\", "/").get_base_dir())
	var user_dir: String = OS.get_user_data_dir().replace("\\", "/")
	if not user_dir.is_empty():
		dirs.append("%s/logs" % user_dir)
	dirs.append(ProjectSettings.globalize_path("user://logs").replace("\\", "/"))
	var seen_dir: Dictionary = {}
	var d: int = 0
	while d < dirs.size():
		var dir_s: String = str(dirs[d]).replace("\\", "/")
		d += 1
		if dir_s.is_empty() or seen_dir.has(dir_s):
			continue
		seen_dir[dir_s] = true
		out.append("%s/godot.log" % dir_s)
		_append_dated_logs(dir_s, out)
	out.append("user://logs/godot.log")
	out.append(ProjectSettings.globalize_path("user://logs/godot.log").replace("\\", "/"))
	return out


func _append_dated_logs(dir_s: String, out: PackedStringArray) -> void:
	var names: PackedStringArray = DirAccess.get_files_at(dir_s)
	if names.is_empty():
		var da: DirAccess = DirAccess.open(dir_s)
		if da != null:
			da.list_dir_begin()
			var listed: PackedStringArray = PackedStringArray()
			var n: String = da.get_next()
			while n != "":
				if n.begins_with("godot") and n.ends_with(".log"):
					listed.append(n)
				n = da.get_next()
			da.list_dir_end()
			names = listed
	var i: int = 0
	while i < names.size():
		var name_s: String = str(names[i])
		i += 1
		if name_s.begins_with("godot") and name_s.ends_with(".log"):
			if dir_s.begins_with("user://") or dir_s.begins_with("res://"):
				out.append("%s/%s" % [dir_s.rstrip("/"), name_s])
			else:
				out.append("%s/%s" % [dir_s, name_s])
				out.append("user://logs/%s" % name_s)


func _prime_log_cursors() -> void:
	var base: Control = EditorInterface.get_base_control()
	if base != null:
		var editor_text: String = _editor_log_text(base)
		if not editor_text.is_empty():
			_last_editor_log = editor_text
	var buf: PackedStringArray = PackedStringArray()
	_fill_debugger_panel_text(buf)
	var panel: String = "\n".join(buf)
	if not panel.is_empty():
		_last_debug_panel = panel


func _snapshot_file_log_offsets() -> void:
	var paths: PackedStringArray = _godot_log_paths()
	var seen_name: Dictionary = {}
	var i: int = 0
	while i < paths.size():
		var path_s: String = str(paths[i])
		i += 1
		var key: String = path_s.get_file().to_lower()
		if key.is_empty() or seen_name.has(key):
			continue
		seen_name[key] = true
		var text: String = _read_whole_log(path_s)
		if text.is_empty() and FileAccess.file_exists(path_s):
			_file_log_offsets[key] = -1
		else:
			_file_log_offsets[key] = text.length()


func _rescan_recent_file_logs() -> void:
	# Tails only. Never rewind a file that was snapshotted at begin_run —
	# whole-file reread would ingest yesterday's SCRIPT ERROR (stale PASS).
	_scrape_file_logs()


func _scrape_file_logs() -> void:
	var paths: PackedStringArray = _godot_log_paths()
	var seen_name: Dictionary = {}
	var i: int = 0
	while i < paths.size():
		var path_s: String = str(paths[i])
		i += 1
		var key: String = path_s.get_file().to_lower()
		if path_s.is_empty() or key.is_empty() or seen_name.has(key):
			continue
		seen_name[key] = true
		var text: String = _read_whole_log(path_s)
		if text.is_empty():
			continue
		var offset: int = int(_file_log_offsets.get(key, 0))
		if offset < 0:
			_file_log_offsets[key] = text.length()
			continue
		var chunk: String = text
		if offset >= text.length():
			chunk = ""
		elif offset > 0:
			chunk = text.substr(offset)
		_file_log_offsets[key] = text.length()
		if not chunk.strip_edges().is_empty():
			_ingest_log_text_block(chunk)


func _read_whole_log(path_s: String) -> String:
	var text: String = FileAccess.get_file_as_string(path_s)
	if not text.is_empty():
		return text
	var f: FileAccess = FileAccess.open(path_s, FileAccess.READ)
	if f != null:
		text = f.get_as_text()
		f.close()
		if not text.is_empty():
			return text
	var rel: String = "user://logs/%s" % path_s.get_file()
	if rel != path_s:
		text = FileAccess.get_file_as_string(rel)
		if not text.is_empty():
			return text
	var user_dir: String = OS.get_user_data_dir().replace("\\", "/")
	if user_dir.is_empty():
		return ""
	var tmp: String = "%s/logs/_hh_play_read.log" % user_dir
	if DirAccess.copy_absolute(path_s, tmp) != OK:
		return ""
	return FileAccess.get_file_as_string(tmp)


func _fill_debugger_panel_text(buf: PackedStringArray) -> void:
	var base: Control = EditorInterface.get_base_control()
	if base == null:
		return
	var hosts: Array = []
	hosts.append_array(base.find_children("*", "ScriptEditorDebugger", true, false))
	hosts.append_array(base.find_children("*", "EditorDebuggerNode", true, false))
	if hosts.is_empty():
		_collect_debug_texts(base, buf, 0)
		return
	var h: int = 0
	while h < hosts.size():
		_collect_debug_texts(hosts[h] as Node, buf, 0)
		h += 1


func _scrape_debugger_panel() -> void:
	var buf: PackedStringArray = PackedStringArray()
	_fill_debugger_panel_text(buf)
	var text: String = "\n".join(buf)
	if text.is_empty() or text == _last_debug_panel:
		return
	var prev: String = _last_debug_panel
	_last_debug_panel = text
	var delta: String = ""
	if prev.is_empty():
		delta = text
	elif text.begins_with(prev):
		delta = text.substr(prev.length())
	else:
		return
	if not delta.strip_edges().is_empty():
		_ingest_log_text_block(delta)


func _collect_debug_texts(node: Node, buf: PackedStringArray, depth: int) -> void:
	if node == null or depth > 14:
		return
	var cls: String = node.get_class().to_lower()
	var nm: String = str(node.name).to_lower()
	var host: bool = "debug" in cls or "debug" in nm or "error" in nm
	if host and node is ItemList:
		var list: ItemList = node as ItemList
		var n: int = 0
		while n < list.item_count:
			buf.append(list.get_item_text(n))
			n += 1
	elif host and node is Tree:
		var tree: Tree = node as Tree
		_dump_tree_item(tree.get_root(), buf, 0)
	elif host and node is RichTextLabel:
		var rtl: RichTextLabel = node as RichTextLabel
		var raw: String = rtl.get_text()
		if raw.is_empty():
			raw = rtl.get_parsed_text()
		if not raw.is_empty():
			buf.append(raw)
	var i: int = 0
	while i < node.get_child_count():
		var child: Node = node.get_child(i)
		var child_cls: String = child.get_class().to_lower()
		var child_nm: String = str(child.name).to_lower()
		if (
			host
			or "debug" in child_cls
			or "debug" in child_nm
			or "error" in child_nm
			or depth < 4
		):
			_collect_debug_texts(child, buf, depth + 1)
		i += 1


func _dump_tree_item(item: TreeItem, buf: PackedStringArray, depth: int) -> void:
	if item == null or depth > 24:
		return
	var tree: Tree = item.get_tree()
	var cols: int = tree.columns if tree != null else 1
	var c: int = 0
	while c < cols:
		var t: String = item.get_text(c)
		if not t.is_empty():
			buf.append(t)
		c += 1
	var child: TreeItem = item.get_first_child()
	while child != null:
		_dump_tree_item(child, buf, depth + 1)
		child = child.get_next()


func _ingest_log_text_block(block: String) -> void:
	var lines: PackedStringArray = block.split("\n")
	var i: int = 0
	while i < lines.size():
		var line_s: String = str(lines[i])
		var key: String = line_s.strip_edges()
		if key.is_empty() or _log_seen.has(key):
			i += 1
			continue
		var lower: String = key.to_lower()
		var interesting: bool = (
			"script error" in lower
			or "parse error" in lower
			or "parser" in lower
			or "invalid" in lower
			or "null instance" in lower
			or "null value" in lower
			or "cannot call" in lower
			or "attempt to call" in lower
			or "attempt to call function" in lower
			or "error" in lower and "res://" in lower
			or "at:" in lower and "res://" in lower
		)
		if interesting:
			_log_seen[key] = true
			var loc: Dictionary = _extract_loc(key, [])
			var stack: Array = []
			var message: String = key
			if i + 1 < lines.size() and "at:" in str(lines[i + 1]).to_lower():
				var at_line: String = str(lines[i + 1]).strip_edges()
				message = "%s | %s" % [key, at_line]
				stack.append({"path": str(loc.get("path", "")), "function": at_line, "line": int(loc.get("line", 0))})
				var at_loc: Dictionary = _extract_loc(at_line, [])
				if str(loc.get("path", "")).is_empty():
					loc = at_loc
				if int(loc.get("line", 0)) <= 0:
					loc["line"] = int(at_loc.get("line", 0))
			_ingest_text(_classify_text(message + " " + str(loc.get("path", ""))), message, str(loc.get("path", "")), int(loc.get("line", 0)), stack)
		i += 1


func _ingest_text(kind: String, text: String, path_s: String, line: int, stack: Array) -> void:
	var seen_key: String = text.strip_edges()
	if (
		not seen_key.begins_with("play process")
		and not seen_key.begins_with("watchdog hang")
		and _session_seen.has(seen_key)
	):
		return
	if (
		not seen_key.begins_with("play process")
		and not seen_key.begins_with("watchdog hang")
	):
		_session_seen[seen_key] = true
	var rec: Dictionary = {
		"kind": kind,
		"message": text,
		"path": path_s,
		"line": line,
		"stack": stack,
		"tree_kind": "remote" if _debugger_attached and EditorInterface.is_playing_scene() else "editor",
		"run_id": _run_id,
		"ts_ms": Time.get_ticks_msec(),
	}
	if kind == LOG_KIND_PARSER and not str(rec.get("message", "")).contains("PARSER"):
		rec["message"] = "PARSER %s" % text
	_logs.append(rec)
	if _logs.size() > HHAgentConstants.PLAY_LOG_RING:
		_logs.remove_at(0)
	if not _run_id.is_empty():
		_append_evidence(_run_id, "logs.jsonl", JSON.stringify(rec))


func _classify_text(text: String) -> String:
	var lower: String = text.to_lower()
	if "parse error" in lower or "parser" in lower or "compile error" in lower or "parse failed" in lower:
		return LOG_KIND_PARSER
	if "import" in lower or "failed to load" in lower or "error loading" in lower:
		return LOG_KIND_IMPORT
	return LOG_KIND_RUNTIME


func _extract_loc(text: String, data: Array) -> Dictionary:
	var path_s: String = ""
	var line: int = 0
	if data.size() >= 5 and typeof(data[2]) == TYPE_STRING:
		path_s = _normalize_res(str(data[2]))
	if data.size() >= 5:
		line = int(data[4])
	var found: RegExMatch = _path_line_re.search(text)
	if found != null:
		if path_s.is_empty():
			path_s = _normalize_res(found.get_string(1))
		if line <= 0:
			line = int(found.get_string(2))
	return {"path": path_s, "line": line}


func _extract_stack(data: Array) -> Array:
	var stack: Array = []
	var i: int = 5
	while i + 2 < data.size():
		stack.append({
			"path": _normalize_res(str(data[i])),
			"function": str(data[i + 1]),
			"line": int(data[i + 2]),
		})
		i += 3
	return stack


func _message_text(message: String, data: Array) -> String:
	var parts: PackedStringArray = PackedStringArray()
	parts.append(message)
	var i: int = 0
	while i < data.size() and i < 16:
		parts.append(str(data[i]))
		i += 1
	return " ".join(parts)


func _on_unexpected_stop() -> void:
	if _stop_reason.is_empty():
		_stop_reason = "crash"
	_playing_expected = false
	_debugger_attached = false
	_release_all()
	_rescan_recent_file_logs()
	_scrape_debugger_panel()
	_drop_runtime_autoload()
	_ingest_text(LOG_KIND_RUNTIME, "play process stopped unexpectedly", _scene, 0, [])
	_emit_event("play.stopped", {"reason": _stop_reason})


func _release_all() -> void:
	# Internal only. Empty set is OK. Never ACK input.action.
	_held_inputs = PackedStringArray()


func _install_runtime_autoload() -> void:
	if _on_runtime_autoload.is_valid():
		_on_runtime_autoload.call()


func _drop_runtime_autoload() -> void:
	if _off_runtime_autoload.is_valid():
		_off_runtime_autoload.call()


func _emit_event(name: String, payload: Dictionary) -> void:
	var rec: Dictionary = payload.duplicate(true)
	rec["event"] = name
	rec["run_id"] = _run_id
	rec["ts_ms"] = Time.get_ticks_msec()
	print("[hh_agent] event=%s run_id=%s" % [name, _run_id])
	if not _run_id.is_empty():
		_append_evidence(_run_id, "events.jsonl", JSON.stringify(rec))
	var store: HHAgentActivityStore = HHAgentActivityStore.current()
	if store != null and not _run_id.is_empty():
		store.set_runtime({"job": "play %s" % _run_id})


func _ensure_evidence_dir(run_id: String) -> void:
	var res_dir: String = "%s/%s" % [EVIDENCE_ROOT, run_id]
	var abs_dir: String = ProjectSettings.globalize_path(res_dir)
	DirAccess.make_dir_recursive_absolute(abs_dir)


func _append_evidence(run_id: String, filename: String, line: String) -> void:
	var res_path: String = "%s/%s/%s" % [EVIDENCE_ROOT, run_id, filename]
	var f: FileAccess
	if FileAccess.file_exists(res_path):
		f = FileAccess.open(res_path, FileAccess.READ_WRITE)
		if f != null:
			f.seek_end()
	else:
		f = FileAccess.open(res_path, FileAccess.WRITE)
	if f == null:
		return
	f.store_string(line + "\n")
	f.flush()
	f.close()


func _cancel_pending(_message: String) -> void:
	if _pending.is_empty():
		return
	_pending = {}


func _is_headless() -> bool:
	return str(DisplayServer.get_name()).to_lower() == "headless"


func _normalize_res(path_s: String) -> String:
	var p: String = path_s.strip_edges().replace("\\", "/")
	if p.is_empty():
		return ""
	if p.begins_with("res://"):
		return p
	return "res://%s" % p.lstrip("/")


func _scenes_match(a: String, b: String) -> bool:
	return _normalize_res(a) == _normalize_res(b) and not _normalize_res(a).is_empty()


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


func _fallback_post(action: String) -> String:
	if action == "start":
		return "play_process_running"
	if action == "stop":
		return "play_process_stopped"
	if action == "restart":
		return "play_process_restarted"
	if action == "debug":
		return "play_debug_attached"
	return "play_op"


func _checks(post: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	out.append(post)
	return out
