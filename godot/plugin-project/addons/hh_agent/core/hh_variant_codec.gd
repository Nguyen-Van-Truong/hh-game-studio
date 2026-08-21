class_name HHAgentVariantCodec
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")

## hh-godot-variant/1 encode/decode. No generic invoke.

const SCHEMA: String = "hh-godot-variant/1"
const VEC_ABS_MAX: float = 1000000.0
const CONTAINER_MAX: int = 256

var _errors: HHAgentErrors = HHAgentErrors.new()


func encode(value: Variant) -> Dictionary:
	var t: int = typeof(value)
	if t == TYPE_BOOL:
		return _ok("bool", value)
	if t == TYPE_INT:
		return _ok("int", value)
	if t == TYPE_FLOAT:
		return _ok("float", value)
	if t == TYPE_STRING or t == TYPE_STRING_NAME:
		return _ok("string", str(value))
	if t == TYPE_VECTOR2:
		var v2: Vector2 = value
		return _ok("Vector2", {"x": v2.x, "y": v2.y})
	if t == TYPE_VECTOR2I:
		var v2i: Vector2i = value
		return _ok("Vector2i", {"x": v2i.x, "y": v2i.y})
	if t == TYPE_VECTOR3:
		var v3: Vector3 = value
		return _ok("Vector3", {"x": v3.x, "y": v3.y, "z": v3.z})
	if t == TYPE_RECT2:
		var r: Rect2 = value
		return _ok("Rect2", {"x": r.position.x, "y": r.position.y, "w": r.size.x, "h": r.size.y})
	if t == TYPE_TRANSFORM2D:
		var xf: Transform2D = value
		return _ok("Transform2D", {
			"x": {"x": xf.x.x, "y": xf.x.y},
			"y": {"x": xf.y.x, "y": xf.y.y},
			"origin": {"x": xf.origin.x, "y": xf.origin.y},
		})
	if t == TYPE_TRANSFORM3D:
		var xf3: Transform3D = value
		return _ok("Transform3D", {
			"basis": {
				"x": {"x": xf3.basis.x.x, "y": xf3.basis.x.y, "z": xf3.basis.x.z},
				"y": {"x": xf3.basis.y.x, "y": xf3.basis.y.y, "z": xf3.basis.y.z},
				"z": {"x": xf3.basis.z.x, "y": xf3.basis.z.y, "z": xf3.basis.z.z},
			},
			"origin": {"x": xf3.origin.x, "y": xf3.origin.y, "z": xf3.origin.z},
		})
	if t == TYPE_COLOR:
		var c: Color = value
		return _ok("Color", {"r": c.r, "g": c.g, "b": c.b, "a": c.a})
	if t == TYPE_NODE_PATH:
		var np: String = str(value)
		if np.is_empty():
			return _ok("NodePath", null)
		return _ok("NodePath", np)
	if t == TYPE_RID:
		return _ok("RID", str(value))
	if t == TYPE_NIL:
		return _ok("Resource", null)
	if t == TYPE_OBJECT:
		if value == null:
			return _ok("Resource", null)
		if value is Resource:
			return _ok("Resource", _resource_ref(value as Resource))
		return _fail(HHAgentErrors.E_UNKNOWN_VARIANT_TYPE, "unsupported Object (not a Resource)", "value")
	if t == TYPE_ARRAY:
		return _encode_array(value)
	if t == TYPE_DICTIONARY:
		return _encode_dict(value)
	if t == TYPE_PACKED_BYTE_ARRAY:
		return _encode_packed_ints("int", Array(value))
	if t == TYPE_PACKED_INT32_ARRAY or t == TYPE_PACKED_INT64_ARRAY:
		return _encode_packed_ints("int", Array(value))
	if t == TYPE_PACKED_FLOAT32_ARRAY or t == TYPE_PACKED_FLOAT64_ARRAY:
		return _encode_packed_floats(Array(value))
	if t == TYPE_PACKED_STRING_ARRAY:
		return _encode_packed_strings(value)
	if t == TYPE_PACKED_VECTOR2_ARRAY:
		return _encode_packed_vec2(value)
	if t == TYPE_PACKED_VECTOR3_ARRAY:
		return _encode_packed_vec3(value)
	if t == TYPE_PACKED_COLOR_ARRAY:
		return _encode_packed_color(value)
	return _fail(HHAgentErrors.E_UNKNOWN_VARIANT_TYPE, "unsupported Variant typeof %d" % t, "value")


func decode(raw: Variant, path: String = "value") -> Dictionary:
	if typeof(raw) != TYPE_DICTIONARY:
		return _fail(HHAgentErrors.E_INVALID_TYPE, "variant must be an object", path)
	var rec: Dictionary = raw
	for key_v: Variant in rec.keys():
		var key: String = str(key_v)
		if key != "schema" and key != "type" and key != "value":
			return _fail(HHAgentErrors.E_UNKNOWN_PARAM, "unknown field %s" % key, "%s/%s" % [path, key])
	if str(rec.get("schema", "")) != SCHEMA:
		return _fail(HHAgentErrors.E_INVALID_VARIANT, "variant schema must be %s" % SCHEMA, "%s/schema" % path)
	var kind: String = str(rec.get("type", ""))
	if kind.is_empty():
		return _fail(HHAgentErrors.E_INVALID_TYPE, "variant type must be a string", "%s/type" % path)
	if not _known_type(kind):
		return _fail(HHAgentErrors.E_UNKNOWN_VARIANT_TYPE, "unknown Variant type %s" % kind, "%s/type" % path)
	return _decode_kind(kind, rec.get("value"), "%s/value" % path)


