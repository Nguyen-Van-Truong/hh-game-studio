"""One-use, coordinator-owned refresh for the GT07 installed source binding.

This repairs the stale GT06 generation after GT07 source changes.  It only
admits the pinned GT05 manifest plus the current installed dependency inventory,
pins the exact expected delta, and verifies the installed reader before leaving
the new generation in place.  It never launches an engine or changes the GT05
manifest.  A failed replace restores both metadata files byte-for-byte.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile


SOURCE = Path(__file__).resolve().parent
PROJECT = next(parent for parent in SOURCE.parents if (parent / "studio").is_dir())
STUDIO = PROJECT / "studio"
BASE = STUDIO / ".local/reviews/gt07-binding-refresh-20261005-02"
sys.path.insert(0, str(PROJECT))
from studio.host.replay import execution_binding as binding  # noqa: E402
from studio.host.replay import execution_installed as installed  # noqa: E402


OLD_BINDING_SHA256 = "8e7bf80e9c625f0b2106cea1e37cde688d1245896ee0b86b2c11ff2a0a6b4bff"
OLD_SELECTOR_SHA256 = "3948c161f96771b60e8b00ef41724ed8d65e50286595a7356aacbf05cc244685"
EXPECTED_SOURCE_COUNT = 233
EXPECTED_DELTA = (
    "host/blender/client_writer_owner.py",
    "host/core/custody.py",
    "host/core/private_events.py",
)


def encoded(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_file(path: Path, cap: int) -> bytes:
    return binding._read(path, cap)


def atomic_replace(path: Path, raw: bytes) -> None:
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.gt07-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def accepted_sources() -> dict[str, str]:
    anchor = PROJECT / "zdoc/reviews/20260917-gt05-s63-audit/manifest.json"
    raw = read_file(anchor, binding.MAX_BINDING_BYTES)
    if sha(raw) != binding.GT05_MANIFEST_SHA256:
        raise SystemExit("GT05_ANCHOR_CHANGED")
    document = binding._json_object(raw)
    source_files = document.get("source_files")
    if not isinstance(source_files, dict):
        raise SystemExit("GT05_SOURCE_MAP_INVALID")
    prefixed = binding._source_map(source_files)
    for name in prefixed:
        if not isinstance(name, str) or not name.startswith(binding.GT05_SOURCE_PREFIX):
            raise SystemExit("GT05_SOURCE_OUTSIDE_STUDIO")
    return prefixed


def current_map(accepted: dict[str, str]) -> dict[str, str]:
    names = set(installed._required_sources(STUDIO))
    names.update(name[len(binding.GT05_SOURCE_PREFIX):] for name in accepted)
    if names & installed.METADATA_PATHS:
        raise SystemExit("METADATA_IN_SOURCE_MAP")
    # _read rejects reparse points and verifies identity before and after read.
    result = {name: sha(read_file(STUDIO / name, binding.MAX_SOURCE_BYTES))
              for name in sorted(names)}
    result = binding._source_map(result)
    return result


def metadata() -> dict[str, bytes]:
    return {
        installed.BINDING_PATH: read_file(STUDIO / installed.BINDING_PATH,
                                          binding.MAX_BINDING_BYTES),
        installed.SELECTOR_PATH: read_file(STUDIO / installed.SELECTOR_PATH,
                                           binding.MAX_BINDING_BYTES),
    }


def main() -> None:
    marker = BASE / "refresh-started.json"
    try:
        with marker.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump({"authority": 0, "operation": "GT07_BINDING_REFRESH"}, stream)
            stream.write("\n")
    except FileExistsError:
        raise SystemExit("REFRESH_ALREADY_STARTED") from None

    old = metadata()
    if sha(old[installed.BINDING_PATH]) != OLD_BINDING_SHA256:
        raise SystemExit("OLD_BINDING_GENERATION_CHANGED")
    if sha(old[installed.SELECTOR_PATH]) != OLD_SELECTOR_SHA256:
        raise SystemExit("OLD_SELECTOR_GENERATION_CHANGED")
    old_document = binding._object(old[installed.BINDING_PATH])
    old_files = binding._source_map(old_document["source_files"])
    accepted = accepted_sources()
    current = current_map(accepted)
    changed = tuple(sorted(name for name in set(old_files) | set(current)
                           if old_files.get(name) != current.get(name)))
    if len(current) != EXPECTED_SOURCE_COUNT or changed != EXPECTED_DELTA:
        raise SystemExit(f"UNEXPECTED_SOURCE_DELTA count={len(current)} delta={changed!r}")

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
    (BASE / "new/execution-source.json").write_bytes(new_binding)
    (BASE / "new/execution-current.json").write_bytes(new_selector)

    try:
        # A reader between these replacements rejects the generation hash; it
        # can never accept a half-updated source map.  Failure restores bytes.
        atomic_replace(STUDIO / installed.BINDING_PATH, new_binding)
        atomic_replace(STUDIO / installed.SELECTOR_PATH, new_selector)
        verified = installed.load_installed(STUDIO, accepted)
        expected = dict(current)
        expected.update(installed.selection_identity(STUDIO))
        if verified != dict(sorted(expected.items())):
            raise SystemExit("INSTALLED_BINDING_VERIFICATION_MISMATCH")
    except BaseException:
        atomic_replace(STUDIO / installed.BINDING_PATH, old[installed.BINDING_PATH])
        atomic_replace(STUDIO / installed.SELECTOR_PATH, old[installed.SELECTOR_PATH])
        raise

    receipt = {
        "authority": 0,
        "formal_acceptance": False,
        "operation": "GT07_INSTALLED_BINDING_REFRESH",
        "old_metadata_sha256": {name: sha(raw) for name, raw in old.items()},
        "new_metadata_sha256": {
            installed.BINDING_PATH: sha(new_binding),
            installed.SELECTOR_PATH: sha(new_selector),
        },
        "source_delta": list(changed),
        "source_count": len(current),
        "source_closure_sha256": sha(encoded(current)),
        "accepted_gt05_manifest_sha256": binding.GT05_MANIFEST_SHA256,
        "verified_execution_files": len(verified),
        "engine_runs": 0,
        "rollback_available": True,
        "atomic_each_metadata_file": True,
    }
    (BASE / "refresh-receipt.json").write_bytes(encoded(receipt))
    print(json.dumps({key: value for key, value in receipt.items()
                      if key not in {"source_delta"}}, sort_keys=True))


if __name__ == "__main__":
    main()
