"""Static fail-closed tests for the O2 TileMapLayer cell candidate."""
from dataclasses import replace
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
SPEC = importlib.util.spec_from_file_location("o2_tilemap_authoring", STUDIO / "godot-addon/tilemap_authoring.py")
tilemap = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = tilemap
SPEC.loader.exec_module(tilemap)
from studio.protocol.core import Request, ValidationError, canonical_bytes


class TileMapAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.context = tilemap.ValidationContext(
            "project.fixture", "sha256:" + "1" * 64, "sha256:" + "2" * 64,
            4, "lease.fixture", 9, 31000, 1000,
            (tilemap.NodeState("root", None, "Node2D", "Root"),
             tilemap.NodeState("map", "root", "TileMapLayer", "Map")),
            (tilemap.TileSourceState(0, "sha256:" + "3" * 64, ((0, 0), (1, 0)), (0, 1)),))

    def request(self, operation="scene.tilemap.cell.set", *, payload=None, target=None, context=None):
        context = context or self.context
        payload = copy.deepcopy(payload or {"cell": [2, 3], "source_id": 0,
                                            "atlas_coords": [0, 0], "alternative": 0})
        payload.setdefault("expected_generation", context.generation)
        payload.setdefault("expected_project_revision", context.project_revision)
        return Request(command_id="tilemap.fixture", project_id=context.project_id,
                       operation=operation, lease_id=context.lease_id,
                       fencing_epoch=context.fencing_epoch, expected_revision=context.revision,
                       target=target or {"stable_id": "map"}, payload=payload,
                       payload_hash="sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest(),
                       deadline_ms=2000)

    def validate(self, request=None, context=None):
        return tilemap.validate_request(request or self.request(), context or self.context)

    def reject(self, request, code=None, *, context=None):
        with self.assertRaises(ValidationError) as raised:
            self.validate(request, context)
        if code:
            self.assertEqual(raised.exception.code, code)

    def test_set_projection_and_preview_are_detached(self):
        result = self.validate()
        self.assertEqual(result.projection["after"]["cell"], [2, 3])
        self.assertEqual(result.preview["authority"], 0)
        projection = result.projection
        projection["after"]["cell"][0] = 99
        self.assertEqual(result.projection["after"]["cell"], [2, 3])

    def test_clear_requires_existing_cell_and_preserves_before_state(self):
        state = tilemap.CellState("map", (2, 3), 0, (0, 0), 0)
        context = replace(self.context, cells=(state,))
        request = self.request("scene.tilemap.cell.clear", payload={"cell": [2, 3]}, context=context)
        self.assertEqual(self.validate(request, context).projection["after"]["source_id"], 0)
        self.reject(self.request("scene.tilemap.cell.clear", payload={"cell": [4, 4]}), "TILEMAP_CLEAR_SHAPE")

    def test_rejects_unknown_source_atlas_duplicate_and_wrong_target(self):
        self.reject(self.request(payload={"cell": [1, 1], "source_id": 7,
                                          "atlas_coords": [0, 0], "alternative": 0}), "TILEMAP_SOURCE_UNKNOWN")
        self.reject(self.request(payload={"cell": [1, 1], "source_id": 0,
                                          "atlas_coords": [9, 9], "alternative": 0}), "TILEMAP_ATLAS_UNKNOWN")
        state = tilemap.CellState("map", (2, 3), 0, (0, 0), 0)
        self.reject(self.request(context=replace(self.context, cells=(state,))), "TILEMAP_DUPLICATE_CELL",
                    context=replace(self.context, cells=(state,)))
        self.reject(self.request(target={"stable_id": "root"}), "TILEMAP_TARGET_TYPE")

    def test_rejects_bad_coordinates_alternative_and_extra_fields(self):
        for cell in ([4097, 0], [1], [True, 0], [0.5, 0]):
            self.reject(self.request(payload={"cell": cell, "source_id": 0,
                                              "atlas_coords": [0, 0], "alternative": 0}), "TILEMAP_CELL")
        self.reject(self.request(payload={"cell": [1, 1], "source_id": 0,
                                          "atlas_coords": [0, 0], "alternative": 9}), "TILEMAP_ALTERNATIVE")
        extra = self.request(payload={"cell": [1, 1], "source_id": 0,
                                      "atlas_coords": [0, 0], "alternative": 0, "extra": True})
        extra = replace(extra, payload_hash="sha256:" + hashlib.sha256(canonical_bytes(extra.payload)).hexdigest())
        self.reject(extra, "TILEMAP_SET_SHAPE")

    def test_rejects_stale_context(self):
        cases = [(replace(self.context, generation=5), "TILEMAP_STALE_GENERATION"),
                 (replace(self.context, revision="sha256:" + "5" * 64), "TILEMAP_STALE_REVISION"),
                 (replace(self.context, stopped=True), "TILEMAP_STOPPED"),
                 (replace(self.context, lease_expires_ms=1500), "TILEMAP_DEADLINE")]
        for context, code in cases:
            with self.subTest(code=code):
                self.reject(self.request(), code, context=context)


if __name__ == "__main__":
    unittest.main()
