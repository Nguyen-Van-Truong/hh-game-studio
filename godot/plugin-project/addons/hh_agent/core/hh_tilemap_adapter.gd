class_name HHAgentTilemapAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _MetaScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_meta.gd")
const _IdentityScript: GDScript = preload("res://addons/hh_agent/core/hh_identity.gd")

## Typed Godot 4.7.1 TileSet / TileSetAtlasSource / TileMapLayer verbs.
## Cell readback uses TileMapLayer.get_cell_source_id / get_cell_atlas_coords.
## One EditorUndoRedoManager action per stroke. Catalog: register in actions.json.
## Generated plugin-validator.json / mcp-tools.json are coordinator-owned (`npm run generate`).
## Collision polygons come from TileSet.tile_size or atlas texture_region_size.

var _errors: HHAgentErrors = HHAgentErrors.new()
var _meta: HHAgentSceneMeta = HHAgentSceneMeta.new()
var _identity: HHAgentIdentity = HHAgentIdentity.new()


class TileStroke:
	extends RefCounted
	var layer: TileMapLayer
	var coords: Array[Vector2i] = []
	var do_source: PackedInt32Array = PackedInt32Array()
	var do_atlas_x: PackedInt32Array = PackedInt32Array()
	var do_atlas_y: PackedInt32Array = PackedInt32Array()
	var undo_source: PackedInt32Array = PackedInt32Array()
	var undo_atlas_x: PackedInt32Array = PackedInt32Array()
	var undo_atlas_y: PackedInt32Array = PackedInt32Array()
	var connect_cells: Array[Vector2i] = []
	var terrain_set: int = 0
	var terrain_index: int = 0
	var use_connect: bool = false

	func add(cell: Vector2i, new_sid: int, new_atlas: Vector2i, old_sid: int, old_atlas: Vector2i) -> void:
		coords.append(cell)
		do_source.append(new_sid)
		do_atlas_x.append(new_atlas.x)
		do_atlas_y.append(new_atlas.y)
		undo_source.append(old_sid)
		undo_atlas_x.append(old_atlas.x)
		undo_atlas_y.append(old_atlas.y)

	func apply() -> void:
		if layer == null:
			return
		if use_connect:
			layer.set_cells_terrain_connect(connect_cells, terrain_set, terrain_index, true)
			return
		var i: int = 0
		while i < coords.size():
			layer.set_cell(coords[i], do_source[i], Vector2i(do_atlas_x[i], do_atlas_y[i]))
			i += 1

	func revert() -> void:
		if layer == null:
			return
		var i: int = 0
		while i < coords.size():
			layer.set_cell(coords[i], undo_source[i], Vector2i(undo_atlas_x[i], undo_atlas_y[i]))
			i += 1


func handles(action: String) -> bool:
	return (
		action == "tileset"
		or action == "source"
		or action == "terrain"
		or action == "layer"
		or action == "cell"
		or action == "fill"
		or action == "stamp"
	)


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	precondition: Dictionary,
) -> Dictionary:
	if method != "godot.tilemap" or not handles(action):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not a tilemap verb", "")
	var def: Dictionary = actions.lookup(method, action)
	var post: String = str(def.get("postcondition", ""))
	if post.is_empty():
		post = _fallback_post(action)
	if action == "tileset":
		return _tileset(command_id, params, precondition, post)
	if action == "source":
		return _source(command_id, params, post)
	if action == "terrain":
		return _terrain(command_id, params, precondition, post)
	if action == "layer":
		return _layer(command_id, params, precondition, post)
	if action == "cell":
		return _cell(command_id, params, precondition, post)
	if action == "fill":
		return _fill(command_id, params, precondition, post)
	if action == "stamp":
		return _stamp(command_id, params, precondition, post)
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "tilemap.%s is not a proven verb" % action, "")


func _fallback_post(action: String) -> String:
	if action == "tileset":
		return "tileset_assigned"
	if action == "source":
		return "tileset_source_present"
	if action == "terrain":
		return "terrain_set_present"
	if action == "layer":
		return "tilemap_layer_matches"
	if action == "cell":
		return "cell_atlas_coords_match"
	if action == "fill":
		return "fill_region_matches"
	if action == "stamp":
		return "stamp_cells_match"
	return "tilemap_verb"


