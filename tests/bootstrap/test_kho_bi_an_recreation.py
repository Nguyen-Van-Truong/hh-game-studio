#!/usr/bin/env python3
"""R8-WP6: fresh-project recreation + G5 review package (does not tick the plan).

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R8-WP6 [ ]; CURRENT_VALID_WP=R8-WP6; progress stays 55/60.
Does not start G5 as signed. Does not fake G5 human dogfood. Does not touch GX.
Win flag stays relic-reached. Do not poke relic_reached as a cheat.
No snake demo. No r7w6 trial. No secret material. No skip-PASS.
--provider plan stays unused here. No remote imagegen. No invented API key.

Official Godot verify (plan §7.3), path a clean kho-bi-an recreate:
  kill leftover Godot on kho-bi-an first (no sidecar; game has no addon)
  recreate twice from brief + assets pin on an empty project; trees must match
  godot --version
  godot --headless --editor --path <fresh-a> --import --quit
  On Windows: godot --windowed --path <fresh-a> --script res://tests/run_all.gd
  (windowed loop is plan §7.3 verify, not G5)
  optional sequential --export-release Windows Desktop to evidence (not R9)

Labels: RECREATE, HASHES, CRITIC, RUBRIC, EXPORT, HUMAN
RECREATE stays unproven. The emit is a snapshot/template, not brief→game.
CRITIC and RUBRIC stay unproven. This PID is not an independent review.
HASHES stays unproven for artifacts (export exe sha is not pinned).
TREE of generated sources may be reported as evidence.
HUMAN must stay unproven. Relic-reached is win.
No same-PID critic.md. No product-side split. No skip-PASS.
PASS does not require RECREATE proven.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
DOGFOOD = REPO_ROOT / "godot" / "dogfood" / "kho-bi-an"
BRIEF = DOGFOOD / "PROJECT_BRIEF.md"
RUN_ALL = DOGFOOD / "tests" / "run_all.gd"
PRESET = DOGFOOD / "export_presets.cfg"
README = DOGFOOD / "README.md"
RUBRIC = DOGFOOD / "REVIEW_RUBRIC.md"
ISSUES = DOGFOOD / "KNOWN_ISSUES.md"
RECREATE_TOOL = REPO_ROOT / "tools" / "godot" / "recreate_kho_bi_an.py"
FRESH_SOURCES = REPO_ROOT / "tools" / "godot" / "kho_bi_an_fresh_sources.py"
GODOT_PIN = REPO_ROOT / "tools" / "godot" / "pin.json"
EVIDENCE = REPO_ROOT / ".hh-agent" / "evidence" / "01R8WP6REC00000000KBA00001"
PINNED_VERSION = "4.7.1.stable.official.a13da4feb"
PINNED = "4.7.1-stable"
RUN_ID = "01R8WP6REC00000000KBA00001"
PATH_LABEL = "start→key→door→relic→win"
LABELS = ("RECREATE", "HASHES", "CRITIC", "RUBRIC", "EXPORT", "HUMAN")
PATH_NEEDLES = ("kho-bi-an", "kho_bi_an")
RUBRIC_AREAS = (
    "gameplay",
    "visual",
    "audio",
    "UX",
    "stability",
    "autonomy",
    "evidence",
)
STRIP_NEEDLES = ("addons/", ".hh-agent/", "token", "evidence", "tests/")
FORBIDDEN_EXPORT = (b"hh_agent", b"HH_TOKEN")


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def emit(text: str) -> None:
    stream = sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    stream.write(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))
    stream.write("\n")


def load_recreate():
    spec = importlib.util.spec_from_file_location("recreate_kho_bi_an", RECREATE_TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load recreate_kho_bi_an.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plan_errors(text: str) -> list[str]:
    errors: list[str] = []
    current = ""
    wp6 = None
    g5 = None
    gx = None
    total = None
    r8_row = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R8-WP6\b", stripped):
            wp6 = stripped
        if "G5 DOGFOOD" in stripped or stripped.startswith("G5 "):
            if g5 is None:
                g5 = stripped
        if "GX FORK" in stripped or stripped.startswith("GX "):
            if gx is None:
                gx = stripped
        if stripped.startswith("Tiến độ tổng:") or stripped.startswith("Tien do tong:"):
            total = stripped
        if "| 8 |" in stripped and "G5" in stripped:
            r8_row = stripped
    if current != "R8-WP6":
        errors.append(f"CURRENT_VALID_WP={current!r} (must stay R8-WP6)")
    if wp6 is None:
        errors.append("plan missing R8-WP6 heading")
    elif re.search(r"\[x\]", wp6, re.I):
        errors.append("R8-WP6 must stay unticked")
    if PATH_LABEL not in text:
        errors.append("plan must keep verify path start→key→door→relic→win")
    if total and "55/60" not in total:
        errors.append(f"progress must stay 55/60 while R8-WP6 is unticked: {total}")
    if r8_row and not re.search(r"\[ \]\s*5/6", r8_row):
        errors.append(f"R8 row must stay 5/6 while WP6 is unticked: {r8_row}")
    if g5 is not None and re.search(r"\[x\]", g5, re.I):
        errors.append("official harness must not tick G5")
    if gx is not None and re.search(r"\[x\]", gx, re.I):
        errors.append("official harness must not touch GX")
    return errors


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    self_text = Path(__file__).read_text(encoding="utf-8")
    for label in LABELS:
        if label not in self_text:
            errors.append(f"official test must label {label}")
    if "No skip-PASS" not in self_text and "skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    if "does not fake G5" not in self_text.lower() and "Does not fake G5" not in self_text:
        errors.append("official test must refuse to fake G5 human dogfood")
    if "does not touch GX" not in self_text.lower() and "Does not touch GX" not in self_text:
        errors.append("official test must refuse to touch GX")
    if "4.7." + "2" in self_text:
        errors.append("official test must refuse Godot 4.7." + "2 pin")
    if ("drive_" + "snake") in self_text:
        errors.append("official test must not include drive_" + "snake scripts")
    if "--provider" in self_text and "unused" not in self_text:
        errors.append("official test must not invoke a model provider")
    if ("HH_" + "OPENAI") in self_text or ("ANTHROPIC_" + "API_KEY") in self_text:
        errors.append("official test must not mention provider secrets")
    if "imagegen" in self_text.lower() and "No remote imagegen" not in self_text:
        errors.append("official test must refuse remote imagegen")
    tool = RECREATE_TOOL.read_text(encoding="utf-8") if RECREATE_TOOL.is_file() else ""
    poke = r"relic_reached\s*=" + r"\s*true"
    if re.search(poke, tool):
        errors.append("recreate tool must not poke relic_reached")
    if "shutil.copy2" in tool:
        errors.append("recreate tool must not shutil.copy2 a dogfood tree")
    if "iter_product_files(src)" in tool and "shutil.copy2(path, target)" in tool:
        errors.append("recreate tool still copies a src tree")
    if "brief+pins" not in tool:
        errors.append("recreate tool must build from brief+pins")
    critic_stamp = 'labels["CRITIC"] = "' + "proven" + '"'
    rubric_stamp = 'labels["RUBRIC"] = "' + "proven" + '"'
    hashes_stamp = 'labels["HASHES"] = "' + "proven" + '"'
    recreate_stamp = 'labels["RECREATE"] = "' + "proven" + '"'
    if critic_stamp in self_text or "labels['CRITIC'] = '" + "proven" + "'" in self_text:
        errors.append("official Python must not stamp CRITIC proven")
    if rubric_stamp in self_text or "labels['RUBRIC'] = '" + "proven" + "'" in self_text:
        errors.append("official Python must not stamp RUBRIC proven")
    if hashes_stamp in self_text or "labels['HASHES'] = '" + "proven" + "'" in self_text:
        errors.append("official Python must not stamp HASHES proven")
    if recreate_stamp in self_text or "labels['RECREATE'] = '" + "proven" + "'" in self_text:
        errors.append("official Python must not stamp RECREATE proven")
    leftover_gate = "copied " + "dogfood leftover"
    if leftover_gate in self_text:
        errors.append("official must not fail extra WP3–WP5 files as leftover copy")
    if "Independent " + "critic" in self_text:
        errors.append("official Python must not write a same-PID critic title")
    if "PASS " + "product-side" in self_text:
        errors.append("official Python must not invent a product-side PASS split")
    if os.environ.get("HH_R8WP6_HUMAN", "").strip().lower() in ("1", "true", "yes"):
        errors.append("HH_R8WP6_HUMAN cannot stamp official HUMAN")
    return errors


def tree_errors() -> list[str]:
    errors: list[str] = []
    required = (
        BRIEF,
        RUN_ALL,
        PRESET,
        README,
        RUBRIC,
        ISSUES,
        DOGFOOD / "NOTICE.md",
        DOGFOOD / "project.godot",
        DOGFOOD / "src" / "game_state.gd",
        DOGFOOD / "assets" / "ASSET_MANIFEST.json",
        RECREATE_TOOL,
        FRESH_SOURCES,
        EVIDENCE / "assumptions.md",
    )
    for path in required:
        if not path.is_file():
            errors.append(f"missing {rel(path)}")
    if not BRIEF.is_file():
        return errors
    state = (DOGFOOD / "src" / "game_state.gd").read_text(encoding="utf-8")
    if "return relic_reached" not in state:
        errors.append("win flag must stay relic_reached")
    if PATH_LABEL not in RUN_ALL.read_text(encoding="utf-8"):
        errors.append("run_all.gd must keep start→key→door→relic→win")
    if re.search(r"relic_reached\s*=\s*true", RUN_ALL.read_text(encoding="utf-8")):
        errors.append("run_all.gd must not poke relic_reached = true")
    preset = PRESET.read_text(encoding="utf-8") if PRESET.is_file() else ""
    if 'name="Windows Desktop"' not in preset:
        errors.append("export_presets.cfg must name Windows Desktop")
    if 'platform="Windows Desktop"' not in preset:
        errors.append("export_presets.cfg must set platform Windows Desktop")
    if "exclude_filter=" not in preset:
        errors.append("export_presets.cfg must author exclude_filter")
    for needle in STRIP_NEEDLES:
        if needle not in preset:
            errors.append(f"exclude_filter must strip {needle}")
    if (DOGFOOD / "addons").exists():
        errors.append("dogfood must not vendor addons")
    readme = README.read_text(encoding="utf-8") if README.is_file() else ""
    rubric = RUBRIC.read_text(encoding="utf-8") if RUBRIC.is_file() else ""
    issues = ISSUES.read_text(encoding="utf-8") if ISSUES.is_file() else ""
    blob = f"{readme}\n{rubric}\n{issues}".lower()
    if re.search(r"\b(g5\s*pass|dogfood signed|g5 signed)\b", blob):
        errors.append("review package must not fake G5 human dogfood")
    if "not" not in readme.lower() or "g5" not in readme.lower():
        errors.append("README must say G5 is not signed")
    for area in RUBRIC_AREAS:
        if area.lower() not in rubric.lower():
            errors.append(f"rubric missing {area}")
    if "do not open r9" not in issues.lower() and "không mở r9" not in issues.lower():
        errors.append("KNOWN_ISSUES must refuse opening R9 on green tests")
    return errors


def find_pinned_godot() -> tuple[Path | None, str]:
    if not GODOT_PIN.is_file():
        return None, "missing tools/godot/pin.json"
    pin = json.loads(GODOT_PIN.read_text(encoding="utf-8"))
    engine = pin.get("godot") if isinstance(pin.get("godot"), dict) else {}
    version_id = str(engine.get("version_id", ""))
    if "4.7." + "2" in version_id or "4.8" in version_id:
        return None, f"refused Godot {version_id}"
    if version_id != PINNED_VERSION:
        return None, f"pin version_id {version_id!r} != {PINNED_VERSION}"
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None, "LOCALAPPDATA missing"
    exe = (
        Path(local)
        / "HHGodotAgent"
        / "tooling"
        / "godot-4.7.1-stable"
        / "bin"
        / "Godot_v4.7.1-stable_win64_console.exe"
    )
    if not exe.is_file():
        return None, "pinned 4.7.1-stable console exe is not installed"
    return exe, version_id


def godot_version(exe: Path) -> str:
    proc = subprocess.run(
        [str(exe), "--version"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return text.splitlines()[0].strip() if text else ""


def command_lines_have_path(blob: str) -> bool:
    lowered = blob.replace("\\", "/").lower()
    return any(needle in lowered for needle in PATH_NEEDLES)


def kho_path_busy() -> bool:
    if os.name == "nt":
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_Process | "
                    "Where-Object { $_.Name -match 'Godot' } | "
                    "Select-Object -ExpandProperty CommandLine"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        return command_lines_have_path((proc.stdout or "") + (proc.stderr or ""))
    proc = subprocess.run(["ps", "-ax", "-o", "args="], capture_output=True, text=True, check=False)
    blob = proc.stdout or ""
    return command_lines_have_path(blob) and "godot" in blob.lower()


def kill_kho_path_holders() -> None:
    if os.name == "nt":
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_Process | "
                    "Where-Object { "
                    "$_.Name -match 'Godot' -and "
                    "$_.CommandLine -and "
                    "((($_.CommandLine -replace '\\\\','/') -match 'kho-bi-an') -or "
                    "(($_.CommandLine -replace '\\\\','/') -match 'kho_bi_an')) "
                    "} | ForEach-Object { "
                    "Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue "
                    "}"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        return
    proc = subprocess.run(["ps", "-ax", "-o", "pid=,args="], capture_output=True, text=True, check=False)
    for line in (proc.stdout or "").splitlines():
        lower = line.lower().replace("\\", "/")
        if "kho-bi-an" not in lower and "kho_bi_an" not in lower:
            continue
        if "godot" in lower:
            pid = line.strip().split(None, 1)[0]
            if pid.isdigit():
                subprocess.run(["kill", "-9", pid], check=False, capture_output=True)


def leftover_godot_count() -> int:
    if os.name == "nt":
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "@(Get-CimInstance Win32_Process | Where-Object { "
                    "$_.Name -match 'Godot' -and $_.CommandLine -and "
                    "((($_.CommandLine -replace '\\\\','/') -match 'kho-bi-an') -or "
                    "(($_.CommandLine -replace '\\\\','/') -match 'kho_bi_an')) "
                    "}).Count"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        text = (proc.stdout or "").strip()
        return int(text) if text.isdigit() else (1 if text else 0)
    proc = subprocess.run(["ps", "-ax", "-o", "args="], capture_output=True, text=True, check=False)
    n = 0
    for line in (proc.stdout or "").splitlines():
        lower = line.lower().replace("\\", "/")
        if "godot" in lower and ("kho-bi-an" in lower or "kho_bi_an" in lower):
            n += 1
    return n


def run_godot(exe: Path, args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(exe), *args],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def project_already_imported(root: Path) -> bool:
    uid = root / ".godot" / "uid_cache.bin"
    tile = root / "assets" / "tiles" / "tileset_vault.png.import"
    actor = root / "assets" / "art" / "actor_player.png.import"
    return uid.is_file() and tile.is_file() and actor.is_file()


def import_project(exe: Path, root: Path) -> tuple[bool, str, int]:
    last_rc = 1
    last_blob = ""
    for _attempt in range(2):
        kill_kho_path_holders()
        imported = run_godot(
            exe,
            ["--headless", "--editor", "--path", str(root), "--import", "--quit"],
            180.0,
        )
        last_rc = imported.returncode
        last_blob = (imported.stdout or "") + (imported.stderr or "")
        if last_rc == 0:
            return True, last_blob, last_rc
    if project_already_imported(root):
        return True, last_blob + f"\nHH_IMPORT already-imported after exit={last_rc}", last_rc
    return False, last_blob, last_rc


def harness_audit(
    plan_text: str,
    hashes_a: dict[str, str],
    hashes_b: dict[str, str],
    pin_errors: list[str],
    labels: dict[str, str],
    exe_path: Path | None,
    fresh_root: Path,
) -> list[str]:
    errors: list[str] = []
    errors.extend(plan_errors(plan_text))
    if hashes_a != hashes_b:
        only_a = sorted(set(hashes_a) - set(hashes_b))
        only_b = sorted(set(hashes_b) - set(hashes_a))
        changed = sorted(
            key for key in hashes_a if key in hashes_b and hashes_a[key] != hashes_b[key]
        )
        errors.append(
            f"generated trees differ only_a={only_a[:8]} only_b={only_b[:8]} changed={changed[:8]}"
        )
    errors.extend(pin_errors)
    if labels.get("HUMAN") == "proven":
        errors.append("harness refuses HUMAN=proven; G5 is not faked")
    if labels.get("CRITIC") == "proven":
        errors.append("harness refuses CRITIC=proven; this PID is not an independent critic")
    if labels.get("RUBRIC") == "proven":
        errors.append("harness refuses RUBRIC=proven; Sign column is human")
    if labels.get("HASHES") == "proven":
        errors.append("harness refuses HASHES=proven; artifact exe hash is not pinned")
    if labels.get("RECREATE") == "proven":
        errors.append("harness refuses RECREATE=proven; emit is a snapshot/template, not brief→game")
    for area in RUBRIC_AREAS:
        if area.lower() not in RUBRIC.read_text(encoding="utf-8").lower():
            errors.append(f"review rubric missing {area}")
    if re.search(r"\b(g5\s*pass|dogfood signed|g5 signed)\b", README.read_text(encoding="utf-8"), re.I):
        errors.append("README fakes G5")
    if "return relic_reached" not in (DOGFOOD / "src" / "game_state.gd").read_text(encoding="utf-8"):
        errors.append("dogfood win flag is not relic_reached")
    fresh_state = fresh_root / "src" / "game_state.gd"
    if fresh_state.is_file() and "return relic_reached" not in fresh_state.read_text(encoding="utf-8"):
        errors.append("fresh win flag is not relic_reached")
    if fresh_state.is_file() and "Generated from PROJECT_BRIEF.md" not in fresh_state.read_text(encoding="utf-8"):
        errors.append("fresh sources must be generated from brief+pins")
    # Extra WP3–WP5 files (run_art.gd / run_polish.gd / run_playtest.gd /
    # *.tres) are legal if present and not required this pass. A fuller
    # tree must not be illegal.
    preset = PRESET.read_text(encoding="utf-8")
    for needle in STRIP_NEEDLES:
        if needle not in preset:
            errors.append(f"strip missing {needle}")
    if exe_path is not None:
        data = exe_path.read_bytes()
        if len(data) < 1024:
            errors.append("export exe too small")
        for token in FORBIDDEN_EXPORT:
            if token in data:
                errors.append(f"export contains {token.decode('ascii', errors='replace')}")
    return errors


def write_harness_notes(audit_errors: list[str], labels: dict[str, str]) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    leftover_critic = EVIDENCE / "critic.md"
    if leftover_critic.is_file():
        leftover_critic.unlink()
    lines = [
        "# Same-PID harness notes — R8-WP6",
        "",
        f"Run: `{RUN_ID}`",
        "",
        "This file is written by the official Python PID.",
        "It is not an independent critic and does not score the rubric.",
        "RECREATE stays unproven. The emit is a snapshot/template, not brief→game.",
        "CRITIC stays unproven. RUBRIC stays unproven. HUMAN stays unproven.",
        "G5 stays unsigned. not_g5=1.",
        "",
        f"Labels: {'; '.join(f'{k}={labels[k]}' for k in LABELS)}",
        "",
    ]
    if audit_errors:
        lines.append("Harness audit: FAIL")
        for item in audit_errors:
            lines.append(f"- {item}")
    else:
        lines.append("Harness audit: no local contradictions found")
        lines.append("- generated A and B source trees match (TREE evidence)")
        lines.append("- asset pins match ASSET_MANIFEST")
        lines.append("- rubric Sign column is blank; this PID did not sign")
        lines.append("- win flag remains relic_reached")
        lines.append("- plan still R8-WP6 [ ] 55/60 G5 [ ]")
        lines.append("- HUMAN unproven; this PID did not play as the user")
        lines.append("- RECREATE unproven; snapshot/template emit, not brief→game")
        lines.append("- extra WP3–WP5 files legal if present; not required")
    lines.append("")
    (EVIDENCE / "harness_notes.md").write_text("\n".join(lines), encoding="utf-8")


def write_hashes(
    hashes_a: dict[str, str],
    version: str,
    exe_path: Path | None,
) -> str:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    lines = [
        f"RUN_ID {RUN_ID}",
        f"PIN {PINNED_VERSION}",
        f"GODOT {version}",
        f"PATH {PATH_LABEL}",
        "NOT_G5 1",
        "HUMAN unproven",
        f"FILES {len(hashes_a)}",
    ]
    digest = hashlib.sha256()
    for key in sorted(hashes_a):
        digest.update(key.encode("utf-8"))
        digest.update(b"\n")
        digest.update(hashes_a[key].encode("utf-8"))
        digest.update(b"\n")
    lines.append(f"TREE {digest.hexdigest()}")
    targets = [
        ("BRIEF", BRIEF),
        ("STATE", DOGFOOD / "src" / "game_state.gd"),
        ("PRESET", PRESET),
        ("README", README),
        ("RUBRIC", RUBRIC),
        ("ISSUES", ISSUES),
        ("RECREATE", RECREATE_TOOL),
        ("FRESH_SOURCES", FRESH_SOURCES),
        ("HARNESS", Path(__file__)),
        ("ASSUMPTIONS", EVIDENCE / "assumptions.md"),
        ("HARNESS_NOTES", EVIDENCE / "harness_notes.md"),
    ]
    for name, path in targets:
        if path.is_file():
            lines.append(f"{name} {hashlib.sha256(path.read_bytes()).hexdigest()}")
    if exe_path is not None and exe_path.is_file():
        lines.append(
            f"EXPORT {exe_path.as_posix()} {hashlib.sha256(exe_path.read_bytes()).hexdigest()} unproven"
        )
    lines.append("HASHES unproven")
    lines.append("TREE_NOTE generated sources only; artifact exe hash is not claimed reproducible")
    text = "\n".join(lines) + "\n"
    (EVIDENCE / "hashes.txt").write_text(text, encoding="utf-8")
    return text


def banner_for(labels: dict[str, str]) -> str:
    return "; ".join(f"{k}={labels[k]}" for k in LABELS)


def main() -> int:
    errors: list[str] = []
    labels = {name: "unproven" for name in LABELS}
    labels["HUMAN"] = "unproven"
    errors.extend(src_scan_errors())
    if not PLAN.is_file():
        errors.append(f"missing {rel(PLAN)}")
        emit("FAIL: R8-WP6 Kho Bi An recreation")
        for item in errors:
            emit(f"  - {item}")
        return 1
    plan_text = PLAN.read_text(encoding="utf-8")
    errors.extend(plan_errors(plan_text))
    errors.extend(tree_errors())
    if errors:
        emit(f"FAIL: R8-WP6 Kho Bi An recreation; {banner_for(labels)}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    recreate = load_recreate()
    fresh_a = EVIDENCE / "kho-bi-an-fresh-a"
    fresh_b = EVIDENCE / "kho-bi-an-fresh-b"
    brief = recreate.parse_brief(BRIEF.read_text(encoding="utf-8"))
    if brief["errors"]:
        errors.extend(str(item) for item in brief["errors"])
        emit(f"FAIL: R8-WP6 Kho Bi An recreation; {banner_for(labels)}")
        for item in errors:
            emit(f"  - {item}")
        return 1
    try:
        hashes_a = recreate.recreate_project(fresh_a)
        hashes_b = recreate.recreate_project(fresh_b)
    except (OSError, RuntimeError) as exc:
        emit(f"FAIL: R8-WP6 Kho Bi An recreation; {banner_for(labels)}")
        emit(f"  - recreate failed: {exc}")
        return 1
    pin_errors = recreate.verify_asset_pins(fresh_a)
    pin_errors.extend(recreate.verify_asset_pins(fresh_b))
    pin_errors.extend(recreate.contradict_brief(fresh_a, brief))
    pin_errors.extend(recreate.contradict_brief(fresh_b, brief))
    if hashes_a != hashes_b:
        errors.append("recreate A and B generated trees differ")
    if not hashes_a:
        errors.append("recreate A produced no files")
    errors.extend(pin_errors)

    exe, pin_reason = find_pinned_godot()
    if exe is None:
        errors.append(f"Godot pin: {pin_reason}")
        emit(f"FAIL: R8-WP6 Kho Bi An recreation; {banner_for(labels)}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    kill_kho_path_holders()
    if kho_path_busy():
        errors.append("leftover Godot still holds kho-bi-an --path after kill")
        emit(f"FAIL: R8-WP6 Kho Bi An recreation; {banner_for(labels)}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    version = godot_version(exe)
    if "4.7." + "2" in version or "4.8" in version:
        errors.append(f"refused Godot --version {version!r}")
    elif version != PINNED_VERSION:
        errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")
    if errors:
        emit(f"FAIL: R8-WP6 Kho Bi An recreation; {banner_for(labels)}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    try:
        _templates, template_version = recreate.ensure_windows_templates()
    except RuntimeError as exc:
        errors.append(f"export templates: {exc}")
        emit(f"FAIL: R8-WP6 Kho Bi An recreation; {banner_for(labels)}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    imported_ok, import_blob, import_rc = import_project(exe, fresh_a)
    if not imported_ok:
        errors.append(f"import failed exit={import_rc}\n{import_blob[-4000:]}")
        emit(f"FAIL: R8-WP6 Kho Bi An recreation; {banner_for(labels)}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    kill_kho_path_holders()
    play_args = ["--path", str(fresh_a), "--script", "res://tests/run_all.gd"]
    official_cmd = f"godot --headless --path {rel(fresh_a)} --script res://tests/run_all.gd"
    if os.name == "nt":
        play_args = [
            "--windowed",
            "--resolution",
            "1280x720",
            "--path",
            str(fresh_a),
            "--script",
            "res://tests/run_all.gd",
        ]
        official_cmd = (
            f"godot --windowed --path {rel(fresh_a)} --script res://tests/run_all.gd"
        )
    godot_t0 = time.perf_counter()
    ran = run_godot(exe, play_args, 180.0)
    godot_wall = time.perf_counter() - godot_t0
    blob = (ran.stdout or "") + (ran.stderr or "")
    if ran.returncode != 0:
        errors.append(f"run_all.gd exit={ran.returncode}")
    if re.search(r"SCRIPT ERROR|Parse Error", blob):
        errors.append("Godot reported a script/parse error")
    if "HH_ASSERT_FAIL" in blob:
        errors.append("run_all.gd asserted a graybox failure")
    if "PASS: R8-WP2 graybox" not in blob:
        errors.append("fresh recreate missing graybox PASS banner")
    if not re.search(r"HH_R8WP2\s+LOOP=proven", blob):
        errors.append("fresh recreate LOOP not proven")
    if PATH_LABEL not in blob and "start->key->door->relic->win" not in blob:
        errors.append("fresh recreate did not report start→key→door→relic→win")
    labels["RECREATE"] = "unproven"

    kill_kho_path_holders()
    windows_dir = REPO_ROOT / "artifacts" / "kho-bi-an-review"
    windows_dir.mkdir(parents=True, exist_ok=True)
    exe_out = windows_dir / "KhoBiAn.exe"
    if exe_out.is_file():
        exe_out.unlink()
    export_cmd = [
        "--headless",
        "--path",
        str(fresh_a),
        "--export-release",
        "Windows Desktop",
        str(exe_out),
    ]
    exported = run_godot(exe, export_cmd, 300.0)
    export_blob = (exported.stdout or "") + (exported.stderr or "")
    if exported.returncode != 0 or not exe_out.is_file() or exe_out.stat().st_size < 1024:
        errors.append(f"export-release failed exit={exported.returncode}")
        labels["EXPORT"] = "unproven"
    else:
        export_data = exe_out.read_bytes()
        leaked = [token for token in FORBIDDEN_EXPORT if token in export_data]
        preset_text = PRESET.read_text(encoding="utf-8")
        strip_ok = (not leaked) and all(needle in preset_text for needle in STRIP_NEEDLES)
        if strip_ok:
            labels["EXPORT"] = "proven"
        else:
            labels["EXPORT"] = "unproven"

    labels["CRITIC"] = "unproven"
    labels["RUBRIC"] = "unproven"
    labels["HASHES"] = "unproven"
    audit_errors = harness_audit(
        plan_text,
        hashes_a,
        hashes_b,
        pin_errors,
        labels,
        exe_out if exe_out.is_file() else None,
        fresh_a,
    )
    if audit_errors:
        errors.extend(audit_errors)
    write_harness_notes(audit_errors, labels)

    if labels.get("HUMAN") == "proven":
        errors.append("HUMAN=proven refused: G5 is not faked")
        labels["HUMAN"] = "unproven"

    kill_kho_path_holders()
    leftover = leftover_godot_count()
    if leftover != 0:
        kill_kho_path_holders()
        leftover = leftover_godot_count()
    if leftover != 0:
        errors.append(f"leftover Godot on kho-bi-an={leftover}")

    if errors:
        emit(f"FAIL: R8-WP6 Kho Bi An recreation; {banner_for(labels)}")
        emit(f"  godot_wall_s={godot_wall:.1f} leftover_godot={leftover} not_g5=1")
        for item in errors:
            emit(f"  - {item}")
        emit("---- godot run_all ----")
        emit(blob[-6000:])
        emit("---- godot export ----")
        emit(export_blob[-4000:])
        return 1

    hashes = write_hashes(hashes_a, version, exe_out if exe_out.is_file() else None)
    leftover = leftover_godot_count()
    if leftover != 0:
        emit(f"FAIL: R8-WP6 Kho Bi An recreation; {banner_for(labels)}")
        emit(f"  - leftover Godot on kho-bi-an={leftover}")
        return 1
    emit(f"PASS: R8-WP6 Kho Bi An recreation; {banner_for(labels)}")
    emit(f"  path={PATH_LABEL} pin={PINNED} run_id={RUN_ID} sidecar=none leftover_godot=0")
    emit(f"  godot_wall_s={godot_wall:.1f} templates={template_version} not_g5=1 HUMAN=unproven")
    emit(f"  official={official_cmd}")
    emit(f"  hashes={rel(EVIDENCE / 'hashes.txt')}")
    emit(hashes.rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
