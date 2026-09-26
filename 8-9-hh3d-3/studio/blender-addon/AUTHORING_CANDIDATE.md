# Blender authoring candidate — CR-BLENDER-AUTHORING-01

This candidate describes typed proposals for `armature.from_template`,
`animation.action.create`, and `animation.keyframe.set`. The catalog is bounded
to trusted template hashes, finite vectors, named bones/channels, 256 keyframes,
and explicit revision/lease/generation checks.

It is static validation only. It does not import `bpy`, open a `.blend`, start
Blender, register a capability, execute a script, write a file, or emit a
committed ACK. Native gates BLEND-AUTH-01 through BLEND-AUTH-04 remain pending:
main-thread operator/timer routing, template readback, action/keyframe readback,
and Undo/recovery/isolation evidence. The proposal includes an explicit undo
policy so a future native adapter cannot claim success without restoring the
observed revision.
