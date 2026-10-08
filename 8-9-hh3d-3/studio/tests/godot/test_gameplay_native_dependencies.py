"""Fail-closed checks for the trusted literal-loader inventory scope."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


STUDIO = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


native = load("native_dependencies_scope_test",
              STUDIO / "godot-addon/gameplay_native_dependencies.py")
evidence = load("dependency_evidence_scope_test",
                STUDIO / "godot-addon/gameplay_dependency_evidence.py")


FILES = {
    "scenes/fixture.tscn": b"[gd_scene format=3]\n",
    "scripts/fixture_actor.gd": b"extends Node\n",
    "scripts/fixture_helper.gd": b"extends Node\n",
    "assets/avatar.glb": b"glb-test\n",
}


def graph():
    edges = {
        "scenes/fixture.tscn": [
            {"kind": "loader_reference", "target": "scripts/fixture_actor.gd"},
        ],
        "scripts/fixture_actor.gd": [
            {"kind": "script_preload", "target": "scripts/fixture_helper.gd"},
            {"kind": "dynamic_load", "target": "assets/avatar.glb"},
        ],
        "scripts/fixture_helper.gd": [],
        "assets/avatar.glb": [],
    }
    nodes = []
    for path, raw in FILES.items():
        kind = "script" if path.endswith(".gd") else (
            "scene" if path.endswith(".tscn") else "asset")
        nodes.append({"path": path, "kind": kind, "size_bytes": len(raw),
                      "sha256": hashlib.sha256(raw).hexdigest(),
                      "edges": edges[path]})
    return {"schema": evidence.SCHEMA, "version": evidence.VERSION,
            "entrypoint": "scenes/fixture.tscn", "nodes": nodes}


def raw(value=None):
    return (native.PREFIX + json.dumps(graph() if value is None else value,
                                       separators=(",", ":")).encode() + b"\n")


class TrustedLiteralLoaderScopeTests(unittest.TestCase):
    def test_reopened_inventory_gets_only_the_narrow_scope(self):
        report = native.validate(FILES, raw(), raw())
        self.assertTrue(report["loader_graph_bound"])
        self.assertTrue(report["reopen_match"])
        self.assertTrue(report["literal_loader_scope_verified"])
        self.assertEqual(report["literal_loader_scope"],
                         native.LITERAL_LOADER_SCOPE)
        self.assertEqual(report["literal_loader_edge_counts"],
                         {"dynamic_load": 1, "loader_reference": 1,
                          "script_preload": 1})
        self.assertIs(report["native_observation_verified"], False)
        self.assertIs(report["dependency_closure_verified"], False)
        self.assertIs(report["dynamic_dependencies_verified"], False)
        self.assertIs(report["public_ack"], False)
        self.assertEqual(report["authority"], 0)

    def test_single_observation_is_not_a_scoped_claim(self):
        report = native.validate(FILES, raw())
        self.assertFalse(report["reopen_match"])
        self.assertIs(report["literal_loader_scope_verified"], False)
        self.assertIsNone(report["literal_loader_scope"])
        self.assertIsNone(report["literal_loader_edge_counts"])
        self.assertIs(report["dependency_closure_verified"], False)
        self.assertIs(report["dynamic_dependencies_verified"], False)

    def test_reopened_drift_fails_before_scope_is_issued(self):
        changed = graph()
        changed["nodes"][0]["edges"] = []
        with self.assertRaisesRegex(ValueError, "^DEPENDENCY_REOPEN_MISMATCH$"):
            native.validate(FILES, raw(), raw(changed))

    def test_unknown_edge_kind_cannot_widen_the_scope(self):
        changed = graph()
        changed["nodes"][0]["edges"][0]["kind"] = "scene_ext_resource"
        with self.assertRaisesRegex(ValueError, "^LOADER_LITERAL_SCOPE_EDGE_KIND$"):
            native.validate(FILES, raw(changed), raw(changed))

    def test_custom_validator_cannot_promote_authority_into_scope(self):
        class SpoofedValidator:
            @staticmethod
            def validate_dependency_observation(_files, _observation, **_kwargs):
                return {"schema": evidence.SCHEMA, "graph_sha256": "0" * 64,
                        "native_observation_verified": True,
                        "reopen_match": True,
                        "dependency_closure_verified": True,
                        "public_ack": True, "authority": 1}

        with self.assertRaisesRegex(ValueError, "^LOADER_LITERAL_SCOPE_AUTHORITY$"):
            native.validate(FILES, raw(), raw(), validator=SpoofedValidator)


if __name__ == "__main__":
    unittest.main(verbosity=2)