func hash_of(value: Variant) -> String:
	var enc: Dictionary = encode(value)
	if enc.get("ok", false) != true:
		return ""
	var body: Dictionary = {
		"schema": SCHEMA,
		"type": str(enc.get("type", "")),
		"value": enc.get("value"),
	}
	return _sha256(_canon(body))


func hash_encoded(encoded: Dictionary) -> String:
	if encoded.get("ok", false) != true:
		return ""
	var body: Dictionary = {
		"schema": SCHEMA,
		"type": str(encoded.get("type", "")),
		"value": encoded.get("value"),
	}
	return _sha256(_canon(body))


func snapshot(value: Variant) -> Variant:
	if value is Array:
		return (value as Array).duplicate(true)
	if value is Dictionary:
		return (value as Dictionary).duplicate(true)
	return value


func same(a: Variant, b: Variant) -> bool:
	var ea: Dictionary = encode(a)
	var eb: Dictionary = encode(b)
	if ea.get("ok", false) != true or eb.get("ok", false) != true:
		return false
	return _canon(ea.get("value")) == _canon(eb.get("value")) and str(ea.get("type", "")) == str(eb.get("type", ""))


func discover(info: Dictionary) -> Dictionary:
	var usage: int = int(info.get("usage", 0))
	var hint: int = int(info.get("hint", 0))
	var hint_string: String = str(info.get("hint_string", ""))
	var read_only: bool = (usage & PROPERTY_USAGE_READ_ONLY) != 0
	var internal: bool = (usage & PROPERTY_USAGE_INTERNAL) != 0
	var storage: bool = (usage & PROPERTY_USAGE_STORAGE) != 0
	var editor: bool = (usage & PROPERTY_USAGE_EDITOR) != 0
	var editor_only: bool = editor and not storage
	var out: Dictionary = {
		"name": str(info.get("name", "")),
		"type": int(info.get("type", 0)),
		"class_name": str(info.get("class_name", "")),
		"usage": usage,
		"hint": hint,
		"hint_string": hint_string,
		"read_only": read_only,
		"internal": internal,
		"editor_only": editor_only,
		"settable": not read_only and not internal and not editor_only,
	}
	if hint == PROPERTY_HINT_RANGE:
		out["range"] = _parse_range(hint_string)
	if hint == PROPERTY_HINT_ENUM or hint == PROPERTY_HINT_ENUM_SUGGESTION:
		out["enum_values"] = _enum_names(hint_string)
	if hint == PROPERTY_HINT_FLAGS:
		out["flags"] = _flag_names(hint_string)
	return out


func reject_usage(info: Dictionary) -> Dictionary:
	var usage: int = int(info.get("usage", 0))
	if usage & PROPERTY_USAGE_CATEGORY:
		return _fail(HHAgentErrors.E_INVALID_VARIANT, "category is not a settable property", "property")
	if usage & PROPERTY_USAGE_GROUP:
		return _fail(HHAgentErrors.E_INVALID_VARIANT, "group is not a settable property", "property")
	if usage & PROPERTY_USAGE_SUBGROUP:
		return _fail(HHAgentErrors.E_INVALID_VARIANT, "subgroup is not a settable property", "property")
	if usage & PROPERTY_USAGE_INTERNAL:
		return _fail(HHAgentErrors.E_INVALID_VARIANT, "internal property is rejected", "property")
	if usage & PROPERTY_USAGE_READ_ONLY:
		return _fail(HHAgentErrors.E_INVALID_VARIANT, "read-only property is rejected", "property")
	var storage: bool = (usage & PROPERTY_USAGE_STORAGE) != 0
	var editor: bool = (usage & PROPERTY_USAGE_EDITOR) != 0
	if editor and not storage:
		return _fail(HHAgentErrors.E_INVALID_VARIANT, "editor-only property is rejected", "property")
	return {}


func _as_int(value: Variant, path: String) -> Dictionary:
	if typeof(value) == TYPE_INT:
		return _ok("int", value)
	if typeof(value) == TYPE_FLOAT and is_equal_approx(float(value), round(float(value))):
		return _ok("int", int(round(float(value))))
	return _fail(HHAgentErrors.E_INVALID_TYPE, "int value must be an integer", path)


