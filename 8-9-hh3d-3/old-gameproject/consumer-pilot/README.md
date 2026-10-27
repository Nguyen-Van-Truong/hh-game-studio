# Consumer pilot S177

This pilot is a separate diagnostic consumer of the accepted GT03/GT04 paths. It never ticks GT06.

- `authoring.py`: bounded authenticated GT03 map mutation, save/readback and durable stop.
- `blender_author.py`: bounded authenticated GT04 export probe, protected artifact selection.
- `run_runtime.py`: fresh Godot consumer snapshot with parse and runtime stages.
- `scripts/pilot_runtime.gd`: live movement, pickup/UI, pause over advancing frames, immutable save generations, recovery from a corrupt newest generation, and deterministic replay.
- `test_evidence.py`: negative tests for exit/PID/tree/stdio, hash and run binding, pause/replay claims, cleanup, paths and log marker.

The launcher always requires fresh run IDs. Raw runs stay under `zdoc/reviews/` and are not copied into this source directory. Use `collect_existing.py` to derive a hash-bound summary from retained raw evidence; it does not launch an engine.

The runtime collector has a read-only recovery path for GUI builds that write `print()` to Godot's own log. It preserves the original failed stdout collection and records the engine log hash separately.
