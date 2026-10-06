# GT07 integration map — current status (O10)

AUTHORITY=0; GT07=IN_PROGRESS; GT01-GT06=ACCEPTED; GT08-GT10=PLANNED.
This file records the fixed M1-M9 scope and evidence status; it is not an acceptance signature. The manifest evidence map is authoritative for path/hash binding.
All raw diagnostic evidence remains immutable and is stored under `studio/.local/reviews/` for new runs.
Historical entries below are retained for provenance; they do not override the table above.

| Matrix | Status | Existing evidence | Remaining proof |
|---|---|---|---|
| M1 / Q01 | DONE (host) | gt07-jobs-integration-20261004-03, 46 tests; verification hash a3a9c429a0130846357a8f129ce4d2c690954d720785bd5b08172987259dc212, actual exit 0, source unchanged | Repeat only in final frozen matrix |
| M2 / Q03 | DIAGNOSTIC COVERED (Blender + Godot) | Blender `gt07-native-queue-20261006-07` and Godot `gt07-native-godot-20261006-17`: matching dry-runs, real-clock expiry, native effect before deadline with reply after expiry, overlapping writer refusal, revoke after effect preserves private receipt and blocks lookup/replay; actual child/editor/wrapper exits 0, Jobs/tree clean, source/snapshot unchanged. Earlier FIFO-only runs without matching dry-run stay excluded | final frozen matrix and two same-hash critics; do not mark DONE from diagnostics |
| M3 / Q05 | DIAGNOSTIC COVERED (current producer + consumer) | Current-source Blender producer cuts gt07-native-queue-20261006-19 (PREPARED), -11 (VALIDATED), -12 (ACTIVATING), -13 (COMMITTED), -14 (ACK), closure 17f381a0b2078096d9631556620a4cfd0c5552ad0d49b89865f0234078b7a0e2; current-source consumer cuts gt07-cross-app-20261006-02 (RELOAD: HELD_LAST_GOOD) and -03 (ACK: COMMITTED_LOOKUP_ONLY), closure c91bc0d770e9730cb10a3bc9fd8e80729f6db9d3485b024664706658993be51c; actual failpoint child exit 1, recovery exit 0, Job/tree clean, source/snapshot unchanged | final frozen matrix and two same-hash critics; failpoint receipts are diagnostics, not product acceptance |
| M4 / Q06 | DIAGNOSTIC COVERED (Godot + Blender) | Godot `gt07-native-godot-20261005-26,42`; Blender `gt07-native-queue-20261005-47` and current-source `gt07-native-queue-20261006-08`: queued stale transform returns UNKNOWN/lookup.reconcile, manual `.blend` state/hash retained, actual child/wrapper/tool exits 0 and owned Jobs clean, source/snapshot unchanged | final frozen matrix and two same-hash critics; previous failed diagnostics remain immutable |
| M5 / TX05/TX09 | DIAGNOSTIC COVERED (current source) | current host gt07-m5-storage-20261006-01/report.json, source closure 8434fd8dc204a12590fd6d789be3ccbed1465585efee77cd594101acd2a86474, source file 9547c4efc2474414ee184f892af5e58ece991957699cbc7dc2b3dafc952b2600, wrapper exit 0 and explicit terminal zero child/Job/handle; real lock/cross-volume refusal and explicitly UNKNOWN injected fsync/diskfull; native gt07-native-godot-20261006-05 remains a separate save-lock diagnostic | final frozen repeat and requirement-map binding; no COMMITTED claim for UNKNOWN rows |
| M6 / Q04 | DIAGNOSTIC COVERED (host) | gt07-m6-host-20261006-01/report.json hash 7ff2782dbed075364510015c5ac25081fe8cd43d933a774659a7493587ea62f2, 10 tests, actual process exit 0, source closure 32c64698b4cf84f10e60768ff22304823b7417023431c8d92f3b7188e95e0ddc, no child/Job/handle residue; covers queue-full cancellation, bounded drain, reopen/no-resume, token rotation and durable Stop readback | final frozen matrix and two same-hash critics |
| M7 / Q07 | DIAGNOSTIC COVERED (current source) | fresh `gt07-m7-rotation-20261006-01` ran the real-clock expiry and PREPARED/ACTIVE_POINTER/COMMITTED QueueOwner cuts: 33 tests, actual exit 0, capacity 169 jobs/510 records, pending/archive recovery preserved, no engine process | final frozen matrix and two same-hash critics |
| M8 / Q08 | DIAGNOSTIC COVERED (current source) | matching dry-run/native `gt07-m8-process-20261006-11`: held identity, forged-start refusal, owned-tree timeout with live sentinel, and 64 MiB Job memory denial; all three verified, actual workers exited, Jobs closed/zero/unretained; source closure `ab498ef2…c9e8` | final frozen matrix and two same-hash critics |
| M9 / TX13 | DIAGNOSTIC COVERED (current source) | one-use refresh03 verified the exact three-file delta (`godot-addon/editor_owner.py`, `host/blender/export_job.py`, `host/blender/publication_owner.py`), source=233/execution=235; matching dry-run `gt06-gt07-m9-playmutation-20261006-01` and native `-02` exit 0 on runtime closure `630124fd…20f10`, with 18/18 checks, Play-time generated-state mutation, stale capture rejection/UNKNOWN/no-replay, natural child exit and clean Job/tree/handles | repeat in the final frozen matrix; two same-hash critics |

