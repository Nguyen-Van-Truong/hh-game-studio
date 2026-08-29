# Vault Fighters

Standalone Godot **4.7.1-stable** dogfood. Mechanics and maps follow
[Superfighters on Y8](https://www.y8.com/games/superfighters). Skins
and the on-screen title are original. This is **not** G6 and **not**
60/60.

Does not modify Kho Bí Ẩn. Does not fork Godot.

## How to run

Kill leftover Godot first. Sequential `--path` only.

```
%LOCALAPPDATA%\HHGodotAgent\tooling\godot-4.7.1-stable\bin\Godot_v4.7.1-stable_win64.exe --path godot/dogfood/superfighters
```

Runtime observe/checkpoint (structured, not UI-pixel guess):
`docs/runtime-diagnostics.md`.

Input map / remap (VF2-WP1): `docs/input-mapping.md`.
Locomotion / camera (VF2-WP2): `docs/locomotion.md`.

Headless loop test:

```
%LOCALAPPDATA%\HHGodotAgent\tooling\godot-4.7.1-stable\bin\Godot_v4.7.1-stable_win64_console.exe --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

## Play

1. Title: VS 1P, VS 2P, or Stage. Cycle map for VS.
2. Last standing wins. Pits kill. Pick up guns by crouching + melee.
3. Escape / Start pauses. Win and Lose offer Restart.

## Controls

**Player 1:** arrows move / jump / crouch / aim · N melee · hold M aim,
release fire · hold comma aim/release throw · Esc pause

**Player 2:** WASD · 1 melee · hold 2 fire · hold 3 throw

**Gamepad (P1 device 0):** stick/dpad · South jump · East crouch · West
melee · RT or Y fire · LB grenade · Start pause

**Gamepad (P2 device 1):** same layout; P1 pad must not drive P2.

Title / Pause **Controls** remaps keyboard binds (atomic save). F11 is
not a fighter key.

Double-tap left/right to sprint (stamina).
Hold-to-aim is a product assumption (`ledger:RL-CTRL-HOLD-AIM`), not an
observed listing behavior.
