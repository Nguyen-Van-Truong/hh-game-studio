# Vault Fighters — restore lab

Technical folder: `superfighter-restored-godot2`. Display name is **Vault Fighters**. This is a local research shell. `NOT_Y8_PARITY=1`. Owner acceptance is none.

Authority is the plan in `zdoc/reverse-restore-superfighter-y8-plan.txt` (`PRODUCT_PLAN_AUTHORITY=0`). It does not tick or edit the Superagent or Vault Fighters product plans.

## Engine

Godot **4.7.1-stable** only:

`%LOCALAPPDATA%\HHGodotAgent\tooling\godot-4.7.1-stable\bin\Godot_v4.7.1-stable_win64_console.exe`

Do not open this folder with the HH3D-3 Godot 4.7.2 pin. One Godot process per project path.

## What this shell is

Fixed 60 Hz physics, typed GDScript, and a headless smoke that prints the title and exits. Gameplay, art and audio are later work packages. Original Flash sprites, SWF files and decompiled scripts stay outside this folder.

## Smoke

```powershell
$godot = "$env:LOCALAPPDATA\HHGodotAgent\tooling\godot-4.7.1-stable\bin\Godot_v4.7.1-stable_win64_console.exe"
& $godot --headless --path .
```

Expected process exit is 0 and stdout contains `RRWP0_SMOKE title=Vault Fighters ticks=60`.
