# S95 GT-06 dependency and next-proof checklist

AUTHORITY=0. DRAFT_ONLY. No acceptance, final closure PASS, critic signature or
permission to dispatch a run. Paths below are relative to `8-9-hh3d-3/`.
This inventory reads the six-file `ad81e944^..ad81e944` diff, recorded source
maps, S83 requirement mapping and S81/S93 reuse notes. It performs no source
hash sweep, engine/test execution, process query/control or live-result audit.
The tools plan remains authoritative; GT-06 is open and GT-07 stays closed.

## Exact delta and affected evidence

Commit `ad81e9444313e6d5cf5bc084d5f771582f16c60c` changes only these six paths
under `studio/`:

| Path | Change and narrow proof obligation |
|---|---|
| `tests/replay/benchmark_commands.py` | Persist each lookup's copied, sanitized `transport_failure` before a retry clears it; command-batch schema becomes 1.3.0. Preserve actual response times and same-ID reconciliation. |
| `tests/replay/benchmark_assembly.py` | Require the new field; validate fixed endpoint/stage/category/elapsed fields on transport UNKNOWN, null otherwise, and elapsed within the enclosing attempt plus the existing microsecond truncation allowance. Reject schema 1.2.0. |
| `tests/replay/benchmark_transport.py` | Use `perf_counter_ns` for diagnostic elapsed time, matching the producer's Windows QPC clock domain. Wire behavior, timeout/retry policy and production transport remain unchanged. |
| `tests/replay/test_benchmark_commands.py` | Cover retained per-attempt failure, recovered actual disconnects, no duplicate submission/effect and persistence before guards. |
| `tests/replay/test_benchmark_assembly.py` | Cover schema, mandatory/null/fixed diagnostic fields, timing bounds and rejection of fabricated progress. |
| `tests/protocol/test_transport_observation.py` | Cover transport stages/categories, diagnostic reset, QPC timing and accepted wire/error equivalence. |

The first three are members of the recorded formal 51-file source map; the
three test files require their own executed-test provenance. The recorded S95
formal closure is
`564e5b7877f49d33a1af84eaf3b3a7ddf4ea2f846c4161eb694c5c40514fc752`
in `zdoc/reviews/20260918-gt06-s95-status-recovery/source-current.json`.
That is read metadata, not a fresh working-tree equality finding here.

- Affected unit proof already exists: S95 `unit-02/invocation.json`,
  `unit-stderr.txt`, `unit-stdout.txt` and `capture.json` record 85 tests,
  zero failures/errors/skips, target 43688 exit 0, helper 31992 exit 0,
  verified tree and unchanged source. Modules are `test_benchmark_commands`,
  `test_benchmark_assembly`, `test_benchmark_campaign` and
  `test_transport_observation`. Preserve failed `unit-01`; it exposed the
  clock mismatch. Reuse unit-02 only at its declared dependency bindings;
  do not rerun it merely to rewrite a report or sum it with overlapping U81.
- F08/F12 benchmark-client supplements and F13/F14 full campaign consumers
  are affected. Old schema 1.2 artifacts remain historical; do not fill missing
  failure fields with null, infer their category, or feed them to schema 1.3
  as if newly produced. Fresh coupled measurement is still required.
- S95 HTTP attribution is supplemental: 200 commands/20 groups, no reproduced
  2s event. Its 48-file closure `1d7726ca9af7c05989aa5bcd4b74372ab386af41c0ca8d7d43381df1752ad7b7`
  excludes formal-map `godot-addon/bundle_staging.py`, `bundle_v2.py` and
  `fixture_profile.py`; the 48 shared entries match the recorded formal map.
  Its mock effects and instrumented timings do not prove native acceptance,
  full workload performance or the cause/fix of S93's timeout-like UNKNOWN.

## Candidate functional reuse, without remint by association

Path-only intersections were checked against all seven original S79 backend
174-file maps, both reviewer 5-file maps, S69 managed replay's 159-file map and
the accepted GT05 143-file map: **none contains any of the six changed paths**.
The four S69 separately pinned verifiers are unchanged by this commit too.
No import of the three benchmark modules was found in `studio/host/` or
`studio/reviewer/`. These observations establish this commit's narrow delta,
not current equality of every dependency. S81's earlier exact joins remain
historical observations and must retain their original identities.

| S83 requirements | Candidate original evidence | Remaining final join / remint trigger |
|---|---|---|
| F01–F06: asset→real input/Play, inspection/capture, fault→repair→replay | Accepted GT05; S65 fault and repair-02; S69 managed replay; relevant S79 functional/adversary lanes | Join original asset/command/source/PID/frame identities and S65 repair-02 causal anchor. Remint only if a consumed dependency or required evidence is actually changed/missing. |
| F07: perf export and statistic semantics | S65 original native/perf exports; separately scoped collector/schema/tests | Preserve original runtime label; exact collector/schema join does not promote historical native execution to the new campaign. F13 measurements remain open. |
| F08–F09: durable admission/UNKNOWN, reviewer and human Stop | S79 service/reviewer/adversary evidence; U79 service/index and unaffected U69 edge cases | Preserve backend/UI maps and actual callbacks. Use S95 unit-02 for the changed benchmark transport/producer/verifier supplement. |
| F10: readiness/reload identity | Scoped S80/U81 readiness evidence | Historical bounded readiness stays scoped. The new campaign must supply every current source-bound startup/reload/postcondition over 10×35. |
| F11–F12: faults, ownership, bounded queues and Stop priority | S60/S64 accepted owned fault cases, S69 scoped tests, S79 Stop/adversaries, U79/U81 supplements | Join exact consumer/verifier dependencies. Keep forced exits/missing historical receipts explicit; successful current campaign cleanup is separate fresh proof. |
| F13–F15: full metrics, sustained ownership, final seal/critics | No completed qualifying campaign supplied by these diagnostics | Fresh complete coupled campaign, full raw verification, final dependency/evidence seal and two new independent critics remain required. |

