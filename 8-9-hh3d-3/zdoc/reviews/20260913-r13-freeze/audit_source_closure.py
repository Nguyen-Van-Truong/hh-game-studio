"""Read-only GT-01 source-closure audit.

The audit intentionally writes only its own sibling manifest/report.  It does
not import or execute the runner, Godot, Blender, or the installer.  Paths in
outputs are repository-relative and deterministic; host-specific roots are
never emitted.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
PRODUCT = OUT.parents[2]  # 8-9-hh3d-3
STUDIO = PRODUCT / "studio"
REPO = PRODUCT.parent

EXPECTED = [
    "studio/toolchain.lock.json",
    "studio/build/bootstrap/run_fixture.py",
    "studio/build/bootstrap/install_toolchain.py",
    "studio/build/bootstrap/verify_archive.py",
    "studio/fixtures/sample-game/project.godot",
    "studio/fixtures/sample-game/main.tscn",
    "studio/fixtures/sample-game/scripts/main.gd",
    "studio/fixtures/sample-game/scripts/main.gd.uid",
    "studio/fixtures/sample-game/scripts/trace.gd",
    "studio/fixtures/sample-game/scripts/trace.gd.uid",
    "studio/fixtures/sample-blender/create_fixture.py",
]
OPTIONAL_DOCS = [
    "studio/build/bootstrap/README.md",
    "studio/fixtures/sample-blender/README.md",
]
GENERATED_DIRS = {".godot", "__pycache__", ".local", "evidence"}
TEXT_SUFFIXES = {".py", ".gd", ".godot", ".tscn", ".uid", ".json", ".md", ".txt", ".toml", ".yml", ".yaml"}
# Require a concrete drive path or UNC share.  Bare ``\\\\`` literals in
# traversal guards are policy checks, not leaked host paths.
ABSOLUTE = re.compile(r"(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/][A-Za-z0-9._-]|\\\\[A-Za-z0-9._-]+[\\/][A-Za-z0-9._-]+|/(?:Users|home|root|tmp|var|opt|mnt|srv)/)")
SECRET = re.compile(r"(?i)(?:api[_-]?key|secret|password|private[_-]?key|access[_-]?token)\s*[:=]\s*['\"]([^'\"]{8,})['\"]")


def rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def identity(path: Path) -> dict:
    try:
        info = os.lstat(path)
    except OSError as exc:
        return {"exists": False, "error": type(exc).__name__}
    return {
        "exists": True,
        "regular": stat.S_ISREG(info.st_mode),
        "symlink": stat.S_ISLNK(info.st_mode),
        "reparse": bool(getattr(info, "st_file_attributes", 0) & 0x400),
        "hard_links": int(getattr(info, "st_nlink", 0)),
        "size_bytes": int(info.st_size),
    }


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def scan_text(path: Path) -> dict:
    result = {"absolute_path_markers": [], "secret_markers": [], "decode_error": None}
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return result
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        result["decode_error"] = "not_utf8"
        return result
    # Keep only line numbers and a stable class; never copy matching content.
    for number, line in enumerate(text.splitlines(), 1):
        if ABSOLUTE.search(line) and not re.search(r"https?://", line):
            result["absolute_path_markers"].append(number)
        if SECRET.search(line):
            result["secret_markers"].append(number)
    return result


def file_record(path: Path, required: bool) -> dict:
    item = {"path": rel(path), "required": required}
    item.update(identity(path))
    if item.get("exists") and item.get("regular") and not item.get("symlink") and not item.get("reparse"):
        try:
            item["sha256"] = digest(path)
            item.update(scan_text(path))
        except OSError as exc:
            item["read_error"] = type(exc).__name__
    return item


def main() -> int:
    records = [file_record(PRODUCT / p, True) for p in EXPECTED]
    docs = [file_record(PRODUCT / p, False) for p in OPTIONAL_DOCS]
    generated = []
    for directory, names, files in os.walk(STUDIO, followlinks=False):
        names[:] = sorted(names)
        files.sort()
        d = Path(directory)
        if d.name in GENERATED_DIRS or any(part in GENERATED_DIRS for part in d.relative_to(STUDIO).parts):
            if d.name in GENERATED_DIRS:
                generated.append({"path": rel(d), "kind": "generated_directory"})
            names[:] = []
            continue
        for name in files:
            p = d / name
            if name.endswith((".pyc", ".pyo", ".tmp", ".swp")) or name.startswith("~$"):
                generated.append({"path": rel(p), "kind": "generated_or_cache"})
    closure_scan = []
    for item in records:
        if item.get("exists") and item.get("regular") and item.get("sha256"):
            closure_scan.append({"path": item["path"], **{k: item.get(k, []) for k in ("absolute_path_markers", "secret_markers")}})
    gaps = []
    for item in records:
        if not item.get("exists"):
            gaps.append({"code": "MISSING_REQUIRED", "path": item["path"]})
        elif not item.get("regular") or item.get("symlink") or item.get("reparse") or item.get("hard_links") != 1:
            gaps.append({"code": "UNSAFE_FILE_IDENTITY", "path": item["path"]})
        elif item.get("read_error") or item.get("decode_error"):
            gaps.append({"code": "UNREADABLE_SOURCE", "path": item["path"]})
    for item in closure_scan:
        if item["absolute_path_markers"]:
            gaps.append({"code": "ABSOLUTE_PATH_MARKER", "path": item["path"], "lines": item["absolute_path_markers"]})
        if item["secret_markers"]:
            gaps.append({"code": "SECRET_MARKER", "path": item["path"], "lines": item["secret_markers"]})
    for item in generated:
        if item["kind"] == "generated_or_cache":
            gaps.append({"code": "GENERATED_FILE_PRESENT", "path": item["path"]})
    payload = {
        "schema": "HH3D-GT01-SOURCE-CLOSURE-AUDIT-1",
        "status": "GAP" if gaps else "CANDIDATE",
        "scope": "GT-01 runner/bootstrap/sample fixtures",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "required_files": records,
        "optional_documentation": docs,
        "generated_observed": generated,
        "text_scan": closure_scan,
        "gaps": gaps,
        "limits": [
            "read-only lexical/lstat/hash audit; no race-proof open-handle guarantee",
            "does not execute Godot, Blender, installer, or runner",
            "does not prove archive/binary hashes or runtime dependency closure",
            "secret scan is conservative pattern matching, not credential validation",
            "generated/cache presence is a freeze gap but files are not deleted",
        ],
    }
    (OUT / "source-closure-manifest.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# GT-01 source-closure audit (r13)",
        "",
        f"Status: **{payload['status']}** (candidate evidence; not acceptance)",
        "",
        "This is a read-only audit of the files required to reproduce the GT-01 runner/bootstrap and both sample fixtures. Paths are repository-relative; no host root is recorded.",
        "",
        "## Required closure",
        "",
        "| Path | State | SHA-256 | Size |",
        "|---|---|---|---:|",
    ]
    for item in records:
        state = "OK" if item.get("sha256") and item.get("hard_links") == 1 else "MISSING/UNSAFE"
        lines.append(f"| `{item['path']}` | {state} | `{item.get('sha256', '-')}` | {item.get('size_bytes', '-')} |")
    lines += ["", "## Freeze gaps", ""]
    if gaps:
        for gap in gaps:
            suffix = f" (lines {','.join(map(str, gap['lines']))})" if "lines" in gap else ""
            lines.append(f"- **{gap['code']}**: `{gap['path']}`{suffix}")
    else:
        lines.append("- None detected by this audit.")
    lines += ["", "## Generated/cache observations", ""]
    if generated:
        lines.extend(f"- `{x['path']}` ({x['kind']})" for x in generated)
    else:
        lines.append("- None observed under `studio/`.")
    lines += ["", "## Limits and next gate", "", *[f"- {x}" for x in payload["limits"]], "", "GT-01 still requires one frozen source hash, official serial runtime evidence, archive/installer recovery evidence, TQ01/TX12/TX14 checks, and two independent critics. This report cannot tick the plan.", ""]
    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "required": len(records), "gaps": len(gaps), "output": "20260913-r13-freeze"}, sort_keys=True))
    return 0 if not gaps else 2


if __name__ == "__main__":
    raise SystemExit(main())
