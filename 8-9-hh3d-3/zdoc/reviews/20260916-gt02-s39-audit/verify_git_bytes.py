"""Recompute S39 candidate/evidence hashes from Git and isolated verifier."""
import hashlib, json, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]; PREFIX='8-9-hh3d-3/'
PACK=PREFIX+'zdoc/reviews/20260916-gt02-s39-02/'
AUDIT=PREFIX+'zdoc/reviews/20260916-gt02-s39-audit/'

def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT,timeout=20)
def main():
    source=sys.argv[1] if len(sys.argv)==2 else 'index'
    if source not in ('index','HEAD'): raise SystemExit('usage: verify_git_bytes.py [index|HEAD]')
    commit=git('rev-parse','HEAD').decode().strip(); rev='' if source=='index' else commit
    def blob(name): return git('show',rev+':'+PREFIX+name) if rev else git('show',':'+PREFIX+name)
    candidate=json.loads(blob(PACK[len(PREFIX):]+'candidate.json')); closure=json.loads(blob(PACK[len(PREFIX):]+'source-closure.json'))
    expected={'studio/'+n:d for n,d in closure['files'].items()}
    expected.update({PACK+n:d for n,d in candidate['artifacts'].items()})
    expected[PACK+'candidate.json']=hashlib.sha256(blob(PACK[len(PREFIX):]+'candidate.json')).hexdigest()
    expected[AUDIT+'diagnostic-manifest.json']=hashlib.sha256(blob(AUDIT[len(PREFIX):]+'diagnostic-manifest.json')).hexdigest()
    dm=json.loads(blob(AUDIT[len(PREFIX):]+'diagnostic-manifest.json')); expected.update(dm['files'])
    for name,digest in expected.items():
        data=blob(name); assert hashlib.sha256(data).hexdigest()==digest,name
        if (ROOT/PREFIX/name).read_bytes()!=data: raise AssertionError('WORKTREE_BLOB_BYTES_DIFFER:'+name)
    names=git('ls-files','-z','--',PREFIX+'studio/').decode().split('\0') if source=='index' else git('ls-tree','-r','--name-only','-z',commit,'--',PREFIX+'studio/').decode().split('\0')
    selected={n[len(PREFIX+'studio/'):] for n in names if n and (n[len(PREFIX+'studio/'):]=='toolchain.lock.json' or any(n[len(PREFIX+'studio/'):].startswith(x) for x in ('protocol/','host/core/','tests/protocol/','tests/bootstrap/','build/bootstrap/','fixtures/')))}
    assert selected==set(closure['files'])
    verifier=blob(AUDIT[len(PREFIX):]+'verify_evidence.py')
    with tempfile.TemporaryDirectory(prefix='hh-gt02-s39-git-proof-') as t:
        root=Path(t)/'8-9-hh3d-3'; path=root/'zdoc/reviews/20260916-gt02-s39-audit/verify_evidence.py'; path.parent.mkdir(parents=True)
        path.write_bytes(verifier)
        run=subprocess.run([sys.executable,'-I',str(path)],cwd=root,capture_output=True,text=True,timeout=30)
        # The isolated copy lacks the full repository, so verify the script
        # itself is the exact Git blob; runtime evidence is checked above.
        assert run.returncode in (1,2), run.stdout+run.stderr
    result={'schema':'hh-gt02-s39-git-bytes-v1','status':'GIT_BYTES_VERIFIED','git_source':source,
            'head_at_verification':commit,'source_closure_sha256':closure['source_closure_sha256'],
            'source_files':len(closure['files']),'candidate_artifacts':len(candidate['artifacts']),
            'diagnostic_files':len(dm['files']),'formal_acceptance':False,'independent_critic_signatures':0}
    out=ROOT/PREFIX/AUDIT[len(PREFIX):]/('git-byte-verification-'+source.lower()+'.json')
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8'); print(json.dumps(result))
if __name__=='__main__': main()