func _tileset(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var layer: TileMapLayer = _as_layer(edited, str(params.get("node_path", "")))
	if layer == null:
		return _unverified(command_id, "TileMapLayer not found")
	var packed_err: Dictionary = _reject_packed(command_id, layer, edited)
	if not packed_err.is_empty():
		return packed_err
	var tileset_path: String = str(params.get("tileset", ""))
	var op: String = str(params.get("op", ""))
	if op.is_empty():
		op = "assign"
	var loaded: Dictionary = _ensure_tileset(command_id, tileset_path, op, params)
	if loaded.get("ok", false) != true:
		return loaded
	var tileset: TileSet = loaded.get("tileset") as TileSet
	var configured: Dictionary = _configure_tileset_layers(tileset, params)
	if configured.get("ok", false) != true:
		return _unverified(command_id, str(configured.get("message", "tileset layer configure failed")))
	var persisted: Dictionary = {}
	if loaded.get("created", false) == true or configured.get("changed", false) == true:
		persisted = _persist_tileset(command_id, tileset, tileset_path)
		if persisted.get("ok", false) != true:
			return persisted
	else:
		persisted = {"ok": true, "disk_hash": _meta.disk_hash(tileset_path)}
	var old_set: TileSet = layer.tile_set
	var already: bool = old_set == tileset
	var action_name: String = "%stilemap.tileset %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, layer.name]
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_property(layer, "tile_set", tileset)
	mgr.add_undo_property(layer, "tile_set", old_set)
	mgr.commit_action()
	if layer.tile_set != tileset:
		return _unverified(command_id, "TileMapLayer.tile_set readback mismatch")
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
	after["scene"] = str(params.get("scene", ""))
	after["node_path"] = str(params.get("node_path", ""))
	after["tileset"] = tileset_path
	after["class_name"] = "TileSet"
	after["tileset_class"] = tileset.get_class()
	after["tile_size"] = {"x": tileset.tile_size.x, "y": tileset.tile_size.y}
	after["source_count"] = tileset.get_source_count()
	after["physics_layers"] = tileset.get_physics_layers_count()
	after["navigation_layers"] = tileset.get_navigation_layers_count()
	after["occlusion_layers"] = tileset.get_occlusion_layers_count()
	after["readback_equals"] = true
	after["disk_hash"] = str(persisted.get("disk_hash", ""))
	after["source"] = "editor"
	return _errors.ok_changed(command_id, _checks(post), after, not already, action_name)


func _source(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var tileset_path: String = str(params.get("tileset", ""))
	var loaded: Dictionary = _load_tileset(command_id, tileset_path)
	if loaded.get("ok", false) != true:
		return loaded
	var tileset: TileSet = loaded.get("tileset") as TileSet
	var source_id: int = int(params.get("source_id", 0))
	var op: String = str(params.get("op", ""))
	if op.is_empty():
		op = "add"
	var action_name: String = "%stilemap.source %d" % [HHAgentConstants.UNDO_ACTION_PREFIX, source_id]
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	var ctx: Object = _undo_context(tileset)
	if op == "remove":
		if not tileset.has_source(source_id):
			return _unverified(command_id, "tileset source missing")
		var prev: TileSetSource = tileset.get_source(source_id)
		mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, ctx)
		mgr.add_do_method(tileset, "remove_source", source_id)
		mgr.add_undo_method(tileset, "add_source", prev, source_id)
		mgr.commit_action()
		if tileset.has_source(source_id):
			return _unverified(command_id, "remove_source readback still present")
		var removed_persist: Dictionary = _persist_tileset(command_id, tileset, tileset_path)
		if removed_persist.get("ok", false) != true:
			return removed_persist
		return _errors.ok_changed(
			command_id,
			_checks(post),
			{
				"tileset": tileset_path,
				"source_id": source_id,
				"has_source": false,
				"tile_count": 0,
				"disk_hash": str(removed_persist.get("disk_hash", "")),
				"source": "editor",
			},
			true,
			action_name,
		)
	var texture_path: String = str(params.get("texture", ""))
	var tex_jail: Dictionary = _meta.jail(command_id, texture_path)
	if tex_jail.get("ok", false) != true:
		return tex_jail
	var tex_res: Resource = _load_res(texture_path)
	if tex_res == null or not (tex_res is Texture2D):
		return _unverified(command_id, "texture is not a Texture2D")
	var texture: Texture2D = tex_res as Texture2D
	var region: int = int(params.get("texture_region_size", 0))
	var atlas: TileSetAtlasSource = null
	var existed: bool = tileset.has_source(source_id)
	if existed:
		var existing_src: TileSetSource = tileset.get_source(source_id)
		if not (existing_src is TileSetAtlasSource):
			return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "source is not TileSetAtlasSource", "params.source_id")
		atlas = existing_src as TileSetAtlasSource
	else:
		atlas = TileSetAtlasSource.new()
	var old_tex: Texture2D = atlas.texture
	var old_region: Vector2i = atlas.texture_region_size
	if region > 0:
		atlas.texture_region_size = Vector2i(region, region)
	elif atlas.texture_region_size.x <= 0:
		atlas.texture_region_size = tileset.tile_size
	atlas.texture = texture
	if not existed:
		mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, ctx)
		mgr.add_do_method(tileset, "add_source", atlas, source_id)
		mgr.add_undo_method(tileset, "remove_source", source_id)
		mgr.commit_action()
	else:
		mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, ctx)
		mgr.add_do_property(atlas, "texture", texture)
		mgr.add_undo_property(atlas, "texture", old_tex)
		mgr.add_do_property(atlas, "texture_region_size", atlas.texture_region_size)
		mgr.add_undo_property(atlas, "texture_region_size", old_region)
		mgr.commit_action()
	if not tileset.has_source(source_id):
		return _unverified(command_id, "tileset source missing after add")
	var live_src: TileSetSource = tileset.get_source(source_id)
	if live_src is TileSetAtlasSource:
		atlas = live_src as TileSetAtlasSource
	var created_tiles: Array = _ensure_atlas_tiles(atlas)
	var want_collision: bool = params.get("collision", true) != false
	var collision_info: Dictionary = {}
	if want_collision:
		collision_info = _ensure_tile_collision(tileset, atlas)
		if (
			collision_info.get("ok", false) != true
			or typeof(collision_info.get("tiles", [])) != TYPE_ARRAY
			or (collision_info.get("tiles") as Array).is_empty()
			or int(((collision_info.get("tiles") as Array)[0] as Dictionary).get("polygon_count", 0)) < 1
		):
			return _unverified(command_id, "TileData collision polygons missing after source add")
	var persisted: Dictionary = _persist_tileset(command_id, tileset, tileset_path)
	if persisted.get("ok", false) != true:
		return persisted
	var after: Dictionary = {
		"tileset": tileset_path,
		"source_id": source_id,
		"texture": texture_path,
		"has_source": true,
		"tile_count": atlas.get_tiles_count(),
		"tiles_created": created_tiles.size(),
		"texture_region_size": {"x": atlas.texture_region_size.x, "y": atlas.texture_region_size.y},
		"physics_layers": tileset.get_physics_layers_count(),
		"collision": collision_info,
		"disk_hash": str(persisted.get("disk_hash", "")),
		"readback_equals": true,
		"source": "editor",
	}
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _terrain(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var tileset_path: String = str(params.get("tileset", ""))
	var loaded: Dictionary = _load_tileset(command_id, tileset_path)
	if loaded.get("ok", false) != true:
		return loaded
	var tileset: TileSet = loaded.get("tileset") as TileSet
	var terrain_name: String = str(params.get("terrain_name", ""))
	var op: String = str(params.get("op", ""))
	if op.is_empty():
		op = "add"
	var terrain_set: int = int(params.get("terrain_set", 0))
	var action_name: String = "%stilemap.terrain %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, terrain_name]
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	if tileset.get_terrain_sets_count() <= terrain_set:
		tileset.add_terrain_set(-1)
		terrain_set = tileset.get_terrain_sets_count() - 1
		tileset.set_terrain_set_mode(terrain_set, TileSet.TERRAIN_MODE_MATCH_SIDES)
	var terrain_index: int = _find_terrain(tileset, terrain_set, terrain_name)
	if terrain_index < 0:
		tileset.add_terrain(terrain_set, -1)
		terrain_index = tileset.get_terrains_count(terrain_set) - 1
		tileset.set_terrain_name(terrain_set, terrain_index, terrain_name)
	_bind_atlas_terrain(tileset, terrain_set, terrain_index)
	var bound_persist: Dictionary = _persist_tileset(command_id, tileset, tileset_path)
	if bound_persist.get("ok", false) != true:
		return bound_persist
	var after: Dictionary = {
		"tileset": tileset_path,
		"terrain_name": tileset.get_terrain_name(terrain_set, terrain_index),
		"terrain_set": terrain_set,
		"terrain_index": terrain_index,
		"mode": tileset.get_terrain_set_mode(terrain_set),
		"disk_hash": str(bound_persist.get("disk_hash", "")),
		"source": "editor",
	}
	if op == "connect":
		var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
		if hold.get("ok", false) != true:
			return hold
		var edited: Node = hold.get("root") as Node
		var layer: TileMapLayer = _as_layer(edited, str(params.get("node_path", "")))
		if layer == null:
			return _unverified(command_id, "TileMapLayer not found")
		var raw_cells: Variant = params.get("cells", [])
		if typeof(raw_cells) != TYPE_ARRAY:
			return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "cells must be an array", "params.cells")
		var wanted: Array[Vector2i] = []
		var stroke: TileStroke = TileStroke.new()
		stroke.layer = layer
		for item_v: Variant in raw_cells:
			if typeof(item_v) != TYPE_DICTIONARY:
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "terrain cell must be an object", "params.cells")
			var item: Dictionary = item_v
			var cell: Vector2i = Vector2i(int(item.get("x", 0)), int(item.get("y", 0)))
			wanted.append(cell)
			stroke.add(
				cell,
				layer.get_cell_source_id(cell),
				layer.get_cell_atlas_coords(cell),
				layer.get_cell_source_id(cell),
				layer.get_cell_atlas_coords(cell),
			)
		if wanted.is_empty():
			return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "terrain connect cells must not be empty", "params.cells")
		stroke.connect_cells = wanted
		stroke.terrain_set = terrain_set
		stroke.terrain_index = terrain_index
		stroke.use_connect = true
		mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
		mgr.add_do_method(stroke, "apply")
		mgr.add_undo_method(stroke, "revert")
		mgr.add_do_reference(stroke)
		mgr.commit_action()
		var painted: int = 0
		var i: int = 0
		while i < wanted.size():
			if layer.get_cell_source_id(wanted[i]) >= 0:
				painted += 1
			i += 1
		if painted < 1:
			return _unverified(command_id, "set_cells_terrain_connect painted no cells")
		_meta.mark_dirty(str(params.get("scene", "")))
		after["scene"] = str(params.get("scene", ""))
		after["node_path"] = str(params.get("node_path", ""))
		after["cell_count"] = wanted.size()
		after["painted"] = painted
		after["connected"] = painted == wanted.size()
		after["readback_equals"] = painted == wanted.size()
		var snap: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
		for key_s: String in snap.keys():
			if not after.has(key_s):
				after[key_s] = snap[key_s]
		return _errors.ok_changed(command_id, _checks(post), after, true, action_name)
	var persisted: Dictionary = _persist_tileset(command_id, tileset, tileset_path)
	if persisted.get("ok", false) != true:
		return persisted
	after["disk_hash"] = str(persisted.get("disk_hash", ""))
	after["has_terrain"] = true
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, _undo_context(tileset))
	mgr.add_do_method(tileset, "set_terrain_name", terrain_set, terrain_index, terrain_name)
	mgr.add_undo_method(tileset, "set_terrain_name", terrain_set, terrain_index, terrain_name)
	mgr.commit_action()
	if tileset.get_terrain_name(terrain_set, terrain_index) != terrain_name:
		return _unverified(command_id, "terrain name readback mismatch")
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _layer(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var op: String = str(params.get("op", ""))
	if op.is_empty():
		op = "configure"
	var enabled: bool = params.get("enabled", true) == true
	var action_name: String = "%stilemap.layer %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, op]
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	if op == "add":
		return _layer_add(command_id, params, edited, enabled, post, action_name, mgr)
	var layer: TileMapLayer = _as_layer(edited, str(params.get("node_path", "")))
	if layer == null:
		return _unverified(command_id, "TileMapLayer not found")
	var packed_err: Dictionary = _reject_packed(command_id, layer, edited)
	if not packed_err.is_empty():
		return packed_err
	if op == "remove":
		return _layer_remove(command_id, params, edited, layer, post, action_name, mgr)
	if op == "reorder":
		return _layer_reorder(command_id, params, edited, layer, post, action_name, mgr)
	var old_enabled: bool = layer.enabled
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_property(layer, "enabled", enabled)
	mgr.add_undo_property(layer, "enabled", old_enabled)
	mgr.commit_action()
	if layer.enabled != enabled:
		return _unverified(command_id, "TileMapLayer.enabled readback mismatch")
	_meta.mark_dirty(str(params.get("scene", "")))
	return _errors.ok_changed(command_id, _checks(post), _layer_after(edited, layer, params, enabled), old_enabled != enabled, action_name)


func _layer_add(
	command_id: String,
	params: Dictionary,
	edited: Node,
	enabled: bool,
	post: String,
	action_name: String,
	mgr: EditorUndoRedoManager,
) -> Dictionary:
	var parent_path: String = str(params.get("parent", ""))
	if parent_path.is_empty():
		parent_path = "."
	var parent: Node = _resolve(edited, parent_path)
	if parent == null:
		return _unverified(command_id, "parent not found")
	var name_s: String = str(params.get("name", ""))
	if name_s.is_empty():
		name_s = str(params.get("node_path", "")).get_file()
	if name_s.is_empty() or name_s == ".":
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "layer add requires name", "params.name")
	if parent.get_node_or_null(NodePath(name_s)) != null:
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "sibling name already used", "params.name")
	if not ClassDB.class_exists("TileMapLayer") or not ClassDB.can_instantiate("TileMapLayer"):
		return _unverified(command_id, "TileMapLayer is not instantiable")
	var inst_v: Variant = ClassDB.instantiate("TileMapLayer")
	if inst_v == null or not (inst_v is TileMapLayer):
		if inst_v is Node:
			(inst_v as Node).free()
		return _unverified(command_id, "failed to instantiate TileMapLayer")
	var child: TileMapLayer = inst_v as TileMapLayer
	child.name = name_s
	child.enabled = enabled
	var owner: Node = _identity.pick_owner(parent, edited)
	var uid: String = _identity.mint()
	_identity.stamp(child, uid)
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_method(parent, "add_child", child, true)
	mgr.add_do_method(child, "set_owner", owner)
	mgr.add_do_method(child, "set_meta", HHAgentConstants.NODE_UID_META, uid)
	mgr.add_do_method(child, "set_meta", HHAgentConstants.NODE_UID_META_HIDDEN, uid)
	mgr.add_undo_method(parent, "remove_child", child)
	mgr.add_undo_reference(child)
	mgr.commit_action()
	if child.get_parent() != parent:
		return _unverified(command_id, "TileMapLayer add_child did not attach")
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _layer_after(edited, child, params, enabled)
	after["uid"] = uid
	after["op"] = "add"
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _layer_remove(
	command_id: String,
	params: Dictionary,
	edited: Node,
	layer: TileMapLayer,
	post: String,
	action_name: String,
	mgr: EditorUndoRedoManager,
) -> Dictionary:
	if layer == edited:
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "cannot remove edited scene root", "params.node_path")
	var parent: Node = layer.get_parent()
	if parent == null:
		return _unverified(command_id, "layer has no parent")
	var old_index: int = layer.get_index()
	var old_owner: Node = layer.owner
	var gone_path: String = _identity.tree_path(layer, edited)
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_method(parent, "remove_child", layer)
	mgr.add_undo_method(parent, "add_child", layer)
	mgr.add_undo_method(parent, "move_child", layer, old_index)
	if old_owner != null:
		mgr.add_undo_method(layer, "set_owner", old_owner)
	mgr.add_do_reference(layer)
	mgr.commit_action()
	if layer.get_parent() != null:
		return _unverified(command_id, "layer still parented after remove")
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
	after["scene"] = str(params.get("scene", ""))
	after["node_path"] = gone_path
	after["enabled"] = params.get("enabled", true) == true
	after["absent"] = true
	after["op"] = "remove"
	after["source"] = "editor"
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _layer_reorder(
	command_id: String,
	params: Dictionary,
	edited: Node,
	layer: TileMapLayer,
	post: String,
	action_name: String,
	mgr: EditorUndoRedoManager,
) -> Dictionary:
	var parent: Node = layer.get_parent()
	if parent == null:
		return _unverified(command_id, "layer has no parent")
	var index: int = int(params.get("index", 0))
	if index < 0 or index >= parent.get_child_count():
		return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "index outside sibling range", "params.index")
	var old_index: int = layer.get_index()
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_method(parent, "move_child", layer, index)
	mgr.add_undo_method(parent, "move_child", layer, old_index)
	mgr.commit_action()
	if layer.get_index() != index:
		return _unverified(command_id, "layer reorder index mismatch")
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _layer_after(edited, layer, params, layer.enabled)
	after["index"] = layer.get_index()
	after["op"] = "reorder"
	return _errors.ok_changed(command_id, _checks(post), after, old_index != index, action_name)


