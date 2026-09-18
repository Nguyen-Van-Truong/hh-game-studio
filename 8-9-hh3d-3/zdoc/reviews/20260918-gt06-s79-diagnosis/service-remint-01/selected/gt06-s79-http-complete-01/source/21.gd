extends Node3D
## Original GT06 behavior. Only input/UI callbacks change gameplay phase/actions.
## The observer calls snapshot(), never these callbacks or controller methods.

const BRIDGE_SCRIPT: Script = preload("res://observe/trace_bridge.gd")
const AUTHORING_SCRIPT: Script = preload("res://gt05/authored.gd")
const INPUT_KEYS: Dictionary = {KEY_ENTER: "ENTER", KEY_TAB: "TAB", KEY_RIGHT: "RIGHT",
	KEY_LEFT: "LEFT", KEY_UP: "UP", KEY_DOWN: "DOWN", KEY_E: "E", KEY_O: "O",
	KEY_M: "M", KEY_ESCAPE: "ESCAPE", KEY_C: "C", KEY_Q: "Q"}
const BODY_HEIGHT: float = 1.85
const MAX_CALLBACKS: int = 8192

var phase: String = "MENU"
var sim_tick: int = 0
var ui_tick: int = 0
var move_speed: float = 0.0
var bridge: Node
var world: Node3D
var imported: Node3D
var rig: Node3D
var skeleton: Skeleton3D
var player: AnimationPlayer
var actor: CharacterBody3D
var outfit: MeshInstance3D
var prop: MeshInstance3D
var prop_body: StaticBody3D
var prop_pivot: Node3D
var camera: Camera3D
var camera_bookmark: int = 0
var start_button: Button
var quit_button: Button
var status: Label
var input_status: Label
var emote_remaining: int = 0
var emote_count: int = 0
var emote_bone: int = -1
var prop_active: bool = false
var prop_spin_tick: int = 0
var prop_count: int = 0
var prop_seed_angle: float = 0.0
var last_prop_hit: Dictionary = {}
var callbacks: Array[Dictionary] = []
var transitions: Array[Dictionary] = []
var ready_for_trace: bool = false


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	process_physics_priority = 0
	set_physics_process(false)
	Engine.physics_ticks_per_second = 60
	Engine.max_fps = 60
	bridge = BRIDGE_SCRIPT.new() as Node
	bridge.name = "ObserveBridge"
	add_child(bridge)
	if not bool(bridge.call("prepare", self)):
		return
	if not _configure() or not _build_world(int(bridge.get("trace_seed"))):
		return
	_build_ui()
	ready_for_trace = true
	set_physics_process(true)
	bridge.call("begin")


func _need(value: bool, code: String) -> bool:
	if not value:
		bridge.call("fail", code)
	return value


func _configure() -> bool:
	# Host admits the exact GT03 declarative profile before this trusted load.
	var config_script: Script = load("res://config/fixture_actor.gd") as Script
	if not _need(config_script != null, "GT06_CONFIG_SCRIPT"):
		return false
	var config: Node3D = Node3D.new()
	config.set_script(config_script)
	var speed_value: Variant = config.get("move_speed")
	if not _need((speed_value is float or speed_value is int) and is_finite(float(speed_value))
			and float(speed_value) >= 0.0 and float(speed_value) <= 100.0, "GT06_CONFIG_SPEED"):
		config.free()
		return false
	move_speed = float(speed_value)
	config.free()
	return true


func _unique(name_value: String) -> Node:
	var found: Array[Node] = imported.find_children(name_value, "", true, false)
	if not _need(found.size() == 1, "GT06_ASSET_ID_" + name_value):
		return null
	return found[0]


