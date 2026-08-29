class_name WeaponDefs
extends RefCounted

## Gun fire numbers live in data/sim/aim.json (VF3-WP3).
## Pistol / Uzi / Shotgun differ by data. Melee/nade stay here.
## Hold-to-aim stays ledger:RL-CTRL-HOLD-AIM (assumption).

const _Aim: GDScript = preload("res://src/sim/aim.gd")


static func data(weapon_id: String) -> Dictionary:
	var from_aim: Dictionary = _Aim.gun(weapon_id)
	if not from_aim.is_empty():
		return from_aim
	if weapon_id == "pipe":
		return {
			"id": "pipe",
			"name": "Pipe",
			"kind": "melee",
			"slot": "melee",
			"damage": 20.0,
			"range": 26.0,
			"cooldown": 0.42,
			"ammo": 0,
			"pellets": 1,
			"spread": 0.0,
			"speed": 0.0,
			"auto": false,
			"icon": "res://assets/art/item_pipe.png",
		}
	if weapon_id == "knife":
		return {
			"id": "knife",
			"name": "Knife",
			"kind": "melee",
			"slot": "melee",
			"damage": 14.0,
			"range": 18.0,
			"cooldown": 0.18,
			"ammo": 0,
			"pellets": 1,
			"spread": 0.0,
			"speed": 0.0,
			"auto": false,
			"icon": "res://assets/art/item_knife.png",
		}
	if weapon_id == "grenade":
		return {
			"id": "grenade",
			"name": "Grenade",
			"kind": "throw",
			"slot": "nade",
			"damage": 42.0,
			"range": 48.0,
			"cooldown": 0.80,
			"ammo": 3,
			"pellets": 1,
			"spread": 0.0,
			"speed": 280.0,
			"auto": false,
			"icon": "res://assets/art/item_grenade.png",
		}
	return {
		"id": "fists",
		"name": "Fists",
		"kind": "melee",
		"slot": "melee",
		"damage": 10.0,
		"range": 18.0,
		"cooldown": 0.28,
		"ammo": 0,
		"pellets": 1,
		"spread": 0.0,
		"speed": 0.0,
		"auto": false,
		"icon": "res://assets/ui/ui_icon_fist.png",
	}


static func spawn_pool() -> PackedStringArray:
	return PackedStringArray(["pipe", "knife", "pistol", "shotgun", "uzi", "grenade"])


static func random_id(rng: RandomNumberGenerator) -> String:
	var pool: PackedStringArray = spawn_pool()
	return String(pool[rng.randi_range(0, pool.size() - 1)])


static func start_gun() -> String:
	return "pistol"


static func start_ammo() -> int:
	return 12


static func start_nades() -> int:
	return 3
