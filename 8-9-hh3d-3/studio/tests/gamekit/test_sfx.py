"""Host tests for deterministic sfx PCM. No Godot."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio.gamekit import common as C
from studio.gamekit import sfx


ROOT = Path(__file__).resolve().parents[3]


def _invoke(argv: list[str]) -> tuple[int, dict]:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sfx.register(sub)
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except C.GamekitError as exc:
        return 2, exc.to_json()
    return (0 if result.get("ok", False) else 1), result


class SfxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.out = self.root / "out"
        self.out.mkdir()
        self._old_state = os.environ.get("HH_GAMEKIT_STATE")
        os.environ["HH_GAMEKIT_STATE"] = str(self.root / "state")
        self._junctions: list[Path] = []

    def tearDown(self) -> None:
        for link in self._junctions:
            try:
                os.rmdir(link)
            except OSError:
                pass
        if self._old_state is None:
            os.environ.pop("HH_GAMEKIT_STATE", None)
        else:
            os.environ["HH_GAMEKIT_STATE"] = self._old_state
        self.tmp.cleanup()

    def _wav(self, name: str = "click.wav") -> Path:
        return self.out / name

    def test_presets_are_synthetic_and_unlicensed(self) -> None:
        listed = sfx.presets()
        self.assertTrue(listed["ok"])
        self.assertIsNone(listed["license"])
        self.assertFalse(listed["recorded"])
        self.assertFalse(listed["foley"])
        self.assertEqual([row["id"] for row in listed["presets"]], list(sfx.PRESET_IDS))
        self.assertIn("not recordings", listed["origin"].lower())
        self.assertIn("not foley", listed["origin"].lower())
        self.assertEqual(listed["import_via"], "hh asset add")

    def test_same_seed_is_byte_stable_and_under_full_scale(self) -> None:
        first, first_meta = sfx.synthesize("ui_click", seed=7)
        second, second_meta = sfx.synthesize("ui_click", seed=7)
        self.assertEqual(first, second)
        self.assertEqual(first_meta["sha256"], second_meta["sha256"])
        self.assertNotIn("_codes", first_meta)
        self.assertLess(first_meta["peak_dbfs"], -0.1)
        self.assertLessEqual(first_meta["peak_dbfs"], -6.0 + 0.2)
        _rate, codes = sfx._decode_wav(first)
        self.assertEqual(codes[0], 0)
        self.assertEqual(codes[-1], 0)
        self.assertLess(max(abs(code) for code in codes), 32767)
        other, _other_meta = sfx.synthesize("ui_click", seed=8)
        self.assertNotEqual(first, other)

    def test_every_preset_stays_deterministic_and_unclipped(self) -> None:
        for preset in sfx.PRESET_IDS:
            for rate in (22050, 48000):
                for peak in (-24.0, -1.0):
                    wav, meta = sfx.synthesize(preset, sample_rate=rate, peak_dbfs=peak)
                    again, again_meta = sfx.synthesize(preset, sample_rate=rate, peak_dbfs=peak)
                    self.assertEqual(wav, again, preset)
                    self.assertEqual(meta["sha256"], again_meta["sha256"])
                    self.assertLess(meta["peak_dbfs"], -0.1)
                    self.assertFalse(meta["provenance"]["foley"])
                    self.assertIsNone(meta["provenance"]["license"])
                    self.assertLessEqual(len(wav), 262144)

    def test_generate_readback_and_replace(self) -> None:
        path = self._wav()
        with patch("studio.gamekit.asset.add", side_effect=AssertionError("asset add bypassed")):
            result = sfx.generate(path, "pickup", seed=3)
        self.assertTrue(result["ok"])
        self.assertEqual(result["readback"], "DECODE_SHA_MATCH")
        self.assertFalse(result["checks"]["clipping"])
        self.assertLess(result["checks"]["peak_dbfs"], -0.1)
        self.assertEqual(result["sha256"], C.sha256_file(path))
        self.assertEqual(path.read_bytes(), sfx.synthesize("pickup", seed=3)[0])
        self.assertIsNone(result["provenance"]["license"])
        self.assertIn("does not assign a license", result["import_via"]["license_note"])
        self.assertEqual(result["import_via"]["command"], "hh asset add")
        before = path.read_bytes()
        with self.assertRaises(C.GamekitError) as bad_preset:
            sfx.generate(path, "nope")
        self.assertEqual(bad_preset.exception.code, "BAD_REQUEST")
        self.assertEqual(path.read_bytes(), before)
        with self.assertRaises(C.GamekitError) as blocked:
            sfx.generate(path, "pickup", seed=9)
        self.assertEqual(blocked.exception.code, "CONFLICT")
        self.assertEqual(path.read_bytes(), before)
        replaced = sfx.generate(path, "pickup", seed=9, replace=True)
        self.assertTrue(replaced["replaced"])
        self.assertNotEqual(replaced["sha256"], result["sha256"])
        self.assertEqual(path.read_bytes(), sfx.synthesize("pickup", seed=9)[0])

    def test_failed_readback_removes_or_restores(self) -> None:
        fresh = self._wav("fresh.wav")
        with patch.object(sfx, "_readback", side_effect=C.GamekitError("READBACK_MISMATCH", "boom")):
            with self.assertRaises(C.GamekitError) as created:
                sfx.generate(fresh, "ui_click")
        self.assertEqual(created.exception.code, "READBACK_MISMATCH")
        self.assertFalse(fresh.exists())
        original = b"keep-these-bytes"
        existing = self._wav("existing.wav")
        existing.write_bytes(original)
        with patch.object(sfx, "_readback", side_effect=C.GamekitError("READBACK_MISMATCH", "boom")):
            with self.assertRaises(C.GamekitError):
                sfx.generate(existing, "ui_click", replace=True)
        self.assertEqual(existing.read_bytes(), original)

    def test_invalid_params_do_not_write(self) -> None:
        path = self._wav("nope.wav")
        cases = (
            {"preset": "nope"},
            {"preset": "ui_click", "duration": 10},
            {"preset": "ui_click", "duration": 0.001},
            {"preset": "ui_click", "sample_rate": 96000},
            {"preset": "ui_click", "peak_dbfs": 0},
            {"preset": "ui_click", "peak_dbfs": -30},
            {"preset": "ui_click", "seed": -1},
            {"preset": "ui_click", "seed": True},
            {"preset": "ui_click", "duration": float("nan")},
        )
        for kwargs in cases:
            with self.assertRaises(C.GamekitError):
                sfx.generate(path, **kwargs)
            self.assertFalse(path.exists(), kwargs)

    def test_path_refusals_do_not_write(self) -> None:
        with self.assertRaises(C.GamekitError) as relative:
            sfx.generate("click.wav", "ui_click")
        self.assertEqual(relative.exception.code, "BAD_PATH")
        missing = self.root / "missing-dir" / "click.wav"
        with self.assertRaises(C.GamekitError) as parent:
            sfx.generate(missing, "ui_click")
        self.assertEqual(parent.exception.code, "BAD_PATH")
        self.assertFalse(missing.exists())
        secret = self.out / "private.raw"
        with self.assertRaises(C.GamekitError) as raw:
            sfx.generate(secret, "ui_click")
        self.assertEqual(raw.exception.code, "FORBIDDEN_PATH")
        self.assertFalse(secret.exists())
        local = C.STUDIO_DIR / ".local" / "hh-sfx-must-not-write.wav"
        self.assertFalse(local.exists())
        with self.assertRaises(C.GamekitError) as local_err:
            sfx.generate(local, "ui_click")
        self.assertEqual(local_err.exception.code, "FORBIDDEN_PATH")
        self.assertFalse(local.exists())
        blocked = Path(r"D:\dataDiskD\superagent-grokdo\hh-sfx-must-not-write.wav")
        self.assertFalse(blocked.exists())
        with self.assertRaises(C.GamekitError) as game:
            sfx.generate(blocked, "ui_click")
        self.assertEqual(game.exception.code, "FORBIDDEN_PATH")
        self.assertFalse(blocked.exists())
        forbidden = self.root / "godot" / "dogfood" / "superfighters" / "a.wav"
        with self.assertRaises(C.GamekitError) as scope:
            sfx.generate(forbidden, "ui_click")
        self.assertEqual(scope.exception.code, "FORBIDDEN_PATH")
        self.assertFalse(forbidden.exists())
        self.assertFalse((self.root / "godot").exists())

    def test_refuses_a_registered_project_and_a_junction(self) -> None:
        game = self.root / "game"
        game.mkdir()
        (game / "project.godot").write_text('config_version=5\nconfig/name="game"\n', encoding="utf-8")
        C.register_project(game, "game")
        inside = game / "click.wav"
        with self.assertRaises(C.GamekitError) as project:
            sfx.generate(inside, "impact")
        self.assertEqual(project.exception.code, "FORBIDDEN_PATH")
        self.assertFalse(inside.exists())
        if os.name != "nt":
            self.skipTest("Windows junction checks")
        target = self.root / "target"
        target.mkdir()
        link = self.root / "link"
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
        self._junctions.append(link)
        with self.assertRaises(C.GamekitError) as junction:
            sfx.generate(link / "click.wav", "jump")
        self.assertEqual(junction.exception.code, "FORBIDDEN_PATH")
        self.assertFalse((target / "click.wav").exists())

    def test_cli_presets_and_generate(self) -> None:
        code, listed = _invoke(["sfx", "presets"])
        self.assertEqual(code, 0)
        self.assertIn("ui_click", [row["id"] for row in listed["presets"]])
        code, bad = _invoke(["sfx", "generate", "--preset", "nope", "--out", str(self._wav())])
        self.assertEqual(code, 2)
        self.assertEqual(bad["error"], "BAD_REQUEST")
        self.assertFalse(self._wav().exists())
        code, wrote = _invoke(["sfx", "generate", "--preset", "explosion", "--out", str(self._wav("boom.wav")), "--seed", "5"])
        self.assertEqual(code, 0, wrote)
        self.assertTrue(self._wav("boom.wav").is_file())
        self.assertLess(wrote["peak_dbfs"], -0.1)

    def test_cli_subprocess_matches_api_bytes(self) -> None:
        path = self._wav("sub.wav")
        script = (
            "import argparse, json, sys\n"
            "from studio.gamekit import sfx\n"
            "parser = argparse.ArgumentParser()\n"
            "sub = parser.add_subparsers(dest='command', required=True)\n"
            "sfx.register(sub)\n"
            "args = parser.parse_args()\n"
            "json.dump(args.func(args), sys.stdout)\n"
        )
        env = os.environ.copy()
        env["HH_GAMEKIT_STATE"] = str(self.root / "state")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [sys.executable, "-B", "-c", script, "sfx", "generate", "--preset", "ui_click", "--out", str(path), "--seed", "11"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        wav, meta = sfx.synthesize("ui_click", seed=11)
        self.assertEqual(payload["sha256"], meta["sha256"])
        self.assertEqual(path.read_bytes(), wav)
