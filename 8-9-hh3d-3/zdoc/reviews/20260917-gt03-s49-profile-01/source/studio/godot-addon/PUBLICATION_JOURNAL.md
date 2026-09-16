# S48 Godot publication journal

This is an internal durable adapter for `publication_state.py`, using the
unchanged GT-02 native storage and exact `WitnessCustody` types. It records and
replays typed observations. It does not stage a scene/script pair, run Godot,
verify claimed engine observations, select an active release, restore writes
after restart, authenticate commands, or issue a public save ACK. A synthetic
COMMITTED record remains `public_ack=false` and `execution_permitted=false`.

All core imports use `studio.host.core`; loading duplicate `host.core` classes
does not satisfy the native exact-type boundaries. A single owner retains the
Registry leaf, file writer guard, blob store, event log and custody under one
bounded mutex. Blocking device calls require an externally bounded process.
For fresh root checks it also uses the existing internal read-only
`ProtectedFileRoot._check(mutation=False)` and `PrivateBlobStore._check()` under
their native-owner locks before and after folding. These verify live handles,
ancestors, guard identity and ACLs; cached root identities alone are insufficient.
No GT-02 code changes, readonly-bit changes or fixture rearm hooks are involved.
The sibling reducer module is bound to its resolved path and SHA-256, and the
exact hashed bytes are compiled. Different snapshots cannot silently reuse a
previously cached reducer from another checkout.

`PublicationJournal.create(parent, storage_id=..., config=...)` requires an
absolute existing parent owned by the caller inside its protected workspace
boundary. This is a trusted local provisioning API, never a worker-selected
path. Native primitives check original path identity, ancestors, links, ACLs,
NTFS and permanent writer guards. Bootstrap must provision the protected
Registry base; `storage_id` is a freshly minted lowercase UUID hex leaf.
`config` is the pure reducer CONFIG object without `store_identity`; the
adapter supplies that identity from the actual newly created blob root.
It validates CONFIG before provisioning and validates the identity-bound
prospective event again before appending it.

`append(event)` first computes the complete prospective pure state. Invalid
shapes, phases, project revisions or invalid observation shapes never reach native
append. It then verifies custody/current head, uses native expected-head CAS,
flushes and reads back the event through `PrivateEventLog`, persists the exact
custody high-water, folds the complete native history again, and compares the
read-back canonical events with the prospective history. Native GENESIS is
checked and excluded from the pure reducer; native sequence 2 is pure CONFIG
sequence 1. Bounded future event capacity is reserved in the native log; this
does not reserve candidate blobs or provide publication capacity admission.
Candidate blob descriptors themselves remain supplied attestations: the journal
does not open their object IDs or verify candidate bytes. The future publication
owner must read actual descriptors/bytes before relying on them. Only the native
root/custody/event identities and the persisted event contents are verified here.

`snapshot()` and `lookup(command_id, digest=None)` recheck the complete durable
history and protected custody before returning detached data. Exact retry
lookup returns the original internal receipt without adding an event. A changed
same-ID digest is a known no-effect rejection; it preserves the healthy owner,
original lookup and Stop path. An unexpected native head, root/custody identity conflict, or any
ambiguous native append/read/barrier failure holds the owner. It cannot silently
retry that append or serve a previously cached snapshot as current evidence.

`reopen(storage_id, project_id=...)` resolves only the exact protected custody
record. It obtains the native file guard, reopens all recorded roots/stream by
typed identities, verifies the complete chain, and refuses a stream ahead of
the saved custody witness. It does not advance custody merely because a suffix
has valid checksums. Every reopened owner is permanently read-only, including
one whose last record is COMMITTED. Pending, UNKNOWN and STOP state survives;
no effect or write resumes automatically. No fixed fixture consumer rearm hook
is used. Actual selected-file/engine reconciliation and write rearm remain
separate unavailable work.

`close()` stops on a failed native close and retains that owner plus its
ancestors for retry. Constructor and runtime errors expose `cleanup_owner`;
callers must retain it until close succeeds. The adapter never deletes roots,
Registry leaves, incomplete records or candidate data. Tests alone clean up
their fresh owned temporary roots and exact verified Registry leaf; they never
delete shared Registry parents.

`test_publication_journal.py` uses real Windows protected roots, native event
flush/readback and Registry custody. Fault injection occurs only in these
trusted tests. Supplied engine/file metadata is explicitly synthetic, including
the internal COMMITTED path. Passing these tests proves neither actual engine
save/reopen nor GT-03 acceptance. S47 evidence does not apply to this S48 source.
