# Survival — VF6-WP4

Display title: **Vault Fighters**. Survival is an endless wave/score
run, **not** a Stage campaign checkpoint. Title **Survival** starts a
new director. Dying ends the run and shows the score. Rematch or
pause Restart clears the director and starts a new run.

Wave count, spawn rate, kill/combo/time points, and entity caps are
`ledger:RL-SURVIVAL-LOOP` / `RL-SURVIVAL-WAVE` /
`RL-SURVIVAL-SCORE` / `RL-SURVIVAL-SPAWN` (**approximation**, not
observed Y8). Records are `ledger:RL-SURVIVAL-RECORD` (assumption).
Bots stay smoke. Art stays VF7.

## Player path

| Step | What happens |
|---|---|
| Title **Survival** | New run on catalog default **Skyline Relay** (`rooftops`). Score 0, wave 1. Stage save is untouched. |
| Play | Director fills an escalating roster (1..6 living bots). One live kill clears a wave. Score rises on kills, combo, and wave clear; survive ticks are a small bonus. Last standing does **not** end the run. |
| Pause | Sim tick, director, and score freeze. Resume continues the same run. |
| Death | Game over. Overlay shows score / wave / combo. This is not a Stage loss checkpoint. |
| Rematch / Restart | New run. Director score/wave/combo reset. Best-score record may update. Stage `current_index` does not change. |
| Title | Stage button still reads Stage / Continue Stage from the campaign save. Survival stays **Survival**. |

## How this is not Stage

- Stage advances a four-map catalog and keeps `user://vf_stage/progress.json`. `stage.json` keeps `survival_shipped: false` because Survival is **not** a Stage arena. `title_survival_shipped: true` records that Title Survival is shipped this WP.
- Survival never calls `StageRules.record_win` and never loads a Stage continue map.
- Survival rematch is a new run, not "stay on this arena / keep the checkpoint".
- Best score lives at `user://vf_survival/records.json` (write `.tmp`, park `.bak`, rename). Official/test runs may set `HH_VF_SURVIVAL_STORE`.

## Caps and seed

Living bots cap at 6. Pickups cap at 12. Seed stays `7 + stage * 13`
(`ledger:RL-MATCH-SEED`); Survival uses stage index 0 so official seed
is 7. Mode/map are not mixed.

## Official path

No teleport. No `force_kill`. No `apply_eval` rematch. Title Survival
uses viewport clicks on rooftops. Official score/spawn proof is live
`apply_frames` melee: wave increment, living bots 1→2→3 (then toward
cap 6), kill/combo/wave-clear points, and a live `spawn_denied`
`living_cap` while 6 bots are alive. Idle AFK points are not the
monotonic proof. Pause still is captured while the clock is frozen
and the pause overlay is visible. Official lose is combat
`death_cause=damage` against a bot that actually fought, not a
rooftops pit walk. Restart proves a cleared director. Official soaks are
10-minute headless and 5-minute window wall-clock. P2/bot stay smoke
(`NOT_AI=1`). Loop/wave/score/spawn stay approximation. Not Y8 parity.
