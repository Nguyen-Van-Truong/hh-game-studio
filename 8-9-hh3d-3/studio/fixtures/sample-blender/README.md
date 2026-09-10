# GT-01 Blender fixture

Original 1 m cube, centered origin, identity world transform, Blender Z-up
right-handed coordinates, one material and no external files. This is the
small GT-01 source fixture; it does not implement the GT-04 Blender bridge.

Run the pinned executable in a fresh background process:

```text
blender --background --factory-startup --disable-autoexec --python-exit-code 2 --python create_fixture.py -- --output <new-directory>/cube-origin.blend
```

The output parent must already exist. Existing outputs and linked paths are
rejected. The script saves a unique staging file, reopens it, verifies geometry,
material and units, then publishes exclusively without replacing another file.
A failed staging run may leave its diagnostic directory for inspection.

GT01_BLENDER_TRACE is emitted only after save/reopen readback. Actual process
exit and descendant cleanup are separate host checks; no GLB/export/bridge
or full GT-01 acceptance is claimed by this fixture.
