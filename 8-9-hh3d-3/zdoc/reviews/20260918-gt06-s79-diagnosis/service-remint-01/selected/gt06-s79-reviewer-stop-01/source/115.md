# GT05 fixed Godot consumer

Implementation candidate. Captured native diagnostics have checked 12 meshes,
12 bones, 792 sampled poses, 2,160 skin vertices and two clips. Same-project
reimport preserves the authored script, material override and socket while
reading back the intended crate-width edit. Each diagnostic remains bound to
its own source map; it is not final GT05 acceptance. The current visual revision
still needs new native capture. This is a fixed pipeline profile; accepted GT03
scene grammar and GT04 adapter contracts remain unchanged.

The coordinator owns the private staging directory, complete input admission,
source freeze, process caps/ownership, actual exits, diagnostics and final proof.
This module starts no process and grants no public write or publication right.
Run complete GLB binary/PNG/Khronos checks before staging or importing a candidate.
The consumer repeats only bounded GLB container and fixed-name checks.

## Integration API and fixed files

Import `studio.pipeline.godot.consumer` with the HH3D-3 directory on `sys.path`.
Call `prepare(new_project, glb=..., manifest=..., producer_report=...)` with exact
already admitted bytes. The output directory must not exist. It creates:

- Fixed authored sources: `project.godot`, `authored.tscn`, `authored.gd`,
  `authored_material.tres`, `probe.gd`.
- Fixed input slots: `input/fixture.glb`, `input/manifest.json`, and the full
  unchanged native `input/producer-report.json`.
- `input/consumer.json`: small fixed-catalog projection, input/source/profile/
  naming/toolchain hashes and the source socket's local offset.
- `input/fixture.glb.import`: explicit initial import preset.
- Empty `out/` for new readback and optional rendered evidence.

The producer's `contract.asset_catalog()` and `producer-report.json.observed`
are the single source of expected identities and native source values. The
consumer validates required fixture membership; a caller-provided PASS flag is
never consumed. The GLB digest is checked against its producer artifact row;
the manifest is preserved and hash-bound, not treated as authority to fetch or
open a path. Root must validate its semantic/source/license bindings upstream.

`command(binary, project, phase)` returns the fixed argument vector. The root
runner pins the GUI executable directly to `toolchain.lock.json`, places the command
under the existing owned Job and environment isolation, and executes one engine
stage at a time. Equivalent commands are:

```text
<pinned Godot GUI binary> --headless --editor --path <private project> --import
<pinned Godot GUI binary> --headless --path <private project> --script res://probe.gd -- --phase baseline
```

The first command must complete import successfully before the second starts.
The Windows console wrapper launches another PID; direct engine launch makes
the captured target PID match `OS.get_process_id()` in the native observation.
Use a new evidence directory for each host launch. Successful native observation
writes only `out/baseline.json` and one `GT05_GODOT_OBSERVED` marker containing
phase, native PID and exact report hash. Existing report files are rejected.
Process exit zero or the marker alone is insufficient. After checking actual
target/wrapper exits, clean owned trees and diagnostics, call:

```python
observed = consumer.verify_binding(project, phase="baseline", stdout=raw_stdout)
comparison = consumer.compare_observation(producer_report_dict, observed)
```

The result contains checked counts and `formal_acceptance=False`, not a public
ACK. Root must additionally bind marker PID to the launched native target and
include these scripts and producer/validator dependencies in its frozen closure.

## Native observations

