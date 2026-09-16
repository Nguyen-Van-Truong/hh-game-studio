"""Pure policy/lifecycle tests. No Docker process, Godot, mount or daemon effect."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('linux_executor_tests', STUDIO / 'godot-addon/linux_executor.py')
executor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(executor)
NAME = 'hh-gt03-' + 'a' * 32
CID = 'b' * 64
IMAGE_ENV = ['PATH=/usr/local/bin:/usr/bin', 'LANG=C.UTF-8', 'GPG_KEY=PUBLIC', 'PYTHON_VERSION=3.12', 'PYTHON_SHA256=PUBLIC']


def inspected(name, cid, mode, tool, snapshot):
    environment = dict(entry.split('=', 1) for entry in IMAGE_ENV)
    environment.update(executor.ENVIRONMENT)
    return {'Id': cid, 'Name': '/' + name, 'Image': executor.IMAGE_ID,
            'Config': {'Labels': {'hh.gt03.owner': name}, 'User': '65532:65532', 'WorkingDir': '/project',
                       'Entrypoint': ['/tool/' + executor.BINARY_NAME], 'Cmd': executor._command(mode),
                       'Env': [key + '=' + value for key, value in environment.items()], 'Healthcheck': {'Test': ['NONE']}},
            'HostConfig': {'ReadonlyRootfs': True, 'NetworkMode': 'none', 'IpcMode': 'private', 'CgroupnsMode': 'private',
                           'PidMode': '', 'UsernsMode': '', 'CapDrop': ['ALL'], 'CapAdd': None, 'Privileged': False,
                           'Devices': [], 'DeviceRequests': None,
                           'SecurityOpt': ['no-new-privileges=true', 'seccomp=builtin'], 'Memory': 1073741824,
                           'MemorySwap': 1073741824, 'NanoCpus': 1000000000, 'PidsLimit': 64, 'ShmSize': 16777216,
                           'LogConfig': {'Type': 'none', 'Config': {}}, 'RestartPolicy': {'Name': 'no'}, 'AutoRemove': False,
                           'Tmpfs': dict(executor.TMPFS),
                           'Ulimits': [{'Name': key, 'Soft': value, 'Hard': value} for key, value in executor.ULIMITS.items()],
                           'PortBindings': {}, 'VolumesFrom': None, 'Links': None,
                           'ReadonlyPaths': ['/proc/bus', '/proc/fs', '/proc/irq', '/proc/sys', '/proc/sysrq-trigger'],
                           'MaskedPaths': ['/proc/acpi', '/proc/kcore', '/proc/keys', '/proc/scsi', '/sys/firmware']},
            'Mounts': [{'Type': 'bind', 'Source': str(source), 'Destination': target, 'RW': False, 'Propagation': 'rprivate'}
                       for source, target in ((tool, '/tool'), (snapshot, '/project'))],
            'State': {'Running': False, 'Pid': 0, 'ExitCode': 0, 'OOMKilled': False}}


def write_project(root):
    root.mkdir()
    (root / 'scenes').mkdir()
    (root / 'scripts').mkdir()
    (root / 'project.godot').write_bytes(executor.PROJECT_TEMPLATE.encode())
    (root / 'scenes/fixture.tscn').write_bytes(b'[gd_scene format=3]\n[node name="Fixture" type="Node3D"]\n')
    (root / 'scripts/fixture_actor.gd').write_bytes(b'extends Node3D\n')


class PolicyTests(unittest.TestCase):
    def test_fixed_commands_reject_modes_and_never_accept_caller_argv(self):
        self.assertEqual(executor._command('parse')[-3:], ['--check-only', '--script', 'res://scripts/fixture_actor.gd'])
        self.assertEqual(executor._command('import')[-1], 'res://scenes/fixture.tscn')
        for mode in ('exec', '--script=outside', ['parse'], None, True):
            with self.assertRaises(executor.ExecutorError): executor._command(mode)
        with self.assertRaises(TypeError): executor.run(Path('unused'), mode='parse', output=Path('unused2'), argv=['x'])

    def test_lock_bytes_and_pins_are_exact(self):
        self.assertEqual(executor._lock()['binary_sha256'], executor.BINARY_SHA256)
        with patch.object(executor, '_read_file', return_value=b'{"status":"accepted"}'):
            with self.assertRaisesRegex(executor.ExecutorError, 'LOCK_BYTES'): executor._lock()

    def test_scope_valid_input_and_empty_cache_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'project'; write_project(root)
            expected = executor._project_bytes(root)
            (root / '.godot').mkdir()
            self.assertEqual(executor._project_bytes(root), expected)
            (root / '.godot/cache').write_bytes(b'x')
            with self.assertRaisesRegex(executor.ExecutorError, 'NONEMPTY_CACHE'): executor._project_bytes(root)

    def test_wrong_template_extra_case_path_and_oversized_script_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'project'; write_project(root)
            settings = root / 'project.godot'
            settings.write_bytes(settings.read_bytes() + b'[autoload]\nevil="res://evil.gd"\n')
            with self.assertRaisesRegex(executor.ExecutorError, 'TEMPLATE'): executor._project_bytes(root)
            settings.write_bytes(executor.PROJECT_TEMPLATE.encode())
            extra = root / 'scripts/evil.gd'; extra.write_bytes(b'@tool')
            with self.assertRaisesRegex(executor.ExecutorError, 'EXTRA_INPUT'): executor._project_bytes(root)
            extra.unlink()
            actor = root / 'scripts/fixture_actor.gd'; actor.write_bytes(b'x' * 16385)
            with self.assertRaisesRegex(executor.ExecutorError, 'FILE_SHAPE'): executor._project_bytes(root)

    def test_hardlink_is_rejected_without_reading_external_content(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'project'; write_project(root)
            external = Path(folder) / 'external'; external.write_bytes(b'sentinel')
            actor = root / 'scripts/fixture_actor.gd'; actor.unlink(); os.link(external, actor)
            with self.assertRaisesRegex(executor.ExecutorError, 'FILE_SHAPE'): executor._project_bytes(root)
            self.assertEqual(external.read_bytes(), b'sentinel')

    def test_reparse_or_symlink_identity_is_rejected(self):
        fake = type('Stat', (), {'st_mode': 0o100600, 'st_file_attributes': 0x400})()
        with patch.object(Path, 'lstat', return_value=fake):
            with self.assertRaisesRegex(executor.ExecutorError, 'LINK_FORBIDDEN'): executor._no_links(Path('anything'))

    def test_exact_inspect_and_each_critical_tamper_fail_closed(self):
        tool, snapshot = Path('C:/tool'), Path('C:/snapshot')
        value = inspected(NAME, CID, 'import', tool, snapshot)
        args = dict(name=NAME, container_id=CID, mode='import', tool=tool, snapshot=snapshot, image_environment=IMAGE_ENV)
        executor._validate_inspect(value, **args)
        mutations = [lambda v: v['HostConfig'].update(ReadonlyRootfs=False),
                     lambda v: v['HostConfig'].update(NetworkMode='host'),
                     lambda v: v['HostConfig'].update(MemorySwap=-1),
                     lambda v: v['HostConfig'].update(PidsLimit=0),
                     lambda v: v['HostConfig'].update(SecurityOpt=['seccomp=unconfined']),
                     lambda v: v['HostConfig'].update(CapAdd=['SYS_ADMIN']),
                     lambda v: v['HostConfig'].update(Devices=[{'PathOnHost': '/dev/sda'}]),
                     lambda v: v['HostConfig'].update(LogConfig={'Type': 'json-file', 'Config': {}}),
                     lambda v: v['HostConfig']['Tmpfs'].update({'/tmp': 'rw'}),
                     lambda v: v['HostConfig'].update(MaskedPaths=[]),
                     lambda v: v['Config'].update(User='0'),
                     lambda v: v['Config']['Cmd'].append('--script=res://evil.gd'),
                     lambda v: v['Config']['Env'].append('HTTP_PROXY=http://private'),
                     lambda v: v['Mounts'][0].update(RW=True),
                     lambda v: v['Mounts'].append({'Type': 'bind', 'Destination': '/var/run/docker.sock'}),
                     lambda v: v['Config']['Labels'].update({'hh.gt03.owner': 'another-owner'})]
        for index, mutate in enumerate(mutations):
            tampered = copy.deepcopy(value); mutate(tampered)
            with self.subTest(index=index), self.assertRaises(executor.ExecutorError):
                executor._validate_inspect(tampered, **args)

    def test_no_implicit_pull_or_shared_daemon_options(self):
        args = executor._create_args(NAME, 'parse', Path('C:/tool'), Path('C:/snapshot'))
        self.assertIn('--pull=never', args)
        self.assertNotIn('--privileged', args)
        self.assertNotIn('--rm', args)
        self.assertEqual(args[args.index('--entrypoint') + 1], '/tool/' + executor.BINARY_NAME)
        with self.assertRaises(executor.ExecutorError): executor._create_args('foreign', 'parse', Path('C:/t'), Path('C:/s'))

    def test_failed_stream_reader_is_never_clean_even_with_zero_process_exit(self):
        class BrokenStream(io.BytesIO):
            def read1(self, count):
                raise OSError('injected read failure')
        class Process:
            stdin = io.BytesIO(); stdout = io.BytesIO(b'normal'); stderr = BrokenStream()
            returncode = 0
            def poll(self): return 0
            def wait(self, timeout): return 0
        class Owner:
            def _job_for_process(self, process): return object()
            def _job_active_count(self, job): return 0
            def _terminate_job(self, job): pass
            def _close_job(self, job): pass
        with tempfile.TemporaryDirectory() as folder, patch.object(executor.subprocess, 'Popen', return_value=Process()):
            row, _ = executor._cli(Owner(), ['version'], Path(folder), 'reader-failure')
        self.assertEqual(row['exit_code'], 0)
        self.assertEqual(row['stream_reader_eof'], [True, False])
        self.assertEqual(row['stream_reader_errors'], [None, 'OSError'])
        self.assertFalse(executor._cli_clean(row))


class FakeDocker:
    def __init__(self, scenario):
        self.scenario = scenario; self.state = None; self.calls = []; self.removed = False

    def __call__(self, owned, args, output, label, *, timeout=20, cap=262144):
        self.calls.append(args)
        code, payload, stderr = 0, b'', b''
        if args[:2] == ['context', 'inspect']:
            payload = json.dumps('npipe:////./pipe/dockerDesktopLinuxEngine').encode()
        elif args[:2] == ['image', 'inspect']:
            payload = json.dumps([{'Id': executor.IMAGE_ID, 'Os': 'linux', 'Architecture': 'amd64', 'Config': {'Env': IMAGE_ENV}}]).encode()
        elif args[0] == 'create':
            name = args[args.index('--name') + 1]
            mounts = [args[i + 1] for i, item in enumerate(args) if item == '--mount']
            sources = {dict(part.split('=', 1) for part in item.split(',') if '=' in part)['dst']:
                       dict(part.split('=', 1) for part in item.split(',') if '=' in part)['src'] for item in mounts}
            self.state = inspected(name, CID, 'parse', Path(sources['/tool']), Path(sources['/project']))
            payload = b'LOST_REPLY' if self.scenario == 'lost_create' else CID.encode()
        elif args[0] == 'inspect':
            if self.removed:
                code, stderr = 1, ('error: no such object: ' + CID).encode()
            else:
                payload = json.dumps([self.state]).encode()
        elif args[0] == 'start':
            self.state['State'].update(Running=self.scenario == 'cap', Pid=55 if self.scenario == 'cap' else 0)
            payload = b'{"forged_valid":true}\n'
        elif args[0] == 'kill':
            self.state['State'].update(Running=False, Pid=0, ExitCode=137)
        elif args[0] == 'wait':
            payload = str(self.state['State']['ExitCode']).encode()
        elif args[0] == 'rm':
            if self.state['State']['Running']: raise AssertionError('removed running container without inspection')
            if args != ['rm', CID]: raise AssertionError('removed foreign ID')
            self.removed = True
        else:
            raise AssertionError('unexpected Docker operation')
        row = {'exit_code': code, 'timed_out': False, 'stream_cap_exceeded': self.scenario == 'cap' and args[0] == 'start',
               'stream_cap_bytes_each': cap, 'job_active_count': 0, 'readers_stopped': True,
               'stream_reader_eof': [True, True], 'stream_reader_errors': [None, None],
               'stdout': label + '-stdout.txt', 'stderr': label + '-stderr.txt'}
        (output / row['stdout']).write_bytes(payload)
        (output / row['stderr']).write_bytes(stderr)
        return row, payload


class LifecycleTests(unittest.TestCase):
    def exercise(self, scenario):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder); project = folder / 'project'; write_project(project)
            tool = folder / 'tool'; tool.mkdir(); binary = tool / executor.BINARY_NAME; binary.write_bytes(b'pinned-test-binary')
            fake = FakeDocker(scenario)
            with patch.object(executor, '_cli', side_effect=fake), patch.object(executor, '_binary', return_value=binary), \
                 patch.object(executor, '_owned_runner', return_value=object()), \
                 patch.object(executor, '_lock', return_value={'docker_endpoint': 'npipe:////./pipe/dockerDesktopLinuxEngine'}), \
                 patch.object(executor, 'BINARY_SHA256', hashlib.sha256(binary.read_bytes()).hexdigest()):
                result = executor.run(project, mode='parse', output=folder / 'out')
            self.assertTrue(result['owned_removed'])
            self.assertTrue(result['input_unchanged'])
            self.assertTrue(result['snapshot_unchanged'])
            self.assertFalse(result['public_ack']); self.assertFalse(result['sandbox_acceptance'])
            self.assertEqual(result['state']['Pid'], 0)
            return result, fake.calls

    def test_lost_create_reply_reconciles_owned_id_without_start(self):
        result, calls = self.exercise('lost_create')
        self.assertFalse(result['diagnostic_process_clean'])
        self.assertFalse(any(args[0] == 'start' for args in calls))
        self.assertIn(['rm', CID], calls)

    def test_output_cap_stops_owned_container_before_inspected_remove(self):
        result, calls = self.exercise('cap')
        self.assertFalse(result['diagnostic_process_clean'])
        self.assertEqual(result['state']['ExitCode'], 137)
        self.assertLess(calls.index(['kill', CID]), calls.index(['rm', CID]))

    def test_clean_process_does_not_promote_forged_child_claim(self):
        result, _ = self.exercise('clean')
        self.assertTrue(result['diagnostic_process_clean'])
        self.assertFalse(result['public_ack']); self.assertFalse(result['sandbox_acceptance'])


if __name__ == '__main__':
    unittest.main()
