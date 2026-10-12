extends SceneTree
## gamekit scene tool: inspect / apply / readback / check on any text scene of a Godot project.
## The host (studio/gamekit/scene.py) validates first, checkpoints, renames the temp file into
## place and acknowledges only after a fresh process running mode=readback matches.

const HH = preload("hhgk.gd")
var classes: Array = []
var resources: Array = []
var root_node: Node = null
var expected: Array = []
var touched: Array = []


func _initialize() -> void:
	var req: Variant = HH.read_request()
	var result: Dictionary
	if req == null:
		result = HH.fail("BAD_REQUEST", "missing or invalid --request file")
	else:
		var r: Dictionary = req
		classes = r.get("classes", [])
		resources = r.get("resources", [])
		match str(r.get("mode", "")):
			"inspect":
				result = _inspect(r)
			"apply":
				result = _apply(r)
			"readback":
				result = _readback(r)
			"check":
				result = _check(r)
			"catalog":
				result = _catalog()
			_:
				result = HH.fail("BAD_REQUEST", "unknown mode")
	if root_node != null and is_instance_valid(root_node):
		root_node.free()
	HH.emit(result)
	var ok_flag: bool = result.get("ok", false)
	quit(0 if ok_flag else 3)


# ------------------------------------------------------------------ inspect / readback


func _load_packed(path: String) -> PackedScene:
	if not ResourceLoader.exists(path):
		return null
	var res: Resource = ResourceLoader.load(path, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE)
	if res is PackedScene:
		var packed: PackedScene = res
		return packed
	return null


func dump_state(packed: PackedScene) -> Dictionary:
	var st: SceneState = packed.get_state()
	var nodes: Array = []
	for i: int in st.get_node_count():
		var props: Dictionary = {}
		for j: int in st.get_node_property_count(i):
			props[str(st.get_node_property_name(i, j))] = HH.to_json(st.get_node_property_value(i, j))
		var inst: PackedScene = st.get_node_instance(i)
		var groups: Array = []
		for g: String in st.get_node_groups(i):
			groups.append(g)
		var parent_v: Variant = null
		if i > 0:
			parent_v = _clean_path(str(st.get_node_path(i, true)))
		var instance_v: Variant = null
		if inst != null:
			instance_v = inst.resource_path
		nodes.append({
			"path": _clean_path(str(st.get_node_path(i))),
			"parent": parent_v,
			"type": str(st.get_node_type(i)),
			"name": str(st.get_node_name(i)),
			"instance": instance_v,
			"groups": groups,
			"index": st.get_node_index(i),
			"props": props,
		})
	var conns: Array = []
	for c: int in st.get_connection_count():
		conns.append({
			"from": _clean_path(str(st.get_connection_source(c))),
			"signal": str(st.get_connection_signal(c)),
			"to": _clean_path(str(st.get_connection_target(c))),
			"method": str(st.get_connection_method(c)),
			"flags": st.get_connection_flags(c),
			"binds": HH.to_json(st.get_connection_binds(c)),
		})
	return {"nodes": nodes, "connections": conns, "node_count": nodes.size()}


func _clean_path(p: String) -> String:
	if p.begins_with("./"):
		return p.substr(2)
	return p


func _inspect(r: Dictionary) -> Dictionary:
	var path: String = str(r.get("scene", ""))
	var packed: PackedScene = _load_packed(path)
	if packed == null:
		return HH.fail("NOT_FOUND", "cannot load scene " + path)
	var out: Dictionary = {"ok": true, "scene": path}
	out.merge(dump_state(packed))
	return out


func _readback(r: Dictionary) -> Dictionary:
	var path: String = str(r.get("scene", ""))
	var packed: PackedScene = _load_packed(path)
	if packed == null:
		return HH.fail("NOT_FOUND", "cannot load scene " + path)
	var out: Dictionary = {"ok": true, "scene": path, "state": dump_state(packed)}
	var probes: Array = r.get("probes", [])
	var values: Array = []
	if not probes.is_empty():
		root_node = packed.instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE)
		for p: Variant in probes:
			var pd: Dictionary = p
			var node: Node = root_node.get_node_or_null(NodePath(str(pd["path"])))
			if node == null:
				values.append({"path": pd["path"], "prop": pd["prop"], "missing": true})
			else:
				values.append({"path": pd["path"], "prop": pd["prop"], "value": HH.to_json(node.get(str(pd["prop"])))})
	out["probes"] = values
	return out


# ------------------------------------------------------------------ apply


