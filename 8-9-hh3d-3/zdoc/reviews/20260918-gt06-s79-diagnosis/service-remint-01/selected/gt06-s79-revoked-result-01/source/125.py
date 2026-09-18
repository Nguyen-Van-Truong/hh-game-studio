"""Pure bounded admission for original GT05 GLB bytes before native parsers.

This is not a publication certificate. Khronos, actual producer/Godot readback,
source ownership and process evidence are independent required stages.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from .glb_container import inspect_glb
from .accessor_values import decode_accessors
from .png_decode import decode_png
from .glb_semantics import validate_semantics

MAX_DECODED_RGBA = 128 * 1024 * 1024


class PreflightRejected(ValueError):
    pass


def plain(value):
    if hasattr(value, 'items'):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return value


def canonical(value):
    # This private hash domain is explicitly JSON sort/compact, not protocol JCS.
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def inspect_asset(raw: bytes):
    container = inspect_glb(raw)
    values = decode_accessors(container)
    core_semantics = validate_semantics(container, values)
    document = container.document
    image_rows = []
    remaining = MAX_DECODED_RGBA
    for source in document.get('images', ()):
        view = document['bufferViews'][source['bufferView']]
        offset = view.get('byteOffset', 0)
        encoded = container.binary[offset:offset + view['byteLength']]
        # PNG dimensions are bounded before inflation by the independent decoder.
        # Check aggregate allocation before calling it as well (IHDR fixed bytes).
        if len(encoded) < 24:
            raise PreflightRejected('TEXTURE_HEADER')
        width = int.from_bytes(encoded[16:20], 'big')
        height = int.from_bytes(encoded[20:24], 'big')
        if width * height * 4 > remaining:
            raise PreflightRejected('TEXTURE_AGGREGATE_CAP')
        image = decode_png(encoded)
        remaining -= len(image.rgba8)
        image_rows.append({'name': source.get('name'), 'width': image.width,
            'height': image.height, 'rgba8_sha256': image.rgba8_sha256,
            'source_png_sha256': image.source_sha256})
    # Remove file-layout and generator metadata from the repeat-export signature.
    # All accessor numbers, node/skin/channel/index relationships and decoded
    # pixels remain; this fingerprint does not equate reordered topology.
    semantic = {key: plain(value) for key, value in document.items()
                if key not in ('asset', 'buffers', 'bufferViews', 'accessors', 'images')}
    semantic['accessors'] = [{'type': item.kind, 'component_type': item.component_type,
        'normalized': item.normalized, 'values': item.values} for item in values]
    semantic['images'] = [{key: value for key, value in item.items() if key != 'source_png_sha256'}
                          for item in image_rows]
    fingerprint = hashlib.sha256(canonical(semantic)).hexdigest()
    report = {'schema': 'HH-GT05-PREFLIGHT-1', 'artifact_sha256': container.sha256,
        'artifact_bytes': len(raw), 'accessors': len(values),
        'decoded_scalars': sum(len(row) for item in values for row in item.values),
        'decoded_rgba_bytes': MAX_DECODED_RGBA - remaining, 'images': image_rows,
        'semantic_sha256': fingerprint,
        'semantic_hash_domain': 'decoded-core-indexed-v1/json-sort-compact',
        'core_semantics': plain(asdict(core_semantics)),
        'formal_acceptance': False, 'public_ack': False}
    return report, semantic


def compare_repeat(left, right):
    """Strict repeat-export comparison; a stricter tolerance than asset parity.

    Native cross-engine parity separately uses asset-profile's TRS tolerances.
    Ignore container layout/PNG encoding only; changed semantic data must fail.
    """
    def compare(a, b):
        if type(a) in (int, float) and type(b) in (int, float):
            if abs(a - b) > 1e-7:
                raise PreflightRejected('REPEAT_NUMERIC_DIFFERENCE')
        elif isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)):
            if len(a) != len(b):
                raise PreflightRejected('REPEAT_SHAPE_DIFFERENCE')
            for x, y in zip(a, b):
                compare(x, y)
        elif type(a) is dict and type(b) is dict:
            if a.keys() != b.keys():
                raise PreflightRejected('REPEAT_FIELDS_DIFFERENCE')
            for key in a:
                compare(a[key], b[key])
        elif type(a) is not type(b) or a != b:
            raise PreflightRejected('REPEAT_VALUE_DIFFERENCE')
    compare(left, right)
    return {'equivalent': True, 'numeric_tolerance': 1e-7, 'formal_acceptance': False}
