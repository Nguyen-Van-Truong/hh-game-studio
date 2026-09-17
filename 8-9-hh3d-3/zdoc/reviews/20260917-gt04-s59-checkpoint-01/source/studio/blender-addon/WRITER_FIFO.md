# Private Blender writer FIFO

AUTHORITY=0; public_ack=false. TX06 applies FIFO/fencing to GT04. This bounded
single-fixture scheduler uses the unchanged GT02 Journal's OS lock, checksummed
records, fsync/readback and lease epochs. It adds no protected custody or public
transport capability.

`request_writer(ticket_id, writer, wait_ms, lease_ms)` persists a ticket before
returning WAITING. At most eight tickets may wait and at most 64 IDs may be used
within this journal; one pending ticket per writer is allowed. Queue wait and
lease TTL are each capped at 120 seconds. Exact retries preserve the original
deadline and terminal result; changed requests under an old ID conflict.

`pump_writers()` selects the first still-pending durable ticket after the current
lease expires. The native lease cannot outlive that ticket's queue deadline.
It persists the new epoch and grant intent, arms the authenticated Blender
main-thread fence, then persists GRANTED after exact native readback. Waiting
order is the order of durable append under the OS writer lock, including equal
clock timestamps. The older immediate-acquire API is disabled once FIFO mode
is activated, so renewals cannot jump the queue.

`cancel_writer()` terminally cancels an ungranted ticket. A completed grant is
not canceled retroactively and expires at its original lease deadline. Early
release of an active lease is not exposed by this slice. Cancel during native
arming prevents a GRANTED receipt; its unused native lease expires without
authorizing an edit. An interrupted/lost grant reply stays GRANTING while that
lease may be live, then becomes UNKNOWN instead of silently rearming the same
ticket. Other pending tickets retain their order.

`writer_status()` recovers persisted ticket state across cooperating session
objects. Expiry/cancel/Stop append terminal records; IDs are never reused to
create a second grant. Stop reaches the native control lane before waiting for
the scene-command lock or journaling queue cancellation. All pending tickets
become CANCELED and another session cannot continue dispatch after the durable
Stop marker. Historical native command responses remain available.

This is one owned GUI generation and one fixed journal path. Reopening another
Blender generation still requires reconciliation. The native fixture uses two
independent synthetic client processes speaking bounded JSON over inherited
stdio to the trusted test broker; the broker invokes these production methods
and the existing authenticated Blender IPC. This proves contention/order on
the owned fixture, not general public client authentication or GT09 conformance.
