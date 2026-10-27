class_name VaultFighter
extends CharacterBody2D

signal defeated(player_id: int)

const GRAVITY: float = 1250.0
const WALK_SPEED: float = 255.0
const ACCELERATION: float = 1700.0
const JUMP_SPEED: float = 455.0
const CLIMB_SPEED: float = 150.0
const ROLL_SPEED: float = 430.0

var player_id: int = 1
var controls: Dictionary = {}
var tint: Color = Color("5bc0eb")
var match_controller: VaultGame
var health: int = 100
var ammo: int = 12
var grenades: int = 3
var power: int = 1
var facing: int = 1
var on_ladder: bool = false
var ladder_x: float = 0.0
var roll_timer: float = 0.0
var roll_direction: int = 1
var attack_cooldown: float = 0.0
var invulnerability: float = 0.0
var burning: float = 0.0
var _previous: Dictionary = {}

func configure(id: int, start: Vector2, color: Color, input_controls: Dictionary, controller: VaultGame) -> void:
	player_id = id
	position = start
	tint = color
	controls = input_controls
	match_controller = controller
	_previous = {"punch": false, "shoot": false, "throw": false, "power": false, "jump": false}
	queue_redraw()

func _ready() -> void:
	collision_layer = 1
	collision_mask = 1
	up_direction = Vector2.UP
	var shape_node := CollisionShape2D.new()
	var shape := RectangleShape2D.new()
	shape.size = Vector2(34.0, 64.0)
	shape_node.shape = shape
	shape_node.position = Vector2(0.0, -32.0)
	add_child(shape_node)
	queue_redraw()

func _physics_process(delta: float) -> void:
	if match_controller == null or match_controller.is_match_paused() or health <= 0:
		return
	attack_cooldown = maxf(0.0, attack_cooldown - delta)
	invulnerability = maxf(0.0, invulnerability - delta)
	if burning > 0.0:
		burning -= delta
		if int(burning * 10.0) % 5 == 0:
			take_damage(2, Vector2.ZERO, 0)
	var input_state: Dictionary = _read_input()
	var axis: float = float(input_state["right"]) - float(input_state["left"])
	if axis != 0.0:
		facing = 1 if axis > 0.0 else -1
	var jump_pressed: bool = _edge("jump", bool(input_state["jump"]))
	var punch_pressed: bool = _edge("punch", bool(input_state["punch"]))
	var shoot_pressed: bool = _edge("shoot", bool(input_state["shoot"]))
	var throw_pressed: bool = _edge("throw", bool(input_state["throw"]))
	var power_pressed: bool = _edge("power", bool(input_state["power"]))
	var ladder: Rect2 = match_controller.arena.ladder_at(position + Vector2(0.0, -28.0))
	if not on_ladder and ladder.size != Vector2.ZERO and (bool(input_state["up"]) or bool(input_state["down"])):
		on_ladder = true
		ladder_x = ladder.get_center().x
	if on_ladder:
		position.x = move_toward(position.x, ladder_x, 1000.0 * delta)
		velocity = Vector2(0.0, (float(input_state["down"]) - float(input_state["up"])) * CLIMB_SPEED)
		if jump_pressed or (not ladder.grow(16.0).has_point(position + Vector2(0.0, -28.0))):
			on_ladder = false
			if jump_pressed:
				velocity.y = -JUMP_SPEED
	else:
		if roll_timer > 0.0:
			roll_timer -= delta
			velocity.x = roll_direction * ROLL_SPEED
		else:
			velocity.x = move_toward(velocity.x, axis * WALK_SPEED, ACCELERATION * delta)
			if jump_pressed and is_on_floor():
				velocity.y = -JUMP_SPEED
			else:
				velocity.y += GRAVITY * delta
			if bool(input_state["down"]) and absf(axis) > 0.1 and is_on_floor() and roll_timer <= 0.0:
				roll_timer = 0.30
				roll_direction = 1 if axis > 0.0 else -1
			if punch_pressed:
				match_controller.resolve_punch(self)
			if shoot_pressed:
				match_controller.spawn_bullet(self, _aim_direction(bool(input_state["up"]), bool(input_state["down"])))
			if throw_pressed:
				match_controller.spawn_grenade(self, _aim_direction(bool(input_state["up"]), bool(input_state["down"])))
			if power_pressed:
				match_controller.power_blast(self)
	move_and_slide()
	if position.y > 775.0:
		match_controller.fighter_fell(self)
	if match_controller.arena.fire_at(position + Vector2(0.0, -12.0)) and roll_timer <= 0.0:
		burning = maxf(burning, 1.25)
	else:
		burning = maxf(0.0, burning - delta * 0.5)
	queue_redraw()

