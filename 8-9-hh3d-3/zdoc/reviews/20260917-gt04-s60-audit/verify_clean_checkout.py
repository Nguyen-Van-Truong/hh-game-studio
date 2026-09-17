"""Reconstruct exact staged bytes and verify views with no original raw present."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
REPO = ROOT.parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    saved = json.loads((HERE / 'files.json').read_bytes())
    files = saved['files']
    clone = ROOT / 'studio/.local/repro/gt04-s60-git-view-01'
    clone.mkdir(parents=True, exist_ok=False)
    stream = subprocess.run(['git', 'cat-file', '--batch'], cwd=REPO,
        input=''.join(':' + name + '\n' for name in files).encode(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=True).stdout
    cursor = 0
    for name, digest in files.items():
        end = stream.index(b'\n', cursor)
        header = stream[cursor:end].split()
        assert len(header) == 3 and header[1] == b'blob', name
        size = int(header[2]); cursor = end + 1
        raw = stream[cursor:cursor + size]; cursor += size
        assert stream[cursor:cursor + 1] == b'\n' and sha(raw) == digest, name
        cursor += 1
        path = clone / name
        path.resolve().relative_to(clone.resolve())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    assert cursor == len(stream)
    child_root = clone / ROOT.name
    child_script = child_root / HERE.relative_to(ROOT) / 'verify_views.py'
    assert not (child_root / 'studio/.local/reviews').exists()
    spec = importlib.util.spec_from_file_location('owned_runner', ROOT/'studio/build/bootstrap/run_fixture.py')
    runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
    evidence = clone / 'verification'; evidence.mkdir()
    good = runner.run_process([sys.executable, '-B', str(child_script)],
        cwd=child_root, output=evidence, timeout=30, label='portable')
    assert good['exit_code'] == good['wrapper_exit_code'] == 0 and good['tree_verified'] and not good['timed_out']
    assert not (evidence/'portable-stderr.txt').read_bytes()
    report = json.loads((evidence/'portable-stdout.txt').read_bytes())
    assert report['passed'] and report['local_raw_verified'] is False
    # Controlled missing-original probe: fail closed, without emitting a
    # traceback containing paths or accepting the sanitized view as the raw.
    code = ("import importlib.util,json; from pathlib import Path; "
            "p=Path(" + repr(str(child_script)) + "); "
            "s=importlib.util.spec_from_file_location('views',p); "
            "m=importlib.util.module_from_spec(s); s.loader.exec_module(m)\n"
            "try: m.verify(local=True)\n"
            "except FileNotFoundError: print('MISSING_LOCAL_RAW_REJECTED',flush=True)\n"
            "else: raise SystemExit(3)\n")
    # Support module resolution is confined to the reconstructed audit path.
    code = 'import sys; sys.path.insert(0,' + repr(str(child_script.parent)) + ')\n' + code
    missing = runner.run_process([sys.executable, '-B', '-c', code],
        cwd=child_root, output=evidence, timeout=30, label='missing-raw')
    assert missing['exit_code'] == missing['wrapper_exit_code'] == 0 and missing['tree_verified']
    assert (evidence/'missing-raw-stdout.txt').read_bytes().strip() == b'MISSING_LOCAL_RAW_REJECTED'
    assert not (evidence/'missing-raw-stderr.txt').read_bytes()
    result = {'passed': True, 'reconstructed_files': len(files),
              'reconstructed_files_sha256': saved['files_sha256'], 'git_ref': 'index',
              'portable_integrity': True, 'missing_raw_rejected': True,
              'actual_wrapper_and_target_exits_zero': True, 'owned_trees_clean': True,
              'exact_original_bytes_reconstructed': False, 'native_engines_launched': 0,
              'formal_acceptance': False,
              'local_proof_directory': evidence.relative_to(ROOT).as_posix()}
    (HERE/'clean-checkout.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
