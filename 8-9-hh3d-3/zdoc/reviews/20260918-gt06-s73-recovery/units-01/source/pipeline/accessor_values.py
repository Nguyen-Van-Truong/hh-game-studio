"""Bounded glTF accessor values from inspect_glb's immutable byte layouts.

Values follow matrix column-major component order, excluding column padding and
interleaved fields. Float32 NaN/Inf is rejected. Declared min/max is checked on
raw (not normalized) values; JSON float bounds are rounded to float32 exactly,
not compared with an epsilon. Normalized integer output uses the core glTF
conversion, including clamping the most-negative signed integer to -1.

This validates declared bounds only; required POSITION/time bounds, index/skin
relationships, normalized-weight sums, quaternions, animation timing, geometry
and naming are separate semantic checks. No I/O, engine or publication occurs.
Container objects and this result are data, not an import/authority certificate.

https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#accessors-bounds
https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#animations
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from types import MappingProxyType

from .glb_container import AccessorLayout, GLBContainer, MAX_ACCESSORS, MAX_GLB_BYTES

MAX_DECODED_VALUES = 1_048_576  # Scalars over ALL accessors, including aliased input.
_FORMATS = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}
_SHAPES = {"SCALAR": (1, 1), "VEC2": (1, 2), "VEC3": (1, 3), "VEC4": (1, 4),
           "MAT2": (2, 2), "MAT3": (3, 3), "MAT4": (4, 4)}
_INTEGER_RANGE = {5120: (-128, 127), 5121: (0, 255), 5122: (-32768, 32767),
                  5123: (0, 65535), 5125: (0, 4294967295)}


class AccessorRejected(ValueError):
    """Stable error code without candidate data."""


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise AccessorRejected(code)


@dataclass(frozen=True, slots=True)
class AccessorValues:
    index: int
    component_type: int
    kind: str
    normalized: bool
    values: tuple[tuple[int | float, ...], ...]
    minimum: tuple[int | float, ...]  # Raw stored-domain extrema.
    maximum: tuple[int | float, ...]


def _admit_layout(layout: AccessorLayout, binary_size: int) -> int:
    """Keep decode allocations/reads safe even if a caller constructs a record."""
    _need(type(layout) is AccessorLayout and type(layout.component_type) is int and
          layout.component_type in _FORMATS and type(layout.kind) is str and layout.kind in _SHAPES,
          "ACCESSOR_LAYOUT_TYPE")
    _need(type(layout.count) is int and 1 <= layout.count <= MAX_DECODED_VALUES and
          type(layout.offset) is int and layout.offset >= 0 and
          type(layout.byte_stride) is int and 1 <= layout.byte_stride <= 252 and
          type(layout.end) is int, "ACCESSOR_LAYOUT_RANGE")
    size = struct.calcsize(_FORMATS[layout.component_type])
    columns, rows = _SHAPES[layout.kind]
    column_stride = (rows * size + 3) // 4 * 4 if columns > 1 else rows * size
    offsets = tuple(column * column_stride + row * size for column in range(columns) for row in range(rows))
    packed, extent = columns * column_stride, offsets[-1] + size
    _need(type(layout.component_offsets) is tuple and
          all(type(item) is int for item in layout.component_offsets) and layout.component_offsets == offsets and
          type(layout.packed_stride) is int and layout.packed_stride == packed and
          type(layout.element_extent) is int and layout.element_extent == extent, "ACCESSOR_LAYOUT_COMPONENTS")
    _need(layout.offset % size == 0 and layout.byte_stride % size == 0 and layout.byte_stride >= packed and
          layout.end == layout.offset + (layout.count - 1) * layout.byte_stride + extent and
          layout.end <= binary_size, "ACCESSOR_LAYOUT_BOUNDS")
    if columns > 1:
        _need(layout.offset % 4 == 0 and layout.byte_stride % 4 == 0, "ACCESSOR_LAYOUT_ALIGNMENT")
    _need(type(layout.normalized) is bool and
          (not layout.normalized or layout.component_type in (5120, 5121, 5122, 5123)),
          "ACCESSOR_NORMALIZATION")
    return layout.count * len(offsets)


def _bound(value: int | float, component: int) -> int | float:
    _need(type(value) in (int, float) and (type(value) is int or math.isfinite(value)),
          "ACCESSOR_DECLARED_BOUND_TYPE")
    if component == 5126:
        try:
            rounded = struct.unpack("<f", struct.pack("<f", value))[0]
        except (OverflowError, struct.error):
            raise AccessorRejected("ACCESSOR_DECLARED_BOUND_RANGE") from None
        _need(math.isfinite(rounded), "ACCESSOR_DECLARED_BOUND_RANGE")
        return rounded
    low, high = _INTEGER_RANGE[component]
    _need(low <= value <= high and (type(value) is int or value.is_integer()), "ACCESSOR_DECLARED_BOUND_RANGE")
    return int(value)


def _normalize(value: int, component: int) -> float:
    if component == 5120:
        return max(value / 127.0, -1.0)
    if component == 5122:
        return max(value / 32767.0, -1.0)
    return value / (255.0 if component == 5121 else 65535.0)


def decode_accessors(container: GLBContainer, *, max_values: int = MAX_DECODED_VALUES) -> tuple[AccessorValues, ...]:
    """Decode all accessors, rejecting aggregate scalar work before any unpack."""
    _need(type(max_values) is int and 0 <= max_values <= MAX_DECODED_VALUES, "ACCESSOR_VALUE_BUDGET")
    _need(type(container) is GLBContainer and type(container.binary) is bytes and
          len(container.binary) <= MAX_GLB_BYTES and type(container.accessors) is tuple and
          len(container.accessors) <= MAX_ACCESSORS and type(container.document) is MappingProxyType,
          "ACCESSOR_CONTAINER_TYPE")
    declarations = container.document.get("accessors", ())
    _need(type(declarations) is tuple and len(declarations) == len(container.accessors), "ACCESSOR_DECLARATION_BINDING")
    total = 0
    for layout, declared in zip(container.accessors, declarations):
        total += _admit_layout(layout, len(container.binary))
        _need(total <= max_values, "ACCESSOR_VALUE_LIMIT")
        _need(type(declared) is MappingProxyType and declared.get("componentType") == layout.component_type and
              declared.get("type") == layout.kind and declared.get("count") == layout.count and
              declared.get("normalized", False) == layout.normalized, "ACCESSOR_DECLARATION_BINDING")
    results = []
    for index, (layout, declared) in enumerate(zip(container.accessors, declarations)):
        reader = struct.Struct("<" + _FORMATS[layout.component_type])
        width = len(layout.component_offsets)
        low, high = [math.inf] * width, [-math.inf] * width
        values = []
        for element in range(layout.count):
            start = layout.offset + element * layout.byte_stride
            stored = tuple(reader.unpack_from(container.binary, start + offset)[0] for offset in layout.component_offsets)
            _need(all(math.isfinite(value) for value in stored), "ACCESSOR_NONFINITE_BINARY")
            for axis, value in enumerate(stored):
                low[axis], high[axis] = min(low[axis], value), max(high[axis], value)
            values.append(tuple(_normalize(value, layout.component_type) for value in stored)
                          if layout.normalized else stored)
        for key, actual in (("min", low), ("max", high)):
            if key in declared:
                bounds = declared[key]
                _need(type(bounds) is tuple and len(bounds) == width, "ACCESSOR_DECLARED_BOUND_SHAPE")
                expected = tuple(_bound(value, layout.component_type) for value in bounds)
                _need(expected == tuple(actual), "ACCESSOR_DECLARED_BOUND_MISMATCH")
        results.append(AccessorValues(index, layout.component_type, layout.kind, layout.normalized,
                                      tuple(values), tuple(low), tuple(high)))
    return tuple(results)
