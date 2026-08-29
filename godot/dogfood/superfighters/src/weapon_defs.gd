class_name WeaponDefs
extends RefCounted

## Roster-backed weapon table (VF3-WP5). Gun fire numbers also
## live in data/sim/aim.json (VF3-WP3). Grenade numbers also
## live in data/sim/explosive.json (VF3-WP4). Values are tuning.
## Hold-to-aim stays ledger:RL-CTRL-HOLD-AIM (assumption).
## Hold-to-throw stays ledger:RL-NADE-HOLD (assumption).

const _Roster: GDScript = preload("res://src/data/weapons/roster.gd")
const _Aim: GDScript = preload("res://src/sim/aim.gd")
const _Expl: GDScript = preload("res://src/sim/explosive.gd")


static func data(weapon_id: String) -> Dictionary:
	var from_roster: Dictionary = _Roster.item(weapon_id)
	if not from_roster.is_empty():
		return from_roster
	var from_aim: Dictionary = _Aim.gun(weapon_id)
	if not from_aim.is_empty():
		return from_aim
	if weapon_id == "grenade":
		return _Expl.weapon_row()
	if weapon_id == "cinder":
		return _Expl.weapon_row_for("cinder")
	return _Roster.item("fists")


static func spawn_pool() -> PackedStringArray:
	var pool: PackedStringArray = _Roster.spawn_pool()
	if pool.is_empty():
		return PackedStringArray(["pipe", "knife", "pistol", "shotgun", "uzi", "grenade"])
	return pool


static func random_id(rng: RandomNumberGenerator) -> String:
	var pool: PackedStringArray = spawn_pool()
	return String(pool[rng.randi_range(0, pool.size() - 1)])


static func start_gun() -> String:
	return _Roster.start_gun()


static func start_ammo() -> int:
	return _Roster.start_ammo()


static func start_nades() -> int:
	return _Roster.start_nades()
