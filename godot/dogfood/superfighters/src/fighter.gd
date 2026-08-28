class_name Fighter
extends CharacterBody2D

const GRAVITY: float = 1700.0
const JUMP_VEL: float = -430.0
const WALK: float = 170.0
const SPRINT: float = 260.0
const CROUCH_SPEED: float = 70.0
const AIM_SPEED: float = 55.0
const CLIMB: float = 140.0
const ACCEL: float = 2400.0
const AIR_ACCEL: float = 1400.0
const FRICTION: float = 2000.0
const COYOTE: float = 0.09
const JUMP_BUF: float = 0.10
const TAP_WINDOW: float = 0.22
const MAX_HP: float = 100.0
const MAX_STAMINA: float = 100.0

var slot: int = 0
var team: int = 0
var is_bot: bool = false
var is_human: bool = true
var health: float = MAX_HP
var stamina: float = MAX_STAMINA
var facing: float = 1.0
var aiming: bool = false
var aim_dir: Vector2 = Vector2.RIGHT
var crouched: bool = false
var on_ladder: bool = false
var melee_id: String = "fists"
var gun_id: String = "pistol"
var weapon_id: String = "pistol"
var ammo: int = 12
var grenades: int = 3
var melee_cd: float = 0.0
var fire_cd: float = 0.0
var grenade_cd: float = 0.0
var melee_flash: float = 0.0
var throw_flash: float = 0.0
var invuln: float = 0.0
var dead: bool = false
var death_cause: String = ""
var combat_timer: float = 0.0
var coyote: float = 0.0
var jump_buf: float = 0.0
var sprinting: bool = false
var last_tap_dir: float = 0.0
var last_tap_at: float = 99.0
var last_held_x: float = 0.0
var sprite: AnimatedSprite2D
var stand_shape: RectangleShape2D
var crouch_shape: RectangleShape2D
var col_shape: CollisionShape2D
var want_melee: bool = false
var want_fire: bool = false
var want_grenade: bool = false
var last_jump: bool = false


func setup(p_slot: int, p_team: int, p_bot: bool) -> void:
	slot = p_slot
	team = p_team
	is_bot = p_bot
	is_human = not p_bot
	name = "Fighter_%d" % p_slot
	motion_mode = CharacterBody2D.MOTION_MODE_GROUNDED
	collision_layer = Maps.COL_FIGHTER
	collision_mask = Maps.COL_WORLD | Maps.COL_PLATFORM | Maps.COL_PROP
	floor_stop_on_slope = true
	floor_snap_length = 4.0
	safe_margin = 0.2
	melee_id = "fists"
	gun_id = WeaponDefs.start_gun()
	weapon_id = gun_id
	ammo = WeaponDefs.start_ammo()
	grenades = WeaponDefs.start_nades()
	col_shape = CollisionShape2D.new()
	stand_shape = RectangleShape2D.new()
	stand_shape.size = Vector2(10, 22)
	crouch_shape = RectangleShape2D.new()
	crouch_shape.size = Vector2(10, 14)
	col_shape.shape = stand_shape
	col_shape.position = Vector2(0, 1)
	add_child(col_shape)
	var body: ColorRect = ColorRect.new()
	body.name = "Body"
	body.size = Vector2(12, 24)
	body.position = Vector2(-6, -12)
	body.color = Color(0.2, 0.3, 0.5, 1.0)
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(body)
	sprite = Visuals.attach_actor(self, team)
	sprite.play("idle")


