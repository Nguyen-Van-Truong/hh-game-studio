"""Seal the terminal S229 raw/supervisor evidence without changing it."""
from pathlib import Path
import hashlib
import json
import os
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "studio/.local/reviews/gt06-s229-formal-01"
SUPERVISOR = ROOT / "studio/.local/reviews/gt06-s229-formal-01-supervisor"
ARCHIVE = ROOT / "studio/.local/archives/gt06-s229-formal-01-s230-terminal.zip"
MANIFEST = RAW / "raw-manifest.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def regular(path: Path) -> None:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or info.st_nlink != 1 or not stat.S_ISREG(info.st_mode):
        raise RuntimeError(f"NON_REGULAR:{path}")


def files(root: Path, prefix: str):
    rows = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        regular(path)
        rel = path.relative_to(root).as_posix()
        rows.append((prefix + rel, path))
    return rows


def main() -> None:
    if MANIFEST.exists() or ARCHIVE.exists():
        raise RuntimeError("S230_ALREADY_SEALED")
    raw_rows = [(name, path) for name, path in files(RAW, "raw/")]
    raw_rows = [(name, path) for name, path in raw_rows if path != MANIFEST]
    supervisor_rows = files(SUPERVISOR, "supervisor/")
    rows = sorted(raw_rows + supervisor_rows)
    manifest = {
        "authority": 0,
        "formal_acceptance": False,
        "run_id": "gt06-s229-formal-01",
        "schema_id": "hh-studio.gt06-s229-raw-manifest",
        "schema_version": "1.0.0",
        "files": [
            {"bytes": path.stat().st_size, "path": name, "sha256": sha(path)}
            for name, path in rows
        ],
    }
    encoded = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    with MANIFEST.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    if MANIFEST.read_bytes() != encoded:
        raise RuntimeError("MANIFEST_READBACK")
    if sha(MANIFEST) != hashlib.sha256(encoded).hexdigest():
        raise RuntimeError("MANIFEST_HASH")

    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.write(MANIFEST, "raw-manifest.json")
        for name, path in rows:
            archive.write(path, name)
    if not ARCHIVE.is_file():
        raise RuntimeError("ARCHIVE_MISSING")
    result = {
        "archive_sha256": sha(ARCHIVE),
        "manifest_sha256": sha(MANIFEST),
        "archive_members": len(rows) + 1,
        "raw_entries": len(rows),
        "archive": str(ARCHIVE),
        "manifest": str(MANIFEST),
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
