"""Quick bot regressions for 3D ground coverage and report output (no Godot)."""

from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio.gamekit import bot as B
from studio.gamekit import common as C


LABEL = "Player:global_position"


def _rows(points: list[list[float]]) -> list[dict]:
    return [{"frame": frame, "values": {LABEL: point}} for frame, point in enumerate(points)]


class BotHardeningTest(unittest.TestCase):
    def test_3d_z_walk_counts_ground_cells_and_is_not_stuck(self) -> None:
        observations = _rows([[0, 5, float(frame)] for frame in range(31)])
        trace = B.build_trace(["forward"], 30, 3, 6, 12)
        report = B.analyze(observations, trace, LABEL, 30, 5, 1, 2)
        self.assertEqual(report["plane"], "xz")
        self.assertEqual(report["coverage"], 16)
        self.assertEqual(report["bbox"], {"min": [0.0, 0.0], "max": [0.0, 30.0]})
        self.assertEqual(report["stuck"], [])

    def test_default_3d_vertical_motion_does_not_expand_ground_coverage(self) -> None:
        observations = _rows([[2, float(frame), 3] for frame in range(31)])
        trace = B.build_trace(["jump"], 30, 3, 6, 12)
        report = B.analyze(observations, trace, LABEL, 30, 5, 1, 2)
        self.assertEqual(report["coverage"], 1)
        self.assertTrue(report["stuck"])
        side_view = B.analyze(observations, trace, LABEL, 30, 5, 1, 2, "xy")
        self.assertGreater(side_view["coverage"], 1)
        self.assertFalse(side_view["stuck"])

    def test_2d_keeps_xy_and_invalid_positions_are_ignored(self) -> None:
        trace = B.build_trace(["right"], 10, 3, 6, 12)
        observations = [{"frame": 0, "values": {LABEL: None}}] + _rows([[float(frame), 2] for frame in range(11)])
        observations.append({"frame": False, "values": {LABEL: [500, 500]}})
        report = B.analyze(observations, trace, LABEL, 10, 5, 1, 2)
        self.assertEqual(report["plane"], "xy")
        self.assertEqual(report["samples"], 11)
        self.assertEqual(report["bbox"], {"min": [0.0, 2.0], "max": [10.0, 2.0]})

    def test_output_contains_the_full_bot_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hh-bot-unit-") as temp:
            root = Path(temp)
            project = C.Project("game", root / "game")
            project.root.mkdir()
            out = root / "bot.json"
            played = {"ok": True, "crashed": False, "errors": [], "observations": _rows([[0, 0, 0], [0, 0, 2]])}
            with patch.object(B.P, "play", return_value=played):
                result = B.run_bot(project, actions="forward", track="Player", frames=1, cell=1, out=str(out))
            self.assertEqual(json.loads(out.read_text(encoding="utf-8")), result)
            self.assertEqual(result["coverage"], 2)
            self.assertEqual(result["plane"], "xz")
            self.assertIn("events", result["trace"])

    def test_bad_output_path_rejected_before_play(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hh-bot-unit-") as temp:
            project = C.Project("game", Path(temp))
            with patch.object(B.P, "play") as launched, self.assertRaises(C.GamekitError) as caught:
                B.run_bot(project, actions="forward", track="Player", out=str(project.root / "bot.json"))
            self.assertEqual(caught.exception.code, "FORBIDDEN_PATH")
            launched.assert_not_called()

    def test_bot_does_not_report_ok_when_play_fails_or_positions_are_missing(self) -> None:
        project = C.Project("game", Path("."))
        for played in (
            {"ok": False, "crashed": False, "errors": [], "observations": _rows([[0, 0]])},
            {"ok": True, "crashed": False, "errors": [], "observations": []},
        ):
            with self.subTest(played=played), patch.object(B.P, "play", return_value=played):
                result = B.run_bot(project, actions="forward", track="Player", frames=1)
                self.assertFalse(result["ok"])

    def test_cli_accepts_output_and_plane(self) -> None:
        parser = argparse.ArgumentParser()
        B.register(parser.add_subparsers())
        args = parser.parse_args(["bot", "game", "--actions", "forward", "--track", "Player", "--out", "bot.json", "--plane", "yz"])
        self.assertEqual(args.out, "bot.json")
        self.assertEqual(args.plane, "yz")


if __name__ == "__main__":
    unittest.main()
