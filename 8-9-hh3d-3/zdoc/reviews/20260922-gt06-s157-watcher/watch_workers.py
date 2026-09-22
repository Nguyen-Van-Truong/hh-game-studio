"""Transport-only Cursor watcher. No AI, worker retry, process kill or acceptance."""
from __future__ import annotations

import argparse
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def utc():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def moment(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def same_path(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def process_identity(worker, start):
    kernel = C.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
    kernel.OpenProcess.restype = W.HANDLE
    kernel.CloseHandle.argtypes = [W.HANDLE]
    kernel.CloseHandle.restype = W.BOOL
    kernel.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
    kernel.WaitForSingleObject.restype = W.DWORD
    kernel.GetProcessTimes.argtypes = [W.HANDLE] + [C.POINTER(W.FILETIME)] * 4
    kernel.GetProcessTimes.restype = W.BOOL
    kernel.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = W.BOOL
    handle = kernel.OpenProcess(0x1000 | 0x100000, False, worker["pid"])
    if not handle:
        error = C.get_last_error()
        return "ABSENT" if error == 87 else f"UNKNOWN_OPEN_{error}"
    try:
        times = [W.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(C.byref(t) for t in times)):
            return "UNKNOWN_TIMES"
        ticks = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        actual = ticks / 10_000_000 - 11644473600
        size = W.DWORD(32768)
        name = C.create_unicode_buffer(size.value)
        if not kernel.QueryFullProcessImageNameW(handle, 0, name, C.byref(size)):
            return "UNKNOWN_IMAGE"
        if abs(actual - moment(start["start_utc"])) > 0.00001 or not same_path(name.value, start["executable"]):
            return "PID_REUSED"
        state = kernel.WaitForSingleObject(handle, 0)
        return {0: "EXITED", 258: "LIVE"}.get(state, "UNKNOWN_WAIT")
    finally:
        if not kernel.CloseHandle(handle):
            raise OSError("Watcher query handle CloseHandle failed")


def validate_result(worker):
    """A closed report + marker + same-attempt wrapper exit means reviewable only."""
    attempt = Path(worker["attempt"])
    report = Path(worker["workspace"]) / worker["report_relative"]
    marker_path = report.with_name("completion.json")
    try:
        start, dispatch = read(attempt / "wrapper-start.json"), read(attempt / "dispatch.json")
        marker, terminal = read(marker_path), read(attempt / "terminal.json")
        exit_code = int((attempt / "exit.txt").read_text(encoding="utf-8-sig").strip())
        if start["session_id"] != worker["session_id"] or terminal["session_id"] != worker["session_id"]:
            raise ValueError("session binding mismatch")
        if start["pid"] != worker["pid"] or dispatch["pid"] != worker["pid"]:
            raise ValueError("process binding mismatch")
        if abs(moment(start["start_utc"]) - moment(worker["process_start_utc"])) > 0.00001:
            raise ValueError("process start binding mismatch")
        if start["model_requested"] != "grok-4.7-xhigh" or dispatch["model_requested"] != "grok-4.7-xhigh":
            raise ValueError("wrong requested model")
        if not same_path(start["workspace"], worker["workspace"]) or not same_path(terminal["report"], report):
            raise ValueError("workspace/report binding mismatch")
        # Some current worker markers carry only lane+hash. The exact report
        # path is then bound by the frozen registry AND same-session wrapper,
        # explicitly as observer transport provenance, not a worker assertion.
        marker_report = Path(marker.get("report", str(report)))
        if not marker_report.is_absolute():
            marker_report = Path(worker["workspace"]) / marker_report
        if not same_path(marker_report, report):
            raise ValueError("marker report path mismatch")
        expected_lane = "s157-" + worker["lane"]
        if marker.get("lane") not in (worker["lane"], expected_lane):
            raise ValueError("marker lane mismatch")
        sha = digest(report)
        if sha != marker["report_sha256"].lower() or sha != terminal["report_sha256"].lower():
            raise ValueError("report hash mismatch")
        if exit_code != terminal["cli_exit"]:
            raise ValueError("exit receipt mismatch")
        if moment(terminal["ended_utc"]) < moment(start["start_utc"]):
            raise ValueError("terminal predates attempt")
        if terminal.get("formal_acceptance") is not False or marker.get("acceptance_claim", False) or marker.get("formal_acceptance", False):
            raise ValueError("unexpected acceptance claim")
        return {"state": "NEEDS_REVIEW" if exit_code == 0 else "WORKER_FAILED",
                "report": str(report), "report_sha256": sha, "marker_sha256": digest(marker_path),
                "exit_code": exit_code, "worker_verdict": marker.get("verdict", "UNKNOWN"),
                "marker_report_path_source": "worker" if "report" in marker else "registry_and_wrapper",
                "provenance": "observer_transport_only", "formal_acceptance": False}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return {"state": "INCOMPLETE", "reason": str(exc), "report": str(report), "formal_acceptance": False}


def notify(out, key, title, message):
    notice = out / (key + ".json")
    # Claim before dispatch: restart cannot duplicate a notification.
    try:
        with notice.open("x", encoding="utf-8") as f:
            json.dump({"utc": utc(), "title": title, "message": message, "delivery": "PENDING"}, f, ensure_ascii=False)
    except FileExistsError:
        return
    helper = Path(__file__).with_name("show_notice.ps1")
    try:
        proc = subprocess.Popen(["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
                                 "-ExecutionPolicy", "Bypass", "-File", str(helper), "-Notice", str(notice)],
                                creationflags=subprocess.CREATE_NO_WINDOW,
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        write(out / (key + "-dispatch.json"), {"utc": utc(), "helper_pid": proc.pid,
              "delivery": "DISPATCHED_NOT_CONFIRMED_SEEN", "notice": str(notice)})
    except OSError as exc:
        write(out / (key + "-dispatch.json"), {"utc": utc(), "error": str(exc), "delivery": "FAILED"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--notify-test", action="store_true")
    args = parser.parse_args()
    workers = read(args.registry)["workers"]
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    # Windows releases this exclusive lock if the observer crashes.
    import msvcrt
    lock = (out / "watcher.lock").open("a+b")
    if lock.tell() == 0:
        lock.write(b"0")
        lock.flush()
    lock.seek(0)
    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    write(out / "watcher-start.json", {"pid": os.getpid(), "utc": utc(), "registry": str(Path(args.registry).resolve()),
          "script_sha256": digest(__file__), "interval_seconds": 30, "uses_ai": False})
    if args.notify_test:
        notify(out, "notification-test", "HH3D S157 - Watcher da bat",
               "Day la thong bao thu. Watcher khong dung AI. Se bao khi 3 worker co ket qua hoac bi gian doan.\n" + str(out / "STATUS.txt"))
    started = time.monotonic()
    stable, missing, activity = {}, {}, {}
    while True:
        rows = []
        for worker in workers:
            lane = worker["lane"]
            attempt = Path(worker["attempt"])
            try:
                identity = process_identity(worker, read(attempt / "wrapper-start.json"))
            except (OSError, ValueError, KeyError) as exc:
                identity = "UNKNOWN_IDENTITY: " + str(exc)
            result = validate_result(worker)
            row = {"lane": lane, "identity": identity, "attempt": str(attempt), **result}
            if identity == "LIVE":
                row["state"] = "RUNNING"
                stable.pop(lane, None)
                # Metadata only, no tool/thinking/event stream content is read.
                paths = list(attempt.glob("*")) + list(Path(result["report"]).parent.glob("*"))
                stamps = []
                for path in paths:
                    try:
                        if path.is_file():
                            stat = path.stat()
                            stamps.append((str(path), stat.st_size, stat.st_mtime_ns))
                    except OSError:
                        pass
                fingerprint = hash(tuple(sorted(stamps)))
                old = activity.get(lane)
                if old is None or old[0] != fingerprint:
                    activity[lane] = (fingerprint, time.monotonic())
                idle = time.monotonic() - activity[lane][1]
                row["unchanged_seconds_observed"] = round(idle)
                if idle >= 1200:
                    row["state"] = "CHECKPOINT_NEEDED"
                    notify(out, lane + "-checkpoint", "HH3D S157 - Can kiem tra " + lane,
                           "Worker van song, 20 phut khong doi file. Chua ket luan treo; khong tu retry. Gui Codex: kiem tra S157.\n" + str(out / "STATUS.txt"))
            elif identity in ("ABSENT", "EXITED", "PID_REUSED"):
                if result["state"] in ("NEEDS_REVIEW", "WORKER_FAILED"):
                    signature = (result["report_sha256"], result["marker_sha256"], result["exit_code"])
                    if stable.get(lane) != signature:
                        stable[lane] = signature
                        row["state"] = "VERIFYING_CLOSED_REPORT"
                else:
                    missing.setdefault(lane, time.monotonic())
                    if time.monotonic() - missing[lane] < 60:
                        row["state"] = "WAITING_FINAL_FILES"
                    else:
                        row["state"] = "WORKER_INCOMPLETE"
                if row["state"] in ("NEEDS_REVIEW", "WORKER_FAILED", "WORKER_INCOMPLETE"):
                    notify(out, lane + "-terminal", "HH3D S157 - " + lane,
                           row["state"] + "; CLI exit=" + str(result.get("exit_code", "UNKNOWN")) +
                           ". Can coordinator review, chua phai GT06 PASS.\nReport: " + result["report"] +
                           "\nStatus: " + str(out / "STATUS.txt"))
            else:
                row["state"] = "UNKNOWN"
                notify(out, lane + "-identity-unknown", "HH3D S157 - UNKNOWN " + lane,
                       "Khong doc duoc process identity. Khong ket luan da dung hay tu retry.\n" + str(out / "STATUS.txt"))
            rows.append(row)
        all_terminal = all(r["state"] in ("NEEDS_REVIEW", "WORKER_FAILED", "WORKER_INCOMPLETE") for r in rows)
        write(out / "status.json", {"utc": utc(), "all_terminal": all_terminal, "formal_acceptance": False, "workers": rows})
        lines = ["HH3D S157 - Cursor Grok 4.7 Extra High (non-Fast)", "UTC: " + utc(),
                 "Watcher checks every 30 seconds; no AI calls. Transport state only, NOT GT06 acceptance.", ""]
        for row in rows:
            lines += [row["lane"] + ": " + row["state"] + " / " + row["identity"], "Report: " + row["report"], ""]
        lines += ["ALL TERMINAL: " + str(all_terminal), "When all terminal or interrupted, send Codex: Tiep tuc S157, doc ket qua watcher."]
        temp = out / "STATUS.tmp"
        temp.write_text("\n".join(lines), encoding="utf-8")
        os.replace(temp, out / "STATUS.txt")
        if all_terminal:
            notify(out, "all-terminal", "HH3D S157 - Ca 3 worker da ket thuc",
                   "Da co trang thai cuoi cho 3 worker. Gui Codex: Tiep tuc S157, doc ket qua watcher.\nChua phai toan plan hoan tat.\n" + str(out / "STATUS.txt"))
            break
        if args.once:
            break
        if time.monotonic() - started > 43200:
            notify(out, "watcher-timeout", "HH3D S157 - Watcher het 12 gio",
                   "Theo doi het han; worker khong bi dung. Gui Codex kiem tra.\n" + str(out / "STATUS.txt"))
            break
        time.sleep(30)
    write(out / "watcher-end.json", {"utc": utc(), "all_terminal": all_terminal, "once": args.once, "uses_ai": False})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        import sys
        import traceback
        if "--out" in sys.argv:
            error_out = Path(sys.argv[sys.argv.index("--out") + 1]).resolve()
            error_out.mkdir(parents=True, exist_ok=True)
            # Do not clobber a live observer's status on a duplicate launch.
            error_path = error_out / ("watcher-error-" + str(os.getpid()) + ".json")
            write(error_path, {"utc": utc(), "error": str(exc), "traceback": traceback.format_exc()})
            notify(error_out, "watcher-error-" + str(os.getpid()), "HH3D S157 - Watcher error",
                   "Watcher loi, khong tac dong worker. Gui Codex kiem tra.\n" + str(error_path))
        raise
