import json
from pathlib import Path
import tempfile
import unittest

from tests.conformance import run_gt09_playtest_evidence as packer


class GT09PlaytestEvidenceTests(unittest.TestCase):
    def test_run_root_rejects_traversal_and_wrong_shape(self):
        with self.assertRaisesRegex(ValueError, "invalid_run_id"):
            packer._run_root("../gt09-playtest-20261009-20", "arena")
        with self.assertRaisesRegex(ValueError, "invalid_fixture"):
            packer._run_root("gt09-playtest-20261009-20", "other")

    def test_pack_rejects_legacy_copy_before_consuming_outputs(self):
        original = packer.RAW_ROOT
        try:
            with tempfile.TemporaryDirectory(prefix="gt09-playtest-pack-") as temp:
                packer.RAW_ROOT = Path(temp)
                root = packer._run_root("gt09-playtest-20261009-20", "arena")
                root.mkdir(parents=True)
                (root / "metadata.json").write_text(json.dumps({
                    "run_id": "gt09-playtest-20261009-20", "fixture": "arena",
                    "source_mode": "legacy-copy", "legacy_unaccepted": True,
                }), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "native_publication_snapshot_required"):
                    packer.pack(run_id="gt09-playtest-20261009-20", fixture="arena")
                self.assertFalse((root / "manifest.json").exists())
        finally:
            packer.RAW_ROOT = original

    def test_pack_refuses_to_replace_existing_manifest(self):
        original = packer.RAW_ROOT
        try:
            with tempfile.TemporaryDirectory(prefix="gt09-playtest-pack-") as temp:
                packer.RAW_ROOT = Path(temp)
                root = packer._run_root("gt09-playtest-20261009-21", "room")
                root.mkdir(parents=True)
                (root / "manifest.json").write_text("{}", encoding="utf-8")
                with self.assertRaisesRegex(FileExistsError, "PLAYTEST_MANIFEST_EXISTS"):
                    packer.pack(run_id="gt09-playtest-20261009-21", fixture="room")
        finally:
            packer.RAW_ROOT = original


if __name__ == "__main__":
    unittest.main()
