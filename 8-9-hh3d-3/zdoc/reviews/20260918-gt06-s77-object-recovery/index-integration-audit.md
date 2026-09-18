# S77 disk-derived journal index integration audit

Date: 2026-09-18, Asia/Saigon. Scope: HH3D tools, GT-06. Read-only source audit; no acceptance verdict, runtime change, engine launch, test execution, or raw-evidence hashing. The only written file is this report.

Observed Git HEAD: `398de65ca4f98cede6646df4b5f1809c4e28de5b`. Tracked `8-9-hh3d-3/studio` status was clean when inspected. The coordinator's native diagnostic was already active; it was left untouched. Line references below describe the source fingerprints at the end of this report.

There is no current `studio/host/replay/journal_cache.py`. The cache consumer is `studio/host/replay/verified_journal.py`. A new `journal_cache.py` could hold the disk store, but should not be confused with an existing implementation.

## Concrete result

The smallest contained route is an instance-owned, disposable disk store behind the two collection interfaces already injected by `VerifiedJournal._load`. Keep `studio/host/core/journal.py` unchanged. Preserve its serializer, validation, guard lock, pending-capacity reservation, journal fsync, tombstone rules, and journal replacement. Change the replay subclass to own the cache transaction/lifetime, and change its two callers to close that resource explicitly.

Replacing only `ProjectCommandIndex` is insufficient: `PackedOffsets._words` also grows with every journal record. Both are currently O(N) retained memory (`journal_index.py:16–57`, `60–123`). Receipt bodies already remain on disk through `_DiskRecords.__getitem__` (`core/journal.py:73–93`). This proposal addresses host Python retention; it does **not** establish the cause of Godot's object-count change or establish a benchmark pass.

Three integration hazards require source changes alongside the new store:

1. A cache write can fail **after** the authoritative journal fsync. Such a failure must invalidate the cache and preserve UNKNOWN/reconciliation semantics.
2. ReplayService currently turns non-missing journal lookup errors into `SafetyViolation`, which its HTTP transport renders REJECTED. A new index failure must not use that path.
3. Journals currently have no owned file handle or `close()` contract. Producer/service constructors, concurrent HTTP calls, and shutdown must acquire explicit ownership of the new resource.

## Existing authority and consumer boundaries

