# GT-02 journal contract

This single-host fixture journal owns trusted private host state. Agent-selected
project paths must never become its storage path. It is not the project safe-write
API or a distributed database. Native locks serialize cooperating writers and
readers; the permanent guard is never unlinked. Windows liveness checks use a
synchronizable process handle, because `os.kill(pid, 0)` terminates on Windows.
`lease_guard` holds that same OS lock from fresh fencing validation through a
bounded local effect. A separate `check_lease` followed by an effect leaves an
interleaving window. Deadline/expiry must still be checked at the actual effect;
release the guard before terminal journal calls, I/O or asynchronous readback.

Before durable PENDING admission, the journal reserves one terminal record and
`profile.max_envelope_bytes` bytes. Other appends, including leases and new
commands, cannot consume this reservation. Reservations are derived from durable
pending entries after reload/compaction. This prevents predictable configured
capacity failures after apply; it cannot guarantee against physical disk/I/O
failure. Such failures require UNKNOWN and reconciliation, never a success ACK.

The retry horizon is not permission to execute an old ID again. `lookup` rejects
expired IDs. `lookup_archive` reads their original status, receipt, digest and
timestamps with `archived=true` and `execution_permitted=false`. Compaction keeps
the original receipt and status in a tombstone. An expired PENDING receipt remains
unresolved intent; the typed transport reports UNKNOWN, never COMMITTED.
Tombstones cannot be revived by a clock rollback. Historical tombstones that
already lost their bodies report `ARCHIVE_RESULT_UNAVAILABLE`.

Archive bodies remain in the same checksummed, bounded disk journal and are
loaded on demand through an offset index. No archive eviction makes an ID new.
Every reload opens the existing journal with write access and performs a
durability barrier before exposing records. This reconciles a terminal line
left visible after a prior writer's fsync failure; if the barrier fails, the
reader returns `JOURNAL_DURABILITY_UNCONFIRMED` and transport does not authorize
COMMITTED. A readable cached line alone is never proof of durable success.
Guard acquisition or reload failure leaves the original command outcome unknown,
including a configured FULL/RECORD_LIMIT that prevents reading existing history.
Transport returns UNKNOWN and stops admission until reconciliation. Capacity
rejection inside append, after history was read successfully and before new
admission, remains REJECTED without effects. Classify the failure by its phase,
not solely by the error code; a lock-release failure cannot revoke an effect.
When retained history fills the configured capacity, admission fails closed.
Cross-host storage, automatic archive rotation and engine publish recovery are
outside this fixture baseline; they require their own verified implementation.
