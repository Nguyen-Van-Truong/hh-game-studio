# GT04 profile and remaining acceptance boundary

AUTHORITY=0. This is an implementation contract, not a plan checkbox or review
signature. All current internal responses keep `public_ack=false`.

The implemented export profiles are `HH-BLENDER-BOX-EXPORT-PROFILE-1` without
materials and `HH-BLENDER-MATERIAL-EXPORT-PROFILE-1` with the closed opaque
Principled grammar in `MATERIAL_PROFILE.md`. Both keep 1–16 independent boxes,
8 vertices/6 faces each, finite names/TRS, zero images, bones, clips, modifiers,
drivers, constraints, linked libraries or external URI. At most four original
materials are supported, one per owning mesh. Native reopen snapshots and
bounded GLB vertices/names/TRS/material values must agree.

The UI command catalog is inspect, create box, typed transform, opaque Principled
material create/update, native undo/redo,
fixed-slot checkpoint save, and fixed-slot export preparation. The external
owned host performs capped background GLB export. Native cleanup retains the
exact process/Job/drain owners; checked close failures can be retried, ambiguous
native close results stay held. Cleanup retry cannot promote an unknown export
to success or rewrite its original host result.

`DurableBlenderSession` now wraps that UI catalog with a private checksummed,
fsync/readback journal using the unchanged GT02 Journal. A terminal response's
canonical UTF-8 bytes and digest are persisted before return. Exact duplicate
IDs return the same bytes; changed commands conflict. Orphan pending intents
return UNKNOWN and never redispatch. A journal reopened without its original
native generation is lookup-only. These are durable historical observations,
not durable `.blend` publication or restoration of GUI state.

Writer leases have persisted increasing epochs, one admitted writer, expected
scene revision/context, and an authenticated consumer fence checked again on the
Blender main thread before dispatch. Rotation rejects late old envelopes, and
expiry while queued prevents mutation. The private FIFO writer-ticket API now
persists queue order, expiry/cancel and fenced handoff (see `WRITER_FIFO.md`).
Stop bypasses the data/receipt lock. General artist
files, hostile parser isolation, protected journal custody and power-loss
publication are outside this internal fixture candidate.

TQ04's material reopen is addressed by the material candidate. Rig, avatar,
clips, textures and LOD remain unsupported and deferred to GT05's dependencies.
GT05 owns final naming, asset manifest, texture/LOD policy, Godot import and
visual/animation parity; this slice neither opens GT05 nor defines a competing
naming convention. Protected publication and independent criticism still
remain before full GT04 acceptance.
