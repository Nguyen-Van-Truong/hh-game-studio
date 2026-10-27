class_name PropVisuals
extends RefCounted
## Original atlas regions shared by destructible props and fixed cover.
## Bounds come from the existing presentation contract; this never adds bodies.

const TEXTURE: Texture2D = preload("res://art/props/relay_objects_v2.png")
const REGIONS: Dictionary = {
	&"crate": Rect2(220, 47, 439, 419),
	&"barrel": Rect2(964, 30, 316, 444),
	&"cover": Rect2(130, 535, 784, 426),
	&"glass": Rect2(1014, 514, 368, 450),
}

static func draw_prop(c: CanvasItem, kind: StringName, bounds: Rect2, health: float = 1.0) -> bool:
	if not REGIONS.has(kind):
		return false
	var source: Rect2 = REGIONS[kind]
	var shade: float = 0.62 + 0.38 * clampf(health, 0.0, 1.0)
	c.draw_texture_rect_region(TEXTURE, bounds, source, Color(shade, shade, shade))
	return true
