class_name HHAgentRouter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _EnvelopeScript: GDScript = preload("res://addons/hh_agent/core/hh_envelope.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _PauseScript: GDScript = preload("res://addons/hh_agent/core/hh_pause.gd")
const _ReadsScript: GDScript = preload("res://addons/hh_agent/core/hh_read_adapters.gd")
const _SceneScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_adapter.gd")
const _NodeScript: GDScript = preload("res://addons/hh_agent/core/hh_node_adapter.gd")
const _PropertyScript: GDScript = preload("res://addons/hh_agent/core/hh_property_adapter.gd")
const _ResourceScript: GDScript = preload("res://addons/hh_agent/core/hh_resource_adapter.gd")
const _SignalScript: GDScript = preload("res://addons/hh_agent/core/hh_signal_adapter.gd")
const _ScriptScript: GDScript = preload("res://addons/hh_agent/core/hh_script_adapter.gd")
const _AssetScript: GDScript = preload("res://addons/hh_agent/core/hh_asset_adapter.gd")
const _SettingsScript: GDScript = preload("res://addons/hh_agent/core/hh_settings_adapter.gd")
const _TxScript: GDScript = preload("res://addons/hh_agent/core/hh_transaction_adapter.gd")
const _CanvasScript: GDScript = preload("res://addons/hh_agent/core/hh_canvas_adapter.gd")
const _TilemapScript: GDScript = preload("res://addons/hh_agent/core/hh_tilemap_adapter.gd")
const _AnimationScript: GDScript = preload("res://addons/hh_agent/core/hh_animation_adapter.gd")
const _UiScript: GDScript = preload("res://addons/hh_agent/core/hh_ui_adapter.gd")
const _PhysicsScript: GDScript = preload("res://addons/hh_agent/core/hh_physics_adapter.gd")
const _AudioScript: GDScript = preload("res://addons/hh_agent/core/hh_audio_adapter.gd")
const _RenderScript: GDScript = preload("res://addons/hh_agent/core/hh_render_adapter.gd")
const _PlayScript: GDScript = preload("res://addons/hh_agent/core/hh_play_adapter.gd")
const _PresenterScript: GDScript = preload("res://addons/hh_agent/core/hh_presenter.gd")
const _OverlayScript: GDScript = preload("res://addons/hh_agent/ui/overlay/hh_overlay.gd")
const _SchedulerScript: GDScript = preload("res://addons/hh_agent/core/hh_scheduler.gd")
const _StoreScript: GDScript = preload("res://addons/hh_agent/core/hh_activity_store.gd")

## Routes read/view adapters, scene/node/property/resource/signal/script/asset/project/transaction/tilemap/animation/ui/physics/audio/render/play apply.

var _errors: HHAgentErrors = HHAgentErrors.new()
var _envelope: HHAgentEnvelope = HHAgentEnvelope.new()
var _reads: HHAgentReadAdapters = HHAgentReadAdapters.new()
var _scenes: HHAgentSceneAdapter = HHAgentSceneAdapter.new()
var _nodes: HHAgentNodeAdapter = HHAgentNodeAdapter.new()
var _props: HHAgentPropertyAdapter = HHAgentPropertyAdapter.new()
var _resources: HHAgentResourceAdapter = HHAgentResourceAdapter.new()
var _signals: HHAgentSignalAdapter = HHAgentSignalAdapter.new()
var _scripts: HHAgentScriptAdapter = HHAgentScriptAdapter.new()
var _assets: HHAgentAssetAdapter = HHAgentAssetAdapter.new()
var _settings: HHAgentSettingsAdapter = HHAgentSettingsAdapter.new()
var _tx: HHAgentTransactionAdapter = HHAgentTransactionAdapter.new()
var _canvas: HHAgentCanvasAdapter = HHAgentCanvasAdapter.new()
var _tilemap: HHAgentTilemapAdapter = HHAgentTilemapAdapter.new()
var _animation: HHAgentAnimationAdapter = HHAgentAnimationAdapter.new()
var _ui: HHAgentUiAdapter = HHAgentUiAdapter.new()
var _physics: HHAgentPhysicsAdapter = HHAgentPhysicsAdapter.new()
var _audio: HHAgentAudioAdapter = HHAgentAudioAdapter.new()
var _render: HHAgentRenderAdapter = HHAgentRenderAdapter.new()
var _play_local: HHAgentPlayAdapter = HHAgentPlayAdapter.new()
var _presenter: HHAgentPresenter = HHAgentPresenter.new()
var _overlay_local: HHAgentOverlay = HHAgentOverlay.new()
var _scheduler_local: HHAgentScheduler = HHAgentScheduler.new()


func dispatch(raw: Variant, actions: HHAgentActions, queued_at_ms: int, pause_gate: HHAgentPauseGate = null) -> Dictionary:
	var parsed: Dictionary = _envelope.parse(raw, actions)
	if parsed.get("ok", false) != true:
		var err_v: Variant = parsed.get("error", {})
		var err: Dictionary = err_v if err_v is Dictionary else {}
		var command_id: String = ""
		if raw is Dictionary:
			command_id = str((raw as Dictionary).get("command_id", ""))
		return _errors.fail(
			command_id,
			str(err.get("code", HHAgentErrors.E_INVALID_ENVELOPE)),
			str(err.get("message", "invalid envelope")),
			str(err.get("path", "")),
		)
	var envelope_v: Variant = parsed.get("envelope", {})
	var envelope: Dictionary = envelope_v if envelope_v is Dictionary else {}
	var command_id: String = str(envelope.get("command_id", ""))
	var method: String = str(envelope.get("method", ""))
	var action: String = str(envelope.get("action", ""))
	if actions.is_noop(method, action):
		return _errors.ok_noop(command_id)
	var def: Dictionary = actions.lookup(method, action)
	if def.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_UNKNOWN_ACTION, "unknown action", "action")
	var timeout_ms: int = int(def.get("timeout_ms", 5000))
	if queued_at_ms > 0:
		var waited: int = Time.get_ticks_msec() - queued_at_ms
		if waited > timeout_ms:
			return _errors.fail(command_id, HHAgentErrors.E_BUSY, "request timed out in queue", "")
	var params_v: Variant = envelope.get("params", {})
	var params: Dictionary = params_v if params_v is Dictionary else {}
	_sync_presentation_mode(envelope)
	var required_v: Variant = def.get("required", [])
	if required_v is Array:
		for field_v: Variant in required_v:
			var field: String = str(field_v)
			if field.is_empty():
				continue
			if not params.has(field):
				return _errors.fail(
					command_id,
					HHAgentErrors.E_MISSING_REQUIRED,
					"missing required param %s" % field,
					"params.%s" % field,
				)
	var side_effect: String = str(def.get("side_effect", ""))
	if pause_gate != null and not pause_gate.allows_side_effect(side_effect):
		return _errors.fail(command_id, HHAgentErrors.E_PAUSED, "mutation gate is paused", "pause")
	var pre: Dictionary = {}
	if envelope.has("precondition") and envelope.get("precondition") is Dictionary:
		pre = envelope.get("precondition") as Dictionary
	var result: Dictionary = {}
	if method == "godot.job" and action == "transaction":
		result = _tx.handle(command_id, method, action, params, actions, pre)
	elif method == "godot.scene" and action == "instantiate":
		result = _nodes.handle(command_id, method, action, params, actions, pre)
	elif method == "godot.node" and action != "query" and _nodes.handles(action):
		result = _nodes.handle(command_id, method, action, params, actions, pre)
	elif method == "godot.property" and action != "get" and _props.handles(action):
		result = _props.handle(command_id, method, action, params, actions, pre)
	elif method == "godot.resource" and action != "load" and action != "uid" and _resources.handles(action):
		result = _resources.handle(command_id, method, action, params, actions, pre)
	elif method == "godot.signal" and _signals.handles(action):
		result = _signals.handle(command_id, method, action, params, actions, pre)
	elif method == "godot.asset" and _assets.handles(action):
		result = _assets.handle(command_id, method, action, params, actions, pre, pause_gate)
	elif method == "godot.script" and _scripts.handles(action):
		result = _scripts.handle(command_id, method, action, params, actions, pre)
	elif method == "godot.project" and action != "inspect" and action != "doctor" and _settings.handles(action):
		result = _settings.handle(command_id, method, action, params, actions, pre)
	elif method == "godot.scene" and _scenes.handles(action):
		result = _scenes.handle(command_id, method, action, params, actions, pre)
	elif method == "godot.editor" and (action == "select" or action == "focus" or action == "main_screen"):
		result = _presenter.handle(command_id, method, action, params, actions, envelope)
	elif method == "godot.canvas" or method == "godot.camera":
		if _canvas.handles(method, action):
			result = _canvas.handle(command_id, method, action, params, actions, pre)
		else:
			return _errors.fail(command_id, HHAgentErrors.E_UNKNOWN_ACTION, "unknown canvas/camera action", "action")
	elif method == "godot.tilemap":
		if action == "query":
			result = _reads.handle(command_id, method, action, params, actions, envelope)
		elif _tilemap.handles(action):
			result = _tilemap.handle(command_id, method, action, params, actions, pre)
		else:
			return _errors.fail(command_id, HHAgentErrors.E_UNKNOWN_ACTION, "unknown tilemap action", "action")
	elif method == "godot.animation":
		if _animation.handles(action):
			result = _animation.handle(command_id, method, action, params, actions, pre)
		else:
			return _errors.fail(command_id, HHAgentErrors.E_UNKNOWN_ACTION, "unknown animation action", "action")
	elif method == "godot.ui":
		if _ui.handles(action):
			result = _ui.handle(command_id, method, action, params, actions, pre)
		else:
			return _errors.fail(command_id, HHAgentErrors.E_UNKNOWN_ACTION, "unknown ui action", "action")
	elif method == "godot.physics":
		if _physics.handles(action):
			result = _physics.handle(command_id, method, action, params, actions, pre)
		else:
			return _errors.fail(command_id, HHAgentErrors.E_UNKNOWN_ACTION, "unknown physics action", "action")
	elif method == "godot.audio":
		if _audio.handles(action):
			result = _audio.handle(command_id, method, action, params, actions, pre)
		else:
			return _errors.fail(command_id, HHAgentErrors.E_UNKNOWN_ACTION, "unknown audio action", "action")
	elif method == "godot.render":
		if _render.handles(action):
			result = _render.handle(command_id, method, action, params, actions, pre)
		else:
			return _errors.fail(command_id, HHAgentErrors.E_UNKNOWN_ACTION, "unknown render action", "action")
	elif method == "godot.play" and _play().handles(action):
		result = _play().handle(command_id, method, action, params, actions, pre)
	elif method == "godot.input":
		result = _input_apply(command_id, action, params, actions)
	elif method == "godot.runtime" and (action == "freeze" or action == "step"):
		result = _time_apply(command_id, action, params, actions)
	elif method == "godot.runtime" and (action == "screenshot" or action == "perf"):
		result = _capture_apply(command_id, action, params, actions)
	elif method == "godot.editor" and (action == "frame_view" or action == "replay"):
		result = _overlay().handle(command_id, method, action, params, actions, envelope)
	elif method == "godot.review" and action == "replay":
		result = _overlay().handle(command_id, method, action, params, actions, envelope)
	elif side_effect == "read" or side_effect == "view":
		result = _reads.handle(command_id, method, action, params, actions, envelope)
	else:
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not dispatched", "")
	result = _scheduler().after_success(result, method, action, params, envelope)
	return result


