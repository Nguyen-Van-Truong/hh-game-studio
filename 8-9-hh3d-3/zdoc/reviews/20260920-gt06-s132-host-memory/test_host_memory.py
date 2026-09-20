"""Failure-path checks without HTTP, engines or scheduler operations."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

path=Path(__file__).with_name('host_memory.py')
spec=importlib.util.spec_from_file_location('host_memory',path)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class FailureTests(unittest.TestCase):
    def test_host_screen_edges_and_unavailable(self):
        def row(rss=100,handles=2):
            return {'counters':{'rss_bytes':{'value':rss},'held_handles':{'value':handles}}}
        m.screen(row(110),row(),2000,5)
        for current,gap,index,code in [(row(111),2000,5,'CAMPAIGN_RSS_GROWTH'),
            (row(100,3),2000,5,'CAMPAIGN_RETAINED_COUNTER_GROWTH'),
            (row(),2000.001,5,'CAMPAIGN_STATUS_GAP'),
            (row(100,None),0,4,'CAMPAIGN_COUNTER_UNAVAILABLE')]:
            with self.subTest(code=code),self.assertRaises(Exception) as error:
                m.screen(current,row(),gap,index)
            self.assertEqual(error.exception.code,code)

    def test_constructor_owner_and_failed_cleanup_are_retained(self):
        class Held:
            closed=False
            observer=SimpleNamespace(probe=SimpleNamespace(handle=99))
            journal=SimpleNamespace(_cache_closed=False)
            closes=0
            def close(self):
                self.closes+=1
                raise m.job.BenchmarkJobError('CLEANUP_HELD')
            def phase_snapshot(self): return {'retained':True}
        held=Held()
        error=RuntimeError('constructor failed'); error.cleanup_owner=held
        campaign=SimpleNamespace(source_files=lambda:{})
        with tempfile.TemporaryDirectory() as tmp,patch.object(m,'OUT',Path(tmp)),\
             patch.object(m,'check',return_value=(campaign,{},path)),\
             patch.object(m,'CommandProducer',side_effect=error):
            self.assertEqual(m.child(),1)
            cleanup=json.loads((Path(tmp)/'child-cleanup.json').read_bytes())
            summary=json.loads((Path(tmp)/'summary.json').read_bytes())
            self.assertEqual(held.closes,1)
            self.assertFalse(cleanup['producer_closed'])
            self.assertFalse(cleanup['probe_released'])
            self.assertFalse(cleanup['journal_closed'])
            self.assertIsNotNone(cleanup['cleanup_error'])
            self.assertEqual(summary['disposition'],'FAILED')
            self.assertEqual(summary['error_code'],'RuntimeError')

    def test_parent_popen_failure_preserves_unknown_exit(self):
        class Held:
            process=None
            job=None
            def close(self): raise RuntimeError('cleanup failed')
            def process_handle_snapshot(self): return {'released':False}
        error=RuntimeError('Popen failed'); error.cleanup_owner=Held()
        with tempfile.TemporaryDirectory() as tmp,patch.object(m,'OUT',Path(tmp)/'run'),\
             patch.object(m,'check',return_value=(None,{},path)),\
             patch.object(m.job,'BenchmarkProcess',side_effect=error):
            self.assertEqual(m.launch(),1)
            result=json.loads((m.OUT/'result.json').read_bytes())
            self.assertIsNone(result['helper_exit'])
            self.assertFalse(result['captured_success'])
            self.assertEqual(len(result['errors']),2)

if __name__=='__main__': unittest.main()