func validate_hints(info: Dictionary, decoded: Variant, kind: String) -> Dictionary:
	var hint: int = int(info.get("hint", 0))
	var hint_string: String = str(info.get("hint_string", ""))
	if hint == PROPERTY_HINT_ENUM and kind == "int":
		if typeof(decoded) != TYPE_INT:
			return _fail(HHAgentErrors.E_INVALID_TYPE, "enum property requires int", "value")
		var allowed: Dictionary = _enum_ints(hint_string)
		if not allowed.has(int(decoded)):
			return _fail(HHAgentErrors.E_INVALID_VARIANT, "enum value is not in hint", "value")
	if hint == PROPERTY_HINT_FLAGS and kind == "int":
		if typeof(decoded) != TYPE_INT:
			return _fail(HHAgentErrors.E_INVALID_TYPE, "flags property requires int", "value")
		var mask: int = _flag_mask(hint_string)
		if (int(decoded) & ~mask) != 0:
			return _fail(HHAgentErrors.E_INVALID_VARIANT, "flags value has bits outside hint", "value")
	if hint == PROPERTY_HINT_RANGE and (kind == "int" or kind == "float"):
		var rng: Dictionary = _parse_range(hint_string)
		if rng.get("ok", false) == true:
			var n: float = 0.0
			if typeof(decoded) == TYPE_INT or typeof(decoded) == TYPE_FLOAT:
				n = float(decoded)
			else:
				return _fail(HHAgentErrors.E_INVALID_TYPE, "range property requires a number", "value")
			if rng.get("or_less", false) != true and n < float(rng.get("min", 0.0)):
				return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "value below range min", "value")
			if rng.get("or_greater", false) != true and n > float(rng.get("max", 0.0)):
				return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "value above range max", "value")
	if kind == "RID":
		return _fail(HHAgentErrors.E_UNVERIFIED, "RID assignment is not reconstructible", "value")
	return {}


func types_compatible(prop_type: int, kind: String, decoded: Variant, class_name_s: String) -> Dictionary:
	if kind == "RID":
		return _fail(HHAgentErrors.E_UNVERIFIED, "RID assignment is not reconstructible", "value")
	if decoded == null:
		if kind == "Resource" and prop_type == TYPE_OBJECT:
			return {}
		if kind == "NodePath" and prop_type == TYPE_NODE_PATH:
			return {}
		return _fail(HHAgentErrors.E_INVALID_VARIANT, "null is only allowed for Resource and NodePath", "value")
	if prop_type == TYPE_NIL:
		return {}
	if kind == "bool" and prop_type == TYPE_BOOL:
		return {}
	if kind == "int" and prop_type == TYPE_INT:
		return {}
	if kind == "int" and prop_type == TYPE_FLOAT:
		return {}
	if kind == "float" and prop_type == TYPE_FLOAT:
		return {}
	if kind == "string" and (prop_type == TYPE_STRING or prop_type == TYPE_STRING_NAME):
		return {}
	if kind == "Vector2" and prop_type == TYPE_VECTOR2:
		return {}
	if kind == "Vector2i" and prop_type == TYPE_VECTOR2I:
		return {}
	if kind == "Vector3" and prop_type == TYPE_VECTOR3:
		return {}
	if kind == "Rect2" and prop_type == TYPE_RECT2:
		return {}
	if kind == "Transform2D" and prop_type == TYPE_TRANSFORM2D:
		return {}
	if kind == "Transform3D" and prop_type == TYPE_TRANSFORM3D:
		return {}
	if kind == "Color" and prop_type == TYPE_COLOR:
		return {}
	if kind == "NodePath" and prop_type == TYPE_NODE_PATH:
		return {}
	if kind == "Dictionary" and prop_type == TYPE_DICTIONARY:
		return {}
	if kind == "Array" and prop_type == TYPE_ARRAY:
		return {}
	if kind == "TypedArray" and _typed_array_prop(prop_type):
		return {}
	if kind == "Resource" and prop_type == TYPE_OBJECT:
		if decoded is Resource:
			var got_class: String = (decoded as Object).get_class()
			if class_name_s.is_empty():
				return {}
			if got_class == class_name_s or ClassDB.is_parent_class(got_class, class_name_s):
				return {}
			return _fail(HHAgentErrors.E_INVALID_TYPE, "Resource class %s is not %s" % [got_class, class_name_s], "value")
		return _fail(HHAgentErrors.E_INVALID_TYPE, "Resource value is not a Resource", "value")
	return _fail(HHAgentErrors.E_INVALID_TYPE, "Variant type %s does not match property type %d" % [kind, prop_type], "value")


func _typed_array_prop(prop_type: int) -> bool:
	if prop_type == TYPE_ARRAY:
		return true
	if prop_type >= TYPE_PACKED_BYTE_ARRAY and prop_type <= TYPE_PACKED_VECTOR4_ARRAY:
		return true
	return false


func to_packed(kind_element: String, items: Array, prop_type: int) -> Variant:
	if prop_type == TYPE_PACKED_VECTOR2_ARRAY:
		var packed2: PackedVector2Array = PackedVector2Array()
		for item_v: Variant in items:
			if item_v is Vector2:
				packed2.append(item_v)
		return packed2
	if prop_type == TYPE_PACKED_VECTOR3_ARRAY:
		var packed3: PackedVector3Array = PackedVector3Array()
		for item_v2: Variant in items:
			if item_v2 is Vector3:
				packed3.append(item_v2)
		return packed3
	if prop_type == TYPE_PACKED_COLOR_ARRAY:
		var packedc: PackedColorArray = PackedColorArray()
		for item_v3: Variant in items:
			if item_v3 is Color:
				packedc.append(item_v3)
		return packedc
	if prop_type == TYPE_PACKED_STRING_ARRAY:
		var packeds: PackedStringArray = PackedStringArray()
		for item_v4: Variant in items:
			packeds.append(str(item_v4))
		return packeds
	if prop_type == TYPE_PACKED_INT32_ARRAY:
		var packedi: PackedInt32Array = PackedInt32Array()
		for item_v5: Variant in items:
			packedi.append(int(item_v5))
		return packedi
	if prop_type == TYPE_PACKED_FLOAT32_ARRAY:
		var packedf: PackedFloat32Array = PackedFloat32Array()
		for item_v6: Variant in items:
			packedf.append(float(item_v6))
		return packedf
	return items