The typed probe observes imported content before applying authored overrides.
It requires exact unique mesh names and resolves each skin's actual Skeleton3D
through its MeshInstance3D skeleton reference. It records world bounds, triangle
counts, vertices/weights, material names/factors/channels, decoded RGBA8 image
hashes, named skin binds, bone parents/rest transforms, and idle/walk poses at
all 31 frames from 0 through 1 second at 30 Hz plus 0.25 and 0.75 second. Source vertex counts are not equated with imported
counts because normal/UV seams may split vertices. The four character meshes'
actual per-position bone weights are checked against original fixture geometry.
Each named inverse bind is also compared to the inverse of the producer's
glTF joint-world rest transform. This relies on this fixture's verified identity
mesh/rig object transforms and unit joint scales. The pinned importer copies
glTF inverse bind matrices into [Godot's named Skin binds](https://github.com/godotengine/godot/blob/4.7.2-stable/modules/gltf/gltf_document.cpp#L3229).
This does not claim general bind-shape transforms or GPU deformation parity.

Position comparison is Euclidean within 1 mm; bounds are componentwise within
1 mm; scales and factors within 1e-4; rotation uses normalized quaternion
geodesic angle within 0.1 degrees, treating opposite quaternion signs equally.
Names, role identities and hashes remain exact. Bone renames/deletes are rejected
as migration requirements; no guessed remapping or array-index identity exists.
Godot +Y-up/+Z model front follows the declared interchange convention and does
not define a gameplay controller's forward direction.

The wrapper explicitly constructs collider and navigation objects from declared
proxy meshes, hides those render proxies, switches both character LOD pairs,
and attaches an authored marker to `bn_hand_r` with the observed socket offset.
Nonpaired props remain visible at either character LOD. Collider evidence includes
an actual physics ray hit. Navigation evidence is constructed mesh/region
readback, not a claimed pathfinding gameplay test. Both imported and authored
socket world poses are compared during the clip samples.

The three embedded PNGs are decoded to RGBA8 by Godot, with dimensions and a
total decode budget checked first. Mipmaps are excluded from pixel hashes.
Exact source pixels and metallic/roughness channel mapping are checked against
the producer's observations. This complements, and does not replace, upstream
bounded decoding before engine import.

## Import policy, reimport and visuals

The preset disables both node-type/name suffix options, automatic LOD generation
and mesh compression; uses named skins, 30 Hz animation, no trimming or immutable
track removal; explicitly disables animation optimization and compression on
`PATH:AnimationPlayer`; explicitly sets idle/walk looping; embeds uncompressed textures;
and sets the texture-map mode explicitly. The probe reads back suffix settings
and rejects unexpected importer-generated physics/navigation nodes. Options
were checked against the pinned [Godot 4.7.2 scene importer source](https://github.com/godotengine/godot/blob/4.7.2-stable/editor/import/3d/resource_importer_scene.cpp)
and [glTF importer source](https://github.com/godotengine/godot/blob/4.7.2-stable/modules/gltf/editor/editor_scene_importer_gltf.cpp).
The default animation optimizer is enabled in the pinned importer, and the first
diagnostic exceeded the 0.1-degree bone-world threshold at two half-frame samples.
The revised probe requires 36 named bone tracks per clip, 31 key times per track,
linear interpolation and no compressed tracks. These settings were read back in
the captured native baseline and reimport diagnostics. Compact observation JSON has an explicit 1 MiB cap;
clip rows omit duplicate rest transforms to leave room for the full sample grid.

For the same-project reimport proof, retain an immutable copy of the baseline
input/evidence outside this staged project, stop the engine, then call
`replace_inputs(project, glb=edited_bytes, manifest=..., producer_report=...)`.
It refuses a missing/mismatched baseline or changed authored source and replaces
only the three fixed input files and their consumer binding. It preserves the
Godot import metadata/cache, authored scene/script/material and baseline report.
This isolated fixture update is not an atomic active-release publication API.
Run import again, then probe phase `reimport`, and both Python checks again.
Verification requires changed GLB bytes and exact preserved authored hashes,
script marker, material override and attachment behavior. Root separately checks
the intended crate-width delta, not merely any changed binary hash.

The optional phase `visual` requires a real rendering display. Its ready argv is
the same fixed probe invocation without `--headless`, ending `--phase visual`.
It writes six orthographic views plus 31 frames at 30 Hz for each idle/walk clip,
all fixed names under `out/`, and binds hashes, dimensions, native PID and frame
number in `out/visual.json`. `verify_binding` requires all 68 exact image files.
These files still need visual review and runtime evidence; source code alone
does not establish appearance, usable animation or performance.

Imported material albedo RGB is converted from Godot's sRGB storage back to
linear glTF factor space before applying the existing 1e-4 tolerance. Alpha is
unchanged. The pinned importer explicitly calls [linear_to_srgb for baseColorFactor](https://github.com/godotengine/godot/blob/4.7.2-stable/modules/gltf/gltf_document.cpp#L2880),
and the inverse uses [Godot's piecewise color transfer](https://github.com/godotengine/godot/blob/4.7.2-stable/core/math/color.h#L177).
Authored override colors remain compared in their directly authored Godot space;
decoded PNG samples are never passed through this factor conversion.

Pure check command from repository root:

```text
python -B -m unittest discover -s 8-9-hh3d-3/studio/tests/pipeline -p test_godot_import_contract.py -v
```

No staging/commit, native run, tick, final acceptance, cross-app activation,
Android or HH World behavior is claimed by this implementation lane.
