class_name HHAgentCompat
extends RefCounted

## Capability-lock / protocol / schema mismatch → Observe/Doctor only (S7).

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")


static func observe_only_reason() -> String:
	var observed: String = godot_string()
	if observed != HHAgentConstants.PINNED_GODOT:
		return "Godot %s != pin %s; Observe/Doctor only" % [observed, HHAgentConstants.PINNED_GODOT]
	var protocol: String = planted_text("res://.hh-agent/protocol")
	if not protocol.is_empty() and protocol != HHAgentConstants.PROTOCOL:
		return "protocol %s != %s; Observe/Doctor only" % [protocol, HHAgentConstants.PROTOCOL]
	var schema: String = planted_text("res://.hh-agent/schema-version")
	if not schema.is_empty() and schema != HHAgentConstants.SCHEMA_VERSION:
		return "schema %s != %s; Observe/Doctor only" % [schema, HHAgentConstants.SCHEMA_VERSION]
	var lock: Dictionary = load_lock()
	if lock.is_empty():
		return ""
	var godot_v: Variant = lock.get("godot", {})
	var godot: Dictionary = godot_v if godot_v is Dictionary else {}
	var version_id: String = str(godot.get("version_id", ""))
	if not version_id.is_empty() and version_id != HHAgentConstants.PINNED_GODOT:
		return "capability-lock %s != pin %s; Observe/Doctor only" % [version_id, HHAgentConstants.PINNED_GODOT]
	return ""


static func lock_summary() -> Dictionary:
	var lock: Dictionary = load_lock()
	var godot_v: Variant = lock.get("godot", {})
	var godot: Dictionary = godot_v if godot_v is Dictionary else {}
	return {
		"has_project_lock": not lock.is_empty(),
		"version_id": str(godot.get("version_id", "")),
		"protocol": planted_text("res://.hh-agent/protocol"),
		"schema": planted_text("res://.hh-agent/schema-version"),
		"mode": "Observe/Doctor only" if not observe_only_reason().is_empty() else "mutate-allowed",
	}


static func godot_string() -> String:
	var info: Dictionary = Engine.get_version_info()
	var hash_s: String = str(info.get("hash", ""))
	if hash_s.length() > 9:
		hash_s = hash_s.substr(0, 9)
	return "%s.%s.%s.%s.%s.%s" % [
		str(info.get("major", 0)),
		str(info.get("minor", 0)),
		str(info.get("patch", 0)),
		str(info.get("status", "")),
		str(info.get("build", "")),
		hash_s,
	]


static func planted_text(res_path: String) -> String:
	if not FileAccess.file_exists(res_path):
		return ""
	var file: FileAccess = FileAccess.open(res_path, FileAccess.READ)
	if file == null:
		return ""
	return file.get_as_text().strip_edges()


static func load_lock() -> Dictionary:
	var res_path: String = "res://.hh-agent/capability-lock.json"
	if not FileAccess.file_exists(res_path):
		return {}
	var file: FileAccess = FileAccess.open(res_path, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if parsed is Dictionary:
		return parsed
	return {}
