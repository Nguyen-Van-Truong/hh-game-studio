# O2 scene-instance candidate

`scene_instance.py` is an authority-0 validator for creating and removing
typed PackedScene instances. It binds a proposal to a trusted scene-source
manifest (`scene_id`, `scenes/*.tscn`, source revision), parent node identity,
project/scene revision, generation, lease and deadline. It accepts only finite
2D or 3D transforms, checks parent dimensionality, rejects traversal/external
paths, duplicate stable IDs and stale source revisions, and returns detached
projections with `changes_applied=false` and `runtime_authorized=false`.

The module does not load a scene, call `PackedScene`, mutate Godot, perform
UndoRedo, save, or issue an ACK. A future native owner must re-read the source
hash and parent on the Godot main thread, instantiate atomically, verify the
new stable ID, and add an UndoRedo transaction before this candidate can join
`CR-GODOT-AUTHORING-01` or GT-09.

Static verification:

```powershell
python -B -m unittest tests.godot.test_scene_instance
```

This file does not enable the candidate profile or alter the accepted adapter.
