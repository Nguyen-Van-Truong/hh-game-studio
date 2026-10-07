# GT09 candidate evidence and remaining work — 2026-10-07

This is a read-only candidate package. It does not sign GT09 acceptance and does
not change the checkbox or the `CURRENT_VALID_WP` header.

## Current integration (21:06 Asia/Saigon)

Main `37d6a24f` integrates O2 under O10.5 after merged-tree regression. Public
gameplay-source stays disabled. Two final fixtures now use the private typed
adapter, each with two native source revisions, context reset/reconnect,
durable lookup/retry after a newer revision and reopen, unsupported-version
rejection, and same-length owner-edit conflict without overwriting the edit.
An overlapping request is rejected BUSY; native jobs remain sequential.

- `o2-adapter-gt09-arena-20261007-01`: saved arena, original Blender GLB,
  input/physics/pickup/bot, four effects, replay/checkpoint and frame budget.
- `o2-adapter-gt09-room-20261007-01`: original Blender GLB, 3D movement,
  camera/interaction/pickup/HUD, replay/checkpoint and frame budget.
- Four actual host/container/docker-wait exits are 0; Jobs closed/zero with no
  retained handle; containers removed; owner records released. Original producer
  source hashes remain original. Consumer source stayed unchanged (82 arena and
  79 room driver files; owner runtime domain
  `d9bda850561fcd56132a96965657ddee4d456b803042bc1df6da488d72509e53`).
- Offline verification rebuilt all four observations and checked current/frozen
  source, candidate hashes, actual host/inspect receipts and preserved owner
  edits. Receipt: `studio/.local/reviews/gt09-adapter-20261007-launch/verified-native.json`,
  SHA256 `c249734b5e68dbbd5c2f7a7300421f2ba44ef5546b9958955c46583d1dbae7b5`.

This is private adapter evidence, not full MCP/public source acceptance. Child
gameplay/graph observations remain untrusted; do not claim AUTH02/05 complete.
The old final-source manifest below is historical, not today's final package.

## Parent phase attribution integration

The opt-in executor path now commits to an ephemeral key before candidate
execution, protects the parent memory/FDs, records child stdout/stderr as
untrusted framed payload, and reveals only after actual wait and three pipe
EOFs. A private pre-exec pipe reports OS guard facts and closes before Godot
exec. Publication and reopen independently rederive the transcript and bind the
host/container receipts and exact inspected command. Error text inside framed
child output is still checked; encoding cannot make an error log clean.

- Native `o2-adapter-attributed-20261007-01`: two actual host/container/wait
  exits 0, four successful child phases each, retry/reconnect/reopen no third
  execution, owned containers removed and Jobs closed/zero/unretained.
- Original runtime closure
  `d210d63791c4139d0d021f91d7e0327a6525eeaf77dfe6bf70974ececfa0d938`;
  36 source files and retained raw verified before subsequent guard hardening.
  Receipt `studio/.local/reviews/gt09-attribution-20261007-launch/verified-native.json`,
  SHA256 `7960915a74a2ce6c87050bd99405af0054c4c1b08edc1ac3fdb213fa5a9af23d`.
- Focused integration regression 88 tests exit 0; subsequent command-binding,
  guard-pipe and log-policy tests 30 actual tests passed (two mistaken module
  names were invocation errors, not passing tests); correct owner/probe/adapter
  regression 107 tests exit 0. Native timing limits/resources were unchanged.
- Remaining: hostile native spoof/proc-descriptor checks, trusted dependency
  observation, and enforcement through the public catalog. This run authenticates
  phase waits/pre-exec OS probes only. It does not authenticate child gameplay
  or dependency claims, accept AUTH05, or advertise public source execution.

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

0. Private adapter E2E and reconnect/retry/context-reset/owner-edit proof are now
present above. Still open: independently attributed AUTH02/05 native evidence,
public catalog integration, full fixture lifecycle and measured pinned external
MCP comparison/client capability matrix. BUSY overlap is not parallel native
source-job completion. Next code work addresses trusted phase/OS attribution;
do not rerun existing fixtures solely to refresh hashes.

1. O12 records owner's direct delegation: agent performs each fixture playtest
   for about 15 minutes and records input/trace/video/readback, duration and
   findings as `performed_by=agent`, `delegated_by=owner`. This is still pending;
   short native probes above do not replace it. Never sign a human review.
2. Two independent read-only critics must review this exact package and source
   hash. Each must record an explicit `TICK=yes` before the coordinator can
   accept GT09; current technical evidence alone is not acceptance.
3. GT08B is DEFERRED by owner (O12); no Android claim. It does not block GT10-PC.
4. GT10-PC remains unopened until GT09 acceptance: package/install/upgrade/
   rollback/uninstall/handoff and release soak `10 fresh pairs × 35 batches`
   on the release source. Full Android delivery remains a separately deferred scope.

The evidence supports a reusable Godot + Blender authoring fixture pipeline. It
does not support a claim that the tool creates a complete game or establishes
Y8 parity.
