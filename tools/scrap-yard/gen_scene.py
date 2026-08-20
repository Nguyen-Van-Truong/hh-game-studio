#!/usr/bin/env python3
"""Generate games/scrap-yard/scenes/main.gscene.json.

Arena is a 40 x 22 industrial interior (original layout, not a licensed map).
Only dyadic-safe floats are emitted so gs-player pack accepts the scene.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "games" / "scrap-yard" / "scenes" / "main.gscene.json"

ARENA_W = 40
ARENA_H = 22
CAM_X = 20.0
CAM_Y = 11.0
ORTHO_H = 24.0

# Catwalk tops = cell_y + 1. Floor top is 1.0.
TIER_LOW_Y = 5
TIER_MID_Y = 10
TIER_HIGH_Y = 15
TOWER_A_Y = 3
TOWER_B_Y = 8
TOWER_C_Y = 13
DAIS_Y = 2

VELA_ID = 20
ROOK_ID = 21
VELA_X = 6.0
ROOK_X = 34.0
SPAWN_Y = 2.25

def fmt_float(value: float) -> str:
    """Emit only dyadic eighths so f32 → ryu → parse round-trips."""
    f = float(value)
    if f == 0.0:
        return "0.0"
    eighths = f * 8.0
    n = int(round(eighths))
    if abs(eighths - n) > 1e-9:
        raise ValueError(f"unsafe float {value!r} — use a dyadic like 0.25/0.5/0.75/1.5")
    if n % 8 == 0:
        return f"{n // 8}.0"
    if n % 4 == 0:
        return f"{n // 4 / 2:.1f}"
    if n % 2 == 0:
        return f"{n // 2 / 4:.2f}"
    return f"{n / 8:.3f}"


def eid(n: int) -> str:
    return f"e_{n:06d}"


def asset(n: int) -> dict:
    return {"$asset": f"a_{n:06d}"}


def dumps(value, indent: int = 0) -> str:
    pad = "  " * indent
    inner = "  " * (indent + 1)
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return fmt_float(value)
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, list):
        if not value:
            return "[]"
        parts = [dumps(item, indent + 1) for item in value]
        body = ",\n".join(f"{inner}{part}" for part in parts)
        return f"[\n{body}\n{pad}]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        keys = sorted(value.keys())
        parts = [f"{inner}{dumps(key)}: {dumps(value[key], indent + 1)}" for key in keys]
        body = ",\n".join(parts)
        return f"{{\n{body}\n{pad}}}"
    raise TypeError(type(value))


def transform(x, y, sx=1.0, sy=1.0, z=0, rot=0.0) -> dict:
    return {
        "rot": float(rot),
        "sx": float(sx),
        "sy": float(sy),
        "x": float(x),
        "y": float(y),
        "z_index": int(z),
    }


def sprite(asset_id: int, color, pivot=None, flip_x=False, flip_y=False) -> dict:
    if pivot is None:
        pivot = [0.5, 0.0]
    return {
        "asset": asset(asset_id),
        "color": [float(c) for c in color],
        "flip_x": flip_x,
        "flip_y": flip_y,
        "pivot": [float(pivot[0]), float(pivot[1])],
    }


def rigid(kind: str, gravity=1.0, fixed=True) -> dict:
    return {
        "ccd": False,
        "fixed_rotation": fixed,
        "gravity_scale": float(gravity),
        "kind": kind,
        "linear_damping": 0.0,
    }


def collider(w, h, sensor=False, ox=0.0, oy=0.0, friction=0.5) -> dict:
    return {
        "friction": float(friction),
        "is_sensor": sensor,
        "layer": 1,
        "mask": 4294967295,
        "offset": [float(ox), float(oy)],
        "restitution": 0.0,
        "shape": {"box": {"h": float(h), "w": float(w)}},
    }


def tilemap(tileset: int, cells: list[list[int]], layer_name: str, solid=True) -> dict:
    return {
        "cell_size": [1.0, 1.0],
        "layers": [
            {
                "cells": cells,
                "name": layer_name,
                "solid": solid,
            }
        ],
        "tileset": asset(tileset),
    }


def rle_from_cells(cells: set[tuple[int, int]]) -> list[list[int]]:
    by_y: dict[int, list[int]] = {}
    for x, y in cells:
        by_y.setdefault(y, []).append(x)
    runs: list[list[int]] = []
    for y in sorted(by_y):
        xs = sorted(set(by_y[y]))
        i = 0
        while i < len(xs):
            start = xs[i]
            length = 1
            while i + length < len(xs) and xs[i + length] == start + length:
                length += 1
            runs.append([start, y, length, 1])
            i += length
    return runs


class Scene:
    def __init__(self) -> None:
        self.entities: dict[int, dict] = {}
        self._next = 1
        self.reserved = {VELA_ID, ROOK_ID}

    def take(self, want: int | None = None) -> int:
        if want is not None:
            if want in self.entities:
                raise ValueError(f"duplicate entity {want}")
            self.entities[want] = {}
            return want
        while self._next in self.entities or self._next in self.reserved:
            self._next += 1
        n = self._next
        self.entities[n] = {}
        self._next += 1
        return n

    def add(self, n: int, name: str, components: dict, tags=None, parent=None) -> int:
        if n not in self.entities:
            self.take(n)
        comps = {"Name": {"value": name}}
        comps.update(components)
        if tags:
            comps["Tags"] = {"values": list(tags)}
        self.entities[n] = {
            "id": eid(n),
            "order": 0,
            "parent": parent,
            "components": comps,
        }
        return n

    def to_root(self) -> dict:
        items = []
        for i, n in enumerate(sorted(self.entities)):
            ent = self.entities[n]
            ent["order"] = i
            items.append(ent)
        return {
            "entities": items,
            "mode": "2d",
            "schema_version": 1,
        }


WHITE = [1.0, 1.0, 1.0, 1.0]
VELA_TINT = [0.25, 0.75, 1.0, 1.0]
ROOK_TINT = [1.0, 0.5, 0.25, 1.0]
HP_BACK = [0.25, 0.25, 0.25, 1.0]
HP_VELA = [0.25, 1.0, 0.5, 1.0]
HP_ROOK = [1.0, 0.5, 0.25, 1.0]


def build() -> Scene:
    s = Scene()

    s.add(
        s.take(),
        "camera",
        {
            "Camera2D": {"active": True, "ortho_height": ORTHO_H},
            "Transform2D": transform(CAM_X, CAM_Y),
        },
    )

    floor_cells: set[tuple[int, int]] = set()
    for x in range(ARENA_W):
        floor_cells.add((x, 0))
    for x in range(17, 23):
        floor_cells.add((x, 1))
        floor_cells.add((x, DAIS_Y))
    s.add(
        s.take(),
        "yard_floor",
        {
            "Tilemap": tilemap(1, rle_from_cells(floor_cells), "deck", True),
            "Transform2D": transform(0.0, 0.0),
        },
    )

    wall_cells: set[tuple[int, int]] = set()
    for y in range(1, ARENA_H - 1):
        wall_cells.add((0, y))
        wall_cells.add((ARENA_W - 1, y))
    for x in range(ARENA_W):
        wall_cells.add((x, ARENA_H - 1))
    s.add(
        s.take(),
        "yard_walls",
        {
            "Tilemap": tilemap(2, rle_from_cells(wall_cells), "hull", True),
            "Transform2D": transform(0.0, 0.0),
        },
    )

    plat_cells: set[tuple[int, int]] = set()

    def run(x: int, y: int, length: int) -> None:
        for i in range(length):
            plat_cells.add((x + i, y))

    # Three catwalk tiers, mirrored in spirit but not pixel-identical.
    run(5, TIER_LOW_Y, 10)
    run(18, TIER_LOW_Y, 3)
    run(26, TIER_LOW_Y, 9)
    run(6, TIER_MID_Y, 9)
    run(16, TIER_MID_Y, 5)
    run(24, TIER_MID_Y, 10)
    run(5, TIER_HIGH_Y, 8)
    run(15, TIER_HIGH_Y, 8)
    run(26, TIER_HIGH_Y, 8)
    # Side-tower steps (climb by jumping; ladders are decoration only).
    run(1, TOWER_A_Y, 3)
    run(1, TOWER_B_Y, 4)
    run(1, TOWER_C_Y, 3)
    run(36, TOWER_A_Y, 3)
    run(35, TOWER_B_Y, 4)
    run(36, TOWER_C_Y, 3)

    s.add(
        s.take(),
        "yard_plats",
        {
            "Tilemap": tilemap(3, rle_from_cells(plat_cells), "catwalks", True),
            "Transform2D": transform(0.0, 0.0),
        },
    )

    s.add(
        s.take(),
        "yard_director",
        {
            "Script": {"file": "scripts/yard.luau", "props": {"camera": "e_000001"}},
            "Transform2D": transform(-8.0, -8.0),
        },
    )

    # Background machinery grid (2 x 2 world, no collider).
    s._next = 100
    for gy in range(1, 20, 2):
        for gx in range(1, 40, 2):
            s.add(
                s.take(),
                f"bg_{gx}_{gy}",
                {
                    "Sprite": sprite(10, WHITE),
                    "Transform2D": transform(float(gx), float(gy), 2.0, 2.0, -8),
                },
            )

    for i, lx in enumerate((4.0, 10.0, 16.0, 20.0, 24.0, 30.0, 36.0)):
        s.add(
            s.take(),
            f"lamp_{i}",
            {
                "Sprite": sprite(11, WHITE),
                "Transform2D": transform(lx, 20.0, 1.0, 1.0, -2),
            },
        )

    for side, x in (("w", 2.5), ("e", 37.5)):
        for y in range(1, 17):
            s.add(
                s.take(),
                f"ladder_{side}_{y}",
                {
                    "Sprite": sprite(14, WHITE),
                    "Transform2D": transform(x, float(y), 1.0, 1.0, 0),
                },
            )

    crates = [
        (3.5, 1.0),
        (9.5, 1.0),
        (24.5, 1.0),
        (36.5, 1.0),
        (7.5, 6.0),
        (29.5, 6.0),
        (11.5, 11.0),
        (27.5, 11.0),
    ]
    for i, (x, y) in enumerate(crates):
        s.add(
            s.take(),
            f"crate_{i}",
            {
                "Collider2D": collider(1.0, 1.0, False, 0.0, 0.5, 0.5),
                "RigidBody2D": rigid("static", 0.0),
                "Sprite": sprite(12, WHITE),
                "Transform2D": transform(x, y, 1.0, 1.0, 1),
            },
            tags=["cover", "crate"],
        )

    barrels = [
        (22.5, 1.0),
        (20.0, 3.0),
        (32.5, 6.0),
        (8.5, 11.0),
        (18.5, 16.0),
    ]
    for i, (x, y) in enumerate(barrels):
        s.add(
            s.take(),
            f"barrel_{i}",
            {
                "Collider2D": collider(1.0, 1.0, False, 0.0, 0.5, 0.5),
                "RigidBody2D": rigid("static", 0.0),
                "Sprite": sprite(13, WHITE),
                "Transform2D": transform(x, y, 1.0, 1.0, 1),
            },
            tags=["cover", "barrel"],
        )

    hud = {
        "vela_back": s.take(40),
        "vela_fill": s.take(41),
        "vela_tag": s.take(42),
        "rook_back": s.take(43),
        "rook_fill": s.take(44),
        "rook_tag": s.take(45),
    }

    s.add(
        VELA_ID,
        "vela",
        {
            "Collider2D": collider(0.75, 2.0, False, 0.0, 1.0, 0.0),
            "RigidBody2D": rigid("dynamic", 1.0, True),
            "Script": {
                "file": "scripts/fighter.luau",
                "props": {
                    "ai": True,
                    "bar_back": eid(hud["vela_back"]),
                    "bar_fill": eid(hud["vela_fill"]),
                    "body_sx": 1.5,
                    "body_sy": 2.0,
                    "slot": "p1",
                    "tag": eid(hud["vela_tag"]),
                },
            },
            "Sprite": sprite(20, WHITE),
            "Transform2D": transform(VELA_X, SPAWN_Y, 1.5, 2.0, 3),
        },
        tags=["fighter", "fighter_p1"],
    )
    s.add(
        ROOK_ID,
        "rook",
        {
            "Collider2D": collider(1.25, 2.0, False, 0.0, 1.0, 0.0),
            "RigidBody2D": rigid("dynamic", 1.0, True),
            "Script": {
                "file": "scripts/fighter.luau",
                "props": {
                    "ai": False,
                    "bar_back": eid(hud["rook_back"]),
                    "bar_fill": eid(hud["rook_fill"]),
                    "body_sx": 1.5,
                    "body_sy": 2.0,
                    "slot": "p2",
                    "tag": eid(hud["rook_tag"]),
                },
            },
            "Sprite": sprite(30, WHITE, flip_x=True),
            "Transform2D": transform(ROOK_X, SPAWN_Y, 1.5, 2.0, 3),
        },
        tags=["fighter", "fighter_p2"],
    )

    def hp_quad(n: int, name: str, x: float, asset_id: int, color, z: int) -> None:
        s.add(
            n,
            name,
            {
                "Sprite": sprite(asset_id, color),
                "Transform2D": transform(x, 4.0, 1.5, 0.25, z),
            },
        )

    hp_quad(hud["vela_back"], "hp_vela_back", VELA_X, 50, HP_BACK, 5)
    hp_quad(hud["vela_fill"], "hp_vela_fill", VELA_X, 51, HP_VELA, 6)
    hp_quad(hud["rook_back"], "hp_rook_back", ROOK_X, 50, HP_BACK, 5)
    hp_quad(hud["rook_fill"], "hp_rook_fill", ROOK_X, 51, HP_ROOK, 6)
    s.add(
        hud["vela_tag"],
        "tag_vela",
        {
            "Sprite": sprite(51, VELA_TINT),
            "Transform2D": transform(VELA_X, 4.5, 0.25, 0.25, 6),
        },
    )
    s.add(
        hud["rook_tag"],
        "tag_rook",
        {
            "Sprite": sprite(51, ROOK_TINT),
            "Transform2D": transform(ROOK_X, 4.5, 0.25, 0.25, 6),
        },
    )

    pickups = [
        (50, "pipe", 40, "pipe", 12.5, 1.25),
        (51, "blaster", 41, "blaster", 30.5, 6.25),
        (52, "bomb", 42, "bomb", 13.5, 11.25),
        (53, "clock", 43, "clock", 19.0, 16.25),
    ]
    for n, name, art, kind, x, y in pickups:
        s.add(
            s.take(n),
            name,
            {
                "Collider2D": collider(1.0, 1.0, True, 0.0, 0.5, 0.0),
                "Sprite": sprite(art, WHITE),
                "Transform2D": transform(x, y, 1.0, 1.0, 2),
            },
            tags=["pickup", f"pickup_{kind}"],
        )

    for i in range(10):
        s.add(
            s.take(60 + i),
            f"bolt_{i}",
            {
                "Collider2D": collider(0.5, 0.5, True, 0.0, 0.0, 0.0),
                "Sprite": sprite(44, WHITE, pivot=[0.5, 0.5]),
                "Transform2D": transform(-6.0, -6.0, 0.5, 0.5, 4),
            },
            tags=["proj_idle", "proj_bullet"],
        )
    for i in range(6):
        s.add(
            s.take(70 + i),
            f"grenade_{i}",
            {
                "Collider2D": collider(1.0, 1.0, True, 0.0, 0.0, 0.0),
                "Sprite": sprite(42, WHITE, pivot=[0.5, 0.5]),
                "Transform2D": transform(-6.0, -8.0, 1.0, 1.0, 4),
            },
            tags=["proj_idle", "proj_grenade"],
        )

    return s


def main() -> int:
    scene = build()
    root = scene.to_root()
    text = dumps(root) + "\n"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    ids = sorted(scene.entities)
    print(f"wrote {OUT.relative_to(ROOT).as_posix()}")
    print(f"entities={len(ids)} next_entity={ids[-1] + 1}")
    print(
        f"arena={ARENA_W}x{ARENA_H} camera=({CAM_X},{CAM_Y}) ortho_height={ORTHO_H}"
    )
    print(
        "tiers: floor_top=1.0 low=6.0 mid=11.0 high=16.0 "
        "towers=4.0/9.0/14.0 dais=3.0"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
