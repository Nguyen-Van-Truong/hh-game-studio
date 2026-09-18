"""Pure disposable-project patch plus read-only unit validation; never runs Godot."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import unittest

BASE_SHA256 = "52fbd9af5c6191ada5baf1d7195a75685ed5e27a95f4d244af8b4d679f8c00f2"
MARKER = "# S91_SPARSE_HELPER_BOUNDARY\n"
ANCHOR = "    var objects: float = Performance.get_monitor(Performance.OBJECT_COUNT)\n"
INSERTION = "    _s91_before_batch()\n    if _failed:\n        return\n"


def patch_native(raw: bytes, probe: str | bytes) -> bytes:
    if hashlib.sha256(raw).hexdigest() != BASE_SHA256:
        raise ValueError("S91_BASE_SOURCE")
    helper = probe.decode("utf-8-sig") if isinstance(probe, bytes) else probe
    if helper.count(MARKER) != 1 or not helper.startswith(MARKER):
        raise ValueError("S91_HELPER_BOUNDARY")
    if "func _s91_before_batch() -> void:" not in helper:
        raise ValueError("S91_HELPER_ENTRYPOINT")
    script = raw.decode("utf-8")
    start = script.index("func _write_batch() -> void:\n")
    end = script.index("\n\nfunc _wait_host_ack() -> void:\n", start)
    section = script[start:end]
    if section.count(ANCHOR) != 1:
        raise ValueError("S91_BATCH_COUNTER_PATCH_POINT")
    section = section.replace(ANCHOR, INSERTION + ANCHOR, 1)
    return (script[:start] + section + script[end:] + "\n" + helper.split(MARKER, 1)[1]).encode("utf-8")


def self_test(raw: bytes, probe: bytes) -> dict:
    class PatchTests(unittest.TestCase):
        def test_exact_round_trip(self):
            patched = patch_native(raw, probe).decode("utf-8")
            helper_body = probe.decode("utf-8-sig").split(MARKER, 1)[1]
            self.assertTrue(patched.endswith("\n" + helper_body))
            restored = patched[: -(len(helper_body) + 1)].replace(INSERTION, "", 1)
            self.assertEqual(restored.encode("utf-8"), raw)

        def test_hook_is_before_original_publication_counters(self):
            patched = patch_native(raw, probe).decode("utf-8")
            section = patched.split("func _write_batch() -> void:\n", 1)[1].split("func _wait_host_ack()", 1)[0]
            self.assertEqual(section.count(INSERTION), 1)
            self.assertIn(INSERTION + ANCHOR, section)
            self.assertLess(section.index(INSERTION), section.index('var name: String = "batch-'))

        def test_ack_unchanged(self):
            original = raw.decode("utf-8").split("func _wait_host_ack()", 1)[1]
            patched = patch_native(raw, probe).decode("utf-8").split("func _wait_host_ack()", 1)[1]
            self.assertTrue(patched.startswith(original))
            self.assertNotIn("file = null", original.split("func _advance_batch", 1)[0])

        def test_source_change_rejected(self):
            with self.assertRaisesRegex(ValueError, "S91_BASE_SOURCE"):
                patch_native(raw + b"\n", probe)

        def test_duplicate_patch_rejected(self):
            with self.assertRaisesRegex(ValueError, "S91_BASE_SOURCE"):
                patch_native(patch_native(raw, probe), probe)

        def test_bad_helper_rejected(self):
            for invalid in (probe.replace(MARKER.encode(), b""), probe + MARKER.encode(), MARKER.encode()):
                with self.assertRaises(ValueError):
                    patch_native(raw, invalid)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PatchTests)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    return {"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
            "base_sha256": hashlib.sha256(raw).hexdigest(),
            "probe_sha256": hashlib.sha256(probe).hexdigest(),
            "effective_sha256": hashlib.sha256(patch_native(raw, probe)).hexdigest(),
            "godot_executed": False, "files_written": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.add_argument("base", type=Path)
    parser.add_argument("probe", type=Path)
    args = parser.parse_args()
    print(json.dumps(self_test(args.base.read_bytes(), args.probe.read_bytes()), sort_keys=True))
