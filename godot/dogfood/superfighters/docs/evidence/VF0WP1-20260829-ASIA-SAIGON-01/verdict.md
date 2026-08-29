# VF0-WP1 verdict

PASS functional: first playable headless on frozen HEAD `094822467edfe97d20f99890366a0103dc93b9b1`.

- EXIT 0
- `HH_VF_PATH title→fight→win/lose→restart`
- `HH_VF LOOP=proven COMBAT=proven MAPS=proven NO_ERRORS=proven`
- `PASS: Vault Fighters first playable`
- leftover Godot after run: 0

NOT claimed: Y8 parity, V0 gate tick, R9-WP4, G6, GX, 60/60.

Frozen HEAD stderr (expected, VF0-WP2):
- WARNING: 31 ObjectDB instances were leaked at exit
- ERROR: 5 resources still in use at exit

Repro (HEAD snapshot):
```
git archive --format=zip -o %TEMP%\vf0-wp1-head.zip HEAD -- godot/dogfood/superfighters
# expand zip, then:
$godot = Join-Path $env:LOCALAPPDATA 'HHGodotAgent/tooling/godot-4.7.1-stable/bin/Godot_v4.7.1-stable_win64_console.exe'
& $godot --headless --path <extract>\godot\dogfood\superfighters --import
& $godot --headless --path <extract>\godot\dogfood\superfighters --script res://tests/run_all.gd
```

Plan §18.1 (working tree; currently includes unpublished VF0-WP2 mute):
```
$godot = Join-Path $env:LOCALAPPDATA 'HHGodotAgent/tooling/godot-4.7.1-stable/bin/Godot_v4.7.1-stable_win64_console.exe'
& $godot --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
git diff --check -- godot/dogfood/superfighters/
```
