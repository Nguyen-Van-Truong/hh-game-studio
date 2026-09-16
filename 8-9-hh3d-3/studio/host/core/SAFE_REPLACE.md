# Protected Windows replacement experiment

`ProtectedFileRoot` creates a fresh owner-only NTFS root, pins its ancestors,
checks canonical handle paths/FileIDs/types/link counts/security, and retains
one writer guard. It accepts bounded single-component names and bytes. It
cannot adopt an arbitrary shared writable directory.

The trust boundary is broker versus OS-confined workers. DACL and AppContainer
token exclude untrusted writers. Unrestricted processes using the broker's OS
account, or administrators, have broker authority. Sharing modes and random
names alone do not establish isolation. Workers never inherit broker handles.

The target is checked against FileVersion (volume, FileID, size, SHA-256) and
remains open without write sharing. A protected stage is created, made
delete-pending, checked for remaining links, written/flushed/read back, then
made non-pending. FileRenameInfoEx replace/POSIX switches the name while the
old handle remains held. Final path/identity/bytes and old bytes are checked;
the parent is flushed. Target CAS depends on the protected namespace, writer
guard and mutex, not rename flags. A shared writable folder is unsupported.

Failures after staging starts are UNKNOWN and poison the instance. Cleanup
does not delete a published pathname. Failed native closes remain owned for
retry. API constructor errors retain unclosed token ownership in the local
cleanup_api exception field. Handles and cleanup objects never go to clients.

Reopen requires trusted saved root identity and initially is read-only. confirm_barrier
revalidates and flushes a known file/directory without rewriting or enabling
mutation. The private ManagedFixtureOwner may rearm only a verified terminal
active.json under durable custody/fresh fencing; orphan/pending/Stop stay held.
Cache readback cannot clear uncertainty alone. Five actual process
cuts prove old/new visibility on this host; they are not power-loss proof.

FileFixtureReleaseConsumer publishes the complete inert fixture snapshot to
the fixed active.json name. Selector CONFIG binds its root identity. COMMITTED
requires actual file readback and the journal terminal barrier. Duplicate IDs
return prior receipts. Lost-receipt recovery may confirm exact selected bytes
without another replace. Mismatched bytes cannot be overwritten on reopen;
the write hold requires verified supervisor reconciliation. MANAGED_FIXTURE.md
defines the bounded terminal-state restart owner. No engine consumer or public
discovery registration is provided by these internal building blocks.

Provision files in a dedicated parent: a peer journal/blob store holds shared
ancestors without write sharing and can block a flush of that same parent.

Research, 2026-09-16: Microsoft documents that
[POSIX rename flags](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information)
allow replacement while old handles remain usable; no expected FileID field
is provided. The
[Win32 rename structure](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info)
uses native pointer alignment and UTF-16 byte length. ctypes derives offsets;
the buffer reserves terminator/padding and final-path checks remain mandatory.

Public safe_open.safe_write and atomic_replace remain false. Fixed native
probes and unit tests are implementation evidence, not acceptance reviews.
