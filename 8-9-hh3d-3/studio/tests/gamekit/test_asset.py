"""Fast unit tests (no Godot) for gamekit W7: licenses, LUFS, GLB/PNG/JPEG, ledger."""

from __future__ import annotations

import array
import json
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio.gamekit import asset as A
from studio.gamekit import common as C
from studio.gamekit import media_inspect as M
from studio.gamekit.selftests import w7_asset as W


ALLOWED_IDS = ("CC0-1.0", "self-made")
ATTRIBUTION_IDS: set[str] = set()
OWNER_REVIEW_IDS = (
    "CC-BY-3.0", "CC-BY-4.0", "OFL-1.1", "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "Unlicense",
)


def _wav(frames: bytes, rate: int, channels: int, bits: int, audio_format: int = 1) -> bytes:
    block = channels * (bits // 8)
    fmt = struct.pack("<HHIIHH", audio_format, channels, rate, rate * block, block, bits)
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(frames)) + frames
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _jpeg(width: int, height: int) -> bytes:
    # SOF0 with one component, preceded by a JFIF APP0 segment.
    app = b"JFIF\x00" + bytes([1, 1, 0, 0, 1, 0, 1, 0, 0])
    app_seg = b"\xff\xe0" + struct.pack(">H", 2 + len(app)) + app
    body = struct.pack(">BHHB", 8, height, width, 1) + bytes([1, 0x11, 0])
    sof = b"\xff\xc0" + struct.pack(">H", 2 + len(body)) + body
    return b"\xff\xd8" + app_seg + sof + b"\xff\xd9"


def _webp_lossless(width: int, height: int) -> bytes:
    bits = (width - 1) | ((height - 1) << 14)
    payload = bytes([0x2F]) + struct.pack("<I", bits)
    chunk = b"VP8L" + struct.pack("<I", len(payload)) + payload
    if len(payload) & 1:
        chunk += b"\x00"
    return b"RIFF" + struct.pack("<I", 4 + len(chunk)) + b"WEBP" + chunk


def _ogg_page(serial: int, granule: int, body: bytes, *, bos: bool, sequence: int) -> bytes:
    segs = []
    rest = len(body)
    while rest >= 255:
        segs.append(255)
        rest -= 255
    segs.append(rest)
    page = bytearray(b"OggS")
    page += bytes([0, 0x02 if bos else 0x00])
    page += struct.pack("<qIII", granule, serial, sequence, 0)
    page += bytes([len(segs)])
    page += bytes(segs)
    page += body
    return bytes(page)


class LicensePolicyTest(unittest.TestCase):
    def test_allow_list_and_attribution(self) -> None:
        table = A.load_licenses()
        ids = tuple(rec["id"] for rec in table["allowed"])
        self.assertEqual(ids, ALLOWED_IDS)
        attr = {rec["id"] for rec in table["allowed"] if rec.get("attribution_required")}
        self.assertEqual(attr, ATTRIBUTION_IDS)
        for rec in table["allowed"]:
            got = A.check_license(rec["id"], "Ada")
            self.assertEqual(got["id"], rec["id"])
            self.assertEqual(bool(got.get("attribution_required")), rec["id"] in ATTRIBUTION_IDS)

    def test_owner_review_ids_are_refused_until_owner_allows(self) -> None:
        table = A.load_licenses()
        self.assertEqual(tuple(rec["id"] for rec in table["owner_review"]), OWNER_REVIEW_IDS)
        for license_id in OWNER_REVIEW_IDS + ("cc-by-4.0",):
            with self.assertRaises(C.GamekitError) as cm:
                A.check_license(license_id, "Ada")
            self.assertEqual(cm.exception.code, "LICENSE_REJECTED", license_id)
            self.assertIn("owner rule 09-10", cm.exception.detail)

    def test_self_made_requires_author(self) -> None:
        self.assertEqual(A.check_license("self-made", "Ada")["id"], "self-made")
        with self.assertRaises(C.GamekitError) as cm:
            A.check_license("self-made", "  ")
        self.assertEqual(cm.exception.code, "VALIDATION_FAILED")

    def test_rejected_ids(self) -> None:
        cases = [
            ("CC-BY-NC-4.0", "non-commercial"),
            ("cc-by-nc-4.0", "non-commercial"),
            ("CC-BY-ND-4.0", "no-derivatives"),
            ("CC-BY-NC-SA-4.0", "non-commercial"),
            ("proprietary", "proprietary"),
            ("unknown", "unknown"),
            ("editorial", "editorial"),
            ("GPL-3.0-only", "copyleft"),
            ("LGPL-2.1-only", "copyleft"),
            ("AGPL-3.0-only", "copyleft"),
            ("CC-BY-SA-4.0", "share-alike"),
            ("NotARealLicense", "not allowed"),
        ]
        for license_id, needle in cases:
            with self.assertRaises(C.GamekitError) as cm:
                A.check_license(license_id, "Ada")
            self.assertEqual(cm.exception.code, "LICENSE_REJECTED", license_id)
            self.assertIn(needle, cm.exception.detail)


