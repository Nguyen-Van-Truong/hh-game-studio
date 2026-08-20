#!/usr/bin/env python3
"""Install/verify the frozen Godot 4.7.1-stable pin. No global latest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
PIN_PATH = HERE / "pin.json"
REFUSE_EXIT = 2
HASH_EXIT = 3
VERSION_EXIT = 4
DOWNLOAD_EXIT = 5


def load_pin() -> dict[str, Any]:
    with PIN_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def cache_root(pin: dict[str, Any]) -> Path:
    local = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME")
    if not local:
        local = str(Path.home() / ".cache")
    dirname = pin["godot"]["cache_dirname"]
    return Path(local) / "HHGodotAgent" / "tooling" / dirname


def fail(code: int, message: str) -> None:
    print(f"doctor: FAIL: {message}", file=sys.stderr)
    raise SystemExit(code)


def refused_reason(text: str, pin: dict[str, Any]) -> str | None:
    lowered = text.lower().strip()
    if not lowered:
        return None
    for prefix in pin["godot"]["refuse_version_prefixes"]:
        if lowered.startswith(prefix.lower()) or prefix.lower() in lowered:
            return f"refused Godot channel/version {prefix!r} in {text!r}"
    for needle in pin["godot"]["refuse_url_substrings"]:
        if needle.lower() in lowered:
            return f"refused substring {needle!r} in {text!r}"
    return None


def assert_url_allowed(url: str, pin: dict[str, Any]) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("https",):
        fail(REFUSE_EXIT, f"refusing non-https URL: {url}")
    host = (parsed.netloc or "").lower()
    if host not in {"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"}:
        fail(REFUSE_EXIT, f"refusing non-allowlisted host {host!r}: {url}")
    reason = refused_reason(url, pin)
    if reason:
        fail(REFUSE_EXIT, reason)
    tag = pin["godot"]["tag"]
    if tag not in url:
        fail(REFUSE_EXIT, f"URL does not contain frozen tag {tag}: {url}")


def hash_file(path: Path) -> tuple[int, str, str]:
    sha256 = hashlib.sha256()
    sha512 = hashlib.sha512()
    size = 0
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            sha256.update(chunk)
            sha512.update(chunk)
    return size, sha256.hexdigest(), sha512.hexdigest()


def download(url: str, dest: Path, pin: dict[str, Any]) -> None:
    assert_url_allowed(url, pin)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".partial")
    curl = shutil_which("curl")
    print(f"doctor: downloading {url}")
    print(f"doctor: -> {dest}")
    if curl:
        cmd = [
            curl,
            "-L",
            "--fail",
            "--retry",
            "5",
            "--retry-all-errors",
            "-o",
            str(tmp),
            url,
        ]
        proc = subprocess.run(cmd, check=False)
        if proc.returncode != 0:
            if tmp.exists():
                tmp.unlink()
            fail(DOWNLOAD_EXIT, f"curl failed ({proc.returncode}) for {url}")
    else:
        import urllib.request

        try:
            with urllib.request.urlopen(url) as resp, tmp.open("wb") as out:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
        except Exception as exc:  # noqa: BLE001 — bootstrap; surface download errors
            if tmp.exists():
                tmp.unlink()
            fail(DOWNLOAD_EXIT, f"download failed: {exc}")
    tmp.replace(dest)


def shutil_which(name: str) -> str | None:
    from shutil import which

    found = which(name)
    if found:
        return found
    if os.name == "nt":
        return which(f"{name}.exe")
    return None


def verify_artifact(path: Path, spec: dict[str, Any], *, sha256_key: str = "sha256") -> tuple[int, str, str]:
    if not path.is_file():
        fail(HASH_EXIT, f"missing artifact {path}")
    size, sha256, sha512 = hash_file(path)
    expected_size = int(spec["bytes"])
    if size != expected_size:
        fail(HASH_EXIT, f"{path.name} size {size} != pinned {expected_size}")
    expected_sha512 = spec["sha512"].lower()
    if sha512 != expected_sha512:
        fail(HASH_EXIT, f"{path.name} SHA-512 mismatch")
    expected_sha256 = spec.get(sha256_key)
    if expected_sha256:
        if sha256 != expected_sha256.lower():
            fail(HASH_EXIT, f"{path.name} SHA-256 mismatch")
    print(f"doctor: OK {path.name}")
    print(f"  bytes    {size}")
    print(f"  sha256   {sha256}")
    print(f"  sha512   {sha512}")
    return size, sha256, sha512


def extract_editor(zip_path: Path, bin_dir: Path, spec: dict[str, Any]) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        wanted = {spec["console_exe"], spec["gui_exe"]}
        for name in names:
            base = Path(name).name
            if base in wanted:
                target = bin_dir / base
                with zf.open(name) as src, target.open("wb") as dst:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        dst.write(chunk)
    console = bin_dir / spec["console_exe"]
    gui = bin_dir / spec["gui_exe"]
    if not console.is_file():
        fail(VERSION_EXIT, f"zip missing console exe {spec['console_exe']}")
    if not gui.is_file():
        fail(VERSION_EXIT, f"zip missing gui exe {spec['gui_exe']}")
    return console


def godot_version(exe: Path) -> str:
    proc = subprocess.run(
        [str(exe), "--version"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    text = (proc.stdout or "") + (proc.stderr or "")
    line = text.strip().splitlines()[0].strip() if text.strip() else ""
    if proc.returncode != 0 and not line:
        fail(VERSION_EXIT, f"{exe.name} --version exited {proc.returncode}: {text!r}")
    return line


def ensure_not_forbidden_version(version: str, pin: dict[str, Any]) -> None:
    reason = refused_reason(version, pin)
    if reason:
        fail(REFUSE_EXIT, reason)
    expected = pin["godot"]["version_id"]
    if version != expected:
        fail(VERSION_EXIT, f"--version {version!r} != pin {expected!r}")


def write_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify/install frozen Godot 4.7.1-stable.")
    p.add_argument("--install", action="store_true", help="download missing artifacts into the cache")
    p.add_argument(
        "--requested-version",
        default="",
        help="caller-requested Godot version; any 4.7.2/4.8/latest/mono is refused",
    )
    p.add_argument("--skip-templates", action="store_true", help="do not download/hash export templates")
    p.add_argument("--print-bin", action="store_true", help="print console exe path on success")
    p.add_argument("--print-gui", action="store_true", help="print GUI exe path on success")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    pin = load_pin()
    godot = pin["godot"]
    expected = godot["version_id"]

    if args.requested_version:
        if args.requested_version.strip() != godot["tag"] and args.requested_version.strip() != expected:
            reason = refused_reason(args.requested_version, pin)
            if reason:
                fail(REFUSE_EXIT, reason)
            fail(
                REFUSE_EXIT,
                f"requested {args.requested_version!r} is not frozen pin {godot['tag']} ({expected})",
            )

    zip_spec = godot["downloads"]["win64_editor_zip"]
    tpz_spec = godot["downloads"]["export_templates_tpz"]
    assert_url_allowed(zip_spec["url"], pin)
    assert_url_allowed(tpz_spec["url"], pin)
    assert_url_allowed(godot["sums_url"], pin)

    root = cache_root(pin)
    downloads = root / "downloads"
    bin_dir = root / "bin"
    zip_path = downloads / zip_spec["file"]
    tpz_path = downloads / tpz_spec["file"]

    print(f"doctor: pin {expected}")
    print(f"doctor: cache {root}")

    if args.install:
        if not zip_path.is_file() or zip_path.stat().st_size != int(zip_spec["bytes"]):
            download(zip_spec["url"], zip_path, pin)
        if not args.skip_templates and (
            not tpz_path.is_file() or tpz_path.stat().st_size != int(tpz_spec["bytes"])
        ):
            download(tpz_spec["url"], tpz_path, pin)

    if not zip_path.is_file():
        fail(
            DOWNLOAD_EXIT,
            f"editor zip missing at {zip_path}; re-run with --install",
        )

    _, zip_sha256, zip_sha512 = verify_artifact(zip_path, zip_spec)
    console = extract_editor(zip_path, bin_dir, zip_spec)
    gui = bin_dir / zip_spec["gui_exe"]
    version = godot_version(console)
    print(f"doctor: --version {version}")
    ensure_not_forbidden_version(version, pin)

    templates_sha256 = None
    templates_sha512 = None
    if not args.skip_templates:
        if not tpz_path.is_file():
            fail(
                DOWNLOAD_EXIT,
                f"templates tpz missing at {tpz_path}; re-run with --install",
            )
        _, templates_sha256, templates_sha512 = verify_artifact(
            tpz_path, tpz_spec, sha256_key="sha256_github_digest"
        )
        github_digest = tpz_spec.get("sha256_github_digest", "").lower()
        if templates_sha256 == github_digest:
            print("doctor: templates SHA-256 matches GitHub digest (now locally verified)")
        else:
            fail(HASH_EXIT, "templates SHA-256 does not match recorded GitHub digest")

    state = {
        "version_id": version,
        "cache": str(root),
        "console_exe": str(console),
        "gui_exe": str(gui),
        "editor_zip": {
            "path": str(zip_path),
            "sha256": zip_sha256,
            "sha512": zip_sha512,
        },
        "export_templates": None
        if args.skip_templates
        else {
            "path": str(tpz_path),
            "sha256": templates_sha256,
            "sha512": templates_sha512,
        },
    }
    write_state(root / "state.json", state)
    print("doctor: PASS")
    if args.print_bin:
        print(console)
    if args.print_gui:
        print(gui)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        fail(1, f"uncaught {type(exc).__name__}: {exc}")
