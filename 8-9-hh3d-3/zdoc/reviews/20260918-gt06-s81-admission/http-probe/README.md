# S81 supplemental HTTP probe — prepared, not executed

AUTHORITY=0. The coordinator must review and launch this once against its
green frozen source. Preparation used static AST parsing only. No HTTP
listener, source import, copied journal, engine or test was started here.

`run_probe.py` accepts the already frozen source tree, reads every Python file
beneath `studio/` into a manifest, freezes both driver and owner source into a
new exclusive output directory, and calls that tree's unchanged generic
`build/bootstrap/run_fixture.py::run_process` with a **240-second hard Job
bound**. It records the actual target and wrapper exits, timeout and owned tree
cleanup returned by that owner. It never calls the Godot CLI. The child has a
210-second cooperative guard before each command, leaving cleanup headroom.
Neither bound is raised if the workload does not finish.

The child copies the exact S80 journal (15,586,409 bytes, 22,170 records;
SHA-256 `4d8ecb5bacd76a57d3137e9f812c36c3a6a759d4d51d41008627e9114ee1377a`)
into its new `commands/` directory through a local factory injected into
`CommandProducer`. A second factory provides a fresh distinct project ID,
counter and lease namespace. Old journal records remain intact; no original
runtime state or lease is restored and no old command is resubmitted.

The unchanged `CommandProducer.run_batch(0)` sends 1,000 commands in the original
500-inspect/300-reject/200-admit mix. Its original auxiliary Cancel after group
49 remains, including the existing 1,000 ms mock job delay. **No additional
delay or fault is injected.** Normal 2.0-second HTTP calls and the five-second
terminal lookup budget remain. SQLite stays synchronous FULL/DELETE. Journal
hashing, fsync, limits, retry and uncertainty semantics remain unchanged.

Fixed-label instrumentation wraps existing functions without duplicating their
logic: journal snapshot, canonical fsync, host dispatch, fault-probe lock path,
and response send. It retains count, sum, maximum and the three slowest timestamped
spans per label (at most 160 labels). No request body, header, token, session,
arbitrary exception text or arbitrary identifier is retained by the spans.
The new FixtureClient fixed failure category/stage survives in the unchanged
producer's failure report. Metrics overlap and cannot be added as disjoint
time. Instrumentation has overhead, and this is not a clean campaign sample.

The driver validates every loaded `studio.*` file after import and shutdown
against the entire frozen Python manifest, rejects modules loaded outside that
tree, and rechecks every frozen Python file at completion. This is an actual
loaded-module closure plus full frozen selection, not a 47/50-file assumption.
The owner separately binds the Python binary, driver, source manifest and
owned runner. Canonical journal prefix and original bytes are hashed again;
a complete batch must append exactly 1,403 records. Source files and original
journal are never written. Index disposal, listener fds, server/worker threads,
observer handle and retained producer state are recorded and checked.

Proposed invocation from the workspace root, **only after coordinator review**:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s81-admission/http-probe/run_probe.py `
  --source-root 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s81-admission/checks-01/source `
  --journal 8-9-hh3d-3/studio/.local/reviews/gt06-s80-campaign-01/run-00-attempt-01/commands/commands.jsonl `
  --output 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s81-admission/http-probe/result-01 `
  --run-id gt06-s81-http-probe-01
```

Use a fresh output and run ID for a subsequent authorized attempt; preserve all
previous outputs. A `SUPPLEMENTAL_COMPLETE` child or exit 0 does not establish
full benchmark PASS, native effects, GT-06 acceptance, or the cause of S80.
Review the outer capture and original failure as well as the child report.