class LoudnessTest(unittest.TestCase):
    def test_48k_coefficients_match_bs1770_table(self) -> None:
        coeff = M.k_weight_coefficients(48000)
        pre = coeff["pre"]
        rlb = coeff["rlb"]
        self.assertAlmostEqual(pre[0], 1.53512485958697, places=8)
        self.assertAlmostEqual(pre[1], -2.69169618940638, places=8)
        self.assertAlmostEqual(pre[2], 1.19839281085285, places=8)
        self.assertAlmostEqual(pre[3], -1.69065929318241, places=8)
        self.assertAlmostEqual(pre[4], 0.73248077421585, places=8)
        self.assertEqual(rlb[0], 1.0)
        self.assertEqual(rlb[1], -2.0)
        self.assertEqual(rlb[2], 1.0)
        self.assertAlmostEqual(rlb[3], -1.99004745483398, places=8)
        self.assertAlmostEqual(rlb[4], 0.99007225036621, places=8)
        other = M.k_weight_coefficients(44100)["pre"]
        self.assertNotAlmostEqual(other[0], pre[0], places=4)

    def test_silence_is_gated(self) -> None:
        checks = M.inspect_media(W.silence_wav(), ".wav")
        self.assertTrue(checks["loudness_gated"])
        self.assertIsNone(checks["integrated_lufs"])
        self.assertEqual(checks["gating_blocks_used"], 0)
        self.assertIsNone(checks["peak_dbfs"])
        self.assertFalse(checks["clipping"])

    def test_sine_peak_and_lufs(self) -> None:
        checks = M.inspect_media(W.sine_wav(), ".wav")
        lufs = checks["integrated_lufs"]
        peak = checks["peak_dbfs"]
        print(f"MEASURED_LUFS {lufs} PEAK {peak}")
        self.assertIsInstance(lufs, float)
        self.assertLessEqual(abs(lufs - (-23.0)), 1.5)
        self.assertLessEqual(abs(peak - (-20.0)), 0.05)
        self.assertFalse(checks["loudness_gated"])
        self.assertGreater(checks["gating_blocks_used"], 0)
        self.assertFalse(checks["clipping"])
        self.assertTrue(checks["loudness_outside_window"])
        self.assertEqual(checks["sample_rate"], 48000)
        self.assertEqual(checks["channels"], 1)
        self.assertEqual(checks["encoding"], "pcm_s16")
        self.assertAlmostEqual(checks["duration_seconds"], 1.0, places=4)

    def test_pcm24_and_float32_peak(self) -> None:
        rate = 8000
        n = 16
        s24 = bytearray()
        value = int(round(0.1 * 8388608))
        for _ in range(n):
            s24 += struct.pack("<i", value)[:3]
        checks = M.inspect_media(_wav(bytes(s24), rate, 1, 24), ".wav")
        self.assertEqual(checks["encoding"], "pcm_s24")
        self.assertLessEqual(abs(checks["peak_dbfs"] - (-20.0)), 0.05)
        floats = array.array("f", [0.1] * n)
        fchecks = M.inspect_media(_wav(floats.tobytes(), rate, 1, 32, audio_format=3), ".wav")
        self.assertEqual(fchecks["encoding"], "pcm_f32")
        self.assertLessEqual(abs(fchecks["peak_dbfs"] - (-20.0)), 0.05)


