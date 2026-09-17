"""Exact S59 byte inventory; excludes private working roots and lock files."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REVIEWS=HERE.parent
ROOT=REVIEWS.parent.parent
REPO=ROOT.parent

def sha(raw): return hashlib.sha256(raw).hexdigest()

def inventory():
    files={}
    def add(path,expected=None):
        path=path.resolve();path.relative_to(ROOT)
        assert path.is_file() and not path.is_symlink() and path.name!='.writer'
        digest=sha(path.read_bytes());assert expected is None or digest==expected,str(path)
        files[path.relative_to(REPO).as_posix()]=digest
    for name,digest in json.loads((HERE/'portable-artifacts.json').read_bytes()).items():add(ROOT/name,digest)
    source=json.loads((REVIEWS/'20260917-gt04-s59-scene-01/source-closure.json').read_bytes())['files']
    for name,digest in source.items():add(ROOT/'studio'/name,digest)
    for name in ('.gitattributes','AGENTS.md','zdoc/8-9-godot-blender-agent-studio-plan.txt'):add(ROOT/name)
    add(REVIEWS/'20260917-gt04-s58-audit/git-HEAD.json')
    for relative in ('20260917-gt04-s56-audit/verify_evidence.py','20260917-gt03-s55-audit/checkpoint.py'):
        add(REVIEWS/relative)
    for folder, lane in [('20260917-gt04-s59-matrix','ui'),('20260917-gt04-s59-matrix-02','stop_after_selector')]:
        base=REVIEWS/folder
        for name in ('binding.py','matrix.py','publication_recovery_bound.py','execution-closure.json'):
            add(base/name)
        if (base/'failure-note.json').exists():add(base/'failure-note.json')
        for path in (base/lane).rglob('*'):
            if path.is_file() and path.name!='.writer' and not path.name.endswith('.guard') and not any(part in ('__pycache__','.cache','temp') or part.endswith('-temp') for part in path.parts):
                add(path)
    for path in HERE.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.name not in ('files.json','paths.nul','git-index.json','git-HEAD.json','review-closure.json'):add(path)
    return dict(sorted(files.items()))

def main():
    mode=sys.argv[1]
    if mode=='inventory':
        files=inventory()
        review={'files':files,'review_closure_sha256':sha(json.dumps(files,sort_keys=True,separators=(',',':')).encode()),'formal_acceptance':False}
        (HERE/'review-closure.json').write_text(json.dumps(review,indent=2)+'\n',encoding='utf-8',newline='\n')
        files[(HERE/'review-closure.json').relative_to(REPO).as_posix()]=sha((HERE/'review-closure.json').read_bytes())
        files=dict(sorted(files.items()))
        saved={'files':files,'files_sha256':sha(json.dumps(files,sort_keys=True,separators=(',',':')).encode())}
        (HERE/'files.json').write_text(json.dumps(saved,indent=2)+'\n',encoding='utf-8',newline='\n')
        (HERE/'paths.nul').write_bytes(b''.join(name.encode()+b'\0' for name in files))
    else:
        assert mode in ('index','HEAD')
        saved=json.loads((HERE/'files.json').read_bytes())
        for name,digest in saved['files'].items():assert sha((REPO/name).read_bytes())==digest,name
        spec=importlib.util.spec_from_file_location('git_bytes',REVIEWS/'20260917-gt03-s55-audit/checkpoint.py')
        helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
        helper.verify_git(saved['files'],mode)
        result={'passed':True,'files':len(saved['files']),'files_sha256':saved['files_sha256'],'ref':mode,
            'head_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO).decode().strip(),'formal_acceptance':False}
        (HERE/('git-'+mode+'.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'mode':mode,'files':len(saved['files']),'files_sha256':saved['files_sha256']}))

if __name__=='__main__':main()
