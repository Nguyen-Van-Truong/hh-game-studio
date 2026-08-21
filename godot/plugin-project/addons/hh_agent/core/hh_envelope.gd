class_name HHAgentEnvelope
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")

## Second schema pass. Source of allowed/forbidden fields is actions.json
## (copied from bridge/generated/plugin-validator.json).

const ULID_PATTERN: String = "^[0-7][0-9A-HJKMNPQRSTVWXYZ]{25}$"

var _errors: HHAgentErrors = HHAgentErrors.new()
var _ulid: RegEx = RegEx.new()
var _res_path: RegEx = RegEx.new()


func _init() -> void:
	var ulid_err: Error = _ulid.compile(ULID_PATTERN)
	if ulid_err != OK:
		push_error("hh_agent: ULID regex failed")
	var path_err: Error = _res_path.compile("^res://[^\\s]+$")
	if path_err != OK:
		push_error("hh_agent: res path regex failed")


func parse(raw: Variant, actions: HHAgentActions) -> Dictionary:
	if typeof(raw) != TYPE_DICTIONARY:
		return _bad(_errors.typed(HHAgentErrors.E_INVALID_ENVELOPE, "envelope must be an object", ""))
	var rec: Dictionary = raw
	var allowed: Dictionary = {}
	for field: String in actions.allowed_fields:
		allowed[field] = true
	var forbidden: Dictionary = {}
	for field: String in actions.forbidden_fields:
		forbidden[field] = true
	for key_v: Variant in rec.keys():
		var key: String = str(key_v)
		if forbidden.has(key):
			return _bad(_errors.typed(HHAgentErrors.E_CLIENT_ESCALATION, "client must not set %s" % key, key))
		if not allowed.has(key):
			return _bad(_errors.typed(HHAgentErrors.E_INVALID_ENVELOPE, "unknown envelope field %s" % key, key))
	if str(rec.get("protocol", "")) != HHAgentConstants.PROTOCOL:
		return _bad(_errors.typed(HHAgentErrors.E_PROTOCOL_VERSION, "protocol must be %s" % HHAgentConstants.PROTOCOL, "protocol"))
	var command_id: String = str(rec.get("command_id", ""))
	if not _is_ulid(command_id):
		return _bad(_errors.typed(HHAgentErrors.E_INVALID_COMMAND_ID, "command_id must be a ULID", "command_id"))
	var method: String = str(rec.get("method", ""))
	var action: String = str(rec.get("action", ""))
	if method.is_empty() or action.is_empty():
		return _bad(_errors.typed(HHAgentErrors.E_UNKNOWN_ACTION, "action verb required", "action"))
	if method == HHAgentConstants.NOOP_METHOD:
		if action != HHAgentConstants.NOOP_ACTION:
			return _bad(_errors.typed(HHAgentErrors.E_UNKNOWN_ACTION, "unknown plugin action", "action"))
	elif not method.begins_with("godot."):
		return _bad(_errors.typed(HHAgentErrors.E_UNKNOWN_ACTION, "method must be godot.<group>", "method"))
	var params_v: Variant = rec.get("params", null)
	if typeof(params_v) != TYPE_DICTIONARY:
		return _bad(_errors.typed(HHAgentErrors.E_INVALID_TYPE, "params must be an object", "params"))
	if rec.has("action_version"):
		if str(rec.get("action_version", "")) != HHAgentConstants.ACTION_VERSION:
			return _bad(_errors.typed(HHAgentErrors.E_ACTION_VERSION, "action_version must be %s" % HHAgentConstants.ACTION_VERSION, "action_version"))
	if rec.has("precondition"):
		var pre_err: Dictionary = _validate_precondition(rec.get("precondition", null))
		if not pre_err.is_empty():
			return _bad(pre_err)
	if rec.has("presentation"):
		var pres_err: Dictionary = _validate_presentation(rec.get("presentation", null))
		if not pres_err.is_empty():
			return _bad(pres_err)
	var envelope: Dictionary = {
		"protocol": HHAgentConstants.PROTOCOL,
		"command_id": command_id,
		"method": method,
		"action": action,
		"params": params_v,
	}
	if rec.has("action_version"):
		envelope["action_version"] = str(rec.get("action_version", ""))
	if rec.has("precondition") and rec.get("precondition") is Dictionary:
		envelope["precondition"] = rec.get("precondition")
	if rec.has("presentation") and rec.get("presentation") is Dictionary:
		envelope["presentation"] = rec.get("presentation")
	return {"ok": true, "envelope": envelope}


