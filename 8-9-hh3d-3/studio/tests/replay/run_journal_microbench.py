"""Bounded O6.2 journal residency microbench (diagnostic only).

This is deliberately separate from the GT-06 campaign.  It exercises one
``VerifiedJournal`` in one process using a formal-like mix of committed and
pending commands, terminal completion, dedupe lookups, leases, and rejected
inputs.  Every mark is quiescent (GC is explicit here) and records private
bytes plus tracemalloc data.  The JSONL journal is retained for review; only
the disposable SQLite index is cleaned up by ``VerifiedJournal.close``.

The script does not claim an O1.4 or formal result.  The host private-byte
counter includes Python, SQLite, allocator and OS effects, while tracemalloc
only observes Python allocations.  A parent process must still capture the
actual process exit and decide whether this diagnostic warrants a formal run.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import sys
import time
import tracemalloc

STUDIO = Path(__file__).resolve().parents[2]
PRODUCT_ROOT = STUDIO.parent
sys.path.insert(0, str(PRODUCT_ROOT))

from studio.host.core.journal import JournalError
from studio.host.replay.process_probe import ProcessProbe, ProbeError
from studio.host.replay.verified_journal import VerifiedJournal
from studio.tests.replay.benchmark_profile import memory_gate_codes


SCHEMA = "HH-GT06-O6-RAM-MICROBENCH-2"
DEFAULT_COMMANDS = 35_000
DEFAULT_MARK = 1_000
PROJECT = "microbench"
DIGEST = "sha256:" + "a" * 64
WORKLOAD_CLASSES = ("inspect",) * 5 + ("rejected",) * 3 + ("admitted",) * 2
FULL_COMMANDS = 35_000
O14_BASELINE_COMMANDS = (3_000, 4_000, 5_000)
O14_MAIN_COMMANDS = tuple(range(6_000, 35_001, 1_000))
O14_EARLY_COMMANDS = tuple(range(6_000, 20_001, 1_000))
O14_LATE_COMMANDS = tuple(range(21_000, 35_001, 1_000))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_files() -> dict[str, str]:
    """Return the complete Python closure used by this direct bench.

    The closure is intentionally conservative: all host core/replay Python
    sources are hashed, together with this launcher.  Generated caches and
    evidence are excluded.
    """
    # The journal imports the protocol package through host/core/transport.
    # Include that local package in the manifest; otherwise a protocol-only
    # source edit could leave a stale diagnostic binding.
    roots = [STUDIO / "host" / "core", STUDIO / "host" / "replay",
             STUDIO / "protocol"]
    paths = {Path(__file__).resolve(),
             STUDIO / 'tests/replay/benchmark_profile.py'}
    for root in roots:
        paths.update(path for path in root.rglob("*.py") if path.is_file())
    result = {}
    for path in sorted(paths):
        relative = path.relative_to(STUDIO).as_posix()
        result[relative] = _sha256(path)
    return result


def source_closure(files: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(files.items()):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(value.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def private_bytes() -> dict[str, object]:
    """Read process private commit through the shared retained-handle probe."""
    if os.name == "nt":
        probe = None
        try:
            probe = ProcessProbe(os.getpid(), Path(sys.executable))
            # Use the retained-handle observation path shared by the formal
            # runner.  This binds the memory value and handle count to the
            # same identity-checked process handle and avoids the old
            # ctypes(GetCurrentProcess) shortcut that returned Win32 error 6.
            sample = probe.sample_with_handle_count()
            if sample is None or sample.get("private_commit_bytes") is None:
                return {"value": None, "unit": "bytes",
                        "method": "ProcessProbe.sample_with_handle_count.private_commit",
                        "error": "PROCESS_EXITED"}
            return {"value": int(sample["private_commit_bytes"]), "unit": "bytes",
                    "method": "ProcessProbe.sample_with_handle_count.private_commit",
                    "held_handles": int(sample["held_handles"]),
                    "handle_mono_us": int(sample["handle_mono_us"])}
        except (ProbeError, OSError) as error:
            return {"value": None, "unit": "bytes",
                    "method": "ProcessProbe.sample_with_handle_count.private_commit",
                    "error": str(error)}
        finally:
            if probe is not None:
                try:
                    probe.close()
                except BaseException as error:
                    # A failed native close is a retained cleanup owner and
                    # must make the memory observation unavailable.
                    return {"value": None, "unit": "bytes",
                            "method": "ProcessProbe.sample_with_handle_count.private_commit",
                            "error": f"PROBE_CLOSE:{error}"}
    status = Path("/proc") / str(os.getpid()) / "status"
    try:
        for line in status.read_text(encoding="utf-8").splitlines():
            if line.startswith("VmData:"):
                return {"value": int(line.split()[1]) * 1024, "unit": "bytes",
                        "method": "/proc/status VmData"}
    except (FileNotFoundError, OSError, ValueError, IndexError):
        pass
    return {"value": None, "unit": "bytes", "method": "unavailable"}


def _require_output(path: Path) -> Path:
    path = path.resolve()
    root = (STUDIO / ".local" / "reviews").resolve()
    if path != root and root not in path.parents:
        raise ValueError("output must be under studio/.local/reviews")
    if path.exists():
        raise ValueError("output already exists; use a fresh run id")
    path.mkdir(parents=True)
    return path


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _error(error: BaseException) -> dict[str, object]:
    code = getattr(error, "code", None)
    return {"type": type(error).__name__,
            "code": code if isinstance(code, str) else None,
            "message": str(error)}


def _slope(points: list[tuple[int, int | float]]) -> float | None:
    if len(points) < 2:
        return None
    x_bar = statistics.fmean(point[0] for point in points)
    y_bar = statistics.fmean(point[1] for point in points)
    denominator = sum((x - x_bar) ** 2 for x, _ in points)
    return None if denominator == 0 else sum((x - x_bar) * (y - y_bar)
                                             for x, y in points) / denominator


def _o1_4(marks: list[dict[str, object]]) -> dict[str, object]:
    by_command = {int(mark["commands"]): mark for mark in marks}
    expected = tuple(range(1000, FULL_COMMANDS + 1, 1000))
    missing_marks = [command for command in expected if command not in by_command]
    private_missing = [command for command in expected
                       if command in by_command and
                       by_command[command]["private_bytes"]["value"] is None]
    baseline = [by_command[commands]["private_bytes"]["value"]
                for commands in O14_BASELINE_COMMANDS
                if commands in by_command and by_command[commands]["private_bytes"]["value"] is not None]
    early = [by_command[commands]["private_bytes"]["value"]
             for commands in O14_EARLY_COMMANDS
             if commands in by_command and by_command[commands]["private_bytes"]["value"] is not None]
    late = [by_command[commands]["private_bytes"]["value"]
            for commands in O14_LATE_COMMANDS
            if commands in by_command and by_command[commands]["private_bytes"]["value"] is not None]
    # O1.4 is only observable on the exact 3k/4k/5k baseline followed by the
    # complete 6k..35k main series. A short or private-counter-missing smoke
    # run therefore cannot be reported as PASS.
    available = not missing_marks and not private_missing
    result = {
        "baseline_marks_commands": list(O14_BASELINE_COMMANDS),
        "main_window_commands": list(O14_MAIN_COMMANDS),
        "early_window_commands": list(O14_EARLY_COMMANDS),
        "late_window_commands": list(O14_LATE_COMMANDS),
        "baseline_median_bytes": statistics.median(baseline) if baseline else None,
        "main_max_bytes": max(early + late) if early or late else None,
        "late_max_bytes": max(late) if late else None,
        "main_over_baseline_percent": None,
        "late_over_early_percent": None,
        "gate_codes": None,
        "missing_marks": missing_marks,
        "private_counter_missing_marks": private_missing,
        "available": bool(available and baseline and early and late),
    }
    if baseline and (early or late):
        result["main_over_baseline_percent"] = max(early + late) * 100 / statistics.median(baseline)
    if early and late:
        # The late window is compared with the preceding (early) window;
        # combining both windows would make this ratio tautologically <=100%.
        result["late_over_early_percent"] = max(late) * 100 / max(early)
    if result['available']:
        result['gate_codes'] = memory_gate_codes(
            'host', 'private_commit_bytes', statistics.median(baseline),
            max(early + late), max(early), max(late))
    return result


def _mark(journal: VerifiedJournal, commands: int, mark: int,
          previous_current: int | None) -> tuple[dict[str, object], int]:
    gc.collect()
    current, peak = tracemalloc.get_traced_memory()
    private = private_bytes()
    record = {
        "commands": commands,
        "commands_len": len(journal._commands),
        "commands_type": type(journal._commands).__name__,
        "records_len": len(journal._records),
        "records_type": type(journal._records.offsets).__name__,
        "pending": len(journal._pending),
        "leases": len(journal._leases),
        "private_bytes": private,
        "tracemalloc_current_bytes": current,
        "tracemalloc_peak_bytes": peak,
        "tracemalloc_delta_since_previous_mark": (current - previous_current
                                                    if previous_current is not None else None),
        "gc_collected": True,
        "mark_every": mark,
    }
    return record, current


def mark_schedule(command_count: int, mark_every: int) -> tuple[int, ...]:
    """Return marks, retaining the frozen O1.4 indices for the full run.

    Short smoke runs use their requested interval so cleanup and source
    closure can be tested without pretending that a partial series is O1.4.
    All marks are retained, including the first two warmup batches. Batch i
    finishes at (i+1)*1000 logical commands; baseline 2..4 is 3k/4k/5k.
    """
    return tuple(range(mark_every, command_count + 1, mark_every))


def _full_workload_counts(command_count: int) -> dict[str, int]:
    groups, remainder = divmod(command_count, len(WORKLOAD_CLASSES))
    if remainder:
        return {}
    return {"inspect": groups * 5, "rejected": groups * 3,
            "admitted": groups * 2, "groups": groups,
            "append_pending": groups * 7, "finish": groups * 7,
            "lookup": groups * 7, "rejected_no_record_check": groups * 3,
            "invalid_rejection": groups * 3}


def run(run_id: str, output: Path, command_count: int, mark_every: int) -> int:
    if not re.fullmatch(r"o6-ram-[a-z0-9-]{1,48}", run_id):
        raise ValueError("run id must match o6-ram-<fresh-id>")
    if (command_count <= 0 or command_count > FULL_COMMANDS or mark_every <= 0
            or command_count % mark_every or command_count % 10):
        raise ValueError("command count must be a positive multiple of 10 and mark interval")
    root = _require_output(output)
    before = source_files()
    binding = {"schema": SCHEMA, "run_id": run_id,
               "source_closure_sha256": source_closure(before),
               "command_count": command_count, "mark_every": mark_every,
               "diagnostic_only": True}
    _write(root / "source-files.json", before)
    _write(root / "binding.json", binding)
    journal_path = root / "journal.jsonl"
    journal: VerifiedJournal | None = None
    marks: list[dict[str, object]] = []
    invalid_rejections = 0
    operation_counts = {"inspect": 0, "admitted": 0, "rejected": 0,
                        "append_committed": 0, "append_pending": 0,
                        "finish": 0, "dedupe": 0, "lookup": 0,
                        "rejected_no_record_check": 0,
                        "lease_acquire": 0, "lease_check": 0,
                        "invalid_rejection": 0}
    marks_expected = mark_schedule(command_count, mark_every)
    previous_current = None
    started = time.monotonic()
    primary: BaseException | None = None
    cleanup: dict[str, object] = {"close_attempted": False, "close_ok": False,
                                  "errors": []}
    tracemalloc.start()
    baseline_snapshot = tracemalloc.take_snapshot()
    try:
        journal = VerifiedJournal(journal_path)
        now = 1_000_000
        for index in range(1, command_count + 1):
            command_id = f"cmd-{index:06d}"
            now += 1
            kind = WORKLOAD_CLASSES[(index - 1) % len(WORKLOAD_CLASSES)]
            operation_counts[kind] += 1
            if kind == "rejected":
                try:
                    journal.append_command(project_id=PROJECT, command_id=command_id,
                                           digest="invalid", receipt={"index": index}, now_ms=now)
                except JournalError as error:
                    if getattr(error, "code", None) != "INVALID_DIGEST":
                        raise
                    invalid_rejections += 1
                    operation_counts["invalid_rejection"] += 1
                # Prove the rejected input did not create a command record.
                try:
                    journal.lookup(project_id=PROJECT, command_id=command_id, now_ms=now + 1)
                except JournalError as error:
                    if getattr(error, "code", None) != "COMMAND_NOT_FOUND":
                        raise
                    operation_counts["rejected_no_record_check"] += 1
                else:
                    raise JournalError("REJECTED_COMMAND_RECORDED")
            else:
                # The direct journal equivalent uses the same durable path for
                # inspect and admitted commands: pending append, terminal
                # finish, then a postcondition lookup. Rejections above have
                # no append at all.
                journal.append_command(project_id=PROJECT, command_id=command_id,
                                       digest=DIGEST,
                                       receipt={"index": index, "kind": kind},
                                       now_ms=now, pending=True)
                operation_counts["append_pending"] += 1
                journal.finish_command(project_id=PROJECT, command_id=command_id,
                                       status="COMMITTED",
                                       receipt={"index": index, "kind": kind}, now_ms=now + 1)
                operation_counts["finish"] += 1
                now += 1
                found = journal.lookup(project_id=PROJECT, command_id=command_id, now_ms=now + 1)
                if found.get("status") != "COMMITTED":
                    raise JournalError("COMMAND_POSTCONDITION")
                operation_counts["lookup"] += 1
                if index % 11 == 0:
                    replay = journal.append_command(project_id=PROJECT, command_id=command_id,
                                                    digest=DIGEST,
                                                    receipt={"index": index, "kind": kind},
                                                    now_ms=now + 2)
                    if replay.get("replayed") is not True:
                        raise JournalError("COMMAND_DEDUPE_POSTCONDITION")
                    operation_counts["dedupe"] += 1
            if index % 50 == 0:
                lease = journal.acquire_lease(project_id=PROJECT, target="writer",
                                              owner="microbench", now_ms=now + 3, ttl_ms=600_000)
                operation_counts["lease_acquire"] += 1
                journal.check_lease(lease, now_ms=now + 4)
                operation_counts["lease_check"] += 1
                now += 4
            if index in marks_expected:
                mark, previous_current = _mark(journal, index, mark_every, previous_current)
                marks.append(mark)
                _write(root / f"mark-{index:06d}.json", mark)
                print("HH_GT06_O6_RAM_MARK " + json.dumps({"commands": index,
                      "private_bytes": mark["private_bytes"],
                      "tracemalloc_current_bytes": mark["tracemalloc_current_bytes"]}), flush=True)
        snapshot = tracemalloc.take_snapshot()
        stats = []
        for entry in snapshot.compare_to(baseline_snapshot, "filename")[:10]:
            stats.append({"file": str(entry.traceback[0]), "size_diff": entry.size_diff,
                          "count_diff": entry.count_diff})
        _write(root / "tracemalloc-top-deltas.json", stats)
    except BaseException as error:
        primary = error
    finally:
        if journal is not None:
            cleanup["close_attempted"] = True
            try:
                journal.close()
                cleanup["close_ok"] = True
            except BaseException as error:
                cleanup["errors"].append(_error(error))
        try:
            leftovers = sorted(path.name for path in root.iterdir()
                               if path.name.startswith(".hh-index-"))
            cleanup["index_leftovers"] = leftovers
        except OSError as error:
            cleanup["errors"].append(_error(error))
        tracemalloc.stop()
    after = source_files()
    source_unchanged = after == before
    cleanup["journal_retained"] = journal_path.is_file()
    cleanup["journal_guard_retained"] = journal_path.with_name(journal_path.name + ".guard").is_file()
    cleanup["safe_index_cleanup"] = cleanup.get("close_ok") is True and not cleanup.get("index_leftovers")
    workload = _full_workload_counts(command_count)
    workload_complete = bool(workload) and all(
        operation_counts.get(name) == value for name, value in workload.items()
        if name in operation_counts)
    o1_4 = _o1_4(marks)
    marks_complete = tuple(mark["commands"] for mark in marks) == marks_expected
    private_complete = all(mark["private_bytes"]["value"] is not None for mark in marks)
    slopes = {
        "private_bytes_per_logical_command": _slope([
            (int(mark['commands']), int(mark['private_bytes']['value']))
            for mark in marks if mark['commands'] >= 3000 and mark['private_bytes']['value'] is not None]),
        "tracemalloc_current_bytes_per_logical_command": _slope([
            (int(mark['commands']), int(mark['tracemalloc_current_bytes']))
            for mark in marks if mark['commands'] >= 3000]),
    }
    complete = (primary is None and source_unchanged and marks_complete and private_complete
                and workload_complete and o1_4['available']
                and cleanup.get('safe_index_cleanup') is True)
    gate_codes = list(o1_4['gate_codes'] or [])
    if complete and slopes['private_bytes_per_logical_command'] > 32:
        gate_codes.append('O6_RAM_SLOPE')
    passed = complete and not gate_codes
    result = dict(binding)
    result.update({
        # A parent supervisor owns the real process exit observation. This is
        # only the expected status derived from the captured workload.
        "completed": complete,
        "actual_result": "PASS_DIAGNOSTIC" if passed else
                         "FAIL_DIAGNOSTIC" if primary is not None or complete else "INCOMPLETE_DIAGNOSTIC",
        "expected_exit_code": 0 if passed else 1 if primary is not None or complete else 2,
        "diagnostic_gate_codes": gate_codes,
        "elapsed_seconds": time.monotonic() - started,
        "marks": marks,
        "invalid_rejections": invalid_rejections,
        "operation_counts": operation_counts,
        "slopes": slopes,
        "slope_window_commands": [3000, 35000],
        "o1_4_observation": o1_4,
        "marks_expected": list(marks_expected),
        "marks_complete": marks_complete,
        "private_counter_complete": private_complete,
        "workload_complete": workload_complete,
        "source_unchanged": source_unchanged,
        "cleanup": cleanup,
        "limitations": [
            "Diagnostic only; no formal acceptance or O1.4 gate decision.",
            "Private bytes include Python, SQLite, allocator and OS effects.",
            "tracemalloc observes Python allocations only and cannot attribute all private commit.",
            "The parent must capture the host process exit independently.",
            "This is one process and one journal path; it is not the mixed host/editor campaign.",
        ],
    })
    if primary is not None:
        result["error"] = _error(primary)
    _write(root / ("result.json" if result["completed"] else "failure.json"), result)
    return int(result["expected_exit_code"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--commands", type=int, default=DEFAULT_COMMANDS)
    parser.add_argument("--mark-every", type=int, default=DEFAULT_MARK)
    args = parser.parse_args()
    output = args.output or (STUDIO / ".local" / "reviews" / args.run_id)
    try:
        return run(args.run_id, output, args.commands, args.mark_every)
    except BaseException as error:
        print(json.dumps({"completed": False, "expected_exit_code": 1,
                          "error": _error(error)}), file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
