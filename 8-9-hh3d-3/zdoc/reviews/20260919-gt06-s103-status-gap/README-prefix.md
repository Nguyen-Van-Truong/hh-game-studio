# S103 status-gap prefix diagnostic

This packet diagnoses the missing native `save_scene()` return boundary from
S102. It is pinned to source checkpoint
`56bfd448e83aa2512c0c2561e8e1a29f12134360`, the 53-file closure
`7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467`, profile
`0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`, and native
base `13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95`.

`owned_prefix.py --check` is inert and verifies all 53 source bytes, the
profile, binary and exact additive overlay. The runner creates a disposable
project, installs the overlay with temp+replace and readback, and records
actual owner/child/cleanup receipts. It never changes the formal runtime
source or acceptance gates. `--launch` remains fail-closed.

The bounded runs are complete:

* `gt06-s103-prefix-preflight-06` ran exactly one diagnostic batch: 1000 HTTP
  commands and 100 native cycles. Command/native receipts completed, all
  Jobs/handles/threads were clean, and the child stopped at the diagnostic
  boundary. The editor target natural exit is `UNKNOWN` because the bounded
  stop is intentional; this is not a PASS or dataset sample.
* `gt06-s103-prefix-01` completed batches 0–5 and stopped at the original
  `CAMPAIGN_RETAINED_COUNTER_GROWTH` gate. Editor handles changed 555→561 at
  batch 5; no HTTP transport failure or >2000 ms status gap was observed in
  this prefix. Child failure, owner exit and cleanup receipts are present and
  clean. This is a diagnostic failure, not a formal benchmark result.

The locked screen gate compares batch 5 to the exact batch-4 baseline. The raw
editor handle sequence is 565, 563, 559, 555, 555, 561; ObjectDB/resources
remain 71128/6, host handles remain 202, and the largest status gap is
642.433 ms. The non-monotonic sequence is a measured counter excursion, not
proof of a leak or root cause: no handle identity/type or post-idle stabilization
was captured. A future attribution probe may add those observations after
quiescence, while keeping the gate and formal profile unchanged.

The run roots under `studio/.local/reviews/` and the earlier collector-failure
roots `01`–`05` remain preserved. Their raw and portable hash domains are kept
separate. Do not merge any prefix rows into F13/F14, infer no leak or root
cause, or retry a formal campaign from this packet. The formal gate remains
10 fresh host/editor pairs × 35 batches (5 warmup + 30 measured), with the
original 1000 HTTP + 100 native workload and all exit/tree/handle/hash checks.

Static verification (no engine launch):

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260919-gt06-s103-status-gap/owned_prefix.py --check
python -B 8-9-hh3d-3/zdoc/reviews/20260919-gt06-s103-status-gap/test_owned_prefix.py
python -B 8-9-hh3d-3/zdoc/reviews/20260919-gt06-s103-status-gap/test_native_probe.py
python -B 8-9-hh3d-3/zdoc/reviews/20260919-gt06-s103-status-gap/test_read_native_save.py
```

The diagnostic is evidence for attribution only. A later formal retry needs a
fresh campaign ID and source/profile/workstation verification after a narrow
repair is proven; it must not reuse either S102 or this diagnostic prefix.

The proposed two-snapshot PSS attribution design, including access/identity
limits and observer-overhead rules, is in
[`handle-attribution-design.md`](handle-attribution-design.md). It is a design
only; no PSS snapshot or new engine run has been started.
