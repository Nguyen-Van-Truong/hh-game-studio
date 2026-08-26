#!/usr/bin/env python3
"""R9-WP2 shared package/install/doctor/rollback logic.

Does not tick the 20-8 plan. Does not start R9-WP3. Does not start Superfighter.
Does not tick G6 or GX. Does not invent an API key or a signing cert.
Unsigned internal builds only; public sign/publish is E3.
Current-user install. No admin. No online-latest bootstrap.
Stdlib only. Business logic lives here, not in .ps1 wrappers.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCHEMA = "hh-godot-studio-bundle/1"
INSTALL_SCHEMA = "hh-godot-studio-install/1"
SBOM_SCHEMA = "hh-godot-studio-sbom/1"
PRODUCT = "hh-godot-agent"
DEFAULT_VERSION = "0.9.2"
PINNED = "4.7.1-stable"
PINNED_VERSION = "4.7.1.stable.official.a13da4feb"
PINNED_NODE = "24.19.0"
PLUGIN_RES = "res://addons/hh_agent/plugin.cfg"
HERE = Path(__file__).resolve().parent
REPO_DEFAULT = HERE.parents[1]

ADMIN_NEEDLES = (
    "\\program files\\",
    "\\program files (x86)\\",
    "\\windows\\system32\\",
    "/program files/",
    "/windows/system32/",
)
SKIP_DIR_NAMES = {
    ".git",
    ".godot",
    "__pycache__",
    "node_modules",
    "target",
}
SKIP_SUFFIXES = {".pyc", ".partial", ".tmp"}
FORBIDDEN_FILE_NAMES = {
    ".env",
    "credentials.json",
    ".pfx",
}
FORBIDDEN_SUFFIXES = {".pfx", ".p12", ".token"}
FORBIDDEN_PARTS = {"evidence", "khobian.exe"}
REFUSE_LATEST = (
    "/releases/latest",
    "npx -y",
    "npm@latest",
    "godot@latest",
    "latest.stable",
)
TOOLS_SHIP = (
    "studio_bundle.py",
    "package.py",
    "install.py",
    "launch.py",
    "doctor.py",
    "doctor.ps1",
    "package.ps1",
    "install.ps1",
    "launch.ps1",
    "pin.json",
    "README.md",
)
TEXT_SUFFIXES = {
    ".py",
    ".ps1",
    ".md",
    ".txt",
    ".json",
    ".toml",
    ".gd",
    ".cfg",
    ".ts",
    ".js",
    ".cmd",
    ".bat",
}


class BundleError(RuntimeError):
    def __init__(self, message: str, *, do: str = "") -> None:
        super().__init__(message)
        self.do = do


def repo_root(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    env = os.environ.get("HH_STUDIO_REPO")
    if env:
        return Path(env).resolve()
    return REPO_DEFAULT


def default_install_root() -> Path:
    env = os.environ.get("HH_STUDIO_INSTALL_ROOT")
    if env:
        return Path(env).resolve()
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise BundleError(
            "LOCALAPPDATA missing",
            do="run as the current Windows user; do not invent a machine-wide path",
        )
    return Path(local) / "HHGodotAgent" / "install"


def addon_src(repo: Path) -> Path:
    return repo / "godot" / "plugin-project" / "addons" / "hh_agent"


def hash_file(path: Path) -> tuple[int, str, str]:
    sha256 = hashlib.sha256()
    sha512 = hashlib.sha512()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            sha256.update(chunk)
            sha512.update(chunk)
    return size, sha256.hexdigest(), sha512.hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def posix_rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def is_admin_path(path: Path) -> bool:
    blob = str(path.resolve()).replace("/", "\\").lower()
    if not blob.endswith("\\"):
        blob += "\\"
    return any(needle in blob for needle in ADMIN_NEEDLES)


def refuse_admin_dest(path: Path) -> None:
    if is_admin_path(path):
        raise BundleError(
            f"refusing admin/system path {path}",
            do="install under %LOCALAPPDATA%/HHGodotAgent (current user; no admin)",
        )


def node_bin() -> str:
    return "node.exe" if os.name == "nt" else "node"


def npm_bin() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def read_plugin_version(addon: Path) -> str:
    cfg = addon / "plugin.cfg"
    if not cfg.is_file():
        raise BundleError(
            "missing addon plugin.cfg",
            do="keep godot/plugin-project/addons/hh_agent/plugin.cfg in the tree",
        )
    match = re.search(r'(?m)^version="([^"]+)"', cfg.read_text(encoding="utf-8"))
    if not match:
        raise BundleError("plugin.cfg missing version", do="restore hh_agent plugin.cfg")
    return match.group(1)


def node_version() -> str | None:
    exe = shutil.which(node_bin())
    if not exe:
        return None
    proc = subprocess.run(
        [exe, "--version"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    line = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
    return line[0].strip() if line else ""


def skip_copy(path: Path, root: Path) -> bool:
    rel_parts = path.relative_to(root).parts if is_under(path, root) else path.parts
    if any(part in SKIP_DIR_NAMES for part in rel_parts):
        return True
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    name = path.name.lower()
    if name in FORBIDDEN_FILE_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
        return True
    lowered = "/".join(rel_parts).lower()
    if any(part in lowered for part in FORBIDDEN_PARTS):
        return True
    return False


def refuse_latest_blob(text: str, *, label: str) -> None:
    lowered = text.lower()
    if "refuse_url_substrings" in lowered or "does not use github `/releases/latest`" in lowered:
        return
    if "no online-latest" in lowered or "not use github `/releases/latest`" in lowered:
        return
    for needle in REFUSE_LATEST:
        if needle.lower() in lowered and "refuse" not in lowered and "do not" not in lowered:
            raise BundleError(
                f"{label} contains online-latest bootstrap {needle!r}",
                do="package exact pins only; do not use latest feeds",
            )


def copy_tree(src: Path, dest: Path, *, root_for_skip: Path | None = None) -> list[Path]:
    if not src.is_dir():
        raise BundleError(f"missing source tree {src}", do="build or restore that tree first")
    skip_root = root_for_skip or src
    copied: list[Path] = []
    dest.mkdir(parents=True, exist_ok=True)
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        if skip_copy(path, skip_root):
            continue
        rel = path.relative_to(src)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(target)
    return copied


def replace_dir(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    old = dest.with_name(dest.name + ".old")
    if old.exists():
        shutil.rmtree(old)
    tmp = dest.with_name(dest.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(src, tmp)
    if dest.exists():
        dest.replace(old)
    tmp.replace(dest)
    if old.exists():
        shutil.rmtree(old)


def host_sidecar_lookup_ok(text: str) -> bool:
    """Installed launcher must prefer bundle/sidecar/main.js over repo bridge/dist."""
    lowered = text.replace("\\", "/")
    has_bundled = "sidecar" in lowered and "main.js" in lowered
    return has_bundled and "existsSync" in text


def ensure_built(package_dir: Path, *, kind: str) -> Path:
    main_js = package_dir / "dist" / "main.js"
    mcp = package_dir / "dist" / "mcp_child.js"
    stale_host = False
    if kind == "host":
        if not mcp.is_file():
            stale_host = True
        else:
            stale_host = not host_sidecar_lookup_ok(mcp.read_text(encoding="utf-8", errors="replace"))
    if main_js.is_file() and not stale_host:
        return main_js
    npm = shutil.which(npm_bin())
    if not npm:
        raise BundleError(
            f"{kind} dist/main.js missing and npm is not on PATH",
            do=f"install Node {PINNED_NODE} exact (not latest), then npm ci && npm run build in {kind}/",
        )
    node_modules = package_dir / "node_modules"
    if not node_modules.is_dir():
        proc = subprocess.run(
            [npm, "ci", "--omit=dev"],
            cwd=str(package_dir),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        # DevDependencies include tsc; retry full lockfile ci if omit-dev left no compiler.
        if proc.returncode != 0 or not (package_dir / "node_modules" / "typescript").is_dir():
            proc = subprocess.run(
                [npm, "ci"],
                cwd=str(package_dir),
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        if proc.returncode != 0:
            raise BundleError(
                f"npm ci failed in {kind}: {proc.stderr or proc.stdout}",
                do="use the pinned lockfile; do not npm install latest",
            )
    proc = subprocess.run(
        [npm, "run", "build"],
        cwd=str(package_dir),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0 or not main_js.is_file():
        raise BundleError(
            f"npm run build failed in {kind}: {proc.stderr or proc.stdout}",
            do=f"fix {kind} TypeScript build; do not bootstrap latest packages",
        )
    return main_js


def write_licenses(dest: Path, repo: Path, addon_version: str, version: str) -> None:
    notice_src = repo / "docs" / "godot-agent" / "NOTICE"
    licenses = dest / "LICENSES"
    licenses.mkdir(parents=True, exist_ok=True)
    if notice_src.is_file():
        shutil.copy2(notice_src, dest / "NOTICE.md")
        shutil.copy2(notice_src, licenses / "HH-NOTICE.md")
    else:
        atomic_write_text(
            dest / "NOTICE.md",
            "HH Godot Agent Autopilot — in-house thin. Godot 4.7.1-stable is MIT.\n",
        )
    atomic_write_text(
        licenses / "README.txt",
        "\n".join(
            [
                "HH Godot Agent studio bundle licenses (exact pins, no latest feed)",
                "",
                f"bundle {PRODUCT} {version}",
                f"addon hh_agent {addon_version} — in-house thin (see NOTICE.md)",
                f"Godot Engine {PINNED} ({PINNED_VERSION}) — MIT; official binary pin, not vendored C++",
                f"Node.js {PINNED_NODE} — MIT; sidecar/host runtime pin",
                "TypeScript 5.9.3 — Apache-2.0 (compile-time only; not required at install)",
                "",
                "This bundle is unsigned. Public sign/publish is E3 and needs a user-supplied cert.",
                "Do not add a .pfx to the repo or the bundle.",
                "",
            ]
        )
        + "\n",
    )


def write_launcher_cmd(dest: Path) -> None:
    atomic_write_text(
        dest / "hh-godot-agent.cmd",
        "\n".join(
            [
                "@echo off",
                "setlocal",
                "set \"HERE=%~dp0\"",
                "if \"%~1\"==\"\" (",
                "  echo usage: hh-godot-agent.cmd ^<user-project^>",
                "  echo current-user launcher; does not require admin",
                "  exit /b 2",
                ")",
                "python \"%HERE%tools\\launch.py\" --project \"%~1\" --godot",
                "exit /b %ERRORLEVEL%",
                "",
            ]
        ),
    )


def iter_bundle_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name.endswith(".tmp"):
            continue
        files.append(path)
    files.sort(key=lambda p: posix_rel(root, p).lower())
    return files


CHECKSUM_LINE = re.compile(r"^(SHA256|SHA512)\s+([0-9a-f]{64,128})\s+(\S+)\s*$")


def parse_checksums(text: str) -> dict[str, dict[str, str]]:
    listed: dict[str, dict[str, str]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = CHECKSUM_LINE.match(line)
        if not match:
            raise BundleError(
                f"checksums.txt has a bad line: {line}",
                do="checksum reject; Observe/Doctor only; restore the official bundle",
            )
        kind, digest, rel = match.group(1).lower(), match.group(2), match.group(3)
        listed.setdefault(rel, {})[kind] = digest
    return listed


def write_manifest(root: Path, payload: dict[str, Any], files: list[Path]) -> dict[str, Any]:
    records: dict[str, dict[str, Any]] = {}
    for path in files:
        rel = posix_rel(root, path)
        if rel in {"manifest.json", "checksums.txt"}:
            continue
        size, sha256, sha512 = hash_file(path)
        records[rel] = {"bytes": size, "sha256": sha256, "sha512": sha512}
    payload["files"] = records
    atomic_write_json(root / "manifest.json", payload)
    checksum_lines = [
        f"# {PRODUCT} {payload['version']} checksums",
        "# SHA-256 / SHA-512 of every shipped file except this checksums.txt. Tamper = reject.",
        "# Includes sidecar/main.js and manifest.json. verify_bundle uses this file.",
    ]
    for path in iter_bundle_files(root):
        rel = posix_rel(root, path)
        if rel == "checksums.txt":
            continue
        _size, sha256, sha512 = hash_file(path)
        checksum_lines.append(f"SHA256  {sha256}  {rel}")
        checksum_lines.append(f"SHA512  {sha512}  {rel}")
    atomic_write_text(root / "checksums.txt", "\n".join(checksum_lines) + "\n")
    return payload


def verify_bundle(root: Path) -> dict[str, Any]:
    manifest_path = root / "manifest.json"
    checksums_path = root / "checksums.txt"
    if not manifest_path.is_file():
        raise BundleError(
            "bundle missing manifest.json",
            do="use an official package; checksum reject; Observe/Doctor only",
        )
    if not checksums_path.is_file():
        raise BundleError(
            "bundle missing checksums.txt",
            do="use an official package; checksum reject; Observe/Doctor only",
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA:
        raise BundleError(
            "bundle schema mismatch",
            do="use a bundle with schema hh-godot-studio-bundle/1",
        )
    if manifest.get("signing", {}).get("status") == "signed" and not manifest.get("signing", {}).get(
        "user_cert"
    ):
        raise BundleError(
            "signed bundle without user cert",
            do="E3: do not invent a cert; unsigned internal is allowed",
        )
    listed = parse_checksums(checksums_path.read_text(encoding="utf-8"))
    if not listed:
        raise BundleError("checksums.txt is empty", do="repackage; do not install")
    if "sidecar/main.js" not in listed:
        raise BundleError(
            "checksums.txt missing sidecar/main.js",
            do="checksum reject; Observe/Doctor only; restore the official bundle",
        )
    if "manifest.json" not in listed:
        raise BundleError(
            "checksums.txt missing manifest.json",
            do="checksum reject; Observe/Doctor only; restore the official bundle",
        )
    seen: set[str] = set()
    for path in iter_bundle_files(root):
        rel = posix_rel(root, path)
        if rel == "checksums.txt":
            continue
        seen.add(rel)
        rec = listed.get(rel)
        if rec is None:
            raise BundleError(
                f"extra file not in checksums.txt: {rel}",
                do="checksum reject; Observe/Doctor only; restore the official bundle",
            )
        _size, sha256, sha512 = hash_file(path)
        if rec.get("sha256") != sha256 or rec.get("sha512") != sha512:
            raise BundleError(
                f"tampered hash for {rel}",
                do="checksum reject; Observe/Doctor only; restore the official bundle and reinstall",
            )
    for rel in listed:
        if rel not in seen:
            raise BundleError(
                f"missing packaged file {rel}",
                do="checksum reject; Observe/Doctor only",
            )
    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    if not files:
        raise BundleError("bundle manifest has no files", do="repackage; do not install")
    if "sidecar/main.js" not in files:
        raise BundleError(
            "manifest missing sidecar/main.js",
            do="checksum reject; Observe/Doctor only; restore the official bundle",
        )
    for rel, rec in files.items():
        if rel in {"checksums.txt", "manifest.json"}:
            continue
        path = root.joinpath(*rel.split("/"))
        if not path.is_file():
            raise BundleError(
                f"missing packaged file {rel}",
                do="checksum reject; Observe/Doctor only",
            )
        size, sha256, sha512 = hash_file(path)
        if int(rec.get("bytes", -1)) != size or rec.get("sha256") != sha256 or rec.get("sha512") != sha512:
            raise BundleError(
                f"tampered hash for {rel}",
                do="checksum reject; Observe/Doctor only; restore the official bundle and reinstall",
            )
    return manifest


def build_package(repo: Path, out_dir: Path, version: str) -> dict[str, Any]:
    refuse_admin_dest(out_dir)
    if any(bad in version for bad in ("latest", "4.7.2", "4.8")):
        raise BundleError(
            f"refused bundle version {version!r}",
            do=f"use an exact studio version, Godot stays {PINNED}",
        )
    addon = addon_src(repo)
    if not addon.is_dir():
        raise BundleError("missing hh_agent addon", do="do not invent a second addon tree")
    addon_version = read_plugin_version(addon)
    pin_path = repo / "tools" / "godot" / "pin.json"
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    godot = pin.get("godot") if isinstance(pin.get("godot"), dict) else {}
    if godot.get("version_id") != PINNED_VERSION or godot.get("tag") != PINNED:
        raise BundleError("pin.json is not 4.7.1-stable", do="restore tools/godot/pin.json")
    ensure_built(repo / "bridge", kind="bridge")
    ensure_built(repo / "host", kind="host")

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    copy_tree(addon, out_dir / "addon" / "hh_agent")
    copy_tree(repo / "bridge" / "dist", out_dir / "sidecar")
    shutil.copy2(repo / "bridge" / "package.json", out_dir / "sidecar" / "package.json")
    generated = repo / "bridge" / "generated"
    if generated.is_dir():
        copy_tree(generated, out_dir / "sidecar" / "generated")
    copy_tree(repo / "host" / "dist", out_dir / "launcher")
    shutil.copy2(repo / "host" / "package.json", out_dir / "launcher" / "package.json")
    mcp_child = out_dir / "launcher" / "mcp_child.js"
    if not mcp_child.is_file():
        raise BundleError(
            "package missing launcher/mcp_child.js",
            do="rebuild host/; installed launcher must ship mcp_child.js",
        )
    if not host_sidecar_lookup_ok(mcp_child.read_text(encoding="utf-8", errors="replace")):
        raise BundleError(
            "launcher mcp_child.js does not look up bundled sidecar/main.js",
            do="rebuild host so the installed launcher starts bundle/sidecar/main.js, not repo bridge/dist",
        )
    shutil.copy2(pin_path, out_dir / "pin.json")
    lock = repo / ".hh-agent" / "capability-lock.json"
    if lock.is_file():
        shutil.copy2(lock, out_dir / "capability-lock.json")
    tools_dest = out_dir / "tools"
    tools_dest.mkdir(parents=True, exist_ok=True)
    for name in TOOLS_SHIP:
        src = HERE / name
        if src.is_file():
            shutil.copy2(src, tools_dest / name)
    install_doc = repo / "docs" / "godot-agent" / "INSTALL.md"
    if install_doc.is_file():
        (out_dir / "docs").mkdir(parents=True, exist_ok=True)
        shutil.copy2(install_doc, out_dir / "docs" / "INSTALL.md")
    write_licenses(out_dir, repo, addon_version, version)
    write_launcher_cmd(out_dir)
    atomic_write_text(out_dir / "version-stamp.txt", version + "\n")
    atomic_write_json(
        out_dir / "sbom.json",
        {
            "schema": SBOM_SCHEMA,
            "signing": "unsigned",
            "e3_public_release": False,
            "components": [
                {"name": "Godot Engine Standard", "version": PINNED, "version_id": PINNED_VERSION, "spdx": "MIT"},
                {"name": "Node.js", "version": PINNED_NODE, "spdx": "MIT"},
                {"name": "hh_agent", "version": addon_version, "note": "in-house thin"},
                {"name": "hh-godot-bridge", "path": "sidecar/"},
                {"name": "hh-godot-host", "path": "launcher/"},
            ],
        },
    )

    for path in iter_bundle_files(out_dir):
        if path.suffix.lower() in TEXT_SUFFIXES:
            refuse_latest_blob(path.read_text(encoding="utf-8", errors="replace"), label=posix_rel(out_dir, path))

    required = (
        "addon/hh_agent/plugin.cfg",
        "addon/hh_agent/plugin.gd",
        "sidecar/main.js",
        "sidecar/package.json",
        "launcher/main.js",
        "launcher/package.json",
        "pin.json",
        "NOTICE.md",
        "LICENSES/README.txt",
        "hh-godot-agent.cmd",
        "tools/install.py",
        "tools/launch.py",
        "tools/studio_bundle.py",
        "version-stamp.txt",
    )
    for rel in required:
        if not (out_dir / rel).is_file():
            raise BundleError(f"package missing {rel}", do="rebuild the bundle from the repo")

    payload = {
        "schema": SCHEMA,
        "product": PRODUCT,
        "version": version,
        "addon_version": addon_version,
        "godot": {"tag": PINNED, "version_id": PINNED_VERSION},
        "node": {"version": PINNED_NODE},
        "signing": {
            "status": "unsigned",
            "e3": True,
            "message": "unsigned internal build; public release requires a user-supplied cert",
        },
        "privileges": "current-user",
        "online_latest": False,
        "clean_vm": "unproven",
    }
    write_manifest(out_dir, payload, iter_bundle_files(out_dir))
    verify_bundle(out_dir)
    return json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))


def load_state(install_root: Path) -> dict[str, Any]:
    path = install_root / "state.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def save_state(install_root: Path, state: dict[str, Any]) -> None:
    state["schema"] = INSTALL_SCHEMA
    atomic_write_json(install_root / "state.json", state)


def _project_list(state: dict[str, Any]) -> list[str]:
    raw = state.get("user_projects")
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if item]


def install_bundle(bundle: Path, install_root: Path) -> dict[str, Any]:
    refuse_admin_dest(install_root)
    manifest = verify_bundle(bundle)
    current = install_root / "current"
    rollback = install_root / "rollback"
    state = load_state(install_root)
    if current.is_dir() and (current / "manifest.json").is_file():
        if rollback.exists():
            shutil.rmtree(rollback)
        shutil.copytree(current, rollback)
        state["previous_version"] = state.get("version") or read_stamp(current)
    replace_dir(bundle, current)
    verify_bundle(current)
    state.update(
        {
            "version": str(manifest.get("version")),
            "install_root": str(install_root.resolve()),
            "current": str(current.resolve()),
            "rollback": str(rollback.resolve()) if rollback.is_dir() else "",
            "signing": "unsigned",
            "privileges": "current-user",
            "user_projects": _project_list(state),
        }
    )
    save_state(install_root, state)
    return state


def read_stamp(root: Path) -> str:
    stamp = root / "version-stamp.txt"
    if stamp.is_file():
        return stamp.read_text(encoding="utf-8").strip()
    manifest = root / "manifest.json"
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return str(data.get("version") or "")
    return ""


def rollback_install(install_root: Path) -> dict[str, Any]:
    refuse_admin_dest(install_root)
    current = install_root / "current"
    rollback = install_root / "rollback"
    if not rollback.is_dir() or not (rollback / "manifest.json").is_file():
        raise BundleError(
            "no previous version to restore",
            do="rollback keeps one generation; keep the previous bundle if you need a longer history",
        )
    verify_bundle(rollback)
    swap = install_root / "swap-tmp"
    if swap.exists():
        shutil.rmtree(swap)
    if current.exists():
        current.replace(swap)
    rollback.replace(current)
    if swap.exists():
        swap.replace(rollback)
    verify_bundle(current)
    state = load_state(install_root)
    state["version"] = read_stamp(current)
    state["previous_version"] = read_stamp(rollback) if rollback.is_dir() else ""
    save_state(install_root, state)
    return state


def canonical_project_root(project: Path) -> str:
    text = str(project.resolve())
    if os.name == "nt" and len(text) >= 2 and text[1] == ":":
        text = text[0].upper() + text[1:]
    return text


def project_id_for(project: Path) -> str:
    return hashlib.sha256(canonical_project_root(project).encode("utf-8")).hexdigest()[:32]


def sessions_root() -> Path | None:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    return Path(local) / "HHGodotAgent" / "sessions"


def session_dir_for(project: Path) -> Path | None:
    root = sessions_root()
    if root is None:
        return None
    return root / project_id_for(project)


def _norm_root(value: str) -> str:
    return value.replace("\\", "/").rstrip("/").lower()


def purge_project_sessions(projects: list[Path]) -> list[str]:
    """Remove loopback session.json tokens for these user projects. Does not delete the game."""
    root = sessions_root()
    if root is None or not root.is_dir():
        return []
    wanted_ids = set()
    wanted_roots = set()
    for project in projects:
        try:
            wanted_ids.add(project_id_for(project))
            wanted_roots.add(_norm_root(canonical_project_root(project)))
        except OSError:
            continue
    removed: list[str] = []
    for child in list(root.iterdir()):
        desc = child / "session.json"
        if not desc.is_file():
            continue
        try:
            data = json.loads(desc.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        pid = str(data.get("project_id") or "")
        prow = _norm_root(str(data.get("project_root") or ""))
        if pid in wanted_ids or (prow and prow in wanted_roots):
            shutil.rmtree(child, ignore_errors=True)
            removed.append(str(desc))
    return removed


def leftover_session_tokens(projects: list[Path]) -> list[Path]:
    root = sessions_root()
    if root is None or not root.is_dir():
        return []
    wanted_ids = set()
    wanted_roots = set()
    for project in projects:
        try:
            wanted_ids.add(project_id_for(project))
            wanted_roots.add(_norm_root(canonical_project_root(project)))
        except OSError:
            continue
    hits: list[Path] = []
    for child in root.iterdir():
        desc = child / "session.json"
        if not desc.is_file():
            continue
        try:
            data = json.loads(desc.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        pid = str(data.get("project_id") or "")
        prow = _norm_root(str(data.get("project_root") or ""))
        token = str(data.get("token") or "")
        if (pid in wanted_ids or (prow and prow in wanted_roots)) and token:
            hits.append(desc)
    return hits


def uninstall(install_root: Path) -> list[str]:
    refuse_admin_dest(install_root)
    state = load_state(install_root)
    kept = []
    projects: list[Path] = []
    for raw in _project_list(state):
        project = Path(raw)
        projects.append(project)
        if project.exists():
            kept.append(str(project))
        try:
            resolved = project.resolve()
        except OSError:
            continue
        if resolved == install_root.resolve() or is_under(resolved, install_root):
            raise BundleError(
                "refusing uninstall because a user project lives under the install root",
                do="move the user project out of %LOCALAPPDATA%/HHGodotAgent/install first",
            )
    purge_project_sessions(projects)
    current = install_root / "current"
    rollback = install_root / "rollback"
    if current.exists():
        shutil.rmtree(current)
    if rollback.exists():
        shutil.rmtree(rollback)
    state_path = install_root / "state.json"
    if state_path.is_file():
        state_path.unlink()
    if install_root.is_dir() and not any(install_root.iterdir()):
        install_root.rmdir()
    return kept


def _enable_plugin_text(text: str) -> str:
    if PLUGIN_RES in text:
        return text
    plugin_line = f'enabled=PackedStringArray("{PLUGIN_RES}")'
    if "[editor_plugins]" not in text:
        body = text.rstrip() + "\n\n[editor_plugins]\n\n" + plugin_line + "\n"
        return body
    match = re.search(r'(?m)^enabled=PackedStringArray\((.*)\)\s*$', text)
    if not match:
        return text.replace("[editor_plugins]", "[editor_plugins]\n\n" + plugin_line, 1)
    inner = match.group(1).strip()
    if not inner:
        replacement = plugin_line
    else:
        replacement = f'enabled=PackedStringArray({inner}, "{PLUGIN_RES}")'
    return text[: match.start()] + replacement + text[match.end() :]


def write_min_project(project: Path, name: str) -> None:
    atomic_write_text(
        project / "project.godot",
        "\n".join(
            [
                "config_version=5",
                "",
                "[application]",
                "",
                f'config/name="{name}"',
                'config/features=PackedStringArray("4.7", "Forward Plus")',
                "",
                "[debug]",
                "",
                "gdscript/warnings/untyped_declaration=1",
                "gdscript/warnings/inferred_declaration=1",
                "",
                "[editor_plugins]",
                "",
                f'enabled=PackedStringArray("{PLUGIN_RES}")',
                "",
            ]
        )
        + "\n",
    )


def enable_project(project: Path, install_root: Path) -> Path:
    refuse_admin_dest(install_root)
    project = project.resolve()
    if is_under(project, install_root):
        raise BundleError(
            "user project must stay outside the install root",
            do="choose a Documents/dev folder; uninstall must not delete the game",
        )
    current = install_root / "current"
    addon_from = current / "addon" / "hh_agent"
    if not addon_from.is_dir():
        raise BundleError(
            "studio is not installed",
            do="python tools/godot/install.py install --from <bundle>",
        )
    verify_bundle(current)
    project.mkdir(parents=True, exist_ok=True)
    godot = project / "project.godot"
    if godot.is_file():
        atomic_write_text(godot, _enable_plugin_text(godot.read_text(encoding="utf-8")))
    else:
        write_min_project(project, project.name)
    copy_tree(addon_from, project / "addons" / "hh_agent")
    (project / "scenes").mkdir(parents=True, exist_ok=True)
    lock_src = current / "capability-lock.json"
    agent_dir = project / ".hh-agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    if lock_src.is_file() and not (agent_dir / "capability-lock.json").is_file():
        shutil.copy2(lock_src, agent_dir / "capability-lock.json")
    atomic_write_json(
        agent_dir / "studio-install.json",
        {
            "schema": INSTALL_SCHEMA,
            "install_root": str(install_root.resolve()),
            "version": read_stamp(current),
            "addon": "addons/hh_agent",
        },
    )
    state = load_state(install_root)
    projects = _project_list(state)
    key = str(project)
    if key not in projects:
        projects.append(key)
    state["user_projects"] = projects
    state["version"] = state.get("version") or read_stamp(current)
    save_state(install_root, state)
    return project / "addons" / "hh_agent" / "plugin.cfg"


def setup(bundle: Path, install_root: Path, project: Path) -> dict[str, Any]:
    state = install_bundle(bundle, install_root)
    enable_project(project, install_root)
    state = load_state(install_root)
    return state


def doctor_report(install_root: Path, project: Path | None = None) -> dict[str, Any]:
    actions: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []
    current = install_root / "current"
    report: dict[str, Any] = {
        "ok": False,
        "install_root": str(install_root),
        "version": "",
        "signing": "unsigned",
        "privileges": "current-user",
        "clean_vm": "unproven",
        "node": node_version(),
        "actions": actions,
        "errors": errors,
        "warnings": warnings,
    }
    if is_admin_path(install_root):
        errors.append("install root is an admin/system path")
        actions.append("move the install to %LOCALAPPDATA%/HHGodotAgent/install")
        return report
    if not current.is_dir():
        errors.append("studio current/ is missing")
        actions.append("python tools/godot/install.py install --from <bundle>")
        return report
    try:
        manifest = verify_bundle(current)
        report["version"] = str(manifest.get("version") or read_stamp(current))
    except BundleError as exc:
        errors.append(str(exc))
        actions.append(exc.do or "restore the official bundle; checksum reject; Observe/Doctor only")
        return report
    if not (current / "sidecar" / "main.js").is_file():
        errors.append("installed sidecar/main.js missing")
        actions.append("reinstall the official bundle")
    if not (current / "addon" / "hh_agent" / "plugin.cfg").is_file():
        errors.append("installed addon missing")
        actions.append("reinstall the official bundle")
    if not (current / "launcher" / "main.js").is_file():
        errors.append("installed launcher/main.js missing")
        actions.append("reinstall the official bundle")
    nv = report["node"]
    if nv is None:
        errors.append("Node is not on PATH")
        actions.append(f"install Node {PINNED_NODE} exact; do not use latest")
    elif nv.lstrip("v") != PINNED_NODE:
        warnings.append(f"Node {nv} != pin {PINNED_NODE}")
        actions.append(f"use Node {PINNED_NODE}; do not use latest")
    local = os.environ.get("LOCALAPPDATA")
    godot = None
    if local:
        godot = (
            Path(local)
            / "HHGodotAgent"
            / "tooling"
            / "godot-4.7.1-stable"
            / "bin"
            / "Godot_v4.7.1-stable_win64_console.exe"
        )
    if godot is None or not godot.is_file():
        warnings.append("pinned Godot console exe is not installed")
        actions.append("python tools/godot/doctor.py --install")
    if project is not None:
        plugin = project / "addons" / "hh_agent" / "plugin.cfg"
        if not plugin.is_file():
            errors.append("user project does not have hh_agent enabled")
            actions.append(
                f"python tools/godot/install.py enable-project --project {project}"
            )
        else:
            inst = current / "addon" / "hh_agent" / "plugin.cfg"
            if inst.is_file() and hash_file(plugin)[1] != hash_file(inst)[1]:
                warnings.append("project addon hash differs from the installed studio addon")
                actions.append(
                    f"python tools/godot/install.py enable-project --project {project}"
                )
        if is_under(project, install_root):
            errors.append("user project is inside the install root")
            actions.append("move the project out so uninstall cannot delete it")
    rollback = install_root / "rollback"
    if rollback.is_dir() and (rollback / "manifest.json").is_file():
        report["rollback"] = read_stamp(rollback)
    else:
        report["rollback"] = ""
    report["ok"] = not errors
    report["actions"] = actions
    report["errors"] = errors
    report["warnings"] = warnings
    return report


def sidecar_main(install_root: Path) -> Path:
    main = install_root / "current" / "sidecar" / "main.js"
    if not main.is_file():
        raise BundleError(
            "installed sidecar missing",
            do="python tools/godot/install.py install --from <bundle>",
        )
    verify_bundle(install_root / "current")
    return main


def launcher_main(install_root: Path) -> Path:
    main = install_root / "current" / "launcher" / "main.js"
    if not main.is_file():
        raise BundleError(
            "installed launcher missing",
            do="python tools/godot/install.py install --from <bundle>",
        )
    return main


def format_doctor(report: dict[str, Any]) -> str:
    lines = [
        f"doctor: pin godot={PINNED} node={PINNED_NODE} signing=unsigned privileges=current-user",
        "doctor: CLEAN_VM stays unproven",
        f"doctor: install {report.get('install_root')} version={report.get('version') or 'none'}",
    ]
    if report.get("node"):
        lines.append(f"doctor: PATH node {report['node']}")
    for item in report.get("errors") or []:
        lines.append(f"doctor: FAIL: {item}")
    for item in report.get("warnings") or []:
        lines.append(f"doctor: WARN: {item}")
    for item in report.get("actions") or []:
        lines.append(f"doctor: do: {item}")
    lines.append("doctor: PASS" if report.get("ok") else "doctor: FAIL")
    return "\n".join(lines)


def refuse_signing_request() -> None:
    raise BundleError(
        "signing/publish is E3",
        do="unsigned internal build is allowed; public release needs a user-supplied cert — do not invent one",
    )
