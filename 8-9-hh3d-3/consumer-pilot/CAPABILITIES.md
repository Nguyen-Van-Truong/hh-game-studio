# Pilot capability boundary

S177 is one consumer of authored map and asset data. It does not establish a
general game authoring API. None of these rows changes GT01–GT10 acceptance.

| Capability | Implemented path | Evidence and limit |
|---|---|---|
| Primitive map authoring | GT03 authenticated `scene.node.create`, `scene.save`, durable Stop | Three MeshInstance3D/BoxMesh nodes; saved native adoption and map projection agree. |
| Blender asset authoring | GT04 authenticated writer and `export.publish` | One box/material/transform; protected `.blend` and GLB hashes, actual native/export exits and cleanup. |
| Consuming the asset | Native Godot GLTFDocument | The authored GLB is instantiated in the live scene. Presentation normalizes mesh transforms; this is not a transform-parity test. |
| Movement and interaction | Pilot application code | Fixed 60 Hz movement, bounds, distance-based pickup. No collision, combat, or general physics writer proof. |
| UI and input map | Pilot application code | Label text and Godot InputEventAction injection are checked. No GT03 Control/InputMap writer or OS keyboard automation proof. |
| Pause and replay | Pilot runtime loop | Simulation state freezes across 12 advancing engine frames. Two 60-frame input traces agree; a changed trace differs. No network determinism claim. |
| Save/load | Pilot generation files | Hash-checked immutable saves, restored live state, corrupt newest generation falls back to prior save. No power-loss/disk-failure guarantee. |
| General 2D/resources/audio/animation | Not exercised by this pilot | Additional typed writer contracts, readback/undo/recovery tests and real consumers are needed before advertising support. |
| Runtime control via HH Studio | Not exercised by this pilot runtime | GT06 host play/input/pause/capture integration remains separate; application self-tests do not replace it. |
| Android and packaging | Not exercised | GT08 physical device and GT10 install/upgrade/rollback gates remain open. |

The inspected writer contracts are `studio/godot-addon/contract.py` and
`studio/blender-addon/contract.py`; their byte hashes are retained in the
packet. The runtime script and input maps are hand-written consumer code.

Next integration work should reuse the same authored inputs, inspect the
existing GT06 control/capture contract for a supported consumer entry point,
and add only the missing proof. Another Godot/Blender authoring run would not
fill the control/capture or general-writer gaps.
