"""Bounded Blender -> gameplay-source publication coordinator.

This module is deliberately separate from ``NativeOwnerDispatcher``.  The
fixed Godot editor owner is not the gameplay-source owner, so widening that
binding would weaken its contract.  The adapter only coordinates a previously
verified Blender publication with one gameplay-source publish, and records a
queue result after the Godot readback postcondition has been checked.

It is an authority-zero diagnostic seam.  It does not enable a public profile,
does not publish an external ACK, and never replays native work during
recovery.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

from ...protocol.core import canonical_bytes
from ...host.core.transport import epoch_ms
from ...host.jobs.durable_broker import JobRequest, OwnerResult, Reservation


class CrossAppPublicationError(RuntimeError):
    pass


def _need(value: object, code: str) -> None:
    if not value:
        raise CrossAppPublicationError(code)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class ProducerReceipt:
    """Exact, already verified Blender terminal evidence used as a dependency."""

    job_id: str
    project_id: str
    session_id: str
    command_sha256: str
    receipt_sha256: str
    artifact_sha256: str
    artifact_size: int
    manifest_sha256: str
    terminal: str = "COMMITTED"

    def validate(self) -> None:
        for value in (self.job_id, self.project_id, self.session_id):
            _need(type(value) is str and value and " " not in value,
                  "CROSS_APP_PRODUCER_ID")
        for value in (self.command_sha256, self.receipt_sha256,
                      self.artifact_sha256, self.manifest_sha256):
            _need(type(value) is str and len(value) == 64
                  and all(char in "0123456789abcdef" for char in value),
                  "CROSS_APP_PRODUCER_HASH")
        _need(self.terminal == "COMMITTED", "CROSS_APP_PRODUCER_NOT_TERMINAL")
        _need(type(self.artifact_size) is int and self.artifact_size > 0,
              "CROSS_APP_PRODUCER_SIZE")


@dataclass(frozen=True, slots=True)
class ConsumerReceipt:
    job_id: str
    producer_job_id: str
    command_sha256: str
    receipt_sha256: str
    selected_revision: str
    artifact_sha256: str
    readback_ack: bool
    public_ack: bool


class CrossAppPublicationCoordinator:
    """Queue a consumer after Blender is terminal, then publish once."""

    def __init__(self, queue_owner, *, project_id="project.gameplay",
                 session_id="session.gameplay"):
        _need(getattr(queue_owner, "broker", None) is not None,
              "CROSS_APP_QUEUE_REQUIRED")
        self.queue = queue_owner
        self.project_id = project_id
        self.session_id = session_id
        self._consumer = None
        self._reservation = None
        self._calls = 0

    @staticmethod
    def verify_artifact(receipt: ProducerReceipt, artifact: bytes,
                        manifest: bytes) -> None:
        receipt.validate()
        _need(type(artifact) is bytes and len(artifact) == receipt.artifact_size
              and _sha(artifact) == receipt.artifact_sha256,
              "CROSS_APP_ARTIFACT_CHANGED")
        _need(type(manifest) is bytes and _sha(manifest) == receipt.manifest_sha256,
              "CROSS_APP_MANIFEST_CHANGED")

    def admit_producer(self, receipt: ProducerReceipt, *, now_ms=None) -> None:
        """Bind a verified Blender terminal receipt as the dependency root."""
        receipt.validate()
        now_ms = epoch_ms() if now_ms is None else now_ms
        request = JobRequest(receipt.job_id, receipt.project_id,
                             receipt.session_id, now_ms + 120_000, ("blender",),
                             (), receipt.command_sha256)
        row = self.queue.broker.enqueue(request, now_ms=now_ms)
        _need(row.state == "QUEUED", "CROSS_APP_PRODUCER_ADMISSION")
        reservation = self.queue.broker.reserve_next(now_ms=now_ms)
        _need(reservation is not None and reservation.job.job_id == receipt.job_id,
              "CROSS_APP_PRODUCER_RESERVATION")
        self.queue.broker.record_owner_result(
            reservation, OwnerResult("COMMITTED", receipt.command_sha256,
                                     receipt.receipt_sha256))
        row = self.queue.broker.lookup(receipt.job_id)
        _need(row is not None and row.state == "COMMITTED",
              "CROSS_APP_PRODUCER_COMMIT")

    def enqueue_consumer(self, *, job_id: str, producer: ProducerReceipt,
                         command_sha256: str, now_ms=None):
        producer.validate()
        now_ms = epoch_ms() if now_ms is None else now_ms
        request = JobRequest(job_id, self.project_id, self.session_id,
                             now_ms + 120_000, ("godot-gameplay",),
                             (producer.job_id,), command_sha256)
        row = self.queue.broker.enqueue(request, now_ms=now_ms)
        reservation = self.queue.broker.reserve_next(now_ms=now_ms)
        _need(reservation is not None and reservation.job.job_id == job_id,
              "CROSS_APP_CONSUMER_RESERVATION")
        self._consumer = (job_id, producer)
        self._reservation = reservation
        return reservation

    def recover_consumer(self, *, job_id: str, producer: ProducerReceipt,
                         command_sha256: str | None = None):
        """Bind a durable consumer reservation after a coordinator restart.

        Reopening the queue must retain the reservation and its fence.  This
        method only reattaches that exact row for lookup/reconciliation; it
        never reserves a new job or invokes the gameplay owner.
        """
        producer.validate()
        _need(type(job_id) is str and job_id, "CROSS_APP_RECOVERY_JOB")
        if command_sha256 is not None:
            _need(type(command_sha256) is str and len(command_sha256) == 64
                  and all(char in "0123456789abcdef" for char in command_sha256),
                  "CROSS_APP_RECOVERY_COMMAND")
        row = self.queue.broker.lookup(job_id)
        _need(row is not None and row.state in ("RESERVED", "UNKNOWN"),
              "CROSS_APP_RECOVERY_RESERVATION")
        _need(row.job.project_id == self.project_id
              and row.job.session_id == self.session_id
              and row.job.resources == ("godot-gameplay",)
              and row.job.dependencies == (producer.job_id,),
              "CROSS_APP_RECOVERY_BINDING")
        _need(command_sha256 is None or row.command_sha256 == command_sha256,
              "CROSS_APP_RECOVERY_COMMAND")
        producer_row = self.queue.broker.lookup(producer.job_id)
        _need(producer_row is not None and producer_row.state == "COMMITTED"
              and producer_row.command_sha256 == producer.command_sha256
              and producer_row.receipt_sha256 == producer.receipt_sha256,
              "CROSS_APP_RECOVERY_PRODUCER")
        reservations = tuple(item for item in self.queue.broker.snapshot().reservations
                             if item.job.job_id == job_id)
        _need(len(reservations) == 1 and reservations[0].recovered,
              "CROSS_APP_RECOVERY_RESERVATION")
        reservation = reservations[0]
        _need(reservation.job == row.job and reservation.command_sha256 == row.command_sha256
              and reservation.fence == row.fence,
              "CROSS_APP_RECOVERY_BINDING")
        self._consumer = (job_id, producer)
        self._reservation = reservation
        return reservation

    def publish_once(self, reservation: Reservation, owner, request: dict,
                     grant, lease, *, artifact: bytes, manifest: bytes,
                     producer: ProducerReceipt, deadline_ms: int,
                     expected_generation: int) -> ConsumerReceipt:
        """Run one owner publish and record only after postcondition readback."""
        _need(reservation is self._reservation, "CROSS_APP_RESERVATION")
        self.verify_artifact(producer, artifact, manifest)
        _need(type(request) is dict and request.get("source_files", {}).get(
            "assets/avatar.glb") == artifact, "CROSS_APP_SOURCE_BINDING")
        _need(self._calls == 0, "CROSS_APP_REPLAY")
        self._calls += 1
        ack = owner.publish(request, grant=grant, lease=lease,
                            deadline_ms=deadline_ms)
        _need(type(ack) is dict and ack.get("status") == "READBACK_ACK"
              and ack.get("readback_ack") is True
              and ack.get("public_ack") is False,
              "CROSS_APP_READBACK_ACK")
        observed = owner.inspect()
        _need(type(expected_generation) is int and expected_generation > 0
              and type(observed) is dict and observed.get("generation") ==
              expected_generation + 1,
              "CROSS_APP_CURRENT_READBACK")
        current = (owner._root / "CURRENT").read_bytes()
        journal = (owner._root / "journal.jsonl").read_bytes()
        _need(current and journal
              and observed.get("files", {}).get("assets/avatar.glb") ==
              producer.artifact_sha256,
              "CROSS_APP_DURABLE_STATE")
        raw = canonical_bytes(ack)
        result = self.queue.broker.record_owner_result(
            reservation, OwnerResult("COMMITTED", reservation.command_sha256,
                                     _sha(raw)))
        _need(result.state == "COMMITTED", "CROSS_APP_QUEUE_ACK")
        return ConsumerReceipt(reservation.job.job_id, producer.job_id,
                               reservation.command_sha256, _sha(raw),
                               observed["project_revision"],
                               producer.artifact_sha256, True, False)

    def reconcile_lookup_only(self, reservation: Reservation, *, ack: dict,
                              observed: dict, producer: ProducerReceipt) -> ConsumerReceipt:
        """Reconcile an uncertain consumer without invoking owner.publish."""
        _need(reservation is self._reservation and getattr(reservation, "recovered", False),
              "CROSS_APP_RECOVERY_RESERVATION")
        _need(reservation.job.job_id == (self._consumer or (None,))[0],
              "CROSS_APP_RECOVERY_RESERVATION")
        _need((self._consumer or (None, None))[1] == producer
              and reservation.job.dependencies == (producer.job_id,),
              "CROSS_APP_RECOVERY_PRODUCER")
        _need(self._calls == 0, "CROSS_APP_RECOVERY_REPLAY")
        producer.validate()
        producer_row = self.queue.broker.lookup(producer.job_id)
        _need(producer_row is not None and producer_row.state == "COMMITTED"
              and producer_row.command_sha256 == producer.command_sha256
              and producer_row.receipt_sha256 == producer.receipt_sha256,
              "CROSS_APP_RECOVERY_PRODUCER")
        _need(type(ack) is dict and ack.get("status") == "READBACK_ACK"
              and ack.get("readback_ack") is True and ack.get("public_ack") is False,
              "CROSS_APP_RECOVERY_ACK")
        _need(type(observed) is dict and observed.get("project_revision"),
              "CROSS_APP_RECOVERY_READBACK")
        _need(observed.get("files", {}).get("assets/avatar.glb") ==
              producer.artifact_sha256, "CROSS_APP_RECOVERY_ARTIFACT")
        _need(ack.get("project_revision") == observed.get("project_revision")
              and ack.get("selected_revision") == observed.get("project_revision")
              and ack.get("source_sha256") == observed.get("source_sha256")
              and ack.get("readback_sha256") == _sha(canonical_bytes(observed)),
              "CROSS_APP_RECOVERY_READBACK")
        raw = canonical_bytes(ack)
        result = self.queue.broker.record_owner_result(
            reservation, OwnerResult("COMMITTED", reservation.command_sha256,
                                     _sha(raw)))
        _need(result.state == "COMMITTED", "CROSS_APP_RECOVERY_COMMIT")
        return ConsumerReceipt(reservation.job.job_id, producer.job_id,
                               reservation.command_sha256, _sha(raw),
                               observed["project_revision"],
                               producer.artifact_sha256, True, False)


__all__ = ["ProducerReceipt", "ConsumerReceipt", "CrossAppPublicationCoordinator",
           "CrossAppPublicationError"]
