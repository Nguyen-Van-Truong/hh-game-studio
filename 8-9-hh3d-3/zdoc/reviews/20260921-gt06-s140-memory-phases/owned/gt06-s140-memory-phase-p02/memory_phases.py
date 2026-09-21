"""Bounded S140 phase-memory diagnostic for stock GT06 campaign.

The coordinator owns launching. This module only supplies runtime wrappers and a
finally-only report writer; source/profile/native files and campaign gates remain
unchanged.
"""
from __future__ import annotations

from collections import deque
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable, Iterator, Mapping

SCHEMA_ID = "HH-GT06-S140-PHASE-MEMORY-1"
MAX_ROWS = 200
ALLOWED_PREFIXES = frozenset((1, 7))
PHASE_ORDER = (
    "command_completed", "command_released_gc", "native_batch_marker", "native_validated_before_editor",
    "editor_sample", "ack_received", "assembly_before", "assembly_after",
    "screen_sample", "assembly_released_gc",
)
PHASE_LABELS = frozenset(PHASE_ORDER) | {"screen_rejected"}
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}\Z")


class BoundedPhaseStop(RuntimeError):
    code = "S140_BOUNDED_PREFIX"


@dataclass(frozen=True)
class _PrivateCounters:
    private_commit_bytes: int | None
    working_set_bytes: int | None
    page_fault_count: int | None
    allocated_blocks: int | None
    unavailable_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "private_commit_bytes": self.private_commit_bytes,
            "working_set_bytes": self.working_set_bytes,
            "page_fault_count": self.page_fault_count,
            "allocated_blocks": self.allocated_blocks,
            "unavailable_reason": self.unavailable_reason,
        }


class _PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    """Local Windows EX layout; stock ProcessProbe is not modified."""
    _fields_ = [
        ("cb", ctypes.c_uint32), ("page_fault_count", ctypes.c_uint32),
        ("peak_working_set", ctypes.c_size_t), ("working_set", ctypes.c_size_t),
        ("quota_peak_paged_pool", ctypes.c_size_t), ("quota_paged_pool", ctypes.c_size_t),
        ("quota_peak_nonpaged_pool", ctypes.c_size_t), ("quota_nonpaged_pool", ctypes.c_size_t),
        ("pagefile_usage", ctypes.c_size_t), ("peak_pagefile_usage", ctypes.c_size_t),
        ("private_usage", ctypes.c_size_t),
    ]


def _memory_api():
    if os.name != "nt":
        return None
    from ctypes import wintypes as w
    # A separate ctypes function object leaves stock ProcessProbe argtypes intact.
    api = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
    api.argtypes = [w.HANDLE, ctypes.POINTER(_PROCESS_MEMORY_COUNTERS_EX), w.DWORD]
    api.restype = w.BOOL
    return api


_MEMORY_API = _memory_api()


