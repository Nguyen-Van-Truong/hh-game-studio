"""Bounded, exact-model documentation review. No project mutations delegated."""
import argparse, datetime, json, pathlib, subprocess, time

p = argparse.ArgumentParser()
p.add_argument('prompt')
p.add_argument('stem')
p.add_argument('--seconds', type=int, default=300)
a = p.parse_args()
directory = pathlib.Path(__file__).resolve().parent
root = directory.parents[2]
prompt = pathlib.Path(a.prompt).read_text(encoding='utf-8-sig')
stem = directory / a.stem
cmd = ['pwsh', '-NoProfile', '-File', r'C:\Users\truon\AppData\Local\cursor-agent\agent.ps1',
       '--workspace', str(root), '--model', 'cursor-grok-4.6-xhigh-fast',
       '--mode', 'ask', '--trust', '--force', '--print', '--output-format', 'json', prompt]
begin = time.monotonic()
with stem.with_suffix('.stdout').open('wb') as out, stem.with_suffix('.stderr').open('wb') as err:
    proc = subprocess.Popen(cmd, stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW)
    timed_out = False
    try:
        code = proc.wait(timeout=a.seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True, timeout=20)
        code = proc.wait(timeout=20)
raw = stem.with_suffix('.stdout').read_text(encoding='utf-8-sig', errors='replace')
error = stem.with_suffix('.stderr').read_text(encoding='utf-8-sig', errors='replace')
status = {'model': 'cursor-grok-4.6-xhigh-fast', 'exit': code, 'timeout': timed_out,
          'elapsed_s': round(time.monotonic()-begin, 2), 'stdout_bytes': len(raw.encode()),
          'finished_at': datetime.datetime.now().astimezone().isoformat(),
          'error_excerpt': error[:800], 'verdict_present': False}
if code == 0 and raw.strip():
    try:
        parsed = json.loads(raw)
        report = parsed.get('result', raw)
        if not isinstance(report, str): report = json.dumps(report, ensure_ascii=False, indent=2)
        stem.with_suffix('.md').write_text(report, encoding='utf-8')
        status['verdict_present'] = True
    except (json.JSONDecodeError, AttributeError):
        status['parse_error'] = True
stem.with_suffix('.host.json').write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(status, ensure_ascii=False, indent=2))
if status['verdict_present']: print(stem.with_suffix('.md').read_text(encoding='utf-8'))
