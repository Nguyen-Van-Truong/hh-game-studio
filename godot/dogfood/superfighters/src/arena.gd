class_name Arena
extends RefCounted

const _MapCatalog: GDScript = preload("res://src/maps/map_catalog.gd")
const _MapCodec: GDScript = preload("res://src/maps/map_codec.gd")

const SRC_ID: int = 0

var map_id: String = "rooftops"
var player_spawns: Array[Vector2] = []
var weapon_spawns: Array[Vector2] = []
var ladder_cells: Array[Vector2i] = []
var world: Node2D
var layer: TileMapLayer
var _slot_spawns: Dictionary = {}


func build(p_map_id: String) -> Node2D:
	map_id = p_map_id
	player_spawns.clear()
	weapon_spawns.clear()
	ladder_cells.clear()
	_slot_spawns.clear()
	world = Node2D.new()
	world.name = "Arena"
	world.add_child(_backdrop())
	world.add_child(_skyline())
	layer = TileMapLayer.new()
	layer.name = "ArenaTiles"
	layer.tile_set = _make_tileset()
	layer.collision_enabled = true
	_paint(layer)
	world.add_child(layer)
	return world


func has_ladder_at(world_pos: Vector2) -> bool:
	var pts: Array[Vector2] = [
		world_pos,
		world_pos + Vector2(0, 8),
		world_pos + Vector2(0, -8),
		world_pos + Vector2(10, 0),
		world_pos + Vector2(-10, 0),
	]
	var i: int = 0
	while i < pts.size():
		var cell: Vector2i = Vector2i(
			int(floor(pts[i].x / float(Maps.TILE))),
			int(floor(pts[i].y / float(Maps.TILE)))
		)
		if ladder_cells.has(cell):
			return true
		i += 1
	return false


func platform_is_one_way() -> bool:
	if layer == null or layer.tile_set == null:
		return false
	var atlas_src: TileSetSource = layer.tile_set.get_source(SRC_ID)
	var atlas: TileSetAtlasSource = atlas_src as TileSetAtlasSource
	if atlas == null:
		return false
	var data: TileData = atlas.get_tile_data(Maps.ATLAS_PLATFORM, 0)
	if data == null:
		return false
	return data.is_collision_polygon_one_way(1, 0)


func platform_collision_bit() -> int:
	if layer == null or layer.tile_set == null:
		return 0
	if layer.tile_set.get_physics_layers_count() < 2:
		return 0
	return layer.tile_set.get_physics_layer_collision_layer(1)


func _ladder_sprite(at: Vector2) -> Sprite2D:
	var spr: Sprite2D = Sprite2D.new()
	spr.name = "Ladder"
	spr.texture = load(Visuals.LADDER) as Texture2D
	spr.centered = true
	spr.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	spr.position = at
	spr.z_index = -1
	return spr


func _backdrop() -> ColorRect:
	var back: ColorRect = ColorRect.new()
	back.name = "Sky"
	back.color = Color8(18, 28, 48)
	back.position = Vector2(-2048, -2048)
	back.size = Vector2(8192, 8192)
	back.mouse_filter = Control.MOUSE_FILTER_IGNORE
	back.z_index = -20
	return back


func _skyline() -> Sprite2D:
	var spr: Sprite2D = Sprite2D.new()
	spr.name = "Skyline"
	spr.texture = load(Visuals.BG_CITY) as Texture2D
	spr.centered = false
	spr.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	spr.position = Vector2(0, -8)
	spr.z_index = -15
	var size: Vector2 = Maps.pixel_size(map_id)
	if spr.texture != null:
		spr.scale = Vector2(size.x / float(spr.texture.get_width()), size.y / float(spr.texture.get_height()))
	return spr


