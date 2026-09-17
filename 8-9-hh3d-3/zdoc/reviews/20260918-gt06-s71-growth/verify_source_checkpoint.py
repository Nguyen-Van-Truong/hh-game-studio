"""Check exact campaign runtime bytes against index or a named Git revision."""
from pathlib import Path
import argparse
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from studio.tests.replay import run_benchmark_campaign as campaign

parser = argparse.ArgumentParser()
parser.add_argument('revision')
parser.add_argument('--output', required=True)
args = parser.parse_args()
campaign.load_fixture()
source = campaign.source_files()
for relative, digest in source.items():
    path = '8-9-hh3d-3/studio/' + relative
    object_name = ':' + path if args.revision == 'index' else args.revision + ':' + path
    raw = subprocess.check_output(['git', 'show', object_name], cwd=ROOT.parent)
    assert campaign.sha(raw) == digest, relative
result = {'revision': args.revision, 'exact_git_bytes': True, 'source_count': len(source),
    'source_closure_sha256': campaign.closure(source), 'source_files': source,
    'benchmark_profile_sha256': campaign.profile.PROFILE_SHA256,
    'formal_acceptance': False}
target = Path(args.output)
with target.open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(result, stream, indent=2)
    stream.write('\n')
print(json.dumps({key: value for key, value in result.items() if key != 'source_files'}))
