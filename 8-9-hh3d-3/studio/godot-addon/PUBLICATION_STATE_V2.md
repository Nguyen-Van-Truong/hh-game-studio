# Complete-profile publication history v2

`publication_state_v2.py` is a pure, versioned reducer for the eleven logical
files in `bundle_v2.py`, plus their canonical manifest, stored as twelve
`ProtectedFileRoot` objects. V1 is unchanged. This module does not import a
native storage owner or execute filesystem, Registry, process, Godot, network,
activation, rearm, or journal operations.

Every native descriptor, root identity, lease, timestamp, checkpoint, and engine
observation remains a **caller attestation**. COMMITTED means only a consistent
declared sequence. Every lookup and receipt has `public_ack=false` and
`engine_effects_verified=false`; lookup also has `execution_permitted=false`
and `durable_owner_required=true`. The future owner must independently verify
native handles/bytes, actual engine results, selection effects, event append,
custody, readback, and barriers. Replay never resumes effects or clears a hold.

## API and bounds

```python
state = reduce_event(None, config)          # dict or canonical event bytes
state = reduce_event(state, next_event)
state = replay(events)                     # bounded iterable, CONFIG first
state = PublicationState(state.events)      # full replay, never snapshot import
snapshot = state.snapshot()                # detached JSON projection
answer = lookup(state, command_id, digest=None)
manifest = bundle_manifest(files_metadata, scene_revision, engine_sha256)
revision = project_revision(files_metadata, scene_revision, engine_sha256)
intent = selection_identity(project_id, command_id, digest, parent, candidate)
```

`PublicationState` is frozen and slotted. `events` is a tuple of canonical bytes;
`event_count` is its length. Construction and each transition validate all
retained history. A rejected pure transition cannot modify prior state. Errors
are `PublicationError`, a shared `ValidationError` carrying a bounded fixed
`PUBLICATION_*` code. Same-ID/different-digest conflicts are ordinary pure
rejections, not state changes or automatic holds.

The bounds are 256 events, 64 retained command IDs, 12 KiB per canonical event,
3 MiB total canonical history, and a 512 KiB detached state projection.
PREPARED reserves five remaining success records plus one STOP record. IDs and
planned object names are never evicted or reused, including after an early
failure. At most 768 names and 192 distinct observation IDs can be retained.
The native log has a separate GENESIS: it is not reducer CONFIG and must not be
fed to replay. These bounds leave native framing room below the accepted
16 KiB event-body / 512-record / 8 MiB log limits; they do not perform real
quota reservation. The durable owner must reserve bytes, records, terminal
completion, custody, and cleanup capacity before admitting effects.

The eleven paths, roles, individual caps, canonical trusted-source digest and
project digest match the codec-v2 algorithm. The tests compare them against an
actual codec-created synthetic bundle. `bundle_manifest()` reconstructs the
canonical metadata object; no raw file or engine observation is inferred from
a caller's metadata. An installed release factory must separately pin actual
trusted source bytes.

## Event schema

All events have exactly `schema`, `sequence`, `kind`, `project_id`, and
`observed_ms`, plus the fields below. Schema is
`hh-godot-publication-event-2`; sequence begins at 1 and is consecutive;
`observed_ms` is a nonnegative safe integer and never regresses. Unknown fields
are rejected at every defined nested shape. Boolean values never count as
integers. IDs/hashes and the lease, selection, failure and Stop vocabulary keep
the bounded v1 syntax.

| Kind | Exact additional fields |
| --- | --- |
| CONFIG | `engine_sha256`, `source_closure_sha256`, `content_root_identity`, `initial` |
| PREPARED | `command_id`, `digest`, `operation`, `candidate_id`, `before_project_revision`, `before_scene_revision`, `expected_files`, `parent_selection`, `admission`, `checkpoint_sha256`, `script_input`, `planned_names` |
| STAGED | `command_id`, `digest`, `candidate` |
| VALIDATED | `command_id`, `digest`, `observation` |
| ACTIVATING | `command_id`, `digest`, `current`, `selection` |
| READBACK | `command_id`, `digest`, `observation`, `selection` |
| COMMITTED | `command_id`, `digest`, `readback_event_sha256`, `after_project_revision`, `selection` |
| FAILED | `command_id`, `digest`, `reason`, `publication_not_started`, `staging_may_exist` |
| UNKNOWN | `command_id`, `digest`, `reason` |
| STOP | `reason` |

