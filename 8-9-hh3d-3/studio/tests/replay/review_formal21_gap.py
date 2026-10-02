"""Offline verifier for the formal21 host command-lane status-gap boundary.

This tool reads preserved raw evidence only.  It never starts Godot, Docker,
or a benchmark campaign, and it deliberately does not infer a root cause.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA = "HH-GT06-FORMAL21-GAP-REVIEW-1"
REPLAY_SCHEMA = "HH-GT06-FORMAL21-GAP-REPLAY-1"
SCOPE = "host command-lane response progress; not editor UI heartbeat"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_commands(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    commands = value.get("commands")
    if not isinstance(commands, list) or not commands:
        raise ValueError("COMMANDS_MISSING")
    if any(not isinstance(command, dict) for command in commands):
        raise ValueError("COMMAND_ROW")
    return commands


def _gap(left: dict, right: dict) -> int:
    try:
        delta = int(right["ended_mono_us"]) - int(left["ended_mono_us"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("LOOKUP_TIMESTAMP") from error
    if delta < 0:
        raise ValueError("LOOKUP_CLOCK")
    return delta


def review(command_path: Path, *, command_suffix: str = ".153") -> dict:
    commands = _load_commands(command_path)
    candidates: list[dict] = []
    for command in commands:
        command_id = command.get("command_id")
        attempts = command.get("lookup_attempts")
        if not isinstance(command_id, str) or not command_id.endswith(command_suffix):
            continue
        if not isinstance(attempts, list) or len(attempts) < 2:
            continue
        previous = None
        for index, attempt in enumerate(attempts):
            if not isinstance(attempt, dict):
                raise ValueError("LOOKUP_ROW")
            if previous is not None:
                candidates.append({
                    "command_id": command_id,
                    "attempt_index_before": index - 1,
                    "attempt_index_after": index,
                    "gap_us": _gap(previous, attempt),
                    "status_before": previous.get("status"),
                    "status_after": attempt.get("status"),
                    "code_before": previous.get("code"),
                    "code_after": attempt.get("code"),
                    "transport_failure_before": previous.get("transport_failure"),
                    "transport_failure_after": attempt.get("transport_failure"),
                })
            previous = attempt
    if not candidates:
        raise ValueError("GAP_CANDIDATE_MISSING")
    largest = max(candidates, key=lambda item: item["gap_us"])
    return {
        "schema": SCHEMA,
        "formal_acceptance": False,
        "root_cause_proven": False,
        "status_gap_scope": SCOPE,
        "raw_command_json": str(command_path.resolve()),
        "raw_command_sha256": _sha256(command_path),
        "command_suffix": command_suffix,
        "candidate_count": len(candidates),
        "largest_gap": largest,
        "transport_failure_in_gap": bool(
            largest["transport_failure_before"]
            or largest["transport_failure_after"]
        ),
        "review_conclusion": (
            "The host command lane contains a monotonic lookup gap; the raw "
            "receipt has no transport failure in that interval. This is a "
            "diagnostic boundary only and does not identify a cause or change "
            "the formal PRODUCT_FAIL verdict."
        ),
    }


def replay(command_path: Path, *, command_suffix: str = ".153") -> dict:
    """Replay the preserved lookup timeline in memory, without waiting."""
    result = review(command_path, command_suffix=command_suffix)
    commands = _load_commands(command_path)
    command = next(
        command for command in commands
        if command.get("command_id") == result["largest_gap"]["command_id"]
    )
    timeline = []
    previous = None
    for index, attempt in enumerate(command["lookup_attempts"]):
        delta = None if previous is None else _gap(previous, attempt)
        timeline.append({
            "attempt_index": index,
            "ended_mono_us": int(attempt["ended_mono_us"]),
            "delta_from_previous_us": delta,
            "status": attempt.get("status"),
            "code": attempt.get("code"),
            "transport_failure": attempt.get("transport_failure"),
        })
        previous = attempt
    return {
        "schema": REPLAY_SCHEMA,
        "formal_acceptance": False,
        "root_cause_proven": False,
        "raw_command_json": str(command_path.resolve()),
        "raw_command_sha256": result["raw_command_sha256"],
        "command_id": result["largest_gap"]["command_id"],
        "timeline": timeline,
        "largest_gap_us": result["largest_gap"]["gap_us"],
        "replay_is_in_memory_only": True,
        "replay_conclusion": (
            "The preserved lookup sequence deterministically replays the same "
            "monotonic gap. It does not reproduce the scheduler or identify "
            "the cause, and it cannot change the formal verdict."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command_json", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replay-output", type=Path)
    args = parser.parse_args(argv)
    result = review(args.command_json)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    if args.replay_output is not None:
        replay_result = replay(args.command_json)
        args.replay_output.parent.mkdir(parents=True, exist_ok=True)
        with args.replay_output.open("x", encoding="utf-8") as stream:
            json.dump(replay_result, stream, sort_keys=True, indent=2)
            stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
