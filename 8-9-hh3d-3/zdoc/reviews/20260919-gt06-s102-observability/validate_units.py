"""Retain one bounded affected-test invocation and exact dependency hashes."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
sys.path.insert(0, str(ROOT))
from studio.tests.replay import run_benchmark_campaign as campaign

NAMES = ('test_benchmark_http_phases', 'test_benchmark_import_observer',
         'test_benchmark_commands', 'test_transport', 'test_benchmark_campaign',
         'test_campaign_terminal_cleanup', 'test_benchmark_campaign_stop_completion',
         'test_campaign_task', 'test_benchmark_stop')


def main():
    number = int(sys.argv[1])
    assert 1 <= number <= 99
    output = BASE / f'unit-{number:02d}'
    output.mkdir(exist_ok=False)
    campaign.load_fixture()
    sources = campaign.source_files()
    test_paths = {f'tests/replay/{name}.py' for name in NAMES}
    tests = {name: campaign.sha((ROOT / 'studio' / name).read_bytes()) for name in sorted(test_paths)}
    command = [sys.executable, '-B', '-m', 'unittest'] + [
        'studio.tests.replay.' + name for name in NAMES]
    campaign.write(output / 'request.json', {'command': command, 'source_files': sources,
        'source_closure_sha256': campaign.closure(sources), 'tests': tests,
        'profile_sha256': campaign.profile.PROFILE_SHA256,
        'driver_sha256': campaign.sha(Path(__file__).read_bytes()), 'formal_acceptance': False})
    started = time.monotonic()
    with (output / 'stdout.txt').open('xb') as stdout, (output / 'stderr.txt').open('xb') as stderr:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr)
        code = process.wait(timeout=180)
    log = (output / 'stderr.txt').read_text(encoding='utf-8')
    count = re.search(r'Ran (\d+) tests? in ', log)
    unchanged = all(campaign.sha((ROOT / 'studio' / name).read_bytes()) == digest
                    for name, digest in (sources | tests).items())
    result = {'actual_pid': process.pid, 'actual_exit_code': code,
        'elapsed_seconds': time.monotonic() - started, 'test_count': int(count[1]) if count else None,
        'source_unchanged': unchanged, 'formal_acceptance': False,
        'logs': {name: campaign.sha((output / name).read_bytes()) for name in ('stdout.txt', 'stderr.txt')}}
    campaign.write(output / 'result.json', result)
    print(json.dumps(result))
    return 0 if code == 0 and count and unchanged else 1


if __name__ == '__main__':
    raise SystemExit(main())
