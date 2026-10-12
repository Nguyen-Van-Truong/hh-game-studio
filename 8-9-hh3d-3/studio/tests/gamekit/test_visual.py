"""Fast unit tests (no Godot) for gamekit W5: pngio, vcheck, shot validation."""

from __future__ import annotations

import os
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

from studio.gamekit import common as C
from studio.gamekit import pngio
from studio.gamekit import shot
from studio.gamekit import vcheck
from studio.gamekit.hh import build_parser


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def _wrap(width: int, height: int, color_type: int, scanlines: bytes, *, extra: bytes = b"", interlace: int = 0, bit_depth: int = 8, palette: bytes | None = None) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, interlace)
    parts = [pngio.SIGNATURE, _chunk(b"IHDR", ihdr)]
    if palette is not None:
        parts.append(_chunk(b"PLTE", palette))
    parts.append(extra)
    parts.append(_chunk(b"IDAT", zlib.compress(scanlines)))
    parts.append(_chunk(b"IEND", b""))
    return b"".join(parts)


def _rgb(width: int, height: int, seed: int = 3) -> pngio.Image:
    raw = bytes((index * seed + 11) % 256 for index in range(width * height * 3))
    return pngio.Image(width, height, "RGB", raw)


class PngioTest(unittest.TestCase):
    def test_roundtrip_modes_and_filters(self) -> None:
        images = [
            pngio.Image(3, 2, "L", bytes((i * 13 + 1) % 256 for i in range(6))),
            pngio.Image(3, 2, "LA", bytes((i * 9 + 2) % 256 for i in range(12))),
            pngio.Image(3, 2, "RGB", bytes((i * 5 + 7) % 256 for i in range(18))),
            pngio.Image(3, 2, "RGBA", bytes((i * 3 + 4) % 256 for i in range(24))),
            pngio.Image(4, 2, "P", bytes([0, 1, 2, 3, 1, 0, 2, 3]), bytes([10, 20, 30, 40, 50, 60, 70, 80, 90, 200, 210, 220])),
        ]
        for image in images:
            for ftype in (0, 1, 2, 3, 4):
                back = pngio.decode(pngio.encode(image, ftype))
                self.assertEqual(back.mode, image.mode)
                self.assertEqual(back.pixels, image.pixels)
                self.assertEqual(back.palette, image.palette)
        mixed = _rgb(3, 5)
        self.assertEqual(pngio.decode(pngio.encode(mixed, [0, 1, 2, 3, 4])).pixels, mixed.pixels)

    def test_hand_computed_filters(self) -> None:
        # 2x2 RGB. Row0 identical pixels, row1 chosen so Paeth is not Up.
        pixels = bytes([10, 20, 30, 10, 20, 30, 12, 22, 32, 40, 50, 60])
        image = pngio.Image(2, 2, "RGB", pixels)
        cases = {
            0: bytes([0, 10, 20, 30, 10, 20, 30, 0, 12, 22, 32, 40, 50, 60]),
            1: bytes([1, 10, 20, 30, 0, 0, 0, 1, 12, 22, 32, 28, 28, 28]),
            2: bytes([2, 10, 20, 30, 10, 20, 30, 2, 2, 2, 2, 30, 30, 30]),
            3: bytes([3, 10, 20, 30, 5, 10, 15, 3, 7, 12, 17, 29, 29, 29]),
            4: bytes([4, 10, 20, 30, 0, 0, 0, 4, 2, 2, 2, 28, 28, 28]),
        }
        for ftype, scanlines in cases.items():
            self.assertEqual(pngio.filtered_scanlines(image, ftype), scanlines)
            decoded = pngio.decode(_wrap(2, 2, 2, scanlines))
            self.assertEqual(decoded.pixels, pixels)

    def test_palette_transparency_and_chunks(self) -> None:
        palette = bytes([255, 0, 0, 0, 0, 255])
        scanlines = bytes([0, 0, 0, 1])
        trns = _chunk(b"tRNS", bytes([0, 128]))
        text = _chunk(b"tEXt", b"Comment\x00hi")
        blob = _wrap(1, 2, 3, scanlines, extra=trns + text, palette=palette)
        image = pngio.decode(blob)
        self.assertEqual(image.mode, "P")
        self.assertEqual(image.pixels, bytes([0, 1]))
        self.assertEqual(image.palette, palette)
        rgba = image.to_rgba()
        self.assertEqual(rgba[0:4], bytes([255, 0, 0, 0]))
        self.assertEqual(rgba[4:8], bytes([0, 0, 255, 128]))
        compressed = zlib.compress(scanlines)
        split = _chunk(b"IDAT", compressed[:4]) + _chunk(b"IDAT", compressed[4:])
        ihdr = struct.pack(">IIBBBBB", 1, 2, 8, 3, 0, 0, 0)
        parts = pngio.SIGNATURE + _chunk(b"IHDR", ihdr) + _chunk(b"PLTE", palette) + split + _chunk(b"IEND", b"")
        self.assertEqual(pngio.decode(parts).pixels, bytes([0, 1]))

    def test_rejects_interlace_depth_crc_and_critical(self) -> None:
        scanlines = bytes([0, 1, 2, 3])
        with self.assertRaises(pngio.PngError) as interlaced:
            pngio.decode(_wrap(1, 1, 2, scanlines, interlace=1))
        self.assertIn("interlaced", str(interlaced.exception))
        with self.assertRaises(pngio.PngError) as depth:
            pngio.decode(_wrap(1, 1, 2, scanlines, bit_depth=16))
        self.assertIn("8-bit", str(depth.exception))
        good = pngio.encode(pngio.Image(1, 1, "RGB", bytes([1, 2, 3])))
        # IHDR crc starts at byte 29.
        broken = bytearray(good)
        broken[29] ^= 0xFF
        with self.assertRaises(pngio.PngError) as crc:
            pngio.decode(bytes(broken))
        self.assertIn("CRC", str(crc.exception))
        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        bad_critical = pngio.SIGNATURE + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(scanlines))
        bad_critical += _chunk(b"FAIL", b"xx") + _chunk(b"IEND", b"")
        with self.assertRaises(pngio.PngError) as critical:
            pngio.decode(bad_critical)
        self.assertIn("critical", str(critical.exception))
        with self.assertRaises(pngio.PngError):
            pngio.decode(b"not a png")

    def test_gray_key_and_file_roundtrip(self) -> None:
        image = pngio.Image(2, 1, "L", bytes([8, 9]), transparency=b"\x00\x08")
        rgba = image.to_rgba()
        self.assertEqual(rgba[3], 0)
        self.assertEqual(rgba[7], 255)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "g.png"
            pngio.write(path, image, 2)
            self.assertEqual(pngio.read(path).pixels, image.pixels)


