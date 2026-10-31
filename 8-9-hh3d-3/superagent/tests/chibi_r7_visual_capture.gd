extends SceneTree
## R7 body seam/joint visual capture using the actual FighterRigView.
##
## This is a render-only fixture: it supplies authored state/source frames and
## motion dictionaries to FighterRigView, never enters a match, advances a
## controller, drives input, or claims gameplay/Y8 parity.  The output is a
## labelled contact sheet plus 48 deterministic motion frames.  A capture is
## accepted only when the viewport has the requested dimensions and every
## registered body region contains non-background pixels.

const RegistryScript: Script = preload("res://game/core/sf_data_registry.gd")
const RigScript: Script = preload("res://game/fighter/fighter_rig_view.gd")
const FireScript: Script = preload("res://game/world/fire_hazard_system.gd")
const OUT: String = "res://docs/chibi-r7"
const FRAME_COUNT: int = 48
const SOURCE_STEP: float = 0.5
const SHEET_SIZE: Vector2i = Vector2i(1280, 900)
const MOTION_SIZE: Vector2i = Vector2i(1280, 720)
const CELL_TINT: Color = Color("192538")
const ALT_TINT: Color = Color("1c2b40")


class PreviewActor:
	## Presentation-only actor surface read by FighterRigView/FireHazardSystem.
	extends Node2D
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
		push_error("[CHIBI R7 VISUAL] cannot create output directory")
		await _finish(false)
		return
	_registry = _load_registry()
	if _registry == null:
		push_error("[CHIBI R7 VISUAL] missing registry")
		await _finish(false)
		return
	_set_size(SHEET_SIZE)
	_build_sheet()
	if _fixture_failed or not await _capture(OUT + "/joints.png", SHEET_SIZE):
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
		print("[CHIBI R7 VISUAL] PASS frames=48 sheets=1")
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
		registry.name = "ChibiR7VisualRegistry"
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
	label.add_theme_color_override("font_shadow_color", Color(0.0, 0.0, 0.0, 0.92))
	label.add_theme_constant_override("shadow_offset_x", 1)
	label.add_theme_constant_override("shadow_offset_y", 1)
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
	_page.name = "ChibiR7SampledPresentation"
	root.add_child(_page)
	_rect(Vector2.ZERO, Vector2(size_value), Color("0f1725"))
	_label(Vector2(17.0, 7.0), Vector2(float(size_value.x) - 30.0, 26.0), title, 21, Color("f4d68e"))
	_label(Vector2(18.0, 34.0), Vector2(float(size_value.x) - 30.0, 19.0), subtitle, 11, Color("9bb5d1"))


func _new_sample(identity: String, state: String, source: float, motion: Dictionary, scale_value: float, at: Vector2, burn: float = 0.0, corpse: bool = false, body_angle: float = 0.0, pitch: float = 0.0, weapon_frame: int = 1) -> Dictionary:
	# Zoom lives on this presentation wrapper. FighterRigView owns its own
	# facing scale and keeps weapon/body sockets in runtime coordinates.
	var wrapper := Node2D.new()
	wrapper.name = "Sample_" + identity + "_" + state + "_" + str(scale_value)
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
	var sample: Dictionary = {"identity": identity, "actor": actor, "rig": rig, "effects": effects, "wrapper": wrapper, "pitch": pitch, "weapon_frame": weapon_frame}
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
	var pitch: float = float(sample.get("pitch", 0.0))
	var weapon_frame: int = int(sample.get("weapon_frame", 1))
	rig.call("apply_rig_state", str(sample["identity"]), state, 1, 1, pitch, weapon_frame, actor.hp, 100.0, body_angle, false, false, burn, corpse, source, motion)
	rig.queue_redraw()
	var effects: Node2D = sample["effects"] as Node2D
	if effects != null:
		# Draw-only clock assignment: no hazard stepping, damage or SFX.
		effects.set("_visual_tick", source)
		effects.queue_redraw()
		var specs: Array = effects.call("get_chibi_burn_draw_specs", actor, corpse or burn >= 100.0) as Array
		var texture_sequence: Array = effects.get("_fire_01_seq") as Array
		if specs.size() != 3 or texture_sequence.is_empty():
			_fixture_failed = true
			push_error("[CHIBI R7 VISUAL] actual fire anchors/textures unavailable for " + state)


func _add_body_region(region: Rect2i, tint: Color) -> void:
	_body_regions.append(region)
	_region_tints.append(tint)


