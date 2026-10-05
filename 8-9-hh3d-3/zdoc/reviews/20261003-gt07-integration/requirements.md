# GT07 integration map — current status (O10)

AUTHORITY=0; GT07=IN_PROGRESS; GT01-GT06=ACCEPTED; GT08-GT10=PLANNED.
This file records the fixed M1-M9 scope and evidence status; it is not an acceptance signature.
All raw diagnostic evidence remains immutable and is stored under `studio/.local/reviews/` for new runs.
Historical entries below are retained for provenance; they do not override the table above.

| Matrix | Status | Existing evidence | Remaining proof |
|---|---|---|---|
| M1 / Q01 | DONE (host) | `gt07-jobs-integration-20261004-03`, 46 tests | Repeat only in final frozen matrix |
| M2 / Q03 | OPEN | static admission/lease guards | native two-writer, expiry, revoke, late worker |
| M3 / Q05 | OPEN (partial) | Godot edit/save/script and receipt-loss run21; Blender queued export `gt07-native-queue-20261005-06`; all six Godot save crash cuts `gt07-native-godot-20261005-06..11`; O2 asset readback `o2-publication-blender-handoff-20261005-03` | queue-level Blender→Godot publish/reload/ACK and cross-app last-good binding |
| M4 / Q06 | OPEN | no final native proof | manual edit conflict and no rollback overwrite |
| M5 / TX05/TX09 | OPEN | component fault helpers | filelock, cross-volume and injected disk/fsync cuts |
| M6 / Q04 | OPEN (partial) | Stop drain and native run16 | full queue/cancel/reconnect matrix in final run |
| M7 / Q07 | OPEN (partial) | 510-record capacity/JOURNAL_FULL | real-clock expiry, compaction/rotation |
| M8 / Q08 | OPEN | host cleanup helpers | PID reuse, timeout ownership, OOM Job evidence |
| M9 / TX13 | OPEN | no native Play mutation proof | Play/capture conflict on pinned fixture |

## Next

N1: scenario runner, mandatory engine-free dry-run, fixed measurement guard,
stop-on-first-failure matrix, and opt-in failpoint admission are implemented;
the 20 focused runner/guard/recovery tests and both Godot/Blender dry-run
contracts pass.
Native M1–M9 execution remains open and must use fresh IDs after this source
freeze.  A dry-run validates wiring and contract bounds only; it cannot prove
runtime IPC, process cleanup, or engine behavior.
N2: Godot save cuts `gt07-native-godot-20261005-06` through `-11` reached
PREPARED, VALIDATED, ACTIVATING, COMMITTED, RELOAD and ACK in fresh runs.
Each intentional child exit 1 was followed by recovery exit 0, clean owned Job
tree, and a retained last-good state; these are diagnostic crash-cut proofs,
not acceptance. The older RELOAD failures in runs 25 and 02 remain immutable.
The cross-application Blender artifact handoff and queue-level last-good proof
are still open.
N2-N5: the Blender producer PREPARED cut is recorded above; execute the
remaining VALIDATED/ACTIVATING/COMMITTED/ACK producer cuts, then the separate
queue-level Godot reload/ACK binding, followed by M2/M4, M5/M7, M6/M8/M9 with
fresh IDs and preserved raw. `RELOAD` is a Godot consumer phase and is rejected
for the Blender producer route.
N6: freeze closure once, run the full matrix plus focused regressions, map artifacts, then send the same hash to two independent critics.

## Checkpoint, 05-10-2026 — queued Blender publication slice

`gt07-native-queue-20261005-06` passed its mandatory engine-free dry-run and
native `export.publish`: pinned Blender created `scene.glb` and
`checkpoint.blend`, protected manifest/selector readback was byte/hash bound,
queue receipt was COMMITTED, and both Blender plus wrapper exited 0 with Job
closed/zero/unretained. This is a diagnostic M3 producer slice only;
`godot_import_readback=false`, so it does not close Blender→Godot reload/ACK or
GT07. Raw is immutable at `studio/.local/reviews/gt07-native-queue-20261005-06/`;
source closure is `9ddb4aff90783f967ffa6700a84a5784a2ed7716ec36f914484067232283bb77`.

