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

## fixture/

May use `teleport` / `force_kill` for fast unit setup. Fixture evidence
is **not** official E2E (V-A16). The harness must reject these ops when
`kind=official`.
