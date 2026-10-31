extends SceneTree
## Source-frame animation evidence for the three authored punches.
##
## One hidden/offscreen launcher viewport produces 36 PNGs (source frames 0..8
## for PUNCH_01/02/03). This is a sampled presentation sheet, never gameplay
## E2E evidence. The top row uses the original FighterRigView at 6x; the two
## bottom markers exercise the integrated ChibiWeaponView at 1.85x and 3.4x.

const TARGET_SIZE: Vector2i = Vector2i(960, 360)
const OUTPUT_DIR: String = "res://docs/chibi-r5/combo_frames"
const FRAME_COUNT: int = 36
const RegistryScript: Script = preload("res://game/core/sf_data_registry.gd")
const FighterRigViewScript: Script = preload("res://game/fighter/fighter_rig_view.gd")
const ActionPoseScript: Script = preload("res://game/fighter/chibi_action_pose.gd")

var _reg: Node = null
var _page: Node2D = null
var _frame_number: int = 0
var _wait_frames: int = 0
var _started: bool = false


func _process(_delta: float) -> bool:
	if not _started:
		_started = true
		_prepare_root()
		_reg = _load_registry()
		_build_frame(_frame_number)
		_wait_frames = 2
		return false

	if _wait_frames > 0:
		_wait_frames -= 1
		return false

	if not _capture_frame(_frame_number):
		quit(1)
		return true
	_frame_number += 1
	if _frame_number >= FRAME_COUNT:
		print("[CHIBI R5 ANIMATION CAPTURE] PASS: frames=" + str(FRAME_COUNT) + " output=" + OUTPUT_DIR + " actual_exit=0")
		quit(0)
		return true
	if _page != null:
		_page.free()
		_page = null
	_build_frame(_frame_number)
	_wait_frames = 2
	return false


func _prepare_root() -> void:
	root.set("size", TARGET_SIZE)
	root.set("content_scale_size", TARGET_SIZE)
	var viewport: Viewport = root
	RenderingServer.viewport_set_update_mode(viewport.get_viewport_rid(), RenderingServer.VIEWPORT_UPDATE_ALWAYS)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUTPUT_DIR))


func _load_registry() -> Node:
	var existing: Node = root.get_node_or_null("SFDataRegistry")
	if existing != null:
		if existing.has_method("ensure_loaded"):
			existing.call("ensure_loaded")
		return existing
	var created: Node = RegistryScript.new() as Node
	created.name = "ChibiR5AnimationRegistry"
	root.add_child(created)
	if created.has_method("ensure_loaded"):
		created.call("ensure_loaded")
	return created


func _new_rig(parent: Node, char_id: String, state_name: String, source_frame: float, scale_value: float, position_value: Vector2, weapon_frame: int = 1, pitch: float = 0.0) -> Node:
	# Keep zoom on a wrapper: apply_rig_state() owns the FighterRigView scale
	# while the wrapper is only a presentation transform.
	var wrapper := Node2D.new()
	wrapper.name = "FrameRig_" + state_name + "_" + str(int(source_frame)) + "_" + str(scale_value)
	wrapper.position = position_value
	wrapper.scale = Vector2(scale_value, scale_value)
	parent.add_child(wrapper)
	var rig: Node = FighterRigViewScript.new() as Node
	rig.name = "FighterRigView"
	rig.set("registry_override", _reg)
	rig.set("chibi_brawler_enabled", true)
	wrapper.add_child(rig)
	rig.call("apply_rig_state", char_id, state_name, 1, 1, pitch, weapon_frame, 100.0, 100.0, 0.0, false, false, 0.0, false, source_frame)
	return wrapper


func _add_label(parent: Node, position_value: Vector2, size_value: Vector2, text_value: String, font_size: int, color: Color = Color.WHITE) -> void:
	var label := Label.new()
	label.position = position_value
	label.size = size_value
	label.text = text_value
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.add_theme_color_override("font_shadow_color", Color(0.0, 0.0, 0.0, 0.9))
	label.add_theme_constant_override("shadow_offset_x", 1)
	label.add_theme_constant_override("shadow_offset_y", 1)
	label.z_index = 30
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(label)


