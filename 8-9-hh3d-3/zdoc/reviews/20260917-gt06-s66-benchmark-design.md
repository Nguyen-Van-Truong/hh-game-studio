# GT06 S66 benchmark execution design and evidence gaps

2026-09-17. Design only: no benchmark executed, no acceptance decision, no plan checkbox change. Authority remains `../8-9-godot-blender-agent-studio-plan.txt`: GT-06 lines 771–793, TQ06 lines 914–920, tools UX benchmark lines 938–954, section 2.6 lines 653–661, and TX02/05/13/18. Source files below are relative to `../../studio/`.

## Exact workload and thresholds

Preserve the conservative contract already selected by the coordinator: **10 independent process runs, each with 5 excluded warm-up batches followed by 30 measured batches per metric**. Every batch contains **1,000 mock protocol commands: 500 inspect, 300 validation rejection, 200 admitted queue**, plus **100 actual create/undo/save/reload cycles**. A cycle contains all four operations; 100 operations is not 100 cycles.

| Count | Warm-up, excluded | Measured | Total executed |
|---|---:|---:|---:|
| Batches | 50 | 300 | 350 |
| Mock commands | 50,000 | 300,000 | 350,000 |
| Editor cycles | 5,000 | 30,000 | 35,000 |

Measured commands therefore include 150,000 inspect, 90,000 rejected, and 60,000 admitted queue entries. Keep run and batch boundaries; never substitute 30 total samples, ten short probes, one 1,000-command batch, or 100 cycles across the whole campaign. A short pilot may diagnose the harness but cannot count toward these totals.

Plan thresholds: light inspect p95 <= 500 ms; Stop/cancel receipt p95 <= 500 ms; heavy-job watchdog/status update gap <= 2 s; no duplicate/lost effects or steadily increasing leaks; after ten repetitions of the same workload, stable RAM growth <= 10% against warm baseline. Stop receipt means cancellation was received/latching occurred; process drain/termination has separate timing and evidence. Blender render time is excluded. Device or command-mix changes require a new profile/version and rerun.

The plan requires median/p95/p99 and raw samples but does not name a percentile estimator. Proposed frozen profile choice: linear type 7, with all raw command latencies and all 30 batch summaries retained for each run. Report per-run distributions as well as pooled command distributions; neither may hide a failed run. Stop/cancel probes need a fixed, declared schedule during the same batch load, recorded separately from the exact 1,000-command mix. Do not quietly add them to the denominator or replace admitted commands with capacity rejection.

## Reusable pieces, and their limits

| Existing files | Reuse | What they do not establish |
|---|---|---|
| `host/core/transport.py`, `tests/protocol/test_transport.py` | Real loopback HTTP, `LoopbackFixtureHost` / `FixtureClient`, bounded mock queue, exact effect counts, cancel/Stop and durable lookup | Native editor responsiveness or the full sample campaign |
| `godot-addon/editor_owner.py`; `tests/godot/run_editor_edit_probe.py`, `run_editor_owner_probe.py` | Actual EditorPlugin semantic create/update/undo/redo, registered capture/adopt, same-process generation/readback, owned exit | Repeated benchmark cycle lifecycle; direct trusted `apply_projection` is not public authorization |
| `godot-addon/publication_owner.py`, `publication_transport.py`; `tests/godot/run_edit_publication_probe.py` | Authenticated edits reaching EditorUndoRedoManager, duplicate receipt checks, save/reopen and immutable-source evidence | 100 cycles or a latency distribution; existing probes are small correctness runs |
| `tests/godot/run_publication_stop_probe.py`, `run_fifo_publication_probe.py` | Timing a real Stop receipt while an owned validator is active, then independently checking drain | The required 300 measured Stop/cancel batches or replay-service fairness |
| `host/replay/backend.py`, `service.py`, `transport.py`; `tests/replay/run_service_probe.py` | Fixed immutable Play, registered process identity, actual HTTP completion/Stop/reconnect and retained capture/inspection | Editor create/undo/save/reload; current single Stop check `<1000 ms` is a diagnostic bound, not p95 <= 500 ms |
| `host/replay/process_probe.py`, `perf.py`, `perf_export.py` | Retained Windows process handle/RSS; closed frame artifact validation and recomputed statistics; frozen native evidence checks | Editor heartbeat/jank or HTTP command latency; frame percentiles cannot stand in for UX timings |
| Replay and publication transport/backend/session unit tests | Auth, malformed input, congestion, retained cleanup and failure injection | Native UI behavior, actual OOM/disk-full handling, or benchmark performance |

No complete driver implementing the specified 10 x (5 + 30) campaign was identified in these reviewed sources. `host/replay/profile.json` is explicitly `gt06-interactive-diagnostic-v1`: zero warm-up, screenshots included, 20 s / 1,200 frames / 1,000 RSS rows / 8 MiB. It must remain diagnostic. The label `workstation.gt01` supplied to an export is caller context, not hardware discovery. Before measuring, resolve and hash the actual GT01 workstation profile; the reviewed lock, GT01 final evidence and bootstrap sources did not identify a complete versioned hardware benchmark profile.

