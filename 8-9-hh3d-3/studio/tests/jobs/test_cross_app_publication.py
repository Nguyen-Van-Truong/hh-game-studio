from __future__ import annotations

import hashlib
import unittest
from types import SimpleNamespace

from .cross_app_publication import (CrossAppPublicationCoordinator,
                                    CrossAppPublicationError, ProducerReceipt)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class _Broker:
    def __init__(self):
        self.rows = {}
        self.calls = []

    def enqueue(self, request, *, now_ms):
        self.calls.append(("enqueue", request, now_ms))
        row = SimpleNamespace(state="QUEUED", job=request)
        self.rows[request.job_id] = row
        return row

    def reserve_next(self, *, now_ms):
        for row in self.rows.values():
            if row.state == "QUEUED":
                row.state = "RESERVED"
                reservation = SimpleNamespace(job=row.job,
                    command_sha256=row.job.command_sha256,
                    fence=SimpleNamespace(generation=1))
                row.reservation = reservation
                self.calls.append(("reserve", reservation, now_ms))
                return reservation
        return None

    def record_owner_result(self, reservation, result):
        row = self.rows[reservation.job.job_id]
        row.state = result.outcome
        self.calls.append(("result", reservation, result))
        return row

    def lookup(self, job_id):
        return self.rows.get(job_id)


class _Queue:
    def __init__(self):
        self.broker = _Broker()


class _Owner:
    def __init__(self, artifact):
        self.calls = 0
        class _Root:
            def __truediv__(self, name):
                return SimpleNamespace(
                    read_bytes=lambda: b"selector" if name == "CURRENT" else b"journal")
        self._root = _Root()
        self._state = {"generation": 2, "project_revision": "sha256:" + "b" * 64,
                       "files": {"assets/avatar.glb": _sha(artifact)}}
        self._artifact = artifact

    def publish(self, request, *, grant, lease, deadline_ms):
        self.calls += 1
        return {"status": "READBACK_ACK", "readback_ack": True,
                "public_ack": False, "command_id": request["command_id"]}

    def inspect(self):
        return dict(self._state)


def _producer(artifact, manifest):
    return ProducerReceipt("producer-1", "blender.project", "blender.session",
        "a" * 64, "b" * 64, _sha(artifact), len(artifact), _sha(manifest))


class CrossAppPublicationTests(unittest.TestCase):
    def setUp(self):
        self.artifact = b"glb-bytes"
        self.manifest = b"manifest"
        self.producer = _producer(self.artifact, self.manifest)
        self.adapter = CrossAppPublicationCoordinator(_Queue())
        self.adapter.admit_producer(self.producer, now_ms=100)
        self.reservation = self.adapter.enqueue_consumer(
            job_id="consumer-1", producer=self.producer,
            command_sha256="c" * 64, now_ms=101)

    def test_publish_records_only_after_readback(self):
        owner = _Owner(self.artifact)
        request = {"command_id": "consumer-1",
                   "source_files": {"assets/avatar.glb": self.artifact}}
        receipt = self.adapter.publish_once(self.reservation, owner, request,
            None, None, artifact=self.artifact, manifest=self.manifest,
            producer=self.producer, deadline_ms=200, expected_generation=1)
        self.assertEqual(owner.calls, 1)
        self.assertTrue(receipt.readback_ack)
        self.assertFalse(receipt.public_ack)
        self.assertEqual(self.adapter.queue.broker.lookup("consumer-1").state,
                         "COMMITTED")

    def test_artifact_drift_fails_before_publish(self):
        owner = _Owner(self.artifact)
        request = {"command_id": "consumer-1",
                   "source_files": {"assets/avatar.glb": b"other"}}
        with self.assertRaises(CrossAppPublicationError):
            self.adapter.publish_once(self.reservation, owner, request,
                None, None, artifact=b"other", manifest=self.manifest,
                producer=self.producer, deadline_ms=200, expected_generation=1)
        self.assertEqual(owner.calls, 0)
        self.assertEqual(self.adapter.queue.broker.lookup("consumer-1").state,
                         "RESERVED")

    def test_reconcile_does_not_replay(self):
        # A fresh coordinator represents a recovered supervisor. It receives
        # only the durable reservation and exact owner lookup response.
        recovered = CrossAppPublicationCoordinator(self.adapter.queue)
        recovered._consumer = ("consumer-1", self.producer)
        recovered._reservation = self.reservation
        receipt = recovered.reconcile_lookup_only(self.reservation,
            ack={"status": "READBACK_ACK", "public_ack": False},
            observed={"project_revision": "sha256:" + "b" * 64,
                      "files": {"assets/avatar.glb": self.producer.artifact_sha256}},
            producer=self.producer)
        self.assertTrue(receipt.readback_ack)
        self.assertEqual(self.adapter.queue.broker.lookup("consumer-1").state,
                         "COMMITTED")


if __name__ == "__main__":
    unittest.main()
