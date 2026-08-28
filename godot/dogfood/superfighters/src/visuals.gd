class_name Visuals
extends RefCounted

const TILESET: String = "res://assets/tiles/tileset_arena.png"
const LADDER: String = "res://assets/tiles/tile_ladder.png"
const BG_CITY: String = "res://assets/bg/bg_city.png"
const MUZZLE: String = "res://assets/vfx/vfx_muzzle.png"
const BLOOD: String = "res://assets/vfx/vfx_blood.png"
const FRAME: int = 32
const SHEET: Dictionary = {
	"idle": [Vector2i(0, 0), Vector2i(1, 0)],
	"walk": [Vector2i(2, 0), Vector2i(3, 0), Vector2i(4, 0), Vector2i(5, 0)],
	"jump": [Vector2i(6, 0)],
	"fall": [Vector2i(7, 0)],
	"crouch": [Vector2i(0, 1)],
	"melee": [Vector2i(1, 1), Vector2i(2, 1)],
	"aim_side": [Vector2i(3, 1)],
	"aim_up": [Vector2i(4, 1)],
	"aim_down": [Vector2i(5, 1)],
	"dead": [Vector2i(6, 1)],
	"throw": [Vector2i(7, 1)],
}


static func actor_path(team: int) -> String:
	if team == 1:
		return "res://assets/art/actor_red.png"
	if team == 2:
		return "res://assets/art/actor_gold.png"
	if team == 3:
		return "res://assets/art/actor_teal.png"
	return "res://assets/art/actor_blue.png"


static func hide_body(host: Node) -> void:
	var body: ColorRect = host.get_node_or_null("Body") as ColorRect
	if body == null:
		return
	body.visible = false
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var faded: Color = body.color
	faded.a = 0.0
	body.color = faded


static func attach_actor(host: Node2D, team: int) -> AnimatedSprite2D:
	hide_body(host)
	var existing: AnimatedSprite2D = host.get_node_or_null("Sprite") as AnimatedSprite2D
	if existing != null:
		return existing
	var sprite: AnimatedSprite2D = AnimatedSprite2D.new()
	sprite.name = "Sprite"
	sprite.centered = true
	sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	sprite.sprite_frames = make_frames(team)
	sprite.position = Vector2(0.0, -2.0)
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


static func make_frames(team: int) -> SpriteFrames:
	var frames: SpriteFrames = SpriteFrames.new()
	var tex: Texture2D = load(actor_path(team)) as Texture2D
	var keys: PackedStringArray = PackedStringArray([
		"idle", "walk", "jump", "fall", "crouch", "melee",
		"aim_side", "aim_up", "aim_down", "dead", "throw"
	])
	var k: int = 0
	while k < keys.size():
		var key: String = String(keys[k])
		if frames.has_animation(key):
			frames.clear(key)
		else:
			frames.add_animation(key)
		frames.set_animation_loop(key, key == "idle" or key == "walk")
		frames.set_animation_speed(key, 8.0 if key == "walk" else 10.0)
		var cells: Array = SHEET[key] as Array
		var i: int = 0
		while i < cells.size():
			var cell: Vector2i = cells[i] as Vector2i
			var atlas: AtlasTexture = AtlasTexture.new()
			atlas.atlas = tex
			atlas.region = Rect2(
				float(cell.x * FRAME),
				float(cell.y * FRAME),
				float(FRAME),
				float(FRAME)
			)
			frames.add_frame(key, atlas)
			i += 1
		k += 1
	return frames


static func play_fighter(sprite: AnimatedSprite2D, clip: String) -> void:
	if sprite == null or sprite.sprite_frames == null:
		return
	if not sprite.sprite_frames.has_animation(clip):
		clip = "idle"
	if sprite.animation != clip:
		sprite.play(clip)
	elif not sprite.is_playing():
		sprite.play(clip)
