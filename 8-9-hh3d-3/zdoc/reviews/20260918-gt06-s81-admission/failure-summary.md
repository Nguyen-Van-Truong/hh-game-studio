# GT-06 S81 preservation of failed S80 campaign

AUTHORITY=0. Diagnostic preservation only; formal_acceptance=false. No gate verdict or critic signature. GT-06 remains in progress.

`gt06-s80-campaign-01`, launch 1, failed in batch 15 command processing with `ADMISSION_UNKNOWN`. The 15 completed raw batches are five warmup plus ten measured batches, with 15,000 mix commands and 1,500 native cycles. There are **zero complete runs**. Batch 15 contains 801 partial command rows; its final row is ordinal 800, `inspect.400`, with `UNKNOWN` / `CONNECTION_LOST_LOOKUP` after 2,003.3888 ms. These partial records are failed evidence and cannot be combined with a retry to obtain PASS.

The scheduler observation at **2026-09-18 07:41:46 UTC** records state 3, last result 1, and no instances. It was captured before deletion. The supervisor returned 1 after 1,772.640 seconds; that record explicitly does not observe its own actual process exit.

| Layer | Actual target exit | Separate cleanup/return evidence |
|---|---|---|
| Host PID 34988 | 1 | Helper wrapper 1; Job zero and closed; wrapper handle released |
| Import PID 45648 | 0 | Helper wrapper 0; natural tree exit; Job zero and closed |
| Editor PID 5900 | **Missing / null** | No process-exit.json. Helper wrapper 2; Job zero and closed; wrapper handle released |
| Supervisor PID 41820 | **Missing / null** | Returned 1; scheduler result 1; no live instance |

Host, editor and import Job receipts have assigned/configured=true, active_count=0, zero_observed=true, closed=true, handle_retained=false and no reported taint, native error or create/close uncertainty. Host/editor wrapper handle receipts explicitly show released handles. Import capture has no explicit wrapper-handle receipt. Parent failure records owner_closed=true, owned_tree_zero=true, cleanup_error=null. The full process snapshot contains none of the four recorded PIDs and no Godot/Blender process. There is no durable helper PID inventory or final producer/probe handle inventory; neither is inferred from the success-only path. Scheduler state and PID absence do not fill the missing natural editor or supervisor exits.

All **30 operator Stop slots** are absent, as is the supervisor Stop file. The 15 separate per-batch cancel receipts are unique, terminal CANCELED and no-effect. Their presence does not imply an operator Stop caused this failure.

The raw inventory contains **314 files / 48,835,092 bytes** across the campaign and supervisor roots, with no exclusions. **263 selected files / 23,093,820 bytes** are copied exactly, including all completed batch references, failure records, both frozen source snapshots, owner logs, scheduler records and the terminal mutable fixture scene. Streaming hashes and size/mtime checks preceded a complete matching second inventory. Ninety artifact references across fifteen batch captures verify. Originals remain in place and were not edited.

The 50-file source map matches both frozen snapshots, checkpoint `f75a5d08`, and live source at collection. Closure: `1dc889ef923dee9b53c6faeeb1d6fd781acc3a89a4b860b531b55fc3a124cf8f`. All three invoked binary hashes match their invocation records. The campaign and attempt profile bytes match. Fourteen initial project hashes match the terminal project; the benchmark's mutable `scenes/fixture.tscn` differs from its initial hash and is preserved explicitly (terminal SHA-256 `2576c7fab573cf13a4d2e0c6bc7d96518d0f2cbd67c67d71c162915624feebfa`). The first collector incorrectly asserted that this scene remained immutable and exited 1. That collector and its failure note remain; a separate continuation records the comparison and finishes preservation without changing raw files or overwriting evidence.

The completed measured prefix has no retained-counter/RSS/status-gap screen breach against baseline batch 4. Objects remain 71,128, resources 6, host handles 197; editor handles fall from 562 to 556. The measured prefix maximum assembled status gap is 1,128.0714 ms. These are prefix observations, not full-run performance acceptance. Native index, child result, final cleanup, run/campaign capture, assembly manifest, dataset and summary are missing.

Evidence: `failure/terminal-facts.json`, `failure/source-map-verification.json`, `failure/raw-locator-hashmaps.json`, `failure/preserved-byte-manifest*.json`, `failure/completeness-and-screen.json`, `failure/verification.json`, and `failure/verification-independent.json`. Raw originals are at `studio/.local/reviews/gt06-s80-campaign-01` and its `-supervisor` sibling. This worker ran read-only collection/verification only, with no engine or tests, process kills, task deletion, source changes, plan edits or acceptance changes.