## Checkpoint, 05-10-2026 — Godot PREPARED crash cut

`gt07-native-godot-20261005-06` passed the exact-parameter dry-run, reached the
PREPARED failpoint, and was terminated through its owned Job. The child exit 1
is intentional for this cut; host Job/tree/handle cleanup is clean, recovery
returned `GODOT_RECOVERED_LAST_GOOD`, retained the reservation, preserved the
selection, and verified no redispatch/retry effect. This is diagnostic only;
raw remains immutable under `studio/.local/reviews/gt07-native-godot-20261005-06/`.

## Checkpoint, 05-10-2026 — Godot save crash matrix

Fresh runs `gt07-native-godot-20261005-07` through `-11` covered VALIDATED,
ACTIVATING, COMMITTED, RELOAD and ACK. Each passed the matching engine-free
dry-run, recorded the intentional owned child cut (`exit=1`), then recovered
with host exit 0, closed/zero/unretained Job state, and all recovery checks
true. Raw remains immutable in each matching `.local/reviews/` directory;
AUTHORITY remains 0. This closes only the Godot save-phase diagnostic matrix,
not Blender→Godot import/readback or GT07 acceptance.

## Checkpoint, 05-10-2026 — Blender artifact read by Godot fixture

`o2-publication-blender-handoff-20261005-03` is an O2 diagnostic pass. It froze the exact `scene.glb` and producer manifest from `gt07-native-queue-20261005-06`, rechecked the producer hash immediately before dispatch, and loaded that byte through the gameplay-source Godot fixture. The container/host/child exits and cleanup were verified, publication retry after readback and reopen was byte-equal, and the observed GLB hash is `1bb48eb159925ec13f4df7337445a691aac98184580553d81f934d2c674bc87b`. This proves the asset handoff/import readback slice only; it does not prove the GT07 queue coordinator's cross-app reload/ACK or grant acceptance. Raw is under `studio/.local/reviews/o2-publication-blender-handoff-20261005-03/`, AUTHORITY=0. The native fixture completed with outer/host/container exit 0 and clean Job closeout; source closure is `c91bc0d770e9730cb10a3bc9fd8e80729f6db9d3485b024664706658993be51c`.

## Checkpoint, 05-10-2026 — Blender sprite sheet read by Godot fixture

`o2-sprite-atlas-20261005-01` is an authority-zero asset diagnostic. Pinned Blender produced and reopened a 4-cell 128x128 sprite sheet with actual native/reopen exits 0 and clean owned Jobs; pinned Godot then imported, authored, and reloaded it in three fresh processes, all actual exits 0 with clean Jobs. The sheet hash is `42d342dd4e1f6e6ef9ff31d1370703b83ae76e60ad3756156297478c1e546cf8` and the Godot frame artifact hash is `989c4fbbab77a00b40f03bc062890a6d0ea7e188346f43034d18ae4bb0314ef2`. Raw is under `studio/.local/reviews/o2-sprite-atlas-20261005-01/`; this closes only the Blender sprite → Godot fixture import/reload slice. Queue-level cross-app publish/reload/ACK and GT07 acceptance remain open.

## Checkpoint, 05-10-2026 — Blender PREPARED crash recovery cut

`gt07-native-queue-20261005-07` passed a fresh engine-free dry-run and a
native `export.publish` cut at `PREPARED`. The owned Job terminated the child
intentionally after the publisher recorded its INTENT state; host evidence
shows exit 1 for the cut, closed/zero/unretained Job state and a verified
process tree. A fresh read-only recovery process reopened the producer and
queue without starting Blender or replaying the command: publication bytes,
queue record/head and the held reservation were unchanged, uncommitted
selection was rejected, repeated lookup had no effect, and no queue ACK was
created. This is a producer-side crash diagnostic only; cross-application
Godot reload/ACK and GT07 acceptance remain open. Raw is immutable under
`studio/.local/reviews/gt07-native-queue-20261005-07/`; source closure is
`cf15cb641ef1e54f6a389bd3ded440c10e43ef9924244c97a7d57310237e5914`.

