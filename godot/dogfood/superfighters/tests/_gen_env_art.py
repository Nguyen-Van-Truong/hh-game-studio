#!/usr/bin/env python3
"""Original acid / water / rotor sprites for VF4-WP5. Not a VF7 rewrite."""

from __future__ import annotations

import hashlib
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
ACID = (72, 196, 64, 255)
ACID_LT = (168, 232, 96, 255)
ACID_DK = (28, 88, 32, 255)
WATER = (48, 120, 196, 255)
WATER_LT = (120, 196, 232, 255)
WATER_DK = (20, 56, 96, 255)
VOID_DK = (12, 10, 18, 255)
VOID_EDGE = (168, 48, 48, 255)
METAL = (58, 72, 78, 255)
METAL_LT = (88, 108, 116, 255)
METAL_DK = (36, 46, 50, 255)
AMBER = (232, 168, 48, 255)
AMBER_DK = (168, 112, 24, 255)
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


def zone_acid() -> Canvas:
    c = Canvas(32, 16)
    c.fill_rect(1, 4, 30, 11, ACID_DK)
    c.fill_rect(2, 5, 28, 9, ACID)
    c.outline_rect(1, 4, 30, 11, OUTLINE)
    c.hline(3, 6, 26, ACID_LT)
    c.set(8, 8, CREAM)
    c.set(20, 9, CREAM)
    return c


def zone_water() -> Canvas:
    c = Canvas(32, 16)
    c.fill_rect(1, 4, 30, 11, WATER_DK)
    c.fill_rect(2, 5, 28, 9, WATER)
    c.outline_rect(1, 4, 30, 11, OUTLINE)
    c.hline(3, 6, 26, WATER_LT)
    c.set(10, 8, CREAM)
    c.set(22, 10, CREAM)
    return c


def zone_void() -> Canvas:
    c = Canvas(48, 16)
    c.fill_rect(1, 2, 46, 13, VOID_DK)
    c.outline_rect(1, 2, 46, 13, VOID_EDGE)
    c.hline(3, 4, 42, (40, 16, 16, 255))
    c.hline(4, 12, 40, OUTLINE)
    return c


def prop_rotor() -> Canvas:
    c = Canvas(24, 24)
    c.fill_rect(10, 10, 4, 4, METAL)
    c.outline_rect(10, 10, 4, 4, OUTLINE)
    c.fill_rect(2, 10, 20, 4, METAL_DK)
    c.outline_rect(2, 10, 20, 4, METAL_LT)
    c.fill_rect(10, 2, 4, 20, METAL_DK)
    c.outline_rect(10, 2, 4, 20, METAL_LT)
    c.fill_rect(3, 11, 4, 2, AMBER)
    c.fill_rect(17, 11, 4, 2, AMBER)
    c.fill_rect(11, 3, 2, 4, AMBER_DK)
    c.fill_rect(11, 17, 2, 4, AMBER_DK)
    c.set(11, 11, CREAM)
    return c


def main() -> int:
    ART.mkdir(parents=True, exist_ok=True)
    rows = [
        ("zone_acid.png", zone_acid()),
        ("zone_water.png", zone_water()),
        ("zone_void.png", zone_void()),
        ("prop_rotor.png", prop_rotor()),
    ]
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