## Next

M9's current-source adversary is now covered after the one-use binding refresh.
The N6 candidate package is indexed at
`zdoc/reviews/20261003-gt07-integration/CRITIC_PACKAGE.md`; its manifest is
`studio/.local/reviews/gt07-final-matrix-20261006/manifest.json` with SHA
`5f34c0a616c27070779344e65800f9d353666dfab81ae46e1789a7be303bce0d`.
The remaining gate is two independent read-only critics on that exact hash. The manifest now binds M1/M3/M5/M6 paths and the recorded 104-test regression summary; M3 RELOAD/ACK now have current-source receipts and are mapped in the manifest evidence map; historical contextual cuts remain retained separately.
`AUTHORITY=0`; this package is not self-acceptance.

## Checkpoint, 06-10-2026 — M9 current-source binding and Play mutation

The installed selector/binding generation was stale after three committed
source edits. A new one-use refresh in
`zdoc/reviews/20261006-gt07-binding-refresh/` required the exact old metadata
hashes, exact three-file delta, and source count 233, replaced both metadata
files atomically with rollback, and verified `load_installed` (235 execution
files). No engine ran during the refresh; old/new bytes and postcheck are
retained in the review directory.

After the matching dry-run `gt06-gt07-m9-playmutation-20261006-01`, native
`gt06-gt07-m9-playmutation-20261006-02` exited 0 with 18/18 checks. The owned
generated marker was written while Play was RUNNING; the first capture
committed; the changed capture was rejected as `REPLAY_CAPTURE_CHANGED`,
lookup remained `UNKNOWN` without artifact/replay, and the child exited
naturally with a closed zero-member Job and no retained handle. Runtime source
closure was `630124fd17a2e2306408fbd8f6f22bb4214b056b9b6f03696933ee227c820f10`.
This remains authority-zero diagnostic evidence until the final frozen matrix
and two critics.

## Checkpoint, 06-10-2026 - Blender producer phase coverage

The narrow Blender repair in commit `73008c05` gives `export.prepare` the
remaining portion of the host's existing ten-second ceiling when the ordinary
six-second UI wait is insufficient; other native operations keep their normal
wait and the queue lease/deadline is unchanged. The focused timeout guard and
the existing GT07 failpoint/scenario tests exit 0.

After a matching engine-free dry-run, current-source producer cuts completed
for `gt07-native-queue-20261006-11` (VALIDATED), `-12` (ACTIVATING), `-13`
(COMMITTED), and `-14` (ACK), in addition to the retained PREPARED cut `-09`.
Every wrapper reports `passed=true`, the intentional phase child exit is
captured, the owned Job is closed with zero active members and no retained
handle, and the source closure is
`17f381a0b2078096d9631556620a4cfd0c5552ad0d49b89865f0234078b7a0e2`. These
failpoint runs are diagnostic evidence; they do not grant acceptance or
replace the final frozen M1-M9 matrix and two same-hash critics.

