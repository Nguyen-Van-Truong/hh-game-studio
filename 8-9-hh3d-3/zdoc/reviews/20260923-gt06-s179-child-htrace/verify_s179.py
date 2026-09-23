"""Read-only S179 target identity check. No engine launch or ownership claim."""
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent

def need(value, message):
    if not value:
        raise ValueError(message)

def inspect(result, stdout, debugger):
    child = result["child"]
    pid = child["pid"]
    need(type(pid) is int and pid > 0 and pid != result["wrapper"]["pid"], "distinct child PID")
    need(result["debugger"]["attached_pid"] == pid
         and child["parent_pid"] == result["wrapper"]["pid"], "attach binding")
    starts = re.findall(r"^S171_START pid=(\d+)$", stdout, re.M)
    need(starts == [str(pid)], "runtime PID")
    modules = re.findall(r"^ModLoad:\s+([0-9a-fA-F\x60]+)\s+([0-9a-fA-F\x60]+)\s+(.+)$", debugger, re.M)
    matched = [row for row in modules if row[2].strip().casefold() == child["executable"].casefold()]
    need(len(matched) == 1, "child executable module binding")
    need(child["executable"].endswith("Godot_v4.7.2-stable_win64.exe"), "engine image")
    lines = debugger.splitlines()
    counts = {marker: lines.count(marker) for marker in
              ("CDB_ATTACHED_CHILD", "NT_CREATE_BREAK", "CREATE2_BREAK", "CLOSE_BREAK")}
    need(counts["CDB_ATTACHED_CHILD"] == 1, "actual attach marker")
    need(counts["NT_CREATE_BREAK"] + counts["CREATE2_BREAK"] > 0
         and counts["CLOSE_BREAK"] > 0, "actual breakpoint hits")
    events = re.findall(r"Handle = (0x[0-9a-fA-F]+) - (OPEN|CLOSE)\s+"
                        r"Thread ID = (0x[0-9a-fA-F]+), Process ID = (0x[0-9a-fA-F]+)", debugger)
    own = [event for event in events if int(event[3], 16) == pid]
    need(bool(own), "child handle events")
    return {
        "schema": "HH-S179-DERIVED-1", "authority": 0, "gt06_acceptance": False, "engine_started": False,
        "run_id": result["run_id"], "attach_identity_observed": True,
        "breakpoint_hit_counts": counts, "distinct_handles_in_diff": sorted({event[0] for event in own}),
        "child_pid": pid, "wrapper_actual_exit": result["wrapper"]["exit"],
        "child_actual_exit": "UNKNOWN_NOT_INDEPENDENTLY_RETAINED",
        "debugger_actual_exit": result["debugger"]["exit"],
        "attribution": "UNKNOWN", "root_cause": "UNKNOWN",
        "cleanup_authority": "NO_JOB_OR_NATIVE_HANDLE_CLOSURE_PROOF",
        "limitations": [
            "No retained child process handle, creation-time binding or independent child exit receipt.",
            "No checked Job closure or native CloseHandle receipt in executed helper.",
            "Process-query errors map to False in helper; cleanup booleans alone do not prove absence.",
            "Exact-line hits used here; original substring flags also match echoed commands.",
            "Missing stack addresses do not prove PDB absence caused the failure.",
            "Diff handles not proven to be the fixture file or S153/S156 counter growth.",
            "The 60-second loop did not bound all CIM/helper waits; actual run lasted about 23s.",
        ],
    }

def current():
    return inspect(json.loads((HERE / "s179-child-attribution-result.json").read_bytes()),
                   (HERE / "wrapper.stdout.txt").read_text(),
                   (HERE / "cdb.stdout.txt").read_text())

if __name__ == "__main__":
    print(json.dumps(current(), indent=2))