class ImageAndModelTest(unittest.TestCase):
    def test_png_and_jpeg_headers(self) -> None:
        png = M.inspect_media(W.png_rgb(64, 32), ".png")
        self.assertEqual((png["width"], png["height"]), (64, 32))
        self.assertTrue(png["power_of_two"])
        jpeg = M.inspect_media(_jpeg(64, 32), ".jpg")
        self.assertEqual((jpeg["width"], jpeg["height"]), (64, 32))
        self.assertEqual(jpeg["format"], "jpeg")
        webp = M.inspect_media(_webp_lossless(64, 32), ".webp")
        self.assertEqual((webp["width"], webp["height"]), (64, 32))
        big = M.inspect_media(W.png_rgb(8193, 8), ".png")
        self.assertTrue(any("8192" in w for w in big["warnings"]))

    def test_glb_triangle(self) -> None:
        checks = M.inspect_media(W.triangle_glb(), ".glb")
        self.assertEqual(checks["triangles"], 1)
        self.assertEqual(checks["vertices"], 3)
        self.assertEqual(checks["meshes"], 1)
        self.assertEqual(checks["nodes"], 1)
        self.assertEqual(checks["bounds_min"], [0.0, 0.0, 0.0])
        self.assertEqual(checks["bounds_max"], [1.0, 1.0, 0.0])
        self.assertFalse(checks["bounds_over_200m"])
        self.assertFalse(checks["bounds_under_0_005m"])
        self.assertEqual(checks["other_modes"], [])

    def test_gltf_external_uri_rejected(self) -> None:
        external = json.dumps({"asset": {"version": "2.0"}, "buffers": [{"uri": "buf.bin", "byteLength": 4}]}).encode()
        with self.assertRaises(C.GamekitError) as cm:
            M.inspect_media(external, ".gltf")
        self.assertEqual(cm.exception.code, "VALIDATION_FAILED")
        self.assertIn("external", cm.exception.detail)
        embedded = {
            "asset": {"version": "2.0"},
            "buffers": [{"uri": "data:application/octet-stream;base64,AAAA", "byteLength": 3}],
        }
        checks = M.inspect_media(json.dumps(embedded).encode(), ".gltf")
        self.assertEqual(checks["external_uris"], [])
        self.assertEqual(checks["format"], "gltf")

    def test_ogg_duration_from_granule(self) -> None:
        head = b"OpusHead" + bytes([1, 1]) + struct.pack("<H", 312) + struct.pack("<IH", 48000, 0) + bytes([0])
        blob = _ogg_page(1, 0, head, bos=True, sequence=0) + _ogg_page(1, 48312, b"\x00", bos=False, sequence=1)
        checks = M.inspect_media(blob, ".ogg")
        self.assertEqual(checks["codec"], "opus")
        self.assertAlmostEqual(checks["duration_seconds"], 1.0, places=3)


