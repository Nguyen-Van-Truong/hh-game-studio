# S81 bounded preflight review

AUTHORITY=0. Static preflight only; no final critic, PASS or TICK verdict.
No tests, native processes or runtime imports were run. No code was changed.

**No actionable defect found in the requested cleanup/transport scope.**

- Successful terminal state is compatible with its verifier. In
  `benchmark_job.py:353-388`, `finish()` checks actual target exit and natural
  zero-active state, calls `close()`, then writes the Job/handle snapshots.
  `close()` returns immediately once closed (`:433-435`), and
  `cli_job.Owner.snapshot()` contains stable stored state (`:223-229`). Thus
  the later terminal observations and encoded equality at
  `run_benchmark_campaign.py:732-741` do not introduce a clean-run mismatch.
  Target start/exit files use the required exact PID/exit-code shapes;
  `_editor_cleanup_state()` reads the stored helper return code without
  querying its released native handle. Producer close deliberately sets
  `failed=True`, which the verifier correctly does not treat as run failure.
- Failure propagation remains fail-closed (`run_benchmark_campaign.py:629-699,
  923-941`). Independent owners still receive close attempts after another
  close/snapshot fails. A body exception remains primary and keeps its cause;
  cleanup exceptions and retained owners are attached. A cleanup-only failure
  raises instead of returning success. The parent separately requires actual
  host/editor exit zero and verified owner captures; an earlier child-result
  file alone cannot make a finally failure resumable. Missing target exits
  remain unknown and never borrow the helper's exit code.
- The benchmark bridge does not change accepted core bytes. Its fault mutex
  protects only arm/consume, without host/journal/session or socket work under
  that mutex. The copied client method preserves request bytes, HTTP result
  limits, exception classes, UNKNOWN response and connection close behavior;
  added diagnostics use fixed endpoint/stage/category values. The producer
  uses one client sequentially, so its per-call observation is not shared
  concurrently within the campaign.
- The new bridge is eagerly imported by `benchmark_commands.py:38-40`, before
  parent/child source collection. `run_native_benchmark.py:98-115` includes
  every loaded local Python module; both campaign entry paths load the same
  dynamic fixture first. No missing benchmark bridge dependency was found.
  This does not substitute for the actual full campaign closure/exit evidence.

Reviewed current files equal the corresponding checks-02 frozen files:

| File under studio | SHA-256 |
|---|---|
| `tests/replay/run_benchmark_campaign.py` | `bb43ecc04c2de4872177a440eb071d533efdaa9e8194f62b4e0907bad8d4b252` |
| `tests/replay/benchmark_transport.py` | `87875809baa4845fcffba8e2c7d82f7a5bce833099c89d4852f2aab931c34df0` |
| `tests/replay/benchmark_commands.py` | `707b6f9a9291214d9ee848d77f1e4a3dc2267de5f2aeb5e48fa4365866a842c9` |
| `tests/replay/benchmark_job.py` | `be424a6f37ae573ac4bf40954b31017025daee2147699c80b05f9a0ab70e1611` |
| `tests/replay/run_native_benchmark.py` | `e6b0f8e9711ac881cfa65b4537232c685ff577af0a13778a51cc54999b1c1fc7` |

Limit: the successful full campaign and its post-finally verifier path were
not executed in this review. Existing inert tests and the bounded HTTP probe
are not that end-to-end evidence. Historical accepted source preservation is
recorded separately in `dependency-impact.md`.