class VcheckTest(unittest.TestCase):
    def _pair(self, left: bytes, right: bytes, width: int = 2, height: int = 1) -> tuple[pngio.Image, pngio.Image]:
        return pngio.Image(width, height, "RGBA", left), pngio.Image(width, height, "RGBA", right)

    def test_metrics_tolerance_and_bbox(self) -> None:
        a, b = self._pair(bytes(8), bytes([0, 0, 0, 0, 10, 0, 0, 0]))
        same = vcheck.compare(a, a)
        self.assertEqual(same["status"], "PASS")
        self.assertEqual(same["changed_ratio"], 0.0)
        self.assertEqual(same["max_diff"], 0)
        self.assertIsNone(same["bbox"])
        within = vcheck.compare(a, b, pixel_tolerance=10)
        self.assertEqual(within["changed"], 0)
        self.assertEqual(within["max_diff"], 10)
        self.assertEqual(within["status"], "PASS")
        over = vcheck.compare(a, b, pixel_tolerance=8, threshold=0.0)
        self.assertEqual(over["status"], "FAIL")
        self.assertEqual(over["changed_ratio"], 0.5)
        self.assertEqual(over["max_diff"], 10)
        self.assertAlmostEqual(over["mean_abs_diff"], 1.25)
        self.assertEqual(over["bbox"], [1, 0, 1, 0])

    def test_threshold_boundary_and_size_mismatch(self) -> None:
        pixels = bytearray(100 * 4)
        other = bytearray(pixels)
        other[0] = 255
        hundred_a = pngio.Image(10, 10, "RGBA", bytes(pixels))
        hundred_b = pngio.Image(10, 10, "RGBA", bytes(other))
        edge = vcheck.compare(hundred_a, hundred_b, threshold=0.01, pixel_tolerance=0)
        self.assertEqual(edge["changed"], 1)
        self.assertEqual(edge["status"], "PASS")
        other[4] = 255
        two = pngio.Image(10, 10, "RGBA", bytes(other))
        fail = vcheck.compare(hundred_a, two, threshold=0.01, pixel_tolerance=0)
        self.assertEqual(fail["status"], "FAIL")
        self.assertGreater(fail["changed_ratio"], 0.01)
        mismatch = vcheck.compare(pngio.Image(1, 1, "L", b"\x01"), pngio.Image(2, 1, "L", b"\x01\x01"))
        self.assertEqual(mismatch["status"], "FAIL")
        self.assertEqual(mismatch["reason"], "size_mismatch")
        self.assertIsNone(mismatch["changed_ratio"])

    def test_expand_gray_and_palette_then_diff_file(self) -> None:
        gray = pngio.Image(1, 1, "L", b"\x0a")
        rgb = pngio.Image(1, 1, "RGB", bytes([10, 10, 10]))
        self.assertEqual(vcheck.compare(gray, rgb)["changed_ratio"], 0.0)
        pal = pngio.Image(1, 1, "P", b"\x00", bytes([10, 10, 10]))
        self.assertEqual(vcheck.compare(pal, rgb)["max_diff"], 0)
        diff = vcheck.diff_image(
            pngio.Image(1, 1, "RGB", bytes([1, 2, 3])),
            pngio.Image(1, 1, "RGB", bytes([4, 2, 0])),
        )
        self.assertEqual(diff.pixels, bytes([3, 0, 3]))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "a.png"
            b = root / "b.png"
            out = root / "diff.png"
            pngio.write(a, pngio.Image(1, 1, "RGB", bytes([0, 0, 0])))
            pngio.write(b, pngio.Image(1, 1, "RGB", bytes([9, 0, 0])))
            result = vcheck.compare_files(a, b, pixel_tolerance=0, threshold=0.0, diff_out=out, diff_when="fail")
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(pngio.read(out).pixels, bytes([9, 0, 0]))
            wide = root / "wide.png"
            pngio.write(wide, pngio.Image(2, 1, "L", b"\x00\x00"))
            skipped = root / "nope.png"
            mismatch = vcheck.compare_files(a, wide, diff_out=skipped)
            self.assertEqual(mismatch["reason"], "size_mismatch")
            self.assertFalse(skipped.exists())

    def test_blank_rules_and_expect_color(self) -> None:
        solid = pngio.Image(8, 8, "RGB", bytes([20, 30, 40]) * 64)
        info = vcheck.blank(solid)
        self.assertTrue(info["blank"])
        self.assertEqual(info["luminance_stddev"], 0.0)
        self.assertEqual(info["dominant_ratio"], 1.0)
        near = bytearray()
        for i in range(100):
            value = 100 if i < 50 else 101
            near.extend((value, value, value))
        self.assertTrue(vcheck.blank(pngio.Image(10, 10, "RGB", bytes(near)))["blank"])
        mostly = bytearray([0, 0, 0] * 199 + [255, 255, 255])
        dominant = vcheck.blank(pngio.Image(200, 1, "RGB", bytes(mostly)))
        self.assertTrue(dominant["blank"])
        self.assertGreaterEqual(dominant["dominant_ratio"], 0.995)
        self.assertGreaterEqual(dominant["luminance_stddev"], 2.0)
        less = bytearray([0, 0, 0] * 198 + [255, 255, 255] * 2)
        self.assertFalse(vcheck.blank(pngio.Image(200, 1, "RGB", bytes(less)))["blank"])
        checker = bytearray()
        for i in range(64):
            checker.extend((255, 255, 255) if i % 2 == 0 else (0, 0, 0))
        self.assertFalse(vcheck.blank(pngio.Image(8, 8, "RGB", bytes(checker)))["blank"])
        hit = vcheck.check_colors(solid, ["0,0,#141e28,0"])
        self.assertTrue(hit[0]["ok"])
        miss = vcheck.check_colors(solid, ["1,1,#ffffff,2"])
        self.assertFalse(miss[0]["ok"])
        self.assertEqual(miss[0]["got"], "#141e28")
        with self.assertRaises(C.GamekitError):
            vcheck.parse_expect_color("0,0,red,1")
        outside = vcheck.check_colors(solid, ["9,0,#000000,0"])
        self.assertIn("out of range", outside[0]["detail"])


class ShotHostTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self._old = os.environ.get("HH_GAMEKIT_STATE")
        os.environ["HH_GAMEKIT_STATE"] = str(self.root / "state")
        self.game = self.root / "game"
        self.game.mkdir()
        (self.game / "project.godot").write_text(
            'config_version=5\n\n[application]\n\nconfig/name="t"\nrun/main_scene="res://main.tscn"\n',
            encoding="utf-8",
        )
        (self.game / "main.tscn").write_text('[gd_scene format=3]\n\n[node name="Main" type="Node2D"]\n', encoding="utf-8")
        self.project = C.register_project(self.game, "game")

    def tearDown(self) -> None:
        if self._old is None:
            os.environ.pop("HH_GAMEKIT_STATE", None)
        else:
            os.environ["HH_GAMEKIT_STATE"] = self._old
        self.tmp.cleanup()

    def test_parsers_and_cli_flags(self) -> None:
        self.assertEqual(shot.parse_resolution("320x180"), (320, 180))
        self.assertEqual(shot.parse_at("10,30"), [10, 30])
        self.assertEqual(shot.parse_expect("Player,HUD/Score"), ["Player", "HUD/Score"])
        trace = shot.validate_trace({"fps": 60, "events": [{"frame": 0, "action": "paint", "pressed": True}]})
        self.assertEqual(trace["events"][0]["action"], "paint")
        with self.assertRaises(C.GamekitError):
            shot.parse_resolution("big")
        with self.assertRaises(C.GamekitError):
            shot.parse_frames(0)
        with self.assertRaises(C.GamekitError):
            shot.parse_expect("A/../B")
        with self.assertRaises(C.GamekitError):
            shot.validate_trace({"events": [{"frame": 0, "action": "bad name", "pressed": True}]})
        out = Path(r"C:\shots\hero.png")
        self.assertEqual(shot.frame_paths(out, [10, 30], True)[30], Path(r"C:\shots\hero_f30.png"))
        self.assertEqual(shot.frame_paths(out, [10], False)[10], out)
        parser = build_parser()
        args = parser.parse_args([
            "shot", "game", "--out", r"C:\shots\a.png", "--scene", "res://main.tscn", "--frames", "10",
            "--at", "10,30", "--resolution", "320x180", "--seed", "7", "--expect", "Player,HUD/Score",
            "--baseline", "res://tests/visual/a.png", "--threshold", "0.01", "--pixel-tolerance", "8",
            "--update-baseline", "--command-id", "w5.cmd.1", "--diff-out", r"C:\shots\a_diff.png",
        ])
        self.assertEqual(args.frames, 10)
        self.assertTrue(args.update_baseline)
        blank = parser.parse_args(["vcheck", "--blank", r"C:\shots\a.png", "--expect-color", "0,0,#ffffff,1"])
        self.assertEqual(blank.blank, r"C:\shots\a.png")
        pair = parser.parse_args(["vcheck", r"C:\a.png", r"C:\b.png", "--threshold", "0.01", "--pixel-tolerance", "8"])
        self.assertEqual(pair.a, r"C:\a.png")

    def test_refuses_without_launching_godot(self) -> None:
        def boom(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("godot launched")

        out = self.root / "shot.png"
        with mock.patch.object(C, "run_godot", boom), mock.patch.object(C, "run_godot_tool", boom):
            with self.assertRaises(C.GamekitError) as inside:
                shot.capture(self.project, self.game / "in.png", resolution=(320, 180), frames=2)
            self.assertEqual(inside.exception.code, "FORBIDDEN_PATH")
            with self.assertRaises(C.GamekitError) as missing:
                shot.capture(self.project, out, baseline="res://tests/a.png", resolution=(320, 180), frames=2)
            self.assertEqual(missing.exception.code, "BAD_REQUEST")
            C.Journal(self.project).append("w5.cmd.1", "0" * 64, {"ok": True, "status": "BASELINE_WRITTEN"})
            with self.assertRaises(C.GamekitError) as conflict:
                shot.capture(
                    self.project, out, baseline="res://tests/a.png", command_id="w5.cmd.1",
                    resolution=(320, 180), frames=2,
                )
            self.assertEqual(conflict.exception.code, "CONFLICT")
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