## Required bounded lifecycle work before execution

The accepted `EditorOwner.MAX_EFFECTS = 16` is a lifetime retained-intent cap. Public edits need capture plus edit authority and reserve save capacity; save/adopt uses further slots. `PublicationSession` and `ReplaySession` retain 64 commands per owner; replay owners also expire after 120 s. These are not sufficient for this workload. Raising shared caps, clearing private intent tables, rotating only bearer tokens, or replacing real cycles with mocks would change the safety/evidence contract.

Implement and review a **new scoped benchmark cycle lifecycle** under GT06 before the campaign. Each cycle must have fixed operations and a finite local budget, unique run/batch/cycle/command IDs, a fresh revision/generation fence, native UndoRedo/readback, durable hash-bound terminal evidence, and checked teardown of its owned resources. Expired cycle handles remain unusable; journal/tombstones preserve retry identity. A new cycle cannot reset a Stop latch or hide uncertain cleanup. Retain one measured editor process across batches so restarting it cannot erase the memory trend; if the current accepted owner cannot support that safely, record the gap and design the scoped adapter rather than reinterpret “10 process runs” as thousands of unrelated launches. This lifecycle does not yet exist in the reviewed helpers.

Use the accepted mock protocol host for the explicitly mock command portion, with its real framing/auth/queue and fixed payload catalog. Freeze concurrency, arrival order, rejection causes, queue occupancy and mock job cost in the benchmark profile. Keep native editor cycles real and identify them separately. A 200-entry admitted queue workload may drain through bounded capacity; it must not allocate an unbounded queue or count rejected requests as admissions. Stage finite evidence shards through closed references instead of full-series command envelopes. Check estimated journal/disk/retention budgets before launch; stop on exhausted capacity and preserve the failed run.

## Proposed execution and evidence package

1. Freeze profile/version and complete source/tool/schema closure, fixed seed/order, payloads, per-cycle operations, concurrency, timeouts, capture policy, RAM phases and percentile implementation. Record actual CPU/RAM/GPU/driver/OS/power/render settings and resolution. Serialize official GPU work; no simultaneous heavy Blender/GPU lane.
2. For each of ten runs, record PID + native start identity, process role, UTC and host monotonic anchors. Execute five full warm-up batches, then thirty full measured batches without silently dropping slow, rejected or failed observations. Record import/GC/cache phases separately. No forced GC solely to improve a result unless specified by the frozen profile.
3. Time client send through authenticated receipt for inspect, validation rejection, queue admission and Stop/cancel separately. Record terminal effect/drain latency independently. Instrument editor-main-thread heartbeat and reviewer UI event handling; a fast HTTP reply alone does not prove the UI remained responsive. Capture explicit maximum status-update gaps, disconnected/UNKNOWN states and next action.
4. Every native cycle verifies create, exact undo restoration, save bytes, reload generation and semantic equality; preserve authored attachments, reject stale IDs, and correlate one terminal outcome per admitted command. Collect host/editor RSS and object/resource/handle counters at the same quiescent phase after each batch. Compare repetition ten with that run's post-warm-up baseline and retain all thirty measured points; do not hide a leak with process restarts, pooled averages, or unexplained OS-cache subtraction.
5. Seal raw per-run/per-batch latency rows, count/mix checks, cycle receipts, revisions, heartbeat/RSS series, source/profile hashes, logs, actual host/native exits and Job-zero/leftover proof. Warm-up rows stay available but are flagged excluded. A failure remains a failure with its original run ID; reruns get a fresh ID and explicit reason.

## GT06 evidence classification and remaining gates

The retained S65 Native04 -> managed Repair02 -> Native05 chain supplies actual fault/repair/replay observations on the fixed fixture; its screenshot-inclusive frame exports are valid diagnostic data. Native02's missing viewport-readiness export stays GAP. Neither the S65 data, the pending HTTP probe, nor unit tests constitute the tools UX benchmark or HH World performance evidence.

GT06 still needs a same-frozen-source evidence matrix for the complete tool vertical slice: Blender edit/validated GLB/import linkage; real 60 Hz input edges and seed through menu/move/interact/pause/resume/quit; pause simulation frozen while UI advances; capture PID/window/source/time/camera binding; schema compatibility and mandatory 1% low rejection; TX02/05/13 and GT06-scoped TX18 flood/disconnect/Stop/retention proof. Reviewer UX must show keyboard focus/shortcuts, queued/running/draining/unknown/committed/rejected with next action, bounded pages and no reconnect resume after human Stop. Retained inspection is explicitly historical; it cannot claim a live runtime inspector.

Two independent critics must review the frozen candidate and exact evidence. This document supplies an execution design and records gaps; it grants no acceptance and does not move GT07, GT08/Android, or HH World gates.
