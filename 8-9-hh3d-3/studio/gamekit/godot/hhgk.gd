extends RefCounted
## Shared helpers for gamekit tool scripts. Tool scripts run with
## `godot --path <game> --script <abs>/<tool>.gd -- --request <file.json>` and load this file with
## `load(get_script().resource_path.get_base_dir().path_join("hhgk.gd"))`.
## Results are printed as one line: HHGK_RESULT <json>.

const RESULT_MARKER: String = "HHGK_RESULT "
const MAX_DEPTH: int = 6
const MAX_INLINE_ITEMS: int = 64
const MAX_INLINE_TEXT: int = 4000
const DENIED_PROPS: PackedStringArray = [
	"script", "owner", "name", "scene_file_path", "multiplayer", "resource_path",
]
## Editor-facing aliases that Godot persists through another stored property.
const ALIAS_PROPS: PackedStringArray = ["rotation_degrees", "quaternion", "basis", "skew"]

static var _defaults_cache: Dictionary = {}
static var _props_cache: Dictionary = {}


static func emit(result: Dictionary) -> void:
	print(RESULT_MARKER + JSON.stringify(result, "", true, true))


static func fail(code: String, detail: String, extra: Dictionary = {}) -> Dictionary:
	var out: Dictionary = {"ok": false, "error": code, "detail": detail}
	out.merge(extra, true)
	return out


static func user_args() -> Dictionary:
	var out: Dictionary = {}
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var i: int = 0
	while i < args.size():
		var a: String = args[i]
		if a.begins_with("--"):
			var key: String = a.substr(2)
			if i + 1 < args.size() and not args[i + 1].begins_with("--"):
				out[key] = args[i + 1]
				i += 2
				continue
			out[key] = "1"
		i += 1
	return out


static func read_request() -> Variant:
	var path: String = str(user_args().get("request", ""))
	if path.is_empty() or not FileAccess.file_exists(path):
		return null
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if parsed is Dictionary:
		return parsed
	return null


# ------------------------------------------------------------------ Variant -> JSON


static func num(f: float) -> Variant:
	if is_nan(f):
		return "nan"
	if is_inf(f):
		return "inf" if f > 0.0 else "-inf"
	return f


static func to_json(value: Variant, depth: int = 0) -> Variant:
	match typeof(value):
		TYPE_NIL:
			return null
		TYPE_BOOL, TYPE_INT:
			return value
		TYPE_FLOAT:
			return num(value)
		TYPE_STRING:
			var s: String = value
			if s.length() > MAX_INLINE_TEXT:
				return {"$len": s.length(), "$sha256": s.sha256_text()}
			return s
		TYPE_STRING_NAME, TYPE_NODE_PATH:
			return str(value)
		TYPE_VECTOR2, TYPE_VECTOR2I:
			return [num(value.x), num(value.y)]
		TYPE_VECTOR3, TYPE_VECTOR3I:
			return [num(value.x), num(value.y), num(value.z)]
		TYPE_VECTOR4, TYPE_VECTOR4I, TYPE_QUATERNION:
			return [num(value.x), num(value.y), num(value.z), num(value.w)]
		TYPE_RECT2, TYPE_RECT2I:
			return [num(value.position.x), num(value.position.y), num(value.size.x), num(value.size.y)]
		TYPE_PLANE:
			return [num(value.normal.x), num(value.normal.y), num(value.normal.z), num(value.d)]
		TYPE_AABB:
			return [num(value.position.x), num(value.position.y), num(value.position.z),
				num(value.size.x), num(value.size.y), num(value.size.z)]
		TYPE_COLOR:
			return [num(value.r), num(value.g), num(value.b), num(value.a)]
		TYPE_TRANSFORM2D:
			var t2: Transform2D = value
			return [[num(t2.x.x), num(t2.x.y)], [num(t2.y.x), num(t2.y.y)], [num(t2.origin.x), num(t2.origin.y)]]
		TYPE_BASIS:
			return _basis_json(value)
		TYPE_TRANSFORM3D:
			var t3: Transform3D = value
			return {"basis": _basis_json(t3.basis), "origin": [num(t3.origin.x), num(t3.origin.y), num(t3.origin.z)]}
		TYPE_OBJECT:
			return _object_json(value, depth)
		TYPE_DICTIONARY:
			var d: Dictionary = value
			var out: Dictionary = {}
			for k: Variant in d.keys():
				out[str(k)] = to_json(d[k], depth + 1) if depth < MAX_DEPTH else "$depth"
			return out
		TYPE_ARRAY, TYPE_PACKED_BYTE_ARRAY, TYPE_PACKED_INT32_ARRAY, TYPE_PACKED_INT64_ARRAY, \
		TYPE_PACKED_FLOAT32_ARRAY, TYPE_PACKED_FLOAT64_ARRAY, TYPE_PACKED_STRING_ARRAY, \
		TYPE_PACKED_VECTOR2_ARRAY, TYPE_PACKED_VECTOR3_ARRAY, TYPE_PACKED_COLOR_ARRAY, \
		TYPE_PACKED_VECTOR4_ARRAY:
			var n: int = value.size()
			if n > MAX_INLINE_ITEMS or typeof(value) == TYPE_PACKED_BYTE_ARRAY and n > 16:
				return {"$len": n, "$sha256": _hash_variant(value)}
			var arr: Array = []
			for item: Variant in value:
				arr.append(to_json(item, depth + 1) if depth < MAX_DEPTH else "$depth")
			return arr
	return {"$type": type_string(typeof(value))}


