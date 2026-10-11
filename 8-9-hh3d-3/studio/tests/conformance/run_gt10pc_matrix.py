"""GT-10-PC requirement table and fail-closed evidence entry point.

Schema 1 was a host-only prototype mislabeled as native. Its generated PASS
rows, self-written exit.json and short install loop are invalid release proof.
Keep that raw for diagnosis, but never upgrade it to schema 2 or acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA = "hh-gt10pc-matrix-2"
ROW_DEFS = {
    "P1": ("host", "Signed v0.1 artifact, complete runtime closure, real schema/lock digests, SBOM/license/notice, flags and support docs"),
    "P2": ("host+native", "External pinned test public key; tamper/truncate/version/target rejected before unpack; native rejection preserves source"),
    "P3": ("native", "Two real fixtures on Windows and Linux headless installed from artifact; roundtrip+Play; source/save unchanged"),
    "P4": ("native", "Trusted compatible old/new upgrade and rollback; reject incompatible schema; roundtrip+Play on preserved copies"),
    "P5": ("native", "Ownership-based addon uninstall and reinstall preserves game/art/source/save and manual edits"),
    "P6": ("native", "Actual AUTH-07 discovery through install/upgrade/rollback; another project does not discover the profile"),
    "P7": ("native", "At most 8 process-kill/Stop lifecycle cuts; journal lookup same command_id; no repeated effect; last-good intact"),
    "P8": ("host", "Missing dependency/template/version actionable rejects, no latest fetch; artifact/closure verify before install"),
    "P9": ("docs+native", "Compatibility lock/runbook/known limits and scrubbed support bundle; independent consumer fixture smoke"),
    "P10": ("native", "GT08A PC regression and K8/K10 run from installed package with bound native receipts"),
    "P11": ("native", "Accepted formal25 machinery: 10x35 on frozen release, O5.6 lock and actual host exits; rehearsal one short iteration"),
    "P12": ("external", "Two independent different-model critics TICK=yes on the same frozen final manifest"),
}


def table() -> dict:
    return {key: {"evidence": value[0], "requirement": value[1],
                  "implementation": "INCOMPLETE"} for key, value in ROW_DEFS.items()}


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))
from studio.package.release_contract import (
    verify_package, digest_file, digest_bytes, safe_path, strict_json, need, HEX, _safe_member,
)
from studio.package.trust import load_trust

FIXTURES = ("gt09-arena", "gt09-room")
LEDGERS = ("project-before.json", "project-before-play.json", "project-after-play.json",
           "project-after-uninstall.json", "project-after-reinstall.json", "project-after-deactivate.json")


def _read(path: Path) -> dict:
    with safe_path(path).open("rb") as stream:
        raw = stream.read(16 * 1024**2 + 1)
    need(len(raw) <= 16 * 1024**2, "GT10PC_EVIDENCE_OVERSIZE")
    doc = strict_json(raw)
    need(isinstance(doc, dict), "GT10PC_EVIDENCE_OBJECT")
    return doc


def _process(base: Path, label: str, process: dict) -> str:
    need(isinstance(process, dict) and process.get("exit_code") == 0
         and process.get("wrapper_exit_code") == 0 and process.get("tree_verified") is True
         and process.get("timed_out") is False, "GT10PC_INSTALLED_EXIT")
    host = _read(base / (label + "-host.json"))
    need(type(host.get("target_pid")) is int and host["target_pid"] > 0
         and host["target_pid"] == process.get("target_pid") and type(host.get("exit_code")) is int
         and host["exit_code"] == 0, "GT10PC_HOST_EXIT_DISAGREES")
    need(process.get("host") == label + "-host.json"
         and process.get("stdout") == label + "-stdout.txt"
         and process.get("stderr") == label + "-stderr.txt"
         and process.get("ownership") == "gated_job_kill_on_close", "GT10PC_PROCESS_BINDING")
    stdout = safe_path(base / (label + "-stdout.txt")).read_text(encoding="utf-8")
    stderr = safe_path(base / (label + "-stderr.txt")).read_bytes()
    need(not stderr and not re.search(r"(?im)\b(error|warning|orphan)\b", stdout), "GT10PC_INSTALLED_LOG")
    return stdout


def _lifecycle(stdout: str) -> int:
    states, summaries, inputs = [], [], []
    for line in stdout.splitlines():
        for marker, rows in (("HH_FIXTURE_LIFECYCLE_STATE ", states),
                             ("HH_FIXTURE_LIFECYCLE_SUMMARY ", summaries),
                             ("HH_FIXTURE_LIFECYCLE_INPUT ", inputs)):
            if line.startswith(marker):
                rows.append(strict_json(line[len(marker):].encode()))
    expected = ["menu", "start", "pause", "resume", "restart", "pause", "resume", "quit"]
    need([r.get("event") for r in states] == expected and len(summaries) == 1,
         "GT10PC_LIFECYCLE_TRANSITIONS")
    summary = summaries[0]
    need(summary.get("transitions") == expected[1:] and summary.get("lifecycle_complete") is True
         and summary.get("freeze_errors") == 0 and summary.get("seed") == 90127
         and summary.get("pause_frames", 0) > 0 and summary.get("mode") == "smoke"
         and summary.get("reason") == "input_quit" and summary.get("input_edges") == len(inputs)
         and len(inputs) >= 20 and summary.get("state_observations") == 8,
         "GT10PC_LIFECYCLE_SUMMARY")
    need(all(r.get("freeze_errors") == 0 and r.get("seed") == 90127 for r in states),
         "GT10PC_LIFECYCLE_STATE")
    for i in (2, 5):
        pause, resume = states[i:i+2]
        need(pause.get("tree_paused") is True and resume.get("tree_paused") is False
             and pause.get("phase") == "PAUSED" and resume.get("phase") == "PLAYING"
             and pause["world"] == resume["world"], "GT10PC_PAUSE_WORLD_MUTATION")
    need(all(r["world"].get("avatar_asset_loaded") is True and r["world"].get("sprite_asset_loaded") is True
             for r in states), "GT10PC_FIXTURE_ASSETS")
    return len(states)


def _verify_native_producer(path: Path, *, trust: Path, trust_sha256: str) -> dict:
    path = safe_path(path)
    producer = _read(path / "producer.json")
    need(producer.get("schema") == "HH-GT10PC-NATIVE-PRODUCER-3"
         and producer.get("authority") == 0 and producer.get("acceptance") is False
         and producer.get("mode") == "DIAGNOSTIC", "GT10PC_NATIVE_PRODUCER_SCHEMA")
    keys = load_trust(trust, expected_sha256=trust_sha256)
    need(producer.get("trust_sha256") == trust_sha256, "GT10PC_EXTERNAL_TRUST_BINDING")
    package = verify_package(path / "release.hhpkg", trusted_keys=keys, target="Windows")
    manifest = package["manifest"]
    need(package["archive_sha256"] == producer.get("artifact_sha256")
         and package["manifest_sha256"] == producer.get("manifest_sha256")
         and manifest["source_closure_sha256"] == producer.get("source_closure_sha256"),
         "GT10PC_ARTIFACT_BINDING")
    evidence = producer.get("evidence")
    need(isinstance(evidence, dict), "GT10PC_EVIDENCE_LEDGER")
    required = set()
    for fixture in FIXTURES:
        required.update("consumer/" + fixture + "/" + name for name in LEDGERS)
        for domain, labels in (("drivers", ("driver",)), ("godot", ("parse", "godot"))):
            required.add(domain + "/" + fixture + "/receipt.json")
            required.update(domain + "/" + fixture + "/" + label + suffix
                            for label in labels for suffix in ("-host.json", "-stdout.txt", "-stderr.txt"))
    need(required <= set(evidence), "GT10PC_EVIDENCE_MISSING")
    for name, expected in evidence.items():
        _safe_member(name)
        need(isinstance(expected, str) and HEX.fullmatch(expected)
             and digest_file(path / name) == expected, "GT10PC_EVIDENCE_CHANGED:" + name)
    fixtures = producer.get("fixtures")
    need(isinstance(fixtures, list) and len(fixtures) == 2
         and {r.get("fixture") for r in fixtures} == set(FIXTURES), "GT10PC_NATIVE_FIXTURE_SET")
    lock = strict_json(package["members"]["payload/studio/toolchain.lock.json"])
    addon_prefix = "payload/studio/godot-addon/addons/hh_studio/"
    addon = {"addons/hh_studio/" + k[len(addon_prefix):]: v for k, v in manifest["files"].items()
             if k.startswith(addon_prefix)}
    addon["addons/hh_studio/jcs_godot.gd"] = manifest["files"]["payload/studio/protocol/jcs_godot.gd"]
    checked = []
    for row in fixtures:
        fixture = row["fixture"]
        for key in ("install_receipt", "reinstall_receipt"):
            receipt = row.get(key, {})
            need(receipt.get("status") == "COMMITTED" and receipt.get("action") == "install"
                 and receipt.get("active") == package["manifest_sha256"]
                 and receipt.get("package_id") == manifest["package_id"]
                 and receipt.get("source_closure_sha256") == manifest["source_closure_sha256"],
                 "GT10PC_INSTALL_RECEIPT_BINDING")
        need(row.get("deactivate_receipt", {}).get("active") is None, "GT10PC_DEACTIVATE_RECEIPT")
        ledger_hashes = row.get("ledger_sha256")
        need(isinstance(ledger_hashes, dict) and set(ledger_hashes) == set(LEDGERS), "GT10PC_CONSUMER_LEDGER_RECEIPT")
        ledgers = {}
        for name in LEDGERS:
            rel = "consumer/" + fixture + "/" + name
            need(ledger_hashes[name] == evidence[rel], "GT10PC_CONSUMER_LEDGER_HASH")
            ledgers[name] = _read(path / rel)
        baseline = ledgers["project-before.json"]
        # Bind the baseline to fixture files inside the signed artifact, plus
        # the explicit consumer save. Do not let two equal empty ledgers pass.
        fixture_prefix = "payload/studio/fixtures/" + fixture + "/"
        expected_baseline = {k[len(fixture_prefix):]: v for k, v in manifest["files"].items() if k.startswith(fixture_prefix)}
        save = b"consumer-save-before-install\n"
        expected_baseline["owner-save.dat"] = {"sha256": digest_bytes(save), "size": len(save)}
        need(baseline == expected_baseline, "GT10PC_CONSUMER_BASELINE")
        manual_bytes = b"owner edit must survive uninstall\n"
        manual = {"addons/hh_studio/owner-manual-note.txt":
                  {"sha256": digest_bytes(manual_bytes), "size": len(manual_bytes)}}
        installed = {**baseline, **addon, **manual}
        for name in ("project-before-play.json", "project-after-play.json", "project-after-reinstall.json", "project-after-deactivate.json"):
            need(ledgers[name] == installed, "GT10PC_CONSUMER_LEDGER_MUTATION:" + name)
        need(ledgers["project-after-uninstall.json"] == {**baseline, **manual}, "GT10PC_CONSUMER_UNINSTALL_MUTATION")
        driver_base, native_base = path / "drivers" / fixture, path / "godot" / fixture
        _process(driver_base, "driver", _read(driver_base / "receipt.json"))
        receipt = _read(native_base / "receipt.json")
        need(receipt.get("schema") == "hh-installed-native-probe-2"
             and receipt.get("active_release") == package["manifest_sha256"]
             and receipt.get("godot_sha256") == lock["godot"]["console_sha256"]
             and receipt.get("probe_sha256") == manifest["files"]["payload/studio/package/installed_probe.py"]["sha256"]
             and receipt.get("launcher_sha256") == manifest["files"]["payload/studio/build/bootstrap/run_fixture.py"]["sha256"],
             "GT10PC_INSTALLED_SOURCE_BINDING")
        expected_studio = path / "consumer" / fixture / "install/releases" / package["manifest_sha256"] / "payload/studio"
        need(safe_path(Path(receipt.get("studio", ""))) == expected_studio, "GT10PC_INSTALLED_LOCATION")
        _process(native_base, "parse", receipt.get("parse"))
        stdout = _process(native_base, "godot", receipt.get("process"))
        lifecycle = _lifecycle(stdout)
        checked.append({"fixture": fixture, "exit": 0, "lifecycle": lifecycle, "authority": 0})
    return {"status": "DIAGNOSTIC_NATIVE_VERIFIED", "authority": 0, "fixtures": checked,
            "artifact_sha256": package["archive_sha256"], "evidence_files": len(evidence)}


def verify_only(path: Path, *, trust: Path, trust_sha256: str) -> int:
    doc = _read(path / "matrix.json")
    need(doc.get("schema") == SCHEMA and doc.get("acceptance") is False
         and doc.get("authority") == 0 and doc.get("producer") == "producer.json"
         and doc.get("mode") == "DIAGNOSTIC", "GT10PC_LEGACY_SYNTHETIC_EVIDENCE_VOID")
    need(doc.get("producer_sha256") == digest_file(path / "producer.json"), "GT10PC_PRODUCER_HASH")
    raw = _verify_native_producer(path, trust=trust, trust_sha256=trust_sha256)
    print(json.dumps({"schema": SCHEMA, "authority": 0, "acceptance": False, "raw": raw}, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--verify-only", type=Path)
    mode.add_argument("--matrix", choices=("rehearsal", "final"))
    parser.add_argument("--trust", type=Path)
    parser.add_argument("--trust-sha256")
    parser.add_argument("--rows")
    parser.add_argument("--run-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    rows = args.rows.split(",") if args.rows else list(ROW_DEFS)
    if any(row not in ROW_DEFS for row in rows) or len(rows) != len(set(rows)):
        parser.error("unknown or duplicate row")
    if args.matrix == "final" and args.rows:
        parser.error("final must run the entire frozen matrix")
    if args.dry_run:
        print(json.dumps({"schema": SCHEMA, "authority": 0, "acceptance": False,
                          "status": "PLAN_ONLY", "rows": table()}, sort_keys=True))
        return 0
    try:
        if args.verify_only:
            need(args.trust is not None and args.trust_sha256 is not None, "GT10PC_EXTERNAL_TRUST_REQUIRED")
            return verify_only(args.verify_only, trust=args.trust, trust_sha256=args.trust_sha256)
        raise ValueError("GT10PC_PRODUCERS_INCOMPLETE_FINAL_AND_REHEARSAL_DISABLED")
    except (ValueError, OSError) as exc:
        print(json.dumps({"schema": SCHEMA, "status": "DIAGNOSTIC_FAIL",
                          "authority": 0, "acceptance": False, "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
