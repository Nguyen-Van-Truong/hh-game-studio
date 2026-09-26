extends SceneTree
## Trusted O2 reflection only. Does not instantiate or mutate catalog objects.

func _initialize() -> void:
	var document: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://catalog-input.json"))
	if not document is Dictionary or not document.get("classes") is Array:
		quit(31)
		return
	var classes: Array[Dictionary] = []
	for candidate: Dictionary in document["classes"]:
		var class_name_value: StringName = StringName(candidate["class_name"])
		var exists: bool = ClassDB.class_exists(class_name_value)
		var row: Dictionary = {"class_name": str(class_name_value), "exists": exists,
			"parent": "", "can_instantiate": false, "singleton": false, "properties": []}
		if exists:
			row["parent"] = str(ClassDB.get_parent_class(class_name_value))
			row["can_instantiate"] = ClassDB.can_instantiate(class_name_value)
			row["singleton"] = Engine.has_singleton(class_name_value)
			var native_properties: Array[Dictionary] = ClassDB.class_get_property_list(class_name_value, false)
			for property_name: String in candidate["properties"]:
				var matches: Array[Dictionary] = []
				for native: Dictionary in native_properties:
					if str(native["name"]) == property_name:
						matches.append({"name": property_name, "type": int(native["type"]),
							"class_name": str(native.get("class_name", "")), "hint": int(native["hint"]),
							"hint_string": str(native["hint_string"]), "usage": int(native["usage"]),
							"setter": str(ClassDB.class_get_property_setter(class_name_value, property_name))})
				row["properties"].append({"name": property_name, "matches": matches})
		classes.append(row)
	var report: Dictionary = {"schema": "hh-o2-classdb-observation-1", "pid": OS.get_process_id(),
		"engine_version": Engine.get_version_info(), "catalog_input_sha256": FileAccess.get_sha256("res://catalog-input.json"),
		"classes": classes, "runtime_authorized": false, "native_mutation": false}
	var encoded: String = JSON.stringify(report, "", true, true)
	if encoded.to_utf8_buffer().size() > 262144:
		quit(32)
		return
	print("HH_O2_CLASSDB " + encoded)
	quit(0)
