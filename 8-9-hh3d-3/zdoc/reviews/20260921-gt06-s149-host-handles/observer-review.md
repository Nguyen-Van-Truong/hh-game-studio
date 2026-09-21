# S149 observer review

This is a read-only review of `host_handles.py` and the existing
`studio/.local/reviews/gt06-s149-handles-smoke-01` package. I did not launch an
engine, run the tests, start another workload, or change source. The frozen
`host_handles.py` SHA (`8746f142596d32f0c4072ca5dc96caa9afd3ed294f88a1b30b3223ff4dc75834`)
matches the smoke package's `freeze.json`.

## Observation timing and the 173/174 difference

The two values are from different observation phases:

| Artifact | Evidence |
| --- | --- |
| `sample-00.json` | Child's original `_observe()` sample: `held_handles=173`, `monotonic_us=899954134319`. |
| `checkpoint-00.json` | Written after that sample at `2026-09-21T21:42:16.519941+07:00`; it carries the same 173 sample and PID/start identity. |
| `census-00.json` | External PSS started at `899954174642300 ns`, about `40,323 us` after the child sample. PSS saw `target_handle_count_before=174`, `target_handle_count_after=174`, and `handles_captured=174`. |
| `observed-00.json` | ACK was `OBSERVED`, so the child accepted the census and exited normally. |

The child polls for the ACK and sleeps for `.05` seconds between polls after
writing the checkpoint (`host_handles.py:95-100`). Therefore the PSS census is
not a same-instant repeat of the original counter. It was taken while the
child was in the post-sample wait phase. A transient wait/timer descriptor is a
plausible explanation for the extra one handle; the census contains five
`IRTimer` rows, but its redacted object identity cannot prove which descriptor
changed. The artifact supports only this bounded statement: PSS observed 174
handles at its own timestamp, stable across its own capture. It does not show a
leak, a retained object, or a contradiction in the original 173 sample.

The PSS adapter's own limitations are correctly present: supplemental observer
effect is unknown, numeric handles are not object identity, and no leak/root
cause claim is allowed. The difference must remain an attribution gap unless a
future run adds a separately evidenced same-phase barrier that does not add a
target handle or alter the command workload.

## Gate equivalence

The smoke package is not gate-equivalent to the GT06 diagnostic:

* `--smoke` executes one `run_diagnostic()` group (the ten-command smoke), so
  it never establishes the five-warmup baseline or executes `screen()` at
  index 5 and later.
* The original `screen()` checks the child's own RSS, held-handle counter, and
  status gap. It never consumes the external PSS count. The PSS count of 174
  therefore cannot be substituted for the gate sample of 173.
* Native/ACK/idle/assembly coverage is explicitly absent, and both `summary`
  and `result` correctly keep `authority=0`, `formal_acceptance=false`, and
  `eligible_for_dataset=false`.

The static boundary checks and the smoke's successful identity/cleanup path are
useful prerequisites, but they do not establish the eleven-batch or original
host-gate result.

## Identity, exits, and cleanup

These parts of the smoke evidence are internally consistent and fail closed:

* The retained `ProcessProbe` is bound to PID `14300` and process start
  `windows:134344753354186935`; the checkpoint, PSS identity, process-start,
  and process-exit records agree.
* PSS reports `status=OBSERVED`, with released marker, snapshot, and process
  handle. `result.json` reports `probe_released=true` and no errors.
* The target process exit record is PID `14300`, exit `0`; the owner helper and
  wrapper also report exit `0`. The target exit is read from the child's
  `process-exit.json`, rather than inferred from a banner or a PID scan.
* The owner capture records `active_at_wrapper_exit=1` followed by
  `active_before_cleanup=0`, a natural tree exit, a closed untainted Job, and
  no retained wrapper handle. `child-cleanup.json` reports closed producer and
  journal, released probe, no live threads, no cleanup errors, and unchanged
  source bytes.

No cleanup or identity defect is visible in this package. Keep the target exit,
helper/wrapper exit, and Job cleanup as separate fields in any later report;
their agreement here is evidence for this run, not permission to collapse them
into one inferred exit.

## Minimal safe improvement

Do not change the original gate, baseline, timeout, sleep interval, or command
workload to make 173 and 174 match. The smallest safe instrumentation change is
to publish the phase explicitly alongside each census: the child sample's
monotonic timestamp, the PSS start timestamp, their microsecond delta, and a
phase such as `post_sample_ack_wait`. If the values differ, mark the row
`TEMPORAL_MISMATCH` for attribution while retaining the PSS type census. Keep
the original child sample as the only input to `screen()`.

If descriptor identity at the exact gate point becomes necessary, design and
review a real two-phase barrier first. It must be shown not to add a timer/event
handle to the target and not to change command timing; replacing the wait with
a busy spin or relaxing the gate would invalidate the measurement. Until that
evidence exists, the 173/174 delta is a documented instrumentation artifact,
not a reason for a runtime repair or a formal retry.

Disposition: `HOST_ONLY_BOUNDARY_CAPTURED`, authority 0, smoke prerequisite
only. No formal acceptance or root-cause claim is supported.
