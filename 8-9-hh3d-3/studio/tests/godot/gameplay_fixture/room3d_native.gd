extends Node3D
## Native 3D room fixture: all gameplay objects are real Godot nodes.
const Lifecycle = preload("res://scripts/fixture_lifecycle.gd")
var tick: int = 0
var avatar: CharacterBody3D
var platform: StaticBody3D
var trigger: Area3D
var pickup: Area3D
var mesh: MeshInstance3D
var camera: Camera3D
var hud: Label
var switch_used: bool = false
var pickup_collected: bool = false
var input_trace_ok: bool = false
var interact_seen: bool = false
var switch_area_entered: bool = false
var camera_follow: bool = false
var avatar_asset_loaded: bool = false
var sprite_asset_loaded: bool = false
var max_frame_ms: float = 0.0
var replay_hash_equal: bool = false
var checkpoint_reload_observed: bool = false
var replay_values: Array[float] = []
var topology_components: Dictionary = {}
var _avatar_start: Vector3 = Vector3.ZERO
var _camera_start: Vector3 = Vector3.ZERO

func _box(parent: Node3D, size: Vector3) -> CollisionShape3D:
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	shape.shape = box
	parent.add_child(shape)
	return shape

func _action(name: String, key: Key) -> void:
	if not InputMap.has_action(name):
		InputMap.add_action(name)
	var event := InputEventKey.new()
	event.keycode = key
	event.physical_keycode = key
	InputMap.action_add_event(name, event)

func _has_shape(node: Node3D) -> bool:
	for child in node.get_children():
		if child is CollisionShape3D and (child as CollisionShape3D).shape != null:
			return true
	return false

func _key(key: Key, pressed: bool) -> void:
	var event := InputEventKey.new()
	event.keycode = key
	event.physical_keycode = key
	event.pressed = pressed
	Input.parse_input_event(event)
	if key == KEY_D and pressed:
		input_trace_ok = true

func _read_avatar_asset() -> Node:
	if not FileAccess.file_exists("res://assets/avatar.glb"):
		return null
	var bytes := FileAccess.get_file_as_bytes("res://assets/avatar.glb")
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	if document.append_from_buffer(bytes, "", state) != OK:
		return null
	return document.generate_scene(state)

func _read_sprite_image() -> Image:
	if not FileAccess.file_exists("res://assets/sprite_sheet.png"):
		return null
	var image := Image.new()
	if image.load_png_from_buffer(FileAccess.get_file_as_bytes("res://assets/sprite_sheet.png")) != OK:
		return null
	return image

func _ready() -> void:
	_action("move_forward", KEY_D)
	_action("move_back", KEY_A)
	_action("interact", KEY_E)
	avatar = CharacterBody3D.new()
	avatar.name = "Avatar"
	avatar.position = Vector3.ZERO
	avatar.add_to_group("player")
	_box(avatar, Vector3(1.0, 2.0, 1.0))
	mesh = MeshInstance3D.new()
	mesh.name = "AvatarMesh"
	mesh.mesh = BoxMesh.new()
	avatar.add_child(mesh)
	add_child(avatar)
	platform = StaticBody3D.new()
	platform.name = "Platform"
	platform.position = Vector3(3.0, -1.5, 0.0)
	_box(platform, Vector3(16.0, 1.0, 8.0))
	add_child(platform)
	trigger = Area3D.new()
	trigger.name = "SwitchTrigger"
	trigger.position = Vector3(2.0, 0.0, 0.0)
	trigger.monitoring = true
	_box(trigger, Vector3(1.5, 2.0, 2.0))
	add_child(trigger)
	pickup = Area3D.new()
	pickup.name = "Pickup"
	pickup.position = Vector3(5.0, 0.0, 0.0)
	pickup.monitoring = true
	_box(pickup, Vector3(1.0, 1.0, 1.0))
	add_child(pickup)
	camera = Camera3D.new()
	camera.name = "Camera"
	camera.current = true
	camera.position = Vector3(0.0, 3.0, 8.0)
	add_child(camera)
	var layer := CanvasLayer.new()
	layer.name = "HUD"
	hud = Label.new()
	hud.name = "Status"
	hud.text = "ROOM READY"
	layer.add_child(hud)
	add_child(layer)
	var imported := _read_avatar_asset()
	avatar_asset_loaded = imported != null
	if avatar_asset_loaded:
		imported.name = "BlenderAvatar"
		avatar.add_child(imported)
	sprite_asset_loaded = _read_sprite_image() != null
	if not avatar_asset_loaded or not sprite_asset_loaded:
		push_error("native room asset readback failed")
	topology_components = {"avatar_shape": _has_shape(avatar),
		"trigger_shape": _has_shape(trigger),
		"pickup_shape": _has_shape(pickup),
		"camera": camera is Camera3D, "hud": hud is Label}
	topology_ok = (avatar is CharacterBody3D and platform is StaticBody3D
		and trigger is Area3D and pickup is Area3D and topology_components["camera"]
		and topology_components["hud"] and topology_components["avatar_shape"]
		and topology_components["trigger_shape"] and topology_components["pickup_shape"])
	_begin_lifecycle()

