"""Lookup-only Godot queue recovery; no native engine or effect replay."""
from __future__ import annotations

import importlib.util
import hashlib
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))

spec = importlib.util.spec_from_file_location(
    'gt07_native_godot_recovery_owner', STUDIO / 'godot-addon/publication_owner.py')
owner_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = owner_module
spec.loader.exec_module(owner_module)

from studio.host.jobs.dispatch_policy import PendingJob, QueueLimits
from studio.host.jobs.durable_broker import Fence, JobRecord, Reservation
from studio.host.jobs.native_dispatch import (GodotOwnerBinding, NativeDispatchError,
                                               NativeOwnerDispatcher, _BINDINGS)
from studio.host.jobs.queue_owner import QueueOwner
from studio.protocol.core import Request, canonical_bytes


class NativeGodotRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.owner = object.__new__(owner_module.GodotPublicationOwner)
        self.owner._lock = threading.RLock()
        self.owner._attachment_lock = threading.RLock()
        self.owner._work = threading.Lock()
        self.owner._closed = False
        self.owner._held = False
        self.owner._transport = None
        self.owner._queue_dispatcher = None
        self.owner._source_closure_sha256 = 'a' * 64
        self.owner._source_release = ('release', 'b' * 64)
        self.owner.storage_id = 'storage.fixture'
        self.owner._editor = SimpleNamespace(identity={'session_id': 'editor.old', 'pid': 101})
        self.owner._journal = object()
        self.owner.sessions = SimpleNamespace(
            _check_grant=lambda *_args, **_kwargs: None,
            check=lambda *_args, **_kwargs: None)
        self.grant = SimpleNamespace(session_id='session.fixture')
        self.owner._auth = lambda *_args, **_kwargs: self.grant
        self.owner._same_release = lambda: None
        target = {'stable_id': 'root'}
        payload = {}
        self.request = Request('command.recover', 'project.fixture', 'scene.node.update',
                               'lease.fixture', 1, 'sha256:' + 'c' * 64,
                               target, payload, 'sha256:' + hashlib.sha256(
                                   canonical_bytes(payload)).hexdigest(), 30_000)
        self.binding = self._binding()
        job_id = 'native-' + hashlib.sha256(canonical_bytes([
            self.binding.resource, self.binding.project_id, self.binding.command_id])).hexdigest()
        self.job = PendingJob(job_id, 'project.fixture', 'session.fixture',
                              1, 60_000, (self.binding.resource,), ())
        self.fence = Fence('stream.fixture', 1)
        self.row = JobRecord(self.job, self.binding.command_sha256, 'RESERVED', self.fence)
        self.queue = object.__new__(QueueOwner)
        self.queue._lifecycle = threading.RLock()
        self.queue._dispatcher = None
        self.queue.broker = SimpleNamespace(
            limits=QueueLimits(), lookup=lambda _key: self.row)
        self.dispatch = NativeOwnerDispatcher(self.queue)
        self.addCleanup(self._cleanup)

    def _binding(self):
        values = {
            'owner': self.owner,
            'body': canonical_bytes(self.request.as_dict()),
            'authorization': 'Bearer fixture',
            'grant': self.grant,
            'resource': 'godot-storage.fixture',
            'session_id': 'session.fixture',
            'project_id': 'project.fixture',
            'command_id': self.request.command_id,
            'command_sha256': hashlib.sha256(
                canonical_bytes(self.request.as_dict())).hexdigest(),
            'catalog_digest': 'sha256:' + 'e' * 64,
            'source_closure_sha256': self.owner._source_closure_sha256,
            'source_release': self.owner._source_release,
            'editor_identity': canonical_bytes(self.owner._editor.identity),
            'storage_id': self.owner.storage_id,
            'journal': self.owner._journal,
            'sessions': self.owner.sessions,
        }
        binding = object.__new__(GodotOwnerBinding)
        for name, value in values.items():
            object.__setattr__(binding, name, value)
        with __import__('studio.host.jobs.native_dispatch', fromlist=['_BIND']).__dict__['_BIND']:
            _BINDINGS[binding] = tuple(values[name] for name in binding.__dataclass_fields__)
        return binding

    def _cleanup(self):
        if not self.dispatch._closed:
            self.dispatch.close()

    def test_recovery_attaches_only_existing_reservation(self):
        self.dispatch.register_recovery(self.binding)
        key = self.dispatch._job_id(self.binding)
        self.assertIn(key, self.dispatch._recovery_only)
        self.assertIs(self.dispatch._bindings[key], self.binding)
        with self.assertRaisesRegex(NativeDispatchError, 'NATIVE_RECOVERY_LOOKUP_ONLY'):
            self.dispatch.enqueue(self.binding)
        reservation = Reservation(self.job, self.binding.command_sha256, self.fence)
        with self.assertRaisesRegex(NativeDispatchError, 'NATIVE_RECOVERY_LOOKUP_ONLY'):
            self.dispatch.advance(reservation)

    def test_recovery_rejects_queued_or_mismatched_reservation(self):
        self.row = JobRecord(self.job, self.binding.command_sha256, 'QUEUED', self.fence)
        with self.assertRaisesRegex(NativeDispatchError, 'NATIVE_RECOVERY_RESERVATION_REQUIRED'):
            self.dispatch.register_recovery(self.binding)
        self.row = JobRecord(self.job, 'f' * 64, 'RESERVED', self.fence)
        with self.assertRaisesRegex(NativeDispatchError, 'NATIVE_RECOVERY_RESERVATION_REQUIRED'):
            self.dispatch.register_recovery(self.binding)

    def test_binding_for_recovery_requires_exact_durable_fence(self):
        self.dispatch.register_recovery(self.binding)
        good = Reservation(self.job, self.binding.command_sha256, self.fence)
        self.assertIs(self.dispatch._binding_for(good), self.binding)
        bad = Reservation(self.job, self.binding.command_sha256, Fence('stream.fixture', 2))
        with self.assertRaisesRegex(NativeDispatchError, 'NATIVE_RESERVATION_REQUIRED'):
            self.dispatch._binding_for(bad)


if __name__ == '__main__':
    unittest.main()
