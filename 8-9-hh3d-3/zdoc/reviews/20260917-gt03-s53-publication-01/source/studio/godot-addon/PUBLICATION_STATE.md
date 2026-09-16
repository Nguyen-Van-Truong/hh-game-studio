# Pure Godot publication state

`publication_state.py` is an immutable replay reducer for one project and exactly
`scenes/fixture.tscn` plus `scripts/fixture_actor.gd`. It performs no filesystem,
registry, network, Godot, process, queue or capability operation. It imports the
accepted shared protocol's JCS encoder/parser without modifying GT-02.

Every file, lease, checkpoint, engine result and timestamp in an event is a
**caller attestation**. The reducer checks shape, ordering and consistency; it
does not prove those observations. In particular, its terminal `COMMITTED`
means only that a complete internally consistent sequence was supplied. It is
not a public protocol ACK, durable journal receipt, engine acceptance, sandbox
proof or permission to execute/rearm anything. Every lookup includes
`public_ack=false`, `durable_owner_required=true`, `execution_permitted=false`.

## API

```python
state = reduce_event(None, config_event)
state = reduce_event(state, next_event)      # dict or exact canonical bytes
state = replay(events)                      # bounded iterable, CONFIG first
copy = state.snapshot()                     # detached dict
count = state.event_count
immutable_bytes = state.events              # tuple[bytes, ...]
result = lookup(state, command_id, digest=None)
```

`PublicationState` is a frozen/slotted dataclass. Its only constructor input is
the tuple of canonical event bytes, and direct construction validates the whole
history again. No serialized state projection can be imported as trusted state.
Events, snapshots and lookup results cannot mutate retained history. Rejected
events leave the prior state unchanged. `PublicationError` extends shared
`ValidationError` with a fixed code and no source text in its message.

The current deliberately small reducer replays retained history on each new
state. It keeps at most 256 events, 64 command IDs and a 512 KiB state projection.
Canonical event bytes are capped at 12 KiB, leaving space for the native
`PrivateEventLog` frame body below its 16 KiB limit. PREPARED reserves room in
this event-count budget for all five remaining success phases and one Stop.
The durable owner must independently reserve native log bytes, staging bytes,
terminal/custody barriers and cleanup capacity. This module does not reserve
any real resource. IDs are never evicted or made new by expiry; full retention
rejects new admission.

`project_revision(files, scene_revision, engine_sha256)` computes the same
metadata digest as the inert bundle codec. It checks exactly the two file
hash/length pairs but does not read their bytes. `selection_identity(project_id,
command_id, digest, parent, candidate)` derives a command/parent/generation/
candidate/manifest-bound intent identity; it is not a native selection receipt.

## Exact events

All events have exactly these common fields plus their row below:

```text
schema = "hh-godot-publication-event-1"
sequence = consecutive integer starting at 1
kind = one of the fixed event kinds
project_id = the CONFIG project
observed_ms = nonnegative safe integer, nondecreasing through history
```

IDs use lowercase `[a-z][a-z0-9._-]{0,63}` except project IDs, which allow the
shared bounded alphanumeric/dot/underscore/hyphen form. Hashes are lowercase
64-character SHA-256. Revisions/digests/selection identities add `sha256:`.
Native file IDs are 32 lowercase hex characters; volume IDs are canonical
unsigned 64-bit decimal strings. Boolean values never count as integers.

| Kind | Additional exact fields |
| --- | --- |
| CONFIG | `engine_sha256`, `source_closure_sha256`, `store_identity`, `initial` |
| PREPARED | `command_id`, `digest`, `operation`, `candidate_id`, `before_project_revision`, `before_scene_revision`, `expected_files`, `parent_selection`, `admission`, `checkpoint_sha256`, `script_input` |
| STAGED | `command_id`, `digest`, `candidate` |
| VALIDATED | `command_id`, `digest`, `observation` |
| ACTIVATING | `command_id`, `digest`, `current`, `selection` |
| READBACK | `command_id`, `digest`, `observation`, `selection` |
| COMMITTED | `command_id`, `digest`, `readback_event_sha256`, `after_project_revision`, `selection` |
| FAILED | `command_id`, `digest`, `reason`, `publication_not_started`, `staging_may_exist` |
| UNKNOWN | `command_id`, `digest`, `reason` |
| STOP | `reason` |

Nested objects are exact-shape too:

* `files` / `expected_files`: exactly the two allowed paths, each containing
  `{sha256, size_bytes}`. Scene cap 1 MiB, script cap 16 KiB, zero permitted.
* `selection` / `parent_selection`: `{generation, identity}`. CONFIG's initial
  generation is nonnegative. A new activation must be precisely parent+1 and
  have the helper-derived identity, even if content is unchanged.
* `store_identity`: `{volume, file_id}`. CONFIG pins it for all staged blobs.
* `initial`: `{project_revision, scene_revision, files, selection}`. Project
  revision must match the bundle-metadata digest under the pinned engine.
* `admission`: `{lease_id, fencing_epoch, admitted_ms, deadline_ms,
  lease_expires_ms, editor_session_id, editor_generation}`. Admission time must
  equal event time, with `admitted_ms < deadline_ms <= min(lease_expires_ms,
  admitted_ms + 30000)`. Fence/generation are positive. Fence cannot decrease;
  the same fence requires the same lease ID and expiry. These checks do not
  authenticate a lease, session, process or wall clock.