The companion producer cuts `gt07-native-queue-20261005-08` through `-11`
covered `VALIDATED`, `ACTIVATING`, `COMMITTED` and `ACK` with fresh dry-runs
and the same owned-cut/recovery contract. Each intentionally cut child exited
1, recovery exited 0 with a clean Job/tree, and all recovery checks passed;
the source closure for `-08..-11` is
`59f94968f321de72908c508123b2dd492545e14348b1c7a6faeb51ac211b6155`.
`COMMITTED` and `ACK` here mean the producer's terminal publication boundary;
the queue receipt remains unacknowledged until the coordinator collects it.
These five cuts still do not prove queue-level Godot reload/ACK or close M3.
## Historical log (preserved verbatim)
# GT07 integration map — opened after GT06 acceptance

AUTHORITY=0 until full GT07 evidence and two independent critics.
Dependency: GT05 accepted; GT06 accepted by
`../20261003-gt06-owner-critics/coordinator-acceptance.md` at `9a6c8598`.
This map locks the initial integration fixture and does not replace plan TQ/TX.

| ID | Requirement | Existing reusable boundary | New evidence required |
|---|---|---|---|
| Q01 | Durable bounded admission and fair project/session selection | `dispatch_policy`, native private event log/custody | enqueue/reserve/cursor atomicity, admission quotas, dependency validation, same-ID conflict, concurrent callers |
| Q02 | No duplicate effect after restart or uncertain storage | event high-water witness, registered selector lookup | crash after reserve/before phase/after effect; retained reservation, explicit lookup before release |
| Q03 | Owner/session/lease/fence at every effect | `SelectorFixtureBroker.advance`, Godot FIFO, Blender writer journal | actual coordinator dispatch, revoked/expired/late worker, two writers on .tscn/.blend |
| Q04 | Stop priority, no automatic reconnect/resume, bounded draining | separate control routes, native owned Job runners | Stop while full, queued cancellation, uncertain/active slots retained, actual owned cleanup |
| Q05 | Complete publish/reload/ACK recovery and last-good preservation | fixture selector, protected CAS, Godot/Blender publication, GT05 snapshot owner | all PREPARED/VALIDATED/ACTIVATING/COMMITTED/reload/ACK crash cuts through new integration |
| Q06 | Manual edit/revision conflict and storage failures | native protected file boundary and component fault harnesses | preserve newer edit under rollback, actual filelock/crossvolume/diskfull plus explicit injected-fault limits |
| Q07 | Journal full has actionable reply, capacity and expiry proof | bounded journal terminal reservation/compaction | real capacity measurement, real clock expiry/compaction, no early ACK or retry amplification |
| Q08 | Correct process evidence and source closure | accepted GT06 role/Job collection; new Scheduler terminal receipt persistence | native launch/termination/restart receipts with PID/start/root binding; complete source-specific manifests |
| Q09 | Complete requirement map, regressions, independent reviews | accepted GT05/GT06 snapshots only for unchanged domains | remaining TQ07/TX05/06/09/11/13/14/18 evidence and two same-hash critics |

Initial internal scheduling limits: 64 pending,
4 active, 2 active/project, 1 active/session, at most 8 resources and 16 dependencies
per job, 1024 terminal receipt projection entries. Review after initial native
integration added admission caps before the next run: 32 pending/project and
8 pending/session. Active quotas alone did not protect admission from a flood.
These are candidate limits,
not installed public limits. Durable event storage remains bounded by the existing
512-record/8-MiB profile; admission must reserve terminal/Stop headroom and reject
exhaustion explicitly. It must not silently evict IDs or pretend to compact this
new stream. Journal capacity/retention work is separate Q07.

