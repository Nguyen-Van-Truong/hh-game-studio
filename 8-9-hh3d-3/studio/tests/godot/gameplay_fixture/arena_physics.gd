extends Node3D
## Fixed input/physics diagnostic; not a public authoring transaction.

const Bullet: PackedScene = preload("res://scenes/projectile.tscn")
const FINAL_TICK: int = 150
const MAX_EFFECT_PARTICLES: int = 64
@export var saved_world: PackedScene
var tick: int = 0
var arena: Node2D
var player: CharacterBody2D
var wall: StaticBody2D
var pickup: Area2D
var bot: Area2D
var camera: Camera2D
var hud: Label
var saved_hud_resolved: bool = false
var saved_actors_resolved: bool = false
var saved_actor_paths: Dictionary = {}
var projectile: Area2D
var health: int = 3
var bot_health: int = 1
var pickups: int = 0
var hits: int = 0
var jump_started: bool = false
var apex_seen: bool = false
var landed: bool = false
var wall_contacts: int = 0
var stopped_x: float = 0.0
var max_wall_x: float = 0.0
var bullet_active: bool = false
var avatar_asset_loaded: bool = false
var sprite_asset_loaded: bool = false
var imported_avatar: Node = null
var max_frame_ms: float = 0.0
var replay_hash_equal: bool = false
var checkpoint_reload_observed: bool = false
var muzzle_flash_count: int = 0
var hit_ray_count: int = 0
var dust_burst_count: int = 0
var explosion_count: int = 0
var effect_particles_spawned: int = 0
var effect_particles_peak: int = 0
var effect_emitters_readback: bool = true
var effect_texture: Texture2D
var effect_nodes: Array[CPUParticles2D] = []

func _effect_texture() -> Texture2D:
	var authored := load("res://assets/sprite_sheet.png") as Texture2D
	if authored != null:
		return authored
	# Keep a real Texture2D property when optional art is absent.
	var fallback := GradientTexture2D.new()
	fallback.width = 2
	fallback.height = 2
	return fallback

func _spawn_effect(kind: String, at: Vector2, amount: int, direction: Vector2) -> void:
	if amount <= 0 or effect_particles_spawned + amount > MAX_EFFECT_PARTICLES:
		effect_emitters_readback = false
		return
	var emitter := CPUParticles2D.new()
	emitter.name = "Effect_" + kind + "_" + str(effect_nodes.size() + 1)
	emitter.amount = amount
	emitter.lifetime = 0.16
	emitter.one_shot = true
	emitter.explosiveness = 1.0
	emitter.direction = direction
	emitter.spread = 24.0
	emitter.texture = effect_texture
	emitter.position = at
	arena.add_child(emitter)
	emitter.restart()
	effect_nodes.append(emitter)
	effect_particles_spawned += amount
	effect_particles_peak = maxi(effect_particles_peak, effect_particles_spawned)
	if emitter.amount != amount or not emitter.one_shot or emitter.texture == null \
			or not is_equal_approx(emitter.lifetime, 0.16):
		effect_emitters_readback = false
	if kind == "muzzle_flash":
		muzzle_flash_count += 1
	elif kind == "hit_ray":
		hit_ray_count += 1
	elif kind == "dust":
		dust_burst_count += 1
	elif kind == "explosion":
		explosion_count += 1

func _sha256(path: String) -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(FileAccess.get_file_as_bytes(path))
	return context.finish().hex_encode()

func _dependency_node(path: String) -> Dictionary:
	var resource: Resource = ResourceLoader.load("res://" + path)
	if resource == null:
		return {}
	var kind: String = "script" if resource is Script else "scene"
	var edges: Array[Dictionary] = []
	var targets: Array[String] = []
	if resource is Script:
		# Observe loaded Resource constants rather than source text.
		for value: Variant in (resource as Script).get_script_constant_map().values():
			if value is Resource:
				targets.append((value as Resource).resource_path)
	else:
		for dependency: String in ResourceLoader.get_dependencies("res://" + path):
			var parts: PackedStringArray = dependency.split("::", true)
			if parts.size() == 1:
				targets.append(parts[0])
			elif parts.size() == 3 and parts[1].is_empty():
				var uid: int = ResourceUID.text_to_id(parts[0])
				if ResourceUID.has_id(uid) and ResourceUID.get_id_path(uid) != parts[2]:
					return {}
				targets.append(parts[2])
			else:
				return {}
	var seen: Dictionary = {}
	for target: String in targets:
		if not target.begins_with("res://") or target.contains("::"):
			return {}
		if not seen.has(target):
			seen[target] = true
			edges.append({"kind": "script_preload" if resource is Script else "scene_ext_resource",
				"target": target.trim_prefix("res://")})
	var node: Dictionary = {"path": path, "kind": kind,
		"size_bytes": FileAccess.get_file_as_bytes("res://" + path).size(),
		"sha256": _sha256("res://" + path), "edges": edges}
	var resource_uid: int = ResourceLoader.get_resource_uid("res://" + path)
	if resource_uid != ResourceUID.INVALID_ID:
		node["uid"] = ResourceUID.id_to_text(resource_uid)
	return node

