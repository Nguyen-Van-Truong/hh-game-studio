extends SceneTree
## Actual FighterRigView + FireHazardSystem viewport samples.
## Fixed stage positions, authored source time and supplied velocity; NOT
## gameplay/input E2E, damage simulation, measured FPS or owner art acceptance.
## Run with a rendering driver. A deferred coroutine owns every post-draw wait.

const RegistryScript: Script = preload("res://game/core/sf_data_registry.gd")
const RigScript: Script = preload("res://game/fighter/fighter_rig_view.gd")
const FireScript: Script = preload("res://game/world/fire_hazard_system.gd")
const OUT: String = "res://docs/chibi-r6"
const FRAME_COUNT: int = 36
const SOURCE_STEP: float = 0.5
const SHEET_SIZE: Vector2i = Vector2i(1280, 720)
const MOTION_SIZE: Vector2i = Vector2i(960, 480)
const CELL_TINT: Color = Color("192538")
const ALT_TINT: Color = Color("1c2b40")


class PreviewActor:
	extends Node2D
	# The view reads these presentation inputs from its actor. This fixture has
	# no controller, collision, damage method, AI, input or simulation callbacks.
	var rig_view: Node2D = null
	var is_dead: bool = false
	var burned: bool = false
	var burn_state: float = 0.0
	var is_gibbed: bool = false
	var hp: float = 100.0
	var air_velocity: Vector2 = Vector2.ZERO
	var on_ground: bool = true
	var taking_cover: bool = false
	var kneeling: bool = false
	var grabbed_target: Node2D = null
	var _hit_flash_timer: float = 0.0
	var awakening_timer: float = 0.0
	var overheat_timer: float = 0.0
	var bullet_deflect_timer: float = 0.0
	var is_summoned_clone: bool = false
	var resource_spec: Dictionary = {}
	var _afterimage_trail: Array = []
	var active_vfx_overlays: Array = []


var _registry: Node = null
var _page: Node2D = null
var _samples: Array[Dictionary] = []
var _body_regions: Array[Rect2i] = []
var _region_tints: Array[Color] = []
var _motion_captions: Array[Label] = []
var _clock_caption: Label = null
var _fixture_failed: bool = false


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	if DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT + "/motion_frames")) != OK:
		push_error("[CHIBI R6 VISUAL] cannot create output directory")
		await _finish(false)
		return
	_registry = _load_registry()
	if _registry == null:
		push_error("[CHIBI R6 VISUAL] missing registry")
		await _finish(false)
		return
	_set_size(SHEET_SIZE)
	_build_sheet()
	if _fixture_failed or not await _capture(OUT + "/poses.png", SHEET_SIZE):
		await _finish(false)
		return
	_clear_page()
	await process_frame
	_set_size(MOTION_SIZE)
	_build_motion_page()
	for frame_number: int in range(FRAME_COUNT):
		_update_motion(frame_number)
		if _fixture_failed or not await _capture(OUT + ("/motion_frames/frame_%04d.png" % frame_number), MOTION_SIZE):
			await _finish(false)
			return
	await _finish(true)


func _finish(success: bool) -> void:
	_clear_page()
	await process_frame
	var drained: bool = true
	var audio: Node = root.get_node_or_null("AudioManager")
	if audio != null and audio.has_method("stop_all_and_drain"):
		drained = bool(await audio.call("stop_all_and_drain"))
	if success and drained:
		print("[CHIBI R6 VISUAL] PASS frames=36 sheets=1")
	quit(0 if success and drained else 1)


func _clear_page() -> void:
	_samples.clear()
	_body_regions.clear()
	_region_tints.clear()
	_motion_captions.clear()
	_clock_caption = null
	if is_instance_valid(_page):
		_page.free()
	_page = null


func _load_registry() -> Node:
	var registry: Node = root.get_node_or_null("SFDataRegistry")
	if registry == null:
		registry = RegistryScript.new() as Node
		registry.name = "ChibiR6VisualRegistry"
		root.add_child(registry)
	if registry.has_method("ensure_loaded"):
		registry.call("ensure_loaded")
	return registry


func _set_size(size_value: Vector2i) -> void:
	root.size = size_value
	root.content_scale_size = size_value
	RenderingServer.viewport_set_update_mode(root.get_viewport_rid(), RenderingServer.VIEWPORT_UPDATE_ALWAYS)


func _label(at: Vector2, size_value: Vector2, text_value: String, font_size: int, color: Color = Color("deebfa")) -> Label:
	var label := Label.new()
	label.position = at
	label.size = size_value
	label.text = text_value
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.z_index = 30
	_page.add_child(label)
	return label


func _rect(at: Vector2, size_value: Vector2, tint: Color, parent: Node = null) -> void:
	var panel := ColorRect.new()
	panel.position = at
	panel.size = size_value
	panel.color = tint
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	(parent if parent != null else _page).add_child(panel)


