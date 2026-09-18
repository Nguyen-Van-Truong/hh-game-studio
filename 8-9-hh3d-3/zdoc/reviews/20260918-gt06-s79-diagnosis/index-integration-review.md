# S79 supplemental index integration review

AUTHORITY=0. Read-only implementation review, not a final critic verdict, gate acceptance or tick. Scope: the applied changes in `studio/host/replay/disk_journal_index.py`, `studio/host/replay/service.py`, and the new `studio/tests/replay/test_index_faults.py`. Dependency methods were read only to check the changed control flow. No tests, engines, scheduler/process actions, broad source scans/hashes or source edits were performed. Only this report is written.

**Finding: no actionable correctness regression identified in this three-file change.** The review supports the narrow error-boundary repair; it does not prove full GT-06 runtime or benchmark acceptance.

## SQLite cursor boundary

`disk_journal_index.py:113-125` now places execute/fetch and cursor finalization within the same `sqlite3.Error` conversion boundary. A cursor-close SQLite exception can no longer escape as an unclassified driver exception after an append already reached JSONL fsync. A pending return is canceled by a failing `finally`, so no row/success escapes before cursor close. The surrounding reentrant lock remains held throughout. The owning connection remains attached to the index; `VerifiedJournal` converts `DiskIndexError` to outcome-unknown and invalidates the verified generation, requiring recovery from authoritative JSONL. The change does not alter SQL, transactions, receipt authority or journal limits.

The cursor fault fixture deliberately closes the real cursor and then raises. It validates the ambiguous-success boundary, not every possible native SQLite finalization failure. Separate connection-close and unlink failure tests verify that the index/journal owner remains reachable and rejects work until cleanup retry succeeds.

## Uncertain submit and effect ownership

`service.py:195-209` computes uncertainty from the trusted local `JournalError.outcome_unknown`, latches session halt and requests backend Stop before returning the exception. This also covers a durable pending append whose derived index failed before `_jobs` insertion and before `admitted_here=True`.

The permit order is correct against the existing session contract: `halt()` cancels a RESERVED permit itself. `permit_status()` then returns CANCELED, so the handler appropriately avoids a second cancel. If a permit was STARTED, halt leaves it drainable; `finish_effect(..., known=False)` drains it, marks uncertainty and retains the stop latch. The work lock always releases in the existing `finally`. No branch resumes a session or starts an effect after the uncertain journal error.

The new `admitted_here or uncertain` condition publishes `_uncertain[command_id]` even if registration never reached `_jobs`. `_record_unknown()` sets its in-memory receipt before disk I/O. Failed persistence does not revert to ACCEPTED_PENDING, and a terminal receipt already durable remains authoritative. Future work is denied by session authorization after halt; lookup remains available for reconciliation.

`PreparedPlay.stop()` is a state/event latch, not a release of native ownership. The service keeps its backend and journal references; native owners remain with the backend for the existing close/drain path. The changed exception branch neither replaces nor discards those references. No new public ACK or replay permission is introduced.

## Constructor and shutdown boundaries

`service.py:41-65,342-364` initializes journal/watchdog placeholders and every field used by `close()` before attempting directory, journal or watchdog creation.

| Failure point | Reviewed behavior |
|---|---|
| Parent service-directory creation or journal rejection before an owner is returned | `_journal`/`_watchdog` remain None; session/backend stop/close still runs; no None journal close or unstarted thread join occurs. |
| Journal constructor fails with retained `JournalError.cleanup_owner` | The retained journal is adopted into `_journal` before service cleanup. A further cleanup failure exposes the service as `error.cleanup_owner`, preserving the service → journal → index → connection/directory chain. |
| Thread object creation or start fails after journal allocation | The journal is already reachable. `close()` drains existing users and closes it; watchdog join is conditional on a real thread identity. The original constructor exception is re-raised. |
| Cleanup fails | The service is attached as the retryable cleanup owner. `_journal` remains attached and journal operations stay disabled after its failed close. A later `close()` retries; there is no early `_closed` return that would skip ownership recovery. |
| Normal close | Existing order remains backend stop/drain, completion and Stop-persistence thread drain, work-lock acquisition, retained-view/index close, shutdown event and watchdog join. |

Binding/session setup at lines 34–40 remains outside the new protected allocation block. These steps precede service journal/watchdog allocation, and the supplied PREPARED backend is still held by the caller. This patch does not extend its contract to arbitrary errors during those earlier validations. Constructor cleanup ownership is returned through the exception; this review does not claim that every external caller has been audited for consuming that owner.

## Tests and retained evidence

The new module defines 12 tests. It imports fixture modules rather than `TestCase` classes, avoiding accidental rediscovery/inflation. The tests use real JSONL/SQLite for COMMIT, cursor-close, index rebuild, connection-close and unlink faults; fake prepared backends for service lifecycle; and real loopback HTTP with synthetic observation for command-host integration. They check durable bytes, no duplicate append, no backend start, halted subsequent work, stable UNKNOWN lookup, retained owner identity and release of exact scratch directories after retry.

Constructor coverage explicitly includes watchdog-start failure with successful cleanup, watchdog-start plus close failure, and index-constructor failure with cleanup held through disk/journal/service layers. It does not explicitly inject every pre-journal mkdir failure, thread-object allocation failure, or a thread that starts and then raises. Those branches were reviewed statically; no stronger test coverage is claimed.

I read the coordinator's existing `index-checks-01` capture and terminal logs without rerunning them: **95 run, 0 failures, 0 errors, 0 skips**, actual target PID 7008 exit 0, wrapper PID 9380 exit 0, timed_out=false, tree_verified=true, source_unchanged=true. This is the coordinator-owned test run, not an independent execution by this reviewer. Only the three small reviewed source files were byte-compared with that capture's source copies; all three match. No native03 evidence or running process was touched.

| Reviewed file | Bytes | SHA-256 |
|---|---:|---|
| `studio/host/replay/disk_journal_index.py` | 13593 | `56beb93119dfb66feec32eb51d389fc089d89911c0a1be199071c17e1801cb28` |
| `studio/host/replay/service.py` | 19763 | `d8d046ea2144ade026cce7e63a53b52885a28b213193fed19f932a773a9758a5` |
| `studio/tests/replay/test_index_faults.py` | 21552 | `8e22d06e73550cbc98d0a6111909e74e2c2e2cad4b3bd064a3b0ed07bc9721c6` |

Recorded 2026-09-18T06:26:21.310915+00:00. Test evidence: `zdoc/reviews/20260918-gt06-s79-diagnosis/index-checks-01/{capture.json,unit-host.json,unit-stdout.txt,unit-stderr.txt}`. No final critic signature or acceptance is supplied.
