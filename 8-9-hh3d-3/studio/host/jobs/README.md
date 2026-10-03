# GT07 preparation: dispatch policy

AUTHORITY=0. O7.5 permits this isolated code/unit preparation after Formal25's
two pairs passed. GT06 remains the current WP awaiting owner-dispatched critics.
This branch is not merged; GT07 is not opened, ticked or accepted. Nothing here
changes an installed route, public quota profile or the frozen GT06 candidate.

The existing transport owns one configured project and pops one deque. Godot's
PublicationFifo and BlenderWriterJournal already serialize their registered
fixture writers. The missing policy prepared here chooses among multiple
projects/sessions without replacing those owners.

`dispatch_policy.select_next` consumes immutable, host-produced queue and active
snapshots. It returns one job ID and the next fairness cursor, or no work. Project
round-robin comes first, session round-robin second: registering more sessions
cannot buy more project turns. FIFO uses the durable enqueue sequence, never a
client priority or timestamp. The first unexpired ticket of a session blocks its
later tickets; an older unexpired resource claim blocks younger claims for the
same resource. Unrelated resources may progress. A failed, missing or UNKNOWN
dependency is not ready. A Stop latch prevents every new selection.

The internal candidate defaults bound 64 pending jobs, 4 active jobs, 2 active
per project, 1 per session, 8 resources and 16 dependencies per job. They are not
installed public limits. Expired jobs are excluded from selection, not deleted
or silently given terminal receipts. Draining/uncertain jobs must remain in the
active snapshot until their real ownership/cleanup proof permits removal.

## Integration contract when GT07 opens

The future coordinator supplies one coherent trusted snapshot while holding its
durable reservation transaction. It validates registered project/session owners,
canonical global resource identities and the dependency graph before policy use.
The receipt projection contains completed jobs only; active/pending IDs cannot
also appear there. Only verified COMMITTED prerequisites make dependents ready.

Selection, slot/resource reservation and cursor persistence must commit together.
Do not advance the cursor on deferred or failed admission. Reusing an unchanged
snapshot deliberately returns the same selection; it does not authorize a second
launch. Recheck native authority, expected revision, fencing and Stop through the
existing registered adapter immediately before effects. Keep control/Stop outside
the work queue and caps. Policy output is neither a lease nor a public ACK.

Concrete future call sites are the coordinator selecting which registered owner
admission or `SelectorFixtureBroker.advance` phase to invoke. Do not replace
authenticated owner routes with arbitrary callback dispatch.

## Remaining GT07 work

- Durable broker admission, queue/project/session quotas, reservation and cursor
  recovery; dependency-cycle rejection; no duplicate launch after crash/reconnect.
- Native Godot/Blender writers and expiry/late-result fencing; Stop/cancel race
  through the existing journal and correct Job ownership.
- Full PREPARED/VALIDATED/ACTIVATING/COMMITTED/reload/ACK crash matrix and manual
  edit reconciliation, plus real file-lock/disk-full/cross-volume/journal-full
  evidence with preserved last-good source and actual capacity/clock conditions.
- Result/diagnostic retention, consumer integration and independent acceptance.

Unit evidence for this policy cannot establish those native, durability, fair
queue-admission or full TX18/GT07 claims. Do not derive progress percentages from
the policy test count or copy accepted GT06 signatures to this branch.

## Preparation verification

One focused run on 2026-10-03 completed 18/18 unit tests, actual process PID
46128 exit 0. The policy and test source hashes were unchanged across the run.
Receipt and stdout/stderr are retained at
`studio/.local/reviews/gt07-policy-prep-20261003-01/verification.json` in this
worktree. Command from repository root:

`python -B 8-9-hh3d-3/studio/tests/jobs/test_dispatch_policy.py -v`

A separate read-only policy audit found no concrete bugs within this pure
snapshot contract. It was a scoped implementation audit, not a GT07 critic
signature. No engine ran and no installed source changed.
