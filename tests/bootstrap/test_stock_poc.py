#!/usr/bin/env python3
"""R1-WP4 guard: stock-poc fixture exists; plugin-project stays addon-free.

Fails (exit != 0) if:
  - godot/plugin-project gained addons / MCP / GUT / hh_stock_poc
  - stock-poc missing disposable hh_stock_poc plugin
  - hh-godot-editor.bat no longer opens minimal-2d
  - recorded 20/20 RESULT is missing or any run FAIL
  - RESULT claims screenshot PASS without a real player-sized PNG

Stdlib only. Does not enable MCP. Does not fetch GitHub.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
STOCK_POC = REPO_ROOT / "godot" / "test-projects" / "stock-poc"
PLUGIN_CFG = STOCK_POC / "addons" / "hh_stock_poc" / "plugin.cfg"
EDITOR_BAT = REPO_ROOT / "hh-godot-editor.bat"
POC_BAT = REPO_ROOT / "hh-stock-poc.bat"
RESULT_MD = REPO_ROOT / "tests" / "e2e" / "stock_poc" / "RESULT.md"
RESULT_JSON = REPO_ROOT / "tests" / "e2e" / "stock_poc" / "results.json"
DRIVER = REPO_ROOT / "tests" / "e2e" / "stock_poc" / "run_slice.py"

MCP_NEEDLES = (
    "godot_mcp",
    "beckett",
    "keeveeg",
    "sods2",
    "satelliteoflove",
    "addons/gut",
)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def plugin_project_errors() -> list[str]:
    errors: list[str] = []
    if not PLUGIN_PROJECT.is_dir():
        return [f"missing {rel(PLUGIN_PROJECT)}"]
    addons = PLUGIN_PROJECT / "addons"
    if addons.is_dir():
        leftover = [
            p for p in addons.rglob("*") if p.is_file() and ".godot" not in p.parts
        ]
        if leftover:
            errors.append(
                "godot/plugin-project/addons/ must stay empty; found "
                + ", ".join(rel(p) for p in leftover[:8])
            )
    for marker in PLUGIN_PROJECT.rglob("*"):
        if not marker.is_file() or any(part == ".godot" for part in marker.parts):
            continue
        posix = marker.as_posix().lower()
        name = marker.name.lower()
        if name in {"plugin.cfg", "plugin.gd"}:
            errors.append(f"plugin-project must not contain addon files: {rel(marker)}")
        if any(needle in posix for needle in MCP_NEEDLES):
            errors.append(f"plugin-project must not contain MCP/GUT: {rel(marker)}")
        if "hh_stock_poc" in posix:
            errors.append(f"hh_stock_poc must not be copied into plugin-project: {rel(marker)}")
    return errors


def main() -> int:
    errors: list[str] = []
    errors.extend(plugin_project_errors())

    if not STOCK_POC.is_dir():
        errors.append(f"missing {rel(STOCK_POC)}")
    if not PLUGIN_CFG.is_file():
        errors.append(f"missing {rel(PLUGIN_CFG)}")
    else:
        cfg = PLUGIN_CFG.read_text(encoding="utf-8")
        if "R1-WP4" not in cfg and "disposable" not in cfg.lower():
            errors.append("stock-poc plugin.cfg must name the R1 disposable POC")
        if "MCP" in cfg and "NOT MCP" not in cfg:
            errors.append("plugin.cfg must say it is NOT MCP")
    if not (STOCK_POC / "project.godot").is_file():
        errors.append("stock-poc missing project.godot")
    else:
        godot = (STOCK_POC / "project.godot").read_text(encoding="utf-8")
        if "config_version=5" not in godot:
            errors.append("stock-poc project.godot must be config_version=5")
        if "4.7" not in godot:
            errors.append("stock-poc project.godot must list features 4.7")
        if "godot_mcp" in godot or "beckett" in godot.lower():
            errors.append("stock-poc must not enable MCP plugins")
    if (STOCK_POC / "addons" / "godot_mcp").exists() or (STOCK_POC / "addons" / "beckett").exists():
        errors.append("stock-poc must not vendor MCP addons")
    if (STOCK_POC / "addons" / "gut").exists():
        errors.append("stock-poc must not vendor GUT")
    if not DRIVER.is_file():
        errors.append(f"missing {rel(DRIVER)}")

    if not EDITOR_BAT.is_file():
        errors.append(f"missing {rel(EDITOR_BAT)}")
    else:
        bat = EDITOR_BAT.read_text(encoding="utf-8", errors="replace")
        if "minimal-2d" not in bat:
            errors.append("hh-godot-editor.bat must still open godot/test-projects/minimal-2d")
        if "stock-poc" in bat:
            errors.append("hh-godot-editor.bat must not be retargeted to stock-poc")
        if "4.7.1-stable" not in bat:
            errors.append("hh-godot-editor.bat must keep the 4.7.1-stable pin")

    if POC_BAT.is_file():
        poc = POC_BAT.read_text(encoding="utf-8", errors="replace")
        if "stock-poc" not in poc:
            errors.append("hh-stock-poc.bat should open the stock-poc fixture")
        if "godot_mcp" in poc.lower() or "beckett" in poc.lower():
            errors.append("hh-stock-poc.bat must not launch MCP")

    if not RESULT_JSON.is_file() and not RESULT_MD.is_file():
        errors.append("missing tests/e2e/stock_poc/RESULT.md or results.json (run run_slice.py --runs 20)")
    else:
        passed = failed = runs = -1
        if RESULT_JSON.is_file():
            try:
                data = json.loads(RESULT_JSON.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"results.json invalid: {exc}")
                data = {}
            if isinstance(data, dict):
                runs = int(data.get("runs") or 0)
                passed = int(data.get("passed") or 0)
                failed = int(data.get("failed") or 0)
                if runs != 20 or passed != 20 or failed != 0:
                    errors.append(
                        f"results.json must record 20/20 PASS, got passed={passed} failed={failed} runs={runs}"
                    )
                if data.get("plugin_project_clean") is not True:
                    errors.append("results.json must record plugin_project_clean true")
                if data.get("godot") != "4.7.1.stable.official.a13da4feb":
                    errors.append("results.json godot pin must be 4.7.1.stable.official.a13da4feb")
                projects: list[str] = []
                for row in data.get("rows") or []:
                    if not isinstance(row, dict):
                        continue
                    if row.get("overall") != "PASS":
                        errors.append(f"run {row.get('run')} overall is {row.get('overall')}")
                    proj = str(row.get("project") or "")
                    if proj:
                        projects.append(proj)
                    if row.get("screenshot") == "PASS":
                        errors.append(
                            f"run {row.get('run')} screenshot PASS is not allowed without a "
                            "committed player-sized PNG (this WP recorded SKIP)"
                        )
                    if row.get("inspector") not in {"GAP", "SKIP", "PASS"}:
                        errors.append(f"run {row.get('run')} inspector={row.get('inspector')!r}")
                if len(projects) != 20 or len(set(projects)) != 20:
                    errors.append(
                        f"results.json must have 20 unique copy paths, got {len(set(projects))}"
                    )
        if RESULT_MD.is_file():
            text = RESULT_MD.read_text(encoding="utf-8")
            match = re.search(r"STOCK_POC_OVERALL=(\d+)/(\d+)", text)
            if not match:
                errors.append("RESULT.md missing STOCK_POC_OVERALL=N/N")
            else:
                if match.group(1) != "20" or match.group(2) != "20":
                    errors.append(f"RESULT.md STOCK_POC_OVERALL={match.group(1)}/{match.group(2)} (need 20/20)")
            if re.search(r"STOCK_POC_FAILS=([1-9]\d*)", text):
                errors.append("RESULT.md records failures")
            if "dummy" not in text.lower() and "SKIP" not in text:
                errors.append("RESULT.md must document screenshot SKIP/dummy policy")

    if errors:
        print("FAIL: stock-poc guard", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: plugin-project has no addons/MCP; stock-poc plugin present; "
        "hh-godot-editor.bat still minimal-2d; RESULT 20/20"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