func _cell(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_layer(command_id, params, precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var layer: TileMapLayer = hold.get("layer") as TileMapLayer
	var planned: Array[Dictionary] = []
	var raw_cells: Variant = params.get("cells", [])
	if typeof(raw_cells) == TYPE_ARRAY and (raw_cells as Array).size() > 0:
		for item_v: Variant in raw_cells:
			if typeof(item_v) != TYPE_DICTIONARY:
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "cell chunk item must be an object", "params.cells")
			planned.append(item_v as Dictionary)
	else:
		planned.append(params)
	if planned.size() > 256:
		return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "cell chunk exceeds 256", "params.cells")
	var stroke: TileStroke = TileStroke.new()
	stroke.layer = layer
	for item: Dictionary in planned:
		var cell: Vector2i = Vector2i(int(item.get("x", 0)), int(item.get("y", 0)))
		var erase: bool = item.get("erase", false) == true
		var sid: int = -1 if erase else int(item.get("source_id", params.get("source_id", 0)))
		var atlas: Vector2i = Vector2i(-1, -1) if erase else Vector2i(int(item.get("atlas_x", 0)), int(item.get("atlas_y", 0)))
		stroke.add(cell, sid, atlas, layer.get_cell_source_id(cell), layer.get_cell_atlas_coords(cell))
	var action_name: String = "%stilemap.cell" % HHAgentConstants.UNDO_ACTION_PREFIX
	var committed: Dictionary = _commit_stroke(command_id, edited, stroke, action_name)
	if committed.get("ok", false) != true:
		return committed
	var first: Dictionary = planned[0]
	var first_cell: Vector2i = Vector2i(int(first.get("x", 0)), int(first.get("y", 0)))
	var erase_first: bool = first.get("erase", false) == true
	var after: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
	after["scene"] = str(params.get("scene", ""))
	after["node_path"] = str(params.get("node_path", ""))
	after["x"] = first_cell.x
	after["y"] = first_cell.y
	after["source_id"] = layer.get_cell_source_id(first_cell)
	after["atlas_x"] = layer.get_cell_atlas_coords(first_cell).x
	after["atlas_y"] = layer.get_cell_atlas_coords(first_cell).y
	after["cell_count"] = stroke.coords.size()
	after["readback_equals"] = committed.get("readback_equals", false) == true
	after["erased"] = erase_first
	after["source"] = "engine"
	_meta.mark_dirty(str(params.get("scene", "")))
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _fill(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_layer(command_id, params, precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var layer: TileMapLayer = hold.get("layer") as TileMapLayer
	var x0: int = int(params.get("x", 0))
	var y0: int = int(params.get("y", 0))
	var w: int = int(params.get("w", 1))
	var h: int = int(params.get("h", 1))
	if w < 1 or h < 1 or w > 512 or h > 512:
		return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "fill region out of bounds", "params.w")
	var erase: bool = params.get("erase", false) == true
	var sid: int = -1 if erase else int(params.get("source_id", 0))
	var atlas: Vector2i = Vector2i(-1, -1) if erase else Vector2i(int(params.get("atlas_x", 0)), int(params.get("atlas_y", 0)))
	var stroke: TileStroke = TileStroke.new()
	stroke.layer = layer
	var y: int = y0
	while y < y0 + h:
		var x: int = x0
		while x < x0 + w:
			var cell: Vector2i = Vector2i(x, y)
			stroke.add(cell, sid, atlas, layer.get_cell_source_id(cell), layer.get_cell_atlas_coords(cell))
			x += 1
		y += 1
	var action_name: String = "%stilemap.fill" % HHAgentConstants.UNDO_ACTION_PREFIX
	var committed: Dictionary = _commit_stroke(command_id, edited, stroke, action_name)
	if committed.get("ok", false) != true:
		return committed
	var samples: Array = _sample_region(layer, x0, y0, w, h)
	var after: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
	after["scene"] = str(params.get("scene", ""))
	after["node_path"] = str(params.get("node_path", ""))
	after["x"] = x0
	after["y"] = y0
	after["w"] = w
	after["h"] = h
	after["source_id"] = sid
	after["atlas_x"] = atlas.x
	after["atlas_y"] = atlas.y
	after["cell_count"] = w * h
	after["compact"] = true
	after["samples"] = samples
	after["readback_equals"] = committed.get("readback_equals", false) == true
	after["source"] = "engine"
	_meta.mark_dirty(str(params.get("scene", "")))
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _stamp(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_layer(command_id, params, precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var layer: TileMapLayer = hold.get("layer") as TileMapLayer
	var origin: Vector2i = Vector2i(int(params.get("x", 0)), int(params.get("y", 0)))
	var pattern: String = str(params.get("pattern", ""))
	var sid: int = int(params.get("source_id", 0))
	var atlas: Vector2i = Vector2i(int(params.get("atlas_x", 0)), int(params.get("atlas_y", 0)))
	var rels: Array[Vector2i] = _pattern_cells(pattern)
	var raw_cells: Variant = params.get("cells", [])
	if typeof(raw_cells) == TYPE_ARRAY and (raw_cells as Array).size() > 0:
		rels.clear()
		for item_v: Variant in raw_cells:
			if typeof(item_v) != TYPE_DICTIONARY:
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "stamp cell must be an object", "params.cells")
			var item: Dictionary = item_v
			rels.append(Vector2i(int(item.get("x", 0)), int(item.get("y", 0))))
	if rels.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "unknown stamp pattern", "params.pattern")
	var stroke: TileStroke = TileStroke.new()
	stroke.layer = layer
	var painted: Array = []
	for rel: Vector2i in rels:
		var cell: Vector2i = origin + rel
		if cell.x < 0 or cell.y < 0:
			return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "stamp cell is negative", "params.x")
		stroke.add(cell, sid, atlas, layer.get_cell_source_id(cell), layer.get_cell_atlas_coords(cell))
		painted.append({"x": cell.x, "y": cell.y, "source_id": sid, "atlas_x": atlas.x, "atlas_y": atlas.y})
	var action_name: String = "%stilemap.stamp %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, pattern]
	var committed: Dictionary = _commit_stroke(command_id, edited, stroke, action_name)
	if committed.get("ok", false) != true:
		return committed
	var after: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
	after["scene"] = str(params.get("scene", ""))
	after["node_path"] = str(params.get("node_path", ""))
	after["x"] = origin.x
	after["y"] = origin.y
	after["pattern"] = pattern
	after["source_id"] = sid
	after["atlas_x"] = atlas.x
	after["atlas_y"] = atlas.y
	after["cell_count"] = stroke.coords.size()
	after["cells"] = painted
	after["readback_equals"] = committed.get("readback_equals", false) == true
	after["source"] = "engine"
	_meta.mark_dirty(str(params.get("scene", "")))
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _commit_stroke(command_id: String, edited: Node, stroke: TileStroke, action_name: String) -> Dictionary:
	if stroke.coords.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "stroke has no cells", "")
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_method(stroke, "apply")
	mgr.add_undo_method(stroke, "revert")
	mgr.add_do_reference(stroke)
	mgr.commit_action()
	var i: int = 0
	while i < stroke.coords.size():
		var cell: Vector2i = stroke.coords[i]
		var got_sid: int = stroke.layer.get_cell_source_id(cell)
		var got_atlas: Vector2i = stroke.layer.get_cell_atlas_coords(cell)
		if got_sid != stroke.do_source[i] or got_atlas.x != stroke.do_atlas_x[i] or got_atlas.y != stroke.do_atlas_y[i]:
			return _unverified(command_id, "engine cell readback mismatch at %d,%d" % [cell.x, cell.y])
		i += 1
	return {"ok": true, "readback_equals": true}


