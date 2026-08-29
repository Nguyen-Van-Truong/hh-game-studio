# Vault Fighters input traces (VF1-WP3)

Display title: **Vault Fighters**. Clock is product 60 Hz
(`ledger:RL-SIM-FIXED-60`, class=`assumption`). Not a Y8 tick-rate claim.
Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` (`assumption`). Roll/dive stay
`ledger:RL-MOVE-ROLL-DIVE` (`unavailable`).

## official/

Replayable `InputFrame` traces. Replay uses `GameSession.apply_frames`
with typed frames (pressed/held/released). **No** `teleport`, **no**
`force_kill`, **no** cmd-dict `step_fixed` as the official MATCH path.

| File | Beat |
|---|---|
| `title_fight_restart.json` | title → fight → restart |
| `walk_jump_crouch.json` | walk / jump / crouch |
| `fire_throw.json` | hold/release fire and throw |
| `death_lose.json` | pit death / lose |
| `win_restart.json` | last-standing win → restart |

## locomotion/

VF2-WP2 official InputFrame traces. Same schema as `official/`.
Replay uses `apply_frames`. No teleport. No `step_fixed`.
Clock stays `ledger:RL-SIM-FIXED-60` (`assumption`).

| File | Beat |
|---|---|
| `walk_accel_friction.json` | walk ramp then friction |
| `variable_jump.json` | held jump |
| `crouch_shape.json` | crouch AABB |
| `pit_fall.json` | walk off police pit |
| `no_tunnel_solid.json` | walk into storage wall |
| `no_tunnel_oneway.json` | idle on hazardous one-way |

## fixture/

May use `teleport` / `force_kill` for fast unit setup. Fixture evidence
is **not** official E2E (V-A16). The harness must reject these ops when
`kind=official`.
