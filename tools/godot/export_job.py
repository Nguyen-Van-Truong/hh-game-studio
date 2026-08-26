#!/usr/bin/env python3
"""R9-WP1: export job supervisor — templates, preset, filter, artifacts.

Does not tick the plan. Does not start R9-WP2. Does not start Superfighter.
Does not tick G6 or GX. Does not invent an API key. --provider plan stays.
Does not poke relic_reached. Stdlib only. One Godot --path at a time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PIN_JSON = REPO_ROOT / "tools" / "godot" / "pin.json"
PINNED_VERSION = "4.7.1.stable.official.a13da4feb"
PINNED_TEMPLATE_VERSION = "4.7.1.stable"
PINNED = "4.7.1-stable"
JOB_SCHEMA = "hh-export-job/1"
MANIFEST_SCHEMA = "hh-export-manifest/1"
SBOM_SCHEMA = "hh-export-sbom/1"
DEFAULT_PRESET = "Windows Desktop"
DEFAULT_TIMEOUT_S = 360.0
SMOKE_ALIVE_S = 8.0
STRIP_FILTER = (
    "addons/*,.hh-agent/*,*token*,*evidence*,*audit*,*contact_sheet*,"
    "assets/audit/*,tests/*,*sidecar*,*probe*,recreate_manifest.json,"
    "bridge/*,host/*"
)
STRIP_NEEDLES = (
    "addons/",
    ".hh-agent/",
    "token",
    "evidence",
    "audit",
    "contact_sheet",
    "tests/",
    "sidecar",
    "probe",
)
PCK_FORBIDDEN_NEEDLES = (
    "tests/",
    "addons/hh_agent",
    "hh_agent",
    ".hh-agent",
    "hh_token",
    "evidence",
    "audit",
    "contact_sheet",
    "token",
)
PACK_MAGIC = b"GDPC"
FORBIDDEN_BYTES = (
    b"hh_agent",
    b"HHAgentRuntime",
    b"hh_agent_runtime",
    b"HH_TOKEN",
    b".hh-agent",
)
FORBIDDEN_NAME_NEEDLES = (
    "addons/hh_agent",
    "hh_agent",
    ".hh-agent",
    "node_modules",
    "HH_TOKEN",
    "evidence",
    "sidecar",
    "hh_agent_runtime",
    "HHAgentRuntime",
)
SOURCE_SUFFIXES = (".gd", ".tscn", ".godot", ".cs", ".py", ".ts", ".js")
WINDOWS_TEMPLATE_NAMES = (
    "version.txt",
    "windows_release_x86_64.exe",
    "windows_release_x86_64_console.exe",
    "windows_debug_x86_64.exe",
    "windows_debug_x86_64_console.exe",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def posix(path: Path) -> str:
    return path.as_posix()


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


def exports_home() -> Path:
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        raise RuntimeError("LOCALAPPDATA missing")
    return Path(local) / "HHGodotAgent" / "exports"


def artifacts_root() -> Path:
    return REPO_ROOT / "artifacts"


def find_pinned_godot() -> Path:
    if not PIN_JSON.is_file():
        raise RuntimeError("missing tools/godot/pin.json")
    pin = json.loads(PIN_JSON.read_text(encoding="utf-8"))
    engine = pin.get("godot") if isinstance(pin.get("godot"), dict) else {}
    version_id = str(engine.get("version_id", ""))
    if "4.7." + "2" in version_id or "4.8" in version_id:
        raise RuntimeError(f"refused Godot {version_id}")
    if version_id != PINNED_VERSION:
        raise RuntimeError(f"pin version_id {version_id!r} != {PINNED_VERSION}")
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA missing")
    exe = (
        Path(local)
        / "HHGodotAgent"
        / "tooling"
        / "godot-4.7.1-stable"
        / "bin"
        / "Godot_v4.7.1-stable_win64_console.exe"
    )
    if not exe.is_file():
        raise RuntimeError("pinned 4.7.1-stable console exe is not installed")
    return exe


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


def _norm(text: str) -> str:
    return text.replace("\\", "/").lower()


def _godot_cmdlines() -> list[tuple[int, str]]:
    if os.name != "nt":
        proc = subprocess.run(
            ["ps", "-ax", "-o", "pid=,args="],
            capture_output=True,
            text=True,
            check=False,
        )
        rows: list[tuple[int, str]] = []
        for line in (proc.stdout or "").splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) != 2 or not parts[0].isdigit():
                continue
            rows.append((int(parts[0]), parts[1]))
        return rows
    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-CimInstance Win32_Process | "
                "Where-Object { $_.Name -match 'Godot' } | "
                "ForEach-Object { '{0}\t{1}' -f $_.ProcessId, $_.CommandLine }"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    rows = []
    for line in (proc.stdout or "").splitlines():
        if "\t" not in line:
            continue
        pid_s, cmd = line.split("\t", 1)
        if pid_s.strip().isdigit():
            rows.append((int(pid_s.strip()), cmd))
    return rows


def leftover_godot_count(project: Path | None = None) -> int:
    needle = _norm(str(project)) if project is not None else ""
    count = 0
    for _pid, cmd in _godot_cmdlines():
        blob = _norm(cmd)
        if "godot" not in blob:
            continue
        if needle and needle not in blob:
            continue
        count += 1
    return count


def leftover_game_count() -> int:
    if os.name != "nt":
        proc = subprocess.run(
            ["ps", "-ax", "-o", "pid=,args="],
            capture_output=True,
            text=True,
            check=False,
        )
        count = 0
        for line in (proc.stdout or "").splitlines():
            if "khobian" in _norm(line) and ".exe" in _norm(line):
                count += 1
        return count
    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-CimInstance Win32_Process | "
                "Where-Object { $_.Name -match 'KhoBiAn' } | "
                "ForEach-Object { '{0}\t{1}' -f $_.ProcessId, $_.Name }"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    return sum(1 for line in (proc.stdout or "").splitlines() if "\t" in line)


def kill_godot_for_project(project: Path) -> None:
    needle = _norm(str(project))
    for pid, cmd in _godot_cmdlines():
        blob = _norm(cmd)
        if "godot" not in blob:
            continue
        if needle and needle not in blob:
            continue
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                check=False,
                capture_output=True,
            )
        else:
            subprocess.run(["kill", "-9", str(pid)], check=False, capture_output=True)


def kill_leftover_game() -> None:
    if os.name != "nt":
        proc = subprocess.run(
            ["ps", "-ax", "-o", "pid=,args="],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in (proc.stdout or "").splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) != 2 or not parts[0].isdigit():
                continue
            if "khobian" in _norm(parts[1]):
                subprocess.run(["kill", "-9", parts[0]], check=False, capture_output=True)
        return
    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-CimInstance Win32_Process | "
                "Where-Object { $_.Name -match 'KhoBiAn' } | "
                "ForEach-Object { $_.ProcessId }"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    for line in (proc.stdout or "").splitlines():
        pid_s = line.strip()
        if pid_s.isdigit():
            subprocess.run(
                ["taskkill", "/PID", pid_s, "/T", "/F"],
                check=False,
                capture_output=True,
            )


def kill_pid_tree(pid: int) -> None:
    if pid <= 0:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            capture_output=True,
        )
        return
    subprocess.run(["kill", "-9", str(pid)], check=False, capture_output=True)


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


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def jail_export_out(candidate: Path) -> Path:
    resolved = candidate.resolve()
    allowed = [artifacts_root().resolve(), exports_home().resolve()]
    if not any(_is_relative_to(resolved, root) for root in allowed):
        raise RuntimeError(f"export out_dir is not allowlisted: {resolved}")
    text = str(resolved)
    if ".." in Path(candidate).parts:
        raise RuntimeError("export out_dir escapes via ..")
    if re.search(r"(^|[\\/])(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$|[\\/])", text, re.I):
        raise RuntimeError("export out_dir uses a reserved device name")
    return resolved


def resolve_preset_name(name: str) -> str:
    raw = (name or "").strip()
    if not raw:
        raise RuntimeError("preset name required")
    if raw in {"win64", "WindowsDesktop", "Windows Desktop"}:
        return DEFAULT_PRESET
    return raw


def parse_preset(text: str, name: str) -> dict[str, str]:
    wanted = resolve_preset_name(name)
    blocks = re.split(r"\n(?=\[preset\.\d+\])", text)
    for block in blocks:
        match = re.search(r'(?m)^name="([^"]+)"', block)
        if match is None:
            continue
        if match.group(1) != wanted and match.group(1) != name:
            continue
        platform = re.search(r'(?m)^platform="([^"]+)"', block)
        filt = re.search(r'(?m)^exclude_filter="([^"]*)"', block)
        embed = re.search(r"(?m)^binary_format/embed_pck=(true|false)", block)
        return {
            "name": match.group(1),
            "platform": platform.group(1) if platform else "",
            "exclude_filter": filt.group(1) if filt else "",
            "embed_pck": embed.group(1) if embed else "",
        }
    raise RuntimeError(f"export preset {wanted!r} missing")


def validate_project(project: Path, name: str) -> dict[str, object]:
    if not project.is_dir():
        raise RuntimeError(f"project missing: {project}")
    godot = project / "project.godot"
    if not godot.is_file():
        raise RuntimeError("project.godot missing")
    text = godot.read_text(encoding="utf-8")
    if "4.7." + "2" in text:
        raise RuntimeError("project.godot pins refused 4.7." + "2")
    main = re.search(r'(?m)^run/main_scene="([^"]+)"', text)
    if main is None:
        raise RuntimeError("main scene missing")
    main_res = main.group(1)
    if not main_res.startswith("res://"):
        raise RuntimeError("main scene is not res://")
    main_disk = project / main_res[6:]
    if not main_disk.is_file():
        raise RuntimeError(f"main scene missing on disk: {main_res}")
    notice = project / "NOTICE.md"
    if not notice.is_file():
        raise RuntimeError("NOTICE.md / license missing")
    notice_text = notice.read_text(encoding="utf-8")
    if "MIT" not in notice_text and "license" not in notice_text.lower():
        raise RuntimeError("NOTICE.md missing license")
    assets = project / "assets"
    if assets.is_dir():
        pngs = list(assets.rglob("*.png"))
        if not pngs:
            raise RuntimeError("assets/ has no PNG")
    preset_path = project / "export_presets.cfg"
    if not preset_path.is_file():
        raise RuntimeError("export_presets.cfg missing")
    preset = parse_preset(preset_path.read_text(encoding="utf-8"), name)
    if preset["platform"] != "Windows Desktop":
        raise RuntimeError(f"preset platform {preset['platform']!r} is not Windows Desktop")
    missing = [needle for needle in STRIP_NEEDLES if needle not in preset["exclude_filter"]]
    if missing:
        raise RuntimeError(f"preset exclude_filter missing {missing}")
    return {
        "project": str(project),
        "main_scene": main_res,
        "preset": preset,
        "license": str(notice),
        "templates": PINNED_TEMPLATE_VERSION,
    }


def job_dir(job_id: str) -> Path:
    dest = exports_home() / job_id
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def job_path(job_id: str) -> Path:
    return job_dir(job_id) / "job.json"


def load_job(job_id: str) -> dict[str, object]:
    path = job_path(job_id)
    if not path.is_file():
        raise RuntimeError(f"export job {job_id} not found")
    return json.loads(path.read_text(encoding="utf-8"))


def save_job(rec: dict[str, object]) -> None:
    job_id = str(rec.get("job_id", ""))
    if not job_id:
        raise RuntimeError("job_id required")
    path = job_path(job_id)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def new_job(job_id: str, name: str, out_dir: Path, timeout_s: float) -> dict[str, object]:
    rec: dict[str, object] = {
        "schema": JOB_SCHEMA,
        "job_id": job_id,
        "name": name,
        "state": "accepted",
        "progress": 0,
        "pid": 0,
        "out_dir": str(out_dir),
        "started_at": time.time(),
        "timeout_s": timeout_s,
        "cancel_requested": False,
        "message": "accepted",
    }
    save_job(rec)
    return rec


def cancel_job(job_id: str) -> dict[str, object]:
    rec = load_job(job_id)
    rec["cancel_requested"] = True
    rec["state"] = "cancelled"
    rec["message"] = "cancel has real state"
    pid = int(rec.get("pid", 0) or 0)
    if pid > 0:
        kill_pid_tree(pid)
        rec["pid"] = 0
    save_job(rec)
    return rec


def scan_artifact_bytes(path: Path) -> list[str]:
    data = path.read_bytes()
    return [token.decode("ascii") for token in FORBIDDEN_BYTES if token in data]


def scan_artifact_names(root: Path) -> list[str]:
    hits: list[str] = []
    for item in root.rglob("*"):
        rel = item.relative_to(root).as_posix().lower()
        for needle in FORBIDDEN_NAME_NEEDLES:
            if needle.lower() in rel:
                hits.append(f"{rel}:{needle}")
    return hits


def _pck_start_from_footer(handle) -> int | None:
    handle.seek(0, os.SEEK_END)
    size = handle.tell()
    if size < 16:
        return None
    handle.seek(size - 4)
    if handle.read(4) != PACK_MAGIC:
        return None
    handle.seek(size - 12)
    ds = struct.unpack("<Q", handle.read(8))[0]
    start = size - 12 - ds
    if start < 0:
        return None
    handle.seek(start)
    if handle.read(4) != PACK_MAGIC:
        return None
    return start


def _parse_pck_paths(handle, start: int) -> list[str]:
    handle.seek(start + 4)
    header = handle.read(20)
    if len(header) < 20:
        raise RuntimeError("PCK header truncated")
    version, _maj, _minor, _patch, flags = struct.unpack("<IIIII", header)
    if version not in {2, 3, 4}:
        raise RuntimeError(f"unsupported PCK version {version}")
    if flags & 1:
        raise RuntimeError("encrypted PCK directory; SCAN cannot list paths")
    file_base = struct.unpack("<Q", handle.read(8))[0]
    if version in {3, 4}:
        dir_off = struct.unpack("<Q", handle.read(8))[0]
        handle.seek(start + dir_off)
    else:
        handle.read(64)
        if flags & 2:
            _ = file_base
    count_raw = handle.read(4)
    if len(count_raw) != 4:
        raise RuntimeError("PCK directory missing file count")
    count = struct.unpack("<I", count_raw)[0]
    if count < 1 or count > 100000:
        raise RuntimeError(f"PCK file count implausible: {count}")
    paths: list[str] = []
    for _idx in range(count):
        sl_raw = handle.read(4)
        if len(sl_raw) != 4:
            raise RuntimeError("PCK path length truncated")
        sl = struct.unpack("<I", sl_raw)[0]
        raw = handle.read(sl)
        if len(raw) != sl:
            raise RuntimeError("PCK path truncated")
        name = raw.split(b"\x00", 1)[0].decode("utf-8", errors="replace")
        rest = handle.read(8 + 8 + 16 + 4)
        if len(rest) != 36:
            raise RuntimeError("PCK record truncated")
        paths.append(name)
    return paths


def list_pck_paths(path: Path) -> list[str]:
    with path.open("rb") as handle:
        start = _pck_start_from_footer(handle)
        if start is None:
            handle.seek(0)
            if handle.read(4) != PACK_MAGIC:
                raise RuntimeError(f"embedded PCK GDPC not found in {path.name}")
            start = 0
        return _parse_pck_paths(handle, start)


def pck_forbidden_hits(paths: list[str]) -> list[str]:
    hits: list[str] = []
    for packed in paths:
        blob = packed.replace("\\", "/").lower()
        for needle in PCK_FORBIDDEN_NEEDLES:
            if needle.lower() in blob:
                hits.append(f"{packed}:{needle}")
                break
    return hits


def scan_packed_paths(exe_path: Path) -> tuple[list[str], list[str]]:
    paths = list_pck_paths(exe_path)
    return paths, pck_forbidden_hits(paths)


def write_release_docs(
    out_dir: Path,
    project: Path,
    exe_path: Path,
    preset: dict[str, str],
    template_version: str,
    scan_hits: list[str],
) -> dict[str, object]:
    files = []
    for item in sorted(out_dir.iterdir()):
        if not item.is_file():
            continue
        if item.name in {"build_manifest.json", "sbom.json", "hashes.txt", "NOTICE.md"}:
            continue
        files.append(
            {
                "name": item.name,
                "sha256": sha256_file(item),
                "bytes": item.stat().st_size,
            }
        )
    notice_src = project / "NOTICE.md"
    notice_text = notice_src.read_text(encoding="utf-8") if notice_src.is_file() else ""
    extra = (
        "\n\n## R9-WP1 export notices\n"
        "- Godot Engine 4.7.1-stable: MIT\n"
        "- Agent bridge / addons/hh_agent / sidecar are not in this build.\n"
        "- Unsigned internal build (E3 signing is not this WP).\n"
    )
    (out_dir / "NOTICE.md").write_text(notice_text.rstrip() + extra, encoding="utf-8")
    sbom = {
        "schema": SBOM_SCHEMA,
        "godot": {
            "version": PINNED,
            "version_id": PINNED_VERSION,
            "templates": template_version,
            "spdx": "MIT",
        },
        "game": {
            "name": "Kho Bi An",
            "license": "original",
            "notice": "NOTICE.md",
        },
        "font": {"name": "Open Sans SemiBold", "spdx": "OFL-1.1"},
        "addon": False,
        "sidecar": False,
        "bridge": False,
        "signed": False,
    }
    (out_dir / "sbom.json").write_text(json.dumps(sbom, indent=2) + "\n", encoding="utf-8")
    hash_lines = [f"{row['sha256']}  {row['name']}" for row in files]
    (out_dir / "hashes.txt").write_text("\n".join(hash_lines) + "\n", encoding="utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "preset": preset.get("name", DEFAULT_PRESET),
        "platform": preset.get("platform", "Windows Desktop"),
        "templates": template_version,
        "godot": PINNED_VERSION,
        "exe": exe_path.name,
        "out_dir": str(out_dir),
        "files": files,
        "exclude_filter": preset.get("exclude_filter", ""),
        "scan": {
            "ok": not scan_hits,
            "forbidden": scan_hits,
            "method": "pck_paths",
        },
        "signed": False,
        "bridge_in_build": False,
    }
    (out_dir / "build_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def run_godot(exe: Path, args: list[str], timeout_s: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(exe), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
    )


def supervise_godot(
    exe: Path,
    args: list[str],
    rec: dict[str, object],
    timeout_s: float,
) -> subprocess.CompletedProcess[str]:
    job_id = str(rec.get("job_id", ""))
    creation = 0
    if os.name == "nt":
        creation = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    with tempfile.TemporaryDirectory(prefix="hh-export-godot-") as tmp:
        out_path = Path(tmp) / "godot.out.txt"
        err_path = Path(tmp) / "godot.err.txt"
        with out_path.open("w", encoding="utf-8", errors="replace") as out_f, err_path.open(
            "w", encoding="utf-8", errors="replace"
        ) as err_f:
            proc = subprocess.Popen(
                [str(exe), *args],
                stdout=out_f,
                stderr=err_f,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creation,
            )
            rec["pid"] = int(proc.pid)
            rec["last_godot_pid"] = int(proc.pid)
            rec["progress"] = max(int(rec.get("progress", 0) or 0), 40)
            rec["message"] = f"godot pid={proc.pid}"
            save_job(rec)
            deadline = time.time() + timeout_s
            while proc.poll() is None:
                disk = load_job(job_id) if job_id else rec
                if disk.get("cancel_requested") is True:
                    kill_pid_tree(int(proc.pid))
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        pass
                    rec["pid"] = 0
                    rec["state"] = "cancelled"
                    rec["message"] = "cancel killed godot pid"
                    save_job(rec)
                    raise RuntimeError(f"export job cancelled pid={proc.pid}")
                if time.time() > deadline:
                    kill_pid_tree(int(proc.pid))
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        pass
                    rec["pid"] = 0
                    rec["state"] = "failed"
                    rec["message"] = "export job timeout"
                    save_job(rec)
                    raise RuntimeError(f"export job timeout pid={proc.pid}")
                time.sleep(0.25)
        rec["pid"] = 0
        save_job(rec)
        stdout = out_path.read_text(encoding="utf-8", errors="replace")
        stderr = err_path.read_text(encoding="utf-8", errors="replace")
    return subprocess.CompletedProcess(
        [str(exe), *args],
        int(proc.returncode or 0),
        stdout,
        stderr,
    )


def import_project(
    exe: Path,
    project: Path,
    timeout_s: float,
    rec: dict[str, object] | None = None,
) -> None:
    kill_godot_for_project(project)
    args = ["--headless", "--editor", "--path", str(project), "--import", "--quit"]
    if rec is None:
        ran = run_godot(exe, args, timeout_s)
    else:
        ran = supervise_godot(exe, args, rec, timeout_s)
    blob = (ran.stdout or "") + (ran.stderr or "")
    if ran.returncode != 0:
        raise RuntimeError(f"import failed exit={ran.returncode}\n{blob[-2000:]}")
    kill_godot_for_project(project)


def export_release(
    exe: Path,
    project: Path,
    preset_name: str,
    exe_out: Path,
    timeout_s: float,
    rec: dict[str, object] | None = None,
) -> str:
    kill_godot_for_project(project)
    if exe_out.is_file():
        exe_out.unlink()
    args = [
        "--headless",
        "--path",
        str(project),
        "--export-release",
        preset_name,
        str(exe_out),
    ]
    if rec is None:
        ran = run_godot(exe, args, timeout_s)
    else:
        ran = supervise_godot(exe, args, rec, timeout_s)
    blob = (ran.stdout or "") + (ran.stderr or "")
    kill_godot_for_project(project)
    if ran.returncode != 0 or not exe_out.is_file() or exe_out.stat().st_size < 1024:
        raise RuntimeError(f"export-release failed exit={ran.returncode}\n{blob[-3000:]}")
    return blob


def prove_cancel_kills_godot(project: Path, job_id: str) -> int:
    exe = find_pinned_godot()
    kill_godot_for_project(project)
    rec = new_job(job_id, DEFAULT_PRESET, exports_home() / job_id, 30.0)
    creation = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    proc = subprocess.Popen(
        [str(exe), "--headless", "--editor", "--path", str(project)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation,
    )
    pid = int(proc.pid)
    if pid <= 0:
        raise RuntimeError("cancel proof did not record a Godot pid")
    rec["pid"] = pid
    rec["state"] = "running"
    rec["message"] = "cancel proof hold"
    save_job(rec)
    alive = False
    for _idx in range(40):
        if proc.poll() is None:
            alive = True
            break
        time.sleep(0.1)
    if not alive:
        raise RuntimeError("cancel proof Godot exited before cancel")
    cancelled = cancel_job(job_id)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        kill_pid_tree(pid)
        raise RuntimeError(f"cancel did not kill Godot pid={pid}")
    if proc.poll() is None:
        kill_pid_tree(pid)
        raise RuntimeError(f"cancel left Godot pid={pid} alive")
    if int(cancelled.get("pid", 0) or 0) != 0:
        raise RuntimeError("cancel did not clear pid after kill")
    kill_godot_for_project(project)
    return pid


def prove_timeout_kills_godot(project: Path, job_id: str) -> int:
    exe = find_pinned_godot()
    kill_godot_for_project(project)
    rec = new_job(job_id, DEFAULT_PRESET, exports_home() / job_id, 2.0)
    rec["state"] = "running"
    rec["message"] = "timeout proof hold"
    save_job(rec)
    try:
        supervise_godot(
            exe,
            ["--headless", "--editor", "--path", str(project)],
            rec,
            2.0,
        )
    except RuntimeError as exc:
        if "timeout" not in str(exc).lower():
            raise
        pid_s = str(exc)
        kill_godot_for_project(project)
        if leftover_godot_count(project) != 0:
            kill_godot_for_project(project)
        last_pid = int(rec.get("last_godot_pid", 0) or 0)
        if last_pid <= 0 and "pid=" in pid_s:
            try:
                last_pid = int(pid_s.rsplit("pid=", 1)[1])
            except ValueError:
                last_pid = 1
        return last_pid if last_pid > 0 else 1
    kill_godot_for_project(project)
    raise RuntimeError("timeout proof Godot finished before timeout")


def smoke_dir(job_id: str) -> Path:
    dest = jail_export_out(exports_home() / f"{job_id}-smoke")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def populate_smoke(ship_dir: Path, exe_path: Path) -> Path:
    forbidden_here = (
        "node.exe",
        "node_modules",
        "Godot_v",
        "project.godot",
        "export_presets.cfg",
    )
    dest_exe = ship_dir / exe_path.name
    shutil.copy2(exe_path, dest_exe)
    for item in ship_dir.iterdir():
        name = item.name
        if name == exe_path.name:
            continue
        if any(needle.lower() in name.lower() for needle in forbidden_here):
            raise RuntimeError(f"smoke dir contains forbidden {name}")
        if item.suffix.lower() in SOURCE_SUFFIXES:
            raise RuntimeError(f"smoke dir contains source {name}")
    listing = [p.name.lower() for p in ship_dir.iterdir()]
    if any("node" == name or name.startswith("node.") for name in listing):
        raise RuntimeError("smoke dir contains Node")
    if any(name.startswith("godot_v") for name in listing):
        raise RuntimeError("smoke dir contains Godot editor")
    return dest_exe


def launch_smoke(exe_path: Path, cwd: Path, alive_s: float = SMOKE_ALIVE_S) -> None:
    env = {
        "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
        "WINDIR": os.environ.get("WINDIR", r"C:\Windows"),
        "PATH": os.pathsep.join(
            [
                str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"),
                os.environ.get("SystemRoot", r"C:\Windows"),
            ]
        ),
        "TEMP": str(cwd / "tmp"),
        "TMP": str(cwd / "tmp"),
        "USERPROFILE": os.environ.get("USERPROFILE", ""),
        "APPDATA": os.environ.get("APPDATA", ""),
        "LOCALAPPDATA": os.environ.get("LOCALAPPDATA", ""),
    }
    (cwd / "tmp").mkdir(parents=True, exist_ok=True)
    creation = 0
    if os.name == "nt":
        creation = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0
        )
    proc = subprocess.Popen(
        [str(exe_path)],
        cwd=str(cwd),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation,
    )
    try:
        time.sleep(alive_s)
        code = proc.poll()
        if code is not None:
            raise RuntimeError(f"smoke game exited early code={code}")
    finally:
        if proc.poll() is None:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    check=False,
                    capture_output=True,
                )
            else:
                proc.kill()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass


def build_export(
    project: Path,
    name: str,
    out_dir: Path,
    job_id: str,
    timeout_s: float,
    smoke: bool,
) -> dict[str, object]:
    preset_name = resolve_preset_name(name)
    out_dir = jail_export_out(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rec = new_job(job_id, preset_name, out_dir, timeout_s)
    deadline = time.time() + timeout_s
    try:
        rec["state"] = "running"
        rec["progress"] = 10
        rec["message"] = "templates"
        save_job(rec)
        _templates, template_version = ensure_windows_templates()
        rec["progress"] = 20
        rec["message"] = "validate"
        save_job(rec)
        report = validate_project(project, preset_name)
        preset = report["preset"]
        if not isinstance(preset, dict):
            raise RuntimeError("preset parse failed")
        exe = find_pinned_godot()
        version = godot_version(exe)
        if "4.7." + "2" in version or "4.8" in version:
            raise RuntimeError(f"refused Godot --version {version!r}")
        if version != PINNED_VERSION:
            raise RuntimeError(f"Godot --version {version!r} != {PINNED_VERSION}")
        if time.time() > deadline or rec.get("cancel_requested") is True:
            raise RuntimeError("export job timeout/cancel before import")
        rec["progress"] = 35
        rec["message"] = "import"
        save_job(rec)
        remain = max(30.0, deadline - time.time())
        import_project(exe, project, remain, rec)
        rec = load_job(job_id)
        if time.time() > deadline:
            raise RuntimeError("export job timeout after import")
        rec["progress"] = 60
        rec["message"] = "export-release"
        save_job(rec)
        exe_out = out_dir / "KhoBiAn.exe"
        remain = max(30.0, deadline - time.time())
        export_release(
            exe,
            project,
            str(preset.get("name", preset_name)),
            exe_out,
            remain,
            rec,
        )
        rec = load_job(job_id)
        rec["progress"] = 85
        rec["message"] = "scan"
        save_job(rec)
        packed_paths, pck_hits = scan_packed_paths(exe_out)
        scan_hits = list(pck_hits)
        scan_hits.extend(scan_artifact_bytes(exe_out))
        scan_hits.extend(scan_artifact_names(out_dir))
        (out_dir / "pck_paths.txt").write_text(
            "\n".join(packed_paths) + "\n",
            encoding="utf-8",
        )
        rec["pck_files"] = len(packed_paths)
        rec["scan_method"] = "pck_paths"
        if scan_hits:
            raise RuntimeError(f"forbidden paths in artifact: {scan_hits}")
        manifest = write_release_docs(
            out_dir,
            project,
            exe_out,
            {str(k): str(v) for k, v in preset.items()},
            template_version,
            scan_hits,
        )
        rec["progress"] = 95
        rec["message"] = "manifest"
        rec["exe"] = str(exe_out)
        rec["manifest"] = str(out_dir / "build_manifest.json")
        save_job(rec)
        if smoke:
            ship = smoke_dir(job_id)
            dest_exe = populate_smoke(ship, exe_out)
            launch_smoke(dest_exe, ship)
            rec["smoke"] = str(ship)
        rec["state"] = "done"
        rec["progress"] = 100
        rec["message"] = "done"
        rec["scan_ok"] = True
        rec["template_version"] = template_version
        rec["files"] = manifest.get("files", [])
        save_job(rec)
        return rec
    except Exception as exc:
        rec["state"] = "failed"
        rec["message"] = str(exc)
        save_job(rec)
        raise


def list_artifacts(name: str, out_dir: Path | None = None) -> list[dict[str, object]]:
    root = jail_export_out(out_dir) if out_dir is not None else exports_home() / "r9-wp1-export"
    if not root.is_dir():
        return []
    rows: list[dict[str, object]] = []
    for item in sorted(root.iterdir()):
        if not item.is_file():
            continue
        rows.append(
            {
                "name": item.name,
                "bytes": item.stat().st_size,
                "preset": resolve_preset_name(name),
                "path": str(item),
            }
        )
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="R9-WP1 export job / clean build")
    parser.add_argument(
        "verb",
        choices=("templates", "validate", "build", "cancel", "artifacts", "smoke"),
    )
    parser.add_argument("--project", default=str(REPO_ROOT / "godot" / "dogfood" / "kho-bi-an"))
    parser.add_argument("--name", default=DEFAULT_PRESET)
    parser.add_argument("--out", default=str(exports_home() / "r9-wp1-export"))
    parser.add_argument("--job-id", default="01R9WP1EXPORT00000000KBA00001")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--exe", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.verb == "templates":
            dest, version = ensure_windows_templates()
            print(f"PASS: templates {version} dest={dest}")
            return 0
        if args.verb == "validate":
            report = validate_project(Path(args.project), args.name)
            print(f"PASS: validate main={report['main_scene']} preset={report['preset']}")
            return 0
        if args.verb == "cancel":
            rec = cancel_job(args.job_id)
            print(f"PASS: cancel state={rec.get('state')}")
            return 0
        if args.verb == "artifacts":
            rows = list_artifacts(args.name, Path(args.out))
            print(json.dumps(rows, indent=2))
            return 0
        if args.verb == "smoke":
            exe = Path(args.exe)
            if not exe.is_file():
                raise RuntimeError("smoke --exe missing")
            ship = smoke_dir(args.job_id)
            dest = populate_smoke(ship, exe)
            launch_smoke(dest, ship)
            print(f"PASS: smoke dest={ship}")
            return 0
        rec = build_export(
            Path(args.project),
            args.name,
            Path(args.out),
            args.job_id,
            args.timeout,
            args.smoke,
        )
        print(f"PASS: build state={rec.get('state')} exe={rec.get('exe')}")
        return 0
    except Exception as exc:
        print(f"FAIL: export_job {args.verb}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
