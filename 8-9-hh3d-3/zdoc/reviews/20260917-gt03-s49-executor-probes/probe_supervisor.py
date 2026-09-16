"""Owned bounded S49 supervisor diagnostics, never an acceptance runner."""
from pathlib import Path
import importlib.util
import json
import sys
import uuid

STUDIO = Path(__file__).resolve().parents[3] / 'studio'
spec = importlib.util.spec_from_file_location('s49_executor', STUDIO / 'godot-addon/linux_executor.py')
executor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(executor)


def probe(output, child, duration=4, supervisor=True):
    output.mkdir()
    owned = executor._owned_runner()
    name = 'hh-gt03-' + uuid.uuid4().hex
    cid = None
    result = {'name': name, 'public_ack': False, 'sandbox_acceptance': False}
    def call(args, label, timeout=8):
        return executor._cli(owned, args, output, label, timeout=timeout, cap=16384)
    def inspect(selector, label):
        row, raw = call(['inspect', selector], label)
        if not executor._cli_clean(row):
            return None
        values = json.loads(raw)
        return values[0] if len(values) == 1 else None
    args = ['create', '--pull=never', '--name', name, '--label', 'hh.gt03.owner=' + name,
            '--platform', 'linux/amd64', '--read-only', '--network', 'none', '--ipc', 'private',
            '--cgroupns', 'private', '--user', '65532:65532', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges=true', '--security-opt', 'seccomp=builtin',
            '--memory', '1g', '--memory-swap', '1g', '--cpus', '1', '--pids-limit', '64',
            '--log-driver', 'none', '--restart', 'no', '--no-healthcheck', '--shm-size', '16m']
    for key, value in executor.ULIMITS.items():
        args += ['--ulimit', f'{key}={value}:{value}']
    args += ['--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=16m,nr_inodes=2048,uid=65532,gid=65532,mode=0700']
    args += ['--entrypoint', '/usr/bin/timeout' if supervisor else '/usr/local/bin/python3', executor.IMAGE_ID]
    if supervisor:
        args += ['--signal=TERM', '--kill-after=1s', str(duration) + 's', '/usr/local/bin/python3']
    args += ['-B', '-c', child]
    executor._write(output / 'create-argv.json', args)
    try:
        row, raw = call(args, 'create')
        value = inspect(name, 'created-inspect')
        if value and executor._owned_identity(value, name):
            cid = value['Id']
        executor._need(cid and executor._cli_clean(row), 'PROBE_CREATE_UNCERTAIN')
        executor._need(value['Config']['Entrypoint'] == [args[args.index('--entrypoint') + 1]]
                       and value['HostConfig']['ReadonlyRootfs'] and not value.get('Mounts')
                       and value['HostConfig']['Memory'] == 1073741824
                       and value['HostConfig']['PidsLimit'] == 64
                       and value['HostConfig']['NetworkMode'] == 'none'
                       and value['HostConfig']['CapDrop'] == ['ALL']
                       and not value['HostConfig'].get('Init'), 'PROBE_CONFIG')
        result['command_host'], _ = call(['start', '--attach', cid], 'engine', timeout=duration + 5)
        value = inspect(cid, 'exited-inspect')
        executor._need(value and executor._owned_identity(value, name, cid), 'PROBE_EXIT_IDENTITY')
        result['state'] = value['State']
    finally:
        value = inspect(cid or name, 'cleanup-inspect')
        if value and executor._owned_identity(value, name, cid):
            cid = value['Id']
            if value['State']['Running']:
                call(['kill', cid], 'owned-kill')
                call(['wait', cid], 'owned-wait')
                value = inspect(cid, 'cleanup-exited-inspect')
            executor._need(value and not value['State']['Running'] and value['State']['Pid'] == 0, 'PROBE_NOT_STOPPED')
            result['final_state'] = value['State']
            row, _ = call(['rm', cid], 'owned-remove')
            executor._need(executor._cli_clean(row), 'PROBE_REMOVE')
            gone, _ = call(['inspect', cid], 'removed-inspect')
            result['owned_removed'] = gone['exit_code'] == 1 and ('no such object: ' + cid) in (output / gone['stderr']).read_text().lower()
        result['container_id'] = cid
        executor._write(output / 'result.json', result)
    return result


if __name__ == '__main__':
    code = "import pathlib,hashlib,json,subprocess,os; p=pathlib.Path('/usr/bin/timeout'); print(json.dumps({'timeout_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'timeout_bytes':p.stat().st_size,'version':subprocess.run([str(p),'--version'],capture_output=True,text=True,timeout=3).stdout.splitlines()[0],'yama':pathlib.Path('/proc/sys/kernel/yama/ptrace_scope').read_text().strip(),'pid':os.getpid()}))"
    print(json.dumps(probe(Path(sys.argv[1]), code, supervisor=False)))
