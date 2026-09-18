@tool
extends EditorPlugin

var _done := false

func _enter_tree() -> void:
	if "--gt01-editor-probe" in OS.get_cmdline_user_args():
		call_deferred("_probe")

func _probe() -> void:
	var deadline := 120
	while deadline > 0 and EditorInterface.get_edited_scene_root() == null:
		await get_tree().process_frame
		deadline -= 1
	var root := EditorInterface.get_edited_scene_root()
	var base := EditorInterface.get_base_control()
	var window := base.get_window() if base != null else null
	var visible := window != null and window.visible
	var scene_ok := root != null and root.name == "Fixture" and root.scene_file_path == "res://main.tscn"
	var display := DisplayServer.get_name()
	_done = scene_ok and visible and display != "headless"
	var event := {"result": "PASS" if _done else "FAIL", "display_server": display, "scene": root.scene_file_path if root != null else "", "root": root.name if root != null else "", "visible": visible}
	print("GT01_EDITOR_TRACE " + JSON.stringify(event))
	var output_path := OS.get_environment("GT01_EDITOR_PROBE_OUTPUT")
	if not output_path.is_empty():
		var file := FileAccess.open(output_path, FileAccess.WRITE)
		if file != null:
			file.store_string(JSON.stringify(event) + "\n")
			file.close()
	if not _done:
		push_error("GT01 editor probe postcondition failed")
	get_tree().quit(0 if _done else 2)
