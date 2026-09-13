"""Generate and verify the complete, portable GT-01 source closure.

The command is read-only with respect to the product tree.  It writes only
files in this review directory and deliberately excludes caches, snapshots,
runtime output and host-specific paths.  The aggregate hash is independent of
timestamps and therefore can bind an official runtime evidence package.
"""
from __future__ import annotations

import argparse
import ast
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
ROOT_PREFIX = "8-9-hh3d-3/"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_REL = re.compile(r"^[A-Za-z0-9._/-]+$")
ABSOLUTE = re.compile(r"(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/][A-Za-z0-9._-]|\\\\[A-Za-z0-9._-]+[\\/][A-Za-z0-9._-]+|/(?:Users|home|root|tmp|var|opt|mnt|srv)/)")
SECRET = re.compile(r"(?i)(?:api[_-]?key|secret|password|private[_-]?key|access[_-]?token)\s*[:=]\s*['\"]([^'\"]{8,})['\"]")
TEXT_SUFFIXES = {".py", ".gd", ".godot", ".tscn", ".uid", ".json", ".md", ".txt", ".toml", ".yml", ".yaml"}
EXCLUDED_DIRS = {".godot", ".local", "__pycache__", "evidence"}
EXCLUDED = tuple(sorted(name + "/" for name in EXCLUDED_DIRS))

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
# This list is a minimum required baseline, not an inventory allowlist. Every
# other file under studio is discovered too, exactly as in run_fixture.


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


def _test_example_spans(source: str) -> list[tuple[int, int, int, int]]:
    """Allow only synthetic path literals and prefix-only regex test inputs."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    allowed: list[ast.Constant] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value.replace("\\", "/")
            if (re.fullmatch(r"(?i)[a-z]:/fake(?:/[A-Za-z0-9_.-]+)+", value)
                    and not any(part in (".", "..") for part in value.split("/"))):
                allowed.append(node)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "assertNotRegex" and len(node.args) > 1):
            pattern = node.args[1]
            if isinstance(pattern, ast.Constant) and isinstance(pattern.value, str):
                matches = list(ABSOLUTE.finditer(pattern.value))
                # A policy regex may list /Users/ or /home/ as prefixes. A
                # literal host name after that prefix is still a real marker.
                if matches and all(match.end() < len(pattern.value)
                                   and pattern.value[match.end()] in "|)$]"
                                   for match in matches):
                    allowed.append(pattern)
    # AST columns count UTF-8 bytes; the scan below uses character columns.
    lines = source.splitlines()
    def column(line: int, offset: int) -> int:
        return len(lines[line - 1].encode("utf-8")[:offset].decode("utf-8"))
    return [(node.lineno, column(node.lineno, node.col_offset),
             node.end_lineno, column(node.end_lineno, node.end_col_offset)) for node in allowed]


def text_scan(path: Path, *, test_examples: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {"absolute_path_markers": [], "secret_markers": [], "decode_error": None}
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return out
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        out["decode_error"] = "not_utf8"
        return out
    examples = _test_example_spans(source) if test_examples and path.suffix == ".py" else []
    for number, line in enumerate(source.splitlines(), 1):
        urls = [(m.start(), m.end()) for m in re.finditer(r"https?://[^\s\"'<>]+", line)]
        for match in ABSOLUTE.finditer(line):
            if any(start <= match.start() and match.end() <= end for start, end in urls):
                continue
            if any((start_line, start) <= (number, match.start())
                   and (number, match.end()) <= (end_line, end)
                   for start_line, start, end_line, end in examples):
                continue
            out["absolute_path_markers"].append(number)
            break
        if SECRET.search(line):
            out["secret_markers"].append(number)
    return out


def checked_ancestors(path: Path, *, include_self: bool = False) -> None:
    # abspath normalizes spelling without following a junction or symlink.
    absolute = Path(os.path.abspath(path))
    for parent in ([absolute] if include_self else []) + list(absolute.parents):
        try:
            info = os.lstat(parent)
        except OSError as exc:
            raise ClosureError("missing or unreadable source ancestor") from exc
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & 0x400):
            raise ClosureError("symlink/reparse or non-directory source ancestor")


def validate_relpath(path: Any) -> str:
    if not isinstance(path, str) or not path.startswith("studio/") or not SAFE_REL.fullmatch(path):
        raise ClosureError("unsafe closure path")
    parts = path.split("/")
    if any(part in ("", ".", "..") or part.endswith(".") for part in parts):
        raise ClosureError("traversal or ambiguous closure path")
    if any(part in EXCLUDED_DIRS for part in parts[1:]):
        raise ClosureError("excluded directory in closure path")
    return path


def role_for(path: str) -> str:
    if path.startswith("studio/tests/bootstrap/"):
        return "test"
    if Path(path).suffix.lower() in {".md", ".txt"}:
        return "documentation"
    if path.startswith("studio/fixtures/"):
        return "fixture"
    return "runtime"


def discover(repo: Path) -> dict[str, str]:
    """Mirror the runner's studio walk; reject unsafe entries before reading."""
    studio = repo / "studio"
    checked_ancestors(studio, include_self=True)
    expected = dict(STATIC_FILES)
    seen: set[str] = set()
    def walk_error(_error: OSError) -> None:
        raise ClosureError("unreadable source directory")
    for directory, names, files in os.walk(studio, followlinks=False, onerror=walk_error):
        root = Path(directory)
        names[:] = sorted(name for name in names if name not in EXCLUDED_DIRS)
        for name in names:
            validate_relpath((root / name).relative_to(repo).as_posix())
            checked_ancestors(root / name, include_self=True)
        for name in sorted(files):
            path = root / name
            relative = validate_relpath(path.relative_to(repo).as_posix())
            if relative.casefold() in seen:
                raise ClosureError("duplicate source path")
            seen.add(relative.casefold())
            # The runner rejects stray bytecode outside excluded caches.
            if path.suffix == ".pyc":
                raise ClosureError("unsupported bytecode in source closure")
            expected[relative] = role_for(relative)
    return dict(sorted(expected.items()))


