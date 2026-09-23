"""Read-only S200/S202 archive and collector audit. Never starts an engine."""
import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def audit(stage, packet_name, terminal):
    raw = ROOT / f"studio/.local/reviews/gt06-s{stage}-cdb-handle-snapshot-01"
    archive = ROOT / f"studio/.local/archives/gt06-s{stage}-cdb-handle-snapshot-01-s{terminal}-terminal.zip"
    packet = ROOT / "zdoc/reviews" / packet_name
    manifest_bytes = (raw / "raw-manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    seal = json.loads((packet / "terminal-seal.json").read_bytes())
    assert sha(manifest_bytes) == seal["raw_manifest_sha256"]
    assert sha(archive.read_bytes()) == seal["archive_sha256"]
    with zipfile.ZipFile(archive) as zipped:
        names = zipped.namelist()
        expected = {item["path"] for item in manifest["files"]} | {"raw-manifest.json"}
        assert len(names) == len(set(names)) == len(expected), "Duplicate/missing ZIP entry"
        assert set(names) == expected
        assert zipped.read("raw-manifest.json") == manifest_bytes
        for item in manifest["files"]:
            contents = (raw / item["path"]).read_bytes()
            assert len(contents) == item["bytes"]
            assert sha(contents) == item["sha256"]
            assert zipped.read(item["path"]) == contents, item["path"]
    result = json.loads((raw / "result.json").read_bytes())
    capture = json.loads((raw / "editor-host/capture.json").read_bytes())
    driver = json.loads((raw / "driver-exit.json").read_bytes())
    assert not driver["timed_out"] and driver["exit_code"] == 0
    assert capture["actual_process_exit"] == result["target_actual_exit"]
    assert capture["actual_process_exit"]["exit_code"] == 0
    assert capture["wrapper_exit_code"] == result["helper_exit"] == 0
    for filename, digest in capture["artifacts"].items():
        assert sha((raw / "editor-host" / filename).read_bytes()) == digest
    assert result["job"] == capture["job"]
    assert result["job"]["active_count"] == 0 and result["job"]["closed"]
    assert result["job"]["zero_observed"] and not result["job"]["handle_retained"]
    assert not result["job"]["failed_operations"]
    cdb = (raw / "cdb.stdout.txt").read_text(encoding="utf-8")
    section = cdb.split("Outstanding handles opened since the previous snapshot:", 1)[1].split("Displayed ", 1)[0]
    records = re.findall(r"Handle = (0x[0-9a-f]+) - OPEN\s+Thread ID = (0x[0-9a-f]+), Process ID = (0x[0-9a-f]+)", section, re.I)
    residual = re.sub(r"Handle = 0x[0-9a-f]+ - OPEN|Thread ID = 0x[0-9a-f]+, Process ID = 0x[0-9a-f]+|[-\s]", "", section, flags=re.I)
    assert not residual, "Unexpected trace payload; inspect frames, do not label header-only"
    editor_bytes = (raw / "editor-host/stdout.txt").read_bytes()
    rows = []
    for line in editor_bytes.decode("utf-8").splitlines():
        match = re.fullmatch(r"(HH_S\d+_COMPLETE) (\{.*\})", line)
        if match:
            value = json.loads(match[2])
            assert value["pid"] == capture["actual_process_exit"]["pid"]
            rows.append({"marker": match[1], "payload": value})
    return {
        "run_id": result["run_id"], "authority": 0, "formal_acceptance": False,
        "archive_and_raw_byte_equal_entries": len(expected),
        "raw_manifest_sha256": sha(manifest_bytes), "archive_sha256": seal["archive_sha256"],
        "target_helper_exits": [capture["actual_process_exit"]["exit_code"], capture["wrapper_exit_code"]],
        "driver_exit": driver, "cdb_exit_reported_by_waiting_driver": result["cdb_exit"],
        "header_only_open_records": len(records), "creator_stack_address_frames": 0,
        "trace_process_ids": sorted({int(row[2], 16) for row in records}),
        "trace_thread_record_counts": dict(Counter(row[1] for row in records)),
        "new_history_entries": int(re.search(r"0x([0-9a-f]+) new stack traces", cdb, re.I)[1], 16),
        "invalid_store_message": "is not a valid store" in cdb,
        "reload_syntax_error": "Extra character error" in cdb,
        "completion_rows_derived_from_retained_stdout": rows,
        "original_collector_completion_rows": result["native_completion"],
        "editor_stdout_sha256": sha(editor_bytes),
        "conclusion": "Trace headers identify recorded PID/TID only. There are zero stack-address frames; missing symbols alone is not proven as their cause. Original collector failures remain unchanged.",
    }


if __name__ == "__main__":
    print(json.dumps({
        "schema": "HH-GT06-RETAINED-DIAGNOSTIC-AUDIT-1", "authority": 0,
        "formal_acceptance": False, "engine_started": False,
        "script_sha256": sha(Path(__file__).read_bytes()),
        "results": [audit(200, "20260924-gt06-s200-htrace-diff", 201), audit(202, "20260924-gt06-s202-symbol-htrace", 203)],
    }, sort_keys=True, indent=2))