def _int_or_none(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _allocated_blocks() -> int | None:
    getter = getattr(sys, "getallocatedblocks", None)
    if getter is None:
        return None
    try:
        return int(getter())
    except BaseException:
        return None


def _read_private_counters(probe: Any) -> _PrivateCounters:
    """Read an existing retained handle; unavailable is never fabricated zero."""
    optional = getattr(probe, "sample_private_memory", None)
    if callable(optional):
        try:
            value = optional()
            if isinstance(value, Mapping):
                return _PrivateCounters(
                    _int_or_none(value.get("private_commit_bytes")),
                    _int_or_none(value.get("working_set_bytes")),
                    _int_or_none(value.get("page_fault_count")),
                    _int_or_none(value.get("allocated_blocks")),
                    value.get("unavailable_reason"),
                )
        except BaseException as error:
            return _PrivateCounters(None, None, None, None, type(error).__name__)
    if probe is None or getattr(probe, "handle", None) is None:
        return _PrivateCounters(None, None, None, None, "retained_handle_unavailable")
    if os.name != "nt":
        return _PrivateCounters(None, None, None, None, "windows_api_unavailable")
    try:
        counters = _PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(counters)
        if not _MEMORY_API(probe.handle, ctypes.byref(counters), counters.cb):
            return _PrivateCounters(None, None, None, None, "GetProcessMemoryInfo_failed")
        return _PrivateCounters(
            int(counters.private_usage), int(counters.working_set),
            int(counters.page_fault_count),
            _allocated_blocks() if probe.pid == os.getpid() else None, None,
        )
    except BaseException as error:
        return _PrivateCounters(None, None, None, None, type(error).__name__)


def _identity(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    pid, started = value.get("pid"), value.get("process_start")
    if type(pid) is int and type(started) is str:
        return {"pid": pid, "process_start": started}
    return None


def _probe_identity(probe: Any) -> dict[str, Any] | None:
    return _identity({"pid": getattr(probe, "pid", None),
                      "process_start": getattr(probe, "process_start", None)})


class PhaseMemoryRecorder:
    """Bounded tuple collection; conversion to JSON happens only at persist."""
    def __init__(self, run_id: str, prefix: int, *, max_rows: int = MAX_ROWS,
                 clock: Callable[[], int] | None = None):
        if type(run_id) is not str or not _RUN_ID.fullmatch(run_id):
            raise ValueError("run_id must be a bounded identifier")
        if type(prefix) is not int or prefix not in ALLOWED_PREFIXES:
            raise ValueError("prefix must be exactly 1 or 7")
        if type(max_rows) is not int or not 1 <= max_rows <= MAX_ROWS:
            raise ValueError("max_rows must be in 1..200")
        self.run_id, self.prefix, self.max_rows = run_id, prefix, max_rows
        self._clock = clock or (lambda: time.perf_counter_ns() // 1000)
        self._rows: deque[tuple[Any, ...]] = deque(maxlen=max_rows)
        self._seen = self._dropped = 0
        self._current_index: int | None = None
        self.last_screened_index: int | None = None
        self._host_probe = self._editor_probe = None
        self._identities: dict[str, dict[str, Any] | None] = {"host": None, "editor": None}

    @property
    def rows(self) -> tuple[tuple[Any, ...], ...]:
        return tuple(self._rows)

    @property
    def row_count(self) -> int:
        return len(self._rows)

    @property
    def dropped_rows(self) -> int:
        return self._dropped

    @property
    def current_index(self) -> int | None:
        return self._current_index

    def bind_host(self, probe: Any = None, identity: Mapping[str, Any] | None = None) -> None:
        self._bind("host", probe, identity)
        self._host_probe = probe

    def bind_editor(self, probe: Any = None, identity: Mapping[str, Any] | None = None) -> None:
        self._bind("editor", probe, identity)
        self._editor_probe = probe

    def _bind(self, role, probe, identity):
        observed, declared = _probe_identity(probe), _identity(identity)
        if declared is not None and observed != declared:
            raise RuntimeError("S140_PROBE_IDENTITY_MISMATCH")
        current = declared or observed
        previous = self._identities[role]
        if previous is not None and previous != current:
            raise RuntimeError("S140_PROBE_IDENTITY_CHANGED")
        self._identities[role] = current

    def record(self, phase: str, index: int | None = None, *,
               host_probe: Any = None, editor_probe: Any = None) -> None:
        if phase not in PHASE_LABELS:
            raise ValueError(f"unknown phase label: {phase}")
        if index is not None and (type(index) is not int or index < 0):
            raise ValueError("index must be a non-negative integer")
        if index is not None:
            self._current_index = index
        if host_probe is not None:
            self.bind_host(host_probe)
        if editor_probe is not None:
            self.bind_editor(editor_probe)
        started = self._clock()
        host = _read_private_counters(self._host_probe)
        editor = _read_private_counters(self._editor_probe) if self._editor_probe is not None else None
        ended = self._clock()
        row = (
            self._seen, self._current_index, phase, started, max(0, ended - started),
            host.as_dict(), None if editor is None else editor.as_dict(),
            self._identities["host"], self._identities["editor"],
        )
        self._seen += 1
        if len(self._rows) == self.max_rows:
            self._dropped += 1
        self._rows.append(row)

    def _json_rows(self) -> list[dict[str, Any]]:
        rows = []
        for sequence, index, phase, mono_us, overhead_us, host, editor, host_id, editor_id in self._rows:
            rows.append({
                "sequence": sequence, "index": index, "phase": phase,
                "mono_us": mono_us, "measurement_overhead_us": overhead_us,
                "host_memory": host, "editor_memory": editor,
                "host_identity": host_id, "editor_identity": editor_id,
            })
        return rows

    def report(self, *, status: str = "DIAGNOSTIC",
               error_code: str | None = None) -> dict[str, Any]:
        return {
            "schema_id": SCHEMA_ID, "schema_version": "1.0.0",
            "authority": 0, "formal_acceptance": False, "diagnostic_only": True,
            "run_id": self.run_id, "prefix_batches": self.prefix,
            "max_rows": self.max_rows, "rows_seen": self._seen,
            "rows_dropped": self._dropped, "row_count": self.row_count,
            "phase_order": list(PHASE_ORDER), "identities": dict(self._identities),
            "status": status, "error_code": error_code, "rows": self._json_rows(),
        }

    def persist(self, path: str | os.PathLike[str], *, status: str = "DIAGNOSTIC",
                error_code: str | None = None) -> dict[str, Any]:
        """Only caller's finally block should call this method."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        value = self.report(status=status, error_code=error_code)
        temporary = target.with_name(target.name + ".tmp")
        raw = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
        with temporary.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(target)
        return value


class _GCProxy:
    """Campaign-local proxy: the process-global gc module is untouched."""
    def __init__(self, recorder: PhaseMemoryRecorder, original: Any):
        self._recorder, self._original = recorder, original

    def collect(self, *args: Any, **kwargs: Any) -> int:
        result = self._original.collect(*args, **kwargs)
        recorder = self._recorder
        after_screen = recorder.current_index is not None and recorder.last_screened_index == recorder.current_index
        recorder.record("assembly_released_gc" if after_screen else "command_released_gc")
        if after_screen and recorder.current_index >= recorder.prefix - 1:
            raise BoundedPhaseStop(recorder.run_id)
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._original, name)


class _Patch:
    def __init__(self, owner: Any, name: str, value: Any):
        self.owner, self.name, self.original = owner, name, getattr(owner, name)
        self.local = name in vars(owner)
        setattr(owner, name, value)

    def restore(self) -> None:
        if self.local:
            setattr(self.owner, self.name, self.original)
        else:
            delattr(self.owner, self.name)


@contextmanager
def install_phase_memory_wrappers(campaign: Any, recorder: PhaseMemoryRecorder) -> Iterator[PhaseMemoryRecorder]:
    """Wrap stock hooks and restore all attributes on exit.

    screen_sample invokes the original gate first. The original end-of-batch GC
    then raises BoundedPhaseStop; original gate exceptions propagate unchanged.
    """
    had_active = hasattr(campaign, "_s140_phase_memory_active")
    prior_active = getattr(campaign, "_s140_phase_memory_active", None)
    if prior_active:
        raise RuntimeError("S140 wrappers already installed")
    setattr(campaign, "_s140_phase_memory_active", True)
    patches: list[_Patch] = []
    try:
        producer_cls, native_log_cls = campaign.CampaignProducer, campaign.NativeLog
        original_run_batch = producer_cls.run_batch
        original_wait = native_log_cls.wait
        original_sample_editor = campaign.sample_editor
        original_assemble = campaign.assemble_sample
        original_screen = campaign.screen_sample
        original_gc = campaign.gc

        def run_batch(self: Any, index: int, *args: Any, **kwargs: Any) -> Any:
            result = original_run_batch(self, index, *args, **kwargs)
            recorder.bind_host(getattr(getattr(self, "observer", None), "probe", None),
                               getattr(self, "identity", None))
            recorder.record("command_completed", index)
            return result

        def wait(self: Any, suffix: str, index: int, timeout: Any, *args: Any, **kwargs: Any) -> Any:
            result = original_wait(self, suffix, index, timeout, *args, **kwargs)
            if suffix == "BATCH":
                recorder.record("native_batch_marker", index)
            elif suffix == "ACK":
                recorder.record("ack_received", index)
            return result

        def sample_editor(probe: Any, *args: Any, **kwargs: Any) -> Any:
            index = recorder.current_index
            recorder.bind_editor(probe)
            # The stock caller parsed native output before invoking this hook.
            recorder.record("native_validated_before_editor", index)
            result = original_sample_editor(probe, *args, **kwargs)
            recorder.record("editor_sample", index)
            return result

        def assemble_sample(*args: Any, **kwargs: Any) -> Any:
            index = kwargs.get("index", recorder.current_index)
            recorder.record("assembly_before", index)
            result = original_assemble(*args, **kwargs)
            recorder.record("assembly_after", index)
            return result

        def screen_sample(sample: Mapping[str, Any], baseline: Any, *args: Any, **kwargs: Any) -> Any:
            index = sample.get("index", recorder.current_index) if isinstance(sample, Mapping) else recorder.current_index
            try:
                result = original_screen(sample, baseline, *args, **kwargs)
            except BaseException:
                recorder.record("screen_rejected", index)
                raise
            recorder.record("screen_sample", index)
            recorder.last_screened_index = index
            return result

        for owner, name, value in (
            (producer_cls, "run_batch", run_batch),
            (native_log_cls, "wait", wait),
            (campaign, "sample_editor", sample_editor),
            (campaign, "assemble_sample", assemble_sample),
            (campaign, "screen_sample", screen_sample),
            (campaign, "gc", _GCProxy(recorder, original_gc)),
        ):
            patches.append(_Patch(owner, name, value))
        yield recorder
    finally:
        for patch in reversed(patches):
            patch.restore()
        if had_active:
            setattr(campaign, "_s140_phase_memory_active", prior_active)
        else:
            try:
                delattr(campaign, "_s140_phase_memory_active")
            except AttributeError:
                pass


def run_child_with_phase_memory(campaign: Any, root: str | os.PathLike[str], *,
                                run_id: str, prefix: int,
                                output: str | os.PathLike[str]) -> dict[str, Any]:
    """Run stock run_child under the bounded wrapper and persist in finally."""
    recorder = PhaseMemoryRecorder(run_id, prefix)
    status, error_code = "DIAGNOSTIC", None
    try:
        with install_phase_memory_wrappers(campaign, recorder):
            campaign.run_child(Path(root))
    except BoundedPhaseStop as error:
        status, error_code = "BOUNDED_STOP", error.code
    except BaseException as error:
        status, error_code = "ORIGINAL_GATE_FAILURE", getattr(error, "code", type(error).__name__)
        raise
    finally:
        recorder.persist(output, status=status, error_code=error_code)
    return recorder.report(status=status, error_code=error_code)


__all__ = [
    "ALLOWED_PREFIXES", "BoundedPhaseStop", "MAX_ROWS", "PHASE_ORDER",
    "PhaseMemoryRecorder", "install_phase_memory_wrappers", "run_child_with_phase_memory",
]