Initial adapter fixture: registered inert file-release selector owners for two
projects and their locally authenticated sessions. No arbitrary callback, wire
path, raw filesystem handle or generated source execution is introduced. A
reservation is scheduling state, not a lease or COMMITTED public ACK. Original
adapter auth/fencing/revision/readback remains the effect authority. On restart,
reservations remain held and session execution is not reconstructed.

This file-only integration proves neither Blender/Godot mutation nor actual
process-fault, multi-application or game coverage. Those remain explicit Q03–Q06
and Q08 gaps. Existing component tests are reused when unchanged, not rerun just
to inflate a total. Tests exercise failures at real boundaries where practical;
fault injection must be labeled and cannot stand in for native proofs.

## Verified checkpoint, 04-10-2026

- `gt07-jobs-integration-20261004-03`: 46 tests, actual PID 45616 exit 0;
  scoped source hashes unchanged before/after. Raw and host receipt under
  `studio/.local/reviews/gt07-jobs-integration-20261004-03/`.
- New-command admission now waits until the previous owner phase and its durable
  queue receipt have both completed. The race reproducer failed before the lock
  boundary repair and passes after it. Control cancellation remains separate.
- An injected failure after owner COMMITTED but before queue receipt preserves
  the reservation. After closing/reopening the actual native owners, explicit
  exact-command lookup/readback retires it without republishing or reissuing a
  session. This covers one Q02/Q05 cut; it is not the complete crash matrix.
- `gt07-jobs-integration-20261004-01` logs show 45 tests OK, but its PowerShell
  wrapper failed while assigning the reserved `$PID` variable after launch.
  The child finished, but no retained host exit was collected. This run has no
  acceptance authority; raw logs are preserved. Run 02 repaired the capture
  wrapper and is the source of the exit claim above.
- `gt07-journal-action-20261003-01`: two authenticated HTTP tests, actual PID
  20136 exit 0. Certain journal-capacity refusals include a recovery next action;
  uncertain writes remain UNKNOWN/lookup.reconcile. Reduced test limits do not
  prove default journal capacity or elapsed-time compaction.
- `gt07-capacity-20261004-01`: one focused test, actual PID 6136 exit 0 after
  148.941 seconds. The default native stream reached 510 records and 233,319
  bytes, rejected the next admission with `BROKER_JOURNAL_FULL`, then reopened
  with all 169 terminal receipts and Stop headroom intact. This is real record
  capacity/retention evidence; rotation, compaction, disk-full and clock
  expiry remain open. Source hashes were unchanged before/after.

All entries remain AUTHORITY=0. Hash scope in diagnostic receipts is an explicit
file list, not a claim of a complete runtime dependency closure. The final
package still needs the complete closure, Q03-Q08 native evidence and two
independent critics on the same frozen candidate.

## Verified checkpoint, 04-10-2026 — native Blender queue slice

- `gt07-native-queue-20261004-10` is a preserved negative diagnostic. Its
  frozen child could not load `godot-addon/cli_job.py` because the first probe
  source list omitted that runtime dependency. The wrapper exit and Job cleanup
  were captured, and no native mutation was claimed.
- `gt07-native-queue-20261004-11` is a preserved negative diagnostic after the
  dependency repair. Blender created the box and returned a committed owner
  receipt, but the probe verifier incorrectly expected a `size` field that is
  not part of the native observation schema. The child and Blender both exited
  cleanly; this remains FAIL because the verifier did not prove its postcondition.
- `gt07-native-queue-20261004-12` is the first successful bounded native queue
  slice after those two reproducer-driven repairs. A frozen source snapshot
  (`source_closure_sha256=adbf8a98820eff44406790aeced8eb0b1a0790d9f5604255e5873a50f6f0401c`)
  launched one pinned Blender owner through `NativeOwnerDispatcher`. The actual
  wrapper and child exits are both `0`; the native Blender cleanup exit is `0`,
  `tree_verified=true`, `job.zero_observed=true`, `handle_retained=false`, and
  the durable queue receipt is `COMMITTED`. Readback proves the object id,
  eight vertices, and extents `[1,2,3]`. The report is `authority=0`,
  `formal_acceptance=false`, and `public_ack=false`.
