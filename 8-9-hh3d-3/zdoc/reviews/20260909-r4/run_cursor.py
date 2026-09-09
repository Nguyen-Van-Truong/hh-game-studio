"""Bounded, exact-model documentation review. No project mutations delegated.

Same launcher as reviews/20260908-r3/run_cursor.py (S4/S5 rounds); copied here because the
r3 intermediate files were removed from the working tree after commit aa5ae15.
"""
import argparse, datetime, json, pathlib, subprocess, time

p = argparse.ArgumentParser()
p.add_argument('prompt')
p.add_argument('stem')
p.add_argument('--seconds', type=int, default=600)
a = p.parse_args()
directory = pathlib.Path(__file__).resolve().parent
root = directory.parents[2]
prompt = pathlib.Path(a.prompt).read_text(encoding='utf-8-sig')
stem = directory / a.stem
# pwsh (PowerShell 7) is not on PATH in this host session; use the same Windows PowerShell 5.1
# launcher that agent.cmd uses, invoked directly so the UTF-8 prompt reaches argv as Unicode.
cmd = [r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
       '-File', r'C:\Users\truon\AppData\Local\cursor-agent\cursor-agent.ps1',
       '--workspace', str(root), '--model', 'cursor-grok-4.6-xhigh-fast',
       '--mode', 'ask', '--trust', '--force', '--print', '--output-format', 'json', prompt]
begin = time.monotonic()
(stem.with_suffix('.started.json')).write_text(json.dumps({
    'model': 'cursor-grok-4.6-xhigh-fast', 'mode': 'ask', 'started_at': datetime.datetime.now().astimezone().isoformat(),
    'workspace': str(root), 'prompt_file': a.prompt}, ensure_ascii=False, indent=2), encoding='utf-8')
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
        for v in ('VERDICT=ACCEPT', 'VERDICT=REVISE', 'VERDICT=INSUFFICIENT_EVIDENCE'):
            if v in report: status['verdict'] = v.split('=')[1]
    except (json.JSONDecodeError, AttributeError):
        status['parse_error'] = True
stem.with_suffix('.host.json').write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(status, ensure_ascii=False, indent=2))
if status['verdict_present']: print(stem.with_suffix('.md').read_text(encoding='utf-8'))
