class_name HHAgentErrors
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")

const E_UNKNOWN_ACTION: String = "E_UNKNOWN_ACTION"
const E_PROTOCOL_VERSION: String = "E_PROTOCOL_VERSION"
const E_ACTION_VERSION: String = "E_ACTION_VERSION"
const E_UNKNOWN_PARAM: String = "E_UNKNOWN_PARAM"
const E_MISSING_REQUIRED: String = "E_MISSING_REQUIRED"
const E_INVALID_TYPE: String = "E_INVALID_TYPE"
const E_OUT_OF_BOUNDS: String = "E_OUT_OF_BOUNDS"
const E_INVALID_COMMAND_ID: String = "E_INVALID_COMMAND_ID"
const E_CLIENT_ESCALATION: String = "E_CLIENT_ESCALATION"
const E_INVALID_ENVELOPE: String = "E_INVALID_ENVELOPE"
const E_UNKNOWN_VARIANT_TYPE: String = "E_UNKNOWN_VARIANT_TYPE"
const E_INVALID_VARIANT: String = "E_INVALID_VARIANT"
const E_UNVERIFIED: String = "E_UNVERIFIED"
const E_AUTH: String = "E_AUTH"
const E_PROJECT_MISMATCH: String = "E_PROJECT_MISMATCH"
const E_BUSY: String = "E_BUSY"
const E_IDEMPOTENCY_CONFLICT: String = "E_IDEMPOTENCY_CONFLICT"
const E_UNCERTAIN: String = "E_UNCERTAIN"
const E_POLICY: String = "E_POLICY"
const E_CHECKPOINT: String = "E_CHECKPOINT"
const E_CONFLICT: String = "E_CONFLICT"
const E_PAUSED: String = "E_PAUSED"
const E_LEASE: String = "E_LEASE"
const E_PATH: String = "E_PATH"
const E_VERSION_SKEW: String = "E_VERSION_SKEW"
const E_TIMEOUT: String = "E_TIMEOUT"


func typed(code: String, message: String, path: String = "") -> Dictionary:
	return {"code": code, "message": message, "path": path}


func fail(command_id: String, code: String, message: String, path: String = "") -> Dictionary:
	return {
		"type": HHAgentConstants.RESULT_TYPE,
		"ok": false,
		"command_id": command_id,
		"changed": false,
		"postcondition": {"verified": false, "checks": []},
		"error": typed(code, message, path),
	}


func ok_read(command_id: String, checks: PackedStringArray, after: Dictionary) -> Dictionary:
	var check_list: Array = []
	for item: String in checks:
		check_list.append(item)
	if check_list.is_empty():
		return fail(command_id, E_UNVERIFIED, "read adapter produced empty postcondition checks", "")
	return {
		"type": HHAgentConstants.RESULT_TYPE,
		"ok": true,
		"command_id": command_id,
		"changed": false,
		"after": after,
		"postcondition": {"verified": true, "checks": check_list},
	}


func ok_changed(
	command_id: String,
	checks: PackedStringArray,
	after: Dictionary,
	changed: bool,
	undo_action: String = "",
) -> Dictionary:
	var check_list: Array = []
	for item: String in checks:
		check_list.append(item)
	if check_list.is_empty():
		return fail(command_id, E_UNVERIFIED, "empty postcondition checks", "")
	var result: Dictionary = {
		"type": HHAgentConstants.RESULT_TYPE,
		"ok": true,
		"command_id": command_id,
		"changed": changed,
		"after": after,
		"postcondition": {"verified": true, "checks": check_list},
	}
	if not undo_action.is_empty():
		result["undo_action"] = undo_action
	return result


func ok_noop(command_id: String) -> Dictionary:
	return {
		"type": HHAgentConstants.RESULT_TYPE,
		"ok": true,
		"command_id": command_id,
		"changed": false,
		"postcondition": {"verified": true, "checks": ["noop"]},
	}
