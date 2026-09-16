# Resumable frozen unit matrix

The runner is an audit controller, outside the studio runtime closure. It preserves the six existing partitions: publication journal V1, V2, V3, V4, V5, and every other discovered `tests/godot/test_*.py` test. Journal lanes retain 360-second limits; `other` retains 600 seconds. Default concurrency is one to avoid competing native storage loads; `--workers 2` is available when the coordinator explicitly chooses concurrent lanes. There is no automatic unbounded retry.

After the coordinator releases the execution slot, run from the repository root:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s54-audit/run_unit_matrix.py --output 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s55-units-01 --runtime-package 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s55-source-01 --workers 1
```

Resume the same package with the same controller bytes:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s54-audit/run_unit_matrix.py --output 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s55-units-01 --runtime-package 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s55-source-01 --workers 1 --resume
```

`--runtime-package` verifies the complete file map, closure digest and manifest bytes before importing the referenced bootstrap runner. No runtime file is copied or changed. Omitting the option on a fresh output retains the original freeze-and-copy behavior. On resume the option may be omitted, in which case the recorded reference is used; supplying a different reference is rejected even if its bytes match. Frozen-source, reference, invocation or controller drift rejects resume. The legacy S54 units01 controller/schema cannot be imported as reusable proof; its incomplete capture remains unchanged.

Each attempt owns `attempts/<lane>/<number>/`, including raw stdout/stderr, raw child exit/PID, the bootstrap runner's wrapper/Job result, and an artifact hash seal. Resume revalidates every selected lane against those files, exact source/controller/invocation identity, the fixed lane predicate, a unique full test inventory, the completion count and actual exits. A stored `passed` flag cannot make a lane reusable. Failed, absent, interrupted, stale or corrupted attempts get a new directory; earlier attempt bytes are preserved. Each invocation preserves `rounds/<number>/capture.json`; only the top-level latest `capture.json` is atomically updated. An OS-held controller lock prevents simultaneous execution into one output and releases if the controller dies.

The latest capture stays `passed=false` while running and becomes true only after all six verified inventories agree, their selections are disjoint and cover the full inventory, all tests complete without errors/failures/skips, and the frozen runtime/controller metadata remain exact. Origin checkout equality is reported separately before and after the run; execution authority is the explicitly named immutable snapshot. A component PASS never means GT-03 acceptance or proof for a changed live checkout. Contradictory full inventories fail the aggregate and require investigation; the controller does not choose one as authoritative or hide the mismatch by summing counts.

Validation: [unit-runner-validation-01/report.json](unit-runner-validation-01/report.json) records **23/23 inert tests**, actual Python exit 0, unchanged controller/test hashes, and a read-only verification of all 176 files in S55 closure `3a220b51105166274bad4bde950f4cc1d975e87b009b66e52428fad9dc27b02e`. The tests cover selective timeout/failure retry, completed-lane reuse, missing/tampered/stale evidence, forged success fields, raw PID/exit mismatch, duplicate/missing completion markers, inventory/count mismatch, source/controller/reference drift, incomplete controller output and capture state. They use a fake runner and launch no studio tests, Godot, Linux container or native storage. The full matrix was not run by this lane.

Controller SHA256: `f285ddba8fe71bfc9fd7bbfedf0ba13f04fafb741cbb496d039d6e50380dfc7a`.
