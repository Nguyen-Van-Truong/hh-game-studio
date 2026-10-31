extends SceneTree
## Chibi R5 diagnostic contact-sheet capture.
##
## The launcher runs this diagnostic hidden/offscreen.  The only output is a
## viewport image written to res://docs/chibi-r5; this script never drives a
## desktop window or uses cursor/UI automation.  Every cell contains an actual
## FighterRigView under a generic presentation wrapper.

const TARGET_SIZE: Vector2i = Vector2i(1280, 720)
const OUTPUT_DIR: String = "res://docs/chibi-r5"
const RegistryScript: Script = preload("res://game/core/sf_data_registry.gd")
const FighterRigViewScript: Script = preload("res://game/fighter/fighter_rig_view.gd")
const ActionPoseScript: Script = preload("res://game/fighter/chibi_action_pose.gd")

const PAGE_FILES: Array[String] = [
	"01_punches_diagnostic.png",
	"02_guns_diagnostic.png",
	"03_actions_diagnostic.png",
	"04_roster_diagnostic.png",
]

const ROSTER: Array[String] = [
	"johnny", "boris", "agent", "hideki", "blaire", "savage", "cruger", "ivan", "brody", "mac", "billy",
	"scott", "funnyman", "jeff", "goku", "luffy", "naruto", "saitama", "solaria", "atlas", "shinobi", "tideweaver",
]

const FIREARM_AIM_STATES: Array[String] = [
	"AIM_PISTOL", "AIM_MAGNUM", "AIM_RIFLE", "AIM_UZI",
	"AIM_SHOTGUN", "AIM_SNIPER", "AIM_BAZOOKA", "AIM_FLAMETHROWER",
]

var _reg: Node = null
var _page: Node2D = null
var _page_idx: int = -1
var _wait_frames: int = 0
var _failures: int = 0


func _process(_delta: float) -> bool:
	if _page_idx < 0:
		_prepare_root()
		_reg = _load_registry()
		_page_idx = 0
		_build_page(_page_idx)
		_wait_frames = 4
		return false

	_wait_frames -= 1
	if _wait_frames > 0:
		return false
	if not _capture_page(_page_idx):
		_failures += 1
		quit(1)
		return true

	if _page != null:
		_page.queue_free()
		_page = null
	_page_idx += 1
	if _page_idx >= PAGE_FILES.size():
		print("[CHIBI R5 CAPTURE] PASS: wrote " + str(PAGE_FILES.size()) + " diagnostic viewport contact sheets to " + OUTPUT_DIR)
		quit(0)
		return true
	_build_page(_page_idx)
	_wait_frames = 4
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
	created.name = "ChibiR5CaptureRegistry"
	root.add_child(created)
	if created.has_method("ensure_loaded"):
		created.call("ensure_loaded")
	return created


func _new_rig(parent: Node, char_id: String, state_name: String, frame: int, facing: int, pitch: float, scale_value: float, source_frame: float = 0.0) -> Node:
	# FighterRigView.set_facing() owns its own scale and resets it during
	# apply_rig_state().  Keep the contact-sheet zoom on a generic wrapper so
	# it cannot be lost when the rig applies a state or facing.
	var wrapper := Node2D.new()
	wrapper.name = "RigCell_" + char_id + "_" + state_name + "_" + str(facing)
	wrapper.scale = Vector2(scale_value, scale_value)
	parent.add_child(wrapper)
	var rig: Node = FighterRigViewScript.new() as Node
	rig.name = "FighterRigView"
	rig.set("registry_override", _reg)
	rig.set("chibi_brawler_enabled", true)
	wrapper.add_child(rig)
	rig.call("apply_rig_state", char_id, state_name, frame, facing, pitch, frame, 100.0, 100.0, 0.0, false, false, 0.0, false, source_frame)
	return wrapper


func _add_background(page: Node2D, title: String, subtitle: String) -> void:
	var bg := ColorRect.new()
	bg.name = "DiagnosticDarkBackground"
	bg.position = Vector2.ZERO
	bg.size = Vector2(TARGET_SIZE)
	bg.color = Color("101522")
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	page.add_child(bg)
	_add_label(page, Vector2(24.0, 10.0), Vector2(1230.0, 28.0), "CHIBI R5 DIAGNOSTIC  /  " + title, 21, Color("f5d68b"))
	_add_label(page, Vector2(26.0, 38.0), Vector2(1230.0, 20.0), subtitle, 11, Color("a8bfdc"))


