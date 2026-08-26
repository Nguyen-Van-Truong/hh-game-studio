#!/usr/bin/env python3
"""R8-WP6: build Kho Bi An from brief + pinned asset bytes.

Does not copy godot/dogfood/kho-bi-an sources. Does not tick the plan.
Does not fake G5. Does not poke relic_reached. Stdlib only.
--provider plan stays unused. No invented API key.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PIN_ROOT = REPO_ROOT / "godot" / "dogfood" / "kho-bi-an"
BRIEF_DEFAULT = PIN_ROOT / "PROJECT_BRIEF.md"
MANIFEST_DEFAULT = PIN_ROOT / "assets" / "ASSET_MANIFEST.json"
SOURCES = Path(__file__).resolve().parent / "kho_bi_an_fresh_sources.py"
PINNED_TEMPLATE_VERSION = "4.7.1.stable"
SKIP_DIR_NAMES = {".godot", "addons", "__pycache__"}
HASH_SKIP_NAMES = {"recreate_manifest.json"}
WINDOWS_TEMPLATE_NAMES = (
    "version.txt",
    "windows_release_x86_64.exe",
    "windows_release_x86_64_console.exe",
    "windows_debug_x86_64.exe",
    "windows_debug_x86_64_console.exe",
)
PATH_LABEL = "start→key→door→relic→win"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def load_sources():
    spec = importlib.util.spec_from_file_location("kho_bi_an_fresh_sources", SOURCES)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load kho_bi_an_fresh_sources.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_brief(text: str) -> dict[str, object]:
    errors: list[str] = []
    lowered = text.lower()
    if "relic-reached is win" not in lowered and "relic_reached" not in lowered:
        errors.append("brief missing win=relic-reached")
    if "door-open is not win" not in lowered:
        errors.append("brief missing door-open is not win")
    if "key pickup is not win" not in lowered:
        errors.append("brief missing key pickup is not win")
    path_ok = (
        "key pickup" in lowered
        and "door-open" in lowered
        and "relic-reached" in lowered
        and "relic-after-door" in lowered
    )
    if not path_ok:
        errors.append("brief missing path start→key→door→relic")
    view = re.search(r"base design resolution:\*\*\s*(\d+)x(\d+)", text, re.I)
    if view is None:
        errors.append("brief missing base design resolution")
        view_w, view_h = 0, 0
    else:
        view_w, view_h = int(view.group(1)), int(view.group(2))
        if (view_w, view_h) != (1280, 720):
            errors.append(f"brief resolution {view_w}x{view_h} contradicts 1280x720")
    stretch = re.search(r"stretch mode:\*\*\s*(\S+)", text, re.I)
    aspect = re.search(r"aspect:\*\*\s*(\S+)", text, re.I)
    stretch_mode = stretch.group(1).strip() if stretch else ""
    stretch_aspect = aspect.group(1).strip() if aspect else ""
    if stretch_mode != "canvas_items":
        errors.append(f"brief stretch mode {stretch_mode!r} contradicts canvas_items")
    if stretch_aspect != "keep":
        errors.append(f"brief aspect {stretch_aspect!r} contradicts keep")
    if "wasd" not in lowered or "arrows" not in lowered:
        errors.append("brief missing WASD/arrows move")
    if "escape pause" not in lowered:
        errors.append("brief missing Escape pause")
    if "e or enter interact" not in lowered:
        errors.append("brief missing E/Enter interact")
    return {
        "errors": errors,
        "win": "relic_reached",
        "path": PATH_LABEL,
        "view_w": view_w,
        "view_h": view_h,
        "stretch_mode": stretch_mode,
        "stretch_aspect": stretch_aspect,
    }


def iter_product_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIR_NAMES]
        current = Path(dirpath)
        for name in filenames:
            files.append(current / name)
    files.sort()
    return files


def hash_tree(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in iter_product_files(root):
        if path.name in HASH_SKIP_NAMES:
            continue
        rel = path.relative_to(root).as_posix()
        hashes[rel] = sha256_file(path)
    return hashes


def pin_rows(manifest_path: Path) -> list[dict]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise RuntimeError("asset manifest missing assets list")
    rows: list[dict] = []
    for row in assets:
        if not isinstance(row, dict):
            continue
        if str(row.get("role", "")) != "ship":
            continue
        if str(row.get("kind", "")) == "bundled":
            continue
        rel = str(row.get("rel", ""))
        expected = str(row.get("hash", ""))
        if not rel or not expected:
            raise RuntimeError(f"pin missing rel/hash for {row.get('id')}")
        rows.append(row)
    return rows


def copy_pinned_bytes(pin_root: Path, dest: Path, manifest_path: Path) -> None:
    dest_manifest = dest / "assets" / "ASSET_MANIFEST.json"
    dest_manifest.parent.mkdir(parents=True, exist_ok=True)
    dest_manifest.write_bytes(manifest_path.read_bytes())
    for row in pin_rows(manifest_path):
        rel = str(row["rel"])
        expected = str(row["hash"])
        src = pin_root / rel
        if not src.is_file():
            raise RuntimeError(f"pinned asset missing at pin root: {rel}")
        got = sha256_file(src)
        if got != expected:
            raise RuntimeError(f"pin mismatch at pin root {rel}")
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(src.read_bytes())


def write_generated(dest: Path, brief: dict[str, object]) -> None:
    module = load_sources()
    files = module.text_files(brief)
    for rel, text in files.items():
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")


def contradict_brief(dest: Path, brief: dict[str, object]) -> list[str]:
    errors: list[str] = []
    godot = (dest / "project.godot").read_text(encoding="utf-8") if (dest / "project.godot").is_file() else ""
    state = (dest / "src" / "game_state.gd").read_text(encoding="utf-8") if (dest / "src" / "game_state.gd").is_file() else ""
    vault = (dest / "src" / "vault_map.gd").read_text(encoding="utf-8") if (dest / "src" / "vault_map.gd").is_file() else ""
    run_all = (dest / "tests" / "run_all.gd").read_text(encoding="utf-8") if (dest / "tests" / "run_all.gd").is_file() else ""
    readme = (dest / "README.md").read_text(encoding="utf-8") if (dest / "README.md").is_file() else ""
    if f"viewport_width={brief['view_w']}" not in godot:
        errors.append("generated project.godot width contradicts brief")
    if f"viewport_height={brief['view_h']}" not in godot:
        errors.append("generated project.godot height contradicts brief")
    if f'stretch/mode="{brief["stretch_mode"]}"' not in godot:
        errors.append("generated project.godot stretch contradicts brief")
    if f'stretch/aspect="{brief["stretch_aspect"]}"' not in godot:
        errors.append("generated project.godot aspect contradicts brief")
    if "return relic_reached" not in state:
        errors.append("generated win flag is not relic_reached")
    if re.search(r"relic_reached\s*=\s*true", run_all):
        errors.append("generated run_all.gd pokes relic_reached")
    if PATH_LABEL not in run_all:
        errors.append("generated run_all.gd missing start→key→door→relic→win")
    if "KEY_CELL" not in vault or "DOOR_CELL" not in vault or "RELIC_CELL" not in vault:
        errors.append("generated vault_map missing start/key/door/relic cells")
    if "not accepted" not in readme.lower() and "not" not in readme.lower():
        errors.append("generated README must not claim the game is accepted")
    if re.search(r"\b(g5\s*pass|dogfood signed|g5 signed)\b", readme, re.I):
        errors.append("generated README fakes G5")
    return errors


def recreate_project(
    dest: Path,
    brief_path: Path | None = None,
    manifest_path: Path | None = None,
    pin_root: Path | None = None,
) -> dict[str, str]:
    brief_file = Path(brief_path) if brief_path is not None else BRIEF_DEFAULT
    manifest_file = Path(manifest_path) if manifest_path is not None else MANIFEST_DEFAULT
    pins = Path(pin_root) if pin_root is not None else PIN_ROOT
    dest = Path(dest)
    if dest.resolve() == pins.resolve():
        raise RuntimeError("refusing to write over the pin root")
    if not brief_file.is_file():
        raise RuntimeError(f"missing brief {brief_file}")
    if not manifest_file.is_file():
        raise RuntimeError(f"missing asset pin {manifest_file}")
    brief = parse_brief(brief_file.read_text(encoding="utf-8"))
    if brief["errors"]:
        raise RuntimeError("brief keys invalid: " + "; ".join(str(item) for item in brief["errors"]))
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "PROJECT_BRIEF.md").write_bytes(brief_file.read_bytes())
    copy_pinned_bytes(pins, dest, manifest_file)
    write_generated(dest, brief)
    contradictions = contradict_brief(dest, brief)
    if contradictions:
        raise RuntimeError("built game contradicts brief: " + "; ".join(contradictions))
    hashes = hash_tree(dest)
    manifest = {
        "schema": 1,
        "source": "brief+pins",
        "brief": brief_file.as_posix(),
        "manifest": manifest_file.as_posix(),
        "dest": dest.as_posix(),
        "file_count": len(hashes),
        "hashes": hashes,
        "not_g5": True,
        "win_flag": "relic_reached",
        "path": PATH_LABEL,
        "copy2_dogfood_src": False,
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    (dest.parent / f"{dest.name}.manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return hashes


def verify_asset_pins(root: Path, manifest_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    path = manifest_path if manifest_path is not None else root / "assets" / "ASSET_MANIFEST.json"
    if not path.is_file():
        return [f"missing asset manifest {path}"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    assets = payload.get("assets")
    if not isinstance(assets, list):
        return ["asset manifest missing assets list"]
    for row in assets:
        if not isinstance(row, dict):
            errors.append("asset row is not an object")
            continue
        if str(row.get("role", "")) != "ship":
            continue
        if str(row.get("kind", "")) == "bundled":
            continue
        rel = str(row.get("rel", ""))
        expected = str(row.get("hash", ""))
        if not rel or not expected:
            errors.append(f"pin missing rel/hash for {row.get('id')}")
            continue
        file_path = root / rel
        if not file_path.is_file():
            errors.append(f"pinned asset missing {rel}")
            continue
        got = sha256_file(file_path)
        if got != expected:
            errors.append(f"pin mismatch {rel}")
    return errors


def template_dir() -> Path:
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        raise RuntimeError("APPDATA missing")
    return Path(appdata) / "Godot" / "export_templates" / PINNED_TEMPLATE_VERSION


def tpz_path() -> Path:
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        raise RuntimeError("LOCALAPPDATA missing")
    return (
        Path(local)
        / "HHGodotAgent"
        / "tooling"
        / "godot-4.7.1-stable"
        / "downloads"
        / "Godot_v4.7.1-stable_export_templates.tpz"
    )


def ensure_windows_templates() -> tuple[Path, str]:
    dest = template_dir()
    dest.mkdir(parents=True, exist_ok=True)
    version_file = dest / "version.txt"
    release_exe = dest / "windows_release_x86_64.exe"
    if version_file.is_file() and release_exe.is_file():
        version = version_file.read_text(encoding="utf-8").strip()
        if "4.7." + "2" in version or version.startswith("4.8"):
            raise RuntimeError(f"refused export templates {version!r}")
        if version != PINNED_TEMPLATE_VERSION:
            raise RuntimeError(f"template version {version!r} != {PINNED_TEMPLATE_VERSION}")
        return dest, version
    archive = tpz_path()
    if not archive.is_file():
        raise RuntimeError(f"missing pinned templates tpz at {archive}")
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        for name in WINDOWS_TEMPLATE_NAMES:
            inner = f"templates/{name}"
            if inner not in names:
                raise RuntimeError(f"tpz missing {inner}")
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(inner) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)
    version = version_file.read_text(encoding="utf-8").strip()
    if "4.7." + "2" in version or version.startswith("4.8"):
        raise RuntimeError(f"refused extracted templates {version!r}")
    if version != PINNED_TEMPLATE_VERSION:
        raise RuntimeError(f"extracted template version {version!r} != {PINNED_TEMPLATE_VERSION}")
    if not release_exe.is_file():
        raise RuntimeError("windows_release_x86_64.exe missing after extract")
    return dest, version


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Kho Bi An from brief + pins.")
    parser.add_argument("--out", required=True, help="empty or new destination directory")
    parser.add_argument("--brief", default=str(BRIEF_DEFAULT), help="PROJECT_BRIEF.md")
    parser.add_argument("--manifest", default=str(MANIFEST_DEFAULT), help="ASSET_MANIFEST.json")
    parser.add_argument("--pin-root", default=str(PIN_ROOT), help="root that holds pinned asset bytes")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dest = Path(args.out)
    try:
        hashes = recreate_project(
            dest,
            brief_path=Path(args.brief),
            manifest_path=Path(args.manifest),
            pin_root=Path(args.pin_root),
        )
    except RuntimeError as exc:
        print(f"FAIL: R8-WP6 recreate {exc}")
        return 1
    pin_errors = verify_asset_pins(dest)
    if pin_errors:
        print("FAIL: R8-WP6 recreate pin")
        for item in pin_errors:
            print(f"  - {item}")
        return 1
    print(f"PASS: R8-WP6 recreate files={len(hashes)} dest={dest} not_g5=1 source=brief+pins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