M2 late/revoked writer, M4 Blender conflict, M5 Godot-save lock, and M6 Stop
coverage now have current diagnostic receipts. M3 now has producer phase
coverage and consumer cuts; M7, M8 and M9 now have current-source diagnostic
receipts. They remain authority-zero until one frozen M1–M9 matrix is bound and
reviewed. Do not
repeat completed diagnostics solely to refresh timestamps; build the final
source/review/raw manifest and then obtain two independent critics on that hash.

`gt07-native-writer-fifo-20261006-05` is a fresh M2 diagnostic on the current
source: unit and native wrappers exited 0, two client processes exited 0, all
19 FIFO/fencing/expiry/Stop checks passed, Blender Job/tree was clean,
and Stop completed in 109 ms. Correction: there was no revoke-during-effect or
late-completion check, and no matching O10 dry-run; this redundant diagnostic
does not close M2 and is excluded from final evidence. No rerun of this subset.
The eight-scenario app runner alone is not the full M1–M9 matrix. Close only
missing coverage, then freeze one closure and execute the complete matrix plus
affected regressions. Submit the same hash to two independent critics. Existing slices are
context; none grants acceptance. Do not replay a completed diagnostic solely
to refresh its timestamp. Every native launch needs its matching engine-free
dry-run; source changes invalidate that admission.

## Checkpoint, 06-10-2026 - held-editor receipt collection

`gt07-native-queue-20261006-06` - M2 FAIL, child 1/Blender 0/Job clean; final native inspect used an invalid uppercase ID (reproduced offline); raw unchanged.
`gt07-native-queue-20261006-07` - M2 Blender diagnostic PASS after recipe validation in dry-run; actual child/wrapper/Blender exits 0, source/snapshot unchanged, closure `036c21bf6b77c1ff00fb9730267446a6b9e2293e0c53e722917734d1fd1a33df`; two case effects observed, revoked reservation remains RESERVED, retained receipt is supervisor-only. 17 scenario tests exit 0 include rejection of the old final-read recipe before engine launch; AUTHORITY=0.

`gt07-native-godot-20261006-01..03` - FAIL, child exit 1; the real lock preserved last-good but healthy-editor identity blocked UNKNOWN collection; raw retained.
`gt07-native-godot-20261006-04` - FAIL, child exit 1, editor exit 0/Job clean; repaired collector returned the journal's canonical UNKNOWN, but the probe expected a transient save-error code.
`gt07-native-godot-20261006-05` - diagnostic PASS, child/wrapper/editor/lock-holder exits 0, Job/tree/handles clean, source/snapshot unchanged (`d36da7be6f7b701a349eb26ab5e82f13356359d0c808715014da4fbe20514b35`); real share=0 denial 32 at capture precondition, file identity/hash and active selection unchanged, queue UNKNOWN, durable Stop.

Repair: read-only `lookup_identity` permits only the held state while retaining
source/process/root/security/diagnostic checks; effects and COMMITTED readback
still require healthy identity. No authentication or journal fallback exists.
Nine focused regression tests include the old failure, real session rotation/
revocation, source/identity/phase drift and receipt mismatch. The probe checks
the actual reducer's durable response, not the owner's pre-journal error code.
94 focused tests completed, exit 0 (92 passed, 2 environment skips); the added reducer guard and M6
host tests then passed in a 21-test selection. Installed binding refresh02 is
historical after these production edits; refresh the exact reviewed delta
before the final frozen matrix. No benchmark rerun or GT07 acceptance claim.

## Checkpoint, 06-10-2026 - Blender export Job cap ordering repair

`gt07-export-caps-20261006-02` reproduced a Windows boundary without starting
Blender: configuring `JOB_OBJECT_LIMIT_JOB_TIME` after a warmed helper had
already been assigned made the queried 15-second cap include consumed CPU time
(`150468750` 100-ns units instead of `150000000`). Configuring and verifying the
same limits while the Job was empty, through the existing `cli_job.create`
`before_assign` callback, matched the exact CPU, memory, process-count and flag
caps; both helpers exited 0 and their Jobs closed with zero active members.
The regression is covered by the focused publication/cleanup/Job tests.

The repaired native export `gt07-native-queue-20261006-01` then passed its
matching dry-run and completed the pinned Blender path: native child and
wrapper exited 0, the output GLB preflight matched the snapshot and revision,
and the owned Job closed with zero active members and no retained handle. Its
source closure is `124f8423a1cb77bfcbddf7826f618b6ef2d7bb72e06566128c0a0c25cfffd006`.
The earlier `gt07-native-queue-20261005-82` mismatch remains immutable failure
history and is not relabeled. This is a diagnostic repair, not GT07 acceptance;
the final frozen M1-M9 matrix and two same-hash critics remain required.

