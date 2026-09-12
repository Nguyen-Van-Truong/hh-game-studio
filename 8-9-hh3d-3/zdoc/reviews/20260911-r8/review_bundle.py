"""Validate a completed Grok bundle and stage it outside canonical source."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import py_compile
import re
import shutil

HERE = Path(__file__).resolve().parent
ALLOW = {
    'archive-repair': {'studio/build/bootstrap/verify_archive.py', 'studio/tests/bootstrap/test_verify_archive.py'},
    'archive-verify': {'studio/build/bootstrap/verify_archive.py', 'studio/tests/bootstrap/test_verify_archive.py'},
    'version-repair': {'studio/build/bootstrap/run_fixture.py', 'studio/tests/bootstrap/test_version_probe.py'},
    'version-check': {'studio/build/bootstrap/run_fixture.py', 'studio/tests/bootstrap/test_version_probe.py'},
    'runner-admission': {'studio/build/bootstrap/run_fixture.py', 'studio/tests/bootstrap/test_runner_admission.py'},
    'bootstrap-offline': {'studio/build/bootstrap/install_toolchain.py', 'studio/tests/bootstrap/test_install_toolchain.py'},
    'memory-trial': {'memory_trial.py'},
}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('role', choices=ALLOW)
    ap.add_argument('--poll', action='store_true')
    args = ap.parse_args()
    batch_path = HERE / (args.role + '-batch.local.json')
    batch = json.loads(batch_path.read_text(encoding='utf-8-sig'))
    if args.poll:
        if batch['polls_used'] >= 2:
            raise ValueError('Poll budget exhausted')
        batch['polls_used'] += 1
        batch_path.write_text(json.dumps(batch, indent=2), encoding='utf-8')
    job = batch['jobs'][0]
    attempt, work = Path(job['attempt_dir']), Path(job['workspace'])
    report = {'role': args.role, 'polls_used': batch['polls_used'], 'status': 'PENDING'}
    meta_path = attempt / 'runner-meta.json'
    if not meta_path.exists():
        print(json.dumps(report)); return
    meta = json.loads(meta_path.read_text(encoding='utf-8-sig'))
    report['host'] = meta
    try:
        if meta['exit_code'] != 0 or meta['timed_out'] or meta['launcher_error']:
            raise ValueError('Worker did not complete normally')
        for row in json.loads((work / 'input-manifest.json').read_text(encoding='utf-8')):
            if sha(work / row['path']) != row['sha256']:
                raise ValueError('Read-only input changed: ' + row['path'])
        response = work / 'response.txt'
        report['response_sha256'] = sha(response)
        raw = response.read_text(encoding='utf-8-sig')
        if len(raw) > 500000:
            raise ValueError('Oversized response')
        fenced = re.fullmatch(r'\s*```json\s*\n([\s\S]*?)\n```\s*', raw)
        if fenced:
            # Transport-only normalization. Inner JSON still parses strictly.
            report['delivery_warning'] = 'One Markdown JSON fence removed; raw response retained'
            raw = fenced.group(1)
        data = json.loads(raw, object_pairs_hook=unique_object)
        writes = {}
        for item in data.get('edits', []):
            path = item['path']
            if path not in ALLOW[args.role]:
                raise ValueError('Out-of-lease edit')
            text = writes.get(path, (work / path).read_text(encoding='utf-8'))
            if not item['old'] or text.count(item['old']) != 1:
                raise ValueError('Old block does not match exactly once: ' + path)
            writes[path] = text.replace(item['old'], item['new'], 1)
        for item in data.get('files', []):
            path = item['path']
            if path not in ALLOW[args.role] or path in writes or (work / path).exists():
                raise ValueError('New file invalid/out-of-lease/duplicate: ' + path)
            writes[path] = item['content']
        if not writes:
            raise ValueError('Empty bundle')
        stage = attempt / 'coordinator-stage'
        if stage.exists():
            raise ValueError('Stage exists; do not overwrite reviewed artifacts')
        shutil.copytree(work, stage, ignore=shutil.ignore_patterns('response.txt'))
        changes = []
        for path, content in writes.items():
            if PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts:
                raise ValueError('Unsafe path')
            target = stage / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8', newline='\n')
            if target.suffix == '.py':
                py_compile.compile(str(target), doraise=True)
            changes.append({'path': path, 'sha256': sha(target), 'lines': len(content.splitlines())})
        report.update(status='STAGED_NOT_REVIEWED', changes=changes, stage=str(stage), limitations=data.get('limitations', []))
    except Exception as exc:
        report.update(status='REJECTED', reason=str(exc))
    destination = attempt / 'coordinator-review.json'
    if destination.exists():
        sequence = 2
        while (attempt / f'coordinator-review-{sequence}.json').exists():
            sequence += 1
        destination = attempt / f'coordinator-review-{sequence}.json'
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))

if __name__ == '__main__':
    main()
