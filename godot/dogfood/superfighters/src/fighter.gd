class_name Fighter
extends CharacterBody2D

## Locomotion numbers come from data/sim/locomotion.json.
## Jump/crouch stay ledger:RL-MOVE-JUMP-CROUCH (assumption).
## Sprint stays ledger:RL-MOVE-SPRINT (assumption).
## Roll stays ledger:RL-MOVE-ROLL (assumption). Dive stays
## ledger:RL-MOVE-DIVE (assumption). Jump-kick stays
## ledger:RL-MOVE-JUMP-KICK (assumption). Fall stays
## ledger:RL-MOVE-FALL (assumption). Ladder stays
## ledger:RL-MOVE-LADDER (assumption). Ledge stays
## ledger:RL-MOVE-LEDGE (assumption). Drop stays
## ledger:RL-MOVE-DROP (assumption). Melee phases stay
## ledger:RL-HIT-PHASES (assumption). Hitboxes stay
## ledger:RL-HIT-BOX (assumption). Friendly-fire stays
## ledger:RL-HIT-FF (assumption). Hitstop stays
## ledger:RL-HIT-HITSTOP (assumption, presentation only).
## Knockback stays ledger:RL-HIT-KNOCK (assumption).
## Knockdown/getup stay ledger:RL-HIT-DOWN (assumption).
## Hit invuln stays ledger:RL-HIT-INVULN (assumption).
## Punch disarm stays ledger:RL-HIT-DISARM (assumption).
## Hold-to-aim stays ledger:RL-CTRL-HOLD-AIM (assumption).
## Aim dirs stay ledger:RL-AIM-DIRS (assumption).
## Semi release stays ledger:RL-FIRE-SEMI (assumption).
## Auto cadence stays ledger:RL-FIRE-AUTO (assumption).
## Hold-to-throw stays ledger:RL-NADE-HOLD (assumption).
## Four slots stay ledger:RL-ITEM-SLOTS-4 (assumption).
## Roster stays ledger:RL-ITEM-ROSTER (assumption).
## Pickup slot replace stays ledger:RL-ITEM-PICK-SLOT (assumption).
## Keep-gun stays ledger:RL-ITEM-KEEP-GUN (assumption).
## Ammo/reload stay ledger:RL-ITEM-AMMO-RELOAD (assumption).
## Chaos crit/knock/spread stay ledger:RL-BAL-CRIT /
## RL-BAL-KNOCK-JITTER / RL-BAL-SPREAD-RNG (assumption).
## Damage caps stay ledger:RL-BAL-CAP (assumption).
## Stamina stays ledger:RL-BAL-STAMINA (assumption).
## InputFrame `ledge` stays reserved. Y8 observation stays
## ledger:RL-MOVE-ROLL-DIVE (unavailable). Not a Y8 observation.

