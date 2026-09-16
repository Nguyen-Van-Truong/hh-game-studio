import json
import time
import unittest
from unittest import mock
from test_managed_service import ManagedServiceTests

class ServiceDeadlineDiagnostic(ManagedServiceTests):
    def test_frame_received_after_deadline_during_admitted_phase(self):
        # Long enough to build/admit the real native fixture, then wait past it.
        self.start(session_timeout_ms=700)
        request=self.request()
        entered=__import__('threading').Event()
        original=self.owner.selector.stage
        def delayed(*args,**kwargs):
            entered.set()
            self.release.wait(3)
            return original(*args,**kwargs)
        with mock.patch.object(self.owner.selector,'stage',side_effect=delayed):
            self.send('/v1/commands',request)
            self.assertTrue(entered.wait(2))
            self.assertEqual(self.replies['work'].get(timeout=2)['status'],'ACCEPTED_PENDING')
            # Both readers were already waiting and the pump is in admitted I/O.
            time.sleep(max(0,self.service._deadline-time.monotonic())+.05)
            before=self.owner.log.binding().witnessed
            sent_after_ms=(time.monotonic()-self.service._deadline)*1000
            result=self.rpc('/v1/lease',{'project_id':'project.fixture','ttl_ms':1000})
            after=self.owner.log.binding().witnessed
            observed={'sent_after_deadline_ms':round(sent_after_ms,1),
                      'fresh_lease_received':'lease_id' in result,
                      'durable_event_added':after.sequence>before.sequence,
                      'before_sequence':before.sequence,'after_sequence':after.sequence}
            print('HH_SERVICE_DEADLINE_DIAGNOSTIC '+json.dumps(observed),flush=True)
            self.assertTrue(observed['fresh_lease_received'])
            self.assertTrue(observed['durable_event_added'])
            self.release.set()

suite=unittest.TestSuite([ServiceDeadlineDiagnostic('test_frame_received_after_deadline_during_admitted_phase')])
r=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if r.wasSuccessful() else 1)
