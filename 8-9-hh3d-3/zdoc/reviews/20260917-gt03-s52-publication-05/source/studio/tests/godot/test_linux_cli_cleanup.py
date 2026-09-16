"""Pure CLI cleanup regressions. Every Popen/Job factory is mocked."""
from pathlib import Path
import copy
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('linux_cli_cleanup_executor', STUDIO/'godot-addon/linux_executor.py')
executor = importlib.util.module_from_spec(spec); spec.loader.exec_module(executor)


class FakeProcess:
    def __init__(self, *, wait_fails=False, kill_fails=False):
        self.stdin=io.BytesIO(); self.stdout=io.BytesIO(b'bounded-output'); self.stderr=io.BytesIO()
        self.returncode=None; self.wait_fails=wait_fails; self.kill_fails=kill_fails
        self.kill_calls=0; self.wait_calls=0
    def poll(self):return self.returncode
    def kill(self):
        self.kill_calls+=1
        if self.kill_fails:raise OSError('injected exact-helper kill failure')
        self.returncode=2
    def wait(self,timeout):
        self.wait_calls+=1
        if self.returncode is None and self.wait_fails:
            raise subprocess.TimeoutExpired('mocked-helper',timeout)
        return self.returncode


class FakeOwner:
    def __init__(self, process, *, reap_after_close=False, close_fails=False):
        self.process=process; self.reap_after_close=reap_after_close; self.close_fails=close_fails
        self.closed=False; self.zero_observed=True; self.tainted=False; self.close_calls=0
    def active_count(self):return 0
    def terminate(self):pass
    def close(self):
        self.close_calls+=1
        if self.close_fails:
            self.tainted=True
            raise OSError('injected native close failure')
        self.closed=True
        if self.reap_after_close:self.process.returncode=2
    def snapshot(self):
        return {'configured':True,'assigned':True,'closed':self.closed,'zero_observed':self.zero_observed,
                'tainted':self.tainted,'handle_retained':not self.closed,'active_count':0,
                'failed_operations':['CLOSE'] if self.tainted else [],'native_error':5 if self.tainted else None}


class ConstructorFailure(RuntimeError):
    def __init__(self, cleanup_owner=None):
        super().__init__('injected constructor failure')
        self.cleanup_owner=cleanup_owner


class Factory:
    def __init__(self, owner=None, *, create_error=None, held=False):
        self.owner=owner; self.create_error=create_error; self.held=held
    def require_no_holds(self):
        if self.held:raise RuntimeError('cleanup is held')
    def create(self,process):
        if self.create_error:raise self.create_error
        return self.owner
    def owner_for_process(self,process):return self.owner


