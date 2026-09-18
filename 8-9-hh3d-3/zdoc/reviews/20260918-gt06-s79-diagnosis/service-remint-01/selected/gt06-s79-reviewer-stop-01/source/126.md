# Original fixture producer

`run_blender.py` is a trusted, background-only Blender 5.2.1 script. It generates
original geometry and pixels, saves one compressed source, reopens that exact
source with scripts disabled, reads the semantics again, and exports one GLB.
It never accepts an existing Blender file, script, export setting or asset path.
This is the new `gt05-original-fixture-v1` profile; the GT04 adapter is unchanged.

The coordinator owns the native lease, protected staging directory, process
limits, cancellation, actual exit capture and publication. The producer's root
check rejects nonabsolute/outside/nonempty/reparse paths, but is not a substitute
for the host's directory identity and ACL protection. Only the host may launch:

```text
<pinned blender.exe> --background --factory-startup --disable-autoexec --offline-mode --threads 1 --python-exit-code 17 --python <absolute producer/run_blender.py> -- <empty absolute directory under studio/.local> baseline
```

The last argument is exactly `baseline` or `edited`. Each invocation needs a
fresh empty directory; the edited variant changes crate/collider width from
0.6 m to 0.8 m. Output names are fixed:

| File | Meaning | Cap |
| --- | --- | --- |
| `fixture.blend` | Compressed source, then reopened and verified | 1 MiB |
| `fixture.glb` | Explicit pinned exporter output | 1 MiB |
| `producer-report.json` | Actual source observations and exact hashes | 1 MiB |

Only successful completion creates the report, exclusively. A partial output
directory or completion marker without the host's actual successful exit is
not evidence of success. No public ACK, admission, Godot validation or acceptance
is claimed by the producer. Root stages only independently admitted GLB bytes.

## Fixed original fixture

`contract.asset_catalog()` is the single declaration of names and roles. It has
eight assets, twelve meshes and one rig node, plus `socket_hand_r` owned by
`chr_fixture_avatar`. Blender has fourteen objects. The 1 m axis cube, three
colored positive axis arrows and asymmetric negative-Y front arrow make axis
mapping measurable. Geometry is baked with object scale `(1,1,1)`.

The avatar's twelve bones form one parent tree. Body and outfit use that same
armature modifier and actual vertex groups with one influence of weight 1 per
vertex. Skinned mesh objects remain scene roots (identity object transforms),
so validator does not warn that a parent transform is ineffective for glTF skin.
Body LOD0/1 have 576/144 triangles; outfit LOD0/1 have 288/72. Both LODs retain
the same rest bounds and shared rig identity. The entire source has 1,200
triangles, including explicit collider and nav meshes. This low-poly fixture
tests the pipeline and is not production character art.

`idle` and `walk` use original joint poses, frames 0 through 30 inclusive at
30 Hz, linear key interpolation and a stationary root. The source observations
include all 31 frames and fractional frames 7.5 and 22.5 for consumer checks at
0, 0.25, 0.5, 0.75 and 1 second. Loop semantics are explicit metadata; the Godot
consumer must configure and read back loop behavior itself.

The opaque crate uses base color, tangent-space normal and metallic/roughness
textures, each original 4x4 RGBA8 PNG. Source PNG contains only IHDR, one IDAT and
IEND, with filter zero and no color/profile/external data. All are packed into
the source with empty external paths. The only temporary paths are the three
fixed `img_fixture_{base,normal,orm}.png` basenames in the admitted staging root:
write original bytes exclusively, load with the native image decoder, pack,
clear the path and remove the exact hash-checked temporary file before saving.
Native pixel readback must match decoded source PNG; exported PNG must preserve
the exact source bytes, decoded pixels, texture bindings and sampler. Complete
independent bounded intake remains mandatory. No occlusion map is claimed.

Pinned exporter 5.2.40 emits one known sampler warning for the standard MR graph:
`material/texture.py:175` counts two socket traversals without deduplicating the
same texture node. Metallic B and roughness G use one original image node, with
identical Closest/Repeat settings. The exported postcondition verifies nearest
mag/min-mipmap-nearest and repeat S/T for all three textures. Preserve the exact
warning in evidence and explain this source-level cause; do not suppress broad
warnings or modify the pinned exporter to hide it.