S79 original IDs are `gt06-s79-http-complete-01`, `gt06-s79-http-stop-01`,
`gt06-s79-saturated-stop-01`, `gt06-s79-revoked-result-01`,
`gt06-s79-stale-capture-01`, `gt06-s79-reviewer-complete-01` and
`gt06-s79-reviewer-stop-01`. Their maps are
`studio/.local/reviews/<run-id>/source-files.json`; reviewer maps additionally
use `reviewer-probe/source.json`. S69 is `gt06-s69-managed-replay-01`, with
`repair-replay.json#/verifier_sources`. GT05 uses
`zdoc/reviews/20260917-gt05-s63-audit/manifest.json`.

Do not relabel whole S68/S65 runtime or broad U69/U79/U81 test snapshots as
current. S93 `reuse.json` only supports unchanged S91 native probe/patch and
observer-test helper scopes; changed launch/source bindings stay separate.
S93 failed at batch 6 (2033.1318ms status gap), with baseline-only sparse data.
Its forced cleanup, absent inner editor exit receipt and absent operator Stop
latch remain recorded limits. Neither it nor the S95 native-only diagnostic
can supply formal coupled samples, irrespective of the native-only outcome.

## Ordered next-proof checklist

- After the owned diagnostic becomes terminal, root audits its raw counters,
  sparse captures, actual exits and cleanup before deciding repair or a coupled
  run. A native-only negative finding is limited by absent HTTP load and its
  different wall age. Preserve all diagnostic/failure packages byte-for-byte;
  this draft makes no claim about the ongoing diagnostic's outcome.
- At the next eligible freeze, record fresh run IDs, complete actual dependency
  membership and source/test/driver/verifier/schema maps. Use the S95 map only
  if its exact bytes still match; any later repair requires its own delta and
  affected proof. Carry S81's original functional maps forward through explicit
  path/hash and membership joins, including GT05 asset and S69 verifier pins.
  Recheck affected lanes rather than invoking S79's unrelated whole-snapshot
  verifier or rerunning every accepted native lane.
- Obtain **10 fresh host/editor pairs × 35 ordered batches** on one frozen
  source, toolchain, workstation and profile. Each pair keeps its identity;
  batches 0–4 are retained warmup, 5–34 measured. Every batch has 1000 HTTP
  commands at 50/30/20 plus auxiliary Cancel, 100 real native
  create/undo/save/reload cycles and ready/start/joint/ACK joins. Preserve
  7410s/run, profile `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`,
  native index 1.3.0 readiness, four-frame/1.1s settle and real serialization
  readback. No partial-prefix assembly, altered workload or concurrent heavy
  engine/test lane supplies this proof.
- Verify command schema 1.3.0 and all per-attempt observations with the frozen
  validator. Require actual inspect/Stop receipt p95 ≤500ms, status gap ≤2000ms,
  no duplicate/lost effects and all existing profile gates. Memory baseline is
  exactly batch 4 post-batch-quiescent per role/counter; every measured batch
  requires host/editor RSS ≤110% of its baseline and host OS handles plus
  editor objects/resources/OS handles ≤their baseline. Even one above-baseline
  count fails; no reset/subtraction/averaging or plateau exception. Missing
  required counters are GAP; only host objects/resources have profile N/A.
- After scheduler terminal/no instances, bind effective task/request/launch/
  interpreter identity and externally observed supervisor exit. For every run,
  independently bind actual host/editor/import target and helper exits, Job
  zero/closed, released owned handles and post-finally
  `child-terminal-cleanup.json` schema 1.0.0. Require 35 completed batches,
  null primary error, no cleanup errors, stopped heartbeat/threads, closed
  sockets/cache/index and released constructor/editor/probe ownership.
  Child host/supervisor exit fields intentionally stay null; external receipts
  must supply them. Scheduler/helper success or self-written return is not an
  actual target-exit receipt. Keep operator Stop evidence distinct from Cancel.
- Resolve F01–F15 using S83 `requirements.json`: seal all executed sources,
  test/driver/verifier/schema bindings, exact raw byte references and excluded
  raw locators, original asset→fault→repair→replay chain, prior failures and
  explicit limits. Keep source, canonical profile and raw-file hash domains
  separate; preserve Git/evidence bytes and explain warning/error/leak gaps.
  Correct adequate derived evidence from retained raw without unnecessary
  engine remints. Two new independent critics must issue PASS/TICK=yes on
  the same final manifest before coordinator acceptance or GT-07 dispatch.

Reference anchors: `20260918-gt06-s81-admission/dependency-impact.md`,
`20260918-gt06-s83-mapping/{requirements.md,requirements.json,seal-checklist.md}`,
`20260918-gt06-s93-sparse-attribution/{README.md,reuse.json}` and
`20260918-gt06-s95-status-recovery/{README.md,source-current.json}` under
`zdoc/reviews/`. The current tools plan's exact baseline rule supersedes the
older S83 shorthand “no steady retained-resource growth”; it does not relax it.
