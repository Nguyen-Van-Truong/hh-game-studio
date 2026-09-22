# Vertical slice verification — S172 clean copy

This package records an independent Track B verification of the Godot/Blender
vertical slice. It is not GT06 evidence and cannot close or replace any GT06
gate, dataset, attribution requirement, or critic review.

## Run

- `run_id`: `gt06-s172-vertical-slice-clean-01`
- `command_id`: `cmd.gt06.s172.vertical-slice.clean.1`
- `run_namespace`: `vertical-slice` (the historical `gt06-` prefix is retained
  for traceability and does not make this GT06 evidence)
- source commit: `034d20be1d27218285457202ec80d1020865403b`
- evidence commit: `9953d076bcec6135bc748541cb2a4ed90c9e4dc9`
- wrapper: `8-9-hh3d-3/vertical-slice/verify_slice.ps1`
- interpreter: bundled `pwsh.exe` (the system Windows PowerShell lacked
  `Get-FileHash` in its execution environment)
- Godot executable: pinned Godot 4.7.2 console binary; SHA256 is recorded in
  `vertical-slice-verification-s172.json`.

The wrapper ran on a fresh temporary copy with the generated authoring files
relocated as designed. Import, smoke, deterministic, save/load, gameplay and
asset readback all returned process exit `0` and their required markers.

Observed markers:

- deterministic digest: `44a33feadaa955fe738d8d0e840a141bacd85801f2a827fa71086f2c7f7fdeb9`
- save/load: malformed save rejected and backup recovery succeeded
- gameplay: pause froze simulation while runtime advanced; win and loss restart
  paths passed
- asset readback: `mesh_count=2`

## Environment observations

A direct run against the existing checkout timed out during editor layout
loading after 30 seconds. No Godot process remained. The fresh copy imported
and passed the complete wrapper, so this is retained as a checkout/editor-cache
observation rather than a source failure. A first wrapper invocation using
system Windows PowerShell stopped before tests because `Get-FileHash` was not
available; the bundled `pwsh.exe` run is the authoritative result in this
package.

## Scope

`AUTHORITY=0`, `TRACK=VERTICAL_SLICE`, `GT06_DATASET=0`, `F13=0`, `F14=0`,
`GT06_ACCEPTANCE=0`. No formal benchmark or CDB attribution run was started
for this package, and no generated `.godot` state from the temporary copy is
part of the source manifest.
