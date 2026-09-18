"""Bounded core semantics for the original GT05 fixture, after byte decoding.

Call only with inspect_glb(raw) and decode_accessors(that_same_container).
Inputs/results are data, not provenance or an import authorization token.
This profile supports TRIANGLES, one joint/weight set, core attributes and
LINEAR/STEP TRS animation. Each fixture sampler spans exactly 0..1 seconds.
Unit-vector length/orthogonality and float weight-sum tolerances are 1e-4;
normalized integer weights instead require the exact raw-domain total.

Both unique mesh triangles and all node instances (including inactive scenes)
are conservatively capped at 300,000. Avatar LOD/naming budgets, topology
quality, material/images, bind-pose correctness, skeleton hierarchy semantics,
root motion, world transforms, authored pose equivalence and engine readback
remain separate checks. Missing inverse binds mean identity, as in glTF.
No filesystem, importer, engine or publication access occurs here.

https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#meshes
https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#skins
https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#animations
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType

from .accessor_values import AccessorValues, MAX_DECODED_VALUES
from .glb_container import GLBContainer

MAX_TRIANGLES = 300_000
MAX_SEMANTIC_SCALARS = 8 * MAX_DECODED_VALUES
UNIT_TOLERANCE = 1e-4
WEIGHT_TOLERANCE = 1e-4
CLIP_START_SECONDS = 0.0
CLIP_END_SECONDS = 1.0


class SemanticRejected(ValueError):
    """Stable code only; candidate names/data are never echoed."""


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise SemanticRejected(code)


@dataclass(frozen=True, slots=True)
class SemanticSummary:
    mesh_triangles: tuple[int, ...]
    total_mesh_triangles: int
    node_instance_triangles: int
    primitive_count: int
    skin_count: int
    skinned_node_count: int
    animation_durations: tuple[float, ...]


class _Work:
    def __init__(self):
        self.left = MAX_SEMANTIC_SCALARS

    def spend(self, scalars: int) -> None:
        self.left -= scalars
        _need(self.left >= 0, "SEMANTIC_WORK_LIMIT")


def _records(container: GLBContainer, records: tuple[AccessorValues, ...]) -> None:
    _need(type(container) is GLBContainer and type(container.document) is MappingProxyType and
          type(records) is tuple and len(records) == len(container.accessors), "SEMANTIC_INPUT_BINDING")
    total = 0
    for index, (layout, record) in enumerate(zip(container.accessors, records)):
        _need(type(record) is AccessorValues and record.index == index and record.kind == layout.kind and
              record.component_type == layout.component_type and record.normalized == layout.normalized and
              type(record.values) is tuple and len(record.values) == layout.count, "SEMANTIC_INPUT_BINDING")
        total += len(record.values) * len(layout.component_offsets)
        _need(total <= MAX_DECODED_VALUES, "SEMANTIC_VALUE_LIMIT")
    for layout, record in zip(container.accessors, records):
        for row in record.values:
            _need(type(row) is tuple and len(row) == len(layout.component_offsets) and
                  all(type(value) in (int, float) and -1e39 < value < 1e39 and math.isfinite(value)
                      for value in row), "SEMANTIC_VALUE_SHAPE_OR_FINITE")


def _typed(record: AccessorValues, kinds: tuple[str, ...], components: tuple[int, ...],
           *, normalized: bool = False) -> None:
    _need(record.kind in kinds and record.component_type in components and record.normalized == normalized,
          "SEMANTIC_ACCESSOR_TYPE")


def _float_or_normalized(record: AccessorValues, kinds: tuple[str, ...]) -> None:
    if record.component_type == 5126:
        _typed(record, kinds, (5126,))
    else:
        _typed(record, kinds, (5121, 5123), normalized=True)


def _unit(row: tuple, width: int) -> bool:
    return abs(math.hypot(*row[:width]) - 1.0) <= UNIT_TOLERANCE


def _meshes(document, records, work):
    """Cache repeated accessor checks while bounding paired/shared work."""
    checked = set()
    mesh_triangles, skinned_meshes = [], []
    primitive_count, total_triangles = 0, 0
    declarations = document.get("accessors", ())
    for mesh in document.get("meshes", ()):
        triangles, skin_pairs = 0, []
        for primitive in mesh["primitives"]:
            primitive_count += 1
            _need(primitive.get("mode", 4) == 4, "SEMANTIC_TRIANGLES_ONLY")
            attributes = primitive["attributes"]
            _need("POSITION" in attributes, "SEMANTIC_POSITION_REQUIRED")
            positions = records[attributes["POSITION"]]
            _typed(positions, ("VEC3",), (5126,))
            _need("min" in declarations[positions.index] and "max" in declarations[positions.index],
                  "SEMANTIC_POSITION_BOUNDS_REQUIRED")
            vertices = len(positions.values)
            for semantic, index in attributes.items():
                record = records[index]
                _need(len(record.values) == vertices, "SEMANTIC_ATTRIBUTE_COUNT")
                if (semantic, index) in checked:
                    continue
                checked.add((semantic, index))
                work.spend(len(record.values) * len(record.values[0]))
                if semantic in ("NORMAL", "TANGENT"):
                    _typed(record, ("VEC3" if semantic == "NORMAL" else "VEC4",), (5126,))
                    _need(all(_unit(row, 3) for row in record.values), "SEMANTIC_UNIT_VECTOR")
                    if semantic == "TANGENT":
                        _need(all(row[3] in (-1.0, 1.0) for row in record.values), "SEMANTIC_TANGENT_SIGN")
                elif semantic == "TEXCOORD_0":
                    _float_or_normalized(record, ("VEC2",))
                elif semantic == "COLOR_0":
                    _float_or_normalized(record, ("VEC3", "VEC4"))
                    _need(all(0 <= value <= 1 for row in record.values for value in row), "SEMANTIC_COLOR_RANGE")
                elif semantic == "JOINTS_0":
                    _typed(record, ("VEC4",), (5121, 5123))
                elif semantic == "WEIGHTS_0":
                    _float_or_normalized(record, ("VEC4",))
                    for row in record.values:
                        _need(all(0 <= value <= 1 for value in row), "SEMANTIC_WEIGHT_RANGE")
                        if record.component_type == 5126:
                            _need(abs(math.fsum(row) - 1) <= WEIGHT_TOLERANCE, "SEMANTIC_WEIGHT_SUM")
                        else:
                            divisor = 255 if record.component_type == 5121 else 65535
                            _need(sum(round(value * divisor) for value in row) == divisor, "SEMANTIC_WEIGHT_SUM")
            if "TANGENT" in attributes:
                _need("NORMAL" in attributes, "SEMANTIC_TANGENT_NEEDS_NORMAL")
                key = ("orthogonal", attributes["NORMAL"], attributes["TANGENT"])
                if key not in checked:
                    checked.add(key)
                    work.spend(vertices * 6)
                    normal, tangent = records[key[1]], records[key[2]]
                    _need(all(abs(math.fsum(a * b for a, b in zip(n, t[:3]))) <= UNIT_TOLERANCE
                              for n, t in zip(normal.values, tangent.values)), "SEMANTIC_TANGENT_ORTHOGONAL")
            if "indices" in primitive:
                indices = records[primitive["indices"]]
                _typed(indices, ("SCALAR",), (5121, 5123, 5125))
                key = ("indices", indices.index, vertices)
                if key not in checked:
                    checked.add(key)
                    work.spend(len(indices.values))
                    restart = {5121: 255, 5123: 65535, 5125: 4294967295}[indices.component_type]
                    _need(all(type(row[0]) is int and 0 <= row[0] < vertices and row[0] != restart
                              for row in indices.values), "SEMANTIC_INDEX_RANGE")
                count = len(indices.values)
            else:
                count = vertices
            _need(count >= 3 and count % 3 == 0, "SEMANTIC_TRIANGLE_COUNT")
            triangles += count // 3
            _need(("JOINTS_0" in attributes) == ("WEIGHTS_0" in attributes), "SEMANTIC_SKIN_ATTRIBUTE_PAIR")
            if "JOINTS_0" in attributes:
                pair = (attributes["JOINTS_0"], attributes["WEIGHTS_0"])
                skin_pairs.append(pair)
                key = ("joint_weights", *pair)
                if key not in checked:
                    checked.add(key)
                    work.spend(vertices * 8)
                    for joints, weights in zip(records[pair[0]].values, records[pair[1]].values):
                        active = [joint for joint, weight in zip(joints, weights) if weight > 0]
                        _need(len(active) == len(set(active)), "SEMANTIC_DUPLICATE_WEIGHTED_JOINT")
        total_triangles += triangles
        _need(total_triangles <= MAX_TRIANGLES, "SEMANTIC_TRIANGLE_LIMIT")
        mesh_triangles.append(triangles)
        skinned_meshes.append(skin_pairs)
    return tuple(mesh_triangles), skinned_meshes, primitive_count


def _skins(document, records, skin_pairs, mesh_triangles, work):
    skins = document.get("skins", ())
    for skin in skins:
        joints = skin["joints"]
        _need(joints and len(set(joints)) == len(joints), "SEMANTIC_SKIN_JOINTS")
        if "inverseBindMatrices" in skin:
            matrices = records[skin["inverseBindMatrices"]]
            _typed(matrices, ("MAT4",), (5126,))
            _need(len(matrices.values) >= len(joints), "SEMANTIC_INVERSE_BIND_COUNT")
            work.spend(len(matrices.values) * 16)
            _need(all((row[3], row[7], row[11], row[15]) == (0, 0, 0, 1) for row in matrices.values),
                  "SEMANTIC_INVERSE_BIND_AFFINE")
    checked, bound_meshes = set(), set()
    instance_triangles, skinned_nodes = 0, 0
    for node in document.get("nodes", ()):
        _need("skin" not in node or "mesh" in node, "SEMANTIC_SKIN_NEEDS_MESH")
        if "mesh" not in node:
            continue
        mesh_index = node["mesh"]
        instance_triangles += mesh_triangles[mesh_index]
        _need(instance_triangles <= MAX_TRIANGLES, "SEMANTIC_INSTANCE_TRIANGLE_LIMIT")
        pairs = skin_pairs[mesh_index]
        if "skin" not in node:
            _need(not pairs, "SEMANTIC_SKIN_ATTRIBUTES_WITHOUT_BINDING")
            continue
        skinned_nodes += 1
        bound_meshes.add(mesh_index)
        _need(len(pairs) == len(document["meshes"][mesh_index]["primitives"]), "SEMANTIC_SKIN_ATTRIBUTES_REQUIRED")
        joint_count = len(skins[node["skin"]]["joints"])
        for joint_index, _ in pairs:
            key = (joint_index, joint_count)
            if key not in checked:
                checked.add(key)
                work.spend(len(records[joint_index].values) * 4)
                _need(all(type(joint) is int and 0 <= joint < joint_count
                          for row in records[joint_index].values for joint in row), "SEMANTIC_JOINT_RANGE")
    _need(all(not pairs or index in bound_meshes for index, pairs in enumerate(skin_pairs)),
          "SEMANTIC_SKIN_ATTRIBUTES_WITHOUT_BINDING")
    return instance_triangles, skinned_nodes


def _animations(document, records, work):
    durations, checked = [], set()
    declarations = document.get("accessors", ())
    for animation in document.get("animations", ()):
        for sampler in animation["samplers"]:
            _need(sampler.get("interpolation", "LINEAR") in ("LINEAR", "STEP"), "SEMANTIC_ANIMATION_INTERPOLATION")
            times, output = records[sampler["input"]], records[sampler["output"]]
            _typed(times, ("SCALAR",), (5126,))
            _need("min" in declarations[times.index] and "max" in declarations[times.index],
                  "SEMANTIC_TIME_BOUNDS_REQUIRED")
            _need(len(times.values) == len(output.values), "SEMANTIC_ANIMATION_COUNT")
            if times.index not in checked:
                checked.add(times.index)
                work.spend(len(times.values))
                _need(times.values[0][0] == CLIP_START_SECONDS and times.values[-1][0] == CLIP_END_SECONDS,
                      "SEMANTIC_FIXTURE_CLIP_RANGE")
                _need(all(b[0] > a[0] for a, b in zip(times.values, times.values[1:])), "SEMANTIC_TIME_ORDER")
        targets = set()
        for channel in animation["channels"]:
            target = channel["target"]
            key = (target["node"], target["path"])
            _need(key not in targets, "SEMANTIC_DUPLICATE_ANIMATION_TARGET")
            targets.add(key)
            _need("matrix" not in document["nodes"][target["node"]], "SEMANTIC_ANIMATED_MATRIX")
            output = records[animation["samplers"][channel["sampler"]]["output"]]
            if target["path"] == "rotation":
                _typed(output, ("VEC4",), (5126,))
                rotation_key = ("rotation", output.index)
                if rotation_key not in checked:
                    checked.add(rotation_key)
                    work.spend(len(output.values) * 4)
                    _need(all(_unit(row, 4) for row in output.values), "SEMANTIC_UNIT_ROTATION")
            else:
                _typed(output, ("VEC3",), (5126,))
        durations.append(CLIP_END_SECONDS - CLIP_START_SECONDS)
    return tuple(durations)


def validate_semantics(container: GLBContainer, decoded_accessors: tuple[AccessorValues, ...]) -> SemanticSummary:
    """Check this documented fixture subset, without granting engine admission."""
    _records(container, decoded_accessors)
    document, work = container.document, _Work()
    triangles, pairs, primitives = _meshes(document, decoded_accessors, work)
    instances, skinned = _skins(document, decoded_accessors, pairs, triangles, work)
    durations = _animations(document, decoded_accessors, work)
    return SemanticSummary(triangles, sum(triangles), instances, primitives,
                           len(document.get("skins", ())), skinned, durations)
