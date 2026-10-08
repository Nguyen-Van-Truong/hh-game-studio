"""Engine-free checks for the closed Blender fixture producer."""
from __future__ import annotations

import copy
import json
import struct
import unittest
import zlib

from host.blender import fixture_content as content


class FixtureContentTests(unittest.TestCase):
    def test_recipe_is_fixed_and_validates_existing_contracts(self):
        recipe = content.recipe()
        report = content.validate_recipe(recipe)
        self.assertEqual(report["commands"], 31)
        self.assertEqual(report["keyframes"], 10)
        tampered = copy.deepcopy(recipe)
        tampered["commands"][0]["payload"]["size"][0] = 99
        with self.assertRaisesRegex(content.ContentError, "CONTENT_RECIPE_NOT_HOST_PRESET"):
            content.validate_recipe(tampered)

    def test_png_profile_checks_crc_dimensions_filters_and_cells(self):
        # The native producer's PNG is checked structurally here; this minimal
        # image must still be rejected because it is not the required 128x128
        # four-cell RGBA profile.
        raw = bytearray(b"\x89PNG\r\n\x1a\n")
        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
        for kind, payload in ((b"IHDR", ihdr), (b"IDAT", zlib.compress(b"\x00\x00\x00\x00\x00")), (b"IEND", b"")):
            raw.extend(struct.pack(">I", len(payload)) + kind + payload)
            raw.extend(struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))
        with self.assertRaisesRegex(content.ContentError, "CONTENT_PNG_PROFILE"):
            content.inspect_png(bytes(raw))
        broken = bytearray(raw)
        broken[29] ^= 1
        with self.assertRaisesRegex(content.ContentError, "CONTENT_PNG_CRC"):
            content.inspect_png(bytes(broken))

    def test_glb_rejects_external_buffers_and_old_box_only_export(self):
        # A syntactically valid header without the closed skin/walk profile is
        # rejected before any consumer can treat it as fixture content.
        json_chunk = json.dumps({"asset": {"version": "2.0"}}, separators=(",", ":")).encode()
        json_chunk += b" " * ((4 - len(json_chunk) % 4) % 4)
        binary = b"\0\0\0\0"
        raw = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(json_chunk) + 8 + len(binary))
        raw += struct.pack("<II", len(json_chunk), 0x4e4f534a) + json_chunk
        raw += struct.pack("<II", len(binary), 0x004e4942) + binary
        with self.assertRaisesRegex(content.ContentError, "CONTENT_GLB_EXTERNAL_BUFFER"):
            content.inspect_glb(raw)

    def test_publication_descriptor_does_not_grant_ack(self):
        self.assertFalse(content.PROJECT == "project.public")
        self.assertIn("scene.glb", content.FIXED_ARTIFACTS)
        self.assertEqual(content.SCHEMA, "HH-BLENDER-FIXTURE-CONTENT-1")


if __name__ == "__main__":
    unittest.main()
