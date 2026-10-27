class_name FighterController
extends CharacterBody2D
## Complete AS3-accurate Fighter Locomotion, 24Hz-on-60Hz Physics, Melee Combo, Grab/Throw,
## 5-Slot Inventory, FireSequence Gunplay, Grenade Cooking, and MUGEN Adapter (SF-M2 / SF-M3 / SF-M6).

const _PreloadMugenFighterAdapter = preload("res://game/fighter/mugen_fighter_adapter.gd")
const _PreloadFighterRigView = preload("res://game/fighter/fighter_rig_view.gd")

const RUN_SPEED_24HZ: float = 1.7
const SPRINT_SPEED_24HZ: float = 3.4
const ROLL_SPEED_24HZ: float = 2.0
const DIVE_SPEED_X_24HZ: float = 3.6
const DIVE_SPEED_Y_24HZ: float = -3.0
const CLIMB_SPEED_24HZ: float = 1.5
const SLIDE_SPEED_24HZ: float = 3.0
const PUNCH_GLIDE_SPEED_24HZ: float = 2.0

const GRAVITY_24HZ: float = 0.6
const TERMINAL_VEL_Y_24HZ: float = 11.0
const FALL_TRIGGER_SPEED_24HZ: float = 8.5
const JUMP_POWER_24HZ: float = -5.0
const WALL_JUMP_POWER_Y_24HZ: float = -5.0
const WALL_JUMP_POWER_X_24HZ: float = 1.7

const MELEE_SPECS: Dictionary = {
	"FISTS": {"damages": [6.0, 7.0, 8.0], "ranges": [14.0, 15.0, 17.0], "anims": ["PUNCH_01", "PUNCH_02", "PUNCH_03"], "durability": -1, "sfx_swing": "swing", "sfx_hit": "punch", "can_deflect": false},
	"BATON": {"damages": [7.0, 8.0, 9.0], "ranges": [16.0, 16.0, 20.0], "anims": ["BATON_01", "BATON_02", "BATON_03"], "durability": 20, "sfx_swing": "swing_machete", "sfx_hit": "punch", "can_deflect": true},
	"PIPE": {"damages": [7.0, 8.0, 9.0], "ranges": [16.0, 16.0, 20.0], "anims": ["BATON_01", "BATON_02", "BATON_03"], "durability": 20, "sfx_swing": "swing_machete", "sfx_hit": "punch", "can_deflect": true},
	"BASEBALL_BAT": {"damages": [8.0, 9.0, 10.0], "ranges": [18.0, 18.0, 22.0], "anims": ["SWORD_01", "SWORD_02", "SWORD_03"], "durability": 20, "sfx_swing": "swing_axe", "sfx_hit": "punch", "can_deflect": true},
	"KNIFE": {"damages": [8.0, 9.0, 10.0], "ranges": [16.0, 16.0, 20.0], "anims": ["MACHETE_01", "MACHETE_02", "MACHETE_03"], "durability": 20, "sfx_swing": "swing_sword", "sfx_hit": "cut", "can_deflect": true},
	"MACHETE": {"damages": [8.0, 9.0, 10.0], "ranges": [17.0, 17.0, 23.0], "anims": ["MACHETE_01", "MACHETE_02", "MACHETE_03"], "durability": 20, "sfx_swing": "swing_machete", "sfx_hit": "cut", "can_deflect": true},
	"AXE": {"damages": [11.0, 12.0, 13.0], "ranges": [22.0, 22.0, 24.0], "anims": ["AXE_01", "AXE_02", "AXE_03"], "durability": 20, "sfx_swing": "swing_axe", "sfx_hit": "cut", "can_deflect": true},
	"SWORD": {"damages": [13.0, 14.0, 15.0], "ranges": [22.0, 22.0, 27.0], "anims": ["SWORD_01", "SWORD_02", "SWORD_03"], "durability": 20, "sfx_swing": "swing_sword", "sfx_hit": "cut", "can_deflect": true},
	"CHAINSAW": {"damages": [2.5, 2.5, 2.5], "ranges": [20.0, 20.0, 20.0], "anims": ["CHAINSAW_01", "CHAINSAW_02", "CHAINSAW_01"], "durability": 100, "sfx_swing": "chainsaw", "sfx_hit": "cut", "can_deflect": true},
}

const BURST_WEAPONS: Array[String] = ["UZI", "RIFLE", "TOMMY_GUN", "SMG", "M60"]
const AUTO_FIRE_WEAPONS: Array[String] = []
const WEAPON_COOLDOWNS_24HZ: Dictionary = {
	"PISTOL": 4.0,
	"SILENCED_PISTOL": 4.0,
	"MAGNUM": 8.0,
	"UZI": 6.0,
	"SMG": 6.0,
	"TOMMY_GUN": 6.0,
	"RIFLE": 6.0,
	"M60": 6.0,
	"SHOTGUN": 5.0,
	"SAWED_OFF": 8.0,
	"SNIPER": 16.0,
	"LASER_GUN": 12.0,
	"BAZOOKA": 12.0,
	"FLARE_GUN": 10.0,
	"FLAMETHROWER": 10.0,
}

# --- Contract Public Properties ---
var slot_index: int = 0
var team_id: int = 0
var character_id: String = "johnny"
var display_name: String = "Johnny"
var is_bot: bool = false
var bot_difficulty: int = 2
var hp: float = 100.0
var max_hp: float = 100.0
var sprint_energy: float = 100.0
var max_sprint_energy: float = 100.0
var is_dead: bool = false
var is_gibbed: bool = false
var facing: int = 1
var current_state: String = "IDLE"
var on_ground: bool = true
var sprinting: bool = false
var kneeling: bool = false
var taking_cover: bool = false
var rolling: bool = false
var diving: bool = false
var climbing: bool = false
var falling: bool = false
var knockdowned: bool = false
var aiming: bool = false
var aim_mode: int = 0
var current_aim_pitch: float = 0.0
var burn_state: float = 0.0
var burned: bool = false
var cover_object_id: int = -1
var air_velocity: Vector2 = Vector2.ZERO
var inventory: Dictionary = {1: "FISTS", 2: "", 3: "", 4: "", 5: ""}
var inventory_ammo: Dictionary = {1: -1, 2: 0, 3: 0, 4: 0, 5: 0}
var active_gun_slot: int = 2
var rig_view: Node2D = null
var match_world: Node2D = null

# --- Extended / MUGEN / Test Support Properties ---
var mugen_adapter: _PreloadMugenFighterAdapter = null
var bot_brain_input: Dictionary = {}
var projectile_manager_override: Node2D = null
var fire_hazard_system_override: Node2D = null
var map_loader_override: Node2D = null
var external_targets: Array = []

var default_floor_y: float = 154.0
var use_default_floor: bool = true
var local_solid_rects: Array[Rect2] = []
var local_cloud_rects: Array[Rect2] = []
var local_ladder_rects: Array[Rect2] = []

var hp_Mult: float = 1.0
var speed_mult: float = 1.0
var _hp_damage_timer: float = 0.0
var _pushback_accum: float = 0.0
var _dodge_bullet_cursor: int = 0
var _dodge_rocket_cursor: int = 0

# Animation & State timers (in 24Hz frames)
var anim_frame_idx: int = 1
var weapon_anim_frame_nr: int = 1
var body_rotation_deg: float = 0.0
var _anim_seq_idx: int = 0
var _anim_tick_accum: float = 0.0
var _roll_frames: float = 0.0
var _roll_cooldown_frames: float = 0.0
var _knockdown_frames: float = 0.0
var _stagger_frames: float = 0.0
var _cloud_drop_ignore_until_y: float = -99999.0
var _near_wall_dir: int = 0
var _on_cloud_platform: bool = false
var _ladder_sliding: bool = false
var _ladder_regrab_cooldown_frames: float = 0.0
var ledge_grabbing: bool = false
var _ledge_grab_cooldown_frames: float = 0.0
var _ledge_grab_top_y: float = 0.0
var _ledge_grab_wall_x: float = 0.0
var _ledge_jump_vault_frames: float = 0.0
var _ledge_jump_target_dir: int = 0
var _rocket_riding: bool = false
var _hit_by_bazooka_blast: bool = false
var moving_direction_inversed: int = 0

# Double-tap trackers (in 24Hz frames)
var _last_tap_dir: int = 0
var _last_tap_timer: float = 0.0
var _last_release_dir: int = 0
var _release_timer_24hz: float = 0.0
var _down_tap_timer: float = 0.0
var _prev_input: Dictionary = {}

# Melee & Combo state
var combo_step: int = 0
var _combo_window_frames: float = 0.0
var _melee_active_frames: float = 0.0
var _melee_total_frames: float = 0.0
var _melee_hit_applied: bool = false
var _melee_is_kick: bool = false
var _melee_is_jump_kick: bool = false
var _queued_next_combo: bool = false
var _queued_combo_count: int = 0
var _post_kick_punch_cycle: bool = false
var _picked_up_weapon_this_tick: bool = false
var last_disarmed_weapon_id: String = ""

# Dive-Grab / Throw state
var grabbed_target: Node2D = null
var grabbed_by: Node2D = null
var _sideway_bounced: bool = false

# Ranged FireSequence & Grenade Cooking state
const POST_FIRE_AIM_HOLD_FRAMES: float = 6.0
var _fire_seq_active: bool = false
var _fire_seq_weapon_id: String = ""
var _fire_seq_steps: Array = []
var _fire_seq_idx: int = 0
var _fire_seq_timer: float = 0.0
var _fire_cooldown_frames: float = 0.0
var _aim_pitch_hold_frames: float = 0.0
var _aim_pitch_speed: float = 0.0
var _was_gun_aiming: bool = false
var _aim_canceled_until_release: bool = false
var _throw_canceled_until_release: bool = false
var _aim_hold_frames: float = 0.0
var _fired_during_current_aim: bool = false
var _post_fire_aim_hold_frames: float = 0.0
var _fast_trigger_pending: bool = false
var _roll_burn_immunity_frames: float = 0.0
var _last_fired_weapon_id: String = ""
var _cooking_grenade: bool = false
var _grenade_fuse_frames: float = 72.0
var _grenade_tick_accum: float = 0.0

# MUGEN special state
var _mugen_state_active: bool = false
var _mugen_frame_timer: float = 0.0
var _mugen_hit_applied: bool = false
var _collision_shape: CollisionShape2D = null


func _init() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_ensure_child_nodes()
	_sync_rig_view()


func _ensure_child_nodes() -> void:
	_collision_shape = get_node_or_null("CollisionShape2D") as CollisionShape2D
	if _collision_shape == null:
		_collision_shape = CollisionShape2D.new()
		_collision_shape.name = "CollisionShape2D"
		var rect_shape: RectangleShape2D = RectangleShape2D.new()
		rect_shape.size = Vector2(12.0, 18.0)
		_collision_shape.shape = rect_shape
		_collision_shape.position = Vector2(0.0, -9.0)
		add_child(_collision_shape)

	rig_view = get_node_or_null("FighterRigView") as Node2D
	if rig_view == null:
		var rv: _PreloadFighterRigView = _PreloadFighterRigView.new()
		rv.name = "FighterRigView"
		add_child(rv)
		rig_view = rv


func setup_fighter(
	p_slot: int,
	p_char_id: String,
	p_pos: Vector2,
	p_is_bot: bool = false,
	p_team: int = 0,
	p_diff: int = 2
) -> void:
	_ensure_child_nodes()
	slot_index = p_slot
	character_id = p_char_id.to_lower()
	global_position = p_pos
	default_floor_y = p_pos.y
	is_bot = p_is_bot
	team_id = p_team
	bot_difficulty = clampi(p_diff, 1, 3)

	var reg: Object = _get_registry()
	if reg != null and reg.has_method("ensure_input_map"):
		reg.call("ensure_input_map")
	_PreloadMugenFighterAdapter.ensure_registry_integration(reg)

	if _PreloadMugenFighterAdapter.is_mugen_character_id(character_id):
		mugen_adapter = _PreloadMugenFighterAdapter.new()
		mugen_adapter.load_for_character(character_id, reg)
		display_name = mugen_adapter.display_name
		hp_Mult = mugen_adapter.hp_mult
		speed_mult = mugen_adapter.speed_mult
	else:
		mugen_adapter = null
		var cdata: Dictionary = reg.call("get_character_data", character_id) as Dictionary if reg != null else {}
		display_name = str(cdata.get("display_name", character_id.capitalize()))
		hp_Mult = float(cdata.get("hp_mult", 1.0))
		speed_mult = float(cdata.get("speed_mult", 1.0))

	if rig_view != null:
		rig_view.visible = true
	if rig_view is _PreloadFighterRigView:
		(rig_view as _PreloadFighterRigView).mugen_adapter = mugen_adapter

	max_hp = 100.0 * hp_Mult
	hp = max_hp
	max_sprint_energy = 100.0
	sprint_energy = max_sprint_energy
	is_dead = false
	is_gibbed = false
	facing = 1 if (p_slot % 2 == 0) else -1
	current_state = "IDLE"
	on_ground = true
	sprinting = false
	kneeling = false
	taking_cover = false
	rolling = false
	diving = false
	climbing = false
	falling = false
	knockdowned = false
	aiming = false
	aim_mode = 0
	current_aim_pitch = 0.0
	burn_state = 0.0
	burned = false
	cover_object_id = -1
	air_velocity = Vector2.ZERO
	body_rotation_deg = 0.0

	# Always start completely unarmed (Slot 1 = FISTS, Slots 2..5 empty)
	inventory = {1: "FISTS", 2: "", 3: "", 4: "", 5: ""}
	inventory_ammo = {1: -1, 2: 0, 3: 0, 4: 0, 5: 0}
	active_gun_slot = 2

	combo_step = 0
	_combo_window_frames = 0.0
	_melee_active_frames = 0.0
	_queued_next_combo = false
	_queued_combo_count = 0
	_post_kick_punch_cycle = false
	_roll_frames = 0.0
	_roll_cooldown_frames = 0.0
	_roll_burn_immunity_frames = 0.0
	_last_tap_dir = 0
	_last_tap_timer = 0.0
	_last_release_dir = 0
	_release_timer_24hz = 0.0
	_down_tap_timer = 0.0
	_prev_input.clear()
	_fire_seq_active = false
	_was_gun_aiming = false
	_aim_canceled_until_release = false
	_throw_canceled_until_release = false
	_aim_hold_frames = 0.0
	_aim_pitch_hold_frames = 0.0
	_aim_pitch_speed = 0.0
	_fired_during_current_aim = false
	_post_fire_aim_hold_frames = 0.0
	_fast_trigger_pending = false
	_last_fired_weapon_id = ""
	_cooking_grenade = false
	grabbed_target = null
	grabbed_by = null
	_mugen_state_active = false
	_ladder_sliding = false
	_ladder_regrab_cooldown_frames = 0.0
	ledge_grabbing = false
	_ledge_grab_cooldown_frames = 0.0
	_ledge_grab_top_y = 0.0
	_ledge_grab_wall_x = 0.0
	_ledge_jump_vault_frames = 0.0
	_ledge_jump_target_dir = 0
	_cloud_drop_ignore_until_y = -99999.0
	_rocket_riding = false
	_hit_by_bazooka_blast = false
	moving_direction_inversed = 0

	_set_state("IDLE", true)
	_sync_rig_view()


func equip_default_loadout() -> void:
	equip_weapon("PISTOL", 12)
	equip_weapon("GRENADE", 3)


func on_portal_teleported(flip_x: bool, entry_dir_x: int) -> void:
	# AS3 Player.as:1368-1378 (SetCoordinates): lock MovingDirectionInversed when teleporting through an InverseX portal
	if flip_x and entry_dir_x != 0:
		moving_direction_inversed = -1 if entry_dir_x < 0 else 1


func get_last_input_state() -> Dictionary:
	return _prev_input


func _get_registry() -> Object:
	var tree: SceneTree = Engine.get_main_loop() as SceneTree
	if tree != null and tree.root != null:
		var reg: Node = tree.root.get_node_or_null("SFDataRegistry")
		if reg != null:
			return reg
	if rig_view is _PreloadFighterRigView:
		return (rig_view as _PreloadFighterRigView)._get_registry()
	return null


func _play_sfx(sound_id: String) -> void:
	if DisplayServer.get_name() == "headless":
		return
	var tree: SceneTree = Engine.get_main_loop() as SceneTree
	if tree != null and tree.root != null:
		var audio: Node = tree.root.get_node_or_null("AudioManager")
		if audio != null and audio.is_inside_tree() and audio.has_method("play_sfx_at"):
			audio.call("play_sfx_at", sound_id, global_position)


func _get_map_loader() -> Object:
	if map_loader_override != null:
		return map_loader_override
	if match_world != null:
		var ml: Variant = match_world.get("map_loader")
		if ml is Object:
			return ml as Object
	return null


func _get_projectile_manager() -> Object:
	if projectile_manager_override != null:
		return projectile_manager_override
	if match_world != null:
		var pm: Variant = match_world.get("projectile_manager")
		if pm is Object:
			return pm as Object
	return null


func _get_fire_hazard_system() -> Object:
	if fire_hazard_system_override != null:
		return fire_hazard_system_override
	if match_world != null:
		var fhs: Variant = match_world.get("fire_hazard_system")
		if fhs is Object:
			return fhs as Object
	return null


func _get_all_fighters() -> Array:
	var out: Array = []
	if match_world != null:
		var f_var: Variant = match_world.get("fighters")
		if typeof(f_var) == TYPE_ARRAY:
			for item: Variant in f_var as Array:
				if is_instance_valid(item) and item != self and not out.has(item):
					out.append(item)
	for ef: Variant in external_targets:
		if is_instance_valid(ef) and ef != self and not out.has(ef):
			out.append(ef)
	return out


func get_mid_pos() -> Vector2:
	if diving:
		return global_position
	if knockdowned or is_dead:
		return global_position + Vector2(0.0, -3.0)
	if kneeling or taking_cover or falling:
		return global_position + Vector2(0.0, -6.0)
	return global_position + Vector2(0.0, -8.0)


func get_hit_rect() -> Rect2:
	var h: float = 18.0
	if is_dead:
		h = 4.0
	elif diving:
		h = 8.0
	elif knockdowned:
		h = 10.0
	elif falling or kneeling or taking_cover:
		h = 12.0
	elif rolling:
		h = 14.0
	return Rect2(global_position.x - 6.0, global_position.y - h, 12.0, h)


func get_mugen_clsn1_world_boxes() -> Array[Rect2]:
	if mugen_adapter != null and mugen_adapter.is_mugen_state(current_state):
		return mugen_adapter.get_world_clsn1_boxes(current_state, anim_frame_idx, global_position, facing)
	return []


func equip_weapon(weapon_id: String, ammo_override: int = -999) -> void:
	var key: String = weapon_id.to_upper()
	if key.is_empty():
		return
	var reg: Object = _get_registry()
	var wdata: Dictionary = reg.call("get_weapon_data", key) as Dictionary if reg != null else {}
	var slot: int = int(wdata.get("slot", 0))
	if slot <= 0:
		if MELEE_SPECS.has(key):
			slot = 1
		elif key in ["PISTOL", "SILENCED_PISTOL", "MAGNUM", "UZI", "FLARE_GUN"]:
			slot = 2
		elif key in ["GRENADE", "MOLOTOV", "C4", "MINE"]:
			slot = 4
		elif key in ["MEDKIT", "PILLS", "SLOMO05", "SLOMO10"]:
			slot = 5
		else:
			slot = 3

	var default_ammo: int = int(wdata.get("ammo", 12))
	if slot == 1:
		var mspec: Dictionary = MELEE_SPECS.get(key, MELEE_SPECS["FISTS"]) as Dictionary
		default_ammo = int(mspec.get("durability", 20))
	elif key in ["SHOTGUN", "SAWED_OFF"] and ammo_override == -999:
		default_ammo = 8 if key == "SHOTGUN" else 6
	elif key == "UZI" and ammo_override == -999:
		default_ammo = 25
	elif key == "FLAMETHROWER" and ammo_override == -999:
		default_ammo = 40

	var final_ammo: int = ammo_override if ammo_override != -999 else default_ammo
	if slot == 2 or slot == 3:
		# AS3 PlayerState.as: all guns share a single Ranged weapon slot (CurrentRangeWeapon)
		if str(inventory.get(slot, "")) != key:
			_fire_seq_active = false
			_fire_cooldown_frames = 0.0
		var other_gun_slot: int = 3 if slot == 2 else 2
		inventory[other_gun_slot] = ""
		inventory_ammo[other_gun_slot] = 0
		active_gun_slot = slot
	inventory[slot] = key
	inventory_ammo[slot] = final_ammo


func get_active_weapon_id() -> String:
	var gun_id: String = str(inventory.get(active_gun_slot, ""))
	if not gun_id.is_empty():
		return gun_id
	var alt_slot: int = 3 if active_gun_slot == 2 else 2
	var alt_id: String = str(inventory.get(alt_slot, ""))
	if not alt_id.is_empty():
		active_gun_slot = alt_slot
		return alt_id
	return str(inventory.get(1, "FISTS"))


func get_active_weapon_ammo() -> int:
	var gun_id: String = str(inventory.get(active_gun_slot, ""))
	if not gun_id.is_empty():
		return int(inventory_ammo.get(active_gun_slot, 0))
	return int(inventory_ammo.get(1, -1))


func _is_act_pressed(act: String) -> bool:
	if InputMap.has_action(act) and Input.is_action_pressed(act):
		return true
	# Direct physical scan-code fallback so Vietnamese Telex IME (W->ư, D->đ, S, A...) can never block movement or actions!
	match act:
		"p1_left":
			return Input.is_physical_key_pressed(KEY_LEFT)
		"p1_right":
			return Input.is_physical_key_pressed(KEY_RIGHT)
		"p1_up":
			return Input.is_physical_key_pressed(KEY_UP)
		"p1_down":
			return Input.is_physical_key_pressed(KEY_DOWN)
		"p1_attack":
			return Input.is_physical_key_pressed(KEY_KP_1)
		"p1_aim":
			return Input.is_physical_key_pressed(KEY_KP_2)
		"p1_throw":
			return Input.is_physical_key_pressed(KEY_KP_3)
		"p1_powerup":
			return Input.is_physical_key_pressed(KEY_KP_4)
		"p2_left":
			return Input.is_physical_key_pressed(KEY_A)
		"p2_right":
			return Input.is_physical_key_pressed(KEY_D)
		"p2_up":
			return Input.is_physical_key_pressed(KEY_W)
		"p2_down":
			return Input.is_physical_key_pressed(KEY_S)
		"p2_attack":
			return Input.is_physical_key_pressed(KEY_J)
		"p2_aim":
			return Input.is_physical_key_pressed(KEY_K)
		"p2_throw":
			return Input.is_physical_key_pressed(KEY_L)
		"p2_powerup":
			return Input.is_physical_key_pressed(KEY_SEMICOLON)
	return false


func _is_act_just_pressed(act: String) -> bool:
	return InputMap.has_action(act) and Input.is_action_just_pressed(act)


