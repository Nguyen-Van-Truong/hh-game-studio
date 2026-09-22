# Vertical slice Blender direct verification — S173

This is an independent Track B asset-pipeline run. It is not GT06 evidence
and does not satisfy any GT06 benchmark, attribution, dataset, leak, or critic
gate.

## Run identity

- `run_id`: `vertical-slice-s173-blender-direct-01`
- `command_id`: `cmd.vertical-slice.s173.blender.direct.1`
- `run_namespace`: `vertical-slice`
- `authority`: `0`
- source commit: `034d20be1d27218285457202ec80d1020865403b`
- Blender: bundled `blender-5.2.1-windows-x64/blender.exe`, SHA256
  `8f7a131ad8bc148edc218b334f07d92a57f5a357fa66d913b290537fd8353c06`

## Result

The bounded native Blender route used `blender.exe --background
--factory-startup --python ...` for both steps. Authoring and reopen/export
both exited `0`, wrote no stderr, and emitted the expected markers. The output
artifacts were reopened in a fresh Blender process before the second export.

- author marker: `BLENDER_ASSET_PASS`
- reopen marker: `BLENDER_REOPEN_EXPORT_PASS`
- GLB SHA256: `1ec4d9e00909f68e11afa3617cb72d6fef11b3be9a6dc10729bbc5cc27672588`
- `.blend` SHA256: `3cff3e668ed3ebd9f08ee29b6c5fe4c64aafc9cc3a306e0c5cd31ebff38a0882`
- leftover Blender/Godot/CDB/WinDbg processes: `0`

Raw stdout/stderr is preserved in this directory. The existing
`verify_blender.ps1` wrapper was also exercised in this wave and failed before
authoring because it passed a plain Python interpreter without `bpy`; that is
a harness defect, not an asset failure. The direct Blender executable path is
the valid bounded result recorded here. The wrapper should be repaired to pass
`blender.exe --background --python` or to use a Python environment that
actually provides `bpy`; this package does not silently convert the wrapper
failure into a pass.

## Exclusions

`GT06_DATASET=0`, `F13=0`, `F14=0`, `GT06_ACCEPTANCE=0`, `LEAK=0`,
`ROOT_CAUSE=0`, `FORMAL_RETRY=0`.
