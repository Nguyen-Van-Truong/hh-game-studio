class_name WeaponInventory
extends RefCounted

## Four-slot inventory helpers. Pickup replaces the matching slot
## and drops the old item. Melee / explosive / power pickups do not
## strip the firearm (ledger:RL-ITEM-KEEP-GUN, assumption).
## Slot names stay ledger:RL-ITEM-SLOTS-4 (assumption).

const _Roster: GDScript = preload("res://src/data/weapons/roster.gd")


static func snapshot(fighter: Fighter) -> Dictionary:
	if fighter == null:
		return {}
	return {
		"melee": fighter.melee_id,
		"firearm": fighter.gun_id,
		"explosive": fighter.explosive_id,
		"power": fighter.power_id,
		"ammo": fighter.ammo,
		"reserve": fighter.reserve,
		"reload_left": fighter.reload_left,
		"nades": fighter.grenades,
		"power_ammo": fighter.power_ammo,
		"weapon": fighter.weapon_id,
	}


static func apply_snapshot(fighter: Fighter, row: Dictionary) -> void:
	if fighter == null:
		return
	fighter.melee_id = str(row.get("melee", fighter.melee_id))
	fighter.gun_id = str(row.get("firearm", fighter.gun_id))
	fighter.explosive_id = str(row.get("explosive", fighter.explosive_id))
	fighter.power_id = str(row.get("power", fighter.power_id))
	fighter.ammo = int(row.get("ammo", fighter.ammo))
	fighter.reserve = int(row.get("reserve", fighter.reserve))
	fighter.reload_left = int(row.get("reload_left", fighter.reload_left))
	fighter.grenades = int(row.get("nades", fighter.grenades))
	fighter.power_ammo = int(row.get("power_ammo", fighter.power_ammo))
	fighter.weapon_id = str(row.get("weapon", fighter.weapon_id))


static func dropped_on_pickup(fighter: Fighter, next_id: String) -> String:
	if fighter == null:
		return ""
	var slot: String = _Roster.slot_of(next_id)
	if slot == "firearm":
		if fighter.gun_id != "" and fighter.gun_id != next_id:
			return fighter.gun_id
		return ""
	if slot == "melee":
		if fighter.melee_id != "" and fighter.melee_id != next_id:
			return fighter.melee_id
		return ""
	if slot == "explosive":
		if fighter.explosive_id != "" and fighter.explosive_id != next_id and fighter.grenades > 0:
			return fighter.explosive_id
		return ""
	if slot == "power":
		if fighter.power_id != "" and fighter.power_id != next_id and fighter.power_ammo > 0:
			return fighter.power_id
		return ""
	return ""


static func give(fighter: Fighter, next_id: String) -> String:
	if fighter == null:
		return ""
	var spec: Dictionary = _Roster.item(next_id)
	if spec.is_empty():
		spec = WeaponDefs.data(next_id)
	var slot: String = _Roster.canonicalize_slot(str(spec.get("slot", "melee")))
	var dropped: String = ""
	if slot == "explosive" or next_id == "grenade":
		if fighter.explosive_id != "" and fighter.explosive_id != next_id and fighter.grenades > 0:
			dropped = fighter.explosive_id
			fighter.grenades = 0
		fighter.explosive_id = next_id
		fighter.grenades += maxi(int(spec.get("ammo", 1)), 1)
		return dropped
	if slot == "power":
		if fighter.power_id != "" and fighter.power_id != next_id and fighter.power_ammo > 0:
			dropped = fighter.power_id
			fighter.power_ammo = 0
		if fighter.power_id == next_id:
			fighter.power_ammo += maxi(int(spec.get("ammo", 1)), 1)
		else:
			fighter.power_id = next_id
			fighter.power_ammo = maxi(int(spec.get("ammo", 1)), 1)
		return dropped
	if slot == "firearm":
		if fighter.gun_id != "" and fighter.gun_id != next_id:
			dropped = fighter.gun_id
		fighter.gun_id = next_id
		fighter.ammo = int(spec.get("ammo", 0))
		fighter.reserve = int(spec.get("reserve", 0))
		fighter.mag_size = maxi(int(spec.get("mag_size", fighter.ammo)), 0)
		fighter.reload_left = 0
		fighter.weapon_id = next_id
		return dropped
	if fighter.melee_id != "" and fighter.melee_id != next_id:
		dropped = fighter.melee_id
	fighter.melee_id = next_id
	if fighter.ammo <= 0:
		fighter.weapon_id = next_id
	return dropped


static func eject_slot(fighter: Fighter, slot: String) -> String:
	if fighter == null:
		return ""
	var kind: String = _Roster.canonicalize_slot(slot)
	if kind == "explosive":
		if fighter.explosive_id != "" and fighter.grenades > 0:
			var exploded: String = fighter.explosive_id
			fighter.explosive_id = ""
			fighter.grenades = 0
			return exploded
		return ""
	if kind == "power":
		if fighter.power_id != "" and fighter.power_ammo > 0:
			var powered: String = fighter.power_id
			fighter.power_id = ""
			fighter.power_ammo = 0
			return powered
		return ""
	if kind == "firearm":
		if fighter.gun_id != "":
			var gun: String = fighter.gun_id
			fighter.gun_id = ""
			fighter.ammo = 0
			fighter.reserve = 0
			fighter.reload_left = 0
			fighter.weapon_id = fighter.melee_id
			return gun
		return ""
	if kind == "melee":
		if fighter.melee_id != "":
			var melee: String = fighter.melee_id
			fighter.melee_id = ""
			if fighter.weapon_id == melee:
				fighter.weapon_id = fighter.gun_id
			return melee
		return ""
	return ""


static func power_throw_ready(fighter: Fighter) -> bool:
	if fighter == null:
		return false
	return fighter.power_ammo > 0 and _Roster.is_throw(fighter.power_id)
