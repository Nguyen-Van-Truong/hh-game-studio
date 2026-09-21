"""Read-only exact S141 command/transport/journal attribution from retained data."""
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
HH3D = BASE.parents[2]
RAW = HH3D / "studio/.local/reviews/gt06-s141-formal-01/run-00-attempt-01"
PACKET = BASE / "terminal-01/packet"


def read(name):
    return json.loads((PACKET/"raw/run-00-attempt-01"/name).read_bytes())


def main():
    failure = read("child-failure.json")
    partial = failure["partial_command"]
    command = partial["commands"][-1]
    observation = read("http-phases-final.json")["observation"]
    starts, ends = {}, {}
    for event in observation["events"]:
        if event["kind"] == "enter":
            starts[event["span_id"]] = event
        elif event["kind"] == "exit":
            ends[event["span_id"]] = event
    calls = [event for event in starts.values() if event["phase"] == "client.call"
             and event["route"] == "commands" and event["span_id"] in ends
             and command["started_mono_us"]*1000 <= event["started_ns"]
             and ends[event["span_id"]]["timestamp_ns"] <= command["receipt_mono_us"]*1000]
    assert len(calls) == 1
    call = calls[0]
    ports = {(row["client_port"], row["server_port"]) for row in observation["events"]
             if row["root_id"] == call["root_id"] and row["client_port"] is not None}
    assert len(ports) == 1
    pair = next(iter(ports))
    servers = {row["root_id"] for row in observation["events"] if row["phase"] == "server.handle"
               and (row["client_port"], row["server_port"]) == pair
               and call["started_ns"] <= row["started_ns"] <= ends[call["span_id"]]["timestamp_ns"]}
    assert len(servers) == 1
    server_root = next(iter(servers))
    spans = []
    for sid, start in starts.items():
        if start["root_id"] not in (call["root_id"], server_root):
            continue
        assert sid in ends, "selected span missing exit"
        end = ends[sid]
        spans.append({"span_id": sid, "root_id": start["root_id"], "phase": start["phase"],
                      "start_ns": start["started_ns"], "end_ns": end["timestamp_ns"],
                      "wall_ms": (end["timestamp_ns"]-start["started_ns"])/1e6,
                      "outcome": end["outcome"]})
    history = RAW/"commands/commands.jsonl"
    history_sha = hashlib.sha256(history.read_bytes()).hexdigest()
    manifest = json.loads((PACKET/"manifest.json").read_bytes())
    pin = next(row for row in manifest["local_journal_inventory"] if row["source"].endswith("commands.jsonl"))
    assert pin["sha256"] == history_sha
    records = []
    for number, line in enumerate(history.read_bytes().splitlines(), 1):
        row = json.loads(line)
        # Journal checksum envelope contains the authoritative record.
        record = row.get("record", row)
        if record.get("command_id") == command["command_id"]:
            assert record["digest"] == command["request_digest"]
            records.append({"line": number, "status": record["status"], "receipt": record["receipt"]})
    assert len(records) == 2 and records[0]["status"] == "ACCEPTED_PENDING" and records[1]["status"] == "CANCELED"
    assert records[1]["receipt"]["code"] == "CANCELED_BEFORE_APPLY"
    result = {"authority": 0, "formal_acceptance": False, "eligible_for_dataset": False,
              "completed_batches": failure["completed_batches"], "failed_command": command,
              "transport_failure": partial["transport_failure"], "status_gap_ms": partial["max_status_gap_ms"],
              "client_root": call["root_id"], "server_root": server_root, "client_server_ports": pair,
              "clock": observation["clock"], "pid": observation["pid"], "spans": spans,
              "journal_sha256": history_sha, "journal_records": records,
              "first_lookup_failure": observation["first_failure"],
              "failures_by_route": observation["transport_failures_by_route"],
              "limits": ["Client admission remains UNKNOWN; later server admission is not a timely client receipt.",
                         "Server send returning does not establish that the client consumed the response.",
                         "Snapshot includes read/hash/metadata/fsync; this trace cannot distinguish them.",
                         "Editor target natural exit UNKNOWN; import wrapper cleanup receipt absent."]}
    with (BASE/"terminal-01/failure-analysis.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"completed_batches": failure["completed_batches"], "failed_command": command["command_id"],
                      "client_root": call["root_id"], "server_root": server_root, "journal_records": len(records)}))


if __name__ == "__main__":
    main()
