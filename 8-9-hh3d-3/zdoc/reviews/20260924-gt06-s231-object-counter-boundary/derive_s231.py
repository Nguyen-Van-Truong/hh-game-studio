"""Derive S231 facts from the sealed S229 raw campaign without running an engine."""
from __future__ import annotations
import argparse, json
from pathlib import Path

def rows(raw: Path):
    root = raw / "run-00-attempt-01"
    out = []
    for path in sorted(root.glob("joint-*.json"), key=lambda p: int(p.stem.split("-")[1])):
        value = json.loads(path.read_text(encoding="utf-8"))
        out.append({
            "batch": value["index"],
            "objects": value["editor"]["native_observation"]["objects"]["value"],
            "resources": value["editor"]["native_observation"]["resources"]["value"],
            "editor_handles": value["editor"]["held_handles"]["value"],
            "host_handles": value["host"]["counters"]["held_handles"]["value"],
            "rss_bytes": value["editor"]["rss_bytes"]["value"],
            "host_effect_count": value["host_effect_count"],
            "status_gap_ms": value["barrier_receipt"]["max_status_gap_ms"],
        })
    return out

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw", type=Path)
    args = parser.parse_args()
    data = rows(args.raw)
    print(json.dumps(data, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
