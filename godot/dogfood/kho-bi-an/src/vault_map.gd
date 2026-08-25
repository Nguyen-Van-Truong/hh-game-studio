class_name VaultMap
extends RefCounted

const TILE: int = 16
const MAP_W: int = 48
const MAP_H: int = 16
const ACTOR: int = 32
const INTERACT_REACH: float = 28.0
const WARDEN_TOUCH: float = 22.0
const PLAYER_SPEED: float = 120.0
const WARDEN_SPEED: float = 36.0
const CAMERA_ZOOM: float = 2.0

const PLAYER_SPAWN: Vector2i = Vector2i(4, 8)
const KEY_CELL: Vector2i = Vector2i(10, 8)
const DOOR_CELL: Vector2i = Vector2i(26, 7)
const RELIC_CELL: Vector2i = Vector2i(34, 8)
const DOOR_ROOM: Vector2i = Vector2i(18, 8)
const RELIC_ENTER: Vector2i = Vector2i(28, 8)
const WARDEN_A: Vector2i = Vector2i(18, 6)
const WARDEN_B: Vector2i = Vector2i(23, 6)

const OPENING_Y0: int = 6
const OPENING_Y1: int = 8
const DIV_START_DOOR: int = 13
const DIV_DOOR_RELIC: int = 26

const COL_WORLD: int = 1
const COL_PLAYER: int = 2
const COL_WARDEN: int = 4
const COL_DOOR: int = 16


static func tile_center(cell: Vector2i) -> Vector2:
	return Vector2(
		float(cell.x * TILE + TILE / 2),
		float(cell.y * TILE + TILE / 2)
	)


static func map_size_px() -> Vector2:
	return Vector2(float(MAP_W * TILE), float(MAP_H * TILE))


static func room_id_at(world: Vector2) -> String:
	var col: int = int(floor(world.x / float(TILE)))
	# Relic begins strictly past the door column. The door tile is "door".
	if col > DIV_DOOR_RELIC:
		return "relic"
	if col >= DIV_START_DOOR:
		return "door"
	return "start"


static func is_relic_room(room_id: String) -> bool:
	return room_id == "relic"


static func is_start_side_room(room_id: String) -> bool:
	return room_id == "start" or room_id == "door"


static func is_opening_cell(cell: Vector2i) -> bool:
	if cell.y < OPENING_Y0 or cell.y > OPENING_Y1:
		return false
	return cell.x == DIV_START_DOOR or cell.x == DIV_DOOR_RELIC


static func is_border_wall(cell: Vector2i) -> bool:
	if cell.x <= 0 or cell.y <= 0 or cell.x >= MAP_W - 1 or cell.y >= MAP_H - 1:
		return true
	if is_opening_cell(cell):
		return false
	if cell.x == DIV_START_DOOR or cell.x == DIV_DOOR_RELIC:
		return true
	return false