| Source location | Observed behavior | Integration consequence |
| --- | --- | --- |
| `core/journal.py:99–109` | Constructor creates `_DiskRecords`, `_commands`, `_pending`, `_leases`, then calls virtual `_load()` under `_writer_lock()`. | Initialize cache lifecycle state before calling `super().__init__`; bind the new adapters before the inherited parser runs. Constructor failure must release any allocated cache. |
| `core/journal.py:164–213` | Permanent `.guard` inode; OS-exclusive lock; legacy metadata recovery; private-path checks before yielding. | Keep this lock and its acquisition/release behavior. The disk store is not a replacement lock or new authority. |
| `core/journal.py:255–260` | Reload clears all four collections then invokes `_load()`. | New collections must support streaming rebuild and `clear`; failed or partial rebuild cannot remain usable. |
| `core/journal.py:263–283` | All decorated operations, including lookup, lock then reload. `outcome_unknown` is automatically set only when the method was not entered or already completed. | An index error inside `_append` is neither case; explicitly mark it uncertain. A cache transaction commit failing during guard exit is also uncertain. |
| `core/journal.py:289–322` | Streams one line at a time, decodes and validates complete history, populates indexes, then fsyncs before returning. | Keep streaming history validation. Do not rebuild through `list(records)`, `dict(all_commands)`, or `fetchall()`. Mark a generation verified only after inherited recovery fsync and successful cache publication. |
| `core/journal.py:338–340`, `365–370` | Command lookup uses latest-record index; loaded history validates allowed pending-to-terminal transition against that previous record. | The index must support reads of rows inserted earlier in the same rebuild transaction. A latest-record pointer is functional state used during validation, not an optional diagnostic. |
| `core/journal.py:386–423` | `_apply_loaded` updates command/pending/lease state. Append fsync is at 419; `_apply_loaded` at 422 and offset append at 423 occur afterward. | A cache transaction must couple command and offset updates. Any error after 419 poisons the whole derived generation, including pending/lease state until a full reload. |
| `core/journal.py:437–525` | Append/finish/dedupe/archive all read authoritative receipt bytes. Expired command IDs cannot be reused. | Preserve exact project-plus-command keys, receipts, digest conflicts, expiry, and `archive_status`. Never evict old IDs to meet a memory target. |
| `core/journal.py:553–566` | `lease_guard` is expressly non-reentrant and protects a bounded effect. | Do not invoke another journal API from an index callback or hold a cache-only lock through engine work. Preserve the same lock ordering for lease checks. |
| `core/journal.py:574–618` | Compaction streams latest commands, retains every expired ID as a tombstone, fsyncs a temporary journal, replaces journal, reloads. | Support streaming `.values()`. Rebuild offsets for the replaced journal; never carry old offsets through compact. Cache lifetime is independent of journal replacement. |
| `replay/verified_journal.py:31–63`, `84–98` | Every operation hashes the full current journal; a matching identity/size/digest/policy gets a recovery fsync. Changed content goes through accepted full replay. | Keep complete byte verification, inode/device check and policy check. No mtime-only shortcut and no persistent cache startup trust. |
| `replay/verified_journal.py:65–82` | Injects packed offsets and grouped commands; accepted load followed by snapshot and total offset-length check. | Replace the collection injection and establish cache generation validity here. Sum lengths by bounded cursor/SQL aggregate, without materializing offsets. |
| `replay/verified_journal.py:100–123` | Invalidates hash before append; extends cached digest only after successful inherited append and metadata confirmation. | Hash validity must additionally depend on the completed cache transaction. Metadata-stat failure may leave a valid but unverified cache; a disk-store error must leave no reusable generation. |

## Minimal disk-store contract

Recommended implementation shape: one private SQLite database per live `VerifiedJournal`, containing only command keys/latest record indexes and record-number/offset/length tuples. This is a proposal for implementation, not a tested dependency claim. Keep the packed classes available for their existing standalone tests or explicitly migrate those tests; do not silently change their advertised standalone integer/key domain.

- Use an exclusive disposable file/directory in host-owned scratch, not a caller-selected path and not a stable shared cache filename. A fresh journal instance always derives a fresh store from the authoritative journal. No cache is imported into evidence as a durable receipt source. Closing/deleting this scratch must never delete journal, `.guard`, or legacy lock metadata.
- Keep commands and offsets in the same store/transaction. Conceptually: `records(record_index PRIMARY KEY, byte_offset, byte_length)` and `commands(project_key, command_key, latest_record_index, insertion_order...)`. Compound keys must remain exact. Binary, length-preserving encoding of each key independently avoids delimiter, NUL, Unicode normalization and SQLite text-encoding surprises. A command-ID digest alone is insufficient.
- Keep one connection per instance, shared across the finite HTTP/worker threads under one explicit mutex. If the selected Python SQLite connection disables creator-thread enforcement, the mutex is still mandatory. Avoid one connection or cache per command/thread, retained cursors, or unbounded statement/page caches.
- Configure bounded SQLite page/statement caches and disk-backed temporary work; do not use an in-memory database, an ever-growing mmap, or a rebuild transaction whose rollback data is deliberately retained in RAM. These settings need later measurement; they are not proof of constant total RSS. Disk usage still scales with retained history.
- Required offset surface: `len`, integer lookup including negative indices used by tests, streaming iteration, `append`, `clear`. Required command surface: `get`, set, `len`, streaming `values`/iteration and `clear`. A SQL row-count scalar is acceptable; a retained Python list of all keys or offsets is not.
- Compaction needs every latest record once. Prefer preserving the current grouped-project/command-insertion order using stored ordinal columns, so this change does not incidentally change compacted byte order. Iterate a cursor rather than sorting all keys in Python.
- The actual journal's bounded record/byte ranges fit an ordinary database integer representation, but the current standalone `PackedOffsets` tests intentionally cover full unsigned 64-bit words and `ProjectCommandIndex` tests allow values above 64 bits (`test_journal_index.py:33–35`, `88–95`). Either encode the wider standalone domain losslessly in a separate adapter test or keep old types unchanged and document the new internal adapter's actual journal domain. Do not truncate values.
- A cache query/read/commit failure invalidates the store; it never becomes a missing-command answer. Read the receipt from the journal, retain `_decode_record`, and check that a command hit refers to the requested project/command. Scratch is trusted host process state within the same OS-principal isolation boundary as the existing journal; this design should not claim tamper resistance against arbitrary same-principal writes to cache files.

