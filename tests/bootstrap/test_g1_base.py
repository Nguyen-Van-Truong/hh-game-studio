#!/usr/bin/env python3
"""R1-WP5: G1 base is in-house thin; no vendor MCP in product trees.

Fails (exit != 0) if:
  - DECISIONS / G1_BASE / capability-lock missing or g1_base is not in-house-thin
  - godot/plugin-project/addons contains anything other than hh_agent
  - product trees contain satelliteoflove / Beckett / KeeVeeG / Sods2 addon copies
  - npx -y or Beckett Full purchase is recommended as the G1 path
  - lock SHAs drift from bake-off PIN.json files
  - lock uses npm 4.1.0 SHA 59da3d0… as reference_shas.A
  - lock missing never_enable_release_mistaken_for_A / g1_status never-enable
  - lock missing bridge_npm integrities or they drift from bridge/package-lock.json
  - lock Godot zip SHA-256/SHA-512 drift from tools/godot/pin.json
  - any third_party/mcp-staging/*/PIN.json lacks g1=never-enable
  - implementer ticked R1-WP5 or G1 NO-FORK, or CURRENT_VALID_WP is not R1-WP5
  - Godot pin in lock != 4.7.1.stable.official.a13da4feb
  - bridge/package.json gains godot-mcp or a caret-ranged MCP SDK
    (exact-pinned @modelcontextprotocol/sdk is the only extra MCP dep allowed)

This test still does **not** run Godot or `npm ci`. If offline npm is not
cached, that is a GAP — do not download godot-mcp.

Stdlib only. Does not fetch npm/GitHub.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hh_agent_allow import hh_agent_only_addon_errors

REPO_ROOT = Path(__file__).resolve().parents[2]
DECISIONS = REPO_ROOT / "docs" / "DECISIONS.md"
G1_BASE = REPO_ROOT / "docs" / "godot-agent" / "G1_BASE.md"
NOTICE = REPO_ROOT / "docs" / "godot-agent" / "NOTICE"
BAKEOFF = REPO_ROOT / "docs" / "godot-agent" / "MCP_BAKEOFF.md"
SBOM = REPO_ROOT / "docs" / "godot-agent" / "SBOM_BASELINE.md"
STAGING_README = REPO_ROOT / "third_party" / "mcp-staging" / "README.md"
LOCK = REPO_ROOT / ".hh-agent" / "capability-lock.json"
GODOT_PIN = REPO_ROOT / "tools" / "godot" / "pin.json"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
MINIMAL_2D = REPO_ROOT / "godot" / "test-projects" / "minimal-2d"
GODOT_ADDONS = REPO_ROOT / "godot" / "addons"
BRIDGE_ROOT = REPO_ROOT / "bridge"
BRIDGE_SRC = REPO_ROOT / "bridge" / "src"
BRIDGE_PKG = REPO_ROOT / "bridge" / "package.json"
BRIDGE_LOCK = REPO_ROOT / "bridge" / "package-lock.json"
PLAN_20_8 = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
STAGING = REPO_ROOT / "third_party" / "mcp-staging"

DECISION_ID = "GODOT-G1-BASE-2026-08-20"
G1_BASE_VALUE = "in-house-thin"
GODOT_VERSION_ID = "4.7.1.stable.official.a13da4feb"
GODOT_COMMIT = "a13da4feb8d8aefc283c3763d33a2f170a18d541"
FUTURE_PLUGIN = "godot/plugin-project/addons/hh_agent/"
FUTURE_BRIDGE = "bridge/"

PIN_DIRS = {
    "A": "satelliteoflove-godot-mcp",
    "B": "keeveeg-godot-mcp",
    "C": "beckett-godot-mcp-lite",
    "D": "sods2-godot-mcp",
}

EXPECTED_SHAS = {
    "A": "1b7d40537240fd54300f54bf6fda1ea91f06c878",
    "B": "9ea1a41b9ed6cd819c602a37cc111c50017707d8",
    "C": "efb81dec03ba0af2b7a6dce0e4678bdbde5e454d",
    "D": "78b2cee00d697f117d6875e07675101b867efe70",
}

# npm @satelliteoflove/godot-mcp@4.1.0 / tag godot-mcp-v4.1.0 — older than A.
NPM_RELEASE_MISTAKEN_FOR_A = "59da3d0dae06c79cc970d83828e54b2fc16d0769"
G1_NEVER_ENABLE = "never-enable"
NODE_ENGINE = "24.19.0"

# name -> (version, package-lock packages key)
BRIDGE_NPM_PACKAGES = {
    "typescript": ("5.9.3", "node_modules/typescript"),
    "@types/node": ("24.13.3", "node_modules/@types/node"),
    "undici-types": ("7.18.2", "node_modules/undici-types"),
}

NOT_CANDIDATE_A = "is **not** candidate A"

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SKIP_DIR_NAMES = {".godot", "node_modules", "__pycache__", "dist"}
VENDOR_PATH_NEEDLES = (
    "godot_mcp",
    "mcpgamebridge",
    "satelliteoflove",
    "keeveeg",
    "beckett",
    "sods2",
    "evaluate_expression",
)
VENDOR_TEXT_NEEDLES = (
    "godot_mcp",
    "MCPGameBridge",
    "satelliteoflove",
    "KeeVeeG",
    "keeveeg",
    "evaluate_expression",
    "call_method",
    "Object.callv",
)
NEGATION_RE = re.compile(
    r"do\s+\*?\*?not\*?\*?|must\s+not|never|forbidden|reject|refused|"
    r"closed|không|bác|fail-hard|không mua|do not buy|not purchased|"
    r"not chosen|not vendor|none\b",
    re.IGNORECASE,
)
G1_HEADING_RE = re.compile(r"^## G1\b", re.MULTILINE)
DECISION_HEADING_RE = re.compile(
    r"^## .+G1 base:.+$",
    re.MULTILINE,
)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def extract_after_heading(text: str, heading_re: re.Pattern[str]) -> str:
    match = heading_re.search(text)
    if not match:
        return ""
    start = match.start()
    rest = text[match.end() :]
    nxt = re.search(r"\n## ", rest)
    if nxt:
        return text[start : match.end() + nxt.start()]
    return text[start:]


def iter_files(root: Path):
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        yield path


def plugin_project_errors() -> list[str]:
    return hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT)


def product_tree_vendor_errors() -> list[str]:
    errors: list[str] = []
    if GODOT_ADDONS.exists():
        errors.append("godot/addons/ must not exist (G1 closed MCP vendors)")
    trees = (PLUGIN_PROJECT, MINIMAL_2D, BRIDGE_SRC, BRIDGE_ROOT)
    for root in trees:
        if not root.exists():
            errors.append(f"missing product tree {rel(root)}")
            continue
        for path in iter_files(root):
            posix = path.as_posix().lower()
            if any(needle in posix for needle in VENDOR_PATH_NEEDLES):
                errors.append(f"product tree has vendor path: {rel(path)}")
                continue
            try:
                blob = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for needle in VENDOR_TEXT_NEEDLES:
                if needle in blob or needle.lower() in blob.lower():
                    errors.append(
                        f"product tree {rel(path)} contains vendor needle {needle!r}"
                    )
                    break
    return errors


def positive_g1_path_errors(label: str, text: str) -> list[str]:
    errors: list[str] = []
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("Do **not**") or stripped.startswith("Do not"):
            continue
        low = stripped.lower()
        negated = bool(NEGATION_RE.search(stripped))
        if re.search(r"npx\s+-y", low) and not negated:
            errors.append(f"{label}:{i} recommends npx -y as a G1 path")
        if re.search(r"vendor a as-is", low) and not negated:
            errors.append(f"{label}:{i} says vendor A as-is")
        if re.search(r"vendor c as-is", low) and not negated:
            errors.append(f"{label}:{i} says vendor C as-is")
        if re.search(r"(buy|buying|purchase)\s+beckett(\s+full)?", low) and not negated:
            errors.append(f"{label}:{i} recommends buying Beckett Full as a G1 path")
        if re.search(r"depend exact package", low) and not negated:
            if "rejected" not in low and "(2)" not in low:
                errors.append(f"{label}:{i} chooses depend exact package")
    return errors


def require_phrases(label: str, text: str, phrases: tuple[str, ...]) -> list[str]:
    errors: list[str] = []
    low = text.lower()
    for phrase in phrases:
        if phrase.lower() not in low:
            errors.append(f"{label} missing required phrase {phrase!r}")
    return errors


def load_json(path: Path) -> tuple[dict, list[str]]:
    raw = read_text(path)
    if raw is None:
        return {}, [f"missing {rel(path)}"]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {}, [f"{rel(path)} invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return {}, [f"{rel(path)} must be a JSON object"]
    return data, []


def godot_hash_errors(lock_godot: dict, pin: dict) -> list[str]:
    errors: list[str] = []
    pin_engine = pin.get("godot") if isinstance(pin.get("godot"), dict) else {}
    pin_dl = (
        pin_engine.get("downloads")
        if isinstance(pin_engine.get("downloads"), dict)
        else {}
    )
    lock_dl = (
        lock_godot.get("downloads")
        if isinstance(lock_godot.get("downloads"), dict)
        else {}
    )
    if not lock_dl:
        errors.append(f"{rel(LOCK)} missing godot.downloads (copy zip hashes from pin.json)")
        return errors

    zip_pin = (
        pin_dl.get("win64_editor_zip")
        if isinstance(pin_dl.get("win64_editor_zip"), dict)
        else {}
    )
    zip_lock = (
        lock_dl.get("win64_editor_zip")
        if isinstance(lock_dl.get("win64_editor_zip"), dict)
        else {}
    )
    for key in ("sha256", "sha512"):
        if not zip_lock.get(key):
            errors.append(f"{rel(LOCK)} missing godot.downloads.win64_editor_zip.{key}")
        elif zip_lock.get(key) != zip_pin.get(key):
            errors.append(
                f"{rel(LOCK)} godot win64 zip {key} drifted from {rel(GODOT_PIN)}"
            )

    tpl_pin = (
        pin_dl.get("export_templates_tpz")
        if isinstance(pin_dl.get("export_templates_tpz"), dict)
        else {}
    )
    tpl_lock = (
        lock_dl.get("export_templates_tpz")
        if isinstance(lock_dl.get("export_templates_tpz"), dict)
        else {}
    )
    if not tpl_lock.get("sha512"):
        errors.append(f"{rel(LOCK)} missing godot.downloads.export_templates_tpz.sha512")
    elif tpl_lock.get("sha512") != tpl_pin.get("sha512"):
        errors.append(
            f"{rel(LOCK)} godot templates sha512 drifted from {rel(GODOT_PIN)}"
        )
    if tpl_lock.get("sha256_verified") != tpl_pin.get("sha256_verified"):
        errors.append(
            f"{rel(LOCK)} godot templates sha256_verified drifted from {rel(GODOT_PIN)}"
        )
    return errors


def bridge_npm_errors(lock: dict) -> list[str]:
    errors: list[str] = []
    npm = lock.get("bridge_npm") if isinstance(lock.get("bridge_npm"), dict) else {}
    pkgs = npm.get("packages") if isinstance(npm.get("packages"), dict) else {}
    if str(npm.get("node", "")) != NODE_ENGINE:
        errors.append(
            f"{rel(LOCK)} bridge_npm.node={npm.get('node')!r} (need {NODE_ENGINE!r})"
        )

    lockfile, lockfile_errors = load_json(BRIDGE_LOCK)
    errors.extend(lockfile_errors)
    lock_pkgs = (
        lockfile.get("packages") if isinstance(lockfile.get("packages"), dict) else {}
    )
    root = lock_pkgs.get("") if isinstance(lock_pkgs.get(""), dict) else {}
    engines = root.get("engines") if isinstance(root.get("engines"), dict) else {}
    if str(engines.get("node", "")) != NODE_ENGINE:
        errors.append(
            f"{rel(BRIDGE_LOCK)} engines.node={engines.get('node')!r} (need {NODE_ENGINE!r})"
        )
    elif str(npm.get("node", "")) != str(engines.get("node", "")):
        errors.append(f"{rel(LOCK)} bridge_npm.node drifted from {rel(BRIDGE_LOCK)}")

    for name, (version, lock_key) in BRIDGE_NPM_PACKAGES.items():
        pinned = pkgs.get(name) if isinstance(pkgs.get(name), dict) else {}
        if not pinned.get("integrity"):
            errors.append(f"{rel(LOCK)} missing bridge_npm.packages.{name}.integrity")
            continue
        if str(pinned.get("version", "")) != version:
            errors.append(
                f"{rel(LOCK)} bridge_npm.packages.{name}.version="
                f"{pinned.get('version')!r} (need {version!r})"
            )
        actual = lock_pkgs.get(lock_key) if isinstance(lock_pkgs.get(lock_key), dict) else {}
        if not actual:
            errors.append(f"{rel(BRIDGE_LOCK)} missing {lock_key}")
            continue
        if str(actual.get("version", "")) != version:
            errors.append(
                f"{rel(BRIDGE_LOCK)} {lock_key} version={actual.get('version')!r} "
                f"(need {version!r})"
            )
        if str(pinned.get("integrity", "")) != str(actual.get("integrity", "")):
            errors.append(
                f"{rel(LOCK)} bridge_npm.packages.{name}.integrity drifted from "
                f"{rel(BRIDGE_LOCK)}"
            )
    return errors


def plan_g1_progress_errors(text: str) -> list[str]:
    """Allow either pre-tick (implementer) or post-tick (coordinator) plan state."""
    errors: list[str] = []
    found_wp = False
    wp5_ticked = False
    g1_ticked = False
    current = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R1-WP5\b", stripped):
            found_wp = True
            wp5_ticked = bool(re.search(r"\[x\]", stripped, re.IGNORECASE))
        if stripped.startswith("G1 NO-FORK") and re.search(r"\[x\]", stripped, re.IGNORECASE):
            g1_ticked = True
    if not found_wp:
        errors.append(f"{rel(PLAN_20_8)} missing R1-WP5 heading")
    if "CURRENT_VALID_WP=" not in text:
        errors.append(f"{rel(PLAN_20_8)} missing CURRENT_VALID_WP=")
    if not wp5_ticked:
        if current != "R1-WP5":
            errors.append(
                f"{rel(PLAN_20_8)} CURRENT_VALID_WP={current!r} "
                "(need R1-WP5 while WP5 is unticked)"
            )
        if g1_ticked:
            errors.append(f"{rel(PLAN_20_8)} G1 NO-FORK ticked before R1-WP5")
    else:
        if not re.match(r"^R[2-9]-WP\d+$", current):
            errors.append(
                f"{rel(PLAN_20_8)} CURRENT_VALID_WP={current!r} "
                "(need R2+ after R1-WP5 tick)"
            )
        if not g1_ticked:
            errors.append(f"{rel(PLAN_20_8)} G1 NO-FORK must tick with R1-WP5")
    return errors


def main() -> int:
    errors: list[str] = []

    for path in (DECISIONS, G1_BASE, NOTICE, BAKEOFF, LOCK, STAGING_README, SBOM):
        if not path.is_file():
            errors.append(f"missing {rel(path)}")

    lock_raw = read_text(LOCK)
    if lock_raw is None:
        print("FAIL: G1 base check", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    try:
        lock = json.loads(lock_raw)
    except json.JSONDecodeError as exc:
        errors.append(f"{rel(LOCK)} invalid JSON: {exc}")
        lock = {}

    if not isinstance(lock, dict):
        errors.append(f"{rel(LOCK)} must be a JSON object")
        lock = {}

    if lock.get("g1_base") != G1_BASE_VALUE:
        errors.append(
            f"{rel(LOCK)} g1_base={lock.get('g1_base')!r} (need {G1_BASE_VALUE!r})"
        )
    if lock.get("mcp_vendor") != "none":
        errors.append(f"{rel(LOCK)} mcp_vendor={lock.get('mcp_vendor')!r} (need 'none')")
    if lock.get("decision_id") != DECISION_ID:
        errors.append(f"{rel(LOCK)} decision_id={lock.get('decision_id')!r}")
    if lock.get("future_plugin") != FUTURE_PLUGIN:
        errors.append(f"{rel(LOCK)} future_plugin={lock.get('future_plugin')!r}")
    if lock.get("future_bridge") != FUTURE_BRIDGE:
        errors.append(f"{rel(LOCK)} future_bridge={lock.get('future_bridge')!r}")
    if lock.get("upstream_boundary") != "none":
        errors.append(f"{rel(LOCK)} upstream_boundary must be none (reference-only)")
    if lock.get("patch_queue") != "do-not-patch-vendor":
        errors.append(f"{rel(LOCK)} patch_queue must be do-not-patch-vendor")
    if lock.get("schema_ownership") != "bridge/src/registry/":
        errors.append(f"{rel(LOCK)} schema_ownership must be bridge/src/registry/")
    if lock.get("update_cadence") != "none":
        errors.append(f"{rel(LOCK)} update_cadence must be none for MCP candidates")

    godot = lock.get("godot") if isinstance(lock.get("godot"), dict) else {}
    if godot.get("version_id") != GODOT_VERSION_ID:
        errors.append(
            f"{rel(LOCK)} godot.version_id={godot.get('version_id')!r} "
            f"(need {GODOT_VERSION_ID})"
        )
    if godot.get("commit_full") != GODOT_COMMIT:
        errors.append(f"{rel(LOCK)} godot.commit_full drift")
    if godot.get("tag") != "4.7.1-stable":
        errors.append(f"{rel(LOCK)} godot.tag must be 4.7.1-stable")
    if "4.7.2" in lock_raw or "4.8" in json.dumps(godot):
        errors.append(f"{rel(LOCK)} must not pin Godot 4.7.2 or 4.8")

    if GODOT_PIN.is_file():
        try:
            pin = json.loads(GODOT_PIN.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{rel(GODOT_PIN)} invalid JSON: {exc}")
            pin = {}
        engine = pin.get("godot") if isinstance(pin.get("godot"), dict) else {}
        if engine.get("version_id") != godot.get("version_id"):
            errors.append("capability-lock Godot version_id != tools/godot/pin.json")
        if engine.get("commit_full") != godot.get("commit_full"):
            errors.append("capability-lock Godot commit_full != tools/godot/pin.json")
        errors.extend(godot_hash_errors(godot, pin))
    else:
        errors.append(f"missing {rel(GODOT_PIN)}")

    ref = lock.get("reference_shas") if isinstance(lock.get("reference_shas"), dict) else {}
    g1_status = lock.get("g1_status") if isinstance(lock.get("g1_status"), dict) else {}
    mistaken = str(lock.get("never_enable_release_mistaken_for_A", ""))
    if mistaken != NPM_RELEASE_MISTAKEN_FOR_A:
        errors.append(
            f"{rel(LOCK)} never_enable_release_mistaken_for_A={mistaken!r} "
            f"(need {NPM_RELEASE_MISTAKEN_FOR_A})"
        )
    if str(ref.get("A", "")) == NPM_RELEASE_MISTAKEN_FOR_A:
        errors.append(
            f"{rel(LOCK)} reference_shas.A must not be npm 4.1.0 SHA "
            f"{NPM_RELEASE_MISTAKEN_FOR_A} (that release is not candidate A)"
        )
    if mistaken and mistaken == str(ref.get("A", "")):
        errors.append(
            f"{rel(LOCK)} never_enable_release_mistaken_for_A must not equal reference_shas.A"
        )

    for cid, expected in EXPECTED_SHAS.items():
        got = str(ref.get(cid, ""))
        if not SHA_RE.fullmatch(got):
            errors.append(f"{rel(LOCK)} reference_shas.{cid} is not a 40-char SHA")
        elif got != expected:
            errors.append(
                f"{rel(LOCK)} reference_shas.{cid}={got} != bake-off pin {expected}"
            )
        if g1_status.get(cid) != G1_NEVER_ENABLE:
            errors.append(
                f"{rel(LOCK)} g1_status.{cid}={g1_status.get(cid)!r} "
                f"(need {G1_NEVER_ENABLE!r})"
            )
        pin_path = STAGING / PIN_DIRS[cid] / "PIN.json"
        if not pin_path.is_file():
            errors.append(f"missing {rel(pin_path)}")
            continue
        try:
            staged = json.loads(pin_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{rel(pin_path)} invalid JSON: {exc}")
            continue
        staged_commit = str(staged.get("commit", ""))
        if staged_commit != got:
            errors.append(
                f"{rel(LOCK)} reference_shas.{cid} drifted from {rel(pin_path)}"
            )
        if staged.get("g1") != G1_NEVER_ENABLE:
            errors.append(f"{rel(pin_path)} g1 must be {G1_NEVER_ENABLE!r}")
        if staged.get("vendored_source_tree") is not False:
            errors.append(f"{rel(pin_path)} vendored_source_tree must stay false")
        if cid == "A":
            tag_commit = str(staged.get("tag_commit", ""))
            if tag_commit != NPM_RELEASE_MISTAKEN_FOR_A:
                errors.append(
                    f"{rel(pin_path)} tag_commit must remain {NPM_RELEASE_MISTAKEN_FOR_A}"
                )
            if tag_commit == staged_commit:
                errors.append(
                    f"{rel(pin_path)} tag_commit 59da3d0… must not equal bake-off commit A"
                )

    errors.extend(plugin_project_errors())
    errors.extend(product_tree_vendor_errors())

    decisions = read_text(DECISIONS) or ""
    g1_base_text = read_text(G1_BASE) or ""
    bakeoff = read_text(BAKEOFF) or ""
    notice = read_text(NOTICE) or ""
    sbom = read_text(SBOM) or ""
    staging_readme = read_text(STAGING_README) or ""

    g1_decision = extract_after_heading(decisions, DECISION_HEADING_RE)
    if DECISION_ID not in decisions or not g1_decision:
        errors.append(f"{rel(DECISIONS)} missing {DECISION_ID} entry")
    else:
        if "GODOT-REBOOT-2026-08-20" in g1_decision:
            errors.append("G1 decision must not duplicate GODOT-REBOOT")
        errors.extend(
            require_phrases(
                rel(DECISIONS),
                g1_decision,
                (
                    "in-house thin",
                    "in-house-thin",
                    "status: choice-approved",
                    "plan G1 checkbox",
                    "Rejected (1) vendor exact MIT commit",
                    "Rejected (2) depend exact package",
                    "MUST-PATCH",
                    "silent spec rewrite",
                    FUTURE_PLUGIN,
                    "bridge/",
                    "6550",
                    "godot_exec",
                    "UndoRedo",
                    "update_node",
                    "MCPGameBridge",
                    "call_method",
                    "Object.callv",
                    "zero-sidecar",
                    "E2",
                    "FAIL for both",
                    GODOT_VERSION_ID,
                    "do not patch-vendor",
                    "npx -y",
                    NPM_RELEASE_MISTAKEN_FOR_A,
                    NOT_CANDIDATE_A,
                ),
            )
        )
        if "satelliteoflove" not in g1_decision.lower():
            errors.append("G1 decision must explain satelliteoflove default did not đạt")
        errors.extend(positive_g1_path_errors(rel(DECISIONS) + " G1 entry", g1_decision))

    errors.extend(
        require_phrases(
            rel(G1_BASE),
            g1_base_text,
            (
                "in-house-thin",
                "in-house thin",
                "mcp_vendor: none",
                DECISION_ID,
                GODOT_VERSION_ID,
                FUTURE_PLUGIN,
                "not created this WP",
                "do not patch-vendor",
                "bridge/src/registry/",
                "none",
                NPM_RELEASE_MISTAKEN_FOR_A,
                NOT_CANDIDATE_A,
            ),
        )
    )
    errors.extend(positive_g1_path_errors(rel(G1_BASE), g1_base_text))

    g1_bakeoff = extract_after_heading(bakeoff, G1_HEADING_RE)
    if not g1_bakeoff:
        errors.append(f"{rel(BAKEOFF)} missing ## G1 section")
    else:
        errors.extend(
            require_phrases(
                rel(BAKEOFF) + " G1",
                g1_bakeoff,
                (
                    "in-house thin",
                    "upstream boundary",
                    "do not patch-vendor",
                    "bridge/src/registry/",
                    "update cadence",
                    "reference-only",
                ),
            )
        )
        errors.extend(positive_g1_path_errors(rel(BAKEOFF) + " G1", g1_bakeoff))
        if re.search(r"vendor a as-is", g1_bakeoff, re.IGNORECASE):
            if not re.search(
                r"do not vendor a as-is|must not vendor a as-is|not vendor a as-is",
                g1_bakeoff,
                re.IGNORECASE,
            ):
                errors.append("G1 bake-off section must not say vendor A as-is")

    if "did not copy" not in notice.lower() and "does not contain vendored" not in notice.lower():
        errors.append(f"{rel(NOTICE)} must state we did not copy A/C/B/D source")
    if "third_party/mcp-staging" not in notice.replace("\\", "/"):
        errors.append(f"{rel(NOTICE)} must keep MIT LICENSE under third_party/mcp-staging/")

    if "in-house thin" not in sbom.lower() and "g1" not in sbom.lower():
        errors.append(f"{rel(SBOM)} must record G1 in-house thin (no vendor MCP landing)")
    if re.search(r"vendor mcp may land|a vendor mcp will land", sbom, re.IGNORECASE):
        errors.append(f"{rel(SBOM)} still implies a vendor MCP may land")

    if "production vendor" not in staging_readme.lower() and "closed" not in staging_readme.lower():
        errors.append(f"{rel(STAGING_README)} must say G1 closed these as production vendors")

    if BRIDGE_PKG.is_file():
        try:
            pkg = json.loads(BRIDGE_PKG.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{rel(BRIDGE_PKG)} invalid JSON: {exc}")
            pkg = {}
        deps = {}
        if isinstance(pkg.get("dependencies"), dict):
            deps.update(pkg["dependencies"])
        if isinstance(pkg.get("devDependencies"), dict):
            deps.update(pkg["devDependencies"])
        allowed = {"typescript", "@types/node", "@modelcontextprotocol/sdk"}
        extra = set(deps) - allowed
        if extra:
            errors.append(f"{rel(BRIDGE_PKG)} added unexpected deps this WP: {sorted(extra)}")
        blob = json.dumps(pkg)
        sdk_ver = deps.get("@modelcontextprotocol/sdk")
        if sdk_ver is not None:
            if not isinstance(sdk_ver, str) or not re.fullmatch(r"\d+\.\d+\.\d+", sdk_ver):
                errors.append(
                    f"{rel(BRIDGE_PKG)} @modelcontextprotocol/sdk must be an exact x.y.z pin (no caret)"
                )
            pinned = (
                lock.get("bridge_npm", {}).get("packages", {}).get("@modelcontextprotocol/sdk")
                if isinstance(lock.get("bridge_npm"), dict)
                else None
            )
            if not isinstance(pinned, dict) or not pinned.get("integrity"):
                errors.append(
                    f"{rel(LOCK)} missing bridge_npm.packages.@modelcontextprotocol/sdk.integrity"
                )
        if "satelliteoflove" in blob.lower():
            errors.append(f"{rel(BRIDGE_PKG)} must not add satelliteoflove packages")
        if "godot-mcp" in blob.lower():
            errors.append(f"{rel(BRIDGE_PKG)} must not add godot-mcp this WP")

    errors.extend(bridge_npm_errors(lock))

    plan_text = read_text(PLAN_20_8)
    if plan_text is None:
        errors.append(f"missing {rel(PLAN_20_8)}")
    else:
        errors.extend(plan_g1_progress_errors(plan_text))

    if errors:
        print("FAIL: G1 base check", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: G1 in-house-thin lock; mcp_vendor=none; plugin-project allows only hh_agent; "
        "no vendor MCP copies; SHAs match PIN.json; Godot 4.7.1.stable.official.a13da4feb; "
        "bridge_npm integrities match package-lock; 59da3d0 is not A; "
        "plan G1 progress consistent. This test does not run Godot or npm ci."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
