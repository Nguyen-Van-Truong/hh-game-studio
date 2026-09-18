"""Local fixed-fixture reviewer. Credentials never leave this process.

The prepared owner has a 120-second lifetime. Closing the window requests Stop
and verifies owned resources drain. A fresh explicitly prepared run is needed
for another Play; reconnect cannot resume a stopped run.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import secrets
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from studio.host.replay.backend import PreparedPlay, BackendError
from studio.host.replay.service import ReplayService
from studio.host.replay.transport import ReplayTransport
from studio.reviewer.client import ReplayClient

HELD_REVIEWERS = []


class PreparedReviewer:
    """Trusted local lifecycle, with retained ownership on any cleanup failure."""
    def __init__(self):
        self.backend = self.service = self.transport = self.client = None
        self.closed = False

    @classmethod
    def prepare(cls, run_id):
        if HELD_REVIEWERS:
            raise RuntimeError('REVIEWER_CLEANUP_HELD')
        owner = cls()
        try:
            try:
                owner.backend = PreparedPlay.prepare(run_id)
            except BackendError as error:
                owner.backend = error.cleanup_owner
                raise
            owner.service = ReplayService(owner.backend)
            credential = owner.service.sessions.issue(ttl_ms=115_000)
            owner.transport = ReplayTransport(owner.service)
            owner.transport.start()
            owner.client = ReplayClient(port=owner.transport.port,
                control_port=owner.transport.control_port, stop_port=owner.transport.stop_port,
                credential=credential, project_id=owner.service.project_id, binding=owner.service.binding)
            return owner
        except BaseException:
            owner.close()
            raise

    def close(self):
        if self.closed:
            return True
        try:
            if self.service is not None:
                self.service.close()
            elif self.backend is not None:
                self.backend.close()
            if self.transport is not None:
                self.transport.close()
        except BaseException:
            if self not in HELD_REVIEWERS:
                HELD_REVIEWERS.append(self)
            raise
        self.closed = True
        if self in HELD_REVIEWERS:
            HELD_REVIEWERS.remove(self)
        return True


def main(run_id):
    import tkinter as tk
    from studio.reviewer.app import ReviewerWindow
    owner = PreparedReviewer.prepare(run_id)
    root = None
    try:
        root = tk.Tk()
        ReviewerWindow(root, owner.client, on_close=owner.close)
        root.mainloop()
    finally:
        owner.close()
        if root is not None:
            try:
                root.destroy()
            except tk.TclError:
                pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', default='gt06-review-' + time.strftime('%Y%m%d%H%M%S') + '-' + secrets.token_hex(3))
    main(parser.parse_args().run_id)
