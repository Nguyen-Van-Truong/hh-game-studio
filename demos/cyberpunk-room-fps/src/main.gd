extends Node3D

const ROUND_SECONDS: float = 60.0

@onready var player: CharacterBody3D = $Player
@onready var hud: CanvasLayer = $HUD
@onready var room_holder: Node3D = $RoomHolder
@onready var collision: Node3D = $Collision
@onready var targets: Node3D = $Targets
@onready var start_sfx: AudioStreamPlayer = $StartSfx

var score: int = 0
var time_left: float = ROUND_SECONDS
var running: bool = false
var paused: bool = false
var round_over: bool = false


func _ready() -> void:
	randomize()
	_instance_room()
	_build_collision()
	_place_player()
	_spawn_targets()
	player.set_play_enabled(false)
	hud.set_score(0)
	hud.set_time(ROUND_SECONDS)
	hud.hide_overlay()
	await get_tree().process_frame
	await get_tree().create_timer(0.4).timeout
	_save_preview()
	hud.show_overlay(
		"NIGHT ROOM FPS",
		"Click to start\nWASD move  •  Mouse look  •  Left click shoot\nSpace jump  •  Shift sprint  •  Esc pause  •  R restart"
	)


func _instance_room() -> void:
	var packed: PackedScene = load("res://assets/environment/gaming_room.glb") as PackedScene
	if packed == null:
		push_warning("gaming_room.glb missing; collision room still playable")
		return
	var room: Node = packed.instantiate()
	room_holder.add_child(room)
	# Blender +Y depth becomes Godot -Z via glTF. Keep importer transform.
	room.position = Vector3.ZERO
	_prepare_imported_room(room)


func _prepare_imported_room(room: Node) -> void:
	var stack: Array[Node] = [room]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		for child in n.get_children():
			stack.append(child)
		var node_name := String(n.name)
		if node_name.begins_with("HorizonGlow") or node_name.begins_with("Win_"):
			n.visible = false
			continue
		var light := n as Light3D
		if light:
			light.visible = false
			light.light_energy = 0.0
			continue
		var mi := n as MeshInstance3D
		if mi:
			_clamp_mesh_emission(mi)


func _clamp_mesh_emission(mi: MeshInstance3D) -> void:
	if mi.mesh == null:
		return
	var seen: Dictionary = {}
	for i in mi.mesh.get_surface_count():
		var mat: Material = mi.get_active_material(i)
		if mat == null or seen.has(mat):
			continue
		seen[mat] = true
		_clamp_material(mat)


func _clamp_material(mat: Material) -> void:
	var base := mat as BaseMaterial3D
	if base == null:
		return
	if base.emission_enabled:
		base.emission_energy_multiplier = clampf(base.emission_energy_multiplier * 0.06, 0.0, 0.45)
		var e: Color = base.emission
		base.emission = Color(e.r * 0.65, e.g * 0.65, e.b * 0.65, e.a)


func _add_box(pos: Vector3, size: Vector3) -> void:
	var body := StaticBody3D.new()
	body.collision_layer = 1
	body.collision_mask = 0
	body.position = pos
	var col := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	col.shape = shape
	body.add_child(col)
	collision.add_child(body)