class _TempProject(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self._old_state = os.environ.get("HH_GAMEKIT_STATE")
        os.environ["HH_GAMEKIT_STATE"] = str(self.root / "state")
        self.game = self.root / "game"
        self.game.mkdir()
        (self.game / "project.godot").write_text('config_version=5\n\n[application]\n\nconfig/name="game"\n', encoding="utf-8")
        self.project = C.register_project(self.game, "game")

    def tearDown(self) -> None:
        if self._old_state is None:
            os.environ.pop("HH_GAMEKIT_STATE", None)
        else:
            os.environ["HH_GAMEKIT_STATE"] = self._old_state
        self.tmp.cleanup()


def _fake_import(root, force=False):
    root = Path(root)
    targets = [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in A.IMPORTABLE_EXTS]
    for path in targets:
        side = Path(str(path) + ".import")
        if not side.exists():
            side.write_text('[remap]\nimporter="fake"\n', encoding="utf-8")
    return {"imported": True, "exit_code": 0, "seconds": 0.0, "timed_out": False, "errors": [], "warnings": []}


class LedgerContractTest(_TempProject):
    def test_add_replay_conflict_and_verify_without_godot(self) -> None:
        src = self.root / "hero.png"
        src.write_bytes(W.png_rgb(8, 8))
        with patch("studio.gamekit.asset.scene.refresh_import", side_effect=_fake_import) as mocked:
            receipt = A.add(self.project, src, "res://assets/hero.png", "CC0-1.0", "Ada", command_id="w7.unit.1")
            self.assertTrue(mocked.called)
            self.assertEqual(receipt["status"], "COMMITTED")
            self.assertTrue((self.game / "assets" / "hero.png.import").is_file())
            again = A.add(self.project, src, "res://assets/hero.png", "CC0-1.0", "Ada", command_id="w7.unit.1")
            self.assertTrue(again.get("replayed"))
            with self.assertRaises(C.GamekitError) as cm:
                A.add(self.project, src, "res://assets/hero.png", "CC0-1.0", "Ada", command_id="w7.unit.1", notes="nope")
            self.assertEqual(cm.exception.code, "CONFLICT")
            with self.assertRaises(C.GamekitError) as cm:
                A.add(self.project, src, "res://assets/other.png", "CC-BY-NC-4.0", "Ada", command_id="w7.unit.nc")
            self.assertEqual(cm.exception.code, "LICENSE_REJECTED")
            self.assertFalse((self.game / "assets" / "other.png").exists())
        listed = A.list_assets(self.project)
        self.assertEqual(listed["count"], 1)
        clean = A.verify(self.project)
        self.assertTrue(clean["ok"], clean)
        loose = self.game / "assets" / "loose.png"
        loose.write_bytes(b"loose")
        dirty = A.verify(self.project)
        self.assertFalse(dirty["ok"])
        self.assertIn("res://assets/loose.png", dirty["untracked"])
        target = self.game / "assets" / "hero.png"
        target.write_bytes(target.read_bytes() + b"\x00")
        tampered = A.verify(self.project)
        self.assertFalse(tampered["ok"])
        self.assertTrue(any("sha256 mismatch" in p for p in tampered["problems"]))

    def test_credits_groups_attribution_and_ai(self) -> None:
        text = A.render_credits([
            {"res": "res://assets/a.png", "license": "CC0-1.0", "author": "Ada", "ai_generated": False, "source_url": ""},
            {"res": "res://assets/b.png", "license": "CC-BY-4.0", "author": "Bea", "ai_generated": True,
             "source_url": "https://example.com/b"},
        ])
        self.assertIn("## CC0 1.0 Universal (`CC0-1.0`)", text)
        self.assertIn("## Creative Commons Attribution 4.0 (`CC-BY-4.0`)", text)
        self.assertIn("Attribution is required", text)
        self.assertIn("Ada", text)
        self.assertIn("https://example.com/b", text)
        self.assertIn("## AI-generated content", text)
        self.assertIn("res://assets/b.png", text.split("## AI-generated content", 1)[1])
        self.assertNotIn("res://assets/a.png", text.split("## AI-generated content", 1)[1])
        ledger = {
            "schema": "hh-gamekit-assets-1",
            "assets": [
                {"res": "res://assets/a.png", "sha256": "abc", "bytes": 1, "license": "CC-BY-4.0",
                 "author": "Bea", "source_url": "", "ai_generated": True, "notes": "", "added_at": "t", "checks": {}},
            ],
        }
        C.atomic_write_json(self.project.res_to_path("res://hh_assets.json"), ledger)
        receipt = A.credits(self.project, "w7.credits.unit")
        self.assertEqual(receipt["status"], "COMMITTED")
        body = self.project.res_to_path("res://CREDITS.md").read_text(encoding="utf-8")
        self.assertIn("Bea", body)
        self.assertIn("AI-generated content", body)
        replayed = A.credits(self.project, "w7.credits.unit")
        self.assertTrue(replayed.get("replayed"))
        ledger["assets"].append(dict(ledger["assets"][0], res="res://assets/c.png"))
        C.atomic_write_json(self.project.res_to_path("res://hh_assets.json"), ledger)
        with self.assertRaises(C.GamekitError) as cm:
            A.credits(self.project, "w7.credits.unit")
        self.assertEqual(cm.exception.code, "CONFLICT")


if __name__ == "__main__":
    unittest.main()
