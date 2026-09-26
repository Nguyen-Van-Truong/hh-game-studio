# O1 counter-rule conflict — decision needed before formal

AUTHORITY=0. This memo changes no owner requirement and accepts no campaign.

The requested formulas and the required test outcome disagree. Let warmup
batches 2–4 all have 558 handles, and measured batch i have
`558 + floor((i - 4) / 7)` for i=5..34. This is one new handle each seven
batches: baseline 558, early maximum 560, late maximum 562.
Both host (T=4/G=2) and editor (T=8/G=2) pass the exact inclusive O1 bounds.
Therefore a verifier implementing those bounds cannot also fail this series
without an additional rule or changing an inequality.

The coordinator added a >=2 monotonic net-growth rule in source `2f404289`.
An independent review of `bd230d12` found this also rejects a one-time +2
object step followed by a plateau, although O1 permits it. That rule was an
unapproved interpretation and is removed from the current candidate. A later
uncommitted three-step replacement is also removed. The new profile version
keeps literal O1 formulas; tests expose the sparse-leak gap explicitly and
check the plateau and exact inclusive counter/memory boundaries.

Two reviewable choices:

1. Keep literal O1 T/G as authoritative. Change the sparse-leak test expectation
   to PASS under the two-window check and retain the series for diagnostic
   reporting/release soak. This preserves the existing numerical contract but
   does not guarantee detection of every small leak in 35 batches.
2. Add an explicit supplemental handle rule: FAIL when all 30 measured handle
   counts are nondecreasing, there are at least three positive consecutive
   differences, and at least one positive difference occurs within each half
   (5–19 and 20–34). Apply per host/editor; keep all existing T/G and private
   commit bounds. This rejects the seven-batch staircase and permits a single
   step/plateau and alternating +/-3 noise. It can still reject legitimate
   monotonic initialization and cannot guarantee detection with noisy decreases.
   This option requires a new locked profile and focused tests before review/run.

Until the owner chooses, the 1-per-7 requirement is UNMET, not waived by green
unit tests. No formal dispatch or new acceptance is authorized by this memo.
Preflight app blockers are independent and still need clearing before launch.
