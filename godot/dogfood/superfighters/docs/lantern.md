# Lantern Cut — VF5-WP6

Display title: **Vault Fighters**. This document does **not** claim Y8 parity.

Internal id stays `lantern`. Display name is **Lantern Cut**.
Topology is `ledger:RL-MAP-LANTERN` (`assumption`), not observed Y8.

Compact backstreet: two stacked alleys, fire-escape ladders, a clothesline
one-way, a shutter door, and a west-street wash gutter. Taller/narrower
than the four Stage arenas (48×18). Unique live beat is walking into the
gutter with `apply_frames`. Overlap sets `fighter.wet` from the live
`cut_gutter_*` body (no fabricated `env_id`) and changes locomotion:
walk is slower and sprint is blocked. leftover-0 measures dry vs wet
walk delta on the same body.

Water is a live env on this VS map. It is no longer fixture-only for the
roster. Rotor / toxic stay off this map.

Clock is `ledger:RL-SIM-FIXED-60` (`assumption`). Jump envelope is product
tuning. Art still VF7.
