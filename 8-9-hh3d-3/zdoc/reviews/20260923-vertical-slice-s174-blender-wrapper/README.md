# Vertical slice Blender wrapper verification — S174

Independent Track B evidence for the repaired `verify_blender.ps1` wrapper.
This does not open or satisfy GT06.

- `run_id`: `vertical-slice-s174-blender-wrapper-01`
- `command_id`: `cmd.vertical-slice.s174.blender.wrapper.1`
- `run_namespace`: `vertical-slice`
- `authority`: `0`
- source commit: `57e5b54e4e5fa6623614a23b8aa313d409a25123`
- wrapper SHA256: `49e13cb362d25b561ae89a951b0954964d0fc2821e3ab445028ad8b6aa36ce56`
- Blender SHA256: `8f7a131ad8bc148edc218b334f07d92a57f5a357fa66d913b290537fd8353c06`

The wrapper was run with the bundled `pwsh.exe` and explicit native Blender
executable. It now invokes two fresh Blender processes in background mode,
checks actual exits and markers, and reports the GLB hash. Author and
reopen/export both exited `0`, stderr was empty, and the expected markers were
present. Raw stdout/stderr is retained in this directory.

The previous plain-Python `bpy` failure remains preserved in S173 evidence;
this run verifies the corrected wrapper rather than hiding that failure.

`GT06_DATASET=0`, `F13=0`, `F14=0`, `GT06_ACCEPTANCE=0`, `LEAK=0`,
`ROOT_CAUSE=0`, `FORMAL_RETRY=0`.
