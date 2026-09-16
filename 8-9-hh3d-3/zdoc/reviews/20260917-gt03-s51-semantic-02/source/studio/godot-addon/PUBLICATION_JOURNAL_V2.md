# Complete-bundle journal and native bootstrap

Internal GT-03 implementation. No authenticated save, engine acceptance or
public ACK. The accepted GT-02 core and historical v1 journal remain unchanged.

`PublicationJournalV2.create(parent, storage_id, config, initial_bundle)` owns
the Registry custody, bundle store, compatibility blob root and native event
log. The blob root exists for the unchanged custody schema; complete bundle
files use `ProtectedBundleStore`. The store owns the native file root close;
the journal retains an alias for read-only identity checks, never a second
writer. File-root construction precedes the other roots' ancestor sharing.

CONFIG omits `content_root_identity`; the journal supplies the actual protected
files identity. Supplied initial metadata must exactly match the decoded
eleven-file bundle and canonical manifest. Initial selection generation is 0.
Metadata alone does not select anything. The native log records, in order:

1. Native GENESIS and protected custody binding.
2. BOOTSTRAP_PREPARED: CONFIG, exact manifest and all twelve generated names.
3. Actual immutable staging, manifest/directory barrier and full readback.
4. BOOTSTRAP_SELECTING: exact canonical selector, before its creation.
5. Actual selector create, namespace barrier, full bundle/selector readback.
6. BOOTSTRAP_SELECTED: observed selector FileVersion and bytes digest.
7. Pure reducer CONFIG, matching the selected baseline.

Each bootstrap append uses expected-head CAS, native flush/readback and custody
high-water before the next effect. The three bootstrap events are separate from
the pure reducer schema; CONFIG is pure sequence1, native sequence5. Full replay
validates strict bootstrap shapes, config, names, descriptor bytes/identities,
manifest, initial selection and recorded selector version. A later selector
does not make the historical bootstrap selector version a current observation.

`prepare(event_without_planned_names, bundle)` reserves actual native names,
validates unchanged-file/scene/script constraints and persists PREPARED before
file creation. Invalid input cancels only an unused preparation, retaining the
store's tombstone. Same-command retries must use `lookup`, not prepare again.
`stage_prepared(command_id, digest, observed_ms, scene_observation)` performs
actual stage/barrier/readback and derives the STAGED descriptor from the
registered receipt. Direct arbitrary PREPARED/STAGED records are rejected.
Known invalid time/observation arguments reject before staging begins.

`append`, `lookup` and `snapshot` verify complete native history and custody.
Engine observations, semantic revision, admission, lease/fence and timestamps
are still trusted-caller attestations. Persisting VALIDATED/ACTIVATING/READBACK/
COMMITTED does not perform or verify those effects. Ordinary selector mutation
is deliberately not exposed by this journal; the future authenticated owner
must guard the effect and obtain actual editor adoption/readback.

`selected_bytes()` reads the actual current selector and complete referenced
bundle through the store. It does not validate Godot or equate selected bytes
with a COMMITTED engine operation. All reports retain `public_ack=false`,
`engine_effects_verified=false`, `execution_permitted=false`.

`reopen(storage_id, project_id)` resolves only protected Registry custody,
checks root/stream identities and rejects any log ahead of custody. Incomplete
bootstrap cannot be reopened as a ready journal. Complete and pending histories
reopen permanently read-only; no write rearm, automatic stage/selection or
orphan adoption is supplied. Crash recovery to writable authenticated ownership
remains a separate implementation requirement.

Any ambiguous append, native effect or cleanup holds the owner. Exact failed
cleanup owners are retained; close stops at the first failure and can be retried.
Low-level retained APIs use `close_owned`, not their handle-specific `close`.
KeyboardInterrupt/SystemExit are preserved after cleanup; unresolved cleanup
is attached to the original exception. Blocking native calls still require an
external owned process deadline. These checks do not simulate physical power loss.

The focused tests use actual Windows NTFS/Registry, with synthetic engine
metadata clearly identified. They prove bytes/order/reopen/uncertainty behavior,
not an engine transaction, live authorization or GT-03 acceptance.
