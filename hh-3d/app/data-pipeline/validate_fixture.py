#!/usr/bin/env python3
"""Validate the authored 400 m fixture. Local only. Exit 1 on mismatch."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

CENTER_LAT = 10.7725
CENTER_LON = 106.6980
HALF_M = 200.0
PAD_M = 2.0
M_PER_LAT = 111320.0
M_PER_LON = 111320.0 * math.cos(math.radians(CENTER_LAT))

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data-pipeline" / "fixtures" / "ben-thanh-400m.authored.geojson"
PUBLIC = ROOT / "web" / "public" / "data" / "ben-thanh-400m.authored.geojson"
MANIFEST = ROOT / "manifests" / "world-manifest.json"
PUBLIC_MANIFEST = ROOT / "web" / "public" / "data" / "world-manifest.json"


def fail(msg: str) -> None:
    print(f"FAIL {msg}", file=sys.stderr)
    raise SystemExit(1)


def coords_of(geom: dict) -> list[list[float]]:
    t = geom["type"]
    c = geom["coordinates"]
    if t == "Point":
        return [c]
    if t == "LineString":
        return c
    if t == "Polygon":
        out: list[list[float]] = []
        for ring in c:
            out.extend(ring)
        return out
    fail(f"unsupported geometry {t}")
    return []


def meters_from_center(lon: float, lat: float) -> tuple[float, float]:
    return ((lon - CENTER_LON) * M_PER_LON, (lat - CENTER_LAT) * M_PER_LAT)


def _point_in_ring(lon: float, lat: float, ring: list) -> bool:
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if yi != yj and (yi > lat) != (yj > lat) and lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def main() -> None:
    for path in (FIXTURE, PUBLIC, MANIFEST, PUBLIC_MANIFEST):
        if not path.is_file():
            fail(f"missing {path}")

    raw = FIXTURE.read_bytes()
    if raw != PUBLIC.read_bytes():
        fail("public GeoJSON does not match pipeline fixture")
    if MANIFEST.read_bytes() != PUBLIC_MANIFEST.read_bytes():
        fail("public manifest does not match manifests/world-manifest.json")

    data = json.loads(raw.decode("utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    artifact_hash = hashlib.sha256(raw).hexdigest()
    if artifact_hash != manifest.get("artifact_hash"):
        fail("artifact_hash mismatch")
    if data.get("type") != "FeatureCollection":
        fail("not a FeatureCollection")

    limit = HALF_M + PAD_M
    for feat in data["features"]:
        props = feat.get("properties") or {}
        if props.get("authored_or_source") != "authored":
            fail(f"{feat.get('id')} not authored")
        if props.get("accuracy_class") != "authored":
            fail(f"{feat.get('id')} accuracy_class")
        if "accessed_at" in props:
            fail(f"{feat.get('id')} must not emit accessed_at as a currentness twin")
        blob = json.dumps(feat, ensure_ascii=False).lower()
        for banned in ("superfighters", "super fighter", "vault fighters", "y8"):
            if banned in blob:
                fail(f"forbidden chrome string {banned}")
        for lon, lat in coords_of(feat["geometry"]):
            east_m, north_m = meters_from_center(lon, lat)
            if abs(east_m) > limit or abs(north_m) > limit:
                fail(f"{feat.get('id')} outside 400 m frame")

    places = [f for f in data["features"] if (f.get("properties") or {}).get("kind") == "place"]
    if len(places) < 3:
        fail("need at least 3 place points")

    buildings = [f for f in data["features"] if (f.get("properties") or {}).get("kind") == "building"]
    if len(buildings) < 24:
        fail(f"need a walkable block, not five boxes ({len(buildings)})")
    if len(buildings) > 120:
        fail(f"still a small authored block, not a city ({len(buildings)})")

    rings = []
    for feat in buildings:
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Polygon":
            fail(f"{feat.get('id')} building is not a Polygon")
        ring = geom["coordinates"][0]
        if len(ring) < 4:
            fail(f"{feat.get('id')} ring too short")
        rings.append((feat.get("id"), ring))

    keep_clear = [
        (106.69804, 10.77162, "spawn"),
        (106.6980366, 10.7718712, "shop"),
        (106.69804 + 7 / M_PER_LON, 10.77162, "seat-b"),
        (106.69804 - 7 / M_PER_LON, 10.77162, "seat-c"),
        (CENTER_LON + 4 / M_PER_LON, CENTER_LAT - 40 / M_PER_LAT, "harbor-mid"),
        (CENTER_LON, CENTER_LAT, "crossing"),
    ]
    for lon, lat, label in keep_clear:
        for fid, ring in rings:
            if _point_in_ring(lon, lat, ring):
                fail(f"{label} is inside {fid}")

    print("PASS authored 400 m fixture")
    print(f"artifact_hash={artifact_hash}")
    print(f"features={len(data['features'])} buildings={len(buildings)} places={len(places)}")


if __name__ == "__main__":
    main()