const MAX_HP: float = 100.0
const MAX_STAMINA: float = 100.0
const _Traversal: GDScript = preload("res://src/sim/traversal.gd")
const _Combat: GDScript = preload("res://src/sim/combat.gd")
const _Aim: GDScript = preload("res://src/sim/aim.gd")
const _Expl: GDScript = preload("res://src/sim/explosive.gd")
const _Roster: GDScript = preload("res://src/data/weapons/roster.gd")
const _Inv: GDScript = preload("res://src/data/weapons/inventory.gd")
const _Bal: GDScript = preload("res://src/sim/balance.gd")
const _Hazard: GDScript = preload("res://src/world/prop_hazard.gd")
const _Env: GDScript = preload("res://src/world/env_spec.gd")

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
var last_aim_dir: Vector2 = Vector2.RIGHT
var last_muzzle: Vector2 = Vector2.ZERO
var last_fire_dir: Vector2 = Vector2.ZERO
var last_fire_gun: String = ""
var shots_fired: int = 0
var crouched: bool = false
var on_ladder: bool = false
var melee_id: String = "fists"
var gun_id: String = "pistol"
var weapon_id: String = "pistol"
var explosive_id: String = "grenade"
var power_id: String = ""
var ammo: int = 12
var reserve: int = 0
var mag_size: int = 12
var reload_left: int = 0
var grenades: int = 3
var power_ammo: int = 0
var melee_cd: float = 0.0
var fire_cd: float = 0.0
var grenade_cd: float = 0.0
var melee_flash: float = 0.0
var throw_flash: float = 0.0
var invuln: float = 0.0
var dead: bool = false
var death_cause: String = ""
var death_logged: bool = false
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
var knockdown_ended: bool = false
var knockdown_blocked: bool = false
var getup_left: float = 0.0
var getup_started: bool = false
var getup_ended: bool = false
var hit_airborne: bool = false
var hit_airborne_started: bool = false
var hit_airborne_ended: bool = false
var knockback_started: bool = false
var knockback_ended: bool = false
var knockback_grounded_end: bool = false
var invuln_ticks: int = 0
var invuln_started: bool = false
var invuln_ended: bool = false
var disarm_weapon: String = ""
var peak_fall_vy: float = 0.0
var air_origin_y: float = 0.0
var fall_armed: bool = false
var fall_damage_applied: bool = false
var fall_immune_landed: bool = false
var burning: bool = false
var burn_left: int = 0
var burn_accum: int = 0
var fire_extinguish_count: int = 0
var fire_ignited: bool = false
var fire_tick_applied: bool = false
var fire_ended: bool = false
var wet: bool = false
var acid_contact: bool = false
var env_inside_id: String = ""
var env_entered: bool = false
var env_exited: bool = false
var env_damage_applied: bool = false
var last_tap_dir: float = 0.0
var last_tap_at: float = 99.0
var last_held_x: float = 0.0
var climbing: bool = false
var climb_seq: int = 0
var attach_started: bool = false
var detach_started: bool = false
var last_climb_block: String = ""
var climb_blocked_now: bool = false
var hanging: bool = false
var platform_riding: bool = false
var hang_time: float = 0.0
var hang_seq: int = 0
var hang_started: bool = false
var hang_ended: bool = false
var recover_left: float = 0.0
var recover_total: float = 0.0
var recover_hold_left: float = 0.0
var recover_started: bool = false
var recover_max_step: float = 0.0
var last_ledge_block: String = ""
var hang_anchor: Vector2 = Vector2.ZERO
var hang_from: Vector2 = Vector2.ZERO
var hang_stand: Vector2 = Vector2.ZERO
var ledge_lock_left: float = 0.0
var drop_through_left: float = 0.0
var drop_hold: float = 0.0
var drop_started: bool = false
var drop_ended: bool = false
var last_drop_block: String = ""
var last_contact_nx: float = 0.0
var last_contact_ny: float = 0.0
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
var attack_phase: String = "idle"
var attack_age: int = 0
var attack_seq: int = 0
var attack_style: String = ""
var attack_weapon: String = ""
var attack_hits: PackedInt32Array = PackedInt32Array()
var attack_started: bool = false
var attack_active_entered: bool = false
var attack_recovery_entered: bool = false
var attack_ended: bool = false
var attack_missed: bool = false
var hitstop_left: int = 0
var damage_taken_tick: float = 0.0
var last_crit: bool = false
var last_incoming_raw: float = 0.0
var last_applied_damage: float = 0.0


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
	melee_id = _Roster.start_melee()
	gun_id = WeaponDefs.start_gun()
	weapon_id = gun_id
	explosive_id = _Roster.start_explosive()
	power_id = _Roster.start_power()
	ammo = WeaponDefs.start_ammo()
	reserve = int(_Roster.item(gun_id).get("reserve", 0))
	mag_size = maxi(int(_Roster.item(gun_id).get("mag_size", ammo)), 0)
	reload_left = 0
	grenades = WeaponDefs.start_nades()
	power_ammo = int(_Roster.start_row().get("power_ammo", 0))
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
	attack_started = false
	attack_active_entered = false
	attack_recovery_entered = false
	attack_ended = false
	attack_missed = false
	roll_started = false
	roll_ended = false
	fire_ignited = false
	fire_tick_applied = false
	fire_ended = false
	env_entered = false
	env_exited = false
	env_damage_applied = false
	dive_started = false
	dive_ended = false
	kick_started = false
	kick_ended = false
	fall_damage_applied = false
	fall_immune_landed = false
	sprint_started = false
	sprint_ended = false
	attach_started = false
	detach_started = false
	hang_started = false
	hang_ended = false
	recover_started = false
	drop_started = false
	drop_ended = false
	climb_blocked_now = false
	if ledge_lock_left > 0.0:
		ledge_lock_left = maxf(ledge_lock_left - SimConstants.TICK_DT, 0.0)
	if recover_hold_left > 0.0:
		recover_hold_left = maxf(recover_hold_left - SimConstants.TICK_DT, 0.0)
	if dead:
		last_roll_block = "dead"
		last_dive_block = "dead"
		last_kick_block = "dead"
		last_climb_block = "dead"
		last_ledge_block = "dead"
		last_drop_block = "dead"
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
	_advance_attack()
	if hitstop_left > 0:
		hitstop_left -= 1
	melee_cd = maxf(melee_cd - delta, 0.0)
	fire_cd = maxf(fire_cd - delta, 0.0)
	grenade_cd = maxf(grenade_cd - delta, 0.0)
	_tick_reload()
	melee_flash = maxf(melee_flash - delta, 0.0)
	throw_flash = maxf(throw_flash - delta, 0.0)
	_tick_invuln()
	_tick_burn()
	combat_timer = maxf(combat_timer - delta, 0.0)
	_tick_knock_reaction(delta)
	if knockback_grounded_end:
		knockback_ended = true
		knockback_grounded_end = false
	last_tap_at += delta
	if combat_timer <= 0.0:
		health = minf(MAX_HP, health + 4.0 * delta)
	var on_floor_now: bool = is_on_floor() or platform_riding
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
				sprinting = not wet
			last_tap_dir = x
			last_tap_at = 0.0
		if x == 0.0:
			sprinting = false
	last_held_x = x
	if x != 0.0 and not rolling and not diving:
		facing = x
	var fire_held: bool = bool(cmd.get("fire_held", false))
	var fire_released: bool = bool(cmd.get("fire_released", false))
	var can_throw: bool = grenades > 0 or _Inv.power_throw_ready(self)
	var nade_held: bool = bool(cmd.get("grenade_held", false)) and can_throw
	var nade_released: bool = bool(cmd.get("grenade_released", false)) and can_throw
	on_ladder = bool(cmd.get("on_ladder", false))
	var snap_x: float = float(cmd.get("ladder_snap_x", global_position.x))
	var climb_up_blocked: bool = bool(cmd.get("climb_up_blocked", false))
	var climb_down_blocked: bool = bool(cmd.get("climb_down_blocked", false))
	var one_way_under: bool = bool(cmd.get("one_way_under", false))
	var ledge: Dictionary = {}
	if cmd.get("ledge") is Dictionary:
		ledge = cmd.get("ledge") as Dictionary
	_update_aim(cmd, fire_held, fire_released, nade_held, nade_released)
	var crouch_held: bool = bool(cmd.get("crouch", false))
	var crouch_pressed: bool = bool(cmd.get("crouch_pressed", false))
	var jump_cmd: bool = bool(cmd.get("jump", false))
	var jump_pressed: bool = bool(cmd.get("jump_pressed", false))
	var roll_pressed: bool = bool(cmd.get("roll", false))
	var dive_pressed: bool = bool(cmd.get("dive", false))
	var kick_pressed: bool = bool(cmd.get("kick", false))
	if reaction_locked():
		last_roll_block = "knockdown"
		last_dive_block = "knockdown"
		last_kick_block = "knockdown"
		last_climb_block = "knockdown"
		last_ledge_block = "knockdown"
		last_drop_block = "knockdown"
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
			crouched = crouch_held and on_floor_now and not aiming and not climbing and not hanging
	if kicking:
		kick_time = maxf(kick_time - delta, 0.0)
		if kick_time <= 0.0 or on_floor_now:
			kicking = false
			kick_ended = true
	_tick_drop_through(delta, on_floor_now, crouch_held, one_way_under)
	_tick_hang(delta, jump_cmd, jump_pressed, crouch_held, crouch_pressed, ledge)
	_tick_ladder(delta, x, jump_cmd, jump_pressed, crouch_held, snap_x, climb_up_blocked, climb_down_blocked)
	_apply_shape()
	if rolling or diving or kicking or reaction_locked() or hanging or recover_left > 0.0 or recover_hold_left > 0.0:
		jump_buf = 0.0
		last_jump = false
	elif climbing:
		jump_buf = 0.0
		last_jump = false
	elif jump_pressed and not fire_held and not nade_held:
		jump_buf = jump_buf_time
	else:
		jump_buf = maxf(jump_buf - delta, 0.0)
	var jump_held: bool = bool(cmd.get("jump", false)) and not fire_held and not nade_held
	if not rolling and not diving and not kicking and not reaction_locked() and not climbing and not hanging and recover_left <= 0.0 and jump_buf > 0.0 and coyote > 0.0 and not fire_held and not nade_held:
		velocity.y = jump_vel * (float(_Env.wet_jump_mul()) if wet else 1.0)
		jump_buf = 0.0
		coyote = 0.0
		last_jump = true
	elif last_jump and not jump_held and velocity.y < variable_jump_cut_vy:
		velocity.y *= variable_jump_cut
		last_jump = false
	if on_floor_now and velocity.y >= 0.0:
		last_jump = false
	var speed: float = walk
	if wet:
		sprinting = false
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
	if wet and not rolling and not diving:
		speed *= float(_Env.wet_walk_mul())
	if sprinting and not was_sprinting:
		sprint_started = true
	if was_sprinting and not sprinting:
		sprint_ended = true
	var target: float = facing * speed if rolling or diving else x * speed
	var acc: float = accel if on_floor_now or climbing else air_accel
	if hanging or recover_left > 0.0 or recover_hold_left > 0.0:
		pass
	elif climbing:
		velocity.x = 0.0
	elif rolling:
		velocity.x = move_toward(velocity.x, facing * roll_speed, accel * delta)
	elif diving:
		velocity.x = move_toward(velocity.x, facing * dive_speed, accel * delta)
		velocity.y = maxf(velocity.y, dive_down)
	elif reaction_locked():
		velocity.x = move_toward(velocity.x, 0.0, friction * delta)
	elif x == 0.0:
		velocity.x = move_toward(velocity.x, 0.0, friction * delta)
	else:
		velocity.x = move_toward(velocity.x, target, acc * delta)
	if not on_floor_now and not climbing and not hanging and recover_left <= 0.0 and recover_hold_left <= 0.0:
		if not diving:
			velocity.y += gravity * delta
		velocity.y = minf(velocity.y, max_fall_speed)
		peak_fall_vy = maxf(peak_fall_vy, velocity.y)
	var melee_pressed: bool = bool(cmd.get("melee", false)) or kick_pressed
	if not rolling and not diving and not hanging and not climbing and not reaction_locked() and melee_pressed:
		if crouched and on_floor_now:
			want_melee = true
		elif melee_cd <= 0.0 and attack_phase == "idle":
			if not on_floor_now and not on_ladder:
				_try_start_kick()
			elif kick_pressed and on_floor_now:
				last_kick_block = "ground"
			else:
				want_melee = true
	if not rolling and not diving and _gun_ready() and fire_cd <= 0.0:
		if _is_auto() and fire_held:
			want_fire = true
		elif fire_released:
			want_fire = true
	if not rolling and not diving and nade_released and grenade_cd <= 0.0:
		want_grenade = true
		grenade_cd = _Expl.throw_cd()
		throw_flash = 0.16
	_apply_ledge_motion(delta)
	var recover_pos0: Vector2 = global_position
	move_and_slide()
	if recover_left > 0.0:
		recover_max_step = maxf(recover_max_step, global_position.distance_to(recover_pos0))
		if _ledge_recover_boarded():
			_finish_ledge_recover()
	_record_contacts()
	if climbing and is_on_ceiling():
		if last_climb_block != "solid":
			climb_blocked_now = true
		last_climb_block = "solid"
		velocity.y = 0.0
	if not hanging and not climbing and recover_left <= 0.0:
		_try_ledge_grab(ledge)
	var landed: bool = is_on_floor() and not on_floor_now
	if hit_airborne and is_on_floor() and velocity.y >= 0.0:
		hit_airborne = false
		hit_airborne_ended = true
		knockback_ended = true
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
		sprite.speed_scale = 0.0 if hitstop_left > 0 else 1.0
	if hitstop_left <= 0:
		_play_clip(_pose_clip())


