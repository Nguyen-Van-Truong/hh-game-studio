# S77 object diagnostic launch review

Scope: read-only inspection of `diagnose_objects.py`, `object_probe.gd`, and
the existing process-owner interfaces. Python AST parsing succeeded. No engine,
tests, GDScript parser, or workload was launched by this reviewer. The coordinator
dispatched while review was in progress; the launched helpers remain unchanged.
This is supplemental review, not either independent GT-06 acceptance verdict.

1. **Outer result can report shell success without an actual target exit.**
   `diagnose_objects.py:44` returns `result['exit_code']` directly. The reused
   `run_fixture.run_process` sets that value to `None` when no target receipt
   exists, including a timed-out target. `SystemExit(None)` then exits zero.
   The helper also does not reject a nonzero wrapper exit, unverified tree, or
   timeout independently. After this frozen launch is terminal, require an
   integer actual target exit and explicitly check wrapper exit, timeout, and
   tree verification before reporting success. The coordinator has confirmed
   that it will independently require actual target/native exit 0, wrapper 0,
   `tree_verified=true`, and `timed_out=false`; shell exit alone is insufficient.

2. **Constructor cleanup ownership is not recovered on its failure path.**
   In `child()`, assignment to `owner` occurs only after `BenchmarkProcess(...)`
   returns. That constructor attaches `cleanup_owner` to the raised exception
   when initial setup or cleanup fails, but the handler at line 135 never adopts
   it. Consequently `finally` can see `owner=None` and miss the retained owner.
   The outer owned Job still bounds the descendant processes, but that is not
   proof that the inner Job and wrapper handles were checked closed. Future
   helper code should adopt the exception's retained owner, retry bounded
   cleanup, and preserve any cleanup exception separately from the initiating
   failure. Do not infer clean ownership on this failure path from outer exit.

No additional concrete syntax/type blocker was found by inspection. The probe
stores primitive descriptions, not Object/RefCounted references, in its retained
maps. Its before/after counters and scan flags help detect observation effects,
but do not establish a complete ObjectDB census or causal leak attribution.
The existing 540-second child watchdog and 600-second outer watchdog bound this
diagnostic. Inventory traversal itself has no per-traversal node/depth budget;
the 512-point/8-MiB-point/128-MiB-total limits apply only after collection. A
traversal failure or watchdog kill must remain a failed diagnostic, with no
object-stability claim. This limitation does not require mutating the running
fixture or delaying its already dispatched bounded observation.
