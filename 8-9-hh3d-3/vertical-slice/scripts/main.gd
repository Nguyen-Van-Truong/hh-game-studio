extends Node2D

## Small playable 2D slice. Gameplay is Godot-owned; Blender assets are an
## independent import step and are never used as acceptance for GT06.

const VIEW_SIZE := Vector2(960.0, 540.0)
const FLOOR_Y := 465.0
const GRAVITY := 1250.0
const MOVE_SPEED := 250.0
const JUMP_SPEED := -520.0
const PLAYER_SIZE := Vector2(28.0, 44.0)
const SAVE_PATH := "user://hh3d_vertical_slice_save.json"
const TEST_SAVE_PATH := "user://hh3d_vertical_slice_test_save.json"
const SAVE_BACKUP_SUFFIX := ".bak"
const PLATFORM_RECTS: Array[Rect2] = [
	Rect2(65.0, FLOOR_Y - 148.0, 180.0, 12.0),
	Rect2(355.0, FLOOR_Y - 92.0, 250.0, 12.0),
]

var player_position := Vector2(150.0, FLOOR_Y - PLAYER_SIZE.y * 0.5)
var player_velocity := Vector2.ZERO
var facing := 1.0
var health := 3
var score := 0
var paused := false
var pickup_collected := false
var enemies: Array[Dictionary] = []
var bullets: Array[Dictionary] = []
var message := ""
var message_time := 0.0
var smoke_time := -1.0
var game_state := "playing"
var invulnerability_time := 0.0
var asset_visual_ready := false
var asset_mesh_count := 0
var asset_container: SubViewportContainer
var asset_viewport: SubViewport
var asset_model: Node3D
var active_save_path := SAVE_PATH
var runtime_tick := 0

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	if _has_arg("--integration-test"):
		active_save_path = TEST_SAVE_PATH
	reset_game()
	_ensure_asset_visual()
	if _has_arg("--deterministic-test"):
		_run_deterministic_test()
		return
	if _has_arg("--asset-test"):
		_run_asset_test()
		return
	if _has_arg("--gameplay-test"):
		await _run_gameplay_test()
		return
	if _has_arg("--integration-test"):
		_run_integration_test()
		return
	if _has_arg("--smoke-test"):
		smoke_time = 2.0
	queue_redraw()

func _physics_process(delta: float) -> void:
	runtime_tick += 1
	if smoke_time >= 0.0:
		smoke_time -= delta
		if smoke_time <= 0.0:
			print("SMOKE_PASS score=%d health=%d" % [score, health])
			get_tree().quit(0)
			return
	if invulnerability_time > 0.0:
		invulnerability_time -= delta
	if not paused and game_state == "playing":
		_step_gameplay(delta, _read_axis(), _read_jump(), _read_fire())
	if message_time > 0.0:
		message_time -= delta
	queue_redraw()

func _unhandled_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	match event.keycode:
		KEY_P:
			_apply_command("pause")
		KEY_R:
			_apply_command("restart")
		KEY_S:
			save_game()
		KEY_L:
			load_game()

func _read_axis() -> float:
	var axis := Input.get_axis("move_left", "move_right")
	if axis == 0.0:
		axis = float(Input.is_key_pressed(KEY_D)) - float(Input.is_key_pressed(KEY_A))
	return axis

func _read_jump() -> bool:
	return Input.is_action_just_pressed("jump") or Input.is_key_pressed(KEY_W)

func _read_fire() -> bool:
	return Input.is_action_just_pressed("fire") or Input.is_key_pressed(KEY_F)

func _step_gameplay(delta: float, axis: float, jump_pressed: bool, fire_pressed: bool) -> void:
	_update_player(delta, axis, jump_pressed, fire_pressed)
	_update_bullets(delta)
	_update_enemies(delta)
	_check_pickup()
	if enemies.is_empty() and game_state == "playing":
		game_state = "won"
		message = "ROUND WON - R TO RESTART"
		message_time = 3.0

