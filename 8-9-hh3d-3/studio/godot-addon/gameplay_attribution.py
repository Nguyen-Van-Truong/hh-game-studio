"""Authenticated, bounded transcript for the trusted gameplay supervisor.

The driver commits to an ephemeral key before launching any candidate, protects
its memory/FDs with non-dumpability, and reveals the key only after every child
has been reaped and its pipes drained. This detects writes via PID 1's outer
stdout too. It does not authenticate a candidate's gameplay or dependency claims.
The codec alone is not native evidence: the pinned launcher must enforce these
lifecycle preconditions. No public capability is enabled by this module.
"""
from __future__ import annotations

import base64
import ctypes
import hashlib
import hmac
import json
import os
import re
import secrets
import sys

SCHEMA = 'hh-gameplay-attribution-1'
MAX_WIRE_BYTES = 262_144  # Framing overhead counts toward the existing cap.
MAX_FRAMES = 2048
MAX_CHUNK_BYTES = 8192
DOMAIN = b'HH-GAMEPLAY-PARENT-RECORD-1\0'
_HEX = re.compile(r'[0-9a-f]{64}\Z')
_ID = re.compile(r'[a-z][a-z0-9.-]{0,95}\Z')
GUARD_FACTS = {
    'no_new_privileges': 1, 'seccomp_mode': 2,
    'fork_errno': 1, 'socket_ipv4_errno': 1,
    'socket_ipv6_errno': 1, 'socket_unix_errno': 1,
}


class AttributionError(ValueError):
    pass


def need(condition, code):
    if not condition:
        raise AttributionError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                      separators=(',', ':')).encode('ascii')


def _integer(value):
    return type(value) is int


def _context(value):
    need(type(value) is dict and set(value) == {
        'run_id', 'source_closure_sha256', 'input_manifest_sha256'}, 'ATTRIBUTION_CONTEXT')
    need(type(value['run_id']) is str and _ID.fullmatch(value['run_id']), 'ATTRIBUTION_CONTEXT')
    need(all(type(value[k]) is str and _HEX.fullmatch(value[k])
             for k in ('source_closure_sha256', 'input_manifest_sha256')), 'ATTRIBUTION_CONTEXT')


def protect_parent():
    """Run in the trusted Linux driver BEFORE creating the key or any child."""
    need(sys.platform == 'linux' and os.getuid() == 65532, 'ATTRIBUTION_PLATFORM')
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.restype = ctypes.c_int
    need(libc.prctl(4, 0, 0, 0, 0) == 0 and libc.prctl(3, 0, 0, 0, 0) == 0,
         'ATTRIBUTION_PARENT_DUMPABLE')


