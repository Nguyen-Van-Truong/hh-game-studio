class_name ChibiWeaponView
extends Node2D
## Authentic source gun pixels with articulated Chibi hands. Child of AimPivot:
## its parent owns aim and Rig owns facing. No gameplay or socket mutation.

const WEAPONS: Dictionary = {
	"PISTOL": {"asset": "pistol", "muzzle": Vector2(5.5, 1.5), "grip": Vector2(1.5, 3.0), "scale": 1.15},
	"HANDGUN": {"asset": "pistol", "muzzle": Vector2(5.5, 1.5), "grip": Vector2(1.5, 3.0), "scale": 1.15},
	"MAGNUM": {"asset": "magnum", "muzzle": Vector2(8.5, 1.5), "grip": Vector2(1.5, 3.0), "scale": 1.15},
	"UZI": {"asset": "uzi", "muzzle": Vector2(8.5, 2.0), "grip": Vector2(3.5, 5.0), "scale": 1.0},
	"RIFLE": {"asset": "rifle", "muzzle": Vector2(21.5, 2.0), "grip": Vector2(7.0, 4.0), "support": Vector2(15.0, 3.5), "scale": 1.0},
	"SHOTGUN": {"asset": "shotgun", "muzzle": Vector2(18.5, 1.0), "grip": Vector2(6.0, 3.0), "support": Vector2(13.0, 2.5), "scale": 1.0},
	"SNIPER": {"asset": "sniper", "muzzle": Vector2(24.5, 4.0), "grip": Vector2(8.0, 6.0), "support": Vector2(17.0, 5.0), "scale": 1.0},
	"BAZOOKA": {"asset": "bazooka", "muzzle": Vector2(22.5, 4.0), "grip": Vector2(11.5, 7.0), "support": Vector2(16.0, 6.5), "scale": 1.0},
	"FLAMETHROWER": {"asset": "flamethrower", "muzzle": Vector2(16.5, 4.5), "grip": Vector2(2.0, 6.0), "support": Vector2(10.5, 7.0), "scale": 1.0},
	"THROW": {"asset": "grenade_thrown", "muzzle": Vector2(2.0, 2.0), "grip": Vector2(2.0, 2.0), "scale": 1.0, "anchor_kind": "grip", "render_kind": "source_prop"},
	"GRENADE": {"asset": "grenade_thrown", "muzzle": Vector2(2.0, 2.0), "grip": Vector2(2.0, 2.0), "scale": 1.0, "anchor_kind": "grip", "render_kind": "source_prop"},
	"MOLOTOV": {"asset": "molotov_thrown", "muzzle": Vector2(2.5, 6.5), "grip": Vector2(2.5, 6.5), "scale": 1.0, "anchor_kind": "grip", "render_kind": "source_prop"},
	"SELF": {"asset": "pills", "muzzle": Vector2(2.5, 4.0), "grip": Vector2(2.5, 4.0), "scale": 1.0, "anchor_kind": "grip", "render_kind": "source_prop"},
	"CHAINSAW": {"asset": "", "muzzle": Vector2(18.0, 3.0), "grip": Vector2(4.0, 6.0), "support": Vector2(9.0, 6.0), "scale": 1.0, "anchor_kind": "blade_tip", "render_kind": "procedural_melee"},
}
const DARK: Color = Color(0.06, 0.07, 0.11)
const LimbRenderer = preload("res://game/fighter/chibi_limb_renderer.gd")

var _textures: Dictionary = {}
var _spec: Dictionary = {}
var _muzzle: Vector2 = Vector2.ZERO
var _frame: int = 1
var _style: Dictionary = {}
var weapon_texture: Texture2D = null


static func _weapon_key(state_name: String) -> String:
	var state: String = state_name.to_upper().left(96)
	if state.begins_with("AIM_"):
		return state.trim_prefix("AIM_")
	if state.begins_with("START_"):
		return state.trim_prefix("START_")
	return ""


static func has_weapon(state_name: String) -> bool:
	return WEAPONS.has(_weapon_key(state_name))


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	position = Vector2.ZERO
	prewarm()


func prewarm() -> void:
	# One load per source gun outside draw; aliases share the same cached texture.
	for spec_var: Variant in WEAPONS.values():
		var spec: Dictionary = spec_var as Dictionary
		var asset: String = str(spec["asset"])
		if asset.is_empty():
			continue
		if not _textures.has(asset):
			var path: String = "res://assets/sprites/weapons/wpn_" + asset + ".png"
			_textures[asset] = ResourceLoader.load(path) as Texture2D