The command/offset optimization does not remove all possible Python growth: `_pending` and `_leases` remain inherited collections. Pending commands are capped at admission; the benchmark repeatedly leases one target. A generalized workload with many distinct lease targets must be measured separately. ReplaySession also deliberately retains up to 64 commands (`replay/session.py:31`, `233–242`); do not erase that history as part of this change.

## VerifiedJournal integration and failure phases

Add explicit `close()` plus an operation/close mutex in `verified_journal.py`. Initialize it and the closed/cache-owner fields before `super().__init__`, because construction calls overridable methods. All cache access, including initialization, reload, mutation, compaction, and close, must participate in this mutex. Retain the inherited OS writer lock inside it. A bounded wait should retain the existing lock-timeout semantics rather than create an unbounded local stall. Preserve the inherited non-reentrancy contract.

An overridden `_writer_lock` is a narrow integration point: local operation gate → inherited writer lock → cache transaction → existing method → cache commit → inherited unlock → local unlock. This lets the inherited parser see its own newly inserted index rows. It also protects a cache connection from lookup/terminal/Stop thread races. A transaction that contains cache rebuild or appends must finish before the verified hash becomes usable by another operation. Do not call a decorated journal method recursively to recover while this guard is held.

On an operational store failure:

1. Invalidate `_verified_hash` and the entire cache generation; roll back/discard the partial cache while retaining ownership of any resource whose close failed.
2. Raise a local `JournalError` with a specific safe code, for example `JOURNAL_INDEX_UNAVAILABLE`, and `outcome_unknown=True`. Preserve the original exception as its cause without exposing paths or database error strings on the wire. Do not turn programmer-contract errors into successful fallbacks.
3. Next operation must rebuild from the full authoritative journal under the same inherited parser/fsync boundary, or remain unavailable. Do not resume using just the old command map with new offsets, or vice versa.
4. Never automatically repeat the business command or append another terminal row. Once recovery succeeds, ordinary lookup returns the durable terminal receipt if one exists. If only pending exists, reconciliation remains required.

At line 419 the journal may already be durable even when the cache failed at 422/423. The current `_mutating` decorator will not infer that fact for a newly invented index error thrown during the method body. Setting the exception's local `outcome_unknown=True` is sufficient for the benchmark transport's existing `_journal_failure` (`core/transport.py:529–537`); changing the accepted transport's error-code allowlist is unnecessary for this path. An untranslated SQLite exception instead reaches the generic transport failure handler and loses the journal-specific stop/admission behavior (`core/transport.py:522–526`).

The same invalidation is needed for cache commit failure after the method computed a receipt, clear/rebuild failure, cache query failure during history validation, and compaction that has already replaced the journal. A metadata-only stat failure in current `_append` has a different treatment: it already suppresses only the optimization and forces a later full replay. Do not extend that suppression to a failed command/offset update.

## Minimal ReplayService edits