func _apply(r: Dictionary) -> Dictionary:
	var scene_path: String = str(r.get("scene", ""))
	var temp_out: String = str(r.get("temp_out", ""))
	if temp_out.is_empty() or not temp_out.begins_with("res://"):
		return HH.fail("BAD_REQUEST", "temp_out missing")
	var create: Variant = r.get("create")
	if create is Dictionary:
		var cd: Dictionary = create
		var rtype: String = str(cd.get("root_type", ""))
		if not classes.has(rtype) or not ClassDB.is_parent_class(rtype, "Node") or not ClassDB.can_instantiate(rtype):
			return HH.fail("VALIDATION_FAILED", "root type not allowed: " + rtype)
		var rname: String = str(cd.get("root_name", rtype))
		if rname.validate_node_name() != rname or rname.is_empty():
			return HH.fail("VALIDATION_FAILED", "invalid root name: " + rname)
		root_node = ClassDB.instantiate(rtype)
		root_node.name = rname
		var rprops: Variant = cd.get("props", {})
		if rprops is Dictionary:
			var rprops_d: Dictionary = rprops
			if not rprops_d.is_empty():
				var e0: String = HH.set_props(root_node, rprops_d, _ctx())
				if not e0.is_empty():
					return HH.fail("VALIDATION_FAILED", e0, {"op_index": -1})
				_expect(root_node, rprops_d)
	else:
		var packed: PackedScene = _load_packed(scene_path)
		if packed == null:
			return HH.fail("NOT_FOUND", "cannot load scene " + scene_path)
		root_node = packed.instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE)
		if root_node == null:
			return HH.fail("GODOT_FAILED", "cannot instantiate " + scene_path)
	var ops: Array = r.get("ops", [])
	for i: int in ops.size():
		var op: Dictionary = ops[i]
		var err: String = _run_op(op)
		if not err.is_empty():
			return HH.fail("VALIDATION_FAILED", err, {"op_index": i, "op": str(op.get("op", ""))})
	var out_scene: PackedScene = PackedScene.new()
	var perr: int = out_scene.pack(root_node)
	if perr != OK:
		return HH.fail("GODOT_FAILED", "pack failed: " + error_string(perr))
	var serr: int = ResourceSaver.save(out_scene, temp_out)
	if serr != OK:
		return HH.fail("GODOT_FAILED", "save failed: " + error_string(serr))
	var reloaded: PackedScene = _load_packed(temp_out)
	if reloaded == null:
		return HH.fail("GODOT_FAILED", "temp scene does not reload")
	return {"ok": true, "scene": scene_path, "temp_out": temp_out, "state": dump_state(reloaded),
		"expected": _final_expected(), "touched": _final_touched()}


func _ctx() -> Dictionary:
	return {"resources": resources, "root": root_node}


func _rel(node: Node) -> String:
	return str(root_node.get_path_to(node))


func _alive(node: Variant) -> bool:
	if not is_instance_valid(node):
		return false
	var n: Node = node
	return n == root_node or root_node.is_ancestor_of(n)


## Expected values are taken after the last op, at each node's final path (ops may rename,
## move or delete nodes after setting them); set_props already checked each value on set().
func _final_expected() -> Array:
	var out: Array = []
	var seen: Dictionary = {}
	for e: Variant in expected:
		var pair: Array = e
		if not _alive(pair[0]):
			continue
		var node: Node = pair[0]
		var key: String = _rel(node) + "|" + str(pair[1])
		if seen.has(key):
			continue
		seen[key] = true
		out.append({"path": _rel(node), "prop": str(pair[1]), "value": HH.to_json(node.get(str(pair[1])))})
	return out


func _final_touched() -> Array:
	var out: Array = []
	for t: Variant in touched:
		if t is String:
			out.append(t)
		elif t is Node:
			var touched_node: Node = t
			if _alive(touched_node):
				var p: String = _rel(touched_node)
				if not out.has(p):
					out.append(p)
	return out


func _expect(node: Node, props: Dictionary) -> void:
	for k: Variant in props.keys():
		expected.append([node, str(k)])


func _owned(path: String) -> Node:
	var node: Node = root_node.get_node_or_null(NodePath(path)) if path != "." else root_node
	if node == null:
		return null
	if node != root_node and node.owner != root_node:
		return null
	return node


func _check_name(parent: Node, name: String) -> String:
	if name.is_empty() or name.validate_node_name() != name:
		return "invalid node name: " + name
	if parent.has_node(NodePath(name)):
		return "sibling already named " + name
	return ""


func _set_owner_tree(node: Node, owned_before: Array) -> void:
	node.owner = root_node
	for n: Node in owned_before:
		if is_instance_valid(n) and n != node:
			n.owner = root_node


func _owned_descendants(node: Node) -> Array:
	var out: Array = []
	for child: Node in node.get_children(true):
		if child.owner == root_node:
			out.append(child)
			out.append_array(_owned_descendants(child))
	return out


