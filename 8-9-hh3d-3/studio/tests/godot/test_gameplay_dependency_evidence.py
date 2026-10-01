"""Pure dependency-observation contract tests; never launch Godot or Docker."""
import copy
import importlib.util
from pathlib import Path
import unittest


STUDIO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "gameplay_dependency_evidence_test",
    STUDIO / "godot-addon/gameplay_dependency_evidence.py")
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)


FILES = {
    "scripts/main.gd": b'extends Node3D\n',
    "scripts/shared.gd": b'extends Node3D\n',
    "scenes/mover.tscn": b"[gd_scene format=3]\n",
    "assets/avatar.glb": b"glTF-fixture",
}


def observation():
    return {
        "schema": evidence.SCHEMA,
        "version": evidence.VERSION,
        "entrypoint": "scripts/main.gd",
        "nodes": [
            {"path": "scripts/main.gd", "kind": "script",
             "size_bytes": len(FILES["scripts/main.gd"]),
             "sha256": evidence._sha(FILES["scripts/main.gd"]), "uid": "uid://main",
             "edges": [
                 {"kind": "script_preload", "target": "scripts/shared.gd"},
                 {"kind": "script_preload", "target": "scenes/mover.tscn"},
                 {"kind": "dynamic_load", "target": "assets/avatar.glb"},
             ]},
            {"path": "scripts/shared.gd", "kind": "script",
             "size_bytes": len(FILES["scripts/shared.gd"]),
             "sha256": evidence._sha(FILES["scripts/shared.gd"]), "uid": "uid://shared",
             "edges": []},
            {"path": "scenes/mover.tscn", "kind": "scene",
             "size_bytes": len(FILES["scenes/mover.tscn"]),
             "sha256": evidence._sha(FILES["scenes/mover.tscn"]), "uid": "uid://mover",
             "edges": [
                 {"kind": "scene_ext_resource", "target": "scripts/shared.gd"},
             ]},
            {"path": "assets/avatar.glb", "kind": "asset",
             "size_bytes": len(FILES["assets/avatar.glb"]),
             "sha256": evidence._sha(FILES["assets/avatar.glb"]), "uid": "uid://avatar",
             "edges": []},
        ],
    }