func _poll_human_input() -> Dictionary:
	var prefix: String = "p1_" if slot_index == 0 else "p2_"
	var has_human_p2: bool = false
	if match_world != null:
		if bool(match_world.get("two_player")):
			has_human_p2 = true
		else:
			for f_var: Variant in _get_all_fighters():
				var other: Node2D = f_var as Node2D
				if int(other.get("slot_index")) == 1 and not bool(other.get("is_bot")):
					has_human_p2 = true
					break
	var allow_both_clusters: bool = (slot_index == 0) and not has_human_p2
	if allow_both_clusters:
		return {
			"left": _is_act_pressed("p1_left") or _is_act_pressed("p2_left"),
			"right": _is_act_pressed("p1_right") or _is_act_pressed("p2_right"),
			"up": _is_act_pressed("p1_up") or _is_act_pressed("p2_up"),
			"down": _is_act_pressed("p1_down") or _is_act_pressed("p2_down"),
			"attack": _is_act_pressed("p1_attack") or _is_act_pressed("p2_attack"),
			"jump": _is_act_pressed("p1_jump") or _is_act_pressed("p2_jump"),
			"aim": _is_act_pressed("p1_aim") or _is_act_pressed("p2_aim"),
			"throw": _is_act_pressed("p1_throw") or _is_act_pressed("p2_throw"),
			"sprint": _is_act_pressed("p1_sprint") or _is_act_pressed("p2_sprint"),
			"powerup": _is_act_pressed("p1_powerup") or _is_act_pressed("p2_powerup"),
			"slot_1": _is_act_just_pressed("p1_slot_1") or _is_act_just_pressed("p2_slot_1"),
			"slot_2": _is_act_just_pressed("p1_slot_2") or _is_act_just_pressed("p2_slot_2"),
			"slot_3": _is_act_just_pressed("p1_slot_3") or _is_act_just_pressed("p2_slot_3"),
			"slot_4": _is_act_just_pressed("p1_slot_4") or _is_act_just_pressed("p2_slot_4"),
		}
	return {
		"left": _is_act_pressed(prefix + "left"),
		"right": _is_act_pressed(prefix + "right"),
		"up": _is_act_pressed(prefix + "up"),
		"down": _is_act_pressed(prefix + "down"),
		"attack": _is_act_pressed(prefix + "attack"),
		"jump": _is_act_pressed(prefix + "jump"),
		"aim": _is_act_pressed(prefix + "aim"),
		"throw": _is_act_pressed(prefix + "throw"),
		"sprint": _is_act_pressed(prefix + "sprint"),
		"powerup": _is_act_pressed(prefix + "powerup"),
		"slot_1": _is_act_just_pressed(prefix + "slot_1"),
		"slot_2": _is_act_just_pressed(prefix + "slot_2"),
		"slot_3": _is_act_just_pressed(prefix + "slot_3"),
		"slot_4": _is_act_just_pressed(prefix + "slot_4"),
	}


func _normalize_input(raw: Dictionary) -> Dictionary:
	var src: Dictionary = raw
	if src.is_empty():
		if is_bot:
			src = bot_brain_input
		else:
			src = _poll_human_input()

	var raw_left: bool = bool(src.get("left", false))
	var raw_right: bool = bool(src.get("right", false))
	# AS3 Player.as:2088-2101 (UpdateInversedDirection) & 1574-1592 / 3745-3763 (PressingRight / PressingLeft):
	# When exiting an InverseX portal while still holding the entry direction key, invert horizontal input until key release!
	if moving_direction_inversed != 0:
		if moving_direction_inversed == 1 and not raw_right:
			moving_direction_inversed = 0
		elif moving_direction_inversed == -1 and not raw_left:
			moving_direction_inversed = 0

	var cur_left: bool = raw_left
	var cur_right: bool = raw_right
	if moving_direction_inversed == -1:
		cur_left = false
		cur_right = raw_left
	elif moving_direction_inversed == 1:
		cur_right = false
		cur_left = raw_right

	var cur_up: bool = bool(src.get("up", false))
	var cur_down: bool = bool(src.get("down", false))
	var cur_attack: bool = bool(src.get("attack", false))
	var cur_jump: bool = bool(src.get("jump", false))
	var cur_sprint: bool = bool(src.get("sprint", false))
	var cur_aim: bool = bool(src.get("aim", src.get("shoot", false)))
	var cur_throw: bool = bool(src.get("throw", false))
	var cur_powerup: bool = bool(src.get("powerup", false))

	var up_just_pressed: bool = bool(src.get("up_just_pressed", cur_up and not bool(_prev_input.get("up", false))))
	var jump_just_pressed: bool = bool(src.get("jump_just_pressed", cur_jump and not bool(_prev_input.get("jump", false))))
	if up_just_pressed and not aiming and not cur_aim and not cur_throw and not climbing:
		jump_just_pressed = true

	var out: Dictionary = {
		"left": cur_left,
		"right": cur_right,
		"up": cur_up,
		"down": cur_down,
		"attack": cur_attack,
		"jump": cur_jump or (cur_up and not aiming and not cur_aim and not cur_throw and not climbing),
		"sprint": cur_sprint,
		"aim": cur_aim,
		"throw": cur_throw,
		"powerup": cur_powerup,
		"kick": bool(src.get("kick", false)),
		"roll": bool(src.get("roll", false)),
		"dive": bool(src.get("dive", false)),
		"mugen_special": str(src.get("mugen_special", "")),
		"left_just_pressed": bool(src.get("left_just_pressed", cur_left and not bool(_prev_input.get("left", false)))),
		"right_just_pressed": bool(src.get("right_just_pressed", cur_right and not bool(_prev_input.get("right", false)))),
		"left_just_released": bool(src.get("left_just_released", not cur_left and bool(_prev_input.get("left", false)))),
		"right_just_released": bool(src.get("right_just_released", not cur_right and bool(_prev_input.get("right", false)))),
		"up_just_pressed": up_just_pressed,
		"down_just_pressed": bool(src.get("down_just_pressed", cur_down and not bool(_prev_input.get("down", false)))),
		"attack_just_pressed": bool(src.get("attack_just_pressed", cur_attack and not bool(_prev_input.get("attack", false)))),
		"jump_just_pressed": jump_just_pressed,
		"aim_just_released": bool(src.get("aim_just_released", not cur_aim and bool(_prev_input.get("aim", false)))),
		"throw_just_released": bool(src.get("throw_just_released", not cur_throw and bool(_prev_input.get("throw", false)))),
		"slot_1": bool(src.get("slot_1", false)),
		"slot_2": bool(src.get("slot_2", false)),
		"slot_3": bool(src.get("slot_3", false)),
		"slot_4": bool(src.get("slot_4", false)),
	}
	_prev_input = {
		"left": cur_left,
		"right": cur_right,
		"up": cur_up,
		"down": cur_down,
		"attack": cur_attack,
		"jump": cur_jump,
		"sprint": cur_sprint,
		"aim": cur_aim,
		"throw": cur_throw,
		"powerup": cur_powerup,
	}
	return out


func step_fighter(step_24hz: float, input_state: Dictionary = {}) -> void:
	if is_dead:
		_step_dead_physics(step_24hz)
		_advance_animation(step_24hz)
		_sync_rig_view()
		return

	var inp: Dictionary = _normalize_input(input_state)

	# 1. Timers, HP Regen & Burn DoT (PlayerState.as:725, 1138, Fires.as)
	if _hp_damage_timer > 0.0:
		_hp_damage_timer = maxf(0.0, _hp_damage_timer - step_24hz)
	elif hp < max_hp and burn_state < 15.0:
		hp = minf(max_hp, hp + 0.1 * step_24hz)

	if _pushback_accum > 0.0:
		_pushback_accum = maxf(0.0, _pushback_accum - 1.5 * step_24hz)

	if _last_tap_timer > 0.0:
		_last_tap_timer = maxf(0.0, _last_tap_timer - step_24hz)
	if _release_timer_24hz > 0.0:
		_release_timer_24hz = maxf(0.0, _release_timer_24hz - step_24hz)
	if _down_tap_timer > 0.0:
		_down_tap_timer = maxf(0.0, _down_tap_timer - step_24hz)
	if _roll_cooldown_frames > 0.0:
		_roll_cooldown_frames = maxf(0.0, _roll_cooldown_frames - step_24hz)
		if not bool(inp.get("down", false)) or burn_state > 0.0:
			_roll_cooldown_frames = 0.0
	if _roll_burn_immunity_frames > 0.0:
		_roll_burn_immunity_frames = maxf(0.0, _roll_burn_immunity_frames - step_24hz)
	# AS3 PlayerState.as:823-826 & Player.as:7342-7345: BackToIdleTimer counts down after the fire sequence completes while not holding Aim
	if _post_fire_aim_hold_frames > 0.0 and not _fire_seq_active and not bool(inp.get("aim", false)):
		_post_fire_aim_hold_frames = maxf(0.0, _post_fire_aim_hold_frames - step_24hz)
	if _combo_window_frames > 0.0:
		_combo_window_frames = maxf(0.0, _combo_window_frames - step_24hz)
		if _combo_window_frames <= 0.0 and _melee_active_frames <= 0.0 and not _mugen_state_active:
			combo_step = 0
			_post_kick_punch_cycle = false
			_queued_combo_count = 0
			_queued_next_combo = false
	if _fire_cooldown_frames > 0.0 and not _fire_seq_active:
		_fire_cooldown_frames = maxf(0.0, _fire_cooldown_frames - step_24hz)
	if _ladder_regrab_cooldown_frames > 0.0:
		_ladder_regrab_cooldown_frames = maxf(0.0, _ladder_regrab_cooldown_frames - step_24hz)
	if _ledge_grab_cooldown_frames > 0.0:
		_ledge_grab_cooldown_frames = maxf(0.0, _ledge_grab_cooldown_frames - step_24hz)

	_verify_ground_support()
	if on_ground:
		falling = false
		body_rotation_deg = 0.0
	_step_burn_damage(step_24hz)
	if is_dead:
		_sync_rig_view()
		return

	# 2. If dive-tackled by another fighter in mid-air (Player.as:7996-8017 UpdateGrabbedPlayer),
	# follow the diver until they land or hit a wall
	if is_instance_valid(grabbed_by):
		if bool(grabbed_by.get("diving")) and not bool(grabbed_by.get("is_dead")):
			current_state = "FALL_B"
			on_ground = false
			_sync_rig_view()
			return
		else:
			grabbed_by = null
			force_fall(0.0, 0.0, true)
	elif grabbed_by != null:
		grabbed_by = null

	# 3. If Rocket Riding, stay in ROCKET_RIDE_R / ROCKET_RIDE_L
	if _rocket_riding:
		current_state = "ROCKET_RIDE_R" if facing >= 0 else "ROCKET_RIDE_L"
		_advance_animation(step_24hz)
		_sync_rig_view()
		return

	# 4. Slot switching & Powerup usage
	_handle_slot_and_pickup_inputs(inp)

	# 5. Step active FireSequence or Grenade cooking
	_step_fire_sequence(step_24hz, inp)
	_step_grenade_cooking(step_24hz, inp)

	# 6. Knockdown / Stagger recovery
	if knockdowned:
		_knockdown_frames -= step_24hz
		air_velocity.x *= pow(0.75, step_24hz)
		var kd_dy: float = 0.0
		if not on_ground:
			air_velocity.y = minf(air_velocity.y + GRAVITY_24HZ * step_24hz, TERMINAL_VEL_Y_24HZ)
			kd_dy = air_velocity.y * step_24hz
		_apply_world_movement(Vector2(air_velocity.x * step_24hz, kd_dy), step_24hz)
		if _knockdown_frames <= 0.0 and on_ground:
			knockdowned = false
			_set_state("KNEEL" if bool(inp["down"]) else "IDLE")
		_advance_animation(step_24hz)
		_sync_rig_view()
		return

	if _stagger_frames > 0.0:
		_stagger_frames -= step_24hz
		if _stagger_frames <= 0.0:
			_set_state("IDLE")

	# 7. Clean up stale grabbed_target if not diving
	if is_instance_valid(grabbed_target) and not diving:
		_drop_dive_tackled_target()
	elif grabbed_target != null and not is_instance_valid(grabbed_target):
		grabbed_target = null

	# 8. Active MUGEN state (4-hit combo / Shunpo Slash / Chakra Wave)
	if _mugen_state_active and mugen_adapter != null:
		_step_mugen_active_state(step_24hz, inp)
		_sync_rig_view()
		return

	# 9. Active Melee / Kick swing
	if _melee_active_frames > 0.0:
		_step_active_melee(step_24hz, inp)
		_advance_animation(step_24hz)
		_sync_rig_view()
		return

	# 10. Check MUGEN special triggers or Combat triggers (Melee / Kick / Aim / Throw)
	var move_dir: int = (1 if bool(inp["right"]) else 0) - (1 if bool(inp["left"]) else 0)
	if move_dir != 0 and not rolling and not diving:
		# AS3 Player.as:6399-6414 (AimLeft) & 8591-8606 (AimRight):
		# Turning left/right while aiming resets CurrentAimPitch = 0 and CurrentChangePitchSpeed = 0
		if aiming and move_dir != facing:
			current_aim_pitch = 0.0
			_aim_pitch_speed = 0.0
			_aim_pitch_hold_frames = 0.0
		facing = move_dir

	var m_spec_req: String = str(inp.get("mugen_special", ""))
	if mugen_adapter != null and not m_spec_req.is_empty():
		if perform_mugen_special(m_spec_req):
			_sync_rig_view()
			return

	# Check Aiming / Shooting / Throwing inputs
	if _handle_aim_and_combat_inputs(step_24hz, inp, move_dir):
		_resolve_solid_prop_space()
		_advance_animation(step_24hz)
		_sync_rig_view()
		return

	# 11. Locomotion State Machine (Roll, Dive, Climb, Jump, Sprint, Run, Kneel/Cover, Idle)
	_step_locomotion(step_24hz, inp, move_dir)
	_resolve_solid_prop_space()
	_advance_animation(step_24hz)
	_sync_rig_view()


func _step_burn_damage(step_24hz: float) -> void:
	if burn_state <= 0.0:
		return
	if burn_state >= 100.0:
		burn_state = 100.0
		# Stage 2 fire (FireRank2): 0.4 HP/frame (never self-extinguishes; requires 2 Rolls!)
		_apply_raw_damage(0.4 * step_24hz)
	elif burn_state >= 15.0:
		# Stage 1 fire (FireRank1): 0.2 HP/frame.
		# AS3 FireNodeData.as:400-402 & Player.as:2434: once burning (burn_state >= 15), fire NEVER decays by time!
		# Instead, if the player does not Roll, Stage 1 escalates up to Stage 2 (burn_state = 100)!
		_apply_raw_damage(0.2 * step_24hz)
		if not is_dead and not rolling:
			burn_state = minf(100.0, burn_state + 0.35 * step_24hz)
	else:
		# Pre-ignition smoke (< 15): cools down if not yet ignited
		burn_state = maxf(0.0, burn_state - 1.2 * step_24hz)


func _decrease_burn_state() -> void:
	# Exact AS3 DecreaseBurnState on Roll (PlayerState.as:742-756):
	# Stage 1 (15 <= BurnState < 100) -> 1 Roll extinguishes to 0.
	# Stage 2 (BurnState >= 100) -> 1st Roll reduces to 50 (Stage 1); 2nd Roll extinguishes to 0!
	# Grant 20 frames (~0.83s) of proximity re-ignition immunity so rolling near a burning player/prop/fire cleanly escapes the fire!
	_roll_burn_immunity_frames = 20.0
	if burn_state < 100.0 and not burned:
		burn_state = 0.0
	else:
		burn_state = 50.0


func _drain_energy(amount: float) -> void:
	sprint_energy = clampf(sprint_energy - amount, 0.0, max_sprint_energy)
	if sprint_energy <= 0.0:
		sprinting = false


func has_any_gun_equipped() -> bool:
	var g2: String = str(inventory.get(2, ""))
	if not g2.is_empty() and int(inventory_ammo.get(2, 0)) > 0:
		return true
	var g3: String = str(inventory.get(3, ""))
	if not g3.is_empty() and int(inventory_ammo.get(3, 0)) > 0:
		return true
	return false


func is_weapon_slot_empty_for(wid: String) -> bool:
	var key: String = wid.to_upper()
	var reg: Object = _get_registry()
	var wdata: Dictionary = reg.call("get_weapon_data", key) as Dictionary if reg != null else {}
	var slot: int = int(wdata.get("slot", 0))
	if slot <= 0:
		if MELEE_SPECS.has(key):
			slot = 1
		elif key in ["PISTOL", "SILENCED_PISTOL", "MAGNUM", "UZI", "FLARE_GUN"]:
			slot = 2
		elif key in ["GRENADE", "MOLOTOV", "C4", "MINE"]:
			slot = 4
		elif key in ["MEDKIT", "PILLS", "SLOMO05", "SLOMO10"]:
			slot = 5
		else:
			slot = 3
	if slot == 1:
		var m_id: String = str(inventory.get(1, "FISTS"))
		return m_id.is_empty() or m_id == "FISTS"
	if slot == 2 or slot == 3:
		return not has_any_gun_equipped()
	if slot == 4:
		var th_id: String = str(inventory.get(4, ""))
		return th_id.is_empty() or int(inventory_ammo.get(4, 0)) <= 0
	if slot == 5:
		if key in ["MEDKIT", "PILLS"]:
			return hp < max_hp
		var p_id: String = str(inventory.get(5, ""))
		return p_id.is_empty() or int(inventory_ammo.get(5, 0)) <= 0
	return true


func _handle_slot_and_pickup_inputs(inp: Dictionary) -> void:
	if bool(inp.get("slot_2", false)) and not str(inventory.get(2, "")).is_empty():
		active_gun_slot = 2
	elif bool(inp.get("slot_3", false)) and not str(inventory.get(3, "")).is_empty():
		active_gun_slot = 3
	elif bool(inp.get("powerup", false)) and not str(inventory.get(5, "")).is_empty():
		use_powerup_slot()

	# AS3 Player.as:1236-1301 (UpdateWeaponGrab) & 3097-3107 / 3156-3166 (Kneel + Attack manual swap):
	_picked_up_weapon_this_tick = false
	if match_world != null and match_world.has_method("update_fighter_weapon_grab"):
		var manual_swap: bool = on_ground and bool(inp.get("down", false)) and bool(inp.get("attack_just_pressed", false))
		var grabbed: bool = bool(match_world.call("update_fighter_weapon_grab", self, manual_swap))
		if manual_swap and grabbed:
			_picked_up_weapon_this_tick = true
	else:
		_check_auto_pickup(inp)


func _check_auto_pickup(inp: Dictionary) -> void:
	if match_world == null or is_dead:
		return
	var pickups_var: Variant = match_world.get("pickups")
	if typeof(pickups_var) != TYPE_ARRAY:
		return
	var pickups: Array = pickups_var as Array
	if pickups.is_empty():
		return

	var reg: Object = _get_registry()
	var best_idx: int = -1
	var best_dist: float = 22.0
	for i: int in range(pickups.size()):
		var p_var: Variant = pickups[i]
		if not is_instance_valid(p_var):
			continue
		var p_node: Node2D = p_var as Node2D
		var dx: float = absf(p_node.global_position.x - global_position.x)
		var dy: float = absf(p_node.global_position.y - global_position.y)
		if dx <= 22.0 and dy <= 22.0:
			var dist: float = dx + dy
			if dist < best_dist:
				best_dist = dist
				best_idx = i

	if best_idx < 0:
		return

	var pickup_node: Node2D = pickups[best_idx] as Node2D
	var wid: String = str(pickup_node.get("weapon_id")).to_upper()
	if wid.is_empty():
		return
	var p_ammo: int = int(pickup_node.get("ammo")) if pickup_node.get("ammo") != null else -999

	# 1. Instant auto-pickup for MEDKIT / PILLS when injured or burning (SLOMO05 / SLOMO10 are stored in slot 5 for manual Key 4 activation!)
	if wid == "MEDKIT":
		if hp < max_hp or burn_state > 0.0:
			hp = max_hp
			burn_state = 0.0
			burned = false
			_play_sfx("powerup")
			if match_world.has_method("spawn_floating_text"):
				match_world.call("spawn_floating_text", global_position + Vector2(0.0, -20.0), "+HP", Color(0.35, 1.0, 0.45, 1.0))
			pickups.remove_at(best_idx)
			pickup_node.queue_free()
			return
	elif wid == "PILLS":
		if hp < max_hp:
			hp = minf(max_hp, hp + 50.0)
			_play_sfx("powerup")
			if match_world.has_method("spawn_floating_text"):
				match_world.call("spawn_floating_text", global_position + Vector2(0.0, -20.0), "+50 HP", Color(0.35, 1.0, 0.45, 1.0))
			pickups.remove_at(best_idx)
			pickup_node.queue_free()
			return

	# 2. Determine weapon slot (1=Melee, 2=Sidearm, 3=Primary, 4=Throwable, 5=Powerup)
	var wdata: Dictionary = reg.call("get_weapon_data", wid) as Dictionary if reg != null else {}
	var slot: int = int(wdata.get("slot", 0))
	if slot <= 0:
		if MELEE_SPECS.has(wid):
			slot = 1
		elif wid in ["PISTOL", "SILENCED_PISTOL", "MAGNUM", "UZI", "FLARE_GUN"]:
			slot = 2
		elif wid in ["GRENADE", "MOLOTOV", "C4", "MINE"]:
			slot = 4
		elif wid in ["MEDKIT", "PILLS", "SLOMO05", "SLOMO10"]:
			slot = 5
		else:
			slot = 3

	var cur_in_slot: String = str(inventory.get(slot, ""))
	var cur_ammo: int = int(inventory_ammo.get(slot, 0))
	var slot_empty: bool = cur_in_slot.is_empty() or (slot == 1 and cur_in_slot == "FISTS") or cur_ammo <= 0
	var want_manual_swap: bool = on_ground and ((bool(inp.get("down", false)) and bool(inp.get("attack_just_pressed", false))) or bool(inp.get("down_just_pressed", false)))

	if slot_empty or want_manual_swap:
		var pickup_ammo_val: int = p_ammo if p_ammo > 0 else int(wdata.get("ammo", 12))
		var stacked_same: bool = (not slot_empty and cur_in_slot == wid and slot in [2, 3, 4] and cur_ammo > 0)
		if not slot_empty and want_manual_swap and not stacked_same and match_world.has_method("spawn_weapon_pickup"):
			match_world.call("spawn_weapon_pickup", cur_in_slot, global_position + Vector2(float(-facing) * 8.0, -4.0), cur_ammo, false)
		if stacked_same:
			equip_weapon(wid, cur_ammo + pickup_ammo_val)
		else:
			equip_weapon(wid, p_ammo if p_ammo > 0 else -999)
		_picked_up_weapon_this_tick = want_manual_swap
		_play_sfx("pickup" if slot in [1, 4] else "pickup_gun")
		if match_world.has_method("spawn_floating_text"):
			var label_str: String = str(wdata.get("display_name", wid))
			if stacked_same:
				label_str += " +" + str(pickup_ammo_val)
			match_world.call("spawn_floating_text", global_position + Vector2(0.0, -20.0), label_str, Color(1.0, 0.92, 0.35, 1.0))
		pickups.remove_at(best_idx)
		pickup_node.queue_free()


func use_powerup_slot() -> bool:
	var p_id: String = str(inventory.get(5, ""))
	if p_id.is_empty() or int(inventory_ammo.get(5, 0)) <= 0:
		return false
	if p_id == "MEDKIT":
		hp = max_hp
		burn_state = 0.0
		burned = false
	elif p_id == "PILLS":
		hp = minf(max_hp, hp + 50.0)
	elif p_id == "SLOMO05" or p_id == "SLOMO10":
		if match_world != null and match_world.has_method("activate_slowmo"):
			match_world.call("activate_slowmo", 120.0 if p_id == "SLOMO05" else 240.0)
		if match_world != null and match_world.has_method("spawn_floating_text"):
			match_world.call("spawn_floating_text", global_position + Vector2(0.0, -20.0), "SLOW-MO!", Color(0.45, 0.9, 1.0, 1.0))
	_play_sfx("powerup")
	inventory[5] = ""
	inventory_ammo[5] = 0
	return true


