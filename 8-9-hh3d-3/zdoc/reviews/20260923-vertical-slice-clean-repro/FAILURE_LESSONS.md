# Clean reproduction lessons

The first clean-checkout attempt exposed two harness defects before the final pass:

1. `Start-Process -ArgumentList` needed explicit quoting for Python and Godot
   paths when the checkout directory contained spaces.
2. A fresh Godot checkout needed a bounded editor import pass, and generated
   `.blend`/`.blend1` files had to be temporarily isolated so the GLB importer
   did not require a GUI Blender path. The wrapper now restores those files in
   `finally`.

The final run used a fresh temporary checkout, Blender author/reopen/export,
Godot import and all five runtime tests. It is Track B evidence only (`AUTHORITY=0`).
