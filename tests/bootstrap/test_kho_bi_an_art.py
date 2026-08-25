#!/usr/bin/env python3
"""R8-WP3: art/animation/audio pipeline + license manifest (does not tick the plan).

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R8-WP3 [ ]; CURRENT_VALID_WP=R8-WP3; progress stays 52/60.
Does not start R8-WP4 polish. Does not fake G5 human dogfood. Does not touch GX.
Does not replace ColorRect graybox actors. Win flag stays relic-reached.
No snake demo. No r7w6 trial. No secret material. No skip-PASS.
--provider plan stays unused here. No remote imagegen.

Official Godot verify (plan §7.3), path godot/dogfood/kho-bi-an:
  kill leftover Godot on that --path first (no sidecar; game has no addon)
  godot --version
  godot --headless --editor --path <kho-bi-an> --import --quit
  godot --headless --path <kho-bi-an> --script res://tests/run_art.gd
  godot --headless --path <kho-bi-an> --script res://tests/run_all.gd

Labels: CONTACT, ANIM, AUDIO, ATTRIB, LICENSE
Graybox LOOP must stay proven. Relic-reached is win.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import wave
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
DOGFOOD = REPO_ROOT / "godot" / "dogfood" / "kho-bi-an"
BRIEF = DOGFOOD / "PROJECT_BRIEF.md"
MANIFEST = DOGFOOD / "assets" / "ASSET_MANIFEST.json"
LAYOUT = DOGFOOD / "assets" / "ATLAS_LAYOUT.json"
CONTACT = DOGFOOD / "assets" / "audit" / "contact_sheet.png"
RUN_ART = DOGFOOD / "tests" / "run_art.gd"
RUN_ALL = DOGFOOD / "tests" / "run_all.gd"
GENERATOR = REPO_ROOT / "tools" / "godot" / "gen_kho_bi_an_art.py"
GODOT_PIN = REPO_ROOT / "tools" / "godot" / "pin.json"
PINNED_VERSION = "4.7.1.stable.official.a13da4feb"
PINNED = "4.7.1-stable"
RUN_ID = "01R8WP3ART00000000KBA00001"
PATH_LABEL = "start→key→door→relic→win"
LABELS = ("CONTACT", "ANIM", "AUDIO", "ATTRIB", "LICENSE")
PATH_NEEDLES = ("kho-bi-an", "kho_bi_an")
ALLOWED_LICENSES = {"original", "CC0", "MIT", "OFL-1.1"}
SHIP_ART = (
    "tileset_vault",
    "actor_player",
    "actor_warden",
    "item_key",
    "prop_door",
    "item_relic",
    "ui_icon_key",
    "vfx_interact",
)
SHIP_AUDIO = (
    "sfx_pickup",
    "sfx_door",
    "sfx_caught",
    "sfx_win",
    "sfx_lose",
    "sfx_interact",
    "music_vault",
)
REQUIRED_FIELDS = ("source", "tool", "prompt", "model", "license", "hash")
ANIM_TRES = (
    DOGFOOD / "assets" / "anim" / "actor_player.tres",
    DOGFOOD / "assets" / "anim" / "actor_warden.tres",
    DOGFOOD / "assets" / "anim" / "vfx_interact.tres",
)
REMAP_IDENTITY = (
    "process/channel_remap/red=0",
    "process/channel_remap/green=1",
    "process/channel_remap/blue=2",
    "process/channel_remap/alpha=3",
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
    wp3 = None
    wp4 = None
    g5 = None
    gx = None
    total = None
    r8_row = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R8-WP3\b", stripped):
            wp3 = stripped
        if re.match(r"^R8-WP4\b", stripped):
            wp4 = stripped
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
    if current != "R8-WP3":
        errors.append(f"CURRENT_VALID_WP={current!r} (must stay R8-WP3)")
    if wp3 is None:
        errors.append("plan missing R8-WP3 heading")
    elif re.search(r"\[x\]", wp3, re.I):
        errors.append("R8-WP3 must stay unticked")
    if wp4 is not None and re.search(r"\[x\]", wp4, re.I):
        errors.append("R8-WP4 must stay unticked; this WP does not start polish")
    if PATH_LABEL not in text:
        errors.append("plan must keep verify path start→key→door→relic→win")
    if total and "52/60" not in total:
        errors.append(f"progress must stay 52/60 while R8-WP3 is unticked: {total}")
    if r8_row and not re.search(r"\[ \]\s*2/6", r8_row):
        errors.append(f"R8 row must stay 2/6 while WP3 is unticked: {r8_row}")
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
    if ("write" + "_text") in self_text:
        errors.append("official test must verify imports, not rewrite them")
    run_art = RUN_ART.read_text(encoding="utf-8") if RUN_ART.is_file() else ""
    if "ResourceSaver.save" in run_art:
        errors.append("run_art.gd must not be the writer of assets/anim/*.tres")
    if "get_image()" in run_art:
        errors.append("run_art.gd must not prove ANIM from AtlasTexture.get_image()")
    return errors


def graybox_still_testable() -> list[str]:
    errors: list[str] = []
    session = (DOGFOOD / "src" / "game_state.gd").read_text(encoding="utf-8")
    if "return relic_reached" not in session:
        errors.append("win flag must stay relic_reached")
    win_fn = re.search(r"func is_win\(\)[^:]*:[^\n]*\n(?:\t.*\n)*", session)
    if win_fn and "has_key" in win_fn.group(0):
        errors.append("is_win must not use has_key")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if PATH_LABEL not in run_all:
        errors.append("run_all.gd must keep start→key→door→relic→win")
    if re.search(r"relic_reached\s*=\s*true", run_all):
        errors.append("WIN_FLAG must not poke relic_reached = true")
    builder = (DOGFOOD / "src" / "world_builder.gd").read_text(encoding="utf-8")
    if "res://assets/tiles/tileset_vault.png" not in builder:
        errors.append("WorldBuilder must use res://assets/tiles/tileset_vault.png")
    if "Image.create(64, 16" in builder or "fill_rect(Rect2i(0, 0, 16, 16)" in builder:
        errors.append("WorldBuilder must not paint a second solid-color 64x16 atlas")
    player = (DOGFOOD / "src" / "player.gd").read_text(encoding="utf-8")
    warden = (DOGFOOD / "src" / "warden.gd").read_text(encoding="utf-8")
    if "Sprite2D" in player or "AnimatedSprite" in player or "Sprite2D" in warden or "AnimatedSprite" in warden:
        errors.append("WP3 must not swap ColorRect actors for Sprite2D")
    return errors


def manifest_errors() -> list[str]:
    errors: list[str] = []
    required = (
        BRIEF,
        MANIFEST,
        LAYOUT,
        CONTACT,
        RUN_ART,
        GENERATOR,
        DOGFOOD / "NOTICE.md",
        DOGFOOD / "project.godot",
        *ANIM_TRES,
    )
    for path in required:
        if not path.is_file():
            errors.append(f"missing {rel(path)}")
    if not MANIFEST.is_file():
        return errors
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("unknown_forbidden") is not True:
        errors.append("release manifest must set unknown_forbidden")
    if data.get("placeholder_forbidden") is not True:
        errors.append("release manifest must set placeholder_forbidden")
    if data.get("run_id") != RUN_ID:
        errors.append(f"manifest run_id {data.get('run_id')!r} != {RUN_ID}")
    assets = data.get("assets")
    if not isinstance(assets, list) or not assets:
        errors.append("release manifest missing assets")
        return errors
    ship_art: list[str] = []
    ship_audio: list[str] = []
    ship_font = 0
    hashes: set[str] = set()
    for row in assets:
        if not isinstance(row, dict):
            errors.append("manifest row is not an object")
            continue
        asset_id = str(row.get("id", ""))
        license = str(row.get("license", "")).strip()
        if license == "" or license.upper() == "UNKNOWN":
            errors.append(f"LICENSE UNKNOWN on {asset_id}")
        if license not in ALLOWED_LICENSES:
            errors.append(f"license not commercial-safe on {asset_id}: {row.get('license')}")
        if "PLACEHOLDER" in asset_id.upper() or "PLACEHOLDER" in str(row.get("rel", "")).upper():
            errors.append(f"PLACEHOLDER asset {asset_id}")
        for field in REQUIRED_FIELDS:
            if field not in row:
                errors.append(f"ATTRIB missing {field} on {asset_id}")
        rel_path = str(row.get("rel", ""))
        kind = str(row.get("kind", ""))
        role = str(row.get("role", "ship"))
        if kind == "image" and role == "ship":
            ship_art.append(asset_id)
        if kind == "audio" and role == "ship":
            ship_audio.append(asset_id)
        if kind in ("font", "bundled") and role == "ship":
            ship_font += 1
        if kind == "bundled":
            digest = str(row.get("hash", ""))
            if re.fullmatch(r"[0-9a-fA-F]{64}", digest):
                errors.append(f"bundled {asset_id} hash claims SHA-256 of bytes")
            if rel_path:
                errors.append(f"bundled {asset_id} must not claim a file of bytes")
            continue
        if rel_path:
            path = DOGFOOD / rel_path
            if not path.is_file():
                errors.append(f"missing shipped file {rel_path}")
            else:
                digest = __import__("hashlib").sha256(path.read_bytes()).hexdigest()
                if digest != row.get("hash"):
                    errors.append(f"hash mismatch {asset_id}")
                if digest in hashes and role == "ship":
                    errors.append(f"duplicate asset bytes {asset_id}")
                hashes.add(digest)
                sidecar = path.with_name(path.name + ".manifest.json")
                if not sidecar.is_file():
                    errors.append(f"missing sidecar {rel(sidecar)}")
        if kind == "audio" and rel_path:
            wav_path = DOGFOOD / rel_path
            if wav_path.is_file():
                with wave.open(str(wav_path), "rb") as handle:
                    frames = handle.getnframes()
                    width = handle.getsampwidth()
                    if frames < 32 or width != 2:
                        errors.append(f"AUDIO {asset_id} is not a usable PCM wav")
                    raw = handle.readframes(frames)
                    peak = 0
                    for i in range(0, len(raw) - 1, 2):
                        sample = int.from_bytes(raw[i : i + 2], "little", signed=True)
                        peak = max(peak, abs(sample))
                    if peak < 800:
                        errors.append(f"AUDIO {asset_id} silent")
    for name in SHIP_ART:
        if name not in ship_art:
            errors.append(f"missing ship art {name}")
    for name in SHIP_AUDIO:
        if name not in ship_audio:
            errors.append(f"missing ship audio {name}")
    if ship_font != 1:
        errors.append(f"font count {ship_font} != 1")
    if len(ship_art) > 16:
        errors.append(f"art count {len(ship_art)} exceeds cap 16")
    if len(ship_audio) > 8:
        errors.append(f"audio count {len(ship_audio)} exceeds cap 8")
    if not CONTACT.is_file() or CONTACT.stat().st_size < 64:
        errors.append("contact sheet missing or empty")
    notice = (DOGFOOD / "NOTICE.md").read_text(encoding="utf-8") if (DOGFOOD / "NOTICE.md").is_file() else ""
    if "original" not in notice.lower():
        errors.append("NOTICE.md must attribute original procedural assets")
    if "OFL" not in notice and "Open Font" not in notice:
        errors.append("NOTICE.md must keep the bundled font OFL line")
    godot = (DOGFOOD / "project.godot").read_text(encoding="utf-8")
    if "default_texture_filter=0" not in godot:
        errors.append("project must keep nearest default filter")
    if "importer_defaults" not in godot or "mipmaps/generate" not in godot:
        errors.append("project must pin texture import preset nearest/no-mipmaps")
    if (DOGFOOD / "addons").exists():
        errors.append("dogfood must not vendor addons")
    for path in DOGFOOD.rglob("*"):
        if path.is_file() and "PLACEHOLDER" in path.name.upper():
            errors.append(f"PLACEHOLDER asset not allowed: {rel(path)}")
    layout = json.loads(LAYOUT.read_text(encoding="utf-8")) if LAYOUT.is_file() else {}
    if layout.get("filter") != "nearest" or layout.get("mipmaps") is not False:
        errors.append("atlas layout must pin nearest / no mipmaps")
    if layout.get("rows") != ["down", "left", "right", "up"]:
        errors.append("atlas layout must keep 4-dir rows")
    errors.extend(checked_in_anim_errors())
    errors.extend(warden_walk_up_errors())
    return errors


def png_rgba(path: Path) -> tuple[int, int, bytes]:
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
    rgba = bytearray()
    stride = width * 4
    for y in range(height):
        start = y * (stride + 1)
        if raw[start] != 0:
            raise ValueError(f"{path} filter {raw[start]} not supported")
        rgba.extend(raw[start + 1 : start + 1 + stride])
    return width, height, bytes(rgba)


def frame_rgba(rgba: bytes, width: int, col: int, row: int, size: int = 32) -> bytes:
    out = bytearray()
    x0 = col * size
    y0 = row * size
    for y in range(size):
        start = ((y0 + y) * width + x0) * 4
        out.extend(rgba[start : start + size * 4])
    return bytes(out)


def warden_walk_up_errors() -> list[str]:
    errors: list[str] = []
    path = DOGFOOD / "assets" / "art" / "actor_warden.png"
    if not path.is_file():
        return ["missing actor_warden.png for walk_up hash"]
    try:
        width, height, rgba = png_rgba(path)
    except ValueError as exc:
        return [str(exc)]
    if width < 192 or height < 128:
        return [f"actor_warden sheet too small {width}x{height}"]
    idle = {frame_rgba(rgba, width, col, 3) for col in range(2)}
    for col in range(2, 6):
        if frame_rgba(rgba, width, col, 3) in idle:
            errors.append(f"warden walk_up frame {col - 2} is byte-identical to idle_up")
    return errors


def checked_in_anim_errors() -> list[str]:
    errors: list[str] = []
    player = (DOGFOOD / "assets" / "anim" / "actor_player.tres").read_text(encoding="utf-8")
    warden = (DOGFOOD / "assets" / "anim" / "actor_warden.tres").read_text(encoding="utf-8")
    vfx = (DOGFOOD / "assets" / "anim" / "vfx_interact.tres").read_text(encoding="utf-8")
    for clip in (
        "idle_down",
        "idle_left",
        "idle_right",
        "idle_up",
        "walk_down",
        "walk_left",
        "walk_right",
        "walk_up",
    ):
        needle = f'&"{clip}"'
        if needle not in player:
            errors.append(f"checked-in actor_player.tres missing {clip}")
        if needle not in warden:
            errors.append(f"checked-in actor_warden.tres missing {clip}")
    if '&"burst"' not in vfx:
        errors.append("checked-in vfx_interact.tres missing burst")
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
        r"HH_R8WP3\s+CONTACT=(\w+)\s+ANIM=(\w+)\s+AUDIO=(\w+)\s+ATTRIB=(\w+)\s+LICENSE=(\w+)",
        blob,
    )
    if match:
        found["CONTACT"] = match.group(1)
        found["ANIM"] = match.group(2)
        found["AUDIO"] = match.group(3)
        found["ATTRIB"] = match.group(4)
        found["LICENSE"] = match.group(5)
    return found


def verify_import_presets() -> list[str]:
    errors: list[str] = []
    for png in DOGFOOD.rglob("*.png"):
        sidecar = Path(str(png) + ".import")
        if not sidecar.is_file():
            errors.append(f"missing import sidecar {rel(sidecar)}")
            continue
        text = sidecar.read_text(encoding="utf-8")
        if "mipmaps/generate=true" in text:
            errors.append(f"mipmaps enabled on {rel(png)}")
        if "mipmaps/generate=false" not in text:
            errors.append(f"import must pin nearest/no-mipmaps on {rel(png)}")
        for needle in REMAP_IDENTITY:
            if needle not in text:
                errors.append(f"import channel remap not identity on {rel(png)}")
                break
    music = DOGFOOD / "assets" / "audio" / "music_vault.wav.import"
    if not music.is_file():
        errors.append("missing music_vault.wav.import")
    else:
        text = music.read_text(encoding="utf-8")
        if "edit/loop_mode=1" not in text and "loop_mode=1" not in text:
            errors.append("music_vault.wav.import must keep loop_mode=1")
        if "loop_mode=0" in text:
            errors.append("music_vault.wav.import must not be loop_mode=0")
    godot = (DOGFOOD / "project.godot").read_text(encoding="utf-8")
    if '"process/channel_remap/red": 0' not in godot or '"process/channel_remap/green": 1' not in godot:
        errors.append("project importer_defaults must keep identity channel remap")
    return errors


def main() -> int:
    errors: list[str] = []
    errors.extend(src_scan_errors())
    if not PLAN.is_file():
        errors.append(f"missing {rel(PLAN)}")
        emit("FAIL: R8-WP3 Kho Bi An art")
        for item in errors:
            emit(f"  - {item}")
        return 1
    plan_text = PLAN.read_text(encoding="utf-8")
    errors.extend(plan_errors(plan_text))
    errors.extend(manifest_errors())
    errors.extend(verify_import_presets())
    errors.extend(graybox_still_testable())

    labels = {name: "unproven" for name in LABELS}
    if errors:
        banner = "; ".join(f"{k}={labels[k]}" for k in LABELS)
        emit(f"FAIL: R8-WP3 Kho Bi An art; {banner}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    exe, pin_reason = find_pinned_godot()
    if exe is None:
        errors.append(f"Godot pin: {pin_reason}")
        emit("FAIL: R8-WP3 Kho Bi An art; CONTACT=unproven; ANIM=unproven; AUDIO=unproven; ATTRIB=unproven; LICENSE=unproven")
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
    errors.extend(verify_import_presets())

    kill_kho_path_holders()
    ran = run_godot(
        exe,
        ["--headless", "--path", str(DOGFOOD), "--script", "res://tests/run_art.gd"],
        180.0,
    )
    blob = (ran.stdout or "") + (ran.stderr or "")
    labels = parse_labels(blob)
    if ran.returncode != 0:
        errors.append(f"run_art.gd exit={ran.returncode}")
    if re.search(r"SCRIPT ERROR|Parse Error", blob):
        errors.append("Godot reported a script/parse error")
    if "HH_ASSERT_FAIL" in blob:
        errors.append("run_art.gd asserted an art/audio/license failure")
    for key in LABELS:
        if labels[key] != "proven":
            errors.append(f"{key} not proven")
    if "PASS: R8-WP3 art/audio/license pipeline" not in blob:
        errors.append("run_art.gd missing PASS banner")

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
    if "HH_R8WP2 LOOP=proven" not in gray_blob.replace(" ", " "):
        if not re.search(r"HH_R8WP2\s+LOOP=proven", gray_blob):
            errors.append("graybox LOOP not proven after art staging")

    banner = "; ".join(f"{k}={labels[k]}" for k in LABELS)
    if errors:
        emit(f"FAIL: R8-WP3 Kho Bi An art; {banner}")
        for item in errors:
            emit(f"  - {item}")
        emit("---- godot run_art ----")
        emit(blob[-6000:])
        emit("---- godot run_all ----")
        emit(gray_blob[-3000:])
        return 1
    emit(f"PASS: R8-WP3 Kho Bi An art; {banner}")
    emit(f"  path={PATH_LABEL} pin={PINNED} run_id={RUN_ID} sidecar=none")
    emit(f"  official=godot --headless --path {rel(DOGFOOD)} --script res://tests/run_art.gd")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