func _new_page(size_value: Vector2i, title: String, subtitle: String) -> void:
	_page = Node2D.new()
	_page.name = "ChibiR6SampledPresentation"
	root.add_child(_page)
	_rect(Vector2.ZERO, Vector2(size_value), Color("0f1725"))
	_label(Vector2(16.0, 7.0), Vector2(float(size_value.x) - 30.0, 28.0), title, 21, Color("f4d68e"))
	_label(Vector2(17.0, 36.0), Vector2(float(size_value.x) - 30.0, 22.0), subtitle, 11, Color("9bb5d1"))


func _new_sample(identity: String, state: String, source: float, motion: Dictionary, scale_value: float, at: Vector2, burn: float = 0.0, corpse: bool = false, body_angle: float = 0.0) -> Dictionary:
	# Facing belongs to FighterRigView. Zoom belongs to the wrapper, shared by
	# the actual hazard renderer, so world burn anchors and flame size agree.
	var wrapper := Node2D.new()
	wrapper.name = "Sample_" + state + "_" + str(scale_value)
	wrapper.position = at
	wrapper.scale = Vector2.ONE * scale_value
	_page.add_child(wrapper)
	var actor := PreviewActor.new()
	actor.name = "PresentationFixtureActor"
	wrapper.add_child(actor)
	var rig: Node2D = RigScript.new() as Node2D
	rig.name = "FighterRigView"
	rig.set("registry_override", _registry)
	rig.set("chibi_brawler_enabled", true)
	actor.rig_view = rig
	actor.add_child(rig)
	var effects: Node2D = null
	if burn >= 15.0:
		effects = FireScript.new() as Node2D
		effects.name = "ActualFireHazardSystem"
		wrapper.add_child(effects)
		effects.set("external_fighters", [actor])
	var sample: Dictionary = {"identity": identity, "actor": actor, "rig": rig, "effects": effects, "wrapper": wrapper}
	_apply_sample(sample, state, source, motion, burn, corpse, body_angle)
	_samples.append(sample)
	return sample


func _apply_sample(sample: Dictionary, state: String, source: float, motion: Dictionary, burn: float = 0.0, corpse: bool = false, body_angle: float = 0.0) -> void:
	var actor: PreviewActor = sample["actor"] as PreviewActor
	var rig: Node2D = sample["rig"] as Node2D
	actor.is_dead = corpse
	actor.burned = corpse
	actor.burn_state = burn
	actor.hp = 0.0 if corpse else 100.0
	actor.air_velocity = motion.get("velocity", Vector2.ZERO) as Vector2
	actor.on_ground = bool(motion.get("grounded", true))
	rig.call("apply_rig_state", str(sample["identity"]), state, 1, 1, 0.0, 1, actor.hp, 100.0, body_angle, false, false, burn, corpse, source, motion)
	rig.queue_redraw()
	var effects: Node2D = sample["effects"] as Node2D
	if effects != null:
		# Draw-only clock assignment. Never call step_hazards(), spawn fire,
		# apply damage, play SFX or advance any gameplay state in this fixture.
		effects.set("_visual_tick", source)
		effects.queue_redraw()
		var specs: Array = effects.call("get_chibi_burn_draw_specs", actor, corpse or burn >= 100.0) as Array
		var texture_sequence: Array = effects.get("_fire_01_seq") as Array
		if specs.size() != 3 or texture_sequence.is_empty():
			_fixture_failed = true
			push_error("[CHIBI R6 VISUAL] actual fire anchors/textures unavailable for " + state)


func _add_body_region(region: Rect2i, tint: Color) -> void:
	_body_regions.append(region)
	_region_tints.append(tint)


