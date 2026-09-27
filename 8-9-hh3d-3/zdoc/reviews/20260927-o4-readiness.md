# O4 implementation readiness — 2026-09-27

AUTHORITY=0; FORMAL_ACCEPTANCE=false; GT06 remains IN_PROGRESS.

Owner decision b0802472 is implemented in benchmark_environment.py and the
campaign supervisor. No performance profile, timeout, warmup/status-gap,
counter or retained-handle v5 threshold changed. The current hardened source
closure is edb07f656dae02581f182291cfe4d0f946d4fa9c74f97cd7e208db3b1e0bcaf0
(54 files).
Profile remains 9dfa0ae003577e8607e28e722089328933d60e6cdb5b1ae1c5e978b3ad9d335e.

## Changes and limits

- Before each pair: available >=4 GiB, commit <=85%, no foreign Godot/Blender.
  App/Docker/WSL names are inventory only. All-process inventory includes top
  private bytes; inaccessible counters are explicit, not invented zeroes.
- Supervisor samples every 5 seconds outside the measured host Job. Native
  Job membership distinguishes owned engines from foreign ones; no PID/name
  termination. Continuous low RAM/CPU timers, commit threshold, sleep/resume
  and sample gaps fail closed. No sample can grant measurement PASS.
- Memory pressure is classified INFRA_ABORT only when external pressure is
  sufficient after removing campaign private bytes and owned inventory is
  complete. Otherwise PRODUCT_FAIL is retained without claiming a proven
  leak cause. A previously recorded child failure always wins. Missing sample
  cadence is HARNESS_FAIL; it cannot be hidden as an environmental PASS.
- KeepAwake restores the calling thread's original execution state. It does
  not override an explicit user sleep; sampled uptime/awake clocks detect
  sleep/resume. Timers are sampled evidence, not an uninterrupted OS trace.
- Samples are durably captured and replayed by the verifier, with coverage
  checked against actual owned-run duration. Stop receipt remains latched.
  Two recorded same-day INFRA_ABORT attempts block further dispatch.
- Each sample stream begins with an exact run/source/campaign binding header;
  replay validates that header, UTC timestamps, and inventory fields before
  applying policy. Observer/schema failures persist a bounded error and stop
  latch as HARNESS_FAIL instead of becoming an unexplained product failure.
- Both before and after preflight records are schema/resource validated before
  a completed pair can be resumable. A post-run foreign-engine observation is
  retained as failure evidence and never promotes a partial run.
- Interrupted S258 stays sealed. New runs require new IDs. Final two-model,
  same-hash critics still go through the owner per O4.3.

## Verification

- Intermediate broad benchmark suite: 219 tests, actual exit 0.
- Task/profile verifier suite: 30 tests, actual exit 0.
- Final changed-boundary plus terminal/historical/native regressions: 110
  tests, actual exit 0. These suites overlap; do not add their counts.
- Full replay suite after the binding remint, handle-lifecycle test repair and
  watchdog evidence hardening: 617 tests, actual exit 0. The Windows handle
  assertion now requires no net process-handle growth and separately verifies
  the probe handle/global owner are released; it does not assume unrelated
  runtime handles stay constant.
- Final native supervisor probe: gt06-o4-env-probe-02, matching closure above.
  Scheduler result 0/no instances, target PID 28876 actual exit 0, wrapper
  exit 0, natural Job/tree zero, held owners 0, clean stderr. This is a
  12-second Python ownership/watchdog probe, not a Godot formal run.
- Fresh 09:30:12Z preflight PASS: 8.27 GiB available, 72.39% commit, no foreign
  engines. The launcher must take another fresh snapshot immediately before
  formal dispatch. An old PASS is not continuing launch permission.
- Formal attempt `gt06-o4-formal-01` is retained as raw diagnostic only. It
  reached run-00 batch 27, then stopped at watchdog sample 977/978 after CPU
  stayed above 95% for the required 60 seconds. Parent classification is
  `INFRA_ABORT`, actual scheduler exit is 1, and owned tree is zero; no pair
  was accepted and the source was not rebound. A new campaign ID is required
  after the hardened source commit and a fresh idle-host preflight.

Raw, source/test copies and logs are archived under studio/.local/reviews;
20260927-o4-readiness-manifest.json records 90 members and SHA256 bindings,
including the final 617-test replay log and exit receipt. The archive is still
diagnostic evidence only and does not grant GT06 acceptance.
Only this summary and manifest are committed. Historical raw is unchanged.

## Reviewer corrections adopted

The 87912523 verifier checked status gap only from batch 5; current code checks
warmup too. The earlier coordinator report misread the review; O4.2 approves
the tightening. Exact count before O4 was 20/26 commits touching the plan.
Docker Desktop was the active WSL distribution, but Docker availability is
not AUTH-05 and preflight PASS is not evidence that the product has no bugs.

O2 details/gap table moved to studio/AUTHORING_STATUS.md on the isolated branch
at 0faf7c44. PATH_ISOLATION is the current label; old raw hashes/labels stay
historical. Integration must reconcile the existing O2 AGENTS.md divergence,
not merge its stale governance. No further DSL effect expansion is planned.

Win32 references: [execution state](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate),
[awake clock](https://learn.microsoft.com/en-us/windows/win32/api/realtimeapiset/nf-realtimeapiset-queryunbiasedinterrupttime),
[Job membership](https://learn.microsoft.com/en-us/windows/win32/api/jobapi/nf-jobapi-isprocessinjob).
