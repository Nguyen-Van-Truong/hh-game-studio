GT-02 / future activation — append-only selector assessment, 2026-09-15

AUTHORITY=0
DESIGN_FEASIBLE=CONDITIONAL
IMPLEMENTED=NO
ACCEPTANCE=NONE
PRODUCTION_SAFE_WRITE=UNSUPPORTED_SAFE_OPEN_WINDOWS

Yes: an append-only activation journal can represent the authoritative active
manifest without replacing a mutable pointer file. It satisfies §2.5 only if
one verified durable record selects an entire immutable release and every
consumer resolves/pins that same generation through the broker. This is a
logical atomic selection, not a claim that a filesystem append is an atomic
multi-sector write. It removes destination-inode replacement/CAS from normal
activation; it does not remove revision/fencing, file identity, namespace
durability, recovery, editor readback or TX15 isolation requirements.

I read the current plan's exact §2.2, §2.5 and TX15, and current
studio/host/core/{safe_open.py,journal.py,JOURNAL.md}. §2.5 requires PREPARED,
VALIDATED, durable ACTIVATING intent and expected source/game revisions, then
immutable release + atomic active manifest + editor reload/readback. It does
not prescribe an active.json pathname or a particular rename API. Interpreting
the manifest as a guarded durable selection is therefore a defensible
implementation choice, provided the original observable requirements hold.
It cannot be used to reinterpret an unsupported operation as supported.

The inspected journal.py SHA256 is
826bc5e4c60817e3a22dd2e0b6a199eb522a4eb78532cb5300249fe9056c0cc6;
safe_open.py is
efc083f1c4fa875d3f748602924a05712aa60fed3abcdb46d058672930201535.
This is a design review, not a review of the concurrent CREATE_NEW experiment
or an independent acceptance of S31's AppContainer probe.

Minimal contract:

1. The broker provisions one private selector store on the tested local NTFS
   volume. It retains a verified writable/readable handle, root/ancestor
   identities and a permanent writer guard; untrusted workers receive no store,
   volume, file, mapping or token handles. All store readers serialize with the
   writer, or read an immutable broker snapshot produced under that guard.
   No pathname-following reader parses the changing file independently. Initial
   store/guard creation and each immutable release name still require validated
   namespace durability. Reopening verifies the trusted store binding; absence
   or identity mismatch is recovery, never automatic empty-store creation.

2. The authoritative value returned by `resolve_active(project_id)` is a whole
   snapshot: `{store_id, store_identity, generation, selection_record_hash,
   release_id, release_manifest_hash, source_revision, game_revision}` plus
   readiness/recovery status. The broker derives paths and identities itself.
   Consumers retain this snapshot while loading all referenced resources; they
   must not ask “latest” separately for each file. The immutable manifest covers
   the complete release closure. A cached active.json, directory scan, mtime or
   filename ordering must never become a second selector authority.

3. The semantic operation `activate_release` uses the existing command envelope
   and payload containing the new release ID/hash and expected parent selection
   token, source revision/hash and game revision. Put semantic parent conditions
   inside the hashed payload: same ID with a different expected parent is a
   conflict. Lease/fence renewal still does not create a fresh command identity.
   Existing lookup/archive/cancel/Stop remain; recovery is a separately
   authorized broker operation, not an untrusted “force” flag.

4. Under the same writer transaction, refresh history, dedupe the command,
   validate lease/deadline and compare the expected parent generation, record
   hash and store/release identities. Persist an activation intent before any
   selection effect. A stale source/game revision rejects before selection;
   a later owner edit is preserved, never overwritten or rolled back. A
   successful compare followed by an unlocked append is not sufficient CAS.
   Reserve bytes/records for the entire intent/selection/outcome sequence before
   admission, including a bounded recovery outcome. Do not hold the current
   non-reentrant lease_guard while calling another public journal method.

5. A framed, bounded SELECT record names one full release and includes sequence,
   parent selection hash, command ID/digest, old/new release hashes, revisions,
   fencing epoch and checksum/hash-chain data. Verify complete write, flush,
   file identity/link count/EOF and readback before exposing the new selection.
   Readers accept only a validated chain after a successful durability barrier;
   bytes visible in page cache are insufficient. A partial or suspect append
   quarantines selection and new admission. The guarded, durably validated
   SELECT is the selection linearization point, not a later mutable pointer.

6. Distinguish “durably selected” from “loaded/read back by the consumer.” During
   ACTIVATING, report the selected generation and last verified runtime
   generation separately. Preserve the running last-good release until verified
   adoption. Return command COMMITTED only after the required consumer readback
   and durable terminal receipt. On reload failure, preserve last-good runtime
   and reconcile: complete the selected generation, or append a new
   revision-checked RESTORE selection pointing to the old immutable release.
   RESTORE increments generation; it does not erase history or reset revisions.
   No consumer may execute unvalidated staging. GT-02 can test this contract on
   a mock consumer; real Godot/Blender reload remains the relevant later gate.

One authoritative event stream should govern selection and command outcomes.
If existing command results remain in a second journal, SELECT must bind its
command ID/digest, and recovery must explicitly reconcile both stores before
ACK or retry. Two independently successful writes are not an atomic transaction.
Do not duplicate effects because a SELECT survived while its command receipt
did not. Terminal results/tombstones and unresolved intents survive retention;
activation records cannot disappear merely because a retry horizon expired.

Crash and recovery semantics:

