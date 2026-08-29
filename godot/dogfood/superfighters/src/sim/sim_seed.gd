class_name SimSeed
extends RefCounted

## Match seed. Formula is the first-playable spawn RNG
## (`7 + stage * 13`). Not an observed Y8 RNG
## (ledger:RL-MODE-CHAOS / ledger:RL-ITEM-RANDOM-SPAWN).


static func for_match(_mode: String, _map_id: String, stage: int) -> int:
	return 7 + stage * 13


static func is_valid(seed: int) -> bool:
	return seed >= 0