func _build_frame(frame_number: int) -> void:
	_page = Node2D.new()
	_page.name = "ChibiR5AnimationFrame" + str(frame_number)
	root.add_child(_page)
	var bg := ColorRect.new()
	bg.size = Vector2(TARGET_SIZE)
	bg.color = Color("101522")
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_page.add_child(bg)
	_add_label(_page, Vector2(16.0, 7.0), Vector2(920.0, 22.0), "SAMPLED SOURCE-FRAME ANIMATION / NOT GAMEPLAY E2E   frame=" + str(frame_number).pad_zeros(2) + "/35   source_frame=" + str(frame_number % 9), 15, Color("f4d68e"))

	var source_frame: float = float(frame_number % 9)
	var states: Array[String] = ["PUNCH_01", "PUNCH_02", "PUNCH_03"]
	var x_positions: Array[float] = [160.0, 480.0, 800.0]
	for i: int in range(states.size()):
		var state_name: String = states[i]
		_new_rig(_page, "johnny", state_name, source_frame, 6.0, Vector2(x_positions[i], 246.0))
		var pose: Dictionary = ActionPoseScript.sample(state_name, 1, 0.0, false, source_frame)
		_add_label(_page, Vector2(x_positions[i] - 142.0, 36.0), Vector2(284.0, 45.0), state_name + "\n" + str(pose.get("family", "safe_fallback")) + " / " + str(pose.get("phase", "hold")) + "  contact=" + str(bool(pose.get("contact", false))), 12, Color("dbe6f8"))

	# Small actual weapon markers keep the new source gun/hand layer visible in
	# the same receipt without changing the punch samples or their sockets.
	_new_rig(_page, "johnny", "AIM_PISTOL", 0.0, 1.85, Vector2(300.0, 349.0), 2 if frame_number % 9 in [2, 3] else 1, -25.0)
	_new_rig(_page, "johnny", "AIM_SHOTGUN", 0.0, 3.4, Vector2(680.0, 349.0), 2 if frame_number % 9 in [2, 3] else (3 if frame_number % 9 in [4, 5, 6] else 1), 20.0)
	_add_label(_page, Vector2(206.0, 296.0), Vector2(190.0, 45.0), "AIM_PISTOL / ChibiWeaponView / 1.85x", 10, Color("8fb4d9"))
	_add_label(_page, Vector2(578.0, 296.0), Vector2(220.0, 45.0), "AIM_SHOTGUN / ChibiWeaponView / 3.4x", 10, Color("8fb4d9"))


func _capture_frame(frame_number: int) -> bool:
	var viewport: Viewport = root
	var viewport_texture: ViewportTexture = viewport.get_texture()
	if viewport_texture == null:
		push_error("[CHIBI R5 ANIMATION CAPTURE] viewport texture unavailable")
		return false
	var image: Image = viewport_texture.get_image()
	if image == null or image.is_empty():
		push_error("[CHIBI R5 ANIMATION CAPTURE] empty viewport image")
		return false
	if image.get_width() != TARGET_SIZE.x or image.get_height() != TARGET_SIZE.y:
		image.resize(TARGET_SIZE.x, TARGET_SIZE.y, Image.INTERPOLATE_NEAREST)
	var path: String = OUTPUT_DIR + ("/frame_%04d.png" % frame_number)
	var err: Error = image.save_png(ProjectSettings.globalize_path(path))
	if err != OK:
		push_error("[CHIBI R5 ANIMATION CAPTURE] save_png failed: " + path + " err=" + str(err))
		return false
	print("[CHIBI R5 ANIMATION CAPTURE] frame=" + str(frame_number) + " source_frame=" + str(frame_number % 9) + " saved=" + path)
	return true