func _decode_kind(kind: String, value: Variant, path: String) -> Dictionary:
	if kind == "bool":
		if typeof(value) != TYPE_BOOL:
			return _fail(HHAgentErrors.E_INVALID_TYPE, "bool value must be boolean", path)
		return _ok(kind, value)
	if kind == "int":
		var as_int: Dictionary = _as_int(value, path)
		if as_int.get("ok", false) != true:
			return as_int
		return _ok(kind, as_int.get("value"))
	if kind == "float":
		if typeof(value) != TYPE_FLOAT and typeof(value) != TYPE_INT:
			return _fail(HHAgentErrors.E_INVALID_TYPE, "float value must be a finite number", path)
		return _ok(kind, float(value))
	if kind == "string":
		if typeof(value) != TYPE_STRING:
			return _fail(HHAgentErrors.E_INVALID_TYPE, "string value must be a string", path)
		return _ok(kind, value)
	if kind == "Vector2":
		return _decode_vec2(value, path, false, kind)
	if kind == "Vector2i":
		return _decode_vec2(value, path, true, kind)
	if kind == "Vector3":
		return _decode_vec3(value, path, kind)
	if kind == "Rect2":
		return _decode_rect2(value, path)
	if kind == "Transform2D":
		return _decode_xf2(value, path)
	if kind == "Transform3D":
		return _decode_xf3(value, path)
	if kind == "Color":
		return _decode_color(value, path)
	if kind == "NodePath":
		if value == null:
			return _ok(kind, NodePath(""))
		if typeof(value) != TYPE_STRING:
			return _fail(HHAgentErrors.E_INVALID_TYPE, "NodePath value must be a string or null", path)
		return _ok(kind, NodePath(str(value)))
	if kind == "RID":
		if typeof(value) != TYPE_STRING or str(value).is_empty():
			return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "RID string length 1..128", path)
		return _ok(kind, str(value))
	if kind == "Resource":
		return _decode_resource(value, path)
	if kind == "Array":
		return _decode_array(value, path)
	if kind == "Dictionary":
		return _decode_dict(value, path)
	if kind == "TypedArray":
		return _decode_typed_array(value, path)
	return _fail(HHAgentErrors.E_UNKNOWN_VARIANT_TYPE, "unknown Variant type %s" % kind, path)


func _decode_vec2(value: Variant, path: String, integer: bool, kind: String) -> Dictionary:
	if typeof(value) != TYPE_DICTIONARY:
		return _fail(HHAgentErrors.E_INVALID_TYPE, "vector value must be an object", path)
	var rec: Dictionary = value
	for key_v: Variant in rec.keys():
		var key: String = str(key_v)
		if key != "x" and key != "y":
			return _fail(HHAgentErrors.E_UNKNOWN_PARAM, "unknown field %s" % key, "%s/%s" % [path, key])
	if not rec.has("x") or not rec.has("y"):
		return _fail(HHAgentErrors.E_INVALID_TYPE, "vector needs x and y", path)
	if integer:
		var xi_d: Dictionary = _as_int(rec.get("x"), "%s/x" % path)
		if xi_d.get("ok", false) != true:
			return xi_d
		var yi_d: Dictionary = _as_int(rec.get("y"), "%s/y" % path)
		if yi_d.get("ok", false) != true:
			return yi_d
		var xi: int = int(xi_d.get("value"))
		var yi: int = int(yi_d.get("value"))
		if abs(xi) > int(VEC_ABS_MAX) or abs(yi) > int(VEC_ABS_MAX):
			return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "vector component out of range", path)
		return _ok(kind, Vector2i(xi, yi))
	if not _finite(rec.get("x")) or not _finite(rec.get("y")):
		return _fail(HHAgentErrors.E_INVALID_TYPE, "vector needs finite x and y", path)
	var xf: float = float(rec.get("x"))
	var yf: float = float(rec.get("y"))
	if abs(xf) > VEC_ABS_MAX or abs(yf) > VEC_ABS_MAX:
		return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "vector component out of range", path)
	return _ok(kind, Vector2(xf, yf))


func _decode_vec3(value: Variant, path: String, kind: String) -> Dictionary:
	if typeof(value) != TYPE_DICTIONARY:
		return _fail(HHAgentErrors.E_INVALID_TYPE, "Vector3 value must be an object", path)
	var rec: Dictionary = value
	for key_v: Variant in rec.keys():
		var key: String = str(key_v)
		if key != "x" and key != "y" and key != "z":
			return _fail(HHAgentErrors.E_UNKNOWN_PARAM, "unknown field %s" % key, "%s/%s" % [path, key])
	if not _finite(rec.get("x")) or not _finite(rec.get("y")) or not _finite(rec.get("z")):
		return _fail(HHAgentErrors.E_INVALID_TYPE, "Vector3 needs finite x, y, z", path)
	var x: float = float(rec.get("x"))
	var y: float = float(rec.get("y"))
	var z: float = float(rec.get("z"))
	if abs(x) > VEC_ABS_MAX or abs(y) > VEC_ABS_MAX or abs(z) > VEC_ABS_MAX:
		return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "Vector3 component out of range", path)
	return _ok(kind, Vector3(x, y, z))