func _run_op(op: Dictionary) -> String:
	var kind: String = str(op.get("op", ""))
	match kind:
		"node.create":
			return _op_create(op)
		"node.update":
			return _op_update(op)
		"node.delete":
			return _op_delete(op)
		"node.move":
			return _op_move(op)
		"node.rename":
			return _op_rename(op)
		"node.duplicate":
			return _op_duplicate(op)
		"resource.new":
			return _op_update({"path": op.get("path", ""), "props": {str(op.get("prop", "")): {
				"$type": op.get("type", ""), "props": op.get("props", {})}}})
		"resource.load":
			return _op_update({"path": op.get("path", ""), "props": {str(op.get("prop", "")): {"$res": op.get("res", "")}}})
		"resource.update":
			return _op_resource_update(op)
		"script.attach":
			return _op_script(op)
		"script.detach":
			var nd: Node = _owned(str(op.get("path", "")))
			if nd == null:
				return "node not found or inside an instance: " + str(op.get("path", ""))
			nd.set_script(null)
			touched.append(nd)
			return ""
		"instance.add":
			return _op_instance(op)
		"signal.connect":
			return _op_connect(op, true)
		"signal.disconnect":
			return _op_connect(op, false)
		"group.add", "group.remove":
			var ng: Node = _owned(str(op.get("path", "")))
			var group: String = str(op.get("group", ""))
			if ng == null:
				return "node not found or inside an instance: " + str(op.get("path", ""))
			if group.is_empty() or group.length() > 64:
				return "invalid group name"
			if kind == "group.add":
				ng.add_to_group(group, true)
			else:
				ng.remove_from_group(group)
			touched.append(ng)
			return ""
		"tileset.from_atlas":
			return _op_tileset(op)
		"tilemap.set_cells":
			return _op_cells(op)
		"tilemap.fill_rect":
			return _op_fill(op)
		"spriteframes.from_sheet":
			return _op_spriteframes(op)
		"animation.create":
			return _op_animation(op)
	return "unknown op: " + kind


func _op_create(op: Dictionary) -> String:
	var parent: Node = _owned(str(op.get("parent", ".")))
	if parent == null:
		return "parent not found or inside an instance: " + str(op.get("parent", "."))
	var type: String = str(op.get("type", ""))
	if not classes.has(type):
		return "node class not in gamekit catalog: " + type
	if not ClassDB.class_exists(type) or not ClassDB.can_instantiate(type) or not ClassDB.is_parent_class(type, "Node"):
		return "not an instantiable node class in this Godot: " + type
	var name: String = str(op.get("name", type))
	var nerr: String = _check_name(parent, name)
	if not nerr.is_empty():
		return nerr
	var node: Node = ClassDB.instantiate(type)
	node.name = name
	parent.add_child(node)
	node.owner = root_node
	if op.has("index"):
		parent.move_child(node, HH.variant_int(op["index"]))
	if HH.variant_bool(op.get("unique", false)):
		node.unique_name_in_owner = true
	var props: Variant = op.get("props", {})
	if props is Dictionary:
		var props_d: Dictionary = props
		var perr: String = HH.set_props(node, props_d, _ctx())
		if not perr.is_empty():
			return perr
		_expect(node, props_d)
	touched.append(node)
	return ""


func _op_update(op: Dictionary) -> String:
	var node: Node = _owned(str(op.get("path", "")))
	if node == null:
		return "node not found or inside an instance: " + str(op.get("path", ""))
	var props: Variant = op.get("props", {})
	if not (props is Dictionary):
		return "props must be a non-empty object"
	var props_d: Dictionary = props
	if props_d.is_empty():
		return "props must be a non-empty object"
	var perr: String = HH.set_props(node, props_d, _ctx())
	if not perr.is_empty():
		return perr
	_expect(node, props_d)
	touched.append(node)
	return ""


func _op_delete(op: Dictionary) -> String:
	var node: Node = _owned(str(op.get("path", "")))
	if node == null or node == root_node:
		return "cannot delete (missing, root or inside an instance): " + str(op.get("path", ""))
	var rel: String = _rel(node)
	node.get_parent().remove_child(node)
	node.free()
	touched.append("deleted:" + rel)
	return ""


func _op_move(op: Dictionary) -> String:
	var node: Node = _owned(str(op.get("path", "")))
	var parent: Node = _owned(str(op.get("parent", ".")))
	if node == null or node == root_node:
		return "cannot move (missing, root or inside an instance): " + str(op.get("path", ""))
	if parent == null:
		return "new parent not found: " + str(op.get("parent", ""))
	if parent == node or node.is_ancestor_of(parent):
		return "cannot move a node under itself"
	if parent != node.get_parent():
		var nerr: String = _check_name(parent, str(node.name))
		if not nerr.is_empty():
			return nerr
		var owned: Array = _owned_descendants(node)
		node.get_parent().remove_child(node)
		parent.add_child(node)
		_set_owner_tree(node, owned)
	if op.has("index"):
		parent.move_child(node, HH.variant_int(op["index"]))
	touched.append(node)
	return ""


func _op_rename(op: Dictionary) -> String:
	var node: Node = _owned(str(op.get("path", "")))
	if node == null:
		return "node not found or inside an instance: " + str(op.get("path", ""))
	var name: String = str(op.get("name", ""))
	if node == root_node:
		if name.is_empty() or name.validate_node_name() != name:
			return "invalid node name: " + name
	else:
		var nerr: String = _check_name(node.get_parent(), name)
		if not nerr.is_empty():
			return nerr
	node.name = name
	touched.append(node)
	return ""


