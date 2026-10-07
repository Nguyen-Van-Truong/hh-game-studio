# GT09 candidate critic package — 2026-10-07

This is a read-only candidate package. It does not sign GT09 acceptance and does
not change the checkbox or the `CURRENT_VALID_WP` header.

## Frozen evidence

- coordinator source commit: `929f6b568d1b28d553f998388abcf223b340e4c7`
- fixture source closure: `c91bc0d770e9730cb10a3bc9fd8e80729f6db9d3485b024664706658993be51c`
- offline conformance report:
  `studio/.local/reviews/gt09-conformance-20261007-04/report.json`
- native 2D fixture:
  `studio/.local/reviews/o2-publication-gt09-arena-20261007-09/`
- native 3D fixture:
  `studio/.local/reviews/o2-publication-gt09-room-native-20261007-12/`
- Blender producer:
  `studio/.local/reviews/gt07-native-queue-20261007-25/`
- Blender handoff manifest SHA256:
  `53dcdbbd1f1d2d107dad8ddeaddb80ef658503036c896780e75f4628eac0e29a`
- Blender `scene.glb` SHA256:
  `1bb48eb159925ec13f4df7337445a691aac98184580553d81f934d2c674bc87b`

Both native fixture runs report `DIAGNOSTIC_PASS`, `native_run_count=1`, clean
owned-process lifecycle, durable retry/reopen equality, and
`blender_handoff_verified=true`. The conformance report is `CANDIDATE_PASS` and
`acceptance=false` by design.

## Requirements still open

1. Owner must play each fixture for about 15 minutes and record OK/not-OK plus
   notes. Synthetic input and agent observations do not satisfy this row.
2. Two independent read-only critics must review this exact package and source
   hash. Each must record an explicit `TICK=yes` before the coordinator can
   accept GT09.
3. GT08B still requires a physical Android device and USB-debugging evidence.
4. GT10 remains unopened: package/install/upgrade/rollback/uninstall/handoff and
   release soak `10 fresh pairs × 35 batches` on the release source.

The evidence supports a reusable Godot + Blender authoring fixture pipeline. It
does not support a claim that the tool creates a complete game or establishes
Y8 parity.
