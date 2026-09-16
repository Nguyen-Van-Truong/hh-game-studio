extends SceneTree
## Trusted, fixed readback program. Host eligibility MUST precede invocation.
## Output is an observation, never authorization or a public COMMITTED receipt.

const SCRIPT_PATH: String = "res://scripts/fixture_actor.gd"
const SCENE_PATH: String = "res://scenes/fixture.tscn"
const SceneCommands = preload("res://addons/hh_studio/scene_commands.gd")
const SERIALIZER_PATH: String = "res://addons/hh_studio/scene_commands.gd"
const JCS_PATH: String = "res://addons/hh_studio/jcs_godot.gd"
const MAX_REPORT_BYTES: int = 196608
const EXPORT_NAMES: Array[String] = ["fixture_value", "move_speed", "turn_speed", "enabled"]
var _failed: bool = false


func _vector(value: Vector3) -> Array:
	return [value.x, value.y, value.z]


func _transform(value: Transform3D) -> Array:
	# TSCN serializes the basis by rows; Basis.x/y/z are columns.
	return [value.basis.x.x, value.basis.y.x, value.basis.z.x,
		value.basis.x.y, value.basis.y.y, value.basis.z.y,
		value.basis.x.z, value.basis.y.z, value.basis.z.z,
		value.origin.x, value.origin.y, value.origin.z]


func _value(value: Variant) -> Dictionary:
	match typeof(value):
		TYPE_NIL:
			return {"type": "nil", "value": null}
		TYPE_BOOL:
			return {"type": "bool", "value": value}
		TYPE_INT:
			return {"type": "int", "value": value}
		TYPE_FLOAT:
			if not is_finite(value):
				_failed = true
				return {"type": "invalid"}
			return {"type": "float", "value": value}
		TYPE_STRING, TYPE_STRING_NAME:
			return {"type": "string", "value": str(value)}
		TYPE_VECTOR3:
			return {"type": "Vector3", "value": _vector(value)}
		TYPE_TRANSFORM3D:
			return {"type": "Transform3D", "value": _transform(value)}
		TYPE_OBJECT:
			if value == null:
				return {"type": "nil", "value": null}
			if value is GDScript:
				return {"type": "GDScript", "path": value.resource_path,
					"source_sha256": value.source_code.sha256_text()}
			if value is BoxMesh:
				return {"type": "BoxMesh", "id": value.resource_scene_unique_id,
					"size": _vector(value.size)}
	_failed = true
	return {"type": "unsupported"}


func _names(rows: Array[Dictionary]) -> Array[String]:
	var names: Array[String] = []
	for row: Dictionary in rows:
		names.append(str(row.name))
	names.sort()
	return names


func _exports(script: GDScript, object: Object = null) -> Dictionary:
	var result: Dictionary = {}
	for row: Dictionary in script.get_script_property_list():
		var property_name: String = str(row.name)
		if property_name in EXPORT_NAMES:
			result[property_name] = _value(script.get_property_default_value(property_name)
				if object == null else object.get(property_name))
	return result


func _state(scene: PackedScene) -> Dictionary:
	var state: SceneState = scene.get_state()
	var result: Dictionary = {"node_count": state.get_node_count(),
		"connections": state.get_connection_count(), "inherited": state.get_base_scene_state() != null,
		"source_sha256": FileAccess.get_sha256(SCENE_PATH), "nodes": []}
	if state.get_node_count() < 1 or state.get_node_count() > 64:
		_failed = true
		return result
	for index: int in range(state.get_node_count()):
		var properties: Array[Dictionary] = []
		for property_index: int in range(state.get_node_property_count(index)):
			properties.append({"name": str(state.get_node_property_name(index, property_index)),
				"value": _value(state.get_node_property_value(index, property_index))})
		result.nodes.append({"index": index, "path": str(state.get_node_path(index)),
			"parent": str(state.get_node_path(index, true)), "name": str(state.get_node_name(index)),
			"type": str(state.get_node_type(index)), "owner": str(state.get_node_owner_path(index)),
			"instanced": state.get_node_instance(index) != null,
			"placeholder": state.get_node_instance_placeholder(index),
			"groups": Array(state.get_node_groups(index)), "properties": properties})
	return result


