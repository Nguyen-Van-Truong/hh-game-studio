# S45 custody / managed-fixture implementation review

2026-09-16, Asia/Saigon. Read-only implementation feedback during concurrent
development; **NOT an acceptance verdict, NOT a frozen-source critic review**.
I implemented the admission preflight earlier in this task and do not claim
independence when assessing S45. No source edits or new runtime tests were
performed during this review. Findings were sent promptly to the coordinator.

Scope: `custody.py`, `managed_fixture.py`, the private
`safe_replace._rearm_verified_snapshot` method, and the surrounding ownership
and event-custody hooks needed to follow their lifecycle. Registry code was
still being developed by its owner; this is not a registry security review.

## Outstanding constructor-ownership path

**P2: a nested native API cleanup owner can be hidden by the event-log
constructor wrapper.** `PrivateEventLog.__init__` adopts an exception's
`cleanup_owner` only when it is a `PrivateBlobStore`. If `_StoreApi.__init__`
fails before assignment to `PrivateBlobStore` and native cleanup also fails,
the exception instead carries `cleanup_api`. The event-log constructor has
`_store=None`, wraps the failure as `EventLogError(cleanup_owner=log)`, and does
not adopt or forward that API.

`ManagedFixtureOwner._failed_init` takes the top `cleanup_owner` in preference
to `cleanup_api`. In this path it retains the incomplete log; closing that
log cannot drain the original API's still-open token/file handles. The API
remains in the chained cause, but the normal close/retry path does not traverse
or close it. A successfully closed wrapper is therefore insufficient evidence
that all constructor resources were drained.

Locations as read: `private_events.py` constructor exception handler around
lines 147-163; `managed_fixture.py` `_failed_init` around lines 111-122.
This is a static path finding, not an executed leak reproduction. Parent and
the private-events worker were notified.

Required regression: make `_StoreApi` construction retain a genuinely unclosed
native token after failed cleanup; verify event-log/managed construction keeps
an explicit cleanup owner for that exact API, then restore CloseHandle and
prove a later owner.close() drains it. Do not use a mock that closes the real
handle and only then reports failure. Forward/adopt the retained API explicitly
or preserve a deduplicated ownership chain through wrappers.

## Findings corrected during this review

- `WitnessCustody._check` initially converted poisoned uncertainty into a
  default `CustodyError(outcome_unknown=False)`. Current source explicitly
  raises with `outcome_unknown=True`. The regression should inject a registry
  store failure and prove later record/binding/confirm/persist attempts remain
  UNKNOWN without another store.
- Managed creation initially persisted PROVISIONING/READY and created roots
  before the selector validated project ID and initial revisions. A concrete
  mismatch was `project_id='bad:project'`: the custody codec allowed the colon,
  while selector `_name` rejected it only after provisioning. Current create
  validates `_name` and `_revisions` first. Tests should assert no registry or
  filesystem provisioning for invalid setup inputs.
- Initial creation silently resolved the supplied parent and used plain
  `mkdir` for intermediate directories before ancestor pinning. That erased
  the original alias spelling before safe native checks. Current source passes
  the original parent to `ProtectedFileRoot.create` first, then creates peer
  stores after file namespace provisioning/barriers. Test junction/symlink
  parent rejection without outside writes; this correction was inspected, not
  independently exercised here.
- Initial reopen acquired a lease as a different logical owner, which could
  reject an immediate clean restart while the previous 30-second lease was
  still live. Current source renews the recorded logical owner with a new ID,
  a higher fencing epoch, and a one-millisecond recovery lease after exclusive
  roots/custody/history are checked. See the conditions below.

These observations describe source changes made by the coordinator. They are
not substitutes for the coordinator's integration regressions or independent
frozen-source review.

## Lifecycle assessment and required tests

The recorded-owner recovery lease is sound for the fixed trusted supervisor
when all exclusive roots are reacquired, the new lease ID and strictly greater
fencing epoch are durably witnessed before rearm, and old authenticated sessions
are never restored. The owner string is bookkeeping, not recreated client
authority. The one-millisecond TTL is an availability choice; safety cannot
depend on native disk work finishing within one millisecond. Test immediate
restart before old expiry, refusal of the pre-crash lease ID/epoch, and normal
new-session lease acquisition after the short lease expires.

The inspected supervisor leaves pending commands and durable STOP read-only.
It does not call stage/select/adopt on pending work during startup. Rearm occurs
only on the terminal path after `load_committed` checks the exact current file
and performs a fresh barrier. The private rearm method checks the fixed
`.writer`/`active.json` namespace, exact FileVersion, file/directory flushes,
and a successful handle close before clearing read-only. It is trusted broker
code, not a new transport recovery capability.

The event high-water order is sensible: append/flush/readback precede separate
custody persistence, and append cannot acknowledge until that succeeds. A
complete suffix beyond saved custody is semantically replay-validated before
the supervisor promotes its witness; pending/Stop remains held. Crash tests
must cover both sides of the event-flush/custody-flush window, including
terminal events and Stop, plus truncated/rolled-back event tails. Successful
process-cut recovery does not establish physical power-loss durability.

No runtime import cycle or lock inversion was established: private-events uses
a deferred custody import, and WitnessCustody persistence does not call back
into the locked event log. The record codec bounds input, enforces exact keys,
decimal-string volume IDs, canonical bytes/checksum, distinct roots on one
volume, and a typed witnessed head. The checksum is integrity checking, not
authentication against an unrestricted broker-account process.

## Last inspected bytes (not a combined freeze)

| File | SHA-256 |
| --- | --- |
| `custody.py` | `aa4320faeccb3b729d0eebf29ac3e962d2590bca1e3aba14b0aef620b021fbc9` |
| `managed_fixture.py` | `0cb0b4ec945b1079eac1012d1768a05b13908a2c43f1c9cc3ec9d155d3d5f719` |
| `safe_replace.py` | `d3e2ac47ceb203d1f52b1f73e45a27c7a618eee84f1088577cc5e307d16f3661` |

These files and dependent worker files were being edited concurrently.
No PASS/TICK=yes or completed GT-02 claim is made.
