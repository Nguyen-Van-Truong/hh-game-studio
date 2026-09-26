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

The declaration contains 19 candidate node classes. Each receives static
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
and duplicate state; it does not connect a signal, mutate InputMap, or claim
native readback/UndoRedo. The 57-test O2 static run covers this candidate with
the existing authoring and script-profile tests. A future native remint is
required before it can be included in CR-GODOT-AUTHORING-01 or GT-09.
