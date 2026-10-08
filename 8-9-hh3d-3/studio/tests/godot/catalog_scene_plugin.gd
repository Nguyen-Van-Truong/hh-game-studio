@tool
extends EditorPlugin
## Disposable driver copied into the host-owned catalog project.

const Adapter = preload("res://addons/hh_catalog/catalog_scene_adapter.gd")


func _enter_tree() -> void:
	call_deferred("_run")


func _run() -> void:
	var root: Node = null
	for _frame: int in range(180):
		await get_tree().process_frame
		root = EditorInterface.get_edited_scene_root()
		if root != null:
			break
	var data: Variant = null
	var input := FileAccess.open("res://catalog-input.json", FileAccess.READ)
	if input != null:
		data = JSON.parse_string(input.get_as_text())
		input.close()
	var report: Dictionary
	if root == null or not data is Dictionary:
		report = {"schema": "hh-catalog-native-observation-1", "authority": 0,
			"public_ack": false, "pid": OS.get_process_id(), "input_sha256": "",
			"transaction_digest": "", "command_ids": [], "commands": [], "snapshots": {},
			"checks": {"undo": false, "redo": false, "save": false, "reload": false},
			"failures": ["CATALOG_INPUT_OR_ROOT"], "scene_sha256": ""}
	else:
		report = Adapter.new().run(root, get_undo_redo(), data)
	var complete: bool = not str(report.get("scene_sha256", "")).is_empty()
	for key: String in ["undo", "redo", "save", "reload"]:
		complete = complete and report.get("checks", {}).get(key, false) == true
	if not complete and report.get("failures", []).is_empty():
		report.failures.append("CATALOG_INCOMPLETE")
	_write(report)
	get_tree().quit(0 if complete and report.get("failures", []).is_empty() else 43)


func _write(report: Dictionary) -> void:
	var file := FileAccess.open("res://native-observation.json", FileAccess.WRITE)
	if file == null:
		return
	var canonical: Dictionary = preload("res://addons/hh_catalog/jcs_godot.gd").new().canonicalize(report)
	file.store_string((str(canonical.get("canonical")) if canonical.get("ok", false)
		else JSON.stringify(report, "", true, true)) + "\n")
	file.flush()
	file.close()
