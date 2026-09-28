# GT-06 formal04 — terminal INFRA_ABORT, 2026-09-28

AUTHORITY=0. GT-06 remains IN_PROGRESS with zero accepted pairs. Formal04
completed 26 batches (indices 0–25) in its first pair, then O4.1 stopped it
during native cycles of index 26. The second pair never started. Do not resume
this campaign or treat its prefix as a completed formal pair.

## Verified result

- Watchdog: `CAMPAIGN_WATCHDOG_CPU_PRESSURE`, `INFRA_ABORT`; replaying the raw
  samples with the frozen policy reproduces the CPU trigger. System CPU was
  100% for over 60 seconds. No product failure is waived by this classification.
- Scheduler: Ready, LastTaskResult 1, zero live task instances. The supervisor
  returned 1; host wrapper cleanup recorded exit 2, Job closed/zero, no retained
  Job/process handle, and no cleanup error. No Godot/Blender remained at the
  terminal check. This is aborted cleanup proof, not natural host/editor exit 0.
- All 54 current source files and frozen source copies match formal closure
  `d64c4ce399f5a79153d8daea289ca087b4f07aed0622ac02788f0cbe666ca475`.
  All 156 references in the 26 complete batch captures match size and SHA-256.
- Maximum status gap in those complete batches: 882.5363 ms. This partial
  result does not prove full trend, latency, cleanup or acceptance gates.
- Foreign `rustc.exe` processes occur in the final memory inventory. Historical
  per-process CPU attribution was not captured, so their causal share is unknown.

## Preserved evidence

Paths are relative to `8-9-hh3d-3/`:

- Raw: `studio/.local/reviews/gt06-o4-formal-04/` and sibling
  `gt06-o4-formal-04-supervisor/`.
- Closeout: `studio/.local/reviews/gt06-formal04-closeout-20260928/`.
  `raw.zip` contains 420 raw/verification files plus its manifest; archive CRC
  and each manifest member hash were independently read back.
- Manifest SHA-256:
  `a863f7f318cba343744c1400f1b5d1b1bfc24a356a1e6cfa9155aea34a6cbd85`.
- Archive SHA-256:
  `aa67d7aa44ef2b08476f4c46ea14355faf08c10b27a0972688cb245aa1afeec1`.
- Separate subsequent scheduler receipt `scheduler-terminal.json`, SHA-256:
  `0b866867d0d164bcbd0528abfd6e6cd84daf6d8650f7017f06f00a1ebf37d073`.

## Next action and lesson

This is the first INFRA_ABORT on local date 2026-09-28; one attempt remains
within the daily limit. Source is unchanged, so do not repeat the successful
repair tests or residency diagnostic. Select a fresh CPU-clear window with
O4.1 preflight, then dispatch a new demand-only campaign ID. Leave all owner
apps alone. A launch snapshot cannot guarantee a quiet full run; a watchdog
abort must remain visible even after a healthy prefix. Do not spend time on
debugger attribution or change measurement gates for this infrastructure abort.
