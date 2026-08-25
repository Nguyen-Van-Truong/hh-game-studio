class_name Visuals
extends RefCounted

const PLAYER_FRAMES: String = "res://assets/anim/actor_player.tres"
const WARDEN_FRAMES: String = "res://assets/anim/actor_warden.tres"
const VFX_FRAMES: String = "res://assets/anim/vfx_interact.tres"
const KEY_TEX: String = "res://assets/art/item_key.png"
const DOOR_TEX: String = "res://assets/art/prop_door.png"
const RELIC_TEX: String = "res://assets/art/item_relic.png"
const KEY_ICON: String = "res://assets/ui/ui_icon_key.png"
const TILESET: String = "res://assets/tiles/tileset_vault.png"


static func hide_body(host: Node) -> void:
	var body: ColorRect = host.get_node_or_null("Body") as ColorRect
	if body == null:
		return
	body.visible = false
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var faded: Color = body.color
	faded.a = 0.0
	body.color = faded


static func attach_actor(host: Node2D, frames_path: String) -> AnimatedSprite2D:
	hide_body(host)
	var existing: AnimatedSprite2D = host.get_node_or_null("Sprite") as AnimatedSprite2D
	if existing != null:
		return existing
	var sprite: AnimatedSprite2D = AnimatedSprite2D.new()
	sprite.name = "Sprite"
	sprite.centered = true
	sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	sprite.sprite_frames = load(frames_path) as SpriteFrames
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
