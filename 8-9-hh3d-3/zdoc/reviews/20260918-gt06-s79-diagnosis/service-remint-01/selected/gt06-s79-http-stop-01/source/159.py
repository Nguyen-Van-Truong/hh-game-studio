"""Tiny byte vectors for GT05 container safety, not engine/asset acceptance."""
import copy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from pipeline import glb_container as glb


def encode(document, binary=b"\0" * 12, *, json_bytes=None):
    text = json.dumps(document, separators=(",", ":")).encode() if json_bytes is None else json_bytes
    text += b" " * (-len(text) % 4)
    binary += b"\0" * (-len(binary) % 4)
    chunks = struct.pack("<II", len(text), 0x4E4F534A) + text
    chunks += struct.pack("<II", len(binary), 0x004E4942) + binary
    return struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks


def document(size=12):
    return {"asset": {"version": "2.0"}, "buffers": [{"byteLength": size}],
            "bufferViews": [{"buffer": 0, "byteLength": size}],
            "accessors": [{"bufferView": 0, "componentType": 5126, "count": 1, "type": "VEC3"}]}


def attribute_document(size=12):
    value = document(size)
    value["meshes"] = [{"primitives": [{"attributes": {"POSITION": 0}}]}]
    return value


def rig_vector():
    """Core payload types a later rigged/PBR fixture will need; no PNG decode."""
    binary = bytearray()
    views, accessors = [], []

    def add(data, kind, component, count):
        binary.extend(b"\0" * (-len(binary) % 4))
        views.append({"buffer": 0, "byteOffset": len(binary), "byteLength": len(data)})
        binary.extend(data)
        accessors.append({"bufferView": len(views) - 1, "componentType": component, "count": count, "type": kind})

    add(struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0), "VEC3", 5126, 3)
    add(struct.pack("<9f", *([0, 0, 1] * 3)), "VEC3", 5126, 3)
    add(struct.pack("<6f", 0, 0, 1, 0, 0, 1), "VEC2", 5126, 3)
    add(struct.pack("<3H", 0, 1, 2), "SCALAR", 5123, 3)
    add(bytes(12), "VEC4", 5121, 3)
    add(struct.pack("<12f", *([1, 0, 0, 0] * 3)), "VEC4", 5126, 3)
    add(struct.pack("<16f", *[float(i % 5 == 0) for i in range(16)]), "MAT4", 5126, 1)
    add(struct.pack("<2f", 0, 1), "SCALAR", 5126, 2)
    add(struct.pack("<6f", 0, 0, 0, 0, 0, 0), "VEC3", 5126, 2)
    binary.extend(b"\0" * (-len(binary) % 4))
    views.append({"buffer": 0, "byteOffset": len(binary), "byteLength": 8})
    binary.extend(b"\x89PNG\r\n\x1a\n")  # Deliberately only a header: admission does not decode.
    value = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": len(binary)}],
             "bufferViews": views, "accessors": accessors,
             "nodes": [{"children": [1]}, {"mesh": 0, "skin": 0}],
             "scenes": [{"nodes": [0]}], "scene": 0,
             "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2,
                         "JOINTS_0": 4, "WEIGHTS_0": 5}, "indices": 3, "material": 0}]}],
             "skins": [{"joints": [0], "skeleton": 0, "inverseBindMatrices": 6}],
             "animations": [{"samplers": [{"input": 7, "output": 8}],
                             "channels": [{"sampler": 0, "target": {"node": 0, "path": "translation"}}]}],
             "images": [{"bufferView": 9, "mimeType": "image/png"}],
             "textures": [{"source": 0, "sampler": 0}], "samplers": [{}],
             "materials": [{"pbrMetallicRoughness": {"baseColorTexture": {"index": 0}}}]}
    return value, bytes(binary)