func _build_sheet() -> void:
	_new_page(SHEET_SIZE, "CHIBI R6 / NATURAL POSE + ACTUAL FIRE DIAGNOSTIC", "SAMPLED PRESENTATION - NOT GAMEPLAY E2E | fixed stage positions | Blender head atlas retained | 5x / 3.4x / 1.85x")
	var cases: Array[Dictionary] = [
		{"label": "IDLE", "id": "agent", "state": "IDLE", "t": 0.0, "v": Vector2.ZERO, "floor": true},
		{"label": "WALK", "id": "blaire", "state": "WALK", "t": 4.0, "v": Vector2(1.0, 0.0), "floor": true},
		{"label": "RUN", "id": "goku", "state": "RUN", "t": 3.0, "v": Vector2(2.0, 0.0), "floor": true},
		{"label": "ASCENT", "id": "naruto", "state": "JUMP", "t": 2.0, "v": Vector2(2.0, -5.0), "floor": false},
		{"label": "APEX", "id": "luffy", "state": "JUMP", "t": 4.0, "v": Vector2(2.0, 0.0), "floor": false},
		{"label": "DESCENT", "id": "hideki", "state": "JUMP", "t": 5.0, "v": Vector2(2.0, 3.0), "floor": false},
		{"label": "FREEFALL", "id": "saitama", "state": "JUMP", "t": 6.0, "v": Vector2(2.0, 10.0), "floor": false},
		{"label": "HIT TUMBLE", "id": "johnny", "state": "FALL_B", "t": 4.0, "v": Vector2(-3.0, 10.0), "floor": false, "angle": -20.0},
		{"label": "BURNING IDLE", "id": "agent", "state": "IDLE", "t": 1.75, "v": Vector2.ZERO, "floor": true, "burn": 130.0},
		{"label": "BURNING RUN", "id": "goku", "state": "RUN", "t": 3.0, "v": Vector2(2.0, 0.0), "floor": true, "burn": 130.0},
		{"label": "BURNING ROLL", "id": "blaire", "state": "ROLL", "t": 2.3, "v": Vector2(3.0, 0.0), "floor": true, "burn": 130.0},
		{"label": "BURNED PRONE", "id": "johnny", "state": "DEAD", "t": 6.0, "v": Vector2.ZERO, "floor": true, "burn": 45.0, "corpse": true},
	]
	for index: int in range(cases.size()):
		var data: Dictionary = cases[index]
		var col: int = index % 4
		var row: int = floori(float(index) / 4.0)
		var at := Vector2(8.0 + float(col) * 318.0, 65.0 + float(row) * 215.0)
		var tint: Color = CELL_TINT if col % 2 == 0 else ALT_TINT
		_rect(at, Vector2(310.0, 207.0), tint)
		_label(at + Vector2(8.0, 5.0), Vector2(296.0, 23.0), str(data["label"]) + " / " + str(data["id"]), 14)
		var motion: Dictionary = {"velocity": data["v"], "grounded": data["floor"], "burning": float(data.get("burn", 0.0)) >= 15.0 and not bool(data.get("corpse", false))}
		var sample: Dictionary = _new_sample(str(data["id"]), str(data["state"]), float(data["t"]), motion, 5.0, at + Vector2(80.0, 179.0), float(data.get("burn", 0.0)), bool(data.get("corpse", false)), float(data.get("angle", 0.0)))
		var rig: Node2D = sample["rig"] as Node2D
		var pose: Dictionary = rig.call("get_chibi_pose_snapshot") as Dictionary
		_label(at + Vector2(8.0, 28.0), Vector2(294.0, 18.0), str(data["state"]) + " / " + str(pose["phase"]) + " / s=" + str(data["t"]), 10, Color("aac5de"))
		_new_sample(str(data["id"]), str(data["state"]), float(data["t"]), motion, 3.4, at + Vector2(199.0, 179.0), float(data.get("burn", 0.0)), bool(data.get("corpse", false)), float(data.get("angle", 0.0)))
		_new_sample(str(data["id"]), str(data["state"]), float(data["t"]), motion, 1.85, at + Vector2(274.0, 179.0), float(data.get("burn", 0.0)), bool(data.get("corpse", false)), float(data.get("angle", 0.0)))
		_rect(at + Vector2(8.0, 182.0), Vector2(294.0, 1.0), Color("3b4f68"))
		_label(at + Vector2(61.0, 187.0), Vector2(56.0, 17.0), "5x detail", 10, Color("9bb5d1"))
		_label(at + Vector2(183.0, 187.0), Vector2(54.0, 17.0), "3.4x", 10, Color("9bb5d1"))
		_label(at + Vector2(257.0, 187.0), Vector2(48.0, 17.0), "1.85x", 10, Color("9bb5d1"))
		_add_body_region(Rect2i(Vector2i(at) + Vector2i(20, 62), Vector2i(125, 118)), tint)
		_add_body_region(Rect2i(Vector2i(at) + Vector2i(171, 103), Vector2i(67, 77)), tint)
		_add_body_region(Rect2i(Vector2i(at) + Vector2i(253, 135), Vector2i(52, 45)), tint)