- The source freeze now includes the dynamically loaded `godot-addon/cli_job.py`.
  The probe uses the existing Job runner and records source stability before
  and after the child. It does not prove Godot integration, publication/reload,
  crash cuts, two-writer fencing, disk-full/expiry, or the full Q03–Q08 matrix.

The negative raw runs are retained and must not be relabeled as PASS. The
remaining work stays explicit: add native Godot typed-owner binding, native
publication/reload and conflict/fault cuts, and then prepare the complete
source/review manifest before two independent critics on one frozen hash.

## Verified checkpoint, 04-10-2026 — native Godot publication owner

- `gt07-godot-publication-20261004-01` is retained as a negative closeout
  diagnostic. The frozen Godot child completed authenticated discovery,
  editor mutation, scene save, actual reload, duplicate lookup, and Stop, but
  the helper closed the owner before its asynchronous Stop persistence drained.
  It therefore ended with child exit `1` and `GODOT_STOP_DRAIN_REQUIRED`; no
  PASS is inferred from its partial rows.
- `gt07-godot-publication-20261004-02` reran the same bounded publication
  fixture with a reproducer-driven closeout repair: it waits for the existing
  owner Stop thread to report `DURABLE` before closing. The frozen source
  closure is `710fde2bf9d413c17d1207a152a6f36729c05b53c382817fb4b7156e31901c9e`.
  The wrapper and child both exit `0`, the owned Godot editor exit is `0`,
  its Job is closed with `zero_observed=true`, `active_count=0`,
  `handle_retained=false`, and the source and snapshot remain unchanged.
  The progress rows prove authenticated scene save, actual editor reload,
  duplicate no-effect, lookup, durable Stop, and read-only journal reopen.
  This remains `candidate_only=true`, `gt03_acceptance=false`, and
  `AUTHORITY=0`.

This slice is native Godot publication evidence, but it is not yet a
coordinator queue binding. Q03 still needs the exact typed Godot owner binding
in `native_dispatch.py`, and Q04–Q06 still need queue-level Stop, crash,
revision-conflict, and storage-fault cuts. Do not combine this run with the
Blender queue receipt or claim GT07 acceptance.

## Verified checkpoint, 04-10-2026 — native Godot queue edit

- `gt07-native-godot-20261004-16` completed one authenticated node update via
  the exact `GodotPublicationOwner` and `NativeOwnerDispatcher`. Source closure:
  `03c45847e9c1bee22f1e3648d6bc1c1bd45ce66f01ce7f7401e8ba9d78aacd4f`.
  Raw: `studio/.local/reviews/gt07-native-godot-20261004-16/`.
  Wrapper PID 25860 and child PID 9372 exited 0; editor PID 22220 exited 0.
  The queue recorded COMMITTED after exact journal-response/receipt verification
  and fresh native readback. Root position is `[3,4,5]`. Editor Job was closed,
  active_count 0, zero_observed true, handle_retained false; both source and
  frozen snapshot were unchanged. Stop persistence and journal Stop readback
  are DURABLE/true. This remains AUTHORITY=0 and formal_acceptance=false.
- The edit ACK explicitly says `effect_scope=editor_session`, files_saved=false
  and live_state_durable=false. This run does not prove queued scene save,
  script replacement, crash recovery, game completion, or GT07 acceptance.
- Queue collection now checks exact receipt hashes, scene/project revisions,
  selection/file manifest, editor identity and history. Publication readback
  resolves the retained READBACK event through its receipt hash; script
  replacement validates the old/new editor identities rather than requiring
  the original editor to remain alive. Native coverage for these publication
  branches is still pending.
- Stop latches immediately; `drain_stop()` is a separate bounded supervisor
  step. Pending Stop prevents detach. UNKNOWN persistence cannot satisfy the
  drain, even if the worker thread has ended; current journal readback is also
  required. Four inert lifecycle regressions passed. Eight inert readback
  tests cover identity/revision/selection/saved-state mismatches and script
  successor checks. These are not native engine evidence.