func _op_duplicate(op: Dictionary) -> String:
	var node: Node = _owned(str(op.get("path", "")))
	if node == null or node == root_node:
		return "cannot duplicate (missing, root or inside an instance): " + str(op.get("path", ""))
	var parent: Node = node.get_parent()
	var name: String = str(op.get("name", ""))
	var nerr: String = _check_name(parent, name)
	if not nerr.is_empty():
		return nerr
	var flags: int = Node.DUPLICATE_SIGNALS | Node.DUPLICATE_GROUPS | Node.DUPLICATE_SCRIPTS | Node.DUPLICATE_USE_INSTANTIATION
	var dup: Node = node.duplicate(flags)
	dup.name = name
	parent.add_child(dup)
	dup.owner = root_node
	_own_like(node, dup)
	var props: Variant = op.get("props", {})
	if props is Dictionary:
		var props_d: Dictionary = props
		if not props_d.is_empty():
			var perr: String = HH.set_props(dup, props_d, _ctx())
			if not perr.is_empty():
				return perr
			_expect(dup, props_d)
	touched.append(dup)
	return ""


func _own_like(src: Node, dst: Node) -> void:
	for i: int in mini(src.get_child_count(), dst.get_child_count()):
		var s: Node = src.get_child(i)
		var d: Node = dst.get_child(i)
		if s.owner == root_node:
			d.owner = root_node
			_own_like(s, d)


func _op_resource_update(op: Dictionary) -> String:
	var node: Node = _owned(str(op.get("path", "")))
	if node == null:
		return "node not found or inside an instance: " + str(op.get("path", ""))
	var prop: String = str(op.get("prop", ""))
	var res: Variant = node.get(prop)
	if not (res is Resource):
		return "property %s does not hold a resource" % prop
	var r: Resource = res
	if not r.resource_path.is_empty() and not r.resource_path.contains("::"):
		return "%s is an external resource file (%s); edit that file instead" % [prop, r.resource_path]
	var props: Variant = op.get("props", {})
	if not (props is Dictionary):
		return "props must be a non-empty object"
	var props_d: Dictionary = props
	if props_d.is_empty():
		return "props must be a non-empty object"
	var perr: String = HH.set_props(r, props_d, _ctx())
	if not perr.is_empty():
		return perr
	expected.append([node, prop])
	touched.append(node)
	return ""


func _op_script(op: Dictionary) -> String:
	var node: Node = _owned(str(op.get("path", "")))
	if node == null:
		return "node not found or inside an instance: " + str(op.get("path", ""))
	var spath: String = str(op.get("script", ""))
	if not spath.ends_with(".gd") or not ResourceLoader.exists(spath):
		return "script missing or not .gd: " + spath
	var script: Script = ResourceLoader.load(spath, "Script", ResourceLoader.CACHE_MODE_IGNORE)
	if script == null or not script.can_instantiate():
		return "script does not compile: " + spath
	var base: String = str(script.get_instance_base_type())
	if not node.is_class(base):
		return "script extends %s but node is %s" % [base, node.get_class()]
	node.set_script(load(spath))
	var props: Variant = op.get("props", {})
	if props is Dictionary:
		var props_d: Dictionary = props
		if not props_d.is_empty():
			var perr: String = HH.set_props(node, props_d, _ctx())
			if not perr.is_empty():
				return perr
			_expect(node, props_d)
	touched.append(node)
	return ""


func _op_instance(op: Dictionary) -> String:
	var parent: Node = _owned(str(op.get("parent", ".")))
	if parent == null:
		return "parent not found or inside an instance: " + str(op.get("parent", "."))
	var spath: String = str(op.get("scene", ""))
	if not ResourceLoader.exists(spath):
		return "scene to instance does not exist (import the project?): " + spath
	var loaded: Resource = ResourceLoader.load(spath)
	var packed: PackedScene = null
	if loaded is PackedScene:
		packed = loaded
	if packed == null:
		return "not a scene: " + spath
	var name: String = str(op.get("name", spath.get_file().get_basename()))
	var nerr: String = _check_name(parent, name)
	if not nerr.is_empty():
		return nerr
	var inst: Node = packed.instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE)
	if inst == null:
		return "cannot instantiate " + spath
	inst.name = name
	parent.add_child(inst)
	inst.owner = root_node
	var props: Variant = op.get("props", {})
	if props is Dictionary:
		var props_d: Dictionary = props
		if not props_d.is_empty():
			var perr: String = HH.set_props(inst, props_d, _ctx())
			if not perr.is_empty():
				return perr
			_expect(inst, props_d)
	touched.append(inst)
	return ""