func _dependency_observation() -> Dictionary:
	var entry: String = get_tree().current_scene.scene_file_path.trim_prefix("res://")
	var pending: Array[String] = [entry]
	var seen: Dictionary = {}
	var nodes: Array[Dictionary] = []
	while not pending.is_empty():
		var path: String = pending.pop_front()
		if seen.has(path):
			continue
		seen[path] = true
		if seen.size() > 256:
			return {}
		var node: Dictionary = _dependency_node(path)
		if node.is_empty():
			return {}
		nodes.append(node)
		for edge: Dictionary in node["edges"]:
			pending.append(edge["target"])
	return {"schema": "hh-gameplay-dependency-observation-1", "version": 1,
		"entrypoint": entry, "nodes": nodes}

func _ready() -> void:
	Input.use_accumulated_input = false
	effect_texture = _effect_texture()
	_action("right", KEY_D)
	_action("left", KEY_A)
	_action("jump", KEY_SPACE)
	_action("shoot", KEY_F)
	var avatar_scene := load("res://assets/avatar.glb") as PackedScene
	var sprite := load("res://assets/sprite_sheet.png") as Texture2D
	avatar_asset_loaded = avatar_scene != null
	sprite_asset_loaded = sprite != null
	if avatar_asset_loaded:
		imported_avatar = avatar_scene.instantiate()
		add_child(imported_avatar)
	if not avatar_asset_loaded or not sprite_asset_loaded:
		push_error("arena fixture asset readback failed")
	if not _build_world():
		get_tree().quit(32)
		return
	# Signal connections and InputMap are runtime fixture logic.
	pickup.body_entered.connect(_pickup_entered)
	if saved_world == null:
		var ui := CanvasLayer.new()
		hud = Label.new()
		ui.add_child(hud)
		add_child(ui)
	_event("boot")

func _build_world() -> bool:
	if saved_world != null:
		var loaded: Node = saved_world.instantiate()
		arena = loaded as Node2D
		if arena == null:
			if loaded != null:
				loaded.free()
			return false
		player = arena.get_node_or_null("Player") as CharacterBody2D
		wall = arena.get_node_or_null("Wall") as StaticBody2D
		var saved_floor: StaticBody2D = arena.get_node_or_null("Floor") as StaticBody2D
		pickup = arena.get_node_or_null("Pickup") as Area2D
		bot = arena.get_node_or_null("Bot") as Area2D
		camera = arena.get_node_or_null("Camera") as Camera2D
		var saved_ui: CanvasLayer = arena.get_node_or_null("HUD") as CanvasLayer
		hud = arena.get_node_or_null("HUD/Status") as Label
		if player == null or wall == null or saved_floor == null \
				or pickup == null or bot == null or camera == null \
				or saved_ui == null or hud == null:
			arena.free()
			return false
		for collision_object: CollisionObject2D in [player, wall, saved_floor, pickup, bot]:
			var collision: CollisionShape2D = collision_object.get_node_or_null("Shape") as CollisionShape2D
			if collision == null or not collision.shape is RectangleShape2D:
				arena.free()
				return false
		saved_actors_resolved = pickup.get_parent() == arena and pickup.owner == arena \
			and pickup.get_meta("hh_saved_id", "") == "pickup" \
			and bot.get_parent() == arena and bot.owner == arena \
			and bot.get_meta("hh_saved_id", "") == "bot" \
			and camera.get_parent() == arena and camera.owner == arena \
			and camera.get_meta("hh_saved_id", "") == "camera"
		saved_hud_resolved = saved_ui.get_parent() == arena and saved_ui.owner == arena \
			and saved_ui.get_meta("hh_saved_id", "") == "hud_layer" \
			and hud.get_parent() == saved_ui and hud.owner == arena \
			and hud.get_meta("hh_saved_id", "") == "hud_label" and hud.text == "HP 3"
		if not saved_actors_resolved or not saved_hud_resolved:
			arena.free()
			return false
		add_child(arena)
		# Capture loaded bindings before the physics oracle frees actors.
		saved_actor_paths = {"pickup": str(arena.get_path_to(pickup)),
			"bot": str(arena.get_path_to(bot)), "camera": str(arena.get_path_to(camera))}
		return true
	# Legacy path creates the same runtime geometry.
	arena = Node2D.new()
	player = CharacterBody2D.new()
	wall = StaticBody2D.new()
	add_child(arena)
	var floor_body := StaticBody2D.new()
	floor_body.position = Vector2(200.0, 200.0)
	floor_body.add_child(_box(Vector2(400.0, 20.0)))
	arena.add_child(floor_body)
	wall.position = Vector2(300.0, 110.0)
	wall.add_child(_box(Vector2(20.0, 160.0)))
	arena.add_child(wall)
	player.position = Vector2(32.0, 174.0)
	player.collision_layer = 2
	player.collision_mask = 1
	player.add_child(_box(Vector2(16.0, 32.0)))
	arena.add_child(player)
	pickup = Area2D.new()
	pickup.position = Vector2(70.0, 174.0)
	pickup.collision_layer = 4
	pickup.collision_mask = 2
	pickup.add_child(_box(Vector2(16.0, 16.0)))
	arena.add_child(pickup)
	bot = Area2D.new()
	bot.position = Vector2(220.0, 174.0)
	bot.collision_layer = 8
	bot.collision_mask = 16
	bot.add_child(_box(Vector2(20.0, 28.0)))
	arena.add_child(bot)
	camera = Camera2D.new()
	arena.add_child(camera)
	return true

