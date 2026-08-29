class_name InputConstants
extends RefCounted

## Product input contract (VF2-WP1). Listing keys cite ledger:RL-CTRL-*.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption). Hold-to-aim stays
## ledger:RL-CTRL-HOLD-AIM (assumption). Roll is ledger:RL-MOVE-ROLL
## (assumption). Dive/kick are ledger:RL-MOVE-DIVE /
## RL-MOVE-JUMP-KICK (assumption). Y8 observation stays
## ledger:RL-MOVE-ROLL-DIVE (unavailable).

const SCHEMA_ID: String = "vf.input.remap.v1"
const SCHEMA_VERSION: int = 1
const TRACE_ID: String = "vf.input.event_trace.v1"
const SCHEMA_PATH: String = "res://data/input/remap_schema.json"
const DEFAULTS_PATH: String = "res://data/input/default_bindings.json"
const ACTIONS_PATH: String = "res://data/sim/input_actions.json"
const TRACE_DIR: String = "res://tests/traces/input"
const STORE_DIR: String = "user://vf_input/"
const STORE_FILE: String = "remap.json"
const DEADZONE: float = 0.25
const P1_DEVICE: int = 0
const P2_DEVICE: int = 1
const HELD_AXIS: float = 0.35

const ACTION_NAMES: PackedStringArray = [
	"p1_left", "p1_right", "p1_up", "p1_down", "p1_jump", "p1_crouch",
	"p1_melee", "p1_fire", "p1_grenade",
	"p2_left", "p2_right", "p2_up", "p2_down", "p2_jump", "p2_crouch",
	"p2_melee", "p2_fire", "p2_grenade",
	"pause",
]

const FIGHTER_ACTIONS: PackedStringArray = [
	"p1_left", "p1_right", "p1_up", "p1_down", "p1_jump", "p1_crouch",
	"p1_melee", "p1_fire", "p1_grenade",
	"p2_left", "p2_right", "p2_up", "p2_down", "p2_jump", "p2_crouch",
	"p2_melee", "p2_fire", "p2_grenade",
]


static func device_for_slot(slot: int) -> int:
	if slot == 1:
		return P2_DEVICE
	return P1_DEVICE


static func key_from_name(name: String) -> Key:
	match name:
		"LEFT":
			return KEY_LEFT
		"RIGHT":
			return KEY_RIGHT
		"UP":
			return KEY_UP
		"DOWN":
			return KEY_DOWN
		"A":
			return KEY_A
		"D":
			return KEY_D
		"W":
			return KEY_W
		"S":
			return KEY_S
		"N":
			return KEY_N
		"M":
			return KEY_M
		"COMMA":
			return KEY_COMMA
		"ESCAPE":
			return KEY_ESCAPE
		"1":
			return KEY_1
		"2":
			return KEY_2
		"3":
			return KEY_3
		"B":
			return KEY_B
		"F11":
			return KEY_F11
		_:
			return KEY_NONE


static func name_from_key(keycode: Key) -> String:
	match keycode:
		KEY_LEFT:
			return "LEFT"
		KEY_RIGHT:
			return "RIGHT"
		KEY_UP:
			return "UP"
		KEY_DOWN:
			return "DOWN"
		KEY_A:
			return "A"
		KEY_D:
			return "D"
		KEY_W:
			return "W"
		KEY_S:
			return "S"
		KEY_N:
			return "N"
		KEY_M:
			return "M"
		KEY_COMMA:
			return "COMMA"
		KEY_ESCAPE:
			return "ESCAPE"
		KEY_1:
			return "1"
		KEY_2:
			return "2"
		KEY_3:
			return "3"
		KEY_B:
			return "B"
		KEY_F11:
			return "F11"
		_:
			return "KEY_%d" % int(keycode)


static func joy_button_from_name(name: String) -> JoyButton:
	match name:
		"A":
			return JOY_BUTTON_A
		"B":
			return JOY_BUTTON_B
		"X":
			return JOY_BUTTON_X
		"Y":
			return JOY_BUTTON_Y
		"START":
			return JOY_BUTTON_START
		"LEFT_SHOULDER":
			return JOY_BUTTON_LEFT_SHOULDER
		"DPAD_UP":
			return JOY_BUTTON_DPAD_UP
		"DPAD_DOWN":
			return JOY_BUTTON_DPAD_DOWN
		"DPAD_LEFT":
			return JOY_BUTTON_DPAD_LEFT
		"DPAD_RIGHT":
			return JOY_BUTTON_DPAD_RIGHT
		_:
			return JOY_BUTTON_INVALID


static func name_from_joy_button(button: JoyButton) -> String:
	match button:
		JOY_BUTTON_A:
			return "A"
		JOY_BUTTON_B:
			return "B"
		JOY_BUTTON_X:
			return "X"
		JOY_BUTTON_Y:
			return "Y"
		JOY_BUTTON_START:
			return "START"
		JOY_BUTTON_LEFT_SHOULDER:
			return "LEFT_SHOULDER"
		JOY_BUTTON_DPAD_UP:
			return "DPAD_UP"
		JOY_BUTTON_DPAD_DOWN:
			return "DPAD_DOWN"
		JOY_BUTTON_DPAD_LEFT:
			return "DPAD_LEFT"
		JOY_BUTTON_DPAD_RIGHT:
			return "DPAD_RIGHT"
		_:
			return "BUTTON_%d" % int(button)


static func joy_axis_from_name(name: String) -> JoyAxis:
	match name:
		"LEFT_X":
			return JOY_AXIS_LEFT_X
		"LEFT_Y":
			return JOY_AXIS_LEFT_Y
		"TRIGGER_RIGHT":
			return JOY_AXIS_TRIGGER_RIGHT
		_:
			return JOY_AXIS_INVALID


static func name_from_joy_axis(axis: JoyAxis) -> String:
	match axis:
		JOY_AXIS_LEFT_X:
			return "LEFT_X"
		JOY_AXIS_LEFT_Y:
			return "LEFT_Y"
		JOY_AXIS_TRIGGER_RIGHT:
			return "TRIGGER_RIGHT"
		_:
			return "AXIS_%d" % int(axis)
