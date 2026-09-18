# S96 implementation preflight — 2026-09-18

AUTHORITY=0. This is an independent implementation/source review, not a final
acceptance critic, benchmark PASS, root-cause finding or permission to tick a
plan. The reviewer ran no tests, HTTP clients, engines, task operations or
process manipulation. Only this new review file was written. Runtime checks
below were performed by the coordinator/recorder writer and inspected as saved
evidence after their handoff.

No concrete implementation blocker remains in the source hashes below. The
original batch-timestamp mismatch was corrected before dispatch. The recorder
now preserves the first lookup failure even when another endpoint failed
earlier. Native import and actual full-mode ACK execution remain separate
verification steps; the static checks and HTTP smoke do not prove them.

## Corrected findings

1. **Initial S96 draft broke the full-mode barrier timestamp contract.** It
   refreshed `ended` after the sparse hook in `_write_batch`, while the already
   populated barrier retained its earlier `issued_mono_us` and deadline.
   `studio/tests/replay/benchmark_assembly.py:451–454` requires issued time to
   equal batch end and deadline to equal issued time plus 30,000,000 us. This
   was a source finding, not a claimed failure from a launched S96 run.

   The final patch removes every `_write_batch` alteration. Its sole insertion
   in original native code calls `_s96_before_ack(digest)` and returns on a
   collector failure, immediately before the original fresh ACK counters in
   `_wait_host_ack`. ACK schema/hash/postcondition checks and file-hash readback
   have already succeeded. Original `observed` time, deadline check and
   heartbeat remain intact; no deadline is refreshed or extended. Removing
   that exact insertion reproduces the original native bytes.

2. **A first-any-endpoint failure snapshot could consume the later lookup
   diagnostic window.** The final recorder counts every failure in a fixed
   route map but freezes its single window only when `route == 'lookup'`.
   `observed_client_type` supplies the fixed route before the delegated call
   and captures the existing non-null transport failure before returning to
   retry logic. The regression sends a commands-route failure, a lookup
   failure, then a successful lookup; the frozen call must be the second call.
   The real supplemental smoke exercises the same ordering and distinct ports.

   Correction of the earlier discussion: the current coupled producer does
   **not** deliberately drop a submit response on each batch. Its `_command`
   expects `ACCEPTED_PENDING`, and it does not arm `drop_submit_response_once`.
   The drop is injected in focused tests/smoke. The selection fix addresses
   the generic earlier-nonlookup-failure case; it is not evidence of such an
   injection in the current campaign. Final recorder source states this.

## Reviewed behavior and bindings

- All wrapper signatures match the current `BenchmarkFixtureClient`,
  `BenchmarkFixtureHost`/accepted transport and `VerifiedJournal` methods.
  Delegation occurs once. `HTTPConnection` construction, request/read args,
  response class inheritance, results, exceptions, timeout/retry policy and
  base connection close remain delegated. `Response.read` calls the original
  implementation through `super()` with unchanged args.
- Journal guard acquisition enters the original context once through
  `ExitStack.enter_context`. Its exit runs inside `journal.guard_held`, so
  release duration is included and original exception transformation or
  suppression is preserved. Re-entering the same ExitStack does not acquire
  the underlying guard again. The outer exit finds the callback stack empty.
- Recorder spans use thread-local nesting and one mutex for retained primitive
  state. The mutex is released before delegated work. The event ring, unfinished
  spans and one frozen failure window are bounded. Snapshot copies include a
  separate copy of route counters; caller annotation cannot mutate retained
  state. Overflow never skips the delegated operation and remains explicit.
- Numeric loopback server/client ports bind after connect and at server handle
  entry. Recorded ancestor identities survive later connection close. Ports
  require lifecycle-window disambiguation; missing, reused or evicted markers
  cannot establish a unique join. `server.dispatch` to `server.lookup` is not
  labeled pure lock wait. No request body, command ID, bearer or exception text
  enters the recorder.
- S96 adapts the S95 primitive collector only for full-mode guard, ACK entry
  signature, schema/phase/trigger labels and the already validated ACK digest.
  Primitive collection/diff code remains unchanged. Baseline is ACK batch 4;
  the second snapshot is the first later ACK object-count growth. Published
  `before_ack_counter_readback` rows and their post-publication hash receipts
  must bind to the original ACK receipt's run/PID/batch/digest/counters/frame
  and preceding collection times. Earlier native batch memory is a different
  phase and is not the matching counter source.
- The collector remains a partial inventory of reachable Trees, their
  TreeItems and the Node3D family, with at most 32768 primitive IDs and two
  snapshots. No growth is not a no-leak proof; absence of a second snapshot
  does not measure later identity stability.
- The explicit helper map covers the entry, registration script, composition
  tests, immutable S93 supervisor/observer/imported patch helper, original S95
  probe, phase recorder and current source-map reference. The S93 patch import
  is explicitly loaded from its pinned path before the retained supervisor is
  loaded. The final HTTP snapshot uses the frozen helper digest and reports
  whether current helpers remain identical; it does not relabel changed files
  with a new run digest.
