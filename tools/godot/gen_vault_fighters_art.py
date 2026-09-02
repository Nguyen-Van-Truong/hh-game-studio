#!/usr/bin/env python3
"""Original procedural art/audio for Vault Fighters (Y8 Superfighters-reference).

Does not rip Y8/Flash/SWF/PNG/audio. Does not tick the 20-8 plan.
Does not claim G6/60/60. Stdlib only. No remote imagegen.
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
DOGFOOD = REPO_ROOT / "godot" / "dogfood" / "superfighters"
ASSETS = DOGFOOD / "assets"
TOOL = "tools/godot/gen_vault_fighters_art.py"

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

VOID = (0, 0, 0, 0)
OUTLINE = (8, 10, 14, 255)
SKY = (18, 28, 48, 255)
SKY2 = (28, 42, 68, 255)
SKY3 = (40, 58, 88, 255)
CONCRETE = (78, 82, 90, 255)
CONCRETE_LT = (110, 114, 122, 255)
CONCRETE_DK = (52, 56, 62, 255)
BRICK = (92, 48, 42, 255)
BRICK_LT = (128, 68, 58, 255)
BRICK_DK = (64, 32, 28, 255)
WOOD = (118, 82, 46, 255)
WOOD_LT = (156, 112, 62, 255)
WOOD_DK = (78, 52, 28, 255)
METAL = (58, 72, 78, 255)
METAL_LT = (88, 108, 116, 255)
METAL_DK = (36, 46, 50, 255)
SKIN = (232, 196, 158, 255)
SKIN_SH = (196, 148, 112, 255)
SUIT = (52, 58, 64, 255)
GOGGLE = (40, 200, 220, 255)
GOGGLE_DK = (20, 120, 140, 255)
AMBER = (232, 168, 48, 255)
AMBER_DK = (168, 112, 24, 255)
CREAM = (236, 228, 208, 255)
TEAM_BLUE = (48, 98, 196, 255)
TEAM_RED = (196, 48, 52, 255)
TEAM_GOLD = (212, 168, 36, 255)
TEAM_TEAL = (36, 148, 132, 255)
BLOOD = (160, 28, 36, 255)
WHITE = (240, 240, 236, 255)
HAZARD = (212, 176, 36, 255)
HAZARD_DK = (24, 24, 26, 255)
WINDOW = (80, 140, 180, 255)

PALETTE = {
    VOID,
    OUTLINE,
    SKY,
    SKY2,
    SKY3,
    CONCRETE,
    CONCRETE_LT,
    CONCRETE_DK,
    BRICK,
    BRICK_LT,
    BRICK_DK,
    WOOD,
    WOOD_LT,
    WOOD_DK,
    METAL,
    METAL_LT,
    METAL_DK,
    SKIN,
    SKIN_SH,
    SUIT,
    GOGGLE,
    GOGGLE_DK,
    AMBER,
    AMBER_DK,
    CREAM,
    TEAM_BLUE,
    TEAM_RED,
    TEAM_GOLD,
    TEAM_TEAL,
    BLOOD,
    WHITE,
    HAZARD,
    HAZARD_DK,
    WINDOW,
}

FRAME = 32
TILE = 16
SHEET_W = 8
SHEET_H = 2


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


def noise(i: int, seed: int = 17) -> float:
    x = (i * 1103515245 + seed) & 0x7FFFFFFF
    return (x / 0x7FFFFFFF) * 2.0 - 1.0


def tile_concrete() -> Canvas:
    c = Canvas(TILE, TILE, CONCRETE)
    c.outline_rect(0, 0, TILE, TILE, OUTLINE)
    c.fill_rect(1, 1, 14, 14, CONCRETE)
    c.hline(2, 4, 5, CONCRETE_LT)
    c.hline(8, 10, 5, CONCRETE_DK)
    c.set(3, 12, CONCRETE_LT)
    c.set(12, 3, CONCRETE_DK)
    return c


def tile_brick() -> Canvas:
    c = Canvas(TILE, TILE, BRICK_DK)
    c.fill_rect(1, 1, 6, 6, BRICK)
    c.fill_rect(9, 1, 6, 6, BRICK_LT)
    c.fill_rect(1, 9, 6, 6, BRICK_LT)
    c.fill_rect(9, 9, 6, 6, BRICK)
    c.outline_rect(0, 0, TILE, TILE, OUTLINE)
    c.set(3, 3, AMBER_DK)
    c.set(12, 11, BRICK_DK)
    return c


def tile_crate() -> Canvas:
    c = Canvas(TILE, TILE, WOOD)
    c.outline_rect(0, 0, TILE, TILE, OUTLINE)
    c.fill_rect(2, 2, 12, 12, WOOD_LT)
    c.outline_rect(2, 2, 12, 12, WOOD_DK)
    for i in range(3, 13):
        c.set(i, i, WOOD_DK)
        c.set(15 - i, i, WOOD_DK)
    return c


def tile_metal() -> Canvas:
    c = Canvas(TILE, TILE, METAL)
    c.outline_rect(0, 0, TILE, TILE, OUTLINE)
    c.fill_rect(1, 1, 14, 14, METAL)
    c.hline(2, 3, 12, METAL_LT)
    c.hline(2, 12, 12, METAL_DK)
    c.set(2, 2, CREAM)
    c.set(13, 2, CREAM)
    c.set(2, 13, CREAM)
    c.set(13, 13, CREAM)
    return c


def tile_police() -> Canvas:
    c = Canvas(TILE, TILE, CONCRETE_DK)
    c.outline_rect(0, 0, TILE, TILE, OUTLINE)
    c.fill_rect(1, 1, 14, 14, METAL)
    c.hline(1, 7, 14, TEAM_BLUE)
    c.hline(1, 8, 14, CREAM)
    c.set(4, 4, WINDOW)
    c.set(11, 4, WINDOW)
    return c


def tile_platform() -> Canvas:
    c = Canvas(TILE, TILE, VOID)
    c.fill_rect(0, 0, TILE, 5, METAL_LT)
    c.hline(0, 0, TILE, CREAM)
    c.hline(0, 4, TILE, OUTLINE)
    c.vline(2, 5, 3, METAL_DK)
    c.vline(13, 5, 3, METAL_DK)
    return c


def tile_hazard() -> Canvas:
    c = Canvas(TILE, TILE, HAZARD_DK)
    for i in range(TILE):
        band = ((i // 4) % 2) == 0
        color = HAZARD if band else HAZARD_DK
        c.vline(i, 0, TILE, color)
    c.outline_rect(0, 0, TILE, TILE, OUTLINE)
    return c


def tile_wall() -> Canvas:
    c = Canvas(TILE, TILE, METAL_DK)
    c.outline_rect(0, 0, TILE, TILE, OUTLINE)
    c.fill_rect(1, 1, 14, 14, SKY)
    c.fill_rect(2, 2, 12, 12, CONCRETE_DK)
    c.set(3, 3, METAL_LT)
    c.set(12, 12, METAL)
    return c


def tile_ladder() -> Canvas:
    c = Canvas(TILE, TILE, VOID)
    c.vline(3, 0, TILE, WOOD_DK)
    c.vline(4, 0, TILE, WOOD)
    c.vline(11, 0, TILE, WOOD)
    c.vline(12, 0, TILE, WOOD_DK)
    for y in (2, 7, 12):
        c.hline(3, y, 10, WOOD_LT)
        c.hline(4, y + 1, 8, WOOD_DK)
    return c


def tileset_arena() -> Canvas:
    sheet = Canvas(128, 16, VOID)
    tiles = [
        tile_concrete(),
        tile_brick(),
        tile_crate(),
        tile_metal(),
        tile_police(),
        tile_platform(),
        tile_hazard(),
        tile_wall(),
    ]
    for i, tile in enumerate(tiles):
        sheet.blit(tile, i * TILE, 0)
    return sheet


def _helmet(c: Canvas, x: int, y: int) -> None:
    c.fill_rect(x, y, 10, 8, SUIT)
    c.outline_rect(x - 1, y - 1, 12, 10, OUTLINE)
    c.fill_rect(x + 1, y + 2, 8, 3, GOGGLE)
    c.hline(x + 1, y + 2, 8, GOGGLE_DK)
    c.set(x + 2, y + 3, WHITE)
    c.set(x + 7, y + 3, GOGGLE_DK)


def _torso(c: Canvas, x: int, y: int, shirt: tuple[int, int, int, int], wide: int = 10) -> None:
    c.fill_rect(x, y, wide, 8, shirt)
    c.outline_rect(x - 1, y - 1, wide + 2, 10, OUTLINE)
    c.set(x + 2, y + 1, CREAM)
    c.set(x + wide - 3, y + 1, CREAM)
    c.set(x + wide // 2 - 1, y + 3, CREAM)
    c.set(x + wide // 2, y + 4, CREAM)
    c.set(x + 2, y + 5, CREAM)
    c.set(x + wide - 3, y + 5, CREAM)
    c.hline(x, y + 7, wide, SUIT)


def _legs(c: Canvas, x: int, y: int, phase: int, walk: bool) -> None:
    off_l = 0
    off_r = 0
    if walk:
        off_l = -1 if phase in (0, 3) else 1
        off_r = 1 if phase in (0, 3) else -1
    c.fill_rect(x + off_l, y, 4, 7, SUIT)
    c.fill_rect(x + 5 + off_r, y, 4, 7, SUIT)
    c.fill_rect(x + off_l, y + 6, 4, 3, AMBER_DK)
    c.fill_rect(x + 5 + off_r, y + 6, 4, 3, AMBER_DK)
    c.hline(x + off_l, y + 8, 4, AMBER)
    c.hline(x + 5 + off_r, y + 8, 4, AMBER)


def _arm(c: Canvas, x: int, y: int, shirt: tuple[int, int, int, int], stretch: int = 0) -> None:
    c.fill_rect(x, y, 3 + stretch, 3, shirt)
    c.set(x + 2 + stretch, y + 1, SKIN)


def fighter_frame(kind: str, phase: int, shirt: tuple[int, int, int, int]) -> Canvas:
    c = Canvas(FRAME, FRAME, VOID)
    bob = 0
    if kind == "walk" and phase in (1, 3):
        bob = 1
    if kind == "idle" and phase == 1:
        bob = 1
    y = 3 + bob
    if kind == "dead":
        c.fill_rect(6, 18, 18, 6, shirt)
        c.outline_rect(5, 17, 20, 8, OUTLINE)
        c.fill_rect(20, 16, 8, 7, SUIT)
        c.fill_rect(22, 18, 5, 3, GOGGLE)
        c.fill_rect(6, 20, 5, 3, AMBER_DK)
        c.set(10, 19, BLOOD)
        c.set(14, 21, BLOOD)
        return c
    if kind == "crouch":
        y = 8
        _helmet(c, 11, y)
        _torso(c, 11, y + 8, shirt, 10)
        c.fill_rect(11, y + 16, 4, 5, SUIT)
        c.fill_rect(17, y + 16, 4, 5, SUIT)
        c.fill_rect(11, y + 19, 4, 3, AMBER_DK)
        c.fill_rect(17, y + 19, 4, 3, AMBER_DK)
        _arm(c, 8, y + 10, shirt)
        _arm(c, 21, y + 10, shirt)
        return c
    _helmet(c, 11, y)
    _torso(c, 11, y + 9, shirt, 10)
    if kind == "jump":
        c.fill_rect(12, y + 18, 3, 6, SUIT)
        c.fill_rect(18, y + 17, 3, 7, SUIT)
        c.fill_rect(12, y + 22, 3, 3, AMBER)
        c.fill_rect(18, y + 22, 3, 3, AMBER)
        _arm(c, 8, y + 8, shirt)
        _arm(c, 21, y + 11, shirt)
        return c
    if kind == "fall":
        c.fill_rect(12, y + 17, 3, 7, SUIT)
        c.fill_rect(18, y + 18, 3, 6, SUIT)
        c.fill_rect(12, y + 22, 3, 3, AMBER)
        c.fill_rect(18, y + 22, 3, 3, AMBER)
        _arm(c, 8, y + 12, shirt)
        _arm(c, 21, y + 8, shirt)
        return c
    if kind == "melee":
        _legs(c, 12, y + 18, phase, False)
        sweep = 6 if phase == 1 else 2
        _arm(c, 8, y + 11, shirt)
        c.fill_rect(20, y + 10, 3 + sweep, 3, shirt)
        c.fill_rect(23 + sweep, y + 10, 3, 3, SKIN)
        if phase == 1:
            c.fill_rect(26, y + 8, 4, 2, CREAM)
        return c
    if kind.startswith("aim"):
        _legs(c, 12, y + 18, 0, False)
        _arm(c, 8, y + 12, shirt)
        if kind == "aim_up":
            c.fill_rect(20, y + 4, 3, 8, shirt)
            c.fill_rect(20, y + 2, 3, 3, METAL_LT)
            c.set(21, y + 1, AMBER)
        elif kind == "aim_down":
            c.fill_rect(20, y + 12, 3, 7, shirt)
            c.fill_rect(20, y + 18, 3, 3, METAL_LT)
        else:
            c.fill_rect(20, y + 11, 8, 3, shirt)
            c.fill_rect(27, y + 11, 4, 3, METAL_LT)
            c.set(30, y + 12, AMBER)
        return c
    if kind == "throw":
        _legs(c, 12, y + 18, 0, False)
        _arm(c, 8, y + 8, shirt)
        c.fill_rect(20, y + 6, 3, 6, shirt)
        c.fill_rect(20, y + 4, 4, 3, METAL)
        c.set(21, y + 5, HAZARD)
        return c
    walk = kind == "walk"
    _legs(c, 12, y + 18, phase, walk)
    _arm(c, 8, y + 11 + (1 if walk and phase in (1, 2) else 0), shirt)
    _arm(c, 21, y + 11 + (1 if walk and phase in (0, 3) else 0), shirt)
    return c


def fighter_sheet(shirt: tuple[int, int, int, int]) -> Canvas:
    sheet = Canvas(FRAME * SHEET_W, FRAME * SHEET_H, VOID)
    row0 = ["idle", "idle", "walk", "walk", "walk", "walk", "jump", "fall"]
    row0_phase = [0, 1, 0, 1, 2, 3, 0, 0]
    row1 = ["crouch", "melee", "melee", "aim_side", "aim_up", "aim_down", "dead", "throw"]
    row1_phase = [0, 0, 1, 0, 0, 0, 0, 0]
    for i, kind in enumerate(row0):
        sheet.blit(fighter_frame(kind, row0_phase[i], shirt), i * FRAME, 0)
    for i, kind in enumerate(row1):
        sheet.blit(fighter_frame(kind, row1_phase[i], shirt), i * FRAME, FRAME)
    return sheet


def item_pistol() -> Canvas:
    c = Canvas(16, 16, VOID)
    c.fill_rect(2, 6, 11, 3, METAL_LT)
    c.fill_rect(3, 9, 3, 4, WOOD)
    c.outline_rect(2, 6, 11, 3, OUTLINE)
    c.set(12, 7, AMBER)
    return c


def item_shotgun() -> Canvas:
    c = Canvas(16, 16, VOID)
    c.fill_rect(1, 6, 13, 3, METAL)
    c.fill_rect(2, 9, 5, 4, WOOD_DK)
    c.outline_rect(1, 6, 13, 3, OUTLINE)
    c.fill_rect(10, 5, 4, 2, METAL_LT)
    return c


def item_uzi() -> Canvas:
    c = Canvas(16, 16, VOID)
    c.fill_rect(3, 5, 9, 4, METAL_LT)
    c.fill_rect(5, 9, 3, 4, SUIT)
    c.fill_rect(10, 6, 4, 2, METAL)
    c.outline_rect(3, 5, 9, 4, OUTLINE)
    c.set(12, 6, AMBER)
    return c


def item_pipe() -> Canvas:
    c = Canvas(16, 16, VOID)
    c.fill_rect(7, 1, 3, 13, METAL_LT)
    c.outline_rect(7, 1, 3, 13, OUTLINE)
    c.fill_rect(6, 12, 5, 3, METAL)
    return c


def item_knife() -> Canvas:
    c = Canvas(16, 16, VOID)
    c.fill_rect(7, 1, 2, 9, CREAM)
    c.outline_rect(6, 1, 4, 9, OUTLINE)
    c.fill_rect(6, 10, 4, 4, WOOD)
    c.set(8, 2, WHITE)
    return c


def item_grenade() -> Canvas:
    c = Canvas(16, 16, VOID)
    c.fill_rect(5, 4, 6, 8, METAL)
    c.outline_rect(5, 4, 6, 8, OUTLINE)
    c.fill_rect(6, 2, 4, 3, HAZARD)
    c.set(7, 1, METAL_LT)
    return c


def item_baton() -> Canvas:
    c = Canvas(16, 16, VOID)
    c.fill_rect(7, 1, 2, 12, SUIT)
    c.outline_rect(6, 1, 4, 12, OUTLINE)
    c.fill_rect(6, 11, 4, 4, METAL)
    c.set(7, 2, METAL_LT)
    return c


def item_rifle() -> Canvas:
    c = Canvas(16, 16, VOID)
    c.fill_rect(0, 6, 15, 3, METAL_DK)
    c.fill_rect(1, 5, 12, 2, METAL)
    c.fill_rect(3, 9, 5, 4, WOOD_DK)
    c.outline_rect(0, 6, 15, 3, OUTLINE)
    c.set(14, 6, AMBER)
    return c


def item_launcher() -> Canvas:
    c = Canvas(16, 16, VOID)
    c.fill_rect(1, 5, 13, 5, METAL)
    c.fill_rect(2, 4, 8, 2, METAL_LT)
    c.fill_rect(3, 10, 5, 4, SUIT)
    c.outline_rect(1, 5, 13, 5, OUTLINE)
    c.fill_rect(12, 6, 3, 3, HAZARD)
    return c


def item_cinder() -> Canvas:
    c = Canvas(16, 16, VOID)
    c.fill_rect(5, 5, 6, 8, BRICK)
    c.outline_rect(5, 5, 6, 8, OUTLINE)
    c.fill_rect(6, 6, 4, 4, AMBER)
    c.fill_rect(6, 3, 4, 3, WOOD)
    c.set(8, 4, AMBER_DK)
    c.set(7, 7, BLOOD)
    return c


def prop_crate() -> Canvas:
    c = Canvas(16, 16, VOID)
    c.blit(tile_crate(), 0, 0)
    return c


def prop_barrel() -> Canvas:
    c = Canvas(16, 20, VOID)
    c.fill_rect(3, 2, 10, 16, METAL)
    c.outline_rect(3, 2, 10, 16, OUTLINE)
    c.hline(3, 6, 10, HAZARD)
    c.hline(3, 7, 10, HAZARD_DK)
    c.hline(3, 8, 10, HAZARD)
    c.fill_rect(4, 3, 8, 2, METAL_LT)
    return c


def prop_glass() -> Canvas:
    """Original vault pane. Chunky frame + cyan glass. Not a Y8 rip."""
    c = Canvas(16, 20, VOID)
    c.fill_rect(1, 1, 14, 18, METAL_DK)
    c.outline_rect(1, 1, 14, 18, OUTLINE)
    c.fill_rect(3, 3, 10, 14, WINDOW)
    c.hline(3, 10, 10, METAL)
    c.vline(8, 3, 14, METAL)
    c.fill_rect(4, 4, 3, 2, CREAM)
    c.set(12, 5, CREAM)
    return c


def vfx_break() -> Canvas:
    """Original shard burst. Not a Y8 rip."""
    c = Canvas(16, 16, VOID)
    c.fill_rect(6, 6, 4, 4, CREAM)
    c.set(4, 5, WINDOW)
    c.set(11, 4, WINDOW)
    c.set(3, 9, AMBER)
    c.set(12, 8, AMBER)
    c.set(7, 3, METAL_LT)
    c.set(8, 12, METAL_LT)
    c.set(5, 11, WOOD_LT)
    c.set(10, 11, WOOD_LT)
    return c


def vfx_explode() -> Canvas:
    """Original blast flash. Not a Y8 rip. Not a VF7 rewrite."""
    c = Canvas(16, 16, VOID)
    c.fill_rect(5, 5, 6, 6, AMBER)
    c.fill_rect(6, 6, 4, 4, CREAM)
    c.set(3, 7, AMBER_DK)
    c.set(12, 8, AMBER_DK)
    c.set(7, 3, WHITE)
    c.set(8, 12, HAZARD)
    c.set(4, 4, HAZARD)
    c.set(11, 11, HAZARD)
    return c


def vfx_fire() -> Canvas:
    """Original ember lick. Not a Y8 rip. Not a VF7 rewrite."""
    c = Canvas(16, 16, VOID)
    c.fill_rect(6, 8, 4, 6, AMBER_DK)
    c.fill_rect(7, 5, 2, 6, AMBER)
    c.set(8, 3, CREAM)
    c.set(5, 9, HAZARD)
    c.set(10, 10, HAZARD)
    c.set(7, 12, BLOOD)
    return c


def bg_city() -> Canvas:
    c = Canvas(256, 128, SKY)
    for x in range(256):
        band = SKY2 if (x // 16) % 2 == 0 else SKY
        c.vline(x, 0, 40, band)
    for i in range(0, 256, 18):
        h = 36 + (i * 7) % 50
        w = 12 + (i * 3) % 10
        x = i
        y = 128 - h
        c.fill_rect(x, y, w, h, CONCRETE_DK)
        c.outline_rect(x, y, w, h, OUTLINE)
        for wy in range(y + 4, y + h - 4, 8):
            for wx in range(x + 2, x + w - 2, 5):
                lit = ((wx + wy + i) % 5) != 0
                c.set(wx, wy, WINDOW if lit else METAL_DK)
    c.fill_rect(0, 120, 256, 8, SKY3)
    return c


def vfx_muzzle() -> Canvas:
    c = Canvas(16, 16, VOID)
    c.fill_rect(4, 6, 8, 4, AMBER)
    c.fill_rect(6, 5, 4, 6, CREAM)
    c.set(8, 7, WHITE)
    return c


def vfx_blood() -> Canvas:
    c = Canvas(16, 16, VOID)
    c.set(7, 7, BLOOD)
    c.set(8, 7, BLOOD)
    c.set(6, 8, BLOOD)
    c.set(9, 8, BLOOD)
    c.set(8, 9, BLOOD)
    c.set(5, 6, BLOOD)
    return c


def vfx_roll() -> Canvas:
    c = Canvas(16, 16, VOID)
    c.fill_rect(3, 10, 10, 3, CREAM)
    c.fill_rect(5, 8, 6, 3, AMBER)
    c.set(2, 11, AMBER_DK)
    c.set(13, 11, AMBER_DK)
    c.set(7, 7, CREAM)
    c.set(8, 7, CREAM)
    return c


def ui_icon_fist() -> Canvas:
    c = Canvas(16, 16, VOID)
    c.fill_rect(4, 5, 8, 7, SKIN)
    c.outline_rect(4, 5, 8, 7, OUTLINE)
    c.fill_rect(5, 3, 6, 3, SKIN_SH)
    return c


def make_sfx(kind: str) -> bytes:
    rate = 22050
    if kind == "sfx_punch":
        n = int(rate * 0.09)
        samples = [
            (0.18 * tone(140.0, i / rate) + 0.10 * noise(i, 3)) * envelope(i, n, 0.01, 0.35)
            for i in range(n)
        ]
    elif kind == "sfx_shoot":
        n = int(rate * 0.12)
        samples = []
        for i in range(n):
            t = i / rate
            bang = 0.16 * tone(220.0 - 80.0 * t, t) + 0.12 * noise(i, 9)
            samples.append(bang * envelope(i, n, 0.005, 0.4))
    elif kind == "sfx_shotgun":
        n = int(rate * 0.18)
        samples = [
            (0.20 * tone(90.0, i / rate) + 0.16 * noise(i, 21)) * envelope(i, n, 0.005, 0.45)
            for i in range(n)
        ]
    elif kind == "sfx_pickup":
        n = int(rate * 0.14)
        samples = []
        for i in range(n):
            t = i / rate
            mix = 0.16 * tone(523.25, t) + 0.12 * tone(659.25, t)
            samples.append(mix * envelope(i, n, 0.02, 0.25))
    elif kind == "sfx_explode":
        n = int(rate * 0.32)
        samples = [
            (0.18 * tone(60.0 + 40.0 * (i / n), i / rate) + 0.14 * noise(i, 44))
            * envelope(i, n, 0.01, 0.5)
            for i in range(n)
        ]
    elif kind == "sfx_jump":
        n = int(rate * 0.10)
        samples = [
            0.14 * tone(320.0 + 180.0 * (i / n), i / rate) * envelope(i, n, 0.01, 0.4)
            for i in range(n)
        ]
    elif kind == "sfx_roll":
        n = int(rate * 0.14)
        samples = []
        for i in range(n):
            t = i / rate
            whoosh = 0.12 * tone(180.0 - 70.0 * t, t) + 0.08 * noise(i, 11)
            samples.append(whoosh * envelope(i, n, 0.01, 0.35))
    elif kind == "sfx_hit":
        n = int(rate * 0.11)
        samples = [
            (0.16 * tone(180.0, i / rate) + 0.08 * noise(i, 7)) * envelope(i, n, 0.01, 0.3)
            for i in range(n)
        ]
    elif kind == "sfx_win":
        n = int(rate * 0.55)
        notes = (392.0, 523.25, 659.25, 784.0)
        samples = []
        for i in range(n):
            t = i / rate
            idx = min(3, int(t / 0.12))
            samples.append(0.18 * tone(notes[idx], t) * envelope(i, n, 0.03, 0.22))
    elif kind == "sfx_lose":
        n = int(rate * 0.42)
        notes = (392.0, 329.63, 246.94)
        samples = []
        for i in range(n):
            t = i / rate
            idx = min(2, int(t / 0.12))
            samples.append(0.16 * tone(notes[idx], t) * envelope(i, n, 0.03, 0.28))
    elif kind == "music_fight":
        n = rate * 4
        samples = []
        motif = (98.0, 123.47, 110.0, 82.41)
        hat = (392.0, 0.0, 329.63, 0.0)
        for i in range(n):
            t = i / rate
            step = int((t * 4.0) % 4)
            drone = 0.05 * tone(55.0, t) + 0.04 * tone(motif[step], t)
            click = 0.03 * tone(hat[step], t) if hat[step] > 0 else 0.0
            kick = 0.06 * tone(70.0, t) if (int(t * 4.0) % 2) == 0 else 0.0
            env = 0.40 + 0.60 * math.sin(math.pi * (i / (n - 1)))
            samples.append((drone + click + kick) * env)
    else:
        raise ValueError(kind)
    peak = max(abs(s) for s in samples)
    if peak < 0.04:
        raise ValueError(f"{kind} is too quiet")
    return write_wav_pcm(samples, rate)


def write_png(path: Path, canvas: Canvas) -> dict[str, str]:
    canvas.assert_palette(path.name)
    data = png_bytes(canvas.w, canvas.h, canvas.rgba())
    write_atomic(path, data)
    return {
        "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "sha256": sha256_bytes(data),
        "w": str(canvas.w),
        "h": str(canvas.h),
    }


def write_wav(path: Path, kind: str) -> dict[str, str]:
    data = make_sfx(kind)
    write_atomic(path, data)
    return {
        "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "sha256": sha256_bytes(data),
        "kind": kind,
    }


def main() -> int:
    art = ASSETS / "art"
    tiles = ASSETS / "tiles"
    ui = ASSETS / "ui"
    vfx = ASSETS / "vfx"
    audio = ASSETS / "audio"
    bg = ASSETS / "bg"
    for folder in (art, tiles, ui, vfx, audio, bg):
        folder.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, str]] = []
    manifest.append(write_png(tiles / "tileset_arena.png", tileset_arena()))
    manifest.append(write_png(tiles / "tile_ladder.png", tile_ladder()))
    shirts = {
        "actor_blue.png": TEAM_BLUE,
        "actor_red.png": TEAM_RED,
        "actor_gold.png": TEAM_GOLD,
        "actor_teal.png": TEAM_TEAL,
    }
    for name, color in shirts.items():
        manifest.append(write_png(art / name, fighter_sheet(color)))
    items = {
        "item_pistol.png": item_pistol(),
        "item_shotgun.png": item_shotgun(),
        "item_uzi.png": item_uzi(),
        "item_pipe.png": item_pipe(),
        "item_knife.png": item_knife(),
        "item_grenade.png": item_grenade(),
        "item_baton.png": item_baton(),
        "item_rifle.png": item_rifle(),
        "item_launcher.png": item_launcher(),
        "item_cinder.png": item_cinder(),
        "prop_crate.png": prop_crate(),
        "prop_barrel.png": prop_barrel(),
        "prop_glass.png": prop_glass(),
    }
    for name, canvas in items.items():
        manifest.append(write_png(art / name, canvas))
    manifest.append(write_png(bg / "bg_city.png", bg_city()))
    manifest.append(write_png(vfx / "vfx_muzzle.png", vfx_muzzle()))
    manifest.append(write_png(vfx / "vfx_blood.png", vfx_blood()))
    manifest.append(write_png(vfx / "vfx_break.png", vfx_break()))
    manifest.append(write_png(vfx / "vfx_explode.png", vfx_explode()))
    manifest.append(write_png(vfx / "vfx_fire.png", vfx_fire()))
    manifest.append(write_png(ui / "ui_icon_fist.png", ui_icon_fist()))

    for kind in (
        "sfx_punch",
        "sfx_shoot",
        "sfx_shotgun",
        "sfx_pickup",
        "sfx_explode",
        "sfx_jump",
        "sfx_hit",
        "sfx_win",
        "sfx_lose",
        "music_fight",
    ):
        manifest.append(write_wav(audio / f"{kind}.wav", kind))

    payload = {
        "tool": TOOL,
        "license": "original procedural",
        "source": "hand-authored pixels/tones in this script; no Y8 rip",
        "files": manifest,
    }
    write_atomic(
        ASSETS / "ASSET_MANIFEST.json",
        (json.dumps(payload, indent=2) + "\n").encode("utf-8"),
    )
    print(f"wrote {len(manifest)} assets under {DOGFOOD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