func step(delta: float, cmd: Dictionary, kill_plane: float) -> void:
	want_melee = false
	want_fire = false
	want_grenade = false
	if dead:
		velocity.y += GRAVITY * delta
		move_and_slide()
		_play_clip("dead")
		return
	if global_position.y > kill_plane:
		_die("pit")
		return
	melee_cd = maxf(melee_cd - delta, 0.0)
	fire_cd = maxf(fire_cd - delta, 0.0)
	grenade_cd = maxf(grenade_cd - delta, 0.0)
	melee_flash = maxf(melee_flash - delta, 0.0)
	throw_flash = maxf(throw_flash - delta, 0.0)
	invuln = maxf(invuln - delta, 0.0)
	combat_timer = maxf(combat_timer - delta, 0.0)
	last_tap_at += delta
	if combat_timer <= 0.0:
		health = minf(MAX_HP, health + 4.0 * delta)
	var on_floor_now: bool = is_on_floor()
	if on_floor_now:
		coyote = COYOTE
	else:
		coyote = maxf(coyote - delta, 0.0)
	var x: float = float(cmd.get("x", 0.0))
	if x > 0.35:
		x = 1.0
	elif x < -0.35:
		x = -1.0
	else:
		x = 0.0
	if x != 0.0 and last_held_x == 0.0:
		if last_tap_dir == x and last_tap_at <= TAP_WINDOW:
			sprinting = true
		last_tap_dir = x
		last_tap_at = 0.0
	if x == 0.0:
		sprinting = false
	last_held_x = x
	if x != 0.0:
		facing = x
	var fire_held: bool = bool(cmd.get("fire_held", false))
	var nade_held: bool = bool(cmd.get("grenade_held", false)) and grenades > 0
	on_ladder = bool(cmd.get("on_ladder", false))
	aiming = (fire_held and _gun_ready()) or nade_held
	crouched = bool(cmd.get("crouch", false)) and on_floor_now and not aiming and not on_ladder
	_apply_shape()
	if on_ladder:
		jump_buf = 0.0
		last_jump = false
		velocity.y = 0.0
		if bool(cmd.get("jump", false)):
			velocity.y = -CLIMB
		elif bool(cmd.get("crouch", false)):
			velocity.y = CLIMB
	elif bool(cmd.get("jump_pressed", false)) and not fire_held and not nade_held:
		jump_buf = JUMP_BUF
	else:
		jump_buf = maxf(jump_buf - delta, 0.0)
	var jump_held: bool = bool(cmd.get("jump", false)) and not fire_held and not nade_held
	if not on_ladder and jump_buf > 0.0 and coyote > 0.0 and not fire_held and not nade_held:
		velocity.y = JUMP_VEL
		jump_buf = 0.0
		coyote = 0.0
		last_jump = true
	elif last_jump and not jump_held and velocity.y < -80.0:
		velocity.y *= 0.45
		last_jump = false
	if on_floor_now and velocity.y >= 0.0:
		last_jump = false
	var speed: float = WALK
	if crouched:
		speed = CROUCH_SPEED
		sprinting = false
	elif aiming:
		speed = AIM_SPEED
		sprinting = false
	elif sprinting and stamina > 1.0:
		speed = SPRINT
		stamina = maxf(0.0, stamina - 28.0 * delta)
		if stamina <= 0.0:
			sprinting = false
	else:
		stamina = minf(MAX_STAMINA, stamina + 22.0 * delta)
	var target: float = x * speed
	var acc: float = ACCEL if on_floor_now or on_ladder else AIR_ACCEL
	if x == 0.0:
		velocity.x = move_toward(velocity.x, 0.0, FRICTION * delta)
	else:
		velocity.x = move_toward(velocity.x, target, acc * delta)
	if not on_floor_now and not on_ladder:
		velocity.y += GRAVITY * delta
	if aiming:
		aim_dir = _aim_from(cmd)
	else:
		aim_dir = Vector2(facing, 0.0)
	if bool(cmd.get("melee", false)) and melee_cd <= 0.0:
		want_melee = true
		melee_cd = float(WeaponDefs.data(melee_id).get("cooldown", 0.28))
		melee_flash = 0.12
	if _gun_ready() and fire_cd <= 0.0:
		if _is_auto() and fire_held:
			want_fire = true
		elif bool(cmd.get("fire_released", false)):
			want_fire = true
	if bool(cmd.get("grenade_released", false)) and grenade_cd <= 0.0 and grenades > 0:
		want_grenade = true
		grenade_cd = 0.8
		throw_flash = 0.16
	move_and_slide()
	if sprite != null:
		sprite.flip_h = facing < 0.0
	_play_clip(_pose_clip())


func take_damage(amount: float, knock: Vector2) -> void:
	if dead or invuln > 0.0:
		return
	health -= amount
	combat_timer = 3.0
	velocity += knock
	invuln = 0.08
	if health <= 0.0:
		_die("damage")


func kill() -> void:
	_die("script")


func _die(cause: String) -> void:
	if dead:
		return
	dead = true
	health = 0.0
	death_cause = cause
	collision_layer = 0
	velocity = Vector2(facing * -40.0, -120.0)
	_play_clip("dead")


func give_weapon(next_id: String) -> String:
	var spec: Dictionary = WeaponDefs.data(next_id)
	var slot_kind: String = str(spec.get("slot", "melee"))
	if slot_kind == "nade" or next_id == "grenade":
		grenades += maxi(int(spec.get("ammo", 3)), 1)
		return ""
	if slot_kind == "gun":
		var dropped: String = ""
		if gun_id != "" and ammo > 0:
			dropped = gun_id
		gun_id = next_id
		ammo = int(spec.get("ammo", 0))
		weapon_id = next_id
		return dropped
	var dropped_melee: String = ""
	if melee_id != "fists" and melee_id != next_id:
		dropped_melee = melee_id
	melee_id = next_id
	if ammo <= 0:
		weapon_id = next_id
	return dropped_melee


func consume_ammo() -> void:
	if ammo > 0:
		ammo -= 1
		if ammo <= 0:
			weapon_id = melee_id


func consume_grenade() -> void:
	grenades = maxi(grenades - 1, 0)


func _gun_ready() -> bool:
	var spec: Dictionary = WeaponDefs.data(gun_id)
	return str(spec.get("kind", "")) == "gun" and ammo > 0


func _is_auto() -> bool:
	return bool(WeaponDefs.data(gun_id).get("auto", false))


func _aim_from(cmd: Dictionary) -> Vector2:
	var dir: Vector2 = Vector2(facing, 0.0)
	var up: bool = bool(cmd.get("jump", false))
	var down: bool = bool(cmd.get("crouch", false))
	if up and not down:
		dir.y = -1.0
	elif down and not up:
		dir.y = 1.0
	if absf(float(cmd.get("x", 0.0))) < 0.2 and absf(dir.y) > 0.0:
		dir.x = 0.0
	if dir == Vector2.ZERO:
		dir = Vector2(facing, 0.0)
	return dir.normalized()


func _apply_shape() -> void:
	if col_shape == null:
		return
	if crouched:
		col_shape.shape = crouch_shape
		col_shape.position = Vector2(0, 5)
	else:
		col_shape.shape = stand_shape
		col_shape.position = Vector2(0, 1)


func _pose_clip() -> String:
	if dead:
		return "dead"
	if throw_flash > 0.0:
		return "throw"
	if melee_flash > 0.0:
		return "melee"
	if aiming:
		if aim_dir.y < -0.4:
			return "aim_up"
		if aim_dir.y > 0.4:
			return "aim_down"
		return "aim_side"
	if crouched:
		return "crouch"
	if on_ladder:
		return "walk"
	if not is_on_floor():
		if velocity.y < 0.0:
			return "jump"
		return "fall"
	if absf(velocity.x) > 12.0:
		return "walk"
	return "idle"


func _play_clip(clip: String) -> void:
	Visuals.play_fighter(sprite, clip)
