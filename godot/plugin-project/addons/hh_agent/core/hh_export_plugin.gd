class_name HHAgentExportPlugin
extends EditorExportPlugin

## Strip debug-only runtime probe / addon / evidence from release artifacts.
## Official proof is skip() matching these paths; a full export build is not
## required when no export preset exists.

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")


func _get_name() -> String:
	return "hh_agent_runtime_strip"


func _export_file(path: String, _type: String, _features: PackedStringArray) -> void:
	if _should_skip(path):
		skip()


func _should_skip(path: String) -> bool:
	var p: String = path.replace("\\", "/")
	if p.contains("HHAgentRuntime"):
		return true
	if p.contains("hh_agent_runtime"):
		return true
	if p.contains("addons/hh_agent/runtime"):
		return true
	if p.contains("addons/hh_agent"):
		return true
	if p.contains(".hh-agent"):
		return true
	if p.contains("hh_runtime_debugger"):
		return true
	if p.contains("/r6w2/") or p.contains("r6w2/"):
		return true
	if p.contains("/r6w3/") or p.contains("r6w3/"):
		return true
	if p.contains("/r6w4/") or p.contains("r6w4/"):
		return true
	if p.contains("/r6w5/") or p.contains("r6w5/"):
		return true
	if p.contains("/r6w6/") or p.contains("r6w6/"):
		return true
	return false