func _play_weapon_draw_sfx(weapon_id: String) -> void:
	var key: String = weapon_id.to_upper()
	match key:
		"SHOTGUN", "SAWED_OFF":
			_play_sfx("shotgun_aim")
		"BAZOOKA":
			_play_sfx("bazooka_aim")
		"RIFLE", "TOMMY_GUN", "SMG", "M60", "SNIPER", "LASER_GUN", "FLAMETHROWER":
			_play_sfx("rifle_draw")
		_:
			_play_sfx("aim_small")


func _begin_aiming_session(mode: int) -> void:
	# AS3 PlayerState.as:1104-1112 (set Aiming(true)):
	# Entering Aiming from a holstered/non-aiming state resets CurrentAimPitch = 0 (horizontal forward)
	# and CurrentChangePitchSpeed = 0, while already-active aiming (e.g. during post-shot linger) preserves CurrentAimPitch!
	if not aiming or aim_mode != mode:
		aiming = true
		aim_mode = mode
		current_aim_pitch = 0.0
		_aim_pitch_speed = 0.0
		_aim_pitch_hold_frames = 0.0
		kneeling = false


func _abort_aiming_session() -> void:
	# AS3 Player.as:8228-8257 (AbortAiming) & PlayerState.as:1113-1116 (set Aiming(false)):
	aiming = false
	current_aim_pitch = 0.0
	_aim_pitch_speed = 0.0
	_aim_pitch_hold_frames = 0.0
	_was_gun_aiming = false
	_aim_hold_frames = 0.0
	_fired_during_current_aim = false
	_post_fire_aim_hold_frames = 0.0
	_fast_trigger_pending = false
	weapon_anim_frame_nr = 1


func _handle_aim_and_combat_inputs(step_24hz: float, inp: Dictionary, move_dir: int) -> bool:
	if not bool(inp.get("aim", false)):
		_aim_canceled_until_release = false
	if not bool(inp.get("throw", false)):
		_throw_canceled_until_release = false

	# AS3 Player.as:1066-1092 (RangedDown), 1151 (CheckAimDrop), 8228-8257 (AbortAiming) & PlayerState.as:549-556, 662-677:
	# Fighters can NEVER aim or hold a gun while airborne (!OnGround), Rolling, Diving, Falling, Climbing, or Ledge-Grabbing!
	if not on_ground or rolling or diving or falling or climbing or ledge_grabbing or knockdowned:
		if aiming or _fire_seq_active or _cooking_grenade or _post_fire_aim_hold_frames > 0.0 or _was_gun_aiming or _fast_trigger_pending:
			if _cooking_grenade:
				_drop_live_throwable()
			_fire_seq_active = false
			_cooking_grenade = false
			_abort_aiming_session()
		if bool(inp.get("aim", false)):
			_aim_canceled_until_release = true
		if bool(inp.get("throw", false)):
			_throw_canceled_until_release = true
		if bool(inp.get("attack_just_pressed", false)) and not on_ground and not climbing and not rolling and not diving and not falling and not ledge_grabbing and not knockdowned:
			_start_kick(true)
			return true
		return false

	# Allow Roll (Down + Left/Right or Roll key), Dive (Sprint + Down + Left/Right), or Jump on the ground to immediately cancel Aiming / Firing / Grenade cooking
	# and suppress firing when the canceled Aim key is released!
	var want_roll_input: bool = not sprinting and ((bool(inp.get("down", false)) and move_dir != 0) or bool(inp.get("roll", false)))
	var want_dive_input: bool = (sprinting and move_dir != 0 and (bool(inp.get("down", false)) or bool(inp.get("down_just_pressed", false)))) or bool(inp.get("dive", false))
	var want_jump_input: bool = bool(inp.get("jump_just_pressed", false))
	if want_roll_input or want_dive_input or want_jump_input:
		if aiming or _fire_seq_active or _cooking_grenade or _post_fire_aim_hold_frames > 0.0 or _was_gun_aiming or _fast_trigger_pending or bool(inp.get("aim", false)) or bool(inp.get("throw", false)):
			if _cooking_grenade:
				_drop_live_throwable()
			_fire_seq_active = false
			_cooking_grenade = false
			_abort_aiming_session()
			if bool(inp.get("aim", false)):
				_aim_canceled_until_release = true
			if bool(inp.get("throw", false)):
				_throw_canceled_until_release = true
		if want_roll_input and (bool(inp.get("left_just_pressed", false)) or bool(inp.get("right_just_pressed", false)) or bool(inp.get("down_just_pressed", false)) or bool(inp.get("roll", false)) or bool(inp.get("aim", false))):
			_roll_cooldown_frames = 0.0
		return false

	var want_throw_aim: bool = bool(inp.get("throw", false)) and not _throw_canceled_until_release and not str(inventory.get(4, "")).is_empty() and int(inventory_ammo.get(4, 0)) > 0
	var active_gun: String = ""
	var sidearm: String = str(inventory.get(2, ""))
	var primary: String = str(inventory.get(3, ""))
	if active_gun_slot == 3 and not primary.is_empty() and int(inventory_ammo.get(3, 0)) > 0:
		active_gun = primary
	elif active_gun_slot == 2 and not sidearm.is_empty() and int(inventory_ammo.get(2, 0)) > 0:
		active_gun = sidearm
	elif not primary.is_empty() and int(inventory_ammo.get(3, 0)) > 0:
		active_gun_slot = 3
		active_gun = primary
	elif not sidearm.is_empty() and int(inventory_ammo.get(2, 0)) > 0:
		active_gun_slot = 2
		active_gun = sidearm
	elif active_gun_slot == 3 and not primary.is_empty():
		active_gun = primary
	elif active_gun_slot == 2 and not sidearm.is_empty():
		active_gun = sidearm
	elif not primary.is_empty():
		active_gun_slot = 3
		active_gun = primary
	elif not sidearm.is_empty():
		active_gun_slot = 2
		active_gun = sidearm

	var want_gun_aim: bool = bool(inp.get("aim", false)) and not _aim_canceled_until_release and not active_gun.is_empty()

	# 1. Throwable Aiming & Cooking
	if want_throw_aim:
		_was_gun_aiming = false
		_aim_hold_frames = 0.0
		_post_fire_aim_hold_frames = 0.0
		_fast_trigger_pending = false
		_begin_aiming_session(1)
		sprinting = false
		_update_aim_pitch_from_input(step_24hz, inp)
		var th_id: String = str(inventory.get(4, "GRENADE"))
		if th_id == "GRENADE" and not _cooking_grenade:
			_cooking_grenade = true
			_grenade_fuse_frames = 72.0
			_grenade_tick_accum = 0.0
			_play_sfx("grenade_pin")
		current_state = "AIM_MOLOTOV" if th_id == "MOLOTOV" else "AIM_GRENADE"
		weapon_anim_frame_nr = 1
		return true

	if bool(inp.get("throw_just_released", false)) and not _throw_canceled_until_release and ((aiming and aim_mode == 1) or _cooking_grenade):
		_execute_throw()
		_abort_aiming_session()
		return true

	# AS3 Player.as:3087-3096 (Melee cancels Aiming immediately when not actively holding Aim):
	if not want_gun_aim and not _fire_seq_active and (bool(inp.get("attack_just_pressed", false)) or bool(inp.get("kick", false))):
		_abort_aiming_session()

	# 2. Ranged Gun Aiming, 1-Button Firing & Post-Shot Hold Linger (AS3 Player.as:1066-1092, 7266-7438, 8538-8553)
	if want_gun_aim:
		var gun_to_show: String = _fire_seq_weapon_id if _fire_seq_active else active_gun
		var was_already_aiming_gun: bool = aiming and aim_mode == 0
		_begin_aiming_session(0)
		if not _was_gun_aiming:
			_was_gun_aiming = true
			_aim_hold_frames = 0.0
			_fired_during_current_aim = false
			_fast_trigger_pending = true
			if not was_already_aiming_gun and not _fire_seq_active:
				_play_weapon_draw_sfx(gun_to_show)
		_aim_hold_frames += step_24hz
		_post_fire_aim_hold_frames = POST_FIRE_AIM_HOLD_FRAMES
		sprinting = false
		_update_aim_pitch_from_input(step_24hz, inp)
		current_state = _get_aim_state_for_weapon(gun_to_show)
		if not _fire_seq_active:
			weapon_anim_frame_nr = 1
			var is_auto_gun: bool = active_gun in AUTO_FIRE_WEAPONS
			if is_auto_gun and _aim_hold_frames >= 1.0 and _fire_cooldown_frames <= 0.0:
				if trigger_ranged_fire(active_gun):
					_fired_during_current_aim = true
					_fast_trigger_pending = false
			elif bool(inp.get("attack", false)) and _fire_cooldown_frames <= 0.0:
				if trigger_ranged_fire(active_gun):
					_fired_during_current_aim = true
					_fast_trigger_pending = false
		return true

	# AS3 RangedUp() (Player.as:8538-8553): releasing the shoot button fires and sets BackToIdleTimer = 6
	if (bool(inp.get("aim_just_released", false)) or _was_gun_aiming) and not _aim_canceled_until_release and aiming and aim_mode == 0:
		_was_gun_aiming = false
		_aim_hold_frames = 0.0
		if not active_gun.is_empty():
			_post_fire_aim_hold_frames = POST_FIRE_AIM_HOLD_FRAMES
			var should_fire_on_release: bool = (not (active_gun in AUTO_FIRE_WEAPONS)) or (not _fired_during_current_aim)
			_fired_during_current_aim = false
			if should_fire_on_release:
				if _fire_cooldown_frames <= 0.0 and not _fire_seq_active:
					trigger_ranged_fire(active_gun)
					_fast_trigger_pending = false
				else:
					# AS3 Player.as:7421-7432 (FastTrigger): queue shot to fire immediately when current fire sequence / cooldown ends
					_fast_trigger_pending = true
					_post_fire_aim_hold_frames = maxf(_post_fire_aim_hold_frames, _fire_cooldown_frames + 2.0)
			else:
				_fast_trigger_pending = false

	# AS3 ProgressAFS() (Player.as:7413-7438): keep gun drawn during active FireSequence and while BackToIdleTimer > 0 (6 ticks @ 24Hz)
	if _fire_seq_active or _post_fire_aim_hold_frames > 0.0:
		if _fast_trigger_pending and not _fire_seq_active and _fire_cooldown_frames <= 0.0 and not active_gun.is_empty():
			_fast_trigger_pending = false
			_post_fire_aim_hold_frames = POST_FIRE_AIM_HOLD_FRAMES
			trigger_ranged_fire(active_gun)
		var linger_gun: String = _fire_seq_weapon_id if _fire_seq_active else (active_gun if not active_gun.is_empty() else _last_fired_weapon_id)
		if not linger_gun.is_empty():
			aiming = true
			aim_mode = 0
			sprinting = false
			_update_aim_pitch_from_input(step_24hz, inp)
			current_state = _get_aim_state_for_weapon(linger_gun)
			if not _fire_seq_active:
				weapon_anim_frame_nr = 1
			return true

	# Once BackToIdleTimer expires (or when not aiming), AbortAiming() holsters the weapon and resets CurrentAimPitch = 0.0
	_abort_aiming_session()

	# 3. Kick / JumpKick / Melee / MUGEN Combo on Attack press
	if bool(inp.get("kick", false)) and on_ground:
		_start_kick(false)
		return true

	if bool(inp.get("attack_just_pressed", false)):
		# AS3 Player.as:3097-3107: if Down + Attack just grabbed/swapped a weapon on the ground, do not also swing a melee punch on the same frame!
		if _picked_up_weapon_this_tick:
			_picked_up_weapon_this_tick = false
			return false
		if not on_ground and not climbing:
			_start_kick(true)
			return true
		# AS3 Player.as:695-698, 3111-3125 & 5724-5762 (Melee -> Kick vs 3-Punch Combo Loop):
		# When standing near a kickable prop/skylight/live grenade with no enemy in punch range and not currently in the post-kick 3-punch cycle, Attack performs a KICK;
		# continued spamming cycles KICK -> PUNCH_01 -> PUNCH_02 -> PUNCH_03 -> KICK -> PUNCH_01 -> PUNCH_02 -> PUNCH_03!
		var pm_k: Object = _get_projectile_manager()
		var live_bomb_at_feet: bool = (pm_k != null and pm_k.has_method("has_kickable_throwable_near") and bool(pm_k.call("has_kickable_throwable_near", global_position, facing)))
		var can_kick_now: bool = (combo_step == 0 and not _post_kick_punch_cycle)
		if on_ground and can_kick_now and (live_bomb_at_feet or (not _has_enemy_in_melee_range() and has_kickable_target_nearby())):
			_start_kick(false)
			return true
		if mugen_adapter != null and str(inventory.get(1, "FISTS")) == "FISTS":
			if bool(inp.get("sprint", false)) or sprinting:
				if perform_mugen_special("SHUNPO_SLASH"):
					return true
			if bool(inp.get("up", false)):
				if perform_mugen_special("CHAKRA_WAVE"):
					return true
			_start_mugen_combo_step(1)
			return true
		var next_punch_step: int = 1 if (combo_step <= 0 or combo_step >= 3) else (combo_step + 1)
		_start_melee_combo_step(next_punch_step)
		return true

	return false


func _has_enemy_in_melee_range() -> bool:
	var reach: float = 18.0
	var box_x: float = global_position.x if facing >= 0 else (global_position.x - reach)
	var m_rect: Rect2 = Rect2(box_x, global_position.y - 20.0, reach, 20.0)
	for f_var: Variant in _get_all_fighters():
		var target: Node2D = f_var as Node2D
		if bool(target.get("is_dead")):
			continue
		if team_id > 0 and int(target.get("team_id")) == team_id:
			continue
		var t_rect: Rect2 = Rect2(target.global_position.x - 6.0, target.global_position.y - 18.0, 12.0, 18.0)
		if target.has_method("get_hit_rect"):
			t_rect = target.call("get_hit_rect") as Rect2
		if m_rect.intersects(t_rect):
			return true
	return false


func _is_standing_on_prop_rect(p_rect: Rect2) -> bool:
	return on_ground and absf(global_position.y - p_rect.position.y) <= 3.0 and global_position.x >= p_rect.position.x - 4.0 and global_position.x <= p_rect.end.x + 4.0


func has_kickable_target_nearby() -> bool:
	# AS3 Player.as:7214-7229 (KickHit): ground kick scans x in 0..8*facing and y from _this_y - 8 down to _this_y + 4 (exact visual foot reach = 9.2px, plus prop directly under feet!)
	var k_reach: float = 9.2
	var k_rect: Rect2 = Rect2(
		global_position.x if facing >= 0 else (global_position.x - k_reach),
		global_position.y - 10.0,
		k_reach,
		14.0
	)
	var pm: Object = _get_projectile_manager()
	if pm != null and pm.has_method("has_kickable_throwable_near"):
		if bool(pm.call("has_kickable_throwable_near", global_position, facing)):
			return true
	var ml: Object = _get_map_loader()
	if ml != null and ml.has_method("has_kickable_glass_near"):
		if bool(ml.call("has_kickable_glass_near", global_position, facing)):
			return true
	if match_world != null:
		var props_var: Variant = match_world.get("props")
		if typeof(props_var) == TYPE_ARRAY:
			for p_var: Variant in props_var as Array:
				if not is_instance_valid(p_var):
					continue
				var prop: Node2D = p_var as Node2D
				if bool(prop.get("is_destroyed")) or not bool(prop.get("kickable")):
					continue
				var p_rect: Rect2 = prop.call("get_hit_rect") as Rect2 if prop.has_method("get_hit_rect") else Rect2(prop.global_position.x - 7.0, prop.global_position.y - 7.0, 14.0, 14.0)
				if k_rect.intersects(p_rect) or _is_standing_on_prop_rect(p_rect):
					return true
	return false


func _update_aim_pitch_from_input(step_24hz: float, inp: Dictionary) -> void:
	# AS3 Player.as:6213-6232 (AimUp), 7233-7252 (AimDown) & 6199-6202 (AimIdle):
	# Pitch speed starts at ±0.5 deg/tick on press (or +2.5 deg/tick when aiming downward so players standing on CRATE_HANGING can quickly aim down at the chain!)
	# and accelerates while held; resets to 0 on release.
	var pitch_dir: float = 0.0
	if bool(inp.get("up", false)):
		pitch_dir -= 1.0
	if bool(inp.get("down", false)):
		pitch_dir += 1.0
	if pitch_dir != 0.0:
		if _aim_pitch_speed * pitch_dir < 0.0:
			_aim_pitch_speed = 0.0
		if is_zero_approx(_aim_pitch_speed):
			_aim_pitch_speed = pitch_dir * (2.5 if pitch_dir > 0.0 else 0.5)
		current_aim_pitch = clampf(current_aim_pitch + _aim_pitch_speed * step_24hz, -90.0, 90.0)
		var pitch_accel: float = 2.6 if pitch_dir > 0.0 else 2.0
		_aim_pitch_speed = clampf(_aim_pitch_speed + pitch_dir * pitch_accel * step_24hz, -12.0, 12.0)
		_aim_pitch_hold_frames += step_24hz
	else:
		_aim_pitch_speed = 0.0
		_aim_pitch_hold_frames = 0.0


func _get_aim_state_for_weapon(weapon_id: String) -> String:
	var key: String = weapon_id.to_upper()
	match key:
		"PISTOL", "SILENCED_PISTOL", "FLARE_GUN":
			return "AIM_PISTOL"
		"MAGNUM":
			return "AIM_MAGNUM"
		"UZI":
			return "AIM_UZI"
		"SHOTGUN", "SAWED_OFF":
			return "AIM_SHOTGUN"
		"RIFLE", "TOMMY_GUN", "SMG", "M60", "LASER_GUN":
			return "AIM_RIFLE"
		"SNIPER":
			return "AIM_SNIPER"
		"BAZOOKA":
			return "AIM_BAZOOKA"
		"FLAMETHROWER":
			return "AIM_FLAMETHROWER"
		"MOLOTOV":
			return "AIM_MOLOTOV"
		"GRENADE", "C4", "MINE":
			return "AIM_GRENADE"
		_:
			return "AIM_PISTOL"


func _throw_empty_gun(slot: int, wid: String) -> bool:
	_play_sfx("outofammo_light" if slot == 2 else "outofammo_heavy")
	inventory[slot] = ""
	inventory_ammo[slot] = 0
	aiming = false
	_fire_seq_active = false
	_post_fire_aim_hold_frames = 0.0
	_play_sfx("throw")
	_set_state("THROW", true)

	# Deal light impact damage (5 HP + stagger) to enemy in front within 56px throw arc
	var throw_rect: Rect2 = Rect2(
		global_position.x if facing >= 0 else (global_position.x - 56.0),
		global_position.y - 20.0,
		56.0,
		20.0
	)
	for f_var: Variant in _get_all_fighters():
		var target: Node2D = f_var as Node2D
		if bool(target.get("is_dead")):
			continue
		if team_id > 0 and int(target.get("team_id")) == team_id:
			continue
		var t_rect: Rect2 = target.call("get_hit_rect") as Rect2 if target.has_method("get_hit_rect") else Rect2(target.global_position.x - 6.0, target.global_position.y - 18.0, 12.0, 18.0)
		if throw_rect.intersects(t_rect):
			if target.has_method("apply_melee_hit"):
				target.call("apply_melee_hit", 5.0, facing, false, false, false, self)
			break

	if match_world != null and match_world.has_method("spawn_floating_text"):
		match_world.call("spawn_floating_text", wid + " EMPTY!", global_position + Vector2(0.0, -20.0), Color(1.0, 0.55, 0.3, 1.0))
	return false


func trigger_ranged_fire(weapon_id: String = "") -> bool:
	var wid: String = weapon_id.to_upper() if not weapon_id.is_empty() else get_active_weapon_id().to_upper()
	if wid.is_empty() or wid == "FISTS" or MELEE_SPECS.has(wid):
		return false
	var slot: int = 2 if wid == str(inventory.get(2, "")) else 3
	var cur_ammo: int = int(inventory_ammo.get(slot, 0))
	if cur_ammo <= 0:
		return _throw_empty_gun(slot, wid)

	_begin_aiming_session(0)
	current_state = _get_aim_state_for_weapon(wid)
	_last_fired_weapon_id = wid
	_post_fire_aim_hold_frames = POST_FIRE_AIM_HOLD_FRAMES
	_sync_rig_view()

	_fire_seq_weapon_id = wid
	_fire_seq_steps = _build_fire_sequence_for_weapon(wid)
	_fire_seq_idx = 0
	_fire_seq_active = true
	_fire_seq_timer = 0.0
	_execute_current_fire_step()
	return true


func _build_fire_sequence_for_weapon(wid: String) -> Array:
	var key: String = wid.to_upper()
	# Exact AS3 Weapons.as:174-348 FireSequence (each WeaponSequencePart is 1.0 tick @ 24Hz!)
	if key in BURST_WEAPONS:
		var snd: String = "uzi" if key in ["UZI", "TOMMY_GUN", "SMG"] else ("m60" if key == "M60" else "ak47")
		var burst_steps: Array = []
		for i: int in range(5):
			burst_steps.append({
				"frame_nr": 2,
				"time": 1.0,
				"fire": true,
				"shell": true,
				"muzzle": true,
				"sound": snd,
			})
			burst_steps.append({
				"frame_nr": 1,
				"time": 1.0,
				"fire": false,
				"end": (i == 4),
			})
		return burst_steps

	if key == "FLAMETHROWER":
		var ft_steps: Array = []
		for i: int in range(8):
			ft_steps.append({
				"frame_nr": 2 if (i % 2 == 0) else 3,
				"time": 1.0,
				"fire": true,
				"shell": false,
				"muzzle": false,
				"sound": "flamethrower" if i == 0 else "",
			})
		ft_steps.append({"frame_nr": 1, "time": 1.0, "fire": false, "end": true})
		return ft_steps

	if key == "SHOTGUN":
		return [
			{"frame_nr": 2, "time": 1.0, "fire": true, "shell": false, "muzzle": true, "sound": "shotgun"},
			{"frame_nr": 1, "time": 1.0, "fire": false},
			{"frame_nr": 1, "time": 1.0, "fire": false},
			{"frame_nr": 3, "time": 1.0, "fire": false, "sound": "shotgun_pump"},
			{"frame_nr": 3, "time": 1.0, "fire": false, "shell": true},
			{"frame_nr": 1, "time": 1.0, "fire": false, "end": true},
		]

	if key == "SAWED_OFF":
		return [
			{"frame_nr": 2, "time": 1.0, "fire": true, "shell": true, "muzzle": true, "sound": "shotgun"},
			{"frame_nr": 1, "time": 1.0, "fire": false, "end": true},
		]

	if key in ["SNIPER", "LASER_GUN"]:
		return [
			{"frame_nr": 2, "time": 1.0, "fire": true, "shell": (key == "SNIPER"), "muzzle": true, "sound": "sniper"},
			{"frame_nr": 3, "time": 1.0, "fire": false},
			{"frame_nr": 1, "time": 1.0, "fire": false, "end": true},
		]

	if key == "BAZOOKA":
		return [
			{"frame_nr": 2, "time": 1.0, "fire": true, "shell": false, "muzzle": true, "sound": "bazooka"},
			{"frame_nr": 3, "time": 1.0, "fire": false},
			{"frame_nr": 1, "time": 1.0, "fire": false, "end": true},
		]

	var single_snd: String = "pistol"
	if key == "SILENCED_PISTOL":
		single_snd = "silenced_pistol"
	elif key == "MAGNUM":
		single_snd = "magnum"
	elif key == "FLARE_GUN":
		single_snd = "flaregun"
	return [
		{"frame_nr": 2, "time": 1.0, "fire": true, "shell": (key != "FLARE_GUN"), "muzzle": true, "sound": single_snd},
		{"frame_nr": 1, "time": 1.0, "fire": false, "end": true},
	]


