#!/usr/bin/env python3
"""Original door / lift / trigger sprites for VF4-WP4. Not a VF7 rewrite."""

from __future__ import annotations

import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "assets" / "art"
MANIFEST = ROOT / "assets" / "ASSET_MANIFEST.json"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

VOID = (0, 0, 0, 0)
OUTLINE = (8, 10, 14, 255)
METAL = (58, 72, 78, 255)
METAL_LT = (88, 108, 116, 255)
METAL_DK = (36, 46, 50, 255)
AMBER = (232, 168, 48, 255)
AMBER_DK = (168, 112, 24, 255)
CONCRETE = (78, 82, 90, 255)
CONCRETE_LT = (110, 114, 122, 255)
CONCRETE_DK = (52, 56, 62, 255)
HAZARD = (212, 176, 36, 255)
HAZARD_DK = (24, 24, 26, 255)
CREAM = (236, 228, 208, 255)


class Canvas:
    def __init__(self, w: int, h: int) -> None:
        self.w = w
        self.h = h
        self.px = [VOID] * (w * h)

    def set(self, x: int, y: int, color: tuple[int, int, int, int]) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y * self.w + x] = color

    def fill_rect(self, x: int, y: int, w: int, h: int, color: tuple[int, int, int, int]) -> None:
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.set(xx, yy, color)

    def outline_rect(self, x: int, y: int, w: int, h: int, color: tuple[int, int, int, int]) -> None:
        for xx in range(x, x + w):
            self.set(xx, y, color)
            self.set(xx, y + h - 1, color)
        for yy in range(y, y + h):
            self.set(x, yy, color)
            self.set(x + w - 1, yy, color)

    def hline(self, x: int, y: int, w: int, color: tuple[int, int, int, int]) -> None:
        for xx in range(x, x + w):
            self.set(xx, y, color)

    def rgba(self) -> bytes:
        raw = bytearray()
        for color in self.px:
            raw.extend(color)
        return bytes(raw)


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def png_bytes(w: int, h: int, rgba: bytes) -> bytes:
    raw = bytearray()
    stride = w * 4
    for y in range(h):
        raw.append(0)
        raw.extend(rgba[y * stride : (y + 1) * stride])
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return PNG_MAGIC + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + _chunk(b"IEND", b"")


def prop_door() -> Canvas:
    c = Canvas(16, 24)
    c.fill_rect(2, 1, 12, 22, METAL)
    c.outline_rect(2, 1, 12, 22, OUTLINE)
    c.fill_rect(4, 3, 8, 8, METAL_DK)
    c.outline_rect(4, 3, 8, 8, METAL_LT)
    c.fill_rect(4, 13, 8, 8, METAL_DK)
    c.outline_rect(4, 13, 8, 8, METAL_LT)
    c.fill_rect(11, 11, 2, 3, AMBER)
    c.set(11, 12, AMBER_DK)
    return c


def prop_lift() -> Canvas:
    c = Canvas(32, 8)
    c.fill_rect(1, 1, 30, 6, CONCRETE)
    c.outline_rect(1, 1, 30, 6, OUTLINE)
    c.hline(1, 2, 30, CONCRETE_LT)
    c.hline(1, 5, 30, CONCRETE_DK)
    c.fill_rect(3, 2, 4, 4, HAZARD)
    c.fill_rect(25, 2, 4, 4, HAZARD)
    c.set(4, 3, HAZARD_DK)
    c.set(26, 3, HAZARD_DK)
    return c


def prop_trigger() -> Canvas:
    c = Canvas(16, 6)
    c.fill_rect(1, 1, 14, 4, AMBER_DK)
    c.outline_rect(1, 1, 14, 4, OUTLINE)
    c.hline(2, 2, 12, AMBER)
    c.set(8, 3, CREAM)
    return c


def main() -> int:
    ART.mkdir(parents=True, exist_ok=True)
    rows = [
        ("prop_door.png", prop_door()),
        ("prop_lift.png", prop_lift()),
        ("prop_trigger.png", prop_trigger()),
    ]
    import hashlib

    entries = []
    for name, canvas in rows:
        data = png_bytes(canvas.w, canvas.h, canvas.rgba())
        path = ART / name
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        digest = hashlib.sha256(data).hexdigest()
        entries.append(
            {
                "path": f"godot/dogfood/superfighters/assets/art/{name}",
                "sha256": digest,
                "w": str(canvas.w),
                "h": str(canvas.h),
            }
        )
        print(f"wrote {name} {digest}")
    if MANIFEST.is_file():
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
        files = payload.get("files") or []
        by_path = {str(row.get("path")): row for row in files if isinstance(row, dict)}
        for entry in entries:
            by_path[entry["path"]] = entry
        payload["files"] = list(by_path.values())
        MANIFEST.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