func _decode_rect2(value: Variant, path: String) -> Dictionary:
	if typeof(value) != TYPE_DICTIONARY:
		return _fail(HHAgentErrors.E_INVALID_TYPE, "Rect2 value must be an object", path)
	var rec: Dictionary = value
	for key_v: Variant in rec.keys():
		var key: String = str(key_v)
		if key != "x" and key != "y" and key != "w" and key != "h":
			return _fail(HHAgentErrors.E_UNKNOWN_PARAM, "unknown field %s" % key, "%s/%s" % [path, key])
	if not _finite(rec.get("x")) or not _finite(rec.get("y")) or not _finite(rec.get("w")) or not _finite(rec.get("h")):
		return _fail(HHAgentErrors.E_INVALID_TYPE, "Rect2 needs finite x, y, w, h", path)
	var x: float = float(rec.get("x"))
	var y: float = float(rec.get("y"))
	var w: float = float(rec.get("w"))
	var h: float = float(rec.get("h"))
	if abs(x) > VEC_ABS_MAX or abs(y) > VEC_ABS_MAX or abs(w) > VEC_ABS_MAX or abs(h) > VEC_ABS_MAX:
		return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "Rect2 component out of range", path)
	return _ok("Rect2", Rect2(x, y, w, h))


func _decode_xf2(value: Variant, path: String) -> Dictionary:
	if typeof(value) != TYPE_DICTIONARY:
		return _fail(HHAgentErrors.E_INVALID_TYPE, "Transform2D value must be an object", path)
	var rec: Dictionary = value
	for key_v: Variant in rec.keys():
		var key: String = str(key_v)
		if key != "x" and key != "y" and key != "origin":
			return _fail(HHAgentErrors.E_UNKNOWN_PARAM, "unknown field %s" % key, "%s/%s" % [path, key])
	var x: Dictionary = _decode_vec2(rec.get("x"), "%s/x" % path, false, "Vector2")
	if x.get("ok", false) != true:
		return x
	var y: Dictionary = _decode_vec2(rec.get("y"), "%s/y" % path, false, "Vector2")
	if y.get("ok", false) != true:
		return y
	var origin: Dictionary = _decode_vec2(rec.get("origin"), "%s/origin" % path, false, "Vector2")
	if origin.get("ok", false) != true:
		return origin
	var xf: Transform2D = Transform2D(x.get("value") as Vector2, y.get("value") as Vector2, origin.get("value") as Vector2)
	return _ok("Transform2D", xf)


func _decode_xf3(value: Variant, path: String) -> Dictionary:
	if typeof(value) != TYPE_DICTIONARY:
		return _fail(HHAgentErrors.E_INVALID_TYPE, "Transform3D value must be an object", path)
	var rec: Dictionary = value
	for key_v: Variant in rec.keys():
		var key: String = str(key_v)
		if key != "basis" and key != "origin":
			return _fail(HHAgentErrors.E_UNKNOWN_PARAM, "unknown field %s" % key, "%s/%s" % [path, key])
	if typeof(rec.get("basis")) != TYPE_DICTIONARY:
		return _fail(HHAgentErrors.E_INVALID_TYPE, "Transform3D.basis must be an object", "%s/basis" % path)
	var basis: Dictionary = rec.get("basis")
	var bx: Dictionary = _decode_vec3(basis.get("x"), "%s/basis/x" % path, "Vector3")
	if bx.get("ok", false) != true:
		return bx
	var by: Dictionary = _decode_vec3(basis.get("y"), "%s/basis/y" % path, "Vector3")
	if by.get("ok", false) != true:
		return by
	var bz: Dictionary = _decode_vec3(basis.get("z"), "%s/basis/z" % path, "Vector3")
	if bz.get("ok", false) != true:
		return bz
	var origin: Dictionary = _decode_vec3(rec.get("origin"), "%s/origin" % path, "Vector3")
	if origin.get("ok", false) != true:
		return origin
	var b: Basis = Basis(bx.get("value") as Vector3, by.get("value") as Vector3, bz.get("value") as Vector3)
	return _ok("Transform3D", Transform3D(b, origin.get("value") as Vector3))


func _decode_color(value: Variant, path: String) -> Dictionary:
	if typeof(value) != TYPE_DICTIONARY:
		return _fail(HHAgentErrors.E_INVALID_TYPE, "Color value must be an object", path)
	var rec: Dictionary = value
	for key_v: Variant in rec.keys():
		var key: String = str(key_v)
		if key != "r" and key != "g" and key != "b" and key != "a":
			return _fail(HHAgentErrors.E_UNKNOWN_PARAM, "unknown field %s" % key, "%s/%s" % [path, key])
	for ch: String in ["r", "g", "b", "a"]:
		if not _finite(rec.get(ch)):
			return _fail(HHAgentErrors.E_INVALID_TYPE, "Color.%s must be a finite number" % ch, "%s/%s" % [path, ch])
		var n: float = float(rec.get(ch))
		if n < 0.0 or n > 1.0:
			return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "Color.%s must be 0..1" % ch, "%s/%s" % [path, ch])
	return _ok("Color", Color(float(rec.get("r")), float(rec.get("g")), float(rec.get("b")), float(rec.get("a"))))


