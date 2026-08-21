@tool
extends EditorPlugin

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _QueueScript: GDScript = preload("res://addons/hh_agent/core/hh_queue.gd")
const _RouterScript: GDScript = preload("res://addons/hh_agent/core/hh_router.gd")
const _SessionScript: GDScript = preload("res://addons/hh_agent/core/hh_session.gd")
const _ClientScript: GDScript = preload("res://addons/hh_agent/core/hh_bridge_client.gd")
const _DockScript: GDScript = preload("res://addons/hh_agent/ui/health/hh_health_dock.gd")

## hh_agent EditorPlugin: main-thread router + health dock + outbound sidecar client.
## Disable/reload must not leak sockets, signals, docks, or timers.

const PLUGIN_PRINT: String = "[hh_agent]"

var _actions: HHAgentActions
var _queue: HHAgentQueue
var _router: HHAgentRouter
var _session: HHAgentSession
var _client: HHAgentBridgeClient
var _dock: HHAgentHealthDock
var _reconnect_timer: Timer
var _busy: bool = false
var _paused: bool = false
var _bridge_pid: int = 0
var _reconnect_attempt: int = 0


func _enter_tree() -> void:
	set_process(true)
	_actions = HHAgentActions.new()
	if not _actions.load_from_res():
		push_warning("%s catalog failed to load" % PLUGIN_PRINT)
	_queue = HHAgentQueue.new()
	_router = HHAgentRouter.new()
	_session = HHAgentSession.new()
	_client = HHAgentBridgeClient.new()
	_client.set_enqueue(Callable(self, "_enqueue_inbound"))
	_client.set_hello_handler(Callable(self, "_on_hello"))
	_dock = HHAgentHealthDock.new()
	add_control_to_dock(DOCK_SLOT_LEFT_UL, _dock)
	_reconnect_timer = Timer.new()
	_reconnect_timer.one_shot = true
	_reconnect_timer.timeout.connect(_on_reconnect_timeout)
	add_child(_reconnect_timer)
	_try_connect()
	_refresh_dock()
	print("%s event=enter" % PLUGIN_PRINT)
	_maybe_run_selftest()


func _exit_tree() -> void:
	_cleanup()
	print("%s event=exit" % PLUGIN_PRINT)


func _process(_delta: float) -> void:
	if _client != null:
		_client.poll()
	if _busy:
		_refresh_dock()
		return
	var n: int = 0
	while n < HHAgentConstants.DRAIN_PER_FRAME:
		if _queue == null:
			break
		var item: Dictionary = _queue.take()
		if item.is_empty():
			break
		_busy = true
		_handle_item(item)
		_busy = false
		n += 1
	_refresh_dock()


func _enqueue_inbound(envelope: Variant) -> bool:
	if _queue == null or typeof(envelope) != TYPE_DICTIONARY:
		return false
	return _queue.push_request({"envelope": envelope})


func _handle_item(item: Dictionary) -> void:
	var queued_at: int = int(item.get("_queued_at_ms", 0))
	var envelope_v: Variant = item.get("envelope", {})
	var result: Dictionary = _router.dispatch(envelope_v, _actions, queued_at)
	if _client != null:
		_client.send_dict(result)


func _maybe_run_selftest() -> void:
	if OS.get_environment("HH_AGENT_SELFTEST") != "1":
		return
	var failures: PackedStringArray = PackedStringArray()
	if _router == null or _actions == null:
		failures.append("router or catalog missing")
	else:
		failures = _router.run_selftest(_actions)
	var passed: bool = failures.is_empty()
	var summary: String = "HH_AGENT_SELFTEST=PASS" if passed else "HH_AGENT_SELFTEST=FAIL"
	print("%s %s" % [PLUGIN_PRINT, summary])
	for item: String in failures:
		print("%s   - %s" % [PLUGIN_PRINT, item])
	var out_dir: String = OS.get_environment("HH_AGENT_SELFTEST_OUT")
	if not out_dir.is_empty():
		var path: String = "%s/hh_agent_selftest.txt" % out_dir
		var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
		if f != null:
			f.store_string(summary + "\n")
			for item: String in failures:
				f.store_string("%s\n" % item)
			f.flush()
			f.close()
	var tree: SceneTree = get_tree()
	if tree != null:
		tree.quit(0 if passed else 1)


