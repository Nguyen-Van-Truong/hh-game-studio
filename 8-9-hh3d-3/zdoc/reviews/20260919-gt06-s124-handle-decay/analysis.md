# S124 read-only boundary analysis

`AUTHORITY=0`. This analysis preserves the original gates and does not alter
the GT06 acceptance decision.

| run | source | batches | editor handles | ObjectDB/resources | HTTP failures | disposition |
|---|---|---:|---|---|---:|---|
| S123 | S122 candidate closure `739447...` | 0–5 | `568,557,555,559,555,560` | `71130/6` | 0 | original retained-counter gate at batch 5 |
| S124 | same candidate closure `739447...` | 0–6 | `565,557,560,559,555,555,555` | `71128/6` | 0 | seven-batch diagnostic boundary |

S124 therefore did not reproduce the S123 boundary at the same batch, and its
counter returned to 555 for batches 4–6. Existing base-closure diagnostics
also show variable series (S105 `565,559,555,555,559,555`; S106
`563,557,557,555,563,555`; S108-03 held 556 through batches 4–6; S119 held
556 through batches 5–7). The evidence supports intermittent process-counter
variation, not a source-attributed leak. Numeric `GetProcessHandleCount`
values and bounded PSS type counts do not identify persistent kernel objects.

S124 was intentionally instrumented and stopped at a bounded prefix, so it is
not byte-identical to stock formal `benchmark_native.gd` acceptance execution.
It is excluded from F13/F14 and cannot justify a threshold, baseline, timeout,
priority, RSS, or formal-source change. The correct next state is to preserve
S123/S124 and retain GT06 `IN_PROGRESS`; a blind formal retry or a counter-gate
relaxation has no evidence basis.