class Recorder:
    """Driver-side writer; lifecycle calls are made only by the trusted parent.

    The caller must invoke protect_parent first. Child descriptors must be
    close_fds except a private pre-exec guard pipe, closed before Godot exec.
    No key is put into arguments, environment, files or candidate descriptors.
    """
    def __init__(self, stream, context):
        _context(context)
        self._stream = stream
        self._key = secrets.token_bytes(32)
        self._sequence = 0
        self._bytes = 0
        self._active = None
        self._children = 0
        self._done = False
        self._write({'schema': SCHEMA, 'context': context,
                     'key_commitment': hashlib.sha256(self._key).hexdigest()})

    def _write(self, value):
        raw = canonical(value) + b'\n'
        need(self._bytes + len(raw) <= MAX_WIRE_BYTES, 'ATTRIBUTION_WIRE_CAP')
        need(self._stream.write(raw) == len(raw), 'ATTRIBUTION_SHORT_WRITE')
        self._stream.flush()
        self._bytes += len(raw)

    def _record(self, event):
        need(not self._done and self._sequence < MAX_FRAMES, 'ATTRIBUTION_CLOSED_OR_CAP')
        body = {'seq': self._sequence, 'event': event}
        mac = hmac.new(self._key, DOMAIN + canonical(body), hashlib.sha256).hexdigest()
        self._write({**body, 'mac': mac})
        self._sequence += 1

    def begin_child(self, phase, script, pid):
        need(self._active is None and _integer(pid) and pid > 1, 'ATTRIBUTION_CHILD_ACTIVE')
        self._record({'kind': 'begin', 'phase': phase, 'script': script, 'pid': pid})
        self._active = pid
        self._children += 1

    def guard(self, pid, facts):
        need(self._active == pid, 'ATTRIBUTION_CHILD_ID')
        self._record({'kind': 'guard', 'pid': pid, 'facts': facts})

    def output(self, pid, channel, raw):
        need(self._active == pid and channel in ('stdout', 'stderr')
             and type(raw) is bytes and 0 < len(raw) <= MAX_CHUNK_BYTES, 'ATTRIBUTION_OUTPUT')
        self._record({'kind': 'output', 'pid': pid, 'channel': channel,
                      'base64': base64.b64encode(raw).decode('ascii')})

    def end_child(self, pid, returncode, *, reaped, pipe_eof):
        need(self._active == pid and _integer(returncode) and -255 <= returncode <= 255
             and reaped is True and type(pipe_eof) is list and len(pipe_eof) == 3
             and all(value is True for value in pipe_eof), 'ATTRIBUTION_CHILD_UNCERTAIN')
        self._record({'kind': 'exit', 'pid': pid, 'returncode': returncode,
                      'reaped': True, 'pipe_eof': pipe_eof})
        self._active = None

    def finish(self, returncode):
        need(self._active is None and not self._done and _integer(returncode) and returncode in (0, 45),
             'ATTRIBUTION_UNCERTAIN_TERMINAL')
        self._record({'kind': 'terminal', 'returncode': returncode, 'children': self._children})
        # Never call this from an unconditional finally: active/uncertain child
        # cleanup must withhold the reveal even if the outer driver is exiting.
        self._write({'reveal': self._key.hex()})
        self._done = True


def _pairs(pairs):
    value = {}
    for key, child in pairs:
        need(key not in value, 'ATTRIBUTION_DUPLICATE_KEY')
        value[key] = child
    return value


def _json(raw):
    try:
        value = json.loads(raw, object_pairs_hook=_pairs)
        need(type(value) is dict and canonical(value) == raw, 'ATTRIBUTION_NONCANONICAL')
        return value
    except (ValueError, TypeError, RecursionError, UnicodeError) as error:
        raise AttributionError('ATTRIBUTION_JSON') from error


