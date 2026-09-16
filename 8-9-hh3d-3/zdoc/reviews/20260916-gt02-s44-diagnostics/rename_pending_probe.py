"""Diagnostic only: does delete-pending allow a held-target replacement?"""
from __future__ import annotations

import ctypes as C
import json
from pathlib import Path
import struct
import sys
import tempfile

STUDIO = Path(__file__).resolve().parents[3] / "studio"
sys.path.insert(0, str(STUDIO))
from host.core.safe_create import SafeCreateApi


def run():
    rows = []
    for share in (0, 1, 3, 5, 7):
        for pending in (False, True):
            for info, flags in ((3, 1), (22, 1), (22, 3)):
                with tempfile.TemporaryDirectory(prefix="gt02-s44-rename-") as tmp:
                    root = Path(tmp)
                    target, source = root / "target.txt", root / "source.txt"
                    target.write_bytes(b"old-data")
                    source.write_bytes(b"new-data")
                    api = SafeCreateApi()
                    old = api.dll.CreateFileW(str(target), 0x80010080, share,
                                             None, 3, 0x00200000, None)
                    new = api.dll.CreateFileW(str(source), 0x80010080, 0,
                                             None, 3, 0x00200000, None)
                    if old == C.c_void_p(-1).value or new == C.c_void_p(-1).value:
                        raise RuntimeError("diagnostic setup failed")
                    row = {"share": share, "pending": pending, "info": info, "flags": flags}
                    try:
                        if pending:
                            api.pending(old, True)
                        encoded = str(target).encode("utf-16-le")
                        payload = bytearray(24 + len(encoded))
                        struct.pack_into("<I4xQI", payload, 0, flags, 0, len(encoded))
                        payload[20:20 + len(encoded)] = encoded
                        view = (C.c_ubyte * len(payload)).from_buffer(payload)
                        C.set_last_error(0)
                        row["renamed"] = bool(api.dll.SetFileInformationByHandle(new, info, view, len(payload)))
                        row["winerror"] = C.get_last_error()
                        row["old_bytes"] = api.read(old, 128).decode("ascii")
                        row["new_bytes"] = api.read(new, 128).decode("ascii")
                        if pending and not row["renamed"]:
                            api.pending(old, False)
                    finally:
                        api.close(old)
                        api.close(new)
                    row["target_bytes_after_close"] = target.read_bytes().decode("ascii") if target.exists() else None
                    rows.append(row)
    print(json.dumps({"diagnostic_only": True, "rows": rows}, indent=2), flush=True)


if __name__ == "__main__":
    run()
