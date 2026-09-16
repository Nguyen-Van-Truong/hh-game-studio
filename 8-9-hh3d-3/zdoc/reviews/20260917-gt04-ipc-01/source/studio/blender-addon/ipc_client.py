"""Private fixture IPC; Blender polls sockets and bpy only on its main thread.

No general Python execution, file-open command, listener, or persistent thread.
The one-shot bootstrap comes from inherited stdin, never argv/environment.
"""
from __future__ import annotations
import errno
import hashlib
import hmac
import importlib.util
import os
from pathlib import Path
import re
import socket
import struct
import sys
import threading
import time

sys.dont_write_bytecode = True
STUDIO = Path(__file__).resolve().parents[1]
if str(STUDIO.parent) not in sys.path:
    sys.path.insert(0, str(STUDIO.parent))
from studio.protocol.core import canonical_bytes, parse_json

SCHEMA = 'HH-BLENDER-IPC-1'
MAX_FRAME = 65536
MAX_BUFFER = MAX_FRAME + 4
MAX_MESSAGES = 512
IO_SLICE = 16384
IDLE_SECONDS = 30


class IPCError(ValueError):
    pass


def need(value, code):
    if not value:
        raise IPCError(code)


def exact(value, fields):
    need(type(value) is dict and set(value) == set(fields), 'IPC_FIELDS')


class Channel:
    """A bounded, nonblocking socket owner. One caller per channel at a time."""
    def __init__(self, sock, key, session, lane, sender):
        need(type(key) is bytes and len(key) == 32, 'IPC_KEY')
        need(type(session) is str and re.fullmatch(r'[0-9a-f]{32}', session), 'IPC_SESSION')
        need(lane in ('data', 'control') and sender in ('host', 'blender'), 'IPC_CHANNEL')
        self.sock, self.key, self.session, self.lane, self.sender = sock, key, session, lane, sender
        self.receiver = 'blender' if sender == 'host' else 'host'
        self.sock.setblocking(False)
        self.rx, self.tx = bytearray(), bytearray()
        self.sent = self.received = 0
        self.closed = False
        self.last_receive = time.monotonic()

    def queue(self, kind, body):
        need(not self.closed and type(kind) is str and len(kind) <= 32 and type(body) is dict, 'IPC_ENVELOPE')
        need(self.sent < MAX_MESSAGES, 'IPC_MESSAGE_CAP')
        message = {'schema': SCHEMA, 'session': self.session, 'channel': self.lane,
                   'sender': self.sender, 'sequence': self.sent + 1, 'kind': kind, 'body': body}
        message['mac'] = hmac.new(self.key, canonical_bytes(message), hashlib.sha256).hexdigest()
        raw = canonical_bytes(message)
        need(len(raw) <= MAX_FRAME and len(self.tx) + 4 + len(raw) <= MAX_BUFFER, 'IPC_SEND_CAP')
        self.tx.extend(struct.pack('!I', len(raw)) + raw)
        self.sent += 1
        return self.sent

    def poll(self):
        need(not self.closed, 'IPC_CLOSED')
        if self.tx:
            try:
                count = self.sock.send(memoryview(self.tx)[:IO_SLICE])
                need(count > 0, 'IPC_EOF')
                del self.tx[:count]
            except BlockingIOError:
                pass
        # One bounded recv per poll; oversized headers fail before payload growth.
        if len(self.rx) < MAX_BUFFER:
            try:
                raw = self.sock.recv(min(IO_SLICE, MAX_BUFFER-len(self.rx)))
                need(bool(raw), 'IPC_EOF')
                self.rx.extend(raw)
            except BlockingIOError:
                pass
        if len(self.rx) < 4:
            return None
        size = struct.unpack('!I', self.rx[:4])[0]
        need(0 < size <= MAX_FRAME, 'IPC_FRAME_CAP')
        if len(self.rx) < size + 4:
            return None
        raw = bytes(self.rx[4:size+4]); del self.rx[:size+4]
        value = parse_json(raw)
        exact(value, ('schema','session','channel','sender','sequence','kind','body','mac'))
        signature = value.pop('mac')
        need(type(signature) is str and re.fullmatch('[0-9a-f]{64}',signature)
             and hmac.compare_digest(signature,hmac.new(self.key,canonical_bytes(value),hashlib.sha256).hexdigest()),
             'IPC_AUTH')
        need(value['schema']==SCHEMA and value['session']==self.session and value['channel']==self.lane
             and value['sender']==self.receiver and type(value['sequence']) is int
             and value['sequence']==self.received+1 and value['sequence']<=MAX_MESSAGES
             and type(value['kind']) is str and len(value['kind'])<=32 and type(value['body']) is dict,
             'IPC_BINDING')
        self.received += 1
        self.last_receive = time.monotonic()
        return value

    def close(self):
        if not self.closed:
            self.closed = True
            self.key = b''
            self.rx.clear(); self.tx.clear()
            self.sock.close()


def load_ui():
    path = Path(__file__).with_name('ui_adapter.py')
    spec = importlib.util.spec_from_file_location('_hh_gt04_ipc_ui',path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)
    return module