CONFIG binds `content_root_identity={volume,file_id}` to the declared protected
**FILES root**. A PrivateBlobStore identity is not interchangeable. Pure code
cannot authenticate what kind of native object a caller's identity represents.
Volume is canonical uint64 decimal text; FileID is 32 lowercase hex characters.
`initial={project_revision,scene_revision,files,selection}` must recompute to the
codec-v2 project digest under CONFIG's engine hash. Each `files` row is exactly
`{sha256,size_bytes,role}` for all eleven logical paths. Sizes are positive and
within the codec caps. `selection={generation,identity}` identifies the caller's
initial selection; it is not a native selection readback.

PREPARED binds the original complete project revision, all eleven metadata
rows, parent selection and live scene revision. `before_scene_revision` may
differ from the published scene for a scene.save with unsaved edits. Admission
is exactly `{lease_id,fencing_epoch,admitted_ms,deadline_ms,lease_expires_ms,
editor_session_id,editor_generation}`. Admission time equals event time, with
`admitted_ms < deadline_ms <= min(lease_expires_ms, admitted_ms+30000)`.
Fence/generation are positive; fences never decrease, and the same fence cannot
change lease ID or expiry. `script_input` is null for scene.save, otherwise
exactly `{sha256,size_bytes}` for the positive, bounded replacement script.

`planned_names` is an exact map from the eleven codec paths plus `@manifest`
to twelve unique `obj-<32 lowercase hex>` names. It can be constructed from
`dict(intent.names)` from the complete protected-file staging owner. The plan
is retained before STAGED, including names whose eventual native effects are
uncertain. Names previously planned in this history cannot be reused.

STAGED's candidate is exactly:

```text
{
  candidate_id,
  descriptor: {
    root_identity: {volume, file_id},
    project_revision,
    files: {each_of_11_paths: {name, volume, file_id, size_bytes, sha256}},
    manifest: {name, volume, file_id, size_bytes, sha256}
  },
  bundle_manifest: {schema, profile, files, trusted_source_revision,
                    caller_observations, project_revision},
  scene_observation
}
```

The descriptor root must exactly equal CONFIG. All twelve native FileIDs are
unique, on the root volume and different from the root FileID. Every descriptor
name must match PREPARED. Each file's descriptor hash/size must equal its exact
role-bearing manifest row. The manifest descriptor must hash and size the
actual canonical encoding of `bundle_manifest`. The trusted-source and project
revisions are recomputed using the codec-v2 schema/profile/roles; declared
engine hash must equal CONFIG. Aggregate file plus manifest bytes are capped
at 2 MiB and manifest bytes at 16 KiB. None of these checks reads a descriptor.

For scene.save, all non-scene bytes remain identical, the scene semantic
revision equals the admitted live scene observation, and `scene_observation`
must be null. For script_text.replace, all ten non-script files remain identical
(scene, script UID, configuration, trusted addon source and their UIDs), and the
new script exactly matches `script_input`.

Script replacement additionally requires:

```text
scene_observation = {
  observation_id, editor_session_id, editor_generation, observed_ms,
  project_revision, scene_revision, engine_sha256, source_closure_sha256
}
```

Its full project digest binds all eleven candidate metadata rows. Its source
and engine pins must match CONFIG. The session must differ from the admitted
live editor, its observation ID must not have appeared before, and its time
must satisfy `admitted_ms <= observed_ms <= STAGED.observed_ms`, strictly before
both deadline and lease expiry. The scene revision may equal the old value only
when an explicit fresh candidate observation declares that result; the reducer
never silently carries it across a script replacement. These are consistency
checks, not proof that the claimed observation is fresh or authentic.

