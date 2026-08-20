"""Shared bake-off scenario rows. Tool count is not a score."""

from __future__ import annotations

# Capability rows (PASS = the candidate performed the workflow).
CAPABILITY_STEPS: tuple[str, ...] = (
    "handshake_auth",
    "create_scene",
    "open_scene",
    "save_scene",
    "add_node",
    "delete_node",
    "duplicate_node",
    "reparent_node",
    "reorder_node",
    "set_property",
    "set_resource",
    "script_write",
    "script_validate",
    "script_attach",
    "undo",
    "redo",
    "play",
    "stop",
    "log",
    "screenshot",
    "runtime_state",
    "select_focus",
    "retry_restart",
)

# Negative rows (PASS = the candidate refused with a typed error).
NEGATIVE_STEPS: tuple[str, ...] = (
    "wrong_path",
    "wrong_token",
    "wrong_schema",
    "unsupported_eval_or_callv",
)

STEPS: tuple[str, ...] = CAPABILITY_STEPS + NEGATIVE_STEPS

WEIGHTS: dict[str, int] = {
    "correctness": 5,
    "self_verify": 5,
    "undo": 4,
    "security": 4,
    "maintainability": 3,
    "godot_471": 3,
}
