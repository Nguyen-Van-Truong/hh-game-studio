"""Fast unit tests (no Godot) for gamekit W1 host logic: validation, uid, journal, checkpoints."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from studio.gamekit import common as C
from studio.gamekit import scene as S


class _TempState(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self._old_state = os.environ.get("HH_GAMEKIT_STATE")
        os.environ["HH_GAMEKIT_STATE"] = str(self.root / "state")
        self.game = self.root / "game"
        self.game.mkdir()
        (self.game / "project.godot").write_text("config_version=5\n", encoding="utf-8")
        (self.game / "player.gd").write_text("extends Node2D\n", encoding="utf-8")
        self.project = C.register_project(self.game, "game")
        self.catalog = S.load_catalog()

    def tearDown(self) -> None:
        if self._old_state is None:
            os.environ.pop("HH_GAMEKIT_STATE", None)
        else:
            os.environ["HH_GAMEKIT_STATE"] = self._old_state
        self.tmp.cleanup()


class ValidateOpsTest(_TempState):
    def _reject(self, ops: object, code: str = "VALIDATION_FAILED") -> None:
        with self.assertRaises(C.GamekitError) as cm:
            S.validate_ops(self.project, ops, self.catalog)
        self.assertEqual(cm.exception.code, code, cm.exception.detail)

    def test_accepts_known_ops(self) -> None:
        ops = [
            {"op": "node.create", "parent": ".", "name": "P", "type": "CharacterBody2D", "props": {"position": [1, 2]}},
            {"op": "script.attach", "path": "P", "script": "res://player.gd"},
            {"op": "resource.new", "path": "P", "prop": "material", "type": "CanvasItemMaterial"},
        ]
        self.assertEqual(S.validate_ops(self.project, ops, self.catalog), ops)

    def test_rejects_bad_shapes(self) -> None:
        self._reject({"op": "node.create"})
        self._reject([{"op": "node.explode", "path": "."}])
        self._reject([{"op": "node.create", "parent": ".", "name": "X"}])
        self._reject([{"op": "node.create", "parent": ".", "name": "X", "type": "EvilNode"}])
        self._reject([{"op": "node.update", "path": "P", "props": {"x": float("nan")}}])
        self._reject([{"op": "node.update", "path": "P", "props": {}, "extra": 1}])
        self._reject([{"op": "node.move", "path": "P", "parent": "../Outside"}])
        self._reject([{"op": "node.create", "parent": ".", "name": "X", "type": "Node2D", "index": True}])
        self._reject([{"op": "resource.new", "path": "P", "prop": "m", "type": "Script"}])
        self._reject([{"op": "node.update", "path": "P", "props": {"m": {"$type": "GDScript"}}}])
        self._reject([{"op": "node.delete", "path": "x"}] * (S.MAX_OPS + 1))

    def test_rejects_paths(self) -> None:
        self._reject([{"op": "script.attach", "path": "P", "script": "res://../evil.gd"}], "BAD_PATH")
        self._reject([{"op": "script.attach", "path": "P", "script": "res://.godot/x.gd"}], "BAD_PATH")
        self._reject([{"op": "script.attach", "path": "P", "script": "res://missing.gd"}], "NOT_FOUND")
        self._reject([{"op": "node.update", "path": "P", "props": {"t": {"$res": "res://nope.png"}}}], "NOT_FOUND")


class UidAndCompareTest(unittest.TestCase):
    def test_keep_uid_inserts_original(self) -> None:
        old = b'[gd_scene format=3 uid="uid://abc123"]\n\n[node name="A" type="Node"]\n'
        new = b'[gd_scene format=3]\n\n[node name="A" type="Node"]\n'
        self.assertTrue(S.keep_uid(new, old).startswith(b'[gd_scene format=3 uid="uid://abc123"]'))

    def test_keep_uid_replaces_and_ignores_missing(self) -> None:
        old = b'[gd_scene format=3 uid="uid://keep1"]\n'
        new = b'[gd_scene format=3 uid="uid://other2"]\n'
        self.assertIn(b"uid://keep1", S.keep_uid(new, old))
        self.assertEqual(S.keep_uid(new, None), new)
        self.assertEqual(S.keep_uid(new, b"[gd_scene format=3]\n"), new)

    def test_approx_equal(self) -> None:
        self.assertTrue(S.approx_equal({"a": [1.0, 2.0000001]}, {"a": [1, 2]}))
        self.assertFalse(S.approx_equal({"a": [1.0, 2.1]}, {"a": [1, 2]}))
        self.assertFalse(S.approx_equal(True, 1))
        self.assertFalse(S.approx_equal({"a": 1}, {"a": 1, "b": 2}))

    def test_readback_mismatch_reports_missing_and_changed(self) -> None:
        applied = {"state": {"nodes": []}, "expected": [{"path": "P", "prop": "x", "value": 1},
                                                       {"path": "Q", "prop": "y", "value": 2}]}
        readback = {"state": {"nodes": []}, "probes": [{"path": "P", "prop": "x", "value": 5},
                                                      {"path": "Q", "prop": "y", "missing": True}]}
        problems = S.readback_mismatches(applied, readback)
        self.assertEqual(len(problems), 2)


class JournalCheckpointTest(_TempState):
    def test_replay_and_conflict(self) -> None:
        journal = C.Journal(self.project)
        self.assertIsNone(journal.replay_or_conflict("cmd.1", "d1"))
        journal.append("cmd.1", "d1", {"ok": True, "status": "COMMITTED"})
        self.assertTrue(journal.replay_or_conflict("cmd.1", "d1")["replayed"])
        with self.assertRaises(C.GamekitError) as cm:
            journal.replay_or_conflict("cmd.1", "d2")
        self.assertEqual(cm.exception.code, "CONFLICT")

    def test_checkpoint_restore_bytes_and_absent(self) -> None:
        target = self.game / "a.tscn"
        target.write_bytes(b"before")
        absent = self.game / "new.tscn"
        C.checkpoint(self.project, "cmd.2", [target, absent])
        target.write_bytes(b"after")
        absent.write_bytes(b"created")
        restored = C.restore_checkpoint(self.project, "cmd.2")
        self.assertEqual(target.read_bytes(), b"before")
        self.assertFalse(absent.exists())
        self.assertEqual(sorted(restored), ["res://a.tscn", "res://new.tscn"])

    def test_command_id_rules(self) -> None:
        for bad in ("", "a", "x" * 97, "has space", "../up"):
            with self.assertRaises(C.GamekitError):
                C.validate_command_id(bad)
        self.assertEqual(C.validate_command_id("w1.player:1"), "w1.player:1")

    def test_registry_conflicts_and_forbidden(self) -> None:
        self.assertEqual(C.register_project(self.game, "game").root, self.project.root)
        other = self.root / "other"
        other.mkdir()
        (other / "project.godot").write_text("config_version=5\n", encoding="utf-8")
        with self.assertRaises(C.GamekitError):
            C.register_project(other, "game")
        bad = self.root / "godot" / "dogfood" / "kho-bi-an"
        bad.mkdir(parents=True)
        (bad / "project.godot").write_text("config_version=5\n", encoding="utf-8")
        with self.assertRaises(C.GamekitError) as cm:
            C.register_project(bad, "kba")
        self.assertEqual(cm.exception.code, "FORBIDDEN_PATH")

    def test_lock_is_exclusive(self) -> None:
        with C.project_lock(self.project, "first"):
            with self.assertRaises(C.GamekitError) as cm:
                with C.project_lock(self.project, "second"):
                    pass
            self.assertEqual(cm.exception.code, "LOCKED")
        with C.project_lock(self.project, "third"):
            pass


if __name__ == "__main__":
    unittest.main()
