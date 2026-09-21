"""Read-only phase comparison of retained S131 RSS evidence; no engine launch."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
RAW = BASE / "zdoc/reviews/20260920-gt06-s131-rss-failure/raw/attempt"
OUT = Path(__file__).resolve().parent / "rss-phase-analysis-s139.json"


def read(name: str) -> tuple[dict, str]:
    raw = (RAW / name).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def value(row: dict, *keys):
    for key in keys:
        row = row[key]
    return row


def main() -> int:
    rows = []
    for index in (4, 5):
        command, command_sha = read(f"command-{index:02d}.json")
        capture, capture_sha = read(f"batch-capture-{index:02d}.json")
        joint, joint_sha = read(f"joint-{index:02d}.json")
        rows.append({
            "batch": index,
            "command_after_host_rss": value(command, "memory_after", "counters", "rss_bytes", "value"),
            "joint_host_rss": value(joint, "host", "counters", "rss_bytes", "value"),
            "joint_editor_rss": value(joint, "editor", "rss_bytes", "value"),
            "native_json_bytes": value(capture, "native", "size_bytes"),
            "command_json_bytes": value(capture, "command", "size_bytes"),
            "effect_count": value(joint, "host_effect_count"),
            "journal_bytes": value(command, "journal_bytes"),
            "max_status_gap_ms": value(command, "max_status_gap_ms"),
            "command_sha256": command_sha,
            "batch_capture_sha256": capture_sha,
            "joint_sha256": joint_sha,
        })
    b4, b5 = rows
    result = {
        "schema": "HH-GT06-S139-RSS-PHASE-ANALYSIS-1",
        "authority": 0,
        "formal_acceptance": False,
        "source_run": "gt06-s129-host-attribution-03",
        "source_closure_sha256": "763191109cd7c7f63de499680291c6b99d77a501dad869078e6d77384ecb20b4",
        "rows": rows,
        "deltas_b5_minus_b4": {
            "command_after_host_rss": b5["command_after_host_rss"] - b4["command_after_host_rss"],
            "joint_host_rss": b5["joint_host_rss"] - b4["joint_host_rss"],
            "native_json_bytes": b5["native_json_bytes"] - b4["native_json_bytes"],
            "command_json_bytes": b5["command_json_bytes"] - b4["command_json_bytes"],
            "effect_count": b5["effect_count"] - b4["effect_count"],
            "journal_bytes": b5["journal_bytes"] - b4["journal_bytes"],
        },
        "interpretation": {
            "command_to_joint_b4_bytes": b4["joint_host_rss"] - b4["command_after_host_rss"],
            "command_to_joint_b5_bytes": b5["joint_host_rss"] - b5["command_after_host_rss"],
            "http_only_reproduction": False,
            "root_cause": "UNKNOWN",
            "leak_proven": False,
            "next_diagnostic": "Phase-resolved private-commit/page-fault/working-set samples around command-after, native parse, ACK/joint, post-assembly and GC; diagnostic-only.",
        },
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print(json.dumps({"written": OUT.as_posix(), "formal_acceptance": False,
                      "delta_joint_host_rss": result["deltas_b5_minus_b4"]["joint_host_rss"],
                      "delta_command_host_rss": result["deltas_b5_minus_b4"]["command_after_host_rss"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
