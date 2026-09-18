# GT06 S81: admission ACK and fixture fault locks

Date: 2026-09-18, Asia/Saigon. Bounded read-only follow-up. No source edits,
tests, engine/process operations, threshold changes, or acceptance verdict.
This report is the sole artifact authored during this follow-up.

## Conclusion

There is a real avoidable contention path: every normally completed HTTP
handler acquires the host state lock **four additional times solely for local
disconnect fault hooks**, including twice between durable dispatch completion
and sending its response. A worker holding that same host lock during a long
journal operation can delay an already-durable `ACCEPTED_PENDING` receipt.

A small safe design is a **separate mutex for fixture fault controls**, used by
both arm and consume operations, with the four hooks retained in their exact
present order. No host state, journal state, lease, authorization, or receipt
freshness check is performed by `_disconnect_probe`; its host lock can therefore
be replaced by that independent fault-control synchronization. Avoid an unlocked
`disconnect_once is None` fast path and avoid moving a hook across dispatch/send.

This is **not established as the cause or correction of S80's particular
failure**. S80's pending inspection was eventually canceled with `no_effect`.
If the reply had merely waited behind that inspection's own terminal fsync, its
history would ordinarily be COMMITTED: execution marks APPLIED before terminal
persistence, and cleanup cannot subsequently recast it as canceled before apply.
The observed cancellation instead fits a timeout during admission storage/cache
commit/guard exit or scheduling, followed by `_stopped` becoming true before
worker apply. S80 has no phase timings sufficient to identify the exact stall.

## Present ordering and contention

Relevant current source: `studio/host/core/transport.py`.

The normal `_handle` route is:

1. Read/authenticate request, parse body, validate public identifier.
2. `_disconnect_probe(before_dispatch)` acquires `host._lock`.
3. `_dispatch` acquires `host._lock`, checks current session/route/project and
   performs the requested journal/state operation. For a new command, `_submit`
   validates payload before existing-ID lookup, then validates new-request
   deadline, Stop/capacity and lease/revision, durably appends PENDING, enqueues
   the job, and signals the worker. `_dispatch` releases `host._lock`.
4. `_disconnect_probe(after_dispatch)` reacquires `host._lock`.
5. For `/v1/commands`, the optional `drop_submit_response_once` test is made;
   when true, its clearing currently acquires `host._lock`, then returns without
   sending. Its existing flag check is outside the lock.
6. `_disconnect_probe(before_reply)` reacquires `host._lock`.
7. `_send` obtains **session authority's different lock** only to encode/redact
   the response, then sends it, half-closes, and drains bounded bytes/time.
8. `_disconnect_probe(after_reply)` reacquires `host._lock`.

The four `_disconnect_probe` acquisitions happen even with all test faults
unarmed. The optional drop path acquires an additional host lock only when its
flag is true. `_disconnect_probe` only compares/clears a tuple, writes the
already-created response's status into a test observation, and sets an Event.

Worker `_execute` holds `host._lock` while lease-guard validation and the bounded
effect occur. It also holds `host._lock` while `_finish` persists the terminal
record. The latter can involve whole-history verification/recovery fsync,
authoritative append fsync and cache commit. Thus this schedule is possible:

| Handler | Worker |
| --- | --- |
| Pending append completes; job is enqueued; host lock released | Wakes and acquires host lock |
| Tries `after_dispatch` hook's host lock | Applies and enters slow terminal journal persistence |
| Durable pending receipt waits unsent | Eventually releases host lock |
| Hook completes; response is finally sent | Terminal may already be durable |

The same contention can arise at `before_reply` if the handler wins the first
hook but the worker wins the next acquisition. `after_reply` cannot delay bytes
already sent, but can unnecessarily retain the connection handler and listener
slot. `before_dispatch` is redundant for an unarmed hook but dispatch itself
still requires the host state lock; splitting the hook cannot remove legitimate
dispatch/journal contention.

The session lock in `_send` is **not** held by worker journal fsync: `_finish`
calls `sessions.redact_output(...)` to produce an argument before calling the
journal. The authorization context inside `lease_guard` covers only the bounded
effect; terminal persistence follows outside that session context. Retain this
redaction/authentication locking unchanged.

## Small synchronized change

Give `FixtureFaults` a dedicated mutex and narrow local methods to arm/consume
disconnect and submit-response-drop controls. The lock can instead be host
owned, but placing it with the controls makes all writers and consumers use the
same synchronization domain and avoids accidentally sharing mutable fault
objects across different host locks.

- A disconnect arm operation installs `(route, phase)`, resets any relevant
  observed state/Event under the fault mutex, and returns. A consume operation
  checks and clears exactly one matching tuple, saves the supplied response
  status and sets its Event under that mutex. Nonmatching routes/phases do not
  consume the fault.
- Submit-response-drop arm and consume are also atomic under the fault mutex.
  Preserve its position after `after_dispatch` and before `before_reply`.
- The response status passed into the consume operation is a value from the
  already-created `Response`; it does not require a host state snapshot.
