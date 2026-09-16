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
from unittest.mock import Mock, patch

STUDIO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('linux_executor_tests', STUDIO / 'godot-addon/linux_executor.py')
executor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(executor)
NAME = 'hh-gt03-' + 'a' * 32
CID = 'b' * 64
IMAGE_ENV = ['PATH=/usr/local/bin:/usr/bin', 'LANG=C.UTF-8', 'GPG_KEY=PUBLIC', 'PYTHON_VERSION=3.12', 'PYTHON_SHA256=PUBLIC']
CLEAN_JOB = {'configured':True,'assigned':True,'closed':True,'zero_observed':True,
    'tainted':False,'handle_retained':False,'active_count':0,'failed_operations':[],'native_error':None}


def clean_row(code=0):
    return {'exit_code':code,'timed_out':False,'stream_cap_exceeded':False,
        'job_active_count':0,'readers_stopped':True,'stream_reader_eof':[True,True],
        'stream_reader_errors':[None,None],'job_owner':copy.deepcopy(CLEAN_JOB)}


def inspected(name, cid, mode, tool, snapshot):
    environment = dict(entry.split('=', 1) for entry in IMAGE_ENV)
    environment.update(executor.ENVIRONMENT)
    return {'Id': cid, 'Name': '/' + name, 'Image': executor.IMAGE_ID,
            'Config': {'Labels': {'hh.gt03.owner': name, 'hh.gt03.executor': executor.EXECUTOR_CONTEXT}, 'User': '65532:65532', 'WorkingDir': '/project',
                       'Entrypoint': ['/usr/local/bin/python3'], 'Cmd': executor._supervised_command(mode),
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
                     lambda v: v['HostConfig'].update(Init=True),
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
        self.assertEqual(args[args.index('--entrypoint') + 1], '/usr/local/bin/python3')
        self.assertNotIn('--init', args)
        self.assertIn('--kill-after=1s', args)
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
            closed=True;zero_observed=True;tainted=False
            def require_no_holds(self): pass
            def create(self,process): return self
            def active_count(self): return 0
            def terminate(self): pass
            def close(self): pass
            def snapshot(self): return copy.deepcopy(CLEAN_JOB)
        with tempfile.TemporaryDirectory() as folder, patch.object(executor.subprocess, 'Popen', return_value=Process()), \
             patch.object(executor,'_cli_jobs',return_value=Owner()):
            row, _ = executor._cli(Owner(), ['version'], Path(folder), 'reader-failure')
        self.assertEqual(row['exit_code'], 0)
        self.assertEqual(row['stream_reader_eof'], [True, False])
        self.assertEqual(row['stream_reader_errors'], [None, 'OSError'])
        self.assertFalse(executor._cli_clean(row))

    def test_failed_job_close_is_dirty_and_retains_owner(self):
        class Process:
            stdin=io.BytesIO();stdout=io.BytesIO(b'normal');stderr=io.BytesIO()
            returncode=0
            def poll(self):return 0
            def wait(self,timeout):return 0
        class Owner:
            closed=False;zero_observed=True;tainted=False
            def require_no_holds(self):pass
            def create(self,process):return self
            def active_count(self):return 0
            def terminate(self):pass
            def close(self):self.tainted=True;raise RuntimeError('CloseHandle failed')
            def snapshot(self):return {'closed':False,'zero_observed':True,'tainted':True,'handle_retained':True,'active_count':0}
        owner=Owner()
        with tempfile.TemporaryDirectory() as folder,patch.object(executor.subprocess,'Popen',return_value=Process()), \
             patch.object(executor,'_cli_jobs',return_value=owner):
            row,_=executor._cli(None,['version'],Path(folder),'job-close-failure')
        self.assertFalse(executor._cli_clean(row))
        self.assertEqual(row['host_error'],'CLI_JOB_OWNERSHIP_UNCERTAIN')
        self.assertTrue(row['job_owner']['handle_retained'])


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
        elif args[0] == 'ps':
            payload = b''
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
        row['job_owner']=copy.deepcopy(CLEAN_JOB)
        (output / row['stdout']).write_bytes(payload)
        (output / row['stderr']).write_bytes(stderr)
        return row, payload


class LifecycleTests(unittest.TestCase):
    def exercise(self, scenario):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder); project = folder / 'project'; write_project(project)
            tool = folder / 'tool'; tool.mkdir(); binary = tool / executor.BINARY_NAME; binary.write_bytes(b'pinned-test-binary')
            fake = FakeDocker(scenario)
            admission = type('Admission', (), {'wait_ms': 0, 'abandoned': False, 'close': lambda self: None})()
            with patch.object(executor, '_cli', side_effect=fake), patch.object(executor, '_binary', return_value=binary), \
                 patch.object(executor, '_owned_runner', return_value=object()), \
                 patch.object(executor, '_Admission', return_value=admission), \
                 patch.object(executor, '_owner_path', return_value=folder / 'owner.json'), \
                 patch.object(executor, '_lock', return_value={'docker_endpoint': 'npipe:////./pipe/dockerDesktopLinuxEngine'}), \
                 patch.object(executor, 'BINARY_SHA256', hashlib.sha256(binary.read_bytes()).hexdigest()):
                result = executor.run(project, mode='parse', output=folder / 'out')
            self.assertFalse((folder / 'owner.json').exists())
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

    def test_start_cancellation_propagates_after_owned_container_cleanup_and_result(self):
        for kind in (KeyboardInterrupt,SystemExit):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as folder:
                folder=Path(folder);project=folder/'project';write_project(project)
                tool=folder/'tool';tool.mkdir();binary=tool/executor.BINARY_NAME;binary.write_bytes(b'pin')
                fake=FakeDocker('cap');signal=kind('cancel attached CLI')
                def cancelled(owned,args,output,label,**kwargs):
                    row,raw=fake(owned,args,output,label,**kwargs)
                    if args[0]=='start':raise signal
                    return row,raw
                admission=Mock(wait_ms=0,abandoned=False,acquired=True)
                with patch.object(executor,'_cli',side_effect=cancelled),patch.object(executor,'_binary',return_value=binary), \
                     patch.object(executor,'_owned_runner',return_value=object()),patch.object(executor,'_Admission',return_value=admission), \
                     patch.object(executor,'_owner_path',return_value=folder/'owner.json'), \
                     patch.object(executor,'_lock',return_value={'docker_endpoint':'npipe:////./pipe/dockerDesktopLinuxEngine'}), \
                     patch.object(executor,'BINARY_SHA256',hashlib.sha256(b'pin').hexdigest()):
                    with self.assertRaises(kind) as raised:
                        executor.run(project,mode='parse',output=folder/'out')
                self.assertIs(raised.exception,signal)
                result=json.loads((folder/'out/result.json').read_text())
                self.assertEqual(signal.executor_result,result);self.assertEqual(result['host_cancelled'],kind.__name__)
                self.assertTrue(result['owned_removed']);self.assertEqual(result['state']['Pid'],0)
                self.assertFalse(result['diagnostic_process_clean']);self.assertFalse(result['public_ack'])
                self.assertFalse((folder/'owner.json').exists());admission.close.assert_called_once()
                self.assertLess(fake.calls.index(['kill',CID]),fake.calls.index(['rm',CID]))


class AdmissionTests(unittest.TestCase):
    def record(self, phase='created', cid=CID):
        return {'schema': 'hh-linux-owner-1', 'context': executor.EXECUTOR_CONTEXT,
                'image': executor.IMAGE_ID, 'name': NAME, 'container_id': cid, 'phase': phase}

    def test_supervisor_shape_bounds_and_unsupported_ptrace_policy_fail_closed(self):
        for timeout in (1, 2, 10, 20):
            cmd = executor._supervised_command('parse', timeout)
            self.assertIn('--signal=TERM', cmd)
            self.assertIn('--kill-after=1s', cmd)
            self.assertEqual(cmd[6], str(max(1, timeout - 1)) + 's')
        self.assertIn("in ('1','2','3')", executor.SUPERVISOR_BOOTSTRAP)
        self.assertIn('os.getpid()==1', executor.SUPERVISOR_BOOTSTRAP)
        self.assertIn('os.execv', executor.SUPERVISOR_BOOTSTRAP)
        self.assertNotIn('--foreground', executor._supervised_command('parse'))

    def test_durable_owner_roundtrip_rejects_identity_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'owner.json'
            executor._persist_owner(path, self.record())
            self.assertEqual(executor._read_owner(path), self.record())
            value = self.record(); value['image'] = 'foreign'
            executor._persist_owner(path, value)
            with self.assertRaisesRegex(executor.ExecutorError, 'OWNER_RECORD'):
                executor._read_owner(path)

    def test_failed_native_release_or_close_preserves_handle_and_blocks_module(self):
        for release_ok in (False,True):
            calls=[]
            class Kernel:
                def ReleaseMutex(self,handle):calls.append('release');return release_ok
                def CloseHandle(self,handle):calls.append('close');return False
            value=executor._Admission.__new__(executor._Admission)
            value.kernel=Kernel();value.handle=123;value.acquired=True
            with patch.object(executor,'_INCOMPLETE_ADMISSION_HOLDS',[]):
                with self.assertRaisesRegex(executor.ExecutorError,'UNCERTAIN'):value.close()
                self.assertEqual(value.handle,123)
                self.assertEqual(executor._INCOMPLETE_ADMISSION_HOLDS,[value])
                self.assertEqual(calls,['release','close'] if release_ok else ['release'])

    def test_unknown_context_container_denies_without_removal(self):
        calls = []
        def call(args, label, **kwargs):
            calls.append(args)
            return clean_row(), CID.encode()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'owner.json'
            with self.assertRaisesRegex(executor.ExecutorError, 'UNRECORDED_CONTAINER'):
                executor._reconcile_owner(path, call, Path(folder))
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][0],'ps')

    def test_missing_create_reply_retains_ambiguity_and_never_admits(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder); path=folder/'owner.json'
            executor._persist_owner(path,self.record('create_pending',None))
            def call(args,label,**kwargs):
                (folder/'missing.txt').write_text('Error: No such object: '+NAME)
                return {**clean_row(1),'stderr':'missing.txt'},b''
            with self.assertRaisesRegex(executor.ExecutorError,'OWNER_CREATE_AMBIGUOUS'):
                executor._reconcile_owner(path,call,folder)
            self.assertTrue(path.exists())

    def test_recovery_stops_only_recorded_running_id_before_admission(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder); path=folder/'owner.json'
            executor._persist_owner(path,self.record('start_pending'))
            fake=FakeDocker('clean'); fake.state=inspected(NAME,CID,'parse',Path('C:/t'),Path('C:/s'))
            fake.state['State'].update(Running=True,Pid=42)
            result=executor._reconcile_owner(path,lambda args,label,**kwargs:fake(None,args,folder,label,**kwargs),folder)
            self.assertTrue(result['reconciled']);self.assertTrue(result['removed'])
            self.assertFalse(path.exists())
            self.assertLess(fake.calls.index(['kill',CID]),fake.calls.index(['rm',CID]))
            self.assertEqual(fake.calls[-1][0],'ps')

    def test_native_mutex_create_or_wait_cancellation_retains_ambiguous_owner(self):
        for kind in (KeyboardInterrupt,SystemExit):
            for operation in ('CreateMutexW','WaitForSingleObject'):
                signal=kind('cancel mutex');kernel=Mock()
                kernel.CreateMutexW.return_value=123;kernel.WaitForSingleObject.return_value=0
                getattr(kernel,operation).side_effect=signal
                with patch.object(executor.ctypes,'WinDLL',return_value=kernel), \
                     patch.object(executor,'_INCOMPLETE_ADMISSION_HOLDS',[]):
                    with self.assertRaises(kind) as raised:executor._Admission()
                    self.assertIs(raised.exception,signal)
                    self.assertEqual(len(executor._INCOMPLETE_ADMISSION_HOLDS),1)
                    kernel.CloseHandle.assert_not_called()

    def test_cancelled_release_is_not_claimed_owned_and_never_retried(self):
        for kind in (KeyboardInterrupt,SystemExit):
            signal=kind('release result unavailable');owner=object.__new__(executor._Admission)
            owner.handle=123;owner.acquired=True;owner.kernel=Mock()
            owner.kernel.ReleaseMutex.side_effect=signal
            with patch.object(executor,'_INCOMPLETE_ADMISSION_HOLDS',[]):
                with self.assertRaises(kind) as raised:owner.close()
                self.assertIs(raised.exception,signal);self.assertIsNone(owner.acquired)
                self.assertEqual(executor._INCOMPLETE_ADMISSION_HOLDS,[owner])
                with self.assertRaisesRegex(executor.ExecutorError,'OWNERSHIP_UNKNOWN'):owner.close()
                owner.kernel.ReleaseMutex.assert_called_once();owner.kernel.CloseHandle.assert_not_called()


if __name__ == '__main__':
    unittest.main()
