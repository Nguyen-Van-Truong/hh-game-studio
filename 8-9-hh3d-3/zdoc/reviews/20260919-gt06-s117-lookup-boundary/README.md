# S117 lookup-boundary diagnostic

AUTHORITY=0. Diagnostic-only packet for the preserved S116 stock failure.
It uses a fresh ID and the unchanged source closure/profile/workstation. The
child keeps the stock native benchmark, original 1000 HTTP + 100 native mix,
original gates and original status-gap limit. It adds only the already-reviewed
host Journal timing wrapper plus fixed-label SQLite BEGIN/COMMIT/ROLLBACK timings and stops after the 11th original gate or the first
original failure. It cannot produce F13/F14 samples and makes no repair or
root-cause claim.

Why this boundary: S116 failed at batch 10 with a 2041.7971 ms host
status/lookup gap while its native ACK was 780.821 ms. S115 stopped at batch 6
without reproducing the gap. S117 therefore extends the same coupled
instrumentation to batch 10 so the lookup boundary can be compared without a
formal retry. Preserve S116 unchanged and do not run another formal campaign
until this packet is interpreted.

Run exactly once:

```powershell
python -B lookup_boundary.py --check
python -B lookup_boundary.py --launch
```

After launch, read raw child failure/result, HTTP phases, actual exits, Job /
handle cleanup, source pins and the final packet. A boundary exit is diagnostic
only; missing target exit remains UNKNOWN and must not be inferred.

The additional transaction controls preserve original arguments, return values, exceptions and SQL execution. No SQL parameters/results are recorded. Wall time includes scheduler/I/O wait and cannot identify the device cause. Nested timing spans overlap.

Static validation: 7 controls cover original-gate precedence, cleanup errors, helper layout and SQLite call/exception passthrough. Source53/native/profile pins verified before launch.

Recovery -02: -01 failed in original Job limit readback before releasing its target. It produced no engine workload and remains in failed-launch-01/. Values causing mismatch were not retained. The direct no-engine Job probe subsequently passed the same limits; no cause is asserted. The repaired launcher uses fresh ID -02 and records fixed configure readback fields on future failure without bypassing it. Original validation.json applies to -01; validation-02.json applies to -02. The earlier ad hoc console probe passed an integer instead of Owner and has no acceptance value.

Continuation -03: -02 failed original import wall20s with zero batches, preserved in failed-launch-02/. S118 import-only verbose probe completed in11.359s under original stage limits and unchanged source; this is a non-reproduction, not a repair. -03 executes the still-unmeasured lookup experiment with original nonverbose import. No failed IDs or raw are reused; no formal campaign starts.
