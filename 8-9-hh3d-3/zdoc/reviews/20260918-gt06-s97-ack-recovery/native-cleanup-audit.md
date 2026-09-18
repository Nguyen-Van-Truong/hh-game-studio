# S96 terminal native and cleanup audit

AUTHORITY=0. Diagnostic implementation review only; not a final critic, formal
benchmark result, no-leak conclusion or plan tick. Read the nested AGENTS.md and
tools-plan S96 header first: GT-06 remains IN_PROGRESS; GT-07–10 are not opened.
No runtime/helper changes, tests, engines, task operations or new owned jobs
were performed by this reviewer. Only this new audit document was written.

Run: `gt06-s96-coupled-phases-01`.
Raw root: `8-9-hh3d-3/studio/.local/reviews/gt06-s96-coupled-phases-01/`.
Outer records: `zdoc/reviews/20260918-gt06-s96-coupled-phases/launch-01/observer/`.

**Result:** failed during batch 17 ACK consumption, before the batch-17 sparse
hook or fresh ACK counter readback. There are 18 native batch publications but
only 17 completed joint/ACK observations. The complete native benchmark and
natural editor exit are not proved. Owned cleanup and nonzero actual exits are
recorded in distinct evidence domains; the missing inner editor-exit receipt
remains missing.

## Native prefix and exact failure boundary

- `batch-00.json` through `batch-17.json` each contain 100 cycle records and
  100 timing records for native PID 50100. All 18 files' hashes and sizes match
  the diagnostic manifest. This is 1800 reported native cycles; it is not 18
  completed coupled batches or independent revalidation of every cycle effect.
- All 18 prepublication batch observations contain Objects **71127** and
  Resources **6**. Their barrier issuance equals batch end, and each deadline
  is exactly issuance +30,000,000 us. Their published ACK files bind the same
  run/batch/native digest/deadline.
- `joint-00.json` through `joint-16.json` contain Objects **71128** and
  Resources **6** at the fresh ACK observation. Their raw hashes, native/ACK
  references and receipt fields match. All 17 corresponding ACK log markers
  agree on native/ACK hashes, frame, issue/deadline and observed time. This is
  five warmup plus twelve later complete joint observations, not the required
  35-batch run.
- Batch 17 published at native **2114192579 us**, with ACK deadline
  **2144192579 us**. Native `failure.json` records **2114247696 us**,
  `phase=HOST_BARRIER`, `cycle=100`, code `BENCHMARK_HOST_ACK_READ`.
  Failure was **55.117 ms after issuance**, with **29.944883 s remaining**.
  The recorded failure is not a barrier timeout.
- Final `ack-17.json` exists, is valid JSON and matches batch-17 native digest,
  run, source, profile and deadline. That terminal file does not prove the
  native reader could open or completely read it at the failure instant.
  No ACK17 marker, joint17, sample-preview17 or batch-capture17 exists.
- The frozen source uses `BENCHMARK_HOST_ACK_READ` for both a null
  `FileAccess.open` (stock lines 836–839) and a short `get_buffer` result after
  a valid size (845–849). START_READ similarly covers both branches. S96 did
  not record which branch, expected/actual read length, Godot open-error code
  or OS error. Therefore **open-null is a hypothesis, not established by this
  code alone**. This corrects the reviewer's earlier overly narrow interim
  wording. Either branch precedes ACK JSON/schema/hash/postcondition validation
  and the S96 sparse hook.
- Child failure is `CAMPAIGN_NATIVE_FAILURE`, with 17 completed batches and
  host phase `{batch:17, phase:joint_observation}`. Supervisor return is 1 with
  `BENCHMARK_WRAPPER_EXIT`. Diagnostic manifest says `DIAGNOSTIC_FAILED`.
- Native stdout has 18 BATCH markers, 17 ACK markers and one FAILED marker;
  stderr is empty. No warning/error/leak diagnostic string was found in the
  captured native stdout. Failed/terminated shutdown makes that absence
  insufficient to establish a clean shutdown or no leaked objects.

## Sparse baseline and limits

Only `sparse-00.json` and `sparse-post-00.json` exist. The baseline binds:

| Property | Observed value |
|---|---|
| Schema / phase | `hh-studio.gt06.s96-ack-sparse-attribution` 1.0.0 / `before_ack_counter_readback` |
| Trigger / batch / sequence | `baseline_ack_batch4` / 4 / 0 |
| PID / frame | 50100 / 48267, matching ACK4 |
| Counters before, after collection, after publication | Objects 71128; Resources 6; Nodes 21482; Orphan nodes 313 |
| Counter self-drift | false in both records |
| Collection start/end | 421845805 / 421901652 us; 55847 us elapsed |
| Through-snapshot-publication endpoint | 421913149 us |
| Original ACK observed time | 421919616 us; 6467 us after that publication endpoint |
| Selected inventory | 102 Trees +4493 TreeItems +12 Node3D-family IDs =4607 |
| Outside selected inventory | 71128 −4607 =66521 objects |