static var _method_arg_cache: Dictionary = {}


func _method_arg_count(obj: Object, method_name: String) -> int:
	if obj == null:
		return 0
	var scr: Variant = obj.get_script()
	var cache_key: String = (str(scr.get_instance_id()) if scr != null else obj.get_class()) + ":" + method_name
	if _method_arg_cache.has(cache_key):
		return int(_method_arg_cache[cache_key])
	for m_var: Variant in obj.get_method_list():
		var m_dict: Dictionary = m_var as Dictionary
		if str(m_dict.get("name", "")) == method_name:
			var args_v: Variant = m_dict.get("args", [])
			var cnt: int = (args_v as Array).size() if typeof(args_v) == TYPE_ARRAY else 0
			_method_arg_cache[cache_key] = cnt
			return cnt
	_method_arg_cache[cache_key] = 0
	return 0


func _execute_current_fire_step() -> void:
	if not _fire_seq_active or _fire_seq_idx < 0 or _fire_seq_idx >= _fire_seq_steps.size():
		_fire_seq_active = false
		return

	var step: Dictionary = _fire_seq_steps[_fire_seq_idx] as Dictionary
	weapon_anim_frame_nr = maxi(1, int(step.get("frame_nr", 1)))
	_fire_seq_timer = maxf(0.5, float(step.get("time", 2.0)))
	_sync_rig_view()

	var slot: int = 2 if _fire_seq_weapon_id == str(inventory.get(2, "")) else 3
	var cur_ammo: int = int(inventory_ammo.get(slot, 0))

	if bool(step.get("fire", false)):
		if cur_ammo <= 0:
			_fire_seq_active = false
			weapon_anim_frame_nr = 1
			return
		inventory_ammo[slot] = maxi(0, cur_ammo - 1)

		var muz_pos: Vector2 = global_position + Vector2(float(facing) * 12.0, -14.0)
		var world_angle_deg: float = 0.0 if facing >= 0 else 180.0
		if rig_view is _PreloadFighterRigView:
			var rv: _PreloadFighterRigView = rig_view as _PreloadFighterRigView
			muz_pos = rv.get_muzzle_global_pos()
			world_angle_deg = rv.get_aim_world_angle_deg()

		var fhs: Object = _get_fire_hazard_system()
		var pm: Object = _get_projectile_manager()
		if _fire_seq_weapon_id == "FLAMETHROWER" and fhs != null and fhs.has_method("spawn_flamethrower_stream"):
			fhs.call("spawn_flamethrower_stream", muz_pos, world_angle_deg, self)
		elif pm != null and pm.has_method("spawn_bullet"):
			var ignore_cid: int = cover_object_id if cover_object_id >= 0 else (_find_cover_nearby(facing) if (taking_cover or kneeling) else -1)
			pm.call("spawn_bullet", self, _fire_seq_weapon_id, muz_pos, world_angle_deg, ignore_cid)

		if bool(step.get("muzzle", false)) and fhs != null and fhs.has_method("spawn_muzzle_flash"):
			if _method_arg_count(fhs, "spawn_muzzle_flash") >= 3:
				fhs.call("spawn_muzzle_flash", muz_pos, world_angle_deg, _fire_seq_weapon_id)
			else:
				fhs.call("spawn_muzzle_flash", muz_pos, world_angle_deg)

	if bool(step.get("shell", false)):
		var sh_pos: Vector2 = global_position + Vector2(float(facing) * 6.0, -14.0)
		if rig_view is _PreloadFighterRigView:
			sh_pos = (rig_view as _PreloadFighterRigView).get_shell_global_pos()
		var fhs_s: Object = _get_fire_hazard_system()
		if fhs_s != null and fhs_s.has_method("spawn_shell_casing"):
			if _method_arg_count(fhs_s, "spawn_shell_casing") >= 3:
				fhs_s.call("spawn_shell_casing", sh_pos, facing, _fire_seq_weapon_id)
			else:
				fhs_s.call("spawn_shell_casing", sh_pos, facing)

	var snd: String = str(step.get("sound", ""))
	if not snd.is_empty():
		_play_sfx(snd)


func _step_fire_sequence(step_24hz: float, _inp: Dictionary) -> void:
	if not _fire_seq_active:
		return

	_fire_seq_timer -= step_24hz
	while _fire_seq_active and _fire_seq_timer <= 0.0:
		var prev_rem: float = _fire_seq_timer
		var cur_step: Dictionary = _fire_seq_steps[_fire_seq_idx] as Dictionary
		var is_last_step: bool = bool(cur_step.get("end", false)) or _fire_seq_idx + 1 >= _fire_seq_steps.size()
		if is_last_step:
			_fire_seq_active = false
			weapon_anim_frame_nr = 1
			_fire_cooldown_frames = float(WEAPON_COOLDOWNS_24HZ.get(_fire_seq_weapon_id, 5.0))
			if _post_fire_aim_hold_frames < POST_FIRE_AIM_HOLD_FRAMES:
				_post_fire_aim_hold_frames = POST_FIRE_AIM_HOLD_FRAMES
			# AS3 Player.as:8351: when gun runs out of ammo, automatically discard it when finishing fire sequence
			var f_slot: int = 2 if _fire_seq_weapon_id == str(inventory.get(2, "")) else 3
			if int(inventory_ammo.get(f_slot, 0)) <= 0 and not str(inventory.get(f_slot, "")).is_empty():
				inventory[f_slot] = ""
				inventory_ammo[f_slot] = 0
			break
		# AS3 Player.as:7342-7345: while FireSequence is in progress (.End == false), keep BackToIdleTimer >= 6
		if _post_fire_aim_hold_frames < POST_FIRE_AIM_HOLD_FRAMES:
			_post_fire_aim_hold_frames = POST_FIRE_AIM_HOLD_FRAMES
		_fire_seq_idx += 1
		_execute_current_fire_step()
		_fire_seq_timer += prev_rem


func _step_grenade_cooking(step_24hz: float, _inp: Dictionary) -> void:
	if not _cooking_grenade:
		return
	_grenade_fuse_frames -= step_24hz
	_grenade_tick_accum += step_24hz
	if _grenade_tick_accum >= 12.0:
		_grenade_tick_accum -= 12.0
		_play_sfx("grenade_pin")
	if _grenade_fuse_frames <= 0.0:
		# Cooked too long in hand -> explodes right at the player!
		_cooking_grenade = false
		aiming = false
		var cur_ammo: int = int(inventory_ammo.get(4, 0))
		inventory_ammo[4] = maxi(0, cur_ammo - 1)
		if int(inventory_ammo[4]) <= 0:
			inventory[4] = ""
		var fhs: Object = _get_fire_hazard_system()
		if fhs != null and fhs.has_method("trigger_explosion"):
			fhs.call("trigger_explosion", get_mid_pos(), 33.0, 20.0, 5.0, self)


func _execute_throw() -> bool:
	var th_id: String = str(inventory.get(4, ""))
	if th_id.is_empty() or int(inventory_ammo.get(4, 0)) <= 0:
		_cooking_grenade = false
		aiming = false
		return false

	var fuse: float = _grenade_fuse_frames if (th_id == "GRENADE" and _cooking_grenade) else 72.0
	_cooking_grenade = false
	_grenade_fuse_frames = 72.0
	aiming = false

	inventory_ammo[4] = maxi(0, int(inventory_ammo.get(4, 1)) - 1)
	if int(inventory_ammo[4]) <= 0:
		inventory[4] = ""

	var world_angle_deg: float = current_aim_pitch if facing >= 0 else (180.0 - current_aim_pitch)
	if rig_view is _PreloadFighterRigView:
		world_angle_deg = (rig_view as _PreloadFighterRigView).get_aim_world_angle_deg()

	# AS3 Player.as:2736-2743 (ReleaseThrowable): spawn at shoulder/head height and pass CoverObjectID only when actively in cover
	var spawn_pos: Vector2 = global_position + Vector2(-float(facing) * 3.5, -15.0)
	var ml_th: Object = _get_map_loader()
	if ml_th != null and ml_th.has_method("is_point_solid") and bool(ml_th.call("is_point_solid", spawn_pos, true)):
		spawn_pos = global_position + Vector2(0.0, -15.0)
	var ignore_cid_th: int = cover_object_id if (taking_cover and cover_object_id >= 0) else -1
	var pm: Object = _get_projectile_manager()
	if pm != null and pm.has_method("spawn_throwable"):
		if _method_arg_count(pm, "spawn_throwable") >= 6:
			pm.call("spawn_throwable", self, th_id, spawn_pos, world_angle_deg, fuse, ignore_cid_th)
		else:
			pm.call("spawn_throwable", self, th_id, spawn_pos, world_angle_deg, fuse)
	_play_sfx("throw")
	_set_state("THROW", true)
	return true


func _start_melee_combo_step(step_num: int, carry_queued_count: int = 0) -> void:
	var w_id: String = str(inventory.get(1, "FISTS")).to_upper()
	if w_id.is_empty() or not MELEE_SPECS.has(w_id):
		w_id = "FISTS"
		inventory[1] = "FISTS"
	var mspec: Dictionary = MELEE_SPECS[w_id] as Dictionary
	combo_step = clampi(step_num, 1, 3)
	var anims: Array = mspec.get("anims", ["PUNCH_01", "PUNCH_02", "PUNCH_03"]) as Array
	var anim_name: String = str(anims[clampi(combo_step - 1, 0, anims.size() - 1)])

	aiming = false
	sprinting = false
	_melee_is_kick = false
	_melee_is_jump_kick = false
	_melee_hit_applied = false
	_queued_combo_count = maxi(0, carry_queued_count)
	_queued_next_combo = (_queued_combo_count > 0)
	_melee_total_frames = 8.0 if w_id == "FISTS" else 10.0
	_melee_active_frames = _melee_total_frames
	_combo_window_frames = _melee_total_frames + 10.0
	_play_sfx(str(mspec.get("sfx_swing", "swing")))
	_set_state(anim_name, true)


func _start_kick(is_jump: bool, carry_queued_count: int = 0) -> void:
	aiming = false
	combo_step = 0
	if not is_jump:
		_post_kick_punch_cycle = true
	_melee_is_kick = true
	_melee_is_jump_kick = is_jump
	_melee_hit_applied = false
	_queued_combo_count = maxi(0, carry_queued_count)
	_queued_next_combo = (_queued_combo_count > 0)
	_melee_total_frames = 8.0
	_melee_active_frames = 8.0
	_combo_window_frames = _melee_total_frames + 10.0
	_play_sfx("swing")
	_set_state("JUMPKICK" if is_jump else "KICK", true)


func _advance_combo_or_kick_after_step(carry_queued: int) -> void:
	if _melee_is_kick:
		if not _melee_is_jump_kick:
			_start_melee_combo_step(1, carry_queued)
		return
	if combo_step < 3:
		_start_melee_combo_step(combo_step + 1, carry_queued)
		return
	# Completed 3rd punch (PUNCH_03): wrap cycle back to KICK (if kickable target is nearby) or PUNCH_01!
	combo_step = 0
	_post_kick_punch_cycle = false
	var pm_k: Object = _get_projectile_manager()
	var live_bomb_at_feet: bool = (pm_k != null and pm_k.has_method("has_kickable_throwable_near") and bool(pm_k.call("has_kickable_throwable_near", global_position, facing)))
	if on_ground and (live_bomb_at_feet or (not _has_enemy_in_melee_range() and has_kickable_target_nearby())):
		_start_kick(false, carry_queued)
	else:
		_start_melee_combo_step(1, carry_queued)


func _step_active_melee(step_24hz: float, inp: Dictionary) -> void:
	if bool(inp.get("attack_just_pressed", false)):
		_queued_combo_count = mini(2, _queued_combo_count + 1)
		_queued_next_combo = true

	_melee_active_frames -= step_24hz
	var elapsed: float = _melee_total_frames - _melee_active_frames

	# In Player.as:652-655, 3rd combo hit only glides AFTER the hit frame, scaled by (1.0 - progress)
	if not _melee_is_kick and combo_step == 3 and on_ground and _melee_hit_applied:
		var progress: float = clampf(elapsed / maxf(1.0, _melee_total_frames), 0.0, 1.0)
		var glide_spd: float = PUNCH_GLIDE_SPEED_24HZ * (1.0 - progress)
		_apply_world_movement(Vector2(float(facing) * glide_spd * step_24hz, 0.0), step_24hz)
	elif not on_ground:
		air_velocity.y = minf(air_velocity.y + GRAVITY_24HZ * step_24hz, TERMINAL_VEL_Y_24HZ)
		_apply_world_movement(air_velocity * step_24hz, step_24hz)

	# AS3 PlayerState.as:534-547 (HitPunchComboFrame = [4, 5, 6]) & sf_compiled_rigs.json:
	# Ground KICK extends foot on Keyframe 1 (elapsed >= 1.0); PUNCH_01..03 extend fist on Keyframe 2 (elapsed >= 3.0, 3.5, 4.0)!
	var hit_trigger_frame: float = 1.0 if _melee_is_kick else (3.0 + float(combo_step - 1) * 0.5)
	if not _melee_hit_applied and elapsed >= hit_trigger_frame:
		_melee_hit_applied = true
		_perform_melee_hit_check()
		_verify_ground_support()

	# AS3 PlayerState.as:1903-1916 (MinPunchComboFrame): allow chaining PUNCH_01 -> PUNCH_02 -> PUNCH_03 once strike frame completes
	if not _melee_is_kick and combo_step < 3 and _melee_hit_applied and _queued_next_combo and elapsed >= (6.0 + float(combo_step - 1) * 0.5):
		var rem_q: int = maxi(0, _queued_combo_count - 1)
		_advance_combo_or_kick_after_step(rem_q)
		return

	if _melee_active_frames <= 0.0:
		_melee_active_frames = 0.0
		if _queued_next_combo and not _melee_is_jump_kick:
			var rem_q2: int = maxi(0, _queued_combo_count - 1)
			_advance_combo_or_kick_after_step(rem_q2)
		else:
			if not _melee_is_kick and combo_step >= 3:
				combo_step = 0
				_post_kick_punch_cycle = false
			_queued_combo_count = 0
			_queued_next_combo = false
			_set_state("IDLE" if on_ground else "JUMP")


func _perform_melee_hit_check() -> void:
	var w_id: String = str(inventory.get(1, "FISTS")).to_upper()
	if not MELEE_SPECS.has(w_id):
		w_id = "FISTS"
	var mspec: Dictionary = MELEE_SPECS[w_id] as Dictionary

	var dmg: float = 4.0
	var reach: float = 16.0
	var is_finisher: bool = false
	if not _melee_is_kick:
		var dmgs: Array = mspec.get("damages", [6.0, 7.0, 8.0]) as Array
		var rngs: Array = mspec.get("ranges", [14.0, 15.0, 17.0]) as Array
		var idx: int = clampi(combo_step - 1, 0, dmgs.size() - 1)
		dmg = float(dmgs[idx])
		reach = float(rngs[idx])
		is_finisher = (combo_step >= 3)

	var box_x: float = global_position.x if facing >= 0 else (global_position.x - reach)
	var melee_rect: Rect2 = Rect2(box_x, global_position.y - 20.0, reach, 20.0)
	if _melee_is_kick:
		# AS3 Player.as:7264-7329 (KickHit): kick reaches 4px below the feet to shatter horizontal glass skylights & kick floor props!
		melee_rect = Rect2(box_x - 2.0, global_position.y - 20.0, reach + 4.0, 25.0)

	# Exact AS3 prop contact reach (Player.as:7179-7229 KickHit & Weapons.as:109-145):
	# Ground KICK reaches 8.5px (matching Symbol 622 foot at +8.0px); FISTS reach [9.5, 10.5, 12.0]px (matching Symbol 628/631/634 fist at +9..11px)
	# so interactive props NEVER move before the character's fist/foot/blade sprite visually touches the prop!
	var prop_reach: float = 9.2
	if _melee_is_kick:
		prop_reach = 13.0 if _melee_is_jump_kick else 9.2
	elif w_id == "FISTS":
		var fist_prop_reaches: Array[float] = [9.5, 10.5, 12.0]
		prop_reach = fist_prop_reaches[clampi(combo_step - 1, 0, 2)]
	else:
		prop_reach = maxf(11.0, reach - 3.5)
	var prop_box_x: float = global_position.x if facing >= 0 else (global_position.x - prop_reach)
	var prop_melee_rect: Rect2 = Rect2(
		prop_box_x,
		global_position.y - 16.0,
		prop_reach,
		20.0 if _melee_is_kick else 16.0
	)

	# 1. Deflect bullets if swinging a melee weapon (Machete, Axe, Sword, Baton), and kick live grenades at feet (Player.as:5033, 5724-5762)
	var pm: Object = _get_projectile_manager()
	if pm != null:
		if not _melee_is_kick and bool(mspec.get("can_deflect", false)) and pm.has_method("deflect_bullets_in_box"):
			pm.call("deflect_bullets_in_box", self, melee_rect.grow(4.0), facing)
		if pm.has_method("kick_throwables_in_rect"):
			var throw_kick_rect: Rect2 = Rect2(box_x - 4.0, global_position.y - 16.0, reach + 8.0, 22.0)
			pm.call("kick_throwables_in_rect", throw_kick_rect, facing, self)

	# 2. Check glass breaking (both vertical windows and horizontal glass skylights under feet)
	var ml: Object = _get_map_loader()
	if ml != null:
		if ml.has_method("check_and_break_glass_segment"):
			ml.call(
				"check_and_break_glass_segment",
				global_position + Vector2(0.0, -10.0),
				global_position + Vector2(float(facing) * reach, -10.0),
				Vector2(float(facing) * 6.0, -1.0)
			)
		if ml.has_method("damage_glass_in_rect"):
			ml.call("damage_glass_in_rect", melee_rect, 8.0 if _melee_is_kick else dmg, Vector2(float(facing) * 4.0, 3.0))

	# 3. Check enemy fighters in melee hitbox
	var hit_anyone: bool = false
	for f_var: Variant in _get_all_fighters():
		var target: Node2D = f_var as Node2D
		if bool(target.get("is_dead")):
			continue
		if team_id > 0 and int(target.get("team_id")) == team_id:
			continue
		var t_rect: Rect2 = Rect2(target.global_position.x - 6.0, target.global_position.y - 18.0, 12.0, 18.0)
		if target.has_method("get_hit_rect"):
			t_rect = target.call("get_hit_rect") as Rect2
		if melee_rect.intersects(t_rect):
			if target.has_method("apply_melee_hit"):
				target.call("apply_melee_hit", dmg, facing, is_finisher, _melee_is_kick, _melee_is_jump_kick, self)
			hit_anyone = true

	# 4. Check interactive props (kick pushes props forward; melee damages props; pass `self` as attacker to prevent self-hit!)
	if match_world != null:
		var props_var: Variant = match_world.get("props")
		if typeof(props_var) == TYPE_ARRAY:
			for p_var: Variant in props_var as Array:
				if not is_instance_valid(p_var):
					continue
				var prop: Node2D = p_var as Node2D
				if bool(prop.get("is_hanging_holder")) or (prop.get("kickable") != null and not bool(prop.get("kickable")) and not bool(prop.get("is_parachute_crate"))):
					continue
				var p_rect: Rect2 = Rect2(prop.global_position.x - 8.0, prop.global_position.y - 14.0, 16.0, 14.0)
				if prop.has_method("get_hit_rect"):
					p_rect = prop.call("get_hit_rect") as Rect2
				var standing_on_this_prop: bool = _is_standing_on_prop_rect(p_rect)
				# AS3 Player.as:7171-7177: Punches (param2 == true) ignore _standingOnObject, whereas Ground Kicks (param2 == false) scan down to _this_y + 4 and kick the prop under the fighter's feet!
				if not _melee_is_kick and standing_on_this_prop:
					continue
				if prop_melee_rect.intersects(p_rect) or (_melee_is_kick and standing_on_this_prop):
					if prop.has_method("apply_melee_hit"):
						prop.call("apply_melee_hit", dmg, facing, _melee_is_kick, w_id, self)
					elif _melee_is_kick and prop.has_method("apply_kick_impulse"):
						prop.call("apply_kick_impulse", Vector2(float(facing) * 5.5, -2.0), self)

	if hit_anyone:
		_play_sfx("punch" if (_melee_is_kick or w_id == "FISTS") else str(mspec.get("sfx_hit", "cut")))
		# Note: In AS3 Weapons.as, melee weapons (Machete, Axe, Sword) NEVER break or lose durability on hit!


# --- MUGEN 4-Hit Combo & Special Moves (Shunpo Slash & Chakra Wave) ---
func _start_mugen_combo_step(step_num: int) -> bool:
	if mugen_adapter == null:
		return false
	combo_step = clampi(step_num, 1, 4)
	var st_name: String = mugen_adapter.get_combo_state_for_step(combo_step)
	return _enter_mugen_state(st_name)


func perform_mugen_special(move_name: String) -> bool:
	if mugen_adapter == null:
		return false
	var key: String = move_name.to_upper()
	if not mugen_adapter.is_mugen_state(key):
		return false
	return _enter_mugen_state(key)


func _enter_mugen_state(st_name: String) -> bool:
	if mugen_adapter == null or not mugen_adapter.is_mugen_state(st_name):
		return false
	var st_def: Dictionary = mugen_adapter.get_mugen_state_def(st_name)
	current_state = st_name.to_upper()
	anim_frame_idx = 1
	_mugen_state_active = true
	_mugen_hit_applied = false
	_queued_next_combo = false
	aiming = false
	var fdata: Dictionary = mugen_adapter.get_frame_visual_data(current_state, 1)
	_mugen_frame_timer = maxf(1.0, float(fdata.get("duration", 3)))
	_combo_window_frames = 18.0
	var sfx: String = str(st_def.get("sfx", "swing_sword"))
	if not sfx.is_empty():
		_play_sfx(sfx)
	_sync_rig_view()
	return true


