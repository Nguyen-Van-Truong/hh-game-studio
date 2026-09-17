# Campaign02 retained failure evidence

**FAILED; zero completed runs; no benchmark or GT06 PASS.**
Campaign `gt06-s70-campaign-02`, attempt `gt06-s70-campaign-02.r00.a01`,
stopped at its first measured sample (batch5), after five warmup samples.
`CAMPAIGN_RETAINED_COUNTER_GROWTH` is the initiating child failure. Editor
objects increased from72,866 at baseline4 to73,342 at sample5 (+476), violating
the unchanged nonincrease requirement. Host handles stayed194; host RSS grew
2.148%, within10%. Six published sample previews do not form a complete35-batch
run, and partial data must not be reused as one.

This directory preserves **58 exact-byte files / 516,507 bytes** from the two
original raw roots, with no source edits, task actions, tests or native runs.
`inventory.json` records every copy's source-relative path, size and SHA256.
Each destination was written exclusively, read back byte-for-byte, and checked
against a fresh source hash. The request and registered XML hashes also match
their copied registration bindings. Raw copies are marked `-text` locally to
prevent future Git newline conversion; nothing was staged or committed here.

Frozen source:49 files, closure
`21a17b2a350160efb17950979adada0a2b3e12dbd95e12158833acbe9f233aa0`.
Campaign SHA256:
`7aae14996dc3518808b84b0f319fbf83b86e26c396979196cadc99a14ad9ff53`.
Profile SHA256:
`0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.

## Failure and cleanup are separate facts

| Layer | Exact retained observation |
| --- | --- |
| Child failure | `CAMPAIGN_RETAINED_COUNTER_GROWTH`; batch5/joint_observation; six published batches; `completed=false`. |
| Host target | `host-owner/process-exit.json`: PID48568, actual exit1. |
| Host owner/helper | `cleanup-001.json`: wrapper exit1, `BENCHMARK_WRAPPER_EXIT`; closed/zero untainted Job, active_count0, Job handle released, wrapper process handle released. |
| Editor owner/helper | Forced cleanup: wrapper exit2, `BENCHMARK_CLOSED_BEFORE_FINISH`; closed/zero untainted Job, active_count0, Job handle released, wrapper process handle released. |
| Native editor target | **No `editor-host/process-exit.json` exists. Actual native target exit is unrecorded. Do not report native exit2 or natural exit0 from the wrapper's exit2.** |
| Parent failure | `BENCHMARK_WRAPPER_EXIT`, `owner_closed=true`, `owned_tree_zero=true`, `cleanup_error=null`. |
| Supervisor | Returned1 after910.578seconds; failure code `BENCHMARK_WRAPPER_EXIT`. Its return record explicitly precedes independent exit observation. |
| Scheduler | Retained terminal snapshot: state3, result1, empty instances; exact task `\HHStudio.GT06.gt06-s70-campaign-02`. Retained deletion receipt at2026-09-17T18:53:37.7859787Z. No scheduler action was performed during this copy. |
| Earlier import stage | Independent import target PID8756 exited0; helper0, natural tree exit, closed/zero Job. This successful import is not successful completion of the editor benchmark. |

Job zero/closed and released owner handles substantiate owned-tree closure
after failure. They do not create a missing natural target exit record or a
successful run capture. In particular the editor wrapper's forced exit2 and
host wrapper's exit1 must remain distinguishable from actual target exits.

## Contents and deliberate limits

`campaign/` includes campaign/profile/source/toolchain/context bindings,
initial/editor snapshot maps, child/parent failures, owner invocations,
process-start/available process-exit records, checked cleanup, small error
logs, and samples00–05 with their joint observations and batch references.
`supervisor/` includes the fixed request, XML and registration/start bindings,
historical first-batch status, failure/return, terminal status, deletion receipt
and small stdout/stderr. The earlier status is explicitly historical.

This is a bounded failure subset, **not a complete raw replay package**.
Large command batches, journal/private service state, native cycle shards,
host/editor heartbeat logs, runtime project/cache and full frozen source trees
remain in the originals. References to omitted artifacts are preserved as
references; no replacement data was fabricated. Source snapshots remain in
the original campaign root. Full verification still needs those original raw
bytes and frozen source, not only this subset.

The inventory explicitly records missing editor process-exit/success capture,
host success capture, child-result, run-capture and final campaign/dataset/
summary artifacts. It does not substitute invented exit integers or empty
success records. `README.md`, `.gitattributes` and `inventory.json` are generated
archive metadata and are excluded from the58 copied-original entries.

Original roots, retained unchanged:

- `8-9-hh3d-3/studio/.local/reviews/gt06-s70-campaign-02/`
- `8-9-hh3d-3/studio/.local/reviews/gt06-s70-campaign-02-supervisor/`

Do not retry the deleted task or overwrite its claim/evidence. A source fix
requires a separately frozen new campaign decision; this failure is retained
for diagnosis and must not be relabeled as acceptance evidence.