| Edit point | Required behavior |
| --- | --- |
| `replay/service.py:33–54`, construction | Initialize nullable resource/thread fields before ownership can be acquired. Wrap journal creation and subsequent watchdog setup so a constructor failure closes the journal and stops any started thread. If cleanup cannot complete, preserve an explicit cleanup owner instead of losing the partially constructed service. |
| `replay/service.py:114–196`, especially 142–146 and 184–193 | Handle uncertain journal admission separately from ordinary validation failure. `admitted_here` is assigned only after `append_command` returns; a durable pending row followed by an index exception occurs before this flag. Halt sessions and stop the backend for a `JournalError` carrying uncertain provenance, publish the bounded UNKNOWN overlay for this ID, cancel only a still-RESERVED permit, and reconcile without launching/replaying. The existing `_record_unknown` can attempt terminal reconciliation, but its failure must leave the overlay and halt intact. Keep ordinary pre-admission refusals as refusals. |
| `replay/service.py:142–143` | Inspect the append result before treating it as a fresh admission. A replayed durable pending/terminal receipt must not fall through into `sessions.start_effect` as though a fresh journal intent was just created. Return/reconcile the same ID without scheduling another effect. This covers a previous uncertain admission not present in `_jobs`. |
| `replay/service.py:252–282` | Preserve the existing rule that a durable terminal beats `_uncertain`, and an uncertain overlay beats a bare pending receipt. Do not overwrite a terminal after a cache failure. Cache recovery must remain available to this lookup path even after work admission is halted. |
| `replay/service.py:284–294` | Replace `need(error.code == 'COMMAND_NOT_FOUND', error.code)` with an explicit missing-command branch and propagation/UNKNOWN handling for other journal errors. Only a successful authoritative missing lookup produces `REPLAY_COMMAND_NOT_FOUND`. Today `need` converts storage uncertainty into `SafetyViolation`, and publication transport emits HTTP 400/REJECTED (`godot-addon/publication_transport.py:197–205`). Minimal compatible fix: re-raise non-missing `JournalError`, which the existing transport emits as UNKNOWN; retaining a safe explicit journal code is optional, but must not alter acceptance claims. |
| `replay/service.py:296–317` | Keep Stop latching before disk I/O. Index failure leaves Stop persistence UNKNOWN, with runtime/work admission already stopped. No SQLite mutex may be taken before the Stop latch/backend stop solely for persistence. |
| `replay/service.py:319–336` | Preserve backend stop/drain and join completion/Stop persistence before closing their journal. Close the journal once new work is rejected and in-flight work is drained, with the journal's own operation/close barrier protecting lookup races. Make close retryable/idempotent; admission-closed and resource-close-complete are different states. Mark final closed success only when cache closure and watchdog drain succeeded. A prior close failure must retain the service/resource for retry. |

The replay transport has independent work, control and Stop request threads; `_work` does not cover lookup, `_complete_launch`, or `_persist_stop` (`service.py:217–250`, `270–308`; `replay/transport.py:61–70`). Holding only `_work` during `close()` cannot protect the database from a lookup that passed `_auth` before `_closed` changed. The journal's own close gate is necessary even if the caller improves its closed flag timing.

Existing probe/adversary drivers call `owner.close()` before `server.close()` (`run_service_probe.py:133–136`; `run_service_adversary.py:285–300`), following the transport's documented owner-drain order. Preserve it. An already authenticated HTTP lookup racing close must either finish under the journal gate or fail safely before using the closed connection. The transport drain later joins active requests. If construction introduces a service exception carrying `cleanup_owner`, both drivers must retain that owner at construction failure; they presently recover only `BackendError` from `PreparedPlay.prepare` (`run_service_probe.py:27–34`, `run_service_adversary.py:118–125`).

## Producer ownership and closure

`CommandProducer` is the workload that retains one journal through all 35 batches (`tests/replay/benchmark_commands.py:94–119`, `268–320`). Its constructor creates the journal at 109, then the host at 110. It initializes host/observer fields but not journal at 99. Its current `close` only closes host and observer (`322–333`).

Minimum edits in this file:

1. Initialize `self.journal = None` with the other owned resources before the constructor's protected allocation block.
2. On successful construction retain exactly one store for the same live journal across batches. Do not create a new journal, compact away history, or reset the command namespace between batches.
3. Close host first, then journal, then independent observer cleanup. Only set `producer.closed` when every required resource closure succeeds. A host drain failure retains the journal because a worker may still write; still attempt independent observer cleanup. A journal close failure retains its owner for another `close()` call and preserves existing `CommandError(..., cleanup_owner=self)` semantics.
4. Make repeated cleanup safe for already-closed resources. A constructor failure after journal creation but before host assignment must still close the journal.

