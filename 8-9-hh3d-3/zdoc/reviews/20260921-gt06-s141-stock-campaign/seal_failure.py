"""Retain S141 terminal bytes without executing or retrying the campaign."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

BASE = Path(__file__).resolve().parent
HH3D = BASE.parents[2]
RAW = HH3D / "studio/.local/reviews/gt06-s141-formal-01"
TERMINAL = BASE / "terminal-01"
OUTPUT = TERMINAL / "packet"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main():
    OUTPUT.mkdir(exist_ok=False)
    rows = []
    excluded = []

    def retain(source, relative):
        target = OUTPUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        before = sha(source)
        shutil.copyfile(source, target)
        assert before == sha(source) == sha(target)
        rows.append({"file": relative.as_posix(), "source": source.relative_to(HH3D).as_posix(),
                     "sha256": before, "size_bytes": target.stat().st_size})

    for source in sorted(RAW.rglob("*")):
        if not source.is_file():
            continue
        rel = source.relative_to(RAW)
        parts = rel.parts
        keep = len(parts) == 1 or (parts[0] == "run-00-attempt-01" and (
            len(parts) == 2 or
            (len(parts) == 3 and parts[1] in ("host-owner", "editor-host", "import-host")) or
            parts[1:4] in (("project", "benchmark", "input"), ("project", "benchmark", "out"))))
        if keep and source.suffix in (".json", ".txt"):
            retain(source, Path("raw") / rel)
        elif "commands" in parts:
            excluded.append({"source": source.relative_to(HH3D).as_posix(), "sha256": sha(source),
                             "size_bytes": source.stat().st_size, "reason": "LOCAL_JOURNAL_NOT_PORTABLE_PAYLOAD"})
    supervisor = HH3D / "zdoc/reviews/20260920-gt06-s129-supervision"
    name = "gt06-s129-s141-formal-supervisor"
    for group in ("runs", "tasks"):
        for source in sorted((supervisor/group/name).iterdir()):
            if source.is_file():
                retain(source, Path("supervision")/group/source.name)
    for name in ("dispatch-once.json", "launcher-return.json", "freeze.json", "startup-liveness-01.json"):
        retain(BASE/name, Path("launcher")/name)
    retain(TERMINAL/"scheduler-terminal.json", Path("scheduler-terminal.json"))
    freeze = json.loads((BASE/"freeze.json").read_bytes())
    mismatches = [name for name, digest in freeze["files"].items() if sha(HH3D/name) != digest]
    assert not mismatches, mismatches
    write(OUTPUT/"source-pin-check.json", {"authority": 0, "files": len(freeze["files"]),
          "mismatches": mismatches, "checked_utc": datetime.now(timezone.utc).isoformat(),
          "scope": "Post-terminal static source/input check; no engine or acceptance"})
    rows.append({"file": "source-pin-check.json", "source": "derived",
                 "sha256": sha(OUTPUT/"source-pin-check.json"),
                 "size_bytes": (OUTPUT/"source-pin-check.json").stat().st_size})
    write(OUTPUT/"manifest.json", {"schema": "HH-S141-SELECTED-FAILURE-1", "authority": 0,
          "created_utc": datetime.now(timezone.utc).isoformat(), "eligible_for_dataset": False,
          "formal_acceptance": False, "files": rows, "local_journal_inventory": excluded,
          "exclusions": ["Caches, generated source/assets and source copies remain at raw/freeze paths.",
                         "This is a selected failure payload, not the final acceptance closure.",
                         "Editor natural exit UNKNOWN; cleanup cannot substitute for that receipt."]})
    for row in rows:
        path = OUTPUT/row["file"]
        assert path.stat().st_size == row["size_bytes"] and sha(path) == row["sha256"]
    result = {"files": len(rows), "missing": 0, "hash_mismatches": 0,
              "manifest_sha256": sha(OUTPUT/"manifest.json"), "formal_acceptance": False}
    write(TERMINAL/"packet-verification.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