## Latest diagnostic checkpoint

`gt07-m6-host-20261006-01` — engine-free M6/Q04 host receipt: command
`cmd.gt07.m6.host.20261006.01`, 10 tests, actual process exit 0, source closure
`32c64698b4cf84f10e60768ff22304823b7417023431c8d92f3b7188e95e0ddc`, no child
processes/owned Jobs/retained handles. AUTHORITY=0; final matrix/critics remain open.

`gt07-native-queue-20261006-08` — current-source Blender M4 conflict diagnostic
after its matching dry-run: actual child/wrapper/Blender exits 0, tree verified,
Job closed with zero active members and no retained handle; manual edit and hash
were preserved, queue remained `UNKNOWN` with `lookup.reconcile`, source and
snapshot stayed unchanged. AUTHORITY=0; final matrix/critics remain open.

`gt07-native-godot-20261006-17` — Godot M2 diagnostic PASS after the matching
engine-free dry-run: actual child/editor/wrapper exits 0, owned Jobs/tree clean,
no retained handles, source/snapshot unchanged, and the authority proof records
late COMMITTED reply-after-expiry, contender fencing, and revoke-after-effect
UNKNOWN with `public_ack=false`; AUTHORITY=0 and final matrix/critics remain open.

`gt07-native-queue-20261005-47` — Blender manual conflict PASS; child/wrapper 0,
source unchanged (`0eff6f0d…137172`), manual checkpoint retained. Runs 45/46 remain
failed harness history (missing import, then wrong expected terminal state).

`gt07-cross-app-20261005-53` and `-54` close the previously missing consumer
cuts diagnostically on source closure `c91bc0d770e9730cb10a3bc9fd8e80729f6db9d3485b024664706658993be51c`:
RELOAD retains the exact last-good CURRENT/journal and refuses ambiguous staging;
ACK reopens the durable owner and reconciles the queue lookup-only with no second
native dispatch. Authority remains zero; the final frozen M1–M9 matrix and critics
are still required.

`gt07-native-godot-20261005-60..64` and `gt07-native-queue-20261005-60..62`
passed the eight-scenario sequential runner after matching engine-free dry-runs:
actual editor/Blender children and wrappers exited 0, owned Jobs closed cleanly,
and source closures were recorded separately for each pinned tool. These are
current-source diagnostic slices; the final package must rerun the complete
M1–M9 map after its single freeze.

## Historical checkpoints

## Checkpoint, 05-10-2026 — M8 host process ownership proof

`gt07-m8-process-20261005-05` passed its dry-run/source binding and all three
host-only scenarios. A forged PID/start-time identity was refused before any
termination; the owned timeout killed only the gated root and descendant while
an unrelated sentinel remained alive; and a real 64 MiB Windows Job memory cap
denied `VirtualAlloc` with native error 1455 rather than a Python allocation
exception. All worker exits, Job membership, cleanup handles and zero active
counts were captured. This is authority-zero host evidence; a final frozen
M1–M9 repeat and critic package remain required.

The frozen-source host repeat `gt07-m8-process-20261005-07` reproduced all
three scenarios with actual worker exits, zero active/closed Job handles and
the same source closure.  It is still authority-zero evidence until the final
M1–M9 package and two same-hash critics.

## Checkpoint, 05-10-2026 — M5 storage fault boundary

`gt07-m5-storage-20261005-05` passed its engine-free dry-run and the
authority-zero host-only matrix after a reproducer repair.  The exclusive
Windows holder refused `MoveFileExW` with access error 5 while the target
identity and last-good bytes stayed unchanged; a writable C:→D: pair refused
the cross-volume replace with error 17 and preserved the destination; and the
fsync/disk-full injections returned `UNKNOWN` with no receipt and no commit
proof.  The worker exited 0 and all owned temporary files were cleaned.  The
report is diagnostic evidence, not product acceptance; the frozen M1–M9
repeat and requirement-map binding remain open.  Raw is immutable under
`studio/.local/reviews/gt07-m5-storage-20261005-05/`; source closure is
`78676a84db15d9d4af7b62cb9b51787e5064e0796212f21d8d8c19ad2d4174a4`.

