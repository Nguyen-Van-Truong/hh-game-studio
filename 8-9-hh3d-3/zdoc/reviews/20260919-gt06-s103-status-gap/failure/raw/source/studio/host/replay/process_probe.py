"""Read-only metrics from one retained Windows process handle, never PID kills."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import time


class ProbeError(RuntimeError):
    def __init__(self, code, *, cleanup_owner=None):
        super().__init__(code)
        self.cleanup_owner = cleanup_owner


HELD_PROBES = []


class ProcessProbe:
    def __init__(self, pid: int, expected_executable: Path):
        if HELD_PROBES:
            raise ProbeError('PROBE_CLEANUP_HELD', cleanup_owner=HELD_PROBES[0])
        if os.name != 'nt' or type(pid) is not int or not 0 < pid < 0xffffffff:
            raise ProbeError('PROBE_WINDOWS_PID')
        from ctypes import wintypes as w
        self.pid, self.handle = pid, None
        self.close_uncertain = False
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        self.p = ctypes.WinDLL('psapi', use_last_error=True)
        self.u = ctypes.WinDLL('user32', use_last_error=True)
        k = self.k
        k.OpenProcess.argtypes, k.OpenProcess.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
        k.CloseHandle.argtypes, k.CloseHandle.restype = [w.HANDLE], w.BOOL
        k.GetProcessTimes.argtypes = [w.HANDLE] + [ctypes.POINTER(w.FILETIME)] * 4
        k.GetProcessTimes.restype = w.BOOL
        k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
        k.QueryFullProcessImageNameW.restype = w.BOOL
        k.WaitForSingleObject.argtypes, k.WaitForSingleObject.restype = [w.HANDLE, w.DWORD], w.DWORD
        class Memory(ctypes.Structure):
            _fields_ = [('cb', w.DWORD), ('page_faults', w.DWORD),
                        ('peak_working_set', ctypes.c_size_t), ('working_set', ctypes.c_size_t),
                        ('peak_paged', ctypes.c_size_t), ('paged', ctypes.c_size_t),
                        ('peak_nonpaged', ctypes.c_size_t), ('nonpaged', ctypes.c_size_t),
                        ('pagefile', ctypes.c_size_t), ('peak_pagefile', ctypes.c_size_t)]
        self.Memory = Memory
        self.p.GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.POINTER(Memory), w.DWORD]
        self.p.GetProcessMemoryInfo.restype = w.BOOL
        self.callback_type = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
        self.u.EnumWindows.argtypes = [self.callback_type, w.LPARAM]
        self.u.EnumWindows.restype = w.BOOL
        self.u.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
        self.u.GetWindowThreadProcessId.restype = w.DWORD
        self.u.IsWindowVisible.argtypes, self.u.IsWindowVisible.restype = [w.HWND], w.BOOL
        try:
            self.handle = k.OpenProcess(0x0400 | 0x0010 | 0x100000, False, pid)
            self._need(self.handle, 'PROBE_OPEN')
            times = [w.FILETIME() for _ in range(4)]
            self._need(k.GetProcessTimes(self.handle, *(ctypes.byref(v) for v in times)), 'PROBE_START')
            self.process_start = 'windows:' + str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)
            size, text = w.DWORD(32768), ctypes.create_unicode_buffer(32768)
            self._need(k.QueryFullProcessImageNameW(self.handle, 0, text, ctypes.byref(size)), 'PROBE_IMAGE')
            self._need(os.path.normcase(text.value) == os.path.normcase(str(expected_executable.resolve())), 'PROBE_IMAGE_IDENTITY')
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _need(value, code):
        if not value:
            raise ProbeError(code)

    def sample(self):
        from ctypes import wintypes as w
        self._need(self.handle is not None and not self.close_uncertain, 'PROBE_CLOSED_OR_UNCERTAIN')
        wait = self.k.WaitForSingleObject(self.handle, 0)
        if wait == 0:
            return None
        self._need(wait == 258, 'PROBE_WAIT')
        memory = self.Memory()
        memory.cb = ctypes.sizeof(memory)
        self._need(self.p.GetProcessMemoryInfo(self.handle, ctypes.byref(memory), memory.cb), 'PROBE_RSS')
        windows = []
        def visit(hwnd, _):
            owner = w.DWORD()
            if not self.u.GetWindowThreadProcessId(hwnd, ctypes.byref(owner)):
                # A foreign window can disappear during enumeration. It has
                # never supplied authority to this process observation.
                return True
            if owner.value == self.pid and self.u.IsWindowVisible(hwnd):
                windows.append(str(int(hwnd)))
            return True
        callback = self.callback_type(visit)
        self._need(self.u.EnumWindows(callback, 0), 'PROBE_WINDOWS')
        return {'host_mono_us': time.perf_counter_ns() // 1000,
                'rss_bytes': int(memory.working_set), 'visible_window_handles': sorted(windows)}

    def close(self):
        if self.handle is not None:
            if self.close_uncertain:
                raise ProbeError('PROBE_CLOSE_UNCERTAIN', cleanup_owner=self)
            if self not in HELD_PROBES:
                HELD_PROBES.append(self)
            self.close_uncertain = True
            if not self.k.CloseHandle(self.handle):
                self.close_uncertain = False  # Checked native failure retains ownership.
                raise ProbeError('PROBE_CLOSE', cleanup_owner=self)
            self.handle = None
            self.close_uncertain = False
            HELD_PROBES.remove(self)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
