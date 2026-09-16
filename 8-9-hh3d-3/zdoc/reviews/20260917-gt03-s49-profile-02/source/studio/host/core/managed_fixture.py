"""Local owner for one protected inert fixture and its durable restart custody.

No registry paths, handles, arbitrary filenames or recovery switches are wire
inputs. This lifecycle owner is not yet a public endpoint or engine adapter.
Callers bound blocking I/O with the owned-process runner. Constructor failures
retain cleanup ownership and preserve provisioned data for reconciliation.
"""
from __future__ import annotations

from pathlib import Path
import threading
import uuid

from .custody import WitnessCustody, CustodyError, identity_from
from .custody_registry import RegistryCustody
from .fixture_selector import FixtureSelector, FileFixtureReleaseConsumer, _name, _revisions, _clock
from .limits import SafetyViolation, SafePathResolver
from .private_events import PrivateEventLog
from .private_store import PrivateBlobStore
from .safe_replace import ProtectedFileRoot


class ManagedFixtureError(SafetyViolation):
    def __init__(self, code, *, outcome_unknown=False, cleanup_owner=None):
        self.outcome_unknown = outcome_unknown
        self.cleanup_owner = cleanup_owner
        super().__init__(code)


class ManagedFixtureOwner:
    """One registry record + three exclusively owned private roots.

    New roots persist PROVISIONING before creation. Existing roots open only
    from protected custody. Startup never executes a pending effect or clears
    STOP. Only an exact committed file can regain admission for fresh work.
    """
    @classmethod
    def create(cls, parent, *, project_id, initial_revisions):
        _name(project_id)
        _revisions(initial_revisions)
        SafePathResolver(parent)  # validate original spelling before provisioning
        owner = cls()
        try:
            RegistryCustody.provision_base()
            owner.storage_id, owner.project_id = uuid.uuid4().hex, project_id
            owner.registry = RegistryCustody.create(owner.storage_id)
            owner.custody = WitnessCustody(owner.registry, storage_id=owner.storage_id,
                                          project_id=project_id, create=True)
            # File namespace provisioning/barriers happen before peer stores
            # retain their read-shared ancestors. Every directory is minted by
            # a checked native primitive; never mkdir through an unpinned path.
            owner.parent = Path(parent)
            owner.files = ProtectedFileRoot.create(owner.parent)
            owner.store = PrivateBlobStore.create(owner.parent)
            owner.log = PrivateEventLog.create(owner.parent)
            owner.custody.activate(file_root=owner.files.root, file_identity=owner.files.root_identity,
                                  blob_root=owner.store.root, blob_identity=owner.store.root_identity,
                                  event_root=owner.log.root, event_binding=owner.log.binding())
            owner.log.bind_custody(owner.custody)
            owner.consumer = FileFixtureReleaseConsumer(project_id, owner.files)
            owner.selector = FixtureSelector(owner.log, owner.store, owner.consumer,
                                            project_id=project_id, initial_revisions=initial_revisions)
            return owner
        except BaseException as exc:
            owner._failed_init(exc)

    @classmethod
    def reopen(cls, storage_id, *, project_id, now_ms):
        _name(project_id)
        _clock(now_ms)
        owner = cls()
        try:
            owner.storage_id, owner.project_id = storage_id, project_id
            owner.registry = RegistryCustody.reopen(storage_id)
            owner.custody = WitnessCustody(owner.registry, storage_id=storage_id, project_id=project_id)
            record = owner.custody.record
            if record['phase'] != 'READY':
                raise CustodyError('CUSTODY_INCOMPLETE_PROVISIONING')
            # The file guard serializes all registry updates for READY roots.
            owner.files = ProtectedFileRoot.reopen_readonly(record['files']['path'], identity_from(record['files']['identity']))
            owner.custody.confirm_current()
            owner.store = PrivateBlobStore.reopen(record['blobs']['path'], identity_from(record['blobs']['identity']))
            owner.log = PrivateEventLog.reopen(record['events']['path'], owner.custody.binding)
            owner.consumer = FileFixtureReleaseConsumer(project_id, owner.files)
            owner.selector = FixtureSelector(owner.log, owner.store, owner.consumer, project_id=project_id)
            # The reducer checked the whole chain. Complete suffixes beyond the
            # last durable witness are held effects, never permission to replay.
            owner.custody.persist_binding(owner.log.binding())
            owner.log.bind_custody(owner.custody)
            state = owner.selector.snapshot()
            if not state['stopped'] and state['pending_command'] is None and state['selected'] is not None:
                # Renew the recorded logical owner with a fresh epoch under
                # the reacquired native guard. No old authentication session
                # or lease ID survives. The short recovery lease expires before
                # a newly authenticated client acquires its own ordinary lease.
                previous = owner.selector._state['lease']
                logical_owner = previous['owner'] if previous else 'supervisor-recovery'
                owner.selector.lease(logical_owner, now_ms=now_ms, ttl_ms=1)
                owner.selector.load_committed(now_ms=now_ms)
                # Exact terminal selection + actual file barrier + fresh durable
                # fence authorize only new commands, never prior command replay.
                owner.files._rearm_verified_snapshot(owner.consumer._version)
            return owner
        except BaseException as exc:
            owner._failed_init(exc)

    def __init__(self):
        self._lifecycle_lock = threading.RLock()
        self._service = None
        self.registry = self.custody = self.files = self.store = self.log = None
        self.consumer = self.selector = None
        self._cleanup_errors = []

    def _failed_init(self, exc):
        # Components can fail before assignment yet retain real native handles.
        cleanup = getattr(exc, 'cleanup_owner', None) or getattr(exc, 'cleanup_api', None)
        if cleanup is not None:
            self._cleanup_errors.append(cleanup)
        try:
            self.close()
        except BaseException:
            pass
        raise ManagedFixtureError('MANAGED_FIXTURE_RECONCILIATION_REQUIRED', outcome_unknown=True,
                                  cleanup_owner=self) from exc

    def close(self):
        with self._lifecycle_lock:
            if self._service is not None or getattr(self.selector, '_pipe_broker', None) is not None:
                raise ManagedFixtureError('MANAGED_FIXTURE_SERVICE_ACTIVE', cleanup_owner=self)
            self._close_components()

    def _close_components(self):
        failures = []
        # Close downstream logical owners before the resources they reference.
        for key in ('selector', 'consumer', 'log', 'store', 'files', 'registry'):
            component = getattr(self, key)
            if component is None:
                continue
            try:
                component.close()
            except BaseException:
                failures.append(component)
                # Preserve the complete ownership chain for the next retry.
                break
            else:
                setattr(self, key, None)
        retained = []
        for component in self._cleanup_errors:
            try:
                if hasattr(component, 'close_owned'):
                    component.close_owned()
                else:
                    component.close()
            except BaseException:
                retained.append(component)
        self._cleanup_errors = retained
        if failures or retained:
            raise ManagedFixtureError('MANAGED_FIXTURE_CLOSE_UNCERTAIN', outcome_unknown=True, cleanup_owner=self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
