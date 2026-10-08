from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from studio.tests.godot.catalog_gameplay_handoff import (
    CatalogGameplayHandoffError,
    read_blender_content_artifacts,
    inspect_blender_content_publication,
    mount_catalog_arena,
    room_runtime_gap,
    verify_catalog_arena_handoff,
)


STUDIO = Path(__file__).resolve().parents[2]
CATALOG = STUDIO / ".local/reviews/o2-catalog-arena-gt09content07-arena-native04"
REGISTERED = STUDIO / ".local/reviews/o2-registered-authoring-gt09content07-arena-native04"
ROOM_CATALOG = STUDIO / ".local/reviews/o2-catalog-room-gt09content07-room-native"
ROOM_REGISTERED = STUDIO / ".local/reviews/o2-registered-authoring-gt09content07-room-native"
BLENDER = STUDIO / ".local/reviews/gt09-content-native-20261008-07/hh-files-80821f35ea244d648c13ae113986acee"


class CatalogGameplayHandoffTests(unittest.TestCase):
    def test_arena_chain_binds_native_scene_and_owner_receipt(self):
        handoff = verify_catalog_arena_handoff(CATALOG, REGISTERED)
        self.assertEqual(handoff.authority, 0)
        self.assertFalse(handoff.public_ack)
        self.assertEqual(handoff.native_run_id, CATALOG.name)
        self.assertEqual(handoff.scene_bytes,
                         (CATALOG / "project/scenes/authored.tscn").read_bytes())
        self.assertEqual(handoff.provenance["transaction_digest"], handoff.transaction_digest)

    def test_blender_publication_is_bound_read_only(self):
        handoff = verify_catalog_arena_handoff(CATALOG, REGISTERED)
        observed = inspect_blender_content_publication(BLENDER, handoff)
        self.assertTrue(observed["read_only"])
        self.assertFalse(observed["public_ack"])
        self.assertEqual(observed["handoff"]["command_id"], "gt09-content-native-20261008-07")

    def test_blender_artifact_helper_returns_protected_exact_bytes(self):
        handoff = verify_catalog_arena_handoff(CATALOG, REGISTERED)
        artifacts = read_blender_content_artifacts(BLENDER, handoff)
        self.assertFalse(artifacts["public_ack"])
        self.assertEqual(artifacts["artifact_sha256"]["scene.glb"],
                         handoff.provenance["blender_handoff"]["glb_sha256"])
        self.assertEqual(artifacts["artifact_sha256"]["sprite_sheet.png"],
                         handoff.provenance["blender_handoff"]["sprite_sha256"])
        self.assertGreater(len(artifacts["scene_glb_bytes"]), 0)
        self.assertGreater(len(artifacts["sprite_sheet_bytes"]), 0)

    def test_mount_preserves_exact_native_bytes_and_refuses_replacement(self):
        handoff = verify_catalog_arena_handoff(CATALOG, REGISTERED)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            mounted = mount_catalog_arena(handoff, root)
            self.assertEqual(mounted.read_bytes(), handoff.scene_bytes)
            with self.assertRaisesRegex(CatalogGameplayHandoffError, "CATALOG_ARENA_EXISTS"):
                mount_catalog_arena(handoff, root)

    def test_room_report_identifies_dynamic_builder_gaps(self):
        report = room_runtime_gap()
        self.assertEqual(report["authority"], 0)
        self.assertFalse(report["public_ack"])
        self.assertEqual(report["current_builder"],
                         "tests/godot/gameplay_fixture/room3d_native.gd")
        self.assertTrue(report["current_scene_gaps"]["pickup"])
        self.assertTrue(report["current_scene_gaps"]["hud"])
        self.assertTrue(any("thin catalog-room adapter" in row
                            for row in report["smallest_runtime_changes"]))

    def test_room_chain_binds_native_scene_and_owner_receipt(self):
        from studio.tests.godot.catalog_gameplay_handoff import verify_catalog_room_handoff
        handoff = verify_catalog_room_handoff(ROOM_CATALOG, ROOM_REGISTERED)
        self.assertEqual(handoff.authority, 0)
        self.assertFalse(handoff.public_ack)
        self.assertEqual(handoff.scene_bytes,
                         (ROOM_CATALOG / "project/scenes/authored.tscn").read_bytes())


if __name__ == "__main__":
    unittest.main()
