class_name HHAgentConstants
extends RefCounted

## Protocol and plugin constants. No secrets.

const PROTOCOL: String = "hh-godot-agent/1"
const ACTION_VERSION: String = "1"
const PLUGIN_ID: String = "hh_agent"
const PLUGIN_VERSION: String = "0.4.0"
const PINNED_GODOT: String = "4.7.1.stable.official.a13da4feb"
const DEFAULT_PAGE: int = 50
const MAX_PAGE: int = 100
const AGENT_DIR: String = "HHGodotAgent"
const SESSIONS_DIR: String = "sessions"
const DESCRIPTOR_FILE: String = "session.json"
const NOOP_METHOD: String = "hh.plugin"
const NOOP_ACTION: String = "noop"
const POLICY_DISPLAY: String = "OWNER_AUTOPILOT"
const PAUSE_TYPE: String = "pause"
const PAUSE_ACK_TYPE: String = "pause_ack"
const MAX_QUEUE: int = 64
const DRAIN_PER_FRAME: int = 1
const HELLO_TYPE: String = "hello"
const HELLO_OK: String = "hello_ok"
const HELLO_ERR: String = "hello_err"
const REQUEST_TYPE: String = "request"
const RESULT_TYPE: String = "result"
const PING_TYPE: String = "ping"
const PONG_TYPE: String = "pong"
const READBACK_TYPE: String = "readback"
const READBACK_RESULT_TYPE: String = "readback_result"
const RECONNECT_BASE_MS: int = 500
const RECONNECT_CAP_MS: int = 5000
const NODE_UID_META: String = "hh_agent_uid"
const NODE_UID_META_HIDDEN: String = "_hh_agent_uid"
const UNDO_ACTION_PREFIX: String = "Agent: "
const OBSERVER_DIR: String = ".hh-agent/observer"
const OBSERVER_FILE: String = "timeline.json"
const OBSERVER_SCHEMA: String = "hh-observer-timeline/1"
const OBSERVER_RETENTION: int = 10000
const OBSERVER_ACTOR: String = "agent"
const MODE_WATCH: String = "watch"
const MODE_FAST: String = "fast"
const STATUS_PLANNED: String = "planned"
const STATUS_VERIFIED: String = "verified"
const STATUS_FAILED: String = "failed"
