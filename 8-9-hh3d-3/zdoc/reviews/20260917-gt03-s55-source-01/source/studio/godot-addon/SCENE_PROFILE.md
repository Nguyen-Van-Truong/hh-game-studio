# Managed scene eligibility

`scene_profile.py` implements candidate profile `hh-godot-managed-scene-1` for
the fixed `scenes/fixture.tscn` graph. It validates complete original bytes and
returns immutable comparison metadata. It never calls Godot, loads resources,
rewrites source, authorizes operations or issues an ACK. Eligibility is not
parse/import, instance readback, publication proof or full GT-03 acceptance.

## API

`validate_scene(raw: bytes, *, script_uid: bytes, script_source: bytes)` returns
a frozen/slotted `ValidatedSceneProfile`. Direct dataclass construction also
validates; derived fields cannot be supplied to its constructor.

- `source_bytes`, `script_uid_bytes`, `script_source`: exact original bytes.
- `sha256`, `script_uid_sha256`, `script_sha256`: lowercase SHA256 without a
  prefix, computed from the corresponding original bytes.
- `scene_uid`: explicitly declared scene UID, or `None`.
- `script_uid`: canonical UID from the sidecar; `script_uid_declared` indicates
  whether the external-resource section explicitly contains it.
- `external_script_id`: local text ID of the single fixed Script reference.
- `nodes`: ordered tuple of frozen `SceneNode` values; `resources`: ordered
  tuple of frozen `BoxResource` values.
- `snapshot()`: detached dictionaries/lists for native comparison. Mutating a
  snapshot does not mutate the result.

Each node records name, native type, scene-relative path (`.` for root), parent
path/stable ID, owner stable ID, sibling index, optional declared `unique_id`,
effective `transform_rows_origin`, column-length `scale`, optional mesh ID and
BoxMesh size, effective typed `export_values`, and separate
`declared_properties`. A `SceneProperty` contains `name`, `kind` and immutable
scalar/tuple `value`; snapshot properties map names to `{kind, value}`. Resource
metadata includes its local ID, native type, effective size and declared fields.

The effective transform defaults to identity; absent BoxMesh `size` defaults
to `(1, 1, 1)`; absent exported overrides use the approved script declarations.
The root owner is empty; every child owner is `root`. Omitted UID/unique-ID
attributes are not invented. Native generated IDs must be handled separately
from source-declared IDs. A float export written as `move_speed = 7` has an
`int` declared SceneState value but a `float` effective instance value; both
are represented. A default or instance value is not a claim that an engine
has actually been observed.

Import binds the exact sibling `script_profile.py` SHA256
`0aff8d103982e56280b04ad4faca93cf3bd96d086016818daf7b3a432b4de7a5` before executing
those same bytes. Its module cache key includes resolved path and bytes, so a
different snapshot cannot accidentally reuse the previous snapshot's module.
Only this approved dependency is read at import. Subsequent validation is pure;
input never supplies a filesystem path. Script-profile rejection propagates
with its original code. Python immutability/source binding is not isolation
against malicious code already executing inside the host process.

## Closed accepted grammar

Input is exact `bytes`, valid UTF-8, at most 1 MiB. The accepted text is ASCII,
LF only, one final LF, one empty separator line between sections, no empty
lines inside a section, and at most 4096 bytes per line. No comment, escaped
string, BOM, NUL, arbitrary quoted text, expression or general Variant syntax
is parsed. Header/property spacing and attribute order must match these forms:

```text
[gd_scene load_steps=3 format=3 uid="uid://b"]

[ext_resource type="Script" uid="uid://dc8011bj471fi" path="res://scripts/fixture_actor.gd" id="1_script"]

[sub_resource type="BoxMesh" id="BoxMesh_one"]
size = Vector3(1, 1, 1)

[node name="Fixture" type="Node3D" unique_id=1]
script = ExtResource("1_script")
fixture_value = 23
metadata/hh_studio_id = "root"

[node name="Box" type="MeshInstance3D" parent="." unique_id=2]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 4, 5, 6)
mesh = SubResource("BoxMesh_one")
metadata/hh_studio_id = "box"
```

