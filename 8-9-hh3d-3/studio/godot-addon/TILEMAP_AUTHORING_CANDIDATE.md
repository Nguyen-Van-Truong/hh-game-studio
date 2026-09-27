# O2 TileMapLayer cell candidate

`tilemap_authoring.py` is an authority-0 validator for deterministic
`TileMapLayer` cell placement and clearing. It binds each cell to a trusted
TileMapLayer identity, tile source/atlas revision, cell coordinates and
alternative tile, plus project/scene revision, generation, lease and deadline.
It rejects unknown sources, atlas coordinates, alternatives, duplicate cells,
out-of-range coordinates, traversal-like data and stale observations.

The candidate does not create a TileSet, edit Godot, save a scene, use
UndoRedo, or issue an ACK. The disposable native probe now creates a minimal
TileSet atlas, applies one cell through native `TileMapLayer`, verifies source
and atlas readback through do/undo/redo, and removes the temporary layer.
`o2-native-20260927-26` passed with host exit 0, clean log, unchanged
source/project snapshots, and 344 checks. It remains authority 0; production
lease rechecks, atomic save and AUTH-01..05 isolation are still required.

Static verification:

```powershell
python -B -m unittest tests.godot.test_tilemap_authoring
```

This file does not enable the candidate profile or alter the accepted adapter.