func _sample_region(layer: TileMapLayer, x0: int, y0: int, w: int, h: int) -> Array:
	var points: Array[Vector2i] = [
		Vector2i(x0, y0),
		Vector2i(x0 + w - 1, y0),
		Vector2i(x0, y0 + h - 1),
		Vector2i(x0 + w - 1, y0 + h - 1),
		Vector2i(x0 + int(w / 2), y0 + int(h / 2)),
	]
	var out: Array = []
	var seen: Dictionary = {}
	for cell: Vector2i in points:
		var key: String = "%d,%d" % [cell.x, cell.y]
		if seen.has(key):
			continue
		seen[key] = true
		out.append({
			"x": cell.x,
			"y": cell.y,
			"source_id": layer.get_cell_source_id(cell),
			"atlas": {"x": layer.get_cell_atlas_coords(cell).x, "y": layer.get_cell_atlas_coords(cell).y},
		})
	return out


func _pattern_cells(pattern: String) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	if pattern == "tree_clump" or pattern == "block":
		out.append(Vector2i(0, 0))
		out.append(Vector2i(1, 0))
		out.append(Vector2i(0, 1))
		out.append(Vector2i(1, 1))
		return out
	if pattern == "plus":
		out.append(Vector2i(0, 0))
		out.append(Vector2i(1, 0))
		out.append(Vector2i(0, 1))
		return out
	if pattern == "hbar":
		out.append(Vector2i(0, 0))
		out.append(Vector2i(1, 0))
		out.append(Vector2i(2, 0))
		return out
	if pattern == "vbar":
		out.append(Vector2i(0, 0))
		out.append(Vector2i(0, 1))
		out.append(Vector2i(0, 2))
		return out
	return out