- The combined 101-test invocation exited 1 because four contract-vector tests
  lacked `studio/tests/godot` on PYTHONPATH. It is not a suite PASS. With that
  existing test path supplied, all 25 contract tests passed (exit 0); the 12
  focused readback/Stop tests also passed (exit 0). Journal V4 adoption/reopen
  checks, Blender dispatcher and Godot owner/transport checks produced no
  failures in the combined invocation.

Negative runs `gt07-native-godot-20261004-01` through `-15` remain unchanged
under `zdoc/reviews/`. They exposed missing frozen dependencies, a missing Linux
validator path, bypassing the public lease registration, and a relative editor
binary resolved under the snapshot. Runs 09 and 11–15 rejected an oversized
edit deadline. The earlier explanation that startup exhausted the lease was
incorrect: run14/15 timestamps showed almost 90 seconds remaining. The actual
contract permits at most 30 seconds for edits and 90 seconds only for save/
script replacement. Run10's attempted 300-second lease was also invalid.
The final harness uses the public FIFO lease route and a 29-second edit
deadline; no production timeout or gate was relaxed. Immediate close after
asynchronous Stop caused the separate STOP_DRAIN_REQUIRED failures.

Lesson: check both bounds of a deadline error and reproduce admission purely
before another native run. Share catalog deadline validation at queue admission;
never repair a harness failure by bypassing the public lease table or extending
timeouts. Preserve actual errors and distinguish queue Stop from owner durability.

Next gaps: lookup-only recovery registration after a script successor replaces
the bound editor; native queued save/script/reload; Q03/Q04/Q08 revoked/expired/
two-writer/crash/Stop matrix; Q05–Q07 storage/conflict/retention cuts. GT07 remains
IN_PROGRESS and still requires the complete frozen package and two critics.

## Verification note, 04-10-2026 — recovery guard (static)

- `studio/host/jobs/native_dispatch.py` now exposes `register_recovery()` as a
  lookup-only reattachment path. It accepts only an existing durable
  `RESERVED`/`UNKNOWN` row whose resource, project/session and command hash match
  the binding. Recovery bindings are rejected by both `enqueue()` and
  `advance()`; `_binding_for()` still requires the exact persisted fence before
  collection. No new native effect or lease is reconstructed.
- `studio/tests/jobs/test_native_godot_recovery.py` covers three focused
  regressions: exact reservation reattachment with execution blocked, rejection
  of queued/command-mismatched rows, and fence mismatch rejection. Actual run:
three tests, exit 0. This is static/inert evidence only; it does not claim a
native script-successor or queued publication result.
- A test fixture exposed and repaired an incorrect lookup of the command hash
  from `PendingJob`; the durable hash belongs to `JobRecord.command_sha256`.
  Existing native queue semantics and timeout gates are unchanged.

## Native runner checkpoint, 04-10-2026 — O10 admission and live slices

- `gt07-native-godot-20261004-22` ran the new `godot-edit` scenario after an
  engine-free dry-run. The pinned GUI hash, source closure, fixed measurement
  guard and public lease route matched. Native scene update read back
  position `[3,4,5]`; queue state was `COMMITTED`; editor and wrapper exits
  were 0; Job was closed/zero/unretained; durable Stop was read back. Raw is
  under `studio/.local/reviews/gt07-native-godot-20261004-22/`.
- `gt07-native-godot-20261004-23` ran the `godot-recovery` scenario with a
  receipt-loss injection after the native script effect. The child exited 0.
  The reopened reservation retained the exact fence; lookup returned the
  existing `COMMITTED` effect; reconcile appended exactly one `OWNER_RESULT`
  queue event; editor journal head and native scene state were unchanged;
  submit count stayed one; actual editor/Job/wrapper cleanup was clean. Raw is
  under `studio/.local/reviews/gt07-native-godot-20261004-23/`.
- `gt07-native-queue-20261004-13` ran the new Blender scenario after the same
  dry-run boundary. One pinned Blender process created the box and read back
  extents `[1,2,3]`; queue receipt was `COMMITTED`; actual child/wrapper exits
  were 0; Job was closed/zero/unretained; source snapshot was unchanged. Raw
  is under `studio/.local/reviews/gt07-native-queue-20261004-13/`.