func _is_ulid(value: String) -> bool:
	if value.length() != 26:
		return false
	return _ulid.search(value.to_upper()) != null


func _validate_precondition(raw: Variant) -> Dictionary:
	if typeof(raw) != TYPE_DICTIONARY:
		return _errors.typed(HHAgentErrors.E_INVALID_TYPE, "precondition must be an object", "precondition")
	var rec: Dictionary = raw
	var allowed: Dictionary = {
		"scene": true,
		"scene_hash": true,
		"target_uid": true,
		"property_hash": true,
		"fingerprint": true,
		"history_version": true,
	}
	for key_v: Variant in rec.keys():
		var key: String = str(key_v)
		if not allowed.has(key):
			return _errors.typed(HHAgentErrors.E_UNKNOWN_PARAM, "unknown precondition field", "precondition.%s" % key)
		if typeof(rec[key_v]) != TYPE_STRING:
			return _errors.typed(HHAgentErrors.E_INVALID_TYPE, "precondition field must be a string", "precondition.%s" % key)
		var text: String = str(rec[key_v])
		if key == "scene":
			if text.length() < 6 or text.length() > 256 or _res_path.search(text) == null:
				return _errors.typed(HHAgentErrors.E_OUT_OF_BOUNDS, "invalid scene path", "precondition.scene")
		elif key == "target_uid":
			if text.length() < 1 or text.length() > 128:
				return _errors.typed(HHAgentErrors.E_OUT_OF_BOUNDS, "invalid target_uid", "precondition.target_uid")
		elif key == "history_version":
			if text.length() < 1 or text.length() > 32:
				return _errors.typed(HHAgentErrors.E_OUT_OF_BOUNDS, "invalid history_version", "precondition.history_version")
		elif text.length() < 8 or text.length() > 128:
			return _errors.typed(HHAgentErrors.E_OUT_OF_BOUNDS, "invalid hash", "precondition.%s" % key)
	return {}


func _validate_presentation(raw: Variant) -> Dictionary:
	if typeof(raw) != TYPE_DICTIONARY:
		return _errors.typed(HHAgentErrors.E_INVALID_TYPE, "presentation must be an object", "presentation")
	var rec: Dictionary = raw
	for key_v: Variant in rec.keys():
		var key: String = str(key_v)
		if key != "mode" and key != "duration_ms":
			return _errors.typed(HHAgentErrors.E_UNKNOWN_PARAM, "unknown presentation field", "presentation.%s" % key)
	if rec.has("mode"):
		var mode: String = str(rec.get("mode", ""))
		if mode != "watch" and mode != "fast":
			return _errors.typed(HHAgentErrors.E_OUT_OF_BOUNDS, "mode must be watch or fast", "presentation.mode")
	if rec.has("duration_ms"):
		if typeof(rec.get("duration_ms")) != TYPE_FLOAT and typeof(rec.get("duration_ms")) != TYPE_INT:
			return _errors.typed(HHAgentErrors.E_INVALID_TYPE, "duration_ms must be an integer", "presentation.duration_ms")
		var duration: int = int(rec.get("duration_ms", 0))
		if duration < 0 or duration > 60000:
			return _errors.typed(HHAgentErrors.E_OUT_OF_BOUNDS, "duration_ms out of range", "presentation.duration_ms")
	return {}


func _bad(error: Dictionary) -> Dictionary:
	return {"ok": false, "error": error}