func _decode_resource(value: Variant, path: String) -> Dictionary:
	if value == null:
		return _ok("Resource", null)
	if typeof(value) != TYPE_DICTIONARY:
		return _fail(HHAgentErrors.E_INVALID_TYPE, "Resource value must be an object or null", path)
	var rec: Dictionary = value
	for key_v: Variant in rec.keys():
		var key: String = str(key_v)
		if key != "uid" and key != "path" and key != "class_name":
			return _fail(HHAgentErrors.E_UNKNOWN_PARAM, "unknown field %s" % key, "%s/%s" % [path, key])
	var uid: String = str(rec.get("uid", ""))
	var res_path: String = str(rec.get("path", ""))
	var class_name_s: String = str(rec.get("class_name", ""))
	if uid.is_empty() and res_path.is_empty() and class_name_s.is_empty():
		return _fail(HHAgentErrors.E_INVALID_VARIANT, "Resource needs uid, path, or class_name", path)
	if not uid.is_empty():
		var id: int = ResourceUID.text_to_id(uid)
		if id == ResourceUID.INVALID_ID or not ResourceUID.has_id(id):
			return _fail(HHAgentErrors.E_UNVERIFIED, "uid is not in ResourceUID map", "%s/uid" % path)
		var mapped: String = ResourceUID.get_id_path(id)
		if mapped.is_empty() or not ResourceLoader.exists(mapped):
			return _fail(HHAgentErrors.E_UNVERIFIED, "uid has no loadable path", "%s/uid" % path)
		var loaded_uid: Resource = ResourceLoader.load(mapped)
		if loaded_uid == null:
			return _fail(HHAgentErrors.E_UNVERIFIED, "uid resource failed to load", "%s/uid" % path)
		return _ok("Resource", loaded_uid)
	if not res_path.is_empty():
		if not res_path.begins_with("res://") or res_path.contains(".."):
			return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "Resource.path must be a jailed res:// path", "%s/path" % path)
		if not ResourceLoader.exists(res_path):
			return _fail(HHAgentErrors.E_UNVERIFIED, "Resource.path missing", "%s/path" % path)
		var loaded_path: Resource = ResourceLoader.load(res_path)
		if loaded_path == null:
			return _fail(HHAgentErrors.E_UNVERIFIED, "Resource.path failed to load", "%s/path" % path)
		return _ok("Resource", loaded_path)
	if not ClassDB.class_exists(class_name_s):
		return _fail(HHAgentErrors.E_UNVERIFIED, "ClassDB has no class %s" % class_name_s, "%s/class_name" % path)
	if not ClassDB.can_instantiate(class_name_s):
		return _fail(HHAgentErrors.E_UNVERIFIED, "class %s is not instantiable" % class_name_s, "%s/class_name" % path)
	if class_name_s != "Resource" and not ClassDB.is_parent_class(class_name_s, "Resource"):
		return _fail(HHAgentErrors.E_INVALID_TYPE, "class_name must extend Resource", "%s/class_name" % path)
	var inst: Variant = ClassDB.instantiate(class_name_s)
	if inst == null or not (inst is Resource):
		if inst is Object:
			(inst as Object).free()
		return _fail(HHAgentErrors.E_UNVERIFIED, "failed to instantiate %s" % class_name_s, "%s/class_name" % path)
	return _ok("Resource", inst)


func _decode_array(value: Variant, path: String) -> Dictionary:
	if typeof(value) != TYPE_ARRAY:
		return _fail(HHAgentErrors.E_INVALID_TYPE, "Array value must be an array", path)
	var raw: Array = value
	if raw.size() > CONTAINER_MAX:
		return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "Array longer than %d" % CONTAINER_MAX, path)
	var out: Array = []
	var i: int = 0
	while i < raw.size():
		var item: Dictionary = decode(raw[i], "%s/%d" % [path, i])
		if item.get("ok", false) != true:
			return item
		out.append(item.get("value"))
		i += 1
	return _ok("Array", out)


func _decode_dict(value: Variant, path: String) -> Dictionary:
	var out: Dictionary = {}
	if typeof(value) == TYPE_ARRAY:
		var pairs: Array = value
		if pairs.size() > CONTAINER_MAX:
			return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "Dictionary longer than %d" % CONTAINER_MAX, path)
		var i: int = 0
		while i < pairs.size():
			if typeof(pairs[i]) != TYPE_DICTIONARY:
				return _fail(HHAgentErrors.E_INVALID_TYPE, "Dictionary pair must be an object", "%s/%d" % [path, i])
			var pair: Dictionary = pairs[i]
			var key_d: Dictionary = decode(pair.get("key"), "%s/%d/key" % [path, i])
			if key_d.get("ok", false) != true:
				return key_d
			var val_d: Dictionary = decode(pair.get("value"), "%s/%d/value" % [path, i])
			if val_d.get("ok", false) != true:
				return val_d
			out[key_d.get("value")] = val_d.get("value")
			i += 1
		return _ok("Dictionary", out)
	if typeof(value) != TYPE_DICTIONARY:
		return _fail(HHAgentErrors.E_INVALID_TYPE, "Dictionary value must be an object or pair array", path)
	var rec: Dictionary = value
	if rec.size() > CONTAINER_MAX:
		return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "Dictionary longer than %d" % CONTAINER_MAX, path)
	for key_v: Variant in rec.keys():
		var key: String = str(key_v)
		var item: Dictionary = decode(rec[key_v], "%s/%s" % [path, key])
		if item.get("ok", false) != true:
			return item
		out[key] = item.get("value")
	return _ok("Dictionary", out)


