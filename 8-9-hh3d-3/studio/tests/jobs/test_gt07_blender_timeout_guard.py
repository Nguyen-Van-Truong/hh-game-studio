"""Focused guard for bounded Blender publication preparation waits."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from studio.host.blender.publication_owner import BlenderPublicationOwner


class _Host:
    def __init__(self):
        self.calls = []

    def execute(self, command, **kwargs):
        self.calls.append((command, kwargs))
        return {"state": "COMPLETED"}


class GT07BlenderTimeoutGuardTests(unittest.TestCase):
    def setUp(self):
        self.owner = object.__new__(BlenderPublicationOwner)
        self.owner.host = _Host()
        self.owner._state = {"config": {"publication_profile": "export.publish"}}
        self.lease = SimpleNamespace(fencing_epoch=2, expires_ms=9_000_000_000)

    def test_export_prepare_uses_bounded_extended_wait(self):
        with patch("studio.host.blender.publication_owner.epoch_ms", return_value=1_000_000):
            self.owner._native("prepare", "export.prepare", self.lease,
                               deadline_ms=1_009_000)
        self.assertEqual(self.owner.host.calls[0][1]["timeout"], 9.0)
        self.assertEqual(self.owner.host.calls[0][1]["deadline_ms"], 1_009_000)

    def test_other_native_operations_keep_default_wait(self):
        with patch("studio.host.blender.publication_owner.epoch_ms", return_value=1_000_000):
            self.owner._native("inspect", "scene.inspect", self.lease,
                               deadline_ms=1_009_000)
        self.assertNotIn("timeout", self.owner.host.calls[0][1])


if __name__ == "__main__":
    unittest.main()
