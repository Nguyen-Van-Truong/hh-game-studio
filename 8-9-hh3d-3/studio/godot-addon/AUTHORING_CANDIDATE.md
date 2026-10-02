# O2 typed authoring contract candidate

`CR-GODOT-AUTHORING-01`, catalog version 1, proposed profile
`hh-godot-gameplay-source-1`. This is pure validation work under owner O2 in the
25 September tools plan. It is not GT-06 evidence or AUTH/GT-09 acceptance.

`../contracts/godot-authoring-schema-v1.json` is a JSON Schema for its embedded
`x-candidate` catalog instance. `authoring_contract.py` reads that instance with
the shared strict JSON parser and checks its closed metadata, type constraints,
inheritance and references. The ClassDB descriptions are **UNVERIFIED**,
hand-authored candidates. Numeric limits are candidate policy caps, not claims
about native Godot limits. `property_base` shares candidate property definitions;
`native_base` is an unverified proposed native parent, not extraction evidence.

The validator reuses `studio.protocol.core.Request`, payload hashing, canonical
JSON, request digest and the existing `scene.node.create` / `scene.node.update`
operation names. It checks trusted host observations for scene/project revision,
generation, lease/fence/deadline, Stop, node identity and hierarchy. Call
`validate_request(request, context)`; the tests show complete envelope examples.
The separately versioned payload uses `properties` on create and `changes` on
update. Profile selection belongs to a future registered owner; a request cannot
select or enable it. The current adapter/catalog/publication owner is unchanged.

The declaration's `x-candidate` catalog is the source of the candidate class list. Each receives static
accept/reject coverage, including inherited properties. `InputMap` is declared
as a singleton and rejects node creation. Resource properties accept only
`{"resource_id": "..."}` references resolved against the supplied trusted
manifest's exact base assertion. This does not open a resource, verify native
class compatibility, load a dependency graph or permit script attachment.
Resource creation, InputMap actions, tile cells, animation libraries and native
subtype mappings remain work for later contracts and engine integration.

Validation returns immutable proposed data with `runtime_authorized=false`,
`changes_applied=false`, `classdb_verified=false` and pending native tests. It
never applies a mutation, acknowledges a result or advertises a capability.
There is deliberately no in-memory undo adapter or claimed native readback.
Native ClassDB extraction and per-class reject/readback/UndoRedo tests remain
required, along with atomic publication, durable deduplication, effect-time
lease/revision checks, safe resource loading and process ownership.

Gameplay `script_text.replace` is always rejected here. Request flags or
caller-authored AUTH receipts cannot unlock it. AUTH-01 through AUTH-05, including
OS isolation evidence, must be verified by a future registered execution owner
before the new script profile can be enabled. The accepted
`hh-godot-declarative-1` profile remains unchanged.

The separate disposable probe now feeds one byte-exact profile-validated
`hh-godot-declarative-1` script into a temporary Godot editor, checks native
parse/export readback, attaches it through UndoRedo, repeats after redo, and
removes the generated source before snapshot comparison. Run
`o2-native-20260927-33` passed with 396 checks, actual host/wrapper exit 0,
clean log, verified process tree and unchanged source/project snapshots;
closure is `278df6de3137f74fb9bf2f536e4c247d1637a89c63ddd8b68f02f4bca9478d43`.
This is a native profile/readback diagnostic only. It does not execute caller
GDScript, establish an OS sandbox, prove AUTH-05, authorize a public command,
or enable the accepted adapter.

Run `o2-native-20260927-32` is retained as a failed compile attempt: the first
version called a Godot API that does not exist in the pinned engine. It was
repaired before `-33`; no failed artifact was overwritten or promoted.

Pure-Python checks from the repository root (no Godot/Blender execution):

```powershell
python -B 8-9-hh3d-3/studio/tests/godot/test_authoring_contract.py
python -B 8-9-hh3d-3/studio/tests/godot/test_contract.py
python -B 8-9-hh3d-3/studio/tests/godot/test_script_profile.py
```

Observed: 18 candidate tests, 24 existing contract tests and 34 existing
script-profile tests passed. Those results prove static validation only. No
native run, readback/undo, isolation, critic acceptance, plan tick or mini-game
completion is claimed. Merge remains deferred until GT-06 is accepted.

`gameplay_edges.py` adds an authority-0 candidate envelope for signal
connections, group membership, and input-action definitions. It validates
immutable proposals against observed node IDs, revision, generation, lease,
project revision, and duplicate state. Every proposal carries an
`expected_project_revision` in `sha256:<64 lowercase hex>` form, and the
projection records the bound revision. It does not connect a signal, mutate
InputMap, or claim native readback/UndoRedo. The 99-test O2 static run
(including the edge tests) covers this candidate with the existing authoring
and script-profile tests. Disposable native diagnostic `o2-native-20260926-19`
also exercised all three projections through Godot's signal, group, and
InputMap APIs with do/undo/redo/readback; it had actual host exit 0, clean log,
unchanged source/project, and authority 0. This does not enable the profile or
satisfy AUTH-01..05. The native evidence must be reminted if the source closure
changes before inclusion in CR-GODOT-AUTHORING-01 or GT-09.