The four root-level skinned meshes also produce one exact warning each at
`tree.py:253`: `Armature must be the parent of skinned meshArmature is selected by
its name, but may be false in case of instances`. Native05 has exactly four of
this warning and exactly one `More than one shader node tex image used for a
texture. The resulting glTF sampler will behave like the first shader node tex
image.` warning, with empty stderr and no other WARNING/ERROR lines. Preserve
their full text/count; future unexpected warnings are not covered by this note.

The root-level placement satisfies Khronos's skinned-mesh parent restriction.
Blender's exporter then resolves the armature by its exact name. The fixture
creates exactly one armature, no instances, and each of four skin modifiers
references that actual object. Native05 GLB has exactly one skin, four root-level
mesh references to it, all twelve exact joint names, and matching inverse binds.
An independent host readback of all 72 animation channels and 792 sampled bone
local/world poses found maximum matrix-component errors below 3.42e-7, including
the socket world pose. This is specific evidence for the original fixture's
unambiguous binding, not permission to accept the warning on arbitrary assets.

## Report schema consumed by Godot fixture staging

The full report is passed unchanged as the consumer's `input/producer-report.json`,
bound by the coordinator's receipt to the GLB and frozen source hashes. It is
not an arbitrary caller's PASS document. The consumer independently validates
the fixed catalog and required fixtures before using observations as expected
values. Unknown/missing/mismatched source and artifact pins must fail admission.
The engine hashes the complete report and reads only the small generated
`input/consumer.json`; the host comparator reads the complete observations.

Top level is `schema: HH-GT05-PRODUCER-1`, `profile_id`, `variant`, `license`,
`external_inputs: []`, `pins`, `settings`, `catalog`, `observed`,
`observed_sha256`, `source_reopened_exact`, `export_preserved_source`,
`artifacts`, `exported_images`, `proof_scope`, `formal_acceptance: false`, `public_ack: false`.
Canonical digest is UTF-8 JSON, sorted keys, compact separators, no NaN.
`artifacts` maps `fixture.blend` and `fixture.glb` to `{sha256, bytes}`.
`pins` includes exact producer/source/contract files and their hashes, executable
hash, actual Blender/Python/exporter versions, all 128 exporter files as a
canonical aggregate hash, profile/naming/toolchain/settings hashes. Installed
exporter bytes and factory addon set must match the existing frozen exporter lock.

Every transform below uses `{position:[x,y,z], rotation_xyzw:[x,y,z,w],
scale:[x,y,z]}` with finite numeric components. Object matrices are converted by
`C M C^-1`, with `C(x,y,z)=(x,z,-y)`. Pinned exporter `tree.py:326` appends `C`
to each bone world before swizzling: joint world and root-joint local therefore
use `C M`; child-joint local remains `M` in the bone's local axes. Socket object
offset in an exported joint is `M_bone_world^-1 M_socket_world C^-1`. This
distinction is mandatory; applying the object formula to bones rotates their
local axes incorrectly. Quaternions are normalized; opposite signs
represent the same rotation. The consumer compares quaternion geodesic angle,
not raw component equality. Positions and bounds use the pinned profile's
tolerances. Source mesh coordinates are meters/Z-up/-Y-front; `gltf_*` and all
clip transforms are meters/Y-up/+Z-front.

`observed` fields:

