# GT06 S85 interruption forensics (bounded, read-only)

**Run:** `gt06-s84-attribution-01`  
**Scope:** preserve the interruption boundary only; `authority=0`, `formal_acceptance=false`. No relaunch, process control, raw/runtime/plan mutation, cleanup, or acceptance decision was performed.

## Observed boundary

- The final completed capture is index **9** (the tenth capture, 0-based); the final completed native batch is **9**.
- Batch 10 host command evidence exists: `command-10.json` is `status=COMPLETE`, but `native_acceptance=false`; its cancellation receipt is `CANCELED_BEFORE_APPLY` with `no_effect=true`. This is a host command result, not proof of a completed native batch.
- Batch 10 input marker `project/benchmark/input/start-10.json` was written at `2026-09-18T10:27:43.5771161Z`.
- The last editor heartbeat is batch 10, cycle 82, phase `SAVE_WAIT`, `main_thread=true`, PID 44960. The final host/editor stdout mtimes are `2026-09-18T10:28:03.3696863Z` and `2026-09-18T10:28:03.5476023Z` respectively. Host progress remains batch 10 phase `native_cycles`.
- No batch-10 native completion artifacts were found: `joint-10.json`, `batch-capture-10.json`, `sample-preview-10.json`, `project/benchmark/out/batch-10.json`, and `project/benchmark/input/ack-10.json` are absent. The present `ready-10.json` is a prior readiness marker (`2026-09-18T10:26:01.8792973Z`), not a batch-10 completion receipt.
- These run-closure artifacts are absent: `supervisor-return.json`, `child-failure.json`, `child-terminal-cleanup.json`, `child-result.json`, `host-owner/process-exit.json`, and `editor-host/process-exit.json`. The copied `import-host/process-exit.json` belongs to the earlier import stage (`2026-09-18T10:09:45.6764321Z`).
- A bounded process read at `2026-09-18T10:35:26.9835086Z` found PIDs 6444, 11904, and 44960 absent. This is an absence receipt only; it does not establish natural exits or a cause.

## Bounded Windows event query

The `System`, `Application`, and `Microsoft-Windows-TaskScheduler/Operational` logs were queried only for `2026-09-18T10:27:00Z` through `2026-09-18T10:31:00Z`. The exact selected output is in `event-log-window.json`.

- Two `Microsoft-Windows-IsolatedUserMode` informational starts occurred at `10:28:07.4754945Z` and `10:28:07.4763040Z`.
- Three `Application` records at `10:28:37Z`–`10:28:42Z` are Chromium event ID 256 with empty messages.
- Task Scheduler returned no matching events.
- No Godot/Application Error, Windows Error Reporting, resource-exhaustion, shutdown, or Task Scheduler error appeared in this bounded query. This absence does **not** identify why the run stopped.

The evidence cutoff is temporally near the `10:28:03Z` stdout writes, but the bounded records do not support attributing the interruption to OOM, a crash, a tool job, shutdown, or any other cause.

## Source and invocation binding

Copied `diagnostic.json` and `context.json` bind the run to source closure `e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f` and profile `0cd5b530...`; the campaign hash is recorded in the exact copies. The executed helper hashes recorded in `diagnostic.json` are:

- `diagnose_sequence.py`: `dacfc91721eefacc3be6f420e3812f320ad8a9a3f08ff7beafa0ea56d3b0f7c0`
- `object_probe.gd`: `20ed7e62658c247265a8165024682efac78ae9c475a810bb6368e8fe9c75dd40`

Exact invocation JSON, selected stdout, command-10 bytes, timeline, event output, and absence receipt are preserved under this packet. The initial packet manifest is `manifest.json` (SHA-256 sidecar `manifest.sha256`); `manifest-final.json` and its sidecar include this report as well.

## Limits

This packet is diagnostic interruption evidence only. It does not claim run PASS, completion, cleanup, or acceptance, and it does not replace the missing process-exit/child-result records.
