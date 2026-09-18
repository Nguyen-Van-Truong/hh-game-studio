# S95 supplemental HTTP attribution

Prepared only; no execution or acceptance is implied. Coordinator owns launch.
All generated files stay under this directory. One exclusive `run-01` is allowed;
do not delete or reuse it after any attempt.

After review, launch from the repository with the pinned Python:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s95-status-recovery/http-attribution/run_probe.py --launch
```

After the coordinator finishes/freezes the source repair, the launcher obtains
the complete CURRENT source map from `run_benchmark_campaign.source_files()` and
copies those exact bytes into its snapshot. It copies only historical S93
`commands/commands.jsonl`, plus current `run_fixture.py` as the owned runner.
It records the current source closure hash separately from S93 history provenance,
checks source hashes while freezing, records history/Python/probe hashes, and
checks current source, copied source and both history copies again after exit.
The child creates a distinct project/producer via the existing Journal and Host
factory setup, seeds only its new journal, and performs twenty original
`run_diagnostic()` groups (200 commands plus setup, lookup and cancellation).
The original S93 history is never opened for writing. No engine is started.

The run_fixture owner enforces a 105-second target deadline (below 120 seconds)
and retains actual helper/target exits, timeout and owned Job-tree observations.
Owner cleanup can add time after the target deadline. A timeout or missing actual
target receipt stays incomplete; tree zero never substitutes for an exit code.
This runner does not supply the S93 retained-handle observer's extra handle-close
receipt, so its narrower cleanup evidence must remain explicitly labelled.

Runtime-only subclasses call the original VerifiedJournal `_snapshot`, `_reload`,
`_append`, `_load`, `_writer_lock`, and host `_dispatch`. Lock wait includes the
existing mutex and OS guard; held time includes guard release. Original fsync,
timeouts, retry budgets, limits and locking are unchanged. The instrumentation
does add timing/aggregation overhead, including nested wrappers while held.

`child/command-NN.json` contains each existing producer's raw secret-free command
report. `child/report.json` contains per-operation count, returned count, total,
maximum, slow count, and at most 16 largest spans >=50 ms with monotonic times.
Names are fixed; no request arguments, credentials, bodies or exception text are
recorded by attribution. Spans overlap: do not sum reload + snapshot + lock-held
as separate elapsed time. Compare timestamps with raw lookup intervals.

Unexpected failures retain only a sanitized exception class and traceback frame
basename/line, at most three chained exceptions with sixteen frames each. Known
probe failure codes are preserved from an explicit allowlist; messages, arbitrary
arguments, locals and request bodies are excluded. A source mismatch includes a
validated relative source path. Launcher failures are written exclusively to
`launcher-error.json` and stdout; child failures go into its report or
`run-01/child-unexpected-error.json` and owned stdout. Existing error artifacts are
never overwritten.

`owned/capture.json` is the process evidence; `child/report.json` is diagnostic
attribution. This instrumented short HTTP-only run is neither a reproduction of
S93's environment/1000-command batches nor an F13/F14 acceptance dataset.
Non-reproduction does not establish absence or root cause of rare latency.
