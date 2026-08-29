class_name Explosive
extends RefCounted

## Data-driven grenade arc/bounce/fuse, radial blast, owner/team
## rules, and swept nade collision. Clock is
## ledger:RL-SIM-FIXED-60 (assumption).
## Hold-to-throw stays ledger:RL-NADE-HOLD (assumption).
## Arc stays ledger:RL-NADE-ARC (assumption).
## Bounce stays ledger:RL-NADE-BOUNCE (assumption).
## Fuse stays ledger:RL-NADE-FUSE (assumption).
## Falloff stays ledger:RL-NADE-FALLOFF (assumption).
## Owner skip stays ledger:RL-NADE-OWNER (assumption).
## One explosion stays ledger:RL-NADE-ONCE (assumption).
## Timeout cleanup stays ledger:RL-NADE-TIMEOUT (assumption).
## Swept nade collision stays ledger:RL-NADE-SWEEP (assumption).
## Prop break stays ledger:RL-NADE-PROP (deferred VF4).
## Hold-to-aim stays ledger:RL-CTRL-HOLD-AIM (assumption).
## Y8 observation stays ledger:RL-MOVE-ROLL-DIVE (unavailable).
## Not a Y8 play observation.

const PATH: String = "res://data/sim/explosive.json"
const SCHEMA_ID: String = "vf.sim.explosive.v1"

static var _cache: Dictionary = {}


static func data() -> Dictionary:
	if _cache.is_empty():
		_cache = SimConstants.load_json(PATH)
	return _cache


static func nade() -> Dictionary:
	return _dict(data().get("grenade", {}))


static func weapon_row() -> Dictionary:
	var spec: Dictionary = nade()
	return {
		"id": "grenade",
		"name": str(spec.get("name", "Grenade")),
		"kind": "throw",
		"slot": "nade",
		"damage": float(spec.get("damage", 42.0)),
		"range": float(spec.get("radius", 48.0)),
		"cooldown": throw_cd(),
		"ammo": maxi(int(spec.get("ammo", 3)), 1),
		"pellets": 1,
		"spread": 0.0,
		"speed": float(spec.get("throw_speed", 280.0)),
		"auto": false,
		"icon": str(spec.get("icon", "res://assets/art/item_grenade.png")),
	}


static func fuse_ticks() -> int:
	return maxi(int(nade().get("fuse_ticks", 81)), 1)


static func life_ticks() -> int:
	return maxi(int(nade().get("life_ticks", 180)), fuse_ticks())


static func throw_cd_ticks() -> int:
	return maxi(int(nade().get("throw_cd_ticks", 48)), 1)


static func throw_cd() -> float:
	return float(throw_cd_ticks()) * SimConstants.TICK_DT


static func gravity() -> float:
	return float(nade().get("gravity", 900.0))


static func bounce_x() -> float:
	return float(nade().get("bounce_x", 0.55))


static func bounce_y() -> float:
	return float(nade().get("bounce_y", 0.35))


static func rest_vy() -> float:
	return float(nade().get("rest_vy", 24.0))


static func radius() -> float:
	return float(nade().get("radius", 48.0))


static func damage() -> float:
	return float(nade().get("damage", 42.0))


static func owner_self_damage() -> bool:
	return bool(data().get("owner_self_damage", false))


static func prop_break_mode() -> String:
	return str(data().get("prop_break", "deferred_vf4"))


static func collision_mode() -> String:
	return str(data().get("collision", "swept"))


static func team_damage_on(mode: String) -> bool:
	var row: Dictionary = _dict(data().get("team_damage", {}))
	return bool(row.get(mode, false))


static func throw_origin(fighter: Fighter) -> Vector2:
	if fighter == null:
		return Vector2.ZERO
	var spec: Dictionary = nade()
	var forward: float = float(spec.get("throw_forward", 10.0))
	var lift: float = float(spec.get("throw_lift", -8.0))
	return fighter.global_position + Vector2(fighter.facing * forward, lift)


static func throw_dir(fighter: Fighter) -> Vector2:
	if fighter == null:
		return Vector2.RIGHT
	var dir: Vector2 = fighter.aim_dir
	if dir == Vector2.ZERO:
		dir = fighter.last_aim_dir
	if dir == Vector2.ZERO:
		dir = Vector2(fighter.facing, float(nade().get("throw_bias_y", -0.35)))
	return dir.normalized()


static func throw_velocity(dir: Vector2) -> Vector2:
	var spec: Dictionary = nade()
	var aim: Vector2 = dir
	if aim == Vector2.ZERO:
		aim = Vector2.RIGHT
	aim = aim.normalized()
	return aim * float(spec.get("throw_speed", 280.0)) + Vector2(0.0, float(spec.get("throw_up", -80.0)))


static func predicted_velocity(velocity: Vector2, delta: float) -> Vector2:
	return Vector2(velocity.x, velocity.y + gravity() * delta)


static func predicted_pos(from: Vector2, velocity: Vector2, delta: float) -> Vector2:
	return from + predicted_velocity(velocity, delta) * delta


static func bounce_velocity(incoming: Vector2, hit_floor: bool, hit_ceil: bool, hit_wall: bool) -> Vector2:
	var out: Vector2 = incoming
	var bx: float = bounce_x()
	var by: float = bounce_y()
	if hit_floor and incoming.y > 0.0:
		out.y = -absf(incoming.y) * by
		out.x = incoming.x * bx
	elif hit_ceil and incoming.y < 0.0:
		out.y = absf(incoming.y) * by
		out.x = incoming.x * bx
	if hit_wall:
		out.x = -incoming.x * bx
		if not hit_floor and not hit_ceil:
			out.y = incoming.y
	if absf(out.y) < rest_vy():
		out.y = 0.0
	return out


static func falloff(distance: float) -> float:
	return falloff_of(distance, radius())


static func falloff_of(distance: float, rad: float) -> float:
	if rad <= SimConstants.EPSILON:
		return 0.0
	if distance >= rad:
		return 0.0
	return 1.0 - (distance / rad)


static func blast_damage(distance: float) -> float:
	return damage() * falloff(distance)


static func blast_damage_of(max_damage: float, distance: float, rad: float) -> float:
	return max_damage * falloff_of(distance, rad)


static func blast_knock(from: Vector2, to: Vector2, distance: float) -> Vector2:
	return blast_knock_of(from, to, distance, radius())


static func blast_knock_of(from: Vector2, to: Vector2, distance: float, rad: float) -> Vector2:
	var spec: Dictionary = nade()
	var dir: Vector2 = to - from
	if dir == Vector2.ZERO:
		dir = Vector2.UP
	dir = dir.normalized()
	var scale: float = falloff_of(distance, rad)
	return dir * float(spec.get("knock", 140.0)) * scale + Vector2(0.0, float(spec.get("knock_y", -80.0)) * scale)


static func allows_damage(mode: String, owner_slot: int, owner_team: int, target: Fighter) -> bool:
	if target == null or target.dead:
		return false
	if target.slot == owner_slot and not owner_self_damage():
		return false
	if target.team == owner_team and not team_damage_on(mode):
		return false
	return true


static func fixtures() -> Dictionary:
	return _dict(data().get("fixtures", {}))


static func fixture_names() -> Dictionary:
	return _dict(data().get("fixture_names", {}))


static func has_fixture(map_id: String) -> bool:
	return fixtures().has(map_id)


static func _dict(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value as Dictionary
	return {}
