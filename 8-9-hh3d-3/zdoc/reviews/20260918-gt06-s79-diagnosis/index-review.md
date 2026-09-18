# S79 independent index fault review

AUTHORITY=0. Supplemental diagnosis and repair draft; not a final critic, acceptance verdict, campaign result, or permission to change a gate. Reviewed 2026-09-18, final probe at approximately 06:18 UTC / 13:18 Asia/Saigon. Initial HEAD: `4fcdb0c9a2452a9aa52a5a483d6bdfd4e52c46fd`. Nested `8-9-hh3d-3/AGENTS.md` and current GT-06 plan were read. No runtime source was edited and no engine was launched. The coordinator's S79 native diagnostic was left alone.

Three concrete fault-handling gaps reproduced. None establishes the cause of the S78 campaign's ObjectDB growth. The actual campaign command workload uses `LoopbackFixtureHost`, not `ReplayService`; the distinction is tested below.

## Findings and minimal repairs

### P1 — ReplayService leaves a durable uncertain admission pending and admits a new effect

Location: `studio/host/replay/service.py:142–146,184–194`, with lookup at `271–301`.

Inject one real SQLite `COMMIT` failure in the derived index after the authoritative pending JSONL row has been written and fsynced. `VerifiedJournal` correctly raises `JournalError('JOURNAL_INDEX_UNAVAILABLE')` with `outcome_unknown=True`. However, `submit()` has not reached `admitted_here=True`. Its exception branch only cancels the reserved permit; it neither halts sessions nor records an UNKNOWN overlay. The durable receipt now represents a command that has no job and will never run.

Observed with the real journal/session implementation and a deliberately fake backend:

- Exactly one pending intent was added for `command.first`; no `_jobs` or `_uncertain` entry was created.
- `sessions.status()['stopped'] == False` and backend starts remained zero immediately after failure.
- Same-ID lookup returned `ACCEPTED_PENDING`, although no worker exists for that ID.
- A new `command.next` was admitted and started the fake backend once.

Repair: catch the exception as a value, identify uncertain `JournalError` independently of `admitted_here`, latch sessions and stop the backend, then call the existing `_record_unknown` for that ID. Preserve its rule that an already durable terminal receipt wins. The submitted command must not be rerun. The draft produces one pending row plus an UNKNOWN terminal, lookup UNKNOWN, admission stopped, and zero starts on the next ID.

This finding concerns ReplayService. A separate tiny actual HTTP probe against the campaign's `LoopbackFixtureHost` confirms that an ordinary index `COMMIT` failure already returns UNKNOWN / `JOURNAL_INDEX_UNAVAILABLE`, closes admission, yields UNKNOWN / `RECOVERY_REQUIRED` on lookup, and performs zero effects. Do not attribute ReplayService's behavior to the benchmark path.

### P2 — SQLite cursor-finalization errors bypass index normalization and fail to stop the benchmark host

Location: `studio/host/replay/disk_journal_index.py:113–124`; downstream `verified_journal.py:49–66,180–194` and `studio/host/core/transport.py:507–537`.

`cursor.close()` runs in a `finally` outside the `except sqlite3.Error` region. An injected `sqlite3.OperationalError` from close therefore escapes as a raw SQLite error instead of `DiskIndexError` and then an uncertain `JournalError`.

Two independent boundaries reproduced:

- After authoritative append/fsync: one JSONL row exists; append's fingerprint is invalidated, but the escaping `OperationalError` has no `outcome_unknown` provenance.
- During cached lookup: the raw error escapes and `_verified_hash` remains usable instead of requiring a rebuild.

The actual benchmark HTTP path returned UNKNOWN / `TRANSPORT_FAILED` for the post-fsync variant, but `host._stopped.is_set()` stayed false because the generic exception handler does not execute `_journal_failure`. Lookup eventually reconciled to UNKNOWN / `RECOVERY_REQUIRED`; the first request performed zero effects. This is a specific failure-path gap, not evidence that cursor finalization caused any recorded campaign failure.

Repair: nest execution/fetch plus cursor finalization inside the same outer `try/except sqlite3.Error`. Let the existing `DiskIndexError` → uncertain `JournalError` path poison the fingerprint and latch admission. No accepted-core transport edit is needed. The draft makes both journal probes return uncertain `JournalError`, poisons the lookup generation, and makes the actual benchmark HTTP probe stop admission.

The close error here is deliberate fault injection around a real SQLite cursor. This review does not claim the pinned SQLite naturally produced that error, or prove its frequency/reachability under ordinary disk faults.

### P2 — ReplayService constructor does not close or transfer journal ownership after watchdog-start failure

Location: `studio/host/replay/service.py:33–54`, close at `327–348`.

Once the journal has allocated its private SQLite connection/directory, a later `Thread.start()` failure exits the constructor without calling close and without attaching a cleanup owner. The caller does not receive the partial service. In the probe, the connection remained live, `_cache_closed == False`, and the exception had no `cleanup_owner`. A second probe armed a database-close fault as well; the original source did not attempt cleanup or transfer ownership at all. Eventual garbage collection is not a deterministic resource handoff.