def verify(wire, *, context, scripts):
    """Verify the retained wire and derive facts; never trusts a result flag."""
    _context(context)
    need(type(wire) is bytes and 0 < len(wire) <= MAX_WIRE_BYTES
         and wire.endswith(b'\n'), 'ATTRIBUTION_WIRE')
    lines = wire[:-1].split(b'\n')
    need(4 <= len(lines) <= MAX_FRAMES + 2, 'ATTRIBUTION_FRAME_COUNT')
    rows = [_json(line) for line in lines]
    header, reveal = rows[0], rows[-1]
    need(set(header) == {'schema', 'context', 'key_commitment'} and header['schema'] == SCHEMA
         and header['context'] == context, 'ATTRIBUTION_HEADER')
    need(set(reveal) == {'reveal'} and type(reveal['reveal']) is str
         and _HEX.fullmatch(reveal['reveal']), 'ATTRIBUTION_REVEAL')
    key = bytes.fromhex(reveal['reveal'])
    need(type(header['key_commitment']) is str and _HEX.fullmatch(header['key_commitment']) and hmac.compare_digest(
        hashlib.sha256(key).hexdigest(), header['key_commitment']), 'ATTRIBUTION_COMMITMENT')
    need(type(scripts) is list and 1 <= len(scripts) <= 64
         and all(type(s) is str and re.fullmatch(r'scripts/[A-Za-z0-9_./-]+\.gd', s)
                 and all(p not in ('', '.', '..') for p in s.split('/')) for s in scripts)
         and scripts[0] == 'scripts/fixture_actor.gd'
         and scripts[1:] == sorted(scripts[1:]) and len(set(scripts)) == len(scripts),
         'ATTRIBUTION_SCRIPT_INVENTORY')
    expected = [('parse', script) for script in scripts] + [('import', None), ('play', None)]
    active, completed, pids, terminal = None, [], set(), None
    logs = {'stdout': bytearray(), 'stderr': bytearray()}
    for index, row in enumerate(rows[1:-1]):
        need(set(row) == {'seq', 'event', 'mac'} and _integer(row['seq']) and row['seq'] == index
             and type(row['event']) is dict and type(row['mac']) is str
             and _HEX.fullmatch(row['mac']), 'ATTRIBUTION_FRAME')
        body = {'seq': index, 'event': row['event']}
        need(hmac.compare_digest(row['mac'], hmac.new(key, DOMAIN + canonical(body),
             hashlib.sha256).hexdigest()), 'ATTRIBUTION_MAC')
        event = row['event']
        kind = event.get('kind')
        need(terminal is None, 'ATTRIBUTION_AFTER_TERMINAL')
        if kind == 'begin':
            need(set(event) == {'kind', 'phase', 'script', 'pid'} and active is None
                 and len(completed) < len(expected) and (not completed or completed[-1]['returncode'] == 0)
                 and (event['phase'], event['script']) == expected[len(completed)]
                 and _integer(event['pid']) and event['pid'] > 1 and event['pid'] not in pids,
                 'ATTRIBUTION_PHASE_ORDER')
            pids.add(event['pid'])
            active = {k: event[k] for k in ('phase', 'script', 'pid')}
            active['guard'] = None
        elif kind in ('guard', 'output', 'exit'):
            need(active is not None and _integer(event.get('pid'))
                 and event['pid'] == active['pid'], 'ATTRIBUTION_CHILD_ID')
            if kind == 'guard':
                need(set(event) == {'kind', 'pid', 'facts'} and active['guard'] is None
                     and type(event['facts']) is dict and event['facts'] == GUARD_FACTS
                     and all(_integer(v) for v in event['facts'].values()), 'ATTRIBUTION_GUARD')
                active['guard'] = event['facts']
            elif kind == 'output':
                need(set(event) == {'kind', 'pid', 'channel', 'base64'}
                     and type(event['channel']) is str and event['channel'] in logs
                     and type(event['base64']) is str
                     and len(event['base64']) <= ((MAX_CHUNK_BYTES + 2) // 3) * 4,
                     'ATTRIBUTION_OUTPUT')
                try:
                    raw = base64.b64decode(event['base64'], validate=True)
                except (ValueError, TypeError) as error:
                    raise AttributionError('ATTRIBUTION_BASE64') from error
                need(0 < len(raw) <= MAX_CHUNK_BYTES
                     and base64.b64encode(raw).decode('ascii') == event['base64'], 'ATTRIBUTION_BASE64')
                logs[event['channel']].extend(raw)
            else:
                need(set(event) == {'kind', 'pid', 'returncode', 'reaped', 'pipe_eof'}
                     and _integer(event['returncode']) and -255 <= event['returncode'] <= 255
                     and event['reaped'] is True and type(event['pipe_eof']) is list
                     and len(event['pipe_eof']) == 3 and all(v is True for v in event['pipe_eof'])
                     and (event['returncode'] != 0 or active['guard'] is not None), 'ATTRIBUTION_EXIT')
                completed.append({**active, 'returncode': event['returncode']})
                active = None
        elif kind == 'terminal':
            need(set(event) == {'kind', 'returncode', 'children'} and active is None
                 and _integer(event['children']) and event['children'] == len(completed)
                 and completed and _integer(event['returncode']), 'ATTRIBUTION_TERMINAL')
            success = len(completed) == len(expected) and all(r['returncode'] == 0 for r in completed)
            need(event['returncode'] == (0 if success else 45)
                 and (success or completed[-1]['returncode'] != 0), 'ATTRIBUTION_TERMINAL_STATUS')
            terminal = event
        else:
            raise AttributionError('ATTRIBUTION_EVENT_KIND')
    need(terminal is not None and active is None, 'ATTRIBUTION_INCOMPLETE')
    return {'schema': SCHEMA, 'context': context, 'attribution_verified': True,
            'scope': ['phase_wait', 'trusted_preexec_os_probes'],
            'phase_results': completed, 'driver_returncode': terminal['returncode'],
            'wire_sha256': hashlib.sha256(wire).hexdigest(),
            'child_stdout': bytes(logs['stdout']), 'child_stderr': bytes(logs['stderr']),
            'child_claims_authenticated': False, 'dependency_closure_verified': False,
            'public_ack': False, 'authority': 0}
