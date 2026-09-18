# S95 — preserve S93, isolate lookup delay and ObjectDB attribution

AUTHORITY=0. Diagnostic only; no benchmark acceptance or final critic verdict.

## S93 terminal failure

`gt06-s93-sparse-attribution-01` ended 2026-09-18T14:54:47Z after about629s.
Seven captured batches0–6, no full run. `CAMPAIGN_STATUS_GAP` at batch6:
host gap2033.1318ms >2000ms; native579.328ms, native start permit514.287ms.
`gap-analysis.json` binds the exact failing command and command artifact hash.

Command `b6.inspect.4`: admission receipt641389534598us → lookup returns
UNKNOWN641391567730us. Projected difference2033.132ms differs from original
nanosecond-derived value by0.0002ms. Lookup started641389564757us, lasted
2002.973ms; the next same-ID lookup COMMITTED/READBACK_CONFIRMED. Full inspect
latency3246.0636ms. Completion of this command does not erase the failed gate.
New schema1.2 contains discovery/lease receipts, so this is not S91's omitted
setup response. Discovery3.161ms and lease498.036ms were outside the failing gap.

The ~2s duration is consistent with the default client timeout, but UNKNOWN
also represents other socket/HTTP failures. Client returned an uncertainty;
it is not proof of a server response. Per-call sanitized stage/category existed
in memory but a successful retry reset it before the producer persisted the
batch. Preserve raw absence, do not reconstruct exception/stage after the fact.
Underlying disk/lock/CPU/memory/network cause is still unproven.

## Observation regression caught by the owned unit lane

`unit-01` ran78 tests:77 passed, one new actual-disconnect timing-bound test
failed. Target11796 actual exit1, helper39924 actual exit0, tree verified;
all tracked studio source hashes unchanged during the lane. Retain this failure.
It exposed two clocks: transport diagnostic elapsed used monotonic_ns, while
the enclosing producer used perf_counter_ns. `clock-info.json` establishes this
Python3.11.9 Windows runtime uses GetTickCount64 (15.625ms resolution) versus
QueryPerformanceCounter (0.0001ms). A diagnostic15ms inside a6.323ms interval
was therefore possible without an actual out-of-bounds call duration.
Use the same high-resolution clock for the supplemental transport measurement;
keep the strict timing bound. This does not alter S93's status-gap measurement,
which already used perf_counter, or reconstruct its missing per-attempt metadata.

## Cleanup and preserved evidence

Retained external observer handles record supervisor12544/host10984/helper19080
exit1; editor33152/helper30580 exit2 from forced cleanup, not natural success.
Outer/host/editor Jobs zero and closed, retained process handles closed, cleanup
errors empty. Inner editor-host/process-exit.json remains absent; external
receipt is separate evidence, not a rewrite of inner TARGET_EXIT_NOT_RECORDED.
Observer does not self-prove its actual process exit. Independent scheduler
query state3/result1/noinstances is stored in scheduler-terminal.json.
Task retired14:58:03Z only after terminal/raw preservation; deletion receipt is
a separate supplement and does not change the frozen failure manifest.

`seal_s93.py` preserves96 exact copies and90 declared raw artifacts, then checks
all51 frozen runtime files,6 helper copies and observer manifest. Manifest SHA256:
`ca7e46b7fb7cbfb0ee8c81825c7a262afac80d7dbe2ae0167c01f9368c5de4fc`.
Verify from repository root:
`python -B 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s95-status-recovery/seal_s93.py --verify`
Raw and exact-copy domains remain separate; no failed sample goes to F13/F14.

Sparse baseline only, no growth capture. Joints4–6 Objects71128/resources6;
baseline sparse phase Objects71127 is a different lifecycle point. This neither
explains S86+2 nor establishes no-leak. Stop latch absent; seven command Cancel
probes were CANCELED_BEFORE_APPLY/no_effect, not an operator Stop acceptance test.

## Next work and lessons

Three Astra ultra workers split raw interval analysis, per-attempt observation
repair and cleanup/short HTTP attribution preparation. Implementation reviews
do not count as independent final critics. Root integrates and serializes runs.

- Retain sanitized lookup failure with its own attempt before retry overwrites
  it; enforce structure and timing in the evidence validator. Keep timeouts,
  retry budget, UNKNOWN semantics, status timestamps and all acceptance gates.
- A bounded copied-history HTTP probe can locate time in snapshot/reload/append/
  lock phases without launching Godot or changing durability. If no stall is
  reproduced, report that limit rather than claim the cause was fixed.
- Prepare a separate native-only35×100 sparse diagnostic to investigate editor
  objects without HTTP aborting observation. It is a changed experiment, not
  continuation of S93 or formal benchmark. Shorter wall age and absent HTTP load
  limit negative conclusions; original coupled profile must still pass in full.
- Keep this prefix and fix the affected lane; do not repeat the full coupled
  run blindly, synthesize progress stamps, relax limits or alter other apps.

## S95 verification update

Source committed as ad81e9444313e6d5cf5bc084d5f771582f16c60c. The coupled
51-file source closure is564e5b7877f49d33a1af84eaf3b3a7ddf4ea2f846c4161eb694c5c40514fc752;
source-current.json verifies Git HEAD bytes. unit-02:85/85, actualtarget43688/
helper31992exit0/treeverified/sourceunchanged. This is affected-unit coverage,
not a new complete coupled benchmark or acceptance.

HTTP attribution run-01 finished200commands/20groups with actualtarget8824/
helper13900exit0 and verified cleanup; maxstatusgap401.4742ms. No2s event was
reproduced. The HTTP source closure/map is separately frozen and must not be
called identical to the51-file campaign closure. See its analysis for scope.

Native smoke01 completed5x1, import54888/editor26460actualexit0; child37824exit0,
Jobszero/closed/handlesreleased. This reaches baseline only. A subsequent
read-only preflight found a process-start publication race and census hook after
the recorded memory time/heartbeat. Keep smoke01 bytes; repair only the helper
and run a new smoke02 before the long diagnostic. No runtime/profile change.