## Checkpoint, 05-10-2026 — M9 dry-run boundary

Commit `21ddb086` added the engine-free adversary dry-run contract: run ID,
fixed review root, installed source/driver hashes and forbidden backend/native
flags are checked before any process can start. The one-use refresh in
`zdoc/reviews/20261005-gt07-binding-refresh/` repaired the stale 215-entry
generation to a verified 233-entry source map and 235-entry execution map;
its receipt and read-only postcheck retain the old/new metadata bytes and GT05
anchor. Fresh `play-mutation` dry-run `gt06-gt07-m9-playmutation-20261005-01`
then exited 0 with no backend, process, or engine started. This is still
authority-zero wiring evidence. Perform exactly one bounded native
Play/capture conflict run before the final matrix; do not bypass the binding or
convert the dry-run/static proof to acceptance.

## Checkpoint, 05-10-2026 — M9 bounded native play-mutation

Fresh dry-run `gt06-gt07-m9-playmutation-20261005-02` passed with execution
closure `406a07878af08237ebd04bd0a4b061e0ed12c356d6586961c5e05f5e342287c1`.
The bounded native run then exited 0. Its HTTP adversary recorded 18/18
checks: mutation was made while Play was RUNNING, the first capture committed,
the changed capture was rejected with `REPLAY_CAPTURE_CHANGED`, lookup stayed
`UNKNOWN` with no artifact or replay, and no second runtime appeared. The
import/runtime children both exited naturally 0; Job handles closed with zero
active members and no retained handle; source and driver stayed unchanged.
Raw evidence is immutable at
`studio/.local/reviews/gt06-gt07-m9-playmutation-20261005-02/`. This is
authority-zero diagnostic evidence; M9 still needs the final frozen M1–M9
matrix and two same-hash critics.

## Checkpoint, 05-10-2026 — M7 design boundary

The generic `Journal.compact(now_ms)` and the 510-record capacity run do not
close M7: `DurableBroker` still binds one append-only hash stream and rejects
rotation at `BROKER_JOURNAL_FULL`. A safe implementation needs a protected
segmented log manager with rotate-prepared/active-pointer/rotate-committed
custody anchors, immutable archive lookup and crash cuts. Until that design
and real-clock evidence exist, M7 remains OPEN; do not truncate `.events`,
change stream identity in place, or infer rotation from generic journal tests.

05-10: Queue-only PREPARED/ACTIVE_POINTER/COMMITTED custody anchors now preserve old stream bytes; real process cuts, native set-before-flush uncertainty, epoch reserve and append/rotation race checks passed within 61 focused tests (exit 0). Legacy fixture I/O stays unchanged. Queue integration and real-clock retention remain open; no M7 acceptance claim.

## Checkpoint, 05-10-2026 — M7 segmented queue implementation (authority zero)

The coordinator added a queue-only `QueueJournalManager` integrated with
`DurableBroker`/`QueueOwner`. Checkpoints hash their metadata and rows, validate
the logical stream and trusted parent, and are projected before custody barriers;
failed projection closes the uncommitted candidate without selecting it. Reopen
follows witnessed previous descriptors one segment at a time and detects cycles,
duplicate archive IDs and parent escapes. Expired terminal rows leave an
immutable archive tombstone: an identical command returns the old terminal row,
while a changed payload is rejected as `BROKER_ID_CONFLICT`.

Evidence: `studio/tests/jobs/test_segmented_journal.py` (5 selected tests, native custody
guard, actual exit 0) and `studio/tests/jobs/test_durable_broker.py` (18 tests,
actual exit 0; 90.315s). This is an implementation/regression checkpoint only;
M7 remains OPEN until real-clock native soak, crash cuts and the final M1–M9
matrix are reviewed.

The opt-in real-clock case was then run with `GT07_REAL_CLOCK_SOAK=1`: one
selected test, actual exit 0 in 60.545s, using wall-clock epoch timestamps and
a 60-second fixture horizon. The terminal receipt disappeared from the active
projection after rotation while the archive tombstone remained readable. This
closes the bounded expiry observation only; malformed checkpoint and crash-cut
coverage remains open.