func _build_motion_page() -> void:
	_new_page(MOTION_SIZE, "CHIBI R6 / SHARED SOURCE CLOCK", "SAMPLED PRESENTATION - NOT GAMEPLAY E2E | fixed stage positions | actual body + fire draw | source step 0.5 per PNG")
	_clock_caption = _label(Vector2(17.0, 56.0), Vector2(925.0, 19.0), "", 11, Color("f4d68e"))
	var titles: Array[String] = ["RELAXED IDLE / agent", "RUN / goku", "AIR PHASES / naruto", "BURNING RUN / blaire"]
	var identities: Array[String] = ["agent", "goku", "naruto", "blaire"]
	for col: int in range(4):
		var left: float = 6.0 + float(col) * 240.0
		var tint: Color = CELL_TINT if col % 2 == 0 else ALT_TINT
		_rect(Vector2(left, 82.0), Vector2(228.0, 388.0), tint)
		_label(Vector2(left + 8.0, 87.0), Vector2(215.0, 22.0), titles[col], 13)
		_motion_captions.append(_label(Vector2(left + 8.0, 109.0), Vector2(215.0, 21.0), "", 10, Color("aac5de")))
		var state: String = "IDLE" if col == 0 else ("JUMP" if col == 2 else "RUN")
		var burn: float = 130.0 if col == 3 else 0.0
		for zoom: float in [7.0, 3.4, 1.85]:
			var at: Vector2 = Vector2(left + 111.0, 302.0) if zoom > 4.0 else Vector2(left + (77.0 if zoom > 2.0 else 164.0), 427.0)
			var sample: Dictionary = _new_sample(identities[col], state, 0.0, {"velocity": Vector2.ZERO, "grounded": col != 2}, zoom, at, burn)
			sample["motion_column"] = col
		_rect(Vector2(left + 12.0, 305.0), Vector2(204.0, 1.0), Color("3b4f68"))
		_rect(Vector2(left + 12.0, 430.0), Vector2(204.0, 1.0), Color("3b4f68"))
		_label(Vector2(left + 83.0, 313.0), Vector2(90.0, 18.0), "7x detail", 10, Color("9bb5d1"))
		_label(Vector2(left + 60.0, 440.0), Vector2(70.0, 17.0), "3.4x", 11, Color("9bb5d1"))
		_label(Vector2(left + 145.0, 440.0), Vector2(64.0, 17.0), "1.85x", 11, Color("9bb5d1"))
		_add_body_region(Rect2i(int(left) + 35, 136, 157, 166), tint)
		_add_body_region(Rect2i(int(left) + 43, 345, 78, 83), tint)
		_add_body_region(Rect2i(int(left) + 141, 382, 48, 46), tint)


func _update_motion(frame_number: int) -> void:
	var source: float = float(frame_number) * SOURCE_STEP
	var vertical: float = lerpf(-5.0, 10.0, float(frame_number) / float(FRAME_COUNT - 1))
	_clock_caption.text = "PNG %02d/35 | source=%.2f | same clock for poses and FireHazardSystem | velocity is a fixture input" % [frame_number, source]
	for sample: Dictionary in _samples:
		var col: int = int(sample.get("motion_column", -1))
		if col < 0:
			continue
		var state: String = "IDLE" if col == 0 else ("JUMP" if col == 2 else "RUN")
		var velocity: Vector2 = Vector2(2.0, vertical) if col == 2 else Vector2(2.0 if col > 0 else 0.0, 0.0)
		var motion: Dictionary = {"velocity": velocity, "grounded": col != 2, "burning": col == 3}
		_apply_sample(sample, state, source, motion, 130.0 if col == 3 else 0.0)
		var pose: Dictionary = (sample["rig"] as Node).call("get_chibi_pose_snapshot") as Dictionary
		_motion_captions[col].text = str(pose["phase"]) + (" / vy=%.2f" % vertical if col == 2 else "")


func _has_body_pixels(image: Image, region: Rect2i, tint: Color) -> bool:
	var clip: Rect2i = region.intersection(Rect2i(Vector2i.ZERO, image.get_size()))
	var count: int = 0
	for y: int in range(clip.position.y, clip.end.y, 2):
		for x: int in range(clip.position.x, clip.end.x, 2):
			var pixel: Color = image.get_pixel(x, y)
			if absf(pixel.r - tint.r) + absf(pixel.g - tint.g) + absf(pixel.b - tint.b) > 0.18:
				count += 1
				if count >= 12:
					return true
	return false


func _capture(path: String, size_value: Vector2i) -> bool:
	# The deferred runner resumes through both signals; no async _process is
	# re-entered while rendering or capture is awaiting its next frame.
	await process_frame
	await RenderingServer.frame_post_draw
	var texture: ViewportTexture = root.get_texture()
	var image: Image = texture.get_image() if texture != null else null
	if image == null or image.is_empty() or image.get_size() != size_value:
		push_error("[CHIBI R6 VISUAL] empty or wrong-size viewport: " + path)
		return false
	for index: int in range(_body_regions.size()):
		if not _has_body_pixels(image, _body_regions[index], _region_tints[index]):
			push_error("[CHIBI R6 VISUAL] blank body/readability region " + str(index) + " in " + path)
			return false
	var error: Error = image.save_png(ProjectSettings.globalize_path(path))
	if error != OK:
		push_error("[CHIBI R6 VISUAL] cannot save " + path + " error=" + str(error))
		return false
	print("[CHIBI R6 VISUAL] saved=" + path + " size=" + str(size_value))
	return true
