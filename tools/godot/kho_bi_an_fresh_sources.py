#!/usr/bin/env python3
"""Text files emitted by R8-WP6 recreate. Not a dogfood src copy.

Only these strings plus PROJECT_BRIEF.md + ASSET_MANIFEST pin bytes
are written into a fresh tree. Stdlib only. --provider unused.
"""

from __future__ import annotations

HEADER = (
    "# Generated from PROJECT_BRIEF.md + ASSET_MANIFEST pins.\n"
    "# Not a dogfood src copy. Relic-reached is win. not_g5=1.\n"
)

BUS_LAYOUT = """[gd_resource type="AudioBusLayout" format=3]

[resource]
bus/1/name = "Music"
bus/1/solo = false
bus/1/mute = false
bus/1/bypass_fx = false
bus/1/volume_db = 0.0
bus/1/send = &"Master"
bus/2/name = "SFX"
bus/2/solo = false
bus/2/mute = false
bus/2/bypass_fx = false
bus/2/volume_db = 0.0
bus/2/send = &"Master"
"""

MAIN_TSCN = """[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://src/app.gd" id="1_app"]

[node name="App" type="Node"]
process_mode = 3
script = ExtResource("1_app")
"""

EXPORT_PRESETS = """[runnable]

Windows Desktop="Windows Desktop"

[preset.0]

name="Windows Desktop"
platform="Windows Desktop"
dedicated_server=false
custom_features=""
export_filter="all_resources"
include_filter=""
exclude_filter="addons/*,.hh-agent/*,*token*,*evidence*,tests/*,recreate_manifest.json"
export_path=""
patches=PackedStringArray()
encryption_include_filters=""
encryption_exclude_filters=""
encrypt_pck=false
encrypt_directory=false
script_export_mode=2

[preset.0.options]

custom_template/debug=""
custom_template/release=""
debug/export_console_wrapper=1
binary_format/embed_pck=true
texture_format/s3tc_bptc=true
texture_format/etc2_astc=false
binary_format/architecture="x86_64"
codesign/enable=false
application/modify_resources=true
application/icon=""
application/console_wrapper_icon=""
application/icon_interpolation=4
application/file_version=""
application/product_version=""
application/company_name="HH Game Studio"
application/product_name="Kho Bi An"
application/file_description="Kho Bi An review build. Relic-reached is win. Not G5."
application/copyright=""
application/trademarks=""
application/export_angle=0
application/export_d3d12=0
application/d3d12_agility_sdk_multiarch=true
ssh_remote_deploy/enabled=false
"""


def project_godot(view_w: int, view_h: int, stretch_mode: str, stretch_aspect: str) -> str:
    return (
        "; Engine configuration file.\n"
        "; Generated from PROJECT_BRIEF.md + ASSET_MANIFEST pins.\n"
        "; Relic-reached is win. Door-open is not win. Not G5.\n"
        "\n"
        "config_version=5\n"
        "\n"
        "[application]\n"
        "\n"
        'config/name="Kho Bi An"\n'
        'config/description="R8-WP6 fresh recreate. Relic-reached is win. Not G5."\n'
        'run/main_scene="res://scenes/main.tscn"\n'
        'config/features=PackedStringArray("4.7", "Forward Plus")\n'
        "\n"
        "[audio]\n"
        "\n"
        'buses/default_bus_layout="res://default_bus_layout.tres"\n'
        "\n"
        "[autoload]\n"
        "\n"
        'SaveService="*res://autoload/save_service.gd"\n'
        "\n"
        "[debug]\n"
        "\n"
        "gdscript/warnings/untyped_declaration=1\n"
        "gdscript/warnings/inferred_declaration=1\n"
        "\n"
        "[display]\n"
        "\n"
        f"window/size/viewport_width={view_w}\n"
        f"window/size/viewport_height={view_h}\n"
        f'window/stretch/mode="{stretch_mode}"\n'
        f'window/stretch/aspect="{stretch_aspect}"\n'
        "\n"
        "[physics]\n"
        "\n"
        "common/physics_ticks_per_second=60\n"
        "\n"
        "[importer_defaults]\n"
        "\n"
        "texture={\n"
        '"compress/channel_pack": 0,\n'
        '"compress/hdr_compression": 1,\n'
        '"compress/high_quality": false,\n'
        '"compress/lossy_quality": 0.7,\n'
        '"compress/mode": 0,\n'
        '"compress/normal_map": 0,\n'
        '"detect_3d/compress_to": 0,\n'
        '"mipmaps/generate": false,\n'
        '"mipmaps/limit": -1,\n'
        '"process/channel_remap/alpha": 3,\n'
        '"process/channel_remap/blue": 2,\n'
        '"process/channel_remap/green": 1,\n'
        '"process/channel_remap/red": 0,\n'
        '"process/fix_alpha_border": true,\n'
        '"process/hdr_as_srgb": false,\n'
        '"process/hdr_clamp_exposure": false,\n'
        '"process/normal_map_invert_y": false,\n'
        '"process/premult_alpha": false,\n'
        '"process/size_limit": 0\n'
        "}\n"
        "wav={\n"
        '"compress/mode": 0,\n'
        '"edit/loop_begin": 0,\n'
        '"edit/loop_end": -1,\n'
        '"edit/loop_mode": 0,\n'
        '"edit/normalize": false,\n'
        '"edit/trim": false,\n'
        '"force/8_bit": false,\n'
        '"force/max_rate": false,\n'
        '"force/max_rate_hz": 44100,\n'
        '"force/mono": false\n'
        "}\n"
        "\n"
        "[rendering]\n"
        "\n"
        "textures/canvas_textures/default_texture_filter=0\n"
        "environment/defaults/default_clear_color=Color(0.0705882, 0.0862745, 0.164706, 1)\n"
    )


GAME_STATE = HEADER + r'''class_name GameState
extends RefCounted

const SCHEMA: int = 1

var room_id: String = "start"
var has_key: bool = false
var door_open: bool = false
var relic_reached: bool = false
var outcome: String = "play"


func is_win() -> bool:
	return relic_reached


func reset() -> void:
	room_id = "start"
	has_key = false
	door_open = false
	relic_reached = false
	outcome = "play"


func to_dict() -> Dictionary:
	return {
		"schema": SCHEMA,
		"room_id": room_id,
		"has_key": has_key,
		"door_open": door_open,
		"relic_reached": relic_reached,
	}


func apply_dict(data: Dictionary) -> void:
	room_id = str(data.get("room_id", "start"))
	has_key = bool(data.get("has_key", false))
	door_open = bool(data.get("door_open", false))
	relic_reached = bool(data.get("relic_reached", false))
	if relic_reached:
		outcome = "win"
	else:
		outcome = "play"
'''

VAULT_MAP = HEADER + r'''class_name VaultMap
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
const DESIGNED_VIEW: Vector2 = Vector2(1280.0, 720.0)

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


static func zoom_for_size(vp: Vector2) -> float:
	var map_h: float = float(MAP_H * TILE)
	if vp.y < 8.0:
		return CAMERA_ZOOM
	var fill_h: float = vp.y / map_h
	if vp.x <= 900.0:
		return maxf(fill_h, 2.45)
	return fill_h


static func room_id_at(world: Vector2) -> String:
	var col: int = int(floor(world.x / float(TILE)))
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
'''

INPUT_ACTIONS = HEADER + r'''class_name InputActions
extends RefCounted


static func install() -> void:
	_bind_move("move_left", KEY_A, KEY_LEFT, JOY_BUTTON_DPAD_LEFT, JOY_AXIS_LEFT_X, -1.0)
	_bind_move("move_right", KEY_D, KEY_RIGHT, JOY_BUTTON_DPAD_RIGHT, JOY_AXIS_LEFT_X, 1.0)
	_bind_move("move_up", KEY_W, KEY_UP, JOY_BUTTON_DPAD_UP, JOY_AXIS_LEFT_Y, -1.0)
	_bind_move("move_down", KEY_S, KEY_DOWN, JOY_BUTTON_DPAD_DOWN, JOY_AXIS_LEFT_Y, 1.0)
	_ensure("interact")
	if InputMap.action_get_events("interact").is_empty():
		_add_key("interact", KEY_E)
		_add_key("interact", KEY_ENTER)
		_add_joy_button("interact", JOY_BUTTON_A)
	_ensure("pause")
	if InputMap.action_get_events("pause").is_empty():
		_add_key("pause", KEY_ESCAPE)
		_add_joy_button("pause", JOY_BUTTON_START)


static func read_move() -> Vector2:
	var raw: Vector2 = Input.get_vector("move_left", "move_right", "move_up", "move_down")
	return cardinal(raw)


static func cardinal(raw: Vector2) -> Vector2:
	if raw.length_squared() <= 0.0001:
		return Vector2.ZERO
	if absf(raw.x) >= absf(raw.y):
		return Vector2(signf(raw.x), 0.0)
	return Vector2(0.0, signf(raw.y))


static func has_keyboard_and_gamepad(action: String) -> bool:
	var key_ok: bool = false
	var pad_ok: bool = false
	var events: Array = InputMap.action_get_events(action)
	var i: int = 0
	while i < events.size():
		var ev: InputEvent = events[i] as InputEvent
		if ev is InputEventKey:
			key_ok = true
		if ev is InputEventJoypadButton or ev is InputEventJoypadMotion:
			pad_ok = true
		i += 1
	return key_ok and pad_ok


static func _bind_move(
	action: String,
	letter: Key,
	arrow: Key,
	dpad: JoyButton,
	axis: JoyAxis,
	axis_value: float
) -> void:
	_ensure(action)
	if not InputMap.action_get_events(action).is_empty():
		return
	_add_key(action, letter)
	_add_key(action, arrow)
	_add_joy_button(action, dpad)
	_add_joy_axis(action, axis, axis_value)


static func _ensure(action: String) -> void:
	if not InputMap.has_action(action):
		InputMap.add_action(action, 0.5)


static func _add_key(action: String, keycode: Key) -> void:
	var ev: InputEventKey = InputEventKey.new()
	ev.physical_keycode = keycode
	InputMap.action_add_event(action, ev)


static func _add_joy_button(action: String, button: JoyButton) -> void:
	var ev: InputEventJoypadButton = InputEventJoypadButton.new()
	ev.button_index = button
	InputMap.action_add_event(action, ev)


static func _add_joy_axis(action: String, axis: JoyAxis, axis_value: float) -> void:
	var ev: InputEventJoypadMotion = InputEventJoypadMotion.new()
	ev.axis = axis
	ev.axis_value = axis_value
	InputMap.action_add_event(action, ev)
'''

