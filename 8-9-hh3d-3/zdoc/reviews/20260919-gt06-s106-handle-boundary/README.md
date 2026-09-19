# S106 owned handle-boundary diagnostic

This supplement keeps the frozen 53-file runtime, profile, original screen gates,
S103 generated overlay and S105 PSS adapter unchanged. It never supplies F13/F14
acceptance samples or a critic verdict. Existing S105 attempts remain immutable.

`owned_handles.py --check --run-id gt06-s106-handles-check-01` verifies exact
helper pins, base53 and overlay without launching an engine. `--preflight` with a
fresh S106 run ID runs one batch and captures b0. `--prefix` runs at most six
batches, captures b4 and b5 after either original-gate outcome, and stops. There
is no retry loop. The coordinator owns launch decisions; this package's author
does not launch engines.

The original gate runs once, then its outcome is written and read back before
PSS. Each snapshot binds the exact raw sample bytes, the b4 baseline for b5,
context, original-gate receipt, retained editor identity, base source/profile
and diagnostic helper closure. The original exception wins if instrumentation
also fails. UNKNOWN captures or unverified PSS cleanup stop the diagnostic.

Frozen per-run diagnostic modules live under this directory's `owned/<run-id>`
tree, outside `studio`, because the runtime source scanner includes all imported
Python files below `studio`. The parent owner's source map binds base53 plus
those diagnostic copies and context; the child retains the exact base53 map.
Reused helpers are hashed before execution and loaded from those verified bytes.
The copied adapter is loaded only after its diagnostic hash is verified.

The parent checks the unchanged bound Stop-request contract before process
dispatch, before each owner tick and after terminal detection. An existing valid
Stop prevents even the process-owner constructor. Timeout, Stop, constructor and cleanup errors
remain separate. Results inspect original failure code, exact snapshot set and
bindings, reconstruction of every 1000-HTTP/100-native batch, host target exit 1,
separate helper exits, child terminal state, Jobs, probe handles and threads.
`BOUNDARY_CAPTURED` means the diagnostic capture
and checked teardown records exist; it does not mean benchmark PASS. An original
screen failure is `ORIGINAL_GATE_FAILURE_CAPTURED`. Missing evidence, arbitrary
Python failures or drift are `INCOMPLETE`.

PSS is after the completed sample, but native ACK immediately advances to the
next READY. Therefore a b4 snapshot may perturb b5 heartbeat/status-gap behavior.
No time is subtracted and no gate is relaxed. Native PSS calls cannot be
interrupted inside the adapter; its 15-second budget is soft around native calls.
The existing external owner deadline (180 seconds preflight, 1200 seconds prefix)
and bound Stop are the hard process boundary. Capture overhead remains observable.

The unchanged forced diagnostic teardown may leave the editor's actual exit
UNKNOWN even when the recorded Job/probe/thread releases are verified; helper
exit 2 is never substituted for it. The import wrapper's native process-handle
closure is not recorded by the unchanged import capture and remains UNKNOWN.
The outer runner cannot observe its own actual exit: that also remains UNKNOWN
in its result and needs a separate passive observer. No blanket all-handles or
all-exits claim is made. There is no post-idle series: safely delaying teardown
or extending the native workload would require a different diagnostic design.
There is no leak, object-identity or root-cause claim.

Run fake-only integration tests from the HH3D root:

```powershell
python -B zdoc/reviews/20260919-gt06-s106-handle-boundary/test_owned_handles.py
```

The tests use retained S105-03 sample/context/lifecycle shapes and the original
screen/Stop functions, with fake ownership and PSS. They never launch an engine
or call a native PSS API. Test artifacts exist only under temporary directories.
The relocated frozen-child test loads the real unchanged adapter then replaces
its capture call with a fake, and exercises prepare/probe/screen installation and
restoration. Raw-batch tests independently reconstruct all six S105-03 batches
and reject changed refs/counts. Summary-specific tests use reminted gate fixtures
and a separate fake reconstruction result so lifecycle tests remain isolated.

Static validation on 2026-09-19: 30 tests passed in 5.208 seconds, process exit 0;
the `--check` command above exited 0 and reported `STATIC_PINS_VERIFIED`, base53,
and `engine_started=false`. No engine launch or commit was performed by the
implementer. `.gitattributes` preserves exact bytes throughout this package and
future frozen per-run diagnostic copies.
