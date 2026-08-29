class_name Combat
extends RefCounted

## Data-driven melee phases, hitbox/hurtbox overlap, and mode FF.
## Clock is ledger:RL-SIM-FIXED-60 (assumption). Phases stay
## ledger:RL-HIT-PHASES (assumption). Boxes stay
## ledger:RL-HIT-BOX (assumption). Friendly-fire stays
## ledger:RL-HIT-FF (assumption). Hitstop stays
## ledger:RL-HIT-HITSTOP (assumption, presentation only).
## Jump-kick stay ledger:RL-MOVE-JUMP-KICK (assumption).
## Hold-to-aim stays ledger:RL-CTRL-HOLD-AIM (assumption).
## Y8 observation stays ledger:RL-MOVE-ROLL-DIVE (unavailable).
## Not a Y8 play observation.

const PATH: String = "res://data/sim/combat.json"
const SCHEMA_ID: String = "vf.sim.combat.v1"

static var _cache: Dictionary = {}


static func data() -> Dictionary:
	if _cache.is_empty():
		_cache = SimConstants.load_json(PATH)
	return _cache


static func epsilon() -> float:
	return float(data().get("epsilon", SimConstants.EPSILON))


static func hitstop_ticks() -> int:
	return maxi(int(data().get("hitstop_ticks", 2)), 0)


static func weapon_spec(weapon_id: String, style: String) -> Dictionary:
	var weapons: Dictionary = _dict(data().get("weapons", {}))
	var key: String = weapon_id
	if style == "kick":
		key = "kick"
	if not weapons.has(key):
		key = "fists"
	return _dict(weapons.get(key, {}))


static func style_spec(style: String) -> Dictionary:
	var styles: Dictionary = _dict(data().get("styles", {}))
	if styles.has(style):
		return _dict(styles.get(style, {}))
	return _dict(styles.get("melee", {}))


static func startup_ticks(weapon_id: String, style: String) -> int:
	return maxi(int(weapon_spec(weapon_id, style).get("startup", 3)), 1)


static func active_ticks(weapon_id: String, style: String) -> int:
	return maxi(int(weapon_spec(weapon_id, style).get("active", 3)), 1)


static func recovery_ticks(weapon_id: String, style: String) -> int:
	return maxi(int(weapon_spec(weapon_id, style).get("recovery", 8)), 1)


static func total_ticks(weapon_id: String, style: String) -> int:
	return startup_ticks(weapon_id, style) + active_ticks(weapon_id, style) + recovery_ticks(weapon_id, style)


static func damage_of(weapon_id: String, style: String) -> float:
	return float(weapon_spec(weapon_id, style).get("damage", 10.0))


static func knock_of(style: String, facing: float) -> Vector2:
	var spec: Dictionary = style_spec(style)
	var side: float = 1.0 if facing >= 0.0 else -1.0
	return Vector2(side * float(spec.get("knock_x", 80.0)), float(spec.get("knock_y", -40.0)))


static func style_knocks_down(style: String) -> bool:
	return bool(style_spec(style).get("knockdown", false))


static func friendly_fire_on(mode: String) -> bool:
	var row: Dictionary = _dict(data().get("friendly_fire", {}))
	return bool(row.get(mode, false))


static func allows_hit(mode: String, attacker: Fighter, target: Fighter) -> bool:
	if attacker == null or target == null:
		return false
	if attacker == target or target.dead or attacker.dead:
		return false
	if attacker.team == target.team and not friendly_fire_on(mode):
		return false
	return true


static func hurtbox_rect(fighter: Fighter) -> Rect2:
	if fighter == null:
		return Rect2()
	var size: Vector2 = Vector2(10.0, 22.0)
	var offset: Vector2 = fighter.stand_offset
	if fighter.col_shape != null and fighter.col_shape.shape is RectangleShape2D:
		var rect: RectangleShape2D = fighter.col_shape.shape as RectangleShape2D
		size = rect.size
		offset = fighter.col_shape.position
	elif fighter.crouched:
		size = Vector2(10.0, 14.0)
		offset = fighter.crouch_offset
	var center: Vector2 = fighter.global_position + offset
	return Rect2(center - size * 0.5, size)


static func hitbox_rect(fighter: Fighter) -> Rect2:
	if fighter == null:
		return Rect2()
	var spec: Dictionary = weapon_spec(fighter.attack_weapon, fighter.attack_style)
	var size: Vector2 = _vec2(spec.get("hitbox", [16.0, 12.0]), Vector2(16.0, 12.0))
	var offset: Vector2 = _vec2(spec.get("offset", [10.0, -2.0]), Vector2(10.0, -2.0))
	if fighter.attack_style == "crouch" or (fighter.attack_style != "kick" and fighter.crouched):
		size = _vec2(spec.get("crouch_hitbox", [14.0, 10.0]), size)
		offset = _vec2(spec.get("crouch_offset", [10.0, 4.0]), offset)
	var side: float = 1.0 if fighter.facing >= 0.0 else -1.0
	var center: Vector2 = fighter.global_position + Vector2(offset.x * side, offset.y)
	return Rect2(center - size * 0.5, size)


static func overlaps(a: Rect2, b: Rect2) -> bool:
	return a.intersects(b, false)


static func classify_miss(attacker: Fighter, target: Fighter) -> String:
	if attacker == null or target == null:
		return "none"
	var delta: Vector2 = target.global_position - attacker.global_position
	var facing: float = 1.0 if attacker.facing >= 0.0 else -1.0
	if signf(delta.x) != 0.0 and signf(delta.x) != facing:
		return "behind"
	if delta.y < -18.0:
		return "above"
	if delta.y > 18.0:
		return "below"
	if not overlaps(hitbox_rect(attacker), hurtbox_rect(target)):
		return "reach"
	return "none"


static func fixtures() -> Dictionary:
	return _dict(data().get("fixtures", {}))


static func fixture_names() -> Dictionary:
	return _dict(data().get("fixture_names", {}))


static func has_fixture(map_id: String) -> bool:
	return fixtures().has(map_id)


static func fixture_grid(map_id: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	var rows: Variant = fixtures().get(map_id, [])
	if rows is Array:
		var arr: Array = rows as Array
		var i: int = 0
		while i < arr.size():
			out.append(str(arr[i]))
			i += 1
	return out


static func fixture_name(map_id: String) -> String:
	return str(fixture_names().get(map_id, map_id))


static func _dict(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value as Dictionary
	return {}


static func _vec2(value: Variant, fallback: Vector2) -> Vector2:
	if value is Array:
		var arr: Array = value as Array
		if arr.size() >= 2:
			return Vector2(float(arr[0]), float(arr[1]))
	return fallback
