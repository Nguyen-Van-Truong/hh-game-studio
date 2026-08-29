class_name Aim
extends RefCounted

## Data-driven hold-to-aim, fire/release, muzzle, recoil, and
## ballistic sweep. Clock is ledger:RL-SIM-FIXED-60 (assumption).
## Hold-to-aim stays ledger:RL-CTRL-HOLD-AIM (assumption).
## Aim dirs stay ledger:RL-AIM-DIRS (assumption).
## Semi release stays ledger:RL-FIRE-SEMI (assumption).
## Auto cadence stays ledger:RL-FIRE-AUTO (assumption).
## Empty ammo stays ledger:RL-FIRE-AMMO (assumption).
## Muzzle stays ledger:RL-FIRE-MUZZLE (assumption).
## Recoil/spread stay ledger:RL-FIRE-RECOIL (assumption).
## Guns are ballistic, not hitscan (ledger:RL-FIRE-BALLISTIC).
## Continuous collision stays ledger:RL-FIRE-SWEEP (assumption).
## Y8 observation stays ledger:RL-MOVE-ROLL-DIVE (unavailable).
## Not a Y8 play observation.

const PATH: String = "res://data/sim/aim.json"
const SCHEMA_ID: String = "vf.sim.aim.v1"
const _Roster: GDScript = preload("res://src/data/weapons/roster.gd")

static var _cache: Dictionary = {}


static func data() -> Dictionary:
	if _cache.is_empty():
		_cache = SimConstants.load_json(PATH)
	return _cache


static func gun(weapon_id: String) -> Dictionary:
	var guns: Dictionary = _dict(data().get("guns", {}))
	if guns.has(weapon_id):
		return _dict(guns.get(weapon_id, {}))
	var from_roster: Dictionary = _Roster.item(weapon_id)
	if str(from_roster.get("kind", "")) == "gun":
		return from_roster
	return {}


static func is_auto(weapon_id: String) -> bool:
	return bool(gun(weapon_id).get("auto", false))


static func fire_mode(weapon_id: String) -> String:
	var spec: Dictionary = gun(weapon_id)
	if spec.is_empty():
		return ""
	if bool(spec.get("auto", false)):
		return "auto"
	return str(spec.get("fire_mode", "semi"))


static func cadence_ticks(weapon_id: String) -> int:
	return maxi(int(gun(weapon_id).get("cadence_ticks", 23)), 1)


static func pellets(weapon_id: String) -> int:
	return maxi(int(gun(weapon_id).get("pellets", 1)), 1)


static func spread(weapon_id: String) -> float:
	return float(gun(weapon_id).get("spread", 0.0))


static func speed(weapon_id: String) -> float:
	return float(gun(weapon_id).get("speed", 560.0))


static func damage(weapon_id: String) -> float:
	return float(gun(weapon_id).get("damage", 10.0))


static func recoil_of(weapon_id: String) -> float:
	return float(gun(weapon_id).get("recoil", 0.0))


static func projectile_mode() -> String:
	return str(data().get("projectile_mode", "ballistic"))


static func uses_hitscan() -> bool:
	return bool(data().get("hitscan", false))


static func collision_mode() -> String:
	return str(data().get("collision", "swept"))


static func muzzle_origin(fighter: Fighter) -> Vector2:
	if fighter == null:
		return Vector2.ZERO
	var spec: Dictionary = gun(fighter.gun_id)
	var forward: float = float(spec.get("muzzle_forward", 14.0))
	var lift: float = float(spec.get("muzzle_lift", -4.0))
	var dir: Vector2 = fighter.aim_dir
	if dir == Vector2.ZERO:
		dir = Vector2(fighter.facing, 0.0)
	dir = dir.normalized()
	return fighter.global_position + dir * forward + Vector2(0.0, lift)


static func pellet_dir(base: Vector2, pellet_index: int, pellet_count: int, spread_rad: float) -> Vector2:
	var dir: Vector2 = base
	if dir == Vector2.ZERO:
		dir = Vector2.RIGHT
	dir = dir.normalized()
	if pellet_count <= 1 or spread_rad == 0.0:
		return dir
	var ang: float = (float(pellet_index) - float(pellet_count - 1) * 0.5) * spread_rad
	return dir.rotated(ang)


static func pose_from_dir(dir: Vector2) -> String:
	if dir.y < -0.4:
		return "aim_up"
	if dir.y > 0.4:
		return "aim_down"
	return "aim_side"


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
