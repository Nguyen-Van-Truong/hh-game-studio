"""Quick selftests for gamekit (owner O15.3): temp projects in %TEMP%, pinned Godot/Blender, < 3 min."""

from __future__ import annotations

import datetime as _dt
import os
import struct
import tempfile
import traceback
import zlib
from pathlib import Path
from typing import Any, Callable

from .. import common as C


def make_png(width: int, height: int, rgba: Callable[[int, int], tuple[int, int, int, int]]) -> bytes:
    """Tiny RGBA8 PNG encoder for selftest fixtures."""
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            rows.extend(bytes(rgba(x, y)))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b"")


class Ctx:
    """Selftest context: temp root, isolated gamekit state, recorded checks."""

    def __init__(self, name: str) -> None:
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.name = name
        self.root = Path(tempfile.gettempdir()) / "hh-gamekit-selftest" / f"{name}-{stamp}-{os.getpid()}"
        self.root.mkdir(parents=True, exist_ok=True)
        os.environ["HH_GAMEKIT_STATE"] = str(self.root / "state")
        self.checks: list[dict[str, Any]] = []

    def project(
        self,
        name: str,
        files: dict[str, str | bytes] | None = None,
        *,
        main_scene: str | None = None,
        settings: str = "",
        register: bool = True,
    ) -> C.Project:
        root = self.root / name
        root.mkdir(parents=True, exist_ok=True)
        lines = ["config_version=5", "", "[application]", "", f'config/name="{name}"']
        if main_scene:
            lines.append(f'run/main_scene="{main_scene}"')
        lines.append('config/features=PackedStringArray("4.7")')
        text = "\n".join(lines) + "\n"
        if settings:
            text += "\n" + settings.strip("\n") + "\n"
        (root / "project.godot").write_text(text, encoding="utf-8")
        for rel, content in (files or {}).items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content, encoding="utf-8", newline="\n")
        if not register:
            return C.Project(name, root)
        return C.register_project(root, name)

    def check(self, name: str, ok: bool, **detail: Any) -> bool:
        entry: dict[str, Any] = {"check": name, "ok": bool(ok)}
        if detail:
            entry["detail"] = detail
        self.checks.append(entry)
        return bool(ok)

    def expect_error(self, name: str, code: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> C.GamekitError | None:
        try:
            value = fn(*args, **kwargs)
        except C.GamekitError as exc:
            self.check(name, exc.code == code, expected=code, got=exc.code, detail=exc.detail[:300])
            return exc
        except Exception as exc:  # noqa: BLE001 - recorded as a failed check
            self.check(name, False, expected=code, got=repr(exc)[:300])
            return None
        self.check(name, False, expected=code, got="no error", value=str(value)[:300])
        return None

    def guard(self, name: str, fn: Callable[[], Any]) -> Any:
        """Run a step; an unexpected exception becomes a failed check instead of aborting the test."""
        try:
            return fn()
        except C.GamekitError as exc:
            self.check(name, False, error=exc.to_json())
        except Exception as exc:  # noqa: BLE001
            self.check(name, False, error=repr(exc)[:500], trace=traceback.format_exc()[-1500:])
        return None

    def ok(self) -> bool:
        return bool(self.checks) and all(c["ok"] for c in self.checks)
