# O1 counter-rule owner resolution

AUTHORITY=OWNER_DIRECTIVE_20260925; STATUS=RESOLVED_FOR_REVIEW; FORMAL_ACCEPTANCE=false

The owner directive O1 requires the synthetic `+1 retained handle per 7
batches` series to **FAIL**, while the explicitly prescribed inclusive T/G
windows alone allow that series. These requirements cannot both hold without a
separate rule. The owner directive therefore authorizes the v5 supplemental
retained-handle rule already implemented in the frozen candidate:

* apply per host/editor `held_handles` only;
* require all 30 measured values to be nondecreasing;
* require at least three positive steps;
* require a positive step wholly inside each measured half (5–19 and 20–34);
* keep the exact O1 T/G, private-commit, status-gap, timeout, early-stop,
  actual-exit, Job, owned-tree, retained-handle, and effect rules unchanged.

This resolves the test-contract contradiction; it does not accept GT06 or
waive the independent critic, fresh preflight, two fresh 35-batch pairs, raw
closure, or two final same-hash critics. A one-time step/plateau and bounded
non-monotonic noise remain governed by the literal O1 windows and are not
reclassified by this supplemental rule.

The prior `O1-DECISION.md` remains immutable historical diagnostic material.
