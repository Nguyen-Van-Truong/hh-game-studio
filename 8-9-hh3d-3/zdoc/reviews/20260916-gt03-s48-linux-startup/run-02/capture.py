"""Owned existing-Docker startup only. No pulls, installs, service changes or pruning."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import uuid

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
STUDIO = PROJECT / 'studio'
DOCKER = 'C:/Program Files/Docker/Docker/resources/bin/docker.exe'
spec = importlib.util.spec_from_file_location('gt03_owned_runner', STUDIO / 'build/bootstrap/run_fixture.py')
owned = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owned)
BASE = [DOCKER, '--context', 'desktop-linux']
HELPER = "import subprocess,sys; token=sys.stdin.readline(); sys.exit(125) if token != 'GO\\n' else None; p=subprocess.Popen(sys.argv[1:],stdin=subprocess.DEVNULL); sys.exit(p.wait())"


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def cli(args, output, label, timeout=20, cap=262144):
    start = time.monotonic()
    p = subprocess.Popen([sys.executable, '-B', '-c', HELPER, *BASE, *args],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    job = None
    chunks = [bytearray(), bytearray()]
    counts = [0, 0]
    exceeded = threading.Event()
    readers = []
    def read(stream, index):
        while True:
            block = stream.read(4096)
            if not block:
                return
            counts[index] += len(block)
            room = max(0, cap - len(chunks[index]))
            chunks[index].extend(block[:room])
            if counts[index] > cap:
                exceeded.set()
    timed_out = False
    try:
        job = owned._job_for_process(p)
        for i, stream in enumerate((p.stdout, p.stderr)):
            thread = threading.Thread(target=read, args=(stream, i), daemon=True)
            readers.append(thread)
            thread.start()
        p.stdin.write(b'GO\n')
        p.stdin.close()
        while p.poll() is None:
            timed_out = time.monotonic() - start >= timeout
            if timed_out or exceeded.is_set():
                owned._terminate_job(job)
                break
            time.sleep(0.02)
        p.wait(timeout=3)
        for thread in readers:
            thread.join(timeout=2)
        active = owned._job_active_count(job)
        settle_deadline = time.monotonic() + 1
        while active != 0 and time.monotonic() < settle_deadline:
            time.sleep(0.02)
            active = owned._job_active_count(job)
        row = {'argv': ['docker.exe', '--context', 'desktop-linux', *args],
               'exit_code': p.returncode, 'timeout_seconds': timeout, 'timed_out': timed_out,
               'stream_cap_bytes_each': cap, 'stream_byte_counts': counts,
               'stream_cap_exceeded': exceeded.is_set(), 'readers_stopped': all(not t.is_alive() for t in readers),
               'job_active_count': active, 'elapsed_seconds': round(time.monotonic() - start, 3)}
        for i, stream in enumerate(('stdout', 'stderr')):
            (output / (label + '-' + stream + '.txt')).write_bytes(bytes(chunks[i]))
        save(output / (label + '-host.json'), row)
        if timed_out or exceeded.is_set() or active != 0 or not row['readers_stopped']:
            raise RuntimeError('BOUNDED_CLI_FAILED:' + label)
        return row, bytes(chunks[0]), bytes(chunks[1])
    finally:
        if job and owned._job_active_count(job) != 0:
            owned._terminate_job(job)
        if p.poll() is None:
            p.kill()
            p.wait(timeout=3)
        owned._close_job(job)


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r'run-[0-9]{2}', sys.argv[1]):
        raise SystemExit('usage: capture.py run-NN')
    output = HERE / sys.argv[1]
    output.mkdir(exist_ok=False)
    (output / 'capture.py').write_bytes(Path(__file__).read_bytes())
    (output / 'startup_inside.py').write_bytes((HERE / 'harness/startup_inside.py').read_bytes())
    run_id = 'hh-gt03-' + uuid.uuid4().hex
    tool = STUDIO / '.local/tooling/godot-4.7.2-stable-linux'
    binary = tool / 'Godot_v4.7.2-stable_linux.x86_64'
    expected = '8d106cbe6144c2dc7e881d61d2429c1a8a76e6b22ef48bd5e48dcf934953f71e'
    if hashlib.sha256(binary.read_bytes()).hexdigest() != expected:
        raise RuntimeError('binary pin mismatch')
    image_row, raw, _ = cli(['image', 'inspect', 'python:3.12-bookworm'], output, 'image-inspect')
    if image_row['exit_code'] != 0:
        raise RuntimeError('base image unavailable')
    info = json.loads(raw)[0]
    config = info['Config']
    if info['Os'] != 'linux' or info['Architecture'] != 'amd64' or config.get('Volumes'):
        raise RuntimeError('unapproved image shape')
    image_id = info['Id']
    save(output / 'image-selection.json', {'id': image_id, 'repo_digests': info.get('RepoDigests'),
         'os': info['Os'], 'architecture': info['Architecture'], 'volumes': config.get('Volumes'),
         'entrypoint': config.get('Entrypoint'), 'environment_names': [x.partition('=')[0] for x in config.get('Env', [])]})
    input_path = output / 'input'
    input_path.mkdir()
    (input_path / '.godot').mkdir()
    (input_path / 'project.godot').write_text('config_version=5\n[application]\nconfig/name="HH GT03 startup only"\n', encoding='utf-8')
    create = ['create', '--pull=never', '--name', run_id, '--label', 'hh.gt03.owner=' + run_id,
              '--platform', 'linux/amd64', '--read-only', '--network', 'none', '--ipc', 'private',
              '--cgroupns', 'private', '--user', '65532:65532', '--cap-drop', 'ALL',
              '--security-opt', 'no-new-privileges=true', '--security-opt', 'seccomp=builtin',
              '--memory', '1g', '--memory-swap', '1g', '--cpus', '1', '--pids-limit', '64',
              '--ulimit', 'fsize=8388608:8388608', '--ulimit', 'core=0:0', '--ulimit', 'cpu=10:10',
              '--ulimit', 'nofile=256:256', '--ulimit', 'msgqueue=8192:8192',
              '--log-driver', 'none', '--restart', 'no', '--no-healthcheck', '--stop-timeout', '2',
              '--shm-size', '16m', '--workdir', '/project',
              '--env', 'HOME=/home/validator', '--env', 'TMPDIR=/tmp',
              '--env', 'XDG_CACHE_HOME=/home/validator/cache', '--env', 'XDG_CONFIG_HOME=/home/validator/config',
              '--env', 'XDG_DATA_HOME=/home/validator/data', '--env', 'XDG_RUNTIME_DIR=/run',
              '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'PYTHONUNBUFFERED=1']
    for destination, size, inodes in (('/tmp', '16m', 2048), ('/home/validator', '16m', 2048),
                                     ('/run', '4m', 512), ('/project/.godot', '64m', 8192)):
        create += ['--tmpfs', destination + ':rw,nosuid,nodev,noexec,size=' + size + ',nr_inodes=' + str(inodes) + ',uid=65532,gid=65532,mode=0700']
    for source, destination in ((tool, '/tool'), (HERE / 'harness', '/harness'), (input_path, '/project')):
        create += ['--mount', 'type=bind,src=' + str(source.resolve()) + ',dst=' + destination + ',readonly,bind-propagation=rprivate']
    create += ['--entrypoint', '/usr/local/bin/python3', image_id, '-B', '/harness/startup_inside.py']
    container_id = None
    result = {'authority': 0, 'scope': 'TRUSTED_VERSION_STARTUP_ONLY', 'run_id': run_id,
              'image_id': image_id, 'binary_sha256': expected, 'sandbox_acceptance': False,
              'owned_removed': False, 'container_state': None}
    save(output / 'source.json', {'capture.py': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         'startup_inside.py': hashlib.sha256((HERE / 'harness/startup_inside.py').read_bytes()).hexdigest(),
         'owned_runner': hashlib.sha256((STUDIO / 'build/bootstrap/run_fixture.py').read_bytes()).hexdigest()})
    save(output / 'create-argv.json', create)
    try:
        row, raw, _ = cli(create, output, 'create', cap=4096)
        candidate = raw.decode().strip()
        if row['exit_code'] != 0 or not re.fullmatch(r'[0-9a-f]{64}', candidate):
            raise RuntimeError('create failed; preserve name for bounded reconciliation: ' + run_id)
        container_id = candidate
        result['container_id'] = container_id
        row, raw, _ = cli(['inspect', container_id], output, 'created-inspect')
        state = json.loads(raw)[0]
        if state['Id'] != container_id or state['Config']['Labels'].get('hh.gt03.owner') != run_id:
            raise RuntimeError('owned identity mismatch')
        host = state['HostConfig']
        if not (state['Image'] == image_id and state['Config']['User'] == '65532:65532'
                and host['ReadonlyRootfs'] is True and host['NetworkMode'] == 'none'
                and host['CapDrop'] == ['ALL'] and host['Memory'] == 1073741824
                and host['MemorySwap'] == 1073741824 and host['NanoCpus'] == 1000000000
                and host['PidsLimit'] == 64 and host['LogConfig']['Type'] == 'none'
                and host['RestartPolicy']['Name'] == 'no' and host['Privileged'] is False
                and 'no-new-privileges=true' in host['SecurityOpt']
                and 'seccomp=builtin' in host['SecurityOpt']
                and all(mount['RW'] is False for mount in state['Mounts'] if mount['Type'] == 'bind')):
            raise RuntimeError('created confinement configuration mismatch')
        row, raw, _ = cli(['start', '--attach', container_id], output, 'startup')
        result['startup_cli_exit'] = row['exit_code']
        try:
            result['observation'] = json.loads(raw)
        except (ValueError, UnicodeError):
            result['observation'] = None
        row, raw, _ = cli(['wait', container_id], output, 'wait', timeout=5, cap=1024)
        result['docker_wait_exit'] = int(raw.decode().strip()) if row['exit_code'] == 0 else None
        row, raw, _ = cli(['inspect', container_id], output, 'exited-inspect')
        observed = json.loads(raw)[0]
        result['container_state'] = observed['State']
        result['startup_ok'] = (result['startup_cli_exit'] == 0 and result['docker_wait_exit'] == 0
            and not observed['State']['Running'] and observed['State']['Pid'] == 0
            and observed['State']['ExitCode'] == 0 and result['observation'] is not None
            and result['observation'].get('godot_exit') == 0)
    except Exception as exc:
        result['error'] = str(exc)
    finally:
        if container_id is None:
            # A lost create reply is reconciled by the unique owned label/name;
            # only the recovered exact ID is ever passed to destructive cleanup.
            row, raw, _ = cli(['inspect', run_id], output, 'create-reconciliation', timeout=5)
            if row['exit_code'] == 0:
                recovered = json.loads(raw)[0]
                if (re.fullmatch(r'[0-9a-f]{64}', recovered['Id'])
                        and recovered['Config']['Labels'].get('hh.gt03.owner') == run_id
                        and recovered['Name'] == '/' + run_id and recovered['Image'] == image_id):
                    container_id = recovered['Id']
                    result['container_id'] = container_id
        if container_id:
            row, raw, _ = cli(['inspect', container_id], output, 'cleanup-inspect')
            state = json.loads(raw)[0] if row['exit_code'] == 0 else None
            if state and state['Id'] == container_id and state['Config']['Labels'].get('hh.gt03.owner') == run_id:
                if state['State']['Running']:
                    cli(['kill', container_id], output, 'owned-kill', timeout=5, cap=1024)
                    cli(['wait', container_id], output, 'owned-kill-wait', timeout=5, cap=1024)
                row, _, _ = cli(['rm', container_id], output, 'owned-remove', timeout=5, cap=1024)
                verify, _, _ = cli(['inspect', container_id], output, 'removed-inspect', timeout=5, cap=4096)
                result['owned_removed'] = row['exit_code'] == 0 and verify['exit_code'] == 1
            else:
                result['cleanup_error'] = 'OWNED_IDENTITY_UNPROVEN'
        result['binary_unchanged'] = hashlib.sha256(binary.read_bytes()).hexdigest() == expected
        save(output / 'result.json', result)
    print(json.dumps({key: value for key, value in result.items() if key != 'observation'}), flush=True)
    return 0 if result.get('startup_ok') and result['owned_removed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
