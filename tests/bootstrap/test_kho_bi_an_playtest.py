#!/usr/bin/env python3
"""R8-WP5: agent playtest, balance, save/load, bug bash (does not tick the plan).

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R8-WP5 [ ]; CURRENT_VALID_WP=R8-WP5; progress stays 54/60.
Does not start R8-WP6. Does not fake G5 human dogfood. Does not touch GX.
Win flag stays relic-reached. Do not poke relic_reached as a cheat.
No snake demo. No r7w6 trial. No secret material. No skip-PASS.
--provider plan stays unused here. No remote imagegen. No invented API key.

Official Godot verify (plan §7.3), path godot/dogfood/kho-bi-an:
  kill leftover Godot on that --path first (no sidecar; game has no addon)
  godot --version
  godot --headless --editor --path <kho-bi-an> --import --quit
  Retry import or treat already-imported project as ok; never stamp proven on FAIL
  On Windows: godot --windowed --path <kho-bi-an> --script res://tests/run_playtest.gd
  (windowed Viewport.get_image + 600s wall-clock production soak is official, not G5)
  godot --headless --path <kho-bi-an> --script res://tests/run_all.gd

Labels: RUNS, SOAK, STUCK, PERF, VISUAL, CLEAN
Graybox LOOP must stay proven. Relic-reached is win.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
DOGFOOD = REPO_ROOT / "godot" / "dogfood" / "kho-bi-an"
BRIEF = DOGFOOD / "PROJECT_BRIEF.md"
RUN_PLAYTEST = DOGFOOD / "tests" / "run_playtest.gd"
RUN_ALL = DOGFOOD / "tests" / "run_all.gd"
GODOT_PIN = REPO_ROOT / "tools" / "godot" / "pin.json"
EVIDENCE = REPO_ROOT / ".hh-agent" / "evidence" / "01R8WP5PTT00000000KBA00001"
PINNED_VERSION = "4.7.1.stable.official.a13da4feb"
PINNED = "4.7.1-stable"
RUN_ID = "01R8WP5PTT00000000KBA00001"
PATH_LABEL = "start→key→door→relic→win"
LABELS = ("RUNS", "SOAK", "STUCK", "PERF", "VISUAL", "CLEAN")
PATH_NEEDLES = ("kho-bi-an", "kho_bi_an")
SOAK_WALL_S = 600.0
SEEDED_MIN = 20
P95_TARGET_MS = 16.67


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
    wp5 = None
    wp6 = None
    g5 = None
    gx = None
    total = None
    r8_row = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R8-WP5\b", stripped):
            wp5 = stripped
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
    if current != "R8-WP5":
        errors.append(f"CURRENT_VALID_WP={current!r} (must stay R8-WP5)")
    if wp5 is None:
        errors.append("plan missing R8-WP5 heading")
    elif re.search(r"\[x\]", wp5, re.I):
        errors.append("R8-WP5 must stay unticked")
    if wp6 is not None and re.search(r"\[x\]", wp6, re.I):
        errors.append("R8-WP6 must stay unticked; this WP does not start recreation/G5")
    if PATH_LABEL not in text:
        errors.append("plan must keep verify path start→key→door→relic→win")
    if total and "54/60" not in total:
        errors.append(f"progress must stay 54/60 while R8-WP5 is unticked: {total}")
    if r8_row and not re.search(r"\[ \]\s*4/6", r8_row):
        errors.append(f"R8 row must stay 4/6 while WP5 is unticked: {r8_row}")
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
    play = RUN_PLAYTEST.read_text(encoding="utf-8") if RUN_PLAYTEST.is_file() else ""
    if re.search(r"relic_reached\s*=\s*true", play):
        errors.append("WIN_FLAG must not poke relic_reached = true in a play path")
    if "wall_s" not in play or "SOAK_WALL_S" not in play:
        errors.append("run_playtest.gd must run a 600s wall-clock soak")
    if "Engine.time_scale" not in play:
        errors.append("run_playtest.gd must pin Engine.time_scale=1 for soak")
    if "test_driven = false" not in play and "test_driven=false" not in play:
        errors.append("run_playtest.gd soak must use production test_driven=false")
    if "HH_R8WP5_FAST" not in play:
        errors.append("run_playtest.gd must refuse FAST soak proven")
    if "continue_run" not in play:
        errors.append("run_playtest.gd save/load must restore via continue_run")
    if re.search(r'"has_key"\s*:\s*true', play) and "write_slot" in play:
        errors.append("load must not plant {has_key, door_open} via write_slot")
    if "skip_item" not in play or "save_mid" not in play or "load" not in play:
        errors.append("run_playtest.gd must cover skip_item, save_mid, load")
    if "parse_input_event" not in play and "pressed.emit" not in play:
        errors.append("run_playtest.gd must fuzz UI without mouse ownership")
    if "dummy-renderer" not in play:
        errors.append("run_playtest.gd must name the headless dummy-renderer capture limit")
    if "not_g5" not in play:
        errors.append("run_playtest.gd must mark soak as not G5")
    if "perf_counter" not in self_text and "monotonic" not in self_text:
        errors.append("official test must measure Godot wall-clock")
    return errors


def tree_errors() -> list[str]:
    errors: list[str] = []
    required = (
        BRIEF,
        RUN_PLAYTEST,
        RUN_ALL,
        DOGFOOD / "NOTICE.md",
        DOGFOOD / "project.godot",
        DOGFOOD / "src" / "game_session.gd",
        DOGFOOD / "src" / "game_state.gd",
        DOGFOOD / "autoload" / "save_service.gd",
        EVIDENCE / "assumptions.md",
    )
    for path in required:
        if not path.is_file():
            errors.append(f"missing {rel(path)}")
    state = (DOGFOOD / "src" / "game_state.gd").read_text(encoding="utf-8")
    if "return relic_reached" not in state:
        errors.append("win flag must stay relic_reached")
    session = (DOGFOOD / "src" / "game_session.gd").read_text(encoding="utf-8")
    if "func _reach_relic" in session:
        body = session.split("func _reach_relic", 1)[-1].split("func ", 1)[0]
        if "door_open" not in body:
            errors.append("_reach_relic must require door_open")
    if "_prune_vfx" not in session:
        errors.append("session must prune interact VFX during mash/soak")
    if PATH_LABEL not in RUN_ALL.read_text(encoding="utf-8"):
        errors.append("run_all.gd must keep start→key→door→relic→win")
    if re.search(r"relic_reached\s*=\s*true", RUN_ALL.read_text(encoding="utf-8")):
        errors.append("run_all.gd must not poke relic_reached = true")
    if (DOGFOOD / "addons").exists():
        errors.append("dogfood must not vendor addons")
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


def parse_labels(blob: str) -> dict[str, str]:
    found = {name: "unproven" for name in LABELS}
    match = re.search(
        r"HH_R8WP5\s+RUNS=(\w+)\s+SOAK=(\w+)\s+STUCK=(\w+)\s+PERF=(\w+)\s+VISUAL=(\w+)\s+CLEAN=(\w+)",
        blob,
    )
    if match:
        found["RUNS"] = match.group(1)
        found["SOAK"] = match.group(2)
        found["STUCK"] = match.group(3)
        found["PERF"] = match.group(4)
        found["VISUAL"] = match.group(5)
        found["CLEAN"] = match.group(6)
    return found


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _unfilter_png(raw: bytes, width: int, height: int, bpp: int) -> bytes:
    stride = width * bpp
    out = bytearray()
    prev = bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        filt = raw[start]
        row = bytearray(raw[start + 1 : start + 1 + stride])
        if filt == 1:
            for i in range(stride):
                left = row[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + left) & 255
        elif filt == 2:
            for i in range(stride):
                row[i] = (row[i] + prev[i]) & 255
        elif filt == 3:
            for i in range(stride):
                left = row[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + ((left + prev[i]) // 2)) & 255
        elif filt == 4:
            for i in range(stride):
                left = row[i - bpp] if i >= bpp else 0
                up_left = prev[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + _paeth(left, prev[i], up_left)) & 255
        elif filt != 0:
            raise ValueError(f"filter {filt} not supported")
        out.extend(row)
        prev = row
    return bytes(out)


def _png_rgba(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"{path} is not a PNG")
    pos = 8
    width = height = 0
    color_type = 6
    bit_depth = 8
    interlace = 0
    idat = bytearray()
    while pos + 8 <= len(data):
        length = int.from_bytes(data[pos : pos + 4], "big")
        tag = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if tag == b"IHDR":
            width = int.from_bytes(chunk[0:4], "big")
            height = int.from_bytes(chunk[4:8], "big")
            bit_depth = chunk[8]
            color_type = chunk[9]
            interlace = chunk[12]
        elif tag == b"IDAT":
            idat.extend(chunk)
        elif tag == b"IEND":
            break
    if bit_depth != 8 or interlace != 0:
        raise ValueError(f"{path.name} unsupported png depth={bit_depth} interlace={interlace}")
    bpp = {2: 3, 6: 4}.get(color_type)
    if bpp is None:
        raise ValueError(f"{path.name} unsupported png color_type={color_type}")
    raw = zlib.decompress(bytes(idat))
    pixels = _unfilter_png(raw, width, height, bpp)
    if bpp == 4:
        return width, height, pixels
    rgba = bytearray()
    i = 0
    while i < len(pixels):
        rgba.extend(pixels[i : i + 3])
        rgba.append(255)
        i += 3
    return width, height, bytes(rgba)


def png_review_stats(path: Path) -> dict[str, float | int]:
    width, height, rgba = _png_rgba(path)
    stride = width * 4
    unique: set[tuple[int, int, int]] = set()
    total = 0
    clear_n = 0
    for y in range(0, height, 2):
        row = rgba[y * stride : (y + 1) * stride]
        for x in range(0, width, 2):
            i = x * 4
            if row[i + 3] < 40:
                continue
            r, g, b = row[i], row[i + 1], row[i + 2]
            total += 1
            unique.add((r, g, b))
            if abs(r - 76) <= 3 and abs(g - 76) <= 3 and abs(b - 76) <= 3:
                clear_n += 1
    return {
        "width": width,
        "height": height,
        "unique": len(unique),
        "engine_clear_share": (clear_n / total) if total else 1.0,
    }


def copy_artifacts(blob: str) -> tuple[list[str], dict]:
    errors: list[str] = []
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    report: dict = {}
    appdata = os.environ.get("APPDATA", "")
    userdata = Path(appdata) / "Godot" / "app_userdata" / "Kho Bi An" if appdata else None
    abs_by_tag: dict[str, str] = {}
    for match in re.finditer(r"HH_R8WP5_SHOT_ABS\s+(\S+)\s+(.+)", blob):
        abs_by_tag[match.group(1)] = match.group(2).strip()
    for match in re.finditer(r"HH_R8WP5_SHOT\s+(\S+)\s+(user://\S+)\s+([0-9a-f]{64})", blob):
        tag, user_path, digest = match.groups()
        name = user_path.rsplit("/", 1)[-1]
        candidates = []
        if tag in abs_by_tag:
            candidates.append(Path(abs_by_tag[tag]))
        if userdata is not None:
            candidates.append(userdata / name)
        src = next((path for path in candidates if path.is_file()), None)
        if src is None:
            errors.append(f"shot missing on disk {name}")
            continue
        got = hashlib.sha256(src.read_bytes()).hexdigest()
        if got != digest:
            errors.append(f"shot hash mismatch {src.name}")
            continue
        dest = EVIDENCE / src.name
        shutil.copy2(src, dest)
        if dest.stat().st_size < 64:
            errors.append(f"shot too small {dest.name}")
            continue
        try:
            stats = png_review_stats(dest)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if int(stats["unique"]) < 6:
            errors.append(f"VISUAL {dest.name} is too flat unique={stats['unique']}")
        if float(stats["engine_clear_share"]) >= 0.45:
            errors.append(f"VISUAL {dest.name} engine-clear share={stats['engine_clear_share']:.3f}")
    report_abs = ""
    match_rep = re.search(r"HH_R8WP5_REPORT_ABS\s+(.+)", blob)
    if match_rep:
        report_abs = match_rep.group(1).strip()
    report_candidates = []
    if report_abs:
        report_candidates.append(Path(report_abs))
    if userdata is not None:
        report_candidates.append(userdata / "kho_bi_an_r8wp5_report.json")
    src_report = next((path for path in report_candidates if path.is_file()), None)
    if src_report is None:
        errors.append("playtest report missing on disk")
    else:
        dest_report = EVIDENCE / "playtest_report.json"
        shutil.copy2(src_report, dest_report)
        try:
            report = json.loads(dest_report.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            errors.append("playtest report is not JSON")
            report = {}
    return errors, report


def project_already_imported() -> bool:
    uid = DOGFOOD / ".godot" / "uid_cache.bin"
    tile = DOGFOOD / "assets" / "tiles" / "tileset_vault.png.import"
    actor = DOGFOOD / "assets" / "art" / "actor_player.png.import"
    return uid.is_file() and tile.is_file() and actor.is_file()


def import_project(exe: Path) -> tuple[bool, str, int]:
    last_rc = 1
    last_blob = ""
    for _attempt in range(2):
        kill_kho_path_holders()
        imported = run_godot(
            exe,
            ["--headless", "--editor", "--path", str(DOGFOOD), "--import", "--quit"],
            180.0,
        )
        last_rc = imported.returncode
        last_blob = (imported.stdout or "") + (imported.stderr or "")
        if last_rc == 0:
            return True, last_blob, last_rc
    if project_already_imported():
        return True, last_blob + f"\nHH_IMPORT already-imported after exit={last_rc}", last_rc
    return False, last_blob, last_rc


def write_backlog(report: dict, extra: list[str]) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    lines = [
        "# R8-WP5 P2 backlog",
        "",
        f"Run: `{RUN_ID}`",
        "",
        "P0/P1 found in the bash are fixed in product code. These P2 items",
        "are recorded with playtest evidence. Not G5.",
        "",
    ]
    items = []
    raw = report.get("p2") if isinstance(report, dict) else None
    if isinstance(raw, list):
        items.extend(str(x) for x in raw)
    items.extend(extra)
    if not items:
        items.append(
            "Save schema v1 does not persist player position; Continue respawns at room spawn. "
            "Repro: save_mid then load (seeded cases 17-19)."
        )
        items.append(
            "No drop-item action; bỏ item is skip-pickup only. Repro: skip_item cases 5-7."
        )
    for i, item in enumerate(items, start=1):
        lines.append(f"{i}. {item}")
    lines.append("")
    (EVIDENCE / "backlog.md").write_text("\n".join(lines), encoding="utf-8")


def write_hashes() -> str:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    lines = [
        f"RUN_ID {RUN_ID}",
        f"PIN {PINNED_VERSION}",
        f"PATH {PATH_LABEL}",
        "NOT_G5 1",
    ]
    targets = [
        ("SESSION", DOGFOOD / "src" / "game_session.gd"),
        ("STATE", DOGFOOD / "src" / "game_state.gd"),
        ("SAVE", DOGFOOD / "autoload" / "save_service.gd"),
        ("PLAYER", DOGFOOD / "src" / "player.gd"),
        ("WARDEN", DOGFOOD / "src" / "warden.gd"),
        ("RUN_PLAYTEST", RUN_PLAYTEST),
        ("RUN_ALL", RUN_ALL),
        ("HARNESS", Path(__file__)),
        ("ASSUMPTIONS", EVIDENCE / "assumptions.md"),
        ("BACKLOG", EVIDENCE / "backlog.md"),
        ("REPORT", EVIDENCE / "playtest_report.json"),
    ]
    for name, path in targets:
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{name} {digest}")
    for shot in sorted(EVIDENCE.glob("kho_bi_an_r8wp5_*.png")):
        digest = hashlib.sha256(shot.read_bytes()).hexdigest()
        lines.append(f"SHOT {shot.name} {digest}")
    text = "\n".join(lines) + "\n"
    (EVIDENCE / "hashes.txt").write_text(text, encoding="utf-8")
    return text


def banner_for(labels: dict[str, str]) -> str:
    return "; ".join(f"{k}={labels[k]}" for k in LABELS)


def main() -> int:
    errors: list[str] = []
    errors.extend(src_scan_errors())
    if not PLAN.is_file():
        errors.append(f"missing {rel(PLAN)}")
        emit("FAIL: R8-WP5 Kho Bi An playtest")
        for item in errors:
            emit(f"  - {item}")
        return 1
    plan_text = PLAN.read_text(encoding="utf-8")
    errors.extend(plan_errors(plan_text))
    errors.extend(tree_errors())

    labels = {name: "unproven" for name in LABELS}
    if os.environ.get("HH_R8WP5_FAST", "").strip().lower() in ("1", "true", "yes"):
        errors.append("HH_R8WP5_FAST cannot stamp official SOAK")
    if errors:
        emit(f"FAIL: R8-WP5 Kho Bi An playtest; {banner_for(labels)}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    exe, pin_reason = find_pinned_godot()
    if exe is None:
        errors.append(f"Godot pin: {pin_reason}")
        emit(f"FAIL: R8-WP5 Kho Bi An playtest; {banner_for(labels)}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    kill_kho_path_holders()
    if kho_path_busy():
        errors.append("leftover Godot still holds kho-bi-an --path after kill")
        emit(f"FAIL: R8-WP5 Kho Bi An playtest; {banner_for(labels)}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    version = godot_version(exe)
    if "4.7." + "2" in version or "4.8" in version:
        errors.append(f"refused Godot --version {version!r}")
    elif version != PINNED_VERSION:
        errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")
    if errors:
        emit(f"FAIL: R8-WP5 Kho Bi An playtest; {banner_for(labels)}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    imported_ok, import_blob, import_rc = import_project(exe)
    if not imported_ok:
        errors.append(f"import failed exit={import_rc}\n{import_blob[-4000:]}")
        emit(f"FAIL: R8-WP5 Kho Bi An playtest; {banner_for(labels)}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    kill_kho_path_holders()
    play_args = ["--path", str(DOGFOOD), "--script", "res://tests/run_playtest.gd"]
    official_cmd = f"godot --headless --path {rel(DOGFOOD)} --script res://tests/run_playtest.gd"
    if os.name == "nt":
        play_args = [
            "--windowed",
            "--resolution",
            "1280x720",
            "--path",
            str(DOGFOOD),
            "--script",
            "res://tests/run_playtest.gd",
        ]
        official_cmd = (
            f"godot --windowed --path {rel(DOGFOOD)} --script res://tests/run_playtest.gd"
        )
    godot_t0 = time.perf_counter()
    ran = run_godot(exe, play_args, 1500.0)
    godot_wall = time.perf_counter() - godot_t0
    blob = (ran.stdout or "") + (ran.stderr or "")
    labels = parse_labels(blob)
    if ran.returncode != 0:
        errors.append(f"run_playtest.gd exit={ran.returncode}")
    if re.search(r"SCRIPT ERROR|Parse Error", blob):
        errors.append("Godot reported a script/parse error")
        labels["CLEAN"] = "unproven"
    if "HH_ASSERT_FAIL" in blob:
        errors.append("run_playtest.gd asserted a playtest failure")
    if "HH_R8WP5_DISPLAY headless" in blob:
        errors.append("VISUAL refuse dummy-renderer / headless capture")
        labels["VISUAL"] = "unproven"
    soak_done = re.search(
        r"HH_R8WP5_SOAK_DONE frames=(\d+) wall_s=([0-9.]+) os_s=([0-9.]+) time_scale=([0-9.]+) test_driven=(\d+).*blockers=(\d+)",
        blob,
    )
    if soak_done is None:
        errors.append("SOAK missing HH_R8WP5_SOAK_DONE wall-clock banner")
        labels["SOAK"] = "unproven"
    else:
        wall_s = float(soak_done.group(2))
        os_s = float(soak_done.group(3))
        time_scale = float(soak_done.group(4))
        test_driven = int(soak_done.group(5))
        blockers = int(soak_done.group(6))
        if wall_s + 0.001 < SOAK_WALL_S or os_s + 0.001 < SOAK_WALL_S:
            errors.append(f"SOAK short wall_s={wall_s} os_s={os_s}")
            labels["SOAK"] = "unproven"
        if abs(time_scale - 1.0) > 0.001:
            errors.append(f"SOAK time_scale={time_scale} != 1")
            labels["SOAK"] = "unproven"
        if test_driven != 0:
            errors.append("SOAK ran with test_driven=1")
            labels["SOAK"] = "unproven"
        if blockers != 0:
            errors.append(f"SOAK blockers={blockers}")
            labels["SOAK"] = "unproven"
    if godot_wall + 0.001 < SOAK_WALL_S:
        errors.append(f"SOAK Godot wall {godot_wall:.1f}s < 600")
        labels["SOAK"] = "unproven"
    if labels.get("SOAK") == "proven" and godot_wall + 0.001 < SOAK_WALL_S:
        errors.append("SOAK=proven refused: Godot wall < 600")
        labels["SOAK"] = "unproven"
    if "HH_R8WP5_SOAK_FAST" in blob:
        errors.append("FAST soak cannot be official")
        labels["SOAK"] = "unproven"
    if "blockers=0" not in blob and "blockers=0" not in (soak_done.group(0) if soak_done else ""):
        if "blockers=0" not in blob:
            errors.append("SOAK did not report blockers=0")
            labels["SOAK"] = "unproven"
    if "PASS: R8-WP5 playtest 20 seeded + 10min soak" not in blob:
        errors.append("run_playtest.gd missing PASS banner")
    perf_line = re.search(r"HH_R8WP5_PERF load_ms=(\d+) p95_ms=([0-9.]+)", blob)
    if labels.get("PERF") == "proven":
        if perf_line is None:
            errors.append("PERF=proven missing p95 banner")
            labels["PERF"] = "unproven"
        elif float(perf_line.group(2)) > P95_TARGET_MS + 0.001:
            errors.append(
                f"PERF=proven refused: p95 {perf_line.group(2)} ms > {P95_TARGET_MS}"
            )
            labels["PERF"] = "unproven"
    for key in LABELS:
        if key == "PERF":
            continue
        if labels[key] != "proven":
            errors.append(f"{key} not proven")

    kill_kho_path_holders()
    gray = run_godot(
        exe,
        ["--headless", "--path", str(DOGFOOD), "--script", "res://tests/run_all.gd"],
        180.0,
    )
    gray_blob = (gray.stdout or "") + (gray.stderr or "")
    if gray.returncode != 0 or "PASS: R8-WP2 graybox" not in gray_blob:
        errors.append("graybox loop is no longer testable")
    if PATH_LABEL not in gray_blob and "start->key->door->relic->win" not in gray_blob:
        errors.append("graybox did not report start→key→door→relic→win")
    if not re.search(r"HH_R8WP2\s+LOOP=proven", gray_blob):
        errors.append("graybox LOOP not proven after playtest")

    if errors:
        emit(f"FAIL: R8-WP5 Kho Bi An playtest; {banner_for(labels)}")
        emit(f"  godot_wall_s={godot_wall:.1f} leftover_godot={leftover_godot_count()} not_g5=1")
        for item in errors:
            emit(f"  - {item}")
        emit("---- godot run_playtest ----")
        emit(blob[-8000:])
        emit("---- godot run_all ----")
        emit(gray_blob[-3000:])
        return 1

    art_errors, report = copy_artifacts(blob)
    if art_errors:
        emit(f"FAIL: R8-WP5 Kho Bi An playtest; {banner_for(labels)}")
        for item in art_errors:
            emit(f"  - {item}")
        emit("---- godot run_playtest ----")
        emit(blob[-8000:])
        return 1
    seeded = report.get("seeded_count") if isinstance(report, dict) else 0
    if not isinstance(seeded, int) or seeded < SEEDED_MIN:
        emit(f"FAIL: R8-WP5 Kho Bi An playtest; {banner_for(labels)}")
        emit(f"  - seeded_count {seeded!r} < {SEEDED_MIN}")
        return 1
    if bool(report.get("soak_blockers", 1)):
        emit(f"FAIL: R8-WP5 Kho Bi An playtest; {banner_for(labels)}")
        emit(f"  - report soak_blockers={report.get('soak_blockers')}")
        return 1
    report_wall = report.get("soak_wall_s") if isinstance(report, dict) else 0
    try:
        report_wall_f = float(report_wall)
    except (TypeError, ValueError):
        report_wall_f = 0.0
    if report_wall_f + 0.001 < SOAK_WALL_S:
        emit(f"FAIL: R8-WP5 Kho Bi An playtest; {banner_for(labels)}")
        emit(f"  - report soak_wall_s={report_wall!r} < {SOAK_WALL_S}")
        return 1
    if bool(report.get("soak_fast", False)):
        emit(f"FAIL: R8-WP5 Kho Bi An playtest; {banner_for(labels)}")
        emit("  - report soak_fast cannot be official")
        return 1
    extra_p2: list[str] = []
    if labels.get("PERF") != "proven":
        raw_p2 = report.get("p2") if isinstance(report, dict) else None
        p2_text = " ".join(str(x) for x in raw_p2) if isinstance(raw_p2, list) else ""
        if "PERF=unproven" not in p2_text and "16.67" not in p2_text and "60fps" not in p2_text:
            extra_p2.append("PERF left unproven; file p95 vs 16.67 ms 60fps target")
    write_backlog(report, extra_p2)
    hashes = write_hashes()
    leftover = leftover_godot_count()
    if leftover != 0:
        kill_kho_path_holders()
        leftover = leftover_godot_count()
    if leftover != 0:
        emit(f"FAIL: R8-WP5 Kho Bi An playtest; {banner_for(labels)}")
        emit(f"  - leftover Godot on kho-bi-an={leftover}")
        return 1
    emit(f"PASS: R8-WP5 Kho Bi An playtest; {banner_for(labels)}")
    emit(f"  path={PATH_LABEL} pin={PINNED} run_id={RUN_ID} sidecar=none leftover_godot=0")
    emit(f"  godot_wall_s={godot_wall:.1f} soak_wall_s={report_wall_f:.1f} not_g5=1")
    emit(f"  official={official_cmd}")
    emit(f"  hashes={rel(EVIDENCE / 'hashes.txt')}")
    emit(hashes.rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