func _build_collision() -> void:
	# Godot Y-up: Blender (x, y, z) ≈ Godot (x, z, -y)
	# Room 5 x 4 x 2.68, door near x=1, y=0
	_add_box(Vector3(2.5, -0.05, -2.0), Vector3(5.2, 0.10, 4.2))
	_add_box(Vector3(2.5, 2.73, -2.0), Vector3(5.2, 0.10, 4.2))
	_add_box(Vector3(-0.05, 1.34, -2.0), Vector3(0.12, 2.68, 4.2))
	_add_box(Vector3(5.05, 1.34, -2.0), Vector3(0.12, 2.68, 4.2))
	_add_box(Vector3(2.5, 1.34, 0.06), Vector3(5.2, 2.68, 0.12))
	# Back wall with window gap: left / right / sill / head
	_add_box(Vector3(0.30, 1.34, -4.06), Vector3(0.72, 2.68, 0.12))
	_add_box(Vector3(4.20, 1.34, -4.06), Vector3(1.72, 2.68, 0.12))
	_add_box(Vector3(2.05, 0.45, -4.06), Vector3(2.70, 0.90, 0.12))
	_add_box(Vector3(2.05, 2.44, -4.06), Vector3(2.70, 0.48, 0.12))
	# Desk (main + return)
	_add_box(Vector3(1.80, 0.37, -3.42), Vector3(2.75, 0.74, 0.72))
	_add_box(Vector3(0.55, 0.37, -2.45), Vector3(0.70, 0.74, 1.55))
	# Bed
	_add_box(Vector3(4.22, 0.30, -1.55), Vector3(1.42, 0.60, 2.05))
	# Chair
	_add_box(Vector3(1.85, 0.45, -2.42), Vector3(0.50, 0.90, 0.50))


func _place_player() -> void:
	player.global_position = Vector3(1.05, 0.05, -0.70)
	player.look_at(Vector3(1.90, player.global_position.y, -3.20), Vector3.UP)


func _spawn_targets() -> void:
	var packed: PackedScene = load("res://scenes/target.tscn") as PackedScene
	var spots: Array[Vector3] = [
		Vector3(1.05, 1.35, -3.20),
		Vector3(1.85, 1.40, -3.25),
		Vector3(2.65, 1.35, -3.20),
		Vector3(0.55, 1.55, -2.15),
		Vector3(3.55, 1.70, -3.70),
		Vector3(4.20, 1.25, -2.60),
		Vector3(3.90, 1.10, -1.20),
		Vector3(0.35, 1.70, -1.35),
	]
	for i in spots.size():
		var t: RangeTarget = packed.instantiate() as RangeTarget
		t.position = spots[i]
		t.points = 100 + i * 25
		t.destroyed.connect(_on_target_destroyed)
		targets.add_child(t)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("pause"):
		_toggle_pause()
		return
	if event.is_action_pressed("restart"):
		_restart()
		return
	if not running and not round_over and not paused and event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT:
			_start_round()


func _process(delta: float) -> void:
	if not running or paused:
		return
	time_left -= delta
	hud.set_time(time_left)
	if time_left <= 0.0:
		_end_round()


func _save_preview() -> void:
	var tex := get_viewport().get_texture()
	if tex == null:
		return
	var img := tex.get_image()
	if img == null:
		return
	var path := ProjectSettings.globalize_path("res://preview_play.png")
	var err := img.save_png(path)
	print("PREVIEW_PNG=", path, " err=", err)


func _start_round() -> void:
	if running:
		return
	running = true
	paused = false
	round_over = false
	score = 0
	time_left = ROUND_SECONDS
	hud.set_score(0)
	hud.set_time(ROUND_SECONDS)
	hud.hide_overlay()
	hud.set_hint("Shoot the glowing orbs  •  Esc pause")
	player.set_play_enabled(true)
	if start_sfx.stream:
		start_sfx.play()


func _toggle_pause() -> void:
	if not running and not round_over:
		return
	if round_over:
		return
	paused = not paused
	get_tree().paused = paused
	player.set_play_enabled(not paused)
	if paused:
		hud.show_overlay("PAUSED", "Click the game, Esc to resume  •  R restart")
	else:
		hud.hide_overlay()
		player.set_play_enabled(true)


func _end_round() -> void:
	running = false
	round_over = true
	time_left = 0.0
	hud.set_time(0.0)
	player.set_play_enabled(false)
	hud.show_overlay("TIME UP", "Score  %d\nR to play again  •  Esc then close window to quit" % score)


func _restart() -> void:
	get_tree().paused = false
	get_tree().reload_current_scene()


func _on_target_destroyed(target: RangeTarget) -> void:
	if not running:
		return
	score += target.points
	hud.set_score(score)
	hud.flash_hit()
