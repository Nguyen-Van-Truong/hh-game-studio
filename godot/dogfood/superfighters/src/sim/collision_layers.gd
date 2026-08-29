class_name SimCollisionLayers
extends RefCounted

## Named collision bits. Values must stay equal to Maps.COL_*
## (first-playable layers). Not a Y8 physics claim (ledger:RL-DELTA-PHYSICS).

const WORLD: int = 1
const PLATFORM: int = 2
const FIGHTER: int = 4
const PICKUP: int = 8
const HURT: int = 16
const PROP: int = 32


static func as_dict() -> Dictionary:
	return {
		"world": WORLD,
		"platform": PLATFORM,
		"fighter": FIGHTER,
		"pickup": PICKUP,
		"hurt": HURT,
		"prop": PROP,
	}


static func matches_maps() -> bool:
	return (
		WORLD == Maps.COL_WORLD
		and PLATFORM == Maps.COL_PLATFORM
		and FIGHTER == Maps.COL_FIGHTER
		and PICKUP == Maps.COL_PICKUP
		and HURT == Maps.COL_HURT
		and PROP == Maps.COL_PROP
	)
