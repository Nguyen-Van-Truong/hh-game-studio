"""Retain selected exact S140 diagnostic bytes; never promote them to a dataset."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import sys

BASE = Path(__file__).resolve().parent
HH3D = BASE.parents[2]
OUTPUT = BASE / "terminal-packet-01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main():
    OUTPUT.mkdir(exist_ok=False)
    rows = []
    inventory = []

    def copy(source, relative):
        target = OUTPUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        digest = sha(source)
        assert digest == sha(target)
        rows.append({"file": relative.as_posix(), "source": source.relative_to(HH3D).as_posix(),
                     "sha256": digest, "size_bytes": target.stat().st_size})

    for suffix in ("p01", "p02", "p03", "p04"):
        raw = HH3D / "studio/.local/reviews" / ("gt06-s140-memory-phase-" + suffix)
        missing = [name for name in ("diagnostic-summary.json", "phase-memory.json", "result.json",
                   "attempt/child-terminal-cleanup.json", "owned/process-exit.json") if not (raw/name).exists()]
        inventory.append({"run": raw.name, "missing_terminal_receipts": missing,
                          "formal_acceptance": False, "eligible_for_dataset": False})
        for path in sorted(raw.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(raw)
            # Keep payloads and process receipts; exclude live command journals,
            # caches, generated source and assets. Originals remain in raw.
            keep = len(rel.parts) == 1 or (
                rel.parts[0] == "owned" and len(rel.parts) == 2) or (
                rel.parts[0] == "attempt" and (len(rel.parts) == 2 or (
                    rel.parts[1] in ("editor-host", "import-host") and len(rel.parts) == 3))) or (
                rel.parts[:4] in (("attempt", "project", "benchmark", "input"),
                                  ("attempt", "project", "benchmark", "out")))
            if keep and path.suffix in (".json", ".txt"):
                copy(path, Path(suffix) / rel)
    sup = HH3D / "zdoc/reviews/20260920-gt06-s129-supervision"
    name = "gt06-s129-s140-memory-p04-supervisor"
    for group in ("runs", "tasks"):
        for path in sorted((sup/group/name).iterdir()):
            if path.is_file():
                copy(path, Path("supervision")/group/path.name)
    for name in ("analysis-p02.json", "analysis-p04.json"):
        copy(BASE/name, Path(name))
    write(OUTPUT/"attempt-inventory.json", {"authority": 0, "attempts": inventory,
          "p01_classification": "HELPER_COMPOSITION_FAILURE_BEFORE_ENGINE",
          "p03_classification": "INCOMPLETE_UNKNOWN_NO_TERMINAL_EXIT_OR_CLEANUP_PROOF"})
    rows.append({"file": "attempt-inventory.json", "source": "derived",
                 "sha256": sha(OUTPUT/"attempt-inventory.json"),
                 "size_bytes": (OUTPUT/"attempt-inventory.json").stat().st_size})
    manifest = {"schema": "HH-S140-SELECTED-EXACT-COPY-1", "authority": 0,
        "created_utc": datetime.now(timezone.utc).isoformat(), "formal_acceptance": False,
        "eligible_for_dataset": False, "files": rows,
        "exclusions": ["Command journals, caches, generated source/assets remain at original raw paths.",
                       "Selected payload closure only; not a self-contained final GT06 acceptance packet.",
                       "Missing target exits are UNKNOWN; owner cleanup cannot supply them."]}
    write(OUTPUT/"manifest.json", manifest)
    for row in rows:
        path = OUTPUT/row["file"]
        assert path.stat().st_size == row["size_bytes"] and sha(path) == row["sha256"]
    write(BASE/"packet-verification.json", {"files": len(rows), "missing": 0, "hash_mismatches": 0,
          "manifest_sha256": sha(OUTPUT/"manifest.json"), "formal_acceptance": False})
    print(json.dumps({"files": len(rows), "manifest_sha256": sha(OUTPUT/"manifest.json")}))


if __name__ == "__main__":
    main()
