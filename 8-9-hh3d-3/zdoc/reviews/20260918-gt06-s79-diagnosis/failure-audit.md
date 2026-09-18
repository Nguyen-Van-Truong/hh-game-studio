# GT-06 S79 read-only audit of the S78 failed campaign

Recorded 2026-09-18T06:17:20.441585+00:00. Diagnostic only; AUTHORITY=0, formal_acceptance=false. This is not a final critic verdict and does not authorize GT-07.

The S78 attempt remains FAILED/PARTIAL at batch 12 joint observation with `CAMPAIGN_RETAINED_COUNTER_GROWTH`. Baseline is **batch 4**, as required by exact profile `gt06-tools-ux-exact-v2`. The sole observed measured-prefix threshold violation is editor ObjectDB 71124 → 71128 (+4). No owner or leak causation is proven.

| Metric | Batch 4 baseline | Batch 12 | Delta / growth |
|---|---:|---:|---:|
| Editor objects | 71,124 | 71,128 | +4 |
| Editor resources | 6 | 6 | +0 |
| Editor handles | 565 | 558 | -7 |
| Host handles | 197 | 197 | +0 |
| Editor RSS bytes | 707,256,320 | 221,208,576 | -486,047,744 (-68.722998%) |
| Host RSS bytes | 38,219,776 | 28,020,736 | -10,199,040 (-26.685243%) |

Batch 12 assembled status gap is **627.6519 ms**; 550.192 ms in the old README is the native ACK component only. Maximum over all 13 batches is 783.600 ms (warmup batch 3), and maximum over measured batch 5–12 is 742.350 ms. The eight measured batches have inspect p95 145.729035 ms and Stop receipt p95 77.569675 ms, both diagnostic prefix statistics. These cannot replace the required 30 measured batches in each of ten fresh runs.

| Batch | Objects | Editor handles | Host RSS bytes | Editor RSS bytes | Assembled gap ms | Stop receipt ms |
|---:|---:|---:|---:|---:|---:|---:|
| 4 | 71124 | 565 | 38219776 | 707256320 | 593.4869 | 52.6945 |
| 5 | 71124 | 555 | 36769792 | 596942848 | 582.7620 | 44.0039 |
| 6 | 71124 | 555 | 35704832 | 472014848 | 672.6930 | 48.3627 |
| 7 | 71124 | 555 | 30568448 | 371417088 | 653.3721 | 65.9867 |
| 8 | 71124 | 555 | 28409856 | 293982208 | 742.3500 | 54.7613 |
| 9 | 71124 | 555 | 28323840 | 230100992 | 616.3793 | 80.7657 |
| 10 | 71124 | 555 | 28712960 | 185282560 | 670.3772 | 71.6342 |
| 11 | 71124 | 555 | 27971584 | 171737088 | 714.7815 | 63.0705 |
| 12 | 71128 | 558 | 28020736 | 221208576 | 627.6519 | 65.8644 |

The run captured 13 raw complete batches: five warmup and eight measured, with 13,000 HTTP mix commands and 1,300 native cycles. All 13 sample previews rebuild exactly offline from 78 hash/size-checked artifact references and the matching native ACK log entries. There are zero complete runs, 22 measured batches missing from this run and 292 missing from the campaign. No native index, child result, assembly manifest, dataset or summary exists.

| Process layer | Actual captured exit | Separate wrapper/return evidence |
|---|---|---|
| Python campaign host PID 38408 | 1 | Helper wrapper 1 |
| Godot import PID 48772 | 0 | Helper wrapper 0; natural tree exit |
| Godot editor PID 55060 | **Unrecorded**: process-exit.json absent | Helper wrapper 2 after cleanup; not a Godot exit record |
| Supervisor PID 52800 | **Unrecorded** actual exit | returned_exit_code 1 after 1304.844 s; supplementary scheduler state 3, result 1, no instances |

Both host/editor cleanup receipts show Job assigned/configured, zero observed, active_count=0, closed=true, handle_retained=false, no taint/uncertainty/failed operations, and explicit wrapper handles released. The import capture also shows Job zero/closed, natural tree exit and matching process-file hashes. Parent failure records owner_closed=true, owned_tree_zero=true and cleanup_error=null. These facts establish the recorded cleanup scope; they do not supply the absent editor actual exit. There is no durable final producer/probe handle inventory in the failure package. This audit worker made no live process or scheduler query. The coordinator supplied `s78-terminal-status.json` (schema `HH-GT06-TASK-STATUS-1`), observed at **2026-09-18T06:15:55.2541112Z**: campaign `gt06-s78-campaign-01`, launch 1, **state 3, last_task_result 1, instances []**. This terminal scheduler observation supersedes the earlier missing-terminal statement. It is explicitly scheduler state only; result 1 is separate from the supervisor actual process exit and supplies no owned-tree proof.