func _update_player(delta: float, axis: float, jump_pressed: bool, fire_pressed: bool) -> void:
	player_velocity.x = move_toward(player_velocity.x, axis * MOVE_SPEED, 1200.0 * delta)
	if axis != 0.0:
		facing = sign(axis)
	if jump_pressed and _is_grounded():
		player_velocity.y = JUMP_SPEED
	player_velocity.y += GRAVITY * delta
	var previous_position := player_position
	player_position += player_velocity * delta
	player_position.x = clamp(player_position.x, 25.0, VIEW_SIZE.x - 25.0)
	if player_position.y >= FLOOR_Y - PLAYER_SIZE.y * 0.5:
		player_position.y = FLOOR_Y - PLAYER_SIZE.y * 0.5
		player_velocity.y = 0.0
	for platform in PLATFORM_RECTS:
		var platform_top := platform.position.y - PLAYER_SIZE.y * 0.5
		var was_above := previous_position.y <= platform_top + 1.0
		var crossed_top := player_position.y >= platform_top and player_velocity.y >= 0.0
		var overlaps_x := player_position.x + PLAYER_SIZE.x * 0.5 > platform.position.x and player_position.x - PLAYER_SIZE.x * 0.5 < platform.end.x
		if was_above and crossed_top and overlaps_x:
			player_position.y = platform_top
			player_velocity.y = 0.0
	if fire_pressed:
		_fire()

func _is_grounded() -> bool:
	if player_position.y >= FLOOR_Y - PLAYER_SIZE.y * 0.5 - 1.0:
		return true
	for platform in PLATFORM_RECTS:
		if abs(player_position.y - (platform.position.y - PLAYER_SIZE.y * 0.5)) <= 1.0 and player_position.x + PLAYER_SIZE.x * 0.5 > platform.position.x and player_position.x - PLAYER_SIZE.x * 0.5 < platform.end.x:
			return true
	return false

func _fire() -> void:
	if bullets.size() >= 12:
		return
	bullets.append({"position": player_position + Vector2(facing * 24.0, -8.0), "velocity": Vector2(facing * 620.0, 0.0)})

func _update_bullets(delta: float) -> void:
	for i in range(bullets.size() - 1, -1, -1):
		var bullet: Dictionary = bullets[i]
		bullet["position"] = bullet["position"] + bullet["velocity"] * delta
		var remove_bullet: bool = bullet["position"].x < -10.0 or bullet["position"].x > VIEW_SIZE.x + 10.0
		for j in range(enemies.size() - 1, -1, -1):
			if bullet["position"].distance_to(enemies[j]["position"]) < 24.0:
				enemies.remove_at(j)
				score += 10
				remove_bullet = true
				break
		if remove_bullet:
			bullets.remove_at(i)
		else:
			bullets[i] = bullet

func _update_enemies(delta: float) -> void:
	for i in range(enemies.size() - 1, -1, -1):
		var enemy: Dictionary = enemies[i]
		var direction: float = sign(player_position.x - enemy["position"].x)
		enemy["position"].x += direction * 28.0 * delta
		enemy["phase"] += delta
		if enemy["position"].distance_to(player_position) < 28.0 and invulnerability_time <= 0.0:
			health = max(0, health - 1)
			invulnerability_time = 0.75
			enemy["position"] = Vector2(720.0 + i * 50.0, FLOOR_Y - 20.0)
			message = "HIT"
			message_time = 0.5
			if health == 0:
				game_state = "lost"
				message = "ROUND LOST - R TO RESTART"
				message_time = 3.0
		enemies[i] = enemy

func _check_pickup() -> void:
	if not pickup_collected and player_position.distance_to(Vector2(480.0, FLOOR_Y - 24.0)) < 35.0:
		pickup_collected = true
		score += 25
		message = "PICKUP +25"
		message_time = 1.5

