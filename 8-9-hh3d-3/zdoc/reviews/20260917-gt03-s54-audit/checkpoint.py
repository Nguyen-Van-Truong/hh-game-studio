"""Curate S54 WIP bytes for Git; this is not a conformance/acceptance audit."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
REPO=ROOT.parent
REVIEWS=ROOT/'zdoc/reviews'
AUDITS={
    '20260917-gt03-s54-edit-audit':('portable-manifest.json',ROOT),
    '20260917-gt03-s54-recovery-publication-audit':('portable-manifest.json',REVIEWS),
    '20260917-gt04-publication-audit':('portable-artifacts.json',ROOT),
    '20260917-gt04-fifo-audit':('portable-artifacts.json',ROOT),
    '20260917-gt04-material-audit':('portable-artifacts.json',ROOT),
    '20260917-gt04-durable-audit':('portable-artifacts.json',ROOT),
}


def sha(raw):return hashlib.sha256(raw).hexdigest()


def inventory():
    files={}
    def add(path,expected=None):
        path=path.resolve();name=path.relative_to(REPO).as_posix()
        path.relative_to(ROOT)
        assert not set(path.relative_to(ROOT).parts)&{'__pycache__','.godot','storage','appdata','localappdata','temp'},name
        raw=path.read_bytes();digest=sha(raw)
        assert expected is None or digest==expected,'manifest mismatch: '+name
        assert name not in files or files[name]==digest,name
        files[name]=digest
    # Source scopes only. Ignored engines/caches are never enumerated here.
    scopes=['studio/godot-addon','studio/blender-addon','studio/host/blender','studio/tests/godot','studio/tests/blender']
    args=['git','ls-files','-z','--cached','--others','--exclude-standard','--']
    data=subprocess.check_output(args+[ROOT.name+'/'+s for s in scopes],cwd=REPO)
    for name in data.decode().split('\0'):
        if name:add(REPO/name)
    for name in ('.gitattributes','AGENTS.md','zdoc/8-9-godot-blender-agent-studio-plan.txt'):
        add(ROOT/name)
    for directory,(manifest,base) in AUDITS.items():
        audit=REVIEWS/directory
        for name,digest in json.loads((audit/manifest).read_text())['files'].items():add(base/name,digest)
        for path in audit.iterdir():
            if path.is_file():add(path)
    for path in (REVIEWS/'20260917-plan-history-s54').iterdir():
        if path.is_file():add(path)
    units=REVIEWS/'20260917-gt03-s54-units-01'
    frozen=json.loads((units/'source-closure.json').read_text())
    for name,digest in frozen['files'].items():add(units/'source/studio'/name,digest)
    for path in units.iterdir():
        if path.is_file():add(path)
    for path in HERE.iterdir():
        if path.is_file() and path.suffix in ('.py','.md'):add(path)
    return dict(sorted(files.items()))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--git-ref',choices=('index','HEAD'));args=parser.parse_args()
    files=inventory()
    if args.git_ref:
        prefix=':' if args.git_ref=='index' else 'HEAD:'
        result=subprocess.run(['git','cat-file','--batch'],input=''.join(prefix+n+'\n' for n in files).encode(),
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=REPO,check=True,timeout=60)
        cursor=0
        for name,digest in files.items():
            end=result.stdout.index(b'\n',cursor);header=result.stdout[cursor:end].split()
            assert len(header)==3 and header[1]==b'blob','missing Git blob: '+name
            size=int(header[2]);cursor=end+1;raw=result.stdout[cursor:cursor+size];cursor+=size
            assert result.stdout[cursor:cursor+1]==b'\n','batch framing';cursor+=1
            assert sha(raw)==digest,'Git bytes mismatch: '+name
        assert cursor==len(result.stdout),'unexpected Git output'
        report={'passed':True,'files':len(files),'ref':args.git_ref,'formal_acceptance':False}
        (HERE/('checkpoint-git-'+args.git_ref+'.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(report))
    else:
        (HERE/'checkpoint-files.json').write_text(json.dumps({'files':files,'formal_acceptance':False},indent=2)+'\n',encoding='utf-8',newline='\n')
        (HERE/'checkpoint-paths.txt').write_text('\n'.join(files)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps({'files':len(files),'formal_acceptance':False}))


if __name__=='__main__':main()
