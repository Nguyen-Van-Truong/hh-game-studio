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
	texture = load_texture(tex_path)
	if texture == null:
		errors.append("visual failed to load")
	return errors


static func load_texture(tex_path: String) -> Texture2D:
	if ResourceLoader.exists(tex_path):
		var loaded: Texture2D = load(tex_path) as Texture2D
		if loaded != null:
			return loaded
	if not FileAccess.file_exists(tex_path):
		return null
	var img: Image = Image.new()
	if img.load(tex_path) != OK:
		return null
	return ImageTexture.create_from_image(img)


func request_despawn() -> PackedStringArray:
	return PackedStringArray(["presentation cannot despawn"])


func request_set_health(_value: float) -> PackedStringArray:
	return PackedStringArray(["presentation cannot mutate health"])


func request_move(_at: Vector2) -> PackedStringArray:
	return PackedStringArray(["presentation cannot move props"])
