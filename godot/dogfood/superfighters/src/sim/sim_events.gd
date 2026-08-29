class_name SimEventOrder
extends RefCounted

## Deterministic per-tick phase order. Matches GameSession._step_one_tick.
## Combat event payloads belong to later WPs; this is the contract spine.

const SCHEMA_ID: String = SimConstants.EVENT_ORDER_ID

static var PHASES: PackedStringArray = PackedStringArray([
	"input_validate",
	"locomotion",
	"melee",
	"fire_spawn",
	"grenade_spawn",
	"weapon_respawn",
	"projectiles",
	"explosives",
	"match_resolve",
])


static func index_of(phase: String) -> int:
	var i: int = 0
	while i < PHASES.size():
		if String(PHASES[i]) == phase:
			return i
		i += 1
	return -1


static func is_ordered() -> bool:
	var i: int = 1
	while i < PHASES.size():
		if index_of(String(PHASES[i])) <= index_of(String(PHASES[i - 1])):
			return false
		i += 1
	return true
