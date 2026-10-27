extends Node3D
## GT03 supplies the saved map; GT04 the GLB. Gameplay is consumer application code.
signal frame_advanced
const MAP := "res://input/map.json"
const GLB := "res://input/pickup.glb"
const SPEED := 3.5
const DT := 1.0 / 60.0
const ACTIONS := ["move_left", "move_right", "move_forward", "move_back", "interact", "pause", "save", "load"]
var nodes: Dictionary = {}
var player: MeshInstance3D
var asset: Node3D
var hud: Label
var position_state := Vector3.ZERO
var pickup := Vector3.ZERO
var collected := false
var paused := false
var tick := 0
var frames := 0
var pending: Dictionary = {}
var run_id := "interactive"
var test_mode := false
var ready_world := false
var save_seq := 0
var save_root := ""
var io_message := ""
var checks: Dictionary = {}
var observations: Dictionary = {}

func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg == "--pilot-test": test_mode = true
		elif arg.begins_with("--run-id="): run_id = arg.trim_prefix("--run-id=")
	if not _valid_id(run_id):
		_fail("invalid run id")
		return
	save_root = "user://consumer-pilot/" + run_id
	if not _load_map() or not _build():
		_fail("authored input rejected")
		return
	ready_world = true
	_update_hud()
	if test_mode: call_deferred("_test")

func _valid_id(value: String) -> bool:
	if value.is_empty() or value.length() > 80: return false
	for c in value:
		if not c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-": return false
	return true

func _vector_ok(value: Variant) -> bool:
	if not value is Array or value.size() != 3: return false
	for n in value:
		if not (n is float or n is int) or not is_finite(float(n)): return false
	return true

func _v3(value: Array) -> Vector3:
	return Vector3(float(value[0]), float(value[1]), float(value[2]))

func _load_map() -> bool:
	var parser := JSON.new()
	if parser.parse(FileAccess.get_file_as_string(MAP)) != OK: return false
	var data: Variant = parser.data
	if not data is Dictionary or data.get("schema") != 1 or not data.get("nodes") is Array: return false
	for row in data.nodes:
		if not row is Dictionary or not row.get("stable_id") is String or not row.get("name") is String: return false
		for key in ["position", "rotation_degrees", "scale", "box_size"]:
			if not _vector_ok(row.get(key)): return false
		if nodes.has(row.stable_id): return false
		for size in row.box_size:
			if float(size) <= 0: return false
		nodes[row.stable_id] = row
	return nodes.size() == 3 and nodes.has_all(["floor", "player", "pickup"])

func _box(row: Dictionary, color: Color) -> MeshInstance3D:
	var mesh := BoxMesh.new()
	mesh.size = _v3(row.box_size)
	var visual := MeshInstance3D.new()
	visual.mesh = mesh
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	visual.material_override = material
	visual.position = _v3(row.position)
	visual.rotation_degrees = _v3(row.rotation_degrees)
	visual.scale = _v3(row.scale)
	add_child(visual)
	return visual

func _build() -> bool:
	_box(nodes.floor, Color("33435c"))
	player = _box(nodes.player, Color("56b4e9"))
	position_state = _v3(nodes.player.position)
	pickup = _v3(nodes.pickup.position)
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	if document.append_from_file(GLB, state) != OK: return false
	asset = document.generate_scene(state)
	if asset == null: return false
	add_child(asset)
	var meshes := asset.find_children("*", "MeshInstance3D", true, false)
	if meshes.is_empty(): return false
	# Present the actual authored mesh/material at the GT03 pickup position.
	for mesh in meshes: mesh.transform = Transform3D.IDENTITY
	asset.position = pickup
	asset.scale = Vector3.ONE * 0.25
	observations["asset_meshes"] = meshes.size()
	observations["asset_consumer_transform"] = "mesh local identity; root scale 0.25 at GT03 pickup location"
	var camera := Camera3D.new()
	add_child(camera)
	camera.look_at_from_position(Vector3(0, 7, 9), Vector3.ZERO)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-55, -25, 0)
	add_child(light)
	var canvas := CanvasLayer.new()
	add_child(canvas)
	hud = Label.new()
	hud.position = Vector2(18, 18)
	hud.add_theme_font_size_override("font_size", 20)
	canvas.add_child(hud)
	return true

