"""Real tiny PNG vectors; no engine/import/publication acceptance claim."""
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import zlib

from pipeline import png_decode as png

SIGNATURE = b"\x89PNG\r\n\x1a\n"


def chunk(kind, data=b""):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def header(width=1, height=1, *, depth=8, color=6, compression=0, filtering=0, interlace=0):
    return chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, depth, color, compression, filtering, interlace))


def vector(scanlines=b"\0\x12\x34\x56\x78", *, compressed=None, ihdr=None):
    return SIGNATURE + (header() if ihdr is None else ihdr) + chunk(
        b"IDAT", zlib.compress(scanlines) if compressed is None else compressed) + chunk(b"IEND")


class PNGTests(unittest.TestCase):
    def rejects(self, raw, code=None):
        with self.assertRaises(png.PNGRejected) as caught:
            png.decode_png(raw)
        if code is not None:
            self.assertEqual(str(caught.exception), code)

    def test_profile_limits_and_explicit_no_ancillary(self):
        profile = json.loads((Path(__file__).resolve().parents[1] / "asset-profile.json").read_bytes())
        self.assertEqual(png.MAX_PNG_BYTES, profile["limits"]["glb_bytes"])
        self.assertEqual(png.MAX_DIMENSION, profile["limits"]["texture_dimension"])
        self.assertEqual(png.MAX_RGBA_BYTES, profile["limits"]["texture_decoded_rgba8_bytes_total"])
        self.assertEqual(png.SUPPORTED_ANCILLARY, ())

    def test_rgba_preserves_alpha_and_hashes_without_io(self):
        raw = vector()
        with patch("builtins.open", side_effect=AssertionError("no I/O")):
            image = png.decode_png(raw)
        self.assertEqual((image.width, image.height, image.source_color_type), (1, 1, 6))
        self.assertEqual(image.rgba8, bytes.fromhex("12345678"))
        self.assertEqual(image.source_sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(image.rgba8_sha256, hashlib.sha256(image.rgba8).hexdigest())
        with self.assertRaises(FrozenInstanceError):
            image.width = 2

    def test_rgb_adds_opaque_alpha(self):
        image = png.decode_png(vector(b"\0\xff\0\x80\x01\x02\x03", ihdr=header(2, color=2)))
        self.assertEqual(image.rgba8, bytes.fromhex("ff0080ff010203ff"))

    def test_all_five_filters_reconstruct_known_rgba_rows(self):
        # Authored byte vectors, including wraparound and both left/up histories.
        expected = bytes([10, 20, 30, 40, 200, 150, 100, 50, 5, 30, 250, 10, 250, 2, 80, 255])
        rows = {
            0: ([10, 20, 30, 40, 200, 150, 100, 50], [5, 30, 250, 10, 250, 2, 80, 255]),
            1: ([10, 20, 30, 40, 190, 130, 70, 10], [5, 30, 250, 10, 245, 228, 86, 245]),
            2: ([10, 20, 30, 40, 200, 150, 100, 50], [251, 10, 220, 226, 50, 108, 236, 205]),
            3: ([10, 20, 30, 40, 195, 140, 85, 30], [0, 20, 235, 246, 148, 168, 161, 225]),
            4: ([10, 20, 30, 40, 190, 130, 70, 10], [251, 10, 220, 226, 50, 108, 86, 245]),
        }
        for mode, (first, second) in rows.items():
            with self.subTest(mode=mode):
                raw = vector(bytes([mode, *first, mode, *second]), ihdr=header(2, 2))
                self.assertEqual(png.decode_png(raw).rgba8, expected)

    def test_rgb_filter_uses_three_byte_pixel_and_resets_history(self):
        raw = vector(bytes([1, 1, 2, 3, 3, 3, 3, 2, 9, 18, 27, 36, 45, 54]), ihdr=header(2, 2, color=2))
        expected = bytes([1, 2, 3, 255, 4, 5, 6, 255, 10, 20, 30, 255, 40, 50, 60, 255])
        self.assertEqual(png.decode_png(raw).rgba8, expected)
        self.assertEqual(png.decode_png(vector()).rgba8, bytes.fromhex("12345678"))

    def test_idat_may_split_inside_zlib_header_or_checksum(self):
        compressed = zlib.compress(b"\0\x12\x34\x56\x78")
        raw = SIGNATURE + header() + chunk(b"IDAT")
        raw += b"".join(chunk(b"IDAT", bytes([byte])) for byte in compressed) + chunk(b"IDAT") + chunk(b"IEND")
        self.assertEqual(png.decode_png(raw).rgba8, bytes.fromhex("12345678"))

    def test_signature_types_input_limit_and_truncated_chunks(self):
        raw = vector()
        for bad in (bytearray(raw), memoryview(raw), None, raw[:7], b"X" + raw[1:],
                    raw + b"\0" * png.MAX_PNG_BYTES, raw[:-1], raw[:-6], raw[:-12]):
            with self.subTest(kind=type(bad).__name__, size=len(bad) if bad is not None else None):
                self.rejects(bad)
        self.rejects(SIGNATURE + struct.pack(">I", 0x80000000) + b"IHDR" + raw[16:], "PNG_CHUNK_BOUNDS")

    def test_crc_checked_for_every_kind_before_inflate(self):
        chunks = [header(), chunk(b"IDAT", zlib.compress(b"\0\x12\x34\x56\x78")), chunk(b"IEND")]
        for index in range(3):
            changed = chunks.copy()
            changed[index] = changed[index][:-1] + bytes([changed[index][-1] ^ 1])
            with self.subTest(index=index), patch.object(png, "_inflate", side_effect=AssertionError("late CRC")):
                self.rejects(SIGNATURE + b"".join(changed), "PNG_CRC")

    def test_dimensions_and_rgba_budget_reject_before_inflate(self):
        for width, height in ((0, 1), (1, 0), (4097, 1), (1, 4097), (0xFFFFFFFF, 0xFFFFFFFF)):
            with self.subTest(size=(width, height)), patch.object(png, "_inflate", side_effect=AssertionError("allocation")):
                self.rejects(vector(ihdr=header(width, height)), "PNG_DIMENSION_LIMIT")
        with patch.object(png, "MAX_RGBA_BYTES", 4), patch.object(png, "_inflate", side_effect=AssertionError("allocation")):
            self.rejects(vector(ihdr=header(2, 1)), "PNG_RGBA_LIMIT")

    def test_unsupported_color_depth_interlace_and_methods(self):
        for options in ({"color": 0}, {"color": 3}, {"color": 4}, {"color": 7}, {"depth": 16},
                        {"depth": 1}, {"interlace": 1}, {"compression": 1}, {"filtering": 1}):
            with self.subTest(options=options):
                self.rejects(vector(ihdr=header(**options)), "PNG_PROFILE_UNSUPPORTED")

    def test_no_ancillary_unknown_critical_apng_or_profile_chunks(self):
        tail = chunk(b"IDAT", zlib.compress(b"\0\x12\x34\x56\x78")) + chunk(b"IEND")
        for kind in (b"PLTE", b"tRNS", b"acTL", b"fcTL", b"fdAT", b"gAMA", b"sRGB", b"iCCP", b"cHRM",
                     b"sBIT", b"pHYs", b"tEXt", b"ABCD"):
            with self.subTest(kind=kind):
                self.rejects(SIGNATURE + header() + chunk(kind) + tail, "PNG_CHUNK_UNSUPPORTED_OR_ORDER")
        for kind in (b"ABcD", b"1234"):
            self.rejects(SIGNATURE + header() + chunk(kind) + tail, "PNG_CHUNK_TYPE")

    def test_chunk_order_and_trailing_bytes_are_closed(self):
        data = chunk(b"IDAT", zlib.compress(b"\0\x12\x34\x56\x78"))
        end = chunk(b"IEND")
        for body in (data + header() + end, header() + header() + data + end, header() + end + data,
                     header() + data + chunk(b"IEND", b"x"), header() + data + end + b"x",
                     header() + data + end + data, header() + data + chunk(b"tEXt") + data + end,
                     header() + chunk(b"IDAT") + end, header() + data):
            with self.subTest(size=len(body)):
                self.rejects(SIGNATURE + body)

    def test_chunk_count_budget(self):
        raw = SIGNATURE + header() + chunk(b"IDAT", zlib.compress(b"\0\x12\x34\x56\x78"))
        raw += chunk(b"IDAT") * png.MAX_CHUNKS + chunk(b"IEND")
        self.rejects(raw, "PNG_CHUNK_LIMIT")

    def test_truncated_trailing_concatenated_raw_and_dictionary_streams(self):
        compressed = zlib.compress(b"\0\x12\x34\x56\x78")
        dictionary = zlib.compressobj(zdict=b"sample dictionary")
        with_dictionary = dictionary.compress(b"\0\x12\x34\x56\x78") + dictionary.flush()
        for data in (compressed[:-1], compressed + b"x", compressed + compressed,
                     compressed[2:-4], with_dictionary, b"broken"):
            with self.subTest(stream=data.hex()[:32]):
                self.rejects(vector(compressed=data))
        bad_checksum = compressed[:-1] + bytes([compressed[-1] ^ 1])
        self.rejects(vector(compressed=bad_checksum), "PNG_ZLIB_STREAM")

    def test_bomb_long_short_and_invalid_filter(self):
        self.rejects(vector(b"\0" * 1_048_576), "PNG_INFLATE_LIMIT")
        self.rejects(vector(b"\0" * 6), "PNG_INFLATE_LIMIT")
        self.rejects(vector(b"\0" * 4), "PNG_SCANLINE_LENGTH")
        self.rejects(vector(b"\5\0\0\0\0"), "PNG_FILTER_TYPE")


if __name__ == "__main__":
    unittest.main()