def record(relpath: str, role: str, repo: Path = PRODUCT) -> dict[str, Any]:
    validate_relpath(relpath)
    path = repo / relpath
    item: dict[str, Any] = {"path": ROOT_PREFIX + relpath, "role": role, "required": True}
    item.update(identity(path))
    try:
        checked_ancestors(path)
    except ClosureError:
        item["unsafe_ancestor"] = True
    if (item.get("exists") and item.get("regular") and not item.get("symlink")
            and not item.get("reparse") and item.get("hard_links") == 1
            and not item.get("unsafe_ancestor")):
        try:
            item["sha256"] = digest(path)
            item.update(text_scan(path, test_examples=role == "test"))
        except OSError as exc:
            item["read_error"] = type(exc).__name__
    return item


def records_from_manifest(manifest: dict[str, Any]) -> dict[str, str]:
    if manifest.get("gaps") != []:
        raise ClosureError("manifest gaps must be an empty list")
    rows = manifest.get("required_files")
    if not isinstance(rows, list) or not rows:
        raise ClosureError("required_files is missing or empty")
    result: dict[str, str] = {}
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ClosureError("malformed required file record")
        path = row.get("path")
        if not isinstance(path, str) or not path.startswith(ROOT_PREFIX) or not SAFE_REL.fullmatch(path):
            raise ClosureError("unsafe closure path")
        relpath = validate_relpath(path[len(ROOT_PREFIX):])
        value = row.get("sha256")
        if row.get("required") is not True or row.get("exists") is not True or row.get("regular") is not True:
            raise ClosureError("required file is absent or non-regular")
        if (row.get("symlink") or row.get("reparse") or row.get("unsafe_ancestor")
                or type(row.get("hard_links")) is not int or row["hard_links"] != 1):
            raise ClosureError("unsafe file identity")
        if any(row.get(key) for key in ("read_error", "decode_error", "absolute_path_markers", "secret_markers")):
            raise ClosureError("manifest reports unreadable or unsafe source")
        if not isinstance(value, str) or not HEX64.fullmatch(value) or relpath.casefold() in seen:
            raise ClosureError("invalid or duplicate source hash")
        seen.add(relpath.casefold())
        result[relpath] = value
    return result


def closure_hash(records: dict[str, str]) -> str:
    if not isinstance(records, dict) or not records:
        raise ClosureError("source records are missing or empty")
    seen: set[str] = set()
    for path, value in records.items():
        validate_relpath(path)
        if (path.casefold() in seen or not isinstance(value, str) or not HEX64.fullmatch(value)):
            raise ClosureError("invalid or duplicate source hash")
        seen.add(path.casefold())
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


def generate(output: Path, repo: Path = PRODUCT) -> dict[str, Any]:
    gaps: list[dict[str, Any]] = []
    try:
        inventory = discover(repo)
    except ClosureError as exc:
        inventory = {}
        gaps.append({"code": "UNSAFE_INVENTORY", "reason": str(exc)})
    rows = [record(path, role, repo) for path, role in inventory.items()]
    for row in rows:
        if not row.get("exists"):
            gaps.append({"code": "MISSING_REQUIRED", "path": row["path"]})
        elif (not row.get("regular") or row.get("symlink") or row.get("reparse")
              or row.get("unsafe_ancestor") or type(row.get("hard_links")) is not int
              or row.get("hard_links") != 1):
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
        expected = set(discover(repo))
        if set(records) != expected:
            missing = sorted(expected - set(records))
            extra = sorted(set(records) - expected)
            raise ClosureError(f"closure inventory mismatch (missing={missing}, extra={extra})")
        for relpath, expected in records.items():
            path = repo / relpath
            checked_ancestors(path)
            info = identity(path)
            if not info.get("exists") or not info.get("regular") or info.get("symlink") or info.get("reparse") or info.get("hard_links") != 1:
                raise ClosureError(f"unsafe or missing source: {relpath}")
            if digest(path) != expected:
                raise ClosureError(f"source hash mismatch: {relpath}")
            scan = text_scan(path, test_examples=role_for(relpath) == "test")
            if scan["decode_error"] or scan["absolute_path_markers"] or scan["secret_markers"]:
                raise ClosureError(f"unreadable or unsafe source text: {relpath}")
        computed = closure_hash(records)
        if manifest.get("source_closure_sha256") != computed:
            raise ClosureError("source_closure_sha256 mismatch")
    except (ClosureError, OSError) as exc:
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
        result = generate(args.output, args.repo_root)
        print(json.dumps({"status": result["status"], "required": len(result["required_files"]), "gaps": len(result["gaps"])}, sort_keys=True))
        return 0 if not result["gaps"] else 2
    result = verify(args.manifest or (args.output / "source-closure-manifest.json"), args.repo_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
