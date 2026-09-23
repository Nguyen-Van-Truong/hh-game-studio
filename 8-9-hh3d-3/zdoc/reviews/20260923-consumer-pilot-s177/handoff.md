# S177 consumer pilot handoff

- `AUTHORITY=0`; `GT06_ACCEPTANCE=false`; no checkbox tick.
- GT03 selected run `consumer-pilot-s177-gt03-04` authenticated three scene-node creates, save/readback, and durable stop. The editor actual exit was 0 and the retained job was zero/closed. The author parent exit receipt is absent and stays UNKNOWN.
- GT04 selected run `consumer-pilot-s177-gt04-01` authenticated the Blender writer/export path. Native and export actual exits were 0; cleanup and protected asset hashes were verified. The outer collector failed after native success and is preserved as a gap.
- Runtime `consumer-pilot-s177-runtime-01` ran the pinned Godot GUI in a fresh snapshot. Parse and runtime exits were 0; all 11 runtime checks passed. The original stdout-marker collector failure remains in `result.json`; `runtime-validation-01.json` is read-only derived validation from the GUI log.
- `test_evidence.py` passes 9/9 negative contract tests.
- This pilot demonstrates one authored primitive map and one Blender GLB consumer path. It does not demonstrate general 2D/physics/audio/animation/Android capability, full gameplay, or GT06 10x35.

Raw runs remain under the local review archive and are referenced by hashes in `S177-SUMMARY.json`.
