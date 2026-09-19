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