func _op_connect(op: Dictionary, connect_it: bool) -> String:
	var src: Node = _owned(str(op.get("from", "")))
	var dst: Node = _owned(str(op.get("to", "")))
	if src == null or dst == null:
		return "signal source or target not found"
	var sig: String = str(op.get("signal", ""))
	var method: String = str(op.get("method", ""))
	if not src.has_signal(sig):
		return "%s has no signal %s" % [src.name, sig]
	var callable: Callable = Callable(dst, method)
	if connect_it:
		if not dst.has_method(method):
			return "%s has no method %s (attach the script first)" % [dst.name, method]
		var binds: Array = op.get("binds", [])
		if not binds.is_empty():
			callable = callable.bindv(binds)
		if src.is_connected(sig, callable):
			return "already connected"
		var cerr: int = src.connect(sig, callable, CONNECT_PERSIST | HH.variant_int(op.get("flags", 0)))
		if cerr != OK:
			return "connect failed: " + error_string(cerr)
	else:
		if not src.is_connected(sig, callable):
			return "not connected"
		src.disconnect(sig, callable)
	touched.append(src)
	return ""


func _texture(path: String) -> Texture2D:
	if not ResourceLoader.exists(path):
		return null
	var loaded: Resource = load(path)
	if loaded is Texture2D:
		var tex: Texture2D = loaded
		return tex
	return null


func _op_tileset(op: Dictionary) -> String:
	var layer: TileMapLayer = _owned(str(op.get("path", ""))) as TileMapLayer
	if layer == null:
		return "TileMapLayer not found: " + str(op.get("path", ""))
	var tex: Texture2D = _texture(str(op.get("texture", "")))
	if tex == null:
		return "texture missing (import the project?): " + str(op.get("texture", ""))
	var size: Variant = op.get("tile_size", [16, 16])
	if not HH._nums(size, 2):
		return "tile_size must be [w, h]"
	var size_a: Array = size
	if HH.variant_int(size_a[0]) < 1 or HH.variant_int(size_a[1]) < 1:
		return "tile_size must be [w, h]"
	var ts_size: Vector2i = Vector2i(HH.variant_int(size_a[0]), HH.variant_int(size_a[1]))
	var ts: TileSet = TileSet.new()
	ts.tile_size = ts_size
	var src: TileSetAtlasSource = TileSetAtlasSource.new()
	src.texture = tex
	src.texture_region_size = ts_size
	var margins: Variant = op.get("margins", [0, 0])
	var sep: Variant = op.get("separation", [0, 0])
	if HH._nums(margins, 2):
		var margins_a: Array = margins
		src.margins = Vector2i(HH.variant_int(margins_a[0]), HH.variant_int(margins_a[1]))
	if HH._nums(sep, 2):
		var sep_a: Array = sep
		src.separation = Vector2i(HH.variant_int(sep_a[0]), HH.variant_int(sep_a[1]))
	var _source_id: int = ts.add_source(src, 0)
	var grid: Vector2i = src.get_atlas_grid_size()
	for y: int in grid.y:
		for x: int in grid.x:
			src.create_tile(Vector2i(x, y))
	var collide: Variant = op.get("collision", "none")
	if collide is String and collide == "all" or collide is Array:
		ts.add_physics_layer()
		var bits: int = HH.variant_int(op.get("collision_layer", 1))
		ts.set_physics_layer_collision_layer(0, bits)
		var hw: float = ts_size.x / 2.0
		var hh: float = ts_size.y / 2.0
		var square: PackedVector2Array = PackedVector2Array([Vector2(-hw, -hh), Vector2(hw, -hh), Vector2(hw, hh), Vector2(-hw, hh)])
		for y2: int in grid.y:
			for x2: int in grid.x:
				var coords: Vector2i = Vector2i(x2, y2)
				if collide is Array:
					var collide_a: Array = collide
					if not _has_coord(collide_a, coords):
						continue
				var td: TileData = src.get_tile_data(coords, 0)
				td.add_collision_polygon(0)
				td.set_collision_polygon_points(0, 0, square)
	layer.tile_set = ts
	expected.append([layer, "tile_set"])
	touched.append(layer)
	return ""


func _has_coord(list: Array, c: Vector2i) -> bool:
	for item: Variant in list:
		if HH._nums(item, 2):
			var pair: Array = item
			if HH.variant_int(pair[0]) == c.x and HH.variant_int(pair[1]) == c.y:
				return true
	return false


func _cell_ok(layer: TileMapLayer, source: int, atlas: Vector2i) -> String:
	if layer.tile_set == null:
		return "TileMapLayer has no tile_set (run tileset.from_atlas first)"
	if not layer.tile_set.has_source(source):
		return "tile source %d does not exist" % source
	var src: TileSetSource = layer.tile_set.get_source(source)
	if src is TileSetAtlasSource and not (src as TileSetAtlasSource).has_tile(atlas):
		return "atlas tile %s does not exist in source %d" % [atlas, source]
	return ""