func _step_mugen_active_state(step_24hz: float, inp: Dictionary) -> void:
	var st_def: Dictionary = mugen_adapter.get_mugen_state_def(current_state)
	var st_type: String = str(st_def.get("type", "mugen_attack"))

	if bool(inp.get("attack_just_pressed", false)):
		_queued_next_combo = true

	if st_type == "mugen_special_dash":
		var dash_spd: float = float(st_def.get("dash_speed_24hz", 7.5))
		_apply_world_movement(Vector2(float(facing) * dash_spd * step_24hz, 0.0), step_24hz)
	elif st_type == "mugen_attack":
		var step_vx: float = float(st_def.get("step_vel_x", 1.2))
		_apply_world_movement(Vector2(float(facing) * step_vx * step_24hz, 0.0), step_24hz)

	# Check Clsn1 red attack hitboxes on current frame
	var clsn1_boxes: Array[Rect2] = get_mugen_clsn1_world_boxes()
	if not _mugen_hit_applied and not clsn1_boxes.is_empty():
		if st_type == "mugen_special_projectile":
			_mugen_hit_applied = true
			var proj_id: String = str(st_def.get("projectile_id", "CHAKRA_WAVE"))
			var proj_spd: float = float(st_def.get("projectile_speed_24hz", 22.0))
			var proj_dmg: float = float(st_def.get("damage", 20.0))
			var proj_push: float = float(st_def.get("hit_force", 35.0))
			var spawn_p: Vector2 = global_position + Vector2(float(facing) * 12.0, -10.0)
			var pm: Object = _get_projectile_manager()
			if pm != null and pm.has_method("spawn_mugen_projectile"):
				pm.call("spawn_mugen_projectile", self, proj_id, spawn_p, 0.0 if facing >= 0 else 180.0, proj_spd, proj_dmg, proj_push)
			elif pm != null and pm.has_method("spawn_bullet"):
				pm.call("spawn_bullet", self, proj_id, spawn_p, 0.0 if facing >= 0 else 180.0, -1)
		else:
			var m_dmg: float = float(st_def.get("damage", 10.0))
			var m_kd: bool = bool(st_def.get("knockdown", false))
			for f_var: Variant in _get_all_fighters():
				var target: Node2D = f_var as Node2D
				if bool(target.get("is_dead")):
					continue
				var t_rect: Rect2 = target.call("get_hit_rect") as Rect2 if target.has_method("get_hit_rect") else Rect2(target.global_position.x - 6.0, target.global_position.y - 18.0, 12.0, 18.0)
				for c1: Rect2 in clsn1_boxes:
					if c1.intersects(t_rect):
						if target.has_method("apply_melee_hit"):
							target.call("apply_melee_hit", m_dmg, facing, m_kd, false, false, self)
						_mugen_hit_applied = true
						break

	_mugen_frame_timer -= step_24hz
	if _mugen_frame_timer <= 0.0:
		var frames: Array = st_def.get("frames", []) as Array
		if anim_frame_idx < frames.size():
			anim_frame_idx += 1
			var next_fd: Dictionary = mugen_adapter.get_frame_visual_data(current_state, anim_frame_idx)
			_mugen_frame_timer = maxf(1.0, float(next_fd.get("duration", 3)))
		else:
			if _queued_next_combo and current_state.begins_with("MUGEN_COMBO_") and combo_step < 4:
				var next_st: String = mugen_adapter.get_combo_state_for_step(combo_step + 1)
				if mugen_adapter.can_cancel(current_state, next_st):
					_start_mugen_combo_step(combo_step + 1)
					return
			_mugen_state_active = false
			_set_state("IDLE")


# --- AS3 Dive Tackle Impact (Player.as:1881-1947, 6933-6941, 7996-8017) ---
func _try_grab_nearby_target() -> bool:
	if not diving or is_instance_valid(grabbed_target):
		return false
	for f_var: Variant in _get_all_fighters():
		var target: Node2D = f_var as Node2D
		if bool(target.get("is_dead")) or target.get("grabbed_by") != null:
			continue
		if team_id > 0 and int(target.get("team_id")) == team_id:
			continue
		var dx: float = absf(target.global_position.x - global_position.x)
		var my_mid_y: float = global_position.y - 4.0
		var t_mid_y: float = target.global_position.y - (4.0 if bool(target.get("diving")) else 10.0)
		var dy: float = absf(t_mid_y - my_mid_y)
		if dx <= 10.0 and dy <= 11.0:
			# If both fighters are diving into each other: DiveCollision() bounce!
			if bool(target.get("diving")):
				air_velocity.x = -float(facing) * 3.5
				facing = -facing
				diving = false
				falling = true
				target.set("air_velocity", Vector2(float(facing) * 3.5, (target.get("air_velocity") as Vector2).y))
				target.set("diving", false)
				target.set("falling", true)
				_play_sfx("punch")
				return true
			# Check CanBeCatched (!Dead && !Knockdowned && !Falling && !Rolling && !Diving)
			if bool(target.get("knockdowned")) or bool(target.get("falling")) or bool(target.get("rolling")):
				continue
			# Catch target IN FLIGHT while continuing the dive trajectory under gravity!
			grabbed_target = target
			target.set("grabbed_by", self)
			target.set("aiming", false)
			target.set("sprinting", false)
			target.set("on_ground", false)
			_update_dive_tackled_target()
			_play_sfx("dive_catch")
			return true
	return false


func _update_dive_tackled_target() -> void:
	if not is_instance_valid(grabbed_target):
		grabbed_target = null
		return
	if bool(grabbed_target.get("is_dead")):
		_drop_dive_tackled_target()
		return
	grabbed_target.global_position = global_position + Vector2(float(facing) * 6.0, -2.0)
	grabbed_target.set("facing", -facing)
	grabbed_target.set("body_rotation_deg", -body_rotation_deg)
	if grabbed_target.has_method("_sync_rig_view"):
		grabbed_target.call("_sync_rig_view")


func _drop_dive_tackled_target() -> void:
	if not is_instance_valid(grabbed_target):
		grabbed_target = null
		return
	var victim: Node2D = grabbed_target
	grabbed_target = null
	victim.set("grabbed_by", null)
	victim.set("body_rotation_deg", 0.0)
	# AS3 Player.as:6937, 8003 (UpdateGrabbedPlayer(true)): place victim at diver's position and snap up onto stairs/floor!
	var drop_pos: Vector2 = global_position
	var ml: Object = _get_map_loader()
	if ml != null and ml.has_method("get_ground_y_below"):
		var gy: float = float(ml.call("get_ground_y_below", drop_pos.x, drop_pos.y - 16.0, 26.0, true))
		if gy < INF and gy <= drop_pos.y + 8.0:
			drop_pos.y = gy
	victim.global_position = drop_pos
	var v_grounded: bool = on_ground or (ml != null and ml.has_method("get_ground_y_below") and float(ml.call("get_ground_y_below", drop_pos.x, drop_pos.y - 8.0, 14.0, true)) < INF)
	# Player.as:1928-1947 GrabbedByOtherPlayer(false, LastDirX): knock victim down on floor
	victim.set("on_ground", v_grounded)
	victim.set("falling", not v_grounded)
	victim.set("knockdowned", true)
	victim.set("_knockdown_frames", 23.0)
	victim.set("air_velocity", Vector2(float(facing) * 1.4, 0.0))
	if victim.has_method("_set_state"):
		victim.call("_set_state", "KNOCKDOWN", true)
	if victim.has_method("_sync_rig_view"):
		victim.call("_sync_rig_view")


# --- Locomotion State Machine ---
func _step_locomotion(step_24hz: float, inp: Dictionary, move_dir: int) -> void:
	# 1. Double-tap Left/Right for Sprint (AS3 release-to-press <= 6.5 frames or press-to-press <= 10 frames)
	if bool(inp.get("left_just_released", false)):
		_last_release_dir = -1
		_release_timer_24hz = 6.5
	elif bool(inp.get("right_just_released", false)):
		_last_release_dir = 1
		_release_timer_24hz = 6.5

	if bool(inp.get("left_just_pressed", false)) and not bool(inp.get("down", false)) and not kneeling and not rolling:
		if ((_last_release_dir == -1 and _release_timer_24hz > 0.0) or (_last_tap_dir == -1 and _last_tap_timer > 0.0)) and sprint_energy > 5.0:
			sprinting = true
		_last_tap_dir = -1
		_last_tap_timer = 10.0
	elif bool(inp.get("right_just_pressed", false)) and not bool(inp.get("down", false)) and not kneeling and not rolling:
		if ((_last_release_dir == 1 and _release_timer_24hz > 0.0) or (_last_tap_dir == 1 and _last_tap_timer > 0.0)) and sprint_energy > 5.0:
			sprinting = true
		_last_tap_dir = 1
		_last_tap_timer = 10.0

	if bool(inp.get("sprint", false)) and move_dir != 0 and sprint_energy > 0.0:
		sprinting = true
	elif move_dir == 0 and not diving:
		sprinting = false

	# 2. Active Roll state
	if rolling:
		_roll_frames -= step_24hz
		_apply_world_movement(Vector2(float(facing) * ROLL_SPEED_24HZ * step_24hz, 0.0), step_24hz)
		if not on_ground:
			var prev_r_vy: float = air_velocity.y
			air_velocity.y = minf(air_velocity.y + GRAVITY_24HZ * step_24hz, TERMINAL_VEL_Y_24HZ)
			var avg_r_vy: float = (prev_r_vy + air_velocity.y) * 0.5 + (0.143 * step_24hz)
			_apply_world_movement(Vector2(0.0, avg_r_vy * step_24hz), step_24hz)
		if _roll_frames <= 0.0:
			rolling = false
			_roll_cooldown_frames = 3.0 if burn_state <= 0.0 else 0.0
			_set_state("KNEEL" if bool(inp.get("down", false)) else "IDLE")
		return

	# 3. Active Dive state (continues falling under gravity even if carrying a tackled opponent!)
	if diving:
		body_rotation_deg = clampf(body_rotation_deg + 1.5 * step_24hz, -15.0, 28.0)
		var prev_d_vy: float = air_velocity.y
		air_velocity.y = minf(air_velocity.y + GRAVITY_24HZ * step_24hz, TERMINAL_VEL_Y_24HZ)
		var avg_d_vy: float = (prev_d_vy + air_velocity.y) * 0.5 + (0.143 * step_24hz)
		var delta_move: Vector2 = Vector2(air_velocity.x * step_24hz, avg_d_vy * step_24hz)
		var ml: Object = _get_map_loader()
		if ml != null and ml.has_method("check_and_break_glass_segment"):
			ml.call("check_and_break_glass_segment", global_position + Vector2(0.0, -8.0), global_position + delta_move + Vector2(0.0, -8.0), air_velocity)
		_apply_world_movement(delta_move, step_24hz)
		if diving:
			_try_grab_nearby_target()
			_update_dive_tackled_target()
		return

	# 3b. Active Ledge Grab state (Superfighters Deluxe-style auto ledge grab at platform corners)
	if ledge_grabbing:
		sprint_energy = minf(max_sprint_energy, sprint_energy + 1.0 * step_24hz)
		air_velocity = Vector2.ZERO
		on_ground = false
		falling = false
		body_rotation_deg = 0.0
		if move_dir == -facing and (bool(inp.get("jump_just_pressed", false)) or bool(inp.get("up_just_pressed", false))):
			ledge_grabbing = false
			_ledge_grab_cooldown_frames = 14.0
			facing = -facing
			air_velocity = Vector2(float(facing) * WALL_JUMP_POWER_X_24HZ, WALL_JUMP_POWER_Y_24HZ)
			_play_sfx("jump")
			_set_state("JUMP", true)
			return
		var press_into_ledge: bool = (facing > 0 and bool(inp.get("right_just_pressed", false))) or (facing < 0 and bool(inp.get("left_just_pressed", false)))
		if bool(inp.get("jump_just_pressed", false)) or bool(inp.get("up_just_pressed", false)) or press_into_ledge:
			# Deluxe Ledge Jump: jump smoothly up and over the ledge corner instead of teleporting instantaneously!
			ledge_grabbing = false
			_ledge_grab_cooldown_frames = 14.0
			_ledge_jump_vault_frames = 14.0
			_ledge_jump_target_dir = facing
			on_ground = false
			_on_cloud_platform = false
			air_velocity = Vector2(0.0, -4.7)
			_play_sfx("jump")
			_set_state("JUMP", true)
			_step_airborne_movement(step_24hz, {}, move_dir, false)
			return
		if bool(inp.get("down", false)):
			ledge_grabbing = false
			_ledge_grab_cooldown_frames = 14.0
			air_velocity = Vector2(0.0, 1.0)
			_set_state("JUMP", true)
			return
		_set_state("LEDGE_GRAB")
		return

	# 4. Ladder Climbing & Sliding (AS3 Player.as:514-530, 7611-7689, 8019-8027: tests MidPosX(), MidPosY())
	var ladder_rect: Rect2 = _find_ladder_at(get_mid_pos())
	var just_grabbed_ladder: bool = false
	if _can_grab_ladder_in_current_state():
		var want_up: bool = bool(inp.get("up", false))
		var want_down: bool = bool(inp.get("down", false))
		if on_ground:
			# Grounded UP grab: ONLY when not walking/running horizontally (move_dir == 0, so running + W/Up performs a normal running jump!)
			# and ONLY when the ladder extends meaningfully upward above the fighter (so pressing W/Up on the top platform jumps instead of grabbing the ladder tip!)
			if want_up and move_dir == 0 and ladder_rect.size.x > 0.0 and ladder_rect.position.y < global_position.y - 16.0:
				_enter_ladder_climb(ladder_rect, false)
				just_grabbed_ladder = true
			# Grounded DOWN grab: standing on a platform/hatch at the top or middle of a ladder and pressing Down (with move_dir == 0)
			elif want_down and move_dir == 0 and not sprinting:
				var descent_lad: Rect2 = _find_ladder_for_descent()
				if descent_lad.size.x > 0.0:
					_enter_ladder_climb(descent_lad, true)
					ladder_rect = descent_lad
					just_grabbed_ladder = true
		else:
			# Airborne grab: prevent accidental snagging when jumping/moving horizontally across a ladder unless move_dir == 0 (or horizontal speed is very low)
			var allow_air_grab: bool = (move_dir == 0 and absf(air_velocity.x) <= 0.85) or (bool(inp.get("up_just_pressed", false)) and move_dir == 0)
			if allow_air_grab and ladder_rect.size.x > 0.0 and (want_up or want_down):
				_enter_ladder_climb(ladder_rect, false)
				just_grabbed_ladder = true

	if climbing:
		sprint_energy = minf(max_sprint_energy, sprint_energy + 1.0 * step_24hz)
		var cur_lad: Rect2 = _find_ladder_at(get_mid_pos())
		if cur_lad.size.x <= 0.0 and just_grabbed_ladder:
			cur_lad = ladder_rect
		if cur_lad.size.x <= 0.0:
			climbing = false
			_ladder_sliding = false
		else:
			var lad_solids: Array[Rect2] = _collect_solid_rects()
			var near_ladder_top: bool = global_position.y <= cur_lad.position.y + 16.0
			# AS3 LadderJump (Player.as:7918-7926): tapping W/Up while climbing the body of the ladder must NEVER jump off the ladder!
			# Only jump off when near the top of the ladder and holding Up + Left/Right (or at the very top when no platform is directly underfoot).
			var want_ladder_jump: bool = (
				not just_grabbed_ladder
				and near_ladder_top
				and bool(inp.get("up", false))
				and move_dir != 0
			)
			if want_ladder_jump:
				climbing = false
				_ladder_sliding = false
				_ladder_regrab_cooldown_frames = 10.0
				_begin_jump(move_dir, step_24hz)
				return

			if move_dir != 0 and not bool(inp.get("down", false)):
				facing = move_dir
				var old_lad_x: float = global_position.x
				var raw_lad_x: float = old_lad_x + float(move_dir) * CLIMB_SPEED_24HZ * step_24hz
				var clamped_lad_x: float = _clamp_x_against_solid_walls(raw_lad_x, global_position.y, lad_solids, old_lad_x)
				var blocked_by_wall: bool = absf(clamped_lad_x - raw_lad_x) > 0.01
				global_position.x = clamped_lad_x
				if _try_step_onto_adjacent_platform_from_ladder(move_dir):
					climbing = false
					_ladder_sliding = false
					_ladder_regrab_cooldown_frames = 8.0
					return
				# AS3 Player.as:7667-7689: stepping horizontally outside the ladder dismounts onto adjacent platform or air (unless blocked by a solid wall!)
				if _find_ladder_at(get_mid_pos()).size.x <= 0.0:
					if blocked_by_wall:
						global_position.x = clampf(clamped_lad_x, cur_lad.position.x + 2.0, cur_lad.end.x - 2.0)
					else:
						climbing = false
						_ladder_sliding = false
						_ladder_regrab_cooldown_frames = 8.0
						if not _try_step_onto_adjacent_platform_from_ladder(move_dir):
							air_velocity.x = float(move_dir) * RUN_SPEED_24HZ * 0.85
						return
			if bool(inp.get("down", false)):
				_ladder_sliding = true
				_set_state("SLIDE")
				var old_lad_y: float = global_position.y
				var next_lad_y: float = old_lad_y + SLIDE_SPEED_24HZ * step_24hz
				for sr: Rect2 in lad_solids:
					if global_position.x + 3.5 > sr.position.x and global_position.x - 3.5 < sr.end.x:
						if old_lad_y <= sr.position.y + 2.5 and next_lad_y >= sr.position.y:
							global_position.y = sr.position.y
							global_position.x = _clamp_x_against_solid_walls(global_position.x, global_position.y, lad_solids, global_position.x)
							climbing = false
							_ladder_sliding = false
							on_ground = true
							return
				global_position.y = next_lad_y
				global_position.x = _clamp_x_against_solid_walls(global_position.x, global_position.y, lad_solids, global_position.x)
				_kick_fighters_below_on_ladder(cur_lad)
				if global_position.y >= cur_lad.end.y:
					global_position.y = cur_lad.end.y
					global_position.x = _clamp_x_against_solid_walls(global_position.x, global_position.y, lad_solids, global_position.x)
					climbing = false
					_ladder_sliding = false
					on_ground = true
					_verify_ground_support()
					return
			elif bool(inp.get("up", false)):
				_ladder_sliding = false
				_set_state("CLIMB")
				var old_lad_y2: float = global_position.y
				var next_lad_y2: float = old_lad_y2 - CLIMB_SPEED_24HZ * speed_mult * step_24hz
				for sr: Rect2 in lad_solids:
					if sr.size.y >= 4.0 and global_position.x + 2.5 > sr.position.x and global_position.x - 2.5 < sr.end.x:
						if old_lad_y2 - 16.0 >= sr.end.y - 2.0 and next_lad_y2 - 16.0 < sr.end.y:
							next_lad_y2 = sr.end.y + 16.0
							break
				global_position.y = next_lad_y2
				global_position.x = _clamp_x_against_solid_walls(global_position.x, global_position.y, lad_solids, global_position.x)
				# Check if reaching a top platform / hatch at the top of the ladder
				if _try_step_onto_ladder_platform_at_height(cur_lad, old_lad_y2, global_position.y, move_dir, true):
					return
				var min_foot_y: float = cur_lad.position.y + 8.0
				if global_position.y <= min_foot_y:
					global_position.y = min_foot_y
					if _try_step_onto_ladder_platform_at_height(cur_lad, old_lad_y2, global_position.y, move_dir, true):
						return
					climbing = false
					_ladder_sliding = false
					_ladder_regrab_cooldown_frames = 10.0
					_begin_jump(move_dir, step_24hz)
					return
			else:
				_ladder_sliding = false
				if _try_step_onto_ladder_platform_at_height(cur_lad, global_position.y, global_position.y, move_dir, false):
					return
				_set_state("CLIMB")
			return

	# 5. Grounded transitions: Dive, Roll, Cloud-Drop, Jump, Kneel/Cover, Run/Sprint, Idle
	if on_ground:
		body_rotation_deg = 0.0
		falling = false
		_sideway_bounced = false

		# Check Dive (AS3 Player.as:532: requires Sprinting + Down + holding Left/Right, or explicit dive input)
		if (sprinting and move_dir != 0 and (bool(inp.get("down", false)) or bool(inp.get("down_just_pressed", false)))) or bool(inp.get("dive", false)):
			_start_dive(move_dir, step_24hz)
			return

		# Check Roll (Down + Left/Right or explicit roll input)
		if bool(inp.get("down", false)) and move_dir != 0 and not sprinting and (bool(inp.get("left_just_pressed", false)) or bool(inp.get("right_just_pressed", false)) or bool(inp.get("down_just_pressed", false))):
			_roll_cooldown_frames = 0.0
		if (bool(inp.get("down", false)) and move_dir != 0 and not sprinting and _roll_cooldown_frames <= 0.0) or bool(inp.get("roll", false)):
			_start_roll()
			return

		# Check Drop-through One-Way Cloud Platform (Down + Jump or double-tap Down)
		if bool(inp.get("down_just_pressed", false)):
			if _down_tap_timer > 0.0 and _on_cloud_platform:
				_trigger_cloud_drop()
				return
			_down_tap_timer = 6.0

		if bool(inp.get("jump_just_pressed", false)):
			if bool(inp.get("down", false)) and _on_cloud_platform:
				_trigger_cloud_drop()
				return
			_begin_jump(move_dir, step_24hz)
			return

		if bool(inp.get("down", false)):
			# AS3 Player.as:530-539 & PlayerAnimation.as:293-300: pressing Down (KEY_KNEEL) ALWAYS enters KNEEL (never shifts into COVER)
			kneeling = true
			taking_cover = false
			sprinting = false
			sprint_energy = minf(max_sprint_energy, sprint_energy + 2.0 * step_24hz)
			cover_object_id = _find_cover_nearby(facing)
			_set_state("KNEEL")
			return
		else:
			kneeling = false

		if move_dir != 0:
			# AS3 Player.as:6206-6248 (MoveDirection & CanTakeCover):
			# Pressing Left/Right into an adjacent low cover prop while not sprinting enters/maintains TakingCover ("COVER")
			if taking_cover and move_dir == facing:
				var keep_cov_id: int = _find_cover_nearby(facing)
				if keep_cov_id >= 0:
					cover_object_id = keep_cov_id
					sprinting = false
					sprint_energy = minf(max_sprint_energy, sprint_energy + 2.0 * step_24hz)
					_set_state("COVER")
					return
				taking_cover = false
				cover_object_id = -1
			elif taking_cover and move_dir != facing:
				taking_cover = false
				cover_object_id = -1

			if not sprinting and current_state != "RUN" and current_state != "SPRINT":
				var enter_cov_id: int = _find_cover_nearby(move_dir)
				if enter_cov_id >= 0:
					taking_cover = true
					cover_object_id = enter_cov_id
					sprint_energy = minf(max_sprint_energy, sprint_energy + 2.0 * step_24hz)
					_apply_world_movement(Vector2(float(move_dir) * RUN_SPEED_24HZ * speed_mult * step_24hz, 0.0), step_24hz)
					_set_state("COVER")
					return

			var spd: float = (SPRINT_SPEED_24HZ if sprinting else RUN_SPEED_24HZ) * speed_mult
			if sprinting:
				sprint_energy = maxf(0.0, sprint_energy - 1.2 * step_24hz)
				if sprint_energy <= 0.0:
					sprinting = false
					spd = RUN_SPEED_24HZ * speed_mult
			else:
				sprint_energy = minf(max_sprint_energy, sprint_energy + 1.0 * step_24hz)

			_apply_world_movement(Vector2(float(move_dir) * spd * step_24hz, 0.0), step_24hz)
			_set_state("SPRINT" if sprinting else "RUN")
		else:
			sprint_energy = minf(max_sprint_energy, sprint_energy + 2.0 * step_24hz)
			if taking_cover:
				var idle_cov_id: int = _find_cover_nearby(facing)
				if idle_cov_id >= 0:
					cover_object_id = idle_cov_id
					_set_state("COVER")
					return
				taking_cover = false
				cover_object_id = -1
			_set_state("IDLE")
	else:
		# 6. Airborne movement, WallJump, Gravity, FallTriggerSpeed
		_step_airborne_movement(step_24hz, inp, move_dir, true)


