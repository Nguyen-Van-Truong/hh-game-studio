# GT07: durable scheduling and registered owner dispatch

AUTHORITY=0 until GT07 acceptance. GT06 was accepted at `9a6c8598` after two
independent critics; GT07 implementation is now open. The policy preparation
was merged at `86e6134d`; current integration extends it without changing the
sealed GT06 candidate. No public IPC capability or generated-code route is added.

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

The internal candidate defaults bound 64 pending jobs, 32 pending per project,
8 pending per session, 4 active jobs, 2 active
per project, 1 per session, 8 resources and 16 dependencies per job. They are not
installed public limits. Expired jobs are excluded from selection, not deleted
or silently given terminal receipts. Draining/uncertain jobs must remain in the
active snapshot until their real ownership/cleanup proof permits removal.

## Integration contract

The coordinator supplies one coherent trusted snapshot while holding its
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

`DurableBroker` now persists admission, selected resource reservation and cursor
in a dedicated custody-bound `PrivateEventLog`. One durable event contains the
reservation and next cursor. Its fence includes stream identity and a monotonic
generation. Reopen retains reserved/UNKNOWN jobs; it never issues their dispatch
again. Stop has reserved storage headroom outside admission caps and survives
restart. It has no automatic resume API. Pending caps prevent one session or
project from taking every admission slot. Forward/self dependencies and reused
IDs fail closed; only registered-owner COMMITTED results unlock dependents.

`QueueOwner` reuses the existing Windows three-root custody/registry contract.
It owns a dedicated native writer guard and event stream, preserves incomplete
provisioning, rejects an unwitnessed suffix, and retains failed cleanup ownership.
Its provisioned file/blob roots serve this shared custody contract, not gameplay
publication. Trusted local setup supplies its parent; no wire path is accepted.

`SelectorDispatcher` exclusively pumps registered `SelectorFixtureBroker`
instances. Clients still use their existing authenticated admission. Resource
keys come from native file identities. Each phase calls the original owner,
which rechecks session/lease/revision. A terminal scheduling receipt is recorded
only after exact owner lookup and, for COMMITTED, actual selected-file readback.
Storage alone never supplies a gameplay ACK. A canceled job already cleared by
the owner is retired only with the matching terminal receipt and idle phase.
Different/recovered activations are never replayed. Stop immediately fences new
phases; active/uncertain reservations stay held for explicit reconciliation.
`reconcile_terminal` permits a recovered reservation to retire only after its
registered owner proves the exact command/digest and current native readback.
It never advances an owner phase or restores a session. A newer selected release
or an unresolved owner transaction keeps the reservation held.

This is internal integration over inert file fixtures, not Godot/Blender native
mutation or a new multi-project network service. Dedicated storage has the
existing 512-record/8-MiB cap; terminal/Stop slots are reserved, but compaction,
rotation and full-capacity evidence remain open. Operator recovery is explicit.

## Remaining GT07 work

- Production service lifecycle wiring and explicit owner reconciliation for
  recovered nonterminal work; complete fair-admission and bounded retention evidence.
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

## Integration checkpoint

On 2026-10-04, `gt07-jobs-integration-20261004-03` completed 46 tests with
host-captured PID 45616 exit 0 and unchanged scoped source hashes. This covers
native Windows queue custody/reopen, bounded policy, registered file-selector
dispatch, cancellation, admission/terminal-collection serialization and explicit
restart reconciliation after a committed owner effect. It does not cover the
remaining native Godot/Blender or complete GT07 matrix. Raw logs and receipt:
`studio/.local/reviews/gt07-jobs-integration-20261004-03/verification.json`.
Details and limits: `zdoc/reviews/20261003-gt07-integration/requirements.md`.

The same run exercised the default 512-record/8 MiB event stream. Native
custody writes filled it to 510 records (169 completed owner-result jobs), then
rejected the next admission with `BROKER_JOURNAL_FULL`; after reopen, all
receipts and the durable Stop headroom remained intact. This is capacity and
retention evidence, not proof of rotation/compaction or disk-full behavior.
Receipt: `studio/.local/reviews/gt07-capacity-20261004-01/verification.json`.
