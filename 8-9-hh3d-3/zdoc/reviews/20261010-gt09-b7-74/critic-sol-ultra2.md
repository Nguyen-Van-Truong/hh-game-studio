# GT-09 final -74 independent critic (gpt-6.1-sol / ultra2)

**TICK=yes**

This is a read-only critic pass over frozen source `573f3ce8`, final run
`gt09-matrix-final-20261010-74`, manifest SHA256
`8d9a2ec6de47bace6390d7320ed3cc256010b4b352c21c66c8600095abe3d5be`, and
full studio closure
`sha256:6b7b5231291a15c2db2672a8ed6a2a6d9f13219ac8d565f86c5d8e9ef2ee6650`.
No source, plan, or evidence file was edited by this critic.

## Gate and provenance checks

- The nested `8-9-hh3d-3/AGENTS.md` routes this scope to the tools plan. The
  plan's GT-01 decision and O9.8 pin are Godot `4.7.2-stable` official; the
  final runner and `studio/toolchain.lock.json` select that exact binary. The
  Vault Fighters root AGENTS/V-A1 pin is explicitly out of scope for this
  tools plan.
- `manifest.sha256` matches the manifest byte-for-byte. `closure_start` and
  `closure_end` equal the declared full closure, and a fresh
  `python -B -m studio.tests.conformance.run_gt09_matrix --verify-only
  studio/.local/reviews/gt09-matrix-final-20261010-74` returned exit `0` with
  `DIAGNOSTIC_OK` and no validator errors. Current source closure matches the
  manifest.
- The Scheduled Task has an independent start receipt at
  `2026-10-10T07:20:41.502167Z`, return receipt
  `actual_process_exit_observed=true`, `returned_exit_code=0`, elapsed
  `2487.203` seconds, and terminal receipt `last_task_result=0` with
  `instances=0`; the task was then deleted. This is a real host exit, not a
  banner or caller-supplied field.
- The final nonce is `sha256(run_id + ":" + closure)[:10] = 1b5f2db09c`.
  Content, registered, catalog-native, publication, K6, K9, K11, K13, and
  K14 outputs use this nonce. Their result mtimes are after the final task
  start (content 14:20:48; registered 14:21:01/12; publications 14:23:27/47;
  K9 14:28:59; K11 14:29:52; K14 14:30:41). Producer runners reject an
  existing output root. K15 selected previously absent IDs `83` and `84`,
  and both metadata roots were created after task start. This establishes
  same-run membership under O13.3a.
- Child hashes differ by declared source domain (content/recipe closure
  `87718898…`, registered closure `c9cb62…`, fixture playtest closures
  `bf5a184f…`/`cf3dfc2b…`). O13.3b permits these child domain closures; they
  are bound to the final run's nonce, output mtimes, result hashes, and final
  matrix closure rather than being required to equal the full studio hash.

## K1–K15 review

- **K1 PASS:** native Blender producer and native registered arena/room
  discovery/profile-isolation probes; output roots and receipts are fresh.
- **K2 PASS:** unit contract checks plus host registered-check for allowlist,
  identity, idempotency, and digest conflict.
- **K3 PASS:** unit checks plus native registered-script replay showing the
  controller behavior change and readback ACK.
- **K4 PASS:** dependency/UID/import unit checks plus native/host catalog
  checks. The readback and rejection semantics revalidate successfully.
- **K5 PASS:** unit checks plus native syntax and type failure probes; each
  preserves last-good state, retry/reopen behavior, and raw reason/exit.
- **K6 PASS:** unit recovery/stop checks plus native publication with durable
  publish, retry, reopen, owner-edit preservation, and actual exit 0.
- **K7 PASS:** unit/host executor checks plus native boundary, spawn, busy,
  and wall hostile cases. Marker/observation/confinement receipts and clean
  owned trees are present.
- **K8 PASS:** final-run native catalog publications for both fixtures, host
  conformance, and unit handoff checks. Both publications carry command IDs,
  readback ACKs, native fixture observation, Blender provenance, and exact
  reference hashes.
- **K9 PASS:** final-run dry-run and native seeded-fault repair for arena and
  room. The result binds both repair command IDs, observed faults, durable
  reopen/checkpoint, and native replay to the two K8 publications.
- **K10 PASS:** unit log/runtime checks and final publication conformance.
  The persisted artifact is `CANDIDATE_PASS`/authority 0 as required before
  acceptance and includes lifecycle dependency, trace/replay, save/reload,
  and perf evidence with no conformance errors.
- **K11 PASS:** transport/session unit checks plus authenticated native adapter
  probe covering reconnect, retry, context reset, owner edit, and parallel
  source jobs; readback and owned-tree receipts are present.
- **K12 PASS:** unit and host hostile-attribution checks. Metadata/README/URL
  inputs remain opaque, out-of-scope dispatch is rejected, and snapshots and
  owner records remain unchanged.
- **K13 PASS as a measured negative:** all required adapter rows are measured;
  external adapters are explicitly `INCOMPATIBLE` with lease/journal/semantic
  command limitations and retained raw warnings. The final client receipt is
  `MEASURED_INCOMPATIBLE`, authority 0, public ACK false, and binds the two
  recipe events and two repair batches. Under O13.1e this is valid measured
  coverage and makes no unsupported compatibility claim.
- **K14 PASS:** native GT-08A regression matrix and focused contract/owner
  checks; 18/18 rows pass on the final closure with exit 0.
- **K15 PASS:** final-closure delegated arena and room playtests both have
  native host exits 0, durations `927.453 s` and `928.984 s` (at least 900 s),
  lifecycle manifests, publication provenance, and evidence validators with
  no errors.

All 15 rows have actual exit 0, `timed_out=false`, `owned_tree_zero=true`,
fresh receipt hashes, and strict verify-only revalidation. The package remains
authority 0/acceptance false until the coordinator records the two independent
critic signatures; this critic supplies the required second-model signature.

TICK=yes
