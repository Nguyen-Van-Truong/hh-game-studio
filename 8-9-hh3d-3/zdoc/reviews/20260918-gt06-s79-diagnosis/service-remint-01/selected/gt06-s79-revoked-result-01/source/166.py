"""Independent repeat-export and aggregate-budget vectors; no native launch."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.pipeline import preflight


def png(pixel, *, level=6):
    def chunk(kind, payload=b''):
        return (struct.pack('>I', len(payload)) + kind + payload +
                struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(b'\0' + pixel, level)) + chunk(b'IEND'))


def fixture(*, padding=0, generator='first exporter', x=1.0, pixel=b'\x12\x34\x56\xff',
            compression=6, image_count=1):
    binary = bytearray(b'\0' * padding)
    positions = struct.pack('<9f', 0, 0, 0, x, 0, 0, 0, 1, 0)
    views = [{'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(positions)}]
    binary.extend(positions)
    images = []
    for index in range(image_count):
        binary.extend(b'\0' * (-len(binary) % 4))
        encoded = png(pixel, level=compression)
        views.append({'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(encoded)})
        binary.extend(encoded)
        images.append({'name': f'img_{index}', 'bufferView': len(views) - 1, 'mimeType': 'image/png'})
    document = {'asset': {'version': '2.0', 'generator': generator},
        'buffers': [{'byteLength': len(binary)}], 'bufferViews': views,
        'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3',
                       'min': [0,0,0], 'max': [x,1,0]}],
        'meshes': [{'name': 'triangle', 'primitives': [{'attributes': {'POSITION': 0}}]}],
        'nodes': [{'name': 'triangle', 'mesh': 0}], 'scenes': [{'nodes': [0]}], 'scene': 0,
        'images': images}
    text = json.dumps(document, separators=(',', ':')).encode()
    text += b' ' * (-len(text) % 4)
    binary.extend(b'\0' * (-len(binary) % 4))
    chunks = struct.pack('<II', len(text), 0x4e4f534a) + text
    chunks += struct.pack('<II', len(binary), 0x004e4942) + binary
    return struct.pack('<4sII', b'glTF', 2, len(chunks) + 12) + chunks


class PreflightTests(unittest.TestCase):
    def test_repeat_ignores_container_offsets_generator_and_lossless_png_encoding(self):
        original = fixture(compression=0)
        relocated = fixture(padding=64, generator='different exporter metadata', compression=9)
        self.assertNotEqual(hashlib.sha256(original).digest(), hashlib.sha256(relocated).digest())
        before, left = preflight.inspect_asset(original)
        after, right = preflight.inspect_asset(relocated)
        self.assertNotEqual(before['images'][0]['source_png_sha256'], after['images'][0]['source_png_sha256'])
        self.assertEqual(before['semantic_sha256'], after['semantic_sha256'])
        self.assertEqual(left, right)
        self.assertTrue(preflight.compare_repeat(left, right)['equivalent'])

    def test_actual_position_edit_changes_fingerprint_and_fails_repeat(self):
        before, left = preflight.inspect_asset(fixture())
        after, right = preflight.inspect_asset(fixture(x=1.01))
        self.assertNotEqual(before['semantic_sha256'], after['semantic_sha256'])
        with self.assertRaisesRegex(preflight.PreflightRejected, '^REPEAT_NUMERIC_DIFFERENCE$'):
            preflight.compare_repeat(left, right)

    def test_actual_texture_pixel_edit_changes_fingerprint_and_fails_repeat(self):
        before, left = preflight.inspect_asset(fixture())
        after, right = preflight.inspect_asset(fixture(pixel=b'\x13\x34\x56\xff'))
        self.assertNotEqual(before['semantic_sha256'], after['semantic_sha256'])
        with self.assertRaisesRegex(preflight.PreflightRejected, '^REPEAT_VALUE_DIFFERENCE$'):
            preflight.compare_repeat(left, right)

    def test_aggregate_cap_accepts_exact_boundary(self):
        with patch.object(preflight, 'MAX_DECODED_RGBA', 8):
            report, _ = preflight.inspect_asset(fixture(image_count=2))
        self.assertEqual(report['decoded_rgba_bytes'], 8)
        self.assertEqual(len(report['images']), 2)

    def test_aggregate_cap_rejects_before_over_budget_image_decode(self):
        # Each real PNG is independently valid. Keep allocations tiny while
        # proving the third decode never starts once two images consume the cap.
        with patch.object(preflight, 'MAX_DECODED_RGBA', 8), patch.object(
                preflight, 'decode_png', wraps=preflight.decode_png) as decode:
            with self.assertRaisesRegex(preflight.PreflightRejected, '^TEXTURE_AGGREGATE_CAP$'):
                preflight.inspect_asset(fixture(image_count=3))
        self.assertEqual(decode.call_count, 2)


if __name__ == '__main__':
    unittest.main()