func _build_sheet() -> void:
	_new_page(SHEET_SIZE, "CHIBI R7 / JOINT + SEAM REVIEW", "NOTGAMEPLAY / PRESENTATION FIXTURE ONLY | actual FighterRigView | 8x detail + 3.4x real zoom | clean labelled cells")
	var cases: Array[Dictionary] = [
		{"label": "IDLE", "id": "agent", "state": "IDLE", "t": 4.0, "v": Vector2.ZERO, "grounded": true},
		{"label": "RUN", "id": "goku", "state": "RUN", "t": 5.5, "v": Vector2(2.0, 0.0), "grounded": true},
		{"label": "JUMP", "id": "naruto", "state": "JUMP", "t": 1.5, "v": Vector2(2.0, -5.0), "grounded": false},
		{"label": "PUNCH 01", "id": "luffy", "state": "PUNCH_01", "t": 3.0, "v": Vector2.ZERO, "grounded": true},
		{"label": "PUNCH 02", "id": "saitama", "state": "PUNCH_02", "t": 3.5, "v": Vector2.ZERO, "grounded": true},
		{"label": "PUNCH 03", "id": "agent", "state": "PUNCH_03", "t": 4.0, "v": Vector2.ZERO, "grounded": true},
		{"label": "CROUCH", "id": "goku", "state": "CROUCH", "t": 0.0, "v": Vector2.ZERO, "grounded": true},
		{"label": "AIM PISTOL", "id": "naruto", "state": "AIM_PISTOL", "t": 0.0, "pitch": -20.0, "weapon_frame": 2, "v": Vector2.ZERO, "grounded": true},
		{"label": "AIM SHOTGUN 45 DEG", "id": "luffy", "state": "AIM_SHOTGUN", "t": 0.0, "pitch": 45.0, "weapon_frame": 3, "v": Vector2.ZERO, "grounded": true},
		{"label": "ROLL", "id": "saitama", "state": "ROLL", "t": 2.2, "v": Vector2(3.0, 0.0), "grounded": true},
		{"label": "FALL", "id": "agent", "state": "FALL", "t": 6.0, "v": Vector2(2.0, 10.0), "grounded": false},
		{"label": "BURN", "id": "goku", "state": "IDLE", "t": 1.75, "burn": 130.0, "v": Vector2.ZERO, "grounded": true, "burning": true},
	]
	var cell_size := Vector2(416.0, 205.0)
	for index: int in range(cases.size()):
		var data: Dictionary = cases[index]
		var col: int = index % 3
		var row: int = floori(float(index) / 3.0)
		var at := Vector2(8.0 + float(col) * 424.0, 49.0 + float(row) * 211.0)
		var tint: Color = CELL_TINT if col % 2 == 0 else ALT_TINT
		_rect(at, cell_size, tint)
		_label(at + Vector2(8.0, 4.0), Vector2(400.0, 19.0), str(data["label"]) + " / " + str(data["id"]), 13)
		var motion: Dictionary = {"velocity": data["v"], "grounded": data["grounded"], "burning": bool(data.get("burning", false))}
		var sample: Dictionary = _new_sample(str(data["id"]), str(data["state"]), float(data["t"]), motion, 8.0, at + Vector2(132.0, 183.0), float(data.get("burn", 0.0)), false, 0.0, float(data.get("pitch", 0.0)), int(data.get("weapon_frame", 1)))
		var rig: Node2D = sample["rig"] as Node2D
		var pose: Dictionary = rig.call("get_chibi_pose_snapshot") as Dictionary
		_label(at + Vector2(8.0, 181.0), Vector2(215.0, 17.0), str(data["state"]) + " / " + str(pose.get("phase", "hold")), 10, Color("aac5de"))
		_new_sample(str(data["id"]), str(data["state"]), float(data["t"]), motion, 3.4, at + Vector2(307.0, 181.0), float(data.get("burn", 0.0)), false, 0.0, float(data.get("pitch", 0.0)), int(data.get("weapon_frame", 1)))
		_label(at + Vector2(222.0, 181.0), Vector2(62.0, 17.0), "8x / 3.4x", 10, Color("9bb5d1"))
		# Regions deliberately cover torso, elbows and knees while excluding the
		# labels; any missing body draw fails closed at capture time.
		_add_body_region(Rect2i(int(at.x + 42.0), int(at.y + 27.0), 180, 153), tint)
		_add_body_region(Rect2i(int(at.x + 259.0), int(at.y + 111.0), 104, 70), tint)