func _tick_drop_through(delta: float, on_floor_now: bool, crouch_held: bool, one_way_under: bool) -> void:
	if drop_through_left > 0.0:
		drop_through_left = maxf(drop_through_left - delta, 0.0)
		collision_mask = Maps.COL_WORLD | Maps.COL_PROP
		floor_snap_length = 0.0
		if drop_through_left <= 0.0:
			collision_mask = Maps.COL_WORLD | Maps.COL_PLATFORM | Maps.COL_PROP
			floor_snap_length = 4.0
			drop_ended = true
		return
	if hanging or climbing or recover_left > 0.0:
		drop_hold = 0.0
		last_drop_block = "busy"
		return
	if rolling or diving or kicking or reaction_locked():
		drop_hold = 0.0
		last_drop_block = "busy"
		return
	if not on_floor_now:
		drop_hold = 0.0
		last_drop_block = "air"
		return
	if not one_way_under or not crouch_held:
		drop_hold = 0.0
		if not crouch_held:
			return
		last_drop_block = "solid"
		return
	drop_hold += delta
	var hold_min: float = _Traversal.f("drop_hold_min", 0.25)
	if drop_hold + 0.0001 < hold_min:
		last_drop_block = "crouch"
		return
	drop_hold = 0.0
	drop_through_left = _Traversal.f("drop_through", 0.20)
	drop_started = true
	collision_mask = Maps.COL_WORLD | Maps.COL_PROP
	floor_snap_length = 0.0
	velocity.y = maxf(velocity.y, 80.0)
	crouched = false
	last_drop_block = ""


