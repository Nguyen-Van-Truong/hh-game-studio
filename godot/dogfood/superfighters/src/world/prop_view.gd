class_name PropView
extends Sprite2D

## Presentation-only sprite. Cannot despawn, move, or set health.
## ledger:RL-WORLD-OWN (assumption).

const _Paths: GDScript = preload("res://src/world/world_paths.gd")


func bind_visual(tex_path: String) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var reason: String = str(_Paths.reject_reason(tex_path))
	if reason != "":
		errors.append(reason)
		return errors
	name = "PropView"
	centered = true
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	texture = load(tex_path) as Texture2D
	if texture == null:
		errors.append("visual failed to load")
	return errors


func request_despawn() -> PackedStringArray:
	return PackedStringArray(["presentation cannot despawn"])


func request_set_health(_value: float) -> PackedStringArray:
	return PackedStringArray(["presentation cannot mutate health"])


func request_move(_at: Vector2) -> PackedStringArray:
	return PackedStringArray(["presentation cannot move props"])
