#!/usr/bin/env python3
"""R2-WP1: live ActionDef catalog, envelope, generated contracts, executed matrix.

Fails (exit != 0) if:
  - any REQUIRED_VERBS id is missing from the live catalog
  - the 4-way invalid + 1 positive matrix is not executed (or a case fails)
  - generated artifacts lack a DO NOT EDIT / generated header
  - npm run generate dirties those artifacts
  - godot/plugin-project/addons exists
  - plan R2-WP1 is ticked or CURRENT_VALID_WP is not R2-WP1

Does not run Godot. Stdlib + the already-pinned bridge Node/tsc toolchain.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BRIDGE = REPO_ROOT / "bridge"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_ADDONS = REPO_ROOT / "godot" / "plugin-project" / "addons"
GENERATED = (
    BRIDGE / "generated" / "mcp-tools.json",
    BRIDGE / "generated" / "cli-help.txt",
    BRIDGE / "generated" / "plugin-validator.json",
    REPO_ROOT / "docs" / "godot-agent" / "ACTIONS.md",
    REPO_ROOT / "docs" / "godot-agent" / "CONTRACT_MATRIX.md",
)
HEADER_RE = re.compile(r"DO NOT EDIT|AUTO-GENERATED", re.IGNORECASE)


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def npm() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plan_errors(text: str) -> list[str]:
    """Allow pre-tick (implementer) or post-tick (coordinator) plan state."""
    errors: list[str] = []
    current = ""
    wp1 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R2-WP1\b", stripped):
            wp1 = stripped
    if wp1 is None:
        errors.append("plan missing R2-WP1 heading")
        return errors
    ticked = bool(re.search(r"\[x\]", wp1, re.IGNORECASE))
    if not ticked:
        if current != "R2-WP1":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R2-WP1 while WP1 is unticked)")
        if "[ ]" not in wp1:
            errors.append("R2-WP1 heading must keep [ ] until coordinator tick")
    else:
        if current != "R2-WP2":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R2-WP2 after R2-WP1 tick)")
    return errors


def header_errors() -> list[str]:
    errors: list[str] = []
    for path in GENERATED:
        if not path.is_file():
            errors.append(f"missing generated artifact {rel(path)}")
            continue
        blob = path.read_text(encoding="utf-8")
        if not HEADER_RE.search(blob):
            errors.append(f"{rel(path)} missing DO NOT EDIT / generated header")
    return errors


def artifact_digests() -> dict[str, str]:
    return {rel(path): file_digest(path) for path in GENERATED if path.is_file()}


def main() -> int:
    errors: list[str] = []

    if PLUGIN_ADDONS.exists():
        errors.append("godot/plugin-project/addons must stay absent (R2-WP1 is registry only)")

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.is_file() else None
    if plan_text is None:
        errors.append(f"missing {rel(PLAN)}")
    else:
        errors.extend(plan_errors(plan_text))

    gen1 = run([npm(), "run", "generate"], BRIDGE)
    if gen1.returncode != 0:
        errors.append(f"npm run generate failed:\n{gen1.stdout}\n{gen1.stderr}")
        print("FAIL: registry check", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    errors.extend(header_errors())

    mcp_path = BRIDGE / "generated" / "mcp-tools.json"
    if mcp_path.is_file():
        mcp = json.loads(mcp_path.read_text(encoding="utf-8"))
        tool_count = int(mcp.get("tool_count") or 0)
        action_count = int(mcp.get("action_count") or 0)
        tools = mcp.get("tools") if isinstance(mcp.get("tools"), list) else []
        if tool_count >= 50 or len(tools) >= 50:
            errors.append(
                f"mcp-tools.json must be few domain tools, not one per verb "
                f"(tool_count={tool_count})"
            )
        if action_count < 118:
            errors.append(f"mcp-tools.json action_count={action_count} (need ~119)")
        if mcp.get("shape") != "domain-tools-plus-action-discriminator":
            errors.append("mcp-tools.json must declare discriminated domain tools")

    before = artifact_digests()
    gen2 = run([npm(), "run", "generate"], BRIDGE)
    if gen2.returncode != 0:
        errors.append(f"npm run generate (drift) failed:\n{gen2.stdout}\n{gen2.stderr}")
    else:
        after = artifact_digests()
        if before != after:
            errors.append("npm run generate dirtied generated artifacts (drift)")

    contract = run(["node", "dist/registry/run_contract.js"], BRIDGE)
    if contract.returncode != 0:
        errors.append(
            f"contract matrix failed (exit {contract.returncode}):\n"
            f"{contract.stdout}\n{contract.stderr}"
        )
    else:
        summary = None
        for line in contract.stdout.splitlines():
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    summary = json.loads(line)
                except json.JSONDecodeError:
                    summary = None
        if not isinstance(summary, dict) or not summary.get("ok"):
            errors.append(f"contract runner missing ok summary: {contract.stdout!r}")
        else:
            if int(summary.get("actions") or 0) < 118:
                errors.append(f"live catalog actions={summary.get('actions')} (need ~119)")
            if int(summary.get("cases") or 0) < 118 * 5:
                errors.append(
                    f"executed cases={summary.get('cases')} "
                    "(need every action × 4 invalid + 1 positive)"
                )
            if int(summary.get("failed") or 0) != 0:
                errors.append(f"executed matrix failed={summary.get('failed')}")

    if errors:
        print("FAIL: registry check", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: live ActionDef catalog; envelope guards; executed contract matrix; "
        "generated artifacts stable; plan R2-WP1 progress consistent; plugin-project/addons absent. "
        "Did not run Godot."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
