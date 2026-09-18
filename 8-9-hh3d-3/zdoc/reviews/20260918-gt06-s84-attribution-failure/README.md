# S84 preservation — failed S82 attribution diagnostic

AUTHORITY=0. FORMAL_ACCEPTANCE=false. This packet preserves
`gt06-s82-attribution-01`, an instrumented diagnostic that is explicitly
ineligible for the official dataset. It supplies no benchmark PASS, independent
critic signature, root-cause verdict, or gate acceptance. GT-06 remains open.

The run started at **2026-09-18 09:41:18Z** and recorded terminal cleanup at
**09:49:50Z**. Its primary failure is **CAMPAIGN_RSS_GROWTH**, batch 5,
`joint_observation`. Editor RSS increased from the batch-4 baseline
**758,169,600** to **881,020,928 bytes** (about 16.20%, exceeding 10%).
The failed sample also records **2044.2252 ms** maximum status gap, over 2000 ms.
RSS is the actual thrown primary error; the status breach is an additional
static observation, not a replacement error or a complete performance verdict.
ObjectDB remained **71,128**, resources **6** at the baseline and failed sample.

Six captures contain **6000 HTTP command rows**, **600 native cycles**, six
unique per-batch cancellation receipts, and 36 verified artifact references.
They consist of five warmup captures and one failed measured capture, with
29 batches missing from the required 35-batch sequence. There are **zero
complete runs**. `ready-06.json` exists; command/start/ACK/native batch 6 do not.
Readiness is not completed work, and this prefix cannot enter a campaign.

Only the ACK4 `joint_baseline` census exists: **27,401 reachable IDs**,
**43,727 unattributed objects**, collection duration **820,390 microseconds**.
Object counters equal 71,128 before and after collection/publication. The
census explicitly does not cover the complete ObjectDB. No growth census was
produced. This shorter run cannot establish the cause of the earlier +2
ObjectDB growth, disprove it, or establish a fix. Instrumentation affects RSS
and timing; its causal contribution to this failure remains unproven here.

## Exact bytes and source bindings

`raw-locator-hashmaps.json` records all **192 original file names**, sizes and
mtimes across the diagnostic root (189 files) and its launch records (3).
**156 files** have exact SHA-256 hashes; **36 generated cache/per-process
settings files** are explicitly metadata-only exclusions whose contents were
not read, hashed, or copied. Sensitive filename classes are also fail-closed
exclusions; no such extra files were found. A complete second inventory
matched the first. Originals were never written or deleted.

`preserved-byte-manifest.json` maps **105 exact copies**, **14,942,382 bytes**,
to their original paths and hashes. It preserves all selected logs,
invocations, source/helper maps, process/cleanup receipts, commands journal,
six batches and barriers, baseline census, project source including the
executed native overlay, two executed diagnostic helpers, and all three
launch records. The 51 frozen runtime files stay hash-addressed in place
instead of being duplicated. No content was normalized or redacted.
`.gitattributes` disables text conversion for future staging.

All **51 base runtime files** match both the frozen snapshot and live source:

`e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f`.

Profile:
`0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.

Executed helpers match diagnostic declarations, frozen bytes, current helper
bytes, and the host invocation map:

| Helper | SHA-256 |
|---|---|
| `diagnose_sequence.py` | `bb9f288a3df30dce8f3442896a94e8fb31505bd7a6e8e0ef769a9ea24037e095` |
| `object_probe.gd` | `6221092c70591d89b42aa8c00298198299a716edc7c25b8b4813db5d771fe556` |
| Executed native overlay | `a24e69f0e3275cc37c5e57e7ba9279f4bdda2553fbf1d1e155bc86575e6f5b00` |

The editor invocation binds the effective project overlay independently of
the unchanged base closure. Invocation-declared binary hashes are retained;
native/Python binaries were not rehashed for this preservation task. The
fixture scene differs from the initial/editor maps, but its actual serialized
bytes match all 600 native saved-file receipts. The exact scene is copied;
this is not an unchanged-project or failure-cause claim.

## Exits, cleanup and missing evidence

| Process | Actual target receipt | Separate cleanup/return evidence |
|---|---|---|
| Host PID 42832 | Exit **1** | Host Job zero/closed; wrapper exit 1 and wrapper handle closed |
| Import PID 23584 | Exit **0** | Natural tree exit; wrapper exit 0; Job zero/closed |
| Editor PID 32860 | **Missing** | Editor helper PID **47556**, exit **2**; Job zero/closed and wrapper handle closed |
| Supervisor PID 19068 | **Missing** | Pre-exit `returned_exit_code=1`, owner closed and owned tree zero |

Host/editor/import Job receipts show no recorded create/close uncertainty,
retained handle, or failed native operation. Child terminal cleanup reports
closed producer/journal/probes/sockets and stopped threads. The child's null
host self-exit is reconciled with the later parent-owned host exit receipt,
not synthesized. Import wrapper-handle and host/import helper-PID inventories
remain absent from the inspected ownership receipts.

A fresh read-only observation at **10:02:39Z** found none of the five recorded
PIDs above. This proves absence at that observation only, not natural exits.
Supervisor return and helper exit must not substitute for missing editor or
supervisor actual process-exit receipts.

The diagnostic's supported operator Stop slot, `stop-request.json` at its
run root, is absent under `lexists`. Recursive filename checks found no Stop
latch under either original root. This is one disposable diagnostic, so no
30-slot campaign claim is made. Six per-batch cancellation receipts are
present and are distinct from the absent operator Stop latch.

## Reproduce verification

From `8-9-hh3d-3`:

```powershell
python -B 'zdoc/reviews/20260918-gt06-s84-attribution-failure/preserve.py' verify
```

The verifier reads originals and exact copies, checks file-set/size/mtime/hash
stability, source/helper/invocation bindings, all batch references and sample
evidence hashes, cleanup/exit distinctions, Stop absences and the packet seal.
It imports no runtime code and starts no engine. It is a same-agent static
recheck, not an independent acceptance critic. Full verification needs the
51 frozen source originals still in place; cache exclusion content is outside
the hash/copy guarantee.

The initial collector stopped before copying because the conservative
credential-pattern screen matched controlled `source/studio/host/core/transport.py`.
The exact collector and failure receipt are retained as `collector-attempt-01`.
No matched content is published as a credential or copied. The final selection
keeps frozen runtime source in the hash map only; selected evidence and
diagnostic helpers pass the limited pattern/key screen. This is not a universal
secret-absence proof. The final collector and byte verifier both returned
actual host exit 0; their receipts are distinct from diagnostic process exits.

Hash domains remain separate: raw/copy hashes use exact bytes; runtime closure
hashes sorted `path + NUL + lowercase SHA-256 + LF` rows; sample evidence uses
compact sorted-key JSON of source/profile/run/index/processes, six artifact
refs and barrier receipt. The packet sidecar is SHA-256 of exact
`package-manifest.json` bytes, which enumerates every packet file except itself
and the sidecar. It is a preservation seal only.

No engine/test execution, cleanup/delete, runtime/plan edit, commit, or gate
acceptance occurred in this lane.
