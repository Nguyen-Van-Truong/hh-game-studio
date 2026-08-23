class_name HHAgentPlayDebugger
extends EditorDebuggerPlugin

## Observes stock debugger sessions for Play logs. Never steals built-in
## error/output/performance captures (return false from _capture).
## Session.started is "debug attached" — do not use the game-side debugger
## singleton from this editor plugin. Catalog: coordinator-owned generated
## plugin-validator.json / mcp-tools.json.

const BUILTIN_ERROR: String = "error"
const BUILTIN_OUTPUT: String = "output"
const BUILTIN_PERF: String = "performance"
const HH_PLAY: String = "hh_play"


func _has_capture(capture: String) -> bool:
	return (
		capture == HH_PLAY
		or capture == BUILTIN_ERROR
		or capture == BUILTIN_OUTPUT
		or capture == BUILTIN_PERF
	)


func _capture(message: String, data: Array, session_id: int) -> bool:
	var play: HHAgentPlayAdapter = HHAgentPlayAdapter.current()
	if play != null:
		play.note_debugger_message(message, data, session_id)
	# Do not steal stock debugger captures.
	if (
		message == BUILTIN_ERROR
		or message.begins_with("error:")
		or message == BUILTIN_OUTPUT
		or message.begins_with("output:")
		or message == BUILTIN_PERF
		or message.begins_with("performance:")
	):
		return false
	return false


func _setup_session(session_id: int) -> void:
	var session: EditorDebuggerSession = get_session(session_id)
	if session == null:
		return
	if not session.started.is_connected(_on_session_started):
		session.started.connect(_on_session_started.bind(session_id))
	if not session.stopped.is_connected(_on_session_stopped):
		session.stopped.connect(_on_session_stopped.bind(session_id))
	var play: HHAgentPlayAdapter = HHAgentPlayAdapter.current()
	if play != null:
		play.note_session_setup(session_id, session.is_active())


func _on_session_started(session_id: int) -> void:
	var session: EditorDebuggerSession = get_session(session_id)
	if session != null:
		session.toggle_profiler("performance", true)
	var play: HHAgentPlayAdapter = HHAgentPlayAdapter.current()
	if play != null:
		play.note_session_started(session_id)


func _on_session_stopped(session_id: int) -> void:
	var play: HHAgentPlayAdapter = HHAgentPlayAdapter.current()
	if play != null:
		play.note_session_stopped(session_id)
