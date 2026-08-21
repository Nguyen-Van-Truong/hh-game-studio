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

## Routes read/view adapters, scene/node/property/resource/signal/script/asset/project/transaction apply.

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
	if method == "godot.job" and action == "transaction":
		return _tx.handle(command_id, method, action, params, actions, pre)
	if method == "godot.scene" and action == "instantiate":
		return _nodes.handle(command_id, method, action, params, actions, pre)
	if method == "godot.node" and action != "query" and _nodes.handles(action):
		return _nodes.handle(command_id, method, action, params, actions, pre)
	if method == "godot.property" and action != "get" and _props.handles(action):
		return _props.handle(command_id, method, action, params, actions, pre)
	if method == "godot.resource" and action != "load" and action != "uid" and _resources.handles(action):
		return _resources.handle(command_id, method, action, params, actions, pre)
	if method == "godot.signal" and _signals.handles(action):
		return _signals.handle(command_id, method, action, params, actions, pre)
	if method == "godot.asset" and _assets.handles(action):
		return _assets.handle(command_id, method, action, params, actions, pre, pause_gate)
	if method == "godot.script" and _scripts.handles(action):
		return _scripts.handle(command_id, method, action, params, actions, pre)
	if method == "godot.project" and action != "inspect" and action != "doctor" and _settings.handles(action):
		return _settings.handle(command_id, method, action, params, actions, pre)
	if method == "godot.scene" and _scenes.handles(action):
		return _scenes.handle(command_id, method, action, params, actions, pre)
	if side_effect == "read" or side_effect == "view":
		return _reads.handle(command_id, method, action, params, actions)
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not dispatched", "")


func run_selftest(actions: HHAgentActions) -> PackedStringArray:
	var failures: PackedStringArray = PackedStringArray()
	if not actions.loaded or actions.action_count() < 122:
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