INVENTORY = HEADER + r'''class_name Inventory
extends RefCounted

var _items: Array[String] = []


func add(item_id: String) -> void:
	if item_id.is_empty():
		return
	if has_item(item_id):
		return
	_items.append(item_id)


func has_item(item_id: String) -> bool:
	return _items.has(item_id)


func remove(item_id: String) -> void:
	var idx: int = _items.find(item_id)
	if idx >= 0:
		_items.remove_at(idx)


func clear() -> void:
	_items.clear()


func ids() -> Array[String]:
	return _items.duplicate()
'''

VISUALS = HEADER + r'''class_name Visuals
extends RefCounted

const KEY_TEX: String = "res://assets/art/item_key.png"
const DOOR_TEX: String = "res://assets/art/prop_door.png"
const RELIC_TEX: String = "res://assets/art/item_relic.png"
const KEY_ICON: String = "res://assets/ui/ui_icon_key.png"
const TILESET: String = "res://assets/tiles/tileset_vault.png"
const PLAYER_TEX: String = "res://assets/art/actor_player.png"
const WARDEN_TEX: String = "res://assets/art/actor_warden.png"
const VFX_TEX: String = "res://assets/vfx/vfx_interact.png"


static func hide_body(host: Node) -> void:
	var body: ColorRect = host.get_node_or_null("Body") as ColorRect
	if body == null:
		return
	body.visible = false
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var faded: Color = body.color
	faded.a = 0.0
	body.color = faded


static func _atlas(tex: Texture2D, x: int, y: int, w: int, h: int) -> AtlasTexture:
	var at: AtlasTexture = AtlasTexture.new()
	at.atlas = tex
	at.region = Rect2(float(x), float(y), float(w), float(h))
	return at


static func actor_frames(tex_path: String) -> SpriteFrames:
	var tex: Texture2D = load(tex_path) as Texture2D
	var frames: SpriteFrames = SpriteFrames.new()
	var sides: PackedStringArray = PackedStringArray(["down", "left", "right", "up"])
	var row: int = 0
	while row < sides.size():
		var side: String = String(sides[row])
		var idle: StringName = StringName("idle_%s" % side)
		var walk: StringName = StringName("walk_%s" % side)
		frames.add_animation(idle)
		frames.set_animation_speed(idle, 4.0)
		frames.set_animation_loop(idle, true)
		frames.add_frame(idle, _atlas(tex, 0, row * 32, 32, 32))
		frames.add_frame(idle, _atlas(tex, 32, row * 32, 32, 32))
		frames.add_animation(walk)
		frames.set_animation_speed(walk, 8.0)
		frames.set_animation_loop(walk, true)
		var col: int = 0
		while col < 4:
			frames.add_frame(walk, _atlas(tex, 64 + col * 32, row * 32, 32, 32))
			col += 1
		row += 1
	return frames


static func vfx_frames() -> SpriteFrames:
	var tex: Texture2D = load(VFX_TEX) as Texture2D
	var frames: SpriteFrames = SpriteFrames.new()
	frames.add_animation(&"burst")
	frames.set_animation_speed(&"burst", 10.0)
	frames.set_animation_loop(&"burst", false)
	var i: int = 0
	while i < 4:
		frames.add_frame(&"burst", _atlas(tex, i * 16, 0, 16, 16))
		i += 1
	return frames


static func attach_actor(host: Node2D, tex_path: String) -> AnimatedSprite2D:
	hide_body(host)
	var existing: AnimatedSprite2D = host.get_node_or_null("Sprite") as AnimatedSprite2D
	if existing != null:
		return existing
	var sprite: AnimatedSprite2D = AnimatedSprite2D.new()
	sprite.name = "Sprite"
	sprite.centered = true
	sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	sprite.sprite_frames = actor_frames(tex_path)
	host.add_child(sprite)
	return sprite


static func attach_sprite(host: Node2D, tex_path: String) -> Sprite2D:
	hide_body(host)
	var existing: Sprite2D = host.get_node_or_null("Sprite") as Sprite2D
	if existing != null:
		return existing
	var sprite: Sprite2D = Sprite2D.new()
	sprite.name = "Sprite"
	sprite.centered = true
	sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	sprite.texture = load(tex_path) as Texture2D
	host.add_child(sprite)
	return sprite


static func clip_for(facing: Vector2, moving: bool) -> StringName:
	var side: String = "down"
	if facing.x < -0.1:
		side = "left"
	elif facing.x > 0.1:
		side = "right"
	elif facing.y < -0.1:
		side = "up"
	elif facing.y > 0.1:
		side = "down"
	if moving:
		return StringName("walk_%s" % side)
	return StringName("idle_%s" % side)


static func play_actor(sprite: AnimatedSprite2D, facing: Vector2, moving: bool) -> void:
	if sprite == null or sprite.sprite_frames == null:
		return
	var clip: StringName = clip_for(facing, moving)
	if sprite.animation != clip:
		sprite.play(clip)
	elif not sprite.is_playing():
		sprite.play(clip)


static func lantern_texture() -> GradientTexture2D:
	var grad: Gradient = Gradient.new()
	grad.set_color(0, Color(1.0, 0.86, 0.55, 1.0))
	grad.set_color(1, Color(1.0, 0.78, 0.40, 0.0))
	var tex: GradientTexture2D = GradientTexture2D.new()
	tex.gradient = grad
	tex.width = 128
	tex.height = 128
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(1.0, 0.5)
	return tex


static func make_lantern(light_name: String, energy: float, tex_scale: float) -> PointLight2D:
	var light: PointLight2D = PointLight2D.new()
	light.name = light_name
	light.texture = lantern_texture()
	light.energy = energy
	light.texture_scale = tex_scale
	light.color = Color(1.0, 0.82, 0.55)
	light.shadow_enabled = false
	return light


static func make_shade() -> CanvasModulate:
	var shade: CanvasModulate = CanvasModulate.new()
	shade.name = "VaultShade"
	shade.color = Color(0.70, 0.72, 0.80)
	return shade
'''

PLAYER = HEADER + r'''class_name Player
extends CharacterBody2D

var facing: Vector2 = Vector2.DOWN
var sprite: AnimatedSprite2D
var lantern: PointLight2D


func _ready() -> void:
	name = "Player"
	motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	collision_layer = VaultMap.COL_PLAYER
	collision_mask = VaultMap.COL_WORLD | VaultMap.COL_DOOR
	var shape: CollisionShape2D = CollisionShape2D.new()
	var rect: RectangleShape2D = RectangleShape2D.new()
	rect.size = Vector2(10, 10)
	shape.shape = rect
	add_child(shape)
	var body: ColorRect = ColorRect.new()
	body.name = "Body"
	body.size = Vector2(float(VaultMap.ACTOR), float(VaultMap.ACTOR))
	body.position = Vector2(-float(VaultMap.ACTOR) * 0.5, -float(VaultMap.ACTOR) * 0.5)
	body.color = Color(0.93, 0.86, 0.70)
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(body)
	sprite = Visuals.attach_actor(self, Visuals.PLAYER_TEX)
	sprite.play("idle_down")
	lantern = Visuals.make_lantern("Lantern", 0.85, 1.7)
	add_child(lantern)
	var cam: Camera2D = Camera2D.new()
	cam.name = "Camera"
	cam.limit_left = 0
	cam.limit_top = 0
	cam.limit_right = VaultMap.MAP_W * VaultMap.TILE
	cam.limit_bottom = VaultMap.MAP_H * VaultMap.TILE
	cam.position_smoothing_enabled = false
	add_child(cam)
	var vp: Viewport = get_viewport()
	if vp != null:
		fit_camera(vp.get_visible_rect().size)
	else:
		fit_camera(VaultMap.DESIGNED_VIEW)


func fit_camera(vp_size: Vector2) -> void:
	var cam: Camera2D = get_node_or_null("Camera") as Camera2D
	if cam == null:
		return
	var z: float = VaultMap.zoom_for_size(vp_size)
	cam.zoom = Vector2(z, z)
	if is_inside_tree():
		cam.make_current()
		cam.force_update_scroll()


func step_move(delta: float, dir: Vector2) -> void:
	velocity = dir * VaultMap.PLAYER_SPEED
	move_and_slide()
	if dir != Vector2.ZERO:
		facing = dir
	Visuals.play_actor(sprite, facing, dir != Vector2.ZERO)


func pulse() -> void:
	if sprite == null:
		return
	sprite.modulate = Color(1.18, 1.08, 0.88)
'''

WARDEN = HEADER + r'''class_name Warden
extends CharacterBody2D

var _a: Vector2 = Vector2.ZERO
var _b: Vector2 = Vector2.ZERO
var _travel: float = 0.0
var _facing: Vector2 = Vector2.RIGHT
var sprite: AnimatedSprite2D


func _ready() -> void:
	name = "Warden"
	motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	collision_layer = VaultMap.COL_WARDEN
	collision_mask = VaultMap.COL_WORLD
	var shape: CollisionShape2D = CollisionShape2D.new()
	var rect: RectangleShape2D = RectangleShape2D.new()
	rect.size = Vector2(12, 12)
	shape.shape = rect
	add_child(shape)
	var body: ColorRect = ColorRect.new()
	body.name = "Body"
	body.size = Vector2(float(VaultMap.ACTOR), float(VaultMap.ACTOR))
	body.position = Vector2(-float(VaultMap.ACTOR) * 0.5, -float(VaultMap.ACTOR) * 0.5)
	body.color = Color(0.72, 0.22, 0.18)
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(body)
	sprite = Visuals.attach_actor(self, Visuals.WARDEN_TEX)
	sprite.play("idle_right")


func set_patrol(a: Vector2, b: Vector2) -> void:
	_a = a
	_b = b
	global_position = a
	_travel = 0.0
	_facing = Vector2.RIGHT


func step_patrol(delta: float) -> void:
	var before: Vector2 = global_position
	var span: float = _a.distance_to(_b)
	if span > 0.001:
		_travel += delta * VaultMap.WARDEN_SPEED
		var ping: float = pingpong(_travel / span, 1.0)
		global_position = _a.lerp(_b, ping)
	var moved: Vector2 = global_position - before
	var moving: bool = moved.length_squared() > 0.0001
	if moving:
		_facing = InputActions.cardinal(moved)
	Visuals.play_actor(sprite, _facing, moving)


func touches_player(who: Node2D) -> bool:
	return global_position.distance_to(who.global_position) <= VaultMap.WARDEN_TOUCH
'''