Checked the post receipt's exact snapshot SHA, both rows' ACK SHA against raw
ACK4, run/PID/batch/sequence, frame, counter equality and timestamp ordering.
The baseline primitive IDs are nonzero signed integers, sorted/unique in each
list, disjoint across owners/classes/family, and all inventory counts reconcile.
The target inventory is complete within its declared scope and explicitly
partial for ObjectDB; no object references or user content are retained.

The snapshot baseline is **ACK 71128**, not prepublication 71127. The one-count
phase offset is already present throughout the prefix and is not a measured
increase within either phase. No second identity snapshot exists. ACK0–16
contain no count increase, but later identity stability was not measured.
Batch17 never reached this ACK observation point, so its prepublication 71127
cannot stand in for an ACK17 count or resolve the historical batch-17 growth.
No no-leak inference, full ObjectDB attribution or accepted memory result follows.

## Exit and cleanup evidence

The outer observer adopted each process by PID, start identity and parent
relationship, and recorded actual exits through retained handles. All five
individual exit rows match the final outer terminal rows; all retained handles
are marked closed in the terminal record.

| Role | PID | Parent | Actual exit | Evidence domain |
|---|---:|---:|---:|---|
| Supervisor | 6888 | 53484 (observer) | 1 | retained handle; Popen actual return also 1 |
| Host helper | 23452 | 6888 | 1 | retained handle |
| Host child | 22148 | 23452 | 1 | retained handle and inner `host-owner/process-exit.json` agree |
| Editor helper | 5652 | 22148 | 2 | retained handle and child cleanup helper-exit observation agree |
| Godot editor | 50100 | 5652 | 2 | retained handle only; inner target-exit receipt absent |
| Godot import | 29676 | not asserted here | 0 | import capture and its process-exit receipt agree |

`child-terminal-cleanup.json` records no cleanup errors; heartbeat/drain/host
threads are stopped; sockets, journal index/database/directory and probes are
released. The editor Job is zero/closed/untainted, with no retained Job or wrapper
process handle. Its helper exit is 2. The editor target is explicitly
`TARGET_EXIT_NOT_RECORDED`, with null actual exit. The host child does not claim
its own or its supervisor's eventual exit. Those nulls are correct and remain
unchanged; the external rows supply additional evidence without replacing them.

`editor-host/cleanup-001.json` says `BENCHMARK_CLOSED_BEFORE_FINISH`, completed
false, wrapper exit 2. `host-owner/cleanup-001.json` says
`BENCHMARK_WRAPPER_EXIT`, completed false, wrapper exit 1. Both Jobs are
zero/closed/untainted with released wrapper handles. The owner cleanup path
closes the Job and terminates any still-active members; its configured
termination code is 2. The native failure handler requested `get_tree().quit(86)`,
whereas the retained editor exit was 2. These are failure-cleanup observations,
not proof that Godot completed a natural quit. No exit 86 or zero is inferred.

Outer terminal records no observation/cleanup errors, no missing adopted roles,
no watchdog timeout, zero active processes **before outer cleanup**, a
zero/closed/untainted outer Job, and released retained/Popen handles. Inner
cleanup had already occurred; outer pre-cleanup zero does not imply the editor
exited naturally. Outer elapsed time is 2126.906 s. Its `observer_exit_code=1`
is an intended result, not self-observed process-exit proof.

The separate coordinator scheduler receipt at 16:36:03.5609562Z records state 3,
zero instances, result 1 and `known_pids_current=[]`. This supplies the separate
scheduler observation requested by the outer record; it is not a system-wide
leftover sweep. The task-deleted receipt is dated 16:36:46.2852751Z.

Absent artifacts were checked explicitly: child-result, editor process-exit,
editor capture, host-owner capture, native complete index, joint/sample/batch
capture17, and sparse/post01. The diagnostic manifest's required-missing list
names child-result and editor process-exit; it is not an exhaustive list of all
absent success artifacts. External exit evidence does not turn this run into a
successful capture or manufacture any of those files.

## Hash checks and evidence scope