- `campaign()` checks the exact original 51-file map and unchanged profile.
  `--describe`/request checks also bind Python companions, Godot and helpers.
  The effective native overlay is separately saved/hashed. Its `.gd` artifact
  is outside the inherited JSON/log manifest glob and must be included in the
  coordinator's terminal seal, as the implementation README specifies.
- Ownership reuses S93's gated same-PID supervisor, checked seven-slot outer
  Job and 7530-second watchdog, preserving inner profiles. Registration is
  demand-only/current interactive user, hidden, with no restart or trigger.
  `GetTasks(1)` includes hidden GT06 tasks in the active-task exclusion check.
  A one-use dispatch claim precedes task dispatch. Actual target/helper exits,
  owned cleanup and the scheduler's independent observer exit remain required.
- HTTP phase JSON is written only after original child cleanup. A hard kill
  or failed publication can leave it missing; that is a gap, not absence of
  failure. The wrappers add measured overhead and provide diagnostic evidence
  only. Formal workload, gates, deadlines and acceptance thresholds remain
  unchanged; this single instrumented run cannot enter the ten-run dataset.

## Saved verification inspected

- `../20260918-gt06-s95-result-prep/http-phases/unit-02/`: 12 tests, no failures;
  capture records target PID 4300 / helper PID 20936, both actual exit 0,
  no timeout, tree verified. Invocation source pins match the recorder and
  tests listed below.
- `../20260918-gt06-s95-result-prep/http-phases/smoke-02/`: target PID 47412 /
  helper PID 17632, both actual exit 0, no timeout, tree verified. The report
  records 10 ordinary commands, two effects, closed journal/observer/sockets,
  no live host threads and unchanged sources/history. Its explicit supplemental
  cuts yield commands failure 1 then lookup failure 1; first frozen call is
  lookup span 408. Lookup/retry client ports are 65460 and 65461 at server port
  65432. Saved phases report zero eviction, overflow and missing identities.
  The smoke explicitly says `s93_reproduction=false` and ran no engine.
- `unit-01/`: six composition checks, no failures; target PID 53876 / helper
  PID 53992, both actual exit 0, no timeout, tree verified, source unchanged.
  Invocation pins match the three S96 files and original S95 probe below, with
  stock native driver SHA-256
  `52fbd9af5c6191ada5baf1d7195a75685ed5e27a95f4d244af8b4d679f8c00f2`.
  These checks cover byte reversal/ACK placement/labels and
  sanitization, not native execution.

The next coordinator steps are exact request freeze, registration without
dispatch, serialized native import preflight and then the original full
diagnostic. First ACK and batch-4 ACK baseline need bounded readback verification
as they publish. Preserve failed prefixes and missing receipts. This review
does not replace that verification or the eventual two final critics.

## Reviewed source hashes

Paths below are relative to `8-9-hh3d-3/zdoc/reviews/`. These are targeted
file hashes, not a new full-source sweep. README files were not included while
their writers finished documentation. No hash is an execution claim.

| File | SHA-256 |
|---|---|
| `20260918-gt06-s96-coupled-phases/coupled_phases.py` | `b1e311144b5beaad3fc0188b4d09e285351a4978502e64c0ac015122d4465ee0` |
| `20260918-gt06-s96-coupled-phases/register_task.ps1` | `691ea6b4cf3fffc3859ec5cf2522fad1338f6e43e71b89dbc889ae8f594fa859` |
| `20260918-gt06-s96-coupled-phases/test_coupled_phases.py` | `efd3952d4ed479ec863e469f546ebe952dd2e45b50c1d79d3424f59af8d5efd1` |
| `20260918-gt06-s95-result-prep/http-phases/phase_observer.py` | `9a79e5767f07674e80fb457b6d8f6326cb3558e9feb1d5d51884ad7784f5be57` |
| `20260918-gt06-s95-result-prep/http-phases/test_phase_observer.py` | `cb1e2427a0cd93d9ecdbcaebb0f7602c02a55faa12720aa3e67e564f0994c4b4` |
| `20260918-gt06-s93-sparse-attribution/diagnose_sequence_s91.py` | `5b93e33f9589c38889d8cc9ae6cf69e6c98d8e0624753ccf535b5e3a3a168cae` |
| `20260918-gt06-s93-sparse-attribution/launch_observer.py` | `aebbff3662c03f6e130354a0ea99a53f00da01f948b632c3fca9adbe48e0cad6` |
| `20260918-gt06-s93-sparse-attribution/patch_native_s91.py` | `f4226f40839e40579ae5c489cfd33800e3739bb6e280193c38a54414afaf2bc0` |
| `20260918-gt06-s95-native-isolation/object_probe_s95.gd` | `8a1ef457b6d4612fbf61176bc99598ec046d72c081e01c73665bb3237680784e` |
| `20260918-gt06-s95-status-recovery/source-current.json` | `7480a3cce54d1b596d40abdb633c509915554c23ecce91e2e86bc4ad81cf371d` |

Declared original source closure, required by launch-time checks:
`564e5b7877f49d33a1af84eaf3b3a7ddf4ea2f846c4161eb694c5c40514fc752`.
Unchanged profile:
`0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.