The malformed-candidate case was also run under the custody guard (one selected
test, actual exit 0). An extra checkpoint row made the candidate invalid; commit
was rejected and the registry event pointer remained on the old witnessed log.
This closes validation-before-pointer-switch for this cut only, not process
crash cuts at each custody barrier.

## Checkpoint, 05-10-2026 — M7 retention and archive recovery hardening

M7 now persists logical stream, retry horizon, and global enqueue sequence in
the checkpoint metadata. Reopen preserves the logical fence and sequence after
compaction; archive lookup uses the same broker projection for terminal results,
UNKNOWN-to-terminal suffixes, queued expiry, and Stop cancellation. Same-ID
retry after the horizon returns `BROKER_RETRY_EXPIRED`; a changed command remains
`BROKER_ID_CONFLICT`. Focused Windows custody coverage is green: six segmented
journal tests (one opt-in wall-clock case skipped), eight retention/archive
regressions, and eighteen durable-broker regressions. This is still authority
zero and does not close crash cuts or the final M1–M9 matrix.

## Checkpoint, 05-10-2026 — M3 recovery run retained as invalid

`gt07-native-godot-20261005-21` reached the queue recovery harness but failed
at the pinned validation import (`VALIDATION_PHASE_ORDER`) before a native
effect; its cleanup is retained as an infrastructure diagnostic and must not
be replayed without a changed resource/reproducer review.

Earlier `gt07-native-godot-20261005-20` completed the queue receipt-loss/reopen
path with actual editor/Job cleanup and the recovery invariants, but it is not
usable evidence because a separate M9 source commit landed during the native
window and the closeout reported `source_unchanged=false`. Both raw
directories are immutable and retained; the same scenario must be rerun once
after the current source freeze with a fresh ID.

`gt07-native-godot-20261005-23` was then admitted from a fresh dry-run and
stopped before any native effect because the owned Linux validator container
timed out at its 22-second host start/attach bound (`EXECUTOR_ENGINE_OR_HOST_NOT_CLEAN`).
The child exit was 1, the container/Job had exit 124 with zero active handles,
inputs and source stayed unchanged, and the raw closeout is retained.  This is
an infrastructure diagnostic; do not replay it until Docker/validator startup
is healthy or a different scoped reproducer is available.

## Checkpoint, 05-10-2026 - governed M4 conflict admission

The scenario runner now exposes `godot-conflict` with the mandatory engine-free
dry-run and an opt-in native injection at the queue lease boundary. The injected
manual editor projection must leave the owner response `UNKNOWN` with
`lookup.reconcile`, preserve the manual `[8,8,8]` state, and retain the durable
UNKNOWN journal/queue record without replay. The pure runner/owner/dispatcher
suite is 61 tests, exit 0. Dry-run `gt07-native-godot-20261005-17` passed
with source closure `3f84b6e783503d596d19afb1ab6a39bafc81301a299787638e8e2ea6c1ec7e83`.
Native `-16` reached the intended UNKNOWN response but the first harness version
incorrectly inspected a held owner; its raw is retained. Native `-17` was then
blocked during ValidationOwner import because the Docker/Godot profile process
returned SIGKILL before phase ordering; actual child/Job cleanup is clean. This
is an infrastructure diagnostic, not M4 proof; do not rerun until the resource
condition and reproducer review change.

## Checkpoint, 05-10-2026 - M4 native queue conflict PASS slice

After the held-owner inspection and durable generic reconcile fixes, governed
`godot-conflict` run `gt07-native-godot-20261005-19` passed its engine-free
dry-run and native Godot queue path. The manual projection changed the live
root to `[8,8,8]`; the stale owner response was `UNKNOWN` with
`GODOT_PUBLICATION_RECONCILE_REQUIRED`, `public_ack=false`, and
`next_action=lookup.reconcile`. The queue recorded `UNKNOWN`, no replay or
rollback occurred, and editor/owner cleanup was actual exit 0 with a closed,
zero, unretained Job. Source and frozen snapshot remained equal at closure
`c52dff82d1b6394065c9b5428130f94291a74a99bd44579182435831bbdddd2b`. The
61-test focused runner/owner/dispatcher suite also exited 0 (6.101s). This is
the Godot side of M4 only; Blender `.blend` conflict and the frozen M1-M9
repeat remain open.