The 51-entry source map recomputes to
`564e5b7877f49d33a1af84eaf3b3a7ddf4ea2f846c4161eb694c5c40514fc752`.
The frozen stock native source is separately preserved under
`failure/raw/source/studio/tests/replay/benchmark_native.gd`, SHA-256
`52fbd9af5c6191ada5baf1d7195a75685ed5e27a95f4d244af8b4d679f8c00f2`.
All S96 source/line references above bind that frozen version, not the later
candidate in the working tree.
Both native diagnostic and outer observer nine-helper maps recompute to
`49305105575402570035bbff7f3f7abdcc5a98653b8cc994932b4ae07f921795`.
Profile is `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.
This audits map binding, not a fresh sweep of every runtime/source-copy byte.

All 18 native batches, 18 ACK input files, 17 joints and both sparse files were
checked against the diagnostic manifest. Selected cleanup/failure/log/import
records also match their manifest hash and size. All 12 outer-manifest entries
match exact bytes, including five exit rows and terminal. Outer request and
task XML hashes match the observer manifest. The executed native overlay hash
matches its overlay metadata and the coordinator's separately preserved
executed-native supplement. No mismatch was found in these scoped checks.

| Artifact | SHA-256 |
|---|---|
| Raw `diagnostic-manifest.json` | `5c91e8258db80facb7820bc4080b86c32012fa82e370fc9a5593ee46f2905fad` |
| Raw `project/benchmark/out/failure.json` | `f2c9bb97110a3e469f6d988d5f639b46366f573c947b114b1f2f68ad3a9d93ca` |
| Raw `project/benchmark/out/batch-17.json` | `ba30ed708117e7f9bb526f49f416a4e52dbf25822dc0ad23b9562d069ad3fa11` |
| Raw `project/benchmark/input/ack-17.json` | `ed082013ff329c80205d253bfe630f125978c5326797aa04e97c711c5e7c95bd` |
| Raw `project/benchmark/out/sparse-00.json` | `0384675458e6c36e5865525af138c7b82fb70be4a32fded9926f04b6820399ac` |
| Raw `project/benchmark/out/sparse-post-00.json` | `320cbd83a6a8f92960cff1c5af6aa97e757de899ab6767dddb9155cd91fc4f42` |
| Raw `joint-04.json` | `71368b6ba8fadf4fa242712d0fa07ac0115e598300c375ed883389420ff04fd9` |
| Raw `joint-16.json` | `154cc35553082f5aabcf0107f83893ae607aa7ee60c6ad0c6c73d63fc6ab1b79` |
| Raw `child-terminal-cleanup.json` | `5e41c19af3b2a11ec4b6bb574697b073a5bef1e734768b6405862583119e3dce` |
| Raw `editor-host/cleanup-001.json` | `9ff26d2260e6188703654517521ac75e80f618c4e517723042f5f4babc109ee1` |
| Raw `host-owner/cleanup-001.json` | `31f58e29075f8f16bb2df0bb72471bfcd0df794b729d6497022554d84959cfc8` |
| Raw `editor-host/stdout.txt` | `ad7db886d01f6b46cfa62767a630e09c8aa8865d8afc9d609223023278cb4f9b` |
| Raw/supplement executed native `.gd` | `de1838cf836e7dfd9a80fa05c7636774e43da0121dc3d7b551e02b90f5f746b1` |
| Outer `terminal.json` | `4d5dd2f81d8c01ac54f5f01e7e3a15b33872610c13fb8026323c869b67b733e7` |
| Outer `manifest.json` | `3d6ffe3cd42892da0c4760551b45183c2452f7ed9814303aa823f967de8a3b1c` |
| S97 `scheduler-terminal.json` | `180591ee96a0f7ee2a2384cef4646433d833a573bdd8b26b67614cd469292e0f` |
| Coordinator sealed `failure/manifest.json` | `46ad1f9701c5e3bd000b7fb58e7c7d638a1c1bc580d376ea4c2df1f182b126f2` |

The coordinator's full packet seal is a separate result; this reviewer did not
rehash all 244 copies or claim a second full packet verification. Old raw,
manifests, helpers and source remain untouched.

## Conditional repair review — causal probe pending

The current publisher closes/fsyncs its temp write before `Path.rename`, then
readbacks final bytes before returning. A Windows rename visibility interval
with an internal DELETE handle still retained is a plausible hypothesis, not
identified in S96's branch-ambiguous READ failure. Await the controlled probe
before assigning this cause or claiming a repair.

If the probe supports transient open-null, the smaller candidate is to return
to the next frame **only for `FileAccess.open == null`**, preserving original
START/ACK deadlines and every later guard. `_process` already emits its real
heartbeat before invoking the wait method. Do not add sleeping/busy loops,
reset phase/batch/run clocks, renew deadlines, manufacture progress/status/ACK,
or retry invalid size, short read, JSON/schema/hash/postcondition failures.
Permanent open failure would remain failure at the original deadline; retaining
the first error is necessary to avoid replacing its cause with only TIMEOUT.

Keep receipt schemas unchanged. Capture `FileAccess.get_open_error()` immediately
on the first null result, with fixed role/batch, native time/frame and primitive
attempt count; retain it even if a later open succeeds. Distinguish open-null
and short-read in diagnostics. Emit bounded standalone first-null/recovery
records, not one per frame. Use a diagnostic prefix outside
`HH_GT06_BENCHMARK_*`: `NativeLog.poll` queues all non-heartbeat markers under a
256-entry cap, while the ordinary 35×READY/START/BATCH/ACK already uses about
140 entries. First-null plus recovery for both inputs could otherwise add 140
and create a new `CAMPAIGN_MARKER_LIMIT` failure. Avoid the generic log guard's
standalone uppercase ERROR/WARNING tokens; retain numeric Godot errors when an
OS code is unavailable.

A host-ready sentinel published only after rename returns and final readback
would add a second input protocol, file allowlists and failure states. Opening
that sentinel can recreate its publication race; an existence-only marker has
different binding assumptions. It is a larger contract change than bounded
open-null polling. Neither option changes malformed/tampered-input rejection,
the original time budget or measured status-gap gates. No candidate was edited
or executed in this review.

## Follow-up: controlled mechanism probe and candidate static review

The preceding proposal was recorded before the coordinator's controlled probe.
The subsequently inspected `rename-probe/run-01/result.json` has SHA-256
`775fe42d4750968f2128a3029f581bf762998552b4746dcdf4b9c42975ce3804`;
`rename-probe-owned-01/capture.json` has SHA-256
`e1e0a265472a034bc6bc24186c226593d54e62ce993b6d6b23d266d1218bbd28`.
All seven recorded checks are true. Under a retained DELETE-access handle after
an actual rename, the pinned Godot 4.7.2 process saw existence=true, open=false,
Godot error 12. The Win32 reader without delete sharing returned error 32;
the reader with delete sharing obtained the complete 40-byte payload. After
holder release, that same Godot process read the unchanged 40 bytes and exact
SHA-256 `8013aca74ea3cb36142bb0d7ac0418807795fb024722be930be4d39218801d7e`.
The concurrent Python read-only-holder control also succeeded. Thus this
controlled mechanism is observed; the missing S96 branch and handle timing
remain unproved (`s96_cause_proven=false`).

Those coordinator-run records report actual native PID 25620/helper 18964 exits
0/0 and parent PID 48464/helper 43044 exits 0/0, clean owned trees, no probe
errors, released holder handles and unchanged source. This reviewer read and
hashed the saved results; no probe was launched here.

Read-only candidate review binds `studio/tests/replay/benchmark_native.gd` at
SHA-256 `13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95`.
The complete diff against the frozen stock version adds seven primitive fields,
the shared `_open_host_input` helper, bounded open/short-read diagnostics and a
pending-only terminal diagnostic. No concrete runtime blocker was found:

- Both callers return to the ordinary next frame only after null open. The
  existing initial and post-validation absolute deadline checks, `_process`
  run clock, heartbeat cadence, drift checks, receipt shapes, counters and
  semantic/file-hash validation order are unchanged. No new grace period,
  sleep, retry loop or successful receipt is introduced.
- `FileAccess.get_open_error()` is captured immediately after null open.
  State resets only for a new stage/batch, retaining the first error/time/frame
  and total open attempts in primitives. Pending logs once; later open logs
  one recovery, or an unrecovered terminal failure logs once. A successful
  open is explicitly labeled `open_only_not_receipt` and still undergoes all
  original validation. The local returned FileAccess is closed on the existing
  readable-file paths and is not stored in diagnostic state.
- Short reads retain requested/actual lengths and `get_error()` before close,
  then fail immediately with distinct START/ACK SHORT_READ codes. Invalid size,
  JSON, fields, binding, position, hashes, postconditions and changed bytes
  remain fatal. There is no retry of readable invalid content.
- The separate `HH_GT06_HOST_INPUT_*` prefixes bypass the campaign marker
  queue; numeric errors and the emitted code strings do not match its generic
  standalone ERROR/WARNING rejection. Receipt/failure JSON schemas are not
  expanded. The terminal diagnostic is restricted to the matching active
  stage/batch and `_failed` still prevents duplicate failure publication.

This is implementation review, not compilation or native behavioral proof.
The coordinator-owned native regressions must still establish multi-frame
pending behavior, exact-once advance after release, original-deadline timeout
while held, fatal malformed/short-read inputs and actual owned cleanup.
Neither this static result nor the mechanism probe establishes that the full
coupled campaign, its memory gates or the historical ObjectDB increase is fixed.
