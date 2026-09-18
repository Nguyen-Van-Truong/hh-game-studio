"""Actual accessor values after container admission; no geometry/skin claim."""
from dataclasses import FrozenInstanceError, replace
import json
import math
import struct
from types import MappingProxyType
import unittest
from unittest.mock import patch

from pipeline import accessor_values as av
from pipeline.glb_container import inspect_glb


def container(document, binary):
    text = json.dumps(document, separators=(",", ":")).encode()
    text += b" " * (-len(text) % 4)
    padded = binary + b"\0" * (-len(binary) % 4)
    chunks = struct.pack("<II", len(text), 0x4E4F534A) + text
    chunks += struct.pack("<II", len(padded), 0x004E4942) + padded
    return inspect_glb(struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks)


def fixture(binary, *, component=5126, kind="SCALAR", count=1, **fields):
    declared = {"bufferView": 0, "componentType": component, "type": kind, "count": count, **fields}
    document = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": len(binary)}],
                "bufferViews": [{"buffer": 0, "byteLength": len(binary)}], "accessors": [declared]}
    return container(document, binary)


class AccessorTests(unittest.TestCase):
    def rejects(self, data, code=None, **options):
        with self.assertRaises(av.AccessorRejected) as caught:
            av.decode_accessors(data, **options)
        if code is not None:
            self.assertEqual(str(caught.exception), code)

    def test_scalar_all_component_types_and_exact_uint32(self):
        for component, format_, values in ((5120, "b", (-128, -1, 127)), (5121, "B", (0, 128, 255)),
                (5122, "h", (-32768, -1, 32767)), (5123, "H", (0, 32768, 65535)),
                (5125, "I", (0, 16777217, 4294967295)), (5126, "f", (-0.5, 0.25, 1.5))):
            with self.subTest(component=component):
                item = av.decode_accessors(fixture(struct.pack("<3" + format_, *values), component=component,
                                                   count=3, min=[min(values)], max=[max(values)]))[0]
                self.assertEqual(item.values, tuple((value,) for value in values))
                self.assertEqual(item.minimum, (min(values),))
                self.assertEqual(item.maximum, (max(values),))
                self.assertEqual(item.component_type, component)

    def test_normalized_values_and_raw_extrema_signed_clamp(self):
        cases = ((5120, "b", (-128, -127, 0, 127), (-1, -1, 0, 1)),
                 (5122, "h", (-32768, -32767, 0, 32767), (-1, -1, 0, 1)),
                 (5121, "B", (0, 1, 128, 255), (0, 1 / 255, 128 / 255, 1)),
                 (5123, "H", (0, 1, 32768, 65535), (0, 1 / 65535, 32768 / 65535, 1)))
        for component, format_, raw, expected in cases:
            with self.subTest(component=component):
                item = av.decode_accessors(fixture(struct.pack("<4" + format_, *raw), component=component,
                    kind="VEC4", normalized=True, min=list(raw), max=list(raw)))[0]
                self.assertTrue(item.normalized)
                self.assertEqual(item.values, (expected,))
                self.assertEqual(item.minimum, raw)
                self.assertEqual(item.maximum, raw)
        self.rejects(fixture(bytes([255]), component=5121, normalized=True, max=[1]),
                     "ACCESSOR_DECLARED_BOUND_MISMATCH")

    def test_position_uv_normal_joint_weight_and_animation_shapes(self):
        for kind, count, values in (("VEC2", 2, (0.0, 1.0, 0.5, 0.25)),
                                   ("VEC3", 2, (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)),
                                   ("VEC4", 1, (0.0, 0.0, 0.0, 1.0))):
            with self.subTest(kind=kind):
                width = int(kind[-1])
                item = av.decode_accessors(fixture(struct.pack("<" + "f" * len(values), *values), kind=kind, count=count))[0]
                self.assertEqual(item.values, tuple(tuple(values[i:i + width]) for i in range(0, len(values), width)))
        joints = av.decode_accessors(fixture(bytes([0, 4, 7, 59]), component=5121, kind="VEC4"))[0]
        self.assertEqual(joints.values, ((0, 4, 7, 59),))

    def test_matrix_column_padding_and_omitted_final_padding(self):
        cases = (("MAT2", 5121, "B", 2, 4), ("MAT3", 5121, "B", 3, 4),
                 ("MAT3", 5123, "H", 3, 8), ("MAT4", 5126, "f", 4, 16))
        for kind, component, format_, dimension, column_stride in cases:
            with self.subTest(kind=kind, component=component):
                size = struct.calcsize(format_)
                packed = dimension * column_stride
                extent = (dimension - 1) * column_stride + dimension * size
                binary = bytearray(b"\xaa" * (packed + extent))
                for element in range(2):
                    for column in range(dimension):
                        for row in range(dimension):
                            value = element * 20 + column * dimension + row + 1
                            struct.pack_into("<" + format_, binary, element * packed + column * column_stride + row * size, value)
                item = av.decode_accessors(fixture(bytes(binary), component=component, kind=kind, count=2))[0]
                self.assertEqual(item.values, (tuple(range(1, dimension ** 2 + 1)), tuple(range(21, 21 + dimension ** 2))))
                self.assertEqual(item.minimum, item.values[0])
                self.assertEqual(item.maximum, item.values[1])

    def test_interleaved_vertex_stride_and_both_view_accessor_offsets(self):
        binary = b"skip" + struct.pack("<12f", 1, 2, 3, 0, 1, 0, 4, 5, 6, 0, 0, 1)
        document = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": len(binary)}],
                    "bufferViews": [{"buffer": 0, "byteOffset": 4, "byteLength": 48, "byteStride": 24}],
                    "accessors": [{"bufferView": 0, "componentType": 5126, "type": "VEC3", "count": 2},
                                  {"bufferView": 0, "byteOffset": 12, "componentType": 5126, "type": "VEC3", "count": 2}],
                    "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1}}]}]}
        positions, normals = av.decode_accessors(container(document, binary))
        self.assertEqual(positions.values, ((1, 2, 3), (4, 5, 6)))
        self.assertEqual(normals.values, ((0, 1, 0), (0, 0, 1)))
        self.assertEqual((positions.index, normals.index), (0, 1))

    def test_float32_declared_bounds_round_once_without_epsilon(self):
        raw = struct.pack("<2f", 0.1, 0.2)
        item = av.decode_accessors(fixture(raw, count=2, min=[0.1], max=[0.2]))[0]
        self.assertEqual(item.minimum, (struct.unpack("<f", raw[:4])[0],))
        self.rejects(fixture(raw, count=2, min=[0.1000001], max=[0.2]), "ACCESSOR_DECLARED_BOUND_MISMATCH")
        self.rejects(fixture(struct.pack("<f", 0), max=[1e100]), "ACCESSOR_DECLARED_BOUND_RANGE")

    def test_bounds_compare_every_axis_and_integer_range(self):
        raw = bytes([2, 9, 4, 7, 3, 8])
        item = av.decode_accessors(fixture(raw, component=5121, kind="VEC3", count=2, min=[2, 3, 4], max=[7, 9, 8]))[0]
        self.assertEqual(item.minimum, (2, 3, 4))
        self.assertEqual(item.maximum, (7, 9, 8))
        self.rejects(fixture(raw, component=5121, kind="VEC3", count=2, max=[7, 10, 8]), "ACCESSOR_DECLARED_BOUND_MISMATCH")
        for bound in (-1, 256, 2.5):
            self.rejects(fixture(bytes([2]), component=5121, min=[bound]), "ACCESSOR_DECLARED_BOUND_RANGE")

    def test_binary_float_nan_and_both_infinities_rejected(self):
        for bits in (0x7FC00000, 0x7F800001, 0x7F800000, 0xFF800000):
            with self.subTest(bits=hex(bits)):
                self.rejects(fixture(struct.pack("<I", bits)), "ACCESSOR_NONFINITE_BINARY")
        self.assertEqual(av.decode_accessors(fixture(struct.pack("<I", 1)))[0].values, ((2 ** -149,),))

    def test_scalar_budget_counts_aliases_and_checks_before_unpack(self):
        binary = bytes([1, 2, 3, 4])
        document = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": 4}],
                    "bufferViews": [{"buffer": 0, "byteLength": 4}],
                    "accessors": [{"bufferView": 0, "componentType": 5121, "type": "SCALAR", "count": 4}] * 3}
        admitted = container(document, binary)
        with patch.object(av.struct, "Struct", side_effect=AssertionError("must preflight")):
            self.rejects(admitted, "ACCESSOR_VALUE_LIMIT", max_values=11)
        self.assertEqual(len(av.decode_accessors(admitted, max_values=12)), 3)
        for limit in (True, -1, 1.0, av.MAX_DECODED_VALUES + 1):
            self.rejects(admitted, "ACCESSOR_VALUE_BUDGET", max_values=limit)
        self.assertEqual(av.MAX_DECODED_VALUES, 1_048_576)

    def test_no_accessor_empty_result_and_immutable_nonempty_result_without_io(self):
        empty = container({"asset": {"version": "2.0"}, "buffers": [{"byteLength": 4}]}, b"data")
        self.assertEqual(av.decode_accessors(empty, max_values=0), ())
        admitted = fixture(bytes([7]), component=5121)
        with patch("builtins.open", side_effect=AssertionError("no I/O")):
            result = av.decode_accessors(admitted)
        self.assertIsInstance(result, tuple)
        with self.assertRaises(TypeError):
            result[0].values[0][0] = 8
        with self.assertRaises(FrozenInstanceError):
            result[0].kind = "VEC4"

    def test_manually_constructed_unsafe_layouts_fail_closed(self):
        admitted = fixture(struct.pack("<3f", 1, 2, 3), kind="VEC3")
        layout = admitted.accessors[0]
        for change in ({"count": True}, {"count": 0}, {"offset": -1}, {"offset": 4}, {"end": 13},
                       {"byte_stride": 0}, {"component_offsets": (0, 4, 12)}, {"packed_stride": 4},
                       {"component_type": 9999}, {"kind": "UNKNOWN"}, {"normalized": True},
                       {"component_offsets": (False, 4, 8)}, {"element_extent": 999}):
            with self.subTest(change=change):
                self.rejects(replace(admitted, accessors=(replace(layout, **change),)))
        self.rejects(replace(admitted, binary=b""), "ACCESSOR_LAYOUT_BOUNDS")
        self.rejects(replace(admitted, document=dict(admitted.document)), "ACCESSOR_CONTAINER_TYPE")
        self.rejects(None, "ACCESSOR_CONTAINER_TYPE")

    def test_constructed_declarations_bad_binding_bounds_and_huge_integer(self):
        admitted = fixture(struct.pack("<f", 0))

        def changed(**fields):
            declaration = MappingProxyType({**admitted.document["accessors"][0], **fields})
            return replace(admitted, document=MappingProxyType({**admitted.document, "accessors": (declaration,)}))

        self.rejects(changed(count=2), "ACCESSOR_DECLARATION_BINDING")
        self.rejects(changed(min=(0, 0)), "ACCESSOR_DECLARED_BOUND_SHAPE")
        for value in (True, "0", math.nan, math.inf):
            self.rejects(changed(min=(value,)), "ACCESSOR_DECLARED_BOUND_TYPE")
        self.rejects(changed(min=(10 ** 1000,)), "ACCESSOR_DECLARED_BOUND_RANGE")


if __name__ == "__main__":
    unittest.main()
