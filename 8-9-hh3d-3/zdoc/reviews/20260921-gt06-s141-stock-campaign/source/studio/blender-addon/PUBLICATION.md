# Private owned Blender publication

AUTHORITY=0; public_ack=false. This bounded Windows owner captures one closed
fixture scene per owned GUI generation, publishes `checkpoint.blend`, `scene.glb`
and `manifest.json`, then selects their exact versions through `active.json`.
Each artifact is at most 1 MiB. Supported content remains the existing box and
opaque original Principled profile; Object Mode is required. No foreign path,
external library/texture, rig, animation or arbitrary consumer is admitted.

The trusted caller owns the UI host and DurableBlenderSession. It creates and
closes BlenderPublicationOwner before closing that GUI. The publication owner
retains background export cleanup on failure, then closes the event log, blob
store, protected file root and registry custody in order, retaining failed
owners for explicit cleanup retry. No worker-supplied root or storage descriptor
is accepted by publish(); its request contains only schema, command ID and
expected scene revision/context. Provisioning parent and restart storage ID are
local supervisor inputs, outside any public transport.

INTENT is durably witnessed before native save/export. Existing native preflight
rejects unsupported input before saving; only the fixed owned export slot may
be captured. A capped background Blender opens those exact bytes with scripts
disabled, revalidates the profile, reads mesh/transform/material, exports GLB
and checks unchanged context. Host GLB validation binds full geometry, TRS,
names and materials. After native UI readback, staged blobs are read back and
copied into canonical protected files. The manifest binds those versions,
runtime source pins, binary pin, original-fixture license, input identity and
empty external-input closure.

The manifest also preserves the native snapshot's canonical JSON as text:
Blender's scene revision distinguishes integral floats from integers, while
the durable JCS envelope normalizes both. Reopen verifies the original native
revision and canonical text, then binds its semantic value to the manifest
snapshot; it does not recompute that revision from normalized receipt numbers.

Native temporary outputs have inherited file ACLs, so they are not treated as
PrivateBlobStore objects. Capture pins the exact host-owned private export
directory, checks its ACL, and reads only its two fixed artifacts through native
identity/hash-checked handles. The independent protected copies establish the
publication boundary. This does not admit arbitrary user-selected files.

PrivateBlobStore has no per-entry directory barrier. Its mirrors are staging
provenance only. Canonical publication dependencies are ProtectedFileRoot files:
each uses checked native creation/rename plus file and directory barriers.
Reopen reads these exact protected FileVersions and does not need blob mirrors
to recover artifact bytes. STAGED binds the complete graph; SELECTING precedes
the fixed selector write. Only selector/file/bundle readback and barriers permit
the final protected TERMINAL response. Registry WitnessCustody anchors the event
head; a suffix beyond its witness stays held rather than silently acknowledged.

Duplicates return the original canonical terminal bytes, including after a lost
reply or read-only reopen. A changed request under the same ID conflicts. Every
incomplete prefix returns UNKNOWN and is never resumed automatically. This
initial slice permits one publication per storage owner; a second command needs
a new explicitly owned generation. It does not update/replace an existing
release, import into Godot, recover a live GUI after restart or expose a public
ACK. Protected storage remains within the accepted confined-worker threat model;
unrestricted broker-account/admin writes and physical power loss are not proven.

Writer authority comes from the existing durable Blender lease/fence and is
rechecked at phase admission, including immediately before selection. Stop
signals export/native control before waiting for the publication mutex, then
persists STOP; already admitted synchronous disk I/O may finish. This is not a
hard disk-cancellation deadline. Historical terminal lookup remains available.
