# Match rules — VF6-WP1

Display title: **Vault Fighters**. One canonical match state machine
(`src/sim/match.gd`, `data/sim/match.json`) is constructed whenever a
started mode opens a `GameSession`. Official VF6-WP1 lifecycle is **vs2**.
vs1 is started for runtime friendly-fire on `fx_melee_close` only. Stage
has a title button that starts the same machine. Campaign order, save,
and reward live in `data/sim/stage.json` (VF6-WP3). Match
`official_lifecycle` stays vs2. Survival is **not
shipped**: no title button, `app.gd` never calls `start_fight("survival")`,
and `uses_machine` stays false until VF6-WP4.

Clock is `ledger:RL-SIM-FIXED-60` (`assumption`). Hold-to-aim stays
`ledger:RL-CTRL-HOLD-AIM` (`assumption`). Y8 roll/dive observation stays
`ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). Not Y8 parity.

## Phases

`boot → menu → countdown → active ⇄ paused → resolved | quit`

`test_driven` skips countdown ticks (`RL-MATCH-COUNTDOWN`, assumption,
not observed). Live play uses a short product countdown.

## Outcomes and end reasons

| Outcome | End reason | Official proof |
|---|---|---|
| win | `last_standing` | Window: title Map cycle + VS 2P click, then `parse_input_event` walk/fire; HUD "Last standing". `match_win.json` is replay/supplemental. |
| lose | `p1_down` | Window: title VS 2P on rooftops, then `parse_input_event` walk into pit; HUD "Down". `match_lose.json` is replay/supplemental. |
| tie | `timeout` | Window: title VS 2P, labeled timer approximation, HUD "Draw". **Not observed.** |
| quit | `quit` | Window: viewport pause + click Quit; title visible (`title_visible_after=true`). |
| restart | fresh `play` | Window: pause overlay Restart click; new `round_id`. Result Rematch (same mode/map) is VF6-WP2. |
| pause | — | Window: `push_input`/`parse_input_event` Esc; HUD "Paused"; sim tick/body frozen. |

`all_down` (same-tick wipe) is implemented in `MatchRules.evaluate` and
is not the official tie path. Official tie is the labeled timeout.

After quit the title shows `Last match ended: quit` so a player can tell
the round ended and start again from the mode buttons.

## Teams and friendly-fire

- vs1 / Stage: FFA, `friendly_fire=false` (`RL-HIT-FF`, assumption)
- vs2: two teams, `friendly_fire=true`
- Survival: not shipped

Spawn seed stays `7 + stage * 13` (`RL-MATCH-SEED`). Mode/map are not
mixed so VF1–VF5 official seeds stay 7.

## Pause

Pause freezes `SimClock`, rejects `apply_frames`, and does not step
physics/combat. Resume discards leftover wall time. Official pause
proof is a dual-clock: authored trace ticks may continue while
`sim_tick` and body hash stay frozen; resume retimes frames back to
the frozen sim tick. `snapshot_hash()` is physics/combat identity and
must stay stable across pause. Lifecycle (phase/outcome/round_id) is
exported on every transition as `post_phase` plus a separate
`match_hash`.

## Official path

No `teleport`. No `force_kill`. Fixture `force_kill` remains for
`tests/traces/fixture/` only. `apply_frames` may drive the sim after
typed `InputEvent`s; it is not the sole evidence row for
win/lose/tie/quit/restart/pause.

P2/bot stay **smoke** until VF6-WP5. Art stays VF7.