* `script_input`: `null` for `scene.save`; `{sha256, size_bytes}` for
  `script_text.replace`. No script text or raw bytes are legal event fields.
* `candidate`: `{candidate_id, project_revision, scene_revision,
  engine_sha256, files, manifest}`. Here each of the two `files` values and
  `manifest` is a blob descriptor `{object_id, volume, file_id, size_bytes,
  sha256}`. Names are exactly `blob-<32 hex>`; all three names/FileIDs must be
  distinct, on the CONFIG store volume and not its root FileID. The manifest
  is 1–4096 bytes. Candidate IDs are `candidate-<32 hex>`, must match PREPARED
  and cannot be reused by another command in retained history.
* `observation`: `{observation_id, editor_session_id, editor_generation,
  candidate_id, project_revision, scene_revision, engine_sha256,
  source_closure_sha256, manifest_sha256, files, parse_status, import_status,
  exit_code, tree_drained, logs_clean}`. All content/tool fields must equal
  the candidate/CONFIG. Statuses must be `PASS`, exit integer `0`, and both
  booleans true. READBACK requires a different session and observation ID from
  VALIDATED. These supplied markers do not establish actual successful parsing,
  clean logs, process exit, process ownership or isolation.
* `current`: `{project_revision, scene_revision, files, selection, lease_id,
  fencing_epoch, editor_session_id, editor_generation}`. All must equal the
  original PREPARED observations, and ACTIVATING time must precede the original
  deadline and lease expiry. No recovery force flag or refreshed admission is
  accepted. `before_scene_revision` is the live edited scene observation and
  may differ from the last published scene when unsaved edits exist.

Only `scene.save` and `script_text.replace` are modeled. A save candidate must
preserve the original script hash/length and observed live scene revision.
Script replacement must bind its staged script to the exact admitted input
hash/length. The reducer cannot establish whether other scene changes are
semantically allowed: that remains the engine owner's responsibility.

## Phase, failure and lookup behavior

The success sequence is exactly PREPARED → STAGED → VALIDATED → ACTIVATING →
READBACK → COMMITTED. CONFIG's `initial` remains `last_good` until COMMITTED;
ACTIVATING is an intent, not a claim that a native manifest actually changed.
COMMITTED checks the exact preceding READBACK event SHA-256 and derives its
internal receipt from retained original observations. It updates `last_good`
and frees the single pending slot. Its receipt retains original admission,
before/after revisions, two file hashes/lengths, engine/source binding,
selection and validation/readback event hashes. Actual event log/custody proof
must be added by the durable owner rather than inferred from this receipt.

Lookup precedes new admission in the future owner. Same ID/digest returns the
original detached pending/held/terminal observation; a different digest is a
conflict. Appending a second PREPARED is rejected even with identical content.
Likewise event duplicates/out-of-order records are invalid history; a retry is
a lookup, not a second durable append. No retry horizon or implicit execution
permission is provided here. Terminal completion may be recorded after the
original deadline: it does not authorize starting a late effect or replacing
the recorded admission observations.

FAILED is permitted only before ACTIVATING with the explicit attestation
`publication_not_started=true`. Reasons are `VALIDATION_FAILED`, `CANCELED`,
`PRECONDITION_FAILED`, `STAGING_FAILED`. This means publication did not begin;
it never says staging or an earlier in-memory editor operation had no effect.
`staging_may_exist` must be true after STAGED. FAILED preserves last-good and
retains a terminal duplicate lookup result.

UNKNOWN is nonterminal and holds the pending command. Legal reasons depend on
the preceding phase: PREPARED/STAGING_UNCERTAIN;
STAGED/VALIDATION_UNCERTAIN; VALIDATED/ACTIVATION_UNCERTAIN;
ACTIVATING/ACTIVATION_UNCERTAIN or READBACK_UNCERTAIN;
READBACK/READBACK_UNCERTAIN or TERMINAL_UNCERTAIN. It has no normal continuation,
retry or unhold API. A later recovery owner needs a separately reviewed
reconciliation design; this reducer does not impersonate that owner.

STOP reasons are `USER_STOP`, `DEADLINE`, `OWNER_SHUTDOWN`. STOP is a permanent
latch in this history. Before activation it terminally fails a pending command
and preserves last-good; after possible publication it changes the pending
command to UNKNOWN/held. An already UNKNOWN command remains held with its
original uncertainty. A prior COMMITTED receipt remains available. Repeated
STOP events and all new work are rejected; replay never clears the latch.

An inconsistent READBACK event throws and cannot create COMMITTED. Because
reducer validation itself is effect-free, rejection leaves the prior state
unchanged; the real owner must retain an external hold and record UNKNOWN when
an actual effect may have occurred. This pure reducer cannot determine that
from an invalid event. Its sequence checks are not authentication against a
coherently rewritten history: native log identity/hash-chain/custody validation
must precede replay. Nothing invokes or bypasses protected-file rearm.

## Verification scope

`python -B studio/tests/godot/test_publication_state.py` exercises immutable
ownership, exact schema and byte/numeric bounds, each phase-cut replay, two-file
revision binding, synthetic validation/readback failures, Stop before/after
activation, held uncertainty, lost-reply lookup, command conflicts, stale
authority, malformed history and bounded capacity. All engine/native storage
observations in these tests are synthetic. They are not durable publication,
actual sandbox, engine parse/reopen or GT-03 acceptance evidence.
