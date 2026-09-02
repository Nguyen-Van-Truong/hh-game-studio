# Known limitations — mapped to the Capability Matrix (R9-WP4)

This replaces the slogan “the agent can press every Godot button.”
Rows live in [CAPABILITY_MATRIX.md](CAPABILITY_MATRIX.md) (`CM-001` … `CM-159`).
Counts there stay authoritative. This file does not add IDs.

`--provider plan` stays. `CLEAN_VM` stays unproven. `not_g6=1`. GX stays locked.
CLEAN_VM stays unproven. --provider plan stays.

## Honesty rules

| Status in the matrix | What we may say |
|----------------------|-----------------|
| **Supported** | Named action + official E2E ACK, or stock Godot CLI already proven |
| **Alternative** | Same outcome via files / CLI / typed substitute — not “the button works” |
| **Gap** | Missing semantic command or runtime/export proof — do not advertise |

Not every P0 is Supported. Play/debug gaps remain even after R6/R9 smokes.

## Limitations that block a G6 claim

| Limitation | CM-IDs | Matrix status | Honest note |
|------------|--------|---------------|-------------|
| Windows clean-VM export (AC-20) | CM-018, CM-148 | Supported for **smoke/scan on this machine** | Official export is not a clean VM. `CLEAN_VM` unproven. G6. |
| Tamper / version skew on a clean VM (AC-21) | CM-156 | Supported strip/scan here | R9-WP2 TAMPER is this Godot/Node machine only. |
| Clean clone offline (AC-22) | CM-014, CM-146 | Supported CLI/pin here | No offline clean-clone proof. G6. |
| Public store / Steam / sign / channel | CM-158 | Gap (P2) | E3. Agent does not upload. Do not invent a cert. |
| Godot C++ fork | — | — | GX locked. No gap report opened. |

## Play / runtime gaps (do not advertise as buttons)

| Limitation | CM-IDs | Status |
|------------|--------|--------|
| Editor Play / Stop as agent F5/F6 | CM-142, CM-143, CM-144 | Gap — `play.start` stays unverified as a paper-ACK |
| Runtime remote tree | CM-150 | Gap |
| Inject input for agent playtest | CM-151 | Gap |
| Seeded play RNG | CM-159 | Gap |
| Stuck detection | CM-138 | Gap |
| GUT `res://tests/run_all.gd` in plugin-project | CM-154 | Gap — GUT pinned, not enabled |
| Screenshot stills as agent command | CM-147 | Gap (CLI `--write-movie` is Alternative) |

## “All buttons” replacements

| Slogan to refuse | What to say instead |
|------------------|---------------------|
| Agent can press every editor pixel | 159 measurable workflows; mix of Supported / Alternative / Gap |
| Clean VM proven because smoke ran | Smoke ≠ VM. AC-20 is G6. |
| Internal package is a public release | Unsigned internal. E3 for sign/upload/name/channel. |
| Autonomy needs an API key | `--provider plan` is the keyword compiler + DAG |
| Superfighter is in this WP | Not started. Queued after remaining plan WPs. |

## Residual honesty from earlier R9 WPs

- R9-WP1: `job_progress` unproven; cancel/timeout can hold the editor.
- R9-WP2: unsigned checksum rewrite is E3; MICROGAME never Play.
- R9-WP3: leftover `session.json` token; sidecar doctor vs plugin.
  Official WP4 wipes leftover session tokens (live + drill + backup).
  `rotate-token --live` can target the live leftover path.

None of those residuals are a G6 tick.
