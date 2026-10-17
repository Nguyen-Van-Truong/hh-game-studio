# SA5 N3 Godot Physics 2D spike

This isolated fixture probes the SA5 physics decision without importing or
editing `game/core`. It uses Godot 4.7.2 stock at 60 physics ticks per second,
seed `54821`, and a dedicated scene that builds:

- a thirty-body `RigidBody2D` contact pile and a deterministic impulse event;
- a `StaticBody2D` floor and six-step staircase;
- a `PinJoint2D` hanging body released at a fixed tick;
- a `CharacterBody2D` that uses `move_and_slide`, contacts, and pushes a crate;
- a rigid rolling fighter proxy that descends and rotates on the staircase.

Run through the project guard after confirming the shared measurement lock and
`HHStudio.*` scheduled tasks are idle:

```text
python tools/run_guarded.py --project-root . --timeout 30 \
  --evidence docs/physics-spike/run-03-manifest.json \
  --command-id cmd.sa5-n3.physics-spike.3 --seed 54821 --map physics-spike \
  --mode headless --source project.godot \
  --source docs/physics-spike/physics_spike.gd \
  --source docs/physics-spike/physics_spike.tscn -- \
  .local/tooling/godot-4.7.2-stable/Godot_v4.7.2-stable_win64_console.exe \
  --headless --fixed-fps 60 --path . --scene docs/physics-spike/physics_spike.tscn
```

The process prints one `PHYSICS_SPIKE_PASS` JSON row and exits with code zero
when all observations hold. Run twice with fresh command IDs and compare the
`state_hash` fields before treating the trace as deterministic evidence. This
spike is provisional engineering evidence; it is not a Y8 parity claim or an
SA-03 acceptance signature.
