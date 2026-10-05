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
unapproved interpretation and was removed in the v4 candidate (`a7938f9e`).
V4 keeps literal O1 formulas; its tests expose the sparse-leak gap and check
the plateau and exact inclusive counter/memory boundaries. V5 now implements
choice 2 below as a reviewable proposal only. It is not owner-approved, cannot
authorize formal dispatch, and does not replace any historical verdict.

Two reviewable choices:

1. Keep literal O1 T/G as authoritative. Change the sparse-leak test expectation
   to PASS under the two-window check and retain the series for diagnostic
   reporting/release soak. This preserves the existing numerical contract but
   does not guarantee detection of every small leak in 35 batches.
2. Add an explicit supplemental handle rule: FAIL when all 30 measured handle
   counts are nondecreasing, there are at least three positive consecutive
   differences, and at least one positive difference occurs within each half
   (both endpoints in 5–19 or in 20–34; a 19-to-20 step alone does not count
   for the late half). Apply per host/editor; keep all existing T/G and private
   commit bounds. This rejects the seven-batch staircase and permits a single
   step/plateau and alternating +/-3 noise. It can still reject legitimate
   monotonic initialization and cannot guarantee detection with noisy decreases.
   This option requires a new locked profile and focused tests before review/run.

Until the owner chooses, the v4 1-per-7 requirement is UNMET and the v5
supplement is UNAPPROVED, regardless of green unit tests. No formal dispatch
or new acceptance is authorized by this memo. A generic request to continue
implementation has not been recorded as approval of either numerical choice.
Preflight app blockers are independent and still need clearing before launch.