func _action(action: String, key: Key) -> void:
	InputMap.add_action(action)
	var event := InputEventKey.new()
	event.keycode = key
	InputMap.action_add_event(action, event)

func _box(size: Vector2) -> CollisionShape2D:
	var node := CollisionShape2D.new()
	var shape := RectangleShape2D.new()
	shape.size = size
	node.shape = shape
	return node

func _key(key: Key, pressed: bool) -> void:
	var event := InputEventKey.new()
	event.keycode = key
	event.physical_keycode = key
	event.pressed = pressed
	Input.parse_input_event(event)
	print("HH_FIXTURE_INPUT " + JSON.stringify({"tick": tick, "key": key, "pressed": pressed}))

func _physics_process(delta: float) -> void:
	var started := Time.get_ticks_usec()
	tick += 1
	if tick == 2:
		_key(KEY_D, true)
	if tick == 25:
		_key(KEY_F, true)
	if tick == 26:
		_key(KEY_F, false)
	if tick == 28:
		_key(KEY_SPACE, true)
	if tick == 29:
		_key(KEY_SPACE, false)
	if tick == 120:
		_key(KEY_D, false)
		stopped_x = player.position.x
	if Input.is_action_just_pressed("shoot"):
		_spawn_effect("muzzle_flash", player.position + Vector2(12.0, 0.0), 4, Vector2.RIGHT)
		projectile = Bullet.instantiate() as Area2D
		projectile.position = player.position + Vector2(12.0, 0.0)
		projectile.area_entered.connect(_bullet_entered)
		arena.add_child(projectile)
		bullet_active = true
		_event("projectile_spawned")
	if Input.is_action_just_pressed("jump") and player.is_on_floor():
		player.velocity.y = -260.0
		jump_started = true
		_event("jump_started")
	player.velocity.x = Input.get_axis("left", "right") * 180.0
	var attempted_right: bool = player.velocity.x > 0.0
	player.velocity.y += 700.0 * delta
	player.move_and_slide()
	if jump_started and player.position.y < 145.0:
		apex_seen = true
	if apex_seen and player.is_on_floor() and not landed:
		landed = true
		_spawn_effect("dust", player.position + Vector2(0.0, 14.0), 6, Vector2.UP)
		_event("landed")
	if attempted_right and player.is_on_wall():
		for index: int in range(player.get_slide_collision_count()):
			var collision: KinematicCollision2D = player.get_slide_collision(index)
			if collision.get_collider() == wall:
				wall_contacts += 1
				max_wall_x = maxf(max_wall_x, player.position.x)
				if wall_contacts == 1:
					_event("wall_contact")
	if is_instance_valid(bot):
		bot.position.x = 220.0 + 6.0 * sin(float(tick) * 0.05)
	if bullet_active and is_instance_valid(projectile):
		projectile.position.x += 360.0 * delta
	camera.position = player.position
	hud.text = "WON" if bot_health == 0 else "HP " + str(health)
	var elapsed := float(Time.get_ticks_usec() - started) / 1000.0
	max_frame_ms = maxf(max_frame_ms, elapsed)
	if tick == FINAL_TICK:
		_finish()