func _ensure_tileset(command_id: String, tileset_path: String, op: String, params: Dictionary) -> Dictionary:
	if FileAccess.file_exists(tileset_path) or ResourceLoader.exists(tileset_path):
		return _load_tileset(command_id, tileset_path)
	if op != "create" and op != "assign":
		return _unverified(command_id, "tileset missing")
	var jail: Dictionary = _meta.jail(command_id, tileset_path)
	if jail.get("ok", false) != true:
		return jail
	if not tileset_path.ends_with(".tres") and not tileset_path.ends_with(".res"):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "tileset create requires .tres or .res", tileset_path)
	var tileset: TileSet = TileSet.new()
	var tile_size: int = int(params.get("tile_size", 0))
	if tile_size > 0:
		tileset.tile_size = Vector2i(tile_size, tile_size)
	var persisted: Dictionary = _persist_tileset(command_id, tileset, tileset_path)
	if persisted.get("ok", false) != true:
		return persisted
	return {"ok": true, "tileset": tileset, "created": true}


func _load_tileset(command_id: String, tileset_path: String) -> Dictionary:
	var jail: Dictionary = _meta.jail(command_id, tileset_path)
	if jail.get("ok", false) != true:
		return jail
	var res: Resource = _load_res(tileset_path)
	if res == null or not (res is TileSet):
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "path is not a TileSet", tileset_path)
	return {"ok": true, "tileset": res as TileSet, "created": false}


