# S100 driver integration guidance

AUTHORITY=0. Read-only advice for the coordinator's work in progress; not an
independent final critic verdict, source acceptance or permission to change gates.
Only this review directory was written by this worker.

The smallest useful first-class integration is the existing bounded PhaseRecorder
and its observed Journal/Host/Client/HTTPConnection wrappers, created once per
CommandProducer and retained through close. Use the planned
`studio/tests/replay/benchmark_http_phases.py`; retain fixed enum fields, primitive
IDs, QPC timestamps, numeric socket pairs, active-span bound, eviction/overflow
counters and one immutable first lookup failure. An instance-local connection
factory in BenchmarkFixtureClient avoids a process-global HTTP monkey patch.
Existing admission/lookup reconciliation, response sampling, fsync, hash trust,
lock semantics, profile, command/native counts and deadlines must stay identical.

The short probe justified closing the missing-observation gap, not a timeout fix.
Do not transplant its AST rewriting or per-chunk read/hash timers into the first
formal integration. Whole snapshot/reload/append/guard/client/server phases locate
the next failure sufficiently to select a later narrow investigation. They cost
less and avoid a separate instrumentation framework. Keep the short probe's
read/hash percentages as supplemental evidence only.

The fixed 8192-event/64-active-span ring is bounded independently of batch count.
Its first-failure copy is another bounded allocation. Construct the recorder before
the initial host RSS sample; keep it alive throughout warmup and measured batches.
Do not clear it to hide growth, subtract observer memory/time, increase thresholds,
or exclude a batch because instrumentation made it slow. Normal ring eviction is
expected; zero dropped active spans is a different fact from zero evicted events.

## Driver and source boundary

`run_native_benchmark.source_files()` includes imported Python modules beneath
`studio`, while `run_benchmark_campaign.source_files()` adds campaign fixed files.
Both parent and child must import the HTTP helper and import observer before their
first source-map collection. Importing them only in run_child or after freezing
creates a parent/child mismatch or an uncovered runtime dependency. The existing
`load_fixture()` import remains necessary for the three dynamic factory/bundle
files. Its import alone starts no engine.

For the planned changes, source51 gains these two runtime files:

- `tests/replay/benchmark_http_phases.py`
- `tests/replay/benchmark_import_observer.py`

The nominal fresh driver closure is therefore 53 files if neither helper imports
another previously absent local module. Benchmark commands, benchmark transport
and the campaign driver already belong to source51; their changed bytes change
the closure but not that file count. Verify the actual fresh-process map and every
new transitive import, not just the number 53. Unit-test imports can make this
dynamic collector include unrelated test modules, so do not mint the official
closure from a test process. Test source belongs in the review/test closure.

Bind both new helpers in parent/child source equality, frozen source copies,
owner expected_source_files, context source_closure_sha256, native binding input
and run-capture hashes. A new closure requires a fresh campaign ID. It cannot
resume S98 or transfer old source signatures. Native script/profile bytes and
F13/F14 workload need no change. No Godot/Blender/platform implementation change
is necessary for this telemetry integration.

## Exact evidence contract

Use the names already added to the coordinator's driver:

| Artifact | Publication point | Required binding |
|---|---|---|
| `http-phases-final.json` | After all producer/owned-role closes in `_finish_child_cleanup` | kind=http, run ID, source/profile hashes, exact context reference, recorder host PID |
| `import-observation.json` | `_observed_import` finally after observer.close | kind=import, run ID, source/profile hashes, exact context reference; observer sample/process provenance |
| `child-terminal-cleanup.json` | After all close and observation attempts | Original primary failure plus sanitized secondary errors; no inferred self/target exits |

Do not add fields to the strict command-batch, sample or run-assembly schemas.
The observation sidecars belong in the owned-run artifact manifest and
`verify_run_capture` required-file set. Their actual bytes/hashes must be verified
again on resume; wrapper fields alone do not prove artifact integrity. Keep the
existing actual target/helper exit, Job/tree/handle and terminal-cleanup verifiers.

