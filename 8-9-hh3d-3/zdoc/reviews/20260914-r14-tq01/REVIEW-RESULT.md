# GT-01 TQ01/TX12/TX14 candidate audit — 2026-09-14

Status: **CANDIDATE** (5/5 offline checks).

The checker validates lock portability, Unicode/cache isolation, independent host exit fields, synthetic CAS rollback, and evidence secret hygiene.
It does not grant acceptance and does not replace an official remint or the two required read-only critics.

## Remaining gaps
- offline checks do not prove network denial, token rotation, or paid-quota fairness
- TX12 uses synthetic packages; live-owner/crash recovery/manual reconciliation remain unexecuted
- official evidence is historical candidate data and must be reminted after source freeze
- two independent critics on one frozen source hash are still required

## Reproduction
`python check_tq01_tx12_tx14.py`
