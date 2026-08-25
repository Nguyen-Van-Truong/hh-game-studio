#!/usr/bin/env python3
"""R8-WP3: original procedural art/audio + license manifests for Kho Bí Ẩn.

Does not tick the plan. Does not replace ColorRect graybox actors.
Does not call remote imagegen. Stdlib only.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
import sys
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOGFOOD = REPO_ROOT / "godot" / "dogfood" / "kho-bi-an"
ASSETS = DOGFOOD / "assets"
RUN_ID = "01R8WP3ART00000000KBA00001"
TOOL = "tools/godot/gen_kho_bi_an_art.py"

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# Art bible palette. Every shipped pixel is one of these or transparent.
VOID = (0, 0, 0, 0)
OUTLINE = (10, 12, 18, 255)
MIDNIGHT = (18, 22, 42, 255)
INDIGO = (36, 42, 72, 255)
INDIGO_MID = (52, 60, 98, 255)
INDIGO_LIGHT = (72, 82, 128, 255)
BRASS = (196, 163, 74, 255)
BRASS_DARK = (140, 108, 40, 255)
BRASS_DEEP = (92, 68, 24, 255)
CREAM = (237, 228, 200, 255)
CREAM_SHADE = (196, 180, 140, 255)
RUST = (184, 58, 46, 255)
RUST_DARK = (110, 32, 28, 255)
TEAL = (61, 139, 122, 255)
TEAL_DARK = (32, 84, 76, 255)
LANTERN = (255, 196, 96, 255)
LANTERN_DIM = (196, 140, 48, 255)
STONE_DARK = (14, 16, 28, 255)

PALETTE = {
    VOID,
    OUTLINE,
    MIDNIGHT,
    INDIGO,
    INDIGO_MID,
    INDIGO_LIGHT,
    BRASS,
    BRASS_DARK,
    BRASS_DEEP,
    CREAM,
    CREAM_SHADE,
    RUST,
    RUST_DARK,
    TEAL,
    TEAL_DARK,
    LANTERN,
    LANTERN_DIM,
    STONE_DARK,
}

DIRS = ("down", "left", "right", "up")
FRAME = 32
TILE = 16


class Canvas:
    def __init__(self, w: int, h: int, fill: tuple[int, int, int, int] = VOID) -> None:
        self.w = w
        self.h = h
        self.px = [fill] * (w * h)

    def set(self, x: int, y: int, color: tuple[int, int, int, int]) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y * self.w + x] = color

    def get(self, x: int, y: int) -> tuple[int, int, int, int]:
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.px[y * self.w + x]
        return VOID

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

    def vline(self, x: int, y: int, h: int, color: tuple[int, int, int, int]) -> None:
        for yy in range(y, y + h):
            self.set(x, yy, color)

    def blit(self, other: "Canvas", dx: int, dy: int) -> None:
        for y in range(other.h):
            for x in range(other.w):
                color = other.get(x, y)
                if color[3] == 0:
                    continue
                self.set(dx + x, dy + y, color)

    def flip_h(self) -> "Canvas":
        out = Canvas(self.w, self.h)
        for y in range(self.h):
            for x in range(self.w):
                out.set(self.w - 1 - x, y, self.get(x, y))
        return out

    def crop(self, x: int, y: int, w: int, h: int) -> "Canvas":
        out = Canvas(w, h)
        for yy in range(h):
            for xx in range(w):
                out.set(xx, yy, self.get(x + xx, y + yy))
        return out

    def rgba(self) -> bytes:
        raw = bytearray()
        for color in self.px:
            raw.extend(color)
        return bytes(raw)

    def assert_palette(self, name: str) -> None:
        for color in self.px:
            if color[3] == 0:
                continue
            if color not in PALETTE:
                raise ValueError(f"{name}: off-bible pixel {color}")


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def png_bytes(w: int, h: int, rgba: bytes) -> bytes:
    if len(rgba) != w * h * 4:
        raise ValueError(f"pixel buffer {len(rgba)} != {w}*{h}*4")
    raw = bytearray()
    stride = w * 4
    for y in range(h):
        raw.append(0)
        raw.extend(rgba[y * stride : (y + 1) * stride])
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return PNG_MAGIC + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + _chunk(b"IEND", b"")


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_wav_pcm(samples: list[float], rate: int = 22050) -> bytes:
    pcm = bytearray()
    for sample in samples:
        clamped = max(-1.0, min(1.0, sample))
        pcm.extend(struct.pack("<h", int(clamped * 32767.0)))
    data = bytes(pcm)
    header = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt "
    header += struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
    header += b"data" + struct.pack("<I", len(data))
    return header + data


def tone(freq: float, t: float) -> float:
    return math.sin(2.0 * math.pi * freq * t)


def envelope(i: int, n: int, attack: float = 0.02, release: float = 0.08) -> float:
    if n <= 1:
        return 0.0
    start = i / (n - 1)
    a = min(1.0, start / attack) if attack > 0 else 1.0
    r = min(1.0, (1.0 - start) / release) if release > 0 else 1.0
    return a * r


def make_sfx(kind: str) -> bytes:
    rate = 22050
    if kind == "sfx_interact":
        n = int(rate * 0.09)
        samples = [0.22 * tone(880.0, i / rate) * envelope(i, n, 0.01, 0.2) for i in range(n)]
    elif kind == "sfx_pickup":
        n = int(rate * 0.16)
        samples = []
        for i in range(n):
            t = i / rate
            mix = 0.18 * tone(523.25, t) + 0.16 * tone(659.25, t) + 0.14 * tone(783.99, t)
            samples.append(mix * envelope(i, n, 0.02, 0.25))
    elif kind == "sfx_door":
        n = int(rate * 0.28)
        samples = []
        for i in range(n):
            t = i / rate
            scrape = 0.10 * tone(90.0 + 40.0 * t, t)
            click = 0.16 * tone(220.0, t) if 0.18 < t < 0.22 else 0.0
            samples.append((scrape + click) * envelope(i, n, 0.04, 0.2))
    elif kind == "sfx_caught":
        n = int(rate * 0.22)
        samples = []
        for i in range(n):
            t = i / rate
            buzz = 0.16 * tone(110.0, t) + 0.10 * tone(165.0, t)
            samples.append(buzz * envelope(i, n, 0.01, 0.15))
    elif kind == "sfx_win":
        n = int(rate * 0.55)
        notes = (392.0, 523.25, 659.25, 783.99)
        samples = []
        for i in range(n):
            t = i / rate
            idx = min(3, int(t / 0.12))
            samples.append(0.20 * tone(notes[idx], t) * envelope(i, n, 0.03, 0.22))
    elif kind == "sfx_lose":
        n = int(rate * 0.42)
        notes = (392.0, 329.63, 261.63)
        samples = []
        for i in range(n):
            t = i / rate
            idx = min(2, int(t / 0.12))
            samples.append(0.18 * tone(notes[idx], t) * envelope(i, n, 0.03, 0.28))
    elif kind == "music_vault":
        n = rate * 4
        samples = []
        motif = (196.0, 246.94, 220.0, 164.81)
        for i in range(n):
            t = i / rate
            drone = 0.06 * tone(98.0, t) + 0.04 * tone(147.0, t)
            step = int((t * 2.0) % 4)
            melody = 0.05 * tone(motif[step], t)
            env = 0.35 + 0.65 * math.sin(math.pi * (i / (n - 1)))
            samples.append((drone + melody) * env)
    else:
        raise ValueError(kind)
    peak = max(abs(s) for s in samples)
    if peak < 0.04:
        raise ValueError(f"{kind} is too quiet")
    return write_wav_pcm(samples, rate)


def brick_tile(warm: tuple[int, int, int, int], grout: tuple[int, int, int, int], accent: tuple[int, int, int, int] | None) -> Canvas:
    c = Canvas(TILE, TILE, grout)
    c.fill_rect(1, 1, 6, 6, warm)
    c.fill_rect(9, 1, 6, 6, warm)
    c.fill_rect(1, 9, 6, 6, warm)
    c.fill_rect(9, 9, 6, 6, warm)
    c.outline_rect(0, 0, TILE, TILE, OUTLINE)
    if accent is not None:
        c.set(3, 3, accent)
        c.set(12, 11, accent)
    return c


def wall_tile() -> Canvas:
    c = Canvas(TILE, TILE, STONE_DARK)
    c.fill_rect(1, 1, 14, 14, MIDNIGHT)
    c.fill_rect(2, 2, 12, 12, INDIGO)
    c.outline_rect(0, 0, TILE, TILE, OUTLINE)
    c.set(2, 2, BRASS_DARK)
    c.set(13, 2, BRASS_DARK)
    c.set(2, 13, BRASS_DARK)
    c.set(13, 13, BRASS_DARK)
    c.hline(3, 7, 10, BRASS_DEEP)
    return c


def tileset_vault() -> Canvas:
    sheet = Canvas(64, 16, VOID)
    sheet.blit(brick_tile(INDIGO, MIDNIGHT, BRASS_DARK), 0, 0)
    sheet.blit(brick_tile(INDIGO_MID, RUST_DARK, BRASS), 16, 0)
    sheet.blit(brick_tile(TEAL_DARK, MIDNIGHT, TEAL), 32, 0)
    sheet.blit(wall_tile(), 48, 0)
    return sheet


def _lantern(c: Canvas, x: int, y: int, bright: bool) -> None:
    glow = LANTERN if bright else LANTERN_DIM
    c.fill_rect(x, y, 4, 5, BRASS)
    c.outline_rect(x, y, 4, 5, OUTLINE)
    c.set(x + 1, y + 1, glow)
    c.set(x + 2, y + 1, glow)
    c.set(x + 1, y + 2, glow)
    c.set(x + 2, y + 2, CREAM)


def _draw_player_down(walk: bool, phase: int, bright: bool) -> Canvas:
    c = Canvas(FRAME, FRAME, VOID)
    bob = 1 if (walk and phase in (1, 3)) else (1 if (not walk and phase == 1) else 0)
    y = 2 + bob
    c.fill_rect(11, y, 10, 8, CREAM)
    c.outline_rect(10, y - 1, 12, 10, OUTLINE)
    c.fill_rect(12, y + 1, 8, 3, INDIGO)
    c.set(13, y + 4, OUTLINE)
    c.set(18, y + 4, OUTLINE)
    c.set(15, y + 6, CREAM_SHADE)
    c.fill_rect(10, y + 9, 12, 8, CREAM)
    c.outline_rect(9, y + 8, 14, 10, OUTLINE)
    c.hline(10, y + 13, 12, BRASS)
    c.fill_rect(11, y + 17, 4, 8, CREAM_SHADE)
    c.fill_rect(17, y + 17, 4, 8, CREAM_SHADE)
    if walk:
        if phase in (0, 1):
            c.fill_rect(10, y + 17, 5, 9, CREAM_SHADE)
            c.fill_rect(18, y + 18, 4, 7, CREAM)
        else:
            c.fill_rect(17, y + 17, 5, 9, CREAM_SHADE)
            c.fill_rect(10, y + 18, 4, 7, CREAM)
    c.outline_rect(11, y + 17, 4, 8, OUTLINE)
    c.outline_rect(17, y + 17, 4, 8, OUTLINE)
    _lantern(c, 22, y + 10, bright)
    return c


def _draw_player_left(walk: bool, phase: int, bright: bool) -> Canvas:
    c = Canvas(FRAME, FRAME, VOID)
    bob = 1 if (walk and phase in (1, 3)) else (1 if (not walk and phase == 1) else 0)
    y = 2 + bob
    c.fill_rect(12, y, 8, 8, CREAM)
    c.outline_rect(11, y - 1, 10, 10, OUTLINE)
    c.fill_rect(13, y + 1, 6, 3, INDIGO)
    c.set(13, y + 4, OUTLINE)
    c.fill_rect(13, y + 9, 8, 8, CREAM)
    c.outline_rect(12, y + 8, 10, 10, OUTLINE)
    c.hline(13, y + 13, 8, BRASS)
    back = 18 if walk and phase in (0, 1) else 16
    front = 13 if walk and phase in (2, 3) else 15
    c.fill_rect(back, y + 17, 4, 8, CREAM_SHADE)
    c.fill_rect(front, y + 18, 4, 7, CREAM)
    c.outline_rect(back, y + 17, 4, 8, OUTLINE)
    c.outline_rect(front, y + 18, 4, 7, OUTLINE)
    _lantern(c, 7, y + 11, bright)
    return c


def _draw_player_up(walk: bool, phase: int, bright: bool) -> Canvas:
    c = Canvas(FRAME, FRAME, VOID)
    bob = 1 if (walk and phase in (1, 3)) else (1 if (not walk and phase == 1) else 0)
    y = 2 + bob
    c.fill_rect(11, y, 10, 8, INDIGO)
    c.outline_rect(10, y - 1, 12, 10, OUTLINE)
    c.fill_rect(12, y + 1, 8, 4, INDIGO_MID)
    c.fill_rect(10, y + 9, 12, 8, CREAM_SHADE)
    c.outline_rect(9, y + 8, 14, 10, OUTLINE)
    c.hline(10, y + 13, 12, BRASS_DARK)
    c.fill_rect(11, y + 17, 4, 8, CREAM_SHADE)
    c.fill_rect(17, y + 17, 4, 8, CREAM_SHADE)
    if walk:
        if phase in (0, 1):
            c.fill_rect(10, y + 17, 5, 9, CREAM_SHADE)
        else:
            c.fill_rect(17, y + 17, 5, 9, CREAM_SHADE)
    c.outline_rect(11, y + 17, 4, 8, OUTLINE)
    c.outline_rect(17, y + 17, 4, 8, OUTLINE)
    _lantern(c, 22, y + 9, bright)
    return c


def actor_sheet(kind: str) -> Canvas:
    sheet = Canvas(FRAME * 6, FRAME * 4, VOID)
    for row, direction in enumerate(DIRS):
        for col in range(6):
            idle = col < 2
            phase = col if idle else col - 2
            bright = col % 2 == 0
            if kind == "player":
                if direction == "down":
                    frame = _draw_player_down(not idle, phase, bright)
                elif direction == "up":
                    frame = _draw_player_up(not idle, phase, bright)
                elif direction == "left":
                    frame = _draw_player_left(not idle, phase, bright)
                else:
                    frame = _draw_player_left(not idle, phase, bright).flip_h()
            else:
                frame = _draw_warden(direction, not idle, phase, bright)
            sheet.blit(frame, col * FRAME, row * FRAME)
    if kind == "warden":
        assert_walk_up_unique(sheet, "actor_warden")
    elif kind == "player":
        assert_walk_up_unique(sheet, "actor_player")
    return sheet


def assert_walk_up_unique(sheet: Canvas, name: str) -> None:
    up_row = DIRS.index("up")
    idle: list[bytes] = []
    for col in range(2):
        idle.append(sheet.crop(col * FRAME, up_row * FRAME, FRAME, FRAME).rgba())
    for col in range(2, 6):
        walk = sheet.crop(col * FRAME, up_row * FRAME, FRAME, FRAME).rgba()
        if walk in idle:
            raise ValueError(f"{name} walk_up frame {col - 2} is byte-identical to idle_up")


def _draw_warden(direction: str, walk: bool, phase: int, bright: bool) -> Canvas:
    if direction == "right":
        return _draw_warden("left", walk, phase, bright).flip_h()
    c = Canvas(FRAME, FRAME, VOID)
    bob = 1 if (walk and phase in (1, 3)) else (1 if (not walk and phase == 1) else 0)
    y = 1 + bob
    body = RUST
    shade = RUST_DARK
    if direction == "down":
        c.fill_rect(10, y, 12, 7, shade)
        c.outline_rect(9, y - 1, 14, 9, OUTLINE)
        c.fill_rect(11, y + 2, 10, 4, body)
        c.set(13, y + 5, TEAL)
        c.set(18, y + 5, TEAL)
        c.fill_rect(9, y + 8, 14, 10, body)
        c.outline_rect(8, y + 7, 16, 12, OUTLINE)
        c.hline(9, y + 12, 14, BRASS_DEEP)
        c.fill_rect(10, y + 18, 5, 9, shade)
        c.fill_rect(17, y + 18, 5, 9, shade)
        if walk and phase in (0, 1):
            c.fill_rect(9, y + 18, 6, 10, shade)
        elif walk:
            c.fill_rect(17, y + 18, 6, 10, shade)
        c.outline_rect(10, y + 18, 5, 9, OUTLINE)
        c.outline_rect(17, y + 18, 5, 9, OUTLINE)
        c.vline(24, y + 6, 12, BRASS_DARK)
        _lantern(c, 23, y + 3, bright)
    elif direction == "up":
        c.fill_rect(10, y, 12, 7, shade)
        c.outline_rect(9, y - 1, 14, 9, OUTLINE)
        c.fill_rect(11, y + 1, 10, 5, RUST_DARK)
        c.fill_rect(9, y + 8, 14, 10, shade)
        c.outline_rect(8, y + 7, 16, 12, OUTLINE)
        c.hline(9, y + 12, 14, BRASS_DEEP)
        c.fill_rect(10, y + 18, 5, 9, shade)
        c.fill_rect(17, y + 18, 5, 9, shade)
        if walk and phase in (0, 1):
            c.fill_rect(9, y + 18, 6, 10, shade)
            c.fill_rect(18, y + 19, 4, 7, body)
        elif walk:
            c.fill_rect(17, y + 18, 6, 10, shade)
            c.fill_rect(10, y + 19, 4, 7, body)
        c.outline_rect(10, y + 18, 5, 9, OUTLINE)
        c.outline_rect(17, y + 18, 5, 9, OUTLINE)
        lantern_x = 23 if not walk else (21 if phase in (0, 1) else 25)
        c.vline(lantern_x + 1, y + 6, 12, BRASS_DEEP)
        _lantern(c, lantern_x, y + 2, bright)
    else:
        c.fill_rect(12, y, 9, 7, shade)
        c.outline_rect(11, y - 1, 11, 9, OUTLINE)
        c.fill_rect(13, y + 2, 7, 4, body)
        c.set(13, y + 5, TEAL)
        c.fill_rect(12, y + 8, 9, 10, body)
        c.outline_rect(11, y + 7, 11, 12, OUTLINE)
        back = 18 if walk and phase in (0, 1) else 16
        front = 12 if walk and phase in (2, 3) else 14
        c.fill_rect(back, y + 18, 5, 9, shade)
        c.fill_rect(front, y + 19, 4, 8, body)
        c.outline_rect(back, y + 18, 5, 9, OUTLINE)
        c.outline_rect(front, y + 19, 4, 8, OUTLINE)
        c.vline(7, y + 7, 11, BRASS_DARK)
        _lantern(c, 5, y + 3, bright)
    return c


def item_key() -> Canvas:
    c = Canvas(FRAME, FRAME, VOID)
    c.fill_rect(8, 8, 8, 8, BRASS)
    c.outline_rect(7, 7, 10, 10, OUTLINE)
    c.fill_rect(10, 10, 4, 4, LANTERN)
    c.fill_rect(16, 11, 10, 3, BRASS)
    c.outline_rect(16, 10, 10, 5, OUTLINE)
    c.vline(22, 14, 6, BRASS)
    c.vline(25, 14, 4, BRASS)
    c.set(22, 19, OUTLINE)
    c.set(25, 17, OUTLINE)
    return c


def item_relic() -> Canvas:
    c = Canvas(FRAME, FRAME, VOID)
    c.fill_rect(13, 6, 6, 18, BRASS_DARK)
    c.outline_rect(12, 5, 8, 20, OUTLINE)
    c.fill_rect(10, 10, 12, 12, TEAL)
    c.outline_rect(9, 9, 14, 14, OUTLINE)
    c.fill_rect(13, 13, 6, 6, TEAL_DARK)
    c.set(15, 15, LANTERN)
    c.set(16, 15, CREAM)
    c.set(15, 16, CREAM)
    return c


def prop_door() -> Canvas:
    c = Canvas(16, 48, MIDNIGHT)
    c.fill_rect(1, 1, 14, 46, BRASS_DARK)
    c.fill_rect(2, 3, 12, 20, INDIGO)
    c.fill_rect(2, 25, 12, 20, INDIGO)
    c.outline_rect(0, 0, 16, 48, OUTLINE)
    c.hline(2, 23, 12, BRASS)
    c.vline(8, 3, 42, BRASS_DEEP)
    c.fill_rect(11, 22, 3, 5, BRASS)
    c.set(12, 24, LANTERN)
    return c


def ui_icon_key() -> Canvas:
    c = Canvas(16, 16, VOID)
    c.fill_rect(3, 3, 5, 5, BRASS)
    c.outline_rect(2, 2, 7, 7, OUTLINE)
    c.set(5, 5, LANTERN)
    c.fill_rect(8, 5, 6, 2, BRASS)
    c.vline(11, 7, 4, BRASS)
    c.vline(13, 7, 3, BRASS)
    return c


def vfx_interact() -> Canvas:
    sheet = Canvas(64, 16, VOID)
    for i in range(4):
        frame = Canvas(16, 16, VOID)
        r = 1 + i
        cx, cy = 8, 8
        for y in range(16):
            for x in range(16):
                d = abs(x - cx) + abs(y - cy)
                if d == r:
                    frame.set(x, y, LANTERN if i < 2 else BRASS)
                elif d == r + 1 and i > 0:
                    frame.set(x, y, CREAM if i < 3 else BRASS_DARK)
        if i == 0:
            frame.set(8, 8, CREAM)
        sheet.blit(frame, i * 16, 0)
    return sheet


def contact_sheet(images: dict[str, Canvas]) -> Canvas:
    slots = (
        ("tileset_vault", 0, 0, 64, 16),
        ("actor_player", 0, 0, 32, 32),
        ("actor_warden", 0, 0, 32, 32),
        ("item_key", 0, 0, 32, 32),
        ("prop_door", 0, 0, 16, 48),
        ("item_relic", 0, 0, 32, 32),
        ("ui_icon_key", 0, 0, 16, 16),
        ("vfx_interact", 0, 0, 16, 16),
    )
    pad = 6
    cell_w = 70
    cell_h = 56
    cols = 4
    rows = 2
    sheet = Canvas(pad * 2 + cols * cell_w, pad * 2 + rows * cell_h, MIDNIGHT)
    for i, (name, sx, sy, sw, sh) in enumerate(slots):
        col = i % cols
        row = i // cols
        src = images[name].crop(sx, sy, sw, sh)
        dx = pad + col * cell_w + (cell_w - sw) // 2
        dy = pad + row * cell_h + (cell_h - sh) // 2
        sheet.blit(src, dx, dy)
        sheet.outline_rect(dx - 1, dy - 1, sw + 2, sh + 2, BRASS_DEEP)
    return sheet


def asset_entry(
    asset_id: str,
    rel: str,
    kind: str,
    data: bytes,
    extra: dict,
) -> dict:
    entry = {
        "id": asset_id,
        "role": extra.pop("role", "ship"),
        "kind": kind,
        "path": extra.pop("path", f"res://{rel.replace(chr(92), '/')}"),
        "rel": rel.replace("\\", "/"),
        "source": "original procedural",
        "tool": TOOL,
        "prompt": "",
        "model": "none",
        "license": "original",
        "hash": sha256_bytes(data),
        "bytes": len(data),
    }
    entry.update(extra)
    return entry


def main() -> int:
    images = {
        "tileset_vault": tileset_vault(),
        "actor_player": actor_sheet("player"),
        "actor_warden": actor_sheet("warden"),
        "item_key": item_key(),
        "prop_door": prop_door(),
        "item_relic": item_relic(),
        "ui_icon_key": ui_icon_key(),
        "vfx_interact": vfx_interact(),
    }
    for name, canvas in images.items():
        canvas.assert_palette(name)

    files: list[tuple[str, Path, bytes, str, dict]] = [
        (
            "tileset_vault",
            ASSETS / "tiles" / "tileset_vault.png",
            png_bytes(64, 16, images["tileset_vault"].rgba()),
            "image",
            {"width": 64, "height": 16, "tile_size": 16, "pivot": [8, 8], "filter": "nearest", "mipmaps": False},
        ),
        (
            "actor_player",
            ASSETS / "art" / "actor_player.png",
            png_bytes(192, 128, images["actor_player"].rgba()),
            "image",
            {"width": 192, "height": 128, "frame": [32, 32], "pivot": [16, 16], "filter": "nearest", "mipmaps": False},
        ),
        (
            "actor_warden",
            ASSETS / "art" / "actor_warden.png",
            png_bytes(192, 128, images["actor_warden"].rgba()),
            "image",
            {"width": 192, "height": 128, "frame": [32, 32], "pivot": [16, 16], "filter": "nearest", "mipmaps": False},
        ),
        (
            "item_key",
            ASSETS / "art" / "item_key.png",
            png_bytes(32, 32, images["item_key"].rgba()),
            "image",
            {"width": 32, "height": 32, "pivot": [16, 16], "filter": "nearest", "mipmaps": False},
        ),
        (
            "prop_door",
            ASSETS / "art" / "prop_door.png",
            png_bytes(16, 48, images["prop_door"].rgba()),
            "image",
            {"width": 16, "height": 48, "pivot": [8, 24], "filter": "nearest", "mipmaps": False},
        ),
        (
            "item_relic",
            ASSETS / "art" / "item_relic.png",
            png_bytes(32, 32, images["item_relic"].rgba()),
            "image",
            {"width": 32, "height": 32, "pivot": [16, 16], "filter": "nearest", "mipmaps": False},
        ),
        (
            "ui_icon_key",
            ASSETS / "ui" / "ui_icon_key.png",
            png_bytes(16, 16, images["ui_icon_key"].rgba()),
            "image",
            {"width": 16, "height": 16, "pivot": [8, 8], "filter": "nearest", "mipmaps": False},
        ),
        (
            "vfx_interact",
            ASSETS / "vfx" / "vfx_interact.png",
            png_bytes(64, 16, images["vfx_interact"].rgba()),
            "image",
            {"width": 64, "height": 16, "frame": [16, 16], "pivot": [8, 8], "filter": "nearest", "mipmaps": False},
        ),
    ]
    for name in ("sfx_pickup", "sfx_door", "sfx_caught", "sfx_win", "sfx_lose", "sfx_interact", "music_vault"):
        files.append(
            (
                name,
                ASSETS / "audio" / f"{name}.wav",
                make_sfx(name),
                "audio",
                {"loop": name == "music_vault", "bus": "Music" if name == "music_vault" else "SFX"},
            )
        )

    contact = contact_sheet(images)
    contact.assert_palette("contact_sheet")
    contact_bytes = png_bytes(contact.w, contact.h, contact.rgba())
    files.append(
        (
            "contact_sheet",
            ASSETS / "audit" / "contact_sheet.png",
            contact_bytes,
            "image",
            {
                "role": "audit",
                "width": contact.w,
                "height": contact.h,
                "filter": "nearest",
                "mipmaps": False,
            },
        )
    )

    assets: list[dict] = []
    for asset_id, path, data, kind, extra in files:
        write_atomic(path, data)
        entry = asset_entry(asset_id, path.relative_to(DOGFOOD).as_posix(), kind, data, extra)
        assets.append(entry)
        sidecar = path.with_name(path.name + ".manifest.json")
        write_atomic(sidecar, json.dumps(entry, indent=2, sort_keys=True).encode("utf-8"))
        print(f"{entry['rel']:<42} {entry['bytes']:>7} {entry['hash'][:12]}")

    font_entry = {
        "id": "font_ui",
        "role": "ship",
        "kind": "bundled",
        "path": "bundled:OpenSans-SemiBold",
        "rel": "",
        "source": "Godot 4.7.1-stable bundled default project font",
        "tool": "Godot 4.7.1-stable",
        "prompt": "",
        "model": "none",
        "license": "OFL-1.1",
        "hash": "bundled",
        "bytes": 0,
        "note": "ATTRIB does not claim hash as SHA-256 of font bytes",
    }
    assets.append(font_entry)

    layout = {
        "frame": [32, 32],
        "filter": "nearest",
        "mipmaps": False,
        "pivot": [16, 16],
        "rows": list(DIRS),
        "cols": ["idle_0", "idle_1", "walk_0", "walk_1", "walk_2", "walk_3"],
        "fps_idle": 4.0,
        "fps_walk": 8.0,
        "actors": {
            "actor_player": "res://assets/art/actor_player.png",
            "actor_warden": "res://assets/art/actor_warden.png",
        },
        "vfx_interact": {
            "path": "res://assets/vfx/vfx_interact.png",
            "frame": [16, 16],
            "frames": 4,
            "fps": 10.0,
            "animation": "burst",
        },
        "contact_slots": [
            {"id": "tileset_vault", "region": [0, 0, 64, 16]},
            {"id": "actor_player", "region": [0, 0, 32, 32]},
            {"id": "actor_warden", "region": [0, 0, 32, 32]},
            {"id": "item_key", "region": [0, 0, 32, 32]},
            {"id": "prop_door", "region": [0, 0, 16, 48]},
            {"id": "item_relic", "region": [0, 0, 32, 32]},
            {"id": "ui_icon_key", "region": [0, 0, 16, 16]},
            {"id": "vfx_interact", "region": [0, 0, 16, 16]},
        ],
    }
    write_atomic(ASSETS / "ATLAS_LAYOUT.json", json.dumps(layout, indent=2).encode("utf-8"))

    manifest = {
        "schema": 1,
        "project": "kho-bi-an",
        "run_id": RUN_ID,
        "policy": "commercial-safe",
        "allowed_licenses": ["original", "CC0", "MIT", "OFL-1.1"],
        "unknown_forbidden": True,
        "art_count_cap": 16,
        "audio_count_cap": 8,
        "font_count_cap": 1,
        "placeholder_forbidden": True,
        "assets": assets,
    }
    write_atomic(ASSETS / "ASSET_MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"))
    print(f"wrote {len(assets)} manifest rows run_id={RUN_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
