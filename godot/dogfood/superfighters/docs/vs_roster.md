# Six-map VS roster — VF5-WP6

Display title: **Vault Fighters**. This document does **not** claim Y8 parity.

Sidecar evidence: `docs/evidence/VF5WP6-20260831-ASIA-SAIGON-02/`.
`VF5WP6-20260831-ASIA-SAIGON-01` is void. Do **not** remint `-01` or `-02`.

Official MATCH uses `GameSession.apply_frames` on typed `InputFrame`s.
Clock is `ledger:RL-SIM-FIXED-60` (`assumption`).

## Roster

VS selection (`Maps.vs_ids()`, stable order, not filesystem sort):

| id | display | unique live beat |
|---|---|---|
| rooftops | Skyline Relay | cover break |
| storage | Pallet Annex | hanging cargo + office door |
| police | Signal Court | shootable rotor |
| hazardous | Vitriol Sump | toxic world pickup |
| lantern | Lantern Cut | street gutter water (wet walk slower + no sprint) |
| gauge | Gauge Deck | training lift ride |

Stage stays the four explicit ids. **Draft Yard** (`fx_map_author`) is an
authoring demo and is **not** a VS roster map.

Title Map cycle wraps `gauge` → `rooftops` through `map_btn.pressed`.
No hidden catalog map is VS-selectable only from code. Signal Court
rotor uses the starting pistol; the roster path does not call
`give_weapon`.

## Honesty

- Roster / lantern / gauge stay assumption:
  `ledger:RL-MAP-VS-ROSTER`, `ledger:RL-MAP-LANTERN`, `ledger:RL-MAP-GAUGE`.
- Display names stay original (`ledger:RL-DELTA-MAP-NAMES`).
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Y8 roll/dive stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Jump envelope is product tuning (dx=10 / dy=4).
- P2/bot coverage is smoke, not AI and not Y8 parity.
- Art still VF7. Overlay Q2 854×480 contact sheet is not a second official size.
- No new in-game Y8 play. Not a copied billboard or Y8 collision map.
