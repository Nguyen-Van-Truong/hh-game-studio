@tool
extends EditorPlugin
## Disposable O2 native probe driver. It is copied into a temporary project by
## run_authoring_native_probe.py and is never installed as the product addon.

const Probe = preload("res://tests/authoring_native_probe.gd")


func _enter_tree() -> void:
	call_deferred("_run")


func _run() -> void:
	# Wait for the editor to finish opening the disposable fixture scene. The
	# first deferred frame can precede scene activation on a cold editor, so use
	# a bounded wait instead of treating that normal race as a harness failure.
	var root: Node = null
	for _frame in range(120):
		await get_tree().process_frame
		root = EditorInterface.get_edited_scene_root()
		if root != null:
			break
	var catalog_file := FileAccess.open("res://catalog-input.json", FileAccess.READ)
	var edge_file := FileAccess.open("res://edge-input.json", FileAccess.READ)
	var resource_file := FileAccess.open("res://resource-input.json", FileAccess.READ)
	if catalog_file == null or edge_file == null or resource_file == null or root == null:
		_write_result({"schema": "hh-o2-native-authoring-observation-1", "actual_editor": true,
			"runtime_authorized": false, "native_mutation": false,
			"formal_acceptance": false, "checks": [], "failures": ["INPUT_OR_ROOT"]})
		get_tree().quit(41)
		return
	var catalog: Variant = JSON.parse_string(catalog_file.get_as_text())
	catalog_file.close()
	var edge_input: Variant = JSON.parse_string(edge_file.get_as_text())
	edge_file.close()
	var resource_input: Variant = JSON.parse_string(resource_file.get_as_text())
	resource_file.close()
	if not catalog is Dictionary or not edge_input is Dictionary or not resource_input is Dictionary \
			or not edge_input.get("proposals", null) is Array or not resource_input.get("proposals", null) is Array:
		_write_result({"schema": "hh-o2-native-authoring-observation-1", "actual_editor": true,
			"runtime_authorized": false, "native_mutation": false,
			"formal_acceptance": false, "checks": [], "failures": ["CATALOG_JSON"]})
		get_tree().quit(42)
		return
	var run_root := OS.get_environment("HH_O2_RUN_ROOT").replace("\\", "/").trim_suffix("/")
	var report: Dictionary = Probe.new().run(root, get_undo_redo(), catalog, run_root,
		edge_input["proposals"], resource_input["proposals"])
	_write_result(report)
	get_tree().quit(0 if report.get("failures", []).is_empty() else 43)


func _write_result(report: Dictionary) -> void:
	var file := FileAccess.open("res://o2-native-result.json", FileAccess.WRITE)
	if file == null:
		return
	file.store_string(JSON.stringify(report, "", true, true) + "\n")
	file.flush()
	file.close()
