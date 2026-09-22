# HH3D vertical slice

This is an independent product track. It is not GT06 evidence and cannot
close or replace the tooling plan.

The Godot slice is deliberately small but playable: one original arena map,
movement and jump, projectile combat, enemies, a pickup, pause/restart and
JSON save/load. `--deterministic-test`, `--integration-test` and `--smoke-test`
are bounded console modes used by the verification script.

`blender/generate_asset.py` is the source-authoring step for an original
pickup. It has been executed with the official Blender 4.5.10 LTS Python
runtime (`bpy` build `6dc0b208d1b5`). The portable GUI binary on this machine
still has a Windows Side-by-Side `blender.crt` activation issue, so the
verified headless route uses that official runtime package. The generated
`.blend` and `.glb` are ignored build outputs; Godot imports the GLB and the
verification wrapper performs a readback test when it is present.

Save writes use a closed temporary file, a backup rename and recovery before
replacement. This preserves the previous save if the replacement rename fails;
it is a transactional recovery protocol, not a claim of OS-level atomic
replace or power-loss durability.

## Commands

```text
Godot_v4.7.1-stable_win64_console.exe --headless --path vertical-slice --smoke-test
Godot_v4.7.1-stable_win64_console.exe --headless --path vertical-slice --deterministic-test
Godot_v4.7.1-stable_win64_console.exe --headless --path vertical-slice --integration-test
blender.exe --background --python vertical-slice/blender/generate_asset.py
# bounded headless fallback used on this workstation:
python vertical-slice/blender/generate_asset.py
```
