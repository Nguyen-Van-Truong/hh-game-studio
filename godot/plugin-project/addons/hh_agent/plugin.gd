@tool
extends EditorPlugin

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _QueueScript: GDScript = preload("res://addons/hh_agent/core/hh_queue.gd")
const _RouterScript: GDScript = preload("res://addons/hh_agent/core/hh_router.gd")
const _SessionScript: GDScript = preload("res://addons/hh_agent/core/hh_session.gd")
const _ClientScript: GDScript = preload("res://addons/hh_agent/core/hh_bridge_client.gd")
const _PostScript: GDScript = preload("res://addons/hh_agent/core/hh_postcondition.gd")
const _DockScript: GDScript = preload("res://addons/hh_agent/ui/health/hh_activity_dock.gd")
const _StoreScript: GDScript = preload("res://addons/hh_agent/core/hh_activity_store.gd")
const _ReviewStoreScript: GDScript = preload("res://addons/hh_agent/core/hh_review_store.gd")
const _ReviewDockScript: GDScript = preload("res://addons/hh_agent/ui/review/hh_review_dock.gd")
const _OverlayScript: GDScript = preload("res://addons/hh_agent/ui/overlay/hh_overlay.gd")
const _SchedulerScript: GDScript = preload("res://addons/hh_agent/core/hh_scheduler.gd")
const _PauseScript: GDScript = preload("res://addons/hh_agent/core/hh_pause.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _PresenterScript: GDScript = preload("res://addons/hh_agent/core/hh_presenter.gd")
const _PlayScript: GDScript = preload("res://addons/hh_agent/core/hh_play_adapter.gd")
const _PlayDbgScript: GDScript = preload("res://addons/hh_agent/core/hh_play_debugger.gd")
const _RuntimeScript: GDScript = preload("res://addons/hh_agent/core/hh_runtime_adapter.gd")
const _RuntimeDbgScript: GDScript = preload("res://addons/hh_agent/core/hh_runtime_debugger.gd")
const _TestScript: GDScript = preload("res://addons/hh_agent/core/hh_test_adapter.gd")
const _RepairScript: GDScript = preload("res://addons/hh_agent/core/hh_repair_adapter.gd")
const _PlanScript: GDScript = preload("res://addons/hh_agent/core/hh_plan_adapter.gd")
const _OrchScript: GDScript = preload("res://addons/hh_agent/core/hh_orchestrator_adapter.gd")
const _SoakScript: GDScript = preload("res://addons/hh_agent/core/hh_soak_adapter.gd")
const _MultiAgentScript: GDScript = preload("res://addons/hh_agent/core/hh_multi_agent_adapter.gd")
const _ExportScript: GDScript = preload("res://addons/hh_agent/core/hh_export_plugin.gd")
const _ExportAdapterScript: GDScript = preload("res://addons/hh_agent/core/hh_export_adapter.gd")

## hh_agent EditorPlugin: main-thread router + activity/review docks + outbound sidecar client.
## Disable/reload must not leak sockets, signals, docks, or timers.

const PLUGIN_PRINT: String = "[hh_agent]"

var _actions: HHAgentActions
var _queue: HHAgentQueue
var _router: HHAgentRouter
var _session: HHAgentSession
var _client: HHAgentBridgeClient
var _postcondition: HHAgentPostcondition
var _dock: HHAgentActivityDock
var _store: HHAgentActivityStore
var _review_store: HHAgentReviewStore
var _review: HHAgentReviewDock
var _overlay: HHAgentOverlay
var _scheduler: HHAgentScheduler
var _pause_gate: HHAgentPauseGate
var _errors: HHAgentErrors
var _reconnect_timer: Timer
var _busy: bool = false
var _paused: bool = false
var _bridge_pid: int = 0
var _reconnect_attempt: int = 0
var _last_pause_ack: Dictionary = {}
var _play: HHAgentPlayAdapter
var _play_debugger: EditorDebuggerPlugin
var _play_wait: Dictionary = {}
var _runtime: HHAgentRuntimeAdapter
var _runtime_debugger: EditorDebuggerPlugin
var _export_plugin: EditorExportPlugin
var _export: HHAgentExportAdapter
var _export_wait: Dictionary = {}
var _runtime_wait: Dictionary = {}
var _test: HHAgentTestAdapter
var _test_wait: Dictionary = {}
var _repair: HHAgentRepairAdapter
var _repair_wait: Dictionary = {}
var _plan: HHAgentPlanAdapter
var _orch: HHAgentOrchestratorAdapter
var _soak: HHAgentSoakAdapter
var _multi_agent
var _project_text_before_runtime: String = ""
var _runtime_autoload_on: bool = false


func _enter_tree() -> void:
	set_process(true)
	_actions = HHAgentActions.new()
	if not _actions.load_from_res():
		push_warning("%s catalog failed to load" % PLUGIN_PRINT)
	_queue = HHAgentQueue.new()
	_router = HHAgentRouter.new()
	_session = HHAgentSession.new()
	_client = HHAgentBridgeClient.new()
	_postcondition = HHAgentPostcondition.new()
	_pause_gate = HHAgentPauseGate.new()
	_errors = HHAgentErrors.new()
	_store = HHAgentActivityStore.new()
	_store.attach()
	_store.load_from_disk()
	_review_store = HHAgentReviewStore.new()
	_review_store.attach()
	_overlay = HHAgentOverlay.new()
	_overlay.attach()
	_overlay.set_mode(_store.mode())
	_scheduler = HHAgentScheduler.new()
	_scheduler.attach()
	_scheduler.set_mode(_store.mode())
	_play = HHAgentPlayAdapter.new()
	_play.attach()
	_play.set_runtime_autoload_hooks(
		Callable(self, "_install_runtime_autoload"),
		Callable(self, "_remove_runtime_autoload"),
	)
	_runtime = HHAgentRuntimeAdapter.new()
	_runtime.attach()
	_export = HHAgentExportAdapter.new()
	_export.attach()
	_test = HHAgentTestAdapter.new()
	_test.attach()
	_repair = HHAgentRepairAdapter.new()
	_repair.attach()
	_plan = HHAgentPlanAdapter.new()
	_plan.attach()
	_orch = HHAgentOrchestratorAdapter.new()
	_orch.attach()
	_soak = HHAgentSoakAdapter.new()
	_soak.attach()
	_multi_agent = _MultiAgentScript.new()
	_multi_agent.attach()
	_play_debugger = HHAgentPlayDebugger.new()
	add_debugger_plugin(_play_debugger)
	_runtime_debugger = HHAgentRuntimeDebugger.new()
	add_debugger_plugin(_runtime_debugger)
	_export_plugin = HHAgentExportPlugin.new()
	add_export_plugin(_export_plugin)
	set_force_draw_over_forwarding_enabled()
	_client.set_enqueue(Callable(self, "_enqueue_inbound"))
	_client.set_hello_handler(Callable(self, "_on_hello"))
	_client.set_readback(Callable(self, "_on_readback"))
	_client.set_pause_handler(Callable(self, "_on_sidecar_pause"))
	_dock = HHAgentActivityDock.new()
	_dock.pause_requested.connect(_on_pause_requested)
	_dock.pause_on_requested.connect(_on_pause_on_requested)
	_dock.resume_requested.connect(_on_resume_requested)
	_dock.mode_changed.connect(_on_mode_changed)
	add_control_to_dock(DOCK_SLOT_LEFT_UL, _dock)
	_review = HHAgentReviewDock.new()
	_review.view_changed.connect(_on_review_view)
	_review.replay_requested.connect(_on_review_replay)
	_review.revert_requested.connect(_on_review_revert)
	add_control_to_dock(DOCK_SLOT_LEFT_BL, _review)
	_reconnect_timer = Timer.new()
	_reconnect_timer.one_shot = true
	_reconnect_timer.timeout.connect(_on_reconnect_timeout)
	add_child(_reconnect_timer)
	_try_connect()
	_refresh_dock()
	_refresh_review()
	print("%s event=enter" % PLUGIN_PRINT)
	_maybe_open_read_fixture()
	_maybe_run_selftest()


func _exit_tree() -> void:
	_cleanup()
	print("%s event=exit" % PLUGIN_PRINT)


func _process(_delta: float) -> void:
	if _client != null:
		_client.poll()
		# Sidecar exit used to leave the dock on "disconnected" forever.
		if _client.is_closed() and (_reconnect_timer == null or _reconnect_timer.is_stopped()):
			_schedule_reconnect()
	if _play != null:
		_play.tick_watchdog()
	if not _play_wait.is_empty():
		_poll_play_wait()
	if not _runtime_wait.is_empty():
		_poll_runtime_wait()
	if not _test_wait.is_empty():
		_poll_test_wait()
	if not _repair_wait.is_empty():
		_poll_repair_wait()
	if not _export_wait.is_empty():
		_poll_export_wait()
	var inbound_this_frame: bool = false
	if not _busy:
		var n: int = 0
		while n < HHAgentConstants.DRAIN_PER_FRAME:
			if _queue == null:
				break
			var item: Dictionary = _queue.take()
			if item.is_empty():
				break
			inbound_this_frame = true
			_busy = true
			_handle_item(item)
			if (
				not _play_wait.is_empty()
				or not _runtime_wait.is_empty()
				or not _test_wait.is_empty()
				or not _repair_wait.is_empty()
				or not _export_wait.is_empty()
			):
				break
			_busy = false
			n += 1
	if _scheduler != null:
		_scheduler.tick(_delta, inbound_this_frame or _busy)
	if _overlay != null:
		_overlay.tick(_delta)
		if _overlay.is_draw_enabled():
			update_overlays()
	_refresh_dock()
	_refresh_review()


func _enqueue_inbound(envelope: Variant) -> bool:
	if _queue == null or typeof(envelope) != TYPE_DICTIONARY:
		return false
	return _queue.push_request({"envelope": envelope})


func _on_pause_requested() -> void:
	_last_pause_ack = _apply_pause(not _paused)


func _on_pause_on_requested() -> void:
	_last_pause_ack = _apply_pause(true)


func _on_resume_requested() -> void:
	_last_pause_ack = _apply_pause(false)


func _forward_canvas_draw_over_viewport(overlay: Control) -> void:
	_draw_overlay_2d(overlay)


func _forward_canvas_force_draw_over_viewport(overlay: Control) -> void:
	_draw_overlay_2d(overlay)


func _forward_3d_draw_over_viewport(viewport_control: Control) -> void:
	_draw_overlay_3d(viewport_control)


func _forward_3d_force_draw_over_viewport(viewport_control: Control) -> void:
	_draw_overlay_3d(viewport_control)


func _draw_overlay_2d(overlay: Control) -> void:
	if _overlay == null:
		return
	_overlay.draw_canvas(overlay)


func _draw_overlay_3d(viewport_control: Control) -> void:
	if _overlay == null:
		return
	_overlay.draw_spatial(viewport_control)


func _on_mode_changed(mode: String) -> void:
	if _store != null:
		_store.set_mode(mode)
	if _overlay != null:
		_overlay.set_mode(mode)
	if _scheduler != null:
		_scheduler.set_mode(mode)
	_refresh_dock()


func _on_sidecar_pause(paused: bool) -> void:
	_apply_pause(paused, false)


func _apply_pause(paused: bool, notify_sidecar: bool = true) -> Dictionary:
	var t0: int = Time.get_ticks_usec()
	_paused = paused
	var ack: Dictionary = {}
	if _pause_gate != null:
		ack = _pause_gate.set_paused(paused)
	if _paused:
		_drain_mutating()
	var ack_ms: float = float(Time.get_ticks_usec() - t0) / 1000.0
	if ack.is_empty():
		ack = {"paused": _paused, "state": "draining" if _paused else "open", "ack_ms": ack_ms}
	else:
		ack["ack_ms"] = ack_ms
	if notify_sidecar and _client != null:
		_client.send_dict({
			"type": HHAgentConstants.PAUSE_TYPE,
			"paused": _paused,
			"ack_ms": ack_ms,
			"state": str(ack.get("state", "")),
		})
	_refresh_dock()
	return ack


func _envelope_side_effect(envelope_v: Variant) -> String:
	if _actions == null or typeof(envelope_v) != TYPE_DICTIONARY:
		return ""
	var envelope: Dictionary = envelope_v
	var def: Dictionary = _actions.lookup(str(envelope.get("method", "")), str(envelope.get("action", "")))
	return str(def.get("side_effect", ""))


func _item_is_mutating(item: Dictionary) -> bool:
	var side: String = _envelope_side_effect(item.get("envelope", {}))
	return side == "mutate" or side == "destructive" or side == "external"


func _drain_mutating() -> void:
	if _queue == null or _errors == null:
		return
	var rejected: Array[Dictionary] = _queue.drain_mutating(Callable(self, "_item_is_mutating"))
	for item: Dictionary in rejected:
		var envelope_v: Variant = item.get("envelope", {})
		var command_id: String = ""
		if envelope_v is Dictionary:
			command_id = str((envelope_v as Dictionary).get("command_id", ""))
		var result: Dictionary = _errors.fail(command_id, HHAgentErrors.E_PAUSED, "mutation gate is paused", "pause")
		if _postcondition != null:
			_postcondition.remember(command_id, result)
		_record_result(item, result, HHAgentConstants.STATUS_FAILED)
		if _client != null:
			_client.send_dict(result)


func _handle_item(item: Dictionary) -> void:
	var queued_at: int = int(item.get("_queued_at_ms", 0))
	var envelope_v: Variant = item.get("envelope", {})
	_record_planned(item)
	var result: Dictionary = _router.dispatch(envelope_v, _actions, queued_at, _pause_gate)
	if result.get("_hh_play_pending", false) == true:
		_play_wait = {"item": item, "command_id": str(result.get("command_id", ""))}
		return
	if result.get("_hh_runtime_pending", false) == true:
		_runtime_wait = {"item": item, "command_id": str(result.get("command_id", ""))}
		return
	if result.get("_hh_test_pending", false) == true:
		_test_wait = {"item": item, "command_id": str(result.get("command_id", ""))}
		return
	if result.get("_hh_repair_pending", false) == true:
		_repair_wait = {"item": item, "command_id": str(result.get("command_id", ""))}
		return
	if result.get("_hh_export_pending", false) == true:
		_export_wait = {"item": item, "command_id": str(result.get("command_id", ""))}
		return
	_finish_item(item, result)


func _poll_play_wait() -> void:
	if _play == null:
		_finish_play_wait(_errors.fail(str(_play_wait.get("command_id", "")), HHAgentErrors.E_UNVERIFIED, "play adapter gone", "play"))
		return
	var result: Dictionary = _play.poll_pending()
	if result.is_empty() or result.get("_hh_play_pending", false) == true:
		return
	_finish_play_wait(result)


func _finish_play_wait(result: Dictionary) -> void:
	var item_v: Variant = _play_wait.get("item", {})
	var item: Dictionary = item_v if item_v is Dictionary else {}
	_play_wait = {}
	_busy = false
	_finish_item(item, result)


func _poll_runtime_wait() -> void:
	if _runtime == null:
		_finish_runtime_wait(
			_errors.fail(
				str(_runtime_wait.get("command_id", "")),
				HHAgentErrors.E_UNVERIFIED,
				"runtime adapter gone",
				"runtime",
			)
		)
		return
	var result: Dictionary = _runtime.poll_pending()
	if result.is_empty() or result.get("_hh_runtime_pending", false) == true:
		return
	_finish_runtime_wait(result)


func _finish_runtime_wait(result: Dictionary) -> void:
	var item_v: Variant = _runtime_wait.get("item", {})
	var item: Dictionary = item_v if item_v is Dictionary else {}
	_runtime_wait = {}
	_busy = false
	_finish_item(item, result)


func _poll_test_wait() -> void:
	if _test == null:
		_finish_test_wait(
			_errors.fail(
				str(_test_wait.get("command_id", "")),
				HHAgentErrors.E_UNVERIFIED,
				"test adapter gone",
				"test",
			)
		)
		return
	var result: Dictionary = _test.poll_pending()
	if result.is_empty() or result.get("_hh_test_pending", false) == true:
		return
	_finish_test_wait(result)


func _finish_test_wait(result: Dictionary) -> void:
	var item_v: Variant = _test_wait.get("item", {})
	var item: Dictionary = item_v if item_v is Dictionary else {}
	_test_wait = {}
	_busy = false
	_finish_item(item, result)


func _poll_repair_wait() -> void:
	if _repair == null:
		_finish_repair_wait(
			_errors.fail(
				str(_repair_wait.get("command_id", "")),
				HHAgentErrors.E_UNVERIFIED,
				"repair adapter gone",
				"repair",
			)
		)
		return
	var result: Dictionary = _repair.poll_pending()
	if result.is_empty() or result.get("_hh_repair_pending", false) == true:
		return
	_finish_repair_wait(result)


func _finish_repair_wait(result: Dictionary) -> void:
	var item_v: Variant = _repair_wait.get("item", {})
	var item: Dictionary = item_v if item_v is Dictionary else {}
	_repair_wait = {}
	_busy = false
	_finish_item(item, result)


func _poll_export_wait() -> void:
	if _export == null:
		_finish_export_wait(
			_errors.fail(
				str(_export_wait.get("command_id", "")),
				HHAgentErrors.E_UNVERIFIED,
				"export adapter gone",
				"export",
			)
		)
		return
	var result: Dictionary = _export.poll_pending()
	if result.is_empty() or result.get("_hh_export_pending", false) == true:
		return
	_finish_export_wait(result)


func _finish_export_wait(result: Dictionary) -> void:
	var item_v: Variant = _export_wait.get("item", {})
	var item: Dictionary = item_v if item_v is Dictionary else {}
	_export_wait = {}
	_busy = false
	_finish_item(item, result)


func _finish_item(item: Dictionary, result: Dictionary) -> void:
	if _postcondition != null:
		_postcondition.remember(str(result.get("command_id", "")), result)
	var status: String = HHAgentConstants.STATUS_VERIFIED if result.get("ok", false) == true else HHAgentConstants.STATUS_FAILED
	_record_result(item, result, status)
	if _client != null:
		_client.send_dict(result)


func _mutating_side(envelope_v: Variant) -> bool:
	var side: String = _envelope_side_effect(envelope_v)
	return side == "mutate" or side == "destructive" or side == "external"


func _record_planned(item: Dictionary) -> void:
	if _store == null or not _mutating_side(item.get("envelope", {})):
		return
	var row: Dictionary = _row_from_item(item, {}, HHAgentConstants.STATUS_PLANNED)
	if str(row.get("command_id", "")).is_empty():
		return
	_store.record_planned(row)


func _record_result(item: Dictionary, result: Dictionary, status: String) -> void:
	if _store == null or not _mutating_side(item.get("envelope", {})):
		return
	var row: Dictionary = _row_from_item(item, result, status)
	if str(row.get("command_id", "")).is_empty():
		return
	_store.settle(row)


func _row_from_item(item: Dictionary, result: Dictionary, status: String) -> Dictionary:
	var envelope_v: Variant = item.get("envelope", {})
	var envelope: Dictionary = envelope_v if envelope_v is Dictionary else {}
	var params_v: Variant = envelope.get("params", {})
	var params: Dictionary = params_v if params_v is Dictionary else {}
	var method: String = str(envelope.get("method", ""))
	var action: String = str(envelope.get("action", ""))
	var command_id: String = str(result.get("command_id", envelope.get("command_id", "")))
	var scene: String = str(params.get("scene", ""))
	if scene.is_empty():
		scene = str(params.get("path", ""))
	var queued_at: int = int(item.get("_queued_at_ms", 0))
	var elapsed_ms: int = 0
	if queued_at > 0:
		elapsed_ms = maxi(0, Time.get_ticks_msec() - queued_at)
	var err_v: Variant = result.get("error", {})
	var err_code: String = ""
	if err_v is Dictionary:
		err_code = str((err_v as Dictionary).get("code", ""))
	var after_v: Variant = result.get("after", {})
	var after: Dictionary = after_v if after_v is Dictionary else {}
	var summary: String = _redacted_summary(method, action, params, err_code)
	return {
		"command_id": command_id,
		"action": ("%s.%s" % [method.trim_prefix("godot."), action]) if method.begins_with("godot.") else action,
		"method": method,
		"status": status,
		"scene": scene,
		"actor": HHAgentConstants.OBSERVER_ACTOR,
		"elapsed_ms": elapsed_ms,
		"summary": summary,
		"diff": _redacted_diff(action, params, after),
		"undo": str(result.get("undo_action", "")),
		"checkpoint": str(after.get("checkpoint", after.get("checkpoint_id", ""))),
		"evidence": str(after.get("evidence", after.get("evidence_uri", ""))),
		"error": err_code,
		"ok": result.get("ok", false) == true,
	}


func _redacted_summary(method: String, action: String, params: Dictionary, err_code: String) -> String:
	var parts: PackedStringArray = PackedStringArray()
	parts.append("%s.%s" % [method, action])
	var class_name_s: String = str(params.get("class_name", ""))
	if not class_name_s.is_empty():
		parts.append(class_name_s)
	var name_s: String = str(params.get("name", ""))
	if not name_s.is_empty():
		parts.append("name=%s" % name_s)
	var prop: String = str(params.get("property", ""))
	if not prop.is_empty():
		parts.append(prop)
	if not err_code.is_empty():
		parts.append(err_code)
	var raw: String = " ".join(parts)
	if _store != null:
		return _store.redact_text(raw)
	return raw


func _redacted_diff(action: String, params: Dictionary, after: Dictionary) -> String:
	var raw: String = ""
	if action == "add":
		raw = "+%s %s" % [str(params.get("class_name", "")), str(params.get("name", ""))]
	elif action == "set":
		raw = "%s -> %s" % [str(params.get("property", "")), str(after.get("property_hash", "set"))]
	elif action == "write":
		raw = "script %s" % str(params.get("path", ""))
	else:
		raw = action
	if _store != null:
		return _store.redact_text(raw)
	return raw


func _on_readback(command_id: String) -> Dictionary:
	if _postcondition == null:
		return {
			"type": HHAgentConstants.READBACK_RESULT_TYPE,
			"command_id": command_id,
			"found": false,
			"ok": false,
			"postcondition": {"verified": false, "checks": []},
		}
	return _postcondition.readback(command_id)


func _maybe_open_read_fixture() -> void:
	var scene_path: String = OS.get_environment("HH_READ_OPEN_SCENE")
	if scene_path.is_empty():
		return
	EditorInterface.open_scene_from_path(scene_path)
	print("%s event=open_read_fixture path=%s" % [PLUGIN_PRINT, scene_path])


func _maybe_run_selftest() -> void:
	if OS.get_environment("HH_AGENT_SELFTEST") != "1":
		return
	var failures: PackedStringArray = PackedStringArray()
	if _router == null or _actions == null:
		failures.append("router or catalog missing")
	else:
		failures = _router.run_selftest(_actions)
		var post: HHAgentPostcondition = HHAgentPostcondition.new()
		var noop: Dictionary = _router.dispatch(
			{
				"protocol": HHAgentConstants.PROTOCOL,
				"command_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
				"method": HHAgentConstants.NOOP_METHOD,
				"action": HHAgentConstants.NOOP_ACTION,
				"params": {},
			},
			_actions,
			0,
		)
		post.remember(str(noop.get("command_id", "")), noop)
		var rb: Dictionary = post.readback(str(noop.get("command_id", "")))
		if rb.get("found", false) != true:
			failures.append("postcondition readback")
	if _queue != null:
		var flood: int = 0
		_queue.clear()
		while flood < HHAgentConstants.MAX_QUEUE:
			if not _queue.push_request({"envelope": {"n": flood}}):
				failures.append("queue rejected before cap")
				break
			flood += 1
		if _queue.push_request({"envelope": {"n": flood}}):
			failures.append("queue must reject at MAX_QUEUE")
		_queue.clear()
	if _client != null:
		_client.configure(
			"127.0.0.1",
			1,
			"0123456789abcdef0123456789abcdef",
			"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
		)
		if _store != null:
			_store.add_secret("0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef")
		var start_err: Error = _client.start()
		if start_err == ERR_INVALID_PARAMETER or not _client.has_configured_token():
			failures.append("start() must not wipe the configured token")
		_client.close()
		if not _client.has_configured_token():
			failures.append("close() must keep configured credentials")
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
	if _store != null:
		_store.add_secret(token)
	var err: Error = _client.start()
	if err != OK:
		_schedule_reconnect()


func _on_hello(ok: bool) -> void:
	if ok:
		_reconnect_attempt = 0
		if _reconnect_timer != null:
			_reconnect_timer.stop()
		print("%s event=hello_ok" % PLUGIN_PRINT)
		if OS.get_environment("HH_PAUSE_WIRE_BENCH") == "1":
			call_deferred("_wire_pause_bench")
	else:
		print("%s event=hello_err" % PLUGIN_PRINT)
		_schedule_reconnect()
	_refresh_dock()
	_refresh_review()


func _on_review_view(view: String) -> void:
	if _review_store == null:
		return
	_review_store.remember_press(view)
	var snap: Dictionary = _review_store.open_view({"view": view})
	_present_review_view(view, snap)
	if _review != null:
		_review.set_status(_review_store.last_card())


func _on_review_replay(command_id: String) -> void:
	if _review != null and not command_id.is_empty():
		_review.set_selected_command_id(command_id)
	if _overlay != null:
		_overlay.replay_command(command_id)


func _on_review_revert() -> void:
	if _review_store == null:
		return
	var ref: String = _review_store.card_checkpoint_ref()
	# Same COW dest-hash restore as sidecar git.revert_checkpoint (R3). Not git reset --hard.
	var _ignored: Dictionary = _review_store.revert_checkpoint(ref)
	if _review != null:
		_review.set_status(_review_store.last_card())


func _present_review_view(view: String, snap: Dictionary) -> void:
	var path_s: String = ""
	var files_v: Variant = snap.get("files", [])
	var scenes_v: Variant = snap.get("scenes", [])
	if files_v is Array and not (files_v as Array).is_empty():
		path_s = str((files_v as Array)[0])
	elif scenes_v is Array and not (scenes_v as Array).is_empty():
		path_s = str((scenes_v as Array)[0])
	if path_s.is_empty():
		return
	if not path_s.begins_with("res://"):
		path_s = "res://%s" % path_s
	var presenter: HHAgentPresenter = HHAgentPresenter.new()
	var hint: Dictionary = {"filesystem_path": path_s}
	if path_s.ends_with(".gd") or path_s.ends_with(".cs"):
		hint["script_path"] = path_s
	elif path_s.ends_with(".tscn") and view != "diff":
		hint["scene"] = path_s
	presenter.apply_presentation(hint, {}, false)


func _wire_pause_bench() -> void:
	var samples: Array[float] = []
	var i: int = 0
	while i < 40:
		if _dock != null:
			_dock.emit_signal("pause_requested")
		else:
			_on_pause_requested()
		samples.append(float(_last_pause_ack.get("ack_ms", 0.0)))
		i += 1
	if not _paused:
		if _dock != null:
			_dock.emit_signal("pause_requested")
		else:
			_on_pause_requested()
	var sorted: Array[float] = samples.duplicate()
	sorted.sort()
	var idx: int = maxi(0, int(ceil(0.95 * float(sorted.size()))) - 1)
	var p95: float = 0.0
	if idx < sorted.size():
		p95 = sorted[idx]
	print("HH_PAUSE_WIRE %s" % JSON.stringify({
		"path": "hh_health_dock.pause_requested -> plugin.gd:_on_pause_requested",
		"samples": samples,
		"p95": p95,
		"paused": _paused,
	}))


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
	var queue_n: int = _queue.depth() if _queue != null else 0
	if _store != null:
		_store.set_runtime({
			"policy": HHAgentConstants.POLICY_DISPLAY,
			"queue": queue_n,
			"pause": pause_status,
			"agent": "hh_agent",
		})
	var dock_snap: Dictionary = {}
	if _store != null:
		var ui_cursor: String = str(maxi(0, _store.row_count() - HHAgentConstants.DEFAULT_PAGE))
		dock_snap = _store.snapshot({
			"detail": "short",
			"limit": HHAgentConstants.DEFAULT_PAGE,
			"cursor": ui_cursor,
		})
	_dock.set_status({
		"version": version,
		"project": project,
		"bridge": bridge,
		"policy": HHAgentConstants.POLICY_DISPLAY,
		"queue": queue_n,
		"pause": pause_status,
		"task": str(dock_snap.get("task", "idle")),
		"agent": str(dock_snap.get("agent", "hh_agent")),
		"job": str(dock_snap.get("job", "—")),
		"elapsed_ms": int(dock_snap.get("elapsed_ms", 0)),
		"mode": str(dock_snap.get("mode", HHAgentConstants.MODE_WATCH)),
		"dock": dock_snap,
		"rows": dock_snap.get("rows", {}),
	})


func _refresh_review() -> void:
	if _review == null:
		return
	var snap: Dictionary = {}
	if _review_store != null:
		snap = _review_store.last_card()
	if _store != null:
		var ids: PackedStringArray = _store.last_command_ids(20)
		var actions: Array = []
		for cid: String in ids:
			if not cid.is_empty():
				actions.append(cid)
		snap["actions"] = actions
	_review.set_status(snap)


func _install_runtime_autoload() -> void:
	# Never call add_autoload_singleton: it writes project.godot and the
	# editor reloads ~8s later, which kills Play. The Play process reads
	# autoloads from disk, so an in-memory name is not a proven probe.
	# Official Play attaches hh_agent_runtime.gd bytes as the played scene
	# script. This hook only snapshots and strips a leaked name.
	if _project_text_before_runtime.is_empty():
		_project_text_before_runtime = FileAccess.get_file_as_string("res://project.godot")
	_runtime_autoload_on = false
	_restore_project_godot_if_leaked()


func _remove_runtime_autoload() -> void:
	var key: String = "autoload/%s" % HHAgentConstants.RUNTIME_AUTOLOAD_NAME
	if _runtime_autoload_on or ProjectSettings.has_setting(key):
		remove_autoload_singleton(HHAgentConstants.RUNTIME_AUTOLOAD_NAME)
	if ProjectSettings.has_setting(key):
		ProjectSettings.clear(key)
	_runtime_autoload_on = false
	_restore_project_godot_if_leaked()


func _restore_project_godot_if_leaked() -> void:
	var path_s: String = ProjectSettings.globalize_path("res://project.godot")
	var now: String = FileAccess.get_file_as_string(path_s)
	if now.is_empty() or not now.contains("HHAgentRuntime"):
		return
	var restored: String = ""
	if (
		not _project_text_before_runtime.is_empty()
		and not _project_text_before_runtime.contains("HHAgentRuntime")
	):
		restored = _project_text_before_runtime
	else:
		restored = _strip_runtime_autoload_lines(now)
	if restored.is_empty() or restored.contains("HHAgentRuntime"):
		push_warning("%s refused to persist HHAgentRuntime in project.godot" % PLUGIN_PRINT)
		return
	var tmp: String = "%s.hh-runtime-tmp" % path_s
	var f: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		push_warning("%s could not drop HHAgentRuntime from project.godot" % PLUGIN_PRINT)
		return
	f.store_string(restored)
	f.flush()
	f.close()
	if DirAccess.rename_absolute(tmp, path_s) != OK:
		DirAccess.remove_absolute(tmp)
		push_warning("%s could not replace leaked project.godot" % PLUGIN_PRINT)
		return
	_project_text_before_runtime = ""


func _strip_runtime_autoload_lines(text: String) -> String:
	var kept: PackedStringArray = PackedStringArray()
	var lines: PackedStringArray = text.split("\n")
	var i: int = 0
	while i < lines.size():
		var line: String = lines[i]
		i += 1
		if line.contains("HHAgentRuntime") or line.contains("hh_agent_runtime"):
			continue
		kept.append(line)
	return "\n".join(kept)


func _cleanup() -> void:
	set_process(false)
	_remove_runtime_autoload()
	if _runtime_debugger != null:
		remove_debugger_plugin(_runtime_debugger)
		if _runtime_debugger is HHAgentRuntimeDebugger:
			(_runtime_debugger as HHAgentRuntimeDebugger).detach()
		_runtime_debugger = null
	if _export_plugin != null:
		remove_export_plugin(_export_plugin)
		_export_plugin = null
	if _export != null:
		_export.shutdown()
		_export = null
	_export_wait = {}
	if _runtime != null:
		_runtime.shutdown()
		_runtime = null
	_runtime_wait = {}
	if _test != null:
		_test.shutdown()
		_test = null
	_test_wait = {}
	if _repair != null:
		_repair.shutdown()
		_repair = null
	_repair_wait = {}
	if _plan != null:
		_plan.shutdown()
		_plan = null
	if _orch != null:
		_orch.shutdown()
		_orch = null
	if _soak != null:
		_soak.shutdown()
		_soak = null
	if _multi_agent != null:
		_multi_agent.shutdown()
		_multi_agent = null
	if _play_debugger != null:
		remove_debugger_plugin(_play_debugger)
		_play_debugger = null
	if _play != null:
		_play.shutdown()
		_play = null
	_play_wait = {}
	if _reconnect_timer != null:
		if _reconnect_timer.timeout.is_connected(_on_reconnect_timeout):
			_reconnect_timer.timeout.disconnect(_on_reconnect_timeout)
		_reconnect_timer.stop()
		remove_child(_reconnect_timer)
		_reconnect_timer.queue_free()
		_reconnect_timer = null
	if _overlay != null:
		_overlay.detach()
		_overlay = null
	if _scheduler != null:
		_scheduler.detach()
		_scheduler = null
	if _store != null:
		_store.persist()
		_store.detach()
		_store = null
	if _review_store != null:
		_review_store.detach()
		_review_store = null
	if _review != null:
		if _review.view_changed.is_connected(_on_review_view):
			_review.view_changed.disconnect(_on_review_view)
		if _review.replay_requested.is_connected(_on_review_replay):
			_review.replay_requested.disconnect(_on_review_replay)
		if _review.revert_requested.is_connected(_on_review_revert):
			_review.revert_requested.disconnect(_on_review_revert)
	if _dock != null:
		if _dock.pause_requested.is_connected(_on_pause_requested):
			_dock.pause_requested.disconnect(_on_pause_requested)
		if _dock.pause_on_requested.is_connected(_on_pause_on_requested):
			_dock.pause_on_requested.disconnect(_on_pause_on_requested)
		if _dock.resume_requested.is_connected(_on_resume_requested):
			_dock.resume_requested.disconnect(_on_resume_requested)
		if _dock.mode_changed.is_connected(_on_mode_changed):
			_dock.mode_changed.disconnect(_on_mode_changed)
	if _client != null:
		_client.set_enqueue(Callable())
		_client.set_hello_handler(Callable())
		_client.set_readback(Callable())
		_client.set_pause_handler(Callable())
		_client.close()
		_client = null
	_postcondition = null
	_pause_gate = null
	_errors = null
	if _queue != null:
		_queue.clear()
		_queue = null
	if _dock != null:
		remove_control_from_docks(_dock)
		_dock.queue_free()
		_dock = null
	if _review != null:
		remove_control_from_docks(_review)
		_review.queue_free()
		_review = null
	_router = null
	_session = null
	_actions = null
	_busy = false
	_bridge_pid = 0
