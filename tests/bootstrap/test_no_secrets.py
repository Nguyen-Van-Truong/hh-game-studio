#!/usr/bin/env python3
"""Git-ish scan: no credential-shaped secrets in the working tree.

Walks the repo; skips `.git`, `target`, `node_modules`, `.godot`.
Negative policy fixtures must not contain PAT-shaped blobs either.

Exit 0 = clean. Stdlib only. Do not use cargo.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "godot"))

import policy_validate  # noqa: E402

SKIP_DIR_NAMES = {".git", "target", "node_modules", ".godot"}
SKIP_SUFFIXES = {
    ".exe",
    ".dll",
    ".pdb",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".wav",
    ".ogg",
    ".mp3",
    ".zip",
    ".tpz",
    ".wasm",
    ".pyc",
    ".ico",
    ".bin",
}
MAX_BYTES = 2_000_000


def iter_repo_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        yield path


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def read_text_if_small(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:4096]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def main() -> int:
    hits: list[str] = []
    for path in iter_repo_files(REPO_ROOT):
        text = read_text_if_small(path)
        if text is None:
            continue
        for detail, line_no, snippet in policy_validate.find_secrets(text):
            hits.append(f"{rel(path)}:{line_no}: {detail}: {snippet}")

    if hits:
        print("FAIL: credential-shaped secret in tree", file=sys.stderr)
        for item in hits:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print("PASS: no credential-shaped secrets in scanned tree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