func _try_connect() -> void:
	if _session == null or _client == null:
		return
	var desc: Dictionary = _session.load_descriptor()
	if desc.is_empty() or not _session.has_token(desc):
		_schedule_reconnect()
		return
	var host: String = str(desc.get("host", ""))
	var port: int = int(desc.get("port", 0))
	var project_id: String = str(desc.get("project_id", ""))
	var token: String = str(desc.get("token", ""))
	_bridge_pid = int(desc.get("pid", 0))
	_client.configure(host, port, project_id, token)
	var err: Error = _client.start()
	if err != OK:
		_schedule_reconnect()


func _on_hello(ok: bool) -> void:
	if ok:
		_reconnect_attempt = 0
		if _reconnect_timer != null:
			_reconnect_timer.stop()
		print("%s event=hello_ok" % PLUGIN_PRINT)
	else:
		print("%s event=hello_err" % PLUGIN_PRINT)
		_schedule_reconnect()
	_refresh_dock()


func _on_reconnect_timeout() -> void:
	if _client != null and _client.is_ready():
		return
	_try_connect()


func _schedule_reconnect() -> void:
	if _reconnect_timer == null:
		return
	var wait_ms: int = HHAgentConstants.RECONNECT_BASE_MS
	var i: int = 0
	while i < _reconnect_attempt and wait_ms < HHAgentConstants.RECONNECT_CAP_MS:
		wait_ms *= 2
		i += 1
	if wait_ms > HHAgentConstants.RECONNECT_CAP_MS:
		wait_ms = HHAgentConstants.RECONNECT_CAP_MS
	_reconnect_attempt += 1
	_reconnect_timer.stop()
	_reconnect_timer.wait_time = float(wait_ms) / 1000.0
	_reconnect_timer.start()


func _refresh_dock() -> void:
	if _dock == null:
		return
	var version_info: Dictionary = Engine.get_version_info()
	var version: String = "%s / plugin %s / godot %s" % [
		HHAgentConstants.PROTOCOL,
		HHAgentConstants.PLUGIN_VERSION,
		str(version_info.get("string", "")),
	]
	var project_name: String = str(ProjectSettings.get_setting("application/config/name", ""))
	var project_id: String = ""
	if _client != null:
		project_id = _client.project_id()
	if project_id.is_empty() and _session != null:
		project_id = _session.computed_project_id()
	var project: String = "%s (%s)" % [project_name, project_id]
	var bridge: String = "disconnected"
	if _client != null and _client.is_ready():
		bridge = "connected %s:%d pid=%d" % [_client.host(), _client.port(), _bridge_pid]
	elif _client != null and not _client.host().is_empty():
		bridge = "connecting %s:%d" % [_client.host(), _client.port()]
	var pause_status: String = "active" if _paused else "inactive"
	_dock.set_status({
		"version": version,
		"project": project,
		"bridge": bridge,
		"policy": HHAgentConstants.POLICY_DISPLAY,
		"queue": _queue.depth() if _queue != null else 0,
		"pause": pause_status,
	})


func _cleanup() -> void:
	set_process(false)
	if _reconnect_timer != null:
		if _reconnect_timer.timeout.is_connected(_on_reconnect_timeout):
			_reconnect_timer.timeout.disconnect(_on_reconnect_timeout)
		_reconnect_timer.stop()
		remove_child(_reconnect_timer)
		_reconnect_timer.queue_free()
		_reconnect_timer = null
	if _client != null:
		_client.set_enqueue(Callable())
		_client.set_hello_handler(Callable())
		_client.close()
		_client = null
	if _queue != null:
		_queue.clear()
		_queue = null
	if _dock != null:
		remove_control_from_docks(_dock)
		_dock.queue_free()
		_dock = null
	_router = null
	_session = null
	_actions = null
	_busy = false
	_bridge_pid = 0