func _step_airborne_movement(step_24hz: float, inp: Dictionary, move_dir: int, allow_wall_jump: bool = true) -> void:
	kneeling = false
	taking_cover = false
	cover_object_id = -1

	# Check WallJump when airborne near a solid wall and pressing jump (not allowed while falling/knockdowned)
	if _ledge_jump_vault_frames > 0.0:
		_ledge_jump_vault_frames = maxf(0.0, _ledge_jump_vault_frames - step_24hz)
		if not falling and move_dir != -_ledge_jump_target_dir and global_position.y <= _ledge_grab_top_y + 0.5:
			air_velocity.x = float(_ledge_jump_target_dir) * RUN_SPEED_24HZ * speed_mult
	if allow_wall_jump and not falling and not knockdowned and not diving and not rolling and bool(inp.get("jump_just_pressed", false)) and _near_wall_dir != 0 and absf(air_velocity.y) <= 3.5:
		facing = -_near_wall_dir
		air_velocity.x = float(facing) * WALL_JUMP_POWER_X_24HZ
		air_velocity.y = WALL_JUMP_POWER_Y_24HZ
		_near_wall_dir = 0
		_play_sfx("jump")
		_set_state("JUMP", true)
	elif move_dir != 0 and not falling:
		var air_target_vx: float = float(move_dir) * (SPRINT_SPEED_24HZ if sprinting else RUN_SPEED_24HZ) * speed_mult
		air_velocity.x = move_toward(air_velocity.x, air_target_vx, 0.35 * step_24hz)

	var prev_vy: float = air_velocity.y
	air_velocity.y = minf(air_velocity.y + GRAVITY_24HZ * step_24hz, TERMINAL_VEL_Y_24HZ)
	# Midpoint integration calibrated to exact Superfighters Y8 AS3 peak jump height (19.65 px)
	var avg_vy: float = (prev_vy + air_velocity.y) * 0.5 + (0.143 * step_24hz)

	if air_velocity.y >= FALL_TRIGGER_SPEED_24HZ and not falling:
		falling = true
		var fall_st: String = "FALL_F" if (air_velocity.x * float(facing) >= 0.0) else "FALL_B"
		_set_state(fall_st, true)

	if falling:
		var rot_spd: float = 14.0 if current_state == "FALL_F" else -14.0
		body_rotation_deg += rot_spd * step_24hz

	_apply_world_movement(Vector2(air_velocity.x * step_24hz, avg_vy * step_24hz), step_24hz)

	if falling and not on_ground:
		_update_player_falling_on_player()

	if allow_wall_jump and not on_ground and not falling and not knockdowned and not diving and not rolling and not climbing and not ledge_grabbing:
		_try_auto_ledge_grab(inp, move_dir)


func can_be_knocked_by_flying_player() -> bool:
	return not is_dead and not knockdowned and not rolling and not diving


func _update_player_falling_on_player() -> void:
	# AS3 Player.as:6397-6432 (UpdatePlayerFallingOnPlayer):
	# When a fighter in free-fall (`falling == true`) collides with another fighter, transfer momentum (0.9x), deal light impact damage, and knock them into free-fall!
	if not falling or is_dead:
		return
	var tot_vel: float = air_velocity.length()
	if tot_vel < 4.2:
		return
	var my_mid: Vector2 = get_mid_pos()
	for f_var: Variant in _get_all_fighters():
		var other: Node2D = f_var as Node2D
		if other.has_method("can_be_knocked_by_flying_player"):
			if not bool(other.call("can_be_knocked_by_flying_player")):
				continue
		elif bool(other.get("is_dead")) or bool(other.get("knockdowned")) or bool(other.get("rolling")) or bool(other.get("diving")):
			continue
		var other_mid: Vector2 = other.call("get_mid_pos") as Vector2 if other.has_method("get_mid_pos") else (other.global_position + Vector2(0.0, -8.0))
		if my_mid.distance_to(other_mid) <= 13.0:
			var ang: float = atan2((other_mid.y - 4.0) - my_mid.y, other_mid.x - my_mid.x)
			var new_vx: float = cos(ang) * tot_vel * 0.9
			var new_vy: float = minf(sin(ang) * tot_vel * 0.9, -1.8)
			var impact_dmg: float = clampf((tot_vel - 3.0) * 1.1, 3.0, 8.0)
			if other.has_method("_apply_raw_damage"):
				other.call("_apply_raw_damage", impact_dmg)
			if not bool(other.get("is_dead")) and other.has_method("force_fall"):
				other.call("force_fall", new_vx, new_vy, true)
			air_velocity.x = -new_vx * 0.55
			air_velocity.y = minf(-1.2, air_velocity.y * 0.4)
			_play_sfx("body_fall")
			var fhs: Object = _get_fire_hazard_system()
			if fhs != null and fhs.has_method("spawn_hit_sparks"):
				fhs.call("spawn_hit_sparks", (my_mid + other_mid) * 0.5, true)
			break


func _can_grab_ladder_in_current_state() -> bool:
	if is_dead or climbing or falling or knockdowned or rolling or diving or ledge_grabbing:
		return false
	if aiming or _cooking_grenade or _fire_seq_active or _mugen_state_active:
		return false
	if _melee_active_frames > 0.0 or _stagger_frames > 0.0:
		return false
	if grabbed_target != null or grabbed_by != null:
		return false
	return _ladder_regrab_cooldown_frames <= 0.0


func _find_ladder_for_descent() -> Rect2:
	var probes: Array[Vector2] = [
		get_mid_pos(),
		global_position + Vector2(0.0, 2.0),
		global_position + Vector2(0.0, 10.0),
	]
	var solids: Array[Rect2] = _collect_solid_rects()
	for pt: Vector2 in probes:
		var lr: Rect2 = _find_ladder_at(pt)
		if lr.size.x > 0.0 and lr.end.y > global_position.y + 12.0 and global_position.y >= lr.position.y - 10.0:
			var cx: float = clampf(global_position.x, lr.position.x + 2.0, lr.end.x - 2.0)
			if not _is_rect_point_solid(solids, Vector2(cx, global_position.y + 2.0)):
				return lr
	return Rect2()


func _enter_ladder_climb(lad: Rect2, is_descent_from_ground: bool = false) -> void:
	_abort_aiming_session()
	climbing = true
	_ladder_sliding = false
	on_ground = false
	_on_cloud_platform = false
	falling = false
	rolling = false
	diving = false
	sprinting = false
	kneeling = false
	taking_cover = false
	cover_object_id = -1
	ledge_grabbing = false
	air_velocity = Vector2.ZERO
	global_position.x = clampf(global_position.x, lad.position.x + 2.0, lad.end.x - 2.0)
	var lad_solids: Array[Rect2] = _collect_solid_rects()
	global_position.x = _clamp_x_against_solid_walls(global_position.x, global_position.y, lad_solids, global_position.x)
	if is_descent_from_ground:
		_cloud_drop_ignore_until_y = global_position.y + 10.0
		global_position.y = maxf(global_position.y + 2.0, lad.position.y + 8.5)
	_set_state("SLIDE" if is_descent_from_ground else "CLIMB", true)


func _try_step_onto_ladder_platform_at_height(cur_lad: Rect2, old_y: float, new_y: float, move_dir: int, is_holding_up: bool) -> bool:
	var solids: Array[Rect2] = _collect_solid_rects()
	var clouds: Array[Rect2] = _collect_cloud_rects()
	# 1. Check platform/hatch spanning the ladder at the fighter's X
	for cr: Rect2 in clouds:
		if global_position.x + 3.0 > cr.position.x and global_position.x - 3.0 < cr.end.x:
			var is_top_hatch: bool = (cr.position.y >= cur_lad.position.y - 2.0 and cr.position.y <= cur_lad.position.y + 16.0)
			var crossed_top: bool = is_holding_up and is_top_hatch and old_y >= cr.position.y - 1.5 and new_y <= cr.position.y + 1.5
			var paused_on_hatch: bool = (not is_holding_up) and absf(new_y - cr.position.y) <= 3.5
			if (crossed_top or paused_on_hatch) and can_fighter_stand_at_x(global_position.x, cr.position.y):
				global_position.y = cr.position.y
				climbing = false
				_ladder_sliding = false
				on_ground = true
				_on_cloud_platform = true
				_ladder_regrab_cooldown_frames = 8.0
				air_velocity = Vector2.ZERO
				_set_state("RUN" if move_dir != 0 else "IDLE")
				return true

	# 2. If at the top of the ladder, check adjacent left/right floor or cloud ledges at top height
	if new_y <= cur_lad.position.y + 8.5:
		var pref_dir: int = move_dir if move_dir != 0 else (facing if facing != 0 else 1)
		for d: int in [pref_dir, -pref_dir]:
			var side_x: float = (cur_lad.position.x - 5.0) if d < 0 else (cur_lad.end.x + 5.0)
			for sr: Rect2 in solids:
				if side_x + 3.0 > sr.position.x and side_x - 3.0 < sr.end.x:
					if sr.position.y >= cur_lad.position.y - 2.0 and sr.position.y <= cur_lad.position.y + 16.0:
						if can_fighter_stand_at_x(side_x, sr.position.y):
							global_position = Vector2(side_x, sr.position.y)
							climbing = false
							_ladder_sliding = false
							on_ground = true
							_on_cloud_platform = false
							_ladder_regrab_cooldown_frames = 8.0
							air_velocity = Vector2.ZERO
							_set_state("RUN" if move_dir != 0 else "IDLE")
							return true
			for cr2: Rect2 in clouds:
				if side_x + 3.0 > cr2.position.x and side_x - 3.0 < cr2.end.x:
					if cr2.position.y >= cur_lad.position.y - 2.0 and cr2.position.y <= cur_lad.position.y + 16.0:
						if can_fighter_stand_at_x(side_x, cr2.position.y):
							global_position = Vector2(side_x, cr2.position.y)
							climbing = false
							_ladder_sliding = false
							on_ground = true
							_on_cloud_platform = true
							_ladder_regrab_cooldown_frames = 8.0
							air_velocity = Vector2.ZERO
							_set_state("RUN" if move_dir != 0 else "IDLE")
							return true
	return false


func _try_step_onto_adjacent_platform_from_ladder(move_dir: int) -> bool:
	var probe_x: float = global_position.x + float(move_dir) * 4.0
	var solids: Array[Rect2] = _collect_solid_rects()
	var clouds: Array[Rect2] = _collect_cloud_rects()
	var best_y: float = INF
	var is_cloud_hit: bool = false
	for sr: Rect2 in solids:
		if probe_x + 3.0 > sr.position.x and probe_x - 3.0 < sr.end.x:
			if sr.position.y >= global_position.y - 8.0 and sr.position.y <= global_position.y + 6.0 and sr.position.y < best_y:
				if can_fighter_stand_at_x(probe_x, sr.position.y):
					best_y = sr.position.y
					is_cloud_hit = false
	for cr: Rect2 in clouds:
		if probe_x + 3.0 > cr.position.x and probe_x - 3.0 < cr.end.x:
			if cr.position.y >= global_position.y - 8.0 and cr.position.y <= global_position.y + 6.0 and cr.position.y < best_y:
				if can_fighter_stand_at_x(probe_x, cr.position.y):
					best_y = cr.position.y
					is_cloud_hit = true
	if best_y < INF:
		global_position = Vector2(probe_x, best_y)
		on_ground = true
		_on_cloud_platform = is_cloud_hit
		air_velocity = Vector2.ZERO
		_set_state("RUN" if move_dir != 0 else "IDLE")
		return true
	return false


func _try_auto_ledge_grab(inp: Dictionary, move_dir: int) -> bool:
	if _ledge_grab_cooldown_frames > 0.0 or bool(inp.get("down", false)):
		return false
	# Deluxe Ledge Grab: only grab when descending (or at jump apex) and hands are at the ledge top!
	if air_velocity.y < -0.6 or air_velocity.y > 8.0:
		return false

	var solids: Array[Rect2] = _collect_solid_rects()
	var clouds: Array[Rect2] = _collect_cloud_rects()
	var candidates: Array[Rect2] = []
	for sr: Rect2 in solids:
		if sr.size.y >= 5.0 and sr.size.x >= 12.0:
			candidates.append(sr)
	for cr: Rect2 in clouds:
		if cr.size.x >= 12.0:
			candidates.append(cr)

	for sr: Rect2 in candidates:
		var is_thin_cloud: bool = sr.size.y <= 4.5
		# Fighter's feet must be 10..22px below the platform top (so shoulders/hands at y-14 are right at the ledge edge, never when feet can already land on top!)
		if global_position.y < sr.position.y + 10.0 or global_position.y > sr.position.y + 22.0:
			continue
		if is_thin_cloud and (_has_floor_directly_below(solids, global_position, 28.0) or _has_floor_directly_below(clouds, global_position, 28.0)):
			continue

		# Check Left Ledge Corner (fighter to the left of sr.position.x, facing/moving right)
		var max_left_x: float = (sr.position.x - 1.0) if is_thin_cloud else (sr.position.x + 2.5)
		if global_position.x >= sr.position.x - 9.0 and global_position.x <= max_left_x and (facing > 0 or move_dir > 0):
			var head_check: Vector2 = Vector2(sr.position.x + 4.0, sr.position.y - 8.0)
			if not _is_rect_point_solid(solids, head_check) and not _has_floor_directly_below(solids, global_position, 10.0):
				ledge_grabbing = true
				facing = 1
				_ledge_grab_wall_x = sr.position.x
				_ledge_grab_top_y = sr.position.y
				_cloud_drop_ignore_until_y = -99999.0
				global_position = Vector2(sr.position.x - 4.0, sr.position.y + 15.0)
				air_velocity = Vector2.ZERO
				sprinting = false
				body_rotation_deg = 0.0
				_set_state("LEDGE_GRAB", true)
				return true

		# Check Right Ledge Corner (fighter to the right of sr.end.x, facing/moving left)
		var min_right_x: float = (sr.end.x + 1.0) if is_thin_cloud else (sr.end.x - 2.5)
		if global_position.x >= min_right_x and global_position.x <= sr.end.x + 9.0 and (facing < 0 or move_dir < 0):
			var head_check_r: Vector2 = Vector2(sr.end.x - 4.0, sr.position.y - 8.0)
			if not _is_rect_point_solid(solids, head_check_r) and not _has_floor_directly_below(solids, global_position, 10.0):
				ledge_grabbing = true
				facing = -1
				_ledge_grab_wall_x = sr.end.x
				_ledge_grab_top_y = sr.position.y
				_cloud_drop_ignore_until_y = -99999.0
				global_position = Vector2(sr.end.x + 4.0, sr.position.y + 15.0)
				air_velocity = Vector2.ZERO
				sprinting = false
				body_rotation_deg = 0.0
				_set_state("LEDGE_GRAB", true)
				return true
	return false


func _is_rect_point_solid(solids: Array[Rect2], pt: Vector2) -> bool:
	for sr: Rect2 in solids:
		if sr.has_point(pt):
			return true
	return false


func _has_floor_directly_below(solids: Array[Rect2], pos: Vector2, max_dist: float) -> bool:
	for sr: Rect2 in solids:
		if pos.x + 3.0 > sr.position.x and pos.x - 3.0 < sr.end.x:
			if sr.position.y >= pos.y - 1.0 and sr.position.y <= pos.y + max_dist:
				return true
	return false


func _begin_jump(move_dir: int, step_24hz: float = 0.4) -> void:
	_drain_energy(12.0 if sprinting else 5.0)
	on_ground = false
	_on_cloud_platform = false
	_cloud_drop_ignore_until_y = -99999.0
	kneeling = false
	taking_cover = false
	if move_dir != 0:
		_ladder_regrab_cooldown_frames = maxf(_ladder_regrab_cooldown_frames, 6.0)
	air_velocity.y = JUMP_POWER_24HZ
	if sprinting:
		air_velocity.x = float(facing) * SPRINT_SPEED_24HZ * speed_mult
	elif move_dir != 0:
		air_velocity.x = float(move_dir) * RUN_SPEED_24HZ * speed_mult
	_play_sfx("jump")
	_set_state("JUMP", true)
	_step_airborne_movement(step_24hz, {}, move_dir, false)


func _start_roll() -> void:
	_drain_energy(5.0)
	rolling = true
	diving = false
	kneeling = false
	taking_cover = false
	sprinting = false
	body_rotation_deg = 0.0
	_roll_frames = 14.0
	_decrease_burn_state()
	_play_sfx("roll")
	_set_state("ROLL", true)


func _start_dive(move_dir: int = 0, step_24hz: float = 0.4) -> void:
	_drain_energy(12.0)
	if move_dir != 0:
		facing = move_dir
	diving = true
	rolling = false
	on_ground = false
	_on_cloud_platform = false
	_cloud_drop_ignore_until_y = -99999.0
	sprinting = false
	kneeling = false
	taking_cover = false
	global_position.x += float(facing) * 1.0
	global_position.y -= 6.0
	air_velocity.x = float(facing) * DIVE_SPEED_X_24HZ
	air_velocity.y = DIVE_SPEED_Y_24HZ
	body_rotation_deg = clampf(1.5 * maxf(step_24hz, 0.4), -15.0, 28.0)
	_play_sfx("jump")
	_set_state("DIVE", true)
	_try_grab_nearby_target()
	_update_dive_tackled_target()


func _trigger_cloud_drop() -> void:
	_cloud_drop_ignore_until_y = global_position.y + 10.0
	on_ground = false
	_on_cloud_platform = false
	air_velocity.y = maxf(air_velocity.y, 1.2)
	_set_state("JUMP", true)


func can_fighter_stand_at_x(cand_x: float, foot_y: float, ignore_prop: Node2D = null) -> bool:
	var solids: Array[Rect2] = _collect_solid_rects()
	var f_box: Rect2 = Rect2(cand_x - 4.0, foot_y - 14.0, 8.0, 12.0)
	for sr: Rect2 in solids:
		if sr.size.y >= 5.0 and foot_y > sr.position.y + 2.0 and f_box.intersects(sr):
			return false
	if match_world != null:
		var props_var: Variant = match_world.get("props")
		if typeof(props_var) == TYPE_ARRAY:
			for p_var: Variant in props_var as Array:
				if not is_instance_valid(p_var) or p_var == ignore_prop:
					continue
				var prop: Node2D = p_var as Node2D
				if bool(prop.get("is_destroyed")) or not bool(prop.get("has_solid_hitbox")):
					continue
				var ptype: String = str(prop.get("prop_type")).to_upper()
				if ptype in ["TABLE", "TABLE_SMALL", "LAMP_1"] or (ptype == "CRATE_HANGING" and bool(prop.get("is_hanging_released")) and not bool(prop.get("on_ground"))):
					continue
				var prect: Rect2 = prop.call("get_world_rect") as Rect2 if prop.has_method("get_world_rect") else Rect2()
				if prect.size.x > 0.0 and foot_y > prect.position.y + 2.5 and f_box.intersects(prect):
					return false
	return true


func _try_push_prop_chain(first_prop: Node2D, dir_sign: float, desired_dx: float) -> float:
	if first_prop == null or not is_instance_valid(first_prop) or bool(first_prop.get("kinematic")) or bool(first_prop.get("is_destroyed")):
		return 0.0
	var rect0: Rect2 = first_prop.call("get_world_rect") as Rect2 if first_prop.has_method("get_world_rect") else Rect2()
	if rect0.size.x <= 0.0:
		return 0.0

	var chain_props: Array[Node2D] = [first_prop]
	var chain_fighters: Array[Node2D] = []
	var front_x: float = rect0.end.x if dir_sign > 0.0 else rect0.position.x
	var band_top: float = rect0.position.y + 2.0
	var band_bot: float = rect0.end.y - 2.0
	var total_mass: float = maxf(0.5, float(first_prop.get("mass")) if first_prop.get("mass") != null else 1.0)
	var solids: Array[Rect2] = _collect_solid_rects()

	for _iter: int in range(8):
		var wall_probe: Rect2 = Rect2(front_x if dir_sign > 0.0 else (front_x - 2.0), band_top, 2.0, maxf(2.0, band_bot - band_top))
		for sr: Rect2 in solids:
			if sr.size.y >= 5.0 and band_bot > sr.position.y + 1.5 and wall_probe.intersects(sr):
				return 0.0

		var extended: bool = false
		if match_world != null:
			var props_var: Variant = match_world.get("props")
			if typeof(props_var) == TYPE_ARRAY:
				for p_var: Variant in props_var as Array:
					if not is_instance_valid(p_var):
						continue
					var op: Node2D = p_var as Node2D
					if op in chain_props or bool(op.get("is_destroyed")) or not bool(op.get("has_solid_hitbox")):
						continue
					var optype: String = str(op.get("prop_type")).to_upper()
					if optype in ["TABLE", "TABLE_SMALL", "LAMP_1"] or (optype == "CRATE_HANGING" and bool(op.get("is_hanging_released")) and not bool(op.get("on_ground"))):
						continue
					var op_rect: Rect2 = op.call("get_world_rect") as Rect2 if op.has_method("get_world_rect") else Rect2()
					if op_rect.size.x <= 0.0 or op_rect.end.y <= band_top or op_rect.position.y >= band_bot:
						continue
					var gap_p: float = (op_rect.position.x - front_x) if dir_sign > 0.0 else (front_x - op_rect.end.x)
					if gap_p >= -3.0 and gap_p <= 2.5:
						if bool(op.get("kinematic")):
							return 0.0
						chain_props.append(op)
						total_mass += maxf(0.5, float(op.get("mass")) if op.get("mass") != null else 1.0)
						front_x = maxf(front_x, op_rect.end.x) if dir_sign > 0.0 else minf(front_x, op_rect.position.x)
						extended = true
						break

			if not extended:
				for f_var: Variant in _get_all_fighters():
					var of: Node2D = f_var as Node2D
					if of == self or of in chain_fighters or bool(of.get("is_dead")) or bool(of.get("climbing")) or bool(of.get("ledge_grabbing")):
						continue
					if of.global_position.y <= band_top + 1.0 or of.global_position.y - 15.0 >= band_bot:
						continue
					var f_left: float = of.global_position.x - 4.0
					var f_right: float = of.global_position.x + 4.0
					var gap_f: float = (f_left - front_x) if dir_sign > 0.0 else (front_x - f_right)
					if gap_f >= -3.0 and gap_f <= 2.5:
						chain_fighters.append(of)
						total_mass += 1.25
						front_x = maxf(front_x, f_right) if dir_sign > 0.0 else minf(front_x, f_left)
						extended = true
						break

		if not extended:
			break

	# Final wall check at the front of the chain
	var end_probe: Rect2 = Rect2(front_x if dir_sign > 0.0 else (front_x - 2.0), band_top, 2.0, maxf(2.0, band_bot - band_top))
	for sr: Rect2 in solids:
		if sr.size.y >= 5.0 and band_bot > sr.position.y + 1.5 and end_probe.intersects(sr):
			return 0.0

	var chain_count: int = chain_props.size() + chain_fighters.size()
	var resistance: float = total_mass * (1.35 + 1.10 * float(chain_count - 1))
	var push_dist: float = clampf(absf(desired_dx) / maxf(0.85, resistance), 0.03, absf(desired_dx) * 0.72)

	for cf: Node2D in chain_fighters:
		cf.global_position.x += dir_sign * push_dist
	for i: int in range(chain_props.size() - 1, -1, -1):
		var cp: Node2D = chain_props[i]
		var next_px: float = cp.global_position.x + dir_sign * push_dist
		if cp.has_method("_clamp_x_against_walls"):
			next_px = float(cp.call("_clamp_x_against_walls", next_px, cp.global_position.y))
		cp.global_position.x = next_px
		if cp.get("velocity") != null:
			var cp_vel: Vector2 = cp.get("velocity") as Vector2
			cp_vel.x = dir_sign * clampf(push_dist * 0.45, 0.03, 0.55)
			cp.set("velocity", cp_vel)

	return push_dist


func try_push_horizontally_by_prop(dx: float, pusher_prop: Node2D = null) -> bool:
	if is_dead or climbing or ledge_grabbing or absf(dx) <= 0.001:
		return false
	var cand_x: float = global_position.x + dx
	if can_fighter_stand_at_x(cand_x, global_position.y, pusher_prop):
		global_position.x = cand_x
		return true
	return false


