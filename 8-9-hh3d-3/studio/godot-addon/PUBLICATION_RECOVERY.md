# Publication recovery candidate

This module extends the existing protected event stream with at most 32 typed
recovery events, including a reserved deliberate Stop record. The V4 publication prefix and optional V5 edit events retain
their exact original bytes. Selected project files stay read-only throughout;
recovery grants no later edit, save, selector replacement, or generic restart.

`RecoveryJournal` is a trusted storage layer. Its admission/readback dictionaries
are attestations, not user authority or engine proof. `PublicationRecovery`
enforces registered authority and actual editor ownership before supplying
those attestations. Public entry points must use that facade.

## Registered admission

Open `PublicationRecovery` using the storage ID, project ID and expected source
closure. Its `authority_context()` rereads native custody, stream head, selected
descriptor/version and source/engine pins, and returns the minimum fresh epoch.
Construct the fresh session through the exported `session_model` so its class
identity matches the module's source-addressed loader:

```python
owner = PublicationRecovery.open(storage_id, project_id=project_id,
    expected_source_closure_sha256=closure)
context = owner.authority_context()
sessions = session_model.PublicationSession(project_id, parent, catalog_digest,
    minimum_fencing_epoch=context['minimum_authority_epoch'])
# The authenticated host issues and checks a project.reconcile grant, then leases.
authority = ReconciliationAuthority(sessions, registered_grant, registered_lease)
response_bytes = owner.reconcile(authority, original_command_id, original_digest,
    editor_parent=owned_evidence_directory, editor_binary=pinned_editor,
    deadline_ms=deadline)
```

The admission binds one exact native owner, command/digest, storage/project,
source, stream head, complete selection and fresh fencing epoch. Copied grant,
lease or permit objects do not confer authority. Its deadline is at most 30
seconds. Registered session checks and effect admission run before the durable
admission, editor load, and terminal phases. Stop/revoke prevents later phases;
an already started effect drains and retains uncertainty on failure.

The recovery host latches Stop immediately on the independent control route.
An owned drain waits for current recovery accounting, appends typed `STOPPED`
to this same native stream and verifies its custody/readback. Replies distinguish
`PENDING`, `DURABLE` and `UNKNOWN`; a failed barrier never claims persistence.
Opening a new host observes durable Stop before offering another lease or
reconciliation. Historical terminal bytes remain readable. A pending attempt
becomes held, and no later admission/readback/terminal can resume it.

The fresh editor loads a separate owned mirror of all eleven selected files.
Native process/root/session identity, engine/source pins, semantic JCS, script
source/defaults, file bytes, durable generation and empty UndoRedo history are
checked. A local registered receipt retains immutable observation bytes and is
rechecked against the live editor immediately before terminal publication.
Constructor/close failures retain the precise cleanup owner for retry.

## Durable outcomes

| Original state | Narrow supported outcome |
|---|---|
| Witnessed save/script COMMITTED, still selected | Fresh readback; exact original response bytes |
| Pre-CAS pending command, selection equals last-good | Fresh last-good load; durable recovered REJECTED response |
| SELECTED/READBACK or exact CAS before SELECTED | Fresh selected load; separately recovered terminal |
| Original COMMITTED beyond saved custody | Same-stream HOLD before custody advances; original response remains blocked; explicit fresh reconciliation required |
| Pending V5 EDIT_INTENT/EDIT_READY | Fresh selected last-good load; recovered rejection, without restoring volatile state or history |
| Witnessed V5 editor COMMITTED | Distinct `verify-historical-edit` route; exact historical response, explicitly `files_saved=false` and `live_state_durable=false` |
| Unwitnessed V5 editor COMMITTED | Original success remains blocked; recovered last-good rejection retains uncertainty |
| UNKNOWN, no durable Stop, exact last-good selected | Explicit fresh-authority restoration; original UNKNOWN bytes preserved; recovered response states `original_outcome_unknown=true` |
| Durable Stop, or UNKNOWN with a different candidate selected | Remains held; no automatic completion or selector rollback |

The recovered response is stored canonically in the terminal event and reread
from the native stream/custody before return. Lookup and retry do not replay
the original effect. V5 prefixes also verify native checkpoint, capture and
observation blobs. A recovered editor never inherits old ObjectIDs, UndoRedo,
bearers, leases or effect permits.

If recovery dies after a log flush but before Registry custody advances, a
durable HOLD records the saved and observed heads before any witness update.
Reopening reuses a matching HOLD, caps the suffix, and cannot silently promote
an unwitnessed original COMMITTED into a historical success. Ordinary V4/V5
readers continue to reject recovery suffixes.

## Evidence and remaining limits

The S54 storage component has actual Windows crash/custody proof for the
pre-CAS, CAS-before-SELECTED and COMMITTED-before-custody cuts. Its engine and
original authority attestations are synthetic. The separate editor component
uses actual process exit 92, fresh registered authority, actual Godot readback,
same-stream terminal and byte-identical readonly reopen; its trusted bootstrap
uses Windows-observed semantics, without an isolated Linux validator or HTTP
publication proof. Every package retains its own frozen source hash. Neither
component is GT-03 acceptance.

Authenticated Linux/publication/crash/fresh-HTTP recovery has S54 component
evidence; remaining cut coverage, final source integration and independent
critics are still required. Native durable recovery Stop is being verified
separately. A persisted original or recovery Stop remains stopped. An old idle
Stop that existed only in RAM cannot be reconstructed. Recovery does not roll back a selected candidate for UNKNOWN,
preserve unsaved in-memory edits after host death, or reopen publication writes.
