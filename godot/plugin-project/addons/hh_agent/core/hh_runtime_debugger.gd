class_name HHAgentRuntimeDebugger
extends EditorDebuggerPlugin

## Second debugger plugin. Captures only the hh_runtime prefix. Never steals
## stock error/output. Never returns the literal true. Never uses the
## game-side debugger singleton from this editor plugin.

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")

const HH_RUNTIME: String = "hh_runtime"

static var _current: HHAgentRuntimeDebugger

var _session_id: int = -1
var _session_ids: Array[int] = []
var _replies: Dictionary = {}


func _init() -> void:
	_current = self


static func current() -> HHAgentRuntimeDebugger:
	return _current


func detach() -> void:
	if _current == self:
		_current = null
	_replies.clear()
	_session_ids.clear()
	_session_id = -1


func _has_capture(capture: String) -> bool:
	return capture == HH_RUNTIME or capture.begins_with(HH_RUNTIME)


func _capture(message: String, data: Array, session_id: int) -> bool:
	if message.begins_with(HH_RUNTIME):
		_note_reply(message, data, session_id)
	return false


func _setup_session(session_id: int) -> void:
	if not _session_ids.has(session_id):
		_session_ids.append(session_id)
	_session_id = session_id
	var session: EditorDebuggerSession = get_session(session_id)
	if session == null:
		return
	if not session.started.is_connected(_on_session_started):
		session.started.connect(_on_session_started.bind(session_id))
	if not session.stopped.is_connected(_on_session_stopped):
		session.stopped.connect(_on_session_stopped.bind(session_id))


func _on_session_started(session_id: int) -> void:
	_session_id = session_id
	if not _session_ids.has(session_id):
		_session_ids.append(session_id)
	var play: HHAgentPlayAdapter = HHAgentPlayAdapter.current()
	if play != null:
		play.note_session_started(session_id)


func _on_session_stopped(session_id: int) -> void:
	if session_id == _session_id:
		_session_id = -1


func send_payload(message: String, data: Array) -> bool:
	var sent: bool = false
	if has_method("get_sessions"):
		var sessions: Array = get_sessions()
		var s: int = 0
		while s < sessions.size():
			var live: EditorDebuggerSession = sessions[s] as EditorDebuggerSession
			s += 1
			if live != null and live.is_active():
				live.send_message(message, data)
				sent = true
	var ids: Array[int] = _session_ids.duplicate()
	if _session_id >= 0 and not ids.has(_session_id):
		ids.append(_session_id)
	var i: int = 0
	while i < ids.size():
		var sid: int = ids[i]
		i += 1
		var session: EditorDebuggerSession = get_session(sid)
		if session != null and session.is_active():
			session.send_message(message, data)
			sent = true
	return sent


func has_active_session() -> bool:
	var i: int = 0
	while i < _session_ids.size():
		var session: EditorDebuggerSession = get_session(_session_ids[i])
		i += 1
		if session != null and session.is_active():
			return session.is_active()
	if _session_id < 0:
		return false
	var cur: EditorDebuggerSession = get_session(_session_id)
	return cur != null and cur.is_active()


func take_reply(token: String) -> Dictionary:
	if token.is_empty() or not _replies.has(token):
		return {}
	var payload_v: Variant = _replies[token]
	_replies.erase(token)
	if payload_v is Dictionary:
		return payload_v
	return {}


func _note_reply(_message: String, data: Array, session_id: int) -> void:
	_session_id = session_id
	var play: HHAgentPlayAdapter = HHAgentPlayAdapter.current()
	if play != null:
		play.note_debugger_message(_message, data, session_id)
	var payload: Dictionary = {}
	if data.size() > 0:
		if typeof(data[0]) == TYPE_DICTIONARY:
			payload = data[0]
		elif typeof(data[0]) == TYPE_STRING:
			var parsed: Variant = JSON.parse_string(str(data[0]))
			if parsed is Dictionary:
				payload = parsed
	var token: String = str(payload.get("token", ""))
	if token.is_empty():
		return
	_replies[token] = payload
