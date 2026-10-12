extends RefCounted
## Shared helpers for gamekit tool scripts. Tool scripts run with
## `godot --path <game> --script <abs>/<tool>.gd -- --request <file.json>` and preload this file with
## `preload("hhgk.gd")` (sibling of the tool script).
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


## JSON numbers arrive as int or float. Constructors reject Variant, so narrow here.
static func variant_int(value: Variant) -> int:
	if value is bool:
		var b: bool = value
		return int(b)
	if value is int:
		var n: int = value
		return n
	if value is float:
		var f: float = value
		return int(f)
	if value is String:
		var s: String = value
		return s.to_int()
	return 0


static func variant_float(value: Variant) -> float:
	if value is float:
		var f: float = value
		return f
	if value is int:
		var n: int = value
		return float(n)
	if value is bool:
		var b: bool = value
		return float(int(b))
	if value is String:
		var s: String = value
		return s.to_float()
	return 0.0


static func variant_bool(value: Variant) -> bool:
	if value is bool:
		var b: bool = value
		return b
	if value is int:
		var n: int = value
		return n != 0
	if value is float:
		var f: float = value
		return f != 0.0
	return false


static func _compf(value: Variant, index: int) -> float:
	var arr: Array = value
	return variant_float(arr[index])


static func _compi(value: Variant, index: int) -> int:
	var arr: Array = value
	return variant_int(arr[index])


static func to_json(value: Variant, depth: int = 0) -> Variant:
	match typeof(value):
		TYPE_NIL:
			return null
		TYPE_BOOL, TYPE_INT:
			return value
		TYPE_FLOAT:
			return num(variant_float(value))
		TYPE_STRING:
			var s: String = value
			if s.length() > MAX_INLINE_TEXT:
				return {"$len": s.length(), "$sha256": s.sha256_text()}
			return s
		TYPE_STRING_NAME, TYPE_NODE_PATH:
			return str(value)
		TYPE_VECTOR2:
			var v2: Vector2 = value
			return [num(v2.x), num(v2.y)]
		TYPE_VECTOR2I:
			var v2i: Vector2i = value
			return [num(float(v2i.x)), num(float(v2i.y))]
		TYPE_VECTOR3:
			var v3: Vector3 = value
			return [num(v3.x), num(v3.y), num(v3.z)]
		TYPE_VECTOR3I:
			var v3i: Vector3i = value
			return [num(float(v3i.x)), num(float(v3i.y)), num(float(v3i.z))]
		TYPE_VECTOR4:
			var v4: Vector4 = value
			return [num(v4.x), num(v4.y), num(v4.z), num(v4.w)]
		TYPE_VECTOR4I:
			var v4i: Vector4i = value
			return [num(float(v4i.x)), num(float(v4i.y)), num(float(v4i.z)), num(float(v4i.w))]
		TYPE_QUATERNION:
			var quat: Quaternion = value
			return [num(quat.x), num(quat.y), num(quat.z), num(quat.w)]
		TYPE_RECT2:
			var r2: Rect2 = value
			return [num(r2.position.x), num(r2.position.y), num(r2.size.x), num(r2.size.y)]
		TYPE_RECT2I:
			var r2i: Rect2i = value
			return [num(float(r2i.position.x)), num(float(r2i.position.y)), num(float(r2i.size.x)), num(float(r2i.size.y))]
		TYPE_PLANE:
			var plane: Plane = value
			return [num(plane.normal.x), num(plane.normal.y), num(plane.normal.z), num(plane.d)]
		TYPE_AABB:
			var box: AABB = value
			return [num(box.position.x), num(box.position.y), num(box.position.z),
				num(box.size.x), num(box.size.y), num(box.size.z)]
		TYPE_COLOR:
			var col: Color = value
			return [num(col.r), num(col.g), num(col.b), num(col.a)]
		TYPE_TRANSFORM2D:
			var t2: Transform2D = value
			return [[num(t2.x.x), num(t2.x.y)], [num(t2.y.x), num(t2.y.y)], [num(t2.origin.x), num(t2.origin.y)]]
		TYPE_BASIS:
			var basis: Basis = value
			return _basis_json(basis)
		TYPE_TRANSFORM3D:
			var t3: Transform3D = value
			return {"basis": _basis_json(t3.basis), "origin": [num(t3.origin.x), num(t3.origin.y), num(t3.origin.z)]}
		TYPE_OBJECT:
			return _object_json(value, depth)
		TYPE_DICTIONARY:
			var d: Dictionary = value
			var out: Dictionary = {}
			for k: Variant in d.keys():
				var child: Variant = d[k]
				out[str(k)] = to_json(child, depth + 1) if depth < MAX_DEPTH else "$depth"
			return out
		TYPE_ARRAY, TYPE_PACKED_BYTE_ARRAY, TYPE_PACKED_INT32_ARRAY, TYPE_PACKED_INT64_ARRAY, \
		TYPE_PACKED_FLOAT32_ARRAY, TYPE_PACKED_FLOAT64_ARRAY, TYPE_PACKED_STRING_ARRAY, \
		TYPE_PACKED_VECTOR2_ARRAY, TYPE_PACKED_VECTOR3_ARRAY, TYPE_PACKED_COLOR_ARRAY, \
		TYPE_PACKED_VECTOR4_ARRAY:
			var items: Array = value
			var n: int = items.size()
			if n > MAX_INLINE_ITEMS or typeof(value) == TYPE_PACKED_BYTE_ARRAY and n > 16:
				return {"$len": n, "$sha256": _hash_variant(value)}
			var arr: Array = []
			for item: Variant in items:
				arr.append(to_json(item, depth + 1) if depth < MAX_DEPTH else "$depth")
			return arr
	return {"$type": type_string(typeof(value))}


