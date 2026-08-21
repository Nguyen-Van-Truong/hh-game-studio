@tool
extends Node

## In-editor disable/enable driver. Survives hh_agent unload (not part of the addon).
## No-op unless HH_AGENT_RELOAD_N is set. Used by tests/bootstrap/test_plugin_router.py.

const PLUGIN_NAME: String = "hh_agent"

var _want: int = 0


func _ready() -> void:
	if not Engine.is_editor_hint():
		return
	var raw: String = OS.get_environment("HH_AGENT_RELOAD_N")
	if raw.is_empty():
		return
	_want = int(raw)
	if _want <= 0:
		return
	call_deferred("_run_reloads")


func _run_reloads() -> void:
	var plugin_id: String = _resolve_plugin_id()
	if plugin_id.is_empty():
		_finish(false, "plugin id not resolved")
		return
	var i: int = 0
	while i < _want:
		EditorInterface.set_plugin_enabled(plugin_id, false)
		if EditorInterface.is_plugin_enabled(plugin_id):
			_finish(false, "still enabled after disable i=%d" % i)
			return
		await get_tree().process_frame
		EditorInterface.set_plugin_enabled(plugin_id, true)
		if not EditorInterface.is_plugin_enabled(plugin_id):
			_finish(false, "not enabled after enable i=%d" % i)
			return
		await get_tree().process_frame
		i += 1
	_finish(true, "count=%d id=%s" % [_want, plugin_id])


func _resolve_plugin_id() -> String:
	var candidates: PackedStringArray = PackedStringArray([
		PLUGIN_NAME,
		"res://addons/hh_agent/plugin.cfg",
	])
	for candidate: String in candidates:
		if EditorInterface.is_plugin_enabled(candidate):
			return candidate
	return PLUGIN_NAME


func _finish(ok: bool, detail: String) -> void:
	var summary: String = "HH_AGENT_RELOAD=PASS %s" % detail if ok else "HH_AGENT_RELOAD=FAIL %s" % detail
	print("[hh_reload_driver] %s" % summary)
	var out_dir: String = OS.get_environment("HH_AGENT_RELOAD_OUT")
	if not out_dir.is_empty():
		var path: String = "%s/hh_agent_reload.txt" % out_dir
		var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
		if f != null:
			f.store_string(summary + "\n")
			f.flush()
			f.close()
	var tree: SceneTree = get_tree()
	if tree != null:
		tree.quit(0 if ok else 1)