## Checkpoint, 05-10-2026 — current-source M4 native repeat

`gt07-native-godot-20261005-26` passed the mandatory dry-run and native
Godot conflict path on source closure
`737e6aa2ebbf9a3237fbbbd77d0f900a26ccd3e2014f28cca07b0d9b2430c93c`.
The manual projection was preserved, the stale owner response remained
`UNKNOWN` with `lookup.reconcile`, and no replay or public ACK was emitted.
Both editor and validator children exited 0 naturally; the owned Job/tree was
closed with zero active members and no retained handle, and source readback was
unchanged. This is a fresh authority-zero diagnostic slice; the Blender
`.blend` conflict and final frozen M1-M9 matrix remain open.

## Checkpoint, 05-10-2026 — fresh M2 writer FIFO repeat

`gt07-native-writer-fifo-20261005-04` completed its source snapshot and
focused Blender suite with actual wrapper/child exit 0, then ran the native
writer FIFO host with the pinned Blender binary. Both live client processes
exited 0; all 19 checks passed, including persisted FIFO grants, expiry and
fencing rejection, bounded waiter capacity, Stop priority, and no scene drift.
The owner Job/tree closed with zero active members and no retained handle;
source closure was
`ccc2c3f2f5feac425d358309253f1d5f7be5c375d80d1263d3a3176a050dbae9`.
This remains authority-zero evidence until the final frozen M1-M9 matrix and
independent critics.

## Checkpoint, 05-10-2026 — fresh M8 process ownership repeat

`gt07-m8-process-20261005-08` ran without an engine and verified all three
owned-process cases: forged PID/start-time termination was refused, the owned
timeout removed only the gated tree while the sentinel stayed alive, and a
64 MiB Job memory limit caused native `VirtualAlloc` denial (1455) rather than
a Python allocation error. Actual worker exits were captured and every Job
closed with zero active members and no retained handle. Source closure remained
`e54646f8ca640cc465231ddecd204adc233df3aefbf96e39d9376697b7b58f71`.
This is authority-zero host evidence; the final frozen matrix is still open.

## Checkpoint, 05-10-2026 — M3 consumer handoff after dry-run repair

The cross-app runner now consumes a matching `dry-run.json` admission with
source, adapter closure and protected Blender handoff bytes unchanged; it
retains the admission report before native dispatch. Run
`gt07-cross-app-20261005-19` then performed one native consumer dispatch from
the exact COMMITTED producer row, observed Godot readback ACK, queue
`COMMITTED`, and byte-equal reopen. The nested validator and editor children
exited 0 with clean owned Jobs, but its environment diagnostics still report
`diagnostic_process_clean=false`/`log_clean=false`; therefore this is
authority-zero diagnostic evidence, not an M3 acceptance pass. Consumer
crash/reload/last-good coverage and the frozen matrix remain open.

## Checkpoint, 05-10-2026 — M3 current-source receipt-loss recovery

`gt07-native-godot-20261005-27` passed the mandatory matching dry-run/native
admission and ran the receipt-loss/reopen lookup-only cut against source
closure `e733d05e4b54d8a0a2199074885c2ceaefe431764e36b2d38052cb79ec451f18`.
The receipt was intentionally absent; reopen and lookup/reconcile recovered
the existing COMMITTED state without a second native effect. Editor and
validator children exited 0 naturally, owned Jobs/trees closed with zero
active or retained handles, and source remained unchanged. This is
authority-zero diagnostic evidence. The six-phase Blender crash matrix,
consumer last-good proof, and frozen M1–M9 matrix remain open.

## Checkpoint, 05-10-2026 — M5 dry-run/native handoff repair

The M5 storage runner now consumes a matching engine-free dry-run instead of
rejecting the required follow-up with `RUN_ID_USED`; it preserves the
admission report as `dry-run-report.json` and fails closed if the source hash
changes. Focused M5 contract tests pass (5 active, 2 platform-gated skips).
`gt07-m5-storage-20261005-07` then ran the same admitted ID: file-lock
replacement returned UNKNOWN with error 5 and unchanged identity, cross-volume
replacement returned UNKNOWN with error 17, and injected fsync/diskfull paths
kept last-good bytes with no receipt. The diagnostic verified all four cases;
source closure was `308602e88500224bda8f3a045f7bb24d9da0d6c81b332f2506f73566d03fd072`.
This remains authority-zero evidence and does not close the final frozen matrix.