class Client:
    def __init__(self, settings):
        need(threading.current_thread() is threading.main_thread(), 'IPC_MAIN_THREAD')
        import bpy
        exact(settings,('key','session','ports','owned_root'))
        need(type(settings['key']) is str and re.fullmatch('[0-9a-f]{64}',settings['key']), 'IPC_BOOTSTRAP')
        ports=settings['ports']
        exact(ports,('data','control'))
        need(all(type(port) is int and 1<=port<=65535 for port in ports.values()),'IPC_PORT')
        need(not bpy.app.background and bpy.app.version[:3]==(5,2,1)
             and not bpy.context.preferences.filepaths.use_scripts_auto_execute, 'IPC_PINNED_GUI')
        self.bpy=bpy; self.ui=load_ui(); self.owner=None; self.channels={}; self.welcomed=set()
        self.root=Path(settings['owned_root']); self.quitting=False; self.closed=False
        self.started=time.monotonic(); self.timer=self.tick
        key=bytes.fromhex(settings['key'])
        try:
            for lane in ('control','data'):
                sock=socket.socket()
                sock.setblocking(False)
                result=sock.connect_ex(('127.0.0.1',ports[lane]))
                need(result in (0,errno.EINPROGRESS,errno.EWOULDBLOCK,10035),'IPC_CONNECT')
                channel=Channel(sock,key,settings['session'],lane,'blender')
                self.channels[lane]=channel
                channel.queue('hello',{'pid':os.getpid(),'version':bpy.app.version_string,
                    'main_thread':True,'background':False,'python_threads':len(threading.enumerate()),'public_ack':False})
            settings['key']=''; key=b''
            bpy.app.timers.register(self.timer,first_interval=.01,persistent=False)
        except BaseException:
            self.close()
            raise

    def initialize(self):
        # Only the host-created fresh factory scene is admitted. Never open a file.
        need(self.owner is None and len(self.bpy.data.scenes)==1, 'IPC_FACTORY_SCENE')
        for obj in list(self.bpy.data.objects):
            self.bpy.data.objects.remove(obj,do_unlink=True)
        for collection in (self.bpy.data.meshes,self.bpy.data.cameras,self.bpy.data.lights,
                           self.bpy.data.materials,self.bpy.data.images,self.bpy.data.worlds,self.bpy.data.brushes):
            for item in list(collection): collection.remove(item)
        self.bpy.context.scene.unit_settings.system='METRIC'
        self.owner=self.ui.UIAdapter(owned_root=self.root,external_poll=True)

    def dispatch(self,lane,value):
        kind,body=value['kind'],value['body']
        if lane not in self.welcomed:
            need(kind=='welcome' and body=={'public_ack':False},'IPC_WELCOME')
            self.welcomed.add(lane)
            if len(self.welcomed)==2:
                self.initialize()
                self.channels['control'].queue('ready',{'pid':os.getpid(),'public_ack':False})
            return
        need(self.owner is not None,'IPC_NOT_READY')
        try:
            if lane=='control':
                if kind in ('stop','quit','ping'):
                    exact(body,())
                    if kind!='ping': self.owner.stop()
                    self.quitting=kind=='quit'
                    result={'stopped':self.owner._stopped,'public_ack':False}
                elif kind=='result':
                    exact(body,('command_id',))
                    result=self.owner.queue.result(body['command_id'])
                else: raise IPCError('IPC_CONTROL_OPERATION')
            else:
                need(kind=='submit','IPC_DATA_OPERATION'); exact(body,('command','ttl_ms'))
                result=self.owner.queue.submit(self.ui.c.canonical(body['command']),ttl_ms=body['ttl_ms'])
            response={'request_sequence':value['sequence'],'ok':True,'result':result,'public_ack':False}
        except (self.ui.c.Rejected,KeyError):
            response={'request_sequence':value['sequence'],'ok':False,'reason':'COMMAND_REJECTED','public_ack':False}
        self.channels[lane].queue('reply',response)

    def tick(self):
        need(threading.current_thread() is threading.main_thread(),'IPC_MAIN_THREAD')
        try:
            if self.closed: return None
            need(time.monotonic()-self.started<120,'IPC_SESSION_DEADLINE')
            # Control is consumed before data submission or any native effect.
            for lane in ('control','data'):
                channel=self.channels[lane]
                need(time.monotonic()-channel.last_receive<IDLE_SECONDS,'IPC_IDLE_TIMEOUT')
                value=channel.poll()
                if value is not None: self.dispatch(lane,value)
            if self.quitting and not any(ch.tx for ch in self.channels.values()):
                self.close(); self.bpy.ops.wm.quit_blender(); return None
            if self.owner is not None and not self.owner._stopped:
                self.owner.queue.tick()
            return .01
        except BaseException:
            # Fixed text only: exceptions/frames/bootstrap must never leak keys.
            print('HH_BLENDER_IPC_CLOSED',flush=True)
            self.close(); self.bpy.ops.wm.quit_blender(); return None

    def close(self):
        if self.closed: return
        self.closed=True
        if self.owner is not None: self.owner.close()
        for channel in self.channels.values(): channel.close()


def main():
    # The trusted parent writes a single <=4096-byte line, then closes stdin.
    # The outer owned watchdog bounds startup if the parent dies mid-bootstrap.
    raw=sys.stdin.buffer.readline(4097)
    need(raw.endswith(b'\n') and len(raw)<=4096,'IPC_BOOTSTRAP_CAP')
    settings=parse_json(raw)
    global _CLIENT
    _CLIENT=Client(settings)


if __name__=='__main__':
    try: main()
    except BaseException:
        print('HH_BLENDER_IPC_BOOTSTRAP_CLOSED',flush=True)
        import bpy
        bpy.ops.wm.quit_blender()
