class_name Fighter
extends CharacterBody2D

## Locomotion numbers come from data/sim/locomotion.json.
## Jump/crouch stay ledger:RL-MOVE-JUMP-CROUCH (assumption).
## Sprint stays ledger:RL-MOVE-SPRINT (assumption).
## Roll stays ledger:RL-MOVE-ROLL (assumption). Dive stays
## ledger:RL-MOVE-DIVE (assumption). Jump-kick stays
## ledger:RL-MOVE-JUMP-KICK (assumption). Fall stays
## ledger:RL-MOVE-FALL (assumption). Y8 observation stays
## ledger:RL-MOVE-ROLL-DIVE (unavailable). Not a Y8 observation.

const MAX_HP: float = 100.0
const MAX_STAMINA: float = 100.0

var gravity: float = 1700.0
var jump_vel: float = -430.0
var walk: float = 170.0
var sprint: float = 260.0
var crouch_speed: float = 70.0
var aim_speed: float = 55.0
var climb: float = 140.0
var accel: float = 2400.0
var air_accel: float = 1400.0
var friction: float = 2000.0
var coyote_time: float = 0.09
var jump_buf_time: float = 0.10
var tap_window: float = 0.22
var stamina_sprint_drain: float = 28.0
var stamina_recover: float = 22.0
var stamina_roll_cost: float = 22.0
var stamina_dive_cost: float = 18.0
var roll_duration: float = 0.28
var roll_invuln: float = 0.20
var roll_speed: float = 320.0
var dive_duration: float = 0.36
var dive_invuln: float = 0.16
var dive_speed: float = 300.0
var dive_down: float = 420.0
var kick_duration: float = 0.18
var kick_impulse_x: float = 90.0
var kick_impulse_y: float = 220.0
var kick_damage: float = 12.0
var dive_tackle_damage: float = 14.0
var fall_damage_speed: float = 560.0
var fall_drop_min: float = 28.0
var fall_damage: float = 16.0
var knockdown_time: float = 0.28
var variable_jump_cut: float = 0.45
var variable_jump_cut_vy: float = -80.0
var max_fall_speed: float = 800.0
var stand_offset: Vector2 = Vector2(0, 1)
var crouch_offset: Vector2 = Vector2(0, 5)
var roll_offset: Vector2 = Vector2(0, 6)
var dive_offset: Vector2 = Vector2(0, 7)

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
var rolling: bool = false
var roll_time: float = 0.0
var roll_seq: int = 0
var roll_started: bool = false
var roll_ended: bool = false
var sprint_started: bool = false
var sprint_ended: bool = false
var last_roll_block: String = ""
var diving: bool = false
var dive_time: float = 0.0
var dive_seq: int = 0
var dive_started: bool = false
var dive_ended: bool = false
var dive_did_tackle: bool = false
var last_dive_block: String = ""
var kicking: bool = false
var kick_time: float = 0.0
var kick_seq: int = 0
var kick_started: bool = false
var kick_ended: bool = false
var last_kick_block: String = ""
var knockdown_left: float = 0.0
var knockdown_started: bool = false
var peak_fall_vy: float = 0.0
var air_origin_y: float = 0.0
var fall_armed: bool = false
var fall_damage_applied: bool = false
var fall_immune_landed: bool = false
var burning: bool = false
var fire_extinguish_count: int = 0
var last_tap_dir: float = 0.0
var last_tap_at: float = 99.0
var last_held_x: float = 0.0
var sprite: AnimatedSprite2D
var stand_shape: RectangleShape2D
var crouch_shape: RectangleShape2D
var roll_shape: RectangleShape2D
var dive_shape: RectangleShape2D
var col_shape: CollisionShape2D
var want_melee: bool = false
var want_kick: bool = false
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
	roll_shape = RectangleShape2D.new()
	roll_shape.size = Vector2(14, 12)
	dive_shape = RectangleShape2D.new()
	dive_shape.size = Vector2(12, 11)
	col_shape.shape = stand_shape
	col_shape.position = stand_offset
	add_child(col_shape)
	Locomotion.apply_to(self)
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
	want_kick = false
	want_fire = false
	want_grenade = false
	roll_started = false
	roll_ended = false
	dive_started = false
	dive_ended = false
	kick_started = false
	kick_ended = false
	knockdown_started = false
	fall_damage_applied = false
	fall_immune_landed = false
	sprint_started = false
	sprint_ended = false
	if dead:
		last_roll_block = "dead"
		last_dive_block = "dead"
		last_kick_block = "dead"
		velocity.y += gravity * delta
		velocity.y = minf(velocity.y, max_fall_speed)
		move_and_slide()
		_play_clip("dead")
		return
	if global_position.y > kill_plane:
		_die("pit")
		return
	# Pit is a product kill plane (ledger:RL-MOVE-LOCO-BASE), not an
	# observed Y8 height. Teleport-to-pit is not this WP's official proof.
	# Dive does not cancel pit death (ledger:RL-MOVE-DIVE assumption).
	melee_cd = maxf(melee_cd - delta, 0.0)
	fire_cd = maxf(fire_cd - delta, 0.0)
	grenade_cd = maxf(grenade_cd - delta, 0.0)
	melee_flash = maxf(melee_flash - delta, 0.0)
	throw_flash = maxf(throw_flash - delta, 0.0)
	invuln = maxf(invuln - delta, 0.0)
	combat_timer = maxf(combat_timer - delta, 0.0)
	knockdown_left = maxf(knockdown_left - delta, 0.0)
	last_tap_at += delta
	if combat_timer <= 0.0:
		health = minf(MAX_HP, health + 4.0 * delta)
	var on_floor_now: bool = is_on_floor()
	if on_floor_now:
		coyote = coyote_time
		air_origin_y = global_position.y
		fall_armed = true
	else:
		coyote = maxf(coyote - delta, 0.0)
	var x: float = float(cmd.get("x", 0.0))
	if x > 0.35:
		x = 1.0
	elif x < -0.35:
		x = -1.0
	else:
		x = 0.0
	var was_sprinting: bool = sprinting
	if not rolling and not diving:
		if x != 0.0 and last_held_x == 0.0:
			if last_tap_dir == x and last_tap_at <= tap_window:
				sprinting = true
			last_tap_dir = x
			last_tap_at = 0.0
		if x == 0.0:
			sprinting = false
	last_held_x = x
	if x != 0.0 and not rolling and not diving:
		facing = x
	var fire_held: bool = bool(cmd.get("fire_held", false))
	var nade_held: bool = bool(cmd.get("grenade_held", false)) and grenades > 0
	on_ladder = bool(cmd.get("on_ladder", false))
	aiming = (fire_held and _gun_ready()) or nade_held
	var crouch_held: bool = bool(cmd.get("crouch", false))
	var crouch_pressed: bool = bool(cmd.get("crouch_pressed", false))
	var roll_pressed: bool = bool(cmd.get("roll", false))
	var dive_pressed: bool = bool(cmd.get("dive", false))
	var kick_pressed: bool = bool(cmd.get("kick", false))
	if knockdown_left > 0.0:
		last_roll_block = "knockdown"
		last_dive_block = "knockdown"
		last_kick_block = "knockdown"
	if rolling:
		roll_time = maxf(roll_time - delta, 0.0)
		if roll_pressed or crouch_pressed:
			last_roll_block = "rolling"
		if roll_time <= 0.0:
			rolling = false
			roll_ended = true
			crouched = crouch_held and on_floor_now and not aiming and not on_ladder
		else:
			crouched = false
			sprinting = false
	elif diving:
		dive_time = maxf(dive_time - delta, 0.0)
		if dive_pressed or (crouch_pressed and sprinting):
			last_dive_block = "diving"
		if on_floor_now or dive_time <= 0.0:
			diving = false
			dive_ended = true
			if on_floor_now:
				fall_immune_landed = true
				peak_fall_vy = 0.0
			crouched = crouch_held and on_floor_now and not aiming and not on_ladder
		else:
			crouched = false
			sprinting = false
	else:
		var want_roll: bool = roll_pressed or (crouch_pressed and sprinting and on_floor_now)
		var want_dive: bool = dive_pressed or (crouch_pressed and sprinting and not on_floor_now)
		if want_roll:
			_try_start_roll(on_floor_now, aiming)
		elif want_dive:
			_try_start_dive(on_floor_now, aiming)
		if not rolling and not diving:
			crouched = crouch_held and on_floor_now and not aiming and not on_ladder
	if kicking:
		kick_time = maxf(kick_time - delta, 0.0)
		if kick_time <= 0.0 or on_floor_now:
			kicking = false
			kick_ended = true
	_apply_shape()
	if rolling or diving or kicking or knockdown_left > 0.0:
		jump_buf = 0.0
		last_jump = false
	elif on_ladder:
		jump_buf = 0.0
		last_jump = false
		velocity.y = 0.0
		if bool(cmd.get("jump", false)):
			velocity.y = -climb
		elif crouch_held:
			velocity.y = climb
	elif bool(cmd.get("jump_pressed", false)) and not fire_held and not nade_held:
		jump_buf = jump_buf_time
	else:
		jump_buf = maxf(jump_buf - delta, 0.0)
	var jump_held: bool = bool(cmd.get("jump", false)) and not fire_held and not nade_held
	if not rolling and not diving and not kicking and knockdown_left <= 0.0 and not on_ladder and jump_buf > 0.0 and coyote > 0.0 and not fire_held and not nade_held:
		velocity.y = jump_vel
		jump_buf = 0.0
		coyote = 0.0
		last_jump = true
	elif last_jump and not jump_held and velocity.y < variable_jump_cut_vy:
		velocity.y *= variable_jump_cut
		last_jump = false
	if on_floor_now and velocity.y >= 0.0:
		last_jump = false
	var speed: float = walk
	if rolling:
		speed = roll_speed
		sprinting = false
	elif diving:
		speed = dive_speed
		sprinting = false
	elif crouched:
		speed = crouch_speed
		sprinting = false
	elif aiming:
		speed = aim_speed
		sprinting = false
	elif sprinting and stamina > 1.0:
		speed = sprint
		stamina = maxf(0.0, stamina - stamina_sprint_drain * delta)
		if stamina <= 0.0:
			sprinting = false
	else:
		stamina = minf(MAX_STAMINA, stamina + stamina_recover * delta)
	if sprinting and not was_sprinting:
		sprint_started = true
	if was_sprinting and not sprinting:
		sprint_ended = true
	var target: float = facing * speed if rolling or diving else x * speed
	var acc: float = accel if on_floor_now or on_ladder else air_accel
	if rolling:
		velocity.x = move_toward(velocity.x, facing * roll_speed, accel * delta)
	elif diving:
		velocity.x = move_toward(velocity.x, facing * dive_speed, accel * delta)
		velocity.y = maxf(velocity.y, dive_down)
	elif knockdown_left > 0.0:
		velocity.x = move_toward(velocity.x, 0.0, friction * delta)
	elif x == 0.0:
		velocity.x = move_toward(velocity.x, 0.0, friction * delta)
	else:
		velocity.x = move_toward(velocity.x, target, acc * delta)
	if not on_floor_now and not on_ladder:
		if not diving:
			velocity.y += gravity * delta
		velocity.y = minf(velocity.y, max_fall_speed)
		peak_fall_vy = maxf(peak_fall_vy, velocity.y)
	if aiming:
		aim_dir = _aim_from(cmd)
	else:
		aim_dir = Vector2(facing, 0.0)
	var melee_pressed: bool = bool(cmd.get("melee", false)) or kick_pressed
	if not rolling and not diving and knockdown_left <= 0.0 and melee_pressed and melee_cd <= 0.0:
		if not on_floor_now and not on_ladder:
			_try_start_kick()
		elif kick_pressed and on_floor_now:
			last_kick_block = "ground"
		else:
			want_melee = true
			melee_cd = float(WeaponDefs.data(melee_id).get("cooldown", 0.28))
			melee_flash = 0.12
	if not rolling and not diving and _gun_ready() and fire_cd <= 0.0:
		if _is_auto() and fire_held:
			want_fire = true
		elif bool(cmd.get("fire_released", false)):
			want_fire = true
	if not rolling and not diving and bool(cmd.get("grenade_released", false)) and grenade_cd <= 0.0 and grenades > 0:
		want_grenade = true
		grenade_cd = 0.8
		throw_flash = 0.16
	move_and_slide()
	var landed: bool = is_on_floor() and not on_floor_now
	if landed:
		var drop: float = global_position.y - air_origin_y
		if diving or fall_immune_landed:
			fall_immune_landed = true
			diving = false
			if not dive_ended:
				dive_ended = true
			peak_fall_vy = 0.0
		elif fall_armed and (drop + 0.0001 >= fall_drop_min or peak_fall_vy + 0.0001 >= fall_damage_speed):
			var hp0: float = health
			take_damage(fall_damage, Vector2.ZERO)
			if health < hp0 - 0.01:
				fall_damage_applied = true
		peak_fall_vy = 0.0
		if kicking:
			kicking = false
			kick_ended = true
	if sprite != null:
		sprite.flip_h = facing < 0.0
	_play_clip(_pose_clip())