func _build_world(seed_value: int) -> bool:
	world = Node3D.new()
	world.name = "World"
	world.process_mode = Node.PROCESS_MODE_PAUSABLE
	add_child(world)
	var wrapper: Node3D = Node3D.new()
	wrapper.name = "GT05Authoring"
	wrapper.set_script(AUTHORING_SCRIPT)
	wrapper.set("authored_material", load("res://gt05/authored_material.tres"))
	world.add_child(wrapper)
	var packed: PackedScene = load("res://input/fixture.glb") as PackedScene
	if not _need(packed != null, "GT06_GLB_PACKED_SCENE"):
		return false
	imported = packed.instantiate() as Node3D
	if not _need(imported != null, "GT06_GLB_ROOT"):
		return false
	imported.name = "Imported"
	wrapper.add_child(imported)
	rig = _unique("chr_fixture_avatar_rig") as Node3D
	skeleton = _unique("Skeleton3D") as Skeleton3D
	player = _unique("AnimationPlayer") as AnimationPlayer
	outfit = _unique("chr_fixture_outfit_lod0") as MeshInstance3D
	prop = _unique("prp_fixture_crate_lod0") as MeshInstance3D
	if not _need(rig != null and skeleton != null and player != null and outfit != null and prop != null,
			"GT06_REQUIRED_NATIVE_ASSETS"):
		return false
	var producer: Dictionary = bridge.call("read_object", "res://input/producer-report.json", 1048576)
	if not _need(producer.get("catalog") is Dictionary, "GT06_CATALOG"):
		return false
	var catalog: Dictionary = producer["catalog"]
	for asset: Dictionary in catalog.get("assets", []):
		for descriptor: Dictionary in asset.get("nodes", []):
			if descriptor["role"] == "rig":
				continue
			var mesh: MeshInstance3D = _unique(String(descriptor["name"])) as MeshInstance3D
			if not _need(mesh != null, "GT06_CATALOG_MESH"):
				return false
			var role_result: Dictionary = wrapper.call("apply_role", mesh, String(descriptor["role"]), int(descriptor.get("lod", -1)))
			if not _need(not role_result.has("error"), "GT06_AUTHORED_ROLE"):
				return false
	wrapper.call("set_lod", 0)
	prop_body = wrapper.get_node_or_null("prp_fixture_crate_collider_body") as StaticBody3D
	if not _need(prop_body != null, "GT06_PROP_BODY"):
		return false
	prop_pivot = Node3D.new()
	prop_pivot.name = "InteractableCrate"
	world.add_child(prop_pivot)
	prop_pivot.global_position = (prop.global_transform * prop.get_aabb()).get_center()
	prop.reparent(prop_pivot, true)
	prop_body.reparent(prop_pivot, true)
	# Original fixture placement leaves the authored 30-tick move unobstructed.
	# Mesh and collider move together; the admitted GLB bytes stay unchanged.
	prop_pivot.position.x += 0.4
	# Seed affects a visible simulation rate, while both fault and repair share it.
	prop_seed_angle = float(seed_value % 11) * 0.025
	_floor()
	actor = CharacterBody3D.new()
	actor.name = "AvatarBody"
	actor.collision_layer = 2
	actor.collision_mask = 1
	actor.position = Vector3(0.0, BODY_HEIGHT * 0.5 + 0.01, 0.0)
	world.add_child(actor)
	var capsule: CapsuleShape3D = CapsuleShape3D.new()
	capsule.height = BODY_HEIGHT
	capsule.radius = 0.23
	var collision: CollisionShape3D = CollisionShape3D.new()
	collision.shape = capsule
	actor.add_child(collision)
	emote_bone = skeleton.find_bone("bn_upperarm_r")
	if not _need(emote_bone >= 0 and player.has_animation("idle") and player.has_animation("walk"), "GT06_ANIMATION_BINDING"):
		return false
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	player.play("idle")
	player.advance(0.0)
	_lighting()
	return true


func _floor() -> void:
	var floor_body: StaticBody3D = StaticBody3D.new()
	floor_body.name = "Floor"
	floor_body.position.y = -0.1
	world.add_child(floor_body)
	var shape: BoxShape3D = BoxShape3D.new()
	shape.size = Vector3(10.0, 0.2, 7.0)
	var collision: CollisionShape3D = CollisionShape3D.new()
	collision.shape = shape
	floor_body.add_child(collision)
	var mesh: MeshInstance3D = MeshInstance3D.new()
	var box: BoxMesh = BoxMesh.new()
	box.size = shape.size
	mesh.mesh = box
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = Color(0.12, 0.16, 0.2)
	material.roughness = 0.9
	mesh.material_override = material
	floor_body.add_child(mesh)


func _lighting() -> void:
	var environment_node: WorldEnvironment = WorldEnvironment.new()
	var environment: Environment = Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.035, 0.05, 0.08)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(0.82, 0.9, 1.0)
	environment.ambient_light_energy = 0.7
	environment_node.environment = environment
	world.add_child(environment_node)
	var light: DirectionalLight3D = DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-48.0, -25.0, 0.0)
	light.light_energy = 1.1
	world.add_child(light)
	camera = Camera3D.new()
	camera.name = "ReviewCamera"
	camera.current = true
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 7.5
	camera.near = 0.05
	camera.far = 50.0
	add_child(camera)
	_apply_camera()