static func _basis_json(b: Basis) -> Array:
	return [[num(b.x.x), num(b.x.y), num(b.x.z)], [num(b.y.x), num(b.y.y), num(b.y.z)],
		[num(b.z.x), num(b.z.y), num(b.z.z)]]


static func _hash_variant(value: Variant) -> String:
	var ctx: HashingContext = HashingContext.new()
	var start_err: Error = ctx.start(HashingContext.HASH_SHA256)
	var update_err: Error = ctx.update(var_to_bytes(value))
	if start_err != OK or update_err != OK:
		return ""
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
					var usage: int = info["usage"]
					if usage & PROPERTY_USAGE_STORAGE:
						var pname: String = str(info["name"])
						defaults[pname] = inst.get(pname)
				if inst is Node:
					var node: Node = inst
					node.free()
		_defaults_cache[cls] = defaults
	var cached_v: Variant = _defaults_cache[cls]
	var cached: Dictionary = cached_v
	return cached.get(prop)


## Non-default stored properties of a Resource or Object, as JSON.
static func stored_props(obj: Object, depth: int = 0) -> Dictionary:
	var out: Dictionary = {}
	var cls: String = obj.get_class()
	for info: Dictionary in obj.get_property_list():
		var usage: int = info["usage"]
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
	# Never cache: usage depends on other values (emission_shape, Curve2D point_count, ...).
	for info: Dictionary in obj.get_property_list():
		if str(info["name"]) == pname:
			return info
	if ALIAS_PROPS.has(pname) and obj.get(pname) != null:
		return {"name": pname, "type": typeof(obj.get(pname)), "hint": 0, "hint_string": "",
			"usage": PROPERTY_USAGE_EDITOR, "class_name": ""}
	return {}


