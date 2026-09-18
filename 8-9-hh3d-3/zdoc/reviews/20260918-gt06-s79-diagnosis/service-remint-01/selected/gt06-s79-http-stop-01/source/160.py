"""Tiny actual GLB data exercises the layered semantic fixture profile."""
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from pipeline.accessor_values import decode_accessors
from pipeline.glb_container import inspect_glb
from pipeline import glb_semantics as semantics

IDENTITY = tuple(float(index % 5 == 0) for index in range(16))


class Fixture:
    def __init__(self):
        self.binary = bytearray()
        self.document = {"asset": {"version": "2.0"}, "buffers": [], "bufferViews": [], "accessors": []}
        self.ids = {}

    def add(self, label, rows, kind, component=5126, *, bounds=False, normalized=False):
        self.binary.extend(b"\0" * (-len(self.binary) % 4))
        format_ = {5121: "B", 5123: "H", 5125: "I", 5126: "f"}[component]
        values = tuple(value for row in rows for value in row)
        data = struct.pack("<" + format_ * len(values), *values)
        view = {"buffer": 0, "byteOffset": len(self.binary), "byteLength": len(data)}
        self.document["bufferViews"].append(view)
        self.binary.extend(data)
        index = len(self.document["accessors"])
        accessor = {"bufferView": index, "componentType": component, "count": len(rows), "type": kind}
        if normalized:
            accessor["normalized"] = True
        if bounds:
            accessor["min"] = [min(row[axis] for row in rows) for axis in range(len(rows[0]))]
            accessor["max"] = [max(row[axis] for row in rows) for axis in range(len(rows[0]))]
        self.document["accessors"].append(accessor)
        self.ids[label] = index
        return index

    def triangle(self, *, indexed=True, indices=(0, 1, 2), normals=None, tangents=None):
        attributes = {"POSITION": self.add("position", ((0, 0, 0), (1, 0, 0), (0, 1, 0)), "VEC3", bounds=True),
                      "NORMAL": self.add("normal", ((0, 0, 1),) * 3 if normals is None else normals, "VEC3"),
                      "TANGENT": self.add("tangent", ((1, 0, 0, 1),) * 3 if tangents is None else tangents, "VEC4")}
        primitive = {"attributes": attributes}
        if indexed:
            primitive["indices"] = self.add("indices", tuple((index,) for index in indices), "SCALAR", 5123)
        self.document["meshes"] = [{"primitives": [primitive]}]
        self.document["nodes"] = [{"mesh": 0}]
        return self

    def skin(self, *, joints=None, weights=None, weight_component=5126, matrices=None):
        self.document["nodes"] = [{"children": [1]}, {}, {"mesh": 0, "skin": 0}]
        attributes = self.document["meshes"][0]["primitives"][0]["attributes"]
        attributes["JOINTS_0"] = self.add("joints", ((0, 1, 0, 0),) * 3 if joints is None else joints, "VEC4", 5123)
        attributes["WEIGHTS_0"] = self.add("weights", ((0.75, 0.25, 0, 0),) * 3 if weights is None else weights,
                                            "VEC4", weight_component, normalized=weight_component != 5126)
        inverse = self.add("inverse", (IDENTITY, IDENTITY) if matrices is None else matrices, "MAT4")
        self.document["skins"] = [{"joints": [0, 1], "skeleton": 0, "inverseBindMatrices": inverse}]
        return self

    def animation(self, *, times=(0, 0.5, 1), output=None, path="rotation", interpolation="LINEAR"):
        time = self.add("times", tuple((time,) for time in times), "SCALAR", bounds=True)
        values = ((0, 0, 0, 1),) * len(times) if output is None else output
        result = self.add("animation", values, "VEC4" if len(values[0]) == 4 else "VEC3")
        self.document["animations"] = [{"samplers": [{"input": time, "output": result, "interpolation": interpolation}],
                                         "channels": [{"sampler": 0, "target": {"node": 0, "path": path}}]}]
        return self

    def admit(self):
        self.document["buffers"] = [{"byteLength": len(self.binary)}]
        text = json.dumps(self.document, separators=(",", ":")).encode()
        text += b" " * (-len(text) % 4)
        binary = bytes(self.binary) + b"\0" * (-len(self.binary) % 4)
        chunks = struct.pack("<II", len(text), 0x4E4F534A) + text + struct.pack("<II", len(binary), 0x004E4942) + binary
        admitted = inspect_glb(struct.pack("<4sII", b"glTF", 2, len(chunks) + 12) + chunks)
        return admitted, decode_accessors(admitted)

    def check(self):
        return semantics.validate_semantics(*self.admit())


