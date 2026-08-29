#!/usr/bin/env python3
"""VF1-WP4 structure check: runtime diagnostics + bridge schema.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_runtime_api.gd). Does not fetch Y8.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SRC = ROOT / "src" / "runtime"
RUNTIME_DATA = ROOT / "data" / "runtime"
LEDGER = ROOT / "docs" / "reference-ledger.md"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"
DOCS = ROOT / "docs" / "runtime-diagnostics.md"

REQUIRED_SCRIPTS = (
    "runtime_constants.gd",
    "runtime_redact.gd",
    "runtime_checkpoint.gd",
    "runtime_api.gd",
)

REQUIRED_DATA = (
    "schema.json",
    "bridge.json",
)

REQUIRED_OPS = (
    "observe",
    "checkpoint.create",
    "checkpoint.restore",
    "pause",
    "resume",
)

TRADEMARK = re.compile(r"Superfighters|Super Fighter")
SECRET_LEAK = re.compile(r"test-fixture-not-a-secret")


def main() -> int:
    errors: list[str] = []
    for name in REQUIRED_SCRIPTS:
        path = RUNTIME_SRC / name
        if not path.is_file():
            errors.append(f"missing {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        if TRADEMARK.search(text):
            errors.append(f"{name} contains Superfighters trademark")
    for name in REQUIRED_DATA:
        path = RUNTIME_DATA / name
        if not path.is_file():
            errors.append(f"missing {path.relative_to(ROOT)}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{name} is not JSON: {exc}")
            continue
        if not isinstance(payload, dict):
            errors.append(f"{name} must be an object")
            continue
        if payload.get("title") != "Vault Fighters":
            errors.append(f"{name} title must be Vault Fighters")
        if TRADEMARK.search(json.dumps(payload)):
            errors.append(f"{name} contains Superfighters trademark")
    schema_path = RUNTIME_DATA / "schema.json"
    if schema_path.is_file():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if schema.get("schema") != "vf.runtime.v1":
            errors.append("runtime schema id mismatch")
        if schema.get("tick_hz") != 60:
            errors.append("runtime schema tick_hz must be 60")
        if schema.get("y8_tick_rate_claimed") is not False:
            errors.append("runtime schema must set y8_tick_rate_claimed false")
        if schema.get("ledger_clock") != "RL-SIM-FIXED-60":
            errors.append("runtime schema must cite RL-SIM-FIXED-60")
        if schema.get("ledger_observe") != "RL-RUNTIME-OBSERVE":
            errors.append("runtime schema must cite RL-RUNTIME-OBSERVE")
        if schema.get("observe", {}).get("mutate") is not False:
            errors.append("observe must be read-only")
    bridge_path = RUNTIME_DATA / "bridge.json"
    if bridge_path.is_file():
        bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
        if bridge.get("schema") != "vf.runtime.bridge.v1":
            errors.append("bridge schema id mismatch")
        if bridge.get("auth", {}).get("echo_token") is not False:
            errors.append("bridge must not echo tokens")
        ops = bridge.get("ops", {})
        for op in REQUIRED_OPS:
            if op not in ops:
                errors.append(f"bridge missing op {op}")
        observe = ops.get("observe", {})
        if observe.get("mutate") is not False:
            errors.append("bridge observe must set mutate false")
        if observe.get("permission") != "observe":
            errors.append("bridge observe permission mismatch")
        restore = ops.get("checkpoint.restore", {})
        if restore.get("mutate") is not True:
            errors.append("bridge checkpoint.restore must mutate")
        redact = bridge.get("redact_keys", [])
        for key in ("token", "secret", "password"):
            if key not in redact:
                errors.append(f"bridge redact_keys missing {key}")
    title = TITLE.read_text(encoding="utf-8")
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    if "Superfighters" in title or "Super Fighter" in title:
        errors.append("title_screen.gd contains Superfighters string")
    if not DOCS.is_file():
        errors.append("missing docs/runtime-diagnostics.md")
    else:
        docs = DOCS.read_text(encoding="utf-8")
        if "ledger:RL-SIM-FIXED-60" not in docs:
            errors.append("runtime docs must cite ledger:RL-SIM-FIXED-60")
        if "does **not** claim y8 parity" not in docs.lower():
            errors.append("runtime docs lost honesty phrase")
        if SECRET_LEAK.search(docs):
            errors.append("runtime docs leaked the test fixture token")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in ("RL-SIM-FIXED-60", "RL-RUNTIME-OBSERVE", "RL-CTRL-HOLD-AIM", "RL-MOVE-ROLL-DIVE"):
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    evidence = ROOT / "docs" / "evidence"
    if evidence.is_dir():
        for path in evidence.rglob("*"):
            if path.is_file() and "VF1WP4" in path.as_posix():
                text = path.read_text(encoding="utf-8", errors="ignore")
                if SECRET_LEAK.search(text):
                    errors.append(f"{path.relative_to(ROOT)} leaked the test fixture token")
    if errors:
        print("FAIL: Vault Fighters VF1-WP4 runtime files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF1-WP4 runtime files")
    print(f"  scripts={len(REQUIRED_SCRIPTS)} data={len(REQUIRED_DATA)} ops={len(REQUIRED_OPS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