There is a metadata ordering dependency: codec-v2's project digest already
includes the scene revision. The host therefore must obtain/compute a fresh
candidate semantic observation before fixing the final manifest, and bind it
to exactly those eleven bytes. A truthful implementation may perform actual
candidate validation after durable PREPARED and then append STAGED followed by
VALIDATED. VALIDATED may reuse that same scene-observation ID only if every
compact field is identical; a second engine run is not required merely to
follow record order. Future host integration must match actual engine semantic
revision separately from bundle metadata's caller-declared scene revision.

An expanded `observation` is exactly `{observation_id,editor_session_id,
editor_generation,observed_ms,candidate_id,project_revision,scene_revision,
engine_sha256,source_closure_sha256,manifest_sha256,files,parse_status,
import_status,exit_code,tree_drained,logs_clean}`. It must bind all candidate
metadata and pins, PASS/PASS, integer exit 0, and true drained/clean facts.
Its time lies between PREPARED and its event. READBACK also must be at or after
the recorded ACTIVATING event; a fresh ID alone cannot make an earlier
observation a post-activation readback. VALIDATED's observation must
precede the admission deadline/expiry. Except the exact same candidate fact
described above, observation IDs cannot recur anywhere in retained history.
READBACK additionally requires a different session and observation ID from
VALIDATED. Supplied booleans and statuses do not authenticate native results.

## Ordering, duplicate lookup, Stop and recovery

Success is PREPARED → STAGED → VALIDATED → ACTIVATING → READBACK → COMMITTED.
Only one command may be pending. ACTIVATING's exact `current` fields are
`{project_revision,scene_revision,files,selection,lease_id,fencing_epoch,
editor_session_id,editor_generation}`; they must match PREPARED, and event time
must precede its original deadline/lease expiry. Selection advances by exactly
one generation and binds command/digest/parent plus the complete descriptor
and canonical manifest hashes. It is an intent, not an observed replacement.
COMMITTED binds the exact preceding READBACK event hash, candidate project
revision and selection, then updates last-good. Its internal receipt retains
content root and candidate descriptor digest in addition to the original
admission, before/after content, source pins and phase hashes.

Lookup precedes new admission. Same ID/digest returns its original detached
pending, held or terminal result; a changed digest throws a conflict. Appending
another PREPARED is never retry. Terminal records may be written after the
deadline, preserving original admission; this does not permit a late effect.

FAILED is legal only before ACTIVATING with `publication_not_started=true`,
using `VALIDATION_FAILED`, `CANCELED`, `PRECONDITION_FAILED`, or `STAGING_FAILED`.
`staging_may_exist` is an actual boolean and must be true after STAGED. This
does not assert that staging or earlier editor work had no effect. Last-good
is preserved and the terminal command ID remains retained.

UNKNOWN holds the pending command permanently. Allowed reasons follow the
prior phase: PREPARED/STAGING_UNCERTAIN; STAGED/VALIDATION_UNCERTAIN;
VALIDATED/ACTIVATION_UNCERTAIN; ACTIVATING/ACTIVATION_UNCERTAIN or
READBACK_UNCERTAIN; READBACK/READBACK_UNCERTAIN or TERMINAL_UNCERTAIN.
No unhold, recovery, execution, or rearm API exists.

STOP (`USER_STOP`, `DEADLINE`, `OWNER_SHUTDOWN`) permanently latches. Before
activation it fails pending work; after possible activation it holds UNKNOWN.
Already-held work stays held. Earlier committed receipts remain available.
Repeated STOP and new work reject. A pure rejection after real native effects
does not itself create a hold; the actual owner must retain ownership and
record UNKNOWN when possible, rather than treating rejection as no-effect.

## Verification scope

`test_publication_state_v2.py` uses synthetic native identities and engine facts.
It checks codec parity, both full operations, phase-cut replay, immutable
ownership, dedupe/conflict, all eleven role/hash/size rows, exact twelve-object
name plans, foreign roots, native identity aliases, operation preservation,
fresh scene-observation declarations, cold readback, stale authority, deadlines,
Stop/UNKNOWN/failure behavior, canonical/typed bounds and retained-history
capacity. It establishes pure consistency behavior only. It is not native
storage, actual engine validation, durable publication, or GT03 acceptance.