Source closure is `649bd0f3e9a6a0a6d2249d952ec63f0dc6e29b2da3f273bd2b3ef8c8d169b18e`. All 49 bytes/hash entries match both archived source copies and the current worktree. Loading the archived modules and trusted fixture regenerated exactly the same 49-file dependency map; the closure was recomputed using sorted path/NUL/hash/LF records. The editor invocation adds 15 immutable project files (64 total); their hashes match. Python and Godot executable hashes also match the invocations. Profile SHA-256 is `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`; archived profile dataclass, campaign bytes and attempt bytes agree. No profile or threshold was changed.

The exact profile remains ten process pairs, 5 warmup + 30 measured batches per pair, 500 inspect + 300 reject + 200 admitted commands and 100 native cycles per batch, one separate Stop/cancel receipt per batch, type-7 percentiles, inspect/Stop p95 ≤500 ms, status gap ≤2000 ms, RSS growth ≤10%, and no retained-counter growth against batch 4. The import budget is 20 s; benchmark owner wall budget is 7410 s, with four editor process slots and six aggregate host slots.

All **30 operator Stop control slots** (10 runs × 3 attempts) are absent; only run-00-attempt-01 exists. The supervisor Stop file is absent too. Separately, the 13 per-batch cancel targets are unique, terminal CANCELED and no-effect; eight belong to measured batches. Do not confuse control-slot absence with per-batch Stop performance coverage.

The saved task-definition hash matches registration/start. Its raw XML differs from the expected template through scheduler serialization (default omission, order, URI and equivalent PT24H/P1D duration); that byte difference alone does not establish drift. The original raw supervisor directory has no terminal snapshot; the coordinator supplement now supplies the terminal scheduler observation above. Its SHA-256 is `76bbb21585f72f6566ea1d66b0cf7f235cfa98633bbf315a92934a39716739f8`.

Required documentation corrections (raw evidence must stay unchanged):

1. `zdoc/reviews/20260918-gt06-s78-failure/failure-summary.json` — Exact baseline is batch4, not batch0. Editor handle delta is -7, not -10; objects/resources happened to match both baselines. Correct `handles_baseline` from 568 to 565.
2. `zdoc/reviews/20260918-gt06-s78-failure/failure-summary.json` — Current field contains native ACK gap only. Label that scope, and add assembled sample gap=max(command, ACK, start permit). Changed rows: b4 565.956->593.4869, b7 648.009->653.3721, b9 536.271->616.3793, b10 544.703->670.3772, b11 539.763->714.7815, b12 550.192->627.6519. Prefix maximum783.6 remains correct but is warmup b3; measured-prefix maximum742.35 is b8.
3. `zdoc/reviews/20260918-gt06-s78-failure/README.md` — Use full sample b12 status gap627.6519ms;550.192ms is ACK-only. State baseline b4 and include both host/editor RSS and handles. Distinguish 13 completed raw batches (5warmup+8measured) from a complete35-batch run.
4. `zdoc/reviews/20260918-gt06-s78-failure/{README.md,failure-summary.json}` — Add actual editor exit=null/unrecorded; wrapper2 is not Godot exit. Host actual38408/1 and import48772/0 are captured. Jobzero/closed and wrapper-handle release are proven separately. Supervisor returned1 is not its observed process exit. The original raw package has no terminal scheduler result, but the coordinator supplement s78-terminal-status.json records state3/result1/noinstances at 2026-09-18T06:15:55.2541112Z; cite it separately, without converting scheduler result1 into actual exit1.
5. `zdoc/reviews/20260918-gt06-s78-failure/failure-summary.json` — Add baseline_batch_index4, exact profile id/hash, partial coverage8/30 measured and0/10complete runs, no native index/assembly manifest/dataset, all30 control Stopslots absent,13 unique cancellation receipts8measured. Existing hash values are valid but do not bind the missing information.
6. `zdoc/8-9-godot-blender-agent-studio-plan.txt` — Top marker still starts S76_LAUNCH2_FAILED while current benchmark marker correctly says S78_LAUNCH1_FAILED. Align current marker to S78 failure and retain S76 as history; add the exact native-exit gap and separately cite terminal scheduler state3/result1/noinstances if describing closure. Do not change acceptance, thresholds, current GT06 gate or infer leak ownership.

The companion JSON contains the exact profile, all 13 bounded metric rows, per-batch binding checks, cleanup receipts, missing-evidence list and SHA-256 references. Only these two audit files were written by this audit worker; no source, plan, threshold, engine, process, scheduler or raw-evidence action was taken. The terminal update reads the coordinator-provided status file only.
