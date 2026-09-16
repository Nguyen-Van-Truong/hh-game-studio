# In-memory scene command layer

`scene_commands.gd` is a trusted `@tool` helper for the actual EditorPlugin. It
only edits the currently edited `res://scenes/fixture.tscn` on the Godot main
thread. The plugin passes its real `get_undo_redo()` manager and retains this
helper while its scene history is alive. It must create a fresh helper and
strictly newer generation after scene reload. No ObjectID is a wire target.

This layer does not own session authentication, leases/fencing, persistent
deduplication, checkpoints, publish, filesystem save, or durable receipts. The
host must complete those gates before invocation. `SCENE_APPLIED_IN_MEMORY`
means the live scene readback succeeded; it is not `COMMITTED` and cannot be
used as a filesystem publication receipt. The frozen GT-02 JCS source is copied
unchanged by the snapshot builder to `res://addons/hh_studio/jcs_godot.gd`.

## Methods and result shapes

```gdscript
initialize(root: Node3D, manager: EditorUndoRedoManager, generation: int = 1) -> Dictionary
inspect(offset: int = 0, limit: int = 64) -> Dictionary
preview(operation: Dictionary) -> Dictionary
apply(operation: Dictionary) -> Dictionary
undo(operation: Dictionary) -> Dictionary
redo(operation: Dictionary) -> Dictionary
last_transition() -> Dictionary
```

Initialization is once per helper. The root must be the actual edited scene
root, its scene path must match the fixed fixture path, and its `hh_studio_id`
metadata must be the string `root`. Every descendant has its own unique string
`hh_studio_id` and `owner == root`. A script-less root is supported. This helper
does not add missing IDs or repair unowned/unsupported nodes while inspecting.

Successful inspection returns:

```json
{
  "ok": true, "code": "SCENE_INSPECTED", "generation": 1,
  "revision": "sha256:<64 lowercase hex>",
  "state": {"nodes": []}, "total": 1, "offset": 0, "history_id": 1,
  "held": false, "filesystem_mutated": false
}
```

Rows have `stable_id`, `parent_id`, `sibling_index`, `owner_id`, `node_type`,
`name`, `position`, `rotation_degrees`, `scale`, `stored`, and sorted `groups`.
MeshInstance3D rows also have `box_size`. The root has empty parent/owner IDs.
Vectors are three-number arrays. `stored` covers native stored properties and
metadata beyond the writable subset, so a manual change of visibility, mesh
subdivision, metadata or other persisted native properties changes revision.
Resources are represented by supported semantic properties, never instance IDs.
Godot native vector/matrix values use typed byte encodings inside the JCS state;
the revision is defined within the pinned Godot/architecture. Resource path and
generated subresource scene IDs are excluded. A fixed trusted fixture script
is represented by path and source hash. The complete state, not the paginated
rows, determines revision. State canonical bytes are capped at 262144.

Preview returns `ok`, `code: SCENE_PREVIEW`, operation/command ID, generation,
`before_revision`, `diff: {before, after}`, the fixed `affected_files`,
`undo_policy: revision_guarded`, and `filesystem_mutated: false`. Its scratch
node/resource allocations never enter the edited scene or history.

Successful apply/undo/redo returns `ok`, `code: SCENE_APPLIED_IN_MEMORY`,
operation/command ID, generation, `before_revision`, `revision`, complete
`state`, `history_id`, and `filesystem_mutated: false`. A direct native history
invocation obtains the same transition readback from `last_transition()` but
does not have an external command ID. Errors are bounded fixed codes with
`ok: false`, `filesystem_mutated: false`, and `next_action: inspect_reconcile`.
That filesystem flag never asserts that an uncertain in-memory callback made
no change.

## Exact engine projection

The Python catalog validates the original wire/envelope. This layer accepts
exactly these six fields and validates them again before live mutation:

```json
{
  "operation": "scene.node.create", "command_id": "cmd.create.1",
  "expected_revision": "sha256:<current complete scene state hash>",
  "expected_generation": 1, "target_stable_id": "root",
  "payload": {
    "expected_generation": 1, "stable_id": "cube", "node_type": "MeshInstance3D",
    "name": "Cube", "position": [0, 0, 0], "rotation_degrees": [0, 0, 0],
    "scale": [1, 1, 1], "box_size": [1, 1, 1]
  }
}
```

