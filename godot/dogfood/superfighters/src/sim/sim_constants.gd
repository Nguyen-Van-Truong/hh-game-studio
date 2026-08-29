class_name SimConstants
extends RefCounted

## Product simulation constants (V-A14 / V-A15).
## 60 Hz is a Vault Fighters contract, not an observed Y8 clock
## (ledger:RL-SIM-FIXED-60, class=assumption).

const SCHEMA_ID: String = "vf.sim.v1"
const SCHEMA_VERSION: int = 1
const SNAPSHOT_ID: String = "vf.sim.snapshot.v1"
const INPUT_FRAME_ID: String = "vf.sim.input_frame.v1"
const EVENT_ORDER_ID: String = "vf.sim.event_order.v1"
const TRACE_ID: String = "vf.sim.trace.v1"
const LEDGER_ID: String = "vf.sim.event_ledger.v1"
const TICK_HZ: int = 60
const TICK_DT: float = 1.0 / 60.0
const EPSILON: float = 0.001
const HASH_SCALE: float = 1000.0
const ACCUM_EPS: float = 0.0000001
const MAX_CATCHUP: int = 8
const DEFAULT_SNAPSHOT_EVERY: int = 15
const SCHEMA_PATH: String = "res://data/sim/schema.json"
const LAYERS_PATH: String = "res://data/sim/collision_layers.json"
const ACTIONS_PATH: String = "res://data/sim/input_actions.json"
const INPUT_REMAP_SCHEMA_PATH: String = "res://data/input/remap_schema.json"
const INPUT_DEFAULTS_PATH: String = "res://data/input/default_bindings.json"
const INPUT_TRACE_DIR: String = "res://tests/traces/input"
const EVENT_ORDER_PATH: String = "res://data/sim/event_order.json"
const TRACE_SCHEMA_PATH: String = "res://data/sim/trace.json"
const LOCOMOTION_PATH: String = "res://data/sim/locomotion.json"
const LOCO_TRACE_DIR: String = "res://tests/traces/locomotion"
const SPRINT_TRACE_DIR: String = "res://tests/traces/sprint"
const DIVE_TRACE_DIR: String = "res://tests/traces/dive"
const OFFICIAL_TRACE_DIR: String = "res://tests/traces/official"
const FIXTURE_TRACE_DIR: String = "res://tests/traces/fixture"
const RUNTIME_SCHEMA_PATH: String = "res://data/runtime/schema.json"
const RUNTIME_BRIDGE_PATH: String = "res://data/runtime/bridge.json"


static func quantize(value: float) -> int:
	return int(round(value * HASH_SCALE))


static func dequantize(value: int) -> float:
	return float(value) / HASH_SCALE


static func load_json(path: String) -> Dictionary:
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if parsed is Dictionary:
		return parsed as Dictionary
	return {}