func _build_motion_page() -> void:
	_new_page(MOTION_SIZE, "CHIBI R7 / 48 SOURCE-FRAME MOTION REVIEW", "NOTGAMEPLAY / PRESENTATION FIXTURE ONLY | 4 columns: IDLE / RUN / PUNCH COMBO / AIM | 7x detail + 3.4x real zoom")
	_clock_caption = _label(Vector2(18.0, 55.0), Vector2(1240.0, 18.0), "", 11, Color("f4d68e"))
	var titles: Array[String] = ["IDLE / agent", "RUN / goku", "PUNCH COMBO / naruto", "AIM / luffy"]
	var identities: Array[String] = ["agent", "goku", "naruto", "luffy"]
	for col: int in range(4):
		var left: float = 5.0 + float(col) * 320.0
		var tint: Color = CELL_TINT if col % 2 == 0 else ALT_TINT
		_rect(Vector2(left, 80.0), Vector2(310.0, 630.0), tint)
		_label(Vector2(left + 8.0, 86.0), Vector2(294.0, 19.0), titles[col], 13)
		_motion_captions.append(_label(Vector2(left + 8.0, 108.0), Vector2(294.0, 18.0), "", 10, Color("aac5de")))
		var state: String = "IDLE" if col == 0 else ("RUN" if col == 1 else ("PUNCH_01" if col == 2 else "AIM_PISTOL"))
		var pitch: float = 45.0 if col == 3 else 0.0
		var sample: Dictionary = _new_sample(identities[col], state, 0.0, {"velocity": Vector2.ZERO, "grounded": col != 3}, 7.0, Vector2(left + 154.0, 300.0), 0.0, false, 0.0, pitch, 1)
		sample["motion_column"] = col
		var small: Dictionary = _new_sample(identities[col], state, 0.0, {"velocity": Vector2.ZERO, "grounded": true}, 3.4, Vector2(left + 154.0, 535.0), 0.0, false, 0.0, pitch, 1)
		small["motion_column"] = col
		_rect(Vector2(left + 12.0, 385.0), Vector2(286.0, 1.0), Color("3b4f68"))
		_label(Vector2(left + 113.0, 393.0), Vector2(88.0, 17.0), "7x detail", 10, Color("9bb5d1"))
		_label(Vector2(left + 138.0, 562.0), Vector2(67.0, 17.0), "3.4x", 10, Color("9bb5d1"))
		_add_body_region(Rect2i(int(left + 38.0), 137, 218, 167), tint)
		_add_body_region(Rect2i(int(left + 102.0), 467, 106, 68), tint)


func _update_motion(frame_number: int) -> void:
	var source: float = float(frame_number) * SOURCE_STEP
	var sequence: int = frame_number % 12
	_clock_caption.text = "PNG %02d/47 | source_frame=%.1f | source step 0.5 per PNG | elbows/knees at 7x | deterministic fixture clock" % [frame_number, source]
	for sample: Dictionary in _samples:
		var col: int = int(sample.get("motion_column", -1))
		if col < 0:
			continue
		var state: String = "IDLE"
		var velocity := Vector2.ZERO
		var grounded: bool = true
		var pitch: float = 0.0
		var weapon_frame: int = 1
		var local_source: float = source
		if col == 1:
			state = "RUN"
			velocity = Vector2(2.0, 0.0)
		elif col == 2:
			# Sixteen samples each span windup, contact and recovery (0..7.5)
			# for all three punches instead of repeating a short strike cycle.
			state = "PUNCH_01" if frame_number < 16 else ("PUNCH_02" if frame_number < 32 else "PUNCH_03")
			local_source = float(frame_number % 16) * SOURCE_STEP
		elif col == 3:
			state = "AIM_PISTOL" if frame_number < 24 else "AIM_SHOTGUN"
			pitch = lerpf(-45.0, 45.0, float(frame_number % 24) / 23.0)
			weapon_frame = 2 if sequence in [2, 3, 8, 9] else (3 if state == "AIM_SHOTGUN" and sequence in [4, 5, 10, 11] else 1)
			grounded = true
		var motion: Dictionary = {"velocity": velocity, "grounded": grounded, "burning": false}
		sample["pitch"] = pitch
		sample["weapon_frame"] = weapon_frame
		_apply_sample(sample, state, local_source, motion)
		var caption: String = str(state) + " / source=%.1f" % local_source
		if col == 3:
			caption += " / pitch=%d" % int(pitch)
		_motion_captions[col].text = caption


func _has_body_pixels(image: Image, region: Rect2i, tint: Color) -> bool:
	var clip: Rect2i = region.intersection(Rect2i(Vector2i.ZERO, image.get_size()))
	if clip.size.x <= 0 or clip.size.y <= 0:
		return false
	var count: int = 0
	for y: int in range(clip.position.y, clip.end.y, 2):
		for x: int in range(clip.position.x, clip.end.x, 2):
			var pixel: Color = image.get_pixel(x, y)
			if absf(pixel.r - tint.r) + absf(pixel.g - tint.g) + absf(pixel.b - tint.b) > 0.18 and pixel.a > 0.02:
				count += 1
				if count >= 12:
					return true
	return false


func _capture(path: String, size_value: Vector2i) -> bool:
	# A deferred coroutine waits for both a scene process tick and the renderer's
	# post-draw signal, so the saved image is the actual FighterRigView output.
	await process_frame
	await RenderingServer.frame_post_draw
	var texture: ViewportTexture = root.get_texture()
	var image: Image = texture.get_image() if texture != null else null
	if image == null or image.is_empty() or image.get_size() != size_value:
		push_error("[CHIBI R7 VISUAL] empty or wrong-size viewport: " + path)
		return false
	for index: int in range(_body_regions.size()):
		if not _has_body_pixels(image, _body_regions[index], _region_tints[index]):
			push_error("[CHIBI R7 VISUAL] blank body/readability region " + str(index) + " in " + path)
			return false
	var error: Error = image.save_png(ProjectSettings.globalize_path(path))
	if error != OK:
		push_error("[CHIBI R7 VISUAL] cannot save " + path + " error=" + str(error))
		return false
	print("[CHIBI R7 VISUAL] saved=" + path + " size=" + str(size_value))
	return true
