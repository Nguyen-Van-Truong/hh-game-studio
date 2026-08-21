class_name HHAgentRouter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _EnvelopeScript: GDScript = preload("res://addons/hh_agent/core/hh_envelope.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")

## Routes read/view (no live adapters yet) and the test noop. Never mutates the scene.

var _errors: HHAgentErrors = HHAgentErrors.new()
var _envelope: HHAgentEnvelope = HHAgentEnvelope.new()


func dispatch(raw: Variant, actions: HHAgentActions, queued_at_ms: int) -> Dictionary:
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
	if side_effect == "read" or side_effect == "view":
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "no read adapter", "")
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not dispatched", "")


func run_selftest(actions: HHAgentActions) -> PackedStringArray:
	var failures: PackedStringArray = PackedStringArray()
	if not actions.loaded or actions.action_count() < 118:
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
	if str(mutate_err.get("code", "")) != HHAgentErrors.E_UNVERIFIED or mutate.get("ok", true) == true:
		failures.append("mutate must be E_UNVERIFIED")
	var read_act: Dictionary = dispatch(_sample("godot.project", "inspect", {"detail": "short"}), actions, 0)
	if str(_error_of(read_act).get("code", "")) != HHAgentErrors.E_UNVERIFIED:
		failures.append("read without adapter must be E_UNVERIFIED")
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