func _tick_hang(
	delta: float,
	jump_cmd: bool,
	jump_pressed: bool,
	crouch_held: bool,
	crouch_pressed: bool,
	_ledge: Dictionary
) -> void:
	if recover_left > 0.0:
		return
	if not hanging:
		return
	if jump_cmd or jump_pressed:
		recover_total = _Traversal.f("recover_duration", 0.28)
		recover_left = recover_total
		hang_from = global_position
		recover_started = true
		recover_max_step = 0.0
		hanging = false
		last_ledge_block = ""
		return
	if crouch_held or crouch_pressed:
		hanging = false
		hang_ended = true
		ledge_lock_left = 0.12
		velocity.y = 40.0
		if drop_through_left <= 0.0:
			floor_snap_length = 4.0
		last_ledge_block = ""


func _tick_ladder(
	_delta: float,
	x: float,
	jump_cmd: bool,
	jump_pressed: bool,
	crouch_held: bool,
	snap_x: float,
	climb_up_blocked: bool,
	climb_down_blocked: bool
) -> void:
	if hanging or recover_left > 0.0:
		return
	if rolling or diving or kicking or reaction_locked():
		if climbing:
			climbing = false
			detach_started = true
			last_climb_block = "busy"
		return
	var want_vert: bool = jump_cmd or crouch_held
	if not climbing:
		if not on_ladder:
			return
		if not want_vert:
			return
		climbing = true
		climb_seq += 1
		attach_started = true
		global_position.x = snap_x
		velocity.x = 0.0
		sprinting = false
		crouched = false
		last_climb_block = ""
	if not on_ladder:
		climbing = false
		detach_started = true
		return
	global_position.x = snap_x
	velocity.x = 0.0
	if x != 0.0 and not want_vert:
		climbing = false
		detach_started = true
		return
	if jump_pressed and x != 0.0:
		climbing = false
		detach_started = true
		velocity.x = x * walk
		velocity.y = jump_vel * _Traversal.f("hop_off", 0.55)
		return
	velocity.y = 0.0
	if jump_cmd:
		if climb_up_blocked:
			velocity.y = 0.0
			if last_climb_block != "solid":
				climb_blocked_now = true
			last_climb_block = "solid"
		else:
			velocity.y = -climb
			last_climb_block = ""
	elif crouch_held:
		if climb_down_blocked:
			velocity.y = 0.0
			if last_climb_block != "solid":
				climb_blocked_now = true
			last_climb_block = "solid"
		else:
			velocity.y = climb
			last_climb_block = ""


func _ledge_recover_target() -> Vector2:
	## Climb outside the lip first, then board. A diagonal into hang_stand
	## wedges on the solid corner (~15px short) at climb-step speed.
	if global_position.y > hang_stand.y + 1.5:
		return Vector2(hang_anchor.x, hang_stand.y)
	return hang_stand


func _ledge_recover_boarded() -> bool:
	if hanging:
		return false
	if not is_on_floor():
		return false
	return global_position.distance_to(hang_stand) < _Traversal.f("recover_board_eps", 8.0)


