# VF2-WP2 correction-gate verdict

PASS locomotion baseline evidence (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. `CORRECTION_GATE_VF2_WP2` **not** cleared by implementer.

## DoD / Verify (quoted from 29-8 VF2-WP2)

Verify: 60-Hz trace + real window; no tunneling through solid/one-way surface;
snapshot positions within explicit epsilon across runs.

Correction gate: unique `run_id`; evidence layout §18.3; `HASH2` / `TUNNEL` /
`CAMERA` from structured outcomes; `USED_APPLY_FRAMES` counts successful
applies; independent viewport camera postcondition.

## Run

- `run_id`: `VF2WP2-20260829-ASIA-SAIGON-03`
- `command_id`: `cmd.vf2-wp2.locomotion-evidence-gate.1`
- seed `1`, mode `vs2`, map `police`, camera map `rooftops`
- `HASH2=match` `TUNNEL=none` `CAMERA=arena_fit`
- `USED_APPLY_FRAMES=1205` attempted=1205
- source_tree_sha256 `2e9c3bb3778812acb2c078cb7faac1d0e5fed0c403b01704b48574b67e531831`
- base_head `30720a23795ccd6b11a0ca567cdede2d787dc6c8`

## Reproduction

```
python godot/dogfood/superfighters/tests/check_locomotion.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_locomotion.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_locomotion.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Hold-to-aim assumption. Roll/dive unavailable.
- Camera `arena_fit` assumption; independent viewport covers rooftops.
- Not Y8 parity. Not V0.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.