func _input(event: InputEvent) -> void:
	for action in ["pause", "interact", "save", "load"]:
		if event.is_action_pressed(action) and not event.is_echo(): pending[action] = true

func _physics_process(_delta: float) -> void:
	if not ready_world: return
	frames += 1
	if pending.has("pause"): paused = not paused
	if not paused:
		_step(Input.get_vector("move_left", "move_right", "move_forward", "move_back"), pending.has("interact"))
	if pending.has("save"): io_message = "SAVED" if _save() else "SAVE FAILED"
	if pending.has("load"): io_message = "LOADED" if _restore() else "LOAD REJECTED"
	pending.clear()
	_update_hud()
	frame_advanced.emit()

func _step(axis: Vector2, interact: bool) -> void:
	position_state += Vector3(axis.x, 0, axis.y) * SPEED * DT
	position_state.x = clampf(position_state.x, -5.5, 5.5)
	position_state.z = clampf(position_state.z, -5.5, 5.5)
	if interact and not collected and position_state.distance_to(pickup) <= 1.25: collected = true
	tick += 1
	_present()

func _present() -> void:
	player.position = position_state
	asset.visible = not collected

func _update_hud() -> void:
	hud.text = "HH Consumer Pilot | %s | tick %d | %s\nWASD move | E pickup | Space pause | F5 save | F9 load\n%s" % ["PAUSED" if paused else "RUNNING", tick, "PICKUP ACQUIRED" if collected else "Find the pickup", io_message]

func _snapshot() -> Dictionary:
	return {"schema": 1, "tick": tick, "position": [position_state.x, position_state.y, position_state.z], "collected": collected}

func _valid_state(value: Variant) -> bool:
	return value is Dictionary and value.get("schema") == 1 and _vector_ok(value.get("position")) and value.get("collected") is bool and (value.get("tick") is int or value.get("tick") is float) and is_finite(float(value.tick)) and value.tick >= 0 and value.tick == floor(value.tick)

func _read_save(path: String) -> Dictionary:
	if not FileAccess.file_exists(path): return {}
	var parser := JSON.new()
	if parser.parse(FileAccess.get_file_as_string(path)) != OK or not parser.data is Dictionary: return {}
	var envelope: Dictionary = parser.data
	if not envelope.get("payload") is String or envelope.get("sha256") != envelope.payload.sha256_text(): return {}
	if parser.parse(envelope.payload) != OK or not _valid_state(parser.data): return {}
	return parser.data

func _save() -> bool:
	if DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(save_root)) != OK: return false
	# Immutable generations: prior good saves survive every failed rename/write.
	while FileAccess.file_exists(save_root + "/state-%06d.json" % (save_seq + 1)): save_seq += 1
	var target := save_root + "/state-%06d.json" % (save_seq + 1)
	var payload := JSON.stringify(_snapshot())
	var file := FileAccess.open(target + ".tmp", FileAccess.WRITE)
	if file == null: return false
	file.store_string(JSON.stringify({"payload": payload, "sha256": payload.sha256_text()}))
	file.flush()
	var code := file.get_error()
	file.close()
	if code != OK or _read_save(target + ".tmp").is_empty(): return false
	if DirAccess.rename_absolute(ProjectSettings.globalize_path(target + ".tmp"), ProjectSettings.globalize_path(target)) != OK: return false
	save_seq += 1
	return not _read_save(target).is_empty()

func _restore() -> bool:
	var paths := DirAccess.get_files_at(save_root)
	paths.sort()
	paths.reverse()
	for path in paths:
		if not path.begins_with("state-") or not path.ends_with(".json"): continue
		var state := _read_save(save_root + "/" + path)
		if state.is_empty(): continue
		position_state = _v3(state.position)
		collected = state.collected
		tick = int(state.tick)
		_present()
		return true
	return false

func _event(action: String, pressed: bool) -> void:
	var event := InputEventAction.new()
	event.action = action
	event.pressed = pressed
	event.strength = 1.0 if pressed else 0.0
	Input.parse_input_event(event)

