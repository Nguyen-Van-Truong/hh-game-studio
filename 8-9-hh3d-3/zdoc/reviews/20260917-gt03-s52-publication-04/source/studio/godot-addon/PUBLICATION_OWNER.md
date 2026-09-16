# Managed scene save candidate

`GodotPublicationOwner.create` provisions one fresh owned fixture. It validates
the initial complete project in the pinned Linux process, starts the pinned
Windows EditorPlugin and compares full semantic bytes before selecting the
initial bundle. Constructor arguments are trusted local provisioning, never
remote paths. There is no recovered writable constructor.

`PublicationTransport` supplies separate bounded work and control listeners.
It delegates byte framing to the unchanged accepted GT-02 reader/writer, but
dispatches no fixture operation. `PublicationSession` issues empty fixture
scopes and binds a separate Godot grant to its exact issuer, session, project,
catalog and operations. Bearers stay out of argv, discovery and receipts.

The work routes are `/v1/discovery`, `/v1/lease` and `/v1/commands`; the control
routes are `/v1/lookup` and `/v1/stop`. Requests require the bearer and
`X-HH-Catalog`. Lease `access: read` is independent of the single writer lease
and remains available after Stop. An inspect-only grant defaults to read access.
Public operations are `scene.inspect` and `scene.save`; other catalog entries
are internal editor operations or unfinished publication work.

A save binds the current dirty semantic scene, selected project revision,
working scene/script hashes, editor generation, lease/fence and deadline.
It records capture intent before any scratch output, captures the actual edited
root, validates the exact eleven input files and binds a new manifest to the
full canonical semantic observation. The journal stages and reads back all
twelve protected objects, persists selector intent, performs native CAS and
persists the actual selected FileVersion before editor adoption. The same
editor reloads the fixed scene mirror, advances its root/generation and reads
back all inputs plus semantics. READBACK and durable COMMITTED precede the
public response. Repeated same-ID/same-digest requests return the original
receipt only after rechecking its durable journal record.

Capture, stage, select, adopt and commit each have a registered single-use
STARTED permit. Stop/revocation cancel unused permits immediately. If a phase
has started, they report `draining: true`; that bounded phase may finish, but
the next one cannot start. In particular READBACK plus COMMITTED are one final
accounted phase. No lock waits on disk or IPC in the Stop handler. An uncertain
effect retains its owners and returns UNKNOWN, requiring explicit reconcile.

Limits are explicit: 90 seconds for the complete scene save and writer lease,
30 seconds for other command horizons/read leases, at most 10 seconds for an
editor effect intent, and the existing 20-second isolated engine deadline.
The original 30-second total save budget expired in the first integrated
native run after successful validation/staging; it was replaced by this bounded
whole-operation budget, without enlarging the isolated engine quota or removing
deadline checks. The validator currently allows four runs per owner, including
bootstrap, so admission rejects a fourth save before capture. Phase and command
budgets are also checked before admission. These are fixture-candidate limits.

Only `scenes/fixture.tscn` changes in this slice. The other ten inputs must
remain identical. Reload is a declared checkpoint/history boundary: old
generation undo/redo is rejected, with no artist-project history-preservation
claim. Linux candidate observations are distinct from Windows live-editor
observations; native file receipts alone do not establish either.

`run_publication_probe.py` exercises real HTTP, actual dirty editor state,
isolated validation, native selector CAS, same-session adoption, duplicate/
lookup, owned teardown and readonly reopen. Its snapshots remain tied to their
own source hashes. S52 is a candidate; script publication, writable restart,
remaining crash/race cuts and two independent gate reviews are still required.
