"""Real HTTP FIFO/auth routing, inert engine/journal; native proof is separate."""
import http.client
import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch

STUDIO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(STUDIO.parent))
spec=importlib.util.spec_from_file_location('s54_fifo_host_test',STUDIO/'godot-addon/publication_owner.py')
owner=importlib.util.module_from_spec(spec);sys.modules[spec.name]=owner;spec.loader.exec_module(owner)
auth=owner._load('publication_session')
from studio.protocol.core import canonical_bytes,parse_json


class PublicationFifoHostTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='hh-fifo-host-');self.addCleanup(self.temp.cleanup)
        value=self.value=object.__new__(owner.GodotPublicationOwner)
        value._lock=threading.RLock();value._work=threading.Lock()
        value._closed=value._held=False;value._jobs={};value._leases={};value._read_leases={}
        value.project_id='project.fixture';value.contract=owner._load('contract');value.auth_model=auth
        value.sessions=auth.PublicationSession(value.project_id,Path(self.temp.name),value.contract.CATALOG_DIGEST)
        value._same_release=Mock();value._journal=Mock()
        value._journal.snapshot.return_value={'stopped':False}
        def persisted(**kw):value._journal.snapshot.return_value={'stopped':True}
        value._journal.stop.side_effect=persisted
        self.credentials=[value.sessions.issue() for _ in range(3)]
        self.server=owner._load('publication_transport').PublicationTransport(value).start()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.server.close()
        thread=getattr(self.value,'_stop_thread',None)
        if thread is not None:thread.join(3)
        self.value.sessions.halt()

    def call(self,path,body,client=0,control=False):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.control_port if control else self.server.port,timeout=2)
        try:
            connection.request('POST',path,canonical_bytes({'project_id':self.value.project_id,**body}),
                {'Content-Type':'application/json','Authorization':'Bearer '+self.credentials[client].bearer,
                 'X-HH-Catalog':self.value.contract.CATALOG_DIGEST})
            response=connection.getresponse();raw=response.read()
            return response.status,parse_json(raw)
        finally:connection.close()

    def enqueue(self,client):
        code,ticket=self.call('/v1/lease/enqueue',{'request_id':'request.'+str(client),'ttl_ms':30000,'wait_ms':90000},client)
        self.assertEqual(code,200)
        return ticket

    def test_actual_http_fifo_and_historical_ticket_do_not_reissue_lease(self):
        first=self.enqueue(0);second=self.enqueue(1);third=self.enqueue(2)
        self.assertEqual([r['state'] for r in (first,second,third)],['GRANTED','QUEUED','QUEUED'])
        self.assertEqual(self.call('/v1/lease',{'ttl_ms':30000},2)[1]['code'],'GODOT_FIFO_WAITER_ALREADY_OWNED')
        with patch.object(auth,'epoch_ms',return_value=first['lease']['expires_ms']+1):
            code,later=self.call('/v1/lease/poll',{'ticket_id':third['ticket_id']},2)
            self.assertEqual((code,later['state']),(200,'QUEUED'))
            code,granted=self.call('/v1/lease/poll',{'ticket_id':second['ticket_id']},1)
            self.assertEqual((code,granted['state']),(200,'GRANTED'))
            self.assertEqual(granted['lease']['fencing_epoch'],first['lease']['fencing_epoch']+1)
            code,historical=self.call('/v1/lease/poll',{'ticket_id':first['ticket_id']},0)
            self.assertEqual(historical,first)
            self.assertEqual(self.value.sessions._lease.fencing_epoch,granted['lease']['fencing_epoch'])
        self.assertIs(self.value._leases[self.credentials[1].session_id],self.value.sessions._lease)

    def test_legacy_writer_cannot_bypass_older_waiter(self):
        first=self.enqueue(0);second=self.enqueue(1)
        with patch.object(auth,'epoch_ms',return_value=first['lease']['expires_ms']+1):
            code,result=self.call('/v1/lease',{'ttl_ms':30000},2)
            self.assertEqual((code,result['code']),(400,'GODOT_LEASE_BUSY'))
            code,granted=self.call('/v1/lease/poll',{'ticket_id':second['ticket_id']},1)
            self.assertEqual((code,granted['state']),(200,'GRANTED'))
        self.assertEqual(self.value._fifo.snapshot()['queued'],0)

    def test_request_retry_parameters_scope_and_ticket_ownership(self):
        first=self.enqueue(0)
        self.assertEqual(self.enqueue(0),first)
        for path,body,client in (
            ('/v1/lease/poll',{'ticket_id':first['ticket_id']},1),
            ('/v1/lease/cancel',{'ticket_id':first['ticket_id'],'path':'elsewhere'},0),
            ('/v1/lease/enqueue',{'request_id':'request.0','ttl_ms':20000,'wait_ms':90000},0)):
            with self.subTest(path=path):self.assertEqual(self.call(path,body,client)[0],400)
        reader=self.value.sessions.issue(operations=frozenset({'scene.inspect'}))
        self.credentials.append(reader)
        self.assertEqual(self.call('/v1/lease/enqueue',{'request_id':'request.reader','ttl_ms':1000,'wait_ms':1000},3)[1]['code'],
                         'GODOT_OPERATION_FORBIDDEN')
        self.assertEqual(self.call('/v1/lease',{'ttl_ms':1000},3)[0],200)

    def test_stop_cancels_waiters_and_preserves_granted_ticket_and_durable_drain(self):
        first=self.enqueue(0);second=self.enqueue(1)
        code,canceled=self.call('/v1/lease/cancel',{'ticket_id':second['ticket_id']},1)
        self.assertEqual((code,canceled['state']),(200,'CANCELED'))
        third=self.enqueue(2)
        self.value._work.acquire()
        try:
            code,stop=self.call('/v1/stop',{'command_id':'control.stop'},0,True)
            self.assertEqual((code,stop['stopped'],stop['stop_persistence']),(200,True,'PENDING'))
            self.assertEqual(self.call('/v1/lease/poll',{'ticket_id':third['ticket_id']},2)[1]['state'],'STOPPED')
            self.assertEqual(self.call('/v1/lease/poll',{'ticket_id':first['ticket_id']},0)[1],first)
            self.value._journal.stop.assert_not_called()
        finally:self.value._work.release()
        self.value._stop_thread.join(3)
        self.assertEqual(self.value._stop_persistence,'DURABLE')


if __name__=='__main__':unittest.main()
