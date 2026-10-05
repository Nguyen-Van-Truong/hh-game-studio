"""Trusted local custody for a durable queue; no client-selected storage paths.

Reuse the existing three-root Windows custody contract rather than invent a
second restart trust anchor. Files/blobs supply its native identity/guard pair;
this owner does not publish assets there. Incomplete provisioning is preserved.
"""
from __future__ import annotations

from pathlib import Path
import threading
import uuid

from ..core.custody import WitnessCustody, identity_from
from ..core.custody_registry import RegistryCustody
from ..core.limits import SafePathResolver, SafetyViolation
from ..core.private_events import PrivateEventLog
from ..core.private_store import PrivateBlobStore
from ..core.safe_replace import ProtectedFileRoot
from .dispatch_policy import QueueLimits
from .durable_broker import DurableBroker


class QueueOwnerError(SafetyViolation):
    def __init__(self, code, *, cleanup_owner=None):
        self.cleanup_owner = cleanup_owner
        self.outcome_unknown = cleanup_owner is not None
        super().__init__(code)


class QueueOwner:
    """Supervisor owns lifetime. Reopen does not execute or release old jobs."""
    PROJECT = 'studio.scheduler'

    def __init__(self):
        self._lifecycle = threading.RLock()
        self.registry = self.custody = self.files = self.store = self.log = None
        self.broker = self._dispatcher = None
        self._cleanup = []

    @classmethod
    def create(cls, parent, *, limits=QueueLimits()):
        if cls is not QueueOwner or type(limits) is not QueueLimits:
            raise QueueOwnerError('QUEUE_TRUSTED_OWNER_REQUIRED')
        SafePathResolver(parent)
        owner = cls()
        try:
            RegistryCustody.provision_base()
            owner.storage_id = uuid.uuid4().hex
            owner.registry = RegistryCustody.create(owner.storage_id)
            owner.custody = WitnessCustody(owner.registry, storage_id=owner.storage_id,
                                          project_id=cls.PROJECT, create=True)
            owner.files = ProtectedFileRoot.create(Path(parent))
            owner.store = PrivateBlobStore.create(Path(parent))
            owner.log = PrivateEventLog.create(Path(parent))
            owner.custody.activate(file_root=owner.files.root, file_identity=owner.files.root_identity,
                                  blob_root=owner.store.root, blob_identity=owner.store.root_identity,
                                  event_root=owner.log.root, event_binding=owner.log.binding())
            owner.log.bind_custody(owner.custody)
            owner.broker = DurableBroker(owner.log, limits=limits)
            return owner
        except BaseException as exc:
            owner._failed(exc)

    @classmethod
    def reopen(cls, storage_id, *, limits=QueueLimits()):
        if cls is not QueueOwner or type(limits) is not QueueLimits:
            raise QueueOwnerError('QUEUE_TRUSTED_OWNER_REQUIRED')
        owner = cls()
        try:
            owner.storage_id = storage_id
            owner.registry = RegistryCustody.reopen(storage_id)
            owner.custody = WitnessCustody(owner.registry, storage_id=storage_id, project_id=cls.PROJECT)
            record = owner.custody.record
            if record['phase'] != 'READY':
                raise QueueOwnerError('QUEUE_INCOMPLETE_PROVISIONING')
            # Acquire the native exclusive writer guard before trusting custody.
            owner.files = ProtectedFileRoot.reopen_readonly(record['files']['path'], identity_from(record['files']['identity']))
            owner.custody.confirm_current()
            owner.store = PrivateBlobStore.reopen(record['blobs']['path'], identity_from(record['blobs']['identity']))
            owner.log = PrivateEventLog.reopen(record['events']['path'], owner.custody.binding)
            # A suffix without its durable witness is uncertain. Preserve it;
            # never advance custody here just to make startup pass.
            owner.log.bind_custody(owner.custody)
            owner.broker = DurableBroker(owner.log, limits=limits)
            return owner
        except BaseException as exc:
            owner._failed(exc)

    def _failed(self, exc):
        cleanup = getattr(exc, 'cleanup_owner', None) or getattr(exc, 'cleanup_api', None)
        if cleanup is not None and cleanup not in (self.registry, self.files, self.store, self.log, self.broker):
            self._cleanup.append(cleanup)
        try:
            self.close()
        except BaseException:
            pass
        raise QueueOwnerError('QUEUE_RECONCILIATION_REQUIRED', cleanup_owner=self) from exc

    def close(self):
        with self._lifecycle:
            if self._dispatcher is not None:
                raise QueueOwnerError('QUEUE_DISPATCHER_ACTIVE', cleanup_owner=self)
            for key in ('broker', 'log', 'store', 'files', 'registry'):
                component = getattr(self, key)
                if component is None:
                    continue
                try:
                    component.close()
                except BaseException as exc:
                    raise QueueOwnerError('QUEUE_CLOSE_UNCERTAIN', cleanup_owner=self) from exc
                setattr(self, key, None)
            while self._cleanup:
                component = self._cleanup[0]
                try:
                    (component.close_owned if hasattr(component, 'close_owned') else component.close)()
                except BaseException as exc:
                    raise QueueOwnerError('QUEUE_CLOSE_UNCERTAIN', cleanup_owner=self) from exc
                self._cleanup.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
