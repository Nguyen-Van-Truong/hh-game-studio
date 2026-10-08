"""Unit tests for the fail-closed B5 catalog fixture verifier."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).with_name("run_gt09_catalog_fixtures.py")
spec = importlib.util.spec_from_file_location("gt09_catalog_fixtures", MODULE)
assert spec and spec.loader
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def _native(root: Path, fixture: str, closure: str = "sha256:" + "a" * 64) -> None:
    (root / "editor-host").mkdir(parents=True)
    (root / "editor-host" / "process-exit.json").write_text("{}", encoding="utf-8")
    (root / "result.json").write_text(json.dumps({"status": "DIAGNOSTIC_PASS", "authority": 0,
        "public_ack": False}), encoding="utf-8")
    (root / "registered-owner-receipt.json").write_text(json.dumps({
        "schema": "hh-godot-registered-authoring-owner-1", "profile": "hh-godot-gameplay-source-1",
        "profile_catalog_digest": "sha256:" + "b" * 64, "source_closure_sha256": closure,
        "command_ids": [fixture + ".command"], "native_process": {"exit_code": 0},
        "blender_handoff": {"published_root": str(root / "blender"), "glb_sha256": "c" * 64},
    }), encoding="utf-8")
    (root / "blender").mkdir()
    (root / "blender" / "scene.glb").write_bytes(b"glb")
    glb = __import__("hashlib").sha256(b"glb").hexdigest()
    (root / "blender" / "manifest.json").write_text(json.dumps({
        "schema": "HH-BLENDER-PUBLICATION-1", "public_ack": False,
        "native": {"glb_sha256": glb},}), encoding="utf-8")
    receipt = json.loads((root / "registered-owner-receipt.json").read_text())
    receipt["blender_handoff"]["glb_sha256"] = glb
    (root / "registered-owner-receipt.json").write_text(json.dumps(receipt), encoding="utf-8")


class CatalogFixtureVerifierTests(unittest.TestCase):
    def test_missing_repair_perf_and_sprite_stays_open(self):
        with tempfile.TemporaryDirectory(dir=verifier.STUDIO / ".local" / "reviews") as temp:
            root = Path(temp)
            arena, room = root / "arena", root / "room"
            _native(arena, "arena")
            _native(room, "room")
            report = verifier.build_report(arena=arena, room=room)
            self.assertEqual(report["status"], "OPEN")
            self.assertIn("seeded_repair_evidence_missing", report["errors"])
            self.assertIn("arena:blender_sprite_provenance_missing", report["errors"])

    def test_different_closure_cannot_pass(self):
        with tempfile.TemporaryDirectory(dir=verifier.STUDIO / ".local" / "reviews") as temp:
            root = Path(temp)
            _native(root / "arena", "arena", "sha256:" + "a" * 64)
            _native(root / "room", "room", "sha256:" + "d" * 64)
            report = verifier.build_report(arena=root / "arena", room=root / "room")
            self.assertIn("native_source_closure_mismatch", report["errors"])

    def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            report = verifier.build_report(arena=Path(temp), room=Path(temp))
            self.assertEqual(report["status"], "OPEN")
            self.assertIn("arena:root_outside_reviews", report["errors"])


if __name__ == "__main__":
    unittest.main()