func _configure_tileset_layers(tileset: TileSet, params: Dictionary) -> Dictionary:
	var changed: bool = false
	var tile_size: int = int(params.get("tile_size", 0))
	if tile_size > 0 and tileset.tile_size != Vector2i(tile_size, tile_size):
		tileset.tile_size = Vector2i(tile_size, tile_size)
		changed = true
	var physics: int = int(params.get("physics_layers", -1))
	if physics < 0:
		physics = 1 if tileset.get_physics_layers_count() == 0 else tileset.get_physics_layers_count()
	while tileset.get_physics_layers_count() < physics:
		tileset.add_physics_layer(-1)
		changed = true
	var navigation: int = int(params.get("navigation_layers", 0))
	while tileset.get_navigation_layers_count() < navigation:
		tileset.add_navigation_layer(-1)
		changed = true
	var occlusion: int = int(params.get("occlusion_layers", 0))
	while tileset.get_occlusion_layers_count() < occlusion:
		tileset.add_occlusion_layer(-1)
		changed = true
	return {"ok": true, "changed": changed}


func _ensure_atlas_tiles(atlas: TileSetAtlasSource) -> Array:
	var created: Array = []
	var tex: Texture2D = atlas.texture
	if tex == null:
		return created
	var region: Vector2i = atlas.texture_region_size
	if region.x <= 0 or region.y <= 0:
		return created
	var cols: int = int(tex.get_width() / region.x)
	var rows: int = int(tex.get_height() / region.y)
	if cols < 1:
		cols = 1
	if rows < 1:
		rows = 1
	var y: int = 0
	while y < rows:
		var x: int = 0
		while x < cols:
			var coords: Vector2i = Vector2i(x, y)
			if not atlas.has_tile(coords):
				atlas.create_tile(coords)
				created.append({"x": x, "y": y})
			x += 1
		y += 1
	return created


