# HH3D vertical slice verification

This report is independent of GT06 and has `AUTHORITY=0` for the tooling
plan. It demonstrates a small playable Godot + Blender pipeline and does not
replace any GT01–GT10 gate.

| Field | Value |
|---|---|
| `RUN_ID` | `gt06-vertical-slice-godot-01` |
| `COMMAND_ID` | `cmd.vertical-slice.verify.1` |
| `TIMESTAMP_UTC` | `2026-09-22T21:03:37Z` |
| `PLAN_HASH` | `7203d567ce822974d21364b6cd083ed64d30247e809533a78b021bbe154eb899` |
| `TOOLING_SOURCE_HASH` | `fce149cd3a62e102aaba225794b9a5078cd84d7647cb359f6bbcacb8895ddcde` |
| `SLICE_SOURCE_CLOSURE_SHA256` | `ce4d15755ae164ca16c33da08300dab60bf2fd17c59dd76af63f1185439baaea` |
| `CLOSURE_ALGORITHM` | `sorted repo-relative path (including 8-9-hh3d-3/vertical-slice/) + NUL + file SHA-256 + LF, UTF-8; report excluded to avoid circularity` |
| `GODOT_SHA256` | `35dab11e04ece16a2b93035e65204f4a944a3e00b020d43e54409193379d5eef` |
| `BLENDER_RUNTIME` | `bpy 4.5.10 LTS`, build `6dc0b208d1b5` |
| `BLENDER_ZIP_SHA256` | `ef6d846b8015f47ade6df3f9322ce17419080a5d922fa562b6c966064fe30dce` |
| `BLENDER_HEADLESS_STATUS` | `PASS` |
| `BLENDER_GUI_STATUS` | `EXTERNAL_BLOCKED_SXS_blender.crt` |
| `GLB_SHA256` | `201913890337f056defbce7764dea8f8851d0ea698ab34579fade4ebba93502f` |
| `VERTICAL_SLICE_COMMIT` | `6686da2d` |
| `AUTHORITY` | `0` |

## Frozen source manifest

The closure covers these tracked source files. Generated `.blend`, `.glb`,
Godot import/cache and user-save files are excluded and reproducible from the
commands below.

| Path | SHA-256 |
|---|---|
| `.gitignore` | `9dc9153d9296738569964a508d919024a32d04f4b08957b3a41725cc2e3a34e2` |
| `README.md` | `0745a9d5330740880251fd630180b62808196f6ba6e4532708bb8fc623e2bd96` |
| `assets/README.md` | `2d632f988c2a0951a957c079ad4eeaf06ebd91170f7b506698109e5086c9d525` |
| `blender/generate_asset.py` | `2efbc32626d3fb5822e4ec5d772dcba7d9a1a3a246b1089d5f8e47b26e2d0f29` |
| `blender/reopen_export_asset.py` | `1773ab8c05b8a136cf6ac03810072afffa9bfdf2dce8ce23a1e616ae83288b33` |
| `main.tscn` | `c03bdf8a22b9dda5f1d36585c8d8eefc6dee2f1e4751342c24185a511a63092e` |
| `project.godot` | `cfed6b5cc8c0b914cd3570a5688730b0d1e3bb4bff0d182f8fec5c231d6d70af` |
| `scripts/main.gd` | `4faffe419b573ae645f62e96eef814861cf6f01976e8d7600bbb511b4ce438da` |
| `verify_blender.ps1` | `a25ed7f3eb72d23360a660bdd9beed37430bdd2bdfe79d8df33a68897cea297d` |
| `verify_slice.ps1` | `5fbaa26c3eef7c15b7869bd5ae4edeec74449bbd7299a5d14fb75ed96b4a89ea` |

## Verified commands

`verify_slice.ps1` completed with process exit `0` and no Godot process left:

- smoke: `SMOKE_PASS score=0 health=3`
- deterministic fixed-input replay: `DETERMINISTIC_PASS digest=44a33feadaa955fe738d8d0e840a141bacd85801f2a827fa71086f2c7f7fdeb9`
- save/load: `SAVE_LOAD_PASS position=(333.0, 443.0) score=75 health=2 malformed_rejected=true backup_recovered=true` (isolated test path, transactional temp/backup/rename recovery; no OS-level atomicity claim)
- gameplay contract: `GAMEPLAY_PASS platform_landed=true pickup=true pause_frozen=true runtime_advanced=true won_restart=true lost_restart=true`
- Blender authoring: `author PASS exit=0`; fresh reopen/export: `reopen_export PASS exit=0`
- Godot runtime asset instance: `ASSET_RUNTIME_PASS mesh_count=2`

The Blender script produced `pickup_original.blend` and
`pickup_original.glb` from original geometry/materials. A second fresh
`bpy` process reopened the saved `.blend`, validated the named objects and
materials, and re-exported the GLB before Godot imported it. The Godot scene
instantiates the GLB in a `SubViewport` at the pickup location; the runtime
asset test checks that scene graph and mesh count. Generated binaries, Godot
import cache and user saves are ignored and are not part of the source commit.
The portable Blender executable itself remains externally blocked by the
Windows Side-by-Side `blender.crt` activation error; the verified official
`bpy` runtime is the bounded headless route used for this run.

`verify_slice.ps1` supports `-Only` selection and a per-test timeout, captures
stdout/stderr in a temporary directory, checks actual process exit and requires
the expected postcondition marker. Missing GLB output is reported as an
incomplete external state with a nonzero exit. `verify_blender.ps1` applies the
same bounded exit checks to the author and fresh reopen/export processes.
Both wrappers quote paths for checkouts containing spaces. `verify_slice.ps1`
performs a bounded headless Godot import before runtime tests and temporarily
moves generated `.blend`/`.blend1` authoring files out of the project during
that import; a `finally` block restores them after success or failure.
Unknown `-Only` names are rejected, and comma-separated selections are
normalized before dispatch; the final targeted run verified `save_load` and
`gameplay` only, including `runtime_advanced=true` for the pause check.

The clean-checkout reproduction `gt06-vertical-slice-clean-repro-02` ran
Blender author → reopen/export and the full Godot wrapper from a temporary
checkout whose path contained spaces. Blender and Godot wrappers both exited
zero, `godot_import` exited zero, the GLB hash matched, and the generated
`.blend` source was restored. Its receipt is retained under
`zdoc/reviews/20260923-vertical-slice-clean-repro-02/`; this is Track B evidence
only and has `AUTHORITY=0`.

The frozen verification commands use the project file explicitly:

```text
powershell -ExecutionPolicy Bypass -File verify_slice.ps1 -Godot <Godot_v4.7.1-stable_win64_console.exe> -Project <vertical-slice>/project.godot
powershell -ExecutionPolicy Bypass -File verify_blender.ps1 -Python python -Project <vertical-slice>/project.godot
```
