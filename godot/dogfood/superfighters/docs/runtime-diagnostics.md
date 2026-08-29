# Vault Fighters — runtime diagnostics (VF1-WP4)

Timezone: **Asia/Saigon**. Display title: **Vault Fighters**.
In-process observe / checkpoint API, not a Y8 play observation.

Does **not** claim Y8 parity, V0–V6, R9-WP4, G6, GX, or 60/60.

## What this WP ships

- Read-only `observe` snapshot with `seed`, `map_id`, `mode`, tick,
  `pause_reason`, actor/weapon/prop event channels, and UI flags
- `checkpoint.create` / `checkpoint.restore` with hash postcondition
- Bridge request schema (`data/runtime/bridge.json`) for VF8 to adapt
- Token / path secret redaction (V-A8). Tokens are never echoed

This is **not** the live editor MCP socket. VF8-WP1 owns that adapter.

## Clock (ledger:RL-SIM-FIXED-60)

Class: `assumption`. **Do not** cite 60 Hz as “Y8-like”.
Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` (`assumption`).
Roll/dive stay `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`).

## Observe (ledger:RL-RUNTIME-OBSERVE)

`RuntimeApi.handle` accepts `vf.runtime.request.v1` and returns
`vf.runtime.response.v1`. `observe` does not advance the clock or
move actors. Agents should read this payload instead of guessing from
HUD pixels.

Prop events are an empty channel in the first-playable slice — there
are no interactive barrels/glass yet. That is honest emptiness, not a
Y8 claim.

## Checkpoint

Create stores a capture (memory + atomic `user://vf_runtime/<id>.json`).
Restore rebuilds the same `mode`/`map_id`/`stage` and applies fighter,
weapon, projectile, respawn, ledger, and pause fields. Postcondition:
`snapshot_hash` equals the captured hash.

Client-supplied filesystem paths are rejected. `checkpoint_id` may only
use `A-Za-z0-9._-`.

## Auth

Empty server token is fail-closed. Wrong token and malformed requests
must not mutate tick, hash, pause, or P1 position. Mutating ops use
`command_id` idempotency.

## Verify

```
python godot/dogfood/superfighters/tests/check_runtime_api.py
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_runtime_api.gd
```
