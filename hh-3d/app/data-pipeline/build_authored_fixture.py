#!/usr/bin/env python3
"""Build the authored 400 m Bến Thành vicinity fixture. No network. No OSM fetch."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

CENTER_LAT = 10.7725
CENTER_LON = 106.6980
HALF_M = 200.0
M_PER_LAT = 111320.0
M_PER_LON = 111320.0 * math.cos(math.radians(CENTER_LAT))

ACQUIRED_AT = "2026-09-03T00:00:00+07:00"
GENERATED_AT = "2026-09-03T13:50:00+07:00"
PUBLISHED_AT = "2026-09-03T13:50:00+07:00"
SOURCE_RELEASED_AT = "2026-09-03T00:00:00+07:00"
FRESH_UNTIL = "2026-12-03T00:00:00+07:00"
STALE_AFTER = "2027-03-03T00:00:00+07:00"

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
PUBLIC_DIR = ROOT / "web" / "public" / "data"
MANIFEST_DIR = ROOT / "manifests"
QA_DIR = ROOT / "data-qa"


def ll(east_m: float, north_m: float) -> list[float]:
    return [
        round(CENTER_LON + east_m / M_PER_LON, 7),
        round(CENTER_LAT + north_m / M_PER_LAT, 7),
    ]


def ring(min_e: float, min_n: float, max_e: float, max_n: float) -> list[list[float]]:
    return [
        ll(min_e, min_n),
        ll(max_e, min_n),
        ll(max_e, max_n),
        ll(min_e, max_n),
        ll(min_e, min_n),
    ]


def footprint(min_e: float, min_n: float, max_e: float, max_n: float, style: int) -> list[list[float]]:
    """Authored parcel, slightly irregular so Play extrudes a ring, not an AABB box."""
    cut = min(4.2, (max_e - min_e) * 0.2, (max_n - min_n) * 0.2)
    if cut < 1.2:
        return ring(min_e, min_n, max_e, max_n)
    kind = style % 3
    if kind == 0:
        pts = [
            ll(min_e, min_n),
            ll(max_e, min_n),
            ll(max_e, max_n - cut),
            ll(max_e - cut, max_n),
            ll(min_e, max_n),
        ]
    elif kind == 1:
        pts = [
            ll(min_e + cut, min_n),
            ll(max_e, min_n),
            ll(max_e, max_n),
            ll(min_e, max_n),
            ll(min_e, min_n + cut),
        ]
    else:
        inset = cut * 0.55
        pts = [
            ll(min_e + inset, min_n),
            ll(max_e, min_n),
            ll(max_e - inset, max_n),
            ll(min_e, max_n),
        ]
    return pts + [pts[0]]


def building(fid: str, coords: list[list[float]], name: str, height: int) -> dict:
    return feature(
        fid,
        {"type": "Polygon", "coordinates": [coords]},
        currentness(
            kind="building",
            name=name,
            display_name=name,
            height_m=height,
            height_confidence="estimated",
        ),
    )


def fill_block(
    prefix: str,
    title: str,
    min_e: float,
    min_n: float,
    max_e: float,
    max_n: float,
    cols: int,
    rows: int,
    h_lo: int,
    h_hi: int,
    keep_first: str | None = None,
) -> list[dict]:
    gap = 4.6
    width = max_e - min_e
    height = max_n - min_n
    cell_w = (width - gap * (cols - 1)) / cols
    cell_h = (height - gap * (rows - 1)) / rows
    if cell_w < 8.2 or cell_h < 8.2:
        return []
    out: list[dict] = []
    n = 0
    for row in range(rows):
        for col in range(cols):
            x0 = min_e + col * (cell_w + gap)
            y0 = min_n + row * (cell_h + gap)
            n += 1
            fid = keep_first if n == 1 and keep_first else f"{prefix}-{row}{col}"
            span = max(1, h_hi - h_lo + 1)
            roof = h_lo + ((n * 3 + row + col) % span)
            if keep_first and n == 1 and fid == "bldg-market-hall":
                roof = 16
            label = title if n == 1 and keep_first else f"{title} {n}"
            out.append(
                building(fid, footprint(x0, y0, x0 + cell_w, y0 + cell_h, n + row), label, roof)
            )
    return out


def authored_buildings() -> list[dict]:
    """Subdivide the original five footprints; keep Harbor Walk / Tram Approach clear."""
    blocks = [
        # Market Hall remnant, NE of the crossing (was one 95 x 80 m box).
        ("bldg-hall", "Market Hall", 18, 16, 50, 52, 2, 2, 12, 18, "bldg-market-hall"),
        ("bldg-hall-w", "Hall West", -45, 16, -14, 52, 2, 2, 10, 16, None),
        ("bldg-hall-se", "Hall South", 18, -25, 50, -16, 2, 1, 8, 12, None),
        ("bldg-hall-sw", "Hall Court", -45, -25, -14, -16, 2, 1, 8, 11, None),
        # West Block carved by Tram Approach.
        ("bldg-west", "West Block", -170, -50, -95, -16, 3, 2, 11, 15, "bldg-west-block"),
        ("bldg-west-n", "West Loft", -170, 16, -95, 45, 3, 1, 12, 15, None),
        # East Arcade carved by Tram Approach.
        ("bldg-east", "East Arcade", 95, -90, 170, -16, 3, 3, 9, 14, "bldg-east-arcade"),
        ("bldg-east-n", "Arcade North", 95, 16, 170, 25, 3, 1, 8, 11, None),
        # North Stall Row, still east of Clock Garden.
        ("bldg-north", "North Stall Row", 22, 72, 94, 148, 3, 3, 7, 10, "bldg-north-stall"),
        # South Shed split so Harbor Walk stays open.
        ("bldg-south", "South Shed", -35, -175, -14, -108, 1, 3, 6, 8, "bldg-south-shed"),
        ("bldg-south-e", "South Annex", 16, -175, 40, -108, 1, 3, 6, 8, None),
        # Empty stretch between shed and hall, along the existing Harbor Walk.
        ("bldg-steps-w", "Steps West", -48, -100, -14, -30, 2, 3, 8, 13, None),
        ("bldg-steps-e", "Steps East", 16, -100, 52, -30, 2, 3, 8, 13, None),
    ]
    out: list[dict] = []
    for prefix, title, min_e, min_n, max_e, max_n, cols, rows, h_lo, h_hi, keep in blocks:
        out.extend(
            fill_block(prefix, title, min_e, min_n, max_e, max_n, cols, rows, h_lo, h_hi, keep)
        )
    return out


def currentness(**extra: object) -> dict[str, object]:
    base: dict[str, object] = {
        "source_released_at": SOURCE_RELEASED_AT,
        "acquired_at": ACQUIRED_AT,
        "generated_at": GENERATED_AT,
        "published_at": PUBLISHED_AT,
        "fresh_until": FRESH_UNTIL,
        "stale_after": STALE_AFTER,
        "accuracy_class": "authored",
        "geometry_confidence": "low",
        "authored_or_source": "authored",
        "honesty": "authored approximation; not a live survey; not 1:1",
    }
    base.update(extra)
    return base


def feature(fid: str, geom: dict, props: dict) -> dict:
    return {
        "type": "Feature",
        "id": fid,
        "geometry": geom,
        "properties": {"id": fid, **props},
    }


def build_collection() -> dict:
    west, south = ll(-HALF_M, -HALF_M)
    east, north = ll(HALF_M, HALF_M)
    features = [
        feature(
            "aoi-boundary",
            {"type": "Polygon", "coordinates": [ring(-HALF_M, -HALF_M, HALF_M, HALF_M)]},
            currentness(
                kind="aoi",
                name="Bến Thành vicinity (authored frame)",
                display_name="Authored 400 m frame",
            ),
        ),
        feature(
            "park-clock-garden",
            {"type": "Polygon", "coordinates": [ring(-90, 40, -10, 170)]},
            currentness(
                kind="park",
                name="Clock Garden",
                display_name="Clock Garden",
                height_m=None,
                height_confidence="unknown",
            ),
        ),
        *authored_buildings(),
        feature(
            "street-tram-approach",
            {
                "type": "LineString",
                "coordinates": [ll(-190, -5), ll(-40, 0), ll(40, 0), ll(190, 8)],
            },
            currentness(kind="street", name="Tram Approach", display_name="Tram Approach"),
        ),
        feature(
            "street-harbor-walk",
            {
                "type": "LineString",
                "coordinates": [ll(6, -190), ll(4, -40), ll(0, 40), ll(-8, 190)],
            },
            currentness(kind="street", name="Harbor Walk", display_name="Harbor Walk"),
        ),
        feature(
            "place-market-hall",
            {"type": "Point", "coordinates": ll(2, 14)},
            currentness(
                kind="place",
                name="Market Hall",
                display_name="Market Hall",
                summary="Authored stand-in near the Bến Thành vicinity center. Not the real market footprint.",
                height_m=16,
                height_confidence="estimated",
            ),
        ),
        feature(
            "place-clock-garden",
            {"type": "Point", "coordinates": ll(-50, 105)},
            currentness(
                kind="place",
                name="Clock Garden",
                display_name="Clock Garden",
                summary="Authored park block north of the hall. Shape is invented for the local proof.",
                height_m=None,
                height_confidence="unknown",
            ),
        ),
        feature(
            "place-market-steps",
            {"type": "Point", "coordinates": ll(4, -70)},
            currentness(
                kind="place",
                name="Market Steps",
                display_name="Market Steps",
                summary="Authored gathering point south of the hall. Not a surveyed entrance.",
                height_m=None,
                height_confidence="unknown",
            ),
        ),
        feature(
            "place-roundabout-green",
            {"type": "Point", "coordinates": ll(2, 2)},
            currentness(
                kind="place",
                name="Roundabout Green",
                display_name="Roundabout Green",
                summary="Authored crossing of Tram Approach and Harbor Walk.",
                height_m=None,
                height_confidence="unknown",
            ),
        ),
    ]
    return {
        "type": "FeatureCollection",
        "name": "hh-world-ben-thanh-400m-authored",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "bbox": [west, south, east, north],
        "hh_world": {
            "display_name": "HH World",
            "aoi_label": "Bến Thành vicinity, Ho Chi Minh City",
            "center": [CENTER_LON, CENTER_LAT],
            "extent_m": [400, 400],
            "authored_or_source": "authored",
            "honesty": "Authored approximation. Not OSM. Not a live map. Not 1:1.",
        },
        "features": features,
    }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    collection = build_collection()
    encoded = json.dumps(collection, ensure_ascii=False, indent=2) + "\n"
    raw = encoded.encode("utf-8")
    artifact_hash = sha256_bytes(raw)
    source_hash = sha256_bytes(
        json.dumps(collection["hh_world"], ensure_ascii=False, sort_keys=True).encode("utf-8")
    )

    west, south, east, north = collection["bbox"]
    manifest = {
        "schema": "hh-world-manifest/v0",
        "display_name": "HH World",
        "aoi_label": "Bến Thành vicinity, Ho Chi Minh City",
        "center": {"lon": CENTER_LON, "lat": CENTER_LAT},
        "extent_m": {"east_west": 400, "north_south": 400},
        "bbox": {"west": west, "south": south, "east": east, "north": north},
        "renderer": "maplibre-gl local style + local GeoJSON",
        "networking": "OFF",
        "fetch_performed": False,
        "authored_or_source": "authored",
        "accuracy_class": "authored",
        "geometry_confidence": "low",
        "height_confidence": "estimated",
        "source_released_at": SOURCE_RELEASED_AT,
        "acquired_at": ACQUIRED_AT,
        "generated_at": GENERATED_AT,
        "published_at": PUBLISHED_AT,
        "fresh_until": FRESH_UNTIL,
        "stale_after": STALE_AFTER,
        "source_hash": source_hash,
        "artifact_hash": artifact_hash,
        "artifact_path": "data-pipeline/fixtures/ben-thanh-400m.authored.geojson",
        "published_path": "web/public/data/ben-thanh-400m.authored.geojson",
        "honesty": [
            "Authored approximation of a 400 m frame around 10.7725, 106.6980.",
            "Building rings are authored parcels inside that frame, not OSM/Overture.",
            "Not photogrammetry, not a digital twin, not realtime, not 1:1.",
            "Gameplay-facing place names are fictionalized.",
            "Map data as of 2026-09-03 (authored fixture).",
        ],
        "forbidden_claims": ["1:1", "realtime", "digital twin", "GTA-like", "Y8 parity"],
    }

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)

    fixture_path = FIXTURE_DIR / "ben-thanh-400m.authored.geojson"
    public_path = PUBLIC_DIR / "ben-thanh-400m.authored.geojson"
    manifest_path = MANIFEST_DIR / "world-manifest.json"
    public_manifest = PUBLIC_DIR / "world-manifest.json"

    fixture_path.write_bytes(raw)
    public_path.write_bytes(raw)
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    manifest_path.write_bytes(manifest_bytes)
    public_manifest.write_bytes(manifest_bytes)

    qa = {
        "ok": True,
        "artifact_hash": artifact_hash,
        "source_hash": source_hash,
        "feature_count": len(collection["features"]),
        "bbox": collection["bbox"],
        "network": "OFF",
        "fetch": False,
    }
    (QA_DIR / "last-validate.json").write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {fixture_path}")
    print(f"artifact_hash={artifact_hash}")


if __name__ == "__main__":
    main()
