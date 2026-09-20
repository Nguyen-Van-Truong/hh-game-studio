# S128 helper audit (read-only)

`AUTHORITY=0`; this note records a helper coverage defect found after the
incomplete S128 run. It does not modify the pinned runtime source, original
benchmark gates, timeout, baseline, profile, or acceptance policy.

Two independent defects are visible in the copied diagnostic helper:

1. `post_failure_handles.py` reads `identity["creation_filetime"]` when
   binding a supplemental host/editor observation. The copied `pss_adapter.py`
   returns `pid`, `process_start`, and `executable`, but does not return a
   `creation_filetime` key. Therefore a post-failure observation can fail with
   `KeyError` after the native snapshot succeeds. The self-check fabricates a
   different identity shape and does not cover this production schema join.
2. `GateObserver.__call__` raises its boundary exception whenever the gate-row
   count reaches `limit`, without consulting `STOP_AT_BOUNDARY`. The copied
   full helper sets `STOP_AT_BOUNDARY=False`; therefore a nominal 35-row
   terminal path cannot naturally drain through the observer as written.

3. The copied binding path validates the retained editor identity but does not
   compare the joint row's host identity with the retained producer/host
   identity before a supplemental host observation. This is an attribution
   coverage gap; it is not evidence that the captured host was wrong in S128.

4. The launcher has no independent durable supervisor receipt. If its outer
   Python process is interrupted, the owned Job can remove descendants before
   the in-process `finally` writes result/cleanup/exit files. The missing files
   therefore remain an interruption `UNKNOWN`, never an inferred crash or
   engine failure.

5. The copied helper also retains stale S124/S126/S127 boundary/schema labels
   in several emitted records. This makes the helper unsuitable for a new
   launch until it is reminted with an S128 namespace or a fail-closed stale
   marker check. Existing raw samples are not reinterpreted.

The `--check` preflight and self-check do not exercise these production joins:
the self-check supplies a fabricated `creation_filetime`, while the real PSS
adapter supplies `process_start`. A schema-only fixture using the adapter-shaped
identity is therefore required before any future launch.

The observer writes a supplemental row before the PSS identity join is fully
validated. A future packer must require an explicit completion/validation
marker and reject such partial rows; a row file alone is not an observation.

These are diagnostic-helper defects and an evidence limitation, not proof of a
runtime leak, host-counter root cause, engine crash, or S128 cause. S128 remains
`INCOMPLETE_UNKNOWN`: five complete samples (0–4), output ending in batch 5
`commands`, and no result/target/editor/supervisor terminal receipts. No
engine retry is justified until a distinct supervision question is defined and
this helper schema/boundary pair is repaired and statically covered.

Source references (copied packet):
- `post_failure_handles.py` lines 48, 90, 137–139.
- `owned/gt06-s128-host-attribution-01/pss_adapter.py` lines 203–205.
- `post_failure_full.py` line 29 (`STOP_AT_BOUNDARY=False`).
- `post_failure_full.py` lines 232–243 (joint binding).
- launcher/`benchmark_job.py` Popen + kill-on-close lifecycle (source-only
  supervision boundary).
- stale S124/S126/S127 markers in `post_failure_full.py` and
  `post_failure_handles.py` (copied-helper provenance).

No claim in this note is eligible for F13/F14 or final acceptance.
