"""Fail-closed GT-01 bootstrap runner.

Successful process exits are insufficient: the runner checks the pinned
binary, immutable source closure, exact trace, clean stderr and process tree.
The resulting evidence remains a candidate until the plan's critics approve.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import re
import time
from datetime import datetime, timezone
from pathlib import Path

EXCLUDED_DIRS = {".godot", "__pycache__", ".local", "evidence"}
VERSION_RE = re.compile(r"(?P<version>\d+\.\d+\.\d+\.stable\.official(?:\.[0-9a-f]+)?)")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_reparse(path: Path) -> bool:
    if os.name != "nt":
        return path.is_symlink()
    try:
        return bool(path.stat(follow_symlinks=False).st_file_attributes & 0x400)
    except (AttributeError, FileNotFoundError, OSError):
        return path.is_symlink()


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def checked_files(root: Path) -> dict[str, str]:
    if any(_is_reparse(p) for p in [root, *root.parents] if p.exists()):
        raise ValueError("symlink/reparse in source path")
    root = root.resolve(strict=True)
    result: dict[str, str] = {}
    for directory, names, files in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        names[:] = sorted(n for n in names if n not in EXCLUDED_DIRS)
        if any(_is_reparse(directory_path / n) for n in names):
            raise ValueError("symlink/reparse directory in closure")
        for name in sorted(files):
            path = directory_path / name
            if path.suffix == ".pyc" or _is_reparse(path):
                raise ValueError(f"symlink/reparse or unsupported path in closure: {path}")
            if path.is_file():
                result[path.relative_to(root).as_posix()] = hash_file(path)
    return result


def _job_for_process(process: subprocess.Popen[bytes]):
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateJobObject.restype = wintypes.BOOL
    class BasicLimit(ctypes.Structure):
        _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                    ("flags", wintypes.DWORD), ("min_ws", ctypes.c_size_t), ("max_ws", ctypes.c_size_t),
                    ("active_limit", wintypes.DWORD), ("affinity", ctypes.c_size_t),
                    ("priority", wintypes.DWORD), ("scheduling", wintypes.DWORD)]
    class ExtendedLimit(ctypes.Structure):
        _fields_ = [("basic", BasicLimit), ("io", ctypes.c_ulonglong * 6),
                    ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                    ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t)]
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(ExtendedLimit), wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise OSError(ctypes.get_last_error(), "CreateJobObjectW")
    limits = ExtendedLimit()
    limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, no breakaway
    if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        error = ctypes.get_last_error()
        kernel.CloseHandle(job)
        raise OSError(error, "SetInformationJobObject")
    if not kernel.AssignProcessToJobObject(job, wintypes.HANDLE(process._handle)):
        error = ctypes.get_last_error()
        kernel.CloseHandle(job)
        raise OSError(error, "AssignProcessToJobObject")
    return kernel, job


def _terminate_job(job_state) -> None:
    if job_state:
        job_state[0].TerminateJobObject(job_state[1], 2)


def _job_active_count(job_state) -> int | None:
    if not job_state:
        return 0
    import ctypes
    from ctypes import wintypes
    class Basic(ctypes.Structure):
        _fields_ = [("total_user_time", ctypes.c_longlong), ("total_kernel_time", ctypes.c_longlong),
                    ("period_user_time", ctypes.c_longlong), ("period_kernel_time", ctypes.c_longlong),
                    ("total_page_faults", wintypes.DWORD), ("total_processes", wintypes.DWORD),
                    ("active_processes", wintypes.DWORD), ("total_terminated", wintypes.DWORD)]
    kernel, job = job_state
    kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(Basic), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryInformationJobObject.restype = wintypes.BOOL
    value, returned = Basic(), wintypes.DWORD()
    if not kernel.QueryInformationJobObject(job, 1, ctypes.byref(value), ctypes.sizeof(value), ctypes.byref(returned)):
        return None
    return int(value.active_processes)


def _close_job(job_state) -> None:
    if job_state:
        job_state[0].CloseHandle(job_state[1])


def run_process(argv: list[str], *, cwd: Path, output: Path, timeout: int, label: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", label) or not 1 <= timeout <= 600:
        raise ValueError("invalid process label or timeout")
    stdout_path, stderr_path = output / f"{label}-stdout.txt", output / f"{label}-stderr.txt"
    if stdout_path.exists() or stderr_path.exists():
        raise ValueError(f"duplicate process output for {label}")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    started = utc_now()
    # The helper cannot launch the target until assigned to the job. This
    # removes the race where the target could spawn children before assignment.
    host_path = output / f"{label}-host.json"
    if host_path.exists():
        raise ValueError("duplicate host report")
    helper = "import subprocess,sys,json,datetime; token=sys.stdin.readline(); sys.exit(125) if token != 'GO\\n' else None; started=datetime.datetime.now(datetime.timezone.utc).isoformat(); p=subprocess.Popen(sys.argv[2:]); code=p.wait(); f=open(sys.argv[1],'x',encoding='utf-8'); json.dump({'target_pid':p.pid,'started_at':started,'exit_code':code},f); f.close()"
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        process = subprocess.Popen([sys.executable, "-c", helper, str(host_path), *argv], cwd=cwd, stdout=stdout, stderr=stderr,
                                   stdin=subprocess.PIPE, creationflags=flags, start_new_session=os.name != "nt")
        job_state = None
        timed_out = False
        tree_verified = False
        exit_code = None
        try:
            if os.name == "nt":
                job_state = _job_for_process(process)
            process.stdin.write(b"GO\n")
            process.stdin.close()
            try:
                exit_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                if os.name == "nt":
                    _terminate_job(job_state)
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                exit_code = process.wait(timeout=10)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if os.name == "nt":
                    tree_verified = _job_active_count(job_state) == 0
                else:
                    try:
                        os.killpg(process.pid, 0)
                    except ProcessLookupError:
                        tree_verified = True
                if tree_verified:
                    break
                time.sleep(0.02)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            if not tree_verified:
                if job_state:
                    _terminate_job(job_state)
                elif os.name != "nt":
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            _close_job(job_state)
    host_report = json.loads(host_path.read_text(encoding="utf-8")) if host_path.exists() else {}
    portable_argv = [Path(argv[0]).name]
    for arg in argv[1:]:
        if os.path.isabs(arg):
            portable_argv.append("$SNAPSHOT/" + Path(arg).relative_to(cwd).as_posix() if _within(Path(arg), cwd) else Path(arg).name)
        else:
            portable_argv.append(arg)
    return {"wrapper_pid": process.pid, "started_at": started, "argv": portable_argv,
            "exit_code": host_report.get("exit_code"), "target_pid": host_report.get("target_pid"),
            "wrapper_exit_code": exit_code, "timed_out": timed_out,
            "tree_verified": tree_verified, "ownership": "gated_job_kill_on_close" if os.name == "nt" else "process_group", "stdout": stdout_path.name,
            "stderr": stderr_path.name}


def fail(message: str) -> int:
    print(f"GT01_GAP: {message}", file=sys.stderr)
    return 2


def _observed_version(godot: Path, timeout: int) -> tuple[str, str]:
    result = subprocess.run([str(godot), "--version"], capture_output=True, text=True,
                            timeout=min(timeout, 30), check=False)
    combined = (result.stdout or "") + (result.stderr or "")
    match = VERSION_RE.search(combined)
    return (match.group("version") if match else "", combined.strip())


def _version_matches(observed: str, expected: str) -> bool:
    normalized = expected.replace("-", ".")
    return observed == normalized or observed.startswith(normalized + ".")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--studio-root", required=True, type=Path)
    parser.add_argument("--godot-exe", required=True, type=Path)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--console-sha256", required=True)
    parser.add_argument("--gui-sha256", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--command-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout-seconds", default=60, type=int)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.timeout_seconds <= 600:
        return fail("timeout outside 1..600 seconds")
    studio, godot, output = args.studio_root.resolve(), args.godot_exe.resolve(), args.output.resolve()
    fixture = studio / "fixtures" / "sample-game"
    if not studio.is_dir() or not fixture.is_dir() or not godot.is_file():
        return fail("studio, fixture, or Godot executable is missing")
    if output.exists() or _within(output, studio):
        return fail("output must be new and outside studio root")
    if _is_reparse(studio) or _is_reparse(godot):
        return fail("reparse/symlink root or executable")
    try:
        before = checked_files(studio)
        if hash_file(godot) != args.console_sha256.lower():
            return fail("console checksum mismatch")
        gui = godot.with_name(godot.name.replace("_console", ""))
        if not gui.is_file() or hash_file(gui) != args.gui_sha256.lower():
            return fail("GUI companion missing or checksum mismatch")
        observed, raw_version = _observed_version(godot, args.timeout_seconds)
        if not _version_matches(observed, args.expected_version):
            return fail(f"version mismatch: {raw_version}")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return fail(str(error))
    if args.check_only:
        print(json.dumps({"status": "CHECK_ONLY_PASS", "expected_version": args.expected_version,
                          "observed_version": observed, "source_files": len(before)}))
        return 0
    output.mkdir(parents=True, exist_ok=False)
    snapshot = output / "snapshot-unicode-đ" / "sample-game"
    shutil.copytree(fixture, snapshot, ignore=shutil.ignore_patterns(".godot", "*.pyc", "__pycache__"))
    after = checked_files(studio)
    if before != after:
        return fail("source closure changed while snapshot was copied")
    runs = []
    for number, run_argv in enumerate((
        [str(godot), "--headless", "--path", str(snapshot), "--import"],
        [str(godot), "--headless", "--path", str(snapshot), "--check-only", "--script", "res://scripts/trace.gd"],
        [str(godot), "--headless", "--path", str(snapshot), "--script", "res://scripts/trace.gd"],
    ), 1):
        runs.append(run_process(run_argv, cwd=snapshot, output=output,
                                timeout=args.timeout_seconds, label=f"run-{number}"))
        if runs[-1]["exit_code"] != 0 or runs[-1]["timed_out"] or not runs[-1]["tree_verified"]:
            break
    trace_path = output / "run-3-stdout.txt"
    trace_text = trace_path.read_text(encoding="utf-8", errors="replace") if trace_path.exists() else ""
    trace_lines = [line for line in trace_text.splitlines() if line.startswith("GT01_TRACE ")]
    clean_stderr = all(not (output / run["stderr"]).read_text(encoding="utf-8", errors="replace").strip() for run in runs)
    trace_ok = False
    if len(trace_lines) == 1:
        try:
            trace_data = json.loads(trace_lines[0].removeprefix("GT01_TRACE "))
            trace_ok = isinstance(trace_data, dict) and trace_data.get("result") == "PASS" and trace_data.get("phase") == "QUITTING"
        except (ValueError, TypeError):
            pass
    all_ok = all(r["exit_code"] == 0 and not r["timed_out"] and r["tree_verified"] for r in runs) and trace_ok and clean_stderr
    evidence = {"schema": "hh-gt01-bootstrap-evidence-v2", "status": "CANDIDATE" if all_ok else "DIAGNOSTIC",
                "run_id": args.run_id, "command_id": args.command_id, "recorded_at": utc_now(),
                "expected_version": args.expected_version, "observed_version": observed,
                "console_sha256": args.console_sha256.lower(), "gui_sha256": args.gui_sha256.lower(),
                "source_manifest": before, "runs": runs, "trace_lines": trace_lines,
                "checks": {"trace_exactly_one_pass": trace_ok, "stderr_clean": clean_stderr,
                           "source_stable": before == after, "process_tree_verified": all(r["tree_verified"] for r in runs)},
                "limits": ["candidate evidence still requires TQ01/TX12/TX14 and two independent critics"]}
    (output / "evidence.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": evidence["status"], "output": str(output), "runs": runs}, indent=2))
    return 0 if all_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
