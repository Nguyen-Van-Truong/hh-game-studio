# S83 sparse attribution analyzer

AUTHORITY=0. Diagnostic triage only. GT-06 remains open. No acceptance verdict,
runtime change, campaign retry or engine launch is authorized by this folder.

`analyze_attribution.py` uses only Python's standard library and emits JSON to
stdout. It does not write files, import the studio runtime, launch a subprocess,
probe live processes, or hash a complete raw tree. It is fixed to the S82 run,
51-file source manifest closure and profile digest stated in S83.

From the `8-9-hh3d-3` directory, once the coordinator has confirmed that all raw
writers have stopped:

```powershell
python -B zdoc/reviews/20260918-gt06-s83-analyzer/analyze_attribution.py --raw-root studio/.local/reviews/gt06-s82-attribution-01 --mode terminal --terminal-confirmed
```

If saving the stdout result, redirect only to a new file under this analyzer
review directory. Never redirect into the original raw directory. The explicit
terminal flag is a caller assertion, not a process-liveness check. The analyzer
also requires the child-terminal-cleanup and supervisor-return records before
enumerating snapshots or reading terminal logs. Those records alone cannot
prove that every process has already stopped.

For one light inspection during an active run, the default `--mode baseline`
reads only diagnostic/context, editor-start, `object-0000.json`, and
`attribution-04.json`. It does not enumerate later snapshots, hash logs, or
validate terminal records. Baseline mode reports `status=observation_only` and
`liveness=not_checked`; the analyzer does not infer current liveness from mode or
absent terminal files. The S83
worker already performed its single authorized baseline read; do not repeat it
merely to validate this tool while the engine remains active.

The baseline observed on 18 September contained 27,401 reachable identities,
71,128 ObjectDB objects and a 43,727 residual. Its 146 selected descriptors are
initial inventory, not 146 new objects. Counters before collection, after
collection and after publication were all 71,128. This is a baseline observation
only; it does not predict the diagnostic outcome. Coordinator-owned raw refs are
in `../20260918-gt06-s82-attribution/launch/baseline-observation.json`.

The output provides:

- Baseline ID/class membership reconciled against class and inventory counts.
- Per-owner TreeItem totals, with reachable owner identity checks.
- For each growth snapshot, added/removed/changed rows, class deltas, changes to
  known descriptor fields, and owner names/paths where the baseline exposed them.
- ObjectDB growth, reachable inventory growth and their residual, both since the
  previous snapshot and since baseline. Removed rows retain `still_valid` so
  lost reachability is not silently treated as deallocation.
- Before/after collection counter checks, exact-byte hashes of consumed points
  and publication receipts, run/batch binding, and joint/native/ACK hash checks
  when those artifacts exist. Missing post-publication or joint receipts remain
  explicit gaps, including a failure that occurred before an ACK could be sent.
- Actual target exits, separately recorded helper exits, Job state, handle
  release, child terminal cleanup and supervisor return. Nonzero exits are
  retained as facts and are not automatically rejected on an expected failure.
  No target exit is invented from a helper exit, empty Job, or process absence.

`status` is `observation_only`, `terminal`, `error`, or `no_reproduction`. Liveness
is explicitly `not_checked`; terminal status is based on caller confirmation
and the recorded terminal receipts, not a live process probe. A positive
ObjectDB delta gives `run_outcome=positive_objectdb_growth_observed`; it is not
itself proof of a leak or its cause. `no_reproduction` requires a completed
35-batch diagnostic record, bound joint counter receipts and recorded successful
host/editor/import target/helper exits with empty closed Jobs. A partial failure
with no growth is an error observation, not nonreproduction of the full sequence.

Exit 0 means analysis completed, even if the diagnostic failed or exits are
missing. Exit 2 means malformed/mismatched evidence prevented analysis. Always
read `status`, `run_outcome`, `integrity_gaps` and `cleanup_gaps`; do not treat the
analyzer's exit as the diagnostic's exit.

Limits retained deliberately:

- The probe is a partial reachable census. Equal ObjectDB counts can conceal
  identity churn; nonreproduction never proves no leak or a repair.
- Most baseline descriptors are omitted even though ID/classes are complete.
  A changed row can therefore lack its old descriptor. Owner movement cannot be
  fully reconciled for such rows; the output names those unknowns.
- Publication receipts contain no snapshot digest or PID. The analyzer hashes
  observed bytes and checks run/batch/counter binding, but cannot retroactively
  create a producer-signed snapshot-to-receipt digest.
- The supervisor's return record is not its actual exit. This runner records no
  actual exit for its own windowless supervisor; that gap stays explicit.
- Runtime manifest closure is checked; all 51 source file bodies are not reread.
  Named helper/overlay bytes and executed invocation bindings are checked. There
  is no complete execution-closure or raw-tree preservation claim.
- This is not the campaign validator: it does not reassemble samples, assess all
  latency/RSS limits, validate every native cycle, or supply a critic signature.

The initial terminal invocation, `analysis-attribution-01.json`, failed because
the analyzer incorrectly required positive decimal InstanceIDs. The raw baseline
contains 1,099 negative decimal IDs. The corrected analyzer accepts nonzero
signed 64-bit decimal strings, retaining the IDs exactly as written. The failed
result and its original source, README and static receipt remain byte-for-byte
in `superseded-derived/`, bound by `pre-repair-preservation.json`; the original
failed result has not been overwritten.

After the coordinator confirmed the diagnostic was terminal and authorized
tests, all ten focused synthetic tests passed (`tests-01.json`, actual exit 0).
Coverage includes signed baseline/growth IDs, malformed ID rejection, baseline
versus growth, churn with zero inventory net, changed owner descriptors,
malformed/drifting counters, class census mismatch, digest tampering, wrong-run
publication receipts, and failure to verify growth with a missing publication
receipt. The final static AST/compile check is in `static-validation.json`.

The new terminal analysis is `analysis-attribution-02.json`; its actual analyzer
exit was 0 with empty stderr, recorded in `analysis-attribution-02-run.json`.
Its diagnostic verdict is `status=error` and
`run_outcome=diagnostic_failed_without_attributed_growth`: the existing child
failure is `CAMPAIGN_RSS_GROWTH` at batch 5, after six captured batches. The sole
attribution snapshot is the valid batch-4 baseline; no growth snapshot exists.
The analyzer does not turn that partial failure into full-sequence
nonreproduction. Its snapshot analysis does not independently establish all
intervening ObjectDB values; the coordinator's joint/sample review is separate.
Recorded cleanup Jobs are zero/closed, but editor actual target exit and
supervisor actual exit remain explicit missing receipts. No engine was relaunched
and no runtime or original raw evidence was edited.
