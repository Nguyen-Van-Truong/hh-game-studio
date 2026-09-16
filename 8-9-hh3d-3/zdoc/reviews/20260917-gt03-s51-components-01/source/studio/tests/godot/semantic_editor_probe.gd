@tool
extends "res://addons/hh_studio/plugin.gd"
## Fixed diagnostic overlay only, never an installed publication path.


func _enter_tree() -> void:
	super._enter_tree()
	call_deferred("_observe")


func _observe() -> void:
	var snapshot: Dictionary = {}
	for attempt: int in range(120):
		snapshot = inspect_scene()
		if snapshot.get("ok", false):
			break
		await get_tree().process_frame
	var report: Dictionary = {"schema": "hh-editor-semantic-probe-1", "public_ack": false,
		"context_kind": "live_editor", "editor_hint": Engine.is_editor_hint(),
		"engine_version": Engine.get_version_info().string, "pid": OS.get_process_id(),
		"snapshot": snapshot}
	var encoded: String = JSON.stringify(report, "", true, true)
	if encoded.to_utf8_buffer().size() > 196608:
		print("HH_EDITOR_SEMANTIC_LIMIT")
		get_tree().quit(52)
		return
	print("HH_EDITOR_SEMANTIC " + encoded)
	get_tree().quit(0 if snapshot.get("ok", false) and Engine.is_editor_hint() else 51)
