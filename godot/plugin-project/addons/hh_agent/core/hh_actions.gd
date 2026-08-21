class_name HHAgentActions
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")

## Slim catalog loaded from actions.json (subset of plugin-validator.json).

const CATALOG_PATH: String = "res://addons/hh_agent/core/actions.json"

var protocol: String = ""
var allowed_fields: Array[String] = []
var forbidden_fields: Array[String] = []
var loaded: bool = false
var _by_key: Dictionary = {}


func load_from_res() -> bool:
	allowed_fields.clear()
	forbidden_fields.clear()
	_by_key.clear()
	loaded = false
	if not FileAccess.file_exists(CATALOG_PATH):
		return false
	var text: String = FileAccess.get_file_as_string(CATALOG_PATH)
	var parsed: Variant = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		return false
	var root: Dictionary = parsed
	protocol = str(root.get("protocol", ""))
	var envelope_v: Variant = root.get("envelope", {})
	if envelope_v is Dictionary:
		var envelope: Dictionary = envelope_v
		_fill_strings(envelope.get("allowed", []), allowed_fields)
		_fill_strings(envelope.get("forbidden_client_fields", []), forbidden_fields)
	var actions_v: Variant = root.get("actions", {})
	if actions_v is Dictionary:
		var actions: Dictionary = actions_v
		for action_id: Variant in actions.keys():
			var spec_v: Variant = actions[action_id]
			if spec_v is Dictionary:
				var spec: Dictionary = spec_v
				var method: String = str(spec.get("method", ""))
				var verb: String = str(spec.get("verb", ""))
				if method.is_empty() or verb.is_empty():
					continue
				var required: Array[String] = []
				_fill_strings(spec.get("required", []), required)
				_by_key[_key(method, verb)] = {
					"id": str(action_id),
					"method": method,
					"verb": verb,
					"side_effect": str(spec.get("side_effect", "")),
					"timeout_ms": int(spec.get("timeout_ms", 5000)),
					"required": required,
				}
	loaded = protocol == HHAgentConstants.PROTOCOL and not _by_key.is_empty()
	return loaded


func lookup(method: String, action: String) -> Dictionary:
	var found: Variant = _by_key.get(_key(method, action), {})
	if found is Dictionary:
		return found
	return {}


func is_noop(method: String, action: String) -> bool:
	return method == HHAgentConstants.NOOP_METHOD and action == HHAgentConstants.NOOP_ACTION


func action_count() -> int:
	return _by_key.size()


func _key(method: String, action: String) -> String:
	return "%s\t%s" % [method, action]


func _fill_strings(raw: Variant, dest: Array[String]) -> void:
	if raw is Array:
		var items: Array = raw
		for item: Variant in items:
			if typeof(item) == TYPE_STRING:
				dest.append(str(item))