func _resolve_solid_prop_space() -> void:
	if is_dead or climbing or ledge_grabbing or match_world == null:
		return
	var props_var: Variant = match_world.get("props")
	if typeof(props_var) != TYPE_ARRAY:
		return
	var f_box: Rect2 = Rect2(global_position.x - 4.0, global_position.y - 14.0, 8.0, 12.0)
	for p_var: Variant in props_var as Array:
		if not is_instance_valid(p_var):
			continue
		var prop: Node2D = p_var as Node2D
		if bool(prop.get("is_destroyed")) or not bool(prop.get("has_solid_hitbox")):
			continue
		if prop.get("last_attacker") == self and float(prop.get("_attacker_ignore_frames")) > 0.0:
			continue
		var ptype: String = str(prop.get("prop_type")).to_upper()
		if ptype in ["TABLE", "TABLE_SMALL", "LAMP_1"] or (ptype == "CRATE_HANGING" and bool(prop.get("is_hanging_released")) and not bool(prop.get("on_ground"))):
			continue
		var prect: Rect2 = prop.call("get_world_rect") as Rect2 if prop.has_method("get_world_rect") else Rect2()
		var prop_top_y: float = float(prop.call("get_obb_top_y_at_x", global_position.x, 3.5)) if prop.has_method("get_obb_top_y_at_x") else prect.position.y
		if on_ground and prop_top_y < INF and global_position.y <= prop_top_y + 5.5 and global_position.y >= prop_top_y - 3.5:
			global_position.y = minf(global_position.y, prop_top_y)
			f_box.position.y = global_position.y - 14.0
			continue
		if prect.size.x <= 0.0 or global_position.y <= prect.position.y + 2.5 or not f_box.intersects(prect):
			continue
		var p_center_x: float = prect.position.x + prect.size.x * 0.5
		# If an airborne fighter's head is sticking up into the bottom of a suspended/kinematic prop (Screenshot 3), push them down out of its bottom!
		if not on_ground and bool(prop.get("kinematic")) and global_position.y > prect.end.y + 1.5 and global_position.y - 15.5 < prect.end.y and absf(global_position.x - p_center_x) < prect.size.x * 0.5:
			global_position.y = maxf(global_position.y, prect.end.y + 15.5)
			f_box.position.y = global_position.y - 14.0
			if air_velocity.y < 0.0:
				air_velocity.y = 0.0
			continue
		var side_sign: float = -1.0 if global_position.x <= p_center_x else 1.0
		var cand_x: float = (prect.position.x - 4.0) if side_sign < 0.0 else (prect.end.x + 4.0)
		if can_fighter_stand_at_x(cand_x, global_position.y, prop):
			global_position.x = cand_x
			f_box.position.x = global_position.x - 4.0
		elif not bool(prop.get("kinematic")):
			# Fighter is blocked on `side_sign` by a wall or another prop (Screenshot 1: squeezed between Crate and Explosive Barrel!),
			# so push `prop` out of the fighter's space instead of overlapping!
			var req_prop_x: float = global_position.x - side_sign * (4.0 + prect.size.x * 0.5)
			if prop.has_method("_clamp_x_against_walls"):
				req_prop_x = float(prop.call("_clamp_x_against_walls", req_prop_x, prop.global_position.y))
			prop.global_position.x = req_prop_x
			if prop.get("velocity") != null:
				var pv: Vector2 = prop.get("velocity") as Vector2
				pv.x = 0.0
				prop.set("velocity", pv)
		elif _is_rect_point_solid(_collect_solid_rects(), Vector2(cand_x, global_position.y - 6.0)):
			global_position.y = prect.position.y


func _clamp_x_against_solid_walls(cand_x: float, foot_y: float, solids: Array[Rect2], ref_x: float = NAN) -> float:
	var origin_x: float = cand_x if is_nan(ref_x) else ref_x
	var h_box: Rect2 = Rect2(cand_x - 4.0, foot_y - 16.0, 8.0, 13.0)
	for sr: Rect2 in solids:
		if sr.size.y >= 4.0 and foot_y > sr.position.y + 3.0 and foot_y - 16.0 < sr.end.y - 1.5 and h_box.intersects(sr):
			var sr_mid_x: float = sr.position.x + sr.size.x * 0.5
			if origin_x <= sr_mid_x and origin_x + 4.0 <= sr.position.x + 5.0:
				cand_x = minf(cand_x, sr.position.x - 4.0)
				h_box.position.x = cand_x - 4.0
			elif origin_x >= sr_mid_x and origin_x - 4.0 >= sr.end.x - 5.0:
				cand_x = maxf(cand_x, sr.end.x + 4.0)
				h_box.position.x = cand_x - 4.0
	return cand_x


func _does_body_intersect_wall_at(cand_x: float, foot_y: float, solids: Array[Rect2]) -> bool:
	var h_box: Rect2 = Rect2(cand_x - 3.8, foot_y - 15.5, 7.6, 12.0)
	for sr: Rect2 in solids:
		if sr.size.y >= 4.0 and foot_y > sr.position.y + 3.0 and foot_y - 15.5 < sr.end.y - 1.5 and h_box.intersects(sr):
			return true
	return false


func _apply_world_movement(delta_pos: Vector2, _step_24hz: float) -> void:
	var old_pos: Vector2 = global_position
	var new_pos: Vector2 = old_pos + delta_pos
	_near_wall_dir = 0

	# High-impact movements (Diving, Rolling, or fast Falling/Knockback) shatter glass windows in their path before solid wall collection
	if diving or rolling or (falling and air_velocity.length() >= 2.5):
		var ml_glass: Object = _get_map_loader()
		if ml_glass != null:
			var sweep_min_x: float = minf(old_pos.x, new_pos.x) - 5.0
			var sweep_max_x: float = maxf(old_pos.x, new_pos.x) + 5.0
			var sweep_min_y: float = minf(old_pos.y, new_pos.y) - 16.0
			var sweep_max_y: float = maxf(old_pos.y, new_pos.y) + 2.0
			var sweep_rect: Rect2 = Rect2(sweep_min_x, sweep_min_y, sweep_max_x - sweep_min_x, sweep_max_y - sweep_min_y)
			var impact_v: Vector2 = air_velocity if not on_ground else Vector2(float(facing) * 5.0, 1.0)
			if ml_glass.has_method("check_and_break_glass_segment"):
				ml_glass.call("check_and_break_glass_segment", old_pos + Vector2(0.0, -8.0), new_pos + Vector2(0.0, -8.0), impact_v)
			if ml_glass.has_method("damage_glass_in_rect"):
				ml_glass.call("damage_glass_in_rect", sweep_rect, 10.0, impact_v)

	var solids: Array[Rect2] = _collect_solid_rects()
	var prop_solids: Array[Rect2] = _collect_solid_prop_rects(new_pos.x)
	var clouds: Array[Rect2] = _collect_cloud_rects()

	# 1. Horizontal wall check against solid_rects (matches AS3 PlayerEdgeDistance = 4.0)
	if absf(delta_pos.x) > 0.0001:
		var h_box: Rect2 = Rect2(new_pos.x - 4.0, old_pos.y - 16.0, 8.0, 13.0)
		for sr: Rect2 in solids:
			if sr.size.y >= 4.0 and old_pos.y > sr.position.y + 3.0 and old_pos.y - 16.0 < sr.end.y - 1.5 and h_box.intersects(sr):
				var sr_mid_x: float = sr.position.x + sr.size.x * 0.5
				if delta_pos.x > 0.0 and old_pos.x <= sr_mid_x and old_pos.x + 4.0 <= sr.position.x + 5.0:
					new_pos.x = sr.position.x - 4.0
					h_box.position.x = new_pos.x - 4.0
					_near_wall_dir = 1
					if falling:
						air_velocity.x = clampf(-air_velocity.x * 0.5, -2.0, 2.0)
						air_velocity.y = maxf(-2.5, -absf(air_velocity.y) * 0.7)
					else:
						air_velocity.x = 0.0
					if diving:
						_drop_dive_tackled_target()
					break
				elif delta_pos.x < 0.0 and old_pos.x >= sr_mid_x and old_pos.x - 4.0 >= sr.end.x - 5.0:
					new_pos.x = sr.end.x + 4.0
					h_box.position.x = new_pos.x - 4.0
					_near_wall_dir = -1
					if falling:
						air_velocity.x = clampf(-air_velocity.x * 0.5, -2.0, 2.0)
						air_velocity.y = maxf(-2.5, -absf(air_velocity.y) * 0.7)
					else:
						air_velocity.x = 0.0
					if diving:
						_drop_dive_tackled_target()
					break

	# 1b. Horizontal collision, depenetration & jammed-chain resistance against solid interactive props (CRATE, BARREL_EXPLOSIVE, GASCAN, etc.)
	if not is_dead and match_world != null:
		var props_var: Variant = match_world.get("props")
		if typeof(props_var) == TYPE_ARRAY:
			var prop_hbox: Rect2 = Rect2(new_pos.x - 4.0, old_pos.y - 14.0, 8.0, 12.5)
			for p_var: Variant in props_var as Array:
				if not is_instance_valid(p_var):
					continue
				var prop: Node2D = p_var as Node2D
				if bool(prop.get("is_destroyed")) or not bool(prop.get("has_solid_hitbox")):
					continue
				var ptype: String = str(prop.get("prop_type")).to_upper()
				if ptype in ["TABLE", "TABLE_SMALL", "LAMP_1"]:
					continue
				var prect: Rect2 = prop.call("get_world_rect") as Rect2 if prop.has_method("get_world_rect") else Rect2()
				# Only skip horizontal separation for a released falling CRATE_HANGING when the fighter is directly underneath its descending bottom (so it crushes them!)
				if ptype == "CRATE_HANGING" and bool(prop.get("is_hanging_released")) and not bool(prop.get("on_ground")) and old_pos.y > prect.end.y + 1.0:
					continue
				if prect.size.x > 0.0 and old_pos.y > prect.position.y + 2.5 and prop_hbox.intersects(prect):
					if on_ground and not rolling and not diving and absf(delta_pos.x) > 0.01 and not bool(prop.get("kinematic")):
						var dir_s: float = signf(delta_pos.x)
						var p_mid_x: float = prect.position.x + prect.size.x * 0.5
						if (dir_s > 0.0 and old_pos.x <= p_mid_x) or (dir_s < 0.0 and old_pos.x >= p_mid_x):
							_try_push_prop_chain(prop, dir_s, absf(delta_pos.x))
							prect = prop.call("get_world_rect") as Rect2 if prop.has_method("get_world_rect") else prect
					var p_center_x: float = prect.position.x + prect.size.x * 0.5
					var cand_x: float = (prect.position.x - 4.0) if (old_pos.x <= p_center_x) else (prect.end.x + 4.0)
					if _is_rect_point_solid(solids, Vector2(cand_x, old_pos.y - 6.0)):
						# Truly wedged between a moving prop and a static wall -> step up onto the prop top!
						new_pos.y = prect.position.y
						old_pos.y = prect.position.y
					elif can_fighter_stand_at_x(cand_x, old_pos.y, prop):
						new_pos.x = cand_x
						prop_hbox.position.x = new_pos.x - 4.0
					else:
						# Blocked by another prop on the other side: stop at cand_x and push `prop` back so there is zero overlap!
						new_pos.x = cand_x
						prop_hbox.position.x = new_pos.x - 4.0
						if not bool(prop.get("kinematic")):
							var side_s: float = -1.0 if old_pos.x <= p_center_x else 1.0
							prop.global_position.x = new_pos.x - side_s * (4.0 + prect.size.x * 0.5)

	# 2. Vertical floor / ceiling check
	# AS3 Player.as:1742-1767, 3207, 7482-7485: reset cloud drop ignore as soon as feet pass below threshold or move upward
	if _cloud_drop_ignore_until_y > -90000.0 and (old_pos.y >= _cloud_drop_ignore_until_y or new_pos.y >= _cloud_drop_ignore_until_y or delta_pos.y < 0.0):
		_cloud_drop_ignore_until_y = -99999.0

	var landed: bool = false
	var landed_on_cloud: bool = false
	var land_y: float = new_pos.y
	var impact_vy: float = air_velocity.y

	if delta_pos.y >= 0.0 and air_velocity.y >= 0.0:
		# Check solid floors
		for sr: Rect2 in solids:
			if new_pos.x + 4.0 > sr.position.x and new_pos.x - 4.0 < sr.end.x:
				if old_pos.y <= sr.position.y + 2.0 and new_pos.y >= sr.position.y:
					if not landed or sr.position.y < land_y:
						landed = true
						landed_on_cloud = false
						land_y = sr.position.y

		# Check solid interactive prop tops (never ignored by _cloud_drop_ignore_until_y so players never drop inside crates/barrels/gascans!)
		for pr: Rect2 in prop_solids:
			if new_pos.x + 4.0 > pr.position.x and new_pos.x - 4.0 < pr.end.x:
				if old_pos.y <= pr.position.y + 5.5 and new_pos.y >= pr.position.y:
					if not landed or pr.position.y < land_y:
						landed = true
						landed_on_cloud = false
						land_y = pr.position.y

		# Check one-way cloud platforms & elevators if not ignoring (AS3 CollisionFoot snaps feet within 4.5px onto thin cloud shelves)
		if new_pos.y >= _cloud_drop_ignore_until_y:
			for cr: Rect2 in clouds:
				if new_pos.x + 4.0 > cr.position.x and new_pos.x - 4.0 < cr.end.x:
					if old_pos.y <= cr.position.y + 4.8 and new_pos.y >= cr.position.y:
						if not landed or cr.position.y < land_y:
							landed = true
							landed_on_cloud = true
							land_y = cr.position.y

		# Check slope polygons (stairs) if present in MapLoader
		var ml_slope: Object = _get_map_loader()
		if ml_slope != null and ml_slope.get("slope_polygons") != null and not (ml_slope.get("slope_polygons") as Array).is_empty():
			if ml_slope.has_method("get_ground_y_below"):
				var slope_gy: float = float(ml_slope.call("get_ground_y_below", new_pos.x, old_pos.y - 14.0, 26.0, false))
				if slope_gy < INF and old_pos.y <= slope_gy + 14.0 and new_pos.y >= slope_gy - 2.0:
					if _does_body_intersect_wall_at(new_pos.x, slope_gy, solids):
						new_pos.x = _clamp_x_against_solid_walls(new_pos.x, slope_gy, solids, old_pos.x)
						slope_gy = float(ml_slope.call("get_ground_y_below", new_pos.x, old_pos.y - 14.0, 26.0, false))
					if slope_gy < INF and not _does_body_intersect_wall_at(new_pos.x, slope_gy, solids):
						if not landed or slope_gy < land_y:
							landed = true
							landed_on_cloud = false
							land_y = slope_gy

		# Fallback floor when no map solid_rects exist
		if not landed and use_default_floor and solids.is_empty():
			if new_pos.y >= default_floor_y:
				landed = true
				landed_on_cloud = not clouds.is_empty()
				land_y = default_floor_y
	elif delta_pos.y < 0.0:
		# Moving upward: check solid ceilings AND solid props (CollisionHead; prevents jumping upward through the bottom of CRATE_HANGING / props!)
		for sr: Rect2 in solids:
			if sr.size.y >= 4.0 and new_pos.x + 2.5 > sr.position.x and new_pos.x - 2.5 < sr.end.x:
				if old_pos.y > sr.position.y + 2.5 and new_pos.y - 16.0 < sr.end.y and new_pos.y - 2.0 > sr.position.y:
					new_pos.y = minf(old_pos.y, maxf(new_pos.y, sr.end.y + 16.0))
					air_velocity.y = 0.0
					break
		for pr: Rect2 in prop_solids:
			if pr.size.y >= 8.0 and new_pos.x + 3.2 > pr.position.x and new_pos.x - 3.2 < pr.end.x:
				if old_pos.y > pr.end.y - 1.5 and new_pos.y - 16.0 < pr.end.y and new_pos.y - 2.0 > pr.position.y:
					new_pos.y = minf(old_pos.y, maxf(new_pos.y, pr.end.y + 16.0))
					air_velocity.y = 0.0
					break

	if landed:
		_cloud_drop_ignore_until_y = -99999.0
		new_pos.y = land_y
		new_pos.x = _clamp_x_against_solid_walls(new_pos.x, new_pos.y, solids, old_pos.x)
		var was_airborne: bool = not on_ground
		on_ground = true
		_on_cloud_platform = landed_on_cloud
		air_velocity.y = 0.0
		global_position = new_pos
		if was_airborne:
			_on_land_ground(impact_vy)
	elif on_ground and air_velocity.y >= 0.0:
		# Check if an already-grounded fighter is still supported by floor right underneath feet
		var still_supported: bool = false
		var support_cloud: bool = false
		for sr: Rect2 in solids:
			if new_pos.x + 4.0 > sr.position.x and new_pos.x - 4.0 < sr.end.x and absf(new_pos.y - sr.position.y) <= 2.5:
				new_pos.y = minf(new_pos.y, sr.position.y)
				still_supported = true
				break
		if not still_supported:
			for pr: Rect2 in prop_solids:
				if new_pos.x + 4.0 > pr.position.x and new_pos.x - 4.0 < pr.end.x and absf(new_pos.y - pr.position.y) <= 4.5:
					new_pos.y = pr.position.y
					still_supported = true
					break
		if not still_supported and new_pos.y >= _cloud_drop_ignore_until_y:
			for cr: Rect2 in clouds:
				if new_pos.x + 4.0 > cr.position.x and new_pos.x - 4.0 < cr.end.x and absf(new_pos.y - cr.position.y) <= 2.5:
					new_pos.y = minf(new_pos.y, cr.position.y)
					still_supported = true
					support_cloud = true
					break
		if not still_supported:
			var ml_sup: Object = _get_map_loader()
			if ml_sup != null and ml_sup.get("slope_polygons") != null and not (ml_sup.get("slope_polygons") as Array).is_empty():
				if ml_sup.has_method("get_ground_y_below"):
					var s_gy: float = float(ml_sup.call("get_ground_y_below", new_pos.x, new_pos.y - 14.0, 24.0, false))
					if s_gy < INF and absf(new_pos.y - s_gy) <= 8.0 and delta_pos.y >= 0.0:
						if not _does_body_intersect_wall_at(new_pos.x, s_gy, solids):
							new_pos.y = s_gy
							still_supported = true
		if not still_supported and use_default_floor and solids.is_empty() and absf(new_pos.y - default_floor_y) <= 2.0 and delta_pos.y >= 0.0:
			still_supported = true
		on_ground = still_supported
		_on_cloud_platform = support_cloud
	else:
		on_ground = false
		_on_cloud_platform = false

	new_pos.x = _clamp_x_against_solid_walls(new_pos.x, new_pos.y, solids, old_pos.x)
	global_position = new_pos

	# Check map portals
	var ml: Object = _get_map_loader()
	if ml != null:
		if ml.has_method("try_teleport_entity"):
			var p_dir_x: float = signf(delta_pos.x) if absf(delta_pos.x) > 0.05 else float(_near_wall_dir)
			if absf(p_dir_x) > 0.05:
				ml.call("try_teleport_entity", self, p_dir_x)


func _verify_ground_support() -> void:
	if not on_ground or climbing or ledge_grabbing:
		return
	var solids: Array[Rect2] = _collect_solid_rects()
	var prop_solids: Array[Rect2] = _collect_solid_prop_rects(global_position.x)
	var clouds: Array[Rect2] = _collect_cloud_rects()
	var pos: Vector2 = global_position
	if _cloud_drop_ignore_until_y > -90000.0 and pos.y >= _cloud_drop_ignore_until_y:
		_cloud_drop_ignore_until_y = -99999.0
	var still_supported: bool = false
	var support_cloud: bool = false
	for sr: Rect2 in solids:
		if pos.x + 4.0 > sr.position.x and pos.x - 4.0 < sr.end.x and absf(pos.y - sr.position.y) <= 2.5:
			still_supported = true
			break
	if not still_supported:
		for pr: Rect2 in prop_solids:
			if pos.x + 4.0 > pr.position.x and pos.x - 4.0 < pr.end.x and absf(pos.y - pr.position.y) <= 4.5:
				still_supported = true
				break
	if not still_supported and pos.y >= _cloud_drop_ignore_until_y:
		for cr: Rect2 in clouds:
			if pos.x + 4.0 > cr.position.x and pos.x - 4.0 < cr.end.x and absf(pos.y - cr.position.y) <= 3.0:
				still_supported = true
				support_cloud = true
				break
	if not still_supported:
		var ml_sup: Object = _get_map_loader()
		if ml_sup != null and ml_sup.get("slope_polygons") != null and not (ml_sup.get("slope_polygons") as Array).is_empty():
			if ml_sup.has_method("get_ground_y_below"):
				var s_gy: float = float(ml_sup.call("get_ground_y_below", pos.x, pos.y - 14.0, 24.0, false))
				if s_gy < INF and absf(pos.y - s_gy) <= 8.0:
					still_supported = true
	if not still_supported and use_default_floor and solids.is_empty() and absf(pos.y - default_floor_y) <= 2.5:
		still_supported = true
	if not still_supported:
		on_ground = false
		_on_cloud_platform = false
	else:
		_on_cloud_platform = support_cloud


func _damage_props_under_landing(impact_vy: float) -> bool:
	if match_world == null:
		return false
	var props_var: Variant = match_world.get("props")
	if typeof(props_var) != TYPE_ARRAY:
		return false
	var foot_rect: Rect2 = Rect2(global_position.x - 6.0, global_position.y - 4.0, 12.0, 8.0)
	var fall_prop_dmg: float = clampf(absf(impact_vy) * 3.2, 16.0, 42.0) if (falling or impact_vy >= FALL_TRIGGER_SPEED_24HZ) else 14.0
	var any_destroyed: bool = false
	for p_var: Variant in props_var as Array:
		if not is_instance_valid(p_var):
			continue
		var prop: Node2D = p_var as Node2D
		if bool(prop.get("is_destroyed")):
			continue
		var p_rect: Rect2 = prop.call("get_world_rect") as Rect2 if prop.has_method("get_world_rect") else Rect2(prop.global_position.x - 8.0, prop.global_position.y - 8.0, 16.0, 16.0)
		if foot_rect.intersects(p_rect.grow(3.0)):
			if prop.has_method("apply_fall_impact_damage"):
				var broke_p: bool = bool(prop.call("apply_fall_impact_damage", fall_prop_dmg, Vector2(air_velocity.x, maxf(2.0, impact_vy)), self))
				if broke_p:
					any_destroyed = true
			elif prop.has_method("take_damage"):
				prop.call("take_damage", fall_prop_dmg, Vector2(air_velocity.x, maxf(2.0, impact_vy)))
				if bool(prop.get("is_destroyed")):
					any_destroyed = true
	return any_destroyed