func extinguish_fire() -> void:
	## VF4 fire/burning hook. This WP only proves the roll calls it.
	fire_extinguish_count += 1
	burning = false


func current_pose() -> String:
	if sprite != null and sprite.animation != "":
		return sprite.animation
	return _pose_clip()


func _try_start_roll(on_floor_now: bool, is_aiming: bool) -> void:
	if dead:
		last_roll_block = "dead"
		return
	if rolling:
		last_roll_block = "rolling"
		return
	if not on_floor_now:
		last_roll_block = "air"
		return
	if on_ladder:
		last_roll_block = "ladder"
		return
	if is_aiming:
		last_roll_block = "aiming"
		return
	if stamina + 0.0001 < stamina_roll_cost:
		last_roll_block = "stamina"
		return
	stamina = maxf(0.0, stamina - stamina_roll_cost)
	rolling = true
	roll_time = roll_duration
	invuln = maxf(invuln, roll_invuln)
	roll_seq += 1
	roll_started = true
	sprinting = false
	crouched = false
	last_roll_block = ""
	extinguish_fire()


func _try_start_dive(on_floor_now: bool, is_aiming: bool) -> void:
	if dead:
		last_dive_block = "dead"
		return
	if knockdown_left > 0.0:
		last_dive_block = "knockdown"
		return
	if diving:
		last_dive_block = "diving"
		return
	if rolling:
		last_dive_block = "rolling"
		return
	if on_floor_now:
		last_dive_block = "ground"
		return
	if on_ladder:
		last_dive_block = "ladder"
		return
	if is_aiming:
		last_dive_block = "aiming"
		return
	if stamina + 0.0001 < stamina_dive_cost:
		last_dive_block = "stamina"
		return
	stamina = maxf(0.0, stamina - stamina_dive_cost)
	diving = true
	dive_time = dive_duration
	invuln = maxf(invuln, dive_invuln)
	dive_seq += 1
	dive_started = true
	dive_did_tackle = false
	sprinting = false
	crouched = false
	kicking = false
	velocity.x = facing * dive_speed
	velocity.y = maxf(velocity.y, dive_down)
	last_dive_block = ""
	extinguish_fire()


