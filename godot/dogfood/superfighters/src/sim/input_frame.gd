class_name InputFrame
extends Resource

## One fighter's input for one 60 Hz tick (V-A14).
## Actions are product names. Listing keys cite ledger:RL-CTRL-*.
## Hold-to-aim is first-playable semantics, not observed
## (ledger:RL-CTRL-HOLD-AIM). Roll is a product action
## (ledger:RL-MOVE-ROLL, assumption). Dive/kick are
## ledger:RL-MOVE-DIVE / RL-MOVE-JUMP-KICK (assumption).
## Y8 observation stays ledger:RL-MOVE-ROLL-DIVE (unavailable).

@export var schema_version: int = 1
@export var tick: int = 0
@export var slot: int = 0
@export var held: PackedStringArray = PackedStringArray()
@export var pressed: PackedStringArray = PackedStringArray()
@export var released: PackedStringArray = PackedStringArray()
@export var move_x: float = 0.0
@export var move_y: float = 0.0


func is_held(action: String) -> bool:
	return held.has(action)


func is_pressed(action: String) -> bool:
	return pressed.has(action)


func is_released(action: String) -> bool:
	return released.has(action)


func to_dict() -> Dictionary:
	return {
		"schema": SimConstants.INPUT_FRAME_ID,
		"schema_version": schema_version,
		"tick": tick,
		"slot": slot,
		"held": Array(held),
		"pressed": Array(pressed),
		"released": Array(released),
		"move_x": move_x,
		"move_y": move_y,
	}


static func from_dict(raw: Dictionary) -> InputFrame:
	var frame: InputFrame = InputFrame.new()
	frame.schema_version = int(raw.get("schema_version", SimConstants.SCHEMA_VERSION))
	frame.tick = int(raw.get("tick", 0))
	frame.slot = int(raw.get("slot", 0))
	frame.held = _to_packed(raw.get("held", []))
	frame.pressed = _to_packed(raw.get("pressed", []))
	frame.released = _to_packed(raw.get("released", []))
	frame.move_x = float(raw.get("move_x", 0.0))
	frame.move_y = float(raw.get("move_y", 0.0))
	return frame


static func _to_packed(raw: Variant) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	if raw is PackedStringArray:
		return raw as PackedStringArray
	if raw is Array:
		var i: int = 0
		var arr: Array = raw as Array
		while i < arr.size():
			out.append(str(arr[i]))
			i += 1
	return out