func _build_ui() -> void:
	var layer: CanvasLayer = CanvasLayer.new()
	layer.name = "ReviewerUI"
	layer.process_mode = Node.PROCESS_MODE_ALWAYS
	add_child(layer)
	var panel: PanelContainer = PanelContainer.new()
	panel.position = Vector2(18.0, 18.0)
	panel.custom_minimum_size = Vector2(415.0, 190.0)
	layer.add_child(panel)
	var box: VBoxContainer = VBoxContainer.new()
	box.add_theme_constant_override("separation", 7)
	panel.add_child(box)
	var title: Label = Label.new()
	title.text = "HH STUDIO · PLAY & OBSERVE"
	title.add_theme_font_size_override("font_size", 21)
	box.add_child(title)
	status = Label.new()
	box.add_child(status)
	var help: Label = Label.new()
	help.text = "Arrows move · E crate · O outfit · M greet\nEsc pause/resume · C camera · Q quit"
	box.add_child(help)
	var buttons: HBoxContainer = HBoxContainer.new()
	box.add_child(buttons)
	start_button = Button.new()
	start_button.name = "StartButton"
	start_button.text = "Start"
	start_button.custom_minimum_size = Vector2(150.0, 36.0)
	start_button.focus_mode = Control.FOCUS_ALL
	start_button.pressed.connect(_on_start_pressed)
	buttons.add_child(start_button)
	quit_button = Button.new()
	quit_button.name = "QuitButton"
	quit_button.text = "Quit"
	quit_button.custom_minimum_size = Vector2(110.0, 36.0)
	quit_button.focus_mode = Control.FOCUS_ALL
	quit_button.pressed.connect(_on_quit_pressed)
	buttons.add_child(quit_button)
	input_status = Label.new()
	box.add_child(input_status)
	start_button.grab_focus()
	_update_ui()


func _process(_delta: float) -> void:
	if ready_for_trace:
		ui_tick += 1
		_update_ui()


func _physics_process(delta: float) -> void:
	if not ready_for_trace or phase != "PLAY":
		return
	sim_tick += 1
	var direction: Vector2 = Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	actor.velocity.x = direction.x * move_speed
	actor.velocity.z = direction.y * move_speed
	actor.velocity.y -= 9.8 * delta
	actor.move_and_slide()
	rig.global_position = actor.global_position - Vector3.UP * (BODY_HEIGHT * 0.5)
	var wanted_clip: String = "walk" if direction.length_squared() > 0.0 and move_speed > 0.0 else "idle"
	if String(player.current_animation) != wanted_clip:
		player.play(wanted_clip)
	player.advance(delta)
	if emote_remaining > 0:
		emote_remaining -= 1
		var angle: float = -1.1 + sin(float(90 - emote_remaining) * 0.23) * 0.18
		var base_pose: Quaternion = skeleton.get_bone_pose_rotation(emote_bone)
		skeleton.set_bone_pose_rotation(emote_bone, base_pose * Quaternion(Vector3.BACK, angle))
	if prop_active:
		prop_spin_tick += 1
		prop_pivot.rotation.y = float(prop_spin_tick) * (0.0125 + prop_seed_angle)


func _input(event: InputEvent) -> void:
	if not ready_for_trace or not event is InputEventKey:
		return
	var key: InputEventKey = event as InputEventKey
	if not INPUT_KEYS.has(key.keycode) or key.echo:
		return
	if not _record_callback({"callback": "_input", "trace_tick": int(bridge.get("current_tick")),
		"key": INPUT_KEYS[key.keycode], "pressed": key.pressed, "phase_before": phase,
		"window_id": key.window_id}):
		return
	if not key.pressed:
		return
	if key.keycode == KEY_Q:
		_transition("QUITTING", "key.Q")
	elif key.keycode == KEY_ESCAPE and phase == "PLAY":
		_transition("PAUSED", "key.ESCAPE")
	elif key.keycode == KEY_ESCAPE and phase == "PAUSED":
		_transition("PLAY", "key.ESCAPE")
	elif key.keycode == KEY_C and phase != "QUITTING":
		camera_bookmark = 1 - camera_bookmark
		_apply_camera()
	elif phase == "PLAY":
		if key.keycode == KEY_O:
			outfit.visible = not outfit.visible
		elif key.keycode == KEY_M:
			emote_remaining = 90
			emote_count += 1
		elif key.keycode == KEY_E:
			_interact_prop()


func _on_start_pressed() -> void:
	if not _record_callback({"callback": "StartButton.pressed", "trace_tick": int(bridge.get("current_tick")), "phase_before": phase}):
		return
	if phase == "MENU":
		_transition("PLAY", "button.Start")


