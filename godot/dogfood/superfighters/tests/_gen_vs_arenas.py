#!/usr/bin/env python3
"""VF5-WP6: author two original VS arenas as layered JSON.

Does not tick the 29-8 plan. Does not fetch Y8. Does not remint
rooftops/storage/police/hazardous geometry.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "maps" / "arenas"

JUMP_DX = 10
JUMP_DY = 4
MIN_PLATFORM = 2

MAPS = {
    "lantern": {
        "display_name": "Lantern Cut",
        "theme": "asphalt",
        "rows": [
            "................................................",
            "...w........................................w...",
            "..========..............................========",
            "....H....................................H......",
            "....H....................................H......",
            "....H....................................H......",
            ".P..H....................................H.2....",
            "####L....................................H######",
            "....H...............1....................H......",
            "....H============================........H......",
            "....H....................................H......",
            "....H....................................H......",
            "....H.................................ccwH......",
            "....H................========...................",
            "....H...........................................",
            "##########.....            ...........##########",
            "................................................",
            "................................................",
        ],
    },
    "gauge": {
        "display_name": "Gauge Deck",
        "theme": "range",
        "rows": [
            "........................................................................",
            "......w......................................................w..........",
            "....========..............................................========......",
            "....H........................................................H..........",
            "....H=======..........................................=======H..........",
            "....H........................................................H..........",
            ".P..H.............1........................................2.H..........",
            "####H.....cccc................H.....cccc.....................H.#########",
            "....H.........................H..............................H..........",
            "....H.........................H..............................H..........",
            "....H.........................H...........w..................H..........",
            "....H.........................H..............................H..........",
            "##################################################################..####",
            "........................................................................",
        ],
    },
}


def convert(map_id: str, spec: dict) -> dict:
    rows = spec["rows"]
    height = len(rows)
    width = len(rows[0])
    solid: list[list[int]] = []
    one_way: list[list[int]] = []
    ladder: list[list[int]] = []
    hazard: list[list[int]] = []
    prop: list[list[int]] = []
    spawn: list[list[int]] = []
    pickup: list[list[int]] = []
    for y, row in enumerate(rows):
        if len(row) != width:
            raise SystemExit(f"{map_id} row {y} width {len(row)} != {width}")
        for x, ch in enumerate(row):
            if ch == "#":
                solid.append([x, y])
            elif ch == "=":
                one_way.append([x, y])
            elif ch == "H":
                ladder.append([x, y])
            elif ch == "L":
                ladder.append([x, y])
                one_way.append([x, y])
            elif ch == "c":
                prop.append([x, y])
            elif ch == "b":
                hazard.append([x, y])
            elif ch == "P":
                spawn.append([x, y, 0])
            elif ch == "1":
                spawn.append([x, y, 1])
            elif ch == "2":
                spawn.append([x, y, 2])
            elif ch == "w":
                pickup.append([x, y])
            elif ch not in (".", " "):
                raise SystemExit(f"{map_id} unknown char {ch!r} at {x},{y}")
    return {
        "schema": "vf.maps.layers.v1",
        "schema_version": 1,
        "title": "Vault Fighters",
        "id": map_id,
        "display_name": spec["display_name"],
        "width": width,
        "height": height,
        "tile": 16,
        "theme": spec["theme"],
        "y8_parity_claimed": False,
        "original_exact_numbers_claimed": False,
        "values_are_tuning": True,
        "ascii_source_retired": True,
        "live_c_b_tiles": True,
        "layers": {
            "solid": _sort_cells(solid, False),
            "one_way": _sort_cells(one_way, False),
            "ladder": _sort_cells(ladder, False),
            "hazard": _sort_cells(hazard, False),
            "prop": _sort_cells(prop, False),
            "spawn": _sort_cells(spawn, True),
            "pickup": _sort_cells(pickup, False),
        },
    }


def _sort_cells(cells: list[list[int]], with_slot: bool) -> list[list[int]]:
    if with_slot:
        return sorted(cells, key=lambda c: (c[1], c[0], c[2] if len(c) > 2 else 0))
    return sorted(cells, key=lambda c: (c[1], c[0]))


def _layer_set(doc: dict, name: str) -> set[tuple[int, int]]:
    out: set[tuple[int, int]] = set()
    for cell in doc["layers"][name]:
        out.add((int(cell[0]), int(cell[1])))
    return out


def _is_blocker(sets: dict[str, set[tuple[int, int]]], x: int, y: int) -> bool:
    key = (x, y)
    return key in sets["solid"] or key in sets["one_way"] or key in sets["prop"] or key in sets["hazard"]


def _is_walk_support(sets: dict[str, set[tuple[int, int]]], x: int, y: int) -> bool:
    return _is_blocker(sets, x, y)


def _in_bounds(doc: dict, x: int, y: int) -> bool:
    return 0 <= x < int(doc["width"]) and 0 <= y < int(doc["height"])


def _is_walkable(doc: dict, sets: dict[str, set[tuple[int, int]]], x: int, y: int) -> bool:
    if not _in_bounds(doc, x, y):
        return False
    if _is_blocker(sets, x, y) and (x, y) not in sets["one_way"]:
        return False
    if (x, y) in sets["ladder"]:
        return True
    return _is_walk_support(sets, x, y + 1)


def _neighbors(doc: dict, sets: dict[str, set[tuple[int, int]]], x: int, y: int) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()

    def add(nx: int, ny: int) -> None:
        if not _is_walkable(doc, sets, nx, ny):
            return
        key = (nx, ny)
        if key in seen:
            return
        seen.add(key)
        out.append(key)

    add(x - 1, y)
    add(x + 1, y)
    if (
        (x, y) in sets["ladder"]
        or (x, y + 1) in sets["ladder"]
        or (x, y - 1) in sets["ladder"]
    ):
        add(x, y - 1)
        add(x, y + 1)
    fy = y + 1
    while fy < int(doc["height"]):
        if _is_walkable(doc, sets, x, fy):
            add(x, fy)
            break
        if _is_blocker(sets, x, fy) and (x, fy) not in sets["one_way"]:
            break
        fy += 1
    for oy in range(-JUMP_DY, 2):
        for ox in range(-JUMP_DX, JUMP_DX + 1):
            if ox != 0 or oy != 0:
                add(x + ox, y + oy)
    return out


def _platforms(doc: dict, sets: dict[str, set[tuple[int, int]]]) -> list[list[tuple[int, int]]]:
    width = int(doc["width"])
    height = int(doc["height"])
    seen: set[tuple[int, int]] = set()
    out: list[list[tuple[int, int]]] = []
    for y in range(height):
        x = 0
        while x < width:
            if _is_walk_support(sets, x, y) and _is_walkable(doc, sets, x, y - 1) and (x, y) not in seen:
                run: list[tuple[int, int]] = []
                cx = x
                while (
                    cx < width
                    and _is_walk_support(sets, cx, y)
                    and _is_walkable(doc, sets, cx, y - 1)
                ):
                    seen.add((cx, y))
                    run.append((cx, y))
                    cx += 1
                if len(run) >= MIN_PLATFORM:
                    out.append(run)
            x += 1
    return out


def _spawn_walkable(doc: dict, sets: dict[str, set[tuple[int, int]]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    height = int(doc["height"])
    for cell in doc["layers"]["spawn"]:
        sx, sy = int(cell[0]), int(cell[1])
        fy = sy
        while fy < height:
            if _is_walkable(doc, sets, sx, fy):
                out.append((sx, fy))
                break
            fy += 1
    return out


def validate_graph(doc: dict) -> list[str]:
    sets = {
        "solid": _layer_set(doc, "solid"),
        "one_way": _layer_set(doc, "one_way"),
        "ladder": _layer_set(doc, "ladder"),
        "prop": _layer_set(doc, "prop"),
        "hazard": _layer_set(doc, "hazard"),
    }
    errors: list[str] = []
    start = _spawn_walkable(doc, sets)
    if not start:
        return [f"{doc['id']} graph has no reachable spawn walkable"]
    reached: set[tuple[int, int]] = set()
    queue = deque()
    for cell in start:
        if cell not in reached:
            reached.add(cell)
            queue.append(cell)
    while queue:
        cx, cy = queue.popleft()
        for nxt in _neighbors(doc, sets, cx, cy):
            if nxt not in reached:
                reached.add(nxt)
                queue.append(nxt)
    for run in _platforms(doc, sets):
        ok = False
        for x, y in run:
            if (x, y - 1) in reached and _is_walkable(doc, sets, x, y - 1):
                ok = True
                break
            if (x, y) in reached:
                ok = True
                break
        if not ok:
            errors.append(f"{doc['id']} platform at {run[0][0]},{run[0][1]} unreachable")
    if not doc["layers"]["spawn"]:
        errors.append(f"{doc['id']} has no spawn marks")
    if not doc["layers"]["pickup"]:
        errors.append(f"{doc['id']} has no weapon cells")
    if not doc["layers"]["ladder"]:
        errors.append(f"{doc['id']} missing ladders")
    if not doc["layers"]["one_way"]:
        errors.append(f"{doc['id']} missing one-way platforms")
    px = int(doc["width"]) * 16
    py = int(doc["height"]) * 16
    if px > 1280 or py > 720:
        errors.append(f"{doc['id']} pixel size {px}x{py} exceeds camera")
    return errors


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    failed = 0
    for map_id, spec in MAPS.items():
        doc = convert(map_id, spec)
        errors = validate_graph(doc)
        path = OUT / f"{map_id}.json"
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} w={doc['width']} h={doc['height']}")
        if errors:
            failed += 1
            for err in errors:
                print(f"  GRAPH {err}")
        else:
            print("  graph ok")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
