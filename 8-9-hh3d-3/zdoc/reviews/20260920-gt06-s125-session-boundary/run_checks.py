"""Capture focused, no-engine test commands and actual subprocess exits."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('label')
    parser.add_argument('suite', choices=['regression', 'protocol', 'replay'])
    args = parser.parse_args()
    output = HERE / args.label
    output.mkdir(exist_ok=False)
    pattern = {'regression': 'test_transport_pending_lookup.py',
               'protocol': 'test_transport*.py', 'replay': 'test_*.py'}[args.suite]
    command = [sys.executable, '-B', '-W', 'default', '-m', 'unittest', 'discover',
               '-s', 'studio/tests/' + ('protocol' if args.suite == 'regression' else args.suite),
               '-p', pattern, '-v']
    started = datetime.now(timezone.utc).isoformat()
    with (output / 'stdout.txt').open('wb') as stdout, (output / 'stderr.txt').open('wb') as stderr:
        result = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr, timeout=600)
    receipt = {'authority': 0, 'command': command, 'cwd': str(ROOT), 'started': started,
               'ended': datetime.now(timezone.utc).isoformat(), 'actual_exit': result.returncode,
               'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in output.iterdir() if p.is_file()},
               'transport_sha256': hashlib.sha256((ROOT / 'studio/host/core/transport.py').read_bytes()).hexdigest()}
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2))
    print((output / 'stderr.txt').read_text(encoding='utf-8', errors='replace')[-1200:])
    return result.returncode

if __name__ == '__main__':
    raise SystemExit(main())