WORLD_BUILDER = HEADER + r'''class_name WorldBuilder
extends RefCounted

const SRC_ID: int = 0
const TILESET_PATH: String = "res://assets/tiles/tileset_vault.png"
const FLOOR_START: Vector2i = Vector2i(0, 0)
const FLOOR_DOOR: Vector2i = Vector2i(1, 0)
const FLOOR_RELIC: Vector2i = Vector2i(2, 0)
const WALL: Vector2i = Vector2i(3, 0)


func build() -> Node2D:
	var world: Node2D = Node2D.new()
	world.name = "Overworld"
	world.add_child(_make_backdrop())
	var layer: TileMapLayer = TileMapLayer.new()
	layer.name = "VaultRooms"
	layer.tile_set = _make_tileset()
	layer.collision_enabled = true
	_paint(layer)
	world.add_child(layer)
	world.add_child(Visuals.make_shade())
	world.add_child(_color_prop("Key", VaultMap.tile_center(VaultMap.KEY_CELL), Vector2(16, 16), Color(0.85, 0.70, 0.22), Visuals.KEY_TEX))
	world.add_child(_make_door())
	world.add_child(_color_prop("Relic", VaultMap.tile_center(VaultMap.RELIC_CELL), Vector2(16, 16), Color(0.35, 0.72, 0.62), Visuals.RELIC_TEX))
	var relic_light: PointLight2D = Visuals.make_lantern("RelicLantern", 0.55, 1.8)
	relic_light.position = VaultMap.tile_center(VaultMap.RELIC_CELL)
	world.add_child(relic_light)
	var door_light: PointLight2D = Visuals.make_lantern("DoorLantern", 0.40, 1.4)
	door_light.position = VaultMap.tile_center(VaultMap.DOOR_CELL)
	world.add_child(door_light)
	return world


func _make_backdrop() -> ColorRect:
	var back: ColorRect = ColorRect.new()
	back.name = "VaultBackdrop"
	back.color = UiTheme.INDIGO
	back.position = Vector2(-4096, -4096)
	back.size = Vector2(8192, 8192)
	back.mouse_filter = Control.MOUSE_FILTER_IGNORE
	back.z_index = -10
	return back


func _make_tileset() -> TileSet:
	var ts: TileSet = TileSet.new()
	ts.tile_size = Vector2i(VaultMap.TILE, VaultMap.TILE)
	ts.add_physics_layer(-1)
	ts.set_physics_layer_collision_layer(0, VaultMap.COL_WORLD)
	ts.set_physics_layer_collision_mask(0, 0)
	var tex: Texture2D = load(TILESET_PATH) as Texture2D
	if tex == null:
		push_error("WorldBuilder live TileMapLayer missing %s" % TILESET_PATH)
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
	Visuals.attach_sprite(door, Visuals.DOOR_TEX)
	return door


func _color_prop(prop_name: String, at: Vector2, size: Vector2, color: Color, tex_path: String) -> Node2D:
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
	Visuals.attach_sprite(node, tex_path)
	return node
'''

GAME_SESSION = HEADER + r'''class_name GameSession
extends Node2D

signal won
signal lost

var state: GameState = GameState.new()
var inventory: Inventory = Inventory.new()
var player: Player
var warden: Warden
var world: Node2D
var hud: Hud
var pause_screen: PauseScreen
var sfx: SfxBank
var test_driven: bool = false
var _first_move_done: bool = false
var _first_interact_done: bool = false
var _pulse_left: float = 0.0


func setup(saved: Dictionary) -> void:
	name = "GameSession"
	process_mode = Node.PROCESS_MODE_PAUSABLE
	var builder: WorldBuilder = WorldBuilder.new()
	world = builder.build()
	add_child(world)
	player = Player.new()
	add_child(player)
	warden = Warden.new()
	add_child(warden)
	warden.set_patrol(VaultMap.tile_center(VaultMap.WARDEN_A), VaultMap.tile_center(VaultMap.WARDEN_B))
	hud = Hud.new()
	add_child(hud)
	pause_screen = PauseScreen.new()
	pause_screen.resume_pressed.connect(set_paused.bind(false))
	add_child(pause_screen)
	sfx = SfxBank.new()
	add_child(sfx)
	sfx.start_music()
	_apply_saved(saved)
	hud.set_has_key(inventory.has_item("key"))
	hud.set_hint("WASD / stick: move")
	var vp: Viewport = get_viewport()
	if vp != null and not vp.size_changed.is_connected(refit_view):
		vp.size_changed.connect(refit_view)
	refit_view()


func _physics_process(delta: float) -> void:
	if test_driven:
		return
	var tree: SceneTree = get_tree()
	if tree != null and tree.paused:
		return
	if state.outcome != "play":
		return
	var move: Vector2 = InputActions.read_move()
	var interact: bool = Input.is_action_just_pressed("interact")
	step_fixed(delta, move, interact)


func step_fixed(delta: float, move: Vector2, interact: bool) -> void:
	if state.outcome != "play":
		return
	var tree: SceneTree = get_tree()
	if tree != null and tree.paused:
		return
	var dir: Vector2 = InputActions.cardinal(move)
	if dir != Vector2.ZERO and not _first_move_done:
		_first_move_done = true
		hud.set_hint("E / South: interact")
	player.step_move(delta, dir)
	warden.step_patrol(delta)
	state.room_id = VaultMap.room_id_at(player.global_position)
	_tick_pulse(delta)
	if warden.touches_player(player):
		_set_lose()
		return
	if interact:
		_interact()
	hud.set_has_key(inventory.has_item("key"))


func refit_view() -> void:
	var vp: Viewport = get_viewport()
	if vp == null or player == null:
		return
	player.fit_camera(vp.get_visible_rect().size)
	if hud != null:
		hud.layout_on_playfield(playfield_screen_rect())


func playfield_screen_rect() -> Rect2:
	var vp: Viewport = get_viewport()
	if vp == null:
		return Rect2(Vector2.ZERO, VaultMap.DESIGNED_VIEW)
	var xform: Transform2D = vp.get_canvas_transform()
	var map: Vector2 = VaultMap.map_size_px()
	var tl: Vector2 = xform * Vector2.ZERO
	var br: Vector2 = xform * map
	var world_r: Rect2 = Rect2(tl, br - tl)
	var view_r: Rect2 = Rect2(Vector2.ZERO, vp.get_visible_rect().size)
	var hit: Rect2 = world_r.intersection(view_r)
	if hit.size.x < 8.0 or hit.size.y < 8.0:
		return view_r
	return hit


func set_paused(active: bool) -> void:
	if state.outcome != "play" and active:
		return
	var tree: SceneTree = get_tree()
	if tree == null:
		return
	tree.paused = active
	if sfx != null:
		sfx.duck(active)
	if active:
		pause_screen.show_pause()
	else:
		pause_screen.hide_pause()


func snapshot() -> Dictionary:
	var data: Dictionary = state.to_dict()
	data["outcome"] = state.outcome
	data["win"] = state.is_win()
	data["player_x"] = player.global_position.x
	data["player_y"] = player.global_position.y
	data["inventory_key"] = inventory.has_item("key")
	return data


func _apply_saved(saved: Dictionary) -> void:
	state.reset()
	inventory.clear()
	if saved.is_empty():
		player.global_position = VaultMap.tile_center(VaultMap.PLAYER_SPAWN)
		return
	state.apply_dict(saved)
	if state.has_key:
		inventory.add("key")
		_set_prop_visible("Key", false)
	if state.door_open:
		_open_door_collision()
	_place_in_room(state.room_id)


func _place_in_room(room_id: String) -> void:
	if room_id == "relic" and state.door_open:
		player.global_position = VaultMap.tile_center(VaultMap.RELIC_ENTER)
	elif room_id == "door":
		player.global_position = VaultMap.tile_center(VaultMap.DOOR_ROOM)
	else:
		player.global_position = VaultMap.tile_center(VaultMap.PLAYER_SPAWN)


func _interact() -> void:
	if not _first_interact_done:
		_first_interact_done = true
		hud.set_hint("")
	_pulse_left = 0.12
	player.pulse()
	_spawn_vfx(player.global_position)
	if sfx != null:
		sfx.play("interact")
	var kind: String = _nearest_kind()
	if kind == "key":
		_pickup_key()
	elif kind == "door":
		_try_open_door()
	elif kind == "relic":
		_reach_relic()


func _nearest_kind() -> String:
	var best: String = ""
	var best_d: float = VaultMap.INTERACT_REACH
	var names: PackedStringArray = PackedStringArray(["Key", "Door", "Relic"])
	var kinds: PackedStringArray = PackedStringArray(["key", "door", "relic"])
	var i: int = 0
	while i < names.size():
		var node: Node2D = world.get_node_or_null(String(names[i])) as Node2D
		var kind: String = String(kinds[i])
		i += 1
		if node == null:
			continue
		if kind == "key" and inventory.has_item("key"):
			continue
		if kind == "door" and state.door_open:
			continue
		if kind == "relic" and state.relic_reached:
			continue
		var dist: float = player.global_position.distance_to(node.global_position)
		if dist <= best_d:
			best_d = dist
			best = kind
	return best


func _pickup_key() -> void:
	inventory.add("key")
	state.has_key = true
	_set_prop_visible("Key", false)
	hud.set_hint("Key taken")
	if sfx != null:
		sfx.play("pickup")
	_persist()


func _try_open_door() -> void:
	if not inventory.has_item("key"):
		hud.set_hint("Need the key")
		return
	state.door_open = true
	_open_door_collision()
	hud.set_hint("Door open")
	if sfx != null:
		sfx.play("door")
	_persist()


func _reach_relic() -> void:
	if not state.door_open:
		hud.set_hint("Door still closed")
		return
	state.relic_reached = true
	state.outcome = "win"
	if sfx != null:
		sfx.play("win")
	_persist()
	won.emit()


func _set_lose() -> void:
	state.outcome = "lose"
	if sfx != null:
		sfx.play("caught")
		sfx.play("lose")
	lost.emit()


func _open_door_collision() -> void:
	var door: StaticBody2D = world.get_node_or_null("Door") as StaticBody2D
	if door == null:
		return
	door.collision_layer = 0
	var body: ColorRect = door.get_node_or_null("Body") as ColorRect
	if body != null:
		body.visible = false
		body.color = Color(0.40, 0.34, 0.22, 0.0)
	var sprite: Sprite2D = door.get_node_or_null("Sprite") as Sprite2D
	if sprite != null:
		sprite.modulate = Color(1.0, 1.0, 1.0, 0.35)


func _set_prop_visible(prop_name: String, on: bool) -> void:
	var node: Node2D = world.get_node_or_null(prop_name) as Node2D
	if node != null:
		node.visible = on


func _persist() -> void:
	var tree: SceneTree = get_tree()
	if tree == null:
		return
	var saver: Node = tree.root.get_node_or_null("SaveService")
	if saver != null:
		saver.call("autosave", state)


func live_vfx_count() -> int:
	var n: int = 0
	var kids: Array = get_children()
	var i: int = 0
	while i < kids.size():
		var node: Node = kids[i] as Node
		if (
			node != null
			and String(node.name).begins_with("InteractVfx")
			and not node.is_queued_for_deletion()
		):
			n += 1
		i += 1
	return n


func _spawn_vfx(at: Vector2) -> void:
	_prune_vfx(3)
	var burst: AnimatedSprite2D = AnimatedSprite2D.new()
	burst.name = "InteractVfx"
	burst.centered = true
	burst.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	burst.sprite_frames = Visuals.vfx_frames()
	burst.global_position = at
	add_child(burst)
	burst.play("burst")
	burst.animation_finished.connect(_free_vfx.bind(burst))


func _prune_vfx(keep: int) -> void:
	var found: Array[Node] = []
	var kids: Array = get_children()
	var i: int = 0
	while i < kids.size():
		var node: Node = kids[i] as Node
		if node != null and String(node.name).begins_with("InteractVfx"):
			found.append(node)
		i += 1
	var extra: int = found.size() - keep
	var j: int = 0
	while j < extra:
		var old: Node = found[j]
		if is_instance_valid(old):
			old.free()
		j += 1


func _free_vfx(node: Node) -> void:
	if is_instance_valid(node):
		node.queue_free()


func _tick_pulse(delta: float) -> void:
	if _pulse_left <= 0.0:
		return
	_pulse_left -= delta
	if _pulse_left <= 0.0 and player != null and player.sprite != null:
		player.sprite.modulate = Color.WHITE
'''

