"""Pure byte-safety admission for the initial GT05 GLB profile.

This reads no files and decodes no binary scalar/image payloads. A returned
container proves bounded JSON and in-buffer accessor layouts, not valid geometry,
finite binary floats, actual min/max values, skin/animation correctness, texture
decodability, naming, Khronos conformance, Godot import or publication authority.
Those checks remain mandatory downstream. Document values are immutable.

Supported container: one JSON chunk followed by one BIN chunk and one embedded
buffer. No URI, extension, extras, sparse accessor, morph or implicit zero-filled
accessor. These are deliberate availability restrictions, not glTF-wide rules.
Limits mirror tests/asset-profile.json without reading configuration at import.

Layout rules: glTF 2.0 sections 3.6.1 and 3.6.2.4. Matrix columns align to four
bytes; the last column's trailing padding may be absent. Stride belongs only to
vertex attributes. Interleaved/shared views are allowed when their usage fits.
https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#data-alignment
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import struct
from types import MappingProxyType
from typing import Any, Mapping

MAX_GLB_BYTES = 1_048_576
MAX_JSON_BYTES = 262_144
MAX_ACCESSORS = 2048
MAX_BUFFER_VIEWS = 2048
MAX_DEPTH = 32
MAX_JSON_VALUES = 32_768
MAX_ARRAY_ITEMS = 2048
MAX_OBJECT_MEMBERS = 64
MAX_STRING_CHARS = 4096
MAX_NUMBER_CHARS = 64
MAX_NODES = 256
MAX_MESHES = 128
MAX_TEXTURES = 16
MAX_BONES = 60

_JSON_CHUNK = 0x4E4F534A
_BIN_CHUNK = 0x004E4942
_COMPONENT_BYTES = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
_SHAPES = {"SCALAR": (1, 1), "VEC2": (1, 2), "VEC3": (1, 3),
           "VEC4": (1, 4), "MAT2": (2, 2), "MAT3": (3, 3), "MAT4": (4, 4)}
_FORBIDDEN_KEYS = {"uri", "extensions", "extensionsUsed", "extensionsRequired",
                   "extras", "sparse", "targets", "weights"}
_ROOT_FIELDS = {"asset", "scene", "scenes", "nodes", "meshes", "skins", "animations",
                "materials", "textures", "images", "samplers", "buffers", "bufferViews", "accessors"}
_ARRAY_CAPS = {"scenes": MAX_NODES, "nodes": MAX_NODES, "meshes": MAX_MESHES,
               "skins": MAX_NODES, "animations": MAX_NODES, "materials": MAX_NODES,
               "textures": MAX_TEXTURES, "images": MAX_TEXTURES, "samplers": MAX_TEXTURES,
               "buffers": 1, "bufferViews": MAX_BUFFER_VIEWS, "accessors": MAX_ACCESSORS}
_ATTRIBUTE_NAMES = {"POSITION", "NORMAL", "TANGENT", "TEXCOORD_0", "COLOR_0", "JOINTS_0", "WEIGHTS_0"}


class GLBRejected(ValueError):
    """Stable code only; never include untrusted source data in an error."""


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise GLBRejected(code)


def _integer(value: Any, minimum: int = 0, maximum: int = MAX_GLB_BYTES) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _fields(value: Any, required: set[str], allowed: set[str], code: str) -> None:
    _need(type(value) is dict and required <= value.keys() <= allowed, code)


def _list(value: Any, cap: int = MAX_ARRAY_ITEMS, *, minimum: int = 0) -> list:
    _need(type(value) is list and minimum <= len(value) <= cap, "LIST_LIMIT_OR_TYPE")
    return value


def _index(value: Any, values: list) -> int:
    _need(_integer(value, 0, len(values) - 1), "REFERENCE_INDEX")
    return value


def _json_number(token: str, *, integer: bool) -> int | float:
    _need(len(token) <= MAX_NUMBER_CHARS, "JSON_NUMBER_LIMIT")
    value = int(token) if integer else float(token)
    _need(math.isfinite(value), "JSON_NONFINITE")
    return value


def _pairs(pairs: list[tuple[str, Any]]) -> dict:
    _need(len(pairs) <= MAX_OBJECT_MEMBERS, "JSON_MEMBER_LIMIT")
    result = {}
    for key, value in pairs:
        _need(key not in result, "JSON_DUPLICATE_KEY")
        result[key] = value
    return result


def _constant(_value: str) -> None:
    raise GLBRejected("JSON_NONFINITE")


def _strict_json(raw: bytes) -> dict:
    _need(0 < len(raw) <= MAX_JSON_BYTES, "JSON_BYTE_LIMIT")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise GLBRejected("JSON_UTF8") from None
    # Bound lexical nesting BEFORE invoking the recursive standard decoder.
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            _need(depth <= MAX_DEPTH, "JSON_DEPTH_LIMIT")
        elif char in "]}":
            depth -= 1
            _need(depth >= 0, "JSON_SYNTAX")
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant,
                           parse_int=lambda token: _json_number(token, integer=True),
                           parse_float=lambda token: _json_number(token, integer=False))
    except (json.JSONDecodeError, RecursionError, OverflowError):
        raise GLBRejected("JSON_SYNTAX") from None
    _need(type(value) is dict, "JSON_ROOT_OBJECT")
    pending = [value]
    count = 0
    while pending:
        item = pending.pop()
        count += 1
        _need(count <= MAX_JSON_VALUES, "JSON_VALUE_LIMIT")
        if type(item) is dict:
            _need(not item.keys() & _FORBIDDEN_KEYS, "UNSUPPORTED_JSON_FEATURE")
            pending.extend(item.keys())
            pending.extend(item.values())
        elif type(item) is list:
            _list(item)
            pending.extend(item)
        elif type(item) is str:
            _need(len(item) <= MAX_STRING_CHARS and
                  not any(0xD800 <= ord(char) <= 0xDFFF for char in item), "JSON_STRING_OR_UNICODE")
        elif type(item) is float:
            _need(math.isfinite(item), "JSON_NONFINITE")
    return value


def _freeze(value: Any) -> Any:
    # Recursion is bounded by the lexical check above (at most MAX_DEPTH).
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class AccessorLayout:
    buffer_view: int
    offset: int  # Absolute offset in the returned BIN bytes.
    count: int
    component_type: int
    kind: str
    normalized: bool
    component_offsets: tuple[int, ...]  # Relative to each element, column-major.
    packed_stride: int  # Includes matrix-column padding, including the final column.
    byte_stride: int
    element_extent: int  # Ends at the last component; excludes final-column padding.
    end: int  # Exclusive highest byte read, not offset + count * byte_stride.


@dataclass(frozen=True, slots=True)
class GLBContainer:
    document: Mapping[str, Any]
    binary: bytes  # Declared buffer bytes; GLB zero padding is excluded.
    accessors: tuple[AccessorLayout, ...]
    sha256: str
    size_bytes: int


def _accessor_layouts(document: dict, views: list) -> tuple[AccessorLayout, ...]:
    layouts = []
    for accessor in document.get("accessors", []):
        _fields(accessor, {"bufferView", "componentType", "count", "type"},
                {"bufferView", "byteOffset", "componentType", "normalized", "count", "type", "min", "max", "name"},
                "ACCESSOR_FIELDS")
        view_index = _index(accessor["bufferView"], views)
        view = views[view_index]
        component = accessor["componentType"]
        kind = accessor["type"]
        _need(type(component) is int and component in _COMPONENT_BYTES and
              type(kind) is str and kind in _SHAPES, "ACCESSOR_TYPE")
        count = accessor["count"]
        offset = accessor.get("byteOffset", 0)
        _need(_integer(count, 1) and _integer(offset), "ACCESSOR_COUNT_OR_OFFSET")
        normalized = accessor.get("normalized", False)
        _need(type(normalized) is bool and (not normalized or component in (5120, 5121, 5122, 5123)),
              "ACCESSOR_NORMALIZED")
        size = _COMPONENT_BYTES[component]
        columns, rows = _SHAPES[kind]
        column_bytes = rows * size
        column_stride = (column_bytes + 3) // 4 * 4 if columns > 1 else column_bytes
        offsets = tuple(column * column_stride + row * size for column in range(columns) for row in range(rows))
        packed = columns * column_stride
        extent = offsets[-1] + size
        stride = view.get("byteStride", packed)
        absolute = view.get("byteOffset", 0) + offset
        _need(offset % size == 0 and absolute % size == 0 and stride % size == 0,
              "ACCESSOR_COMPONENT_ALIGNMENT")
        if columns > 1:
            _need(absolute % 4 == 0 and stride % 4 == 0, "ACCESSOR_MATRIX_ALIGNMENT")
        _need(stride >= packed, "ACCESSOR_STRIDE_SIZE")
        end = offset + (count - 1) * stride + extent
        _need(end <= view["byteLength"], "ACCESSOR_BOUNDS")
        for bound in ("min", "max"):
            if bound in accessor:
                values = _list(accessor[bound], 16)
                _need(len(values) == columns * rows and all(type(value) in (int, float) for value in values),
                      "ACCESSOR_MIN_MAX_SHAPE")
        if "min" in accessor and "max" in accessor:
            _need(all(a <= b for a, b in zip(accessor["min"], accessor["max"])), "ACCESSOR_MIN_MAX_ORDER")
        layouts.append(AccessorLayout(view_index, absolute, count, component, kind, normalized,
                                      offsets, packed, stride, extent, view.get("byteOffset", 0) + end))
    return tuple(layouts)


def _hierarchy(document: dict) -> None:
    nodes = document.get("nodes", [])
    parents = [0] * len(nodes)
    children = []
    for node in nodes:
        row = _list(node.get("children", []), MAX_NODES)
        found = set()
        for child in row:
            _index(child, nodes)
            _need(child not in found, "NODE_DUPLICATE_CHILD")
            found.add(child)
            parents[child] += 1
            _need(parents[child] <= 1, "NODE_MULTIPLE_PARENTS")
        children.append(row)
        for name, values in (("mesh", document.get("meshes", [])), ("skin", document.get("skins", []))):
            if name in node:
                _index(node[name], values)
    pending = [(index, 1) for index, count in enumerate(parents) if count == 0]
    visited = 0
    while pending:
        index, depth = pending.pop()
        _need(depth <= MAX_DEPTH, "NODE_DEPTH_LIMIT")
        visited += 1
        pending.extend((child, depth + 1) for child in children[index])
    _need(visited == len(nodes), "NODE_CYCLE")
    scenes = document.get("scenes", [])
    if "scene" in document:
        _index(document["scene"], scenes)
    for scene in scenes:
        roots = _list(scene.get("nodes", []), MAX_NODES)
        seen = set()
        for root in roots:
            _index(root, nodes)
            _need(root not in seen and parents[root] == 0, "SCENE_ROOT")
            seen.add(root)


def _usage(document: dict, views: list, layouts: tuple[AccessorLayout, ...]) -> None:
    """Identify byte-view roles, rather than trusting a bufferView target hint."""
    accessors = document.get("accessors", [])
    roles: list[set[str]] = [set() for _ in views]
    vertex_accessors: list[set[int]] = [set() for _ in views]

    def use(index: Any, role: str) -> AccessorLayout:
        index = _index(index, accessors)
        layout = layouts[index]
        roles[layout.buffer_view].add(role)
        if role == "vertex":
            vertex_accessors[layout.buffer_view].add(index)
            local = layout.offset - views[layout.buffer_view].get("byteOffset", 0)
            _need(local % 4 == 0 and layout.byte_stride % 4 == 0, "VERTEX_ALIGNMENT")
        return layout

    for mesh in document.get("meshes", []):
        for primitive in _list(mesh.get("primitives"), minimum=1):
            _fields(primitive, {"attributes"}, {"attributes", "indices", "material", "mode"}, "PRIMITIVE_FIELDS")
            attributes = primitive["attributes"]
            _need(type(attributes) is dict and 0 < len(attributes) <= len(_ATTRIBUTE_NAMES) and
                  attributes.keys() <= _ATTRIBUTE_NAMES, "ATTRIBUTE_NAMES")
            for index in attributes.values():
                use(index, "vertex")
            if "indices" in primitive:
                layout = use(primitive["indices"], "index")
                _need(layout.kind == "SCALAR" and layout.component_type in (5121, 5123, 5125) and
                      not layout.normalized, "INDEX_ACCESSOR_TYPE")
            if "material" in primitive:
                _index(primitive["material"], document.get("materials", []))
            _need(_integer(primitive.get("mode", 4), 0, 6), "PRIMITIVE_MODE")
    nodes = document.get("nodes", [])
    for skin in document.get("skins", []):
        joints = _list(skin.get("joints"), MAX_BONES, minimum=1)
        for joint in joints:
            _index(joint, nodes)
        _need(len(set(joints)) == len(joints), "SKIN_DUPLICATE_JOINT")
        if "skeleton" in skin:
            _index(skin["skeleton"], nodes)
        if "inverseBindMatrices" in skin:
            layout = use(skin["inverseBindMatrices"], "skin")
            _need(layout.kind == "MAT4" and layout.component_type == 5126, "SKIN_ACCESSOR_TYPE")
    for animation in document.get("animations", []):
        samplers = _list(animation.get("samplers"), minimum=1)
        for sampler in samplers:
            _fields(sampler, {"input", "output"}, {"input", "output", "interpolation"}, "ANIMATION_SAMPLER_FIELDS")
            layout = use(sampler["input"], "animation")
            _need(layout.kind == "SCALAR" and layout.component_type == 5126, "ANIMATION_INPUT_TYPE")
            use(sampler["output"], "animation")
            _need(sampler.get("interpolation", "LINEAR") in ("LINEAR", "STEP"), "ANIMATION_INTERPOLATION")
        for channel in _list(animation.get("channels"), minimum=1):
            _fields(channel, {"sampler", "target"}, {"sampler", "target"}, "ANIMATION_CHANNEL_FIELDS")
            _index(channel["sampler"], samplers)
            target = channel["target"]
            _fields(target, {"node", "path"}, {"node", "path"}, "ANIMATION_TARGET_FIELDS")
            _index(target["node"], nodes)
            _need(target["path"] in ("translation", "rotation", "scale"), "ANIMATION_TARGET_PATH")
    images = document.get("images", [])
    for image in images:
        _fields(image, {"bufferView", "mimeType"}, {"bufferView", "mimeType", "name"}, "IMAGE_FIELDS")
        _need(image["mimeType"] == "image/png", "IMAGE_MIME_UNSUPPORTED")
        roles[_index(image["bufferView"], views)].add("image")
    for texture in document.get("textures", []):
        _fields(texture, {"source"}, {"source", "sampler", "name"}, "TEXTURE_FIELDS")
        _index(texture["source"], images)
        if "sampler" in texture:
            _index(texture["sampler"], document.get("samplers", []))
    for index, (view, used) in enumerate(zip(views, roles)):
        _need(len(used) <= 1, "BUFFER_VIEW_MIXED_USAGE")
        if "byteStride" in view:
            _need(used == {"vertex"}, "BUFFER_VIEW_STRIDE_USAGE")
        if len(vertex_accessors[index]) > 1:
            _need("byteStride" in view, "BUFFER_VIEW_SHARED_VERTEX_STRIDE")
        if "target" in view and used:
            expected = 34962 if used == {"vertex"} else 34963 if used == {"index"} else None
            _need(view["target"] == expected, "BUFFER_VIEW_TARGET_USAGE")


def inspect_glb(raw: bytes) -> GLBContainer:
    """Admit a bounded GLB byte container; this never grants import authority."""
    _need(type(raw) is bytes and 28 <= len(raw) <= MAX_GLB_BYTES, "GLB_BYTE_LIMIT_OR_TYPE")
    magic, version, total = struct.unpack_from("<4sII", raw)
    _need(magic == b"glTF" and version == 2 and total == len(raw), "GLB_HEADER")
    chunks = []
    offset = 12
    for expected in (_JSON_CHUNK, _BIN_CHUNK):
        _need(offset + 8 <= len(raw), "GLB_CHUNK_HEADER")
        length, kind = struct.unpack_from("<II", raw, offset)
        offset += 8
        _need(kind == expected and length > 0 and length % 4 == 0, "GLB_CHUNK_KIND_OR_ALIGNMENT")
        _need(offset + length <= len(raw), "GLB_CHUNK_BOUNDS")
        if expected == _JSON_CHUNK:
            _need(length <= MAX_JSON_BYTES, "JSON_BYTE_LIMIT")
        chunks.append(raw[offset:offset + length])
        offset += length
    _need(offset == len(raw), "GLB_EXTRA_CHUNK_OR_TRAILING_BYTES")
    document = _strict_json(chunks[0])
    _fields(document, {"asset", "buffers"}, _ROOT_FIELDS, "DOCUMENT_FIELDS")
    asset = document["asset"]
    _fields(asset, {"version"}, {"version", "minVersion", "generator", "copyright"}, "ASSET_FIELDS")
    _need(asset["version"] == "2.0" and asset.get("minVersion", "2.0") == "2.0", "ASSET_VERSION")
    for name, cap in _ARRAY_CAPS.items():
        if name in document:
            rows = _list(document[name], cap, minimum=1)
            _need(all(type(row) is dict for row in rows), "DOCUMENT_ARRAY_OBJECTS")
    buffers = document["buffers"]
    _need(len(buffers) == 1, "BUFFER_COUNT")
    buffer = buffers[0]
    _fields(buffer, {"byteLength"}, {"byteLength", "name"}, "BUFFER_FIELDS")
    size = buffer["byteLength"]
    _need(_integer(size, 1) and 0 <= len(chunks[1]) - size <= 3, "BUFFER_LENGTH")
    _need(not any(chunks[1][size:]), "BIN_NONZERO_PADDING")
    views = document.get("bufferViews", [])
    for view in views:
        _fields(view, {"buffer", "byteLength"}, {"buffer", "byteOffset", "byteLength", "byteStride", "target", "name"},
                "BUFFER_VIEW_FIELDS")
        start, length = view.get("byteOffset", 0), view["byteLength"]
        _need(_integer(view["buffer"], 0, 0) and _integer(start) and _integer(length, 1) and
              start + length <= size, "BUFFER_VIEW_BOUNDS_OR_TYPE")
        if "byteStride" in view:
            _need(_integer(view["byteStride"], 4, 252) and view["byteStride"] % 4 == 0, "BUFFER_VIEW_STRIDE")
        if "target" in view:
            _need(type(view["target"]) is int and view["target"] in (34962, 34963), "BUFFER_VIEW_TARGET")
    layouts = _accessor_layouts(document, views)
    _hierarchy(document)
    _usage(document, views, layouts)
    return GLBContainer(_freeze(document), chunks[1][:size], layouts, hashlib.sha256(raw).hexdigest(), len(raw))
