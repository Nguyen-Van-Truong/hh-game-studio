"""Pure fault injection plus bounded Windows helpers; no Docker or Godot."""
from pathlib import Path
import importlib.util
import os
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('cli_job_tests', STUDIO/'godot-addon/cli_job.py')
jobs = importlib.util.module_from_spec(spec); spec.loader.exec_module(jobs)


class FakeNative:
    def __init__(self):
        self.fail=set();self.calls=[];self.active=0
    def invoke(self,operation):
        self.calls.append(operation)
        if operation in self.fail:raise OSError(5,operation)
    def create(self):self.invoke('create');return 123
    def configure(self,handle):self.invoke('configure')
    def assign(self,handle,process):self.invoke('assign')
    def active_count(self,handle):self.invoke('query');return self.active
    def terminate(self,handle):self.invoke('terminate');self.active=0
    def close(self,handle):self.invoke('close')


class FaultTests(unittest.TestCase):
    def tearDown(self):
        self.assertEqual(jobs.HOLDS,[])
        self.assertEqual(jobs._LIVE,set())

    def owner(self,native):
        with patch.object(jobs,'_native',return_value=native):return jobs.create(object())

    def test_checked_close_is_idempotent_and_proves_zero(self):
        native=FakeNative();owner=self.owner(native);owner.close();owner.close()
        self.assertEqual(native.calls.count('close'),1)
        self.assertTrue(owner.closed);self.assertTrue(owner.zero_observed)
        self.assertFalse(owner.snapshot()['handle_retained'])

    def test_close_failure_retains_owner_blocks_new_create_and_retries(self):
        native=FakeNative();owner=self.owner(native);native.fail.add('close')
        with self.assertRaises(jobs.JobError) as raised:owner.close()
        self.assertIs(raised.exception.cleanup_owner,owner)
        self.assertEqual(jobs.HOLDS,[owner]);self.assertFalse(owner.closed)
        with self.assertRaisesRegex(jobs.JobError,'CLEANUP_HELD'):self.owner(FakeNative())
        self.assertFalse(jobs.retry_cleanup()[0]['closed'])
        native.fail.clear();rows=jobs.retry_cleanup()
        self.assertTrue(rows[0]['closed']);self.assertTrue(rows[0]['tainted'])

    def test_query_failure_never_calls_native_close_or_reports_zero(self):
        native=FakeNative();owner=self.owner(native);native.fail.add('query')
        self.assertIsNone(owner.active_count())
        with self.assertRaisesRegex(jobs.JobError,'QUERY'):owner.close()
        self.assertNotIn('close',native.calls)
        self.assertFalse(owner.zero_observed)
        native.fail.clear();jobs.retry_cleanup()

    def test_terminate_failure_never_discards_live_owner(self):
        native=FakeNative();owner=self.owner(native);native.active=1;native.fail.add('terminate')
        with self.assertRaisesRegex(jobs.JobError,'TERMINATE'):owner.close()
        self.assertNotIn('close',native.calls);self.assertEqual(jobs.HOLDS,[owner])
        native.fail.clear();jobs.retry_cleanup()

    def test_active_settle_timeout_retains_handle_without_close(self):
        native=FakeNative();owner=self.owner(native);native.active=1
        with patch.object(native,'terminate',return_value=None),patch.object(jobs,'SETTLE_SECONDS',0):
            with self.assertRaisesRegex(jobs.JobError,'ACTIVE'):owner.close()
        self.assertNotIn('close',native.calls)
        native.active=0;jobs.retry_cleanup()

    def test_constructor_failures_expose_cleanup_owner_when_close_fails(self):
        for operation in ('configure','assign'):
            native=FakeNative();native.fail.update([operation,'close'])
            with self.assertRaises(jobs.JobError) as raised:self.owner(native)
            owner=raised.exception.cleanup_owner
            self.assertIsNotNone(owner);self.assertEqual(jobs.HOLDS,[owner])
            self.assertFalse(owner.closed);self.assertEqual(owner.configured,operation=='assign')
            native.fail.clear();jobs.retry_cleanup()

    def test_constructor_cleanup_success_leaves_no_fake_hold(self):
        native=FakeNative();native.fail.add('configure')
        with self.assertRaises(jobs.JobError) as raised:self.owner(native)
        self.assertIsNone(raised.exception.cleanup_owner)
        self.assertEqual(native.calls.count('close'),1)

    def test_create_failure_and_capacity_have_no_unowned_handle(self):
        native=FakeNative();native.fail.add('create')
        with self.assertRaises(jobs.JobError) as raised:self.owner(native)
        self.assertIsNone(raised.exception.cleanup_owner)
        self.assertNotIn('close',native.calls)
        with patch.object(jobs,'MAX_OWNERS',0):
            with self.assertRaisesRegex(jobs.JobError,'CAPACITY'):self.owner(FakeNative())

    def test_constructor_cancellation_preserves_signal_after_checked_cleanup(self):
        for kind in (KeyboardInterrupt,SystemExit):
            for operation in ('configure','assign'):
                native=FakeNative();signal=kind('cancel constructor')
                with self.subTest(kind=kind,operation=operation),patch.object(native,operation,side_effect=signal):
                    with self.assertRaises(kind) as raised:self.owner(native)
                self.assertIs(raised.exception,signal);self.assertIsNone(signal.cleanup_owner)
                self.assertEqual(native.calls.count('close'),1)
                self.assertEqual(jobs.HOLDS,[]);self.assertEqual(jobs._LIVE,set())

    def test_constructor_cancellation_retains_failed_cleanup_and_blocks_admission(self):
        for kind in (KeyboardInterrupt,SystemExit):
            native=FakeNative();native.fail.add('close');signal=kind('cancel assign')
            with patch.object(native,'assign',side_effect=signal):
                with self.assertRaises(kind) as raised:self.owner(native)
            self.assertIs(raised.exception,signal);owner=signal.cleanup_owner
            self.assertEqual(jobs.HOLDS,[owner]);self.assertTrue(owner.snapshot()['handle_retained'])
            with self.assertRaisesRegex(jobs.JobError,'CLEANUP_HELD'):jobs.require_no_holds()
            native.fail.clear();self.assertTrue(jobs.retry_cleanup()[0]['closed'])
            owner.close();self.assertEqual(native.calls.count('close'),2)  # failed call + one success

    def test_secondary_cleanup_cancellation_does_not_replace_original_signal(self):
        native=FakeNative();original=KeyboardInterrupt('first');secondary=SystemExit('second')
        with patch.object(native,'assign',side_effect=original),patch.object(native,'active_count',side_effect=secondary):
            with self.assertRaises(KeyboardInterrupt) as raised:self.owner(native)
        self.assertIs(raised.exception,original);self.assertIs(original.cleanup_owner,secondary.cleanup_owner)
        self.assertEqual(jobs.HOLDS,[original.cleanup_owner]);jobs.retry_cleanup()

    def test_query_terminate_and_settle_cancellation_remain_retryable_and_tainted(self):
        for kind in (KeyboardInterrupt,SystemExit):
            for operation in ('active_count','terminate','settle'):
                native=FakeNative();owner=self.owner(native);signal=kind('cancel operation')
                if operation=='settle':
                    native.active=1
                    context=patch.object(jobs.time,'sleep',side_effect=signal)
                    action=owner.close
                else:
                    context=patch.object(native,operation,side_effect=signal)
                    action=getattr(owner,operation)
                with self.subTest(kind=kind,operation=operation),context:
                    with self.assertRaises(kind) as raised:action()
                self.assertIs(raised.exception,signal);self.assertIs(signal.cleanup_owner,owner)
                self.assertEqual(jobs.HOLDS,[owner]);self.assertTrue(owner.tainted)
                self.assertTrue(jobs.retry_cleanup()[0]['closed'])

    def test_unreceived_create_or_close_result_stays_held_without_handle_retry(self):
        # Fake handles only: ambiguous native close cannot safely be retried in
        # production; process exit is the recovery boundary for this state.
        for kind in (KeyboardInterrupt,SystemExit):
            for operation in ('create','close'):
                native=FakeNative();signal=kind('native result unavailable');owner=None
                if operation=='close':owner=self.owner(native)
                with patch.object(native,operation,side_effect=signal):
                    with self.assertRaises(kind) as raised:
                        owner.close() if owner else self.owner(native)
                self.assertIs(raised.exception,signal);owner=signal.cleanup_owner
                self.assertTrue(getattr(owner,operation+'_uncertain'))
                calls=list(native.calls)
                self.assertIsNone(owner.active_count())
                with self.assertRaises(jobs.JobError):owner.terminate()
                self.assertFalse(jobs.retry_cleanup()[0]['closed'])
                self.assertEqual(native.calls,calls)
                with self.assertRaisesRegex(jobs.JobError,'CLEANUP_HELD'):jobs.require_no_holds()
                with jobs._REGISTRY_LOCK:  # Dispose the artificial registry, never a native handle.
                    jobs.HOLDS.remove(owner);jobs._LIVE.remove(owner)

    def test_constructor_owner_can_be_recovered_by_exact_process_identity(self):
        native=FakeNative();process=object()
        with patch.object(jobs,'_native',return_value=native):owner=jobs.create(process)
        self.assertIs(jobs.owner_for_process(process),owner)
        self.assertIsNone(jobs.owner_for_process(object()))
        owner.close();self.assertIsNone(jobs.owner_for_process(process))

    def test_before_assign_callback_runs_after_base_config_and_before_assignment(self):
        native=FakeNative(); calls=[]
        def callback(owner):
            calls.append((owner.configured, list(native.calls)))
            return {'limit': 'exact'}
        with patch.object(jobs,'_native',return_value=native):
            owner=jobs.create(object(), before_assign=callback)
        self.assertEqual(calls, [(False, ['create','configure'])])
        self.assertEqual(native.calls, ['create','configure','assign'])
        owner.close()

    def test_callback_failure_never_assigns_and_retains_failed_cleanup(self):
        for cleanup_fails in (False, True):
            native=FakeNative()
            if cleanup_fails: native.fail.add('close')
            initiating=ValueError('injected configure rejection')
            def callback(owner):
                self.assertIs(jobs.owner_for_process(owner._process),owner)
                raise initiating
            with patch.object(jobs,'_native',return_value=native):
                with self.assertRaises(jobs.JobError) as caught:
                    jobs.create(object(),before_assign=callback)
            self.assertIs(caught.exception.__cause__,initiating)
            self.assertNotIn('assign',native.calls)
            if cleanup_fails:
                self.assertIsNotNone(caught.exception.cleanup_owner)
                with self.assertRaises(jobs.JobError): jobs.require_no_holds()
                native.fail.clear();self.assertTrue(jobs.retry_cleanup()[0]['closed'])
            else:
                self.assertIsNone(caught.exception.cleanup_owner)

    def test_callback_cancellation_preserves_signal_and_never_assigns(self):
        native=FakeNative();signal=KeyboardInterrupt('cancel empty configuration')
        def callback(owner): raise signal
        with patch.object(jobs,'_native',return_value=native):
            with self.assertRaises(KeyboardInterrupt) as caught:
                jobs.create(object(),before_assign=callback)
        self.assertIs(caught.exception,signal)
        self.assertNotIn('assign',native.calls)
        self.assertIsNone(signal.cleanup_owner)