static func _basis_json(b: Basis) -> Array:
	return [[num(b.x.x), num(b.x.y), num(b.x.z)], [num(b.y.x), num(b.y.y), num(b.y.z)],
		[num(b.z.x), num(b.z.y), num(b.z.z)]]


static func _hash_variant(value: Variant) -> String:
	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(var_to_bytes(value))
	return ctx.finish().hex_encode()


static func _object_json(value: Variant, depth: int) -> Variant:
	var obj: Object = value
	if obj == null:
		return null
	if obj is Resource:
		var res: Resource = obj
		var p: String = res.resource_path
		if not p.is_empty() and not p.contains("::"):
			return {"$res": p}
		if depth >= MAX_DEPTH:
			return {"$type": res.get_class()}
		return {"$type": res.get_class(), "props": stored_props(res, depth + 1)}
	if obj is Node:
		return {"$node": str((obj as Node).name)}
	return {"$type": obj.get_class()}


static func class_default(cls: String, prop: String) -> Variant:
	if not _defaults_cache.has(cls):
		var defaults: Dictionary = {}
		if ClassDB.can_instantiate(cls):
			var inst: Object = ClassDB.instantiate(cls)
			if inst != null:
				for info: Dictionary in inst.get_property_list():
					if int(info["usage"]) & PROPERTY_USAGE_STORAGE:
						defaults[str(info["name"])] = inst.get(info["name"])
				if inst is Node:
					(inst as Node).free()
		_defaults_cache[cls] = defaults
	var cached: Dictionary = _defaults_cache[cls]
	return cached.get(prop)


## Non-default stored properties of a Resource or Object, as JSON.
static func stored_props(obj: Object, depth: int = 0) -> Dictionary:
	var out: Dictionary = {}
	var cls: String = obj.get_class()
	for info: Dictionary in obj.get_property_list():
		var usage: int = int(info["usage"])
		if not (usage & PROPERTY_USAGE_STORAGE):
			continue
		var pname: String = str(info["name"])
		if pname == "resource_path" or pname == "resource_local_to_scene" and not obj.get(pname):
			continue
		var v: Variant = obj.get(pname)
		var def: Variant = class_default(cls, pname)
		if def != null and typeof(def) == typeof(v) and approx_equal(def, v):
			continue
		if def == null and v == null:
			continue
		out[pname] = to_json(v, depth)
	return out


# ------------------------------------------------------------------ JSON -> Variant


