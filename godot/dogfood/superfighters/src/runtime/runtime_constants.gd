class_name RuntimeConstants
extends RefCounted

## Runtime observe / checkpoint contract (VF1-WP4).
## Not a Y8 observation. Clock cites ledger:RL-SIM-FIXED-60.

const SCHEMA_ID: String = "vf.runtime.v1"
const SCHEMA_VERSION: int = 1
const REQUEST_ID: String = "vf.runtime.request.v1"
const RESPONSE_ID: String = "vf.runtime.response.v1"
const OBSERVE_ID: String = "vf.runtime.observe.v1"
const CHECKPOINT_ID: String = "vf.runtime.checkpoint.v1"
const BRIDGE_ID: String = "vf.runtime.bridge.v1"
const SCHEMA_PATH: String = "res://data/runtime/schema.json"
const BRIDGE_PATH: String = "res://data/runtime/bridge.json"
const STORE_DIR: String = "user://vf_runtime/"
const COMMAND_ID_MAX: int = 96
const CHECKPOINT_ID_MAX: int = 64

const OP_OBSERVE: String = "observe"
const OP_CHECKPOINT_CREATE: String = "checkpoint.create"
const OP_CHECKPOINT_RESTORE: String = "checkpoint.restore"
const OP_PAUSE: String = "pause"
const OP_RESUME: String = "resume"

const PERM_OBSERVE: String = "observe"
const PERM_CHECKPOINT: String = "checkpoint"
const PERM_CONTROL: String = "control"

const ERR_MALFORMED: String = "malformed"
const ERR_UNAUTHORIZED: String = "unauthorized"
const ERR_NOT_FOUND: String = "not_found"
const ERR_UNSUPPORTED: String = "unsupported"

const REASON_PLAYER: String = "player"
const REASON_AGENT: String = "agent"


static func permission_for(op: String) -> String:
	if op == OP_OBSERVE:
		return PERM_OBSERVE
	if op == OP_CHECKPOINT_CREATE or op == OP_CHECKPOINT_RESTORE:
		return PERM_CHECKPOINT
	if op == OP_PAUSE or op == OP_RESUME:
		return PERM_CONTROL
	return ""


static func op_mutates_game(op: String) -> bool:
	return op == OP_CHECKPOINT_RESTORE or op == OP_PAUSE or op == OP_RESUME


static func is_known_op(op: String) -> bool:
	return permission_for(op) != ""


static func command_id_ok(command_id: String) -> bool:
	if command_id.is_empty() or command_id.length() > COMMAND_ID_MAX:
		return false
	var i: int = 0
	while i < command_id.length():
		var ch: String = command_id.substr(i, 1)
		var ok: bool = (
			(ch >= "A" and ch <= "Z")
			or (ch >= "a" and ch <= "z")
			or (ch >= "0" and ch <= "9")
			or ch == "."
			or ch == "_"
			or ch == "-"
			or ch == ":"
		)
		if not ok:
			return false
		i += 1
	return true


static func checkpoint_id_ok(checkpoint_id: String) -> bool:
	if checkpoint_id.is_empty() or checkpoint_id.length() > CHECKPOINT_ID_MAX:
		return false
	if checkpoint_id.contains("..") or checkpoint_id.contains("/") or checkpoint_id.contains("\\"):
		return false
	if checkpoint_id.contains(":") or checkpoint_id.contains("~"):
		return false
	var i: int = 0
	while i < checkpoint_id.length():
		var ch: String = checkpoint_id.substr(i, 1)
		var ok: bool = (
			(ch >= "A" and ch <= "Z")
			or (ch >= "a" and ch <= "z")
			or (ch >= "0" and ch <= "9")
			or ch == "."
			or ch == "_"
			or ch == "-"
		)
		if not ok:
			return false
		i += 1
	return true
