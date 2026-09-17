# Fixed checkpoint GUI readback

Internal candidate, `public_ack=false`. `CheckpointRecoveryOwner.open` accepts
the exact read-only `BlenderPublicationOwner` and its exact, cleanly closed
`BlenderUIHost` predecessor. The predecessor must match the publication
generation and have checked actual native exit0, wrapper exit0 and Job0. This
slice cannot reconstruct a crashed host from recorded PID or sidecar data.

The selected protected bundle must be complete and witnessed. Its exact current
producer runtime source map, pinned Blender executable, native revision JSON,
Object-mode context and strict export profile bind the load. A one-use local
seed copies the committed checkpoint to fixed private `recovery-input` files;
the API retains their directory handle through checked host cleanup. Bootstrap
contains only two expected hashes, never a caller-controlled file path.

The new GUI loads with auto-execution disabled before registering the adapter
or timers, verifies its native scene and profile, then reports authenticated
PID, generation and readback. The host verifies that report and performs a
second live inspect against the protected selector. Both host and native IPC
deny edit commands and writer leases independently. The only data command is
bounded `scene.inspect`; Stop and orderly exit retain their control path.

The caller keeps the read-only publication open until the recovery owner
closes. Constructor or cleanup failure retains the exact cleanup owner for
retry. No prior edit/export is replayed and the historical publication receipt
or event graph is never rewritten. A fresh adapter baseline is created; prior
Undo history is not restored.

The result states `live_scene_readback_verified=true`, `recovery_durable=false`,
`new_edit_grant=false`, `undo_history_restored=false`, and `public_ack=false`.
Durable recovery authority, interrupted-command reconciliation, writable
restart, arbitrary file intake, public transport and a Godot consumer remain
outside this slice. Native execution evidence must be assessed separately from
the focused validation tests; this document does not grant acceptance.