func _finish_ledge_recover() -> void:
	recover_left = 0.0
	hanging = false
	hang_ended = true
	ledge_lock_left = maxf(ledge_lock_left, 0.28)
	recover_hold_left = 0.16
	velocity = Vector2.ZERO
	floor_snap_length = 4.0


func _apply_ledge_motion(delta: float) -> void:
	var dt: float = maxf(delta, 0.0001)
	var max_step: float = minf(float(Maps.TILE) * 0.75, climb * dt)
	if hanging:
		floor_snap_length = 0.0
		var to_hang: Vector2 = hang_anchor - global_position
		var dist: float = to_hang.length()
		if dist <= 2.0:
			velocity = Vector2.ZERO
		else:
			velocity = to_hang.normalized() * (minf(dist, max_step) / dt)
		return
	if recover_left > 0.0:
		recover_left = maxf(recover_left - dt, 0.0)
		if _ledge_recover_boarded():
			_finish_ledge_recover()
			return
		if global_position.y <= hang_stand.y + 2.0:
			floor_snap_length = 4.0
		else:
			floor_snap_length = 0.0
		var to_target: Vector2 = _ledge_recover_target() - global_position
		var dist: float = to_target.length()
		if dist <= 1.5:
			velocity = Vector2(0.0, 60.0)
		else:
			velocity = to_target.normalized() * (minf(dist, max_step) / dt)
		if recover_left <= 0.0 and not _ledge_recover_boarded():
			recover_left = dt
		return
	if recover_hold_left > 0.0:
		velocity = Vector2.ZERO
		floor_snap_length = 4.0
		return
	if drop_through_left <= 0.0:
		floor_snap_length = 4.0


func _record_contacts() -> void:
	if hanging or recover_left > 0.0 or recover_hold_left > 0.0:
		return
	var n: Vector2 = Vector2.ZERO
	if is_on_floor():
		n = get_floor_normal()
	elif is_on_wall():
		n = get_wall_normal()
	elif get_slide_collision_count() > 0:
		var col: KinematicCollision2D = get_last_slide_collision()
		if col != null:
			n = col.get_normal()
	var q: Vector2 = _Traversal.quantize_normal(n)
	last_contact_nx = q.x
	last_contact_ny = q.y


func _try_ledge_grab(ledge: Dictionary) -> void:
	if hanging or climbing or recover_left > 0.0 or ledge_lock_left > 0.0 or recover_hold_left > 0.0:
		return
	if platform_riding:
		last_ledge_block = "ride"
		return
	if rolling or diving or kicking or reaction_locked():
		last_ledge_block = "busy"
		return
	if dead:
		last_ledge_block = "dead"
		return
	if is_on_floor() or platform_riding:
		last_ledge_block = "ground"
		return
	if velocity.y <= 20.0:
		last_ledge_block = "rising"
		return
	if not bool(ledge.get("valid", false)):
		last_ledge_block = "none"
		return
	hanging = true
	hang_seq += 1
	hang_started = true
	climbing = false
	sprinting = false
	crouched = false
	kicking = false
	hang_anchor = Vector2(float(ledge.get("x", global_position.x)), float(ledge.get("y", global_position.y)))
	hang_from = global_position
	hang_stand = Vector2(float(ledge.get("stand_x", global_position.x)), float(ledge.get("stand_y", global_position.y)))
	recover_max_step = 0.0
	velocity = Vector2.ZERO
	last_contact_nx = float(ledge.get("nx", 0.0))
	last_contact_ny = float(ledge.get("ny", 0.0))
	last_ledge_block = ""


func extinguish_fire() -> void:
	## Roll remains selected (VF4-WP3). Water is an extra env path (VF4-WP5).
	fire_extinguish_count += 1
	if burning:
		fire_ended = true
	burning = false
	burn_left = 0
	burn_accum = 0


func ignite_fire(ticks: int) -> void:
	if dead:
		return
	if ticks <= 0:
		return
	if not burning:
		fire_ignited = true
	burning = true
	if ticks > burn_left:
		burn_left = ticks


func take_env_tick(amount: float) -> void:
	if dead:
		return
	amount = _Bal.clamp_hit(amount)
	amount = minf(amount, _Bal.tick_room(damage_taken_tick))
	if amount <= 0.0:
		return
	if not _Bal.is_finite_number(amount):
		return
	last_applied_damage = amount
	damage_taken_tick += amount
	health -= amount
	combat_timer = 3.0
	env_damage_applied = true
	if health <= 0.0:
		_die("damage")


func die_env(cause: String) -> void:
	if dead:
		return
	_die(cause)


func apply_env_tint() -> void:
	if sprite == null or not is_instance_valid(sprite):
		return
	if wet:
		sprite.modulate = Color(0.70, 0.86, 1.0, 1.0)
	elif acid_contact:
		sprite.modulate = Color(0.72, 1.0, 0.58, 1.0)
	else:
		sprite.modulate = Color.WHITE


func take_fire_tick(amount: float) -> void:
	if dead:
		return
	if rolling and (invuln_ticks > 0 or invuln > 0.0):
		return
	amount = _Bal.clamp_hit(amount)
	amount = minf(amount, _Bal.tick_room(damage_taken_tick))
	if amount <= 0.0:
		return
	if not _Bal.is_finite_number(amount):
		return
	last_applied_damage = amount
	damage_taken_tick += amount
	health -= amount
	combat_timer = 3.0
	fire_tick_applied = true
	if health <= 0.0:
		_die("fire")


