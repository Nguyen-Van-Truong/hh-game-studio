# Vault Fighters input traces (VF1-WP3)

Display title: **Vault Fighters**. Clock is product 60 Hz
(`ledger:RL-SIM-FIXED-60`, class=`assumption`). Not a Y8 tick-rate claim.
Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` (`assumption`). Roll is
`ledger:RL-MOVE-ROLL` (`assumption`). Dive/kick are
`ledger:RL-MOVE-DIVE` / `ledger:RL-MOVE-JUMP-KICK` (`assumption`).
Y8 observation stays `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`).

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

## sprint/

VF2-WP3 official InputFrame traces. Same schema as `official/`.
Replay uses `apply_frames`. No teleport. No `step_fixed`.
Sprint/roll stay `assumption`. Clock stays `ledger:RL-SIM-FIXED-60`.

| File | Beat |
|---|---|
| `double_tap_sprint.json` | tap window starts sprint |
| `tap_window_miss.json` | late second tap stays walk |
| `crouch_roll.json` | sprint then explicit roll |
| `stamina_drain.json` | sprint drain then recover |

## dive/

VF2-WP4 official InputFrame traces. Same schema as `official/`.
Replay uses `apply_frames`. No teleport. No `step_fixed`.
Dive/kick/fall stay `assumption`. Clock stays `ledger:RL-SIM-FIXED-60`.
Y8 observation stays `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`).

| File | Beat |
|---|---|
| `dive_sprint_crouch.json` | police sprint + jump + dive |
| `jump_kick.json` | police aerial kick |
| `dive_pit.json` | police dive into pit still kills |
| `dive_rooftops.json` | rooftops dive |
| `dive_storage.json` | storage dive |
| `dive_hazardous.json` | hazardous in-place dive |

## traversal/

VF2-WP5 official InputFrame traces. Same schema as `official/`.
Replay uses `apply_frames`. No teleport. No `step_fixed`.
Ladder/ledge/drop stay `assumption`. Clock stays `ledger:RL-SIM-FIXED-60`.
Y8 observation stays `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`).
InputFrame `ledge` stays reserved.

| File | Beat |
|---|---|
| `ladder_up_down.json` | Climb Shaft attach / climb / down |
| `ladder_block.json` | Blocked Shaft climb into solid |
| `ledge_recover.json` | Lip Rail grab / recover |
| `drop_through.json` | Drop Decks one-way crouch |
| `cross_dirs.json` | Cross Walk four directions |
| `map_rooftops.json` | rooftops walk / climb |
| `map_storage.json` | storage climb |
| `map_police.json` | police walk |
| `map_hazardous.json` | hazardous walk |

## reaction/

VF3-WP2 official InputFrame traces. Same schema as `official/`.
Replay uses `apply_frames`. No teleport. No `step_fixed`.
Knock/down/invuln/disarm stay `assumption`. Clock stays
`ledger:RL-SIM-FIXED-60`.

| File | Beat |
|---|---|
| `reaction_knock.json` | punch impulse |
| `reaction_down.json` | kick knockdown + get-up |
| `reaction_invuln.json` | punch then second swing after window |
| `reaction_disarm.json` | punch drops a gun |
| `reaction_drop.json` | drop persists; crouch pickup |
| `reaction_chain.json` | punch during knockdown is blocked |

## aim/

VF3-WP3 official InputFrame traces. Same schema as `official/`.
Replay uses `apply_frames`. No teleport. No `step_fixed`.
Hold-to-aim / fire stay `assumption`. Clock stays
`ledger:RL-SIM-FIXED-60`.

| File | Beat |
|---|---|
| `aim_hold.json` | hold fire aims, no spawn |
| `aim_up.json` | hold fire + jump aims up |
| `aim_down.json` | hold fire + crouch aims down |
| `fire_semi.json` | pistol release-to-fire |
| `fire_edges.json` | fire pressed / held / released |
| `fire_wall.json` | pistol shot stops at Cover Wall |

## roster/

VF3-WP5 official InputFrame traces. Same schema as `official/`.
Replay uses `apply_frames`. No teleport. No `step_fixed`.
Roster / slots stay `assumption`. Clock stays
`ledger:RL-SIM-FIXED-60`.

| File | Beat |
|---|---|
| `roster_idle.json` | settle on Roster Lane |
| `roster_keep.json` | start pistol hold/release fire |
| `roster_melee.json` | fists melee |
| `roster_throw.json` | hold/release grenade |

## balance/

VF3-WP6 official InputFrame traces. Same schema as `official/`.
Replay uses `apply_frames`. No teleport. No `step_fixed`.
Chaos / crit / caps stay `assumption`. Clock stays
`ledger:RL-SIM-FIXED-60`. Traces set `"chaos": true`.

| File | Beat |
|---|---|
| `balance_melee.json` | Clinch Alley fists |
| `balance_high.json` | Shelf Shot aim-down fire |
| `balance_pit.json` | Gap Fall P2 pit death |
| `balance_chain.json` | Twin Fuse two nades on `#` |
| `balance_ff.json` | Cross Fire vs2 melee |

