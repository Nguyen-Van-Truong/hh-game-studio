"""Prepare one bounded Grok task; no launch or acceptance side effects on import."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import shutil
import tempfile
import uuid

HERE = Path(__file__).resolve().parent
SCOPE = HERE.parents[2]
REPO = SCOPE.parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('role')
    ap.add_argument('task', type=Path)
    ap.add_argument('--bundle', action='store_true')
    ap.add_argument('--web', action='store_true')
    ap.add_argument('--minutes', type=int, default=12)
    args = ap.parse_args()
    if not args.role.replace('-', '').isalnum() or not 1 <= args.minutes <= 20:
        ap.error('invalid role or deadline')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    batch_root = Path(tempfile.gettempdir()) / ('hh3d-r8-' + args.role + '-' + stamp)
    attempt = batch_root / args.role
    work = attempt / 'workspace'
    (work / 'inputs').mkdir(parents=True, exist_ok=False)
    shutil.copytree(SCOPE / 'studio', work / 'studio', ignore=shutil.ignore_patterns('.local', '.godot', '__pycache__', 'evidence', '*.pyc'))
    for name in ['8-9-godot-blender-agent-studio-plan.txt', '8-9-hh-world-gameplay-viet-nam-plan.txt']:
        shutil.copy2(SCOPE / 'zdoc' / name, work / 'inputs' / name)
    source = [{'path': p.relative_to(work).as_posix(), 'sha256': sha(p)} for p in sorted(work.rglob('*')) if p.is_file()]
    (work / 'input-manifest.json').write_text(json.dumps(source, indent=2), encoding='utf-8')
    task = args.task.read_text(encoding='utf-8')
    task = task.replace('$WORKSPACE', str(work)).replace('$PYTHON', __import__('sys').executable)
    (attempt / 'TASK.txt').write_text(task, encoding='utf-8')
    (work / 'AGENTS.md').write_text('Only follow TASK.txt supplied by coordinator. S19 GT-01 remains IN_PROGRESS. No canonical writes, git commits, global config changes, model fallback, or subagents. Never report unexecuted commands as executed.\n', encoding='utf-8')
    config = dict(id='hh3d-r8-' + args.role, attempt=stamp, session=str(uuid.uuid4()), workspace=str(work), notification_repo=str(REPO.parent / 'hoan-hao'), turn_limit=35, max_seconds=args.minutes * 60, notify=True, web_search=args.web)
    if args.bundle:
        config.update(delivery='JSON_BUNDLE', tools='read_file,list_dir,grep')
    (attempt / 'config.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
    shutil.copy2(HERE.parent / '20260910-r5' / 'Run-Worker.ps1', attempt / 'Run-Worker.ps1')
    batch = dict(schema='HH3D-WORKER-BATCH-1', created_utc=stamp, batch_root=str(batch_root), model='grok-4.6', reasoning_effort='xhigh', fast_flag='NOT_EXPOSED_BY_CLI', poll_budget=2, polls_used=0, jobs=[dict(role=args.role, attempt_dir=str(attempt), workspace=str(work), supervisor_pid=None, session=config['session'], task_sha256=sha(attempt / 'TASK.txt'))])
    path = HERE / (args.role + '-batch.local.json')
    path.write_text(json.dumps(batch, indent=2), encoding='utf-8')
    (batch_root / 'batch.json').write_text(json.dumps(batch, indent=2), encoding='utf-8')
    print(path)

if __name__ == '__main__':
    main()
