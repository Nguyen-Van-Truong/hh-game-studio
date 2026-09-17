# Blender writer integration candidate

`BlenderWriterClientOwner.from_session(exact_durable_session)` is an explicit
local construction API. It reuses the registered native owner, session issuer,
writer journal, common command ledger and bounded loopback transport. Creating
it does not install a service or expose a network endpoint. Token issuance is
read-only unless the trusted caller explicitly grants supported edit operations.

Connected operations are `scene.inspect`, `mesh.create_box`,
`object.transform.set`, `material.set_principled`, `history.undo` and
`history.redo`. They apply only to one private owned GUI fixture. Discovery is
filtered to connected operations and the authenticated caller's grant. The
optional `publications={operation: exact_publication_owner}` binds
`export.publish`, `scene.save` and `checkpoint.save` to that same durable
session, generation and source. Each owner is provisioned with one immutable
closed profile and has capacity for one bundle. The older `publication=owner`
argument remains the export-only shorthand. Profiles cannot share an owner.

This is still a GT-04 candidate. Live edits are unsaved; all responses retain
`public_ack=false`, `ledger_receipt_only=true` and `scene_state_durable=false`.
Edits retain `durable_publication=false`; verified export uses true only for
its protected bundle, with manifest, selector version and exact artifact hashes.
A common COMMITTED receipt does not restore a writable GUI. Final same-closure
verification and two independent critics remain required for acceptance.

All three publication profiles require OBJECT mode and a nonempty supported
fixture. The native copy goes to the profile's fixed private `export.blend`,
`fixture.blend` or `checkpoint.blend` slot. A separate bounded Blender process
reopens that copy and exports a GLB to validate the same geometry/materials.
Every protected bundle contains `checkpoint.blend`, the verified `scene.glb`
sidecar, manifest and selector. This shares one publication reducer and proof
path; save does not invent a second durability implementation. The live GUI
context/revision/filepath stay unchanged (`copy=True`). Each slot/bundle is
create-only; a different fresh command cannot overwrite the completed bundle.

`BlenderWriterClientTransport(owner)` adds `/v1/preview`. The default read-only
transport keeps its route allowlist. Preview accepts the same typed edit
Request, checks the live native fence/revision/context on the main thread, and
returns an advisory `HH-BLENDER-CLIENT-PREVIEW-1` dictionary. It has no common
ledger INTENT, no native apply ID reservation, and no effect authority. Apply
repeats all checks. Requested values are not fabricated future revisions;
history preview uses an already observed, guarded owned history target.
Actual edit receipts include a bounded before/after diff of received snapshots
in `received-jcs-snapshot-context-v1`, preserving opaque native revisions.
Oversize/secret-altered previews fail without truncation or mismatched hashes.

## Admission and replies

An exact authenticated grant, source/Job/PID/generation binding and registered
native writer lease are required. The public lease ID is not native authority.
The native lease owner must be the random label registered for that grant.

Historical replay is checked before fresh lease/deadline admission. It never
issues another effect permit. New requests take the bounded work slot, validate
revision/context and authority, persist a common INTENT, then consume a one-use
writer permit. The original absolute deadline is forwarded to the main-thread
queue. Its monotonic bound also prevents a later wall-clock rollback from
extending an already admitted request. Synchronous work already started is not
claimed to be forcibly cancellable at its deadline.

The native queue checks fencing, deadline, revision and context before mutation.
Actual operator/readback results are bound to the private command ID/digest.
Native revision hashes name Blender's float-preserving JSON; they cannot be
recomputed from a JCS-normalized IPC snapshot. Public observation hashes name
the separately declared `jcs-observation-v1` domain.

Exact terminal bytes are recorded before response delivery. A failed terminal
reply does not replace that record with UNKNOWN: the owner holds fresh work and
lookup can recover the original result. Pending intent lookup is UNKNOWN and
never redispatches. A different authenticated session cannot import history.

Response delivery has a separate short grant check after persistence. Revoke,
rotation or credential expiration may deny delivery while preserving the true
effect receipt. Stop before authorization blocks work; an already authorized
effect may drain. Fresh reads still obey Stop and deadline at delivery; later
historical lookup does not require a new read lease. Output redaction may deny
delivery but cannot silently change a committed observation under its old hash.

## Scope and maintenance

The core GT-02 implementation is unchanged. The writer journal handles native
lease fencing; the common client ledger handles public command identities. The
integration does not create a second native command receipt for each effect.
Stop retains its separate transport listener and native control channel.
When publication is attached, Stop also cancels that exact publisher's export
job. Original epoch deadlines and registered grant/fence checks reach every
publication phase and the background child gate. A post-INTENT failure retains
UNKNOWN/hold; no automatic replay or claimed rollback. Publication terminal,
selected bytes and common ledger terminal are distinct, checked bindings.
The trusted caller closes transport, publication owner, then GUI; it retains
any cleanup owner returned by a failed close for bounded retry.

External `.blend` intake, arbitrary paths/scripts, restored Undo history,
writable restart and cross-app recovery are not provided here. Unit models are
not native proof. Each native package must capture real child/wrapper exits,
owned Job cleanup and the exact complete source closure.
