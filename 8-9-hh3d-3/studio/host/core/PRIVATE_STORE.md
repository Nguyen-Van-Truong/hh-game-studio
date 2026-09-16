# Experimental Windows staging store

`private_store.py` is an internal broker building block. It is not registered
in transport/discovery and does not change `safe_open.capabilities()`. A
`StagedBlob` is local metadata for staged bytes, not a COMMITTED response,
published release, safe-write capability or recovery decision.

The broker mints a fresh root under a configured local NTFS parent. It retains
all ancestor/root handles without write/delete sharing, and a share=0 writer
guard. Every new object receives the same explicit protected owner DACL at
creation, without inherited or package grants. Owner/DACL, canonical handle
path, volume/FileId, reparse/type, delete-pending and link count are verified.
Reopen requires the saved trusted root identity and the existing guard; it
never creates a missing store or guard.

`put_bytes` accepts only immutable bytes, at most 1 MiB, and mints the basename.
The store permits at most 64 blobs/8 MiB, counting existing partial files on
reopen. CREATE_NEW collisions preserve the original. The same noninheritable
handle performs write-through WriteFile, checked byte count, FlushFileBuffers,
bounded readback and final identity/security checks. A short/failed write is
not restarted. The method returns a descriptor only after successful close.
An empty blob still passes creation, flush and readback checks.

Partial staging and uncertain flush/readback/close preserve the file and poison
the instance. It refuses new writes until the external broker reconciles the
command. Handles whose native close fails remain in an ownership registry;
`close()` may be called again to finish cleanup. Constructor failures after
root creation report uncertainty and retain `cleanup_owner` in the local
exception. API initialization also registers token handles; a failed token
close retains a local `cleanup_api` owner for retry. These objects are never
serialized or exposed to a worker. Cleanup
closes owned handles; it does not delete staging, restore ACLs, kill arbitrary
processes or remove a possibly published file.

`reopen` validates storage identity and reacquires the writer guard. It does
**not** determine the outcome of an earlier put, repair a truncated journal,
authorize replay of an old command, or clear a durable broker recovery hold.
The fresh-process test proves reading a known complete staged blob only.
Production integration must check durable recovery/lease/dedupe state before
admitting commands. No activation or namespace durability ACK is implemented.

The trust boundary is the broker versus OS-confined workers. Unrestricted
same-account processes, the trusted user and administrators can act with broker
authority; directory randomness and share modes do not remove that authority.
No untrusted worker may inherit/duplicate these handles, receive this Python
object, choose ACLs/paths/flags or run inside the broker process. Thread
impersonation is refused on initialization and each operation. Actual worker
isolation, parent ACL rights, network/IPC and native alias attacks remain
separate mandatory integration proofs. A matching DACL alone is not that proof.

The next layer must bind bytes-only IPC to the actual worker, journal command
IDs and lease/fencing, and publish a complete immutable release through an
expected-generation selector with crash/recovery/readback. That layer owns
durable namespace/terminal barriers and one-effect replay; current staging
does not borrow those guarantees from successful local readback.

Primary API contract: [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew),
[GetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo),
[FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers).

Verification: `python -B studio/tests/protocol/test_private_store.py`. Windows
tests use owned disposable roots; platform skips do not prove another OS. The
candidate runner also executes the existing protocol/bootstrap regression
against an immutable snapshot, captures actual process exits, and hashes the
full source closure. These results are implementation evidence, not two
independent acceptance reviews.