static func settable(info: Dictionary) -> bool:
	if info.is_empty():
		return false
	var usage: int = info["usage"]
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
	if not (v is Array):
		return false
	var arr: Array = v
	if arr.size() != n:
		return false
	for x: Variant in arr:
		if not _is_num(x):
			return false
		var f: float = variant_float(x)
		if is_nan(f) or is_inf(f):
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
	if variant_int(info.get("hint", 0)) != PROPERTY_HINT_RANGE:
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
	var t: int = variant_int(info.get("type", TYPE_NIL))
	var hint: int = variant_int(info.get("hint", 0))
	var hs: String = str(info.get("hint_string", ""))
	if depth > MAX_DEPTH:
		return _err("value nested too deep")
	match t:
		TYPE_BOOL:
			return _ok(value) if typeof(value) == TYPE_BOOL else _err("expected bool")
		TYPE_INT:
			if typeof(value) == TYPE_STRING and hint == PROPERTY_HINT_ENUM:
				var enum_name: String = value
				var ev: Variant = _enum_value(hs, enum_name)
				return _ok(variant_int(ev)) if ev != null else _err("unknown enum name %s (allowed: %s)" % [value, hs])
			if value is Array and hint in [PROPERTY_HINT_LAYERS_2D_PHYSICS, PROPERTY_HINT_LAYERS_3D_PHYSICS,
					PROPERTY_HINT_LAYERS_2D_RENDER, PROPERTY_HINT_LAYERS_3D_RENDER,
					PROPERTY_HINT_LAYERS_2D_NAVIGATION, PROPERTY_HINT_LAYERS_3D_NAVIGATION,
					PROPERTY_HINT_LAYERS_AVOIDANCE]:
				var layers: Array = value
				var bits: int = 0
				for layer: Variant in layers:
					var layer_n: int = variant_int(layer)
					if not _is_num(layer) or layer_n < 1 or layer_n > 32:
						return _err("layer numbers must be 1..32")
					bits |= 1 << (layer_n - 1)
				return _ok(bits)
			if value is Array and hint == PROPERTY_HINT_FLAGS:
				var flag_names: Array = value
				var flags: int = 0
				for fname: Variant in flag_names:
					var fv: Variant = _flag_value(hs, str(fname))
					if fv == null:
						return _err("unknown flag %s (allowed: %s)" % [fname, hs])
					flags |= variant_int(fv)
				return _ok(flags)
			var iv: float = variant_float(value)
			if not _is_num(value) or iv != floor(iv):
				return _err("expected integer")
			var rerr: String = _check_range(info, iv)
			return _ok(variant_int(value)) if rerr.is_empty() else _err(rerr)
		TYPE_FLOAT:
			var fv: float = variant_float(value)
			if not _is_num(value) or is_nan(fv) or is_inf(fv):
				return _err("expected finite number")
			var ferr: String = _check_range(info, fv)
			return _ok(fv) if ferr.is_empty() else _err(ferr)
		TYPE_STRING:
			return _ok(value) if typeof(value) == TYPE_STRING else _err("expected string")
		TYPE_STRING_NAME:
			if typeof(value) != TYPE_STRING:
				return _err("expected string")
			var sname: String = value
			return _ok(StringName(sname))
		TYPE_NODE_PATH:
			if typeof(value) != TYPE_STRING:
				return _err("expected node path string")
			var path_s: String = value
			return _ok(NodePath(path_s))
		TYPE_VECTOR2:
			return _ok(Vector2(_compf(value, 0), _compf(value, 1))) if _nums(value, 2) else _err("expected [x, y]")
		TYPE_VECTOR2I:
			return _ok(Vector2i(_compi(value, 0), _compi(value, 1))) if _nums(value, 2) else _err("expected [x, y]")
		TYPE_VECTOR3:
			return _ok(Vector3(_compf(value, 0), _compf(value, 1), _compf(value, 2))) if _nums(value, 3) else _err("expected [x, y, z]")
		TYPE_VECTOR3I:
			return _ok(Vector3i(_compi(value, 0), _compi(value, 1), _compi(value, 2))) if _nums(value, 3) else _err("expected [x, y, z]")
		TYPE_VECTOR4:
			return _ok(Vector4(_compf(value, 0), _compf(value, 1), _compf(value, 2), _compf(value, 3))) if _nums(value, 4) else _err("expected [x, y, z, w]")
		TYPE_VECTOR4I:
			return _ok(Vector4i(_compi(value, 0), _compi(value, 1), _compi(value, 2), _compi(value, 3))) if _nums(value, 4) else _err("expected [x, y, z, w]")
		TYPE_QUATERNION:
			return _ok(Quaternion(_compf(value, 0), _compf(value, 1), _compf(value, 2), _compf(value, 3))) if _nums(value, 4) else _err("expected [x, y, z, w]")
		TYPE_RECT2:
			return _ok(Rect2(_compf(value, 0), _compf(value, 1), _compf(value, 2), _compf(value, 3))) if _nums(value, 4) else _err("expected [x, y, w, h]")
		TYPE_RECT2I:
			return _ok(Rect2i(_compi(value, 0), _compi(value, 1), _compi(value, 2), _compi(value, 3))) if _nums(value, 4) else _err("expected [x, y, w, h]")
		TYPE_PLANE:
			return _ok(Plane(_compf(value, 0), _compf(value, 1), _compf(value, 2), _compf(value, 3))) if _nums(value, 4) else _err("expected [a, b, c, d]")
		TYPE_AABB:
			if not _nums(value, 6):
				return _err("expected [px, py, pz, sx, sy, sz]")
			return _ok(AABB(Vector3(_compf(value, 0), _compf(value, 1), _compf(value, 2)), Vector3(_compf(value, 3), _compf(value, 4), _compf(value, 5))))
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
			var rows_v2: Array = value
			for item: Variant in rows_v2:
				if not _nums(item, 2):
					return _err("expected [[x, y], ...]")
				var _push2: bool = pv2.append(Vector2(_compf(item, 0), _compf(item, 1)))
			return _ok(pv2)
		TYPE_PACKED_VECTOR3_ARRAY:
			var pv3: PackedVector3Array = PackedVector3Array()
			if not (value is Array):
				return _err("expected [[x, y, z], ...]")
			var rows_v3: Array = value
			for item3: Variant in rows_v3:
				if not _nums(item3, 3):
					return _err("expected [[x, y, z], ...]")
				var _push3: bool = pv3.append(Vector3(_compf(item3, 0), _compf(item3, 1), _compf(item3, 2)))
			return _ok(pv3)
		TYPE_PACKED_COLOR_ARRAY:
			var pc: PackedColorArray = PackedColorArray()
			if not (value is Array):
				return _err("expected list of colors")
			var rows_c: Array = value
			for item_c: Variant in rows_c:
				var c: Dictionary = _color(item_c)
				if not variant_bool(c.get("ok", false)):
					return c
				var col: Color = c["value"]
				var _pushc: bool = pc.append(col)
			return _ok(pc)
		TYPE_PACKED_FLOAT32_ARRAY, TYPE_PACKED_FLOAT64_ARRAY, TYPE_PACKED_INT32_ARRAY, \
		TYPE_PACKED_INT64_ARRAY, TYPE_PACKED_BYTE_ARRAY:
			if not (value is Array):
				return _err("expected list of numbers")
			var nums: Array = value
			for item_n: Variant in nums:
				if not _is_num(item_n):
					return _err("expected list of numbers")
			match t:
				TYPE_PACKED_FLOAT32_ARRAY:
					return _ok(PackedFloat32Array(nums))
				TYPE_PACKED_FLOAT64_ARRAY:
					return _ok(PackedFloat64Array(nums))
				TYPE_PACKED_INT32_ARRAY:
					return _ok(PackedInt32Array(nums))
				TYPE_PACKED_INT64_ARRAY:
					return _ok(PackedInt64Array(nums))
			return _ok(PackedByteArray(nums))
		TYPE_PACKED_STRING_ARRAY:
			if not (value is Array):
				return _err("expected list of strings")
			var ps: PackedStringArray = PackedStringArray()
			var rows_s: Array = value
			for item_s: Variant in rows_s:
				if typeof(item_s) != TYPE_STRING:
					return _err("expected list of strings")
				var text: String = item_s
				var _pushs: bool = ps.append(text)
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
		var html: String = value
		if Color.html_is_valid(html):
			return _ok(Color.html(html))
		var named: Color = Color.from_string(html, Color(-1, -1, -1, -1))
		return _ok(named) if named.r >= 0.0 else _err("unknown color " + html)
	if _nums(value, 3):
		return _ok(Color(_compf(value, 0), _compf(value, 1), _compf(value, 2)))
	if _nums(value, 4):
		return _ok(Color(_compf(value, 0), _compf(value, 1), _compf(value, 2), _compf(value, 3)))
	return _err("expected [r, g, b(, a)] or #rrggbb")


