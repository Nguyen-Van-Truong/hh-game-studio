"""Retain explicitly selected S107 raw evidence; fresh output only."""
from pathlib import Path
import json
import re
from verify_packet import sha, closure, need, load, safe, verify

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RAW = REPO/'studio/.local/reviews/gt06-s107-preview-01'
OUTER = RAW.with_name(RAW.name+'-outer')


def new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as out:
        out.write(data)


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)+'\n').encode()


def main():
    need(not (HERE/'manifest.json').exists(), 'OUTPUT_EXISTS')
    capture, context = load(RAW/'capture-manifest.json'), load(RAW/'context.json')
    selected = [(safe(RAW, entry['file']), HERE/'raw'/entry['file']) for entry in capture['files']]
    selected.append((RAW/'capture-manifest.json', HERE/'raw/capture-manifest.json'))
    for name in ('request.json','process-start.json','process-exit.json','observer-close.json','stdout.txt','stderr.txt'):
        selected.append((OUTER/name, HERE/'outer'/name))
    for path in context['diagnostic_files']:
        selected.append((REPO/path, HERE/'frozen'/Path(path).name))
    selected.append((REPO/'zdoc/reviews/20260919-gt06-s107-coordinator/observe_runner.ps1',
                     HERE/'observer/observe_runner.ps1'))
    exact = []
    for source, target in selected:
        raw = source.read_bytes()
        secret_screen(raw, str(source))
        new(target, raw)
        need(target.read_bytes() == raw, 'COPY_READBACK')
        exact.append({'original':str(source), 'portable':target.relative_to(HERE).as_posix(),
                      'sha256':sha(raw),'size_bytes':len(raw)})
    child = load(RAW/'child-result.json')
    new(HERE/'analysis.json', encode(child['analysis']))
    new(HERE/'raw-selected-domain.json', encode(exact))
    files = {path.relative_to(HERE).as_posix():sha(path.read_bytes()) for path in sorted(HERE.rglob('*'))
             if path.is_file() and '__pycache__' not in path.parts}
    manifest = {'schema':'gt06-s107-preview-result-packet-v1','authority':0,
                'formal_acceptance':False,'eligible_for_dataset':False,
                'base_source_closure_sha256':context['source_closure_sha256'],
                'exact_copies':exact,'files':files,'portable_closure_sha256':closure(files),
                'raw_selected_closure_sha256':closure({item['original']:item['sha256'] for item in exact}),
                'exclusions':['cache','localappdata','temp','unlisted outputs']}
    new(HERE/'manifest.json', encode(manifest))
    result=verify()
    new(HERE/'verification.json', encode(result))
    print(json.dumps(result, indent=2))


def secret_screen(raw, source):
    text = raw.decode('utf-8')
    need(not re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|Bearer\s+[A-Za-z0-9_.\-]{16,}|\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}', text), 'SECRET_PATTERN')
    if source.endswith('.json'):
        def visit(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    need(not (key.lower() in ('secret','token','password','authorization','credential','api_key','access_token') and child), 'SENSITIVE_JSON_KEY')
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        visit(json.loads(text))


if __name__ == '__main__':
    main()