func configure(state_name: String, weapon_frame: int, muzzle_local: Vector2, character_style: Dictionary = {}) -> void:
	var key: String = _weapon_key(state_name)
	_spec = WEAPONS.get(key, {}) as Dictionary
	_frame = clampi(weapon_frame, 1, 64)
	_muzzle = muzzle_local if muzzle_local.is_finite() else Vector2.ZERO
	_style = character_style
	weapon_texture = _textures.get(str(_spec.get("asset", ""))) as Texture2D
	position = Vector2.ZERO
	rotation = 0.0
	scale = Vector2.ONE
	visible = not _spec.is_empty()
	queue_redraw()


func get_visual_muzzle_local() -> Vector2:
	return get_draw_contract().get("visual_muzzle", Vector2.ZERO) as Vector2


func _weapon_transform() -> Transform2D:
	var recoil: Vector2 = _style.get("visual_recoil", Vector2.ZERO) as Vector2
	if str(_spec.get("render_kind", "source_firearm")) != "source_firearm":
		recoil = Vector2.ZERO
	var amount: float = recoil.length() if recoil.is_finite() else 0.0
	var angle: float = clampf(recoil.x * 0.035, -0.12, 0.12) if recoil.is_finite() else 0.0
	var factor: float = float(_spec.get("scale", 1.0)) * (1.0 - minf(0.04, amount * 0.012))
	return Transform2D(angle, Vector2(factor, factor), 0.0, _muzzle)


func _source_point(point: Vector2) -> Vector2:
	return _weapon_transform() * (point - (_spec["muzzle"] as Vector2))


func get_draw_contract() -> Dictionary:
	if _spec.is_empty():
		return {"supported": false, "render_kind": "none", "visual_muzzle": Vector2.ZERO}
	var pixel_scale: float = float(_spec["scale"])
	var source_anchor: Vector2 = _spec["muzzle"]
	var top_left: Vector2 = _muzzle - source_anchor * pixel_scale
	var asset: String = str(_spec["asset"])
	var transform: Transform2D = _weapon_transform()
	var support_source: Vector2 = _spec.get("support", _spec["grip"]) as Vector2
	if asset == "shotgun" and _frame >= 3:
		support_source.x -= 2.0
	return {
		"supported": true,
		"render_kind": str(_spec.get("render_kind", "source_firearm")),
		"anchor_kind": str(_spec.get("anchor_kind", "muzzle_texel_center")),
		"asset": "res://assets/sprites/weapons/wpn_" + asset + ".png" if not asset.is_empty() else "procedural://chibi_chainsaw",
		"source_anchor": source_anchor, "top_left": top_left,
		"pixel_scale": pixel_scale,
		"visual_recoil": _style.get("visual_recoil", Vector2.ZERO),
		"draw_transform": transform,
		"visual_muzzle": transform * Vector2.ZERO,
		"grip_local": _source_point(_spec["grip"] as Vector2),
		"support_local": _source_point(support_source),
	}


func _color(key: String, fallback: Color) -> Color:
	var value: Variant = _style.get(key, fallback)
	return _render_color(value as Color if typeof(value) == TYPE_COLOR else fallback)


func _render_color(color: Color) -> Color:
	return LimbRenderer.tint_color(color, bool(_style.get("is_charred", false)), bool(_style.get("is_hit_flash", false)))




