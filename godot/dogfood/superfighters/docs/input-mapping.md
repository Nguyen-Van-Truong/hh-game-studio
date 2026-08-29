# Vault Fighters — input mapping (VF2-WP1)

Timezone: **Asia/Saigon**. Display title: **Vault Fighters**.
Product input contract. This file does **not** claim Y8 parity.

## What this WP ships

- Physical-keycode keyboard map and device-split gamepad map
- Dead-zone `0.25` on analog actions (`ledger:RL-CTRL-DEADZONE`)
- Pressed / held / released edges on `InputFrame` (`ledger:RL-SIM-INPUT-FRAME`)
- Title/Pause **Controls** remap UI; save is temp+rename (`ledger:RL-CTRL-REMAP`)
- P1 pad is device 0; P2 pad is device 1 (`ledger:RL-CTRL-DEVICE-SPLIT`)

Official proof injects real `InputEvent` with `Input.parse_input_event`
into the running Viewport / Input singleton, then reads
`InputActions.read_player_frame`. It does **not** call `Input.action_press`
and does **not** use cmd-dict `step_fixed`.

## Listing keys (ledger:RL-CTRL-*)

| Slot | Keys | Ledger |
|---|---|---|
| P1 move / jump / crouch | arrows | `ledger:RL-CTRL-P1-MOVE` |
| P1 melee | N | `ledger:RL-CTRL-P1-PUNCH` |
| P1 shoot | M | `ledger:RL-CTRL-P1-SHOOT` |
| P1 throw | comma | `ledger:RL-CTRL-P1-NADE` |
| P2 move | WASD | `ledger:RL-CTRL-P2-MOVE` |
| P2 punch / shoot / throw | 1 / 2 / 3 | `ledger:RL-CTRL-P2-ATK` |
| Fullscreen | F11 is **not** a fighter bind | `ledger:RL-CTRL-FULLSCREEN` |

Hold-to-aim / release-to-fire stays first-playable semantics:
`ledger:RL-CTRL-HOLD-AIM` (`assumption`). Not promoted to `observed`.
Roll is a shipped InputFrame action (`ledger:RL-MOVE-ROLL`,
`assumption`) via crouch-while-sprint; no dedicated remap key.
Dive / kick are shipped InputFrame actions (`ledger:RL-MOVE-DIVE` /
`ledger:RL-MOVE-JUMP-KICK`, `assumption`) via airborne sprint+crouch
and aerial melee; no dedicated remap keys. Y8 observation stays
`ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). Ledge stays reserved.

## Clock (ledger:RL-SIM-FIXED-60)

Class: `assumption`. **Do not** cite 60 Hz as “Y8-like”.

## Gamepad

P1: stick/dpad, South jump, East crouch, West melee, Y/RT fire, LB
grenade, Start pause — device **0**.

P2: the same layout on device **1**. Keyboard 2P stays WASD+1/2/3.

Official leftover-0 verify uses a deterministic **synthetic**
non-hardware device (`ledger:RL-CTRL-SYNTH-PAD`). If a real pad is
connected, a smoke inject still runs and is labeled hardware, but the
golden trace stays synthetic.

## Remap persist (V-A13)

`user://vf_input/remap.json` is written to `.tmp` then renamed.
Schema hash of `data/input/remap_schema.json` is stored in the file.
Malformed or same-device payloads are rejected.

## Verify

```
python godot/dogfood/superfighters/tests/check_input_map.py
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_input_map.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_input_map.gd
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

Windowed inject (no `--headless`) is the running-window InputEvent path.
Official leftover-0 after that process exits.
