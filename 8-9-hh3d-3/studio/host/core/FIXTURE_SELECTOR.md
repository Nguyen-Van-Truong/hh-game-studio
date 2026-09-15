# Internal fixture selector transaction

`FixtureSelector` joins `PrivateEventLog`, `PrivateBlobStore` and the fixed
in-memory `FixtureReleaseConsumer`. This is trusted broker code, with no public
operation registration, engine adapter or safe-write capability. The client
cannot supply a consumer, callback, clock, filesystem name or recovery policy.
Each log, store and consumer has one selector owner. Native log/store lifetimes
remain with the caller; closing the selector only releases logical ownership.

The fixture request uses the shared strict Request schema, operation
`fixture.release.activate` and target `{"stable_id":"active-release"}`. Payload
contains `assets`, `entrypoint`, `expected_generation`,
`expected_selection_hash`, `expected_source_revision`,
`expected_source_sha256` and `expected_game_revision`. Asset contents use the
closed inert JSON grammar in FIXTURE_RELEASE.md. The full canonical payload is
limited to 8192 bytes so the entire input can be kept in one durable intent.
Identifiers and revision hashes remain distinct from filesystem paths.

Admission copies and validates input, checks project/command digest, lease,
deadline, source/game revisions and parent generation/hash. A duplicate returns
the saved receipt even after its old deadline/lease expired; it never stages or
selects again. The same ID with a different digest is a conflict. Only one
activation may be pending. The state projection keeps compact command indexes;
terminal receipts are read from the log on demand, not retained in full in RAM.

One private event stream owns CONFIG, LEASE, REVISIONS, STOP, INTENT, STAGING,
STAGED, SELECT, RESTORE and TERMINAL. The pure reducer validates transitions
before append and again during replay under the log guard. CONFIG binds the
project, blob root identity/volume and initial revisions. Persisted intent owns
the entire input and a minted release ID before any asset write. STAGING is
written before the first blob; STAGED binds the checked complete manifest.

Capacity for all assets and a worst-case manifest is checked before intent and
again before staging. Exclusive store ownership and one pending activation
preserve the reservation. Each append reserves remaining worst-case event
bytes/records, including restoration, terminal receipt and a Stop record. A
known capacity refusal before WriteFile has no event effect; uncertain writes
hold admission. No automatic orphan deletion, tail truncation or compaction is
implemented. Preserved orphan files can exhaust this deliberately small store.

SELECT reads back and pins every asset, compares the exact admitted content and
source/base-game metadata, checks current lease/revisions and appends a parent
CAS. Generation increments and the actual selection-record hash identifies the
selection. It is still pending. COMMITTED is appended only after the consumer
has adopted the complete immutable pin and read back generation, selection
hash, release ID, manifest hash and the hash of the actual asset bytes. No
individual file independently resolves a latest version. A failed or missing
receipt after adoption is UNKNOWN, never permission to repeat the command.

`snapshot()` distinguishes selected generation, last durably verified adoption
and the current consumer readback. A fresh consumer is not ready just because
an earlier process committed. Explicit `load_committed()` under a fresh lease
can load that same saved snapshot without reselecting, restaging or writing a
new command receipt. The consumer is a synchronous inert-byte fixture: these
checks do not prove Godot/Blender main-thread or UndoRedo behavior.

Reopen validates existing identities, history and witness; it does not resume
pending work. `reconcile()` is an explicit trusted coordinator decision:

| Durable phase | Allowed recovery |
| --- | --- |
| INTENT | Fresh lease + stage once, or cancel |
| STAGING | Discover one complete matching old manifest, or cancel/preserve |
| STAGED | Fresh lease + select after current source/parent CAS, or cancel |
| SELECTED | Fresh lease + verified adoption, or explicit restore |
| RESTORING | Finish readback/adoption of the restored selection |
| Terminal | Return the original receipt; no command replay |

Discovery uses verified native handles in the retained private store. It finds
the intent's release ID, requires exactly one manifest, pins all dependencies
and checks the original content/revisions. It records the old descriptor
without rewriting blobs. Partial or ambiguous staging stays preserved. A
recovering coordinator can use a new lease after the original deadline; that
authority and fencing epoch are durably recorded. Recovery does not waive
source/game CAS and is not a caller-supplied force flag.

RESTORE appends another generation pointing at the last verified adoption
(or an explicit empty selection before the first commit). It never erases
history or overwrites newer observed owner revisions. Only after consumer
readback does it save an UNKNOWN/restored receipt for the original command.
That receipt is terminal for dedupe: restored does not mean the old command
may run again.

Stop sets an admission event before waiting for the selector mutex and saves a
durable STOP. The signal is checked again after quota scans and pin/readback,
before later staging/selection/consumer admission. An already admitted native
storage operation may finish; Stop is not a hard cancellation bound for a hung
synchronous disk. Before selection it cancels pending activation and explicitly
reports whether staging may exist. After selection it preserves UNKNOWN until
an explicit recovery decision. Durable STOP survives reopen and blocks normal
adoption/new commands; restore remains possible. It is never auto-cleared.

Current limits: clocks/revision observations are trusted fixture inputs, not
proof of external source-file revisions. AppContainer IPC has only exercised
the earlier S35 counter and separate S33 staging, not this selector. The new
transaction needs its own authenticated confined-client proof. Witness custody,
physical power-loss/namespace persistence, damaged-tail repair and engine
consumers remain separate gaps. `safe_write` and `atomic_replace` stay false.

Verification uses the bounded owned Job runner. Tests include source/fence/
parent conflicts, concurrent same-parent admission, capacity before effects,
response loss after adoption, corrupt semantic history, explicit restore and
fresh-consumer readback. Nine actual child-process cuts exit deliberately at
intent/staging/manifest/staged/select/consumer/terminal/restore boundaries.
Each records its actual PID, armed cut marker, host exit, reopened phase and
post-reconciliation generation/blob count. An expected crash exit is evidence
for recovery, not a successful application exit or an independent review.