func _frames(count: int) -> void:
	for _i in count: await frame_advanced

func _tap(action: String) -> void:
	_event(action, true)
	await _frames(1)
	_event(action, false)
	await _frames(1)

func _reset_for_replay() -> void:
	for action in ACTIONS: _event(action, false)
	pending.clear()
	paused = false
	tick = 0
	collected = false
	position_state = _v3(nodes.player.position)
	_present()

func _replay_trace(right_frames: int) -> Dictionary:
	_reset_for_replay()
	var rows: Array = []
	for index in 60:
		if index == 0: _event("move_right", true)
		if index == right_frames: _event("move_right", false)
		if index == 40: _event("interact", true)
		if index == 41: _event("interact", false)
		await _frames(1)
		rows.append(_snapshot())
	return {"sha256": JSON.stringify(rows).sha256_text(), "final": _snapshot(), "frames": rows.size()}

func _test() -> void:
	await _frames(2)
	checks["authored_map_loaded"] = nodes.size() == 3
	checks["blender_asset_instantiated"] = observations.asset_meshes > 0
	var start := position_state
	_event("move_right", true)
	await _frames(12)
	_event("move_right", false)
	checks["movement_live_frames"] = position_state.x > start.x + 0.5
	await _tap("pause")
	var frozen := _snapshot()
	var before_frames := frames
	_event("move_right", true)
	await _frames(12)
	_event("move_right", false)
	checks["pause_live_frames"] = paused and _snapshot() == frozen and frames >= before_frames + 12 and "PAUSED" in hud.text
	observations["pause"] = {"before": frozen, "after": _snapshot(), "frames_advanced": frames - before_frames}
	await _tap("pause")
	checks["resume_live_frames"] = not paused and tick > int(frozen.tick)
	_event("move_right", true)
	await _frames(10)
	_event("move_right", false)
	await _tap("interact")
	checks["pickup_and_ui"] = collected and not asset.visible and "PICKUP ACQUIRED" in hud.text
	await _tap("pause")
	await _tap("save")
	var saved := _snapshot()
	checks["save_via_input"] = io_message == "SAVED" and save_seq == 1
	await _tap("pause")
	_event("move_left", true)
	await _frames(5)
	_event("move_left", false)
	await _tap("pause")
	checks["changed_since_save"] = _snapshot() != saved
	await _tap("load")
	checks["load_restores_runtime"] = _snapshot() == saved and io_message == "LOADED"
	await _tap("save")
	var corrupt := FileAccess.open(save_root + "/state-000002.json", FileAccess.WRITE)
	if corrupt == null:
		_fail("cannot prepare corrupt-save negative case")
		return
	corrupt.store_string("{corrupt")
	corrupt.close()
	await _tap("load")
	checks["corrupt_latest_recovers_prior"] = _snapshot() == saved and io_message == "LOADED"
	var first: Dictionary = await _replay_trace(30)
	var second: Dictionary = await _replay_trace(30)
	var changed: Dictionary = await _replay_trace(20)
	observations["replays"] = [first, second, changed]
	checks["deterministic_replay_live_frames"] = first == second and first.sha256 != changed.sha256 and first.final.collected
	var passed := not checks.is_empty()
	for value in checks.values(): passed = passed and value == true
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://out"))
	var report := {"schema": 2, "run_id": run_id, "pid": OS.get_process_id(), "checks": checks, "observations": observations,
		"map_sha256": FileAccess.get_sha256(MAP), "pickup_glb_sha256": FileAccess.get_sha256(GLB),
		"godot_version": Engine.get_version_info().string, "passed": passed, "authority": 0, "gt06_acceptance": false}
	var output := FileAccess.open("res://out/report.json", FileAccess.WRITE)
	if output == null:
		_fail("report write failed")
		return
	output.store_string(JSON.stringify(report, "  "))
	output.close()
	print("HH_CONSUMER_PILOT_PASS" if passed else "HH_CONSUMER_PILOT_FAIL")
	get_tree().quit(0 if passed else 1)

func _fail(reason: String) -> void:
	push_error(reason)
	get_tree().quit(2)