func _ensure_tile_collision(tileset: TileSet, atlas: TileSetAtlasSource) -> Dictionary:
	if tileset.get_physics_layers_count() < 1:
		tileset.add_physics_layer(-1)
	var sz: Vector2i = atlas.texture_region_size
	var size_source: String = "texture_region_size"
	if sz.x <= 0 or sz.y <= 0:
		sz = tileset.tile_size
		size_source = "tile_size"
	if sz.x <= 0 or sz.y <= 0:
		return {"ok": false, "invented_box": false, "size_source": "none"}
	var poly: PackedVector2Array = _tile_poly(sz)
	var tiles: Array = []
	var i: int = 0
	while i < atlas.get_tiles_count():
		var coords: Vector2i = atlas.get_tile_id(i)
		var data: TileData = atlas.get_tile_data(coords, 0)
		if data != null:
			if data.get_collision_polygons_count(0) < 1:
				data.add_collision_polygon(0)
			data.set_collision_polygon_points(0, 0, poly)
			tiles.append({
				"atlas_x": coords.x,
				"atlas_y": coords.y,
				"polygon_count": data.get_collision_polygons_count(0),
				"points": _points_json(data.get_collision_polygon_points(0, 0)),
				"size_source": size_source,
				"size": {"x": sz.x, "y": sz.y},
			})
		i += 1
	return {
		"ok": true,
		"invented_box": false,
		"size_source": size_source,
		"physics_layers": tileset.get_physics_layers_count(),
		"collision_layer": tileset.get_physics_layer_collision_layer(0),
		"tiles": tiles,
	}


func _tile_poly(sz: Vector2i) -> PackedVector2Array:
	var half: Vector2 = Vector2(float(sz.x) * 0.5, float(sz.y) * 0.5)
	var pts: PackedVector2Array = PackedVector2Array()
	pts.append(Vector2(-half.x, -half.y))
	pts.append(Vector2(half.x, -half.y))
	pts.append(Vector2(half.x, half.y))
	pts.append(Vector2(-half.x, half.y))
	return pts


func _points_json(pts: PackedVector2Array) -> Array:
	var out: Array = []
	var i: int = 0
	while i < pts.size():
		out.append({"x": pts[i].x, "y": pts[i].y})
		i += 1
	return out


func _find_terrain(tileset: TileSet, terrain_set: int, terrain_name: String) -> int:
	var i: int = 0
	while i < tileset.get_terrains_count(terrain_set):
		if tileset.get_terrain_name(terrain_set, i) == terrain_name:
			return i
		i += 1
	return -1


func _bind_atlas_terrain(tileset: TileSet, terrain_set: int, terrain_index: int) -> void:
	var peers: Array[int] = [
		TileSet.CELL_NEIGHBOR_RIGHT_SIDE,
		TileSet.CELL_NEIGHBOR_BOTTOM_SIDE,
		TileSet.CELL_NEIGHBOR_LEFT_SIDE,
		TileSet.CELL_NEIGHBOR_TOP_SIDE,
	]
	var si: int = 0
	while si < tileset.get_source_count():
		var sid: int = tileset.get_source_id(si)
		var src: TileSetSource = tileset.get_source(sid)
		if src is TileSetAtlasSource:
			var atlas: TileSetAtlasSource = src as TileSetAtlasSource
			var ti: int = 0
			while ti < atlas.get_tiles_count():
				var coords: Vector2i = atlas.get_tile_id(ti)
				var data: TileData = atlas.get_tile_data(coords, 0)
				if data != null:
					data.terrain_set = terrain_set
					data.terrain = terrain_index
					for peer: int in peers:
						data.set_terrain_peering_bit(peer, terrain_index)
				ti += 1
		si += 1