func _on_quit_pressed() -> void:
	if not _record_callback({"callback": "QuitButton.pressed", "trace_tick": int(bridge.get("current_tick")), "phase_before": phase}):
		return
	_transition("QUITTING", "button.Quit")


func _record_callback(row: Dictionary) -> bool:
	if not _need(callbacks.size() < MAX_CALLBACKS, "GT06_CALLBACK_CAPACITY"):
		return false
	callbacks.append(row)
	return true


func _transition(destination: String, trigger: String) -> void:
	if phase == "QUITTING" or phase == destination:
		return
	var previous: String = phase
	phase = destination
	get_tree().paused = phase == "PAUSED"
	transitions.append({"trace_tick": int(bridge.get("current_tick")), "from": previous, "to": phase, "trigger": trigger})
	_update_ui()
	# Trace supervisor records the destination after this callback and physics.
	# Quit deliberately leaves the event queue alive until its releases are read.


func _interact_prop() -> void:
	var target: Vector3 = prop_pivot.global_position
	var distance: float = actor.global_position.distance_to(target)
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(actor.global_position, target, 1)
	query.exclude = [actor.get_rid()]
	var hit: Dictionary = world.get_world_3d().direct_space_state.intersect_ray(query)
	var collider: Object = hit.get("collider") as Object
	var matched: bool = distance <= 2.5 and collider == prop_body
	last_prop_hit = {"distance_m": distance, "hit": not hit.is_empty(), "matched_prop": matched,
		"collider": String(prop_body.name) if collider == prop_body else "other_or_none",
		"position": _vector(hit["position"]) if hit.has("position") else []}
	if matched:
		prop_active = not prop_active
		prop_count += 1


func _apply_camera() -> void:
	camera.position = Vector3(5.2, 4.0, 7.5) if camera_bookmark == 0 else Vector3(-5.2, 3.5, 7.5)
	camera.look_at(Vector3(0.0, 0.9, 0.0))


func _update_ui() -> void:
	if status == null:
		return
	status.text = "%s · simulation %d · UI %d" % [phase, sim_tick, ui_tick]
	start_button.disabled = phase != "MENU"
	input_status.text = "Outfit %s · greet %d · crate %d" % ["on" if outfit.visible else "off", emote_count, prop_count]


func _vector(value: Vector3) -> Array[float]:
	return [value.x, value.y, value.z]


func _rotation(value: Quaternion) -> Array[float]:
	return [value.x, value.y, value.z, value.w]


func camera_snapshot() -> Dictionary:
	return {"stable_id": "review.camera", "bookmark": camera_bookmark, "position": _vector(camera.global_position),
		"rotation_xyzw": _rotation(camera.global_basis.get_rotation_quaternion()), "projection": camera.projection,
		"size": camera.size, "near": camera.near, "far": camera.far, "target": [0.0, 0.9, 0.0]}


func snapshot() -> Dictionary:
	# Native values are read afresh. No replay/controller state is assigned here.
	var focus: Control = get_viewport().gui_get_focus_owner()
	return {"phase": phase, "sim_tick": sim_tick, "ui_tick": ui_tick,
		"move_speed": move_speed, "body_position": _vector(actor.global_position), "body_velocity": _vector(actor.velocity),
		"avatar_position": _vector(rig.global_position),
		"animation": {"clip": String(player.current_animation), "position": player.current_animation_position},
		"outfit_visible": outfit.is_visible_in_tree(), "emote_remaining": emote_remaining, "emote_count": emote_count,
		"emote_bone": "bn_upperarm_r", "emote_pose_xyzw": _rotation(skeleton.get_bone_pose_rotation(emote_bone)),
		"prop_active": prop_active, "prop_spin_tick": prop_spin_tick, "prop_count": prop_count,
		"prop_rotation": _vector(prop_pivot.rotation), "prop_position": _vector(prop_pivot.global_position),
		"last_prop_hit": last_prop_hit.duplicate(true), "camera": camera_snapshot(),
		"focus": String(focus.name) if focus != null else "", "tree_paused": get_tree().paused}


func visible_triangle_count() -> int:
	var count: int = 0
	for node: Node in world.find_children("*", "MeshInstance3D", true, false):
		var mesh: MeshInstance3D = node as MeshInstance3D
		if mesh.mesh == null or not mesh.is_visible_in_tree():
			continue
		# Mesh.get_faces is bound on both ArrayMesh and PrimitiveMesh. The
		# surface type/length helpers are not script APIs on BoxMesh in this pin.
		count += int(float(mesh.mesh.get_faces().size()) / 3.0)
	return count
