"""Coordinator-owned one-use refresh of the fixed GT06 execution binding.

This refresh is limited to a proven source dependency delta.  It preserves the
old metadata bytes, writes each new metadata file through a temporary sibling
and atomic replace, verifies the installed reader in this fresh interpreter,
and restores the exact old bytes if verification fails.  It does not start an
engine or alter the pinned GT05 manifest.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


BASE = Path(__file__).resolve().parent
PROJECT = next(parent for parent in BASE.parents if (parent / "studio").is_dir())
STUDIO = PROJECT / "studio"
sys.path.insert(0, str(PROJECT))
from studio.host.replay import execution_binding as binding  # noqa: E402
from studio.host.replay import execution_installed as installed  # noqa: E402


def encoded(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def atomic_replace(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.s146-", dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def read_metadata() -> dict[str, bytes]:
    return {
        installed.BINDING_PATH: (STUDIO / installed.BINDING_PATH).read_bytes(),
        installed.SELECTOR_PATH: (STUDIO / installed.SELECTOR_PATH).read_bytes(),
    }


def main() -> None:
    anchor = PROJECT / "zdoc/reviews/20260917-gt05-s63-audit/manifest.json"
    anchor_raw = binding._read(anchor, binding.MAX_BINDING_BYTES)
    if sha(anchor_raw) != binding.GT05_MANIFEST_SHA256:
        raise SystemExit("GT05 anchor hash changed")
    accepted = json.loads(anchor_raw.decode("utf-8"))["source_files"]

    old = read_metadata()
    old_hashes = {name: sha(raw) for name, raw in old.items()}
    old_document = json.loads(old[installed.BINDING_PATH].decode("utf-8"))
    old_files = dict(old_document["source_files"])

    names = set(installed._required_sources(STUDIO))
    for name in accepted:
        if not name.startswith(binding.GT05_SOURCE_PREFIX):
            raise SystemExit("GT05 source outside pinned studio domain")
        names.add(name[len(binding.GT05_SOURCE_PREFIX):])
    if names & installed.METADATA_PATHS:
        raise SystemExit("metadata entered source map")
    current = {
        name: sha(binding._read(STUDIO / name, binding.MAX_SOURCE_BYTES))
        for name in sorted(names)
    }
    changed = sorted(name for name in set(old_files) | set(current)
                     if old_files.get(name) != current.get(name))
    if changed != ["host/replay/verified_journal.py"]:
        raise SystemExit(f"unexpected binding delta: {changed!r}")

    new_binding = encoded({
        "schema": binding.SCHEMA,
        "accepted_gt05_manifest_sha256": binding.GT05_MANIFEST_SHA256,
        "source_files": current,
    })
    new_selector = encoded({
        "schema": installed.SELECTOR_SCHEMA,
        "binding_sha256": sha(new_binding),
    })

    (BASE / "old").mkdir(parents=True, exist_ok=True)
    for name, raw in old.items():
        (BASE / "old" / Path(name).name).write_bytes(raw)
    (BASE / "new").mkdir(parents=True, exist_ok=True)
    (BASE / "new" / "execution-source.json").write_bytes(new_binding)
    (BASE / "new" / "execution-current.json").write_bytes(new_selector)

    replaced = False
    try:
        # Replace binding first; selector still points to the old generation
        # until the second atomic replacement.  No runtime is launched here.
        atomic_replace(STUDIO / installed.BINDING_PATH, new_binding)
        atomic_replace(STUDIO / installed.SELECTOR_PATH, new_selector)
        replaced = True
        verified = installed.load_installed(STUDIO, accepted)
        expected = dict(current)
        expected.update(installed.selection_identity(STUDIO))
        if verified != dict(sorted(expected.items())):
            raise SystemExit("installed binding verification mismatch")
    except BaseException:
        # Restore exact bytes, again through atomic replacements.
        atomic_replace(STUDIO / installed.BINDING_PATH, old[installed.BINDING_PATH])
        atomic_replace(STUDIO / installed.SELECTOR_PATH, old[installed.SELECTOR_PATH])
        raise

    receipt = {
        "authority": 0,
        "formal_acceptance": False,
        "operation": "S146_INSTALLED_BINDING_REFRESH",
        "source_delta": changed,
        "source_count": len(current),
        "old_metadata_sha256": old_hashes,
        "new_metadata_sha256": {
            installed.BINDING_PATH: sha(new_binding),
            installed.SELECTOR_PATH: sha(new_selector),
        },
        "source_closure_sha256": sha(encoded(current)),
        "accepted_gt05_manifest_sha256": binding.GT05_MANIFEST_SHA256,
        "verified_execution_files": len(verified),
        "engine_runs": 0,
        "atomic_replace": True,
        "rollback_available": True,
    }
    (BASE / "refresh-receipt.json").write_bytes(encoded(receipt))
    print(json.dumps({"source_delta": changed, "source_count": len(current),
                      "verified_execution_files": len(verified),
                      "new_binding_sha256": sha(new_binding),
                      "new_selector_sha256": sha(new_selector)}))


if __name__ == "__main__":
    main()