APP = HEADER + r'''class_name App
extends Node

var title: TitleScreen
var win_screen: WinScreen
var lose_screen: LoseScreen
var session: GameSession
var test_driven: bool = false


func _enter_tree() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	RenderingServer.set_default_clear_color(UiTheme.INDIGO)
	if title != null:
		return
	InputActions.install()
	seed(1)
	title = TitleScreen.new()
	title.play_pressed.connect(start_new_run)
	title.continue_pressed.connect(continue_run)
	title.restart_pressed.connect(_title_restart)
	add_child(title)
	win_screen = WinScreen.new()
	win_screen.restart_pressed.connect(start_new_run)
	add_child(win_screen)
	lose_screen = LoseScreen.new()
	lose_screen.restart_pressed.connect(start_new_run)
	add_child(lose_screen)


func _ready() -> void:
	_refresh_title()


func _input(event: InputEvent) -> void:
	if session == null or session.state.outcome != "play":
		return
	if event.is_echo() or not event.is_pressed():
		return
	if not event.is_action("pause"):
		return
	var tree: SceneTree = get_tree()
	if tree == null:
		return
	session.set_paused(not tree.paused)
	get_viewport().set_input_as_handled()


func start_new_run() -> void:
	_begin_run({})


func continue_run() -> void:
	var data: Dictionary = _load_slot()
	if data.is_empty() or bool(data.get("relic_reached", false)):
		_begin_run({})
		return
	_begin_run(data)


func _title_restart() -> void:
	var saver: Node = _save_service()
	if saver != null:
		saver.call("clear_slot")
	_begin_run({})


func _begin_run(saved: Dictionary) -> void:
	_clear_session()
	if title == null or win_screen == null or lose_screen == null:
		push_error("App UI was not built")
		return
	title.visible = false
	win_screen.visible = false
	lose_screen.visible = false
	var tree: SceneTree = get_tree()
	if tree != null:
		tree.paused = false
	session = GameSession.new()
	session.test_driven = test_driven
	session.won.connect(_on_won)
	session.lost.connect(_on_lost)
	add_child(session)
	session.setup(saved)


func _clear_session() -> void:
	if session == null:
		return
	session.queue_free()
	session = null


func _on_won() -> void:
	win_screen.show_win()


func _on_lost() -> void:
	lose_screen.show_lose()


func _refresh_title() -> void:
	var data: Dictionary = _load_slot()
	var can_continue: bool = not data.is_empty() and not bool(data.get("relic_reached", false))
	title.set_continue_enabled(can_continue)


func _save_service() -> Node:
	var tree: SceneTree = get_tree()
	if tree == null:
		return null
	return tree.root.get_node_or_null("SaveService")


func _load_slot() -> Dictionary:
	var saver: Node = _save_service()
	if saver == null:
		return {}
	return saver.call("load_slot") as Dictionary
'''

HUD = HEADER + r'''class_name Hud
extends CanvasLayer

var _panel: ColorRect
var _key_icon: TextureRect
var _hint: Label


func _ready() -> void:
	name = "Hud"
	follow_viewport_enabled = false
	_panel = ColorRect.new()
	_panel.name = "Panel"
	_panel.color = UiTheme.INDIGO_PANEL
	_panel.size = Vector2(560, 48)
	_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_panel)
	_key_icon = TextureRect.new()
	_key_icon.name = "KeyIcon"
	_key_icon.size = Vector2(24, 24)
	_key_icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_key_icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_key_icon.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_key_icon.texture = load(Visuals.KEY_ICON) as Texture2D
	_key_icon.modulate = Color(0.40, 0.40, 0.44)
	_key_icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_key_icon)
	_hint = Label.new()
	_hint.name = "Hint"
	_hint.size = Vector2(500, 32)
	_hint.text = "WASD / stick: move"
	UiTheme.apply(_hint)
	_hint.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(_hint)
	layout_on_playfield(Rect2(Vector2.ZERO, Vector2(1280, 720)))


func layout_on_playfield(rect: Rect2) -> void:
	if _panel == null or _key_icon == null or _hint == null:
		return
	var origin: Vector2 = Vector2(16, 16)
	if rect.size.x >= 80.0 and rect.size.y >= 40.0:
		origin = rect.position + Vector2(16, 16)
	_panel.position = origin
	_key_icon.position = origin + Vector2(12, 12)
	_hint.position = origin + Vector2(44, 8)


func set_has_key(has_key: bool) -> void:
	if has_key:
		_key_icon.modulate = Color.WHITE
	else:
		_key_icon.modulate = Color(0.40, 0.40, 0.44)


func set_hint(text: String) -> void:
	_hint.text = text
'''

SFX_BANK = HEADER + r'''class_name SfxBank
extends Node

const MUSIC_PATH: String = "res://assets/audio/music_vault.wav"
const PATHS: Dictionary = {
	"pickup": "res://assets/audio/sfx_pickup.wav",
	"door": "res://assets/audio/sfx_door.wav",
	"caught": "res://assets/audio/sfx_caught.wav",
	"win": "res://assets/audio/sfx_win.wav",
	"lose": "res://assets/audio/sfx_lose.wav",
	"interact": "res://assets/audio/sfx_interact.wav",
}

var last_id: String = ""
var _sfx_a: AudioStreamPlayer
var _sfx_b: AudioStreamPlayer
var _music: AudioStreamPlayer
var _music_db_before_duck: float = 0.0
var _ducked: bool = false


func _ready() -> void:
	name = "SfxBank"
	process_mode = Node.PROCESS_MODE_ALWAYS
	_sfx_a = AudioStreamPlayer.new()
	_sfx_a.name = "SfxA"
	_sfx_a.bus = "SFX"
	add_child(_sfx_a)
	_sfx_b = AudioStreamPlayer.new()
	_sfx_b.name = "SfxB"
	_sfx_b.bus = "SFX"
	add_child(_sfx_b)
	_music = AudioStreamPlayer.new()
	_music.name = "Music"
	_music.bus = "Music"
	_music.process_mode = Node.PROCESS_MODE_ALWAYS
	add_child(_music)


func play(sfx_id: String) -> void:
	var path: String = str(PATHS.get(sfx_id, ""))
	if path.is_empty():
		return
	var stream: AudioStream = load(path) as AudioStream
	if stream == null:
		return
	last_id = sfx_id
	var voice: AudioStreamPlayer = _sfx_a
	if _sfx_a.playing:
		voice = _sfx_b
	voice.stream = stream
	voice.play()


func start_music() -> void:
	var stream: AudioStream = load(MUSIC_PATH) as AudioStream
	var wav: AudioStreamWAV = stream as AudioStreamWAV
	if wav != null:
		wav.loop_mode = AudioStreamWAV.LOOP_FORWARD
	_music.stream = stream
	_music.play()


func duck(active: bool) -> void:
	var idx: int = AudioServer.get_bus_index("Music")
	if idx < 0:
		return
	if active and not _ducked:
		_music_db_before_duck = AudioServer.get_bus_volume_db(idx)
		AudioServer.set_bus_volume_db(idx, _music_db_before_duck - 12.0)
		_ducked = true
	elif not active and _ducked:
		AudioServer.set_bus_volume_db(idx, _music_db_before_duck)
		_ducked = false


func is_music_playing() -> bool:
	if _music == null or _music.stream == null:
		return false
	return _music.playing or not _music.stream_paused


static func set_bus_linear(bus_name: String, linear: float) -> void:
	var idx: int = AudioServer.get_bus_index(bus_name)
	if idx < 0:
		return
	var clamped: float = clampf(linear, 0.0, 1.0)
	if clamped <= 0.0001:
		AudioServer.set_bus_volume_db(idx, -80.0)
		return
	AudioServer.set_bus_volume_db(idx, linear_to_db(clamped))
'''