`LoopbackFixtureHost.close` joins its listener service threads and worker, while connection threads are daemon/nonblocking-on-close (`core/transport.py:233–236`, `330–352`). Therefore producer host close alone is not proof that no late HTTP connection can call the journal. The journal operation/close barrier must also cover this caller. A late call must not reopen cache resources.

`CampaignProducer` simply inherits this ownership (`run_benchmark_campaign.py:155–163`). Campaign cleanup checks `producer.closed`, but its explicit `held_handles` sum contains four native owner/probe handles, not a future SQLite connection (`691–701`). Make `producer.closed` contingent on actual journal closure; verify cache handles independently rather than silently treating the existing native handle sum as new database closure evidence.

## Meaningful regression cases for the implementation lane

These are proposed cases; none were run during this audit. Start with engine-free tests after the coordinator's native lane reaches terminal state, then serialize any native evidence work.

| Case | Injection/exercise | Required observation |
| --- | --- | --- |
| Post-fsync command-index failure | Real append bytes and journal fsync complete; fail the command-index update once. Repeat separately for offset insertion. | Error carries UNKNOWN provenance; verified generation is unusable; exactly one authoritative intent exists; lookup/full rebuild recovers that same ID; no effect launched by the failed call. |
| Post-fsync terminal/cache-commit failure | Complete terminal journal fsync; fail index update or transaction commit. | Immediate caller does not claim safe rejection; later recovery returns the original immutable terminal receipt; `_record_unknown` cannot replace it; no duplicate terminal row or effect. |
| Rebuild failure | Fail store clear/insert/query/commit during full reload, including constructor load and compact reload. | No partial generation trusted; next successful attempt rebuilds all commands/offsets; failure holds/cleans owned resources; journal content is unchanged except the already completed accepted append/compact. |
| Existing durability boundary | Fail journal append fsync and cached-read recovery fsync separately, then reopen while fsync still fails. | No cache receipt bypasses `JOURNAL_WRITE_FAILED`/`JOURNAL_DURABILITY_UNCONFIRMED`; successful later barrier recovers only journal facts. Existing verified tests at `test_verified_journal.py:67–91` are useful starting points. |
| External append and replacement | Two independently owned stores over one journal; append/lease using the other accepted writer; replace with same bytes; truncate; corrupt same-size bytes while preserving mtime. | Rebuild on identity/content change; no stale offsets or leases; corruption/truncation rejected by accepted parser; no receipt from the old generation. Extend `test_verified_journal.py:38–65`, `103–117`. |
| Restart and tombstones | Pending→terminal, expired terminal, expired pending, cross-project same ID, legacy tombstone without archive body; compact repeatedly; close and reopen. | Exact original receipt/archive status retained; expired IDs remain non-retryable; expired pending never upgraded to COMMITTED; missing legacy body remains explicit. Port relevant cases from `tests/protocol/test_journal_retention.py:24–86`. |
| Recovery generation identity | Delete/discard cache between closes; leave a stale cache file from another instance; change profile/limits. | Fresh construction always replays the authoritative journal; stale scratch cannot authorize a command or bypass a smaller cap. |
| Exact keys and streaming | NUL/separator/prefix/Unicode-distinct keys, multiple projects, overwrite latest pointer, iteration and compact. | No aliases; all latest records exactly once; no N-sized Python materialization. Preserve accepted key behavior rather than assuming SQL collation equivalence. |
| Real concurrent HTTP | Tiny authenticated fixture with work/lookup/cancel or Stop, plus completion writer and two separately constructed journal owners. | No SQLite creator-thread failure, interleaved transaction, stale dedupe, lost offset, or duplicate effect. Existing four-process cached writer test (`test_verified_journal.py:126–165`) covers process concurrency only; add same-instance HTTP-thread coverage. |
| Service uncertain admission | Inject post-fsync index failure before service sets `admitted_here`; use the actual service transport. | Wire result UNKNOWN, sessions stopped, backend starts remain zero, overlay available, same-ID retry never starts a new effect, different-ID work remains refused. |
| Service lookup failure | Fail store read/rebuild on `control.lookup`, with and without an overlay; also test actual authoritative COMMAND_NOT_FOUND. | Storage uncertainty is never HTTP REJECTED or invented missing; durable terminal wins once recovery succeeds. Missing remains distinct. |
| Close racing lookup and Stop | Pause a lookup after authorization; start close; release lookup. Separately let Stop-persistence/completion hold the journal. | Lookup completes or safely fails without use-after-close; journal closes only after active operation exits; no new connection after close; Stop still latches before persistence waits. |
| Constructor/cleanup failure | Fail after store creation, host construction/start, watchdog start, database close, and scratch unlink; repeat close. | Every resource remains owned until released; independent cleanup still attempted; no false closed flag; no leaked file handles or deleted journal/guard. Existing producer cleanup tests should gain journal assertions. |
| Retained-memory objective | Engine-free bounded growth test over multiple sizes, retaining one journal; inspect Python allocations and DB resource count; later measure native host RSS/handles under the unchanged campaign protocol. | No retained Python command dictionary or offset array scaling with N, no per-command connection/cursor growth. A `sys.getsizeof` wrapper check alone is insufficient because it omits native SQLite allocations. Do not infer campaign acceptance from this test. |