func run_selftest(actions: HHAgentActions) -> PackedStringArray:
	var failures: PackedStringArray = PackedStringArray()
	if not actions.loaded or actions.action_count() < 123:
		failures.append("catalog load")
	if not actions.allowed_fields.has("command_id"):
		failures.append("allowed missing command_id")
	if not actions.forbidden_fields.has("session_id") or not actions.forbidden_fields.has("policy"):
		failures.append("forbidden fields missing")
	var noop: Dictionary = dispatch(_sample(HHAgentConstants.NOOP_METHOD, "noop", {}), actions, 0)
	if noop.get("ok", false) != true:
		failures.append("noop should ACK")
	var post_v: Variant = noop.get("postcondition", {})
	if post_v is Dictionary:
		var checks_v: Variant = (post_v as Dictionary).get("checks", [])
		if not (checks_v is Array) or (checks_v as Array).is_empty():
			failures.append("noop postcondition")
	else:
		failures.append("noop postcondition")
	var missing: Dictionary = dispatch(_sample("godot.node", "add", {"class": "Node2D"}), actions, 0)
	if str(_error_of(missing).get("code", "")) != HHAgentErrors.E_MISSING_REQUIRED:
		failures.append("mutate missing required must be E_MISSING_REQUIRED")
	var mutate: Dictionary = dispatch(
		_sample(
			"godot.node",
			"add",
			{"scene": "res://main.tscn", "parent": ".", "class_name": "Node2D", "name": "X"},
		),
		actions,
		0,
	)
	var mutate_err: Dictionary = _error_of(mutate)
	if mutate.get("ok", true) == true:
		failures.append("node.add on missing scene must not paper-ok")
	if str(mutate_err.get("code", "")) == "":
		failures.append("node.add on missing scene must be a typed error")
	var gate: HHAgentPauseGate = HHAgentPauseGate.new()
	gate.set_paused(true)
	var paused_mutate: Dictionary = dispatch(
		_sample(
			"godot.node",
			"add",
			{"scene": "res://main.tscn", "parent": ".", "class_name": "Node2D", "name": "X"},
		),
		actions,
		0,
		gate,
	)
	if str(_error_of(paused_mutate).get("code", "")) != HHAgentErrors.E_PAUSED:
		failures.append("paused mutate must be E_PAUSED")
	var paused_scene: Dictionary = dispatch(
		_sample("godot.scene", "create", {"path": "res://r3w1/paused.tscn", "root_class": "Node2D"}),
		actions,
		0,
		gate,
	)
	if str(_error_of(paused_scene).get("code", "")) != HHAgentErrors.E_PAUSED:
		failures.append("paused scene.create must be E_PAUSED")
	var tabs: Dictionary = dispatch(_sample("godot.scene", "list_tabs", {"detail": "short"}), actions, 0)
	if tabs.get("ok", false) != true:
		failures.append("scene.list_tabs must ACK")
	else:
		var post_tabs: Variant = tabs.get("postcondition", {})
		if post_tabs is Dictionary:
			var checks_t: Variant = (post_tabs as Dictionary).get("checks", [])
			if not (checks_t is Array) or not ((checks_t as Array).has("open_scene_tabs_match")):
				failures.append("scene.list_tabs postcondition")
	var pause_samples: Dictionary = gate.measure_samples(20)
	if float(pause_samples.get("p95", 999.0)) > 250.0:
		failures.append("plugin Pause ACK p95 exceeded 250 ms")
	var read_act: Dictionary = dispatch(_sample("godot.project", "inspect", {"detail": "short"}), actions, 0)
	if read_act.get("ok", false) != true:
		failures.append("project.inspect must ACK with a read adapter")
	else:
		var post_read: Variant = read_act.get("postcondition", {})
		if post_read is Dictionary:
			var checks_r: Variant = (post_read as Dictionary).get("checks", [])
			if not (checks_r is Array) or not ((checks_r as Array).has("project_inspect_matches_project_godot")):
				failures.append("project.inspect postcondition")
	var describe: Dictionary = dispatch(_sample("godot.capabilities", "describe", {"kind": "version", "limit": 5}), actions, 0)
	if describe.get("ok", false) != true:
		failures.append("capabilities.describe version must ACK")
	else:
		var after_v: Variant = describe.get("after", {})
		if after_v is Dictionary:
			var classes_v: Variant = (after_v as Dictionary).get("classes", {})
			if classes_v is Dictionary:
				var items_v: Variant = (classes_v as Dictionary).get("items", [])
				var total: int = int((classes_v as Dictionary).get("total", 0))
				if not (items_v is Array) or (items_v as Array).size() > 5:
					failures.append("class page exceeded limit")
				if total < 6:
					failures.append("ClassDB page total too small")
	var property_missing: Dictionary = dispatch(
		_sample(
			"godot.property",
			"set",
			{
				"scene": "res://main.tscn",
				"node_path": ".",
				"property": "position",
				"value": {"schema": "hh-godot-variant/1", "type": "Vector2", "value": {"x": 1, "y": 2}},
			},
		),
		actions,
		0,
	)
	if property_missing.get("ok", true) == true:
		failures.append("property.set on missing scene must not paper-ok")
	if str(_error_of(property_missing).get("code", "")) == "":
		failures.append("property.set on missing scene must be a typed error")
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited != null and not str(edited.scene_file_path).is_empty() and FileAccess.file_exists(edited.scene_file_path):
		var live_set: Dictionary = dispatch(
			_sample(
				"godot.property",
				"set",
				{
					"scene": str(edited.scene_file_path),
					"node_path": ".",
					"property": "visible",
					"value": {"schema": "hh-godot-variant/1", "type": "bool", "value": true},
				},
			),
			actions,
			0,
		)
		if live_set.get("ok", false) != true:
			failures.append("property.set on open edited scene must ACK")
		elif not str(live_set.get("undo_action", "")).begins_with(HHAgentConstants.UNDO_ACTION_PREFIX):
			failures.append("property.set on open edited scene missing Agent undo")
		else:
			dispatch(
				_sample("godot.node", "undo", {"scene": str(edited.scene_file_path), "count": 1}),
				actions,
				0,
			)
	var settings_get: Dictionary = dispatch(
		_sample("godot.project", "settings", {"key": "application/config/name", "op": "get"}),
		actions,
		0,
	)
	if settings_get.get("ok", false) != true:
		failures.append("project.settings get must ACK")
	gate.set_paused(true)
	var paused_settings: Dictionary = dispatch(
		_sample(
			"godot.project",
			"settings",
			{
				"key": "hh_test/selftest",
				"op": "set",
				"value": {"schema": "hh-godot-variant/1", "type": "string", "value": "no"},
			},
		),
		actions,
		0,
		gate,
	)
	if str(_error_of(paused_settings).get("code", "")) != HHAgentErrors.E_PAUSED:
		failures.append("paused project.settings must be E_PAUSED")
	gate.set_paused(false)
	var cam_missing: Dictionary = dispatch(_sample("godot.camera", "make_current", {}), actions, 0)
	if str(_error_of(cam_missing).get("code", "")) != HHAgentErrors.E_MISSING_REQUIRED:
		failures.append("camera.make_current missing required must be E_MISSING_REQUIRED")
	var tilemap_missing: Dictionary = dispatch(_sample("godot.tilemap", "cell", {}), actions, 0)
	if str(_error_of(tilemap_missing).get("code", "")) != HHAgentErrors.E_MISSING_REQUIRED:
		failures.append("tilemap.cell missing required must be E_MISSING_REQUIRED")
	var animation_missing: Dictionary = dispatch(_sample("godot.animation", "library", {}), actions, 0)
	if str(_error_of(animation_missing).get("code", "")) != HHAgentErrors.E_MISSING_REQUIRED:
		failures.append("animation.library missing required must be E_MISSING_REQUIRED")
	var ui_missing: Dictionary = dispatch(_sample("godot.ui", "control", {}), actions, 0)
	if str(_error_of(ui_missing).get("code", "")) != HHAgentErrors.E_MISSING_REQUIRED:
		failures.append("ui.control missing required must be E_MISSING_REQUIRED")
	var physics_missing: Dictionary = dispatch(_sample("godot.physics", "body", {}), actions, 0)
	if str(_error_of(physics_missing).get("code", "")) != HHAgentErrors.E_MISSING_REQUIRED:
		failures.append("physics.body missing required must be E_MISSING_REQUIRED")
	var audio_missing: Dictionary = dispatch(_sample("godot.audio", "player", {}), actions, 0)
	if str(_error_of(audio_missing).get("code", "")) != HHAgentErrors.E_MISSING_REQUIRED:
		failures.append("audio.player missing required must be E_MISSING_REQUIRED")
	var render_missing: Dictionary = dispatch(_sample("godot.render", "shader", {}), actions, 0)
	if str(_error_of(render_missing).get("code", "")) != HHAgentErrors.E_MISSING_REQUIRED:
		failures.append("render.shader missing required must be E_MISSING_REQUIRED")
	var play_missing: Dictionary = dispatch(_sample("godot.play", "start", {}), actions, 0)
	if str(_error_of(play_missing).get("code", "")) != HHAgentErrors.E_MISSING_REQUIRED:
		failures.append("play.start missing required must be E_MISSING_REQUIRED")
	var vendor_plugin: Dictionary = dispatch(
		_sample("godot.project", "plugin", {"plugin_name": "fake_vendor", "enabled": true}),
		actions,
		0,
	)
	var vendor_code: String = str(_error_of(vendor_plugin).get("code", ""))
	if vendor_code != HHAgentErrors.E_POLICY and vendor_code != HHAgentErrors.E_CONFLICT:
		failures.append("third-party plugin enable must be E_POLICY")
	var mutate_still: Dictionary = dispatch(
		_sample("godot.input", "action", {"action_name": "interact", "phase": "press"}),
		actions,
		0,
	)
	if str(_error_of(mutate_still).get("code", "")) != HHAgentErrors.E_UNVERIFIED:
		failures.append("play.input inject must stay E_UNVERIFIED")
	if mutate_still.get("ok", true) == true:
		failures.append("play.input inject must not paper-ok")
	var freeze_idle: Dictionary = dispatch(
		_sample("godot.runtime", "freeze", {"frozen": true, "reason": "test"}),
		actions,
		0,
	)
	if str(_error_of(freeze_idle).get("code", "")) != HHAgentErrors.E_UNVERIFIED:
		failures.append("runtime freeze/step idle must stay E_UNVERIFIED")
	if freeze_idle.get("ok", true) == true:
		failures.append("runtime freeze/step idle must not paper-ok")
	var step_idle: Dictionary = dispatch(
		_sample("godot.runtime", "step", {"frames": 1}),
		actions,
		0,
	)
	if str(_error_of(step_idle).get("code", "")) != HHAgentErrors.E_UNVERIFIED:
		failures.append("runtime freeze/step idle must stay E_UNVERIFIED")
	if step_idle.get("ok", true) == true:
		failures.append("runtime freeze/step idle must not paper-ok")
	var shot_idle: Dictionary = dispatch(
		_sample("godot.runtime", "screenshot", {"scale": 1}),
		actions,
		0,
	)
	if str(_error_of(shot_idle).get("code", "")) != HHAgentErrors.E_UNVERIFIED:
		failures.append("runtime screenshot/perf idle must stay E_UNVERIFIED")
	if shot_idle.get("ok", true) == true:
		failures.append("runtime screenshot/perf idle must not paper-ok")
	var perf_idle: Dictionary = dispatch(
		_sample("godot.runtime", "perf", {"detail": "short"}),
		actions,
		0,
	)
	if str(_error_of(perf_idle).get("code", "")) != HHAgentErrors.E_UNVERIFIED:
		failures.append("runtime screenshot/perf idle must stay E_UNVERIFIED")
	if perf_idle.get("ok", true) == true:
		failures.append("runtime screenshot/perf idle must not paper-ok")
	var tx_missing: Dictionary = dispatch(
		_sample(
			"godot.job",
			"transaction",
			{
				"steps": [
					{
						"action": "node.add",
						"params": {"scene": "res://main.tscn", "parent": ".", "class_name": "Node2D", "name": "X"},
					}
				]
			},
		),
		actions,
		0,
	)
	if tx_missing.get("ok", true) == true:
		failures.append("job.transaction on missing scene must not paper-ok")
	if str(_error_of(tx_missing).get("code", "")) == "":
		failures.append("job.transaction on missing scene must be a typed error")
	gate.set_paused(true)
	var paused_tx: Dictionary = dispatch(
		_sample(
			"godot.job",
			"transaction",
			{
				"steps": [
					{
						"action": "node.add",
						"params": {"scene": "res://main.tscn", "parent": ".", "class_name": "Node2D", "name": "X"},
					}
				]
			},
		),
		actions,
		0,
		gate,
	)
	if str(_error_of(paused_tx).get("code", "")) != HHAgentErrors.E_PAUSED:
		failures.append("paused job.transaction must be E_PAUSED")
	gate.set_paused(false)
	var forbidden: Dictionary = dispatch(
		{
			"protocol": HHAgentConstants.PROTOCOL,
			"command_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
			"method": "godot.project",
			"action": "inspect",
			"params": {"detail": "short"},
			"session_id": "nope",
		},
		actions,
		0,
	)
	if str(_error_of(forbidden).get("code", "")) != HHAgentErrors.E_CLIENT_ESCALATION:
		failures.append("session_id must be E_CLIENT_ESCALATION")
	var unknown: Dictionary = dispatch(
		{
			"protocol": HHAgentConstants.PROTOCOL,
			"command_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
			"method": "godot.project",
			"action": "inspect",
			"params": {"detail": "short"},
			"extra_field": true,
		},
		actions,
		0,
	)
	if str(_error_of(unknown).get("code", "")) != HHAgentErrors.E_INVALID_ENVELOPE:
		failures.append("unknown field must be E_INVALID_ENVELOPE")
	return failures