func _make_tileset() -> TileSet:
	var ts: TileSet = TileSet.new()
	ts.tile_size = Vector2i(Maps.TILE, Maps.TILE)
	ts.add_physics_layer(-1)
	ts.set_physics_layer_collision_layer(0, Maps.COL_WORLD)
	ts.set_physics_layer_collision_mask(0, 0)
	ts.add_physics_layer(-1)
	ts.set_physics_layer_collision_layer(1, Maps.COL_PLATFORM)
	ts.set_physics_layer_collision_mask(1, 0)
	var tex: Texture2D = load(Visuals.TILESET) as Texture2D
	var atlas: TileSetAtlasSource = TileSetAtlasSource.new()
	atlas.texture = tex
	atlas.texture_region_size = Vector2i(Maps.TILE, Maps.TILE)
	var coords: Array[Vector2i] = [
		Maps.ATLAS_CONCRETE,
		Maps.ATLAS_BRICK,
		Maps.ATLAS_CRATE,
		Maps.ATLAS_METAL,
		Maps.ATLAS_POLICE,
		Maps.ATLAS_PLATFORM,
		Maps.ATLAS_HAZARD,
		Maps.ATLAS_WALL,
	]
	var i: int = 0
	while i < coords.size():
		atlas.create_tile(coords[i])
		i += 1
	ts.add_source(atlas, SRC_ID)
	_solid_tile(atlas, Maps.ATLAS_CONCRETE, false, 0)
	_solid_tile(atlas, Maps.ATLAS_BRICK, false, 0)
	_solid_tile(atlas, Maps.ATLAS_CRATE, false, 0)
	_solid_tile(atlas, Maps.ATLAS_METAL, false, 0)
	_solid_tile(atlas, Maps.ATLAS_POLICE, false, 0)
	_solid_tile(atlas, Maps.ATLAS_HAZARD, false, 0)
	_solid_tile(atlas, Maps.ATLAS_WALL, false, 0)
	_solid_tile(atlas, Maps.ATLAS_PLATFORM, true, 1)
	return ts


func _solid_tile(atlas: TileSetAtlasSource, cell: Vector2i, one_way: bool, phys_layer: int) -> void:
	var data: TileData = atlas.get_tile_data(cell, 0)
	if data == null:
		return
	if data.get_collision_polygons_count(phys_layer) < 1:
		data.add_collision_polygon(phys_layer)
	var half: float = float(Maps.TILE) * 0.5
	var poly: PackedVector2Array = PackedVector2Array()
	poly.append(Vector2(-half, -half))
	poly.append(Vector2(half, -half))
	poly.append(Vector2(half, half))
	poly.append(Vector2(-half, half))
	data.set_collision_polygon_points(phys_layer, 0, poly)
	if one_way:
		data.set_collision_polygon_one_way(phys_layer, 0, true)
		data.set_collision_polygon_one_way_margin(phys_layer, 0, 2.0)


func _paint(target: TileMapLayer) -> void:
	var doc: Dictionary = _MapCatalog.document(map_id)
	if doc.is_empty():
		return
	var theme: String = str(doc.get("theme", _MapCodec.theme_for(map_id)))
	_paint_layer(target, doc, "solid", theme)
	_paint_layer(target, doc, "prop", theme)
	_paint_layer(target, doc, "hazard", theme)
	_paint_layer(target, doc, "one_way", theme)
	var ladders: Array = _MapCodec.layer_cells(doc, "ladder")
	var i: int = 0
	while i < ladders.size():
		var cell: Array = ladders[i] as Array
		var x: int = int(cell[0])
		var y: int = int(cell[1])
		ladder_cells.append(Vector2i(x, y))
		world.add_child(_ladder_sprite(_cell_center(x, y)))
		i += 1
	var pickups: Array = _MapCodec.layer_cells(doc, "pickup")
	i = 0
	while i < pickups.size():
		var pcell: Array = pickups[i] as Array
		weapon_spawns.append(_cell_center(int(pcell[0]), int(pcell[1])))
		i += 1
	var spawns: Array = _MapCodec.layer_cells(doc, "spawn")
	i = 0
	while i < spawns.size():
		var scell: Array = spawns[i] as Array
		if scell.size() >= 3:
			_slot_spawns[int(scell[2])] = _cell_center(int(scell[0]), int(scell[1]))
		i += 1
	var slot: int = 0
	while slot < 4:
		if _slot_spawns.has(slot):
			player_spawns.append(_slot_spawns[slot] as Vector2)
		slot += 1
	if player_spawns.is_empty():
		player_spawns.append(Vector2(80, 80))


func _paint_layer(target: TileMapLayer, doc: Dictionary, layer: String, theme: String) -> void:
	var atlas: Vector2i = _MapCodec.atlas_for(theme, layer)
	var cells: Array = _MapCodec.layer_cells(doc, layer)
	var i: int = 0
	while i < cells.size():
		var cell: Array = cells[i] as Array
		if cell.size() >= 2:
			target.set_cell(Vector2i(int(cell[0]), int(cell[1])), SRC_ID, atlas)
		i += 1


func _cell_center(x: int, y: int) -> Vector2:
	return Vector2(
		float(x * Maps.TILE) + float(Maps.TILE) * 0.5,
		float(y * Maps.TILE) + float(Maps.TILE) * 0.5
	)
