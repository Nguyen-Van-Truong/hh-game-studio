# Stage progression — VF6-WP3

Display title: **Vault Fighters**. Stage is a campaign, not one isolated
win per map. Four core arenas load in documented order. A win starts the
**next** catalog map. Loss or rematch stays on the current index.
Survival is **not shipped**. Bots stay smoke. Art stays VF7.

Order and difficulty are `ledger:RL-STAGE-ORDER` /
`ledger:RL-STAGE-TIER` (**approximation**, not observed Y8). Do **not**
cite as Bronze/Silver/Gold or an observed Y8 stage list.

## Stage order

| Index | Map id | Display | Bots | Tier | Score |
|---:|---|---|---:|---|---:|
| 0 | rooftops | Skyline Relay | 1 | tier_1 | 100 |
| 1 | storage | Pallet Annex | 2 | tier_2 | 150 |
| 2 | police | Signal Court | 3 | tier_3 | 200 |
| 3 | hazardous | Vitriol Sump | 3 | tier_4 | 250 |

Bot counts and tier ids are a labeled product approximation.

## Player path

| Step | What happens |
|---|---|
| Title **Stage** | Clean save starts rooftops. A checkpoint continues at `current_index`. |
| Title **Reset Stage** | Wipes score, unlocks, awarded bits; next Stage starts at 0. |
| Win | First-win score/unlock persist atomically; next catalog map loads. |
| Loss / Rematch / pause Restart | Same `stage_index` and catalog map. No skip. No extra reward. |
| Title after a mid-run win | **Continue Stage** resumes the checkpoint map. |

Rematch after a win does not replay the same fight: the campaign already
advanced. Rematch after a loss does not skip ahead.

## Save and reward

Progress lives at `user://vf_stage/progress.json` (temp+rename,
`ledger:RL-STAGE-SAVE`). Official/test runs may set `HH_VF_STAGE_STORE`.
`reward_hash` is SHA-256 of schema, index, score, awarded, unlocks, and
cleared. Winning the same index twice does not change the hash.

## Official path

No teleport. No `force_kill`. No `apply_eval` rematch. Title
Stage/Reset/Rematch uses viewport clicks. Wins happen **on** the
catalog maps (Skyline Relay → Pallet Annex → Signal Court → Vitriol
Sump) against live `is_bot` actors. Loss is a damage / last-standing
fight outcome, not a pit walk. Continue is a cold App reload of the
atomic save. Load/roster rows start each catalog map and count live
bots. P2/bot stay smoke (`NOT_AI=1`). Tiers stay approximation. Not
Y8 parity.
