"""Full HTTP batch for the repaired response schema; no native/performance verdict."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
SOURCE = BASE / 'repaired-source'
OUT = BASE / 'result-full' / 'child'
sys.path.insert(0, str(SOURCE))
from studio.tests.replay import benchmark_commands as b, benchmark_assembly as a


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def main():
    OUT.mkdir(exist_ok=False)
    frozen = json.loads((BASE / 'repaired-freeze.json').read_bytes())['files']
    assert all(sha(SOURCE / name) == digest for name, digest in frozen.items())
    original = ROOT / 'studio/.local/reviews/gt06-s91-sparse-attribution-01/commands/commands.jsonl'
    original_hash = sha(original)
    journal_type, host_type = b.Journal, b.LoopbackFixtureHost
    def journal(path):
        assert path.parent == OUT / 'commands' and not path.exists()
        shutil.copyfile(original, path)
        assert sha(path) == original_hash
        return journal_type(path)
    def host(_project, path, journal):
        return host_type('gt06.s93.full-http', path, journal)
    producer = None
    report = {'formal_acceptance': False, 'eligible_for_dataset': False, 'engine_runs': 0,
              'history_sha256': original_hash, 'history_bytes': original.stat().st_size}
    try:
        with patch.object(b, 'Journal', journal), patch.object(b, 'LoopbackFixtureHost', host):
            producer = b.CommandProducer(OUT / 'commands', 'gt06.s93.full-http')
            row = producer.run_batch(0)
            write(OUT / 'command.json', row)
            a.validate_command_batch(row, run_id=row['run_id'], index=0, host_identity=row['host_process'])
            report.update(validated_current_schema=True, commands=len(row['commands']), effects=row['effect_count_after'],
                          max_status_gap_ms=row['max_status_gap_ms'], status_gap_within_2000ms=row['max_status_gap_ms'] <= 2000)
    finally:
        if producer is not None:
            producer.close()
            report['closed'] = producer.closed
        report['history_unchanged'] = sha(original) == original_hash
        report['source_unchanged'] = all(sha(SOURCE / name) == digest for name, digest in frozen.items())
        report['loaded_modules'] = {}
        for name, module in list(sys.modules.items()):
            raw = getattr(module, '__file__', None)
            if name.startswith('studio.') and raw:
                path = Path(raw).resolve(); relative = path.relative_to(SOURCE.resolve()).as_posix()
                assert relative in frozen and sha(path) == frozen[relative]
                report['loaded_modules'][name] = {'path': relative, 'sha256': frozen[relative]}
        write(OUT / 'report.json', report)
    assert report['source_unchanged'] and report['history_unchanged'] and report['closed']
    assert report['validated_current_schema'] and report['status_gap_within_2000ms']


if __name__ == '__main__':
    main()