func _try_start_kick() -> void:
	if dead:
		last_kick_block = "dead"
		return
	if knockdown_left > 0.0:
		last_kick_block = "knockdown"
		return
	if rolling:
		last_kick_block = "rolling"
		return
	if diving:
		last_kick_block = "diving"
		return
	if kicking:
		last_kick_block = "kicking"
		return
	if on_ladder:
		last_kick_block = "ladder"
		return
	if is_on_floor():
		last_kick_block = "ground"
		return
	kicking = true
	kick_time = kick_duration
	kick_seq += 1
	kick_started = true
	want_kick = true
	melee_cd = maxf(melee_cd, kick_duration)
	melee_flash = 0.12
	velocity.x += facing * kick_impulse_x
	velocity.y = maxf(velocity.y, kick_impulse_y)
	last_kick_block = ""


func apply_knockdown(dir: Vector2) -> void:
	if dead:
		return
	knockdown_left = maxf(knockdown_left, knockdown_time)
	knockdown_started = true
	velocity += dir
	sprinting = false
	rolling = false
	diving = false
	kicking = false


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
	if diving and dive_shape != null:
		col_shape.shape = dive_shape
		col_shape.position = dive_offset
	elif rolling and roll_shape != null:
		col_shape.shape = roll_shape
		col_shape.position = roll_offset
	elif crouched:
		col_shape.shape = crouch_shape
		col_shape.position = crouch_offset
	else:
		col_shape.shape = stand_shape
		col_shape.position = stand_offset


