# O2 shape-resource candidate

`resource_authoring.py` is an authority-0, pure validation contract for four
collision-shape resources: `RectangleShape2D`, `CapsuleShape2D`,
`BoxShape3D`, and `CapsuleShape3D`. It accepts `scene.resource.create` and
`scene.resource.update` proposals only; it does not load or create a Godot
resource, mutate a scene, call UndoRedo, save files, or issue an ACK.

The trusted context binds the proposal to project and scene revisions,
generation, lease/fencing epoch, deadline, stop state, a closed node snapshot,
and a closed resource identity snapshot. Creation is limited to a matching
`CollisionShape2D`/`CollisionShape3D` node with finite positive dimensions.
Capsules require `height >= 2 * radius`. Updates require an existing
single-owner, non-shared resource of the asserted class and validate the
resulting dimensions after a partial update. Resource paths, arbitrary classes,
external loads, shared-resource mutation, and script operations are rejected.

The projection and preview are detached copies with `authority=0`,
`changes_applied=false`, `runtime_authorized=false`, and native checks pending.
Future integration must add native ClassDB/property/readback/UndoRedo tests,
atomic save and revision checks, durable deduplication, and AUTH-01..05
isolation before this candidate can join `CR-GODOT-AUTHORING-01` or GT-09.

Pure static verification (no Godot/Blender process):

```powershell
python -B -m unittest tests.godot.test_resource_authoring
```

This file does not change the accepted adapter or enable the candidate profile.