func _op_cells(op: Dictionary) -> String:
	var layer: TileMapLayer = _owned(str(op.get("path", ""))) as TileMapLayer
	if layer == null:
		return "TileMapLayer not found: " + str(op.get("path", ""))
	var cells: Array = op.get("cells", [])
	var erase: Array = op.get("erase", [])
	if cells.size() + erase.size() > 20000:
		return "too many cells in one op (max 20000)"
	for c: Variant in cells:
		if not (c is Array):
			return "cell must be [x, y, source, atlas_x, atlas_y(, alt)]"
		var cell: Array = c
		if cell.size() < 5 or not HH._nums(cell.slice(0, 5), 5):
			return "cell must be [x, y, source, atlas_x, atlas_y(, alt)]"
		var atlas: Vector2i = Vector2i(HH.variant_int(cell[3]), HH.variant_int(cell[4]))
		var cell_source: int = HH.variant_int(cell[2])
		var cerr: String = _cell_ok(layer, cell_source, atlas)
		if not cerr.is_empty():
			return cerr
		var alt: int = 0
		if cell.size() > 5:
			alt = HH.variant_int(cell[5])
		layer.set_cell(Vector2i(HH.variant_int(cell[0]), HH.variant_int(cell[1])), cell_source, atlas, alt)
	for e: Variant in erase:
		if not HH._nums(e, 2):
			return "erase entries must be [x, y]"
		var erase_at: Array = e
		layer.erase_cell(Vector2i(HH.variant_int(erase_at[0]), HH.variant_int(erase_at[1])))
	expected.append([layer, "tile_map_data"])
	touched.append(layer)
	return ""


func _op_fill(op: Dictionary) -> String:
	var layer: TileMapLayer = _owned(str(op.get("path", ""))) as TileMapLayer
	if layer == null:
		return "TileMapLayer not found: " + str(op.get("path", ""))
	var rect: Variant = op.get("rect", [])
	var atlas_v: Variant = op.get("atlas", [0, 0])
	if not HH._nums(rect, 4) or not HH._nums(atlas_v, 2):
		return "fill_rect needs rect [x, y, w, h] and atlas [ax, ay]"
	var rect_a: Array = rect
	var atlas_a: Array = atlas_v
	var rect_w: int = HH.variant_int(rect_a[2])
	var rect_h: int = HH.variant_int(rect_a[3])
	if rect_w * rect_h > 20000 or rect_w < 1 or rect_h < 1:
		return "rect must be 1..20000 cells"
	var source: int = HH.variant_int(op.get("source", 0))
	var atlas: Vector2i = Vector2i(HH.variant_int(atlas_a[0]), HH.variant_int(atlas_a[1]))
	var cerr: String = _cell_ok(layer, source, atlas)
	if not cerr.is_empty():
		return cerr
	var origin_x: int = HH.variant_int(rect_a[0])
	var origin_y: int = HH.variant_int(rect_a[1])
	var alt: int = HH.variant_int(op.get("alt", 0))
	for y: int in rect_h:
		for x: int in rect_w:
			layer.set_cell(Vector2i(origin_x + x, origin_y + y), source, atlas, alt)
	expected.append([layer, "tile_map_data"])
	touched.append(layer)
	return ""


func _op_spriteframes(op: Dictionary) -> String:
	var node: Node = _owned(str(op.get("path", "")))
	if node == null or not (node is AnimatedSprite2D or node is AnimatedSprite3D):
		return "AnimatedSprite2D/3D not found: " + str(op.get("path", ""))
	var tex: Texture2D = _texture(str(op.get("texture", "")))
	if tex == null:
		return "texture missing (import the project?): " + str(op.get("texture", ""))
	var hf: int = HH.variant_int(op.get("hframes", 1))
	var vf: int = HH.variant_int(op.get("vframes", 1))
	if hf < 1 or vf < 1 or hf * vf > 4096:
		return "hframes and vframes must be >= 1"
	var fw: float = float(tex.get_width()) / float(hf)
	var fh: float = float(tex.get_height()) / float(vf)
	var anims: Variant = op.get("animations", {})
	if not (anims is Dictionary):
		return "animations must map name -> {frames, fps, loop}"
	var ad: Dictionary = anims
	if ad.is_empty():
		return "animations must map name -> {frames, fps, loop}"
	var sf: SpriteFrames = SpriteFrames.new()
	if not ad.has("default"):
		sf.remove_animation("default")
	for aname: Variant in ad.keys():
		if not (ad[aname] is Dictionary):
			return "animation %s must be {frames, fps, loop}" % aname
		var spec: Dictionary = ad[aname]
		var frames_v: Variant = spec.get("frames", [])
		if not (frames_v is Array):
			return "animation %s needs frames: [index, ...]" % aname
		var frames_a: Array = frames_v
		if frames_a.is_empty() or not HH._nums(frames_v, frames_a.size()):
			return "animation %s needs frames: [index, ...]" % aname
		var fps: float = HH.variant_float(spec.get("fps", 10.0))
		if not HH._is_num(spec.get("fps", 10.0)) or fps <= 0.0:
			return "animation %s fps must be > 0" % aname
		var an: StringName = StringName(str(aname))
		if not sf.has_animation(an):
			sf.add_animation(an)
		sf.set_animation_speed(an, fps)
		sf.set_animation_loop(an, HH.variant_bool(spec.get("loop", true)))
		for f: Variant in frames_a:
			var idx: int = HH.variant_int(f)
			if idx < 0 or idx >= hf * vf:
				return "frame %d outside sheet (%d frames)" % [idx, hf * vf]
			var at: AtlasTexture = AtlasTexture.new()
			at.atlas = tex
			var row: int = int(float(idx) / float(hf))
			at.region = Rect2((idx % hf) * fw, float(row) * fh, fw, fh)
			sf.add_frame(an, at)
	node.set("sprite_frames", sf)
	var auto: String = str(op.get("autoplay", ""))
	if not auto.is_empty():
		if not sf.has_animation(StringName(auto)):
			return "autoplay animation not defined: " + auto
		node.set("animation", StringName(auto))
		node.set("autoplay", auto)
	expected.append([node, "sprite_frames"])
	touched.append(node)
	return ""


