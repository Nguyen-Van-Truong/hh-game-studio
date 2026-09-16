"""Verify frozen source and S43 evidence against an index or commit tree."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

PRODUCT = Path(__file__).resolve().parents[3]
REPO = Path(subprocess.check_output(['git','rev-parse','--show-toplevel'], cwd=PRODUCT, text=True).strip())
PREFIX = PRODUCT.relative_to(REPO).as_posix()
REF = sys.argv[1] if len(sys.argv) > 1 else 'HEAD'
AUDIT = Path(__file__).resolve().parent

def git_bytes(relative):
    path = PREFIX + '/' + relative
    spec = ':' + path if REF == 'index' else REF + ':' + path
    return subprocess.check_output(['git', 'show', spec], cwd=REPO)

def digest(data):
    return hashlib.sha256(data).hexdigest()

source = json.loads(git_bytes('zdoc/reviews/20260916-gt02-s43-01/source-closure.json'))
rows = []
for relative, expected in sorted(source['files'].items()):
    actual = git_bytes('studio/' + relative)
    if digest(actual) != expected or actual != (PRODUCT/'studio'/relative).read_bytes():
        raise SystemExit('SOURCE_GIT_BYTES_MISMATCH: ' + relative)
    rows.append(PREFIX + '/studio/' + relative + '\0' + expected + '\n')
if digest(''.join(rows).encode()) != source['source_closure_sha256']:
    raise SystemExit('SOURCE_CLOSURE_MISMATCH')
checked = []
for folder in ('20260916-gt02-s43-01', '20260916-gt02-s43-native', '20260916-gt02-s43-audit'):
    for path in sorted((PRODUCT/'zdoc/reviews'/folder).rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts or path.name.startswith('git-byte-verification-'):
            continue
        relative = path.relative_to(PRODUCT).as_posix()
        if git_bytes(relative) != path.read_bytes():
            raise SystemExit('EVIDENCE_GIT_BYTES_MISMATCH: ' + relative)
        checked.append(relative)
record = {'status':'GIT_BYTES_VERIFIED','ref':REF,
          'head_at_verification':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
          'source_closure_sha256':source['source_closure_sha256'],
          'source_files':len(source['files']),'evidence_files':checked}
print(json.dumps(record))
(AUDIT/('git-byte-verification-' + ('index' if REF == 'index' else 'head') + '.json')).write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
