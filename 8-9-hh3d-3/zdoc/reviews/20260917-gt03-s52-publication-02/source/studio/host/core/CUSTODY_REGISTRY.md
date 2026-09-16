# Windows registry custody anchor

`RegistryCustody` is trusted local broker infrastructure. It stores one opaque
bounded value below `HKCU\Software\HHStudio\ManagedFixture\v1\<local_id>`,
where the ID is exactly 32 lowercase hexadecimal characters. It is not a
transport operation, command journal, arbitrary registry API or public
safe-write capability. No worker supplies the ID/provisioning authority.

The OS registry namespace, broker user SID and protected owner-only DACL form
the bootstrap anchor. Reopening does not trust a filesystem record to identify
itself. Ordinary unrestricted processes using the owner account and
administrators have broker authority; this does not prevent their coordinated
rollback of the registry and file stores. Worker AppContainer isolation must
be proved with the actual launch/access configuration.

## Provisioning and API

`provision_base()` is a separate trusted setup call. It opens `Software`, checks
its actual native user-hive path, then opens each product component without
following a registry link. Existing product keys must already have the exact
expected owner/protected DACL; setup never rewrites an existing ACL. Missing
components are created one at a time with the explicit descriptor and must
return the newly-created disposition. A collision fails. Setup flushes created
keys and returns their native paths for the setup record. Partial setup is
preserved and reported uncertain, with `created_components` on the exception.
These shared product keys are configuration, not disposable test keys.

On this task's initial read-only check, the product base did not exist. The
coordinator explicitly authorized this setup mechanism; ordinary
`create()`/`reopen()` still open the base without creating it. Tests and native
probes may create/delete only their unique recorded UUID leaves after setup.

The fixed public-to-host API is:

```python
RegistryCustody.provision_base()       # Explicit local setup only.
state = RegistryCustody.create(local_id)
state.read()                          # None only on fresh live empty creation.
state.store(data, expected=None)       # Exact bytes; <= 16 KiB.
state.store(next_data, expected=data)
state.close()
state = RegistryCustody.reopen(local_id)
state.read()                          # Fresh checked flush before exposure.
state.local_id                        # Read-only binding value.
```

`create()` refuses an existing leaf and creates a nonvolatile leaf with a
flushed `Format` marker bound to its ID. If the process exits before its first
`State`, that existing empty key is incomplete provisioning: reopen fails
`CUSTODY_INCOMPLETE_PROVISIONING`, and create still refuses the collision.
Missing keys fail `CUSTODY_KEY_MISSING`. Neither path repairs, resets or adopts
an empty/corrupt object. Zero-byte `REG_BINARY` data is valid and distinct from
an absent `State`. Once data has been stored or observed, losing it never makes
the current instance fresh again.

The supervisor owns the typed canonical record, checksum, project/file-root
bindings, witnessed event head, monotonic epoch, receipts and recovery policy.
This primitive checks type, size and exact bytes; it does not recognize a
semantically old or checksum-invalid supervisor record. It must not be used
without those upper-layer checks.

## Ordering, ownership and failures

Every operation rejects impersonating threads, checks the retained product
key paths, exact owner/DACL and marker. Open uses `REG_OPTION_OPEN_LINK` and
the explicit 64-bit view. `SymbolicLinkValue` is forbidden. A separate ordinary
open must resolve to the same native key name, so incomplete/broken link
objects are rejected as well. `NtQueryKey(KeyNameInformation)` supplies the
native handle path; an unavailable/failed native query fails closed.

`store()` validates immutable bytes and the expected value, locks the instance,
checks current security, flushes and compares the actual prior value, calls
`RegSetValueExW` once, calls checked `RegFlushKey`, reads back exact type/bytes,
then checks security/path again. Any failure once set begins is
`CUSTODY_STORE_UNCERTAIN` with `outcome_unknown=True` and poisons that instance.
The method does not retry. A stale expected value is a no-write conflict and
does not poison. A fresh reopen must flush successfully before exposing bytes
left visible by an earlier failed barrier; visibility alone is insufficient.

There is one strongly retained local owner per ID, bounded to 16 active/cleanup
owners. A second instance in that Python module is refused. **Registry
compare-then-set is not cross-process CAS:** before updates, the supervisor
must own the project's unique file writer guard and preserve it through the
update/readback. A local mutex or registry key handle does not exclude another
unrestricted broker process. No lease, fencing or independent-process lock is
invented here.

Native registry handles, token handles and LocalAlloc security/SID allocations
are registered as soon as owned. Successful native close/free removes them;
failed closes/frees remain owned for explicit retry, including constructor
failures. Local `cleanup_owner`/`cleanup_api` exceptions and
`pending_custody_cleanup()` retain access to cleanup without serializing it to
workers. `close()` stops use and releases the local ID only after all cleanup
succeeds. Cleanup never deletes keys, changes ACLs or resets state.

RegFlushKey can block and flushes its hive. The calling host must provide a
bounded owned process/job and responsive Stop admission outside synchronous
disk work. This implementation does not promise a storage latency bound or
certify physical power-loss behavior.

## Verification and limits

`python -B studio/tests/protocol/test_custody_registry.py` exercises native
create/reopen and exact binary values, stale expected values, malformed IDs and
oversize/type corruption, actual fresh child reopen, three deliberate process
cuts, native configured and unfinished registry links, actual DACL change,
and retained key/token/security-allocation cleanup failures. Owner comparison
and the impersonation rejection branch have injected unit coverage; that is
not an actual alternate-owner/impersonation attack claim. Focused evidence
uses the bounded owned Job runner with actual exit/tree capture. A separate
native AppContainer denial/positive-control lane is required for the worker
boundary, and whole-candidate exact-source critics remain separate.

Each test records a newly minted absent UUID leaf, closes native resources,
reopens that exact leaf without following links, verifies its actual native
path, deletes that handle with `NtDeleteKey`, and confirms absence. It never
recursively deletes or changes shared product parents.

Microsoft documents nonvolatile creation and explicit security descriptors in
[RegCreateKeyExW](https://learn.microsoft.com/en-us/windows/win32/api/winreg/nf-winreg-regcreatekeyexw),
open-only and link options in
[RegOpenKeyExW](https://learn.microsoft.com/en-us/windows/win32/api/winreg/nf-winreg-regopenkeyexw),
owner/DACL access in
[Registry key security](https://learn.microsoft.com/en-us/windows/win32/sysinfo/registry-key-security-and-access-rights),
and the disk barrier/cost in
[RegFlushKey](https://learn.microsoft.com/en-us/windows/win32/api/winreg/nf-winreg-regflushkey).
For user mode, Microsoft specifies `NtQueryKey` rather than `ZwQueryKey` in
[QueryKey](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-zwquerykey).