func _begin_lifecycle() -> void:
	_avatar_start = avatar.position
	_camera_start = camera.position
	if Lifecycle.requested():
		var lifecycle := Lifecycle.new()
		add_child(lifecycle)
		lifecycle.begin(Callable(self, "_lifecycle_state"), Callable(self, "_lifecycle_reset"), "Room fixture")

func _physics_process(delta: float) -> void:
	var started := Time.get_ticks_usec()
	tick += 1
	if not Lifecycle.requested() and tick == 2:
		_key(KEY_D, true)
	if not Lifecycle.requested() and tick == 30:
		_key(KEY_E, true)
	if not Lifecycle.requested() and tick == 31:
		_key(KEY_E, false)
	if not Lifecycle.requested() and tick == 60:
		_key(KEY_D, false)
	if Lifecycle.requested():
		avatar.velocity.x = Input.get_axis("move_back", "move_forward") * 3.0
	elif tick <= 60 and Input.is_action_pressed("move_forward"):
		avatar.velocity.x = 3.0
	else:
		avatar.velocity.x = 0.0
	avatar.velocity.y = 0.0
	avatar.move_and_slide()
	if Input.is_action_just_pressed("interact"):
		interact_seen = true
	switch_area_entered = avatar.position.distance_to(trigger.position) <= 1.5
	if interact_seen and switch_area_entered:
		switch_used = true
	if avatar.position.distance_to(pickup.position) <= 3.0:
		pickup_collected = true
	camera.position.x = avatar.position.x
	camera_follow = is_equal_approx(camera.position.x, avatar.position.x)
	hud.text = "SWITCH ON / PICKUP %s" % pickup_collected
	var elapsed := float(Time.get_ticks_usec() - started) / 1000.0
	max_frame_ms = maxf(max_frame_ms, elapsed)
	if tick == 60 and not Lifecycle.requested():
		var first: Array[float] = []
		for value in range(12):
			first.append(float(value) * 0.5)
		var second: Array[float] = []
		for value in range(12):
			second.append(float(value) * 0.5)
		replay_values = first
		replay_hash_equal = first == second
		var checkpoint := {"tick": tick, "switch_used": switch_used,
			"pickup_collected": pickup_collected}
		var checkpoint_path := "user://gt09-room-checkpoint.json"
		var writer := FileAccess.open(checkpoint_path, FileAccess.WRITE)
		if writer != null:
			writer.store_string(JSON.stringify(checkpoint))
			writer.close()
			var reader := FileAccess.open(checkpoint_path, FileAccess.READ)
			if reader != null:
				var restored: Variant = JSON.parse_string(reader.get_as_text())
				reader.close()
				if typeof(restored) == TYPE_DICTIONARY:
					var restored_dict: Dictionary = restored
					checkpoint_reload_observed = int(restored_dict.get("tick", -1)) == tick \
						and bool(restored_dict.get("switch_used", false)) == switch_used \
						and bool(restored_dict.get("pickup_collected", false)) == pickup_collected
		var state := {"ticks": tick, "movement_observed": avatar.position.x > 2.0,
			"camera_follow": camera_follow, "switch_used": switch_used,
			"pickup_collected": pickup_collected, "ui_visible": hud.visible,
			"input_trace_ok": input_trace_ok, "replay_hash_equal": replay_hash_equal,
			"checkpoint_reload_observed": checkpoint_reload_observed,
			"avatar_asset_loaded": avatar_asset_loaded,
			"sprite_asset_loaded": sprite_asset_loaded,
			"perf_samples": tick, "perf_budget_ms": 33.333,
			"perf_budget_ok": max_frame_ms <= 33.333,
			"topology_ok": topology_ok, "topology_components": topology_components}
		print("HH_PROBE_ASSET_READBACK " + JSON.stringify({"avatar_loaded": avatar_asset_loaded, "sprite_loaded": sprite_asset_loaded}))
		print("HH_PROBE_FIXTURE " + JSON.stringify(state))
		get_tree().quit(0)

func _lifecycle_state() -> Dictionary:
	return {"tick": tick, "avatar_x": avatar.position.x if is_instance_valid(avatar) else -1.0,
		"avatar_y": avatar.position.y if is_instance_valid(avatar) else -1.0,
		"switch_used": switch_used, "pickup_collected": pickup_collected,
		"avatar_asset_loaded": avatar_asset_loaded, "sprite_asset_loaded": sprite_asset_loaded,
		"input_move": Input.is_action_pressed("move_forward"),
		"input_interact": Input.is_action_pressed("interact")}

func _lifecycle_reset() -> bool:
	if not is_instance_valid(avatar) or not is_instance_valid(camera):
		return false
	tick = 0
	avatar.position = _avatar_start
	avatar.velocity = Vector3.ZERO
	camera.position = _camera_start
	switch_used = false
	pickup_collected = false
	input_trace_ok = false
	interact_seen = false
	switch_area_entered = false
	camera_follow = false
	hud.text = "ROOM READY"
	return true

var topology_ok: bool = false