func _on_land_ground(impact_vy: float) -> void:
	body_rotation_deg = 0.0
	if _hit_by_bazooka_blast:
		_hit_by_bazooka_blast = false
		if is_dead:
			gib_fighter(Vector2(air_velocity.x, -maxf(2.5, absf(impact_vy) * 0.5)))
			return

	# AS3 Player.as:3255-3278, 3320-3381: diving or landing from free-fall onto fragile glass or props damages/breaks them!
	if diving or falling or impact_vy >= FALL_TRIGGER_SPEED_24HZ:
		var ml_g: Object = _get_map_loader()
		if ml_g != null and ml_g.has_method("damage_glass_in_rect"):
			var broke_glass: bool = bool(ml_g.call(
				"damage_glass_in_rect",
				Rect2(global_position.x - 6.0, global_position.y - 4.0, 12.0, 10.0),
				10.0,
				Vector2(air_velocity.x, maxf(3.0, impact_vy))
			))
			if broke_glass:
				on_ground = false
				air_velocity.y = maxf(2.0, impact_vy * 0.65)
				return
		var broke_prop: bool = _damage_props_under_landing(impact_vy)
		if broke_prop:
			_verify_ground_support()
			if not on_ground:
				air_velocity.y = maxf(1.8, impact_vy * 0.55)
				return

	if diving:
		# Dive landing drops any tackled enemy into KNOCKDOWN and transitions into Roll!
		_drop_dive_tackled_target()
		diving = false
		falling = false
		air_velocity.x = 0.0
		_start_roll()
		return

	if falling or impact_vy >= FALL_TRIGGER_SPEED_24HZ:
		# AS3 Player.as:3347, 3363: landing from a fall reduces burn_state just like rolling
		if burn_state > 0.0:
			_decrease_burn_state()
		# Check AS3 SidewayBounce (Player.as:6435-6453): high horizontal velocity bounces once
		if not _sideway_bounced and absf(air_velocity.x) >= 4.0 and absf(air_velocity.x) > absf(impact_vy):
			_sideway_bounced = true
			var tot_vel: float = Vector2(air_velocity.x, impact_vy).length()
			on_ground = false
			air_velocity.y = minf(-1.8, -tot_vel * 0.3)
			air_velocity.x = signf(air_velocity.x) * tot_vel * 0.55
			_play_sfx("body_fall")
			return

		falling = false
		_sideway_bounced = false
		var dmg: float = (absf(impact_vy) - 3.0) * 1.5
		if dmg >= 3.0:
			_apply_raw_damage(dmg)
		if not is_dead:
			knockdowned = true
			_knockdown_frames = 23.0
			air_velocity.x *= 0.65
			_play_sfx("body_fall")
			_set_state("KNOCKDOWN", true)
		return

	air_velocity.x = 0.0
	falling = false
	_sideway_bounced = false
	if current_state in ["JUMP", "FALL_F", "FALL_B", "JUMPKICK"]:
		_set_state("IDLE")


func _collect_solid_rects() -> Array[Rect2]:
	var out: Array[Rect2] = local_solid_rects.duplicate()
	var ml: Object = _get_map_loader()
	if ml != null:
		var s_var: Variant = ml.get("solid_rects")
		if typeof(s_var) == TYPE_ARRAY:
			for r_v: Variant in s_var as Array:
				out.append(r_v as Rect2)
		if ml.has_method("get_intact_horizontal_glass_rects"):
			var g_rects: Variant = ml.call("get_intact_horizontal_glass_rects")
			if typeof(g_rects) == TYPE_ARRAY:
				for gr_v: Variant in g_rects as Array:
					out.append(gr_v as Rect2)
		if ml.has_method("get_intact_vertical_glass_rects"):
			var vg_rects: Variant = ml.call("get_intact_vertical_glass_rects")
			if typeof(vg_rects) == TYPE_ARRAY:
				for vgr_v: Variant in vg_rects as Array:
					out.append(vgr_v as Rect2)
	return out


func _collect_cloud_rects() -> Array[Rect2]:
	var out: Array[Rect2] = local_cloud_rects.duplicate()
	var ml: Object = _get_map_loader()
	if ml != null:
		var c_var: Variant = ml.get("cloud_rects")
		if typeof(c_var) == TYPE_ARRAY:
			for r_v: Variant in c_var as Array:
				out.append(r_v as Rect2)
		var el_var: Variant = ml.get("elevators")
		if typeof(el_var) == TYPE_ARRAY:
			for e_v: Variant in el_var as Array:
				if typeof(e_v) == TYPE_DICTIONARY:
					var er_v: Variant = (e_v as Dictionary).get("rect")
					if typeof(er_v) == TYPE_RECT2:
						out.append(er_v as Rect2)
	return out


func _collect_solid_prop_rects(at_x: float = NAN) -> Array[Rect2]:
	var out: Array[Rect2] = []
	var qx: float = global_position.x if is_nan(at_x) else at_x
	# AS3 MapPremadeItems.as: solid props (CRATE, TABLE, BARREL, BARREL_EXPLOSIVE, GASCAN, DESK, FILECAB...) are solid standable objects!
	if match_world != null:
		var props_var: Variant = match_world.get("props")
		if typeof(props_var) == TYPE_ARRAY:
			for p_var: Variant in props_var as Array:
				if not is_instance_valid(p_var):
					continue
				var prop: Node2D = p_var as Node2D
				if bool(prop.get("is_destroyed")) or not bool(prop.get("has_solid_hitbox")):
					continue
				if prop.has_method("get_solid_support_rect"):
					var prect: Rect2 = prop.call("get_solid_support_rect") as Rect2
					if prect.size.x > 0.0:
						var rot: float = prop.rotation
						if absf(sin(rot)) > 0.015 and absf(cos(rot)) > 0.015 and prop.has_method("get_obb_top_y_at_x"):
							var hit_r: Rect2 = prop.call("get_hit_rect") as Rect2 if prop.has_method("get_hit_rect") else prect
							var obb_top: float = float(prop.call("get_obb_top_y_at_x", qx, 3.5))
							if obb_top < INF:
								prect = Rect2(hit_r.position.x, obb_top, hit_r.size.x, maxf(4.0, hit_r.end.y - obb_top))
						out.append(prect)
	return out


func _find_ladder_at(pt: Vector2) -> Rect2:
	for lr: Rect2 in local_ladder_rects:
		if lr.has_point(pt):
			return lr
	var ml: Object = _get_map_loader()
	if ml != null and ml.has_method("get_ladder_at"):
		return ml.call("get_ladder_at", pt) as Rect2
	if ml != null:
		var l_var: Variant = ml.get("ladder_rects")
		if typeof(l_var) == TYPE_ARRAY:
			for r_v: Variant in l_var as Array:
				var lr: Rect2 = r_v as Rect2
				if lr.has_point(pt):
					return lr
	return Rect2()


func _find_cover_nearby(dir_override: int = 0) -> int:
	var check_dir: int = dir_override if dir_override != 0 else facing
	var ml: Object = _get_map_loader()
	if ml != null and ml.has_method("find_cover_prop_near"):
		var cid: int = int(ml.call("find_cover_prop_near", global_position, check_dir))
		if cid >= 0:
			return cid
	var fdir: float = 1.0 if check_dir >= 0 else -1.0
	var probe_x: float = global_position.x + fdir * 8.0
	var mid_y: float = global_position.y - 8.0
	if match_world != null:
		var props_var: Variant = match_world.get("props")
		if typeof(props_var) == TYPE_ARRAY:
			for p_var: Variant in props_var as Array:
				if not is_instance_valid(p_var):
					continue
				var prop: Node2D = p_var as Node2D
				if bool(prop.get("is_destroyed")) or not bool(prop.get("allow_cover")):
					continue
				var prect: Rect2 = prop.call("get_world_rect") as Rect2 if prop.has_method("get_world_rect") else Rect2(prop.global_position.x - 7.0, prop.global_position.y - 7.0, 14.0, 14.0)
				var dx_center: float = (prop.global_position.x - global_position.x) * fdir
				if dx_center > 0.0 and probe_x >= prect.position.x - 2.5 and probe_x <= prect.end.x + 2.5:
					if mid_y >= prect.position.y - 2.5 and mid_y <= prect.end.y + 2.5 and prect.position.y >= global_position.y - 22.0:
						return int(prop.get("prop_id")) if prop.get("prop_id") != null else prop.get_instance_id()
	return -1


func _kick_fighters_below_on_ladder(lad_rect: Rect2) -> void:
	# AS3 Player.as:8129-8150, 3115-3131 (LadderKnockdown -> Fall): sliding down onto a climber below knocks them off into free-fall!
	var check_rect: Rect2 = lad_rect.grow(6.0)
	for f_var: Variant in _get_all_fighters():
		var other: Node2D = f_var as Node2D
		if bool(other.get("is_dead")):
			continue
		var other_mid: Vector2 = other.call("get_mid_pos") as Vector2 if other.has_method("get_mid_pos") else (other.global_position + Vector2(0.0, -8.0))
		var on_same_ladder: bool = (
			check_rect.has_point(other.global_position)
			or check_rect.has_point(other_mid)
			or (bool(other.get("climbing")) and absf(other.global_position.x - global_position.x) <= 14.0)
		)
		if on_same_ladder:
			if other.global_position.y > global_position.y - 2.0 and other.global_position.y <= global_position.y + 22.0:
				other.set("climbing", false)
				other.set("_ladder_sliding", false)
				other.set("_ladder_regrab_cooldown_frames", 14.0)
				var knock_dir: int = facing if facing != 0 else 1
				if other.has_method("force_fall"):
					other.call("force_fall", float(knock_dir) * 1.8, -1.2, true)


# --- Damage, Dodge, Disarm, Knockdown & Hit Callbacks ---
func check_projectile_dodge(is_rocket: bool = false) -> bool:
	if not (rolling or diving):
		return false
	if is_rocket:
		# 50% dodge against rockets (1st dodges, 2nd hits)
		var dodged_r: bool = (_dodge_rocket_cursor % 2 == 0)
		_dodge_rocket_cursor += 1
		return dodged_r
	else:
		# 90% dodge against normal bullets (first 9 out of 10 dodge)
		var dodged_b: bool = (_dodge_bullet_cursor % 10 != 9)
		_dodge_bullet_cursor += 1
		return dodged_b


func apply_bullet_hit(
	damage: float,
	pushback: float,
	dir_x: int,
	is_crit: bool,
	_hit_pos: Vector2,
	is_rocket: bool = false
) -> bool:
	if is_dead:
		return false
	if check_projectile_dodge(is_rocket):
		return false

	var push_dir: int = 1 if dir_x >= 0 else -1
	# Getting shot by a bullet never disarms a held gun (only drops a live cooked throwable if cooking one)
	_check_aim_drop(push_dir, false)

	_apply_raw_damage(damage)
	_pushback_accum += pushback

	if not is_dead:
		if _pushback_accum >= 100.0 or is_crit:
			_pushback_accum = 0.0
			force_fall(float(push_dir) * 2.0, -2.0, true)
		else:
			global_position.x += float(push_dir) * clampf(pushback * 0.08, 0.5, 3.0)
	return true


func apply_melee_hit(
	damage: float,
	dir_x: int,
	is_finisher: bool,
	is_kick: bool,
	is_jump_kick: bool,
	_attacker: Node2D = null
) -> void:
	if is_dead:
		return
	var push_dir: int = 1 if dir_x >= 0 else -1

	# Disarm (CheckAimDrop): hitting a fighter with a melee attack while they are aiming a gun or throwable disarms/drops it!
	_check_aim_drop(push_dir, true)

	_apply_raw_damage(damage)
	if is_dead:
		return

	if is_kick or is_jump_kick:
		var k_vx: float = float(push_dir) * (4.6 if (is_jump_kick or not on_ground) else 4.0)
		var k_vy: float = -2.5 if (is_jump_kick or not on_ground) else -2.0
		force_fall(k_vx, k_vy, true)
	elif is_finisher:
		force_fall(float(push_dir) * 3.0, -2.5, true)
	elif not on_ground:
		# Player.as:3662-3666: any melee hit on a jumping/airborne opponent knocks them into Fall()!
		force_fall(air_velocity.x + float(push_dir) * 2.2, minf(air_velocity.y, -1.5), true)
	else:
		_stagger_frames = 8.0
		_apply_world_movement(Vector2(float(push_dir) * 1.8, 0.0), 1.0)
		_set_state("STAGGER", true)


func _check_aim_drop(hit_dir_x: int, allow_gun_disarm: bool = false) -> void:
	# AS3 Player.as:8594-8607 (CheckAimDrop): gun disarm ONLY triggers on melee hits; bullet hits never disarm guns!
	var is_holding_weapon_out: bool = aiming or _fire_seq_active or current_state.begins_with("AIM_") or current_state.begins_with("START_")
	if not is_holding_weapon_out:
		return
	if aim_mode == 1 or _cooking_grenade:
		_drop_live_throwable()
	elif allow_gun_disarm:
		_disarm_active_gun(hit_dir_x)


func _drop_live_throwable() -> void:
	# AS3 Player.as:6604-6621 (DropThrowable): drops a live activated grenade/molotov at the fighter's feet!
	var th_id: String = str(inventory.get(4, ""))
	var th_ammo: int = int(inventory_ammo.get(4, 0))
	_cooking_grenade = false
	aiming = false
	if th_id.is_empty() or th_ammo <= 0:
		return
	inventory_ammo[4] = maxi(0, th_ammo - 1)
	if int(inventory_ammo[4]) <= 0:
		inventory[4] = ""
	var pm: Object = _get_projectile_manager()
	if pm != null and pm.has_method("spawn_throwable"):
		var drop_angle: float = -35.0 if facing >= 0 else -145.0
		pm.call("spawn_throwable", self, th_id, global_position + Vector2(float(facing) * 4.0, -10.0), drop_angle, maxf(18.0, _grenade_fuse_frames))
	_grenade_fuse_frames = 72.0


func _disarm_active_gun(hit_dir_x: int) -> void:
	var gun_id: String = str(inventory.get(active_gun_slot, ""))
	var gun_ammo: int = int(inventory_ammo.get(active_gun_slot, 0))
	if gun_id.is_empty():
		var alt: int = 3 if active_gun_slot == 2 else 2
		gun_id = str(inventory.get(alt, ""))
		gun_ammo = int(inventory_ammo.get(alt, 0))
		if not gun_id.is_empty():
			active_gun_slot = alt

	if gun_id.is_empty():
		return

	last_disarmed_weapon_id = gun_id
	inventory[2] = ""
	inventory_ammo[2] = 0
	inventory[3] = ""
	inventory_ammo[3] = 0
	aiming = false
	_fire_seq_active = false
	_post_fire_aim_hold_frames = 0.0

	var launch_dir: int = 1 if hit_dir_x >= 0 else -1
	var ml: Object = _get_map_loader()
	if ml != null and ml.has_method("is_point_solid"):
		if bool(ml.call("is_point_solid", global_position + Vector2(float(launch_dir) * 22.0, -12.0))):
			launch_dir = -launch_dir
	var drop_pos: Vector2 = global_position + Vector2(float(launch_dir) * 10.0, -12.0)
	if match_world != null:
		if match_world.has_method("spawn_dropped_weapon"):
			var drop_vel: Vector2 = Vector2(float(launch_dir) * randf_range(4.2, 5.0), randf_range(-4.0, -3.4))
			match_world.call("spawn_dropped_weapon", gun_id, drop_pos, gun_ammo, drop_vel)
		elif match_world.has_method("spawn_weapon_pickup"):
			match_world.call("spawn_weapon_pickup", gun_id, drop_pos, gun_ammo, false)


func gib_fighter(impulse: Vector2 = Vector2(0.0, -3.0)) -> void:
	if is_gibbed:
		return
	_check_aim_drop(1 if impulse.x >= 0.0 else -1)
	if not is_dead:
		_apply_raw_damage(max_hp + 999.0)
	is_dead = true
	is_gibbed = true
	_rocket_riding = false
	_hit_by_bazooka_blast = false
	aiming = false
	sprinting = false
	rolling = false
	diving = false
	climbing = false
	ledge_grabbing = false
	if rig_view != null:
		rig_view.visible = false
	var fhs: Object = _get_fire_hazard_system()
	if fhs != null and fhs.has_method("spawn_gibs"):
		fhs.call("spawn_gibs", global_position, impulse)


func apply_explosion_hit(angle_rad: float, power: float, damage: float) -> void:
	if is_gibbed:
		return
	var push_dir: int = 1 if cos(angle_rad) >= 0.0 else -1
	_check_aim_drop(push_dir, false)
	var mult: float = 0.55 if (rolling or diving) else 1.0
	var was_already_dead: bool = is_dead
	var hp_before: float = hp
	if not is_dead:
		_apply_raw_damage(damage * mult)
	var vx: float = cos(angle_rad) * power
	var vy: float = minf(-2.2, sin(angle_rad) * power - 1.5)
	if is_dead and hp_before <= 22.0:
		_hit_by_bazooka_blast = true
	# Only gib (banh xác) when the fighter was already dead (corpse) or had low HP (<= 22.0) and died from the blast!
	if (was_already_dead and damage >= 14.0) or (is_dead and hp_before <= 22.0 and damage >= 10.0) or damage >= 48.0:
		gib_fighter(Vector2(vx, vy))
		return
	force_fall(vx, vy, true)


func add_burn(amount: float, set_full: bool = false) -> void:
	if is_dead:
		return
	if not set_full and (rolling or _roll_burn_immunity_frames > 0.0):
		return
	# AS3 Player.as:2443-2460: `burned` is ONLY set when the fighter dies from fire (`hp <= 0`), NOT while alive!
	if set_full:
		burn_state = 100.0
	else:
		burn_state = clampf(burn_state + amount, 0.0, 100.0)


func force_fall(vx: float, vy: float, knockdown: bool = false) -> void:
	_check_aim_drop(1 if vx >= 0.0 else -1)
	aiming = false
	sprinting = false
	rolling = false
	diving = false
	climbing = false
	_ladder_sliding = false
	_ladder_regrab_cooldown_frames = maxf(_ladder_regrab_cooldown_frames, 12.0)
	ledge_grabbing = false
	kneeling = false
	taking_cover = false
	_fire_seq_active = false
	_melee_active_frames = 0.0
	_mugen_state_active = false
	if is_instance_valid(grabbed_target):
		grabbed_target.set("grabbed_by", null)
		grabbed_target = null

	air_velocity = Vector2(vx, vy)
	if vy < 0.0 or not on_ground:
		on_ground = false
		falling = true
		_set_state("FALL_F" if vx * float(facing) >= 0.0 else "FALL_B", true)
	elif knockdown and on_ground:
		knockdowned = true
		_knockdown_frames = 23.0
		_set_state("KNOCKDOWN", true)


func start_rocket_ride(dir_x: int) -> void:
	# AS3 Player.as:5984-6000 (StuckToProjectile): disarms held weapon and extinguishes fire on the rider!
	_check_aim_drop(dir_x)
	burn_state = 0.0
	_rocket_riding = true
	on_ground = false
	aiming = false
	rolling = false
	diving = false
	facing = 1 if dir_x >= 0 else -1
	body_rotation_deg = 0.0
	current_state = "ROCKET_RIDE_R" if facing >= 0 else "ROCKET_RIDE_L"
	_sync_rig_view()


func update_rocket_ride_pose(angle_deg: float, vel_24hz: Vector2) -> void:
	if not _rocket_riding:
		return
	air_velocity = vel_24hz * 0.5
	var cos_a: float = cos(deg_to_rad(angle_deg))
	facing = 1 if cos_a >= 0.0 else -1
	current_state = "ROCKET_RIDE_R" if facing >= 0 else "ROCKET_RIDE_L"
	body_rotation_deg = angle_deg if facing >= 0 else (angle_deg - 180.0)
	_sync_rig_view()


func end_rocket_ride() -> void:
	_rocket_riding = false
	body_rotation_deg = 0.0
	force_fall(float(facing) * 3.5, -3.2, true)


func _apply_raw_damage(dmg: float) -> void:
	if dmg <= 0.0 or is_dead:
		return
	_hp_damage_timer = 72.0
	hp = maxf(0.0, hp - dmg)
	if hp <= 0.0:
		hp = 0.0
		is_dead = true
		_check_aim_drop(facing)
		# AS3 Player.as:2443-2460: dying while burning (>= 15) turns the fighter into a charred black corpse (`player_burnt`)!
		if burn_state >= 15.0:
			burned = true
			burn_state = 100.0
		aiming = false
		sprinting = false
		rolling = false
		diving = false
		climbing = false
		_fire_seq_active = false
		_cooking_grenade = false
		if is_instance_valid(grabbed_target):
			grabbed_target.set("grabbed_by", null)
			grabbed_target = null
		_play_sfx("wilhelm")
		_set_state("DEATH_KNEEL", true)


func _step_dead_physics(step_24hz: float) -> void:
	_verify_ground_support()
	if not on_ground:
		air_velocity.y = minf(air_velocity.y + GRAVITY_24HZ * step_24hz, TERMINAL_VEL_Y_24HZ)
		_apply_world_movement(air_velocity * step_24hz, step_24hz)
	else:
		air_velocity.x *= pow(0.7, step_24hz)
		# AS3 PlayerState.as:935-952: flames on a grounded charred corpse gradually burn down to 0, leaving the black corpse
		if burned and burn_state > 0.0:
			burn_state = maxf(0.0, minf(burn_state, 90.0) - 1.5 * step_24hz)


# --- Animation Stepping & Rig Synchronization ---
func _set_state(new_state: String, force_reset: bool = false) -> void:
	var upper: String = new_state.to_upper()
	if current_state == upper and not force_reset:
		return
	current_state = upper
	anim_frame_idx = 1
	_anim_seq_idx = 0
	_anim_tick_accum = 0.0


func _advance_animation(step_24hz: float) -> void:
	var reg: Object = _get_registry()
	if reg == null:
		return
	var st_data: Dictionary = reg.call("get_state_data", current_state) as Dictionary
	if st_data.is_empty():
		return
	var keyframes: Array = st_data.get("keyframes", []) as Array
	if keyframes.is_empty():
		return

	_anim_tick_accum += step_24hz
	var cur_kf_idx: int = clampi(_anim_seq_idx, 0, keyframes.size() - 1)
	var cur_kf: Dictionary = keyframes[cur_kf_idx] as Dictionary
	var dur_24hz: float = maxf(0.5, float(cur_kf.get("duration", 1.0)))

	while _anim_tick_accum >= dur_24hz:
		_anim_tick_accum -= dur_24hz
		if _anim_seq_idx + 1 < keyframes.size():
			_anim_seq_idx += 1
		elif bool(st_data.get("loop", false)):
			_anim_seq_idx = 0
		else:
			var next_st: Variant = st_data.get("next_state", null)
			if typeof(next_st) == TYPE_STRING and not str(next_st).is_empty() and current_state == "THROW":
				_set_state(str(next_st))
				return
			break
		cur_kf_idx = clampi(_anim_seq_idx, 0, keyframes.size() - 1)
		cur_kf = keyframes[cur_kf_idx] as Dictionary
		dur_24hz = maxf(0.5, float(cur_kf.get("duration", 1.0)))

	var active_kf_idx: int = clampi(_anim_seq_idx, 0, keyframes.size() - 1)
	var active_kf: Dictionary = keyframes[active_kf_idx] as Dictionary
	anim_frame_idx = int(active_kf.get("frame_nr", active_kf_idx + 1))


func _sync_rig_view() -> void:
	if not (rig_view is _PreloadFighterRigView):
		return
	var rv: _PreloadFighterRigView = rig_view as _PreloadFighterRigView
	rv.mugen_adapter = mugen_adapter
	var active_wid: String = _fire_seq_weapon_id if _fire_seq_active else get_active_weapon_id()
	if active_wid.is_empty() or active_wid == "FISTS":
		active_wid = _last_fired_weapon_id
	var is_laser_gun: bool = aiming and aim_mode == 0 and (active_wid in ["SNIPER", "LASER_GUN"])
	var is_aim_guide: bool = aiming and not is_bot
	rv.apply_rig_state(
		character_id,
		current_state,
		anim_frame_idx,
		facing,
		current_aim_pitch,
		weapon_anim_frame_nr,
		hp,
		max_hp,
		body_rotation_deg,
		is_laser_gun,
		is_aim_guide,
		burn_state,
		is_dead and burned
	)
