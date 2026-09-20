"""Preserve prior plan bytes and publish derived source/status metadata only."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
from studio.tests.replay import run_benchmark_campaign as campaign

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    campaign.load_fixture()
    sources = campaign.source_files()
    result = {'authority': 0, 'source_files': sources,
              'source_closure': campaign.closure(sources),
              'profile_sha256': campaign.profile.PROFILE_SHA256,
              'transport_sha256': sha((ROOT / 'studio/host/core/transport.py').read_bytes()),
              'regression_test_sha256': sha((ROOT / 'studio/tests/protocol/test_transport_pending_lookup.py').read_bytes())}
    for label in ('before-01', 'after-01', 'protocol-01'):
        folder = HERE / label
        receipt = json.loads((folder / 'receipt.json').read_bytes())
        for path, expected in receipt['files'].items():
            assert sha((folder / path).read_bytes()) == expected, (label, path)
    archive = HERE / 'archive'
    archive.mkdir(exist_ok=False)
    records = {}
    for relative in ('zdoc/8-9-godot-blender-agent-studio-plan.txt',
                     'zdoc/reviews/20260919-gt06-s123-lookup-repair/README.md',
                     'zdoc/reviews/20260919-gt06-s124-handle-decay/analysis.md'):
        path = ROOT / relative
        prior = subprocess.check_output(['git', 'show', 'HEAD:' + path.relative_to(REPO).as_posix()], cwd=REPO)
        name = 's124-plan.snapshot' if path.suffix == '.txt' else path.parent.name + '-' + path.name + '.snapshot'
        (archive / name).write_bytes(prior)
        records[name] = {'original_path': relative, 'sha256': sha(prior), 'authority': 0}
        if 's123-lookup' in relative:
            text = prior.decode('utf-8').replace('checkpoint `b624f1b4`', 'checkpoint `c4ae9cb2`')
            text += '\nS125 metadata correction: checkpoint label corrected; prior bytes retained in\n../20260920-gt06-s125-session-boundary/archive/. Raw S123 evidence is unchanged.\n'
            path.write_text(text, encoding='utf-8', newline='\n')
        elif 's124-handle' in relative:
            text = prior.decode('utf-8').replace(
                'S124 was intentionally instrumented and stopped at a bounded prefix, so it is\nnot byte-identical to stock formal `benchmark_native.gd` acceptance execution.',
                'S124 had host-side instrumentation and a bounded prefix. Its native\n`benchmark_native.gd` bytes were stock; the complete execution was diagnostic.')
            text += '\nS125 metadata correction: host/native instrumentation scope clarified; prior\nbytes retained in ../20260920-gt06-s125-session-boundary/archive/. Raw unchanged.\n'
            path.write_text(text, encoding='utf-8', newline='\n')
    (archive / 'manifest.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
    (HERE / 'source-manifest.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'source_files'}, indent=2))

if __name__ == '__main__':
    main()
