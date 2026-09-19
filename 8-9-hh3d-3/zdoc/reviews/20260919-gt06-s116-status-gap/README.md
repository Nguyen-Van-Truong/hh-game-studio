# S116 status-gap attribution

AUTHORITY=0. This packet records read-only attribution for the preserved stock
campaign `gt06-s116-formal-01.r00.a01`. It is not a PASS, repair, dataset sample,
or root-cause claim.

The stock campaign stopped at batch 10 during `joint_observation` with
`CAMPAIGN_STATUS_GAP`. The measured sample preview reports
`max_status_gap_ms=2041.7971`, above the unchanged 2000 ms gate. The native ACK
for the same batch was observed at `780.821 ms`; the native counters were
ObjectDB `71128` and resources `6`. This separates the observed failure from a
native ACK timeout in that batch.

The always-on HTTP phase packet records exactly one transport failure, on route
`lookup`; commands, discovery, lease, archive, cancel and stop routes were zero.
The preserved failure span is a lookup header/body boundary of roughly two
seconds. This identifies the host lookup/status lane as the observed boundary;
it does not prove whether the cause is journal I/O, scheduling, lock wait, or
memory pressure.

Cleanup evidence: host process exit `1`; import process exit `0`; editor-owner
wrapper exit `2`; editor target exit is `UNKNOWN` because no target exit receipt
was recorded. The editor Job observed zero active children and closed cleanly;
handles and owned threads were released. Scheduler task is terminal state 3,
result 1. These gaps remain part of the failure evidence.

Raw remains immutable under
`studio/.local/reviews/gt06-s116-formal-01` and its supervisor sibling. Do not
merge the 11 partial batches into F13/F14 and do not infer a leak or root cause.
A future bounded diagnostic, if launched, must use a fresh ID and unchanged
source/profile/workstation/gates. No formal retry is authorized by this packet.
