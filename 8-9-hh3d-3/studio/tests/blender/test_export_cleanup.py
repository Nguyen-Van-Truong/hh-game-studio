"""Retained export cleanup ownership, including a real gated native Job."""
import json
import os
import queue
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

STUDIO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(STUDIO.parent))
from studio.host.blender.export_job import ExportJob, configure_limits, CPU_SECONDS, MEMORY_BYTES, PROCESS_LIMIT
from studio.host.blender.ui_host import BlenderUIHost,HostError,cli_job


class Api:
    def mkdir(self,path):path.mkdir()


class FakeJob:
    def __init__(self):self.fail=True;self.closed=False;self.calls=0
    def close(self):
        self.calls+=1
        if self.fail:raise OSError('injected checked close failure')
        self.closed=True
    def snapshot(self):return {'closed':self.closed,'handle_retained':not self.closed}


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='hh-export-cleanup-')
        host=type('Host',(),{'directory':Path(self.temp.name),'_api':Api()})()
        self.job=ExportJob(host,{})
    def tearDown(self):self.temp.cleanup()
    def test_failure_retains_exact_owner_and_retry_is_idempotent(self):
        native=FakeJob();self.job._job=native;self.job.done.set()
        with self.assertRaises(OSError) as caught:self.job.retry_cleanup()
        self.assertIs(caught.exception.cleanup_owner,self.job)
        self.assertIs(self.job._job,native);self.assertTrue(self.job.cleanup_held)
        first=(self.job.directory/'cleanup-attempt-0001.json').read_bytes()
        native.fail=False
        result=self.job.retry_cleanup();result['job']['closed']=False
        self.assertTrue(self.job.retry_cleanup()['job']['closed'])
        self.assertFalse(self.job.cleanup_held);self.assertEqual(native.calls,2)
        self.assertEqual((self.job.directory/'cleanup-attempt-0001.json').read_bytes(),first)
        self.assertEqual(len(list(self.job.directory.glob('cleanup-attempt-*'))),2)
    def test_active_run_cannot_be_cleaned_from_another_caller(self):
        with self.assertRaisesRegex(HostError,'RUN_ACTIVE'):self.job.retry_cleanup()
        self.assertEqual(self.job._cleanup_attempt,0)
    def test_export_cannot_restart_same_instance(self):
        self.job._started=True
        with self.assertRaisesRegex(HostError,'ALREADY_STARTED'):self.job.run()
        self.assertFalse(self.job.done.is_set())
    def test_failed_result_write_still_signals_done(self):
        self.job.host._stopped=True
        (self.job.directory/'host-result.json').write_bytes(b'preserve-original')
        with self.assertRaises(FileExistsError) as caught:self.job.run()
        self.assertIs(caught.exception.cleanup_owner,self.job)
        self.assertTrue(self.job.done.is_set())
        self.assertEqual((self.job.directory/'host-result.json').read_bytes(),b'preserve-original')
    def test_cleanup_record_write_failure_retains_retry_owner(self):
        (self.job.directory/'cleanup-attempt-0001.json').write_bytes(b'preserve-original')
        self.job.done.set()
        with self.assertRaises(FileExistsError) as caught:self.job.retry_cleanup()
        self.assertIs(caught.exception.cleanup_owner,self.job);self.assertTrue(self.job.cleanup_held)
        self.assertFalse(self.job.retry_cleanup()['cleanup_held'])
    @unittest.skipUnless(os.name=='nt','Windows native Job ownership')
    def test_exact_limits_with_cpu_warmed_gated_helper(self):
        # A populated Job adds the helper's accrued CPU to PerJobUserTimeLimit.
        # Warm the helper to make that boundary deterministic without Blender.
        helper = ('import sys,time\nend=time.process_time()+0.08\n'
                  'while time.process_time()<end: pass\n'
                  'print("READY",flush=True)\nsys.stdin.readline()\n')
        process = subprocess.Popen([sys.executable, '-B', '-c', helper],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW)
        self.job._process = process
        self.job.done.set()
        ready = queue.Queue()
        reader = threading.Thread(target=lambda: ready.put(process.stdout.readline()), daemon=True)
        reader.start()
        observed = {}
        try:
            self.assertEqual(ready.get(timeout=5), b'READY\r\n')
            def configure_empty(owner):
                self.assertEqual(owner.active_count(), 0)
                observed.update(configure_limits(owner))
            self.job._job = cli_job.create(process, before_assign=configure_empty)
            self.assertEqual(observed['job_user_time_100ns'], CPU_SECONDS * 10_000_000)
            self.assertEqual(observed['job_memory_bytes'], MEMORY_BYTES)
            self.assertEqual(observed['active_process_limit'], PROCESS_LIMIT)
            self.assertEqual(observed['limit_flags'], 0x220c)
            process.stdin.write(b'GO\n')
            process.stdin.close()
            self.assertEqual(process.wait(timeout=5), 0)
        finally:
            result = self.job.retry_cleanup()
            reader.join(timeout=3)
        self.assertFalse(reader.is_alive())
        self.assertEqual(result['wrapper_exit_code'], 0)
        self.assertTrue(result['job']['closed'])
        self.assertTrue(result['job']['zero_observed'])
        self.assertFalse(result['job']['handle_retained'])

    @unittest.skipUnless(os.name=='nt','Windows native Job ownership')
    def test_actual_handle_before_close_failure_and_exact_retry(self):
        process=subprocess.Popen([sys.executable,'-B','-c','import sys; sys.stdin.readline()'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
        self.job._process=process;self.job._job=cli_job.create(process);self.job.done.set()
        native=self.job._job
        try:
            self.assertEqual(native.active_count(),1)
            with patch.object(native._native.kernel,'CloseHandle',return_value=0):
                with self.assertRaises(cli_job.JobError) as caught:self.job.retry_cleanup()
                self.assertIs(caught.exception.cleanup_owner,self.job)
                self.assertIs(cli_job.owner_for_process(process),native)
                self.assertTrue(native.snapshot()['handle_retained']);self.assertEqual(native.active_count(),0)
            result=self.job.retry_cleanup()
            self.assertTrue(result['job']['closed']);self.assertTrue(result['job']['zero_observed'])
            self.assertFalse(result['cleanup_held']);self.assertIsNone(cli_job.owner_for_process(process))
            self.assertEqual(result['wrapper_exit_code'],2)
        finally:
            if not native.closed:self.job.retry_cleanup()


if __name__=='__main__':unittest.main()