func _track_info(base: Node, track_path: String) -> Dictionary:
	var np: NodePath = NodePath(track_path)
	var target: Node = base.get_node_or_null(NodePath(str(np.get_concatenated_names())))
	if target == null:
		return {}
	var sub: String = str(np.get_concatenated_subnames())
	if sub.is_empty():
		return {}
	var parts: PackedStringArray = sub.split(":")
	var info: Dictionary = HH.find_property(target, parts[0])
	if info.is_empty():
		return {}
	if parts.size() > 1:
		return {"type": TYPE_FLOAT, "hint": 0, "hint_string": ""}
	return info


func _op_animation(op: Dictionary) -> String:
	var player: AnimationPlayer = _owned(str(op.get("player", ""))) as AnimationPlayer
	if player == null:
		return "AnimationPlayer not found: " + str(op.get("player", ""))
	var base: Node = player.get_node_or_null(player.root_node)
	if base == null:
		return "AnimationPlayer root_node does not resolve"
	var name: String = str(op.get("name", ""))
	if name.is_empty() or name.contains("/"):
		return "animation name required (no /)"
	var anim: Animation = Animation.new()
	anim.length = maxf(HH.variant_float(op.get("length", 1.0)), 0.001)
	anim.step = HH.variant_float(op.get("step", 0.0333333))
	match str(op.get("loop", "none")):
		"linear":
			anim.loop_mode = Animation.LOOP_LINEAR
		"pingpong":
			anim.loop_mode = Animation.LOOP_PINGPONG
		_:
			anim.loop_mode = Animation.LOOP_NONE
	var tracks_v: Variant = op.get("tracks", [])
	if not (tracks_v is Array):
		return "each track must be {path, keys, type?, interp?, update?}"
	var tracks: Array = tracks_v
	for tv: Variant in tracks:
		if not (tv is Dictionary):
			return "each track must be {path, keys, type?, interp?, update?}"
		var track: Dictionary = tv
		var keys_v: Variant = track.get("keys", [])
		if not track.has("path") or not (keys_v is Array):
			return "each track must be {path, keys, type?, interp?, update?}"
		var tpath: String = str(track.get("path", ""))
		var ttype: String = str(track.get("type", "value"))
		var keys: Array = keys_v
		if ttype == "method":
			var target: Node = base.get_node_or_null(NodePath(tpath))
			if target == null:
				return "method track path does not resolve to a node: " + tpath
			var mi: int = anim.add_track(Animation.TYPE_METHOD)
			anim.track_set_path(mi, NodePath(tpath))
			for k: Variant in keys:
				if not (k is Array):
					return "method keys must be [[time, {\"method\": name, \"args\": [...]}], ...]"
				var pair: Array = k
				if pair.size() != 2 or not HH._is_num(pair[0]) or not (pair[1] is Dictionary):
					return "method keys must be [[time, {\"method\": name, \"args\": [...]}], ...]"
				var method_call: Dictionary = pair[1]
				var mname: String = str(method_call.get("method", ""))
				if mname.is_empty() or not target.has_method(mname):
					return "method track: %s has no method %s" % [tpath, mname]
				if not (method_call.get("args", []) is Array):
					return "method track args must be a list"
				var _method_key: int = anim.track_insert_key(mi, HH.variant_float(pair[0]), {"method": mname, "args": method_call.get("args", [])})
			continue
		if ttype != "value":
			return "track type must be value or method: " + ttype
		var info: Dictionary = _track_info(base, tpath)
		if info.is_empty():
			return "track path does not resolve to a property: " + tpath
		var ti: int = anim.add_track(Animation.TYPE_VALUE)
		anim.track_set_path(ti, NodePath(tpath))
		match str(track.get("interp", "linear")):
			"nearest":
				anim.track_set_interpolation_type(ti, Animation.INTERPOLATION_NEAREST)
			"cubic":
				anim.track_set_interpolation_type(ti, Animation.INTERPOLATION_CUBIC)
			_:
				anim.track_set_interpolation_type(ti, Animation.INTERPOLATION_LINEAR)
		if str(track.get("update", "continuous")) == "discrete":
			anim.value_track_set_update_mode(ti, Animation.UPDATE_DISCRETE)
		for k2: Variant in keys:
			if not (k2 is Array):
				return "keys must be [[time, value], ...]"
			var pair2: Array = k2
			if pair2.size() != 2 or not HH._is_num(pair2[0]):
				return "keys must be [[time, value], ...]"
			var conv: Dictionary = HH.from_json(pair2[1], info, _ctx())
			if not conv["ok"]:
				return "%s key: %s" % [tpath, conv["error"]]
			var _value_key: int = anim.track_insert_key(ti, HH.variant_float(pair2[0]), conv["value"])
	var lib_name: StringName = StringName(str(op.get("library", "")))
	var lib: AnimationLibrary
	if player.has_animation_library(lib_name):
		lib = player.get_animation_library(lib_name)
		if not lib.resource_path.is_empty() and not lib.resource_path.contains("::"):
			return "animation library is an external file; edit it separately"
	else:
		lib = AnimationLibrary.new()
		var lib_err: Error = player.add_animation_library(lib_name, lib)
		if lib_err != OK:
			return "add animation library failed: " + error_string(lib_err)
	if lib.has_animation(StringName(name)):
		if not HH.variant_bool(op.get("replace", false)):
			return "animation already exists (pass replace: true): " + name
		lib.remove_animation(StringName(name))
	var add_err: Error = lib.add_animation(StringName(name), anim)
	if add_err != OK:
		return "add animation failed: " + error_string(add_err)
	if HH.variant_bool(op.get("autoplay", false)):
		player.autoplay = name if str(lib_name).is_empty() else str(lib_name) + "/" + name
	expected.append([player, "libraries"])
	touched.append(player)
	return ""