func _decode_typed_array(value: Variant, path: String) -> Dictionary:
	if typeof(value) != TYPE_DICTIONARY:
		return _fail(HHAgentErrors.E_INVALID_TYPE, "TypedArray value must be an object", path)
	var rec: Dictionary = value
	for key_v: Variant in rec.keys():
		var key: String = str(key_v)
		if key != "element" and key != "items":
			return _fail(HHAgentErrors.E_UNKNOWN_PARAM, "unknown field %s" % key, "%s/%s" % [path, key])
	var element: String = str(rec.get("element", ""))
	if not _known_type(element) or element == "TypedArray":
		return _fail(HHAgentErrors.E_UNKNOWN_VARIANT_TYPE, "unknown TypedArray element %s" % element, "%s/element" % path)
	if typeof(rec.get("items")) != TYPE_ARRAY:
		return _fail(HHAgentErrors.E_INVALID_TYPE, "TypedArray.items must be an array", "%s/items" % path)
	var items_raw: Array = rec.get("items")
	if items_raw.size() > CONTAINER_MAX:
		return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "TypedArray longer than %d" % CONTAINER_MAX, "%s/items" % path)
	var items: Array = []
	var i: int = 0
	while i < items_raw.size():
		var item_path: String = "%s/items/%d" % [path, i]
		var decoded: Dictionary
		if element == "Array" or element == "Dictionary":
			decoded = decode(items_raw[i], item_path)
		else:
			decoded = _decode_kind(element, items_raw[i], item_path)
		if decoded.get("ok", false) != true:
			return decoded
		items.append(decoded.get("value"))
		i += 1
	return {"ok": true, "type": "TypedArray", "element": element, "value": items}


func _encode_array(value: Variant) -> Dictionary:
	var raw: Array = value
	if raw.size() > CONTAINER_MAX:
		return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "Array longer than %d" % CONTAINER_MAX, "value")
	var items: Array = []
	for item_v: Variant in raw:
		var enc: Dictionary = encode(item_v)
		if enc.get("ok", false) != true:
			return enc
		items.append({
			"schema": SCHEMA,
			"type": str(enc.get("type", "")),
			"value": enc.get("value"),
		})
	return _ok("Array", items)


func _encode_dict(value: Variant) -> Dictionary:
	var rec: Dictionary = value
	if rec.size() > CONTAINER_MAX:
		return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "Dictionary longer than %d" % CONTAINER_MAX, "value")
	var out: Dictionary = {}
	var all_string: bool = true
	for key_v: Variant in rec.keys():
		if typeof(key_v) != TYPE_STRING and typeof(key_v) != TYPE_STRING_NAME:
			all_string = false
			break
	if all_string:
		for key_v2: Variant in rec.keys():
			var enc: Dictionary = encode(rec[key_v2])
			if enc.get("ok", false) != true:
				return enc
			out[str(key_v2)] = {
				"schema": SCHEMA,
				"type": str(enc.get("type", "")),
				"value": enc.get("value"),
			}
		return _ok("Dictionary", out)
	var pairs: Array = []
	for key_v3: Variant in rec.keys():
		var key_enc: Dictionary = encode(key_v3)
		if key_enc.get("ok", false) != true:
			return key_enc
		var val_enc: Dictionary = encode(rec[key_v3])
		if val_enc.get("ok", false) != true:
			return val_enc
		pairs.append({
			"key": {"schema": SCHEMA, "type": str(key_enc.get("type", "")), "value": key_enc.get("value")},
			"value": {"schema": SCHEMA, "type": str(val_enc.get("type", "")), "value": val_enc.get("value")},
		})
	return _ok("Dictionary", pairs)


func _encode_packed_ints(element: String, items: Array) -> Dictionary:
	if items.size() > CONTAINER_MAX:
		return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "TypedArray longer than %d" % CONTAINER_MAX, "value")
	var out: Array = []
	for item_v: Variant in items:
		out.append(int(item_v))
	return _ok("TypedArray", {"element": element, "items": out})


func _encode_packed_floats(items: Array) -> Dictionary:
	if items.size() > CONTAINER_MAX:
		return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "TypedArray longer than %d" % CONTAINER_MAX, "value")
	var out: Array = []
	for item_v: Variant in items:
		out.append(float(item_v))
	return _ok("TypedArray", {"element": "float", "items": out})


func _encode_packed_strings(value: Variant) -> Dictionary:
	var raw: PackedStringArray = value
	if raw.size() > CONTAINER_MAX:
		return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "TypedArray longer than %d" % CONTAINER_MAX, "value")
	var out: Array = []
	for item: String in raw:
		out.append(item)
	return _ok("TypedArray", {"element": "string", "items": out})


func _encode_packed_vec2(value: Variant) -> Dictionary:
	var raw: PackedVector2Array = value
	if raw.size() > CONTAINER_MAX:
		return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "TypedArray longer than %d" % CONTAINER_MAX, "value")
	var out: Array = []
	for item: Vector2 in raw:
		out.append({"x": item.x, "y": item.y})
	return _ok("TypedArray", {"element": "Vector2", "items": out})


func _encode_packed_vec3(value: Variant) -> Dictionary:
	var raw: PackedVector3Array = value
	if raw.size() > CONTAINER_MAX:
		return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "TypedArray longer than %d" % CONTAINER_MAX, "value")
	var out: Array = []
	for item: Vector3 in raw:
		out.append({"x": item.x, "y": item.y, "z": item.z})
	return _ok("TypedArray", {"element": "Vector3", "items": out})