- Do not hold the fault mutex while entering `_dispatch`, acquiring the host
  lock, accessing the journal, encoding redaction, waiting on test gates, or
  performing socket I/O. Release it before returning to the next handler step.
- Keep `readback_gate` and `applied` Event behavior unchanged. No production
  operation can arm these controls through a wire field.

Known arming callers to migrate from direct field writes:

| File | Present writer |
| --- | --- |
| `tests/protocol/test_transport_recovery.py` | `arm`: clears observed Event and assigns `disconnect_once` |
| `tests/protocol/test_transport.py` | lost-submit test assigns `drop_submit_response_once=True` |
| `tests/replay/test_benchmark_commands.py` | failure-latch test assigns the same drop flag |

The original direct writes are not synchronized by the current host lock
either. Introducing a new reader-side mutex alone would not fix that contract.
Use the synchronized arm APIs at these callers; if direct-assignment API
compatibility is required, implement synchronized properties rather than
leaving unsynchronized backing-field writes. Keeping pre-request arming only
would be another explicit contract, but would not support safe future midflight
arming and is less robust than the small dedicated API.

## Ordering argument

The fault mutex only linearizes fault arming/consumption. It has no authority
over game effects or command admission. With every arm/consume using it, a
concurrent arm either precedes a matching hook's check or follows it; no hook
can consume the same one-shot twice. No unlocked fast path can skip that order.

The semantic order remains:

`before_dispatch -> unchanged dispatch -> after_dispatch -> optional submit
drop -> before_reply -> unchanged send -> after_reply`.

Before-dispatch cuts still happen before mutation. After-dispatch and
before-reply cuts still happen after durable admission and before sending.
After-reply cuts still occur only after `_send` finishes. The same result
status is recorded in each hook. If both controls are armed, an after-dispatch
disconnect must still win and leave submit-drop armed; if submit-drop wins,
the before-reply disconnect must remain armed.

Admission/rejection/deduplication/lease/deadline/Stop ordering remains entirely
inside the unchanged `_dispatch` and `_submit`. The pending ACK still exists
only after the authoritative journal append completes. Sending a pending ACK
while worker completion proceeds is valid: it acknowledges durable admission,
not the latest terminal state. The old code already allowed that schedule and
already sent its original result after a later Stop or completion; its extra
hook locks do not re-read or validate receipt freshness.

No fault lock is held across a host/journal/session acquisition, so this design
adds no reverse lock ordering. Stop's state mutation and drainage remain under
their existing synchronization. Removing test-hook host-lock contention cannot
make Stop bypass a legitimately busy journal section, and must not be claimed
to do so.

Error-response paths in `_handle` (`JournalError`, validation/safety rejection,
generic transport failure) call `_send` directly after their exception handling;
they do not traverse the normal after-dispatch/before-reply hooks. Listener
`CONNECTION_LIMIT` replies also call `_send` directly. Leave those paths and
their public response shapes unchanged.

## Meaningful tests to add or retain

1. **Durable pending ACK independent of terminal persistence.** Use a real
   fixture socket call and event barriers, with no engine and no timing sleeps.
   Wrap `_dispatch` so that after its real durable PENDING return it waits until
   the target worker has entered a gated `journal.finish_command` while holding
   `host._lock`. Let the handler continue while that gate remains closed. Assert
   the client receives the unchanged PENDING receipt before releasing the
   terminal gate. Then release it, look up the command and assert one correct
   terminal/effect. Use bounded waits and `finally` release/join/cleanup. This
   demonstrates removal of the actual dependency, unlike merely counting locks
   or asserting a source-code pattern. The gate must be outside session
   authority's lock so the test isolates the host fault-hook lock.
2. **One shot under concurrency.** Arm one disconnect or one submit-drop, run
   two independent matching real requests concurrently, and assert exactly one
   missing receipt and one ordinary receipt, with both same-ID lookups proving
   the expected durable outcomes and no duplicate effects. Synchronize phases
   with barriers, not arbitrary sleeps. Keep original UNKNOWN responses.
3. **Concurrent arming order.** Pause a handler before a chosen hook, arm using
   the synchronized API, release the handler, and assert that hook consumes the
   fault once. A nonmatching route/phase must leave it armed.
4. **Competing hook order.** Arm both disconnect and submit-drop and verify the
   existing early-return precedence described above. This catches accidental
   batching/snapshotting of controls at handler entry.
5. Retain the existing four-phase socket-cut matrix for pending admission,
   committed lookup, Cancel and Stop in `test_transport_recovery.py`, plus lost
   submit/no-retry benchmark latching. Retain expiry, payload-before-dedupe,
   lease/fencing, journal-capacity and UNKNOWN-durability tests. The optimization
   has no reason to change their outcomes or any public thresholds.

The coordinator should decide whether this small contention removal is worth
including before a new freeze. It removes a demonstrated static mechanism;
the S80 cause remains bounded by its incomplete timing evidence.
