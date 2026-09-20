"""Capture the affected no-engine benchmark test lane against frozen source bytes."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    helper = ROOT / 'zdoc/reviews/20260919-gt06-s123-lookup-repair/support.py'
    spec = importlib.util.spec_from_file_location('s129_candidate_support', helper)
    support = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(support)
    campaign, _, _, sources = support.load_campaign(ROOT)
    tests = {p.relative_to(ROOT).as_posix(): sha(p)
             for p in (ROOT / 'studio/tests/replay').glob('test_benchmark*.py')}
    output = BASE / 'benchmark-tests-01'
    output.mkdir(exist_ok=False)
    command = [sys.executable, '-B', '-W', 'default', '-m', 'unittest',
               'discover', '-s', str(ROOT / 'studio/tests/replay'),
               '-p', 'test_benchmark*.py', '-v']
    started = datetime.now(timezone.utc).isoformat()
    began = time.monotonic()
    with (output / 'stdout.txt').open('xb') as stdout, (output / 'stderr.txt').open('xb') as stderr:
        result = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr, timeout=300)
    after = campaign.source_files()
    stderr = (output / 'stderr.txt').read_text(encoding='utf-8')
    counts = re.findall(r'Ran (\d+) tests? in', stderr)
    receipt = {'schema': 'S129.candidate-tests.1', 'command': command,
        'started_utc': started, 'ended_utc': datetime.now(timezone.utc).isoformat(),
        'elapsed_seconds': time.monotonic() - began, 'actual_exit': result.returncode,
        'tests_run': int(counts[-1]) if counts else None,
        'source_files': sources, 'source_closure': campaign.closure(sources),
        'source_unchanged': after == sources,
        'test_files': tests, 'test_files_unchanged': all(sha(ROOT / p) == h for p, h in tests.items()),
        'profile_sha256': campaign.profile.PROFILE_SHA256,
        'runner_sha256': sha(Path(__file__)),
        'streams': {name: sha(output / name) for name in ('stdout.txt', 'stderr.txt')},
        'engine_launched': False, 'formal_acceptance': False, 'eligible_for_dataset': False}
    support.write(output / 'receipt.json', receipt)
    print(json.dumps({k: receipt[k] for k in ('actual_exit','tests_run','elapsed_seconds','source_closure','source_unchanged','test_files_unchanged')}))
    return 0 if result.returncode == 0 and after == sources and receipt['test_files_unchanged'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