func _tick_burn() -> void:
	if not burning:
		return
	if dead:
		burning = false
		burn_left = 0
		burn_accum = 0
		fire_ended = true
		return
	burn_left -= 1
	burn_accum += 1
	var interval: int = int(_Hazard.burn_interval())
	var dmg: float = float(_Hazard.burn_damage())
	if burn_accum >= interval:
		burn_accum = 0
		take_fire_tick(dmg)
	if burn_left <= 0:
		burning = false
		burn_left = 0
		burn_accum = 0
		fire_ended = true


func current_pose() -> String:
	if sprite != null and sprite.animation != "":
		return sprite.animation
	return _pose_clip()


func _try_start_roll(on_floor_now: bool, is_aiming: bool) -> void:
	if dead:
		last_roll_block = "dead"
		return
	if reaction_locked():
		last_roll_block = "knockdown"
		return
	if rolling:
		last_roll_block = "rolling"
		return
	if not on_floor_now:
		last_roll_block = "air"
		return
	if on_ladder or climbing or hanging:
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
	grant_invuln_ticks(int(round(roll_invuln / SimConstants.TICK_DT)))
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
	if reaction_locked():
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
	if on_ladder or climbing or hanging:
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
	grant_invuln_ticks(int(round(dive_invuln / SimConstants.TICK_DT)))
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
	if reaction_locked():
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
	if on_ladder or climbing or hanging:
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
	begin_attack("kick")
	velocity.x += facing * kick_impulse_x
	velocity.y = maxf(velocity.y, kick_impulse_y)
	last_kick_block = ""


func begin_attack(style: String) -> void:
	if attack_phase != "idle":
		return
	attack_style = style
	if style == "kick":
		attack_weapon = "kick"
	else:
		attack_weapon = melee_id
	attack_phase = "startup"
	attack_age = 0
	attack_seq += 1
	attack_hits = PackedInt32Array()
	attack_started = true
	attack_missed = false
	var total: int = _Combat.total_ticks(attack_weapon, style)
	melee_cd = float(total) * SimConstants.TICK_DT
	melee_flash = melee_cd


func already_hit(target_slot: int) -> bool:
	var i: int = 0
	while i < attack_hits.size():
		if attack_hits[i] == target_slot:
			return true
		i += 1
	return false


func mark_hit(target_slot: int) -> void:
	if not already_hit(target_slot):
		attack_hits.append(target_slot)


func _advance_attack() -> void:
	if attack_phase == "idle":
		return
	attack_age += 1
	if attack_phase == "startup" and attack_age >= _Combat.startup_ticks(attack_weapon, attack_style):
		attack_phase = "active"
		attack_age = 0
		attack_active_entered = true
	elif attack_phase == "active" and attack_age >= _Combat.active_ticks(attack_weapon, attack_style):
		attack_phase = "recovery"
		attack_age = 0
		attack_recovery_entered = true
		if attack_hits.is_empty():
			attack_missed = true
	elif attack_phase == "recovery" and attack_age >= _Combat.recovery_ticks(attack_weapon, attack_style):
		attack_phase = "idle"
		attack_age = 0
		attack_ended = true


func _cancel_attack() -> void:
	attack_phase = "idle"
	attack_age = 0
	attack_style = ""
	attack_weapon = ""
	attack_hits = PackedInt32Array()
	melee_flash = 0.0


func clear_reaction_pulse() -> void:
	knockdown_started = false
	knockdown_ended = false
	knockdown_blocked = false
	getup_started = false
	getup_ended = false
	hit_airborne_started = false
	hit_airborne_ended = false
	knockback_started = false
	knockback_ended = false
	invuln_started = false
	invuln_ended = false
	disarm_weapon = ""


func reaction_locked() -> bool:
	return knockdown_left > 0.0 or getup_left > 0.0


func holds_gun() -> bool:
	return gun_id != "" and ammo > 0


func grant_invuln_ticks(ticks: int) -> void:
	if ticks <= 0:
		return
	if invuln_ticks <= 0:
		invuln_started = true
	invuln_ticks = maxi(invuln_ticks, ticks)
	invuln = float(invuln_ticks) * SimConstants.TICK_DT


func apply_impulse(knock: Vector2) -> void:
	if absf(knock.x) < 0.01 and absf(knock.y) < 0.01:
		return
	velocity += knock
	knockback_started = true
	if knock.y < -1.0 or not is_on_floor():
		if not hit_airborne:
			hit_airborne_started = true
		hit_airborne = true
	else:
		knockback_grounded_end = true


func apply_knockdown(dir: Vector2) -> bool:
	if dead:
		return false
	if _Combat.chain_lock_block() and reaction_locked():
		knockdown_blocked = true
		return false
	knockdown_left = float(_Combat.knockdown_ticks()) * SimConstants.TICK_DT
	knockdown_started = true
	getup_left = 0.0
	apply_impulse(dir)
	grant_invuln_ticks(_Combat.knockdown_invuln_ticks())
	sprinting = false
	rolling = false
	diving = false
	kicking = false
	climbing = false
	hanging = false
	recover_left = 0.0
	_cancel_attack()
	return true


