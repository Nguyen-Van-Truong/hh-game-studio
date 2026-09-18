# Asset naming convention v1

Preparation under plan section 8.1; GT05 integration and acceptance remain gated
on GT04. This contract adds no public command or arbitrary-file intake. The
numeric fixture contract is `tests/asset-profile.json`, fixed before the GT05
engine runs. Changes need a reviewed diff and a fresh affected fixture run.

## Names and identity

Names are lowercase ASCII, at most 64 characters. Words use single underscores;
no whitespace, dot, slash, colon, Unicode lookalikes or implicit normalization.
The first character of an identifier is a letter. Identity is the exact string,
never a case-folded filename, display label or array position.

An `asset_id` is at most 55 characters (reserving the 9-character `_collider`
suffix within the node limit). It has class prefix `chr_`, `prp_`, `env_` or `ui_`, followed by a
nonempty identifier. Class is respectively `character`, `prop`, `environment`
or `ui`. Examples: `chr_fixture_avatar`, `chr_fixture_outfit`,
`prp_fixture_crate`, `env_fixture_axis_cube`. IDs ending in `_lod` plus digits,
`_collider`, `_nav` or `_rig` are reserved and rejected. These are tool asset
IDs; game catalog/economy IDs are defined by the game plan and refer to them.

Node names are bound to their owning asset ID and explicit manifest role:

| Role | Exact name | LOD field |
| --- | --- | --- |
| render | `<asset_id>_lod0` or `<asset_id>_lod1` | integer 0 or 1 |
| collider | `<asset_id>_collider` | absent |
| nav | `<asset_id>_nav` | absent |
| rig | `<asset_id>_rig` | absent |

The manifest role is mandatory; suffixes alone never create physics, navigation
or LOD behavior. The staged Godot consumer must explicitly build and read back
these roles. Automatic import renaming, suffix stripping or guessed node lookup
is not a migration policy.

The future Godot import preset must disable `nodes/use_node_type_suffixes` and
`nodes/use_name_suffixes`, then verify unchanged names in the pinned importer.
Set and read back `idle`/`walk` loop flags explicitly. These are import proof
requirements, not behavior established by this data-only linter.

Bone names use `bn_<identifier>` (examples `bn_root`, `bn_pelvis`, `bn_hand_l`).
Socket names use `socket_<identifier>` (`socket_hand_r`). Material names use
`mat_<identifier>` (`mat_fixture_cloth`). Initial locomotion clip names are
exactly `idle` and `walk`. Names are unique in each typed namespace of an asset;
node names are unique within an asset, and asset IDs across the catalog. Shared
rig/material references must specify their owning asset ID plus exact name.

Deleting/renaming an asset, bone, socket, clip or material is a schema migration:
report affected consumers, map old to new explicitly, validate and read back in
a staged import. Missing/ambiguous names preserve the last good release. Never
repair names silently in the exporter.

## Geometry and semantic comparisons

Blender source uses meters, Z-up and asset front -Y. Exported glTF/Godot assets
use meters, Y-up and asset front +Z: positions map `(x, y, z)` to `(x, z, -y)`.
This model-front convention is separate from camera/controller forward; no
implicit 180-degree correction is allowed. This agrees with the
[glTF coordinate convention](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#coordinate-system-and-units).

Position error is Euclidean distance; bounds/scale use componentwise absolute
error. Rotation error is the shortest quaternion geodesic angle, with `q` and
`-q` equivalent, after validating finite unit quaternions. Clip time tolerance
is one sample at 30 Hz. Semantic comparisons report deltas against the profile;
epsilon does not define hash equality. SHA-256 always pins exact artifact bytes.

LOD bodies/outfits retain the same rig identity and attachment mapping. Render
mesh budgets exclude dedicated collider/nav meshes; the total scene budget
includes everything rendered. Material/image/rig/clip support requires a new
GT05 producer profile: GT04's box/material profile remains unchanged.

Initial generated fixtures must fit the existing protected store's 1 MiB per
blob limit; source and output each undergo capacity admission. The triangle and
decoded texture budgets are upper bounds, not a promise to publish every asset
below those counts. Larger storage needs a separately reviewed profile; do not
raise shared GT02 limits to make a fixture pass.

## Admission and verification scope

`pipeline/naming.py` performs data-only naming checks. It does not parse GLB,
read files, decode images, verify licenses, validate geometry or authorize
publication. A syntactically valid empty catalog proves no required fixture.

The initial GLB profile uses embedded PNG bufferViews and no URI or extension.
Later intake checks must reject undeclared/unsupported extensions throughout the
document, cap image dimensions and total decoded memory before decoding, and
run bounded actual decoding. Header checks alone cannot prove a valid PNG.
Khronos validation plus bounded Godot import/readback remain mandatory; neither
names nor a successful glTF validator report alone prove the complete pipeline.

Fixture assertions and code reviews must use exact profile/contract hashes.
Original asset source/license records, authored Godot consumer code and engine
versions belong to the eventual GT05 source closure.