func _add_label(parent: Node, at: Vector2, size: Vector2, text_value: String, font_size: int, color: Color = Color.WHITE) -> Label:
	var label := Label.new()
	label.position = at
	label.size = size
	label.text = text_value
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.add_theme_color_override("font_shadow_color", Color(0.0, 0.0, 0.0, 0.85))
	label.add_theme_constant_override("shadow_offset_x", 1)
	label.add_theme_constant_override("shadow_offset_y", 1)
	label.z_index = 20
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(label)
	return label


func _add_cell_background(parent: Node, at: Vector2, size: Vector2, tint: Color) -> void:
	var cell := ColorRect.new()
	cell.position = at
	cell.size = size
	cell.color = tint
	cell.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(cell)


func _pose_caption(state_name: String, frame: int, pitch: float, source_frame: float) -> String:
	var pose: Dictionary = ActionPoseScript.sample(state_name, frame, pitch, false, source_frame)
	return state_name + "\n" + str(pose.get("family", "idle")) + " / " + str(pose.get("phase", "hold")) + "\ncontact=" + str(bool(pose.get("contact", false)))


func _add_rig_cell(page: Node2D, cell_at: Vector2, cell_size: Vector2, char_id: String, state_name: String, frame: int, facing: int, pitch: float, scale_value: float, source_frame: float, caption: String) -> void:
	_add_cell_background(page, cell_at, cell_size, Color("172238") if int(cell_at.x / 20.0) % 2 == 0 else Color("1b2940"))
	var rig: Node = _new_rig(page, char_id, state_name, frame, facing, pitch, scale_value, source_frame)
	rig.position = cell_at + Vector2(cell_size.x * 0.5, cell_size.y - 18.0)
	_add_label(page, cell_at + Vector2(7.0, 5.0), Vector2(cell_size.x - 12.0, cell_size.y - 8.0), caption, 11, Color("e7edf8"))


func _build_page(page_index: int) -> void:
	_page = Node2D.new()
	_page.name = "ChibiR5DiagnosticPage" + str(page_index + 1)
	root.add_child(_page)
	match page_index:
		0:
			_build_punch_page(_page)
		1:
			_build_gun_page(_page)
		2:
			_build_action_page(_page)
		3:
			_build_roster_page(_page)


func _build_punch_page(page: Node2D) -> void:
	_add_background(page, "THREE PUNCHES", "9 actual FighterRigView cells | enlarged 6x | windup / contact / recovery | diagnostic art reference")
	var states: Array[String] = ["PUNCH_01", "PUNCH_02", "PUNCH_03"]
	var hits: Array[float] = [3.0, 3.5, 4.0]
	var phases: Array[String] = ["WINDUP", "CONTACT", "RECOVERY"]
	var cell_size := Vector2(412.0, 205.0)
	for row: int in range(3):
		for col: int in range(3):
			var state_name: String = states[row]
			var source_frame: float = hits[row] - 1.0 if col == 0 else (hits[row] if col == 1 else hits[row] + 2.0)
			var cell_at := Vector2(float(col) * cell_size.x + 8.0, 67.0 + float(row) * cell_size.y)
			var caption: String = state_name + "  " + phases[col] + "\n" + _pose_caption(state_name, 1, 0.0, source_frame)
			_add_rig_cell(page, cell_at, cell_size - Vector2(8.0, 7.0), "johnny", state_name, 1, 1, 0.0, 6.0, source_frame, caption)


func _aim_states() -> Array[String]:
	var out: Array[String] = []
	var states: Dictionary = _reg.call("get_states") as Dictionary
	for state_name: String in FIREARM_AIM_STATES:
		var value: Variant = states.get(state_name)
		if typeof(value) != TYPE_DICTIONARY:
			continue
		var data: Dictionary = value as Dictionary
		if str(data.get("type", "")) != "split_rig_aim":
			continue
		var arm: Variant = data.get("weapon_arm", {})
		if typeof(arm) != TYPE_DICTIONARY:
			continue
		var aim_frames: Variant = (arm as Dictionary).get("frames", [])
		if typeof(aim_frames) != TYPE_ARRAY or (aim_frames as Array).is_empty():
			continue
		out.append(state_name)
	out.sort()
	return out


