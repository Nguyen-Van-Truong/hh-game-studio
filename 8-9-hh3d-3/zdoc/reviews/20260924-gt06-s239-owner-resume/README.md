# S239 — owner-authorized bounded GT06 resume

The active task owner authorized the coordinator to keep the tools plan moving without pausing for another approval. S236 supplied a distinct supported measurement boundary: the retained editor process identity was sampled before ACK, after ACK, and during a bounded terminal idle period without issuing another start permit. The S232 post-ACK +2 did not reproduce.

This ADR authorizes exactly one fresh formal campaign, `gt06-s239-formal-01`, on the frozen 53-file formal source closure and unchanged GT06 gate. It does not change timeout, baseline, counter, RSS, profile, dataset, critic, or acceptance rules. A partial or scheduler result cannot tick GT06.

The ADR records an authorization decision, not an acceptance verdict and not a leak/root-cause claim. GT07–GT10 remain unopened until GT06 is accepted.

Verify the decision packet:

`python -B zdoc/reviews/20260924-gt06-s239-owner-resume/verify.py`