class SemanticTests(unittest.TestCase):
    def rejects(self, fixture, code):
        with self.assertRaises(semantics.SemanticRejected) as caught:
            fixture.check()
        self.assertEqual(str(caught.exception), code)

    def test_full_tiny_rig_and_clip_summary_is_immutable_without_io(self):
        admitted, decoded = Fixture().triangle().skin().animation().admit()
        with patch("builtins.open", side_effect=AssertionError("no I/O")):
            result = semantics.validate_semantics(admitted, decoded)
        self.assertEqual(result.mesh_triangles, (1,))
        self.assertEqual((result.total_mesh_triangles, result.node_instance_triangles, result.primitive_count), (1, 1, 1))
        self.assertEqual((result.skin_count, result.skinned_node_count, result.animation_durations), (1, 1, (1.0,)))
        with self.assertRaises(FrozenInstanceError):
            result.skin_count = 10

    def test_indexed_and_unindexed_triangle_counts(self):
        self.assertEqual(Fixture().triangle(indexed=False).check().total_mesh_triangles, 1)
        self.rejects(Fixture().triangle(indices=(0, 1, 3)), "SEMANTIC_INDEX_RANGE")
        self.rejects(Fixture().triangle(indices=(0, 1)), "SEMANTIC_TRIANGLE_COUNT")
        fixture = Fixture().triangle()
        fixture.document["meshes"][0]["primitives"][0]["mode"] = 5
        self.rejects(fixture, "SEMANTIC_TRIANGLES_ONLY")

    def test_triangle_limits_count_meshes_and_every_node_instance(self):
        profile = json.loads((Path(__file__).resolve().parents[1] / "asset-profile.json").read_bytes())
        self.assertEqual(semantics.MAX_TRIANGLES, profile["limits"]["fixture_scene_triangles"])
        fixture = Fixture().triangle()
        fixture.document["nodes"] *= 2
        with patch.object(semantics, "MAX_TRIANGLES", 1):
            self.rejects(fixture, "SEMANTIC_INSTANCE_TRIANGLE_LIMIT")
        fixture = Fixture().triangle()
        fixture.document["meshes"] *= 2
        with patch.object(semantics, "MAX_TRIANGLES", 1):
            self.rejects(fixture, "SEMANTIC_TRIANGLE_LIMIT")

    def test_position_required_bounds_and_attribute_counts(self):
        fixture = Fixture().triangle()
        del fixture.document["meshes"][0]["primitives"][0]["attributes"]["POSITION"]
        self.rejects(fixture, "SEMANTIC_POSITION_REQUIRED")
        fixture = Fixture().triangle()
        del fixture.document["accessors"][fixture.ids["position"]]["min"]
        self.rejects(fixture, "SEMANTIC_POSITION_BOUNDS_REQUIRED")
        self.rejects(Fixture().triangle(normals=((0, 0, 1),) * 2), "SEMANTIC_ATTRIBUTE_COUNT")

    def test_unit_normals_tangent_sign_and_orthogonality(self):
        self.rejects(Fixture().triangle(normals=((0, 0, 0),) * 3), "SEMANTIC_UNIT_VECTOR")
        self.rejects(Fixture().triangle(normals=((0, 0, 1.01),) * 3), "SEMANTIC_UNIT_VECTOR")
        Fixture().triangle(normals=((0, 0, 1.00005),) * 3).check()
        self.rejects(Fixture().triangle(tangents=((1, 0, 0, 0),) * 3), "SEMANTIC_TANGENT_SIGN")
        self.rejects(Fixture().triangle(tangents=((0, 0, 1, 1),) * 3), "SEMANTIC_TANGENT_ORTHOGONAL")
        fixture = Fixture().triangle()
        del fixture.document["meshes"][0]["primitives"][0]["attributes"]["NORMAL"]
        self.rejects(fixture, "SEMANTIC_TANGENT_NEEDS_NORMAL")

    def test_core_uv_tiling_and_color_range(self):
        fixture = Fixture().triangle()
        attributes = fixture.document["meshes"][0]["primitives"][0]["attributes"]
        attributes["TEXCOORD_0"] = fixture.add("uv", ((-1, 2),) * 3, "VEC2")
        attributes["COLOR_0"] = fixture.add("color", ((0.25, 0.5, 1),) * 3, "VEC3")
        fixture.check()
        attributes["COLOR_0"] = fixture.add("bad_color", ((0, 0, 1.01),) * 3, "VEC3")
        self.rejects(fixture, "SEMANTIC_COLOR_RANGE")

    def test_weights_float_sum_range_duplicate_joint_and_integer_exact_sum(self):
        self.rejects(Fixture().triangle().skin(weights=((0.75, 0.3, 0, 0),) * 3), "SEMANTIC_WEIGHT_SUM")
        self.rejects(Fixture().triangle().skin(weights=((1, -0.1, 0.1, 0),) * 3), "SEMANTIC_WEIGHT_RANGE")
        self.rejects(Fixture().triangle().skin(joints=((0, 0, 0, 0),) * 3), "SEMANTIC_DUPLICATE_WEIGHTED_JOINT")
        Fixture().triangle().skin(weights=((255, 0, 0, 0),) * 3, weight_component=5121).check()
        self.rejects(Fixture().triangle().skin(weights=((65534, 0, 0, 0),) * 3, weight_component=5123),
                     "SEMANTIC_WEIGHT_SUM")

    def test_joint_range_including_zero_weight_slots_and_reused_mesh_skins(self):
        self.rejects(Fixture().triangle().skin(joints=((0, 1, 2, 0),) * 3), "SEMANTIC_JOINT_RANGE")
        fixture = Fixture().triangle().skin()
        fixture.document["skins"].append({"joints": [0]})
        fixture.document["nodes"].append({"mesh": 0, "skin": 1})
        self.rejects(fixture, "SEMANTIC_JOINT_RANGE")

    def test_skin_attributes_must_be_paired_and_bound_on_every_primitive(self):
        fixture = Fixture().triangle().skin()
        del fixture.document["meshes"][0]["primitives"][0]["attributes"]["WEIGHTS_0"]
        self.rejects(fixture, "SEMANTIC_SKIN_ATTRIBUTE_PAIR")
        fixture = Fixture().triangle().skin()
        del fixture.document["nodes"][2]["skin"]
        self.rejects(fixture, "SEMANTIC_SKIN_ATTRIBUTES_WITHOUT_BINDING")
        fixture = Fixture().triangle().skin()
        attributes = fixture.document["meshes"][0]["primitives"][0]["attributes"]
        del attributes["JOINTS_0"], attributes["WEIGHTS_0"]
        self.rejects(fixture, "SEMANTIC_SKIN_ATTRIBUTES_REQUIRED")

    def test_inverse_bind_count_affine_row_and_optional_identity(self):
        self.rejects(Fixture().triangle().skin(matrices=(IDENTITY,)), "SEMANTIC_INVERSE_BIND_COUNT")
        bad = (*IDENTITY[:15], 0.5)
        self.rejects(Fixture().triangle().skin(matrices=(IDENTITY, bad)), "SEMANTIC_INVERSE_BIND_AFFINE")
        fixture = Fixture().triangle().skin()
        del fixture.document["skins"][0]["inverseBindMatrices"]
        fixture.check()

    def test_linear_and_step_translation_scale_rotation(self):
        for interpolation in ("LINEAR", "STEP"):
            for path, output in (("rotation", ((0, 0, 0, 1),) * 3), ("translation", ((1, 2, 3),) * 3),
                                 ("scale", ((1, 1, 1),) * 3)):
                with self.subTest(interpolation=interpolation, path=path):
                    Fixture().triangle().animation(output=output, path=path, interpolation=interpolation).check()

    def test_animation_time_order_fixture_range_count_and_required_bounds(self):
        for times in ((0, 0, 1), (0, 0.75, 0.5, 1)):
            self.rejects(Fixture().triangle().animation(times=times), "SEMANTIC_TIME_ORDER")
        for times in ((0.1, 0.5, 1), (0, 0.5, 0.9), (-0.1, 0.5, 1)):
            self.rejects(Fixture().triangle().animation(times=times), "SEMANTIC_FIXTURE_CLIP_RANGE")
        self.rejects(Fixture().triangle().animation(output=((0, 0, 0, 1),) * 2), "SEMANTIC_ANIMATION_COUNT")
        fixture = Fixture().triangle().animation()
        del fixture.document["accessors"][fixture.ids["times"]]["max"]
        self.rejects(fixture, "SEMANTIC_TIME_BOUNDS_REQUIRED")

    def test_rotation_units_types_duplicate_channel_and_matrix_target(self):
        self.rejects(Fixture().triangle().animation(output=((0, 0, 0, 0.99),) * 3), "SEMANTIC_UNIT_ROTATION")
        self.rejects(Fixture().triangle().animation(output=((0, 0, 1),) * 3), "SEMANTIC_ACCESSOR_TYPE")
        fixture = Fixture().triangle().animation()
        fixture.document["animations"][0]["channels"] *= 2
        self.rejects(fixture, "SEMANTIC_DUPLICATE_ANIMATION_TARGET")
        fixture = Fixture().triangle().animation()
        fixture.document["nodes"][0]["matrix"] = list(IDENTITY)
        self.rejects(fixture, "SEMANTIC_ANIMATED_MATRIX")

    def test_bounded_repeated_semantic_work(self):
        with patch.object(semantics, "MAX_SEMANTIC_SCALARS", 1):
            self.rejects(Fixture().triangle(), "SEMANTIC_WORK_LIMIT")

    def test_wrong_decoded_binding_or_constructed_nonfinite_values(self):
        admitted, decoded = Fixture().triangle().admit()
        for bad in (decoded[:-1], list(decoded), (replace(decoded[0], index=1), *decoded[1:]),
                    (replace(decoded[0], values=((float("nan"), 0, 0),) * 3), *decoded[1:])):
            with self.subTest(kind=type(bad).__name__), self.assertRaises(semantics.SemanticRejected):
                semantics.validate_semantics(admitted, bad)


if __name__ == "__main__":
    unittest.main()
