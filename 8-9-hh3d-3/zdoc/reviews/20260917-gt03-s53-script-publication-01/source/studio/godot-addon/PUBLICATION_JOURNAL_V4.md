# Complete-bundle publication v4

V4 extends the S52 scene-save chain with bounded `script_text.replace` and
stores the exact original protocol response. It uses the unchanged v3/v2
native ownership, custody, protected bundle staging, selector CAS, cleanup,
and permanently readonly reopen. Accepted GT-02 core and v3 replay are unchanged.
V4 and v3 reject one another's event schema; no implicit history migration occurs.

The live publication owner verifies registered editor and Linux validation
receipts plus current authorization before supplying bounded facts. Neither
pure replay nor the native journal authenticates these facts, runs an engine,
or independently authorizes a public ACK. Their outer reports retain
`public_ack=false`, `engine_effects_verified=false`, and `execution_permitted=false`.

## Durable order

Both operations begin with `CAPTURE_PREPARED → CAPTURED → PREPARED → STAGED →
VALIDATED`. The original capture contains the real dirty scene and original
script. Save retains all captured inputs. Script replacement requires the exact
requested new script hash/size, the exact captured scene, and unchanged other
nine inputs, including UID files. Candidate semantic revision belongs to the
validated complete bundle; it is distinct from the original captured revision.

Save then uses `ACTIVATING → SELECTED → READBACK → COMMITTED`, with registered
same-editor adoption. Script replacement inserts `RETIRE_PREPARED → RETIRED`
before `ACTIVATING`; only a fresh selected editor can provide its `READBACK`.

`RETIRE_PREPARED` binds a unique intent ID, original editor/generation/root,
unchanged command context, and an at-most-10-second retirement deadline within
the existing admission. `RETIRED` binds the registered observation's hash,
same intent ID, old identity/revision, effect interval, actual exit and wrapper
exit zero, Job count zero/observed/closed, and no tainted Job or retained handles.
Generation overflow is rejected before intent persistence.

Fresh adoption requires another session, a different PID/creation-time pair,
another native workspace identity, the same installed editor source, exactly
old generation + 1, selected native FileVersion, and all final bundle metadata.
Old/new Godot root ObjectIDs may numerically repeat across processes. The new
process interval begins after durable `SELECTED` and the old checked close.
The root owner keeps both lifecycle owners until checked cleanup.

## Typed APIs

`PublicationJournalV4.create/reopen` follow v3. Reopen verifies actual selected
native objects and custody and remains readonly. New methods are:

```python
capture_prepared(command_id, digest, *, operation, script_change,
    expected_revision, editor, editor_generation, root_instance_id,
    admission, scratch_name, observed_ms)
retire_prepared(command_id, digest, *, current, retirement_intent_id,
    deadline_ms, observed_ms)
retired(command_id, digest, retirement_facts, *, observed_ms)
lookup_response(command_id, digest)  # exact canonical response bytes
```

`script_change` is `None` for save; replacement requires exact
`{path, expected_sha256, sha256, size_bytes}` at the profile script path, with
1–16384 UTF-8 bytes bound by the caller and bundle codec. `readback` facts add
`mode=same_editor` or `mode=fresh_editor`. The exact bounded retirement and
fresh-adoption shapes are `RETIREMENT_FIELDS` and `FRESH_ADOPTION_FIELDS` in
`publication_state_v4.py`. Unknown fields and bool/int aliases are rejected.
The command admission remains at most 90000ms; this does not extend per-effect
editor grants or authorize any expired effect.

`commit` constructs the canonical response internally. Its durable receipt
binds operation/digest, before/after revisions, selected FileVersion, and the
READBACK event and adoption hashes. The receipt hash excludes the response;
the response references that hash; the terminal event persists the response.
This avoids a self-referential hash. Public codes are
`GODOT_MANAGED_SCENE_SAVED` and `GODOT_MANAGED_SCRIPT_REPLACED`.

FAILED/UNKNOWN events likewise persist deterministic original responses.
FAILED is allowed only in pre-retirement/pre-selection phases. Retirement or
selection uncertainty becomes UNKNOWN, holds publication, and returns no ACK.
Stop after an existing UNKNOWN preserves its original response and uncertain
phase. Stop after COMMITTED persists stopped state without altering the
already committed command response. Authenticated lookup may return the exact
historical response after readonly reopen without re-executing the effect.

## Scope and checks

`test_publication_state_v4.py` exercises synthetic event histories, strict
value checks, complete-input delta binding, generation/retirement order,
phase cuts, Stop, and exact response replay. `test_publication_journal_v4.py`
uses actual Windows protected roots, registered custody, staged native objects,
selector CAS, response persistence, and readonly reopen. Its editor/auth facts
are synthetic and do not prove the real public engine route.

This slice does not implement reconciliation of an interrupted selection,
restoration of a last-good editor, or writable restart/rearming. A CAS effect
without a witnessed SELECTED event remains held and readonly reopen fails
closed. GT-03 complete/restore proof still requires the separate bounded
same-app recovery path; full scheduling/recovery remains GT-07.
