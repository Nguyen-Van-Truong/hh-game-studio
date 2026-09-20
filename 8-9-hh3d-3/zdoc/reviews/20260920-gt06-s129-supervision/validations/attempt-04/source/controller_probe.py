"""Fixed disposable Python controller/leaf fixture; no engine or benchmark imports."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import passive_observer as observer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('exit0', 'exit7', 'abrupt', 'leaf'), required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--gated', action='store_true')
    args = parser.parse_args()
    fixture = observer.plain(args.fixture)
    observer.need(fixture.is_relative_to(observer.BASE / 'fixtures') and fixture.is_dir(), 'S129_FIXTURE_PATH')
    if args.mode == 'leaf':
        started = time.monotonic()
        while args.gated and not (fixture / 'release-leaf').exists():
            observer.need(time.monotonic() - started < 10, 'S129_LEAF_BOUND')
            time.sleep(.01)
        time.sleep(.05)
        return 0
    argv = [sys.executable, '-B', str(Path(__file__).resolve()), '--mode', 'leaf', '--fixture', str(fixture)]
    if args.gated:
        argv.append('--gated')
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    child = observer.identity(int(process._handle), process.pid)
    observer.write(fixture / 'child-start.json', {'identity': child, 'parent_pid': os.getpid(),
                   'argv_sha256': observer.digest(argv)})
    code = process.wait(timeout=12)
    observer.write(fixture / 'child-exit.json', {'identity': child, 'actual_exit':
        observer.observe_exit(int(process._handle), child), 'popen_exit': code,
        'handle_close': observer.close_popen(process)})
    return 7 if args.mode == 'exit7' else 0


if __name__ == '__main__':
    raise SystemExit(main())
