"""Fast unit tests (no Godot) for gamekit W4: input validation, traces, stuck, coverage."""

from __future__ import annotations

import unittest
from pathlib import Path

from studio.gamekit import bot as B
from studio.gamekit import common as C
from studio.gamekit import inputmap as IM
from studio.gamekit import play as P


class InputValidationTest(unittest.TestCase):
    def test_normalizes_and_rejects(self) -> None:
        actions = IM.validate_actions({
            "move_left": {"events": [{"key": " A "}, {"joy_button": 0}]},
            "move_right": {"deadzone": 0.25, "events": [{"physical_key": "D"}, {"joy_axis": 0, "value": -1}, {"mouse_button": 1}]},
        })
        self.assertEqual(actions["move_left"]["deadzone"], 0.5)
        self.assertEqual(actions["move_left"]["events"][0], {"key": "A"})
        self.assertEqual(actions["move_right"]["events"][1]["value"], -1.0)
        bad = [
            [],
            {"1move": {"events": []}},
            {"move": {"events": [], "extra": 1}},
            {"move": {"deadzone": True, "events": []}},
            {"move": {"deadzone": 1.5, "events": []}},
            {"move": {"events": [{"key": ""}]}},
            {"move": {"events": [{"key": "A", "physical_key": "D"}]}},
            {"move": {"events": [{"joy_button": -1}]}},
            {"move": {"events": [{"joy_button": 1.5}]}},
            {"move": {"events": [{"joy_axis": 0}]}},
            {"move": {"events": [{"joy_axis": 0, "value": 0}]}},
            {"move": {"events": [{"joy_axis": 10, "value": 1}]}},
            {"move": {"events": [{"mouse_button": 0}]}},
            {"move": {"events": [{"tilt": 1}]}},
            {"move": {"events": [{"key": "A"}] * (IM.MAX_EVENTS + 1)}},
        ]
        for item in bad:
            with self.assertRaises(C.GamekitError) as cm:
                IM.validate_actions(item)
            self.assertEqual(cm.exception.code, "VALIDATION_FAILED", cm.exception.detail)

    def test_set_rejects_before_godot(self) -> None:
        project = C.Project("game", Path("."))
        with self.assertRaises(C.GamekitError) as cm:
            IM.set_actions(project, {"move_left": {"events": [{"key": "A"}]}}, "x")
        self.assertEqual(cm.exception.code, "BAD_REQUEST")
        with self.assertRaises(C.GamekitError) as cm2:
            IM.set_actions(project, {"move left": {"events": []}}, "w4.unit.1")
        self.assertEqual(cm2.exception.code, "VALIDATION_FAILED")

    def test_diffs(self) -> None:
        requested = IM.validate_actions({
            "move_left": {"deadzone": 0.5, "events": [{"key": "a"}]},
            "jump": {"events": [{"key": "Space"}]},
        })
        written = [
            {"name": "jump", "deadzone": 0.5, "events": [{"key": "Space"}]},
            {"name": "move_left", "deadzone": 0.5, "events": [{"key": "A"}]},
        ]
        self.assertEqual(IM.diff_request(requested, written), [])
        written[1]["events"] = [{"key": "B"}]
        self.assertTrue(IM.diff_request(requested, written))
        before = [{"name": "dash", "deadzone": 0.2, "events": [{"key": "Shift"}]}]
        fresh = [
            {"name": "dash", "deadzone": 0.2, "events": [{"key": "Shift"}]},
            {"name": "jump", "deadzone": 0.5, "events": [{"key": "Space"}]},
            {"name": "move_left", "deadzone": 0.5, "events": [{"key": "A"}]},
            {"name": "ui_accept", "deadzone": 0.5, "events": [{"key": "Enter"}]},
        ]
        written[1]["events"] = [{"key": "A"}]
        self.assertEqual(IM.diff_readback(before, written, fresh, False), [])
        replaced = [item for item in fresh if item["name"] != "dash"]
        self.assertEqual(IM.diff_readback(before, written, replaced, True), [])
        self.assertTrue(IM.diff_readback(before, written, fresh, True))
        dropped = [item for item in fresh if item["name"] != "jump"]
        self.assertTrue(IM.diff_readback(before, written, dropped, False))