func reset_game() -> void:
	player_position = Vector2(150.0, FLOOR_Y - PLAYER_SIZE.y * 0.5)
	player_velocity = Vector2.ZERO
	facing = 1.0
	health = 3
	score = 0
	paused = false
	game_state = "playing"
	invulnerability_time = 0.0
	pickup_collected = false
	bullets.clear()
	enemies = [
		{"position": Vector2(650.0, FLOOR_Y - 20.0), "phase": 0.0},
		{"position": Vector2(780.0, FLOOR_Y - 20.0), "phase": 1.0},
	]

func _apply_command(command: String) -> void:
	match command:
		"pause":
			if game_state == "playing":
				paused = not paused
				message = "PAUSED" if paused else "RUNNING"
				message_time = 1.5
		"restart":
			reset_game()
			message = "RESTARTED"
			message_time = 1.5

func _recover_save_transaction() -> bool:
	var save_absolute := ProjectSettings.globalize_path(active_save_path)
	var backup_absolute := save_absolute + SAVE_BACKUP_SUFFIX
	var temp_absolute := save_absolute + ".tmp"
	if not FileAccess.file_exists(save_absolute) and FileAccess.file_exists(backup_absolute):
		if DirAccess.rename_absolute(backup_absolute, save_absolute) != OK:
			return false
	if FileAccess.file_exists(save_absolute) and FileAccess.file_exists(backup_absolute):
		DirAccess.remove_absolute(backup_absolute)
	if FileAccess.file_exists(save_absolute) and FileAccess.file_exists(temp_absolute):
		DirAccess.remove_absolute(temp_absolute)
	return true

func _replace_save_transaction(temp_absolute: String, save_absolute: String) -> bool:
	var backup_absolute := save_absolute + SAVE_BACKUP_SUFFIX
	var had_save := FileAccess.file_exists(save_absolute)
	if had_save and DirAccess.rename_absolute(save_absolute, backup_absolute) != OK:
		return false
	if DirAccess.rename_absolute(temp_absolute, save_absolute) == OK:
		if had_save and FileAccess.file_exists(backup_absolute):
			DirAccess.remove_absolute(backup_absolute)
		return true
	if had_save and not FileAccess.file_exists(save_absolute):
		DirAccess.rename_absolute(backup_absolute, save_absolute)
	return false

func save_game() -> bool:
	if not _recover_save_transaction():
		message = "SAVE FAILED"
		message_time = 1.5
		return false
	var temp_path := active_save_path + ".tmp"
	var file := FileAccess.open(temp_path, FileAccess.WRITE)
	if file == null:
		message = "SAVE FAILED"
		message_time = 1.5
		return false
	file.store_string(JSON.stringify({
		"version": 1,
		"player_position": [player_position.x, player_position.y],
		"player_velocity": [player_velocity.x, player_velocity.y],
		"facing": facing,
		"health": health,
		"score": score,
		"pickup_collected": pickup_collected,
		"game_state": game_state,
	}))
	file.flush()
	file.close()
	var temp_absolute := ProjectSettings.globalize_path(temp_path)
	var save_absolute := ProjectSettings.globalize_path(active_save_path)
	if not _replace_save_transaction(temp_absolute, save_absolute):
		message = "SAVE FAILED"
		message_time = 1.5
		return false
	message = "SAVED"
	message_time = 1.5
	return true

