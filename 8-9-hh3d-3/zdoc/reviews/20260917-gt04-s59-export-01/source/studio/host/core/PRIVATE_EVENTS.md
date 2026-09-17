# Retained private event stream

`PrivateEventLog` is the internal storage primitive used by the fixture selector.
It owns a dedicated `PrivateBlobStore` root/ancestor chain and permanent writer
guard, plus a single noninheritable share=0, no-follow, write-through `.events`
handle. The root contains exactly `.writer` and `.events`; it is distinct from
the immutable blob store. Existing blob quota/layout and generic command
journal are unchanged. No client operation or safe-write capability is enabled.

Each frame is a 4-byte little-endian length, canonical JSON and a 32-byte SHA256.
The body includes a format, sequence, previous record hash and event object.
Genesis binds the minted root and actual volume/root/file IDs. Individual
bodies are at most 16 KiB, the stream at most 8 MiB and 512 records. Parsing
streams one record at a time; the resident history index keeps offsets, lengths
and hashes, not every persistent event body. Returned event bytes are immutable.

An append validates/copies input, takes the instance mutex, checks live root/
ancestor/guard/stream identities and protected DACL, flushes and validates the
entire previous chain, compares the exact expected head, and checks capacity.
The same retained handle seeks, writes once with a checked byte count, flushes,
revalidates chain/identity/EOF and reads back the frame before returning a head.
Concurrent commands using the same parent get one append and one conflict.
Optional reserve counts/bytes check remaining capacity only; the typed
selector must persist and reconstruct reservation ownership in its intents.

Reopen always uses existing names and requires trusted root/file identity plus
an acknowledged head witness. It does not create missing files. History is
exposed only after a fresh successful FlushFileBuffers and complete chain
validation, including the witness prefix. Valid newer records may become
visible after a process crash; they are observations requiring explicit command
reconciliation, not permission to repeat effects or return COMMITTED.

Short writes, flush/readback/identity failures quarantine the instance and
report uncertainty. Torn/checksum-invalid/noncanonical/reordered history or a
missing witnessed suffix requires recovery and preserves every byte. There is
no automatic truncation, compaction, retry, tail repair, rollback or deletion.
An old witness alone cannot detect loss of a newer complete suffix. A production
supervisor must obtain the current witness and root identities from durable
custody and require that custody before admitting public mutations.

`bind_custody()` optionally attaches one exact local `WitnessCustody` instance;
it accepts no callback, subclass, wire object or client configuration. The
stored root/stream FileIDs and exact high-water head must match a freshly
flushed and scanned log. Identity sizes are observations, not identity keys:
the same stream's size changes between its creation and later reopen. Binding
does not write or advance custody. A complete log ahead of the saved witness
requires an explicit supervisor reconciliation of selector/file state before
binding; a scan alone does not authorize that decision.

Once attached, custody cannot be replaced or detached. Each custody object has
one log owner, retained until successful log close. The caller still owns the
custody resource lifetime. Append keeps the log mutex through event write,
flush, complete chain/frame/EOF readback and then `persist_binding()`. It returns
the new head only after the custody barrier succeeds. A custody exception,
including an unexpected implementation error, poisons the log and returns
UNKNOWN; the complete event is preserved and never automatically appended
again. The custody implementation must not call back into the log.

Existing unbound internal fixture logs remain supported. That compatibility is
not permission for a supervisor to downgrade or reconnect a public writer
without custody. Reopen still exposes valid ahead records for explicit recovery;
it neither attaches custody automatically nor resumes effects.

At most 16 log owners are strongly retained. Stream close happens before root/
guard close. Failed close retains exact ownership for a later `close()`, even
after a constructor write/cleanup failure or a caller drops its reference.
If the native storage API fails before a `PrivateBlobStore` is constructed,
the event owner also adopts its `cleanup_api` token owner. The top-level
`EventLogError.cleanup_owner` is sufficient to retry cleanup: the log stays in
the bounded ownership registry until that API's actual native close succeeds.
Callers need not retain or traverse nested exception causes.
The mutex has a two-second admission timeout. Native file I/O remains
synchronous: byte/record caps are not a storage-device latency bound; the
supervisor must own a bounded process/job when testing potentially hung I/O.

The trust boundary is the broker versus OS-confined workers. Unrestricted
same-account actors/admins are not excluded by this DACL. No worker receives
the object, root/configuration authority, file/volume/mapping handles or an
impersonating broker thread. S35 proved native counter IPC on its own frozen
closure. S44's file-consumer IPC package integrated this event stream with an
actual confined worker on the S44 frozen closure. That historical proof does
not cover the new S45 registry-custody attachment; native worker proof for that
path is still pending.

NTFS metadata/write-through and FlushFileBuffers are the persistence API
assumptions. Creation flushes the guard and writes/flushes/readbacks a nonempty
genesis. Actual fresh-process reopen and crash-cut tests prove the observed
local NTFS behavior; they do not certify physical power-loss behavior or the
complete release-publication namespace. Hardware/OS persistence assumptions
must stay explicit. Never turn a missing initial store into an empty selector.

`fold()` runs a trusted pure reducer over a single validated guarded snapshot,
reading one event body at a time and checking final EOF before advancing its
witness. A rejected semantic history preserves bytes and quarantines the log.
The reducer cannot perform effects or call back into the log. The internal
fixture selector now supplies typed intent/selection/outcome, revision/fence
CAS, consumer readback and explicit reconciliation; see FIXTURE_SELECTOR.md.
Storage heads alone are not selection generations or command receipts.

Primary references: [CreateFileW caching and NTFS metadata](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew),
[FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers),
[SetFilePointerEx and shared-pointer synchronization](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfilepointerex).

Verification: `python -B studio/tests/protocol/test_private_events.py`, run by
the owned Job runner with actual exit/tree capture. Tests include two concurrent
appenders, a second process denied by the guard, fresh-process read/append,
actual exit at write/flush cuts, partial writes, corrupt/truncated/reordered
history, witness rollback, denied live hardlink attempt and real alias after
close, missing/replaced stream, and retained cleanup ownership. A live hardlink
denial for this access/flag combination does not overturn S30's separate
exclusive-handle counterexample or justify generic project mutation.