class CleanupTests(unittest.TestCase):
    def cancel_mock(self, process, factory, signal):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(executor.subprocess,'Popen',return_value=process), \
             patch.object(executor,'_cli_jobs',return_value=factory), \
             patch.object(executor,'_INCOMPLETE_CLI_HOLDS',[]):
            output=Path(folder)
            with self.assertRaises(type(signal)) as raised:
                executor._cli(None,['version'],output,'cancelled-cli',timeout=0)
            self.assertIs(raised.exception,signal)
            row=json.loads((output/'cancelled-cli-host.json').read_text())
            self.assertEqual(row,signal.cli_result)
            self.assertFalse(executor._cli_clean(row))
            self.assertFalse(executor._cli_done(row,1))
            self.assertEqual(row['host_cancelled'],type(signal).__name__)
            self.assertTrue((output/'cancelled-cli-stdout.txt').is_file())
            self.assertTrue((output/'cancelled-cli-stderr.txt').is_file())
            return row,list(executor._INCOMPLETE_CLI_HOLDS)

    def run_mock(self, process, factory):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(executor.subprocess,'Popen',return_value=process) as popen, \
             patch.object(executor,'_cli_jobs',return_value=factory), \
             patch.object(executor,'_INCOMPLETE_CLI_HOLDS',[]):
            output=Path(folder)
            row,raw=executor._cli(None,['version'],output,'mocked-cli',timeout=0)
            self.assertEqual(json.loads((output/'mocked-cli-host.json').read_text()),row)
            self.assertEqual((output/'mocked-cli-stdout.txt').read_bytes(),raw)
            self.assertTrue((output/'mocked-cli-stderr.txt').is_file())
            return row,list(executor._INCOMPLETE_CLI_HOLDS),popen.call_count

    def test_clean_constructor_failure_reaps_and_closes_all_pipes_without_pending_hold(self):
        process=FakeProcess()
        row,holds,calls=self.run_mock(process,Factory(create_error=ConstructorFailure()))
        self.assertEqual(calls,1);self.assertEqual(process.returncode,2)
        self.assertTrue(all(stream.closed for stream in (process.stdin,process.stdout,process.stderr)))
        self.assertEqual(holds,[])
        self.assertEqual(row['host_error'],'ConstructorFailure')
        self.assertFalse(executor._cli_clean(row))

    def test_constructor_retained_owner_is_retried_and_failure_stays_dirty(self):
        process=FakeProcess();owner=FakeOwner(process,close_fails=True)
        row,holds,_=self.run_mock(process,Factory(create_error=ConstructorFailure(owner)))
        self.assertEqual(owner.close_calls,1);self.assertEqual(holds,[])
        self.assertTrue(row['job_owner']['handle_retained'])
        self.assertEqual(row['host_error'],'CLI_JOB_OWNERSHIP_UNCERTAIN')
        self.assertFalse(executor._cli_clean(row))

    def test_kill_and_wait_errors_still_close_job_write_evidence_and_reap_after_zero(self):
        process=FakeProcess(wait_fails=True,kill_fails=True)
        owner=FakeOwner(process,reap_after_close=True)
        row,holds,_=self.run_mock(process,Factory(owner))
        self.assertEqual(owner.close_calls,1);self.assertTrue(owner.closed)
        self.assertEqual(process.kill_calls,1);self.assertGreaterEqual(process.wait_calls,2)
        self.assertEqual(process.returncode,2);self.assertEqual(holds,[])
        self.assertTrue(all(stream.closed for stream in (process.stdin,process.stdout,process.stderr)))
        self.assertIn('CLI_HELPER_CLEANUP_',row['host_error'])
        self.assertFalse(executor._cli_clean(row))

    def test_unreaped_helper_retains_process_and_pipes_even_after_job_close(self):
        process=FakeProcess(wait_fails=True,kill_fails=True);owner=FakeOwner(process)
        row,holds,_=self.run_mock(process,Factory(owner))
        self.assertEqual(owner.close_calls,1);self.assertTrue(owner.closed)
        self.assertEqual(len(holds),1);self.assertIs(holds[0][0],process)
        self.assertIsNone(process.returncode)
        self.assertFalse(process.stdout.closed);self.assertFalse(process.stderr.closed)
        self.assertIn('CLI_HELPER_REAP_',row['host_error'])
        self.assertFalse(executor._cli_clean(row))

    def test_existing_job_hold_prevents_even_gated_popen(self):
        row,holds,calls=self.run_mock(FakeProcess(),Factory(held=True))
        self.assertEqual(calls,0);self.assertEqual(holds,[])
        self.assertEqual(row['host_error'],'RuntimeError')
        self.assertFalse(executor._cli_clean(row))

    def test_reader_start_failure_still_closes_unused_pipes_and_writes_dirty_evidence(self):
        class UnstartedThread:
            ident=None
            def __init__(self,*args,**kwargs):pass
            def start(self):raise RuntimeError('cannot start new thread')
            def join(self,timeout):raise RuntimeError('cannot join thread before it is started')
            def is_alive(self):return False
        process=FakeProcess();owner=FakeOwner(process)
        with patch.object(executor.threading,'Thread',UnstartedThread):
            row,holds,_=self.run_mock(process,Factory(owner))
        self.assertTrue(owner.closed);self.assertEqual(holds,[])
        self.assertTrue(all(stream.closed for stream in (process.stdin,process.stdout,process.stderr)))
        self.assertTrue(row.get('host_error'));self.assertFalse(executor._cli_clean(row))

    def test_constructor_cancellation_propagates_after_helper_and_pipe_cleanup(self):
        for kind in (KeyboardInterrupt,SystemExit):
            process=FakeProcess();signal=kind('cancel create')
            row,holds=self.cancel_mock(process,Factory(create_error=signal),signal)
            self.assertEqual(process.returncode,2);self.assertEqual(holds,[])
            self.assertTrue(all(stream.closed for stream in (process.stdin,process.stdout,process.stderr)))

    def test_constructor_cancellation_keeps_retained_owner_dirty_when_cleanup_fails(self):
        for kind in (KeyboardInterrupt,SystemExit):
            process=FakeProcess();owner=FakeOwner(process,close_fails=True);signal=kind('cancel create')
            signal.cleanup_owner=owner
            row,holds=self.cancel_mock(process,Factory(create_error=signal),signal)
            self.assertEqual(owner.close_calls,1);self.assertTrue(row['job_owner']['handle_retained'])
            self.assertEqual(holds,[])

    def test_interrupted_constructor_handoff_recovers_exact_registered_owner(self):
        process=FakeProcess();owner=FakeOwner(process);signal=KeyboardInterrupt('before assignment')
        row,holds=self.cancel_mock(process,Factory(owner,create_error=signal),signal)
        self.assertTrue(owner.closed);self.assertEqual(owner.close_calls,1);self.assertEqual(holds,[])

    def test_cleanup_kill_cancellation_still_closes_job_and_reaps_helper(self):
        for kind in (KeyboardInterrupt,SystemExit):
            process=FakeProcess(wait_fails=True);owner=FakeOwner(process,reap_after_close=True)
            signal=kind('cancel helper kill')
            with patch.object(process,'kill',side_effect=signal):
                row,holds=self.cancel_mock(process,Factory(owner),signal)
            self.assertTrue(owner.closed);self.assertEqual(process.returncode,2);self.assertEqual(holds,[])
            self.assertTrue(all(stream.closed for stream in (process.stdin,process.stdout,process.stderr)))

    def test_close_cancellation_preserves_job_state_and_closes_helper_streams(self):
        for kind in (KeyboardInterrupt,SystemExit):
            process=FakeProcess();owner=FakeOwner(process);signal=kind('cancel job close')
            def close():
                owner.tainted=True
                raise signal
            with patch.object(owner,'close',side_effect=close):
                row,holds=self.cancel_mock(process,Factory(owner),signal)
            self.assertTrue(row['job_owner']['handle_retained']);self.assertTrue(row['job_owner']['tainted'])
            self.assertEqual(holds,[])
            self.assertTrue(all(stream.closed for stream in (process.stdin,process.stdout,process.stderr)))

    def test_pipe_close_cancellation_retains_owner_and_continues_other_pipes(self):
        for kind in (KeyboardInterrupt,SystemExit):
            signal=kind('cancel pipe close')
            class Stream(io.BytesIO):
                def close(self):raise signal
            process=FakeProcess();process.returncode=0;process.stdout=Stream(b'output')
            owner=FakeOwner(process)
            row,holds=self.cancel_mock(process,Factory(owner),signal)
            self.assertTrue(owner.closed);self.assertEqual(len(holds),1)
            self.assertIs(holds[0][0],process);self.assertTrue(process.stderr.closed)
            self.assertFalse(process.stdout.closed)
            io.BytesIO.close(process.stdout)  # Only a fake in-memory stream.

    def test_reader_cancellation_reaches_caller_after_cleanup(self):
        for kind in (KeyboardInterrupt,SystemExit):
            signal=kind('cancel reader')
            class Stream(io.BytesIO):
                def read1(self,count):raise signal
            process=FakeProcess();process.returncode=0;process.stderr=Stream()
            owner=FakeOwner(process)
            row,holds=self.cancel_mock(process,Factory(owner),signal)
            self.assertTrue(owner.closed);self.assertEqual(holds,[])
            self.assertEqual(row['stream_reader_errors'][1],kind.__name__)

    def test_dirty_or_missing_job_facts_reject_success_and_expected_missing_proof(self):
        process=FakeProcess();owner=FakeOwner(process);owner.close()
        valid={'exit_code':0,'timed_out':False,'stream_cap_exceeded':False,'job_active_count':0,
               'readers_stopped':True,'stream_reader_eof':[True,True],'stream_reader_errors':[None,None],
               'job_owner':owner.snapshot(),'stderr':'stderr.txt'}
        self.assertTrue(executor._cli_clean(valid))
        mutations=[lambda row:row.pop('job_owner'),
                   lambda row:row['job_owner'].update(closed=False),
                   lambda row:row['job_owner'].update(tainted=True),
                   lambda row:row['job_owner'].update(handle_retained=True),
                   lambda row:row['job_owner'].update(zero_observed=False),
                   lambda row:row['job_owner'].update(assigned=False),
                   lambda row:row['job_owner'].update(active_count=False),
                   lambda row:row['job_owner'].update(create_uncertain=True),
                   lambda row:row['job_owner'].update(close_uncertain=True),
                   lambda row:row.update(host_cancelled='KeyboardInterrupt'),
                   lambda row:row['job_owner'].update(failed_operations=['CLOSE']),
                   lambda row:row['job_owner'].update(native_error=5)]
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder);selector='a'*64
            (output/'stderr.txt').write_text('Error: No such object: '+selector)
            missing=copy.deepcopy(valid);missing['exit_code']=1
            self.assertTrue(executor._missing(missing,output,selector))
            for index,mutate in enumerate(mutations):
                row=copy.deepcopy(valid);mutate(row)
                with self.subTest(index=index):
                    self.assertFalse(executor._cli_clean(row))
                    row['exit_code']=1
                    self.assertFalse(executor._cli_done(row,1))  # Shared owned-removal completion predicate.
                    self.assertFalse(executor._missing(row,output,selector))


if __name__=='__main__':unittest.main()
