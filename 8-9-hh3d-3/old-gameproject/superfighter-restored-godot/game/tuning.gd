class_name Tuning
extends RefCounted
## Constants taken from Code/Data/Players/PlayerState.as (flash units per frame).
## SCALE lifts the tiny flash stage onto a 1280x720 arena.

const FLASH_FPS: float = 30.0
const SCALE: float = 4.0
const RUN_SPEED: float = 1.7
const GRAVITY: float = 0.6
const JUMP_POWER: float = -5.0
const ROLL_SPEED: float = 2.0
const DIVE_SPEED: float = 3.5
const HEALTH: int = 100
const PUNCH_DAMAGE: int = 8
const BULLET_DAMAGE: int = 12
const PUNCH_COOLDOWN: float = 0.28
const SHOOT_COOLDOWN: float = 0.18
const MAGAZINE: int = 12

static func units_to_px_per_sec(units_per_frame: float) -> float:
	return units_per_frame * FLASH_FPS * SCALE

static func gravity_px() -> float:
	return GRAVITY * FLASH_FPS * FLASH_FPS * SCALE
