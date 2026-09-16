"""Bounded framing/authentication and main-thread routing regressions."""
import copy
import hashlib
import hmac
import importlib.util
from pathlib import Path
import socket
import struct
import sys
import threading
import time
import unittest

STUDIO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(STUDIO.parent))
spec=importlib.util.spec_from_file_location('test_gt04_ipc',STUDIO/'blender-addon/ipc_client.py')
ipc=importlib.util.module_from_spec(spec)
exec(compile(spec.loader.get_data(str(spec.origin)),str(spec.origin),'exec'),ipc.__dict__)


class FrameTests(unittest.TestCase):
    def setUp(self):
        a,b=socket.socketpair()
        self.host=ipc.Channel(a,b'x'*32,'a'*32,'control','host')
        self.client=ipc.Channel(b,b'x'*32,'a'*32,'control','blender')
    def tearDown(self):
        self.host.close(); self.client.close()
    def transfer(self,sender,receiver):
        end=time.monotonic()+1
        while time.monotonic()<end:
            sender.poll(); value=receiver.poll()
            if value is not None:return value
        self.fail('bounded frame deadline')
    def wire(self,**changes):
        value={'schema':ipc.SCHEMA,'session':'a'*32,'channel':'control','sender':'host',
               'sequence':1,'kind':'stop','body':{}}
        value.update(changes)
        value['mac']=hmac.new(b'x'*32,ipc.canonical_bytes(value),hashlib.sha256).hexdigest()
        raw=ipc.canonical_bytes(value)
        return struct.pack('!I',len(raw))+raw
    def test_auth_roundtrip_and_bidirectional_sequence(self):
        self.host.queue('stop',{})
        self.assertEqual(self.transfer(self.host,self.client)['kind'],'stop')
        self.client.queue('reply',{'public_ack':False})
        self.assertEqual(self.transfer(self.client,self.host)['sequence'],1)
    def test_empty_nonblocking_poll_returns_immediately(self):
        start=time.monotonic(); self.assertIsNone(self.client.poll())
        self.assertLess(time.monotonic()-start,.1)
    def test_fragmented_header_and_payload(self):
        raw=self.wire()
        for piece in (raw[:2],raw[2:4],raw[4:-1]):
            self.host.sock.sendall(piece); self.assertIsNone(self.client.poll())
        self.host.sock.sendall(raw[-1:]); self.assertEqual(self.client.poll()['kind'],'stop')
    def test_oversized_header_rejected_before_body(self):
        self.host.sock.sendall(struct.pack('!I',ipc.MAX_FRAME+1))
        with self.assertRaisesRegex(ipc.IPCError,'FRAME_CAP'):self.client.poll()
        self.assertEqual(len(self.client.rx),4)
    def test_zero_frame_rejected(self):
        self.host.sock.sendall(b'\0'*4)
        with self.assertRaisesRegex(ipc.IPCError,'FRAME_CAP'):self.client.poll()
    def test_wrong_key_rejected(self):
        self.host.key=b'y'*32; self.host.queue('stop',{}); self.host.poll()
        with self.assertRaisesRegex(ipc.IPCError,'AUTH'):self.client.poll()
    def test_reflected_authenticated_frame_rejected(self):
        self.host.sock.sendall(self.wire(sender='blender'))
        with self.assertRaisesRegex(ipc.IPCError,'BINDING'):self.client.poll()
    def test_foreign_session_rejected(self):
        self.host.sock.sendall(self.wire(session='b'*32))
        with self.assertRaisesRegex(ipc.IPCError,'BINDING'):self.client.poll()
    def test_cross_channel_replay_rejected(self):
        self.host.sock.sendall(self.wire(channel='data'))
        with self.assertRaisesRegex(ipc.IPCError,'BINDING'):self.client.poll()
    def test_duplicate_sequence_rejected(self):
        raw=self.wire(); self.host.sock.sendall(raw); self.client.poll()
        self.host.sock.sendall(raw)
        with self.assertRaisesRegex(ipc.IPCError,'BINDING'):self.client.poll()
    def test_bool_sequence_rejected(self):
        self.host.sock.sendall(self.wire(sequence=True))
        with self.assertRaisesRegex(ipc.IPCError,'BINDING'):self.client.poll()
    def test_duplicate_json_key_rejected(self):
        raw=b'{"schema":1,"schema":2}'
        self.host.sock.sendall(struct.pack('!I',len(raw))+raw)
        with self.assertRaises(ValueError):self.client.poll()
    def test_deep_json_rejected(self):
        raw=b'['*40+b'0'+b']'*40
        self.host.sock.sendall(struct.pack('!I',len(raw))+raw)
        with self.assertRaises(ValueError):self.client.poll()
    def test_send_frame_and_buffer_caps(self):
        with self.assertRaises(ValueError):self.host.queue('stop',{'value':'x'*ipc.MAX_FRAME})
        self.assertEqual(self.host.sent,0)
        self.host.tx.extend(b'x'*(ipc.MAX_BUFFER-1))
        with self.assertRaisesRegex(ipc.IPCError,'SEND_CAP'):self.host.queue('stop',{})
    def test_sequence_budget_and_key_zero_on_close(self):
        self.host.sent=ipc.MAX_MESSAGES
        with self.assertRaisesRegex(ipc.IPCError,'MESSAGE_CAP'):self.host.queue('stop',{})
        self.host.close();self.host.close();self.assertEqual(self.host.key,b'')
    def test_dead_peer_is_terminal_error(self):
        self.host.close()
        with self.assertRaisesRegex(ipc.IPCError,'EOF'):self.client.poll()


class PollTests(unittest.TestCase):
    def test_thread_guard_precedes_bpy(self):
        instance=object.__new__(ipc.Client); errors=[]
        def run():
            try:instance.tick()
            except Exception as exc:errors.append(str(exc))
        thread=threading.Thread(target=run);thread.start();thread.join(1)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,['IPC_MAIN_THREAD'])
    def test_control_stop_precedes_native_queue_effect(self):
        calls=[]
        class Queue:
            def tick(self):calls.append('effect')
        class Owner:
            _stopped=False
            queue=Queue()
        class Channel:
            last_receive=time.monotonic();tx=b''
            def __init__(self,name):self.name=name
            def poll(self):calls.append(self.name);return {'kind':'stop'} if self.name=='control' else None
        instance=object.__new__(ipc.Client)
        instance.closed=instance.quitting=False;instance.started=time.monotonic();instance.owner=Owner()
        instance.channels={name:Channel(name) for name in ('data','control')}
        def dispatch(lane,value):instance.owner._stopped=True
        instance.dispatch=dispatch
        self.assertEqual(instance.tick(),.01);self.assertEqual(calls,['control','data'])


if __name__=='__main__':unittest.main()
