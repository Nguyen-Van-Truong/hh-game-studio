"""Four bounded comparisons using the retained S182 HTTP contention fixture."""
from pathlib import Path
import hashlib
import importlib.util
import inspect
import json
import os
import subprocess
import sys
import textwrap

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
OUT = ROOT/'studio/.local/reviews/gt06-s184-read-buffer-01'
BASE = Path(__file__).resolve().parent.parent/'20260923-gt06-s182-terminal/probe_poll_contention.py'


def child(label, size):
    from studio.host.replay.verified_journal import VerifiedJournal
    import studio.host.replay.verified_journal as journal_module
    from read_buffer import digest_stream
    if size:
        source = textwrap.dedent(inspect.getsource(VerifiedJournal._snapshot))
        start = source.index('            while chunk :=')
        end = source.index('            final = os.fstat', start)
        source = source[:start] + f'            size = digest_stream(stream, digest, self.limits.max_bytes, {size})\n' + source[end:]
        scope = dict(vars(journal_module), digest_stream=digest_stream)
        exec(compile(source, '<s184-read-buffer-candidate>', 'exec'), scope)
        VerifiedJournal._snapshot = scope['_snapshot']
    spec = importlib.util.spec_from_file_location('s182_probe', BASE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT, module.RUN = OUT/label, 'gt06-s184-'+label
    module.OUT.mkdir()
    module.child()


def main():
    if '--child' in sys.argv:
        child(sys.argv[2], int(sys.argv[3]))
        return
    OUT.mkdir(parents=False, exist_ok=False)
    results = []
    for label, size in [('stock-before',0),('buffer-256k',262144),('buffer-1m',1048576),('stock-after',0)]:
        with (OUT/(label+'-stdout.txt')).open('xb') as stdout, (OUT/(label+'-stderr.txt')).open('xb') as stderr:
            process = subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--child',label,str(size)],stdout=stdout,stderr=stderr)
            timed_out = False
            try:
                code = process.wait(timeout=120)
            except subprocess.TimeoutExpired:
                timed_out = True
                process.kill()
                code = process.wait(timeout=10)
        row = {'label':label,'buffer_bytes':size,'pid':process.pid,'actual_exit':code,'timeout':timed_out}
        results.append(row)
        with (OUT/(label+'-exit.json')).open('x') as f: json.dump(row,f,indent=2)
        if code:
            raise SystemExit(1)
    with (OUT/'exits.json').open('x') as f: json.dump(results,f,indent=2)
    print(json.dumps(results))


if __name__ == '__main__':
    main()