class TraceAndPlayValidationTest(unittest.TestCase):
    def test_trace_and_observe(self) -> None:
        trace = P.validate_trace({
            "fps": 60,
            "events": [
                {"frame": 60, "action": "move_right", "pressed": False},
                {"frame": 0, "action": "move_right", "pressed": True, "strength": 1},
            ],
        })
        self.assertEqual([ev["frame"] for ev in trace["events"]], [0, 60])
        self.assertEqual(trace["events"][0]["strength"], 1.0)
        self.assertEqual(P.validate_trace(None), {"fps": 60, "events": []})
        probes = P.parse_observe("Player:position, World/Player:velocity")
        self.assertEqual(probes[0]["label"], "Player:position")
        self.assertEqual(probes[1]["node"], "World/Player")
        rejected = [
            {"fps": 30, "events": []},
            {"events": [{"frame": -1, "action": "a", "pressed": True}]},
            {"events": [{"frame": 0, "action": "a", "pressed": "yes"}]},
            {"events": [{"frame": 0, "action": "", "pressed": True}]},
            {"events": [{"frame": 0, "action": "a", "pressed": True, "strength": 2}]},
            {"extra": 1, "events": []},
        ]
        for item in rejected:
            with self.assertRaises(C.GamekitError) as cm:
                P.validate_trace(item)
            self.assertEqual(cm.exception.code, "VALIDATION_FAILED", cm.exception.detail)
        for text in ("Player", "Player:", ":position", "../Player:position", "Player:velocity:x"):
            with self.assertRaises(C.GamekitError):
                P.parse_observe(text)
        digest = P.trace_hash([{"frame": 0, "values": {"Player:position": [1, 2]}}])
        self.assertEqual(digest, P.trace_hash([{"values": {"Player:position": [1, 2]}, "frame": 0}]))
        self.assertEqual(len(digest), 64)
        self.assertEqual(P.merge_errors([" same "], ["same"], [{"file": "res://a.gd", "line": 3, "code": "boom"}]),
                         ["same", "res://a.gd:3: boom"])

    def test_play_rejects_before_godot(self) -> None:
        project = C.Project("game", Path("."))
        with self.assertRaises(C.GamekitError) as cm:
            P.play(project, frames=0)
        self.assertEqual(cm.exception.code, "VALIDATION_FAILED")
        with self.assertRaises(C.GamekitError) as cm2:
            B.run_bot(project, actions="move_left,move_left", track="Player")
        self.assertEqual(cm2.exception.code, "VALIDATION_FAILED")
        with self.assertRaises(C.GamekitError) as cm3:
            B.run_bot(project, actions="move_left", track="Player", hold_min=8, hold_max=2)
        self.assertEqual(cm3.exception.code, "VALIDATION_FAILED")


class BotTraceTest(unittest.TestCase):
    def test_trace_is_deterministic_and_single_hold(self) -> None:
        actions = ["move_left", "move_right"]
        first = B.build_trace(actions, 300, 1, 10, 25)
        second = B.build_trace(actions, 300, 1, 10, 25)
        self.assertEqual(first, second)
        self.assertNotEqual(first, B.build_trace(actions, 300, 2, 10, 25))
        self.assertEqual(first["fps"], 60)
        self.assertEqual(first["events"][0]["frame"], 0)
        self.assertTrue(first["events"][0]["pressed"])
        self.assertEqual(first["events"][-1]["frame"], 300)
        self.assertFalse(first["events"][-1]["pressed"])
        held = B.held_during(first, 300)
        self.assertEqual(len(held), 300)
        self.assertTrue(all(len(state) == 1 for state in held))
        frames = [ev["frame"] for ev in first["events"]]
        self.assertEqual(frames, sorted(frames))

    def test_free_walk_covers_cells_and_motion_is_not_stuck(self) -> None:
        trace = B.build_trace(["move_left", "move_right"], 300, 1, 10, 25)
        held = B.held_during(trace, 300)
        x = 0.0
        observations = [{"frame": 0, "values": {"Player:global_position": [0.0, 0.0]}}]
        speed = 200.0 / 60.0
        for frame in range(300):
            axis = (1.0 if "move_right" in held[frame] else 0.0) - (1.0 if "move_left" in held[frame] else 0.0)
            x += axis * speed
            observations.append({"frame": frame + 1, "values": {"Player:global_position": [x, 0.0]}})
        report = B.analyze(observations, trace, "Player:global_position", 300, 20, 4.0, 32)
        self.assertGreaterEqual(report["coverage"], 3)
        self.assertEqual(report["stuck"], [])
        self.assertIsNotNone(report["bbox"])

    def test_wall_stop_is_a_stuck_interval(self) -> None:
        frames = 80
        events = [
            {"frame": 0, "action": "move_right", "pressed": True, "strength": 1.0},
            {"frame": frames, "action": "move_right", "pressed": False, "strength": 1.0},
        ]
        trace = {"fps": 60, "events": events}
        observations = []
        for frame in range(frames + 1):
            x = min(frame * (200.0 / 60.0), 12.0)
            observations.append({"frame": frame, "values": {"Player:global_position": [x, 20.0]}})
        report = B.analyze(observations, trace, "Player:global_position", frames, 20, 4.0, 32)
        self.assertGreaterEqual(len(report["stuck"]), 1)
        self.assertGreaterEqual(report["stuck"][0]["frames"], 20)
        self.assertLess(report["stuck"][0]["moved"], 4.0)
        self.assertIn("move_right", report["stuck"][0]["actions"])
        rng_trace = B.build_trace(["move_left", "move_right", "jump"], 40, 3, 6, 12)
        self.assertEqual(rng_trace, B.build_trace(["move_left", "move_right", "jump"], 40, 3, 6, 12))


if __name__ == "__main__":
    unittest.main()
