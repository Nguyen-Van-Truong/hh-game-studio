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
catalog additionally defines save/export integration shapes, but this owner
rejects them as `BLENDER_OPERATION_NOT_CONNECTED`.

This is still a GT-04 candidate. Live edits are unsaved; all responses retain
`public_ack=false`, `ledger_receipt_only=true`, `scene_state_durable=false` and
`durable_publication=false`. A common COMMITTED receipt records an observed
native result, not durable GUI state. Preview/diff, protected save/export
binding and final same-closure verification remain required for acceptance.

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

External `.blend` intake, arbitrary paths/scripts, restored Undo history,
writable restart and cross-app recovery are not provided here. Unit models are
not native proof. Each native package must capture real child/wrapper exits,
owned Job cleanup and the exact complete source closure.
