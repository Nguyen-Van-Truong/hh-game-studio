#!/usr/bin/env python3
"""R8-WP4: integrate art, UI, feedback, accessibility, polish (does not tick the plan).

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R8-WP4 [ ]; CURRENT_VALID_WP=R8-WP4; progress stays 53/60.
Does not start R8-WP5 playtest. Does not fake G5 human dogfood. Does not touch GX.
Win flag stays relic-reached. ColorRects stay as invisible colliders.
No snake demo. No r7w6 trial. No secret material. No skip-PASS.
--provider plan stays unused here. No remote imagegen.

Official Godot verify (plan §7.3), path godot/dogfood/kho-bi-an:
  kill leftover Godot on that --path first (no sidecar; game has no addon)
  godot --version
  godot --headless --editor --path <kho-bi-an> --import --quit
  Retry import or treat already-imported project as ok; never stamp proven on FAIL
  On Windows UI-visible polish: godot --windowed --path <kho-bi-an> --script res://tests/run_polish.gd
  (dummy-renderer headless cannot stamp VISUAL; windowed viewport frame is official, not G5)
  godot --headless --path <kho-bi-an> --script res://tests/run_all.gd

Labels: VISUAL, INPUT, REVIEW
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
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
DOGFOOD = REPO_ROOT / "godot" / "dogfood" / "kho-bi-an"
BRIEF = DOGFOOD / "PROJECT_BRIEF.md"
MANIFEST = DOGFOOD / "assets" / "ASSET_MANIFEST.json"
RUN_POLISH = DOGFOOD / "tests" / "run_polish.gd"
RUN_ALL = DOGFOOD / "tests" / "run_all.gd"
GODOT_PIN = REPO_ROOT / "tools" / "godot" / "pin.json"
EVIDENCE = REPO_ROOT / ".hh-agent" / "evidence" / "01R8WP4PLZ00000000KBA00001"
PINNED_VERSION = "4.7.1.stable.official.a13da4feb"
PINNED = "4.7.1-stable"
RUN_ID = "01R8WP4PLZ00000000KBA00001"
PATH_LABEL = "start→key→door→relic→win"
LABELS = ("VISUAL", "INPUT", "REVIEW")
PATH_NEEDLES = ("kho-bi-an", "kho_bi_an")
SHIP_PATHS = (
    "res://assets/tiles/tileset_vault.png",
    "res://assets/art/actor_player.png",
    "res://assets/art/actor_warden.png",
    "res://assets/art/item_key.png",
    "res://assets/art/prop_door.png",
    "res://assets/art/item_relic.png",
    "res://assets/ui/ui_icon_key.png",
    "res://assets/vfx/vfx_interact.png",
    "res://assets/audio/sfx_pickup.wav",
    "res://assets/audio/sfx_door.wav",
    "res://assets/audio/sfx_caught.wav",
    "res://assets/audio/sfx_win.wav",
    "res://assets/audio/sfx_lose.wav",
    "res://assets/audio/sfx_interact.wav",
    "res://assets/audio/music_vault.wav",
)


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
    wp4 = None
    wp5 = None
    g5 = None
    gx = None
    total = None
    r8_row = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R8-WP4\b", stripped):
            wp4 = stripped
        if re.match(r"^R8-WP5\b", stripped):
            wp5 = stripped
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
    if current != "R8-WP4":
        errors.append(f"CURRENT_VALID_WP={current!r} (must stay R8-WP4)")
    if wp4 is None:
        errors.append("plan missing R8-WP4 heading")
    elif re.search(r"\[x\]", wp4, re.I):
        errors.append("R8-WP4 must stay unticked")
    if wp5 is not None and re.search(r"\[x\]", wp5, re.I):
        errors.append("R8-WP5 must stay unticked; this WP does not start playtest")
    if PATH_LABEL not in text:
        errors.append("plan must keep verify path start→key→door→relic→win")
    if total and "53/60" not in total:
        errors.append(f"progress must stay 53/60 while R8-WP4 is unticked: {total}")
    if r8_row and not re.search(r"\[ \]\s*3/6", r8_row):
        errors.append(f"R8 row must stay 3/6 while WP4 is unticked: {r8_row}")
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
    run_polish = RUN_POLISH.read_text(encoding="utf-8") if RUN_POLISH.is_file() else ""
    if re.search(r"relic_reached\s*=\s*true", run_polish):
        errors.append("WIN_FLAG must not poke relic_reached = true in a play path")
    if "get_image()" not in run_polish and "texture_2d_get" not in run_polish:
        errors.append("run_polish.gd must capture Viewport.get_image/texture_2d_get")
    if "_composite_play" in run_polish or "_blit_scaled" in run_polish:
        errors.append("run_polish.gd must not software-blit VISUAL baselines")
    if "_capture_subviewport" in run_polish:
        errors.append("run_polish.gd must not silently fallback to SubViewport capture")
    if re.search(r"content_scale_mode\s*=\s*Window\.CONTENT_SCALE_MODE_CANVAS_ITEMS", run_polish):
        errors.append("run_polish.gd must not stretch one blit via content scale")
    if "window_get_size" not in run_polish:
        errors.append("run_polish.gd must assert DisplayServer.window_get_size")
    if "76" not in run_polish or "engine-clear" not in run_polish:
        errors.append("run_polish.gd must reject engine-clear 76,76,76")
    if re.search(r"step_fixed\([\s\S]{0,120}Input\.is_action", run_polish):
        errors.append("INPUT must not force-feed interact into step_fixed")
    flow = re.search(r"func _test_input_flow[\s\S]*?\nfunc _test_settings", run_polish)
    if flow and "step_fixed" in flow.group(0):
        errors.append("INPUT flow must not call step_fixed")
    if flow and "test_driven = true" in flow.group(0):
        errors.append("INPUT flow must not flip test_driven=true after parse_input_event")
    if "parse_input_event" not in run_polish:
        errors.append("run_polish.gd must inject parse_input_event")
    if "InputEventKey" not in run_polish:
        errors.append("run_polish.gd must inject InputEventKey")
    if "InputEventJoypadButton" not in run_polish:
        errors.append("run_polish.gd must inject InputEventJoypadButton")
    if "dummy-renderer" not in run_polish:
        errors.append("run_polish.gd must name the headless dummy-renderer capture limit")
    return errors


def tree_errors() -> list[str]:
    errors: list[str] = []
    required = (
        BRIEF,
        MANIFEST,
        RUN_POLISH,
        RUN_ALL,
        DOGFOOD / "NOTICE.md",
        DOGFOOD / "project.godot",
        DOGFOOD / "src" / "visuals.gd",
        DOGFOOD / "src" / "sfx_bank.gd",
        DOGFOOD / "src" / "ui" / "ui_theme.gd",
        DOGFOOD / "src" / "player.gd",
        DOGFOOD / "src" / "warden.gd",
        DOGFOOD / "src" / "world_builder.gd",
        DOGFOOD / "src" / "hud.gd",
        DOGFOOD / "src" / "game_session.gd",
        EVIDENCE / "assumptions.md",
    )
    for path in required:
        if not path.is_file():
            errors.append(f"missing {rel(path)}")
    src_blob = ""
    for gd in (DOGFOOD / "src").rglob("*.gd"):
        src_blob += gd.read_text(encoding="utf-8") + "\n"
    for tres in (DOGFOOD / "assets" / "anim").glob("*.tres"):
        src_blob += tres.read_text(encoding="utf-8") + "\n"
    if "AnimatedSprite2D" not in src_blob:
        errors.append("player/warden must wire AnimatedSprite2D")
    if "PROCESS_MODE_ALWAYS" not in (DOGFOOD / "src" / "app.gd").read_text(encoding="utf-8"):
        errors.append("App pause listener must use PROCESS_MODE_ALWAYS")
    if "return relic_reached" not in (DOGFOOD / "src" / "game_state.gd").read_text(encoding="utf-8"):
        errors.append("win flag must stay relic_reached")
    if "zoom_for_size" not in (DOGFOOD / "src" / "vault_map.gd").read_text(encoding="utf-8"):
        errors.append("camera must expose zoom_for_size for designed views")
    if "refit_view" not in (DOGFOOD / "src" / "game_session.gd").read_text(encoding="utf-8"):
        errors.append("session must refit_view on resize")
    if "layout_on_playfield" not in (DOGFOOD / "src" / "hud.gd").read_text(encoding="utf-8"):
        errors.append("HUD must sit on the playfield, not letterbox void")
    if PATH_LABEL not in RUN_ALL.read_text(encoding="utf-8"):
        errors.append("run_all.gd must keep start→key→door→relic→win")
    if re.search(r"relic_reached\s*=\s*true", RUN_ALL.read_text(encoding="utf-8")):
        errors.append("run_all.gd must not poke relic_reached = true")
    for path in SHIP_PATHS:
        if path not in src_blob:
            errors.append(f"unused ship asset not referenced in src: {path}")
    for gd in (DOGFOOD / "src").rglob("*"):
        if not gd.is_file():
            continue
        if gd.suffix.lower() not in {".gd", ".tres", ".tscn", ".json"}:
            continue
        text = gd.read_text(encoding="utf-8")
        if "PLACEHOLDER" in text:
            errors.append(f"src contains PLACEHOLDER: {rel(gd)}")
    for path in DOGFOOD.rglob("*"):
        if path.is_file() and "PLACEHOLDER" in path.name.upper():
            errors.append(f"PLACEHOLDER asset not allowed: {rel(path)}")
    if (DOGFOOD / "addons").exists():
        errors.append("dogfood must not vendor addons")
    notice = (DOGFOOD / "NOTICE.md").read_text(encoding="utf-8") if (DOGFOOD / "NOTICE.md").is_file() else ""
    if "invisible colliders" not in notice.lower() and "ColorRect" not in notice:
        errors.append("NOTICE.md must say ColorRects stay as invisible colliders")
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
    match = re.search(r"HH_R8WP4\s+VISUAL=(\w+)\s+INPUT=(\w+)\s+REVIEW=(\w+)", blob)
    if match:
        found["VISUAL"] = match.group(1)
        found["INPUT"] = match.group(2)
        found["REVIEW"] = match.group(3)
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


def _unfilter_png(raw: bytes, width: int, height: int) -> bytes:
    stride = width * 4
    out = bytearray()
    prev = bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        filt = raw[start]
        row = bytearray(raw[start + 1 : start + 1 + stride])
        if filt == 1:
            for i in range(stride):
                left = row[i - 4] if i >= 4 else 0
                row[i] = (row[i] + left) & 255
        elif filt == 2:
            for i in range(stride):
                row[i] = (row[i] + prev[i]) & 255
        elif filt == 3:
            for i in range(stride):
                left = row[i - 4] if i >= 4 else 0
                row[i] = (row[i] + ((left + prev[i]) // 2)) & 255
        elif filt == 4:
            for i in range(stride):
                left = row[i - 4] if i >= 4 else 0
                up_left = prev[i - 4] if i >= 4 else 0
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
    idat = bytearray()
    while pos + 8 <= len(data):
        length = int.from_bytes(data[pos : pos + 4], "big")
        tag = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if tag == b"IHDR":
            width = int.from_bytes(chunk[0:4], "big")
            height = int.from_bytes(chunk[4:8], "big")
        elif tag == b"IDAT":
            idat.extend(chunk)
        elif tag == b"IEND":
            break
    raw = zlib.decompress(bytes(idat))
    return width, height, _unfilter_png(raw, width, height)


def png_unique_colors(path: Path) -> tuple[int, int, int]:
    width, height, rgba = _png_rgba(path)
    unique: set[tuple[int, int, int]] = set()
    stride = width * 4
    for y in range(height):
        row = rgba[y * stride : (y + 1) * stride]
        for x in range(0, width, 2):
            i = x * 4
            if row[i + 3] < 40:
                continue
            unique.add((row[i], row[i + 1], row[i + 2]))
    return width, height, len(unique)


def png_review_stats(path: Path) -> dict[str, float | int]:
    width, height, rgba = _png_rgba(path)
    stride = width * 4
    unique: set[tuple[int, int, int]] = set()
    total = 0
    clear_n = 0
    hud_n = 0
    hud_clear = 0
    y1 = min(88, height - 1)
    x1 = min(220, width - 1)
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
            if 8 <= y <= y1 and 8 <= x <= x1:
                hud_n += 1
                if abs(r - 76) <= 3 and abs(g - 76) <= 3 and abs(b - 76) <= 3:
                    hud_clear += 1
    cw = min(48, width)
    ch = min(48, height)
    x0 = (width - cw) // 2
    y0 = (height - ch) // 2
    sum_l = 0.0
    sum2 = 0.0
    crop_n = 0
    fp: list[float] = []
    grid = 8
    for gy in range(grid):
        for gx in range(grid):
            x1 = x0 + gx * cw // grid
            x2 = x0 + (gx + 1) * cw // grid
            y1 = y0 + gy * ch // grid
            y2 = y0 + (gy + 1) * ch // grid
            cell = 0.0
            n = 0
            for y in range(y1, max(y2, y1 + 1)):
                for x in range(x1, max(x2, x1 + 1)):
                    i = y * stride + x * 4
                    cell += (rgba[i] + rgba[i + 1] + rgba[i + 2]) / 3.0
                    n += 1
            fp.append(cell / n if n else 0.0)
    for y in range(ch):
        for x in range(cw):
            i = (y0 + y) * stride + (x0 + x) * 4
            lum = (rgba[i] + rgba[i + 1] + rgba[i + 2]) / 3.0
            sum_l += lum
            sum2 += lum * lum
            crop_n += 1
    mean = (sum_l / crop_n) if crop_n else 0.0
    var = (sum2 / crop_n - mean * mean) if crop_n else 0.0
    std = var ** 0.5 if var > 0.0 else 0.0
    return {
        "width": width,
        "height": height,
        "unique": len(unique),
        "engine_clear_share": (clear_n / total) if total else 1.0,
        "hud_clear_share": (hud_clear / hud_n) if hud_n else 1.0,
        "center_mean": mean,
        "center_std": std,
        "fp": fp,
    }


def _crops_near(a: dict, b: dict) -> bool:
    fa = a.get("fp") or []
    fb = b.get("fp") or []
    if len(fa) != len(fb) or not fa:
        return (
            abs(float(a["center_mean"]) - float(b["center_mean"])) < 4.0
            and abs(float(a["center_std"]) - float(b["center_std"])) < 3.0
        )
    acc = 0.0
    for i, left in enumerate(fa):
        d = float(left) - float(fb[i])
        acc += d * d
    rms = (acc / len(fa)) ** 0.5
    return rms < 5.0


def copy_shots(blob: str) -> list[str]:
    errors: list[str] = []
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    needed = {"1280x720": False, "1920x1080": False, "854x480": False}
    abs_by_size: dict[str, str] = {}
    crop_rows: list[dict[str, float | int]] = []
    for match in re.finditer(r"HH_R8WP4_SHOT_ABS\s+(\d+x\d+)\s+(.+)", blob):
        abs_by_size[match.group(1)] = match.group(2).strip()
    appdata = os.environ.get("APPDATA", "")
    userdata = Path(appdata) / "Godot" / "app_userdata" / "Kho Bi An" if appdata else None
    for match in re.finditer(
        r"HH_R8WP4_SHOT\s+(\d+x\d+)\s+(user://\S+)\s+([0-9a-f]{64})",
        blob,
    ):
        size, user_path, digest = match.groups()
        name = user_path.rsplit("/", 1)[-1]
        candidates = []
        if size in abs_by_size:
            candidates.append(Path(abs_by_size[size]))
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
        unique = int(stats["unique"])
        if unique < 6:
            errors.append(f"shot {dest.name} is too flat unique={unique}")
        clear_share = float(stats["engine_clear_share"])
        if clear_share >= 0.45:
            errors.append(
                f"REVIEW {dest.name} engine-clear 76,76,76 share={clear_share:.3f}"
            )
        if float(stats["hud_clear_share"]) >= 0.35:
            errors.append(f"REVIEW {dest.name} HUD sits on letterbox void")
        if size in needed and f"{int(stats['width'])}x{int(stats['height'])}" == size:
            needed[size] = True
            crop_rows.append(stats)
    for size, found in needed.items():
        if not found:
            errors.append(f"missing reviewed baseline {size}")
    if len(crop_rows) >= 3:
        near_pairs = 0
        for i in range(3):
            if _crops_near(crop_rows[i], crop_rows[(i + 1) % 3]):
                near_pairs += 1
        if near_pairs >= 3:
            errors.append("REVIEW three layouts are the same center crop")
    return errors


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


def write_hashes() -> str:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    lines = [
        f"RUN_ID {RUN_ID}",
        f"PIN {PINNED_VERSION}",
        f"PATH {PATH_LABEL}",
    ]
    targets = [
        ("PLAYER", DOGFOOD / "src" / "player.gd"),
        ("WARDEN", DOGFOOD / "src" / "warden.gd"),
        ("WORLD", DOGFOOD / "src" / "world_builder.gd"),
        ("SESSION", DOGFOOD / "src" / "game_session.gd"),
        ("HUD", DOGFOOD / "src" / "hud.gd"),
        ("VISUALS", DOGFOOD / "src" / "visuals.gd"),
        ("SFX", DOGFOOD / "src" / "sfx_bank.gd"),
        ("THEME", DOGFOOD / "src" / "ui" / "ui_theme.gd"),
        ("PAUSE", DOGFOOD / "src" / "ui" / "pause_screen.gd"),
        ("TITLE", DOGFOOD / "src" / "ui" / "title_screen.gd"),
        ("RUN_POLISH", RUN_POLISH),
        ("HARNESS", Path(__file__)),
        ("NOTICE", DOGFOOD / "NOTICE.md"),
    ]
    for name, path in targets:
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{name} {digest}")
    for shot in sorted(EVIDENCE.glob("kho_bi_an_r8wp4_*.png")):
        digest = hashlib.sha256(shot.read_bytes()).hexdigest()
        lines.append(f"SHOT {shot.name} {digest}")
    text = "\n".join(lines) + "\n"
    (EVIDENCE / "hashes.txt").write_text(text, encoding="utf-8")
    return text


def main() -> int:
    errors: list[str] = []
    errors.extend(src_scan_errors())
    if not PLAN.is_file():
        errors.append(f"missing {rel(PLAN)}")
        emit("FAIL: R8-WP4 Kho Bi An polish")
        for item in errors:
            emit(f"  - {item}")
        return 1
    plan_text = PLAN.read_text(encoding="utf-8")
    errors.extend(plan_errors(plan_text))
    errors.extend(tree_errors())

    labels = {name: "unproven" for name in LABELS}
    if errors:
        banner = "; ".join(f"{k}={labels[k]}" for k in LABELS)
        emit(f"FAIL: R8-WP4 Kho Bi An polish; {banner}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    exe, pin_reason = find_pinned_godot()
    if exe is None:
        errors.append(f"Godot pin: {pin_reason}")
        emit("FAIL: R8-WP4 Kho Bi An polish; VISUAL=unproven; INPUT=unproven; REVIEW=unproven")
        for item in errors:
            emit(f"  - {item}")
        return 1

    kill_kho_path_holders()
    if kho_path_busy():
        errors.append("leftover Godot still holds kho-bi-an --path after kill")
        emit("FAIL: R8-WP4 Kho Bi An polish; VISUAL=unproven; INPUT=unproven; REVIEW=unproven")
        for item in errors:
            emit(f"  - {item}")
        return 1

    version = godot_version(exe)
    if "4.7." + "2" in version or "4.8" in version:
        errors.append(f"refused Godot --version {version!r}")
    elif version != PINNED_VERSION:
        errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")
    if errors:
        emit("FAIL: R8-WP4 Kho Bi An polish; VISUAL=unproven; INPUT=unproven; REVIEW=unproven")
        for item in errors:
            emit(f"  - {item}")
        return 1

    imported_ok, import_blob, import_rc = import_project(exe)
    if not imported_ok:
        errors.append(f"import failed exit={import_rc}\n{import_blob[-4000:]}")
        emit("FAIL: R8-WP4 Kho Bi An polish; VISUAL=unproven; INPUT=unproven; REVIEW=unproven")
        for item in errors:
            emit(f"  - {item}")
        return 1

    kill_kho_path_holders()
    polish_args = ["--path", str(DOGFOOD), "--script", "res://tests/run_polish.gd"]
    official_cmd = f"godot --headless --path {rel(DOGFOOD)} --script res://tests/run_polish.gd"
    if os.name == "nt":
        polish_args = [
            "--windowed",
            "--resolution",
            "1280x720",
            "--path",
            str(DOGFOOD),
            "--script",
            "res://tests/run_polish.gd",
        ]
        official_cmd = (
            f"godot --windowed --path {rel(DOGFOOD)} --script res://tests/run_polish.gd"
        )
    ran = run_godot(exe, polish_args, 240.0)
    blob = (ran.stdout or "") + (ran.stderr or "")
    labels = parse_labels(blob)
    if ran.returncode != 0:
        errors.append(f"run_polish.gd exit={ran.returncode}")
    if re.search(r"SCRIPT ERROR|Parse Error", blob):
        errors.append("Godot reported a script/parse error")
    if "HH_ASSERT_FAIL" in blob:
        errors.append("run_polish.gd asserted a polish failure")
    if "software-composite" in blob:
        errors.append("VISUAL must not be a software blit")
        labels["VISUAL"] = "unproven"
        labels["REVIEW"] = "unproven"
    if "HH_R8WP4_DISPLAY headless" in blob:
        errors.append("VISUAL refuse dummy-renderer / headless capture")
        labels["VISUAL"] = "unproven"
        labels["REVIEW"] = "unproven"
    if "parse_input_event" not in blob and "HH_R8WP4_INPUT_INJECT" not in blob:
        errors.append("INPUT must inject parse_input_event")
        labels["INPUT"] = "unproven"
    for key in LABELS:
        if labels[key] != "proven":
            errors.append(f"{key} not proven")
    if "PASS: R8-WP4 polish art/UI/feedback" not in blob:
        errors.append("run_polish.gd missing PASS banner")

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
        errors.append("graybox LOOP not proven after polish")

    banner = "; ".join(f"{k}={labels[k]}" for k in LABELS)
    if errors:
        emit(f"FAIL: R8-WP4 Kho Bi An polish; {banner}")
        for item in errors:
            emit(f"  - {item}")
        emit("---- godot run_polish ----")
        emit(blob[-8000:])
        emit("---- godot run_all ----")
        emit(gray_blob[-3000:])
        return 1
    shot_errors = copy_shots(blob)
    if shot_errors:
        emit(f"FAIL: R8-WP4 Kho Bi An polish; {banner}")
        for item in shot_errors:
            emit(f"  - {item}")
        emit("---- godot run_polish ----")
        emit(blob[-8000:])
        return 1
    hashes = write_hashes()
    emit(f"PASS: R8-WP4 Kho Bi An polish; {banner}")
    emit(f"  path={PATH_LABEL} pin={PINNED} run_id={RUN_ID} sidecar=none")
    emit(f"  official={official_cmd}")
    emit(f"  hashes={rel(EVIDENCE / 'hashes.txt')}")
    emit(hashes.rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