func _walk(node: Node, scene_root: Node, rows: Array[Dictionary], depth: int) -> void:
	if depth > 16 or rows.size() >= 64 or not node is Node3D:
		_failed = true
		return
	var item: Dictionary = {"path": str(scene_root.get_path_to(node)), "name": str(node.name),
		"type": node.get_class(), "owner": str(scene_root.get_path_to(node.owner)) if node.owner != null else "",
		"stable_id": str(node.get_meta("hh_studio_id", "")),
		"transform_rows_origin": _transform((node as Node3D).transform), "mesh": null,
		"script_sha256": null, "exports": {}, "groups": Array(node.get_groups())}
	if node is MeshInstance3D:
		item.mesh = _value((node as MeshInstance3D).mesh)
	var script: Script = node.get_script() as Script
	if script != null:
		item.script_sha256 = script.source_code.sha256_text()
		item.exports = _exports(script as GDScript, node)
	rows.append(item)
	for child: Node in node.get_children():
		_walk(child, scene_root, rows, depth + 1)


func _semantic(root: Node3D) -> Dictionary:
	var serializer := SceneCommands.StoredSceneSnapshot.new()
	var snapshot: Dictionary = serializer.capture(root)
	if not snapshot.get("ok", false):
		_failed = true
		return {}
	return {"schema": "hh-godot-semantic-snapshot-1", "context_kind": "isolated_candidate",
		"serializer_sha256": FileAccess.get_sha256(SERIALIZER_PATH),
		"jcs_sha256": FileAccess.get_sha256(JCS_PATH),
		"state": snapshot.state, "revision": snapshot.revision}


func _initialize() -> void:
	var report: Dictionary = {"schema": "hh-godot-profile-readback-2", "public_ack": false,
		"engine_version": Engine.get_version_info().string, "pid": OS.get_process_id(), "ok": false}
	var script: GDScript = ResourceLoader.load(SCRIPT_PATH, "GDScript", ResourceLoader.CACHE_MODE_IGNORE) as GDScript
	if script == null:
		print("HH_PROFILE_READBACK " + JSON.stringify(report))
		quit(41)
		return
	var reload_code: int = script.reload(false)
	report.script = {"source_sha256": script.source_code.sha256_text(),
		"disk_sha256": FileAccess.get_sha256(SCRIPT_PATH),
		"uid_source": FileAccess.get_file_as_string(SCRIPT_PATH + ".uid"),
		"resource_uid": ResourceUID.id_to_text(ResourceLoader.get_resource_uid(SCRIPT_PATH)),
		"reload_code": reload_code, "can_instantiate": script.can_instantiate(),
		"base_type": str(script.get_instance_base_type()), "is_tool": script.is_tool(),
		"has_base_script": script.get_base_script() != null, "global_name": str(script.get_global_name()),
		"methods": _names(script.get_script_method_list()), "signals": _names(script.get_script_signal_list()),
		"constants": script.get_script_constant_map().keys(), "defaults": _exports(script)}
	if reload_code != OK or not script.can_instantiate():
		print("HH_PROFILE_READBACK " + JSON.stringify(report))
		quit(42)
		return
	var plain: Node3D = script.new() as Node3D
	if plain == null:
		_failed = true
	else:
		report.fresh_script = {"type": plain.get_class(), "exports": _exports(script, plain),
			"source_sha256": (plain.get_script() as Script).source_code.sha256_text()}
		plain.free()
	var scene: PackedScene = ResourceLoader.load(SCENE_PATH, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
	if scene == null:
		_failed = true
	else:
		report.scene = _state(scene)
		var instance: Node = scene.instantiate(PackedScene.GEN_EDIT_STATE_DISABLED)
		if instance == null:
			_failed = true
		else:
			var rows: Array[Dictionary] = []
			_walk(instance, instance, rows, 1)
			report.instance_nodes = rows
			report.semantic = _semantic(instance as Node3D)
			instance.free()
	report.ok = not _failed
	var encoded: String = JSON.stringify(report, "", true, true)
	if encoded.to_utf8_buffer().size() > MAX_REPORT_BYTES:
		print("HH_PROFILE_READBACK " + JSON.stringify({"schema": report.schema,
			"public_ack": false, "ok": false, "error": "SEMANTIC_REPORT_LIMIT"}))
		quit(44)
		return
	print("HH_PROFILE_READBACK " + encoded)
	quit(43 if _failed else 0)
