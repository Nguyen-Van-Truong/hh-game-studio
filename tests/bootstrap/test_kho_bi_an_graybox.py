#!/usr/bin/env python3
"""R8-WP2: skeleton gameplay + executable graybox (does not tick the plan).

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Stays runnable while CURRENT_VALID_WP is R8-WP2..R8-WP6 (including R8-WP4+).
Does not start R8-WP5. Does not fake G5 human dogfood. Does not touch GX.
No snake demo. No r7w6 trial. No secret material. No skip-PASS.
--provider plan stays unused here.

Official Godot verify (plan §7.3), path godot/dogfood/kho-bi-an:
  kill leftover Godot on that --path first (no sidecar; game has no addon)
  godot --version
  godot --headless --editor --path <kho-bi-an> --import --quit
  godot --headless --path <kho-bi-an> --script res://tests/run_all.gd

Labels: LOOP, SAVE_LOAD, NO_ERRORS, WIN_FLAG
LOOP path is start→key→door→relic→win. Relic-reached is win.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
DOGFOOD = REPO_ROOT / "godot" / "dogfood" / "kho-bi-an"
BRIEF = DOGFOOD / "PROJECT_BRIEF.md"
RUN_ALL = DOGFOOD / "tests" / "run_all.gd"
GODOT_PIN = REPO_ROOT / "tools" / "godot" / "pin.json"
PINNED_VERSION = "4.7.1.stable.official.a13da4feb"
PINNED = "4.7.1-stable"
RUN_ID = "01R8WP2GBX00000000KBA00001"
PATH_LABEL = "start→key→door→relic→win"
OLD_PATH = "start→key→door→win"
LABELS = ("LOOP", "SAVE_LOAD", "NO_ERRORS", "WIN_FLAG")
PATH_NEEDLES = ("kho-bi-an", "kho_bi_an")


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def emit(text: str) -> None:
    stream = sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    stream.write(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))
    stream.write("\n")


def plan_errors(text: str) -> list[str]:
    errors: list[str] = []
    current = ""
    wp2 = None
    wp3 = None
    g5 = None
    gx = None
    total = None
    r8_row = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R8-WP2\b", stripped):
            wp2 = stripped
        if re.match(r"^R8-WP3\b", stripped):
            wp3 = stripped
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
    if not re.match(r"^R8-WP[2-6]$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (must stay an R8-WP2..R8-WP6 gameplay WP)")
    if wp2 is None:
        errors.append("plan missing R8-WP2 heading")
    if PATH_LABEL not in text:
        errors.append("plan must keep verify path start→key→door→relic→win")
    if OLD_PATH in text:
        errors.append("plan must not use start→key→door→win without relic")
    if total:
        progress = re.search(r"(\d+)/60", total)
        if progress is None or not (51 <= int(progress.group(1)) <= 56):
            errors.append(f"progress must stay 51/60..56/60 while R8 graybox is valid: {total}")
    if r8_row and not re.search(r"\[[ xX]\]\s*[1-6]/6", r8_row):
        errors.append(f"R8 row must stay 1/6..6/6 while graybox remains valid: {r8_row}")
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
    return errors


def tree_errors() -> list[str]:
    errors: list[str] = []
    required = (
        BRIEF,
        DOGFOOD / "project.godot",
        DOGFOOD / "NOTICE.md",
        DOGFOOD / "scenes" / "main.tscn",
        DOGFOOD / "src" / "app.gd",
        DOGFOOD / "src" / "game_session.gd",
        DOGFOOD / "src" / "player.gd",
        DOGFOOD / "src" / "warden.gd",
        DOGFOOD / "src" / "world_builder.gd",
        DOGFOOD / "autoload" / "save_service.gd",
        RUN_ALL,
    )
    for path in required:
        if not path.is_file():
            errors.append(f"missing {rel(path)}")
    godot = (DOGFOOD / "project.godot").read_text(encoding="utf-8") if (DOGFOOD / "project.godot").is_file() else ""
    if 'run/main_scene="res://scenes/main.tscn"' not in godot:
        errors.append("project.godot must set main_scene to res://scenes/main.tscn")
    if "1280" not in godot or "720" not in godot:
        errors.append("project.godot must lock 1280x720")
    if "canvas_items" not in godot:
        errors.append("project.godot must use canvas_items stretch")
    if 'window/stretch/aspect="keep"' not in godot:
        errors.append("project.godot must keep aspect")
    if "hh_agent" in godot or "addons/gut" in godot:
        errors.append("dogfood project must not enable hh_agent or GUT")
    if (DOGFOOD / "addons").exists():
        errors.append("dogfood must not vendor addons")
    snake = DOGFOOD / "snake"
    if snake.exists():
        errors.append("dogfood must not use plugin-project snake/")
    for path in DOGFOOD.rglob("*"):
        if path.is_file() and "PLACEHOLDER" in path.name.upper():
            errors.append(f"PLACEHOLDER asset not allowed: {rel(path)}")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if PATH_LABEL not in run_all:
        errors.append("run_all.gd must assert start→key→door→relic→win")
    if "relic_reached" not in run_all:
        errors.append("run_all.gd must assert relic_reached")
    if "room_id" not in run_all:
        errors.append("run_all.gd must assert room_id")
    if re.search(r"relic_reached\s*=\s*true", run_all):
        errors.append("WIN_FLAG must not poke relic_reached = true")
    session_src = (DOGFOOD / "src" / "game_session.gd").read_text(encoding="utf-8") if (DOGFOOD / "src" / "game_session.gd").is_file() else ""
    if "func _reach_relic" in session_src and "door_open" not in session_src.split("func _reach_relic", 1)[-1].split("func ", 1)[0]:
        errors.append("_reach_relic must require door_open")
    src = ""
    for gd in DOGFOOD.rglob("*.gd"):
        src += gd.read_text(encoding="utf-8") + "\n"
    if "class_name Player" not in src:
        errors.append("player.gd must be a typed Player class")
    if "MOTION_MODE_FLOATING" not in src:
        errors.append("player must use floating motion")
    if "TileMapLayer" not in src:
        errors.append("overworld must build a TileMapLayer")
    if "relic_reached" not in src or "is_win" not in src:
        errors.append("win flag must be relic-reached")
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


def parse_labels(blob: str) -> dict[str, str]:
    found = {name: "unproven" for name in LABELS}
    match = re.search(
        r"HH_R8WP2\s+LOOP=(\w+)\s+SAVE_LOAD=(\w+)\s+NO_ERRORS=(\w+)\s+WIN_FLAG=(\w+)",
        blob,
    )
    if match:
        found["LOOP"] = match.group(1)
        found["SAVE_LOAD"] = match.group(2)
        found["NO_ERRORS"] = match.group(3)
        found["WIN_FLAG"] = match.group(4)
    return found


def main() -> int:
    errors: list[str] = []
    errors.extend(src_scan_errors())
    if not PLAN.is_file():
        errors.append(f"missing {rel(PLAN)}")
        emit("FAIL: R8-WP2 Kho Bi An graybox")
        for item in errors:
            emit(f"  - {item}")
        return 1
    plan_text = PLAN.read_text(encoding="utf-8")
    errors.extend(plan_errors(plan_text))
    errors.extend(tree_errors())

    labels = {name: "unproven" for name in LABELS}
    if errors:
        banner = "; ".join(f"{k}={labels[k]}" for k in LABELS)
        emit(f"FAIL: R8-WP2 Kho Bi An graybox; {banner}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    exe, pin_reason = find_pinned_godot()
    if exe is None:
        errors.append(f"Godot pin: {pin_reason}")
        emit("FAIL: R8-WP2 Kho Bi An graybox; LOOP=unproven; SAVE_LOAD=unproven; NO_ERRORS=unproven; WIN_FLAG=unproven")
        for item in errors:
            emit(f"  - {item}")
        return 1

    kill_kho_path_holders()
    if kho_path_busy():
        errors.append("leftover Godot still holds kho-bi-an --path after kill")

    version = godot_version(exe)
    if "4.7." + "2" in version or "4.8" in version:
        errors.append(f"refused Godot --version {version!r}")
    elif version != PINNED_VERSION:
        errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")

    imported = run_godot(
        exe,
        ["--headless", "--editor", "--path", str(DOGFOOD), "--import", "--quit"],
        180.0,
    )
    import_blob = (imported.stdout or "") + (imported.stderr or "")
    if imported.returncode != 0:
        errors.append(f"import failed exit={imported.returncode}\n{import_blob[-4000:]}")

    kill_kho_path_holders()
    ran = run_godot(
        exe,
        ["--headless", "--path", str(DOGFOOD), "--script", "res://tests/run_all.gd"],
        180.0,
    )
    blob = (ran.stdout or "") + (ran.stderr or "")
    labels = parse_labels(blob)
    if ran.returncode != 0:
        errors.append(f"run_all.gd exit={ran.returncode}")
    if (
        PATH_LABEL not in blob
        and "HH_R8WP2_PATH" not in blob
        and "start->key->door->relic->win" not in blob
    ):
        errors.append("run_all.gd did not report start→key→door→relic→win")
    if re.search(r"SCRIPT ERROR|Parse Error", blob):
        errors.append("Godot reported a script/parse error")
        labels["NO_ERRORS"] = "unproven"
    if "HH_ASSERT_FAIL" in blob:
        errors.append("run_all.gd asserted a gameplay failure")
    for key in LABELS:
        if labels[key] != "proven":
            errors.append(f"{key} not proven")
    if "PASS: R8-WP2 graybox" not in blob:
        errors.append("run_all.gd missing PASS banner")

    banner = "; ".join(f"{k}={labels[k]}" for k in LABELS)
    if errors:
        emit(f"FAIL: R8-WP2 Kho Bi An graybox; {banner}")
        for item in errors:
            emit(f"  - {item}")
        emit("---- godot run_all ----")
        emit(blob[-6000:])
        return 1
    emit(f"PASS: R8-WP2 Kho Bi An graybox; {banner}")
    emit(f"  path={PATH_LABEL} pin={PINNED} run_id={RUN_ID} sidecar=none")
    emit(f"  official=godot --headless --path {rel(DOGFOOD)} --script res://tests/run_all.gd")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