func _read_input() -> Dictionary:
	return {
		"left": Input.is_key_pressed(int(controls["left"])),
		"right": Input.is_key_pressed(int(controls["right"])),
		"up": Input.is_key_pressed(int(controls["up"])),
		"down": Input.is_key_pressed(int(controls["down"])),
		"jump": Input.is_key_pressed(int(controls["jump"])),
		"punch": Input.is_key_pressed(int(controls["punch"])),
		"shoot": Input.is_key_pressed(int(controls["shoot"])),
		"throw": Input.is_key_pressed(int(controls["throw"])),
		"power": Input.is_key_pressed(int(controls["power"])),
	}

func _edge(name: StringName, value: bool) -> bool:
	var was: bool = bool(_previous.get(name, false))
	_previous[name] = value
	return value and not was

func _aim_direction(up: bool, down: bool) -> Vector2:
	var y := -0.45 if up else (0.45 if down else 0.0)
	return Vector2(float(facing), y).normalized()

func take_damage(amount: int, knockback: Vector2, source_id: int) -> void:
	if health <= 0 or invulnerability > 0.0:
		return
	health = maxi(0, health - amount)
	invulnerability = 0.24
	velocity += knockback
	if health <= 0:
		defeated.emit(player_id)
		match_controller.fighter_defeated(self, source_id)
	queue_redraw()

func heal(amount: int) -> void:
	health = mini(100, health + amount)
	queue_redraw()

func give_ammo(amount: int) -> void:
	ammo = mini(40, ammo + amount)

func give_grenade(amount: int) -> void:
	grenades = mini(8, grenades + amount)

func give_power(amount: int) -> void:
	power = mini(3, power + amount)

func snapshot() -> Dictionary:
	return {"id": player_id, "x": snappedf(position.x, 0.01), "y": snappedf(position.y, 0.01), "vx": snappedf(velocity.x, 0.01), "vy": snappedf(velocity.y, 0.01), "health": health, "ammo": ammo, "grenades": grenades, "power": power, "ladder": on_ladder}

func _draw() -> void:
	var crouched := Input.is_key_pressed(int(controls.get("down", KEY_S))) and is_on_floor() and roll_timer <= 0.0
	var body_height := 42.0 if crouched else 52.0
	var body_y := -body_height
	var body_color := tint if invulnerability <= 0.0 else Color(1.0, 1.0, 1.0, 0.78)
	if burning > 0.0:
		body_color = Color("f08a35")
	draw_rect(Rect2(-16.0, body_y, 32.0, body_height), body_color)
	draw_circle(Vector2(0.0, body_y - 10.0), 13.0, Color("f1c7a2"))
	draw_rect(Rect2(-12.0, body_y - 16.0, 24.0, 6.0), Color("25324c"))
	draw_line(Vector2(0.0, body_y + 8.0), Vector2(float(facing) * 26.0, body_y + 5.0), Color("dfe9ef"), 5.0)
	if ammo > 0:
		draw_circle(Vector2(float(facing) * 30.0, body_y + 5.0), 3.0, Color("f5de79"))
	draw_rect(Rect2(-22.0, body_y - 34.0, 44.0, 5.0), Color(0.02, 0.03, 0.06, 0.8))
	draw_rect(Rect2(-22.0, body_y - 34.0, 44.0 * float(health) / 100.0, 5.0), Color("63e08a") if health > 35 else Color("e56d7a"))
