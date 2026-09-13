"""Generate and verify the complete, portable GT-01 source closure.

The command is read-only with respect to the product tree.  It writes only
files in this review directory and deliberately excludes caches, snapshots,
runtime output and host-specific paths.  The aggregate hash is independent of
timestamps and therefore can bind an official runtime evidence package.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OUT = Path(__file__).resolve().parent
PRODUCT = OUT.parents[2]  # 8-9-hh3d-3
REPO = PRODUCT.parent
ROOT_PREFIX = PRODUCT.name + "/"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_REL = re.compile(r"^[A-Za-z0-9._/-]+$")
ABSOLUTE = re.compile(r"(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/][A-Za-z0-9._-]|\\\\[A-Za-z0-9._-]+[\\/][A-Za-z0-9._-]+|/(?:Users|home|root|tmp|var|opt|mnt|srv)/)")
SECRET = re.compile(r"(?i)(?:api[_-]?key|secret|password|private[_-]?key|access[_-]?token)\s*[:=]\s*['\"]([^'\"]{8,})['\"]")
TEXT_SUFFIXES = {".py", ".gd", ".godot", ".tscn", ".uid", ".json", ".md", ".txt", ".toml", ".yml", ".yaml"}
EXCLUDED = (".godot/", ".local/", "__pycache__/", "evidence/", "*.pyc", "*.pyo", "*.tmp", "*.swp", "runtime output")

STATIC_FILES = [
    ("studio/toolchain.lock.json", "runtime"),
    ("studio/build/bootstrap/run_fixture.py", "runtime"),
    ("studio/build/bootstrap/install_toolchain.py", "runtime"),
    ("studio/build/bootstrap/verify_archive.py", "runtime"),
    ("studio/fixtures/sample-game/project.godot", "fixture"),
    ("studio/fixtures/sample-game/main.tscn", "fixture"),
    ("studio/fixtures/sample-game/scripts/main.gd", "fixture"),
    ("studio/fixtures/sample-game/scripts/main.gd.uid", "fixture"),
    ("studio/fixtures/sample-game/scripts/trace.gd", "fixture"),
    ("studio/fixtures/sample-game/scripts/trace.gd.uid", "fixture"),
    ("studio/fixtures/sample-blender/create_fixture.py", "fixture"),
    ("studio/build/bootstrap/README.md", "documentation"),
    ("studio/fixtures/sample-blender/README.md", "documentation"),
]


class ClosureError(ValueError):
    pass


def rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    try:
        info = os.lstat(path)
    except OSError as exc:
        return {"exists": False, "error": type(exc).__name__}
    return {"exists": True, "regular": stat.S_ISREG(info.st_mode),
            "symlink": stat.S_ISLNK(info.st_mode),
            "reparse": bool(getattr(info, "st_file_attributes", 0) & 0x400),
            "hard_links": int(getattr(info, "st_nlink", 0)),
            "size_bytes": int(info.st_size)}


def text_scan(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {"absolute_path_markers": [], "secret_markers": [], "decode_error": None}
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return out
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        out["decode_error"] = "not_utf8"
        return out
    for number, line in enumerate(lines, 1):
        # Regex policy tests intentionally contain examples such as /Users/;
        # they are not host paths and must not create a false freeze gap.
        policy_example = "assertNotRegex" in line or "ABSOLUTE" in line
        if not policy_example and "/fake/" not in line.lower() and ABSOLUTE.search(line) and not re.search(r"https?://", line):
            out["absolute_path_markers"].append(number)
        if SECRET.search(line):
            out["secret_markers"].append(number)
    return out


def record(relpath: str, role: str) -> dict[str, Any]:
    path = PRODUCT / relpath
    item: dict[str, Any] = {"path": ROOT_PREFIX + relpath, "role": role, "required": True}
    item.update(identity(path))
    if item.get("exists") and item.get("regular") and not item.get("symlink") and not item.get("reparse"):
        try:
            item["sha256"] = digest(path)
            item.update(text_scan(path))
        except OSError as exc:
            item["read_error"] = type(exc).__name__
    return item


def records_from_manifest(manifest: dict[str, Any]) -> dict[str, str]:
    rows = manifest.get("required_files")
    if not isinstance(rows, list) or not rows:
        raise ClosureError("required_files is missing or empty")
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ClosureError("malformed required file record")
        path = row.get("path")
        if not isinstance(path, str) or not path.startswith(ROOT_PREFIX) or not SAFE_REL.fullmatch(path):
            raise ClosureError("unsafe closure path")
        relpath = path[len(ROOT_PREFIX):]
        if not relpath or any(p in ("", ".", "..") for p in relpath.split("/")):
            raise ClosureError("traversal in closure path")
        value = row.get("sha256")
        if row.get("required") is not True or row.get("exists") is not True or row.get("regular") is not True:
            raise ClosureError("required file is absent or non-regular")
        if row.get("symlink") or row.get("reparse") or row.get("hard_links") != 1:
            raise ClosureError("unsafe file identity")
        if not isinstance(value, str) or not HEX64.fullmatch(value) or relpath in result:
            raise ClosureError("invalid or duplicate source hash")
        result[relpath] = value
    return result


def closure_hash(records: dict[str, str]) -> str:
    canonical = "".join(f"{ROOT_PREFIX}{path}\0{records[path]}\n" for path in sorted(records))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in items:
            if key in out:
                raise ClosureError(f"duplicate JSON key: {key}")
            out[key] = value
        return out
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except (OSError, UnicodeError, json.JSONDecodeError, ClosureError) as exc:
        raise ClosureError(f"invalid manifest: {type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise ClosureError("manifest root is not an object")
    return value


def generate(output: Path) -> dict[str, Any]:
    rows = [record(path, role) for path, role in STATIC_FILES]
    # Every bootstrap test is part of the reproducibility contract.  Sorting
    # gives a stable manifest when a new test is added.
    test_dir = PRODUCT / "studio/tests/bootstrap"
    for path in sorted(test_dir.glob("test*.py")):
        rows.append(record(path.relative_to(PRODUCT).as_posix(), "test"))
    gaps: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("exists"):
            gaps.append({"code": "MISSING_REQUIRED", "path": row["path"]})
        elif not row.get("regular") or row.get("symlink") or row.get("reparse") or row.get("hard_links") != 1:
            gaps.append({"code": "UNSAFE_FILE_IDENTITY", "path": row["path"]})
        elif row.get("read_error") or row.get("decode_error"):
            gaps.append({"code": "UNREADABLE_SOURCE", "path": row["path"]})
        elif row.get("absolute_path_markers") or row.get("secret_markers"):
            gaps.append({"code": "HOST_OR_SECRET_MARKER", "path": row["path"]})
    payload = {"schema": "HH3D-GT01-SOURCE-CLOSURE-2", "status": "GAP" if gaps else "CANDIDATE",
               "scope": "GT-01 runtime/bootstrap/fixtures/tests/documentation",
               "generated_at": datetime.now(timezone.utc).isoformat(),
               "required_files": rows, "excluded_policy": list(EXCLUDED), "gaps": gaps,
               "limits": ["read-only lstat/hash; no runtime execution", "official evidence and two critics remain required"]}
    if not gaps:
        payload["source_closure_sha256"] = closure_hash({r["path"][len(ROOT_PREFIX):]: r["sha256"] for r in rows})
    output.mkdir(parents=True, exist_ok=True)
    (output / "source-closure-manifest.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def verify(manifest_path: Path, repo: Path) -> dict[str, Any]:
    failures: list[str] = []
    try:
        manifest = load(manifest_path)
        if manifest.get("schema") != "HH3D-GT01-SOURCE-CLOSURE-2":
            raise ClosureError("unexpected schema")
        records = records_from_manifest(manifest)
        # A self-consistent but incomplete manifest must not pass.  Rebuild
        # the expected inventory from the frozen layout and require exact set
        # equality, including every bootstrap test present at verification.
        expected = {path for path, _ in STATIC_FILES}
        test_dir = repo / "studio/tests/bootstrap"
        if not test_dir.is_dir():
            raise ClosureError("bootstrap test directory is missing")
        expected.update(path.relative_to(repo).as_posix() for path in test_dir.glob("test*.py"))
        if set(records) != expected:
            missing = sorted(expected - set(records))
            extra = sorted(set(records) - expected)
            raise ClosureError(f"closure inventory mismatch (missing={missing}, extra={extra})")
        for relpath, expected in records.items():
            path = repo / relpath
            info = identity(path)
            if not info.get("exists") or not info.get("regular") or info.get("symlink") or info.get("reparse") or info.get("hard_links") != 1:
                raise ClosureError(f"unsafe or missing source: {relpath}")
            if digest(path) != expected:
                raise ClosureError(f"source hash mismatch: {relpath}")
        computed = closure_hash(records)
        if manifest.get("source_closure_sha256") != computed:
            raise ClosureError("source_closure_sha256 mismatch")
        if manifest.get("gaps") not in ([], None):
            raise ClosureError("manifest reports gaps")
    except ClosureError as exc:
        failures.append(str(exc))
    return {"schema": "HH3D-GT01-SOURCE-CLOSURE-VERIFY-1", "status": "READY" if not failures else "GAP", "source_closure_sha256": None if failures else computed, "failures": failures}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "verify"))
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--repo-root", type=Path, default=PRODUCT)
    args = parser.parse_args(argv)
    if args.command == "generate":
        result = generate(args.output)
        print(json.dumps({"status": result["status"], "required": len(result["required_files"]), "gaps": len(result["gaps"])}, sort_keys=True))
        return 0 if not result["gaps"] else 2
    result = verify(args.manifest or (args.output / "source-closure-manifest.json"), args.repo_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
