# GT09 candidate critic package — 2026-10-07

This is a read-only candidate package. It does not sign GT09 acceptance and does
not change the checkbox or the `CURRENT_VALID_WP` header.

## Frozen evidence

- coordinator source commit: `5afb6386f084ad4527fe508a924c677b043bb3b6`
- fixture source closure: `c91bc0d770e9730cb10a3bc9fd8e80729f6db9d3485b024664706658993be51c`
- offline conformance report: `studio/.local/reviews/gt09-conformance-20261007-07/report.json`
- conformance report SHA256: `fc49943c16be35597d055fefac8fb1b304c8cbb0ac8f395a3f80608a9a955d91`
- final source/review/raw manifest: `20261007-gt09-final-source-review-raw-manifest.json`
- native 2D fixture: `studio/.local/reviews/o2-publication-gt09-arena-effects-20261007-18/`
- native 3D fixture: `studio/.local/reviews/o2-publication-gt09-room-effects-20261007-19/`
- saved arena builder: `studio/.local/reviews/o2-saved-arena-gt09-effects-20261007-01/`
- Blender producer: `studio/.local/reviews/gt07-native-queue-20261007-25/`
- Blender handoff manifest SHA256: `53dcdbbd1f1d2d107dad8ddeaddb80ef658503036c896780e75f4628eac0e29a`
- Blender `scene.glb` SHA256: `1bb48eb159925ec13f4df7337445a691aac98184580553d81f934d2c674bc87b`

Both new native fixture runs report `DIAGNOSTIC_PASS`, actual child exit 0,
`native_run_count=1`, clean owned-process lifecycle, durable retry/reopen
equality, and `blender_handoff_verified=true`. The 2D run exercises the
combined saved Godot arena plus Blender handoff, reads the avatar and sprite
assets, and observes four bounded effect kinds: muzzle flash, hit ray, dust,
and explosion. It records 30 peak particles under a 64-particle limit,
replay equality, checkpoint save/readback, and a bounded 150-sample frame
budget. The room records the corresponding 60-sample result. The conformance
report is `CANDIDATE_PASS` and `acceptance=false` by design.

Earlier failed attempts remain in their original raw directories and are not
relabeled as passes. Existing critic records are historical; the next two
independent read-only reviews must inspect the exact final package/source hash.
The raw arena dependency observation is retained as candidate evidence
(`dependency_closure_verified=false`), and accepted startup stderr noise is
not a clean formal log. Runtime native results remain diagnostic `AUTHORITY=0`.

## Requirements still open

0. AUTH-05 adapter E2E is still open on the O2 branch. The measured pinned MCP
compatibility spike, client/model/host/version capability matrix, unsupported
client-version rejection, reconnect/retry/context-reset no-duplicate proof,
and owner-edit plus two parallel source-job evidence are not present.

1. Owner must play each fixture for about 15 minutes and record OK/not-OK plus
   notes. Synthetic input and agent observations do not satisfy this row.
2. Two independent read-only critics must review this exact package and source
   hash. Each must record an explicit `TICK=yes` before the coordinator can
   accept GT09; current technical evidence alone is not acceptance.
3. GT08B still requires a physical Android device and USB-debugging evidence.
4. GT10 remains unopened: package/install/upgrade/rollback/uninstall/handoff and
   release soak `10 fresh pairs × 35 batches` on the release source.

The evidence supports a reusable Godot + Blender authoring fixture pipeline. It
does not support a claim that the tool creates a complete game or establishes
Y8 parity.