Scene `load_steps` and scene UID are optional. If present, `load_steps` must
equal all declared external/internal resources plus one. External Script UID
is optional, but must equal the supplied sidecar exactly when present. The
sidecar itself is mandatory, at most 128 bytes, and exactly canonical UID text
plus LF. Godot's UID alphabet is **a–y and 0–8**, base 34, at most 13 digits,
with no leading zero digit `a` except the single-digit zero spelling; values
must fit 63 nonnegative bits. Scene/script UIDs cannot collide. This rejects
Godot's permissive alternate/overflow spellings instead of resolving aliases.
[Pinned UID implementation](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/io/resource_uid.cpp#L38).

The first resource is exactly the fixed external Script, attached exactly once
to the root. The script's original bytes must pass `hh-godot-declarative-1`.
There may then be at most 63 internal BoxMesh resources, followed by nodes.
Resource IDs use 1–64 ASCII letters/digits/underscores and must be unique across
both resource kinds. Every BoxMesh is used by exactly one MeshInstance3D;
missing, duplicate, shared, unused and externally loaded meshes are rejected.
Only its optional `size = Vector3(...)` property is accepted.

There are 1–64 nodes, root-inclusive depth at most 16, in depth-first order.
The root is an explicit Node3D with no parent/owner attribute. Other nodes are
Node3D or MeshInstance3D, with an earlier existing relative parent. Child
`owner="."` is optionally accepted before `unique_id`; every child otherwise
implicitly belongs to the root, matching the pinned loader.
[Pinned parent/owner handling](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/resources/resource_format_text.cpp#L188).

Names follow `[A-Za-z][A-Za-z0-9_]{0,47}`; sibling names are unique ignoring
ASCII case. Parent paths are `.` or slash-separated approved names without
traversal, prefixes or escapes. Stable metadata IDs follow
`[a-z][a-z0-9._-]{0,63}`, are unique, and `root` identifies only the root.
Optional node `unique_id` values are unique decimal integers 1–2147483647.

Node fields are only `transform`, `metadata/hh_studio_id`, the root's `script`
and explicitly declared script exports, and MeshInstance3D's required `mesh`.
The script assignment must precede root export overrides. Each field appears
once. Root overrides obey the corresponding approved name/type/range and may
not introduce a declaration. Unknown fields/sections, groups, connections,
instances, inheritance, custom types, embedded scripts, material/resources,
arbitrary paths, `visible`, standalone `position`/`rotation`/`scale`, and other
properties not exposed by the catalog are unsupported.

## Numeric and transform semantics

Scene scalar grammar is a signed ASCII decimal integer part without leading
zeros, an optional dot plus digits, and optional lowercase `e`, optional sign
and 1–3 exponent digits. It accepts forms such as `1`, `1.0`, `4.37114e-08`,
`1e+2` and signed zero; literals are at most 64 characters. It rejects NaN/INF,
hex, underscores, expressions, leading plus, and missing integer/fractional
digits. Source bytes are never normalized. Integer exports additionally use
the script profile's canonical integer spelling; boolean exports are only
`true`/`false`. Float exports use the scene grammar and remain binary64.

Decimal bounds are checked before conversion, so a rounded out-of-range
literal cannot enter. Nonzero underflow and nonfinite representations are
rejected. Vector3/Transform3D components are rounded to binary32 for the stock
engine's `real_t`; vectors/constructors have exact arity and comma-space
separators. Box size is 0.001–1000 per component; translation is
-10000–10000. The serialized Transform3D's first nine components are basis
**rows**, followed by origin xyz, as the pinned writer/parser implements.
[Pinned Variant serialization](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/variant/variant_parser.cpp#L1993).

Each basis component is within -1000–1000, its column lengths must be within
0.001–1000, and its determinant must be positive. Normalized pairwise column
dot products may differ from zero by at most `2e-6` to accommodate serialized
binary32 rotations. This excludes reflection, singularity and material shear.
The range bounds are not expanded by that orthogonality tolerance. Benign
rotations exactly at a scale boundary whose serialization moves a reconstructed
length outside the range are currently unsupported availability, not clamped.
Every proper orthogonal rotation has an Euler representative inside the
catalog's angle bounds; original authored Euler winding is not recoverable
from serialized basis alone. Compare effective matrices rather than claiming
to recover the original command arguments.

## Rejection and remaining proof

`SceneProfileError.code` is `BAD_SCENE_BYTES` for a bad scene byte envelope or
UTF-8, `BAD_SCRIPT_UID_BYTES` for a bad sidecar byte envelope/UTF-8, and
`UNSUPPORTED_SCENE_PROFILE` for all scene/UID eligibility violations. Messages
do not reflect candidate source. Broader benign Godot formatting/serialization
is intentionally unsupported; there is no fallback to a general parser.

Tests are pure: `python -B studio/tests/godot/test_scene_profile.py` from
`8-9-hh3d-3/`. A complete trusted owner must still bind project/configuration,
all UID/source dependencies, approved addon/bootstrap and exact engine; run
real sandbox parse/import and fresh native SceneState plus instance readback;
compare hashes, UID, hierarchy, fields and typed effective values; and enforce
containment, complete streams, Stop/deadline and durable publication. Native
comparison epsilon is a separately documented engine-readback rule, not a
permission to omit postconditions. This module closes only the eligible scene
and script graph; it does not close the complete project or issue COMMITTED.