func load_game() -> bool:
	if not _recover_save_transaction():
		return false
	if not FileAccess.file_exists(active_save_path):
		message = "NO SAVE"
		message_time = 1.5
		return false
	var file := FileAccess.open(active_save_path, FileAccess.READ)
	var parser := JSON.new()
	var parse_error := parser.parse(file.get_as_text())
	file.close()
	if parse_error != OK:
		return false
	var data = parser.data
	if not data is Dictionary or data.get("version", 0) != 1:
		return false
	var saved_position = data.get("player_position", null)
	if not saved_position is Array or saved_position.size() != 2:
		return false
	var saved_velocity = data.get("player_velocity", null)
	if not saved_velocity is Array or saved_velocity.size() != 2:
		return false
	if not data.has_all(["facing", "health", "score", "pickup_collected", "game_state"]):
		return false
	player_position = Vector2(float(saved_position[0]), float(saved_position[1]))
	player_velocity = Vector2(float(saved_velocity[0]), float(saved_velocity[1]))
	facing = float(data["facing"])
	health = int(data["health"])
	score = int(data["score"])
	pickup_collected = bool(data["pickup_collected"])
	game_state = str(data["game_state"])
	message = "LOADED"
	message_time = 1.5
	return true

func _run_asset_test() -> void:
	if not asset_visual_ready or asset_container == null or asset_viewport == null or asset_model == null:
		print("ASSET_FAIL runtime_visual_not_ready")
		get_tree().quit(1)
		return
	if asset_mesh_count < 2:
		print("ASSET_FAIL mesh_count=%d" % asset_mesh_count)
		get_tree().quit(1)
		return
	print("ASSET_RUNTIME_PASS mesh_count=%d" % asset_mesh_count)
	get_tree().quit(0)

func _ensure_asset_visual() -> void:
	var asset := ResourceLoader.load("res://assets/pickup_original.glb")
	if asset == null or not asset is PackedScene:
		return
	var instance := (asset as PackedScene).instantiate()
	var mesh_count := 0
	for node in instance.find_children("*", "MeshInstance3D", true, false):
		mesh_count += 1
	if mesh_count < 2:
		instance.free()
		return
	asset_model = instance
	asset_mesh_count = mesh_count
	asset_viewport = SubViewport.new()
	asset_viewport.size = Vector2i(96, 96)
	asset_viewport.transparent_bg = true
	asset_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	asset_container = SubViewportContainer.new()
	asset_container.position = Vector2(432.0, FLOOR_Y - 72.0)
	asset_container.size = Vector2(96.0, 96.0)
	asset_container.stretch = true
	asset_container.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(asset_container)
	asset_container.add_child(asset_viewport)
	var camera := Camera3D.new()
	camera.position = Vector3(0.0, 0.0, 4.0)
	camera.current = true
	camera.look_at_from_position(camera.position, Vector3.ZERO)
	asset_viewport.add_child(camera)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-35.0, -25.0, 0.0)
	light.light_energy = 2.0
	asset_viewport.add_child(light)
	asset_viewport.add_child(asset_model)
	asset_visual_ready = true

func _run_deterministic_test() -> void:
	var input_trace: Array[int] = []
	for frame in range(180):
		var direction_code: int = 2 if (frame / 30) % 2 == 0 else 0
		var action: int = direction_code
		if frame == 30 or frame == 90:
			action |= 4
		if frame % 45 == 0:
			action |= 8
		input_trace.append(action)
	var first := _trace_digest(input_trace)
	var second := _trace_digest(input_trace)
	if first != second:
		print("DETERMINISTIC_FAIL first=%s second=%s" % [first, second])
		get_tree().quit(1)
		return
	print("DETERMINISTIC_PASS digest=%s" % first)
	get_tree().quit(0)

func _trace_digest(input_trace: Array[int]) -> String:
	reset_game()
	var snapshots := ""
	for frame in range(input_trace.size()):
		var action: int = input_trace[frame]
		var axis: float = float((action & 3) - 1)
		_step_gameplay(1.0 / 60.0, axis, (action & 4) != 0, (action & 8) != 0)
		snapshots += "%d:%.3f,%.3f,%.3f,%d,%d,%d,%s;" % [frame, player_position.x, player_position.y, player_velocity.y, health, score, enemies.size(), game_state]
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(snapshots.to_utf8_buffer())
	return context.finish().hex_encode()