static func _transform2d(value: Variant) -> Dictionary:
	if value is Array:
		var rows: Array = value
		if rows.size() == 3 and _nums(rows[0], 2) and _nums(rows[1], 2) and _nums(rows[2], 2):
			return _ok(Transform2D(Vector2(_compf(rows[0], 0), _compf(rows[0], 1)), Vector2(_compf(rows[1], 0), _compf(rows[1], 1)),
				Vector2(_compf(rows[2], 0), _compf(rows[2], 1))))
	if value is Dictionary:
		var d: Dictionary = value
		var rot_v: Variant = d.get("rotation_degrees", 0.0) if d.has("rotation_degrees") else d.get("rotation", 0.0)
		var rot: float = deg_to_rad(variant_float(rot_v))
		var pos: Variant = d.get("position", [0, 0])
		var scl: Variant = d.get("scale", [1, 1])
		if not _nums(pos, 2) or not _nums(scl, 2):
			return _err("transform2d needs position [x, y] and scale [x, y]")
		return _ok(Transform2D(rot, Vector2(_compf(scl, 0), _compf(scl, 1)), variant_float(d.get("skew", 0.0)), Vector2(_compf(pos, 0), _compf(pos, 1))))
	return _err("expected [[xx, xy], [yx, yy], [ox, oy]] or {position, rotation_degrees, scale}")


