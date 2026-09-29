extends Node3D
## Fixed input/physics diagnostic, executed only by the contained Linux profile.
## This is not a public authoring transaction or the complete GT09 arena.

const Bullet: PackedScene = preload("res://scenes/projectile.tscn")
const FINAL_TICK: int = 150
var tick: int = 0
var arena := Node2D.new()
var player := CharacterBody2D.new()
var wall := StaticBody2D.new()
var pickup := Area2D.new()
var bot := Area2D.new()
var camera := Camera2D.new()
var hud := Label.new()
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

func _ready() -> void:
	Input.use_accumulated_input = false
	_action("right", KEY_D)
	_action("left", KEY_A)
	_action("jump", KEY_SPACE)
	_action("shoot", KEY_F)
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
	pickup.position = Vector2(70.0, 174.0)
	pickup.collision_layer = 4
	pickup.collision_mask = 2
	pickup.add_child(_box(Vector2(16.0, 16.0)))
	pickup.body_entered.connect(_pickup_entered)
	arena.add_child(pickup)
	bot.position = Vector2(220.0, 174.0)
	bot.collision_layer = 8
	bot.collision_mask = 16
	bot.add_child(_box(Vector2(20.0, 28.0)))
	arena.add_child(bot)
	arena.add_child(camera)
	var ui := CanvasLayer.new()
	ui.add_child(hud)
	add_child(ui)
	_event("boot")

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
	var state: Dictionary = {"ticks": tick, "health": health, "bot_health": bot_health,
		"pickups": pickups, "hits": hits, "jump_started": jump_started,
		"apex_seen": apex_seen, "landed": landed,
		"wall_blocked": wall_contacts >= 3 and max_wall_x <= 282.1,
		"input_released": not Input.is_action_pressed("right")
			and not Input.is_action_pressed("jump") and not Input.is_action_pressed("shoot"),
		"stopped": absf(player.position.x - stopped_x) < 0.01,
		"camera_follow": camera.position.is_equal_approx(player.position),
		"hud_win": hud.text == "WON", "round_won": bot_health == 0 and hits == 1}
	_event("finish")
	print("HH_PROBE_FIXTURE " + JSON.stringify(state))
	var ok: bool = health == 4 and bot_health == 0 and pickups == 1 and hits == 1
	for key: String in state:
		if state[key] is bool and not bool(state[key]):
			ok = false
	get_tree().quit(0 if ok else 31)
