class_name WeaponDefs
extends RefCounted


static func data(weapon_id: String) -> Dictionary:
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
	if weapon_id == "pistol":
		return {
			"id": "pistol",
			"name": "Pistol",
			"kind": "gun",
			"slot": "gun",
			"damage": 18.0,
			"range": 0.0,
			"cooldown": 0.38,
			"ammo": 12,
			"pellets": 1,
			"spread": 0.03,
			"speed": 560.0,
			"auto": false,
			"icon": "res://assets/art/item_pistol.png",
		}
	if weapon_id == "shotgun":
		return {
			"id": "shotgun",
			"name": "Shotgun",
			"kind": "gun",
			"slot": "gun",
			"damage": 8.0,
			"range": 0.0,
			"cooldown": 0.70,
			"ammo": 6,
			"pellets": 5,
			"spread": 0.20,
			"speed": 500.0,
			"auto": false,
			"icon": "res://assets/art/item_shotgun.png",
		}
	if weapon_id == "uzi":
		return {
			"id": "uzi",
			"name": "Uzi",
			"kind": "gun",
			"slot": "gun",
			"damage": 7.0,
			"range": 0.0,
			"cooldown": 0.09,
			"ammo": 24,
			"pellets": 1,
			"spread": 0.08,
			"speed": 580.0,
			"auto": true,
			"icon": "res://assets/art/item_uzi.png",
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