static func _basis(value: Variant) -> Dictionary:
	if value is Array:
		var cols: Array = value
		if cols.size() == 3 and _nums(cols[0], 3) and _nums(cols[1], 3) and _nums(cols[2], 3):
			return _ok(Basis(Vector3(_compf(cols[0], 0), _compf(cols[0], 1), _compf(cols[0], 2)),
				Vector3(_compf(cols[1], 0), _compf(cols[1], 1), _compf(cols[1], 2)),
				Vector3(_compf(cols[2], 0), _compf(cols[2], 1), _compf(cols[2], 2))))
	if value is Dictionary:
		var d: Dictionary = value
		var rd: Variant = d.get("rotation_degrees", [0, 0, 0])
		var scl: Variant = d.get("scale", [1, 1, 1])
		if not _nums(rd, 3) or not _nums(scl, 3):
			return _err("basis needs rotation_degrees [x, y, z] and scale [x, y, z]")
		var b: Basis = Basis.from_euler(Vector3(deg_to_rad(_compf(rd, 0)), deg_to_rad(_compf(rd, 1)), deg_to_rad(_compf(rd, 2))))
		return _ok(b.scaled(Vector3(_compf(scl, 0), _compf(scl, 1), _compf(scl, 2))))
	return _err("expected [[x], [y], [z]] columns or {rotation_degrees, scale}")


static func _transform3d(value: Variant) -> Dictionary:
	if not (value is Dictionary):
		return _err("expected {origin, basis} or {origin, rotation_degrees, scale}")
	var d: Dictionary = value
	var origin: Variant = d.get("origin", [0, 0, 0])
	if not _nums(origin, 3):
		return _err("origin must be [x, y, z]")
	var b: Dictionary = _basis(d["basis"]) if d.has("basis") else _basis(d)
	if not variant_bool(b.get("ok", false)):
		return b
	var basis: Basis = b["value"]
	return _ok(Transform3D(basis, Vector3(_compf(origin, 0), _compf(origin, 1), _compf(origin, 2))))