@unittest.skipUnless(os.name=='nt','Windows native Job proof')
class NativeTests(unittest.TestCase):
    def tearDown(self):
        self.assertEqual(jobs.HOLDS,[]);self.assertEqual(jobs._LIVE,set())

    def gated(self,code):
        gate="import sys,subprocess; token=sys.stdin.readline(); sys.exit(125) if token!='GO\\n' else None; "+code
        return subprocess.Popen([sys.executable,'-B','-c',gate],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)

    def cleanup_process(self,process):
        if process.poll() is None:process.kill()
        process.wait(timeout=3)
        for stream in (process.stdin,process.stdout,process.stderr):
            if not stream.closed:stream.close()

    def test_real_gated_helper_exits_and_job_is_zero_before_checked_close(self):
        process=self.gated("print('OWNED_HELPER',flush=True)");owner=None
        try:
            owner=jobs.create(process)
            self.assertEqual(owner.active_count(),1)
            process.stdin.write(b'GO\n');process.stdin.flush()
            out,err=process.communicate(timeout=3)
            self.assertEqual(process.returncode,0);self.assertEqual(out.strip(),b'OWNED_HELPER');self.assertEqual(err,b'')
            owner.close()
            self.assertTrue(owner.closed);self.assertTrue(owner.zero_observed);self.assertFalse(owner.tainted)
        finally:
            if owner and not owner.closed:owner.close()
            self.cleanup_process(process)

    def test_real_descendant_is_terminated_and_no_active_job_process_remains(self):
        process=self.gated("p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(10)']); print('CHILD_STARTED',flush=True); p.wait()")
        owner=None
        try:
            owner=jobs.create(process);process.stdin.write(b'GO\n');process.stdin.flush()
            deadline=time.monotonic()+2
            while owner.active_count()!=2 and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(owner.active_count(),2)
            owner.terminate();process.wait(timeout=3);owner.close()
            self.assertNotEqual(process.returncode,0)
            self.assertEqual(owner.active_count(),0);self.assertTrue(owner.zero_observed)
        finally:
            if owner and not owner.closed:owner.close()
            self.cleanup_process(process)

    def test_real_handle_survives_injected_close_failure_until_checked_retry(self):
        process=self.gated("pass");owner=None
        try:
            owner=jobs.create(process)
            process.stdin.write(b'GO\n');process.stdin.flush();process.wait(timeout=3)
            with patch.object(owner._native.kernel,'CloseHandle',return_value=0):
                with self.assertRaisesRegex(jobs.JobError,'CLOSE'):owner.close()
                self.assertFalse(owner.closed);self.assertTrue(owner.snapshot()['handle_retained'])
                self.assertEqual(owner.active_count(),0)  # Actual native query of retained handle.
            self.assertTrue(jobs.retry_cleanup()[0]['closed'])
        finally:
            if owner and not owner.closed:owner.close()
            self.cleanup_process(process)

    def test_real_constructor_handle_is_retained_on_configure_and_cleanup_failure(self):
        for operation in ('SetInformationJobObject','AssignProcessToJobObject'):
            process=self.gated("raise RuntimeError('gate must stay closed')");owner=None
            native=jobs._Native()
            try:
                with patch.object(jobs,'_native',return_value=native),patch.object(native.kernel,operation,return_value=0), \
                     patch.object(native.kernel,'CloseHandle',return_value=0):
                    with self.assertRaises(jobs.JobError) as raised:jobs.create(process)
                    owner=raised.exception.cleanup_owner
                    self.assertIsNotNone(owner);self.assertFalse(owner.closed)
                    self.assertEqual(owner.active_count(),0)  # Created native Job; helper never assigned.
                    self.assertIsNone(process.poll())
                self.assertTrue(jobs.retry_cleanup()[0]['closed'])
            finally:
                if owner and not owner.closed:owner.close()
                self.cleanup_process(process)

    def test_real_constructor_cancellation_keeps_native_handle_until_checked_retry(self):
        for kind in (KeyboardInterrupt,SystemExit):
            for operation in ('SetInformationJobObject','AssignProcessToJobObject'):
                process=self.gated("raise RuntimeError('cancelled gate must remain closed')")
                native=jobs._Native();owner=None;signal=kind('native constructor cancellation')
                try:
                    with patch.object(jobs,'_native',return_value=native),patch.object(native.kernel,operation,side_effect=signal), \
                         patch.object(native.kernel,'CloseHandle',return_value=0):
                        with self.assertRaises(kind) as raised:jobs.create(process)
                        self.assertIs(raised.exception,signal);owner=signal.cleanup_owner
                        self.assertIs(jobs.owner_for_process(process),owner)
                        self.assertEqual(owner.active_count(),0)
                        self.assertIsNone(process.poll())
                        with self.assertRaisesRegex(jobs.JobError,'CLEANUP_HELD'):jobs.require_no_holds()
                    self.assertTrue(jobs.retry_cleanup()[0]['closed'])
                finally:
                    if owner and not owner.closed:owner.close()
                    self.cleanup_process(process)


if __name__=='__main__':unittest.main()