func _send_key(keycode: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.pressed = true
	_unhandled_input(event)

func _run_gameplay_test() -> void:
	reset_game()
	player_position = Vector2(150.0, PLATFORM_RECTS[0].position.y - PLAYER_SIZE.y * 0.5 - 30.0)
	player_velocity = Vector2(0.0, 100.0)
	for _frame in range(60):
		_step_gameplay(1.0 / 60.0, 0.0, false, false)
	var platform_landed: bool = abs(player_position.y - (PLATFORM_RECTS[0].position.y - PLAYER_SIZE.y * 0.5)) < 0.1

	reset_game()
	player_position = Vector2(480.0, FLOOR_Y - PLAYER_SIZE.y * 0.5)
	_step_gameplay(1.0 / 60.0, 0.0, false, false)
	var pickup_collected_ok: bool = pickup_collected and score == 25

	reset_game()
	var before_pause := player_position
	var before_pause_velocity := player_velocity
	_send_key(KEY_P)
	var tick_before_pause := runtime_tick
	for _frame in range(4):
		await get_tree().physics_frame
	var runtime_advanced: bool = runtime_tick > tick_before_pause
	var pause_frozen: bool = paused and runtime_advanced and player_position == before_pause and player_velocity == before_pause_velocity
	_send_key(KEY_P)

	reset_game()
	player_position = Vector2(500.0, FLOOR_Y - PLAYER_SIZE.y * 0.5)
	enemies = [
		{"position": Vector2(650.0, FLOOR_Y - 20.0), "phase": 0.0},
		{"position": Vector2(780.0, FLOOR_Y - 20.0), "phase": 1.0},
	]
	for _frame in range(240):
		_step_gameplay(1.0 / 60.0, 0.0, false, true)
		if game_state == "won":
			break
	var won: bool = game_state == "won"
	_send_key(KEY_R)
	var won_restart: bool = won and game_state == "playing" and enemies.size() == 2 and score == 0

	reset_game()
	health = 1
	enemies[0]["position"] = player_position
	_step_gameplay(1.0 / 60.0, 0.0, false, false)
	var lost: bool = game_state == "lost"
	_send_key(KEY_R)
	var lost_restart: bool = lost and game_state == "playing" and health == 3

	if not platform_landed or not pickup_collected_ok or not pause_frozen or not won_restart or not lost_restart:
		print("GAMEPLAY_FAIL platform=%s pickup=%s pause=%s won_restart=%s lost_restart=%s" % [platform_landed, pickup_collected_ok, pause_frozen, won_restart, lost_restart])
		get_tree().quit(1)
		return
	print("GAMEPLAY_PASS platform_landed=%s pickup=%s pause_frozen=%s runtime_advanced=%s won_restart=%s lost_restart=%s" % [platform_landed, pickup_collected_ok, pause_frozen, runtime_advanced, won_restart, lost_restart])
	get_tree().quit(0)

func _run_integration_test() -> void:
	player_position = Vector2(333.0, FLOOR_Y - PLAYER_SIZE.y * 0.5)
	score = 75
	health = 2
	pickup_collected = true
	if not save_game():
		get_tree().quit(1)
		return
	player_position = Vector2.ZERO
	score = 0
	health = 0
	pickup_collected = false
	var loaded := load_game()
	if not loaded or player_position != Vector2(333.0, FLOOR_Y - PLAYER_SIZE.y * 0.5) or score != 75 or health != 2 or not pickup_collected:
		print("SAVE_LOAD_FAIL")
		get_tree().quit(1)
		return
	var save_absolute := ProjectSettings.globalize_path(active_save_path)
	var backup_absolute := save_absolute + SAVE_BACKUP_SUFFIX
	if DirAccess.rename_absolute(save_absolute, backup_absolute) != OK:
		print("SAVE_LOAD_FAIL backup_prepare")
		get_tree().quit(1)
		return
	var recovered_from_backup := load_game()
	if not recovered_from_backup or player_position != Vector2(333.0, FLOOR_Y - PLAYER_SIZE.y * 0.5) or score != 75 or health != 2 or not pickup_collected:
		print("SAVE_LOAD_FAIL backup_recovery")
		get_tree().quit(1)
		return
	var malformed := FileAccess.open(active_save_path, FileAccess.WRITE)
	malformed.store_string("{malformed")
	malformed.close()
	var malformed_rejected := not load_game()
	for suffix in ["", ".tmp", SAVE_BACKUP_SUFFIX]:
		DirAccess.remove_absolute(ProjectSettings.globalize_path(active_save_path + suffix))
	if not malformed_rejected:
		print("SAVE_LOAD_FAIL malformed_save_accepted")
		get_tree().quit(1)
		return
	print("SAVE_LOAD_PASS position=%s score=%d health=%d malformed_rejected=%s backup_recovered=%s" % [player_position, score, health, malformed_rejected, recovered_from_backup])
	get_tree().quit(0)

func _has_arg(value: String) -> bool:
	return value in OS.get_cmdline_args()

func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, VIEW_SIZE), Color("101727"))
	draw_rect(Rect2(0.0, FLOOR_Y, VIEW_SIZE.x, VIEW_SIZE.y - FLOOR_Y), Color("1d3950"))
	draw_rect(Rect2(0.0, FLOOR_Y - 4.0, VIEW_SIZE.x, 4.0), Color("69d5c5"))
	draw_rect(Rect2(355.0, FLOOR_Y - 92.0, 250.0, 12.0), Color("315b72"))
	draw_rect(Rect2(65.0, FLOOR_Y - 148.0, 180.0, 12.0), Color("315b72"))
	if not pickup_collected:
		draw_circle(Vector2(480.0, FLOOR_Y - 24.0), 13.0, Color("ffd166"))
		draw_circle(Vector2(480.0, FLOOR_Y - 24.0), 6.0, Color("fff1a8"))
	for enemy in enemies:
		var ep: Vector2 = enemy["position"]
		draw_circle(ep, 18.0, Color("ef476f"))
		draw_line(ep + Vector2(-8.0, -4.0), ep + Vector2(-3.0, 2.0), Color.WHITE, 2.0)
		draw_line(ep + Vector2(8.0, -4.0), ep + Vector2(3.0, 2.0), Color.WHITE, 2.0)
	for bullet in bullets:
		draw_circle(bullet["position"], 5.0, Color("f8f9fa"))
	draw_rect(Rect2(player_position - PLAYER_SIZE * 0.5, PLAYER_SIZE), Color("48cae4"))
	draw_rect(Rect2(player_position + Vector2(facing * 9.0 - 3.0, -8.0), Vector2(6.0, 6.0)), Color("caf0f8"))
	var font := ThemeDB.fallback_font
	draw_string(font, Vector2(24.0, 34.0), "HH3D VERTICAL SLICE", HORIZONTAL_ALIGNMENT_LEFT, -1.0, 22, Color("caf0f8"))
	draw_string(font, Vector2(24.0, 62.0), "A/D move  W/Space jump  F fire  P pause  R restart  S/L save/load", HORIZONTAL_ALIGNMENT_LEFT, -1.0, 15, Color("90e0ef"))
	draw_string(font, Vector2(24.0, 92.0), "HP %d   SCORE %d" % [health, score], HORIZONTAL_ALIGNMENT_LEFT, -1.0, 19, Color("ffd166"))
	if paused:
		draw_rect(Rect2(0.0, 0.0, VIEW_SIZE.x, VIEW_SIZE.y), Color(0.02, 0.04, 0.08, 0.58))
		draw_string(font, Vector2(420.0, 270.0), "PAUSED", HORIZONTAL_ALIGNMENT_LEFT, -1.0, 32, Color.WHITE)
	if message_time > 0.0:
		draw_string(font, Vector2(390.0, 125.0), message, HORIZONTAL_ALIGNMENT_LEFT, -1.0, 22, Color("fff1a8"))