func _pose_clip() -> String:
	if dead:
		return "dead"
	if throw_flash > 0.0:
		return "throw"
	if kicking or (melee_flash > 0.0 and not is_on_floor()):
		return "kick"
	if melee_flash > 0.0:
		return "melee"
	if diving:
		return "dive"
	if rolling:
		return "roll"
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


func apply_runtime_row(row: Dictionary) -> void:
	global_position = Vector2(
		SimConstants.dequantize(int(row.get("x", 0))),
		SimConstants.dequantize(int(row.get("y", 0)))
	)
	velocity = Vector2(
		SimConstants.dequantize(int(row.get("vx", 0))),
		SimConstants.dequantize(int(row.get("vy", 0)))
	)
	health = SimConstants.dequantize(int(row.get("hp", 0)))
	stamina = SimConstants.dequantize(int(row.get("stamina", 0)))
	dead = int(row.get("dead", 0)) != 0
	death_cause = str(row.get("death_cause", ""))
	weapon_id = str(row.get("weapon", weapon_id))
	gun_id = str(row.get("gun", gun_id))
	melee_id = str(row.get("melee", melee_id))
	grenades = int(row.get("nades", grenades))
	ammo = int(row.get("ammo", ammo))
	facing = SimConstants.dequantize(int(row.get("facing", SimConstants.quantize(facing))))
	crouched = int(row.get("crouched", 0)) != 0
	rolling = int(row.get("rolling", 0)) != 0
	diving = int(row.get("diving", 0)) != 0
	kicking = int(row.get("kicking", 0)) != 0
	sprinting = int(row.get("sprinting", 0)) != 0
	if dead:
		collision_layer = 0
		health = 0.0
	else:
		collision_layer = Maps.COL_FIGHTER
	_apply_shape()
	var pose: String = str(row.get("pose", ""))
	if pose == "":
		pose = _pose_clip()
	_play_clip(pose)