static func find_property(obj: Object, pname: String) -> Dictionary:
	var key: String = obj.get_class() + "|" + str(obj.get_script().resource_path if obj.get_script() != null else "")
	if not _props_cache.has(key):
		var table: Dictionary = {}
		for info: Dictionary in obj.get_property_list():
			table[str(info["name"])] = info
		_props_cache[key] = table
	var t: Dictionary = _props_cache[key]
	if not t.has(pname) and ALIAS_PROPS.has(pname) and obj.get(pname) != null:
		return {"name": pname, "type": typeof(obj.get(pname)), "hint": 0, "hint_string": "",
			"usage": PROPERTY_USAGE_EDITOR, "class_name": ""}
	return t.get(pname, {})


static func settable(info: Dictionary) -> bool:
	if info.is_empty():
		return false
	var usage: int = int(info["usage"])
	if usage & PROPERTY_USAGE_READ_ONLY:
		return false
	if usage & (PROPERTY_USAGE_CATEGORY | PROPERTY_USAGE_GROUP | PROPERTY_USAGE_SUBGROUP):
		return false
	if ALIAS_PROPS.has(str(info.get("name", ""))):
		return true
	return bool(usage & (PROPERTY_USAGE_STORAGE | PROPERTY_USAGE_EDITOR))


static func _is_num(v: Variant) -> bool:
	return typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT


static func _nums(v: Variant, n: int) -> bool:
	if not (v is Array) or (v as Array).size() != n:
		return false
	for x: Variant in v:
		if not _is_num(x) or is_nan(float(x)) or is_inf(float(x)):
			return false
	return true


static func _ok(v: Variant) -> Dictionary:
	return {"ok": true, "value": v}


static func _err(msg: String) -> Dictionary:
	return {"ok": false, "error": msg}


static func _enum_value(hint_string: String, name: String) -> Variant:
	var idx: int = 0
	var want: String = name.to_lower().replace(" ", "").replace("_", "")
	for part: String in hint_string.split(","):
		var label: String = part
		var value: int = idx
		if part.contains(":"):
			label = part.get_slice(":", 0)
			value = int(part.get_slice(":", 1))
		if label.to_lower().replace(" ", "").replace("_", "") == want:
			return value
		idx = value + 1
	return null


static func _check_range(info: Dictionary, f: float) -> String:
	if int(info.get("hint", 0)) != PROPERTY_HINT_RANGE:
		return ""
	var parts: PackedStringArray = str(info.get("hint_string", "")).split(",")
	if parts.size() < 2 or not parts[0].is_valid_float() or not parts[1].is_valid_float():
		return ""
	var lo: float = parts[0].to_float()
	var hi: float = parts[1].to_float()
	var or_greater: bool = parts.has("or_greater")
	var or_less: bool = parts.has("or_less")
	if f < lo and not or_less:
		return "value %s below range %s..%s" % [f, lo, hi]
	if f > hi and not or_greater:
		return "value %s above range %s..%s" % [f, lo, hi]
	return ""