class GameplayDependencyEvidenceTests(unittest.TestCase):
    def assert_code(self, code, files=FILES, report=None, **kwargs):
        with self.assertRaisesRegex(evidence.DependencyEvidenceError, code):
            evidence.validate_dependency_observation(
                files, observation() if report is None else report, **kwargs)

    def test_valid_graph_is_hash_bound_and_untrusted(self):
        report = evidence.validate_dependency_observation(
            FILES, observation(), reopened_files=dict(FILES),
            reopened_observation=copy.deepcopy(observation()))
        self.assertEqual(report["schema"], evidence.SCHEMA)
        self.assertEqual(len(report["graph_sha256"]), 64)
        self.assertIs(report["native_observation_verified"], False)
        self.assertIs(report["reopen_match"], True)
        self.assertIs(report["dependency_closure_verified"], False)
        self.assertIs(report["public_ack"], False)

    def test_digest_is_independent_of_mapping_row_and_edge_order(self):
        reversed_files = dict(reversed(list(FILES.items())))
        reversed_observation = observation()
        reversed_observation["nodes"] = list(reversed(reversed_observation["nodes"]))
        for row in reversed_observation["nodes"]:
            row["edges"] = list(reversed(row["edges"]))
        first = evidence.validate_dependency_observation(FILES, observation())
        second = evidence.validate_dependency_observation(reversed_files, reversed_observation)
        self.assertEqual(first["graph_sha256"], second["graph_sha256"])

    def test_exact_schema_rejects_forged_flags_and_unknown_fields(self):
        for key, value in (("native_observation_verified", True),
                           ("dependency_closure_verified", True),
                           ("public_ack", True),
                           ("extra", False)):
            report = observation()
            report[key] = value
            self.assert_code("DEPENDENCY_OBSERVATION_SHAPE", report=report)
        report = observation()
        report["version"] = True
        self.assert_code("DEPENDENCY_OBSERVATION_VERSION", report=report)

    def test_paths_are_canonical_in_root_and_case_unique(self):
        for bad in ("res://scripts/main.gd", "scripts/../main.gd",
                    "scripts\\main.gd", "outside/main.gd", "scripts/CON.gd",
                    "scripts/Main.gd"):
            files = dict(FILES)
            if bad == "scripts/Main.gd":
                files[bad] = files.pop("scripts/main.gd")
            report = observation()
            if bad != "scripts/Main.gd":
                report["nodes"][0]["path"] = bad
            else:
                report["entrypoint"] = bad
                report["nodes"][0]["path"] = bad
            self.assert_code("DEPENDENCY_FILE_PATH|DEPENDENCY_NODE_PATH|DEPENDENCY_PATH_ALIAS",
                             files=files, report=report)
        files = dict(FILES)
        files["scripts/Main.gd"] = files["scripts/main.gd"]
        self.assert_code("DEPENDENCY_PATH_ALIAS", files=files)

    def test_node_set_and_hash_size_binding_reject_missing_extra_stale(self):
        report = observation()
        report["nodes"] = report["nodes"][:-1]
        self.assert_code("DEPENDENCY_NODE_SET", report=report)
        files = dict(FILES)
        files["scenes/extra.tscn"] = b"[gd_scene format=3]\n"
        self.assert_code("DEPENDENCY_NODE_SET", files=files)
        for key, value in (("size_bytes", 999), ("sha256", "0" * 64)):
            report = observation()
            report["nodes"][0][key] = value
            self.assert_code("DEPENDENCY_NODE_SIZE|DEPENDENCY_NODE_HASH", report=report)

    def test_uid_path_bijection_and_kind_extension_are_enforced(self):
        report = observation()
        report["nodes"][1]["uid"] = report["nodes"][0]["uid"]
        self.assert_code("DEPENDENCY_UID_DUPLICATE", report=report)
        report = observation()
        report["nodes"][1]["uid"] = "uid://BAD"
        self.assert_code("DEPENDENCY_UID", report=report)
        report = observation()
        report["nodes"][2]["kind"] = "script"
        self.assert_code("DEPENDENCY_NODE_KIND", report=report)

    def test_edges_are_typed_present_and_unique(self):
        for mutate, code in (
            (lambda row: row["edges"][0].update(target="scripts/missing.gd"),
             "DEPENDENCY_EDGE_MISSING"),
            (lambda row: row["edges"].append(dict(row["edges"][0])),
             "DEPENDENCY_EDGE_DUPLICATE"),
            (lambda row: row["edges"][0].update(kind="scene_ext_resource"),
             "DEPENDENCY_EDGE_KIND"),
            (lambda row: row["edges"][0].update(kind="unknown"),
             "DEPENDENCY_EDGE_KIND"),
        ):
            report = observation()
            mutate(report["nodes"][0])
            self.assert_code(code, report=report)

    def test_cycles_are_rejected(self):
        report = observation()
        report["nodes"][1]["edges"] = [
            {"kind": "script_preload", "target": "scripts/main.gd"}]
        self.assert_code("DEPENDENCY_CYCLE", report=report)

    def test_reopen_requires_both_inputs_and_exact_bytes_and_graph(self):
        self.assert_code("DEPENDENCY_REOPEN_BINDING", reopened_files=dict(FILES))
        changed = dict(FILES)
        changed["scripts/main.gd"] += b"\n# changed after reopen\n"
        changed_report = observation()
        changed_report["nodes"][0]["size_bytes"] = len(changed["scripts/main.gd"])
        changed_report["nodes"][0]["sha256"] = evidence._sha(changed["scripts/main.gd"])
        self.assert_code("DEPENDENCY_REOPEN_MISMATCH", reopened_files=changed,
                         reopened_observation=changed_report)
        changed_report = observation()
        changed_report["nodes"][0]["uid"] = "uid://changed"
        self.assert_code("DEPENDENCY_REOPEN_MISMATCH", reopened_files=dict(FILES),
                         reopened_observation=changed_report)

    def test_non_bytes_files_and_duplicate_edges_fail_closed(self):
        files = dict(FILES)
        files["scripts/main.gd"] = bytearray(files["scripts/main.gd"])
        self.assert_code("DEPENDENCY_FILE_BYTES", files=files)
        report = observation()
        report["nodes"][0]["edges"].append({"kind": "dynamic_load", "target": "assets/avatar.glb"})
        self.assert_code("DEPENDENCY_EDGE_DUPLICATE|DEPENDENCY_EDGE_KIND", report=report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