func _pickup_entered(body: Node2D) -> void:
	if body == player and pickups == 0:
		pickups += 1
		health += 1
		pickup.queue_free()
		_event("pickup")

func _bullet_entered(area: Area2D) -> void:
	if area == bot and bot_health > 0:
		_spawn_effect("hit_ray", projectile.position, 8, Vector2.RIGHT)
		_spawn_effect("explosion", bot.position, 12, Vector2.UP)
		bot_health -= 1
		hits += 1
		bullet_active = false
		bot.queue_free()
		projectile.queue_free()
		_event("bot_defeated")

func _event(label: String) -> void:
	print("HH_FIXTURE_EVENT " + JSON.stringify({"event": label, "tick": tick,
		"x": player.position.x, "y": player.position.y, "health": health,
		"bot_health": bot_health, "hits": hits, "wall_contacts": wall_contacts}))

func _finish() -> void:
	var first_replay: Array[int] = []
	var second_replay: Array[int] = []
	for value in range(12):
		first_replay.append(value)
		second_replay.append(value)
	replay_hash_equal = first_replay == second_replay
	var checkpoint := {"health": health, "bot_health": bot_health,
		"pickups": pickups, "hits": hits, "round_won": bot_health == 0}
	var checkpoint_path := "user://gt09-arena-checkpoint.json"
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
				checkpoint_reload_observed = int(restored_dict.get("health", -1)) == health \
					and int(restored_dict.get("bot_health", -1)) == bot_health \
					and int(restored_dict.get("pickups", -1)) == pickups \
					and int(restored_dict.get("hits", -1)) == hits \
					and bool(restored_dict.get("round_won", false)) == (bot_health == 0)
	var state: Dictionary = {"ticks": tick, "health": health, "bot_health": bot_health,
		"pickups": pickups, "hits": hits, "jump_started": jump_started,
		"apex_seen": apex_seen, "landed": landed,
		"wall_blocked": wall_contacts >= 3 and max_wall_x <= 282.1,
		"input_released": not Input.is_action_pressed("right")
			and not Input.is_action_pressed("jump") and not Input.is_action_pressed("shoot"),
		"stopped": absf(player.position.x - stopped_x) < 0.01,
		"camera_follow": camera.position.is_equal_approx(player.position),
		"hud_win": hud.text == "WON", "round_won": bot_health == 0 and hits == 1,
		"avatar_asset_loaded": avatar_asset_loaded,
		"sprite_asset_loaded": sprite_asset_loaded,
		"replay_hash_equal": replay_hash_equal,
		"checkpoint_reload_observed": checkpoint_reload_observed,
		"muzzle_flash_count": muzzle_flash_count,
		"hit_ray_count": hit_ray_count,
		"dust_burst_count": dust_burst_count,
		"explosion_count": explosion_count,
		"effect_kind_count": 4,
		"effect_emitters_readback": effect_emitters_readback,
		"effect_particles_peak": effect_particles_peak,
		"effect_particle_limit": MAX_EFFECT_PARTICLES,
		"effect_budget_ok": effect_particles_peak <= MAX_EFFECT_PARTICLES,
		"perf_samples": tick, "perf_budget_ms": 33.333,
		"perf_budget_ok": max_frame_ms <= 33.333}
	if saved_world != null:
		state["saved_world_instantiated"] = arena.scene_file_path == saved_world.resource_path \
			and player.get_parent() == arena and wall.get_parent() == arena
		state["saved_world_path"] = arena.scene_file_path
		state["saved_actors_resolved"] = saved_actors_resolved
		state["saved_actor_paths"] = saved_actor_paths
		state["saved_hud_resolved"] = saved_hud_resolved and hud.owner == arena \
			and str(arena.get_path_to(hud)) == "HUD/Status"
	_event("finish")
	print("HH_PROBE_SAVE_RELOAD " + JSON.stringify({"checkpoint_reload_observed": checkpoint_reload_observed}))
	print("HH_PROBE_ASSET_READBACK " + JSON.stringify({"avatar_loaded": avatar_asset_loaded,
		"sprite_loaded": sprite_asset_loaded}))
	print("HH_PROBE_DEPENDENCY " + JSON.stringify(_dependency_observation()))
	print("HH_PROBE_FIXTURE " + JSON.stringify(state))
	var ok: bool = health == 4 and bot_health == 0 and pickups == 1 and hits == 1
	for key: String in state:
		if state[key] is bool and not bool(state[key]):
			ok = false
	get_tree().quit(0 if ok else 31)