| Field | Contents |
| --- | --- |
| `meshes.<exact node>` | `asset_id`, `role`, optional `lod`, source `vertices`, `triangles`, `source_local_bounds`, `source_world_bounds`, `gltf_world_bounds`, `gltf_world_transform`, `materials`, `material_references`, `geometry_sha256`, `skinned`, `rig_owner`, `rig_name`, `influences_max`, `weight_sum_range`, `weights_sha256` |
| `rig` | `owner_asset_id`, `name`, `bones.<exact bone>` with `parent` (null for root), `rest_gltf_local`, `rest_gltf_world` |
| `shared_rigs.chr_fixture_outfit` | `{owner_asset_id:"chr_fixture_avatar", rig_name:"chr_fixture_avatar_rig"}` |
| `clips.<idle or walk>` | `fps`, `frame_start`, `frame_end`, `duration_seconds`, `loop`, `root_motion`, `events`, `samples` |
| `clips.*.samples[]` | `frame`, `time`, `bones.<name>.local`, `bones.<name>.world`, `socket_world` |
| `sockets.socket_hand_r` | `owner_asset_id`, `rig_name`, `bone:"bn_hand_r"`, `rest_gltf_world`, `rest_gltf_bone_local` |
| `materials.<exact material>` | `owner_asset_id`, effective glTF `base_color`, `metallic`, `roughness`, `alpha_mode`, `double_sided`, `normal_scale`, `texture_bindings`, `source_defaults`, `images` |
| `images.<exact image>` | `width`, `height`, `channels`, `color_space`, `packed_png_sha256`, `rgba8_sha256`, `native_pixels_sha256`, `native_pixels_max_error`, `external_path:false` |
| Other | `coordinate_spaces`, `scene_triangles`, `object_count`, `fps`, `meters_per_unit` |

Bounds are `{min:[x,y,z], max:[x,y,z]}`. Mesh bounds refer to unposed rest
geometry in fixture world, retaining both LODs. `vertices` is the actual
Blender source count; glTF may duplicate vertices at normal/UV seams. Triangle
counts, bounds and skin bindings remain the comparison contract. Material
references always contain both `{owner_asset_id, name}`; shared materials on
front/proxy meshes never imply ownership by array position.

Bone `local` and `rest_gltf_local` are absolute transforms relative to the parent
joint, including rest orientation; they are not pose deltas. `world` includes
the rig's fixture-world transform. Source socket world includes Blender's actual
bone-parent offset. An authored Godot attachment should use the recorded
`rest_gltf_bone_local` under `bn_hand_r` and compare world poses across clips.

Effective PBR factors are 1 when the corresponding Principled socket is linked;
unlinked sockets retain their actual values. `source_defaults` also preserves
the native socket defaults. Crate `texture_bindings` is exactly:

```json
{"base_color":"img_fixture_base","normal":"img_fixture_normal","metallic_roughness":"img_fixture_orm"}
```

Other materials have empty bindings. RGBA8 hash is from actual packed source
PNG decoding, excluding color-space conversion, in PNG scanline order. The
independent intake decoder and Godot consumer must observe their actual texture
pixels; discrepancies require diagnosis, not a looser hash comparison.
Top-level `exported_images` also binds actual exported PNG and RGBA8 hashes,
image byte lengths and per-semantic material texture/sampler readback. Its
`exact_source_pngs` field is set only after checking all actual embedded bytes.

## Verification boundary

Pure tests cover original topology/winding, LOD/rest bounds/rig references,
stationary looping poses, critical-only PNG round-trip and corruption rejection,
and controlled path admission. Native generation has separate evidence: pins,
main-thread checks, save/reopen exact semantic comparison, export preservation,
artifact sizes and hashes. The coordinator still needs repeated exports,
source-edit semantics, Khronos validation, independent intake, actual Godot
readback/views/animations/reimport/migration and final independent review.

The independent reusable source/GLB checker lives in
`tests/pipeline/test_producer_contract.py`, outside the producer's runtime pins.
It reads fixed native diagnostic slots with size caps, checks source snapshots,
artifact/log hashes and actual captured exit/Job cleanup, requires exactly the
five documented exporter warnings, and compares native observations with glTF
joint hierarchy, inverse binds and all 30 Hz/fractional samples. Its matrix math
does not import the producer's coordinate projection and normalizes quaternions
before comparison. Run from `studio`:

```text
python -B -c "import json; from tests.pipeline.test_producer_contract import verify_native_fixture; print(json.dumps(verify_native_fixture('.local/reviews/gt05-producer-native-05'),indent=2))"
```

Native05 direct evidence is stored at
`.local/reviews/gt05-producer-direct-check-01/`, including exact verifier source
and input snapshots. This bounded component check does not replace Godot import
or release acceptance. Tests also reject changed rest transforms, inverse bind
matrices, animation poses and socket poses in synthetic GLB records.
