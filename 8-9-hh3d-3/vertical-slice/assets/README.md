# Generated Blender assets

`generate_asset.py` writes `pickup_original.blend` and `pickup_original.glb`
here. They are reproducible build outputs and are intentionally ignored by
Git. The tracked source is the Blender script; the verification wrapper runs
Godot `--asset-test` when the GLB is present and reports an explicit external
blocker when Blender output is unavailable.