## Convert a JSON value to the Variant type described by a property info dictionary.
## ctx keys: "resources" (allowed resource classes), "root" (scene root for $node values).
static func from_json(value: Variant, info: Dictionary, ctx: Dictionary, depth: int = 0) -> Dictionary:
	var t: int = int(info.get("type", TYPE_NIL))
	var hint: int = int(info.get("hint", 0))
	var hs: String = str(info.get("hint_string", ""))
	if depth > MAX_DEPTH:
		return _err("value nested too deep")
	match t:
		TYPE_BOOL:
			return _ok(value) if typeof(value) == TYPE_BOOL else _err("expected bool")
		TYPE_INT:
			if typeof(value) == TYPE_STRING and hint == PROPERTY_HINT_ENUM:
				var ev: Variant = _enum_value(hs, value)
				return _ok(int(ev)) if ev != null else _err("unknown enum name %s (allowed: %s)" % [value, hs])
			if value is Array and hint in [PROPERTY_HINT_LAYERS_2D_PHYSICS, PROPERTY_HINT_LAYERS_3D_PHYSICS,
					PROPERTY_HINT_LAYERS_2D_RENDER, PROPERTY_HINT_LAYERS_3D_RENDER,
					PROPERTY_HINT_LAYERS_2D_NAVIGATION, PROPERTY_HINT_LAYERS_3D_NAVIGATION,
					PROPERTY_HINT_LAYERS_AVOIDANCE]:
				var bits: int = 0
				for layer: Variant in value:
					if not _is_num(layer) or int(layer) < 1 or int(layer) > 32:
						return _err("layer numbers must be 1..32")
					bits |= 1 << (int(layer) - 1)
				return _ok(bits)
			if value is Array and hint == PROPERTY_HINT_FLAGS:
				var flags: int = 0
				for fname: Variant in value:
					var fv: Variant = _flag_value(hs, str(fname))
					if fv == null:
						return _err("unknown flag %s (allowed: %s)" % [fname, hs])
					flags |= int(fv)
				return _ok(flags)
			if not _is_num(value) or float(value) != floor(float(value)):
				return _err("expected integer")
			var rerr: String = _check_range(info, float(value))
			return _ok(int(value)) if rerr.is_empty() else _err(rerr)
		TYPE_FLOAT:
			if not _is_num(value) or is_nan(float(value)) or is_inf(float(value)):
				return _err("expected finite number")
			var ferr: String = _check_range(info, float(value))
			return _ok(float(value)) if ferr.is_empty() else _err(ferr)
		TYPE_STRING:
			return _ok(value) if typeof(value) == TYPE_STRING else _err("expected string")
		TYPE_STRING_NAME:
			return _ok(StringName(value)) if typeof(value) == TYPE_STRING else _err("expected string")
		TYPE_NODE_PATH:
			return _ok(NodePath(value)) if typeof(value) == TYPE_STRING else _err("expected node path string")
		TYPE_VECTOR2:
			return _ok(Vector2(value[0], value[1])) if _nums(value, 2) else _err("expected [x, y]")
		TYPE_VECTOR2I:
			return _ok(Vector2i(int(value[0]), int(value[1]))) if _nums(value, 2) else _err("expected [x, y]")
		TYPE_VECTOR3:
			return _ok(Vector3(value[0], value[1], value[2])) if _nums(value, 3) else _err("expected [x, y, z]")
		TYPE_VECTOR3I:
			return _ok(Vector3i(int(value[0]), int(value[1]), int(value[2]))) if _nums(value, 3) else _err("expected [x, y, z]")
		TYPE_VECTOR4:
			return _ok(Vector4(value[0], value[1], value[2], value[3])) if _nums(value, 4) else _err("expected [x, y, z, w]")
		TYPE_VECTOR4I:
			return _ok(Vector4i(int(value[0]), int(value[1]), int(value[2]), int(value[3]))) if _nums(value, 4) else _err("expected [x, y, z, w]")
		TYPE_QUATERNION:
			return _ok(Quaternion(value[0], value[1], value[2], value[3])) if _nums(value, 4) else _err("expected [x, y, z, w]")
		TYPE_RECT2:
			return _ok(Rect2(value[0], value[1], value[2], value[3])) if _nums(value, 4) else _err("expected [x, y, w, h]")
		TYPE_RECT2I:
			return _ok(Rect2i(int(value[0]), int(value[1]), int(value[2]), int(value[3]))) if _nums(value, 4) else _err("expected [x, y, w, h]")
		TYPE_PLANE:
			return _ok(Plane(value[0], value[1], value[2], value[3])) if _nums(value, 4) else _err("expected [a, b, c, d]")
		TYPE_AABB:
			if not _nums(value, 6):
				return _err("expected [px, py, pz, sx, sy, sz]")
			return _ok(AABB(Vector3(value[0], value[1], value[2]), Vector3(value[3], value[4], value[5])))
		TYPE_COLOR:
			return _color(value)
		TYPE_TRANSFORM2D:
			return _transform2d(value)
		TYPE_BASIS:
			return _basis(value)
		TYPE_TRANSFORM3D:
			return _transform3d(value)
		TYPE_OBJECT:
			return _object(value, info, ctx, depth)
		TYPE_DICTIONARY:
			return _ok(value) if value is Dictionary else _err("expected object")
		TYPE_ARRAY:
			return _array(value, info, ctx, depth)
		TYPE_PACKED_VECTOR2_ARRAY:
			var pv2: PackedVector2Array = PackedVector2Array()
			if not (value is Array):
				return _err("expected [[x, y], ...]")
			for item: Variant in value:
				if not _nums(item, 2):
					return _err("expected [[x, y], ...]")
				pv2.append(Vector2(item[0], item[1]))
			return _ok(pv2)
		TYPE_PACKED_VECTOR3_ARRAY:
			var pv3: PackedVector3Array = PackedVector3Array()
			if not (value is Array):
				return _err("expected [[x, y, z], ...]")
			for item: Variant in value:
				if not _nums(item, 3):
					return _err("expected [[x, y, z], ...]")
				pv3.append(Vector3(item[0], item[1], item[2]))
			return _ok(pv3)
		TYPE_PACKED_COLOR_ARRAY:
			var pc: PackedColorArray = PackedColorArray()
			if not (value is Array):
				return _err("expected list of colors")
			for item: Variant in value:
				var c: Dictionary = _color(item)
				if not c["ok"]:
					return c
				pc.append(c["value"])
			return _ok(pc)
		TYPE_PACKED_FLOAT32_ARRAY, TYPE_PACKED_FLOAT64_ARRAY, TYPE_PACKED_INT32_ARRAY, \
		TYPE_PACKED_INT64_ARRAY, TYPE_PACKED_BYTE_ARRAY:
			if not (value is Array):
				return _err("expected list of numbers")
			for item: Variant in value:
				if not _is_num(item):
					return _err("expected list of numbers")
			match t:
				TYPE_PACKED_FLOAT32_ARRAY:
					return _ok(PackedFloat32Array(value))
				TYPE_PACKED_FLOAT64_ARRAY:
					return _ok(PackedFloat64Array(value))
				TYPE_PACKED_INT32_ARRAY:
					return _ok(PackedInt32Array(value))
				TYPE_PACKED_INT64_ARRAY:
					return _ok(PackedInt64Array(value))
			return _ok(PackedByteArray(value))
		TYPE_PACKED_STRING_ARRAY:
			if not (value is Array):
				return _err("expected list of strings")
			var ps: PackedStringArray = PackedStringArray()
			for item: Variant in value:
				if typeof(item) != TYPE_STRING:
					return _err("expected list of strings")
				ps.append(item)
			return _ok(ps)
		TYPE_NIL:
			return _ok(value)
	return _err("unsupported property type " + type_string(t))