class ContainerTests(unittest.TestCase):
    def rejects(self, raw, code=None):
        with self.assertRaises(glb.GLBRejected) as caught:
            glb.inspect_glb(raw)
        if code is not None:
            self.assertEqual(str(caught.exception), code)

    def test_limits_match_locked_data_profile(self):
        profile = json.loads((Path(__file__).resolve().parents[1] / "asset-profile.json").read_bytes())
        limits = profile["limits"]
        for name, actual in {"glb_bytes": glb.MAX_GLB_BYTES, "json_bytes": glb.MAX_JSON_BYTES,
                             "accessors": glb.MAX_ACCESSORS, "buffer_views": glb.MAX_BUFFER_VIEWS,
                             "hierarchy_depth": glb.MAX_DEPTH, "nodes": glb.MAX_NODES,
                             "meshes": glb.MAX_MESHES, "textures": glb.MAX_TEXTURES,
                             "avatar_bones": glb.MAX_BONES}.items():
            self.assertEqual(actual, limits[name], name)

    def test_returns_exact_bytes_hash_and_immutable_document_without_io(self):
        raw = encode(document())
        with patch("builtins.open", side_effect=AssertionError("no I/O")):
            result = glb.inspect_glb(raw)
        self.assertEqual(result.sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(result.size_bytes, len(raw))
        self.assertEqual(result.binary, bytes(12))
        self.assertEqual(result.accessors[0].component_offsets, (0, 4, 8))
        with self.assertRaises(TypeError):
            result.document["asset"]["version"] = "changed"
        with self.assertRaises(FrozenInstanceError):
            result.accessors[0].count = 5

    def test_rig_uv_indices_weights_matrices_animation_and_embedded_image_ranges(self):
        value, binary = rig_vector()
        result = glb.inspect_glb(encode(value, binary))
        self.assertEqual(len(result.accessors), 9)
        self.assertEqual(result.accessors[6].component_offsets, tuple(range(0, 64, 4)))
        for index, layout in enumerate(result.accessors):
            self.assertLessEqual(layout.end, len(binary), index)
        self.assertEqual(result.document["images"][0]["mimeType"], "image/png")

    def test_nonfinite_binary_and_png_decodability_are_explicitly_not_claimed(self):
        result = glb.inspect_glb(encode(document(), struct.pack("<3f", float("nan"), float("inf"), 0)))
        self.assertEqual(len(result.binary), 12)  # Downstream semantic admission must reject these.

    def test_binary_padding_excluded_from_returned_bytes(self):
        value = document(3)
        value["accessors"][0].update(componentType=5121, type="SCALAR", count=3)
        raw = encode(value, b"abc")
        self.assertEqual(glb.inspect_glb(raw).binary, b"abc")
        self.rejects(raw[:-1] + b"x", "BIN_NONZERO_PADDING")

    def test_header_types_lengths_and_exact_chunk_order(self):
        raw = encode(document())
        json_length = struct.unpack_from("<I", raw, 12)[0]
        first = raw[12:20 + json_length]
        second = raw[20 + json_length:]
        variants = [b"bad!" + raw[4:], raw[:4] + struct.pack("<I", 1) + raw[8:],
                    raw[:8] + struct.pack("<I", len(raw) - 1) + raw[12:],
                    raw[:12] + second + first, raw[:12] + first + first,
                    raw[:12] + struct.pack("<II", json_length + 1, 0x4E4F534A) + raw[20:],
                    raw[:12] + struct.pack("<II", len(raw) * 4, 0x4E4F534A) + raw[20:]]
        for broken in variants:
            self.rejects(broken)
        extra = raw + struct.pack("<II", 4, 0x44444444) + b"abcd"
        extra = extra[:8] + struct.pack("<I", len(extra)) + extra[12:]
        self.rejects(extra, "GLB_EXTRA_CHUNK_OR_TRAILING_BYTES")
        missing = raw[:20 + json_length]
        missing = missing[:8] + struct.pack("<I", len(missing)) + missing[12:]
        self.rejects(missing, "GLB_CHUNK_HEADER")
        for bad in (None, bytearray(raw), memoryview(raw), b"", raw[:27], bytes(glb.MAX_GLB_BYTES + 1)):
            self.rejects(bad, "GLB_BYTE_LIMIT_OR_TYPE")

    def test_every_truncated_prefix_rejected(self):
        raw = encode(document())
        for length in range(len(raw)):
            with self.subTest(length=length):
                self.rejects(raw[:length])

    def test_strict_json_duplicates_numbers_and_unicode(self):
        samples = [(b'{"asset":{"version":"2.0","ve\\u0072sion":"2.0"}}', "JSON_DUPLICATE_KEY"),
                   (b'{"a":1,"a":2}', "JSON_DUPLICATE_KEY"),
                   (b'{"a":NaN}', "JSON_NONFINITE"), (b'{"a":Infinity}', "JSON_NONFINITE"),
                   (b'{"a":-Infinity}', "JSON_NONFINITE"), (b'{"a":1e999}', "JSON_NONFINITE"),
                   (b'{"a":' + b"9" * 65 + b'}', "JSON_NUMBER_LIMIT"),
                   (b'{"a":"\\ud800"}', "JSON_STRING_OR_UNICODE"),
                   (b'{"\\udfff":1}', "JSON_STRING_OR_UNICODE"),
                   (b'{"a":"\xed\xa0\x80"}', "JSON_UTF8"),
                   (b'{"a":"\xc0\x80"}', "JSON_UTF8"),
                   (b'\xef\xbb\xbf{}', "JSON_SYNTAX"),
                   (b'{}{}', "JSON_SYNTAX"), (b'[]', "JSON_ROOT_OBJECT"),
                   (b'{"a":01}', "JSON_SYNTAX"), (b'{"a":1,}', "JSON_SYNTAX")]
        for text, code in samples:
            with self.subTest(code=code, text=text[:40]):
                self.rejects(encode({}, json_bytes=text), code)
        valid = document()
        valid["asset"]["generator"] = "prefix \U0001f600 [ { \\\" suffix"
        self.assertEqual(glb.inspect_glb(encode(valid)).document["asset"]["generator"], valid["asset"]["generator"])

    def test_json_size_nesting_collections_and_aggregate_work_caps(self):
        self.rejects(encode({}, json_bytes=b" " * (glb.MAX_JSON_BYTES + 4)), "JSON_BYTE_LIMIT")
        deep = b'{"a":' + b"[" * 32 + b"0" + b"]" * 32 + b"}"
        self.rejects(encode({}, json_bytes=deep), "JSON_DEPTH_LIMIT")
        value = document()
        value["materials"] = [{str(i): 0 for i in range(65)}]
        self.rejects(encode(value), "JSON_MEMBER_LIMIT")
        value["materials"] = [{"field": [0] * 2049}]
        self.rejects(encode(value), "LIST_LIMIT_OR_TYPE")
        value["materials"] = [{"field": [0] * 256} for _ in range(128)]
        self.rejects(encode(value), "JSON_VALUE_LIMIT")
        value = document()
        value["asset"]["generator"] = "a" * 4097
        self.rejects(encode(value), "JSON_STRING_OR_UNICODE")

    def test_policy_rejects_uri_extensions_extras_sparse_and_morph_at_any_depth(self):
        for key, content in (("uri", "file:///not-read"), ("extensions", {"UNKNOWN": {}}),
                             ("extensionsUsed", []), ("extensionsRequired", ["UNKNOWN"]),
                             ("extras", {}), ("sparse", {}), ("targets", []), ("weights", [])):
            value = document()
            value["materials"] = [{"nested": {key: content}}]
            self.rejects(encode(value), "UNSUPPORTED_JSON_FEATURE")

    def test_buffer_and_view_reject_bool_float_negative_and_out_of_bounds(self):
        for bad in (True, False, 12.0, "12", -1, 0, 13, 8):
            value = document()
            value["buffers"][0]["byteLength"] = bad
            self.rejects(encode(value))
        for key, invalid in (("buffer", (True, 0.0, -1, 1)), ("byteLength", (True, 12.0, -1, 0, 13)),
                             ("byteOffset", (True, 0.0, -1, 1)), ("target", (True, 34962.0, 123)),
                             ("byteStride", (True, 4.0, 0, 3, 5, 256))):
            for bad in invalid:
                value = document()
                value["bufferViews"][0][key] = bad
                self.rejects(encode(value))
        value = document()
        value["buffers"].append({"byteLength": 12})
        self.rejects(encode(value), "LIST_LIMIT_OR_TYPE")

    def test_accessor_type_count_offset_normalization_and_bounds(self):
        mutations = {"bufferView": (True, 0.0, -1, 1), "componentType": (True, 5126.0, 5124, None),
                     "type": ([], "VEC5", True), "count": (True, 1.0, 0, -1, 2, 10**20),
                     "byteOffset": (True, 0.0, -1, 1, 4), "normalized": (1, "true", None, True),
                     "min": ([0, 0], [False, 0, 0], ["0", 0, 0]), "max": ([0, 0], None)}
        for key, invalid in mutations.items():
            for bad in invalid:
                value = document()
                value["accessors"][0][key] = bad
                with self.subTest(key=key, bad=bad):
                    self.rejects(encode(value))
        value = document()
        del value["accessors"][0]["bufferView"]
        self.rejects(encode(value), "ACCESSOR_FIELDS")
        value = document()
        value["accessors"][0].update(min=[1, 0, 0], max=[0, 0, 0])
        self.rejects(encode(value), "ACCESSOR_MIN_MAX_ORDER")

    def test_absolute_alignment_not_only_accessor_local_alignment(self):
        value = document(16)
        value["bufferViews"][0].update(byteOffset=2, byteLength=12)
        self.rejects(encode(value, bytes(16)), "ACCESSOR_COMPONENT_ALIGNMENT")

    def test_all_core_component_widths_and_accessor_shapes_have_bounded_layouts(self):
        for component, size in ((5120, 1), (5121, 1), (5122, 2), (5123, 2), (5125, 4), (5126, 4)):
            for kind, columns, rows in (("SCALAR", 1, 1), ("VEC2", 1, 2), ("VEC3", 1, 3), ("VEC4", 1, 4),
                                        ("MAT2", 2, 2), ("MAT3", 3, 3), ("MAT4", 4, 4)):
                column_stride = ((rows * size + 3) // 4 * 4) if columns > 1 else rows * size
                packed = columns * column_stride
                extent = (columns - 1) * column_stride + rows * size
                length = packed + extent  # Two elements; omit only the final trailing matrix padding.
                value = document(length)
                value["accessors"][0].update(componentType=component, type=kind, count=2)
                result = glb.inspect_glb(encode(value, bytes(length)))
                self.assertEqual(result.accessors[0].end, length)
                value["bufferViews"][0]["byteLength"] -= 1
                self.rejects(encode(value, bytes(length)), "ACCESSOR_BOUNDS")

    def test_matrix_column_padding_uses_last_component_not_naive_component_product(self):
        for kind, component, count, exact, offsets in (
                ("MAT2", 5121, 2, 14, (0, 1, 4, 5)),
                ("MAT3", 5121, 2, 23, (0, 1, 2, 4, 5, 6, 8, 9, 10)),
                ("MAT3", 5123, 2, 46, (0, 2, 4, 8, 10, 12, 16, 18, 20))):
            value = document(exact)
            value["accessors"][0].update(type=kind, componentType=component, count=count)
            self.assertEqual(glb.inspect_glb(encode(value, bytes(exact))).accessors[0].component_offsets, offsets)
            value["bufferViews"][0]["byteLength"] = len(offsets) * count * (2 if component == 5123 else 1)
            self.rejects(encode(value, bytes(exact)), "ACCESSOR_BOUNDS")
        value = document(12)
        value["bufferViews"][0].update(byteOffset=2, byteLength=10)
        value["accessors"][0].update(componentType=5121, type="MAT2")
        self.rejects(encode(value), "ACCESSOR_MATRIX_ALIGNMENT")

    def test_interleaved_vertex_views_are_supported_but_bad_stride_fails(self):
        value = attribute_document(48)
        value["bufferViews"][0].update(byteStride=24, target=34962)
        value["accessors"][0]["count"] = 2
        value["accessors"].append({"bufferView": 0, "byteOffset": 12, "componentType": 5126, "type": "VEC3", "count": 2})
        value["meshes"][0]["primitives"][0]["attributes"]["NORMAL"] = 1
        result = glb.inspect_glb(encode(value, bytes(48)))
        self.assertEqual([row.end for row in result.accessors], [36, 48])
        broken = copy.deepcopy(value)
        del broken["bufferViews"][0]["byteStride"]
        self.rejects(encode(broken, bytes(48)), "BUFFER_VIEW_SHARED_VERTEX_STRIDE")
        broken = copy.deepcopy(value)
        broken["bufferViews"][0]["byteStride"] = 8
        self.rejects(encode(broken, bytes(48)), "ACCESSOR_STRIDE_SIZE")
        value["accessors"][1]["count"] = 3
        self.rejects(encode(value, bytes(48)), "ACCESSOR_BOUNDS")

    def test_vertex_four_byte_alignment_including_implicit_stride(self):
        value = attribute_document(8)
        value["accessors"][0].update(componentType=5121, type="VEC3", count=2)
        self.rejects(encode(value, bytes(8)), "VERTEX_ALIGNMENT")
        value["bufferViews"][0]["byteStride"] = 4
        self.assertEqual(glb.inspect_glb(encode(value, bytes(8))).accessors[0].end, 7)
        value["accessors"][0]["byteOffset"] = 1
        self.rejects(encode(value, bytes(8)), "VERTEX_ALIGNMENT")

    def test_strided_nonvertex_and_mixed_usage_are_rejected(self):
        value = document()
        value["bufferViews"][0]["byteStride"] = 12
        self.rejects(encode(value), "BUFFER_VIEW_STRIDE_USAGE")
        value = attribute_document()
        value["images"] = [{"bufferView": 0, "mimeType": "image/png"}]
        self.rejects(encode(value), "BUFFER_VIEW_MIXED_USAGE")
        value = attribute_document()
        value["bufferViews"][0]["target"] = 34963
        self.rejects(encode(value), "BUFFER_VIEW_TARGET_USAGE")
        value, binary = rig_vector()
        value["bufferViews"][7]["byteStride"] = 4
        self.rejects(encode(value, binary), "BUFFER_VIEW_STRIDE_USAGE")

    def test_referenced_indices_types_and_roles_are_checked(self):
        for index in (True, 0.0, -1, 99):
            value = attribute_document()
            value["meshes"][0]["primitives"][0]["attributes"]["POSITION"] = index
            self.rejects(encode(value), "REFERENCE_INDEX")
        value = attribute_document()
        value["meshes"][0]["primitives"][0]["indices"] = 0
        self.rejects(encode(value), "INDEX_ACCESSOR_TYPE")
        for namespace, field, bad, code in (("skins", "inverseBindMatrices", 0, "SKIN_ACCESSOR_TYPE"),
                                             ("images", "mimeType", "image/jpeg", "IMAGE_MIME_UNSUPPORTED"),
                                             ("images", "bufferView", 99, "REFERENCE_INDEX"),
                                             ("textures", "source", True, "REFERENCE_INDEX")):
            value, binary = rig_vector()
            value[namespace][0][field] = bad
            self.rejects(encode(value, binary), code)
        value, binary = rig_vector()
        value["animations"][0]["samplers"][0]["interpolation"] = "CUBICSPLINE"
        self.rejects(encode(value, binary), "ANIMATION_INTERPOLATION")

    def test_hierarchy_cycles_parent_aliases_depth_and_scene_roots(self):
        cases = [([{"children": [0]}], "NODE_CYCLE"),
                 ([{}, {"children": [2]}, {"children": [1]}], "NODE_CYCLE"),
                 ([{"children": [1, 1]}, {}], "NODE_DUPLICATE_CHILD"),
                 ([{"children": [2]}, {"children": [2]}, {}], "NODE_MULTIPLE_PARENTS"),
                 ([{"children": [True]}, {}], "REFERENCE_INDEX"),
                 ([{"children": [2]}, {}], "REFERENCE_INDEX")]
        for nodes, code in cases:
            value = document()
            value["nodes"] = nodes
            self.rejects(encode(value), code)
        value = document()
        value["nodes"] = [{"children": [i + 1]} for i in range(31)] + [{}]
        self.assertEqual(len(glb.inspect_glb(encode(value)).document["nodes"]), 32)
        value["nodes"][-1] = {"children": [32]}
        value["nodes"].append({})
        self.rejects(encode(value), "NODE_DEPTH_LIMIT")
        value["nodes"] = [{"children": [1]}, {}]
        value["scenes"] = [{"nodes": [1]}]
        self.rejects(encode(value), "SCENE_ROOT")

    def test_profile_array_caps_and_unknown_container_fields(self):
        for field, count in (("nodes", 257), ("meshes", 129), ("images", 17),
                             ("accessors", 2049), ("bufferViews", 2049)):
            value = document()
            value[field] = [{}] * count
            self.rejects(encode(value), "LIST_LIMIT_OR_TYPE")
        value = document()
        value["executable"] = "not-a-supported-field"
        self.rejects(encode(value), "DOCUMENT_FIELDS")
        for field in ("bufferViews", "accessors"):
            value = document()
            value[field][0]["unknown"] = 1
            self.rejects(encode(value))

    def test_exact_accessor_and_view_capacity_is_usable_without_payload_expansion(self):
        value = document(4)
        value["bufferViews"] = [{"buffer": 0, "byteLength": 4} for _ in range(2048)]
        value["accessors"] = [{"bufferView": i, "componentType": 5126, "count": 1, "type": "SCALAR"}
                              for i in range(2048)]
        result = glb.inspect_glb(encode(value, bytes(4)))
        self.assertEqual(len(result.accessors), 2048)
        self.assertEqual(len(result.document["bufferViews"]), 2048)
        self.assertEqual(result.accessors[-1].end, 4)


if __name__ == "__main__":
    unittest.main()
