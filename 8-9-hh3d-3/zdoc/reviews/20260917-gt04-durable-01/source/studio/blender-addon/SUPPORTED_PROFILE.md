# GT04 profile and remaining acceptance boundary

AUTHORITY=0. This is an implementation contract, not a plan checkbox or review
signature. All current internal responses keep `public_ack=false`.

The implemented export profile remains `HH-BLENDER-BOX-EXPORT-PROFILE-1`:
1–16 independent boxes, 8 vertices/6 faces each, finite names/TRS, zero material,
image, bone, clip, modifier, driver, constraint, linked library or external URI.
The native reopen snapshot and bounded GLB vertices/names/TRS must agree. This
does not meet TQ04's material reopen or GT05's rig/PBR fixture dependencies.

The UI command catalog is inspect, create box, typed transform, native undo/redo,
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
expiry while queued prevents mutation. Busy writers are rejected; FIFO writer
scheduling is still open. Stop bypasses the data/receipt lock. General artist
files, hostile parser isolation, protected journal custody and power-loss
publication are outside this internal fixture candidate.

The next bounded profile required before full GT04 acceptance is provisionally
`HH-BLENDER-FIXTURE-MATERIAL-RIG-CLIP-1` and is **not implemented or advertised as
supported**. Its proposed limits are:

| Part | Required bounded contract |
| --- | --- |
| Mesh | At most 4 original fixture meshes and 4096 vertices total; finite transforms and stable IDs. |
| Material | At most 4 Principled PBR materials, one slot per mesh; typed base color/alpha, metallic and roughness; native save/reopen equality. No custom shaders, external or packed images in this first profile. |
| Rig | One original armature, at most 8 uniquely named bones, one root, acyclic parent graph; finite rest/bind transforms and normalized vertex weights. No constraints, drivers, IK, shape keys or arbitrary modifiers; only the explicitly owned armature deformation. |
| Clips | At most 2 baked transform clips, 30 Hz, at most 60 samples each; explicit start/end, bounded key counts, native reopen channel/sample checks. |
| Dependency closure | Zero external libraries/scripts/textures/addons. Every admitted material/rig/clip datablock must be enumerated and bound to source readback; unsupported dependencies fail closed. |

The exact limits and supported node/bone/channel representations must be frozen
with fixtures and native tests before admission expands. GT05 owns final naming,
asset manifest, texture/LOD policy, Godot import and visual/animation parity.
This proposal neither opens GT05 nor defines a competing naming convention.