SAVE_SERVICE = HEADER + r'''extends Node

const SAVE_PATH: String = "user://kho_bi_an_v1.cfg"
const TEST_PATH: String = "user://kho_bi_an_r8wp2_test.cfg"
const SCHEMA: int = 1

var _path: String = SAVE_PATH


func use_test_path() -> void:
	_path = TEST_PATH


func use_default_path() -> void:
	_path = SAVE_PATH


func current_path() -> String:
	return _path


func clear_slot() -> void:
	if FileAccess.file_exists(_path):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(_path))


func autosave(state: GameState) -> void:
	write_slot(state.to_dict())


func write_slot(data: Dictionary) -> void:
	var cfg: ConfigFile = ConfigFile.new()
	cfg.set_value("meta", "schema", int(data.get("schema", SCHEMA)))
	cfg.set_value("flags", "room_id", str(data.get("room_id", "start")))
	cfg.set_value("flags", "has_key", bool(data.get("has_key", false)))
	cfg.set_value("flags", "door_open", bool(data.get("door_open", false)))
	cfg.set_value("flags", "relic_reached", bool(data.get("relic_reached", false)))
	var err: Error = cfg.save(_path)
	if err != OK:
		push_error("SaveService write failed: %s" % str(err))


func load_slot() -> Dictionary:
	if not FileAccess.file_exists(_path):
		return {}
	var cfg: ConfigFile = ConfigFile.new()
	var err: Error = cfg.load(_path)
	if err != OK:
		return {}
	var schema: int = int(cfg.get_value("meta", "schema", 0))
	if schema != SCHEMA:
		return {}
	return {
		"schema": schema,
		"room_id": str(cfg.get_value("flags", "room_id", "start")),
		"has_key": bool(cfg.get_value("flags", "has_key", false)),
		"door_open": bool(cfg.get_value("flags", "door_open", false)),
		"relic_reached": bool(cfg.get_value("flags", "relic_reached", false)),
	}


func write_foreign_schema() -> void:
	var cfg: ConfigFile = ConfigFile.new()
	cfg.set_value("meta", "schema", 99)
	cfg.set_value("flags", "room_id", "door")
	cfg.set_value("flags", "has_key", true)
	var err: Error = cfg.save(_path)
	if err != OK:
		push_error("SaveService foreign write failed: %s" % str(err))
'''

UI_THEME = HEADER + r'''class_name UiTheme
extends RefCounted

const CREAM: Color = Color8(237, 228, 200)
const INDIGO: Color = Color8(18, 22, 42)
const INDIGO_PANEL: Color = Color(0.07, 0.09, 0.16, 0.86)
const BRASS: Color = Color8(196, 163, 74)
const BRASS_DARK: Color = Color8(140, 108, 40)
const TEAL: Color = Color8(61, 139, 122)
const RUST: Color = Color8(184, 58, 46)

static var _cached: Theme


static func shared() -> Theme:
	if _cached == null:
		_cached = make()
	return _cached


static func apply(control: Control) -> void:
	control.theme = shared()


static func contrast_ratio(a: Color, b: Color) -> float:
	var l1: float = _lum(a)
	var l2: float = _lum(b)
	var hi: float = maxf(l1, l2)
	var lo: float = minf(l1, l2)
	return (hi + 0.05) / (lo + 0.05)


static func readable() -> bool:
	return contrast_ratio(CREAM, INDIGO) >= 4.5


static func make() -> Theme:
	var theme: Theme = Theme.new()
	theme.set_color("font_color", "Label", CREAM)
	theme.set_color("font_shadow_color", "Label", Color(0, 0, 0, 0.55))
	theme.set_constant("shadow_offset_x", "Label", 1)
	theme.set_constant("shadow_offset_y", "Label", 1)
	theme.set_font_size("font_size", "Label", 20)
	theme.set_color("font_color", "Button", INDIGO)
	theme.set_color("font_hover_color", "Button", INDIGO)
	theme.set_color("font_focus_color", "Button", INDIGO)
	theme.set_color("font_pressed_color", "Button", CREAM)
	theme.set_color("font_disabled_color", "Button", Color(0.45, 0.42, 0.38))
	theme.set_font_size("font_size", "Button", 20)
	theme.set_color("font_color", "CheckButton", CREAM)
	theme.set_color("font_hover_color", "CheckButton", CREAM)
	theme.set_color("font_focus_color", "CheckButton", CREAM)
	theme.set_font_size("font_size", "CheckButton", 18)
	theme.set_color("font_color", "HSlider", CREAM)
	var btn: StyleBoxFlat = _box(BRASS, 0)
	theme.set_stylebox("normal", "Button", btn)
	var hover: StyleBoxFlat = _box(Color8(220, 190, 100), 0)
	theme.set_stylebox("hover", "Button", hover)
	var focus: StyleBoxFlat = _box(CREAM, 2)
	focus.border_color = BRASS
	theme.set_stylebox("focus", "Button", focus)
	var pressed: StyleBoxFlat = _box(BRASS_DARK, 0)
	theme.set_stylebox("pressed", "Button", pressed)
	var disabled: StyleBoxFlat = _box(Color8(72, 82, 128), 0)
	theme.set_stylebox("disabled", "Button", disabled)
	return theme


static func _box(color: Color, border: int) -> StyleBoxFlat:
	var box: StyleBoxFlat = StyleBoxFlat.new()
	box.bg_color = color
	box.set_corner_radius_all(4)
	box.content_margin_left = 12
	box.content_margin_right = 12
	box.content_margin_top = 8
	box.content_margin_bottom = 8
	if border > 0:
		box.set_border_width_all(border)
		box.border_color = BRASS
	return box


static func _lum(c: Color) -> float:
	return 0.2126 * _lin(c.r) + 0.7152 * _lin(c.g) + 0.0722 * _lin(c.b)


static func _lin(ch: float) -> float:
	if ch <= 0.04045:
		return ch / 12.92
	return pow((ch + 0.055) / 1.055, 2.4)
'''

TITLE_SCREEN = HEADER + r'''class_name TitleScreen
extends Control

signal play_pressed
signal continue_pressed
signal restart_pressed

var play_btn: Button
var continue_btn: Button
var restart_btn: Button


func _ready() -> void:
	name = "Title"
	set_anchors_preset(Control.PRESET_FULL_RECT)
	UiTheme.apply(self)
	var bg: ColorRect = ColorRect.new()
	bg.name = "Backdrop"
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = UiTheme.INDIGO
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	var title: Label = Label.new()
	title.name = "TitleLabel"
	title.text = "Kho Bí Ẩn"
	title.position = Vector2(80, 120)
	title.size = Vector2(720, 56)
	title.add_theme_font_size_override("font_size", 36)
	title.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(title)
	var sub: Label = Label.new()
	sub.name = "Subtitle"
	sub.text = "Relic-reached is win. Door-open is not win."
	sub.position = Vector2(80, 184)
	sub.size = Vector2(900, 32)
	sub.add_theme_color_override("font_color", UiTheme.BRASS)
	add_child(sub)
	var hint: Label = Label.new()
	hint.name = "InputHint"
	hint.text = "WASD / stick move · E / South interact · Esc / Start pause"
	hint.position = Vector2(80, 224)
	hint.size = Vector2(1000, 32)
	hint.add_theme_font_size_override("font_size", 18)
	hint.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(hint)
	play_btn = _make_btn("Play", Vector2(80, 300))
	continue_btn = _make_btn("Continue", Vector2(80, 360))
	restart_btn = _make_btn("Restart", Vector2(80, 420))
	play_btn.pressed.connect(_on_play)
	continue_btn.pressed.connect(_on_continue)
	restart_btn.pressed.connect(_on_restart)
	play_btn.focus_neighbor_bottom = continue_btn.get_path()
	play_btn.focus_neighbor_top = restart_btn.get_path()
	continue_btn.focus_neighbor_top = play_btn.get_path()
	continue_btn.focus_neighbor_bottom = restart_btn.get_path()
	restart_btn.focus_neighbor_top = continue_btn.get_path()
	restart_btn.focus_neighbor_bottom = play_btn.get_path()
	play_btn.grab_focus()


func set_continue_enabled(on: bool) -> void:
	continue_btn.disabled = not on


func _make_btn(text: String, at: Vector2) -> Button:
	var btn: Button = Button.new()
	btn.text = text
	btn.position = at
	btn.size = Vector2(240, 48)
	add_child(btn)
	return btn


func _on_play() -> void:
	play_pressed.emit()


func _on_continue() -> void:
	continue_pressed.emit()


func _on_restart() -> void:
	restart_pressed.emit()
'''

