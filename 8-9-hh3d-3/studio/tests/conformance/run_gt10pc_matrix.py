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


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_native_producer(path: Path) -> dict:
    """Parse host receipts and raw Godot logs; never trust caller booleans."""
    producer_path = path / "producer.json"
    if not producer_path.is_file():
        raise ValueError("GT10PC_NATIVE_PRODUCER_MISSING")
    producer = json.loads(producer_path.read_text(encoding="utf-8"))
    if producer.get("schema") not in ("HH-GT10PC-NATIVE-PRODUCER-1", "HH-GT10PC-NATIVE-PRODUCER-2") or producer.get("authority") != 0:
        raise ValueError("GT10PC_NATIVE_PRODUCER_SCHEMA")
    fixtures = producer.get("fixtures")
    if not isinstance(fixtures, list) or {row.get("fixture") for row in fixtures} != {"gt09-arena", "gt09-room"}:
        raise ValueError("GT10PC_NATIVE_FIXTURE_SET")
    checked = []
    for row in fixtures:
        fixture = row["fixture"]
        for key in ("before", "after_play", "after_uninstall"):
            if key not in row:
                raise ValueError("GT10PC_NATIVE_RECEIPT_FIELD:" + key)
        if producer["schema"] == "HH-GT10PC-NATIVE-PRODUCER-2":
            install = row.get("install_receipt", {})
            reinstall = row.get("reinstall_receipt", {})
            if install.get("status") != "COMMITTED" or install.get("action") != "install" or reinstall.get("status") != "COMMITTED":
                raise ValueError("GT10PC_INSTALL_RECEIPT")
            if install.get("active") != reinstall.get("active") or not install.get("package_id"):
                raise ValueError("GT10PC_IMMUTABLE_REINSTALL")
            if row.get("deactivate_receipt", {}).get("action") != "deactivate":
                raise ValueError("GT10PC_DEACTIVATE_RECEIPT")
        for phase in ("after_play", "after_uninstall"):
            if row["before"]["source"] != row[phase]["source"] or row["before"]["save"] != row[phase]["save"]:
                raise ValueError("GT10PC_CONSUMER_DATA_CHANGED")
        ledger_names = ("project-before.json", "project-before-play.json", "project-after-play.json", "project-after-uninstall.json",
                        "project-after-reinstall.json", "project-after-deactivate.json")
        ledger_hashes = row.get("ledger_sha256")
        if not isinstance(ledger_hashes, dict) or set(ledger_hashes) != set(ledger_names):
            raise ValueError("GT10PC_CONSUMER_LEDGER_RECEIPT")
        ledgers = {}
        for name in ledger_names:
            ledger_path = path / "consumer" / fixture / name
            if not ledger_path.is_file() or _digest(ledger_path) != ledger_hashes[name]:
                raise ValueError("GT10PC_CONSUMER_LEDGER_HASH")
            ledgers[name] = json.loads(ledger_path.read_bytes())
        if ledgers["project-before-play.json"] != ledgers["project-after-play.json"]:
            raise ValueError("GT10PC_CONSUMER_LEDGER_PLAY_MUTATION")
        if ledgers["project-before.json"].get("project.godot") != ledgers["project-after-uninstall.json"].get("project.godot"):
            raise ValueError("GT10PC_CONSUMER_LEDGER_UNINSTALL_SOURCE")
        if ledgers["project-after-reinstall.json"] != ledgers["project-after-deactivate.json"]:
            raise ValueError("GT10PC_CONSUMER_LEDGER_DEACTIVATE_MUTATION")
        receipt_path = path / "godot" / fixture / "receipt.json"
        if not receipt_path.is_file():
            raise ValueError("GT10PC_INSTALLED_RECEIPT_MISSING")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        process = receipt.get("process", {})
        if process.get("exit_code") != 0 or process.get("wrapper_exit_code") != 0 or process.get("tree_verified") is not True or process.get("timed_out") is not False:
            raise ValueError("GT10PC_INSTALLED_EXIT")
        stdout = path / "godot" / fixture / "godot-stdout.txt"
        stderr = path / "godot" / fixture / "godot-stderr.txt"
        if not stdout.is_file() or not stderr.is_file() or stderr.read_text(encoding="utf-8"):
            raise ValueError("GT10PC_INSTALLED_LOG")
        raw_stdout = stdout.read_text(encoding="utf-8")
        lifecycle = raw_stdout.count("HH_FIXTURE_LIFECYCLE_STATE")
        if lifecycle < 2 or re.search(r"(?im)\b(error|warning|orphan)\b", raw_stdout):
            raise ValueError("GT10PC_INSTALLED_PLAY")
        checked.append({"fixture": fixture, "exit": process["exit_code"], "lifecycle": lifecycle, "authority": 0})
    return {"status": "DIAGNOSTIC_NATIVE_VERIFIED", "authority": 0, "fixtures": checked}


def verify_only(path: Path) -> int:
    """Reject legacy banners; parse only raw native receipts for diagnostics."""
    document_path = path / "matrix.json"
    if not document_path.is_file():
        raise ValueError("GT10PC_MATRIX_MISSING")
    doc = json.loads(document_path.read_bytes())
    if doc.get("schema") != SCHEMA:
        raise ValueError("GT10PC_LEGACY_SYNTHETIC_EVIDENCE_VOID")
    raw = _verify_native_producer(path)
    print(json.dumps({"schema": SCHEMA, "authority": 0, "acceptance": False, "raw": raw}, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--verify-only", type=Path)
    mode.add_argument("--matrix", choices=("rehearsal", "final"))
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
            return verify_only(args.verify_only)
        raise ValueError("GT10PC_PRODUCERS_INCOMPLETE_FINAL_AND_REHEARSAL_DISABLED")
    except (ValueError, OSError) as exc:
        print(json.dumps({"schema": SCHEMA, "status": "DIAGNOSTIC_FAIL",
                          "authority": 0, "acceptance": False, "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
