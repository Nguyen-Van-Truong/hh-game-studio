"""Owned Windows EditorPlugin IPC. Registered native facts, never user authority."""
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes as W
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import uuid

from studio.protocol.core import canonical_bytes, parse_json
from studio.host.core.private_store import _StoreApi

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parent
MAX_FRAME = 1572864
MAX_LOG = 262144
MAX_EFFECTS = 16
GUI_SHA256 = 'ab1824f85bfd8e0e4128182c000c4003a3e042245b2967848d089b2a04b22424'
_ID = re.compile(r'[a-z][a-z0-9._-]{0,63}\Z')
_REV = re.compile(r'sha256:[0-9a-f]{64}\Z')


class EditorOwnerError(ValueError):
    def __init__(self, code, *, outcome_unknown=False, cleanup_owner=None):
        self.code, self.outcome_unknown, self.cleanup_owner = code, outcome_unknown, cleanup_owner
        super().__init__(code)


def _need(value, code):
    if not value:
        raise EditorOwnerError(code)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _load(name):
    path = HERE / (name + '.py')
    raw = path.read_bytes()
    key = '_hh_editor_' + _sha(str(path).encode() + b'\0' + raw)
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        try:
            exec(compile(raw, str(path), 'exec'), module.__dict__)
        except BaseException:
            del sys.modules[key]
            raise
    return sys.modules[key]


comparator = _load('profile_readback')
factory = comparator.factory
bundle_codec = factory.bundle_codec
cli_job = _load('cli_job')


def _release():
    paths = [HERE / name for name in ('editor_owner.py', 'cli_job.py', 'profile_readback.py',
             'fixture_profile.py', 'bundle_staging.py', 'bundle_v2.py', 'scene_profile.py', 'script_profile.py',
             'fixture_profile/source-pins.json')]
    paths.append(STUDIO / 'toolchain.lock.json')
    for directory in (STUDIO / 'protocol', STUDIO / 'host/core'):
        paths.extend(path for path in directory.rglob('*.py') if '__pycache__' not in path.parts)
    pins = json.loads((HERE / 'fixture_profile/source-pins.json').read_bytes())
    paths.extend(STUDIO / row['source'] for row in pins['files'].values())
    return {str(path.relative_to(STUDIO)).replace('\\', '/'): _sha(path.read_bytes()) for path in sorted(set(paths))}


_IMPORTED_RELEASE = _release()


def _regular(path):
    info = path.stat(follow_symlinks=False)
    _need(not path.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400, 'EDITOR_REPARSE')
    return info


def _identity(value):
    return {'volume': str(value.volume), 'file_id': value.file_id}


def _metadata(files):
    return {path: {'sha256': _sha(raw), 'size_bytes': len(raw)} for path, raw in files.items()}


def _semantic(snapshot):
    _need(type(snapshot) is dict and snapshot.get('ok') is True and snapshot.get('scene_path') == 'res://scenes/fixture.tscn', 'EDITOR_SNAPSHOT')
    _need(type(snapshot.get('generation')) is int and snapshot['generation'] > 0 and snapshot.get('offset') == 0,
          'EDITOR_GENERATION')
    state = snapshot.get('state')
    _need(type(state) is dict and set(state) == {'nodes'} and type(state['nodes']) is list
          and len(state['nodes']) == snapshot.get('total') and 1 <= len(state['nodes']) <= 64, 'EDITOR_SEMANTIC_SHAPE')
    raw = canonical_bytes(state)
    _need(len(raw) <= 262144 and snapshot.get('revision') == 'sha256:' + _sha(raw), 'EDITOR_SEMANTIC_HASH')
    return raw


@dataclass(frozen=True, slots=True)
class EditorEffectIntent:
    intent_id: str
    command_id: str
    request_digest: str
    kind: str
    expected_generation: int
    expected_revision: str
    deadline_ms: int

    @property
    def scratch_name(self):
        return 'capture-' + self.intent_id + '.tscn'


@dataclass(frozen=True, slots=True)
class EditorEditIntent:
    intent_id: str
    command_id: str
    request_digest: str
    kind: str
    expected_generation: int
    expected_revision: str
    deadline_ms: int
    operation: str
    projection_sha256: str
    checkpoint_observation_id: str
    checkpoint_scene_sha256: str


@dataclass(frozen=True, slots=True)
class EditorEditReceipt:
    command_id: str
    request_digest: str
    observation_id: str
    editor_session_id: str
    semantic_revision: str
    checkpoint_observation_id: str
    public_ack: bool = False


@dataclass(frozen=True, slots=True)
class EditorCaptureReceipt:
    command_id: str
    request_digest: str
    observation_id: str
    editor_session_id: str
    scene_sha256: str
    semantic_revision: str
    public_ack: bool = False


@dataclass(frozen=True, slots=True)
class EditorAdoptionReceipt:
    command_id: str
    request_digest: str
    observation_id: str
    editor_session_id: str
    project_revision: str
    semantic_revision: str
    public_ack: bool = False


@dataclass(frozen=True, slots=True)
class EditorRetirementReceipt:
    command_id: str
    request_digest: str
    observation_id: str
    editor_session_id: str
    next_generation: int
    public_ack: bool = False


@dataclass(frozen=True, slots=True)
class EditorGenerationReceipt:
    command_id: str
    request_digest: str
    observation_id: str
    editor_session_id: str
    project_revision: str
    semantic_revision: str
    public_ack: bool = False


_HELPER = """import subprocess,sys,json,os
if sys.stdin.readline() != 'GO\\n': sys.exit(125)
p=subprocess.Popen(sys.argv[2:],stdin=subprocess.DEVNULL)
with open(sys.argv[1]+'-start.json','x',encoding='utf-8') as f: json.dump({'pid':p.pid},f)
code=p.wait()
with open(sys.argv[1]+'-exit.json','x',encoding='utf-8') as f: json.dump({'pid':p.pid,'exit_code':code},f)
sys.exit(code)
"""