PAUSE_SCREEN = HEADER + r'''class_name PauseScreen
extends Control

signal resume_pressed

var resume_btn: Button
var master_slider: HSlider
var music_slider: HSlider
var sfx_slider: HSlider
var fullscreen_btn: CheckButton
var last_fullscreen: bool = false


func _ready() -> void:
	name = "Pause"
	process_mode = Node.PROCESS_MODE_WHEN_PAUSED
	set_anchors_preset(Control.PRESET_FULL_RECT)
	visible = false
	UiTheme.apply(self)
	var bg: ColorRect = ColorRect.new()
	bg.name = "Backdrop"
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = Color(0.07, 0.09, 0.16, 0.88)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	var label: Label = Label.new()
	label.name = "TitleLabel"
	label.text = "Paused"
	label.position = Vector2(80, 72)
	label.size = Vector2(400, 40)
	label.add_theme_font_size_override("font_size", 32)
	label.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(label)
	resume_btn = Button.new()
	resume_btn.name = "Resume"
	resume_btn.text = "Resume"
	resume_btn.position = Vector2(80, 140)
	resume_btn.size = Vector2(240, 48)
	resume_btn.pressed.connect(_on_resume)
	add_child(resume_btn)
	master_slider = _make_slider("Master", Vector2(80, 214), 1.0, _on_master)
	music_slider = _make_slider("Music", Vector2(80, 294), 1.0, _on_music)
	sfx_slider = _make_slider("SFX", Vector2(80, 374), 1.0, _on_sfx)
	fullscreen_btn = CheckButton.new()
	fullscreen_btn.name = "Fullscreen"
	fullscreen_btn.text = "Fullscreen"
	fullscreen_btn.position = Vector2(80, 454)
	fullscreen_btn.size = Vector2(280, 40)
	fullscreen_btn.focus_mode = Control.FOCUS_ALL
	fullscreen_btn.toggled.connect(set_fullscreen)
	add_child(fullscreen_btn)
	var hint: Label = Label.new()
	hint.name = "InputHint"
	hint.text = "WASD / stick move · E / South interact · Esc / Start pause"
	hint.position = Vector2(80, 520)
	hint.size = Vector2(1000, 32)
	hint.add_theme_font_size_override("font_size", 18)
	hint.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(hint)
	_wire_focus()


func show_pause() -> void:
	visible = true
	resume_btn.grab_focus()


func hide_pause() -> void:
	visible = false


func apply_bus_linear(bus_name: String, linear: float) -> void:
	if bus_name == "Master":
		master_slider.value = linear
	elif bus_name == "Music":
		music_slider.value = linear
	elif bus_name == "SFX":
		sfx_slider.value = linear
	SfxBank.set_bus_linear(bus_name, linear)


func set_fullscreen(on: bool) -> void:
	last_fullscreen = on
	if fullscreen_btn.button_pressed != on:
		fullscreen_btn.set_pressed_no_signal(on)
	if on:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
	else:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)


func _make_slider(bus_name: String, at: Vector2, initial: float, cb: Callable) -> HSlider:
	var caption: Label = Label.new()
	caption.text = "%s volume" % bus_name
	caption.position = at
	caption.size = Vector2(280, 28)
	caption.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(caption)
	var slider: HSlider = HSlider.new()
	slider.name = "%sVolume" % bus_name
	slider.position = Vector2(at.x, at.y + 28)
	slider.size = Vector2(360, 24)
	slider.min_value = 0.0
	slider.max_value = 1.0
	slider.step = 0.01
	slider.value = initial
	slider.focus_mode = Control.FOCUS_ALL
	slider.value_changed.connect(cb)
	add_child(slider)
	return slider


func _wire_focus() -> void:
	resume_btn.focus_neighbor_bottom = master_slider.get_path()
	resume_btn.focus_neighbor_top = fullscreen_btn.get_path()
	master_slider.focus_neighbor_top = resume_btn.get_path()
	master_slider.focus_neighbor_bottom = music_slider.get_path()
	music_slider.focus_neighbor_top = master_slider.get_path()
	music_slider.focus_neighbor_bottom = sfx_slider.get_path()
	sfx_slider.focus_neighbor_top = music_slider.get_path()
	sfx_slider.focus_neighbor_bottom = fullscreen_btn.get_path()
	fullscreen_btn.focus_neighbor_top = sfx_slider.get_path()
	fullscreen_btn.focus_neighbor_bottom = resume_btn.get_path()


func _on_resume() -> void:
	resume_pressed.emit()


func _on_master(value: float) -> void:
	SfxBank.set_bus_linear("Master", value)


func _on_music(value: float) -> void:
	SfxBank.set_bus_linear("Music", value)


func _on_sfx(value: float) -> void:
	SfxBank.set_bus_linear("SFX", value)
'''

WIN_SCREEN = HEADER + r'''class_name WinScreen
extends Control

signal restart_pressed

var restart_btn: Button


func _ready() -> void:
	name = "Win"
	set_anchors_preset(Control.PRESET_FULL_RECT)
	visible = false
	UiTheme.apply(self)
	var bg: ColorRect = ColorRect.new()
	bg.name = "Backdrop"
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = Color(0.07, 0.12, 0.14, 0.92)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	var label: Label = Label.new()
	label.name = "TitleLabel"
	label.text = "Relic reached"
	label.position = Vector2(80, 200)
	label.size = Vector2(640, 48)
	label.add_theme_font_size_override("font_size", 32)
	label.add_theme_color_override("font_color", UiTheme.TEAL)
	add_child(label)
	var sub: Label = Label.new()
	sub.name = "Subtitle"
	sub.text = "The vault opens. Relic-reached is the only win."
	sub.position = Vector2(80, 256)
	sub.size = Vector2(800, 32)
	sub.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(sub)
	restart_btn = Button.new()
	restart_btn.name = "Restart"
	restart_btn.text = "Restart"
	restart_btn.position = Vector2(80, 320)
	restart_btn.size = Vector2(240, 48)
	restart_btn.pressed.connect(_on_restart)
	add_child(restart_btn)


func show_win() -> void:
	visible = true
	restart_btn.grab_focus()


func _on_restart() -> void:
	restart_pressed.emit()
'''

LOSE_SCREEN = HEADER + r'''class_name LoseScreen
extends Control

signal restart_pressed

var restart_btn: Button


func _ready() -> void:
	name = "Lose"
	set_anchors_preset(Control.PRESET_FULL_RECT)
	visible = false
	UiTheme.apply(self)
	var bg: ColorRect = ColorRect.new()
	bg.name = "Backdrop"
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = Color(0.16, 0.07, 0.08, 0.92)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	var label: Label = Label.new()
	label.name = "TitleLabel"
	label.text = "Warden contact"
	label.position = Vector2(80, 200)
	label.size = Vector2(640, 48)
	label.add_theme_font_size_override("font_size", 32)
	label.add_theme_color_override("font_color", UiTheme.RUST)
	add_child(label)
	var sub: Label = Label.new()
	sub.name = "Subtitle"
	sub.text = "The warden found you. Restart to try again."
	sub.position = Vector2(80, 256)
	sub.size = Vector2(800, 32)
	sub.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(sub)
	restart_btn = Button.new()
	restart_btn.name = "Restart"
	restart_btn.text = "Restart"
	restart_btn.position = Vector2(80, 320)
	restart_btn.size = Vector2(240, 48)
	restart_btn.pressed.connect(_on_restart)
	add_child(restart_btn)


func show_lose() -> void:
	visible = true
	restart_btn.grab_focus()


func _on_restart() -> void:
	restart_pressed.emit()
'''