func apply_runtime_extra(extra: Dictionary) -> void:
	if extra.has("is_bot"):
		is_bot = bool(extra.get("is_bot", is_bot))
		is_human = not is_bot
	if extra.has("invuln"):
		invuln = SimConstants.dequantize(int(extra.get("invuln", 0)))
	if extra.has("melee_cd"):
		melee_cd = SimConstants.dequantize(int(extra.get("melee_cd", 0)))
	if extra.has("fire_cd"):
		fire_cd = SimConstants.dequantize(int(extra.get("fire_cd", 0)))
	if extra.has("grenade_cd"):
		grenade_cd = SimConstants.dequantize(int(extra.get("grenade_cd", 0)))
	if extra.has("aim_x") or extra.has("aim_y"):
		aim_dir = Vector2(
			SimConstants.dequantize(int(extra.get("aim_x", 0))),
			SimConstants.dequantize(int(extra.get("aim_y", 0)))
		)
	if extra.has("on_ladder"):
		on_ladder = bool(extra.get("on_ladder", false))
	if extra.has("sprinting"):
		sprinting = bool(extra.get("sprinting", false))
	if extra.has("rolling"):
		rolling = bool(extra.get("rolling", false))
	if extra.has("roll_seq"):
		roll_seq = int(extra.get("roll_seq", roll_seq))
	if extra.has("roll_time"):
		roll_time = SimConstants.dequantize(int(extra.get("roll_time", 0)))
	if extra.has("diving"):
		diving = bool(extra.get("diving", false))
	if extra.has("dive_seq"):
		dive_seq = int(extra.get("dive_seq", dive_seq))
	if extra.has("dive_time"):
		dive_time = SimConstants.dequantize(int(extra.get("dive_time", 0)))
	if extra.has("kicking"):
		kicking = bool(extra.get("kicking", false))
	if extra.has("kick_seq"):
		kick_seq = int(extra.get("kick_seq", kick_seq))
	if extra.has("kick_time"):
		kick_time = SimConstants.dequantize(int(extra.get("kick_time", 0)))
	if extra.has("knockdown_left"):
		knockdown_left = SimConstants.dequantize(int(extra.get("knockdown_left", 0)))
	if extra.has("peak_fall_vy"):
		peak_fall_vy = SimConstants.dequantize(int(extra.get("peak_fall_vy", 0)))
	if extra.has("fire_extinguish_count"):
		fire_extinguish_count = int(extra.get("fire_extinguish_count", fire_extinguish_count))
	if extra.has("burning"):
		burning = bool(extra.get("burning", false))
	_apply_shape()