`verify_observations` should validate envelope shape/version/kind, exact filename,
run ID, source/profile closure, context reference and availability. Bind HTTP PID
to the already verified child host identity, and check the inner recorder schema,
fixed bounds, field types and nonnegative counters sufficiently to reject an empty
or wrong-schema dictionary. For import samples, use the import observer's defined
identity/schema contract rather than inventing process-exit equivalence. A snapshot
is not a target-exit receipt. Wrong/missing/truncated/cross-run observations cannot
be promoted as complete evidence.

Do not turn telemetry into a second latency verdict: a recovered transport failure,
expected wrapper `raised` outcome, nonzero normal eviction, or `first_failure`
presence must not override existing benchmark status-gap/latency/effect gates.
If correlation has missing identities, dropped spans or ambiguous port/time joins,
mark attribution incomplete; never infer a missing phase. No negative evidence
claim follows merely from an empty retained tail. The original gates remain the
acceptance decision; observations make their evidence reviewable.

## Cleanup and failure precedence

The current driver placement after producer.close is appropriate: it includes
close-phase work and observes remaining open spans. It must still attempt HTTP
snapshot/publication after any independent owner close raises. Snapshot or disk
write failures append a sanitized secondary error and must not replace a primary
benchmark/import failure or skip another close/receipt. With no primary failure,
an observation persistence failure cannot return success; retain the owners and
surface the existing cleanup/incomplete path. This is evidence completeness,
not a changed benchmark threshold.

Keep the first lookup failure capture inside the client wrapper before returning
to the producer, so the original retry cannot erase it. Persistence occurs outside
delegated HTTP/journal operations and outside their locks. Do not stop a formal
campaign merely because a first failure was observed: the short probe's early-stop
policy must not be copied. The formal run follows its unchanged timeout/retry/gate
decisions.

If producer construction fails, recover any existing cleanup_owner and keep its
recorder when available. When no producer ever existed, publish explicit unavailable
telemetry with its reason; no fabricated empty-success trace. Import-observer start,
close and snapshot failures need the same primary/secondary error ordering. A hung
or hard-killed host may never publish its final in-memory ring; retain that as an
explicit missing-evidence limit, not zero failures. The current minimal design does
not guarantee crash-surviving streaming telemetry.

## Focused validation boundary

Port the existing 12 fake recorder tests covering call delegation, original
exception/guard suppression, first lookup after a nonlookup failure, socket identity,
active spans at failure, ring eviction/overflow and secret absence. Add the small
integration cases below to existing affected suites rather than another long
diagnostic campaign:

- `test_benchmark_commands.py`: recorder always present, fixed ownership across
  batches, per-instance connection selection, first-failure window survives normal
  same-ID retry/metadata reset, unchanged response timestamps/effect chain/timeouts,
  and constructor/close ownership. Existing file had 19 test methods at audit time.
- Protocol `test_transport_observation.py` and new helper tests: inherited wire
  behavior/results/exception categories remain identical; no global HTTP patch.
- `test_benchmark_campaign.py`: both required sidecars captured and hashed; missing,
  changed, wrong-kind/source/profile/context/PID/inner-schema evidence rejected;
  nonzero normal evictions accepted as bounded retention. Audit snapshot had
  29 methods, including coordinator changes in progress.
- `test_campaign_terminal_cleanup.py`: snapshot/write failures with and without a
  primary error, failure before producer construction, other closes still attempted,
  explicit unavailability, existing terminal files never overwritten. Audit snapshot
  had 15 methods, including changes in progress.
- `test_benchmark_campaign_stop_completion.py`: the four existing Stop cases remain
  relevant because a new finally operation must not bypass Stop or mask its failure.
- `test_benchmark_import_observer.py`: bounded sampling lifetime, constructor/start/
  close faults, no retained target-handle loss, import primary-error preservation,
  deterministic availability/counter identity contract.

Counts are file snapshots, not a test verdict or promised total. Run meaningful
affected suites after integration and one compact formal-path inert/owned binding
check as appropriate. Existing strict assembly/profile suites are useful unchanged
regression guards (33 and 19 methods respectively at this inspection) if the driver
touches their interfaces. Re-run Journal trust suites only if its implementation
changes; the wrapper tests must still prove full delegation. Reuse native reader/
functional evidence only where the complete dependency rule permits it; it does
not certify this new source. Freeze and independently review the final closure
after the scoped checks, then use the unchanged full campaign gates.