func take_damage(amount: float, knock: Vector2) -> void:
	last_incoming_raw = amount
	last_applied_damage = 0.0
	if dead or invuln_ticks > 0 or invuln > 0.0:
		return
	# Caps via Balance.clamp_hit / tick_room (preload; class_name cycle).
	amount = _Bal.clamp_hit(amount)
	amount = minf(amount, _Bal.tick_room(damage_taken_tick))
	if amount <= 0.0:
		return
	if not _Bal.is_finite_number(amount):
		return
	last_applied_damage = amount
	damage_taken_tick += amount
	health -= amount
	combat_timer = 3.0
	apply_impulse(knock)
	grant_invuln_ticks(_Combat.hit_invuln_ticks())
	if health <= 0.0:
		_die("damage")


func disarm_gun() -> String:
	if not holds_gun():
		return ""
	var dropped: String = gun_id
	gun_id = ""
	ammo = 0
	reserve = 0
	reload_left = 0
	weapon_id = melee_id
	disarm_weapon = dropped
	return dropped


func _tick_invuln() -> void:
	if invuln_ticks > 0:
		invuln_ticks -= 1
		invuln = float(invuln_ticks) * SimConstants.TICK_DT
		if invuln_ticks <= 0:
			invuln = 0.0
			invuln_ended = true
	else:
		invuln = 0.0


func _tick_knock_reaction(delta: float) -> void:
	if knockdown_left > 0.0:
		knockdown_left = maxf(knockdown_left - delta, 0.0)
		if knockdown_left <= 0.0:
			knockdown_ended = true
			getup_left = float(_Combat.getup_ticks()) * SimConstants.TICK_DT
			getup_started = true
	elif getup_left > 0.0:
		getup_left = maxf(getup_left - delta, 0.0)
		if getup_left <= 0.0:
			getup_ended = true


func kill() -> void:
	_die("script")


func recycle_alive() -> void:
	dead = false
	death_logged = false
	death_cause = ""
	health = MAX_HP
	stamina = MAX_STAMINA
	collision_layer = Maps.COL_FIGHTER
	velocity = Vector2.ZERO
	invuln_ticks = 0
	invuln = 0.0
	knockdown_left = 0.0
	getup_left = 0.0
	hit_airborne = false
	sprinting = false
	rolling = false
	diving = false
	kicking = false
	climbing = false
	hanging = false
	recover_left = 0.0
	visible = true
	melee_id = _Roster.start_melee()
	gun_id = WeaponDefs.start_gun()
	weapon_id = gun_id
	explosive_id = _Roster.start_explosive()
	power_id = _Roster.start_power()
	ammo = WeaponDefs.start_ammo()
	reserve = int(_Roster.item(gun_id).get("reserve", 0))
	mag_size = maxi(int(_Roster.item(gun_id).get("mag_size", ammo)), 0)
	reload_left = 0
	grenades = WeaponDefs.start_nades()
	power_ammo = int(_Roster.start_row().get("power_ammo", 0))
	_cancel_attack()


func _die(cause: String) -> void:
	if dead:
		return
	dead = true
	health = 0.0
	death_cause = cause
	collision_layer = 0
	velocity = Vector2(facing * -40.0, -120.0)
	knockdown_left = 0.0
	getup_left = 0.0
	hit_airborne = false
	invuln_ticks = 0
	invuln = 0.0
	_cancel_attack()
	_play_clip("dead")


func give_weapon(next_id: String) -> String:
	return _Inv.give(self, next_id)


func consume_ammo() -> void:
	if ammo > 0:
		ammo -= 1
		if ammo <= 0:
			weapon_id = melee_id
			_start_reload()


func consume_grenade() -> void:
	grenades = maxi(grenades - 1, 0)


func consume_power() -> void:
	power_ammo = maxi(power_ammo - 1, 0)
	if power_ammo <= 0:
		power_id = ""


func _start_reload() -> void:
	if gun_id == "" or reserve <= 0 or reload_left > 0:
		return
	var spec: Dictionary = WeaponDefs.data(gun_id)
	var ticks: int = int(spec.get("reload_ticks", 0))
	if ticks > 0:
		reload_left = ticks


func _tick_reload() -> void:
	if reload_left <= 0:
		return
	reload_left -= 1
	if reload_left > 0:
		return
	if reserve <= 0 or mag_size <= 0:
		return
	var fill: int = mini(mag_size, reserve)
	ammo = fill
	reserve -= fill
	if ammo > 0:
		weapon_id = gun_id


func _gun_ready() -> bool:
	var spec: Dictionary = WeaponDefs.data(gun_id)
	return str(spec.get("kind", "")) == "gun" and ammo > 0 and reload_left <= 0


func _is_auto() -> bool:
	return _Aim.is_auto(gun_id)


