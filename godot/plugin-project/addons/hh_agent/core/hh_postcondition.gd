class_name HHAgentPostcondition
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")

## Last-command postcondition memory for crash recovery readback. No scene I/O.

var _command_id: String = ""
var _ok: bool = false
var _verified: bool = false
var _checks: Array[String] = []


func remember(command_id: String, result: Dictionary) -> void:
	_command_id = command_id
	_ok = result.get("ok", false) == true
	_verified = false
	_checks.clear()
	var post_v: Variant = result.get("postcondition", {})
	if post_v is Dictionary:
		var post: Dictionary = post_v
		_verified = post.get("verified", false) == true
		var checks_v: Variant = post.get("checks", [])
		if checks_v is Array:
			for item_v: Variant in checks_v:
				if typeof(item_v) == TYPE_STRING:
					_checks.append(str(item_v))


func readback(command_id: String) -> Dictionary:
	if command_id.is_empty() or command_id != _command_id:
		return {
			"type": HHAgentConstants.READBACK_RESULT_TYPE,
			"command_id": command_id,
			"found": false,
			"ok": false,
			"postcondition": {"verified": false, "checks": []},
		}
	var checks: Array[String] = []
	for item: String in _checks:
		checks.append(item)
	return {
		"type": HHAgentConstants.READBACK_RESULT_TYPE,
		"command_id": command_id,
		"found": true,
		"ok": _ok,
		"postcondition": {"verified": _verified, "checks": checks},
	}
