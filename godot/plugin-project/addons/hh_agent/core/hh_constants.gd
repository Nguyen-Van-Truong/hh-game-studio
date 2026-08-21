class_name HHAgentConstants
extends RefCounted

## Protocol and plugin constants. No secrets.

const PROTOCOL: String = "hh-godot-agent/1"
const ACTION_VERSION: String = "1"
const PLUGIN_ID: String = "hh_agent"
const PLUGIN_VERSION: String = "0.3.0"
const AGENT_DIR: String = "HHGodotAgent"
const SESSIONS_DIR: String = "sessions"
const DESCRIPTOR_FILE: String = "session.json"
const NOOP_METHOD: String = "hh.plugin"
const NOOP_ACTION: String = "noop"
const POLICY_DISPLAY: String = "OBSERVE"
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
