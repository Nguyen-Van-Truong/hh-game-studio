"""hh export: install the pinned Godot 4.7.2 templates and export a project.

``hh export templates`` reports or installs the Windows, Linux and Web templates
Godot reads from ``%APPDATA%/Godot/export_templates/4.7.2.stable``. ``hh export run``
writes only an ``HH Windows`` / ``HH Linux`` / ``HH Web`` preset into ``export_presets.cfg``
(appending it, never rewriting a preset this tool did not create) and exports with
the pinned editor. The Web preset sets ``variant/thread_support=false`` so the page
does not need SharedArrayBuffer or cross-origin isolation headers.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import time
import zipfile
from pathlib import Path
from typing import Any, Iterator, Sequence

from . import common as C

ARCHIVE_NAME = "Godot_v4.7.2-stable_export_templates.tpz"
ARCHIVE_SHA256 = "f298490b8d44d934be425a5a65a51bf15f422428b229a06a6e11d9ffea248011"
VERSION_TEXT = "4.7.2.stable"
CACHE_NAME = "hh-archive-verify-4.7.2.stable.json"
LOCK_NAME = "hh-install-4.7.2.stable.lock"

PRESETS: dict[str, dict[str, str]] = {
    "windows": {"name": "HH Windows", "platform": "Windows Desktop"},
    "linux": {"name": "HH Linux", "platform": "Linux"},
    "web": {"name": "HH Web", "platform": "Web"},
}
TEMPLATE_PLATFORMS = ("windows", "linux", "web", "all")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SECTION_RE = re.compile(r"\[preset\.(\d+)(\.options)?\][ \t]*")
_ASSIGN_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)")

# Basenames Godot 4.7.2 looks up. Console wrappers and dlink/android packs stay in the archive.
REQUIRED_MEMBERS: dict[str, tuple[str, ...]] = {
    "windows": ("windows_release_x86_64.exe", "windows_debug_x86_64.exe"),
    "linux": ("linux_release.x86_64", "linux_debug.x86_64"),
    "web": ("web_nothreads_release.zip", "web_nothreads_debug.zip"),
}
OPTIONAL_MEMBERS: dict[str, tuple[str, ...]] = {
    "web": ("web_release.zip", "web_debug.zip"),
}

_PC_OPTIONS = (
    ("custom_template/debug", '""'),
    ("custom_template/release", '""'),
    ("debug/export_console_wrapper", "0"),
    ("binary_format/embed_pck", "false"),
    ("texture_format/s3tc_bptc", "true"),
    ("texture_format/etc2_astc", "false"),
    ("binary_format/architecture", '"x86_64"'),
    ("shader_baker/enabled", "false"),
)
_WEB_OPTIONS = (
    ("custom_template/debug", '""'),
    ("custom_template/release", '""'),
    ("variant/extensions_support", "false"),
    ("variant/thread_support", "false"),
    ("vram_texture_compression/for_desktop", "true"),
    ("vram_texture_compression/for_mobile", "false"),
    ("progressive_web_app/enabled", "false"),
    ("progressive_web_app/ensure_cross_origin_isolation_headers", "false"),
)

EXPORT_TIMEOUT = 300.0
SMOKE_TIMEOUT = 60.0


def validate_preset(preset: str) -> str:
    if preset not in PRESETS:
        raise C.GamekitError("BAD_REQUEST", f"preset must be one of {', '.join(PRESETS)}")
    return preset


def validate_template_platform(platform: str) -> str:
    if platform not in TEMPLATE_PLATFORMS:
        raise C.GamekitError("BAD_REQUEST", f"platform must be one of {', '.join(TEMPLATE_PLATFORMS)}")
    return platform


def validate_name(name: str) -> str:
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise C.GamekitError("BAD_REQUEST", f"export name must match {NAME_RE.pattern}")
    return name


def output_filenames(preset: str, name: str) -> list[str]:
    """Preferred export products. Linux also accepts ``<name>.x86_64.pck`` at verify time."""
    validate_preset(preset)
    validate_name(name)
    if preset == "windows":
        return [f"{name}.exe", f"{name}.pck"]
    if preset == "linux":
        return [f"{name}.x86_64", f"{name}.pck"]
    return ["index.html", "index.js", "index.wasm", "index.pck"]


_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _path_or_ancestor_reparse(path: Path) -> bool:
    """True when ``path`` or an existing ancestor is a symlink or junction."""
    current = Path(os.path.abspath(str(path)))
    while True:
        try:
            st = os.lstat(current)
        except OSError:
            st = None
        if st is not None and (stat.S_ISLNK(st.st_mode) or getattr(st, "st_file_attributes", 0) & _REPARSE_POINT):
            return True
        parent = current.parent
        if parent == current:
            return False
        current = parent


def validate_out_dir(project: C.Project, out_dir: str | Path) -> Path:
    """Absolute directory outside the project. Relative paths resolve from the cwd."""
    if isinstance(out_dir, Path):
        raw = str(out_dir)
    elif isinstance(out_dir, str):
        raw = out_dir
    else:
        raise C.GamekitError("BAD_REQUEST", "out-dir is required")
    if raw.strip() == "" or any(ch in raw for ch in ("\n", "\r", "\x00")):
        raise C.GamekitError("BAD_REQUEST", "out-dir is empty or contains a control character")
    resolved = Path(os.path.abspath(raw))
    # Inspect the lexical path without following links first. Windows may raise
    # WinError 448 while resolving even an existing junction; a dangling link
    # must still be refused with our stable path error, before traversal.
    if _path_or_ancestor_reparse(resolved):
        raise C.GamekitError("FORBIDDEN_PATH", "out-dir or an ancestor is a junction or symlink")
    try:
        real = Path(os.path.realpath(resolved))
    except OSError as exc:
        raise C.GamekitError("FORBIDDEN_PATH", f"out-dir cannot be resolved: {exc}") from exc
    if _path_or_ancestor_reparse(real):
        raise C.GamekitError("FORBIDDEN_PATH", "out-dir or an ancestor is a junction or symlink")
    for candidate in (resolved, real):
        if C.is_within(candidate, project.root):
            raise C.GamekitError("FORBIDDEN_PATH", "out-dir must be outside the project")
        reason = C.forbidden_reason(candidate)
        if reason:
            raise C.GamekitError("FORBIDDEN_PATH", reason)
    if real.exists() and not real.is_dir():
        raise C.GamekitError("BAD_PATH", "out-dir exists and is not a directory")
    return real


def cache_matches(cache: dict[str, Any] | None, size: int, mtime_ns: int) -> bool:
    """Cheap status hint. Install and extract never treat this as proof of the archive bytes."""
    if not isinstance(cache, dict):
        return False
    try:
        same_size = int(cache.get("size")) == int(size)
        same_mtime = int(cache.get("mtime_ns")) == int(mtime_ns)
    except (TypeError, ValueError):
        return False
    return same_size and same_mtime and cache.get("sha256") == ARCHIVE_SHA256


def _find_zip_member(names: Sequence[str], filename: str) -> str | None:
    preferred = "templates/" + filename
    if preferred in names:
        return preferred
    matches = [n for n in names if n == filename or n.replace("\\", "/").endswith("/" + filename)]
    if not matches:
        return None
    matches.sort(key=len)
    return matches[0]


def select_template_members(zip_names: Sequence[str], platform: str) -> list[tuple[str, str]]:
    """``(zip member, dest basename)`` for the requested platform, version.txt included."""
    platform = validate_template_platform(platform)
    plats = ("windows", "linux", "web") if platform == "all" else (platform,)
    wanted = ["version.txt"]
    for item in plats:
        wanted.extend(REQUIRED_MEMBERS[item])
        for optional in OPTIONAL_MEMBERS.get(item, ()):
            if _find_zip_member(zip_names, optional) is not None:
                wanted.append(optional)
    selected: list[tuple[str, str]] = []
    for filename in wanted:
        member = _find_zip_member(zip_names, filename)
        if member is None:
            raise C.GamekitError("TOOL_MISSING", f"templates archive has no {filename}")
        selected.append((member, filename))
    return selected


def _cfg_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_preset(index: int, preset: str, export_path: str) -> str:
    spec = PRESETS[validate_preset(preset)]
    path_text = export_path.replace("\\", "/")
    header = [
        f"[preset.{index}]",
        "",
        f"name={_cfg_string(spec['name'])}",
        f"platform={_cfg_string(spec['platform'])}",
        "runnable=true",
        "dedicated_server=false",
        'custom_features=""',
        'export_filter="all_resources"',
        'include_filter=""',
        'exclude_filter=""',
        f"export_path={_cfg_string(path_text)}",
        "patch_list=PackedStringArray()",
        'encryption_include_filters=""',
        'encryption_exclude_filters=""',
        "encrypt_pck=false",
        "encrypt_directory=false",
        "script_export_mode=2",
        "",
        f"[preset.{index}.options]",
        "",
    ]
    options = _WEB_OPTIONS if preset == "web" else _PC_OPTIONS
    header.extend(f"{key}={value}" for key, value in options)
    header.append("")
    return "\n".join(header)


def _preset_table(text: str) -> tuple[set[int], dict[int, dict[str, str]], dict[int, list[str]]]:
    used: set[int] = set()
    fields: dict[int, dict[str, str]] = {}
    options: dict[int, list[str]] = {}
    mode: tuple[str, int] | None = None
    for line in text.splitlines():
        section = _SECTION_RE.fullmatch(line)
        if section:
            index = int(section.group(1))
            used.add(index)
            fields.setdefault(index, {})
            options.setdefault(index, [])
            mode = ("opt" if section.group(2) else "main", index)
            continue
        if mode is None:
            continue
        kind, index = mode
        if kind == "opt":
            options[index].append(line)
            continue
        assign = _ASSIGN_RE.fullmatch(line.strip())
        if not assign:
            continue
        raw = assign.group(2).strip()
        if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
            raw = raw[1:-1]
        fields[index][assign.group(1)] = raw
    return used, fields, options


def _threads_off(lines: Sequence[str]) -> bool:
    return any(re.fullmatch(r"variant/thread_support\s*=\s*false\s*", line.strip()) for line in lines)


def merge_presets(text: str, preset: str, export_path: str) -> tuple[str, bool]:
    """Append an HH preset if missing. The original text is kept as a prefix.

    An existing HH preset is left byte-for-byte alone. A same-name preset whose
    platform (or, for Web, thread support) does not match is a CONFLICT rather
    than a rewrite.
    """
    if not isinstance(text, str):
        raise C.GamekitError("BAD_REQUEST", "export_presets.cfg must be text")
    spec = PRESETS[validate_preset(preset)]
    used, fields, options = _preset_table(text)
    found = [index for index, info in fields.items() if info.get("name") == spec["name"]]
    if len(found) > 1:
        raise C.GamekitError("CONFLICT", f"preset name {spec['name']!r} appears more than once")
    if found:
        index = found[0]
        platform = fields[index].get("platform")
        if platform != spec["platform"]:
            raise C.GamekitError(
                "CONFLICT",
                f"preset {spec['name']!r} exists with platform {platform!r}, expected {spec['platform']!r}",
            )
        if preset == "web" and not _threads_off(options.get(index, [])):
            raise C.GamekitError(
                "CONFLICT",
                "preset 'HH Web' exists without variant/thread_support=false; gamekit will not rewrite it",
            )
        return text, False
    index = 0
    while index in used:
        index += 1
        if index > 64:
            raise C.GamekitError("VALIDATION_FAILED", "export_presets.cfg has too many presets")
    rendered = render_preset(index, preset, export_path)
    if text == "":
        return rendered, True
    if text.endswith("\n"):
        return text + rendered, True
    newline = "\r\n" if "\r\n" in text else "\n"
    return text + newline + rendered, True


# ---------------------------------------------------------------- templates


def templates_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise C.GamekitError("TOOL_MISSING", "APPDATA is not set; Godot export templates have nowhere to go")
    return Path(appdata) / "Godot" / "export_templates" / C.GODOT_VERSION


def _archive_path() -> Path:
    return C.TOOLING_DIR / ARCHIVE_NAME


def _cache_path() -> Path:
    return templates_dir().parent / CACHE_NAME


def _read_cache(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = C.read_json(path)
    except C.GamekitError:
        return None
    return data if isinstance(data, dict) else None


def _verify_archive(*, must_hash: bool) -> dict[str, Any]:
    """Hash the pinned archive before install. A status check may skip the hash and say so."""
    archive = _archive_path()
    if not archive.is_file():
        raise C.GamekitError("TOOL_MISSING", f"export templates archive missing: {archive}")
    st = archive.stat()
    size = int(st.st_size)
    mtime_ns = int(st.st_mtime_ns)
    started = time.monotonic()
    cache = _read_cache(_cache_path())
    if not must_hash and cache_matches(cache, size, mtime_ns):
        return {
            "archive": str(archive),
            "archive_sha256": None if not isinstance(cache, dict) else cache.get("sha256"),
            "archive_size": size,
            "archive_cached": True,
            "archive_verified": False,
            "verify_seconds": round(time.monotonic() - started, 3),
        }
    digest = C.sha256_file(archive)
    if digest != ARCHIVE_SHA256:
        raise C.GamekitError(
            "VALIDATION_FAILED",
            "export templates archive sha256 mismatch",
            expected=ARCHIVE_SHA256,
            got=digest,
        )
    _cache_path().parent.mkdir(parents=True, exist_ok=True)
    C.atomic_write_json(
        _cache_path(),
        {
            "schema": "hh-gamekit-export-templates-1",
            "archive": archive.name,
            "size": size,
            "mtime_ns": mtime_ns,
            "sha256": digest,
            "verified_at": C.now_iso(),
        },
    )
    return {
        "archive": str(archive),
        "archive_sha256": digest,
        "archive_size": size,
        "archive_cached": False,
        "archive_verified": True,
        "verify_seconds": round(time.monotonic() - started, 3),
    }


def _version_ok(root: Path | None = None) -> bool:
    path = (root or templates_dir()) / "version.txt"
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    return text == VERSION_TEXT


def _platform_installed(platform: str, root: Path | None = None) -> bool:
    base = root or templates_dir()
    if not _version_ok(base):
        return False
    for name in REQUIRED_MEMBERS[platform]:
        path = base / name
        if not path.is_file() or path.stat().st_size <= 0:
            return False
    return True


def _member_rows(platform: str) -> list[dict[str, Any]]:
    root = templates_dir()
    names = ["version.txt", *REQUIRED_MEMBERS[platform], *OPTIONAL_MEMBERS.get(platform, ())]
    rows = []
    for name in names:
        path = root / name
        rows.append({"name": name, "present": path.is_file() and path.stat().st_size > 0,
                     "bytes": path.stat().st_size if path.is_file() else 0})
    return rows


@contextlib.contextmanager
def _templates_lock(wait_seconds: float = 900) -> Iterator[None]:
    path = templates_dir().parent / LOCK_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + wait_seconds
    payload = json.dumps({"pid": os.getpid(), "purpose": "export.templates", "at": C.now_iso()}).encode("utf-8")
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            holder: dict[str, Any] = {}
            with contextlib.suppress(OSError, ValueError):
                parsed = json.loads(path.read_text(encoding="utf-8") or "{}")
                if isinstance(parsed, dict):
                    holder = parsed
            pid = 0
            with contextlib.suppress(TypeError, ValueError):
                pid = int(holder.get("pid", 0) or 0)
            if not C._pid_alive(pid):
                with contextlib.suppress(OSError):
                    path.unlink()
                continue
            if time.monotonic() >= deadline:
                raise C.GamekitError("LOCKED", "export template install is in progress", holder=holder)
            time.sleep(0.2)
            continue
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
        break
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            path.unlink()


def _atomic_replace(tmp: Path, dest: Path) -> None:
    last: Exception | None = None
    for _ in range(8):
        try:
            os.replace(tmp, dest)
            return
        except PermissionError as exc:
            last = exc
            time.sleep(0.25)
    raise C.GamekitError("VALIDATION_FAILED", f"could not replace {dest.name}: {last}")


def _extract_member(zf: zipfile.ZipFile, info: zipfile.ZipInfo, dest: Path) -> None:
    if "/" in dest.name or "\\" in dest.name or dest.name in (".", ".."):
        raise C.GamekitError("BAD_PATH", f"refusing template name {dest.name!r}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.hhtmp-{os.getpid()}-{secrets.token_hex(3)}")
    try:
        with zf.open(info, "r") as src, open(tmp, "wb") as out:
            shutil.copyfileobj(src, out, length=1 << 20)
            out.flush()
            os.fsync(out.fileno())
        _atomic_replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()
    if not dest.is_file() or dest.stat().st_size != info.file_size:
        raise C.GamekitError("VALIDATION_FAILED", f"extracted size mismatch for {dest.name}")


def _member_sha256(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with zf.open(info, "r") as src:
        for chunk in iter(lambda: src.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _needs_extract(dest: Path, zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> bool:
    """Re-extract unless the file on disk has the same size and sha256 as the archive member."""
    if not dest.is_file():
        return True
    try:
        size = dest.stat().st_size
    except OSError:
        return True
    if size != info.file_size:
        return True
    return C.sha256_file(dest) != _member_sha256(zf, info)


def _install_members(platform: str) -> tuple[list[str], list[str]]:
    archive = _archive_path()
    extracted: list[str] = []
    skipped: list[str] = []
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        for member, filename in select_template_members(names, platform):
            info = zf.getinfo(member)
            dest = templates_dir() / filename
            if _needs_extract(dest, zf, info):
                _extract_member(zf, info, dest)
                extracted.append(filename)
            else:
                skipped.append(filename)
    if not _version_ok():
        found = (templates_dir() / "version.txt").read_text(encoding="utf-8").strip() if (templates_dir() / "version.txt").is_file() else ""
        raise C.GamekitError("VALIDATION_FAILED", f"template version.txt is {found!r}, expected {VERSION_TEXT}")
    return extracted, skipped


def _status_body(platform: str) -> dict[str, Any]:
    selected = ("windows", "linux", "web") if platform == "all" else (platform,)
    platforms = {}
    for item in ("windows", "linux", "web"):
        platforms[item] = {"installed": _platform_installed(item), "files": _member_rows(item)}
    version = VERSION_TEXT if _version_ok() else None
    return {
        "installed": all(platforms[item]["installed"] for item in selected),
        "version": version,
        "templates_dir": str(templates_dir()),
        "platforms": platforms,
    }


def templates(*, install: bool = False, platform: str = "all") -> dict[str, Any]:
    """Report template status, or install the requested platform slice from the pinned archive."""
    if not isinstance(install, bool):
        raise C.GamekitError("BAD_REQUEST", "install must be a boolean")
    platform = validate_template_platform(platform)
    started = time.monotonic()
    try:
        with _templates_lock():
            verified = _verify_archive(must_hash=install)
            extracted: list[str] = []
            skipped: list[str] = []
            extract_started = time.monotonic()
            if install:
                extracted, skipped = _install_members(platform)
            extract_seconds = round(time.monotonic() - extract_started, 3) if install else 0.0
            body = _status_body(platform)
    except OSError as exc:
        raise C.GamekitError("VALIDATION_FAILED", f"export templates filesystem error: {exc}") from exc
    out = {
        "ok": True,
        "action": "templates",
        "install": install,
        "platform": platform,
        "seconds": round(time.monotonic() - started, 3),
        "extract_seconds": extract_seconds,
        **verified,
        **body,
    }
    if install:
        out["extracted"] = extracted
        out["skipped"] = skipped
    return out


def _require_installed(preset: str) -> None:
    if _platform_installed(preset):
        return
    raise C.GamekitError(
        "TOOL_MISSING",
        f"{preset} export templates are not installed; run: hh export templates --install --platform {preset}",
        templates_dir=str(templates_dir()),
    )


# ---------------------------------------------------------------- export run


def _read_presets(path: Path) -> bytes:
    if not path.is_file():
        return b""
    return path.read_bytes()


def _decode_presets(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise C.GamekitError("VALIDATION_FAILED", f"export_presets.cfg is not utf-8: {exc}") from exc


def _write_exact(path: Path, text: str) -> None:
    data = text.encode("utf-8")
    C.atomic_write_bytes(path, data)
    if path.read_bytes() != data:
        raise C.GamekitError("STATE_CORRUPT", "export_presets.cfg readback mismatch")


def _require_main_scene(project: C.Project) -> str:
    path = project.root / "project.godot"
    if not path.is_file():
        raise C.GamekitError("NOT_FOUND", "project.godot is missing")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise C.GamekitError("VALIDATION_FAILED", f"project.godot is not utf-8: {exc}") from exc
    match = re.search(r'(?m)^run/main_scene="(res://[^"]+)"', text)
    if not match:
        raise C.GamekitError("VALIDATION_FAILED", "project.godot has no run/main_scene")
    scene = match.group(1)
    project.res_to_path(scene, must_exist=True)
    return scene


def _export_target(preset: str, out_dir: Path, name: str) -> Path:
    if preset == "web":
        return out_dir / "index.html"
    if preset == "windows":
        return out_dir / f"{name}.exe"
    return out_dir / f"{name}.x86_64"


def _min_bytes(path: Path) -> int:
    lower = path.name.lower()
    if lower.endswith(".exe") or lower.endswith(".x86_64"):
        return 1_000_000
    if lower.endswith(".wasm"):
        return 100_000
    return 64


def _file_record(path: Path) -> dict[str, Any]:
    return {"name": path.name, "path": str(path), "bytes": path.stat().st_size, "sha256": C.sha256_file(path)}


def _collect_outputs(preset: str, out_dir: Path, name: str, run: C.ProcessRun) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    paths = [out_dir / filename for filename in output_filenames(preset, name)]
    if preset == "linux" and not (paths[-1].is_file() and paths[-1].stat().st_size > 0):
        alt = out_dir / f"{name}.x86_64.pck"
        if alt.is_file():
            paths[-1] = alt
    missing = [p.name for p in paths if not (p.is_file() and p.stat().st_size >= _min_bytes(p))]
    if missing:
        present = sorted(p.name for p in out_dir.iterdir()) if out_dir.is_dir() else []
        raise C.GamekitError(
            "GODOT_FAILED",
            f"export did not produce {', '.join(missing)}",
            present=present,
            process=run.summary(),
            tail=(run.stdout + "\n" + run.stderr)[-2000:],
        )
    html = out_dir / "index.html"
    if preset == "web":
        sample = html.read_text(encoding="utf-8", errors="replace")[:8000].lower()
        if "godot" not in sample and "<canvas" not in sample:
            raise C.GamekitError("GODOT_FAILED", "index.html is not a Godot web shell", process=run.summary())
    records = [_file_record(p) for p in paths]
    prefix = "index" if preset == "web" else name
    required_names = {p.name for p in paths}
    extra = []
    for child in sorted(out_dir.iterdir()):
        if child.is_file() and child.name not in required_names and child.name.startswith(prefix):
            extra.append({"name": child.name, "bytes": child.stat().st_size})
    return records, extra


def _require_export_process(run: C.ProcessRun, what: str) -> None:
    tail = (run.stdout + "\n" + run.stderr)[-2000:]
    if run.timed_out:
        raise C.GamekitError("TIMEOUT", f"{what} timed out after {run.seconds:.0f}s", process=run.summary(), tail=tail)
    if run.exit_code != 0:
        raise C.GamekitError("GODOT_FAILED", f"{what} exited {run.exit_code}", process=run.summary(), tail=tail)


def _smoke_windows(exe: Path) -> dict[str, Any]:
    last_error = ""
    for attempt in range(1, 4):
        try:
            run = C.run_process([str(exe), "--headless", "--quit-after", "120"], timeout=SMOKE_TIMEOUT, cwd=exe.parent)
        except OSError as exc:
            last_error = str(exc)
            time.sleep(1.0)
            continue
        if run.exit_code == 0 and not run.timed_out:
            return {"exit_code": 0, "seconds": round(run.seconds, 2), "timed_out": False, "attempts": attempt}
        code = "TIMEOUT" if run.timed_out else "GODOT_FAILED"
        raise C.GamekitError(
            code,
            f"windows export smoke exited {run.exit_code}",
            process=run.summary(),
            tail=(run.stdout + "\n" + run.stderr)[-2000:],
        )
    raise C.GamekitError("GODOT_FAILED", f"windows export smoke could not start: {last_error}")


def _stage_dir(out_dir: Path) -> Path:
    """Fresh folder beside ``out_dir`` (same drive) so a failed export does not touch it."""
    parent = out_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    path = parent / f".hh-export-{os.getpid()}-{secrets.token_hex(4)}"
    path.mkdir()
    return path


def _rollback_publish(info: dict[str, Any]) -> None:
    """Put back files this publish moved and delete products it created."""
    out_dir: Path = info["out_dir"]
    for bak, dest in reversed(info["backups"]):
        if dest.exists():
            dest.unlink()
        if bak.exists():
            _atomic_replace(bak, dest)
    for path in info["new_files"]:
        if path.is_file():
            path.unlink()
    if info["created_dir"] and out_dir.is_dir() and not any(out_dir.iterdir()):
        with contextlib.suppress(OSError):
            out_dir.rmdir()
    backup_dir: Path = info["backup_dir"]
    if backup_dir.exists():
        shutil.rmtree(backup_dir, ignore_errors=True)


def _commit_publish(info: dict[str, Any]) -> None:
    backup_dir: Path = info["backup_dir"]
    if backup_dir.exists():
        shutil.rmtree(backup_dir, ignore_errors=True)


def _publish_stage(stage: Path, out_dir: Path) -> dict[str, Any]:
    """Move staged products into ``out_dir`` with ``os.replace``. Rolls back if a move fails."""
    children = list(stage.iterdir())
    if any(p.is_dir() for p in children):
        raise C.GamekitError("GODOT_FAILED", "export stage contains a subdirectory")
    files = sorted((p for p in children if p.is_file()), key=lambda p: p.name)
    if not files:
        raise C.GamekitError("GODOT_FAILED", "export stage is empty")
    digests = {p.name: C.sha256_file(p) for p in files}
    created_dir = not out_dir.exists()
    out_dir.mkdir(parents=True, exist_ok=True)
    new_files: list[Path] = []
    backups: list[tuple[Path, Path]] = []
    backup_dir = stage.parent / f"{stage.name}.bak"
    info = {
        "backup_dir": backup_dir,
        "backups": backups,
        "new_files": new_files,
        "out_dir": out_dir,
        "created_dir": created_dir,
    }
    try:
        for src in files:
            dest = out_dir / src.name
            existed = dest.exists()
            if existed:
                backup_dir.mkdir(parents=True, exist_ok=True)
                bak = backup_dir / src.name
                _atomic_replace(dest, bak)
                backups.append((bak, dest))
            _atomic_replace(src, dest)
            if not existed:
                new_files.append(dest)
            if not dest.is_file() or C.sha256_file(dest) != digests[src.name]:
                raise C.GamekitError("STATE_CORRUPT", f"moved {dest.name} does not match the staged bytes")
    except Exception:
        _rollback_publish(info)
        raise
    return info


def export_run(
    project: C.Project,
    preset: str,
    out_dir: str | Path,
    command_id: str,
    *,
    debug: bool = False,
    name: str = "Game",
    allow_open_editor: bool = False,
    timeout: float = EXPORT_TIMEOUT,
) -> dict[str, Any]:
    """Export ``preset`` into ``out_dir`` (outside the project) under the mutating contract.

    Godot writes a sibling temp folder. Products move into ``out_dir`` only after smoke and
    readback succeed. A failure deletes that temp folder and leaves ``out_dir`` as it was.
    """
    from . import scene as scene_mod

    command_id = C.validate_command_id(command_id)
    preset = validate_preset(preset)
    name = validate_name(name)
    if not isinstance(debug, bool) or not isinstance(allow_open_editor, bool):
        raise C.GamekitError("BAD_REQUEST", "debug and allow_open_editor must be booleans")
    out_dir = validate_out_dir(project, out_dir)
    spec = PRESETS[preset]
    target = _export_target(preset, out_dir, name)
    request_digest = C.digest({
        "kind": "export.run",
        "project_id": project.project_id,
        "preset": preset,
        "out_dir": str(out_dir),
        "debug": debug,
        "name": name,
    })
    journal = C.Journal(project)
    with C.project_lock(project, "export.run", wait_seconds=30):
        prior = journal.replay_or_conflict(command_id, request_digest)
        if prior is not None:
            return prior
        C.refuse_if_editor_open(project, allow_open_editor)
        _require_installed(preset)
        main_scene = _require_main_scene(project)
        presets_path = project.res_to_path("res://export_presets.cfg")
        old_bytes = _read_presets(presets_path)
        desired, changed = merge_presets(_decode_presets(old_bytes), preset, str(target))
        desired_bytes = desired.encode("utf-8")
        C.checkpoint(project, command_id, [presets_path])
        stage: Path | None = None
        published: dict[str, Any] | None = None
        try:
            if presets_path.is_file() and presets_path.read_bytes() != old_bytes:
                raise C.GamekitError("CONFLICT", "export_presets.cfg changed while the export lock was taken")
            if desired_bytes != old_bytes:
                _write_exact(presets_path, desired)
            imported = scene_mod.refresh_import(project.root)
            stage = _stage_dir(out_dir)
            stage_target = _export_target(preset, stage, name)
            flag = "--export-debug" if debug else "--export-release"
            run = C.run_godot(
                project.root,
                None,
                (),
                headless=True,
                timeout=timeout,
                extra=(flag, spec["name"], str(stage_target)),
            )
            _require_export_process(run, f"export {spec['name']}")
            # Godot fills missing preset options by rewriting the whole cfg. Put our text back so
            # presets this command did not create stay byte-for-byte as they were.
            if _read_presets(presets_path) != desired_bytes:
                _write_exact(presets_path, desired)
            files, extra_files = _collect_outputs(preset, stage, name, run)
            smoke = _smoke_windows(stage_target) if preset == "windows" else None
            published = _publish_stage(stage, out_dir)
            files, extra_files = _collect_outputs(preset, out_dir, name, run)
            _commit_publish(published)
            published = None
        except Exception as original:
            if published is not None:
                try:
                    _rollback_publish(published)
                except Exception as exc:
                    raise C.GamekitError(
                        "STATE_CORRUPT",
                        f"export failed ({original}) and out-dir cleanup failed ({exc})",
                    ) from original
            try:
                C.restore_checkpoint(project, command_id)
            except Exception as exc:
                raise C.GamekitError(
                    "STATE_CORRUPT",
                    f"export failed ({original}) and checkpoint restore failed ({exc})",
                ) from original
            raise
        finally:
            if stage is not None and stage.exists():
                shutil.rmtree(stage, ignore_errors=True)
        receipt = {
            "ok": True,
            "status": "COMMITTED",
            "kind": "export.run",
            "command_id": command_id,
            "project": project.project_id,
            "preset": preset,
            "preset_name": spec["name"],
            "platform": spec["platform"],
            "debug": debug,
            "name": name,
            "out_dir": str(out_dir),
            "main_scene": main_scene,
            "presets_changed": changed,
            "presets_sha256": C.sha256_bytes(desired_bytes),
            "templates_version": VERSION_TEXT,
            "files": files,
            "extra_files": extra_files,
            "smoke": smoke,
            "import": imported,
            "export_exit_code": run.exit_code,
            "export_seconds": round(run.seconds, 2),
            "warnings": run.warnings[:12],
            "errors": run.errors[:12],
            "at": C.now_iso(),
        }
        journal.append(command_id, request_digest, receipt)
        return receipt


# ---------------------------------------------------------------- CLI


def _cmd_templates(args: argparse.Namespace) -> dict[str, Any]:
    return templates(install=bool(args.install), platform=args.platform)


def _cmd_run(args: argparse.Namespace) -> dict[str, Any]:
    return export_run(
        C.get_project(args.project),
        args.preset,
        args.out_dir,
        args.command_id,
        debug=bool(args.debug),
        name=args.name,
        allow_open_editor=bool(args.allow_open_editor),
    )


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("export", help="install export templates and export a project")
    ps = p.add_subparsers(dest="action", required=True)
    t = ps.add_parser("templates", help="show or install the pinned 4.7.2 export templates")
    t.add_argument("--install", action="store_true", help="extract the templates Godot needs for the platform")
    t.add_argument("--platform", choices=list(TEMPLATE_PLATFORMS), default="all")
    t.set_defaults(func=_cmd_templates)
    r = ps.add_parser("run", help="export a registered project with an HH preset")
    r.add_argument("project")
    r.add_argument("--preset", required=True, choices=list(PRESETS))
    r.add_argument("--out-dir", required=True, help="directory outside the project")
    r.add_argument("--debug", action="store_true", help="use --export-debug instead of --export-release")
    r.add_argument("--name", default="Game", help="output basename for Windows and Linux (default Game)")
    r.add_argument("--command-id", required=True)
    r.add_argument("--allow-open-editor", action="store_true")
    r.set_defaults(func=_cmd_run)