func _input_apply(
	command_id: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
) -> Dictionary:
	var live: HHAgentRuntimeAdapter = HHAgentRuntimeAdapter.current()
	if live == null:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"play.input requires Play process (R6)",
			"input",
		)
	var def: Dictionary = actions.lookup("godot.input", action)
	var post: String = str(def.get("postcondition", ""))
	if post.is_empty():
		if action == "release_all":
			post = "all_injected_inputs_released"
		elif action == "sequence":
			post = "input_sequence_accepted"
		else:
			post = "input_%s_injected" % action
	return live.begin_input(command_id, action, params, post)


func _time_apply(
	command_id: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
) -> Dictionary:
	var live: HHAgentRuntimeAdapter = HHAgentRuntimeAdapter.current()
	if live == null:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"runtime freeze/step requires Play process (R6)",
			"runtime",
		)
	var def: Dictionary = actions.lookup("godot.runtime", action)
	var post: String = str(def.get("postcondition", ""))
	if post.is_empty():
		if action == "freeze":
			post = "runtime_frozen_matches"
		else:
			post = "runtime_stepped_frames"
	return live.begin_time(command_id, action, params, post)


func _capture_apply(
	command_id: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
) -> Dictionary:
	var live: HHAgentRuntimeAdapter = HHAgentRuntimeAdapter.current()
	if live == null:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			"runtime screenshot/perf requires Play process (R6)",
			"runtime",
		)
	var def: Dictionary = actions.lookup("godot.runtime", action)
	var post: String = str(def.get("postcondition", ""))
	if post.is_empty():
		if action == "screenshot":
			post = "screenshot_artifact_present"
		else:
			post = "perf_counters_present"
	return live.begin_capture(command_id, action, params, post)


