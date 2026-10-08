"""Static contract checks for the opt-in fixture lifecycle.

These checks never start Godot.  They keep the real-input lifecycle bounded,
preserve the short diagnostic probes, and make the authority boundary visible
to the host packer.
"""
from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent / "gameplay_fixture"
MAX_SOURCE_BYTES = 16 * 1024


class FixtureLifecycleContractTests(unittest.TestCase):
    def read(self, name: str) -> str:
        path = ROOT / name
        raw = path.read_bytes()
        self.assertGreater(len(raw), 0, name)
        self.assertLessEqual(len(raw), MAX_SOURCE_BYTES, name)
        return raw.decode("utf-8")

    def test_shared_component_is_bounded_and_untrusted(self) -> None:
        source = self.read("fixture_lifecycle.gd")
        for marker in (
            '"MENU"', '"PLAYING"', '"PAUSED"', '"QUIT"',
            "InputEventKey", "Input.parse_input_event", "get_tree().paused",
            "HH_FIXTURE_LIFECYCLE_INPUT", "HH_FIXTURE_LIFECYCLE_STATE",
            '"authority": 0', '"acceptance": false', '"playtest_claim": false',
            "SESSION_SECONDS: int = 960", "MAX_INPUT_EDGES: int = 8192",
        ):
            self.assertIn(marker, source)
        self.assertIn("--fixture-lifecycle-smoke", source)
        self.assertIn("--fixture-lifecycle-scripted", source)
        self.assertIn('"state_observations"', source)
        self.assertIn('"transitions"', source)
        self.assertIn("delegated agent run", source)
        for marker in ("func _scripted_once", '"pause2_down"',
                       '"restart_down"', '"quit_down"'):
            self.assertIn(marker, source)
        self.assertIn("External mode never does", source)

    def test_both_fixtures_opt_in_without_changing_short_probe(self) -> None:
        for name, legacy_guard in (
            ("arena_physics.gd", "not Lifecycle.requested()"),
            ("room3d_native.gd", "not Lifecycle.requested()"),
        ):
            source = self.read(name)
            self.assertIn("Lifecycle.requested()", source)
            self.assertIn("lifecycle.begin(", source)
            self.assertIn("_lifecycle_state", source)
            self.assertIn("_lifecycle_reset", source)
            self.assertIn(legacy_guard, source)

    def test_dependency_observation_keeps_candidate_boundary(self) -> None:
        source = self.read("fixture_dependencies.gd")
        self.assertIn("Candidate runtime observation only", source)
        self.assertIn('"hh-gameplay-dependency-observation-1"', source)
        self.assertIn("static func observe(entry: String)", source)


if __name__ == "__main__":
    unittest.main()