| Last durable/observed point | Required result after restart or response loss |
| --- | --- |
| Release staged; no activation intent | Old selection. Orphan release is not active. No source file overwritten. |
| Intent durable; no SELECT | Old selection; admitted command pending/UNKNOWN. Lookup/reconcile or durable cancel; never automatic replay of an uncertain effect. |
| SELECT write/flush failed | Outcome UNKNOWN. A complete row may exist but is not acknowledged until fresh barrier, chain and closure validation; partial data requires recovery. |
| SELECT durable; consumer not verified | New durable selection, old last-good runtime. No COMMITTED ACK. Reconcile adoption or append conditional RESTORE. |
| Consumer adopted; terminal receipt missing/failed | Lookup/readback completes the same command/selection. No second activation generation or object. |
| Terminal durable; ACK lost | Replay the original receipt and selected generation. Changed payload conflicts; Stop remains stopped. |
| Truncated/corrupt row, missing selected release, wrong store identity | Quarantine admission and selector; do not fabricate a current release or success. Preserve previously verified running release and all diagnostic bytes; recover from verified state. |

A retained handle and append-only normal operation reduce namespace changes,
but append changes file data/length metadata and still needs checked persistence.
Microsoft documents FlushFileBuffers and NTFS write-through metadata behavior;
that supports a concrete Windows backend to prove, not immunity to storage
failure. Keep actual API failure codes and the storage/OS assumptions in
evidence. [FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers),
[CreateFileW caching behavior](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)

Truncation is not “scan until bad bytes and use the previous line.” The current
Journal correctly rejects malformed/truncated history; preserve that default.
A valid prefix may be useful recovery evidence, but it does not establish the
outcome of the failed append or consumer adoption. Minimal safe handling is
RECOVERY_REQUIRED with preserved bytes and last-good runtime. Resuming writes
after a torn tail needs an explicit, tested repair protocol: checkpoint the
entire damaged store, verify the recoverable boundary and affected admitted
IDs, persist a recovery intent, then repair only that proven tail under the
retained handle/guard, flush/reload and record unresolved outcomes. A crash
during repair must itself be reconcilable. If the boundary or outcome cannot
be proved, remain blocked; do not truncate through an interior corruption or
discard dedupe tombstones. This is a required integration gap for automatic
recovery, not permission to change the accepted generic Journal's parser.

Checksums and parent chains detect changed/reordered records; they cannot alone
detect removal of an entire valid suffix. Any claim of arbitrary log-rollback
detection needs a trusted acknowledged high-water/checkpoint or independent
receipt witness. Ordinary process-crash tests under a successful-flush storage
assumption must not be advertised as physical-media corruption or power-cut
certification.

Existing implementation gaps that must stay visible:

- Current safe_open advertises no create/write/replace capability. Append-only
  selection does not supply the missing OS-confined writer, protected journal
  namespace or release-create primitive. S31 lifecycle proof alone does not
  close inherited-handle, token-duplication, reparse/hardlink/OpenFileById,
  network/secret or IPC authorization coverage.
- Journal._validate_record currently admits only command and lease records.
  Its per-command terminal transition is not a project selection chain or
  expected-parent CAS. Selection/readiness/recovery schemas and validators are
  missing; arbitrary receipt dictionaries must not become trusted activation.
- Journal._load, _append and _DiskRecords reopen by path. They do not implement
  the proposed retained safe handle. Existing _reload fsync and phase-aware
  UNKNOWN behavior remain requirements to preserve, not substitutes for it.
- Journal.compact uses temp + os.replace and rebuilds retained command/lease
  projections. It cannot run unchanged against this selector: it changes the
  handle identity and can lose event-order authority. The minimum bounded
  version may disable selector compaction and reject new admission at capacity;
  rotation/checkpoint publication needs its own identity/recovery proof.
- Current capacity reservation allows one terminal row per pending command.
  Multi-record activation requires a declared larger reservation or a proved
  encoding with equivalent bounded durable state. Source/release closure
  validation, actual consumer pinning/readback and crash reconciliation remain
  separate integration work. No acceptance is inferred from these API sketches.

Minimum additional tests on the exact frozen implementation:

- Two simultaneous commands using the same parent: exactly one new generation;
  the loser conflicts before selection. Retry same ID/digest across lease
  changes and fresh processes returns the same generation; changed parent,
  release hash, source revision or payload conflicts without effects.
- Readers overlap every append/flush/adoption boundary and load several files
  from each release. Every successful snapshot is entirely old or entirely new;
  no mixed-generation assets or success while the store is quarantined.
- Cut real process/IPC execution before/after intent, SELECT, consumer adoption
  and terminal ACK. Inject short/partial writes, failed flush/close/readback,
  ENOSPC and exhausted reserved capacity; prove fresh-process reconciliation,
  one selection effect and correct UNKNOWN/Stop behavior.
- Tear each record class, corrupt checksum/parent order, truncate at a whole-row
  boundary and remove/corrupt a selected closure file. Record which faults are
  detected, which require a checkpoint/witness, and which remain explicit GAP.
  Any implemented tail repair is interrupted at every repair phase as well.
- Attack the store, ancestors and releases by rename, reparse/alias/hardlink,
  file-ID open, leaked handles/mappings and second writer; verify bytes and
  identities outside the allowed root. Repeat while the broker appends and on
  restart. Positive create/read controls must show the worker actually ran.
- Hit cap/retention, late fence/deadline, new owner source edit and failed
  reload/RESTORE races. Preserve source, last-good release, original command
  evidence and generation monotonicity; no silent compaction or resumed Stop.

Recommendation: proceed with the append-only selector as the smaller candidate
design after the broker CREATE_NEW boundary is proven. It replaces the pointer
file mechanism, not the active-manifest semantics. Keep the old reports and
requirements unchanged; this report neither ticks GT-02 nor demands completing
GT-07's cross-application runtime integration during the current fixture work.

Only this new report was written. No production source, plan, previous report,
process profile or ACL was changed; no test/engine/sandbox process or agent was
started for this assessment.
