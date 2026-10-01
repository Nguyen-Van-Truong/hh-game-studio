"""Pure transport tests for the candidate Godot dependency marker.

These tests never start Godot or Docker.  The marker is untrusted process
output; validation must remain authority zero and bind the payload to bytes
supplied by the caller.
"""
import copy
import importlib.util
from pathlib import Path
import json
import unittest


STUDIO = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evidence = load("dependency_observation_evidence_test",
                STUDIO / "godot-addon/gameplay_dependency_evidence.py")
observation = load("dependency_observation_marker_test",
                   STUDIO / "godot-addon/gameplay_dependency_observation.py")

FILES = {
    "scripts/main.gd": b"extends Node3D\n",
    "scripts/shared.gd": b"extends Node3D\n",
    "scenes/mover.tscn": b"[gd_scene format=3]\n",
}


def graph():
    return {
        "schema": evidence.SCHEMA,
        "version": evidence.VERSION,
        "entrypoint": "scripts/main.gd",
        "nodes": [
            {"path": "scripts/main.gd", "kind": "script",
             "size_bytes": len(FILES["scripts/main.gd"]),
             "sha256": evidence._sha(FILES["scripts/main.gd"]),
             "edges": [
                 {"kind": "script_preload", "target": "scripts/shared.gd"},
                 {"kind": "script_preload", "target": "scenes/mover.tscn"},
             ]},
            {"path": "scripts/shared.gd", "kind": "script",
             "size_bytes": len(FILES["scripts/shared.gd"]),
             "sha256": evidence._sha(FILES["scripts/shared.gd"]),
             "edges": []},
            {"path": "scenes/mover.tscn", "kind": "scene",
             "size_bytes": len(FILES["scenes/mover.tscn"]),
             "sha256": evidence._sha(FILES["scenes/mover.tscn"]),
             "edges": [{"kind": "scene_ext_resource",
                        "target": "scripts/shared.gd"}]},
        ],
    }


def stdout(value=None):
    return "boot\n" + observation.MARKER + json.dumps(
        graph() if value is None else value, sort_keys=True) + "\n"


class GameplayDependencyObservationTests(unittest.TestCase):
    def test_marker_binds_bytes_and_close_reopen_without_authority(self):
        report = observation.parse_dependency_observation(
            stdout(), FILES, reopened_stdout=stdout(),
            reopened_files=dict(FILES))
        self.assertEqual(report["marker_count"], 1)
        self.assertTrue(report["reopen_match"])
        self.assertEqual(report["authority"], 0)
        self.assertIs(report["native_observation_verified"], False)
        self.assertIs(report["dependency_closure_verified"], False)
        self.assertIs(report["public_ack"], False)

    def test_missing_duplicate_and_malformed_markers_reject(self):
        for raw, code in (("", "DEPENDENCY_MARKER_MISSING"),
                          (stdout() + stdout(), "DEPENDENCY_MARKER_DUPLICATE"),
                          (observation.MARKER + "{not-json}\n",
                           "DEPENDENCY_MARKER_JSON")):
            with self.subTest(code=code):
                with self.assertRaisesRegex(observation.DependencyObservationMarkerError, code):
                    observation.parse_dependency_observation(raw, FILES)

    def test_authority_fields_reject_before_contract(self):
        for key in ("authority", "public_ack", "dependency_closure_verified",
                    "native_observation_verified"):
            value = copy.deepcopy(graph())
            value[key] = True
            with self.subTest(key=key):
                with self.assertRaisesRegex(observation.DependencyObservationMarkerError,
                                            "DEPENDENCY_MARKER_AUTHORITY_CLAIM"):
                    observation.parse_dependency_observation(stdout(value), FILES)

    def test_reopen_pairing_and_utf8_are_bound(self):
        with self.assertRaisesRegex(observation.DependencyObservationMarkerError,
                                    "DEPENDENCY_MARKER_REOPEN_BINDING"):
            observation.parse_dependency_observation(stdout(), FILES,
                                                     reopened_files=dict(FILES))
        with self.assertRaisesRegex(observation.DependencyObservationMarkerError,
                                    "DEPENDENCY_MARKER_ENCODING"):
            observation.parse_dependency_observation(b"\xff", FILES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
