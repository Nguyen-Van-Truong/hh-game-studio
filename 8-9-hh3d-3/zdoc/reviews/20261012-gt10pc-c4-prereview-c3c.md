# GT-10-PC C4 pre-review — C3c

DATE=2026-10-12 (Asia/Saigon)  
PACKAGE=`studio/.local/reviews/gt10pc-rehearsal-20261012-c3c`  
MATRIX_SOURCE_CLOSURE=`e7032ee18cb76b0991a7bb3faaff3c6473418854b0c72769abfabba387e2c391`  
MODE=REHEARSAL; AUTHORITY=0; ACCEPTANCE=false; SELF_REVIEW_ONLY=true; TICK=not-applicable

## Observed

- Matrix schema 3 and rows are exactly P1–P11; every row is `REHEARSAL_PASS`.
- P2 has eight host rejection cases plus one native worker; all four native attacks reject and the Godot readback exit is 0.
- P7 has exactly eight native cases split 3+3+2; each child has host exit 0, verified process tree, and no timeout.
- P8 records closure verification, actionable missing dependency/version rejection, no network, and no latest autofetch.
- P9 is authority 0 with docs plus an independent consumer smoke; P10 has both `gt08a` and `catalog` producers on one manifest hash.
- P11 is explicitly one real-Godot cycle (`full_benchmark=false`); it is not release-soak evidence.

## Gaps found before final

1. The Scheduled-Task supervisor still rejected `mode=final`, so C5 could not be started through the required path.
2. The matrix verifier only deeply rechecked the short P11 row; a final verifier must re-open the signed artifacts and the full campaign dataset/run captures.
3. Final selection must be P1–P11. P12 is the external two-critic gate and must not be synthesized by the matrix producer.

## Corrective boundary

The runner now has a separate `FINAL` path that reuses the native P1–P10 producers, calls the real frozen-profile 2x35 campaign for P11, and remains `authority=0`/`acceptance=false`. The final verifier binds archive hashes, campaign/profile/dataset hashes, run captures, actual child receipts, and all row-specific structural gates. The old C3c raw package remains diagnostic history; any source change requires a fresh rehearsal closure before final.

No plan checkbox or acceptance header was changed by this pre-review.
