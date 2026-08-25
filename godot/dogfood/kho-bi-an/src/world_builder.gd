class_name WorldBuilder
extends RefCounted

const SRC_ID: int = 0
const FLOOR_START: Vector2i = Vector2i(0, 0)
const FLOOR_DOOR: Vector2i = Vector2i(1, 0)
const FLOOR_RELIC: Vector2i = Vector2i(2, 0)
const WALL: Vector2i = Vector2i(3, 0)


func build() -> Node2D:
	var world: Node2D = Node2D.new()
	world.name = "Overworld"
	var layer: TileMapLayer = TileMapLayer.new()
	layer.name = "VaultRooms"
	layer.tile_set = _make_tileset()
	layer.collision_enabled = true
	_paint(layer)
	world.add_child(layer)
	world.add_child(_color_prop("Key", VaultMap.tile_center(VaultMap.KEY_CELL), Vector2(16, 16), Color(0.85, 0.70, 0.22)))
	world.add_child(_make_door())
	world.add_child(_color_prop("Relic", VaultMap.tile_center(VaultMap.RELIC_CELL), Vector2(16, 16), Color(0.35, 0.72, 0.62)))
	return world


func _make_tileset() -> TileSet:
	var ts: TileSet = TileSet.new()
	ts.tile_size = Vector2i(VaultMap.TILE, VaultMap.TILE)
	ts.add_physics_layer(-1)
	ts.set_physics_layer_collision_layer(0, VaultMap.COL_WORLD)
	ts.set_physics_layer_collision_mask(0, 0)
	var img: Image = Image.create(64, 16, false, Image.FORMAT_RGBA8)
	img.fill_rect(Rect2i(0, 0, 16, 16), Color(0.14, 0.18, 0.30))
	img.fill_rect(Rect2i(16, 0, 16, 16), Color(0.20, 0.14, 0.16))
	img.fill_rect(Rect2i(32, 0, 16, 16), Color(0.12, 0.22, 0.22))
	img.fill_rect(Rect2i(48, 0, 16, 16), Color(0.06, 0.07, 0.11))
	var tex: ImageTexture = ImageTexture.create_from_image(img)
	var atlas: TileSetAtlasSource = TileSetAtlasSource.new()
	atlas.texture = tex
	atlas.texture_region_size = Vector2i(VaultMap.TILE, VaultMap.TILE)
	atlas.create_tile(FLOOR_START)
	atlas.create_tile(FLOOR_DOOR)
	atlas.create_tile(FLOOR_RELIC)
	atlas.create_tile(WALL)
	ts.add_source(atlas, SRC_ID)
	var wall_data: TileData = atlas.get_tile_data(WALL, 0)
	if wall_data != null:
		if wall_data.get_collision_polygons_count(0) < 1:
			wall_data.add_collision_polygon(0)
		var half: float = float(VaultMap.TILE) * 0.5
		var poly: PackedVector2Array = PackedVector2Array()
		poly.append(Vector2(-half, -half))
		poly.append(Vector2(half, -half))
		poly.append(Vector2(half, half))
		poly.append(Vector2(-half, half))
		wall_data.set_collision_polygon_points(0, 0, poly)
	return ts


func _paint(layer: TileMapLayer) -> void:
	var y: int = 0
	while y < VaultMap.MAP_H:
		var x: int = 0
		while x < VaultMap.MAP_W:
			var cell: Vector2i = Vector2i(x, y)
			if VaultMap.is_border_wall(cell):
				layer.set_cell(cell, SRC_ID, WALL)
			else:
				var floor_atlas: Vector2i = FLOOR_START
				if x > VaultMap.DIV_DOOR_RELIC:
					floor_atlas = FLOOR_RELIC
				elif x >= VaultMap.DIV_START_DOOR:
					floor_atlas = FLOOR_DOOR
				layer.set_cell(cell, SRC_ID, floor_atlas)
			x += 1
		y += 1


func _make_door() -> StaticBody2D:
	var door: StaticBody2D = StaticBody2D.new()
	door.name = "Door"
	door.collision_layer = VaultMap.COL_DOOR
	door.collision_mask = 0
	door.position = VaultMap.tile_center(VaultMap.DOOR_CELL)
	var shape: CollisionShape2D = CollisionShape2D.new()
	var rect: RectangleShape2D = RectangleShape2D.new()
	rect.size = Vector2(12, 48)
	shape.shape = rect
	door.add_child(shape)
	var body: ColorRect = ColorRect.new()
	body.name = "Body"
	body.size = Vector2(16, 48)
	body.position = Vector2(-8, -24)
	body.color = Color(0.72, 0.58, 0.28)
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	door.add_child(body)
	return door


func _color_prop(prop_name: String, at: Vector2, size: Vector2, color: Color) -> Node2D:
	var node: Node2D = Node2D.new()
	node.name = prop_name
	node.position = at
	var body: ColorRect = ColorRect.new()
	body.name = "Body"
	body.size = size
	body.position = Vector2(-size.x * 0.5, -size.y * 0.5)
	body.color = color
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	node.add_child(body)
	return node