func _update_aim(cmd: Dictionary, fire_held: bool, fire_released: bool, nade_held: bool, nade_released: bool) -> void:
	var gun_ready: bool = _gun_ready()
	if fire_held and gun_ready:
		aiming = true
		aim_dir = _aim_from(cmd)
		last_aim_dir = aim_dir
	elif fire_released and gun_ready:
		aiming = true
		if last_aim_dir != Vector2.ZERO:
			aim_dir = last_aim_dir
		else:
			aim_dir = _aim_from(cmd)
	elif nade_held:
		aiming = true
		aim_dir = _aim_from(cmd)
		last_aim_dir = aim_dir
	elif nade_released:
		aiming = true
		if last_aim_dir != Vector2.ZERO:
			aim_dir = last_aim_dir
		else:
			aim_dir = _aim_from(cmd)
	else:
		aiming = false
		aim_dir = Vector2(facing, 0.0)


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
	if attack_phase != "idle" and attack_style == "kick":
		return "kick"
	if kicking or (melee_flash > 0.0 and not is_on_floor()):
		return "kick"
	if attack_phase != "idle" or melee_flash > 0.0:
		return "melee"
	if knockdown_left > 0.0 or getup_left > 0.0:
		return "crouch"
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
	if hanging or recover_left > 0.0:
		return "hang"
	if recover_hold_left > 0.0:
		return "idle"
	if climbing:
		return "climb"
	if on_ladder:
		return "walk"
	if not is_on_floor() and not platform_riding:
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
	gun_id = str(row.get("gun", row.get("firearm", gun_id)))
	melee_id = str(row.get("melee", melee_id))
	grenades = int(row.get("nades", grenades))
	ammo = int(row.get("ammo", ammo))
	explosive_id = str(row.get("explosive", explosive_id))
	power_id = str(row.get("power", power_id))
	power_ammo = int(row.get("power_ammo", power_ammo))
	reserve = int(row.get("reserve", reserve))
	mag_size = int(row.get("mag_size", mag_size))
	reload_left = int(row.get("reload_left", reload_left))
	facing = SimConstants.dequantize(int(row.get("facing", SimConstants.quantize(facing))))
	crouched = int(row.get("crouched", 0)) != 0
	rolling = int(row.get("rolling", 0)) != 0
	diving = int(row.get("diving", 0)) != 0
	kicking = int(row.get("kicking", 0)) != 0
	sprinting = int(row.get("sprinting", 0)) != 0
	attack_phase = str(row.get("attack_phase", attack_phase))
	attack_seq = int(row.get("attack_seq", attack_seq))
	attack_style = str(row.get("attack_style", attack_style))
	attack_age = int(row.get("attack_age", attack_age))
	on_ladder = int(row.get("on_ladder", 0)) != 0
	climbing = int(row.get("climbing", 0)) != 0
	hanging = int(row.get("hanging", 0)) != 0
	climb_seq = int(row.get("climb_seq", climb_seq))
	hang_seq = int(row.get("hang_seq", hang_seq))
	last_contact_nx = SimConstants.dequantize(int(row.get("contact_nx", 0)))
	last_contact_ny = SimConstants.dequantize(int(row.get("contact_ny", 0)))
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
		invuln_ticks = int(round(invuln / SimConstants.TICK_DT))
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
	if extra.has("climbing"):
		climbing = bool(extra.get("climbing", false))
	if extra.has("hanging"):
		hanging = bool(extra.get("hanging", false))
	if extra.has("climb_seq"):
		climb_seq = int(extra.get("climb_seq", climb_seq))
	if extra.has("hang_seq"):
		hang_seq = int(extra.get("hang_seq", hang_seq))
	if extra.has("contact_nx"):
		last_contact_nx = SimConstants.dequantize(int(extra.get("contact_nx", 0)))
	if extra.has("contact_ny"):
		last_contact_ny = SimConstants.dequantize(int(extra.get("contact_ny", 0)))
	if extra.has("drop_through_left"):
		drop_through_left = SimConstants.dequantize(int(extra.get("drop_through_left", 0)))
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
	if extra.has("getup_left"):
		getup_left = SimConstants.dequantize(int(extra.get("getup_left", 0)))
	if extra.has("hit_airborne"):
		hit_airborne = bool(extra.get("hit_airborne", false))
	if extra.has("invuln_ticks"):
		invuln_ticks = int(extra.get("invuln_ticks", invuln_ticks))
		invuln = float(invuln_ticks) * SimConstants.TICK_DT
	if extra.has("peak_fall_vy"):
		peak_fall_vy = SimConstants.dequantize(int(extra.get("peak_fall_vy", 0)))
	if extra.has("fire_extinguish_count"):
		fire_extinguish_count = int(extra.get("fire_extinguish_count", fire_extinguish_count))
	if extra.has("burning"):
		burning = bool(extra.get("burning", false))
	if extra.has("wet"):
		wet = bool(extra.get("wet", false))
	if extra.has("acid_contact"):
		acid_contact = bool(extra.get("acid_contact", false))
	if extra.has("burn_left"):
		burn_left = int(extra.get("burn_left", burn_left))
	if extra.has("attack_phase"):
		attack_phase = str(extra.get("attack_phase", attack_phase))
	if extra.has("attack_seq"):
		attack_seq = int(extra.get("attack_seq", attack_seq))
	if extra.has("attack_style"):
		attack_style = str(extra.get("attack_style", attack_style))
	if extra.has("attack_weapon"):
		attack_weapon = str(extra.get("attack_weapon", attack_weapon))
	if extra.has("attack_age"):
		attack_age = int(extra.get("attack_age", attack_age))
	if extra.has("hitstop_left"):
		hitstop_left = int(extra.get("hitstop_left", hitstop_left))
	if extra.has("explosive"):
		explosive_id = str(extra.get("explosive", explosive_id))
	if extra.has("power"):
		power_id = str(extra.get("power", power_id))
	if extra.has("reserve"):
		reserve = int(extra.get("reserve", reserve))
	if extra.has("mag_size"):
		mag_size = int(extra.get("mag_size", mag_size))
	if extra.has("reload_left"):
		reload_left = int(extra.get("reload_left", reload_left))
	if extra.has("power_ammo"):
		power_ammo = int(extra.get("power_ammo", power_ammo))
	_apply_shape()