func _encode_packed_color(value: Variant) -> Dictionary:
	var raw: PackedColorArray = value
	if raw.size() > CONTAINER_MAX:
		return _fail(HHAgentErrors.E_OUT_OF_BOUNDS, "TypedArray longer than %d" % CONTAINER_MAX, "value")
	var out: Array = []
	for item: Color in raw:
		out.append({"r": item.r, "g": item.g, "b": item.b, "a": item.a})
	return _ok("TypedArray", {"element": "Color", "items": out})


func _resource_ref(res: Resource) -> Dictionary:
	var out: Dictionary = {"class_name": res.get_class()}
	if not res.resource_path.is_empty():
		out["path"] = res.resource_path
		var uid: int = ResourceLoader.get_resource_uid(res.resource_path)
		if uid != ResourceUID.INVALID_ID:
			out["uid"] = ResourceUID.id_to_text(uid)
	return out


func _known_type(kind: String) -> bool:
	return kind in [
		"bool", "int", "float", "string",
		"Vector2", "Vector2i", "Vector3",
		"Rect2", "Transform2D", "Transform3D",
		"Color", "NodePath", "RID", "Resource",
		"Array", "Dictionary", "TypedArray",
	]


func _finite(value: Variant) -> bool:
	if typeof(value) == TYPE_INT:
		return true
	if typeof(value) == TYPE_FLOAT:
		return is_finite(float(value))
	return false


func _parse_range(hint_string: String) -> Dictionary:
	var parts: PackedStringArray = hint_string.split(",")
	var out: Dictionary = {"ok": false}
	if parts.size() < 2:
		return out
	if not parts[0].is_valid_float() or not parts[1].is_valid_float():
		return out
	out["ok"] = true
	out["min"] = float(parts[0])
	out["max"] = float(parts[1])
	out["or_greater"] = hint_string.contains("or_greater")
	out["or_less"] = hint_string.contains("or_less")
	return out


func _enum_ints(hint_string: String) -> Dictionary:
	var allowed: Dictionary = {}
	var parts: PackedStringArray = hint_string.split(",")
	var i: int = 0
	for part: String in parts:
		var val: int = i
		if part.contains(":"):
			var bits: PackedStringArray = part.rsplit(":", false, 1)
			if bits.size() == 2 and bits[1].is_valid_int():
				val = int(bits[1])
		allowed[val] = true
		i += 1
	return allowed


func _enum_names(hint_string: String) -> Array:
	var out: Array = []
	var parts: PackedStringArray = hint_string.split(",")
	var i: int = 0
	for part: String in parts:
		var name_s: String = part
		var val: int = i
		if part.contains(":"):
			var bits: PackedStringArray = part.rsplit(":", false, 1)
			name_s = bits[0]
			if bits.size() == 2 and bits[1].is_valid_int():
				val = int(bits[1])
		out.append({"name": name_s, "value": val})
		i += 1
	return out


func _flag_names(hint_string: String) -> Array:
	var out: Array = []
	var parts: PackedStringArray = hint_string.split(",")
	var bit: int = 0
	for part: String in parts:
		var name_s: String = part
		var val: int = 1 << bit
		if part.contains(":"):
			var bits: PackedStringArray = part.rsplit(":", false, 1)
			name_s = bits[0]
			if bits.size() == 2 and bits[1].is_valid_int():
				val = int(bits[1])
		out.append({"name": name_s, "value": val})
		bit += 1
	return out


func _flag_mask(hint_string: String) -> int:
	var mask: int = 0
	for item_v: Variant in _flag_names(hint_string):
		if item_v is Dictionary:
			mask |= int((item_v as Dictionary).get("value", 0))
	return mask


func _ok(kind: String, value: Variant) -> Dictionary:
	return {"ok": true, "schema": SCHEMA, "type": kind, "value": value}


func _fail(code: String, message: String, path: String) -> Dictionary:
	return {"ok": false, "error": _errors.typed(code, message, path)}


func _canon(value: Variant) -> String:
	var t: int = typeof(value)
	if t == TYPE_NIL:
		return "null"
	if t == TYPE_BOOL:
		return "true" if value == true else "false"
	if t == TYPE_INT:
		return str(int(value))
	if t == TYPE_FLOAT:
		var f: float = float(value)
		if is_equal_approx(f, round(f)):
			return str(int(round(f)))
		return "%.9g" % f
	if t == TYPE_STRING or t == TYPE_STRING_NAME:
		return JSON.stringify(str(value))
	if t == TYPE_ARRAY:
		var parts: PackedStringArray = PackedStringArray()
		for item_v: Variant in value:
			parts.append(_canon(item_v))
		return "[%s]" % ",".join(parts)
	if t == TYPE_DICTIONARY:
		var rec: Dictionary = value
		var keys: Array = rec.keys()
		keys.sort()
		var parts_d: PackedStringArray = PackedStringArray()
		for key_v: Variant in keys:
			parts_d.append("%s:%s" % [JSON.stringify(str(key_v)), _canon(rec[key_v])])
		return "{%s}" % ",".join(parts_d)
	return JSON.stringify(str(value))


func _sha256(text: String) -> String:
	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(text.to_utf8_buffer())
	return ctx.finish().hex_encode()
