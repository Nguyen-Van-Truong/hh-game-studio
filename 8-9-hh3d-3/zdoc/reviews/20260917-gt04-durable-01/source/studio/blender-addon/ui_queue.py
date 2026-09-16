"""Bounded main-thread queue; no transport, threads, bpy, or public ACK."""
from collections import deque
import importlib.util
import json
from pathlib import Path
import time

_path = Path(__file__).with_name("adapter.py")
_spec = importlib.util.spec_from_file_location("_gt04_ui_base", _path)
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
c = base.contract
SCHEMA = "HH-BLENDER-UI-COMMAND-1"
MAX_PENDING = 8
MAX_REQUESTS = 64


def parse(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= c.MAX_BYTES:
        raise c.Rejected("BOUNDED_BYTES_REQUIRED")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=c._pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(c.Rejected("NONFINITE_JSON")))
        c.exact(value, ("schema", "command_id", "operation", "expected_revision", "expected_context", "payload"), "command")
        if value["schema"] != SCHEMA:
            raise c.Rejected("UI_SCHEMA_REQUIRED")
        check = dict(value, schema=c.SCHEMA)
        if value["operation"] in ("history.undo", "history.redo"):
            c.exact(value["payload"], (), "history")
            # Reuse the exact revision/context/identifier validation, without
            # extending the background adapter's admitted operations.
            check.update(operation="mesh.create_box", payload={"object_id": "history", "size": [1, 1, 1]})
        elif value["operation"] in ("checkpoint.save", "export.prepare"):
            c.exact(value["payload"], ("slot",), "checkpoint")
            slots = ("export",) if value["operation"] == "export.prepare" else ("checkpoint", "fixture")
            if value["payload"]["slot"] not in slots:
                raise c.Rejected("FIXED_SAVE_SLOT_REQUIRED")
            check.update(operation="mesh.create_box", payload={"object_id": "save", "size": [1, 1, 1]})
        c.validate(check)
        return json.loads(c.canonical(value))
    except (ValueError, UnicodeError, TypeError, RecursionError, OverflowError) as exc:
        raise c.Rejected("INVALID_UI_COMMAND") from exc


class CommandQueue:
    """Caller is a trusted main-thread poller. Entries/receipts live for this owner only."""
    def __init__(self, dispatch, *, clock=time.monotonic, lease_clock=lambda:time.time_ns()//1_000_000):
        base.main_thread()
        self._dispatch, self._clock = dispatch, clock
        self._pending, self._rows = deque(), {}
        self._stopped = False
        self._lease=None;self._lease_clock=lease_clock

    def arm_lease(self,lease):
        base.main_thread()
        c.exact(lease,('fencing_epoch','expires_ms'),'lease')
        if (type(lease['fencing_epoch']) is not int or not 1<=lease['fencing_epoch']<2**53
            or type(lease['expires_ms']) is not int or not self._lease_clock()<lease['expires_ms']<2**53):
            raise c.Rejected('INVALID_WRITER_LEASE')
        if self._stopped:raise c.Rejected('STOPPED')
        if self._lease is not None:
            if lease==self._lease:return dict(self._lease)
            if lease['fencing_epoch']<=self._lease['fencing_epoch']:raise c.Rejected('STALE_WRITER_FENCE')
        self._lease=dict(lease)
        return dict(self._lease)

    def _check_lease(self,lease):
        if lease is not None:
            c.exact(lease,('fencing_epoch','expires_ms'),'lease')
            if any(type(lease[name]) is not int for name in lease):raise c.Rejected('INVALID_WRITER_LEASE')
        if self._lease is None:
            if lease is not None:raise c.Rejected('WRITER_LEASE_NOT_ARMED')
        elif lease!=self._lease or self._lease_clock()>=self._lease['expires_ms']:
            raise c.Rejected('WRITER_FENCED_OR_EXPIRED')

    def submit(self, raw, *, ttl_ms=1000, lease=None):
        base.main_thread()
        command = parse(raw)
        if type(ttl_ms) is not int or not 1 <= ttl_ms <= 5000:
            raise c.Rejected("DEADLINE_LIMIT")
        key, digest = command["command_id"], c.digest(command)
        if key in self._rows:
            if self._rows[key]["command_digest"] != digest:
                raise c.Rejected("COMMAND_CONFLICT")
            return self.result(key)
        if self._stopped:
            raise c.Rejected("STOPPED")
        self._check_lease(lease)
        if len(self._pending) >= MAX_PENDING or len(self._rows) >= MAX_REQUESTS:
            raise c.Rejected("QUEUE_CAPACITY")
        self._rows[key] = {"command_id": key, "command_digest": digest, "state": "PENDING", "public_ack": False}
        self._pending.append((key, command, self._clock() + ttl_ms / 1000, dict(lease) if lease is not None else None))
        return self.result(key)

    def result(self, key):
        base.main_thread()
        return json.loads(c.canonical(self._rows[c.identifier(key)]))

    def tick(self):
        base.main_thread()
        if not self._pending or self._stopped:
            return
        key, command, deadline, lease = self._pending.popleft()
        row = self._rows[key]
        if self._clock() >= deadline:
            row.update(state="EXPIRED", reason="QUEUE_DEADLINE")
            return
        try:
            self._check_lease(lease)
            row.update(result=self._dispatch(command), state="COMPLETED")
        except c.Rejected as exc:
            row.update(state="REJECTED", reason=str(exc))
        except BaseException as exc:
            row.update(state="HELD", reason=type(exc).__name__)
            self.stop()
            raise

    def stop(self):
        base.main_thread()
        self._stopped = True
        while self._pending:
            key, _, _, _ = self._pending.popleft()
            self._rows[key].update(state="CANCELLED", reason="STOPPED")