static func _object(value: Variant, info: Dictionary, ctx: Dictionary, depth: int) -> Dictionary:
	if value == null:
		return _ok(null)
	if not (value is Dictionary):
		return _err("expected null, {\"$res\": path} or {\"$type\": Class, \"props\": {...}}")
	var d: Dictionary = value
	var hint: int = variant_int(info.get("hint", 0))
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
		var props_d: Dictionary = props
		var perr: String = set_props(res, props_d, ctx, depth + 1)
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
	if variant_int(info.get("hint", 0)) == PROPERTY_HINT_ARRAY_TYPE and not hs.is_empty():
		var head: String = hs.get_slice(":", 0)
		var tail: String = hs.get_slice(":", 1) if hs.contains(":") else ""
		var head0: String = head.get_slice("/", 0)
		var etype: int = head0.to_int() if head0.is_valid_int() else -1
		if etype >= 0:
			elem_info = {"type": etype, "hint": PROPERTY_HINT_RESOURCE_TYPE if etype == TYPE_OBJECT else 0,
				"hint_string": tail}
		elif ClassDB.class_exists(hs):
			elem_info = {"type": TYPE_OBJECT, "hint": PROPERTY_HINT_RESOURCE_TYPE, "hint_string": hs}
	var out: Array = []
	for item: Variant in value:
		if elem_info.is_empty():
			if item is Dictionary:
				var item_d: Dictionary = item
				if item_d.has("$res") or item_d.has("$type"):
					var r: Dictionary = _object(item, {"type": TYPE_OBJECT}, ctx, depth + 1)
					if not variant_bool(r.get("ok", false)):
						return r
					out.append(r["value"])
				else:
					out.append(item)
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
			return is_equal_approx(variant_float(a), variant_float(b))
		return false
	var kind: int = typeof(a)
	if kind == TYPE_FLOAT:
		var fa: float = a
		var fb: float = b
		return is_equal_approx(fa, fb) or (is_nan(fa) and is_nan(fb))
	if kind == TYPE_VECTOR2:
		var a2: Vector2 = a
		var b2: Vector2 = b
		return a2.is_equal_approx(b2)
	if kind == TYPE_VECTOR3:
		var a3: Vector3 = a
		var b3: Vector3 = b
		return a3.is_equal_approx(b3)
	if kind == TYPE_VECTOR4:
		var a4: Vector4 = a
		var b4: Vector4 = b
		return a4.is_equal_approx(b4)
	if kind == TYPE_COLOR:
		var ac: Color = a
		var bc: Color = b
		return ac.is_equal_approx(bc)
	if kind == TYPE_QUATERNION:
		var aq: Quaternion = a
		var bq: Quaternion = b
		return aq.is_equal_approx(bq)
	if kind == TYPE_RECT2:
		var ar: Rect2 = a
		var br: Rect2 = b
		return ar.is_equal_approx(br)
	if kind == TYPE_TRANSFORM2D:
		var at2: Transform2D = a
		var bt2: Transform2D = b
		return at2.is_equal_approx(bt2)
	if kind == TYPE_TRANSFORM3D:
		var at3: Transform3D = a
		var bt3: Transform3D = b
		return at3.is_equal_approx(bt3)
	if kind == TYPE_BASIS:
		var ab: Basis = a
		var bb: Basis = b
		return ab.is_equal_approx(bb)
	if kind == TYPE_AABB:
		var a_box: AABB = a
		var b_box: AABB = b
		return a_box.is_equal_approx(b_box)
	if kind == TYPE_PLANE:
		var a_plane: Plane = a
		var b_plane: Plane = b
		return a_plane.is_equal_approx(b_plane)
	if kind == TYPE_ARRAY:
		var aa: Array = a
		var ba: Array = b
		if aa.size() != ba.size():
			return false
		for i: int in aa.size():
			if not approx_equal(aa[i], ba[i]):
				return false
		return true
	return a == b
