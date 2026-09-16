# S52 authentication/transport implementation review

AUTHORITY=0. Independent implementation review by the Blender worker; no
acceptance signature, frozen full-closure review or native Godot claim.

Two findings were sent to the root author and fixed by that author:

1. Rotating an unrelated read-only session cleared the active writer's lease.
   The original behavior was reproduced with one writer grant/lease and a
   separate `scene.inspect` grant: rotating the latter caused the unchanged
   writer check to raise `GODOT_STALE_LEASE`. The fix limits lease invalidation
   to the rotated session. The new focused regression passes.
2. A second listener thread failing to start could make cleanup call
   `BaseServer.shutdown()` for a server whose serve loop never started.
   The author added explicit server/thread ownership and partial-start cleanup.
   The subsequent bounded injection against the fixed source returns from
   `close()`, with actual target/wrapper exit 0 and clean owned tree. This is
   post-fix verification, not a pre-fix deadlock capture.

Reviewed/tested source:

- `publication_session.py`:
  `57c127b9b80e3b95b28555c9bf60fbdced4653f4daec658fa6fc3801c71e1640`
- `publication_transport.py`:
  `ece929bb735e6b70287e348749b67cd3be72b4587f57c8a7c4cd79408f67ea78`

`focused-review.json` retains all four source/test hashes and the bounded
invocation. All 19 focused tests passed in 0.802 seconds; actual process exit
and wrapper exit were zero, no timeout, owned Job tree clean, and source bytes
unchanged during execution. `invocation.json` and `partial-start-review.json`
retain the separate start-failure injection (four-second watchdog, no timeout).
Raw stdout/stderr and host records are adjacent.

One integration issue was also reported to the root: at inspection time,
`GodotPublicationOwner.submit()` required a `scene.save` lease even for
`scene.inspect`; an inspect-only grant therefore could discover but could not
inspect. The owner module is outside this bounded review and remains subject
to its author's correction and integration verification.

Bearer/project/catalog checks, copied/mutated grants and permits, Stop before
admission, Stop/revoke while an effect is draining, phase deadline recheck,
secret redaction, strict HTTP framing, route separation and actual socket Stop
were reviewed. No bypass was established in these tested module versions.
This does not establish the editor callback's native admission boundary,
journal durability, complete public save path or GT03 acceptance.