Existing `test_journal_index.py` integration tests inject only the in-memory packed types into a test-only subclass (`120–127`). They do not exercise a new disk-store consumer or its close behavior. Add actual `VerifiedJournal` coverage and explicit cleanup to `test_verified_journal.py` (currently instances are left open, including reopen expressions at 91/97). Extend `test_service.py:232–268` with failures at the real post-fsync index boundary, rather than only mocking the whole `finish_command` call. Extend `test_benchmark_commands.py`'s actual tiny HTTP fixtures and constructor/close cases; do not run the full campaign as a unit test.

## Implementation file lanes

- Store/subclass lane: `studio/host/replay/journal_index.py` or a new `journal_cache.py`, `verified_journal.py`, and their direct tests. This lane owns error normalization, transactional generation invalidation, bounded memory settings, threading and close contracts.
- Service lane: `studio/host/replay/service.py`, `studio/tests/replay/test_service.py`, and construction-failure retention in probe/adversary drivers only if the new cleanup-owner contract requires it. Depends on the store lane's uncertainty/close interface.
- Producer lane: `studio/tests/replay/benchmark_commands.py`, `test_benchmark_commands.py`, plus any narrowly required cleanup assertion in the campaign driver. Depends on the same interface. No accepted core Journal or transport change is needed for the proposed route.

Do not swap code beneath the active native diagnostic. Integrate after its terminal process/cleanup evidence is retained, then freeze a new complete source closure. A native diagnostic using the earlier closure cannot validate the newly integrated disk index.

## Source fingerprints

SHA-256, source files only:

| File beneath `8-9-hh3d-3/` | SHA-256 |
| --- | --- |
| `studio/host/replay/verified_journal.py` | `9128749e6a04242106e56a86e959b6de0a67e0f10ffb97965e1bc88390d5a6f2` |
| `studio/host/replay/journal_index.py` | `e7b505a928f3100173007413bb9b3f914931bd2431a5033280a309cc4c4ca5c6` |
| `studio/host/core/journal.py` | `826bc5e4c60817e3a22dd2e0b6a199eb522a4eb78532cb5300249fe9056c0cc6` |
| `studio/host/replay/service.py` | `a09641c7954938aebf1207bd37bf66825eb483e51e7c386032b09fcde496121a` |
| `studio/tests/replay/benchmark_commands.py` | `522e91341eda6175704b692cd9bc5454951f93a891657e815a9a2111cd3eb438` |
| `studio/host/core/transport.py` | `1ec03356b1cb8c8987e1604bcb164aea6a9934dbe259451c19e12de36398aba0` |