func _draw() -> void:
	if _spec.is_empty():
		return
	var tex: Texture2D = weapon_texture
	var procedural: bool = str(_spec.get("render_kind", "")) == "procedural_melee"
	if tex == null and not procedural:
		return
	var top_left: Vector2 = _muzzle - (_spec["muzzle"] as Vector2) * float(_spec["scale"])
	var trigger: Vector2 = _source_point(_spec["grip"] as Vector2)
	var sleeve: Color = _color("sleeve", Color(0.58, 0.64, 0.72))
	var skin: Color = _color("skin_lit", Color(1.0, 0.85, 0.73))
	var glove: Color = _color("glove", Color(0.16, 0.20, 0.28))
	var trim: Color = _color("glove_trim", Color(1.0, 0.52, 0.16))
	var outline: Color = _render_color(DARK)
	# Both source hands are replaced, with a compact elbow joining the true
	# shoulder origin. The gun itself remains the original weapon-only bitmap.
	var shoulder: Vector2 = _style.get("shoulder_origin", Vector2.ZERO) as Vector2
	var elbow: Vector2 = shoulder.lerp(trigger, 0.35) + Vector2(0.0, 1.8)
	var wear: String = str(_style.get("handwear", "bare"))
	var band: bool = bool(_style.get("wristband", false))
	var coverage: String = str(_style.get("sleeve_coverage", "long"))
	var support: Vector2 = Vector2.ZERO
	var rear_elbow: Vector2 = Vector2.ZERO
	var two_handed: bool = _spec.has("support")
	if two_handed:
		var support_source: Vector2 = _spec["support"] as Vector2
		# Compiled weapon frame3 is the shotgun pump pose. Only the supporting
		# wrist moves; the authoritative muzzle and source silhouette stay exact.
		if str(_spec["asset"]) == "shotgun" and _frame >= 3:
			support_source.x -= 2.0
		support = _source_point(support_source)
		var rear_shoulder: Vector2 = _style.get("rear_shoulder_origin", shoulder + Vector2(-0.8, 0.8)) as Vector2
		rear_elbow = rear_shoulder.lerp(support, 0.35) + Vector2(0.0, 2.0)
		LimbRenderer.draw_arm(self, rear_shoulder, rear_elbow, support, sleeve.darkened(0.15), skin.darkened(0.08), glove, trim, outline, false, "grip", wear, band, coverage)
	LimbRenderer.draw_arm(self, shoulder, elbow, trigger, sleeve, skin, glove, trim, outline, false, "grip", wear, band, coverage)
	if procedural:
		_draw_chainsaw(top_left)
	else:
		draw_set_transform_matrix(_weapon_transform())
		draw_texture_rect(tex, Rect2(-(_spec["muzzle"] as Vector2), Vector2(tex.get_size())), false, _render_color(Color.WHITE))
		draw_set_transform_matrix(Transform2D.IDENTITY)
	LimbRenderer.draw_grip_overlay(self, trigger, elbow, skin, glove, outline, wear)
	if two_handed:
		LimbRenderer.draw_grip_overlay(self, support, rear_elbow, skin.darkened(0.08), glove.darkened(0.1), outline, wear)


func _draw_chainsaw(top_left: Vector2) -> void:
	# Dedicated melee prop; the source table's flamethrower pickup alias is not
	# a chainsaw image. Draw an explicit motor, handle and serrated chain bar.
	var motor: Rect2 = Rect2(top_left + Vector2(0.0, 1.0), Vector2(8.0, 6.0))
	draw_rect(motor.grow(0.45), _render_color(DARK))
	draw_rect(motor, _render_color(Color(0.93, 0.67, 0.17)))
	draw_rect(Rect2(top_left + Vector2(1.0, 2.0), Vector2(4.5, 2.0)), _render_color(Color(1.0, 0.85, 0.37)))
	draw_circle(top_left + Vector2(5.0, 4.2), 1.25, _render_color(Color(0.25, 0.28, 0.32)))
	draw_line(top_left + Vector2(1.0, 6.5), top_left + Vector2(1.0, 8.0), _render_color(DARK), 0.9, true)
	draw_line(top_left + Vector2(1.0, 8.0), top_left + Vector2(4.5, 8.0), _render_color(DARK), 0.9, true)
	draw_line(top_left + Vector2(7.3, 0.0), top_left + Vector2(7.3, 6.5), _render_color(DARK), 1.2, true)
	draw_line(top_left + Vector2(7.3, 3.0), top_left + Vector2(17.1, 3.0), _render_color(DARK), 3.8, true)
	draw_line(top_left + Vector2(7.6, 3.0), top_left + Vector2(17.0, 3.0), _render_color(Color(0.70, 0.76, 0.79)), 2.6, true)
	draw_circle(top_left + Vector2(17.1, 3.0), 0.9, _render_color(DARK))
	draw_circle(top_left + Vector2(17.1, 3.0), 0.55, _render_color(Color(0.70, 0.76, 0.79)))
	draw_line(top_left + Vector2(8.0, 3.0), top_left + Vector2(16.8, 3.0), _render_color(Color(0.35, 0.42, 0.48)), 0.65, true)
	for i: int in range(6):
		var x: float = 8.2 + float(i) * 1.4
		draw_line(top_left + Vector2(x, 1.7), top_left + Vector2(x + 0.35, 1.1), _render_color(DARK), 0.65, true)
		draw_line(top_left + Vector2(x, 4.3), top_left + Vector2(x - 0.35, 4.9), _render_color(DARK), 0.65, true)
