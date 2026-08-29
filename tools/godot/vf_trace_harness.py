#!/usr/bin/env python3
"""Vault Fighters VF1-WP3 InputFrame record/replay launcher.

Headless official replay is the verify path. --window omits --headless
so the same script can be watched; it is not the leftover-0 official run.

Does not tick the 29-8 plan. Does not fetch or rip Y8. Title remains
Vault Fighters. 60 Hz is ledger:RL-SIM-FIXED-60 (assumption).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PRODUCT = REPO / "godot" / "dogfood" / "superfighters"
CHECK = PRODUCT / "tests" / "check_golden_traces.py"
SCRIPT = "res://tests/run_golden_traces.gd"


def pinned_console() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise SystemExit("LOCALAPPDATA missing")
    root = Path(local) / "HHGodotAgent" / "tooling" / "godot-4.7.1-stable" / "bin"
    console = root / "Godot_v4.7.1-stable_win64_console.exe"
    gui = root / "Godot_v4.7.1-stable_win64.exe"
    return console if console.is_file() else gui


def pinned_gui() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise SystemExit("LOCALAPPDATA missing")
    return (
        Path(local)
        / "HHGodotAgent"
        / "tooling"
        / "godot-4.7.1-stable"
        / "bin"
        / "Godot_v4.7.1-stable_win64.exe"
    )


def cmd_for(window: bool) -> list[str]:
    exe = pinned_gui() if window else pinned_console()
    if not exe.is_file():
        raise SystemExit(f"pinned Godot missing: {exe}")
    cmd = [str(exe)]
    if not window:
        cmd.append("--headless")
    cmd.extend(["--path", str(PRODUCT), "--script", SCRIPT])
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(description="VF1-WP3 InputFrame trace harness")
    parser.add_argument("action", choices=("check", "replay", "record"), help="check files, replay traces, or print record usage")
    parser.add_argument("--window", action="store_true", help="replay without --headless (not leftover-0 official)")
    args = parser.parse_args()
    if args.action == "check":
        return subprocess.call([sys.executable, str(CHECK)], cwd=str(REPO))
    if args.action == "record":
        print("Record from real Input: play with a SimRecorder attached.")
        print("Headless proof: tests/run_golden_traces.gd record_from_real_input")
        print("uses Input.action_press → InputActions.read_player_frame → apply_frames.")
        print("Window record: same GameSession.recorder path when not test_driven.")
        return 0
    env = os.environ.copy()
    if args.window:
        env["HH_VF_TRACE_WINDOW"] = "1"
    print("vf_trace_harness: title=Vault Fighters")
    print("vf_trace_harness: ledger=RL-SIM-FIXED-60 assumption")
    print(f"vf_trace_harness: window={1 if args.window else 0}")
    print("vf_trace_harness: " + " ".join(cmd_for(args.window)))
    return subprocess.call(cmd_for(args.window), cwd=str(PRODUCT), env=env)


if __name__ == "__main__":
    sys.exit(main())