## world/

VF4-WP1 official InputFrame traces. Same schema as `official/`.
Replay uses `apply_frames`. No teleport. No `step_fixed`.
World schema / ownership stay `assumption`. Clock stays
`ledger:RL-SIM-FIXED-60`.

| File | Beat |
|---|---|
| `world_idle.json` | settle on Prop Yard |
| `world_walk.json` | short walk that does not reach the prop alcove |

## break/

VF4-WP2 official InputFrame traces. Same schema as `official/`.
Replay uses `apply_frames`. No teleport. No `step_fixed`.
Break / throw stay `assumption`. Clock stays
`ledger:RL-SIM-FIXED-60`.

| File | Beat |
|---|---|
| `break_cover.json` | Shatter Lane pistol breaks glass then passes |
| `break_melee.json` | Break Yard fists break wood |
| `break_shove.json` | Break Yard melee shoves loose crate |
| `break_throw.json` | Break Yard carry then throw on `#` |

## hazard/

VF4-WP3 official InputFrame traces. Same schema as `official/`.
Replay uses `apply_frames`. No teleport. No `step_fixed`.
Chain / fire / hang stay `assumption`. Clock stays
`ledger:RL-SIM-FIXED-60`.

| File | Beat |
|---|---|
| `hazard_chain.json` | Blast Row pistol starts a depth-capped chain |
| `hazard_fire.json` | Ember Walk ignite + burn ticks + cleanup |
| `hazard_roll.json` | Ember Walk roll extinguishes fire |
| `hazard_hang.json` | Blast Row hanging crate drops |

## moving/

VF4-WP4 official InputFrame traces. Same schema as `official/`.
Replay uses `apply_frames`. No teleport. No `step_fixed`.
Door / lift / board / trigger stay `assumption`. Clock stays
`ledger:RL-SIM-FIXED-60`.

| File | Beat |
|---|---|
| `move_door.json` | Gate Hall stand on plate then walk through |
| `move_ride.json` | Lift Shaft board and ride without tunnel |
| `move_drop.json` | Lift Shaft walk off at the top; lift returns |
| `move_yard.json` | Relay Shaft door then lift |

## env/

VF4-WP5 official InputFrame traces. Same schema as `official/`.
Replay uses `apply_frames`. No teleport. No `step_fixed`.
Instant / toxic / water / rotor / spawn / arena stay `assumption`.
Fall stays `ledger:RL-MOVE-FALL`. Clock stays
`ledger:RL-SIM-FIXED-60`.

| File | Beat |
|---|---|
| `env_instant.json` | Void Cut walk-in pit death |
| `env_toxic.json` | Acid Trench enter / idle / exit |
| `env_toxic_death.json` | Acid Trench stay-to-death |
| `env_water.json` | Wash Channel extinguish |
| `env_rotor.json` | Mill Shaft overlap + idle |
| `env_fall.json` | Drop Well standing walk-off |
| `env_yard.json` | Hazard Yard walk |

## fixture/

May use `teleport` / `force_kill` for fast unit setup. Fixture evidence
is **not** official E2E (V-A16). The harness must reject these ops when
`kind=official`.