func _build_gun_page(page: Node2D) -> void:
	_add_background(page, "AUTHENTIC HELD GUNS", "8 firearm AIM states | two facings | varied pitch | enlarged 4x | source gun-only art + articulated hands")
	var states: Array[String] = _aim_states()
	var cols: int = 4
	var cell_size := Vector2(315.0, 157.0)
	for i: int in range(states.size() * 2):
		var state_name: String = states[int(i / 2)]
		var facing: int = 1 if i % 2 == 0 else -1
		var pitch: float = [-45.0, 0.0, 45.0, 90.0][i % 4]
		var col: int = i % cols
		var row: int = i / cols
		var cell_at := Vector2(float(col) * cell_size.x + 7.0, 65.0 + float(row) * cell_size.y)
		var caption: String = state_name.replace("AIM_", "") + "  F" + str(facing) + "\npitch=" + str(pitch) + "\n" + _pose_caption(state_name, 1, pitch, 0.0)
		_add_rig_cell(page, cell_at, cell_size - Vector2(6.0, 6.0), "johnny", state_name, 1, facing, pitch, 4.0, 0.0, caption)


func _build_action_page(page: Node2D) -> void:
	_add_background(page, "ACTION FAMILIES", "Actual runtime states sampled through ChibiActionPose | locomotion, cover, melee, air, climb and recovery | 3.4x")
	var states: Array[String] = [
		"IDLE", "WALK", "RUN", "SPRINT", "CROUCH", "COVER", "JUMP", "FALL", "DIVE", "ROLL", "KICK", "JUMPKICK",
		"CLIMB", "SLIDE", "LEDGE_GRAB", "PUNCH_01", "PUNCH_02", "PUNCH_03", "MACHETE_01", "AXE_02", "SWORD_02", "BAT_01",
		"CHAINSAW_01", "THROW", "KNOCKDOWN", "GETUP", "HURT", "WIN",
	]
	var cols: int = 7
	var cell_size := Vector2(180.0, 157.0)
	for i: int in range(states.size()):
		var state_name: String = states[i]
		var col: int = i % cols
		var row: int = i / cols
		var cell_at := Vector2(float(col) * cell_size.x + 7.0, 65.0 + float(row) * cell_size.y)
		var frame: int = 2 if state_name not in ["IDLE", "CROUCH", "COVER"] else 1
		var source_frame: float = 3.5 if state_name in ["PUNCH_02", "AXE_02", "SWORD_02"] else 1.0
		var caption: String = _pose_caption(state_name, frame, 0.0, source_frame)
		_add_rig_cell(page, cell_at, cell_size - Vector2(6.0, 6.0), "agent", state_name, frame, 1, 0.0, 3.4, source_frame, caption)


func _build_roster_page(page: Node2D) -> void:
	_add_background(page, "22 CHARACTER DESIGNS / INTERNAL STUDY", "Same articulated Chibi rig | IDLE pose | 5x | diagnostic roster sheet")
	var cols: int = 7
	var cell_size := Vector2(180.0, 157.0)
	for i: int in range(ROSTER.size()):
		var col: int = i % cols
		var row: int = i / cols
		var cell_at := Vector2(float(col) * cell_size.x + 5.0, 67.0 + float(row) * cell_size.y)
		var char_id: String = ROSTER[i]
		_add_rig_cell(page, cell_at, cell_size - Vector2(5.0, 8.0), char_id, "IDLE", 1, 1, 0.0, 5.0, 0.0, char_id.to_upper() + "\nIDLE / idle / hold\ncontact=false")


func _capture_page(page_index: int) -> bool:
	var viewport: Viewport = root
	var viewport_texture: ViewportTexture = viewport.get_texture()
	if viewport_texture == null:
		push_error("[CHIBI R5 CAPTURE] viewport texture unavailable for page " + str(page_index + 1))
		return false
	var image: Image = viewport_texture.get_image()
	if image == null or image.is_empty():
		push_error("[CHIBI R5 CAPTURE] empty viewport image for page " + str(page_index + 1))
		return false
	if image.get_width() != TARGET_SIZE.x or image.get_height() != TARGET_SIZE.y:
		image.resize(TARGET_SIZE.x, TARGET_SIZE.y, Image.INTERPOLATE_NEAREST)
	var out_path: String = OUTPUT_DIR + "/" + PAGE_FILES[page_index]
	var err: Error = image.save_png(ProjectSettings.globalize_path(out_path))
	if err != OK:
		push_error("[CHIBI R5 CAPTURE] save_png failed for " + out_path + " (err=" + str(err) + ")")
		return false
	print("[CHIBI R5 CAPTURE] wrote " + out_path + " [" + str(image.get_width()) + "x" + str(image.get_height()) + "]")
	return true
