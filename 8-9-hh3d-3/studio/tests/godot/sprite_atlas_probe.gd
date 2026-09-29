extends Node
## Trusted disposable asset test, never a public authoring command.

var sprite: AnimatedSprite2D
var tick: int = 0
var samples: Array[Dictionary] = []
var sheet: Texture2D
const OFFSETS: Array[Vector2i] = [Vector2i(0, 0), Vector2i(64, 0), Vector2i(0, 64), Vector2i(64, 64)]

func _fail(message: String) -> void:
	print("HH_ATLAS_REJECT " + message)
	set_process(false)
	get_tree().quit(21)

func _ready() -> void:
	set_process(false)
	sheet = load("res://sprite_sheet.png") as Texture2D
	if sheet == null or sheet.get_size() != Vector2(128, 128):
		_fail("texture")
		return
	var sheet_image: Image = sheet.get_image()
	var colors_ok: bool = true
	for frame: int in range(4):
		for y: int in range(8, 56):
			for x: int in range(8, 56):
				var color: Color = sheet_image.get_pixel(x + OFFSETS[frame].x, y + OFFSETS[frame].y)
				colors_ok = colors_ok and _color_matches(frame, color)
	for line: int in [0, 63, 64, 127]:
		for i: int in range(128):
			colors_ok = colors_ok and sheet_image.get_pixel(line, i).a <= 0.01
			colors_ok = colors_ok and sheet_image.get_pixel(i, line).a <= 0.01
	if not colors_ok:
		_fail("sheet_pixels")
		return
	if OS.get_cmdline_user_args() == PackedStringArray(["author"]):
		_author()
	elif OS.get_cmdline_user_args() == PackedStringArray(["reload"]):
		_reload()
	else:
		_fail("phase")

func _color_matches(frame: int, color: Color) -> bool:
	if color.a < 0.99:
		return false
	match frame:
		0: return color.r > 1.7 * maxf(color.g, color.b)
		1: return color.g > 1.7 * maxf(color.r, color.b)
		2: return color.b > 1.7 * maxf(color.r, color.g)
		3: return minf(color.r, color.g) > 1.7 * color.b and absf(color.r - color.g) < 0.3
	return false

func _author() -> void:
	var frames: SpriteFrames = SpriteFrames.new()
	frames.remove_animation(&"default")
	frames.add_animation(&"idle")
	frames.set_animation_speed(&"idle", 8.0)
	frames.set_animation_loop(&"idle", true)
	for offset: Vector2i in OFFSETS:
		var atlas: AtlasTexture = AtlasTexture.new()
		atlas.atlas = sheet
		atlas.region = Rect2(Vector2(offset), Vector2(64, 64))
		frames.add_frame(&"idle", atlas, 1.0)
	var directory_error: Error = DirAccess.make_dir_recursive_absolute("res://generated")
	if directory_error != OK or ResourceSaver.save(frames, "res://generated/frames.tres") != OK:
		_fail("frames_save")
		return
	var actor: AnimatedSprite2D = AnimatedSprite2D.new()
	actor.name = "AtlasActor"
	actor.sprite_frames = load("res://generated/frames.tres") as SpriteFrames
	actor.animation = &"idle"
	actor.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	var packed: PackedScene = PackedScene.new()
	var pack_error: Error = packed.pack(actor)
	actor.free()
	if pack_error != OK or ResourceSaver.save(packed, "res://generated/actor.tscn") != OK:
		_fail("scene_save")
		return
	print("HH_ATLAS_AUTHOR " + JSON.stringify({"frames": 4, "fps": 8,
		"loop": true, "sheet_sha256": FileAccess.get_sha256("res://sprite_sheet.png"),
		"frames_sha256": FileAccess.get_sha256("res://generated/frames.tres"),
		"scene_sha256": FileAccess.get_sha256("res://generated/actor.tscn")}))
	get_tree().quit(0)

func _reload() -> void:
	var packed: PackedScene = load("res://generated/actor.tscn") as PackedScene
	if packed == null:
		_fail("scene_reload")
		return
	sprite = packed.instantiate() as AnimatedSprite2D
	if sprite == null:
		_fail("actor_type")
		return
	add_child(sprite)
	var frames: SpriteFrames = sprite.sprite_frames
	if frames == null or frames.get_animation_names() != PackedStringArray(["idle"]) \
		or frames.get_frame_count(&"idle") != 4 or frames.get_animation_speed(&"idle") != 8.0 \
		or not frames.get_animation_loop(&"idle"):
		_fail("frames_reload")
		return
	for frame: int in range(4):
		var atlas: AtlasTexture = frames.get_frame_texture(&"idle", frame) as AtlasTexture
		if atlas == null or atlas.region != Rect2(Vector2(OFFSETS[frame]), Vector2(64, 64)) \
			or frames.get_frame_duration(&"idle", frame) != 1.0 \
			or not _color_matches(frame, atlas.get_image().get_pixel(32, 32)):
			_fail("frame_reload")
			return
	sprite.play(&"idle")
	set_process(true)

func _process(delta: float) -> void:
	tick += 1
	# These are observations of AnimatedSprite2D's native clock, not calls that
	# assign the frame index to the expected value.
	samples.append({"tick": tick, "delta": delta, "frame": sprite.frame,
		"progress": sprite.frame_progress, "playing": sprite.is_playing()})
	if tick == 37:
		sprite.pause()
	if tick == 49:
		sprite.play(&"idle")
	if tick == 100:
		set_process(false)
		print("HH_ATLAS_RELOAD " + JSON.stringify({"samples": samples,
			"sheet_sha256": FileAccess.get_sha256("res://sprite_sheet.png"),
			"frames_sha256": FileAccess.get_sha256("res://generated/frames.tres"),
			"scene_sha256": FileAccess.get_sha256("res://generated/actor.tscn")}))
		get_tree().quit(0)