- Create targets the existing parent. `node_type` is exactly `Node3D` or
  `MeshInstance3D`. The latter requires `box_size`; Node3D forbids it.
- Update targets the existing node; payload is exactly
  `{expected_generation, changes}`. `changes` is a nonempty subset of `name`,
  `position`, `rotation_degrees`, `scale`, and `box_size` (mesh nodes only).
- Remove targets a nonroot leaf; payload is exactly `{expected_generation}`.
  Removing a subtree is deliberately unsupported.
- Undo/redo target `root`; payload is exactly `{expected_generation, steps: 1}`.
  The wrapper refuses foreign history actions rather than undoing user work.
- `scene.inspect` is routed by the plugin to `inspect(offset, limit)` after
  outer validation; it is not an `apply()` operation.

Both generation fields must agree with the initialized editor generation.
Stable IDs and local command IDs match `[a-z][a-z0-9._-]{0,63}`. Names match
`[A-Za-z][A-Za-z0-9_]{0,47}`; sibling name comparisons also reject case aliases.
Position components are within -10000..10000; rotation degrees -360..360;
scale and box-size components 0.001..1000. Boolean values are not numbers.
Finite arrays have exactly three components. There are at most 64 nodes,
maximum depth 16, inspection limit 1..64 and operation canonical cap 8192.

The supported scene consists of those two exact native node classes and
BoxMesh resources. No arbitrary Resource, node class, script path, property
name, method name, `node.call`, eval or execution request is accepted. Attached
GDScript is only readable at `res://scripts/fixture_actor.gd`; this layer never
attaches, writes, reloads, executes or grants trust to that script. Persistent
signal connections and unsupported stored Variant/resource types hold mutation
rather than silently disappearing from the revision. Their support is not
claimed by this layer.

## Undo ownership and manual edits

An action is one guarded callback for do and one for undo, with the edited root
as the manager's custom history context and merging disabled. Callbacks check
the complete expected scene revision and generation immediately before the
first effect, then read back the resulting scene. Node resolution is by stable
ID at admission and callback, with local retained identity checks to reject a
manually replaced object. All mutations are synchronous and use fixed native
properties; there is no await/yield between guard and effect.

Transforms/names and original/new mesh resources are retained. Mesh updates
operate on a duplicated BoxMesh, so changing one node's box size does not mutate
another node that shares the old resource. Both resource snapshots are hashed
and checked before applying them later. Node remove retains its actual node,
parent, sibling index and scene owner. Restore sets owner after reattachment.
Detached-node signatures reject changes made to an off-tree node before redo.

Godot's native UndoRedo cannot veto cursor movement from inside a callback. A
manual edit conflict therefore holds this adapter; no later callback is allowed
to mutate it until the supervisor reconciles using a fresh context. The caller
must inspect `last_transition()` after directly invoking the actual history;
the boolean returned by `UndoRedo.undo()` only reports history traversal.

Created/removed node ownership is retained through a RefCounted custody object
registered by `add_do_reference`/`add_undo_reference`. Its finalizer frees only a
detached node. This prevents clearing redo history after a refused undo from
freeing a still-live node containing the user's manual edit. Custody never frees
an attached node; normal scene ownership handles scene teardown. The plugin
must drain/clear the owned scene history appropriately before discarding the
helper, and must never clear unrelated user/global histories.

There are at most 256 local command receipts. Duplicate ID/content returns its
original in-memory receipt without repeating an action; changed content
conflicts and capacity exhaustion rejects. These receipts are session-local
and do not replace the host's durable command journal or retry horizon.

## Validation status and references

This file describes the implementation contract. Actual editor parse/runtime,
undo/redo/manual-edit, save/reopen and later transactional publication evidence
are recorded by the coordinator's isolated fixture runner; source presence is
not evidence that those gates pass.

API references consulted on 2026-09-16:

- [EditorUndoRedoManager](https://docs.godotengine.org/en/stable/classes/class_editorundoredomanager.html)
- [UndoRedo](https://docs.godotengine.org/en/stable/classes/class_undoredo.html)
- [OS thread IDs](https://docs.godotengine.org/en/4.4/classes/class_os.html)