- The runner now rejects an armed failpoint, duplicate measure-window holder,
  reused output ID, stale source/binary after dry-run, and matrix continuation
  after a nonzero scenario. The 20 focused runner/guard/recovery tests exit 0.
  These are diagnostic slices
  (`AUTHORITY=0`); M2–M9 and the final matrix,
  complete closure and two independent critics remain open.

## Native lookup recovery checkpoint, 04-10-2026

- `gt07-native-godot-20261004-20` is retained as a negative diagnostic. The
  deliberate lost-collection probe completed the native script effect but the
  verifier attempted to serialize the broker `JobRecord` as a wire response;
  child exit was 1 and no PASS is inferred. The raw and manifest remain
  immutable.
- `gt07-native-godot-20261004-21` is the repaired fresh run with closure
  `4ec43bcb4724bd0ca5988fd41116d7096ca2f9fbd796244f6063ef1ef1e4f9d1`.
  It uses `script_text.replace`, intentionally loses queue receipt after the
  native effect, closes/reopens the durable queue, attaches the old binding via
  `register_recovery()` and reconciles by exact authenticated lookup. The
  recovery proof records `native_effect_committed`, `queue_receipt_lost`,
  `reopened_reservation`, `lookup_only_reconcile`, and `COMMITTED`; the effect
  is not replayed. Wrapper/child/editor exits are 0, Job is closed/zero/
  unretained, source and snapshot are unchanged, and Stop persistence/readback
  is durable. Archive and per-file hashes are in the matching manifest.
- This is a native Q02/Q03 recovery slice (`AUTHORITY=0`), not GT07 acceptance.
  It does not close revoked/expired late workers, two-writer fencing, crash
  cuts at every phase, storage faults, or the remaining Q04–Q08 matrix.

## Native queue checkpoint, 04-10-2026 — publication branches

- `gt07-native-godot-20261004-18` exercised one queued `scene.save` on a fresh
  frozen source (`4fda899b0159548c30f7e60f3740414acfefe0bfcd0dbc2983271cd64a19e751`).
  The dirty scene was admitted through the public write lease and queue, then
  the durable response was checked against publication adoption/readback. The
  queue row is `COMMITTED`, response code is `GODOT_MANAGED_SCENE_SAVED`, and
  generation/history boundary, editor exit 0, Job zero/closed/unretained,
  wrapper/child exits 0, and durable Stop all hold. Archive and file hashes are
  in `gt07-native-godot-20261004-18-manifest.json`; raw stays under `.local`.
- `gt07-native-godot-20261004-19` repeated the same bounded fixture for queued
  `script_text.replace` with a path target. It returned
  `GODOT_MANAGED_SCRIPT_REPLACED`; the new editor identity, script readback,
  adoption hash, queue COMMITTED state, actual exits and durable Stop all hold
  under the same frozen closure. Its archive is recorded in the matching
  `...-19-manifest.json`.
- Both are native diagnostic slices (`AUTHORITY=0`, `formal_acceptance=false`).
  They close the two publication branches of this queue adapter but do not
  close Q03/Q04/Q05/Q08: revoked/expired late workers, two writers, crash cuts,
  storage faults, and the final same-hash independent critics remain required.

## Raw migration checkpoint, 04-10-2026

- The 22 historical `gt07-*` raw directories previously left under
  `zdoc/reviews/` were moved unchanged into `studio/.local/reviews/`; the
  ignored `migration-20261004.json` records each run's file count, byte count,
  and hash concatenation. The migration covers 6,304 files and 116,304,991 bytes
  as recorded by that manifest. No raw evidence was deleted or rewritten.
- The two untracked native manifests for runs 20 and 21 were moved into their
  matching `.local/reviews/<run>/manifest.json` directories. Their content and
  SHA-256 values were preserved. `zdoc/reviews/` now contains only tracked
  requirement/history documents for these runs.
