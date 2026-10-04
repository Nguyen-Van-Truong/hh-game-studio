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
