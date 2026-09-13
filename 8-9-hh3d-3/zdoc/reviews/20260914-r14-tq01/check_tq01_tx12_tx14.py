"""Offline candidate audit for GT-01 TQ01/TX12/TX14.

This checker never downloads, launches an engine, or mutates the product.  It
only reads the pinned lock, the prior official candidate package, and the
synthetic lifecycle candidate.  A PASS here is a candidate check, never WP
acceptance: the source must still be frozen and reviewed by two independent
critics.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[2]
STUDIO = PRODUCT / "studio"
REVIEWS = PRODUCT / "zdoc" / "reviews"
OFFICIAL = REVIEWS / "20260913-r13-official"
EVIDENCE = OFFICIAL / "evidence.json"
LIFECYCLE = REVIEWS / "20260913-r11" / "lifecycle-candidate.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load_module("gt01_runner_r14", STUDIO / "build" / "bootstrap" / "run_fixture.py")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def is_host_path(value: str) -> bool:
    return bool(re.match(r"^(?:[A-Za-z]:[\\/]|[\\/]{2}|/Users/|/home/)", value))


def walk_strings(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_strings(item)
    elif isinstance(value, str):
        yield value


class CandidateChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = read_json(EVIDENCE)
        cls.lock = read_json(STUDIO / "toolchain.lock.json")

    def test_tq01_lock_is_pinned_and_portable(self):
        godot = self.lock["godot"]
        self.assertEqual(self.lock["schema"], "HH-STUDIO-TOOLCHAIN-LOCK-2")
        self.assertEqual(godot["version"], "4.7.2-stable")
        self.assertRegex(godot["source_commit"], r"^[0-9a-f]{40}$")
        for value in walk_strings(self.lock):
            # URLs and hashes are intentionally allowed; lock values must not
            # contain a machine-specific path.
            if value.startswith(("http://", "https://")):
                continue
            self.assertFalse(is_host_path(value), value)

    def test_tq01_unicode_cache_isolation(self):
        fixture = STUDIO / "fixtures" / "sample-game"
        with tempfile.TemporaryDirectory(prefix="GT01 Unicode 测试 ") as temp:
            root = Path(temp) / "snapshot space-đ"
            shutil.copytree(fixture, root)
            # Generated caches are deliberately present in the copied tree;
            # checked_files must omit them from the source closure.
            (root / ".godot").mkdir()
            (root / ".godot" / "cache.bin").write_bytes(b"cache")
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "ignored.pyc").write_bytes(b"cache")
            closure = RUNNER.checked_files(root)
            self.assertTrue(closure)
            self.assertTrue(all(not part.startswith((".godot", "__pycache__")) for part in closure))
            self.assertTrue(root.resolve().is_relative_to(Path(temp).resolve()))

    def test_tq01_host_exits_are_independent_and_tree_gated(self):
        self.assertEqual(self.evidence["status"], "CANDIDATE")
        runs = self.evidence["runs"]
        self.assertEqual(len(runs), 3)
        for run in runs:
            self.assertIsInstance(run.get("exit_code"), int)
            self.assertIsInstance(run.get("wrapper_exit_code"), int)
            self.assertFalse(run.get("timed_out"))
            self.assertTrue(run.get("tree_verified"))
            host = read_json(OFFICIAL / run["stdout"].replace("-stdout.txt", "-host.json"))
            self.assertEqual(host["exit_code"], run["exit_code"])
            self.assertIsInstance(host.get("target_pid"), int)
        self.assertTrue(self.evidence["checks"]["process_tree_verified"])

    def test_tx12_synthetic_cas_lifecycle_candidate(self):
        report = read_json(LIFECYCLE)
        self.assertEqual(report["status"], "CANDIDATE")
        self.assertTrue(report["stale_transition_rejected"])
        self.assertTrue(report["replacement_lock_rejected"])
        self.assertEqual(report["rollback_current"]["package"], report["package_a"]["package"])

    def test_tx14_limits_and_no_secret_material(self):
        limits = self.evidence.get("limits", [])
        self.assertTrue(any("TQ01" in item and "TX12" in item and "TX14" in item for item in limits))
        # Evidence must never contain a bearer token or an unredacted common
        # secret field.  This is a hygiene check, not proof of auth behavior.
        for path in [EVIDENCE, *OFFICIAL.glob("*.txt")]:
            text = path.read_text(encoding="utf-8", errors="strict")
            self.assertIsNone(re.search(r"(?i)bearer\\s+[A-Za-z0-9._-]{16,}", text), str(path))
            self.assertIsNone(re.search(r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token)\\s*[:=]\\s*\\S+", text), str(path))


def run() -> dict:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CandidateChecks)
    result = unittest.TestResult()
    suite.run(result)
    checks = len(result.failures) == 0 and len(result.errors) == 0
    failures = [f"{test}: {trace.splitlines()[-1]}" for test, trace in result.failures + result.errors]
    report = {
        "schema": "hh-gt01-tq01-tx12-tx14-candidate-v1",
        "status": "CANDIDATE" if checks else "GAP",
        "run_id": "GT01-R14-TQ01-20260914",
        "checks_run": result.testsRun,
        "checks_passed": result.testsRun - len(result.failures) - len(result.errors),
        "failures": failures,
        "source_hashes_observed": {
            "toolchain_lock": sha256(STUDIO / "toolchain.lock.json"),
            "runner": sha256(STUDIO / "build" / "bootstrap" / "run_fixture.py"),
        },
        "limits": [
            "offline checks do not prove network denial, token rotation, or paid-quota fairness",
            "TX12 uses synthetic packages; live-owner/crash recovery/manual reconciliation remain unexecuted",
            "official evidence is historical candidate data and must be reminted after source freeze",
            "two independent critics on one frozen source hash are still required",
        ],
    }
    (HERE / "tq01-tx12-tx14-candidate.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md = [
        "# GT-01 TQ01/TX12/TX14 candidate audit — 2026-09-14",
        "",
        f"Status: **{report['status']}** ({report['checks_passed']}/{report['checks_run']} offline checks).",
        "",
        "The checker validates lock portability, Unicode/cache isolation, independent host exit fields, synthetic CAS rollback, and evidence secret hygiene.",
        "It does not grant acceptance and does not replace an official remint or the two required read-only critics.",
        "",
        "## Remaining gaps",
        *[f"- {item}" for item in report["limits"]],
        "",
        "## Reproduction",
        "`python check_tq01_tx12_tx14.py`",
    ]
    (HERE / "REVIEW-RESULT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