## Checkpoint, 05-10-2026 — native editor conflict diagnostic

`gt07-native-editor-conflict-20261005-01` ran the pinned Godot EditorOwner
fixture with actual edit/create/update/undo/redo/remove/restore operations and
an intentional same-process manual mutation after capture. All 40 checks passed:
the stale checkpoint was rejected, the manual mutation remained unchanged,
UndoRedo semantics and script attachment were preserved, source hashes stayed
unchanged, and the editor exited 0 with a closed, zero, unretained Job. Raw is
immutable under `studio/.local/reviews/gt07-native-editor-conflict-20261005-01/`.
This is an authority-zero editor diagnostic only; it does not close the Q06
queue lease conflict or prove the Blender `.blend` path, so M4 remains open.

## Checkpoint, 05-10-2026 — queue-level Blender -> Godot consumer

`gt07-cross-app-20261005-07` passed a fresh engine-free admission and one
native gameplay-source publish using the verified Blender handoff from
`gt07-native-queue-20261005-06`. The durable queue committed the producer
receipt first, admitted the Godot consumer with that producer as a dependency,
and recorded the consumer only after Godot `READBACK_ACK`, CURRENT/journal
readback and a clean reopen. The native container and owned Job exited cleanly;
the Godot publish count was exactly one, `public_ack=false`, and the artifact
hash was `1bb48eb159925ec13f4df7337445a691aac98184580553d81f934d2c674bc87b`.
Raw is immutable under `studio/.local/reviews/gt07-cross-app-20261005-07/`;
source closure is `c91bc0d770e9730cb10a3bc9fd8e80729f6db9d3485b024664706658993be51c`.
This closes the non-crash queue-level publish/readback slice only; a queue-level
lost-receipt/last-good crash cut and the frozen M3 matrix remain open.

`gt07-cross-app-20261005-16` repeats the consumer after repairing a binding gap:
the producer dependency now uses the exact COMMITTED Blender queue row
(`native-95fcfd08…`, command and receipt digests read from the producer
closeout) rather than hashes derived from its run id. The adapter closure also
includes the cross-app runner and durable queue runtime. Native import/host
exits and Job cleanup were recorded, but the nested diagnostic reports
`diagnostic_process_clean=false` because of environment stderr; this remains
authority-zero evidence and is not an M3 acceptance pass.

`gt07-cross-app-20261005-18` repeats the repaired exact-producer binding after
an immediate protected-handoff reread before admission. It records one native
dispatch, COMMITTED queue state, readback ACK and byte-equal reopen. The nested
consumer still reports environment diagnostic stderr, so this is diagnostic
only; the consumer crash/reload/last-good cut and frozen matrix remain open.

## Checkpoint, 05-10-2026 — native M2 FIFO repeat

`gt07-native-writer-fifo-20261005-03` passed the unit gate and native host
capture with actual wrapper/child exit 0, clean owned Job/tree and source
closure `ccc2c3f2f5feac425d358309253f1d5f7be5c375d80d1263d3a3176a050dbae9`.
The final repeat observed two distinct live writer clients, persisted FIFO
grants, expiry/cancel handling, fencing and late-writer rejection before
intent, no stale scene drift, bounded waiter capacity, Stop priority and
actual GUI exit/zero Job. Raw is immutable under
`studio/.local/reviews/gt07-native-writer-fifo-20261005-03/`; this remains
authority-zero diagnostic evidence until the frozen M2/M1–M9 package and
independent critics.

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

## Checkpoint, 05-10-2026 — native Blender writer FIFO and fencing

`gt07-native-writer-fifo-20261005-02` passed its frozen unit gate (actual exit
0) and native host (actual exit 0, clean Job/tree). Two distinct client
processes committed in FIFO order; the expired head was never granted, the
fencing epoch advanced on handoff, old and late writers were rejected without
scene drift, and Stop canceled waiters and blocked new effects. This is an
authority-zero diagnostic, not the final frozen GT07 package. Raw is immutable
under `studio/.local/reviews/gt07-native-writer-fifo-20261005-02/`; source
closure is `ccc2c3f2f5feac425d358309253f1d5f7be5c375d80d1263d3a3176a050dbae9`.
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