RUN_ALL = HEADER + r'''extends SceneTree

const STEP: float = 1.0 / 60.0
const ARRIVE: float = 8.0
const PATH: String = "start→key→door→relic→win"

var _fails: PackedStringArray = PackedStringArray()
var _loop: String = "unproven"
var _save: String = "unproven"
var _win_flag: String = "unproven"
var _no_err: String = "unproven"


func _initialize() -> void:
	call_deferred("_boot")


func _boot() -> void:
	seed(1)
	InputActions.install()
	var saver: Node = root.get_node_or_null("SaveService")
	if saver != null:
		saver.call("use_test_path")
		saver.call("clear_slot")
	var app: App = _make_app()
	_test_input_binds()
	_test_critical_path(app)
	_test_save_load(app)
	_test_win_flag_exclusive(app)
	_test_warden_lose_restart(app)
	_test_continue_after_relic(app)
	_test_foreign_schema(app)
	if saver != null:
		saver.call("clear_slot")
		saver.call("use_default_path")
	if _fails.is_empty():
		_no_err = "proven"
	_emit()
	quit(0 if _fails.is_empty() else 1)


func _make_app() -> App:
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	var app: App = packed.instantiate() as App
	app.test_driven = true
	root.add_child(app)
	return app


func _test_input_binds() -> void:
	var actions: PackedStringArray = PackedStringArray([
		"move_left", "move_right", "move_up", "move_down", "interact", "pause"
	])
	var i: int = 0
	while i < actions.size():
		var action: String = String(actions[i])
		if not InputMap.has_action(action):
			_fail("missing InputMap action %s" % action)
		elif not InputActions.has_keyboard_and_gamepad(action):
			_fail("action %s missing keyboard+gamepad" % action)
		i += 1
	var buses: PackedStringArray = PackedStringArray(["Master", "Music", "SFX"])
	var b: int = 0
	while b < buses.size():
		if AudioServer.get_bus_index(String(buses[b])) < 0:
			_fail("missing audio bus %s" % String(buses[b]))
		b += 1


func _test_critical_path(app: App) -> void:
	app.start_new_run()
	var session: GameSession = app.session
	if session == null:
		_fail("LOOP missing session")
		return
	var layer: TileMapLayer = session.world.get_node_or_null("VaultRooms") as TileMapLayer
	if layer == null:
		_fail("LOOP overworld missing TileMapLayer VaultRooms")
	elif layer.tile_set == null:
		_fail("LOOP VaultRooms missing TileSet")
	else:
		var atlas_src: TileSetSource = layer.tile_set.get_source(0)
		var atlas: TileSetAtlasSource = atlas_src as TileSetAtlasSource
		if atlas == null or atlas.texture == null:
			_fail("LOOP VaultRooms missing atlas texture")
		elif atlas.texture.resource_path != "res://assets/tiles/tileset_vault.png":
			_fail("LOOP live TileMapLayer must use tileset_vault.png")
	if VaultMap.room_id_at(VaultMap.tile_center(VaultMap.DOOR_CELL)) == "relic":
		_fail("LOOP door tile must not be room_id relic")
	if VaultMap.room_id_at(VaultMap.tile_center(VaultMap.RELIC_CELL)) != "relic":
		_fail("LOOP relic cell must be room_id relic")
	var snap0: Dictionary = session.snapshot()
	if bool(snap0.get("win", false)) or bool(snap0.get("has_key", false)):
		_fail("LOOP start is not a clean run")
	if str(snap0.get("room_id", "")) != "start":
		_fail("LOOP start room_id must be start")
	_fail_close_relic_before_key(session)
	if not _walk_to(session, VaultMap.tile_center(VaultMap.KEY_CELL)):
		_fail(
			"LOOP cannot reach key at %s from %s"
			% [VaultMap.tile_center(VaultMap.KEY_CELL), session.player.global_position]
		)
		return
	_interact(session)
	var after_key: Dictionary = session.snapshot()
	if not bool(after_key.get("has_key", false)):
		_fail("LOOP key pickup failed kind=%s pos=%s" % [_debug_near(session), session.player.global_position])
	if bool(after_key.get("win", false)) or session.state.outcome == "win":
		_fail("LOOP key pickup must not win")
	if not _walk_to(session, VaultMap.tile_center(VaultMap.DOOR_CELL)):
		_fail("LOOP cannot reach door")
		return
	_interact(session)
	var after_door: Dictionary = session.snapshot()
	if not bool(after_door.get("door_open", false)):
		_fail("LOOP door open failed")
	if bool(after_door.get("win", false)) or session.state.outcome == "win":
		_fail("LOOP door-open must not win")
	if VaultMap.is_relic_room(str(after_door.get("room_id", ""))):
		_fail("LOOP door-open must stay start-side, not relic room")
	if not _walk_to(session, VaultMap.tile_center(VaultMap.RELIC_CELL)):
		_fail("LOOP cannot reach relic")
		return
	_interact(session)
	var after_relic: Dictionary = session.snapshot()
	if not bool(after_relic.get("relic_reached", false)):
		_fail("LOOP relic-reached flag missing")
	if not bool(after_relic.get("win", false)):
		_fail("LOOP relic-reached must be win")
	if session.state.outcome != "win":
		_fail("LOOP outcome is not win")
	if not VaultMap.is_relic_room(str(after_relic.get("room_id", ""))):
		_fail("LOOP win must be in relic room")
	if not app.win_screen.visible:
		_fail("LOOP win screen not shown")
	if _count_prefix("LOOP ") == 0:
		_loop = "proven"


func _fail_close_relic_before_key(session: GameSession) -> void:
	var reached: bool = _walk_to(session, VaultMap.tile_center(VaultMap.RELIC_CELL))
	var snap: Dictionary = session.snapshot()
	if reached or VaultMap.is_relic_room(str(snap.get("room_id", ""))):
		_fail("LOOP reached relic with door closed")
	if bool(snap.get("relic_reached", false)) or bool(snap.get("win", false)):
		_fail("LOOP relic approach with door closed must not win")
	_interact(session)
	var after: Dictionary = session.snapshot()
	if bool(after.get("relic_reached", false)) or bool(after.get("win", false)):
		_fail("LOOP interact at closed door must not set relic_reached")
	if bool(after.get("has_key", false)) or bool(after.get("door_open", false)):
		_fail("LOOP fail-close must not grant key or door")


func _test_save_load(app: App) -> void:
	var saver: Node = root.get_node_or_null("SaveService")
	if saver == null:
		_fail("SAVE_LOAD missing SaveService")
		return
	app.start_new_run()
	var session: GameSession = app.session
	if not _walk_to(session, VaultMap.tile_center(VaultMap.KEY_CELL)):
		_fail("SAVE_LOAD cannot reach key")
		return
	_interact(session)
	if not _walk_to(session, VaultMap.tile_center(VaultMap.DOOR_CELL)):
		_fail("SAVE_LOAD cannot reach door")
		return
	_interact(session)
	if not bool(session.snapshot().get("door_open", false)):
		_fail("SAVE_LOAD door open failed")
		return
	if not _walk_to(session, VaultMap.tile_center(Vector2i(VaultMap.DOOR_CELL.x, VaultMap.PLAYER_SPAWN.y))):
		_fail("SAVE_LOAD cannot step south of door")
		return
	if not _walk_to(session, VaultMap.tile_center(VaultMap.PLAYER_SPAWN)):
		_fail("SAVE_LOAD cannot return to start-side room")
		return
	if str(session.snapshot().get("room_id", "")) != "start":
		_fail("SAVE_LOAD persist room_id must be start, got %s" % str(session.snapshot().get("room_id", "")))
	saver.call("autosave", session.state)
	var written: Dictionary = saver.call("load_slot") as Dictionary
	if not bool(written.get("has_key", false)) or not bool(written.get("door_open", false)):
		_fail("SAVE_LOAD did not persist key/door")
	if bool(written.get("relic_reached", false)):
		_fail("SAVE_LOAD door-open must not persist win")
	if str(written.get("room_id", "")) != "start":
		_fail("SAVE_LOAD persisted room_id must be start")
	app.continue_run()
	var restored: Dictionary = app.session.snapshot()
	if not bool(restored.get("has_key", false)) or not bool(restored.get("door_open", false)):
		_fail("SAVE_LOAD continue did not restore flags")
	if bool(restored.get("win", false)) or bool(restored.get("relic_reached", false)):
		_fail("SAVE_LOAD restored unfinished run must not be win")
	if str(restored.get("room_id", "")) != "start":
		_fail("SAVE_LOAD continue room_id must be start, got %s" % str(restored.get("room_id", "")))
	if VaultMap.is_relic_room(str(restored.get("room_id", ""))):
		_fail("SAVE_LOAD must not teleport into relic after door-open-in-start")
	if VaultMap.room_id_at(app.session.player.global_position) == "relic":
		_fail("SAVE_LOAD player must not spawn in relic room")
	if not _walk_to(app.session, VaultMap.tile_center(VaultMap.RELIC_CELL)):
		_fail("SAVE_LOAD cannot finish path to relic after load")
		return
	_interact(app.session)
	var finished: Dictionary = app.session.snapshot()
	if not bool(finished.get("has_key", false)) or not bool(finished.get("door_open", false)):
		_fail("SAVE_LOAD finish lost key/door flags")
	if not bool(finished.get("relic_reached", false)) or not bool(finished.get("win", false)):
		_fail("SAVE_LOAD must walk to relic and win after load")
	if not VaultMap.is_relic_room(str(finished.get("room_id", ""))):
		_fail("SAVE_LOAD win room_id must be relic")
	if app.session.state.outcome != "win":
		_fail("SAVE_LOAD finish outcome is not win")
	if _count_prefix("SAVE_LOAD ") == 0:
		_save = "proven"


func _test_win_flag_exclusive(app: App) -> void:
	app.start_new_run()
	var session: GameSession = app.session
	session.state.has_key = true
	session.inventory.add("key")
	session.state.door_open = true
	if session.state.is_win() or session.state.relic_reached or session.state.outcome == "win":
		_fail("WIN_FLAG key+door without relic interact must not be win")
	if app.win_screen.visible:
		_fail("WIN_FLAG key+door must not show win screen")
	session.state.door_open = false
	session.player.global_position = VaultMap.tile_center(VaultMap.RELIC_CELL)
	_interact(session)
	if session.state.relic_reached or session.state.is_win() or session.state.outcome == "win":
		_fail("WIN_FLAG relic interact with door closed must not win")
	if app.win_screen.visible:
		_fail("WIN_FLAG closed-door relic interact must not show win screen")
	session.state.door_open = true
	session.state.has_key = true
	session.player.global_position = VaultMap.tile_center(VaultMap.RELIC_CELL)
	_interact(session)
	if not session.state.relic_reached or not session.state.is_win():
		_fail("WIN_FLAG relic interact after door_open must win")
	if session.state.outcome != "win":
		_fail("WIN_FLAG outcome must be win after relic interact")
	if not app.win_screen.visible:
		_fail("WIN_FLAG win screen not shown after relic interact")
	if _count_prefix("WIN_FLAG ") == 0:
		_win_flag = "proven"


func _test_warden_lose_restart(app: App) -> void:
	app.start_new_run()
	var session: GameSession = app.session
	if VaultMap.WARDEN_A.y < VaultMap.OPENING_Y0 or VaultMap.WARDEN_B.y < VaultMap.OPENING_Y0:
		_fail("warden patrol must be on the vault floor, not off-path")
	if not _chase_warden(session):
		_fail("lose path cannot reach warden")
		return
	if session.state.outcome != "lose":
		_fail("warden contact must be lose")
	if session.state.is_win():
		_fail("lose must not set win")
	if not app.lose_screen.visible:
		_fail("lose screen not shown")
	app.start_new_run()
	var fresh: Dictionary = app.session.snapshot()
	if bool(fresh.get("has_key", false)) or fresh["outcome"] != "play":
		_fail("Restart did not start a new run")


func _test_continue_after_relic(app: App) -> void:
	var saver: Node = root.get_node_or_null("SaveService")
	if saver == null:
		return
	var data: Dictionary = {
		"schema": 1,
		"room_id": "relic",
		"has_key": true,
		"door_open": true,
		"relic_reached": true,
	}
	saver.call("write_slot", data)
	app.continue_run()
	var snap: Dictionary = app.session.snapshot()
	if bool(snap.get("relic_reached", false)) or bool(snap.get("has_key", false)):
		_fail("Continue after relic must start a new run")


func _test_foreign_schema(app: App) -> void:
	var saver: Node = root.get_node_or_null("SaveService")
	if saver == null:
		return
	saver.call("write_foreign_schema")
	var loaded: Dictionary = saver.call("load_slot") as Dictionary
	if not loaded.is_empty():
		_fail("foreign schema must start new (empty load)")
	app.continue_run()
	var snap: Dictionary = app.session.snapshot()
	if bool(snap.get("has_key", false)):
		_fail("foreign schema continue must be a new run")


func _debug_near(session: GameSession) -> String:
	var key: Node2D = session.world.get_node_or_null("Key") as Node2D
	if key == null:
		return "no-key-node"
	return "key_dist=%.1f visible=%s" % [
		session.player.global_position.distance_to(key.global_position),
		key.visible
	]


func _interact(session: GameSession) -> void:
	var i: int = 0
	while i < 4:
		session.step_fixed(STEP, Vector2.ZERO, true)
		i += 1


func _chase_warden(session: GameSession) -> bool:
	var frames: int = 0
	while frames < 900:
		if session.state.outcome == "lose":
			return true
		var target: Vector2 = session.warden.global_position
		if session.player.global_position.distance_to(target) <= VaultMap.WARDEN_TOUCH:
			session.step_fixed(STEP, Vector2.ZERO, false)
			return session.state.outcome == "lose"
		session.step_fixed(STEP, target - session.player.global_position, false)
		frames += 1
	return session.state.outcome == "lose"


func _walk_to(session: GameSession, target: Vector2) -> bool:
	var frames: int = 0
	while frames < 720:
		var here: Vector2 = session.player.global_position
		if here.distance_to(target) <= ARRIVE:
			return true
		var delta: Vector2 = target - here
		session.step_fixed(STEP, delta, false)
		if session.player.global_position.distance_to(here) < 0.05 and frames > 8:
			return here.distance_to(target) <= VaultMap.INTERACT_REACH
		frames += 1
	return session.player.global_position.distance_to(target) <= VaultMap.INTERACT_REACH


func _fail(msg: String) -> void:
	_fails.append(msg)
	print("HH_ASSERT_FAIL %s" % msg)


func _count_prefix(prefix: String) -> int:
	var n: int = 0
	var i: int = 0
	while i < _fails.size():
		if String(_fails[i]).begins_with(prefix):
			n += 1
		i += 1
	return n


func _emit() -> void:
	print("HH_R8WP2_PATH %s" % PATH)
	print("HH_R8WP2_PATH_ASCII start->key->door->relic->win")
	print(
		"HH_R8WP2 LOOP=%s SAVE_LOAD=%s NO_ERRORS=%s WIN_FLAG=%s"
		% [_loop, _save, _no_err, _win_flag]
	)
	if _fails.is_empty():
		print("PASS: R8-WP2 graybox start→key→door→relic→win")
	else:
		print("FAIL: R8-WP2 graybox")
		var i: int = 0
		while i < _fails.size():
			print("  - %s" % String(_fails[i]))
			i += 1
'''