func _play() -> HHAgentPlayAdapter:
	var live: HHAgentPlayAdapter = HHAgentPlayAdapter.current()
	if live != null:
		return live
	return _play_local


func _overlay() -> HHAgentOverlay:
	var live: HHAgentOverlay = HHAgentOverlay.current()
	if live != null:
		return live
	return _overlay_local


func _scheduler() -> HHAgentScheduler:
	var live: HHAgentScheduler = HHAgentScheduler.current()
	if live != null:
		return live
	return _scheduler_local


func _sync_presentation_mode(envelope: Dictionary) -> void:
	var pres_v: Variant = envelope.get("presentation", {})
	if not (pres_v is Dictionary):
		return
	var mode_s: String = str((pres_v as Dictionary).get("mode", ""))
	if mode_s != HHAgentConstants.MODE_FAST and mode_s != HHAgentConstants.MODE_WATCH:
		return
	var store: HHAgentActivityStore = HHAgentActivityStore.current()
	if store != null:
		store.set_mode(mode_s)
	_overlay().set_mode(mode_s)
	_scheduler().set_mode(mode_s)


func _sample(method: String, action: String, params: Dictionary) -> Dictionary:
	return {
		"protocol": HHAgentConstants.PROTOCOL,
		"command_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
		"method": method,
		"action": action,
		"params": params,
	}


func _error_of(result: Dictionary) -> Dictionary:
	var err_v: Variant = result.get("error", {})
	if err_v is Dictionary:
		return err_v
	return {}
