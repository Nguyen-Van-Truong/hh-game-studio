# Known issues — Kho Bí Ẩn (not G5)

Recorded from R8-WP5 playtest evidence and residual honesty.
These are not a G5 accept. If a human review fails quality,
go back to the named WP. Do not open R9 on green checkboxes.

## P2 (playtest)

1. Divider walls at columns 13 and 26 stop a held east-west.
   Openings are only at y=6–8. Happy path uses those openings.
   Owner WP: R8-WP2 map / R8-WP5 bash.
2. Warden north-lane in the door room makes random wander die
   often. The y=8 happy path stays safe. Owner WP: R8-WP5.
3. Official soak p95 was about 21.80 ms vs the 16.67 ms 60 fps
   budget. PERF stayed unproven. Owner WP: R8-WP5.

## Honesty leftovers (do not treat as G5)

- Save schema v1 does not persist player position. Continue
  respawns at the room spawn.
- No drop-item action. “Bỏ item” is skip-pickup only.
- Dual-path test input (`parse_input_event` + `action_press`)
  is agent verify, not a player-facing control.
- ColorRect Body nodes stay as invisible colliders; sprites
  are children. That is legal polish, not a color-rect release.
- Windows review export is a dogfood review build. Clean-VM
  ship without editor/Node/addon/token is R9 after G5.

## Win flag

Relic-reached is the only win. Do not poke `relic_reached`.
