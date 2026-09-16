# Managed fixture restart ownership

`ManagedFixtureOwner` joins the typed selector, protected file consumer, blob
store, event stream and OS-protected registry custody. This remains an internal
fixed inert fixture; no engine or arbitrary filesystem operation is exposed.

Provisioning writes a checksummed `PROVISIONING` record before minting any
private root. All roots are created by existing handle-checked primitives.
The file root is provisioned first so its parent barrier precedes the peer
stores' retained ancestor handles. `READY` binds three distinct root identities,
event stream identity and witnessed chain head. An incomplete record never
authorizes creating missing roots on restart.

The registry anchor is a fixed owner-only product namespace with one locally
generated UUID leaf. The record is typed, canonical, bounded to 16 KiB and
checked before any recorded path is used. It stores no secret, handle, code or
arbitrary client recovery instruction. Registry integrity depends on the OS
boundary, not the checksum. The original event journal owns command receipts;
custody stores only their monotonic high-water boundary.

Every bound event append flushes and reads back the event before synchronously
persisting its new custody head. It cannot return success before custody is
stored, flushed and read back. A custody error poisons both layers and leaves
the command UNKNOWN. The [documented RegFlushKey barrier](https://learn.microsoft.com/en-us/windows/win32/api/winreg/nf-winreg-regflushkey)
is blocking and expensive; run this owner within a bounded owned process.
Process-crash tests do not simulate power loss or dishonest device caches.

Reopen uses only the protected record plus local storage ID/project binding.
It acquires the exclusive file guard, rereads custody to reject a stale bootstrap
read, opens the original store/log identities, checks the witnessed prefix and
validates the entire selector history. A complete suffix beyond custody is
recorded only after those checks; it never schedules a prior command's effect.
Missing, malformed, truncated or mismatched records remain held.

Only terminal last-good selection with no pending command and no durable STOP
may load/confirm the exact existing `active.json`. Reacquired exclusive roots
permit the trusted supervisor to renew the recorded logical owner's lease with
a new lease ID/fence, used for this recovery phase only. It has a 1 ms TTL; no
old authenticated session is restored. This duration is not an I/O time bound:
recovery uses its sampled trusted phase-admission time, and subsequent clients
must get a fresh ordinary lease after expiry. Clock rollback remains rejected.

After actual file confirmation and a fresh file/directory barrier, the private
rearm step accepts only `.writer` and `active.json`, checks the expected full
file version and retained guards, then permits fresh commands. It never retries
an old effect, removes an orphan or clears a poisoned primitive. Stop/pending
roots remain read-only. No global safe-open capability is changed.

The single file writer guard serializes custody updates after provisioning.
The registry primitive's compare/read/write sequence is not interprocess CAS.
Unrestricted broker-account/admin code and whole-machine state rollback are
outside the existing confined-worker threat model; adding another same-disk
journal would not protect against those authorities.

Constructor failures retain local cleanup owners. Close proceeds from logical
owners to native storage; any failed close retains the remaining chain for
explicit retry. Provisioned data is preserved rather than automatically deleted.
Public discovery/dispatch and independent acceptance remain separate work.