Repair: initialize nullable journal/watchdog and lifecycle state before protected allocation; wrap journal creation/watchdog startup; close on constructor failure; preserve a journal constructor's existing cleanup owner; and attach the partial service if cleanup itself fails. Make close tolerate a missing journal and an unstarted/missing watchdog. The draft closes the normal failure path and, when close is faulted, returns the exact service owner whose next `close()` releases the retained journal.

## What passed without a repair

The unchanged S78 implementation passed five bounded probes:

1. Post-fsync index COMMIT failure is uncertain; subsequent locked lookup rebuilds; same-ID append replays the one original row rather than duplicating it.
2. Connection-close failure retains the exact journal/index owner, blocks operations, and succeeds on explicit retry without deleting JSONL.
3. Scratch-unlink failure retains the owner after the database has closed; retry removes only scratch and preserves JSONL.
4. An index insert failure during a full rebuild leaves the fingerprint invalid; a later full replay recovers both authoritative commands.
5. Normal index COMMIT failure through the actual campaign command HTTP transport stops admission and reconciles without an effect.

No incorrect JSONL overwrite, duplicate durable admission, or successful receipt from a partial rebuilt index was observed in these probes. Coverage is bounded and does not establish absence of other faults.

## Reproduction and draft validation

Files beside this report:

- `index_fault_probe.py`: 11 independent desired-contract checks using real temporary JSONL/SQLite state. Service probes use the existing fake backend; two command-host probes use actual loopback HTTP with a synthetic observer. The draft imports no engine executable and launches no engine.
- `index_fix_draft.py`: creates the patch or loads candidate changes into Python modules in memory for a bounded check. It never changes runtime source files.
- `index_fix_draft.patch`: minimal proposed changes to only the disk index and ReplayService. Apply from `8-9-hh3d-3` after the coordinator releases the current runtime freeze; it has not been applied here.

Run from `8-9-hh3d-3` with the local Python 3.11 interpreter:

```powershell
python -B zdoc/reviews/20260918-gt06-s79-diagnosis/index_fault_probe.py
python -B zdoc/reviews/20260918-gt06-s79-diagnosis/index_fix_draft.py --check
```

Observed final unchanged-source run: 11 tests, 5 pass, 6 assertion failures, 0 errors, 1.045 s test time, host-captured exit **1**. The six assertions represent the three findings above, not six distinct defects.

Observed draft check: 11 tests, 11 pass, 0 failures/errors, 1.016 s test time, host-captured exit **0**. Runtime bytes remained unchanged. An earlier draft check failed an overly restrictive probe assertion that allowed only one total row: the repair legitimately adds an UNKNOWN terminal after the single pending intent. The final probe explicitly permits that reconciliation and still requires exactly one pending admission and zero later effects.

These are unowned local shell probes, not acceptance evidence: no approved owned-run launcher/Job/process-tree receipt, frozen execution closure, final critics, or native verification is claimed. The source hashes printed by `--check` describe the unchanged files on disk; the executed candidate is the explicitly marked in-memory draft. Promote meaningful cases into the runtime test suite, freeze the repaired source, and run the coordinator's required checks. Do not reuse S78 evidence as proof of the repaired source.

Existing `test_disk_journal_index.py` has five mapping/order/rollback/basic-close tests, without these failure cases. `test_verified_journal.py` covers journal fsync and history refresh but no SQLite close/commit/constructor fault injection. The S78 72-test invocation omits `test_verified_journal.py`; its broad green counts do not prove these fault semantics.

## Source and draft fingerprints

SHA-256; paths below are relative to `8-9-hh3d-3` unless prefixed with `review/`, which denotes this report's directory. Reviewed runtime paths had no Git diff at the final check.

| File | SHA-256 |
| --- | --- |
| `studio/host/replay/disk_journal_index.py` | `a89792950a2afefd78d335e1a962739f8fb1382598d476d9ea1b98f365b43492` |
| `studio/host/replay/verified_journal.py` | `129baa4d9e08c8a1d5acf2ea05c9c89a4fdddb53ca6f3baf2d61311ab98e62ab` |
| `studio/host/replay/service.py` | `39f23e1dd9ed77a14a259da0bc3b0adac9d032a10b2ac26bff1e5b87e8ef3207` |
| `studio/host/core/journal.py` | `826bc5e4c60817e3a22dd2e0b6a199eb522a4eb78532cb5300249fe9056c0cc6` |
| `studio/tests/replay/test_disk_journal_index.py` | `4d9b1736dab81487c806fd15178ec40f1c3c6431d327687b914505c07717b957` |
| `studio/tests/replay/test_verified_journal.py` | `6082317fa113c8d3e5346942535b9577fa38a26cd448503a4bcd4aed5f342975` |
| `studio/tests/replay/test_service.py` | `153cf61db0a4a4b87aa1a3e6300ffc14b99f1bc41b95c51e3adebdb779d4dfe9` |
| `review/index_fault_probe.py` | `8e8357fd2566400eea863e7adf397b1ccce0de6352dbad6bfd5c6778f18a53ae` |
| `review/index_fix_draft.py` | `7e3596ba03aa8eb2c0dd37ef430cda89712f3185e2de66ebafe6c1562c3022a9` |
| `review/index_fix_draft.patch` | `d0d0a4713cf0b92f4438b4ddc0118b4aa3142cff65f2d6a15e4ce7c3455fe744` |