README = """# Kho Bí Ẩn — human review build

Generated from PROJECT_BRIEF.md + ASSET_MANIFEST pins.
This is not a copy of a prior dogfood tree.

This is the R8 dogfood vertical slice. Relic-reached is win.
Door-open is not win. Key pickup is not win.

This file does **not** claim a person finished the 10-minute
review. G5 stays unsigned until that person accepts the game.
Do not treat editor Play, windowed Godot, or the review exe
as Gate G5. The game is not accepted.

## How to play (about 10 minutes)

1. Launch the review Windows build if you have it, or open this
   Godot 4.7.1-stable project and press Play. Mouse is not
   required.
2. Title: Start a new run, or Continue an unfinished save.
3. Move 4-dir. Pick up the key. Open the door. Reach the relic
   and interact. That is the only win.
4. Pause with Escape or Start. Resume from Pause. Win and Lose
   both offer Restart (always a new run).
5. Stay in the vault for about 10 minutes: move, pause, restart,
   try the warden, try Continue. Score the rubric. Do not open
   the editor to patch the game for the agent.

## Controls

- Keyboard: WASD or arrows move, E or Enter interact, Escape pause
- Gamepad: left stick or d-pad move, South/A interact, Start pause

## What to review

Use `REVIEW_RUBRIC.md`. Known residuals are in `KNOWN_ISSUES.md`.
If quality fails, go back to the named WP. Do not open R9 because
a scripted path is green.

## What this is not

- Not a G5 signature
- Not an accepted game
- Not a clean-VM release (that is R9)
- Not an API-key / `--provider` LLM run (`--provider plan` stays)
"""

RUBRIC = """# Review rubric — Kho Bí Ẩn (R8-WP6 / G5)

Human only. Leave every sign-off blank until a person plays.
This file is not a G5 tick. Windowed Godot and agent soaks are
plan §7.3, not this rubric.

Relic-reached is win. Door-open is not win. Key pickup is not win.

| Area | Accept when | Fail / send back | Sign |
|------|-------------|------------------|------|
| gameplay | 4-dir move, interact, key, door, relic-reached win, warden lose, Restart new run, Continue restores an unfinished v1 slot | Softlock, wrong win flag, cannot finish start→key→door→relic→win without the editor | |
| visual | Sprites/tiles read at 1280x720; not a color-rect-only release; no PLACEHOLDER ship art | Solid-color stand-ins only, cutoff HUD, unreadable key/door/relic | |
| audio | Master / Music / SFX; pickup, door, caught, win, lose, interact make sound | Silent key / door / caught on the critical path | |
| UX | Title, Pause, Resume, Win, Lose, Restart without a mouse; one-line hint; keyboard+gamepad | Must use the mouse on the critical path; focus trap; unreadable text | |
| stability | About 10 minutes continuous play; no blocker, no save loss | Crash, blocker, wiped slot, cannot Restart | |
| autonomy | Person only watches / reviews. No owner clicks to author the game | Reviewer had to edit scenes, scripts, or assets to make the loop work | |
| evidence | Recreate hashes, pin 4.7.1-stable, critic notes, review build, known issues | Missing hashes, invented API key, claimed G5 without play | |

If a row fails, return to the WP that owns it. Do not open R9
because unit/E2E boxes are green.

- gameplay loop → R8-WP2
- art / animation / audio / license pin → R8-WP3
- HUD / pause / buses / polish → R8-WP4
- soak / save / stuck / seeded bash → R8-WP5
- fresh recreate / hashes / review export package → R8-WP6
"""

KNOWN_ISSUES = """# Known issues — Kho Bí Ẩn (not G5)

Recorded from R8-WP5 playtest evidence and residual honesty.
These are not a G5 accept. If a human review fails quality,
go back to the named WP. Do not open R9 on green checkboxes.

## P2 (playtest)

1. Divider walls at columns 13 and 26 stop a held east-west.
   Openings are only at y=6–8. Happy path uses those openings.
   Owner WP: R8-WP2 map / R8-WP5 bash.
2. Warden north-lane in the door room makes random wander die
   often. The y=8 happy path stays safe. Owner WP: R8-WP5.
3. Official soak p95 was about 21.80 ms vs the 16.67 ms 60 fps
   budget. PERF stayed unproven. Owner WP: R8-WP5.

## Honesty leftovers (do not treat as G5)

- Save schema v1 does not persist player position. Continue
  respawns at the room spawn.
- No drop-item action. “Bỏ item” is skip-pickup only.
- Dual-path test input (`parse_input_event` + `action_press`)
  is agent verify, not a player-facing control.
- ColorRect Body nodes stay as invisible colliders; sprites
  are children. That is legal polish, not a color-rect release.
- Windows review export is a dogfood review build. Clean-VM
  ship without editor/Node/addon/token is R9 after G5.

## Win flag

Relic-reached is the only win. Do not poke `relic_reached`.
"""

NOTICE = """# NOTICE — Kho Bí Ẩn

Generated from PROJECT_BRIEF.md + ASSET_MANIFEST pins.
Original procedural art and audio. No third-party sprites or
sound packs are shipped. No remote imagegen.
Live tiles use `res://assets/tiles/tileset_vault.png`. ColorRect
Body nodes stay as invisible colliders; sprites are children.
Relic-reached is the only win. G5 is not claimed.
This package is not a human dogfood signature. The game is
not accepted.

- Game code: generated by `tools/godot/recreate_kho_bi_an.py`
- Tiles, actors, items, door, VFX, UI icon, SFX, music: original
  procedural, pinned in `assets/ASSET_MANIFEST.json`
- Godot 4.7.1-stable: MIT
- Bundled default project font (Open Sans SemiBold): SIL Open Font License 1.1
"""


def text_files(brief: dict) -> dict[str, str]:
    view_w = int(brief["view_w"])
    view_h = int(brief["view_h"])
    stretch_mode = str(brief["stretch_mode"])
    stretch_aspect = str(brief["stretch_aspect"])
    return {
        "project.godot": project_godot(view_w, view_h, stretch_mode, stretch_aspect),
        "default_bus_layout.tres": BUS_LAYOUT,
        "export_presets.cfg": EXPORT_PRESETS,
        "scenes/main.tscn": MAIN_TSCN,
        "src/game_state.gd": GAME_STATE,
        "src/vault_map.gd": VAULT_MAP,
        "src/input_actions.gd": INPUT_ACTIONS,
        "src/inventory.gd": INVENTORY,
        "src/visuals.gd": VISUALS,
        "src/player.gd": PLAYER,
        "src/warden.gd": WARDEN,
        "src/world_builder.gd": WORLD_BUILDER,
        "src/game_session.gd": GAME_SESSION,
        "src/app.gd": APP,
        "src/hud.gd": HUD,
        "src/sfx_bank.gd": SFX_BANK,
        "src/ui/ui_theme.gd": UI_THEME,
        "src/ui/title_screen.gd": TITLE_SCREEN,
        "src/ui/pause_screen.gd": PAUSE_SCREEN,
        "src/ui/win_screen.gd": WIN_SCREEN,
        "src/ui/lose_screen.gd": LOSE_SCREEN,
        "autoload/save_service.gd": SAVE_SERVICE,
        "tests/run_all.gd": RUN_ALL,
        "README.md": README,
        "REVIEW_RUBRIC.md": RUBRIC,
        "KNOWN_ISSUES.md": KNOWN_ISSUES,
        "NOTICE.md": NOTICE,
    }