class EditorOwner:
    """One fresh owned project/editor. Root must authorize every effect phase."""
    def __init__(self, evidence_parent: Path, initial_bundle, *, editor_binary: Path, initial_generation: int = 1):
        _need(type(initial_generation) is int and 1 <= initial_generation <= 2147483647, 'EDITOR_GENERATION_SEED')
        _need(os.name == 'nt', 'EDITOR_WINDOWS_REQUIRED')
        _need(type(initial_bundle) is bundle_codec.CompleteFixtureBundle, 'EDITOR_BUNDLE_TYPE')
        factory.qualify(initial_bundle)
        _need(_release() == _IMPORTED_RELEASE, 'EDITOR_RELEASE_CHANGED')
        self._mutex = threading.RLock()
        self._closed = self._held = self._stopped = False
        self._job = self._process = self._connection = self._listener = self._target_handle = None
        self._api = None
        self._threads = []
        self._overflow = threading.Event()
        self._sequence = 0
        self._rx = b''
        self._pending = None
        self._intents, self._records = {}, {}
        self._files = dict(initial_bundle.files)
        self._session = 'editor-' + uuid.uuid4().hex
        self._token = secrets.token_hex(32)
        self._source = dict(_IMPORTED_RELEASE)
        self._binary = Path(editor_binary).absolute()
        self._bundle = initial_bundle
        self._cleanup = None
        self._replacement_reserved = False
        self._successor_reserved = False
        self._edit_commands = set()
        try:
            parent = Path(evidence_parent).absolute()
            for path in (parent, *parent.parents, self._binary, *self._binary.parents):
                _regular(path)
            _need(parent.is_dir() and self._binary.name == 'Godot_v4.7.2-stable_win64.exe'
                  and _sha(self._binary.read_bytes()) == GUI_SHA256, 'EDITOR_BINARY_PIN')
            self._api = _StoreApi()
            self.directory = parent / ('editor-' + uuid.uuid4().hex)
            self._api.mkdir(self.directory)
            self.project = self.directory / 'project'
            self._api.mkdir(self.project)
            self._scratch = self.directory / 'scratch'
            self._api.mkdir(self._scratch)
            self._root_handle = self._api.open(self.project, directory=True)
            self._root_identity = self._api.inspect(self._root_handle, self.project, directory=True)
            self._api.check_security(self._root_handle)
            for name, raw in self._files.items():
                path = self.project / name
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('xb') as handle:
                    handle.write(raw)
            self._listener = socket.socket()
            self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            self._listener.bind(('127.0.0.1', 0))
            self._listener.listen(1)
            self._listener.settimeout(.1)
            env = {key: value for key, value in os.environ.items() if not key.startswith('HH_EDITOR_')}
            env.update(HH_EDITOR_TOKEN=self._token, HH_EDITOR_SESSION=self._session,
                       HH_EDITOR_SCRATCH=str(self._scratch), HH_EDITOR_PORT=str(self._listener.getsockname()[1]))
            for key in ('APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP'):
                path = self.directory / key.lower()
                path.mkdir(exist_ok=True)
                env[key] = str(path)
            argv = [str(self._binary), '--headless', '--editor', '--path', str(self.project),
                    'res://scenes/fixture.tscn', '--rendering-method', 'gl_compatibility']
            self._process = subprocess.Popen([sys.executable, '-B', '-c', _HELPER,
                str(self.directory / 'process'), *argv], cwd=self.project, env=env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW)
            self._job = cli_job.create(self._process)
            for name, pipe in (('stdout', self._process.stdout), ('stderr', self._process.stderr)):
                thread = threading.Thread(target=self._drain, args=(name, pipe), daemon=True)
                self._threads.append(thread)
                thread.start()
            self._process.stdin.write(b'GO\n')
            self._process.stdin.close()
            deadline = time.monotonic() + 20
            while not (self.directory / 'process-start.json').is_file():
                _need(time.monotonic() < deadline and self._process.poll() is None, 'EDITOR_START_TIMEOUT')
                time.sleep(.01)
            started = json.loads((self.directory / 'process-start.json').read_bytes())
            self._pid = started['pid']
            self._bind_process()
            while self._connection is None:
                _need(time.monotonic() < deadline and self._process.poll() is None, 'EDITOR_CONNECT_TIMEOUT')
                try:
                    candidate, address = self._listener.accept()
                except socket.timeout:
                    continue
                candidate.settimeout(.1)
                self._connection = candidate
            hello = self._receive(deadline)
            if type(hello) is dict:
                (self.directory / 'hello.json').write_bytes(canonical_bytes({key: value for key, value in hello.items() if key != 'token'}))
            _need(set(hello) == {'kind', 'token', 'editor_session_id', 'pid', 'project_root', 'editor_hint', 'main_thread', 'version'}
                  and hello['kind'] == 'hello' and secrets.compare_digest(hello['token'], self._token)
                  and hello['editor_session_id'] == self._session and hello['pid'] == self._pid
                  and hello['editor_hint'] is True and hello['main_thread'] is True
                  and hello['version'] == '4.7.2-stable (official)'
                  and Path(hello['project_root']).resolve() == self.project.resolve(), 'EDITOR_HELLO_REJECTED')
            self._token = ''
            self._listener.close()
            self._listener = None
            while True:
                response = self._exchange('inspect', {}, timeout=3, allow_rejection=True)
                if response.get('ok') is True:
                    self._verify_snapshot(response)
                    seeded = self._exchange('seed_generation', {'initial_generation': initial_generation})
                    self._verify_snapshot(seeded)
                    _need(seeded['generation'] == initial_generation and seeded['can_undo'] is False
                          and seeded['can_redo'] is False, 'EDITOR_GENERATION_SEED_READBACK')
                    break
                _need(time.monotonic() < deadline, 'EDITOR_BIND_TIMEOUT')
                time.sleep(.05)
        except BaseException as error:
            self._held = True
            try:
                self.close()
            except BaseException:
                error.cleanup_owner = self
            raise

    def _bind_process(self):
        self._kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        k = self._kernel
        k.OpenProcess.argtypes, k.OpenProcess.restype = [W.DWORD, W.BOOL, W.DWORD], W.HANDLE
        k.GetProcessTimes.argtypes, k.GetProcessTimes.restype = [W.HANDLE] + [ctypes.POINTER(W.FILETIME)] * 4, W.BOOL
        k.QueryFullProcessImageNameW.argtypes, k.QueryFullProcessImageNameW.restype = [W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD)], W.BOOL
        k.CloseHandle.argtypes, k.CloseHandle.restype = [W.HANDLE], W.BOOL
        self._target_handle = k.OpenProcess(0x1000 | 0x100000, False, self._pid)
        _need(self._target_handle, 'EDITOR_NATIVE_PROCESS_OPEN')
        created, exited, kernel, user = (W.FILETIME() for _ in range(4))
        _need(k.GetProcessTimes(self._target_handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)), 'EDITOR_NATIVE_PROCESS_TIME')
        self._creation = str((created.dwHighDateTime << 32) | created.dwLowDateTime)
        path, size = ctypes.create_unicode_buffer(32768), W.DWORD(32768)
        _need(k.QueryFullProcessImageNameW(self._target_handle, 0, path, ctypes.byref(size))
              and Path(path.value).resolve() == self._binary.resolve(), 'EDITOR_NATIVE_PROCESS_IMAGE')

    @property
    def identity(self):
        with self._mutex:
            self._healthy()
            return {'session_id': self._session, 'pid': self._pid, 'creation_filetime': self._creation,
                    'root_identity': _identity(self._root_identity), 'engine_sha256': GUI_SHA256,
                    'installed_source_sha256': _sha(canonical_bytes(self._source))}

    def _drain(self, name, pipe):
        total = 0
        try:
            with (self.directory / (name + '.txt')).open('xb') as output:
                while True:
                    raw = pipe.read1(4096)
                    if not raw:
                        break
                    output.write(raw[:max(0, MAX_LOG - total)])
                    output.flush()
                    total += len(raw)
                    if total > MAX_LOG:
                        self._overflow.set()
        finally:
            pipe.close()

    def _healthy(self):
        _need(not self._closed and not self._held and not self._overflow.is_set(), 'EDITOR_OWNER_HELD_OR_CLOSED')
        _need(_release() == self._source, 'EDITOR_RELEASE_CHANGED')
        _need(self._process.poll() is None and self._job.active_count() not in (None, 0), 'EDITOR_PROCESS_NOT_LIVE')
        current = self._api.inspect(self._root_handle, self.project, directory=True)
        _need(current.same_file(self._root_identity), 'EDITOR_PROJECT_IDENTITY')
        self._api.check_security(self._root_handle)
        for name in ('stdout.txt', 'stderr.txt'):
            path = self.directory / name
            if path.exists():
                _need(not re.search(rb'(?i)\b(warning|error|fatal|traceback)\b', path.read_bytes()), 'EDITOR_NATIVE_DIAGNOSTIC')

    def _read_file(self, path, cap=1048576):
        for part in (path, *path.parents):
            _regular(part)
        handle = self._api.open(path)
        try:
            before = self._api.inspect(handle, path)
            raw = self._api.read(handle, cap)
            _need(self._api.inspect(handle, path) == before and len(raw) == before.size, 'EDITOR_FILE_CHANGED')
            return raw
        finally:
            self._api.close(handle)

    def _receive(self, deadline):
        while b'\n' not in self._rx:
            _need(time.monotonic() < deadline and not self._overflow.is_set(), 'EDITOR_IPC_TIMEOUT')
            try:
                raw = self._connection.recv(65536)
            except socket.timeout:
                continue
            _need(raw, 'EDITOR_IPC_EOF')
            self._rx += raw
            _need(len(self._rx) <= MAX_FRAME, 'EDITOR_IPC_LIMIT')
        line, self._rx = self._rx.split(b'\n', 1)
        # Shared parser's envelope cap is intentionally smaller than the full
        # semantic observation; JSON here is bounded by fixed authenticated IPC.
        def pairs(rows):
            result = {}
            for key, value in rows:
                _need(key not in result, 'EDITOR_DUPLICATE_FIELD')
                result[key] = value
            return result
        return json.loads(line, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(EditorOwnerError('EDITOR_NONFINITE')))

    def _exchange(self, kind, body, *, timeout=5, allow_rejection=False):
        self._healthy()
        self._sequence += 1
        _need(self._sequence <= 128, 'EDITOR_MESSAGE_CAPACITY')
        raw = json.dumps({'sequence': self._sequence, 'editor_session_id': self._session, 'kind': kind, 'body': body},
                         separators=(',', ':'), allow_nan=False).encode() + b'\n'
        _need(len(raw) <= MAX_FRAME, 'EDITOR_IPC_LIMIT')
        deadline = time.monotonic() + timeout
        remaining = memoryview(raw)
        while remaining:
            _need(time.monotonic() < deadline, 'EDITOR_IPC_TIMEOUT')
            try:
                count = self._connection.send(remaining)
            except socket.timeout:
                continue
            _need(count > 0, 'EDITOR_IPC_EOF')
            remaining = remaining[count:]
        response = self._receive(deadline)
        _need(type(response) is dict and set(response) == {'sequence', 'editor_session_id', 'result'}
              and type(response['sequence']) is int and response['sequence'] == self._sequence
              and response['editor_session_id'] == self._session and type(response['result']) is dict,
              'EDITOR_RESPONSE_BINDING')
        value = response['result']
        _need(allow_rejection or value.get('ok') is True, str(value.get('code', 'EDITOR_REJECTED')))
        return value

    def _verify_snapshot(self, value, *, files=None):
        raw = _semantic(value)
        _need(value['editor_session_id'] == self._session and type(value['root_instance_id']) is str
              and value['working_files'] == _metadata(self._files if files is None else files), 'EDITOR_SNAPSHOT_INPUT_BINDING')
        for name, expected in (self._files if files is None else files).items():
            _need(self._read_file(self.project / name) == expected, 'EDITOR_WORKING_BYTES_CHANGED')
        return raw

    def inspect(self):
        with self._mutex:
            value = self._exchange('inspect', {})
            self._verify_snapshot(value)
            return value

    def apply_projection(self, projection):
        """Trusted root supplies an already validated existing semantic command."""
        with self._mutex:
            _need(not self._stopped and self._pending is None, 'EDITOR_EFFECT_PENDING_OR_STOPPED')
            result = self._exchange('projection', {'projection': projection})
            self.inspect()
            return result

    def prepare_edit(self, command_id, digest, projection, checkpoint, *, deadline_ms):
        """Trusted validated projection; exact registered capture is its checkpoint."""
        with self._mutex:
            record = self._receipt(checkpoint, EditorCaptureReceipt)
            prior = parse_json(record[2])
            _need(command_id == checkpoint.command_id and digest == checkpoint.request_digest,
                  'EDITOR_EDIT_CHECKPOINT_COMMAND')
            _need(command_id not in self._edit_commands, 'EDITOR_EDIT_COMMAND_ALREADY_PREPARED')
            _need(type(projection) is dict and set(projection) == {'operation','command_id',
                  'expected_revision','expected_generation','target_stable_id','payload'}, 'EDITOR_EDIT_PROJECTION')
            copied = parse_json(canonical_bytes(projection))
            _need(copied['operation'] in ('scene.node.create','scene.node.update','scene.node.remove','scene.undo','scene.redo')
                  and copied['command_id'] == command_id and copied['expected_revision'] == prior['semantic_revision']
                  and type(copied['expected_generation']) is int and copied['expected_generation'] == prior['generation_after']
                  and type(copied['payload']) is dict
                  and type(copied['payload'].get('expected_generation')) is int
                  and copied['payload']['expected_generation'] == copied['expected_generation'],
                  'EDITOR_EDIT_PROJECTION_BINDING')
            _need(len(canonical_bytes(copied)) <= 65536, 'EDITOR_EDIT_PROJECTION_LIMIT')
            _need(type(deadline_ms) is int and int(time.time()*1000) < deadline_ms <= int(time.time()*1000)+10000,
                  'EDITOR_EDIT_DEADLINE')
            _need(not self._stopped and self._pending is None and len(self._intents) < MAX_EFFECTS,
                  'EDITOR_EFFECT_PENDING_OR_STOPPED')
            self.capture_bytes(checkpoint)
            before = self.inspect()
            _need(before['revision'] == prior['semantic_revision'] and before['generation'] == prior['generation_after']
                  and before['root_instance_id'] == prior['root_after'] and before['working_files'] == prior['working_files']
                  and canonical_bytes(before['state']) == canonical_bytes(prior['semantic_state']),
                  'EDITOR_EDIT_CHECKPOINT_STALE')
            intent = EditorEditIntent(uuid.uuid4().hex,command_id,digest,'edit',before['generation'],before['revision'],
                deadline_ms,copied['operation'],_sha(canonical_bytes(copied)),checkpoint.observation_id,checkpoint.scene_sha256)
            body = {name:getattr(intent,name) for name in intent.__slots__}
            body['projection'] = copied
            self._edit_commands.add(command_id)
            try:
                response = self._exchange('prepare',body)
                self._verify_snapshot(response['before'])
                _need(all(response['before'][key] == before[key] for key in
                      ('revision','generation','root_instance_id','working_files','state','history_id','can_undo','can_redo')),
                      'EDITOR_EDIT_PREPARE_CHANGED')
            except BaseException as error:
                self._held = True
                if not isinstance(error,Exception):
                    error.cleanup_owner = self; error.outcome_unknown = True
                    raise
                raise EditorOwnerError('EDITOR_EDIT_PREPARE_UNKNOWN',outcome_unknown=True,cleanup_owner=self) from error
            self._intents[intent.intent_id] = (intent,canonical_bytes({name:getattr(intent,name) for name in intent.__slots__}),
                before,canonical_bytes(copied),checkpoint)
            self._pending = intent
            return intent

    def apply_edit(self, intent):
        """One main-thread guarded effect; persistence/authority stay in coordinator."""
        with self._mutex:
            record = self._intent(intent,'edit')
            _need(type(intent) is EditorEditIntent and _sha(record[3]) == intent.projection_sha256,
                  'EDITOR_EDIT_INTENT_CHANGED')
            self.capture_bytes(record[4])
            self._pending = None
            try:
                result = self._exchange('consume',{'intent_id':intent.intent_id})
                facts = self._facts(intent,result)
                transition = result.get('edit_result')
                _need(type(transition) is dict and transition.get('ok') is True
                      and transition.get('code') == 'SCENE_APPLIED_IN_MEMORY'
                      and transition.get('command_id') == intent.command_id and transition.get('operation') == intent.operation
                      and transition.get('filesystem_mutated') is False
                      and transition.get('generation') == intent.expected_generation
                      and transition.get('before_revision') == intent.expected_revision
                      and transition.get('revision') == facts['semantic_revision']
                      and canonical_bytes(transition.get('state')) == canonical_bytes(facts['semantic_state']),
                      'EDITOR_EDIT_NATIVE_RESULT')
                _need(facts['generation_after'] == facts['generation_before'] and facts['root_after'] == facts['root_before']
                      and facts['working_files'] == record[2]['working_files'] and facts['history_boundary'] is False,
                      'EDITOR_EDIT_CONTEXT_CHANGED')
                facts.update(operation=intent.operation,projection_sha256=intent.projection_sha256,
                    checkpoint_observation_id=intent.checkpoint_observation_id,checkpoint_scene_sha256=intent.checkpoint_scene_sha256,
                    before_revision=intent.expected_revision, before_semantic_sha256=_sha(canonical_bytes(record[2]['state'])),
                    history_id_before=record[2]['history_id'],history_id_after=result['after']['history_id'],
                    files_saved=False,live_state_durable=False)
                _need(facts['history_id_before'] == facts['history_id_after'], 'EDITOR_EDIT_HISTORY_CHANGED')
                receipt = EditorEditReceipt(intent.command_id,intent.request_digest,'edit-'+uuid.uuid4().hex,
                    self._session,facts['semantic_revision'],intent.checkpoint_observation_id)
                return self._register(receipt,facts)
            except BaseException as error:
                self._held = True
                if not isinstance(error,Exception):
                    error.cleanup_owner = self; error.outcome_unknown = True
                    raise
                raise EditorOwnerError('EDITOR_EDIT_UNKNOWN',outcome_unknown=True,cleanup_owner=self) from error

    def edit_observation(self, receipt):
        with self._mutex:
            row = self._receipt(receipt,EditorEditReceipt)
            facts = parse_json(row[2]); actual = self.inspect()
            _need(actual['revision'] == facts['semantic_revision'] and actual['generation'] == facts['generation_after']
                  and actual['root_instance_id'] == facts['root_after'] and actual['working_files'] == facts['working_files']
                  and actual['history_id'] == facts['history_id_after']
                  and actual['can_undo'] == facts['can_undo'] and actual['can_redo'] == facts['can_redo'],
                  'EDITOR_EDIT_NO_LONGER_CURRENT')
            return facts

    def prepare_effect(self, command_id, digest, kind, *, expected_generation, expected_revision, deadline_ms):
        with self._mutex:
            _need(type(command_id) is str and _ID.fullmatch(command_id) and type(digest) is str and _REV.fullmatch(digest), 'EDITOR_COMMAND')
            _need(kind in ('capture', 'adopt') and type(expected_generation) is int and expected_generation > 0
                  and type(expected_revision) is str and _REV.fullmatch(expected_revision)
                  and type(deadline_ms) is int and int(time.time() * 1000) < deadline_ms <= int(time.time() * 1000) + 30000, 'EDITOR_INTENT')
            _need(not self._stopped and self._pending is None and len(self._intents) < MAX_EFFECTS, 'EDITOR_EFFECT_PENDING_OR_STOPPED')
            value = EditorEffectIntent(uuid.uuid4().hex, command_id, digest, kind, expected_generation, expected_revision, deadline_ms)
            body = {name: getattr(value, name) for name in value.__slots__}
            result = self._exchange('prepare', body)
            self._verify_snapshot(result['before'])
            self._intents[value.intent_id] = (value, canonical_bytes(body), result['before'])
            self._pending = value
            return value

    def _intent(self, value, kind):
        _need(type(value) in (EditorEffectIntent,EditorEditIntent) and value.kind == kind and self._pending is value, 'EDITOR_REGISTERED_INTENT_REQUIRED')
        record = self._intents.get(value.intent_id)
        _need(record is not None and record[0] is value
              and record[1] == canonical_bytes({name: getattr(value, name) for name in value.__slots__}), 'EDITOR_INTENT_CHANGED')
        _need(not self._stopped and int(time.time() * 1000) < value.deadline_ms, 'EDITOR_DEADLINE_OR_STOPPED')
        return record

    def _facts(self, intent, result):
        before, after = result['before'], result['after']
        semantic = self._verify_snapshot(after)
        _need(_semantic(before) == canonical_bytes(self._intents[intent.intent_id][2]['state']), 'EDITOR_EFFECT_SEMANTIC_CONTEXT')
        _need(before['generation'] == intent.expected_generation and before['revision'] == intent.expected_revision
              and before['root_instance_id'] == self._intents[intent.intent_id][2]['root_instance_id'], 'EDITOR_EFFECT_CONTEXT')
        _need(type(result['effect_started_ms']) is int and type(result['effect_completed_ms']) is int
              and result['effect_started_ms'] < intent.deadline_ms
              and result['effect_started_ms'] <= result['effect_completed_ms'] <= int(time.time() * 1000) + 1000, 'EDITOR_EFFECT_TIME')
        return {'schema': 'hh-godot-live-editor-observation-1', 'context_kind': 'live_editor', 'kind': intent.kind,
            'command_id': intent.command_id, 'request_digest': intent.request_digest,
            'editor_session_id': self._session, 'editor_pid': self._pid, 'editor_creation_time': self._creation,
            'project_root_identity': _identity(self._root_identity), 'editor_engine_sha256': GUI_SHA256,
            'source_release_sha256': _sha(canonical_bytes(self._source)), 'generation_before': before['generation'],
            'generation_after': after['generation'], 'root_before': before['root_instance_id'], 'root_after': after['root_instance_id'],
            'effect_started_ms': result['effect_started_ms'], 'effect_completed_ms': result['effect_completed_ms'],
            'semantic_revision': after['revision'], 'semantic_sha256': _sha(semantic), 'semantic_state': after['state'],
            'working_files': after['working_files'], 'history_boundary': result.get('history_boundary', False),
            'can_undo': after['can_undo'], 'can_redo': after['can_redo'], 'public_ack': False}

    def _register(self, receipt, facts, path=None, bundle=None):
        facts['observation_id'] = receipt.observation_id
        raw = canonical_bytes(facts)
        artifact = self.directory / (receipt.observation_id + '.json')
        with artifact.open('xb') as handle:
            handle.write(raw)
        self._records[receipt.observation_id] = (receipt, tuple(getattr(receipt, name) for name in receipt.__slots__), raw, artifact, path, bundle)
        return receipt

    def capture(self, intent):
        with self._mutex:
            self._intent(intent, 'capture')
            self._pending = None  # Single-use before sending a potentially effectful request.
            try:
                result = self._exchange('consume', {'intent_id': intent.intent_id})
                facts = self._facts(intent, result)
                _need(result['before']['revision'] == result['after']['revision'] and facts['generation_before'] == facts['generation_after']
                      and facts['root_before'] == facts['root_after'], 'EDITOR_CAPTURE_CHANGED_LIVE_STATE')
                path = self._scratch / ('capture-' + intent.intent_id + '.tscn')
                scene = self._read_file(path)
                _need(_sha(scene) == result['scene_sha256'], 'EDITOR_CAPTURE_BYTES')
                facts.update(scene_sha256=_sha(scene), scene_size_bytes=len(scene))
                receipt = EditorCaptureReceipt(intent.command_id, intent.request_digest, 'capture-' + uuid.uuid4().hex,
                    self._session, _sha(scene), facts['semantic_revision'])
                return self._register(receipt, facts, path=path)
            except BaseException as error:
                self._held = True
                if not isinstance(error, Exception):
                    error.cleanup_owner = self
                    error.outcome_unknown = True
                    raise
                raise EditorOwnerError('EDITOR_CAPTURE_UNKNOWN', outcome_unknown=True, cleanup_owner=self) from error

    def capture_bytes(self, receipt):
        with self._mutex:
            record = self._receipt(receipt, EditorCaptureReceipt)
            raw = self._read_file(record[4])
            _need(_sha(raw) == receipt.scene_sha256, 'EDITOR_CAPTURE_CHANGED')
            return raw

    def captured_semantic(self, receipt):
        with self._mutex:
            record = self._receipt(receipt, EditorCaptureReceipt)
            return canonical_bytes(parse_json(record[2])['semantic_state'])

    def adopt(self, intent, final_bundle, selection):
        with self._mutex:
            self._intent(intent, 'adopt')
            _need(type(final_bundle) is bundle_codec.CompleteFixtureBundle, 'EDITOR_BUNDLE_TYPE')
            factory.qualify(final_bundle)
            _need(all(final_bundle.files[name] == raw for name, raw in self._files.items() if name != bundle_codec.SCENE_PATH), 'EDITOR_NON_SCENE_CHANGE')
            _need(type(selection) is dict and set(selection) == {'generation', 'identity'} and type(selection['generation']) is int
                  and selection['generation'] > 0 and type(selection['identity']) is str and _REV.fullmatch(selection['identity']), 'EDITOR_SELECTION')
            scene = final_bundle.files[bundle_codec.SCENE_PATH]
            self._pending = None
            try:
                result = self._exchange('consume', {'intent_id': intent.intent_id, 'scene_base64': base64.b64encode(scene).decode(),
                    'scene_sha256': _sha(scene), 'expected_semantic_revision': final_bundle.scene_revision}, timeout=10)
                self._files = dict(final_bundle.files)
                facts = self._facts(intent, result)
                _need(facts['generation_after'] > facts['generation_before'] and facts['root_before'] != facts['root_after']
                      and facts['history_boundary'] is True and facts['can_undo'] is False and facts['can_redo'] is False
                      and facts['semantic_revision'] == final_bundle.scene_revision, 'EDITOR_ADOPTION_READBACK')
                facts.update(project_revision=final_bundle.project_revision, manifest_sha256=_sha(final_bundle.manifest_bytes), selection=dict(selection))
                receipt = EditorAdoptionReceipt(intent.command_id, intent.request_digest, 'adoption-' + uuid.uuid4().hex,
                    self._session, final_bundle.project_revision, facts['semantic_revision'])
                self._bundle = final_bundle
                return self._register(receipt, facts, bundle=final_bundle)
            except BaseException as error:
                self._held = True
                if not isinstance(error, Exception):
                    error.cleanup_owner = self
                    error.outcome_unknown = True
                    raise
                raise EditorOwnerError('EDITOR_ADOPTION_UNKNOWN', outcome_unknown=True, cleanup_owner=self) from error

    def script_observation(self):
        """Read the currently attached script; never load/reload source here."""
        with self._mutex:
            result = self._exchange('script_state', {})
            self._verify_snapshot(result['snapshot'])
            eligible = factory.qualify(self._bundle)
            expected = {'source_sha256': eligible.script.sha256, 'disk_sha256': eligible.script.sha256,
                'uid_source': self._bundle.files[bundle_codec.UID_PATH].decode('ascii'),
                'base_type': 'Node3D', 'is_tool': False, 'has_base_script': False,
                # The pinned editor keeps a non-tool script as a placeholder;
                # standalone Linux validation separately proves instantiation.
                'global_name': '', 'methods': [], 'signals': [], 'constants': [], 'can_instantiate': False,
                'defaults': {row.name: {'type': row.gd_type, 'value': row.value}
                             for row in eligible.script.declarations}}
            comparator._equal(result['script'], expected)
            return result

    @staticmethod
    def _clean_closed(cleanup, pid):
        _need(type(cleanup) is dict and cleanup.get('closed') is True and cleanup.get('held') is False
              and cleanup.get('logs_overflow') is False, 'EDITOR_RETIRE_CLOSE_UNPROVEN')
        actual, job = cleanup.get('actual_process_exit'), cleanup.get('job')
        _need(type(actual) is dict and type(actual.get('pid')) is int and actual['pid'] == pid
              and type(actual.get('exit_code')) is int and actual['exit_code'] == 0
              and type(cleanup.get('wrapper_exit_code')) is int and cleanup['wrapper_exit_code'] == 0,
              'EDITOR_RETIRE_EXIT_UNPROVEN')
        _need(type(job) is dict and all(job.get(k) is True for k in ('configured','assigned','closed','zero_observed'))
              and all(job.get(k) is False for k in ('tainted','handle_retained','close_uncertain','create_uncertain'))
              and type(job.get('active_count')) is int and job['active_count'] == 0
              and job.get('failed_operations') == [] and job.get('native_error') is None,
              'EDITOR_RETIRE_JOB_UNPROVEN')

    def retire_for_replacement(self, command_id, digest, *, retirement_intent_id,
                               expected_snapshot, deadline_ms):
        """Fixed main-thread retire then checked native drain; no successor yet."""
        with self._mutex:
            _need(type(command_id) is str and _ID.fullmatch(command_id) and type(digest) is str
                  and _REV.fullmatch(digest), 'EDITOR_COMMAND')
            _need(type(retirement_intent_id) is str and _ID.fullmatch(retirement_intent_id),
                  'EDITOR_RETIREMENT_INTENT')
            _need(type(expected_snapshot) is dict and type(expected_snapshot.get('generation')) is int
                  and 1 <= expected_snapshot['generation'] < 2147483647, 'EDITOR_GENERATION_OVERFLOW')
            _need(type(deadline_ms) is int and int(time.time()*1000) < deadline_ms
                  <= int(time.time()*1000)+10000, 'EDITOR_RETIRE_DEADLINE')
            _need(not self._stopped and self._pending is None and not self._replacement_reserved,
                  'EDITOR_EFFECT_PENDING_OR_STOPPED')
            identity = self.identity
            self._replacement_reserved = True
            try:
                started_ms = int(time.time()*1000)
                result = self._exchange('retire', {'expected_generation': expected_snapshot['generation'],
                    'expected_revision': expected_snapshot['revision'], 'deadline_ms': deadline_ms,
                    'root_instance_id': expected_snapshot['root_instance_id'],
                    'working_files': expected_snapshot['working_files']})
                before = result['before']
                self._verify_snapshot(before)
                _need(result.get('retired') is True and all(before[k] == expected_snapshot[k] for k in
                    ('generation','revision','root_instance_id','state','working_files')),
                    'EDITOR_RETIRE_CONTEXT_CHANGED')
                cleanup = self.close()
                self._clean_closed(cleanup, identity['pid'])
                for name in ('stdout.txt','stderr.txt'):
                    _need(not re.search(rb'(?i)\b(warning|error|fatal|traceback)\b',
                                        self._read_file(self.directory/name, MAX_LOG)),
                          'EDITOR_RETIRE_NATIVE_DIAGNOSTIC')
                facts = {'schema':'hh-godot-editor-retirement-1','command_id':command_id,
                    'request_digest':digest,'editor':identity,'before':before,'cleanup':cleanup,
                    'retirement_intent_id':retirement_intent_id,
                    'effect_started_ms':started_ms,'effect_completed_ms':int(time.time()*1000),
                    'close_completed_ms':int(time.time()*1000),
                    'next_generation':before['generation']+1,'public_ack':False}
                receipt = EditorRetirementReceipt(command_id,digest,'retired-'+uuid.uuid4().hex,
                    self._session,facts['next_generation'])
                return self._register(receipt,facts)
            except BaseException as error:
                self._held = True
                if not isinstance(error, Exception):
                    error.cleanup_owner = self; error.outcome_unknown = True
                    raise
                raise EditorOwnerError('EDITOR_RETIRE_UNKNOWN',outcome_unknown=True,cleanup_owner=self) from error

    def retirement_observation(self, receipt):
        """Closed-owner proof cannot use _healthy(), which requires a live PID."""
        with self._mutex:
            _need(self._closed and not self._held and type(receipt) is EditorRetirementReceipt,
                  'EDITOR_REGISTERED_RETIREMENT_REQUIRED')
            row = self._records.get(receipt.observation_id)
            _need(row is not None and row[0] is receipt
                  and row[1] == tuple(getattr(receipt,k) for k in receipt.__slots__)
                  and self._read_file(row[3]) == row[2], 'EDITOR_REGISTERED_RETIREMENT_REQUIRED')
            facts = parse_json(row[2])
            self._clean_closed(self._cleanup,self._pid)
            _need(self._cleanup == facts['cleanup']
                  and self._read_file(self.directory/'close.json') == canonical_bytes(facts['cleanup']),
                  'EDITOR_RETIREMENT_CHANGED')
            return facts

    def _reserve_successor(self, retired):
        """One native launch attempt per registered retirement, never implicit retry."""
        with self._mutex:
            facts = self.retirement_observation(retired)
            _need(self._successor_reserved is False, 'EDITOR_SUCCESSOR_ALREADY_ATTEMPTED')
            self._successor_reserved = True
            return facts

    @classmethod
    def open_selected_generation(cls, previous, retired, evidence_parent, final_bundle, *,
                                 editor_binary, selection, semantic_bytes):
        """Trusted coordinator calls only after whole-bundle SELECTED is durable.

        This method proves editor adoption, not selector, grant or journal authority.
        A previous closed owner must remain retained by the coordinator on failure.
        """
        _need(type(previous) is cls, 'EDITOR_PREVIOUS_OWNER_REQUIRED')
        old = previous.retirement_observation(retired)
        _need(type(final_bundle) is bundle_codec.CompleteFixtureBundle, 'EDITOR_BUNDLE_TYPE')
        factory.qualify(final_bundle)
        _need(all(final_bundle.files[name] == raw for name,raw in previous._files.items()
                  if name not in (bundle_codec.SCENE_PATH,bundle_codec.SCRIPT_PATH)),
              'EDITOR_GENERATION_TRUSTED_INPUT_CHANGED')
        _need(type(semantic_bytes) is bytes and canonical_bytes(parse_json(semantic_bytes)) == semantic_bytes
              and final_bundle.scene_revision == 'sha256:'+_sha(semantic_bytes), 'EDITOR_GENERATION_SEMANTICS')
        _need(type(selection) is dict and set(selection) == {'generation','identity'}
              and type(selection['generation']) is int and selection['generation'] > 0
              and type(selection['identity']) is str and _REV.fullmatch(selection['identity']),
              'EDITOR_SELECTION')
        # Claim only after pure preflight, before any constructor/native launch.
        # Keep consumed after success or uncertainty; recovery must reconcile.
        old = previous._reserve_successor(retired)
        successor = None
        try:
            # The registered actual old Job is closed before the constructor launches.
            started_ms = int(time.time()*1000)
            successor = cls(evidence_parent,final_bundle,editor_binary=editor_binary,
                            initial_generation=old['next_generation'])
            readback = successor.script_observation()
            after = readback['snapshot']
            _need(_semantic(after) == semantic_bytes and after['generation'] == old['next_generation']
                  and successor._session != old['editor']['session_id']
                  and int(successor._creation) > int(old['editor']['creation_filetime'])
                  and after['can_undo'] is False and after['can_redo'] is False,
                  'EDITOR_GENERATION_READBACK')
            facts = {'schema':'hh-godot-editor-generation-adoption-1','context_kind':'live_editor',
                'command_id':retired.command_id,'request_digest':retired.request_digest,
                'old_editor':old['editor'],'new_editor':successor.identity,
                'retirement_observation_id':retired.observation_id,
                'retirement_sha256':_sha(canonical_bytes(old)),
                'generation_before':old['before']['generation'],'generation_after':after['generation'],
                'root_before':old['before']['root_instance_id'],'root_after':after['root_instance_id'],
                'semantic_revision':after['revision'],'semantic_state':after['state'],
                'semantic_sha256':_sha(semantic_bytes),'script':readback['script'],
                'project_revision':final_bundle.project_revision,'manifest_sha256':_sha(final_bundle.manifest_bytes),
                'selection':dict(selection),'working_files':after['working_files'],
                'effect_started_ms':started_ms,'effect_completed_ms':int(time.time()*1000),
                'observed_ms':int(time.time()*1000),'history_boundary':True,'public_ack':False}
            receipt = EditorGenerationReceipt(retired.command_id,retired.request_digest,
                'generation-'+uuid.uuid4().hex,successor._session,final_bundle.project_revision,after['revision'])
            successor._generation_predecessor = (previous,retired)
            successor._register(receipt,facts,bundle=final_bundle)
            return successor,receipt
        except BaseException as error:
            if successor is not None:
                try: successor.close()
                except BaseException: error.cleanup_owner = successor
            raise

    def generation_observation(self, receipt, bundle):
        with self._mutex:
            row = self._receipt(receipt,EditorGenerationReceipt)
            _need(type(bundle) is bundle_codec.CompleteFixtureBundle and bundle == row[5],
                  'EDITOR_GENERATION_BUNDLE')
            facts = parse_json(row[2]); before,retired = self._generation_predecessor
            _need(_sha(canonical_bytes(before.retirement_observation(retired))) == facts['retirement_sha256'],
                  'EDITOR_GENERATION_RETIREMENT_CHANGED')
            current = self.script_observation(); actual = current['snapshot']
            _need(self.identity == facts['new_editor'] and actual['revision'] == facts['semantic_revision']
                  and actual['generation'] == facts['generation_after']
                  and actual['root_instance_id'] == facts['root_after']
                  and actual['working_files'] == facts['working_files']
                  and current['script'] == facts['script'], 'EDITOR_GENERATION_NO_LONGER_CURRENT')
            return facts

    def _receipt(self, receipt, kind=None):
        self._healthy()
        _need(type(receipt) in (EditorCaptureReceipt, EditorAdoptionReceipt, EditorGenerationReceipt, EditorEditReceipt) and (kind is None or type(receipt) is kind), 'EDITOR_RECEIPT_TYPE')
        record = self._records.get(receipt.observation_id)
        _need(record is not None and record[0] is receipt and record[1] == tuple(getattr(receipt, name) for name in receipt.__slots__)
              and self._read_file(record[3]) == record[2], 'EDITOR_REGISTERED_RECEIPT_REQUIRED')
        return record

    def observation(self, receipt, bundle=None):
        if type(receipt) is EditorEditReceipt:
            _need(bundle is None, 'EDITOR_EDIT_BUNDLE_ARGUMENT')
            return self.edit_observation(receipt)
        if type(receipt) is EditorGenerationReceipt:
            return self.generation_observation(receipt,bundle)
        with self._mutex:
            record = self._receipt(receipt)
            if type(receipt) is EditorCaptureReceipt:
                self.capture_bytes(receipt)
                _need(bundle is None, 'EDITOR_CAPTURE_BUNDLE_ARGUMENT')
            else:
                _need(bundle is record[5] or (type(bundle) is bundle_codec.CompleteFixtureBundle and bundle == record[5]), 'EDITOR_ADOPTION_BUNDLE')
                actual = self.inspect()
                facts = parse_json(record[2])
                _need(actual['revision'] == receipt.semantic_revision
                      and actual['generation'] == facts['generation_after']
                      and actual['root_instance_id'] == facts['root_after']
                      and actual['working_files'] == facts['working_files'], 'EDITOR_ADOPTION_NO_LONGER_CURRENT')
            return parse_json(record[2])

    def stop(self):
        with self._mutex:
            if self._closed:
                return
            self._stopped = True
            self._pending = None
            if not self._held:
                self._exchange('stop', {})

    def close(self):
        with self._mutex:
            if self._closed:
                return self._cleanup
            self._stopped = True
            if self._connection is not None and self._process is not None and self._process.poll() is None:
                try:
                    self._sequence += 1
                    self._connection.sendall(json.dumps({'sequence': self._sequence, 'editor_session_id': self._session,
                        'kind': 'close', 'body': {}}).encode() + b'\n')
                    self._process.wait(timeout=3)
                except (OSError, subprocess.TimeoutExpired):
                    pass  # Checked Job cleanup below owns any remaining process.
            if self._job is None and self._process is not None:
                self._job = cli_job.owner_for_process(self._process)
            if self._job is not None:
                self._job.close()
            elif self._process is not None and self._process.poll() is None:
                self._process.kill()  # Gated helper cannot yet have launched Godot.
            if self._process is not None:
                self._process.wait(timeout=3)
            for thread in self._threads:
                thread.join(2)
                _need(not thread.is_alive(), 'EDITOR_LOG_DRAIN_UNKNOWN')
            for sock in (self._connection, self._listener):
                if sock is not None:
                    sock.close()
            if self._target_handle is not None:
                _need(self._kernel.CloseHandle(self._target_handle), 'EDITOR_PROCESS_HANDLE_CLOSE')
                self._target_handle = None
            if self._api is not None:
                self._api.close_owned()
            self._closed = True
            exit_path = getattr(self, 'directory', Path()) / 'process-exit.json'
            actual = json.loads(exit_path.read_bytes()) if exit_path.is_file() else None
            self._cleanup = {'actual_process_exit': actual, 'wrapper_exit_code': self._process.returncode if self._process else None,
                'job': self._job.snapshot() if self._job else None, 'logs_overflow': self._overflow.is_set(),
                'closed': True, 'held': self._held, 'public_ack': False}
            if hasattr(self, 'directory'):
                (self.directory / 'close.json').write_bytes(canonical_bytes(self._cleanup))
            return self._cleanup

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