static func _flag_value(hint_string: String, name: String) -> Variant:
	var bit: int = 1
	for part: String in hint_string.split(","):
		var label: String = part
		var value: int = bit
		if part.contains(":"):
			label = part.get_slice(":", 0)
			value = int(part.get_slice(":", 1))
		if label.to_lower() == name.to_lower():
			return value
		bit = value << 1
	return null


static func _color(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_STRING:
		if Color.html_is_valid(value):
			return _ok(Color.html(value))
		var named: Color = Color.from_string(value, Color(-1, -1, -1, -1))
		return _ok(named) if named.r >= 0.0 else _err("unknown color " + str(value))
	if _nums(value, 3):
		return _ok(Color(value[0], value[1], value[2]))
	if _nums(value, 4):
		return _ok(Color(value[0], value[1], value[2], value[3]))
	return _err("expected [r, g, b(, a)] or #rrggbb")


static func _transform2d(value: Variant) -> Dictionary:
	if value is Array and (value as Array).size() == 3 and _nums(value[0], 2) and _nums(value[1], 2) and _nums(value[2], 2):
		return _ok(Transform2D(Vector2(value[0][0], value[0][1]), Vector2(value[1][0], value[1][1]),
			Vector2(value[2][0], value[2][1])))
	if value is Dictionary:
		var d: Dictionary = value
		var rot: float = deg_to_rad(float(d.get("rotation_degrees", 0.0))) if d.has("rotation_degrees") else float(d.get("rotation", 0.0))
		var pos: Variant = d.get("position", [0, 0])
		var scl: Variant = d.get("scale", [1, 1])
		if not _nums(pos, 2) or not _nums(scl, 2):
			return _err("transform2d needs position [x, y] and scale [x, y]")
		return _ok(Transform2D(rot, Vector2(scl[0], scl[1]), float(d.get("skew", 0.0)), Vector2(pos[0], pos[1])))
	return _err("expected [[xx, xy], [yx, yy], [ox, oy]] or {position, rotation_degrees, scale}")


static func _basis(value: Variant) -> Dictionary:
	if value is Array and (value as Array).size() == 3 and _nums(value[0], 3) and _nums(value[1], 3) and _nums(value[2], 3):
		return _ok(Basis(Vector3(value[0][0], value[0][1], value[0][2]), Vector3(value[1][0], value[1][1], value[1][2]),
			Vector3(value[2][0], value[2][1], value[2][2])))
	if value is Dictionary:
		var d: Dictionary = value
		var rd: Variant = d.get("rotation_degrees", [0, 0, 0])
		var scl: Variant = d.get("scale", [1, 1, 1])
		if not _nums(rd, 3) or not _nums(scl, 3):
			return _err("basis needs rotation_degrees [x, y, z] and scale [x, y, z]")
		var b: Basis = Basis.from_euler(Vector3(deg_to_rad(rd[0]), deg_to_rad(rd[1]), deg_to_rad(rd[2])))
		return _ok(b.scaled(Vector3(scl[0], scl[1], scl[2])))
	return _err("expected [[x], [y], [z]] columns or {rotation_degrees, scale}")


static func _transform3d(value: Variant) -> Dictionary:
	if not (value is Dictionary):
		return _err("expected {origin, basis} or {origin, rotation_degrees, scale}")
	var d: Dictionary = value
	var origin: Variant = d.get("origin", [0, 0, 0])
	if not _nums(origin, 3):
		return _err("origin must be [x, y, z]")
	var b: Dictionary = _basis(d["basis"]) if d.has("basis") else _basis(d)
	if not b["ok"]:
		return b
	return _ok(Transform3D(b["value"], Vector3(origin[0], origin[1], origin[2])))


static func _object(value: Variant, info: Dictionary, ctx: Dictionary, depth: int) -> Dictionary:
	if value == null:
		return _ok(null)
	if not (value is Dictionary):
		return _err("expected null, {\"$res\": path} or {\"$type\": Class, \"props\": {...}}")
	var d: Dictionary = value
	var hint: int = int(info.get("hint", 0))
	var allowed: PackedStringArray = str(info.get("hint_string", "")).split(",", false)
	if d.has("$node"):
		if hint != PROPERTY_HINT_NODE_TYPE and not ClassDB.is_parent_class(str(info.get("class_name", "")), "Node"):
			return _err("property does not take a node")
		var root: Node = ctx.get("root")
		var target: Node = root.get_node_or_null(NodePath(str(d["$node"]))) if root != null else null
		return _ok(target) if target != null else _err("node not found: " + str(d["$node"]))
	var res: Resource = null
	if d.has("$res"):
		var path: String = str(d["$res"])
		if not path.begins_with("res://") or path.contains(".."):
			return _err("resource path must be res:// inside the project")
		if not ResourceLoader.exists(path):
			return _err("resource does not exist (import the project?): " + path)
		res = load(path)
		if res == null:
			return _err("failed to load " + path)
	elif d.has("$type"):
		var cls: String = str(d["$type"])
		var ok_types: Array = ctx.get("resources", [])
		if not ok_types.has(cls):
			return _err("resource class not in gamekit catalog: " + cls)
		if not ClassDB.can_instantiate(cls) or not ClassDB.is_parent_class(cls, "Resource"):
			return _err("not an instantiable resource class: " + cls)
		res = ClassDB.instantiate(cls)
		var props: Variant = d.get("props", {})
		if not (props is Dictionary):
			return _err("props must be an object")
		var perr: String = set_props(res, props, ctx, depth + 1)
		if not perr.is_empty():
			return _err(cls + ": " + perr)
	else:
		return _err("object value needs $res, $type or $node")
	if hint == PROPERTY_HINT_RESOURCE_TYPE and not allowed.is_empty():
		var match_any: bool = false
		for a: String in allowed:
			if res.is_class(a.strip_edges()):
				match_any = true
		if not match_any:
			return _err("resource %s is not one of %s" % [res.get_class(), ",".join(allowed)])
	elif str(info.get("class_name", "")) != "" and not res.is_class(str(info["class_name"])):
		return _err("resource %s is not a %s" % [res.get_class(), info["class_name"]])
	return _ok(res)


static func _array(value: Variant, info: Dictionary, ctx: Dictionary, depth: int) -> Dictionary:
	if not (value is Array):
		return _err("expected list")
	var hs: String = str(info.get("hint_string", ""))
	var elem_info: Dictionary = {}
	if int(info.get("hint", 0)) == PROPERTY_HINT_ARRAY_TYPE and not hs.is_empty():
		var head: String = hs.get_slice(":", 0)
		var tail: String = hs.get_slice(":", 1) if hs.contains(":") else ""
		var etype: int = int(head.get_slice("/", 0)) if head.get_slice("/", 0).is_valid_int() else -1
		if etype >= 0:
			elem_info = {"type": etype, "hint": PROPERTY_HINT_RESOURCE_TYPE if etype == TYPE_OBJECT else 0,
				"hint_string": tail}
		elif ClassDB.class_exists(hs):
			elem_info = {"type": TYPE_OBJECT, "hint": PROPERTY_HINT_RESOURCE_TYPE, "hint_string": hs}
	var out: Array = []
	for item: Variant in value:
		if elem_info.is_empty():
			if item is Dictionary and ((item as Dictionary).has("$res") or (item as Dictionary).has("$type")):
				var r: Dictionary = _object(item, {"type": TYPE_OBJECT}, ctx, depth + 1)
				if not r["ok"]:
					return r
				out.append(r["value"])
			else:
				out.append(item)
		else:
			var c: Dictionary = from_json(item, elem_info, ctx, depth + 1)
			if not c["ok"]:
				return c
			out.append(c["value"])
	return _ok(out)


## Set validated properties on an object; returns "" or an error message. Each value is read back
## right after set() so silent clamping by a setter is reported instead of acknowledged.
static func set_props(obj: Object, props: Dictionary, ctx: Dictionary, depth: int = 0) -> String:
	for key: Variant in props.keys():
		var pname: String = str(key)
		if DENIED_PROPS.has(pname) or pname.begins_with("_"):
			return "property %s cannot be set here" % pname
		var info: Dictionary = find_property(obj, pname)
		if not settable(info):
			return "unknown or read-only property %s on %s" % [pname, obj.get_class()]
		var conv: Dictionary = from_json(props[key], info, ctx, depth)
		if not conv["ok"]:
			return "%s: %s" % [pname, conv["error"]]
		obj.set(pname, conv["value"])
		var back: Variant = obj.get(pname)
		if not approx_equal(back, conv["value"]):
			return "%s was not accepted by %s (read back %s)" % [pname, obj.get_class(), str(to_json(back))]
	return ""


static func approx_equal(a: Variant, b: Variant) -> bool:
	if typeof(a) != typeof(b):
		if _is_num(a) and _is_num(b):
			return is_equal_approx(float(a), float(b))
		return false
	match typeof(a):
		TYPE_FLOAT:
			return is_equal_approx(a, b) or (is_nan(a) and is_nan(b))
		TYPE_VECTOR2, TYPE_VECTOR3, TYPE_VECTOR4, TYPE_COLOR, TYPE_QUATERNION, TYPE_RECT2, \
		TYPE_TRANSFORM2D, TYPE_TRANSFORM3D, TYPE_BASIS, TYPE_AABB, TYPE_PLANE:
			return a.is_equal_approx(b)
		TYPE_ARRAY:
			var aa: Array = a
			var bb: Array = b
			if aa.size() != bb.size():
				return false
			for i: int in aa.size():
				if not approx_equal(aa[i], bb[i]):
					return false
			return true
	return a == b