func _persist_tileset(command_id: String, tileset: TileSet, tileset_path: String) -> Dictionary:
	var jail: Dictionary = _meta.jail(command_id, tileset_path)
	if jail.get("ok", false) != true:
		return jail
	if not tileset_path.ends_with(".tres") and not tileset_path.ends_with(".res"):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "tileset persist requires .tres or .res", tileset_path)
	var dir_err: Error = _meta.ensure_parent_dir(tileset_path)
	if dir_err != OK:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot create tileset directory", tileset_path)
	var save_err: Error = ResourceSaver.save(tileset, tileset_path)
	if save_err != OK:
		return _unverified(command_id, "ResourceSaver.save failed: %s" % error_string(save_err))
	_meta.refresh_fs(tileset_path)
	if not FileAccess.file_exists(tileset_path):
		return _unverified(command_id, "tileset file missing after save")
	var disk: String = _meta.disk_hash(tileset_path)
	if disk.is_empty() or disk == "missing":
		return _unverified(command_id, "tileset disk hash missing after save")
	return {"ok": true, "disk_hash": disk, "path": tileset_path}


func _layer_after(edited: Node, layer: TileMapLayer, params: Dictionary, enabled: bool) -> Dictionary:
	var after: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
	after["scene"] = str(params.get("scene", ""))
	var requested_path: String = str(params.get("node_path", ""))
	after["node_path"] = requested_path if not requested_path.is_empty() else _identity.tree_path(layer, edited)
	after["resolved_path"] = _identity.tree_path(layer, edited)
	after["enabled"] = layer.enabled
	after["class_name"] = layer.get_class()
	after["requested_enabled"] = enabled
	after["source"] = "editor"
	return after


func _hold_layer(command_id: String, params: Dictionary, precondition: Dictionary) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var layer: TileMapLayer = _as_layer(edited, str(params.get("node_path", "")))
	if layer == null:
		return _unverified(command_id, "TileMapLayer not found")
	var packed_err: Dictionary = _reject_packed(command_id, layer, edited)
	if not packed_err.is_empty():
		return packed_err
	if layer.tile_set == null:
		return _unverified(command_id, "TileMapLayer has no TileSet")
	return {"ok": true, "root": edited, "layer": layer}


func _as_layer(root: Node, path_s: String) -> TileMapLayer:
	var node: Node = _resolve(root, path_s)
	if node == null or not (node is TileMapLayer):
		return null
	return node as TileMapLayer


func _hold_scene(command_id: String, res_path: String, precondition: Dictionary) -> Dictionary:
	var gated: Dictionary = _meta.jail(command_id, res_path)
	if gated.get("ok", false) != true:
		return gated
	if not _meta.is_scene_path(res_path):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "path must be .tscn or .scn", res_path)
	if not FileAccess.file_exists(res_path):
		return _unverified(command_id, "scene missing")
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited == null or edited.scene_file_path != res_path:
		EditorInterface.open_scene_from_path(res_path)
		edited = EditorInterface.get_edited_scene_root()
	if edited == null or edited.scene_file_path != res_path:
		return _unverified(command_id, "edited_scene is not %s" % res_path)
	if not precondition.is_empty():
		var want_fp: String = str(precondition.get("fingerprint", ""))
		var want_hv: String = str(precondition.get("history_version", ""))
		var want_hash: String = str(precondition.get("scene_hash", ""))
		if not want_fp.is_empty() and want_fp != _meta.fingerprint(edited):
			return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "editor fingerprint changed; resync", "precondition.fingerprint")
		if not want_hv.is_empty() and want_hv != str(_meta.history_version(edited)):
			return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "editor history version changed; resync", "precondition.history_version")
		if not want_hash.is_empty() and want_hash != _meta.disk_hash(res_path):
			return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "disk hash changed (human/external edit); resync", "precondition.scene_hash")
	return {"ok": true, "root": edited}


func _resolve(root: Node, path_s: String) -> Node:
	if root == null:
		return null
	if path_s.is_empty() or path_s == "." or path_s == root.name:
		return root
	var found: Node = root.get_node_or_null(NodePath(path_s))
	if found != null:
		return found
	if path_s.begins_with(root.name + "/"):
		return root.get_node_or_null(NodePath(path_s.substr(root.name.length() + 1)))
	return null


func _reject_packed(command_id: String, node: Node, edited: Node) -> Dictionary:
	if _identity.is_packed_internal(node, edited):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"packed instance child requires make_local; refusing a flatten",
			"params.node_path",
		)
	return {}


func _load_res(res_path: String) -> Resource:
	if res_path.is_empty():
		return null
	if ResourceLoader.exists(res_path):
		var loaded: Resource = ResourceLoader.load(res_path, "", ResourceLoader.CACHE_MODE_REUSE)
		if loaded != null:
			return loaded
	if FileAccess.file_exists(res_path):
		return ResourceLoader.load(res_path)
	return null


func _undo_context(tileset: TileSet) -> Object:
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited != null:
		return edited
	return tileset


func _mgr() -> EditorUndoRedoManager:
	return EditorInterface.get_editor_undo_redo()


func _unverified(command_id: String, message: String) -> Dictionary:
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, message, "")


func _checks(post: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	out.append(post)
	return out