# ------------------------------------------------------------------ catalog / check


func _catalog() -> Dictionary:
	var missing: Array = []
	var wrong_kind: Array = []
	for c: Variant in classes:
		var cls: String = str(c)
		if not ClassDB.class_exists(cls):
			missing.append(cls)
		elif not ClassDB.can_instantiate(cls) or not ClassDB.is_parent_class(cls, "Node"):
			wrong_kind.append(cls)
	for c2: Variant in resources:
		var rcls: String = str(c2)
		if not ClassDB.class_exists(rcls):
			missing.append(rcls)
		elif not ClassDB.can_instantiate(rcls) or not ClassDB.is_parent_class(rcls, "Resource"):
			wrong_kind.append(rcls)
	return {"ok": true, "missing": missing, "wrong_kind": wrong_kind, "node_classes": classes.size(),
		"resource_classes": resources.size(), "godot": Engine.get_version_info().get("string", "")}


func _walk(dir: String, out: Array, limit: int) -> void:
	var da: DirAccess = DirAccess.open(dir)
	if da == null:
		return
	da.include_hidden = false
	for f: String in da.get_files():
		if out.size() >= limit:
			return
		if f.ends_with(".gd") or f.ends_with(".tscn") or f.ends_with(".tres") or f.ends_with(".scn"):
			out.append(dir.path_join(f))
	for d: String in da.get_directories():
		if d.begins_with("."):
			continue
		_walk(dir.path_join(d), out, limit)


func _check(r: Dictionary) -> Dictionary:
	var files: Array = []
	var limit: int = HH.variant_int(r.get("limit", 3000))
	_walk("res://", files, limit)
	var bad: Array = []
	for f: Variant in files:
		var path: String = str(f)
		var res: Resource = ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_IGNORE)
		if res == null:
			bad.append({"file": path, "error": "does not load"})
		elif res is Script and not (res as Script).can_instantiate() and not path.contains("/addons/"):
			bad.append({"file": path, "error": "script does not compile"})
		elif res is PackedScene and not (res as PackedScene).can_instantiate():
			bad.append({"file": path, "error": "scene cannot be instantiated"})
	var main: String = str(ProjectSettings.get_setting("application/run/main_scene", ""))
	if not main.is_empty() and not ResourceLoader.exists(main) and not main.begins_with("uid://"):
		bad.append({"file": "project.godot", "error": "main scene missing: " + main})
	for prop: Dictionary in ProjectSettings.get_property_list():
		var pname: String = str(prop["name"])
		if pname.begins_with("autoload/"):
			var apath: String = str(ProjectSettings.get_setting(pname)).trim_prefix("*")
			if not apath.begins_with("uid://") and not ResourceLoader.exists(apath):
				bad.append({"file": "project.godot", "error": "autoload missing: " + apath})
	return {"ok": true, "files_checked": files.size(), "problems": bad, "clean": bad.is_empty(),
		"truncated": files.size() >= limit}
