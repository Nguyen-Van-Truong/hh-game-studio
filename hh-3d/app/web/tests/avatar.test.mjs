import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const fixture = JSON.parse(
  readFileSync(join(root, "public", "data", "ben-thanh-400m.authored.geojson"), "utf8"),
);

const SPAWN = { lon: 106.69804, lat: 10.77162 };
const SHOP = { lon: 106.6980366, lat: 10.7718712 };
const M_PER_DEG_LAT = 111320;

function metersPerDegLon(lat) {
  return M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);
}

function pointInRing(lon, lat, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yj === yi) {
      continue;
    }
    const intersect = yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi;
    if (intersect) {
      inside = !inside;
    }
  }
  return inside;
}

function buildings() {
  return fixture.features
    .filter((feature) => feature.properties?.kind === "building")
    .map((feature) => feature.geometry.coordinates[0]);
}

function distanceM(a, b) {
  const east = (b.lon - a.lon) * metersPerDegLon((a.lat + b.lat) / 2);
  const north = (b.lat - a.lat) * M_PER_DEG_LAT;
  return Math.hypot(east, north);
}

test("spawn and shop sit on walkable authored ground", () => {
  for (const ring of buildings()) {
    assert.equal(pointInRing(SPAWN.lon, SPAWN.lat, ring), false, "spawn in building");
    assert.equal(pointInRing(SHOP.lon, SHOP.lat, ring), false, "shop in building");
  }
  assert.ok(distanceM(SPAWN, SHOP) > 20, "spawn starts across the street");
  assert.ok(distanceM(SPAWN, SHOP) < 40);
});

test("must stroll to the stall (~4 m) before nearby interact", () => {
  const start = distanceM(SPAWN, SHOP);
  assert.ok(start > 20);
  const afterShort = { lon: SPAWN.lon, lat: SPAWN.lat + 2 / M_PER_DEG_LAT };
  assert.ok(distanceM(afterShort, SHOP) > 4, "1–2 m is still too far for E");
  const acrossStreet = { lon: SPAWN.lon, lat: SPAWN.lat + 8 / M_PER_DEG_LAT };
  assert.ok(distanceM(acrossStreet, SHOP) > 4, "8 m stroll is still across the street");
  const onAsphalt = { lon: SPAWN.lon, lat: SPAWN.lat + 19 / M_PER_DEG_LAT };
  assert.ok(distanceM(onAsphalt, SHOP) > 4, "9 m from persist is still not at the kiosk");
  const atStall = { lon: SPAWN.lon, lat: SPAWN.lat + 25 / M_PER_DEG_LAT };
  assert.ok(distanceM(atStall, SHOP) <= 4, "standing next to the stall marker enters range");
});

test("a point inside Market Hall is blocked", () => {
  const hall = fixture.features.find((feature) => feature.id === "bldg-market-hall");
  const ring = hall.geometry.coordinates[0];
  const midLon = (Math.min(...ring.map((p) => p[0])) + Math.max(...ring.map((p) => p[0]))) / 2;
  const midLat = (Math.min(...ring.map((p) => p[1])) + Math.max(...ring.map((p) => p[1]))) / 2;
  assert.equal(pointInRing(midLon, midLat, ring), true);
});

test("Harbor Walk and seats stay outside building rings", () => {
  const originLat = 10.7725;
  const originLon = 106.698;
  const ll = (east, north) => ({
    lon: originLon + east / metersPerDegLon(originLat),
    lat: originLat + north / M_PER_DEG_LAT,
  });
  const samples = [
    SPAWN,
    SHOP,
    { lon: SPAWN.lon + 7 / metersPerDegLon(SPAWN.lat), lat: SPAWN.lat },
    { lon: SPAWN.lon - 7 / metersPerDegLon(SPAWN.lat), lat: SPAWN.lat },
    ll(6, -180),
    ll(4, -98),
    ll(4, -70),
    ll(4, -40),
    ll(0, 40),
    ll(2, 2),
  ];
  for (const spot of samples) {
    for (const ring of buildings()) {
      assert.equal(pointInRing(spot.lon, spot.lat, ring), false);
    }
  }
});

const AOI = {
  west: 106.6961711,
  south: 10.7707034,
  east: 106.6998289,
  north: 10.7742966,
};
const RADIUS_M = 0.55;
const SPEED_MPS = 1.6;

function ringAabb(ring) {
  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;
  for (const [lon, lat] of ring) {
    west = Math.min(west, lon);
    east = Math.max(east, lon);
    south = Math.min(south, lat);
    north = Math.max(north, lat);
  }
  return { west, south, east, north };
}

function pointInAabb(lon, lat, box) {
  return lon >= box.west && lon <= box.east && lat >= box.south && lat <= box.north;
}

function circleHitsAabb(lon, lat, radiusM, box) {
  const closestLon = Math.min(box.east, Math.max(box.west, lon));
  const closestLat = Math.min(box.north, Math.max(box.south, lat));
  return distanceM({ lon, lat }, { lon: closestLon, lat: closestLat }) < radiusM;
}

function isInsideAoi(lon, lat) {
  const west = AOI.west + 2 / metersPerDegLon(lat);
  const east = AOI.east - 2 / metersPerDegLon(lat);
  const south = AOI.south + 2 / M_PER_DEG_LAT;
  const north = AOI.north - 2 / M_PER_DEG_LAT;
  return lon >= west && lon <= east && lat >= south && lat <= north;
}

function walkable(lon, lat, boxes) {
  if (!isInsideAoi(lon, lat) || boxes.length === 0) {
    return false;
  }
  return !boxes.some((box) => circleHitsAabb(lon, lat, RADIUS_M, box));
}

function closestRingContact(lon, lat, ring) {
  const inside = pointInRing(lon, lat, ring);
  const mPerLon = metersPerDegLon(lat);
  let bestDist = Infinity;
  let bestE = 0;
  let bestN = 0;
  let found = false;
  for (let i = 0; i < ring.length; i += 1) {
    const a = ring[i];
    const b = ring[(i + 1) % ring.length];
    const ae = (a[0] - lon) * mPerLon;
    const an = (a[1] - lat) * M_PER_DEG_LAT;
    const be = (b[0] - lon) * mPerLon;
    const bn = (b[1] - lat) * M_PER_DEG_LAT;
    const ve = be - ae;
    const vn = bn - an;
    const len2 = ve * ve + vn * vn;
    if (len2 < 1e-12) {
      continue;
    }
    const t = Math.max(0, Math.min(1, (-ae * ve - an * vn) / len2));
    const ce = ae + t * ve;
    const cn = an + t * vn;
    const dist = Math.hypot(ce, cn);
    if (dist < bestDist) {
      bestDist = dist;
      bestE = ce;
      bestN = cn;
      found = true;
    }
  }
  if (!found) {
    return null;
  }
  const nx = bestDist > 1e-7 ? (inside ? bestE : -bestE) / bestDist : 0;
  const ny = bestDist > 1e-7 ? (inside ? bestN : -bestN) / bestDist : 1;
  return { distM: bestDist, east: nx, north: ny, inside };
}

function circleHitsRing(lon, lat, radiusM, ring) {
  const hit = closestRingContact(lon, lat, ring);
  return Boolean(hit && (hit.inside || hit.distM < radiusM));
}

function walkableRings(lon, lat, rings) {
  if (!isInsideAoi(lon, lat) || rings.length === 0) {
    return false;
  }
  return !rings.some((ring) => circleHitsRing(lon, lat, RADIUS_M, ring));
}

test("spawn radius stays outside every building AABB", () => {
  const boxes = buildings().map(ringAabb);
  for (const box of boxes) {
    assert.equal(pointInAabb(SPAWN.lon, SPAWN.lat, box), false);
    assert.equal(circleHitsAabb(SPAWN.lon, SPAWN.lat, RADIUS_M, box), false);
    assert.equal(pointInAabb(SHOP.lon, SHOP.lat, box), false);
  }
});

test("chamfered ring sits inside a larger AABB (the old center-point leak)", () => {
  const features = fixture.features.filter(
    (row) => row.properties?.kind === "building" && row.geometry.coordinates[0].length >= 6,
  );
  let found = null;
  for (const feature of features) {
    const ring = feature.geometry.coordinates[0];
    const box = ringAabb(ring);
    const midLat = (box.south + box.north) / 2;
    const dLon = 0.35 / metersPerDegLon(midLat);
    const dLat = 0.35 / M_PER_DEG_LAT;
    const samples = [
      { lon: box.west + dLon, lat: box.south + dLat },
      { lon: box.east - dLon, lat: box.south + dLat },
      { lon: box.east - dLon, lat: box.north - dLat },
      { lon: box.west + dLon, lat: box.north - dLat },
    ];
    for (const cut of samples) {
      if (pointInAabb(cut.lon, cut.lat, box) && !pointInRing(cut.lon, cut.lat, ring)) {
        found = { cut, box };
        break;
      }
    }
    if (found) {
      break;
    }
  }
  assert.ok(found, "expected a chamfer cut inside an AABB");
  assert.equal(circleHitsAabb(found.cut.lon, found.cut.lat, RADIUS_M, found.box), true);
});

test("walking east from spawn is blocked before any building AABB", () => {
  const boxes = buildings().map(ringAabb);
  let lon = SPAWN.lon;
  let lat = SPAWN.lat;
  const dt = 0.05;
  const step = SPEED_MPS * dt;
  for (let i = 0; i < 400; i += 1) {
    const next = {
      lon: lon + step / metersPerDegLon(lat),
      lat,
    };
    if (walkable(next.lon, next.lat, boxes)) {
      lon = next.lon;
      lat = next.lat;
    }
  }
  const eastM = (lon - SPAWN.lon) * metersPerDegLon((SPAWN.lat + lat) / 2);
  assert.ok(eastM > 6, `should walk toward the wall, got ${eastM} m`);
  assert.ok(eastM < 14, `must not pass through the wall, got ${eastM} m`);
  for (const box of boxes) {
    assert.equal(pointInAabb(lon, lat, box), false, "center entered an AABB");
  }
});

test("footprint walk can enter the SW chamfer AABB but not the ring", () => {
  const rings = buildings();
  const steps = fixture.features.find((feature) => feature.id === "bldg-steps-e-00");
  const ring = steps.geometry.coordinates[0];
  const box = ringAabb(ring);
  let lon = SPAWN.lon;
  let lat = SPAWN.lat;
  const dt = 0.05;
  const step = SPEED_MPS * dt;
  for (let i = 0; i < 400; i += 1) {
    const next = { lon: lon + step / metersPerDegLon(lat), lat };
    if (walkableRings(next.lon, next.lat, rings)) {
      lon = next.lon;
      lat = next.lat;
    }
  }
  const eastM = (lon - SPAWN.lon) * metersPerDegLon((SPAWN.lat + lat) / 2);
  const aabbWestM = (box.west - SPAWN.lon) * metersPerDegLon(SPAWN.lat);
  assert.ok(eastM > aabbWestM, `should enter the AABB gap, east=${eastM} aabbWest=${aabbWestM}`);
  assert.ok(eastM > 11.2 && eastM < 13.6, `stop at the chamfer, got ${eastM} m`);
  assert.equal(pointInAabb(lon, lat, box), true, "center should sit in the cut AABB");
  assert.equal(pointInRing(lon, lat, ring), false, "center must not enter the ring");
  assert.equal(circleHitsRing(lon, lat, RADIUS_M, ring), false);
  const extraLon = lon + step / metersPerDegLon(lat);
  assert.equal(walkableRings(extraLon, lat, rings), false, "extra east into the ring is blocked");
});

test("Harbor Walk north stroll stays walkable with body radius", () => {
  const boxes = buildings().map(ringAabb);
  const rings = buildings();
  let lon = SPAWN.lon;
  let lat = SPAWN.lat;
  const dt = 0.05;
  const step = SPEED_MPS * dt;
  for (let i = 0; i < 200; i += 1) {
    const next = { lon, lat: lat + step / M_PER_DEG_LAT };
    assert.equal(walkable(next.lon, next.lat, boxes), true, "street blocked after radius");
    assert.equal(walkableRings(next.lon, next.lat, rings), true, "street blocked by footprint");
    lon = next.lon;
    lat = next.lat;
  }
  const northM = (lat - SPAWN.lat) * M_PER_DEG_LAT;
  assert.ok(northM > 15);
  for (const box of boxes) {
    assert.equal(pointInAabb(lon, lat, box), false);
  }
  for (const ring of rings) {
    assert.equal(pointInRing(lon, lat, ring), false);
  }
});

test("heading east is 90 degrees from north", () => {
  const heading = ((Math.atan2(1, 0) * 180) / Math.PI + 360) % 360;
  assert.equal(heading, 90);
});

test("camera-relative W at bearing 0 is north", () => {
  const bearing = 0;
  const forward = 1;
  const right = 0;
  const east = forward * Math.sin(bearing) + right * Math.cos(bearing);
  const north = forward * Math.cos(bearing) - right * Math.sin(bearing);
  assert.equal(east, 0);
  assert.equal(north, 1);
});

test("Space jump rises then lands on the slab; second jump in air is ignored", () => {
  const JUMP = 6.1;
  const GRAVITY = 17;
  const GROUND = 0;
  let alt = GROUND;
  let vy = 0;
  let airborne = false;
  const jump = () => {
    if (airborne) return;
    vy = JUMP;
    airborne = true;
  };
  const step = (dt) => {
    if (!airborne && alt <= GROUND && vy <= 0) {
      alt = GROUND;
      vy = 0;
      airborne = false;
      return;
    }
    vy -= GRAVITY * dt;
    alt += vy * dt;
    if (alt <= GROUND && vy <= 0) {
      alt = GROUND;
      vy = 0;
      airborne = false;
    }
  };
  jump();
  assert.equal(airborne, true);
  step(0.05);
  const midVy = vy;
  jump();
  assert.equal(vy, midVy, "second jump in air is ignored");
  let peak = alt;
  for (let i = 0; i < 40; i += 1) {
    step(0.02);
    peak = Math.max(peak, alt);
  }
  assert.ok(peak > 0.9, `peak ${peak}`);
  assert.ok(peak < 1.3, `peak ${peak} must not clear a building`);
  assert.equal(airborne, false);
  assert.equal(alt, GROUND);
  assert.equal(vy, 0);
});

test("95 degree hold slides along a west face without lon jitter or clip", () => {
  const box = {
    west: 106.6981463,
    south: 10.7716017,
    east: 106.6982899,
    north: 10.7717837,
  };
  const radius = RADIUS_M;
  const heading = 95;
  const rad = (heading * Math.PI) / 180;
  let lon = box.west - (radius + 0.02) / metersPerDegLon(10.77172);
  let lat = 10.77172;
  const lons = [];
  const lats = [];
  const dt = 0.05;
  const step = SPEED_MPS * dt;
  const aabbNormal = (x, y) => {
    const closestLon = Math.min(box.east, Math.max(box.west, x));
    const closestLat = Math.min(box.north, Math.max(box.south, y));
    const east = (x - closestLon) * metersPerDegLon(y);
    const north = (y - closestLat) * M_PER_DEG_LAT;
    const len = Math.hypot(east, north);
    if (len > 1e-7) {
      return { east: east / len, north: north / len };
    }
    return { east: -1, north: 0 };
  };
  for (let i = 0; i < 80; i += 1) {
    const east = Math.sin(rad) * step;
    const north = Math.cos(rad) * step;
    const next = { lon: lon + east / metersPerDegLon(lat), lat: lat + north / M_PER_DEG_LAT };
    if (walkable(next.lon, next.lat, [box])) {
      lon = next.lon;
      lat = next.lat;
    } else {
      const n = aabbNormal(lon, lat);
      const into = east * -n.east + north * -n.north;
      let se = east;
      let sn = north;
      if (into > 0) {
        se += n.east * into;
        sn += n.north * into;
      }
      const along = { lon: lon + se / metersPerDegLon(lat), lat: lat + sn / M_PER_DEG_LAT };
      if (walkable(along.lon, along.lat, [box])) {
        lon = along.lon;
        lat = along.lat;
      }
    }
    lons.push(lon);
    lats.push(lat);
    assert.equal(pointInAabb(lon, lat, box), false, "center entered AABB");
    assert.equal(circleHitsAabb(lon, lat, radius, box), false);
  }
  const lonSpan = Math.max(...lons) - Math.min(...lons);
  const south = (lats[0] - lats[lats.length - 1]) * M_PER_DEG_LAT;
  assert.ok(lonSpan * metersPerDegLon(lat) < 0.04, `lon jitter ${lonSpan}`);
  assert.ok(south > 0.35, `should slide south, got ${south} m`);
  assert.ok(south < 8, `must not teleport, got ${south} m`);
});

test("95 degree hold slides along the Steps East footprint face", () => {
  const steps = fixture.features.find((feature) => feature.id === "bldg-steps-e-00");
  const ring = steps.geometry.coordinates[0];
  const box = ringAabb(ring);
  const heading = 95;
  const rad = (heading * Math.PI) / 180;
  let lon = box.west - (RADIUS_M + 0.04) / metersPerDegLon(10.77174);
  let lat = 10.77174;
  const lons = [];
  const lats = [];
  const dt = 0.05;
  const step = SPEED_MPS * dt;
  for (let i = 0; i < 80; i += 1) {
    const east = Math.sin(rad) * step;
    const north = Math.cos(rad) * step;
    const next = { lon: lon + east / metersPerDegLon(lat), lat: lat + north / M_PER_DEG_LAT };
    if (walkableRings(next.lon, next.lat, [ring])) {
      lon = next.lon;
      lat = next.lat;
    } else {
      const contact = closestRingContact(lon, lat, ring);
      const n = contact ?? { east: -1, north: 0 };
      const into = east * -n.east + north * -n.north;
      let se = east;
      let sn = north;
      if (into > 0) {
        se += n.east * into;
        sn += n.north * into;
      }
      const along = { lon: lon + se / metersPerDegLon(lat), lat: lat + sn / M_PER_DEG_LAT };
      if (walkableRings(along.lon, along.lat, [ring])) {
        lon = along.lon;
        lat = along.lat;
      }
    }
    lons.push(lon);
    lats.push(lat);
    assert.equal(pointInRing(lon, lat, ring), false, "center entered ring");
    assert.equal(circleHitsRing(lon, lat, RADIUS_M, ring), false);
  }
  const lonSpan = (Math.max(...lons) - Math.min(...lons)) * metersPerDegLon(lat);
  const south = (lats[0] - lats[lats.length - 1]) * M_PER_DEG_LAT;
  assert.ok(lonSpan < 0.08, `lon jitter ${lonSpan}`);
  assert.ok(south > 0.35, `should slide south, got ${south} m`);
  assert.ok(south < 8, `must not teleport, got ${south} m`);
});

test("sprint is faster than walk; release returns walk; look axis unchanged", () => {
  const walk = 2.55;
  const sprint = 4.35;
  assert.ok(sprint > walk);
  const dt = 3;
  const walkM = walk * dt;
  const sprintM = sprint * dt;
  assert.ok(sprintM > walkM * 1.4);
  assert.ok(sprintM < walkM * 2);
  const boxes = buildings().map(ringAabb);
  const stepWalk = (from, seconds, speed) => {
    let lon = from.lon;
    let lat = from.lat;
    const tick = 0.05;
    const n = Math.round(seconds / tick);
    for (let i = 0; i < n; i += 1) {
      const next = { lon, lat: lat + (speed * tick) / M_PER_DEG_LAT };
      if (walkable(next.lon, next.lat, boxes)) {
        lon = next.lon;
        lat = next.lat;
      }
    }
    return (lat - from.lat) * M_PER_DEG_LAT;
  };
  const northWalk = stepWalk(SPAWN, 3, walk);
  const northSprint = stepWalk(SPAWN, 3, sprint);
  assert.ok(northWalk > 7 && northWalk < 8, `walk ${northWalk}`);
  assert.ok(northSprint > northWalk && northSprint < 14, `sprint ${northSprint}`);
  assert.ok(northSprint > northWalk);
  const eastRings = buildings();
  let lon = SPAWN.lon;
  let lat = SPAWN.lat;
  const tick = 0.05;
  for (let i = 0; i < 400; i += 1) {
    const next = { lon: lon + (sprint * tick) / metersPerDegLon(lat), lat };
    if (walkableRings(next.lon, next.lat, eastRings)) {
      lon = next.lon;
      lat = next.lat;
    }
  }
  const eastM = (lon - SPAWN.lon) * metersPerDegLon((SPAWN.lat + lat) / 2);
  const steps = fixture.features.find((feature) => feature.id === "bldg-steps-e-00");
  assert.ok(eastM > 6, `sprint still reaches the wall ${eastM}`);
  assert.ok(eastM < 14, `sprint must not clip the wall ${eastM}`);
  assert.equal(pointInRing(lon, lat, steps.geometry.coordinates[0]), false);
  const bearing = 25.2 * (Math.PI / 180);
  const eastLook = Math.sin(bearing);
  const northLook = Math.cos(bearing);
  assert.ok(eastLook > 0.4 && northLook > 0.85);
});

test("look delta turns yaw; WASD along look is camera-relative", () => {
  const sens = 0.14;
  const yawSign = -1;
  let yaw = 0;
  yaw = ((yaw + -160 * sens * yawSign) % 360 + 360) % 360;
  assert.ok(yaw > 20 && yaw < 26);
  const rad = (yaw * Math.PI) / 180;
  const east = Math.sin(rad);
  const north = Math.cos(rad);
  assert.ok(east > 0.35);
  assert.ok(north > 0.85);
});

test("authored 400 m keep-in stops at the fixture edge; spawn and lantern stay free", () => {
  const rings = buildings();
  const southLimit = AOI.south + 2 / M_PER_DEG_LAT;
  const northLimit = AOI.north - 2 / M_PER_DEG_LAT;
  const westLimit = AOI.west + 2 / metersPerDegLon(SPAWN.lat);
  const eastLimit = AOI.east - 2 / metersPerDegLon(SPAWN.lat);
  assert.equal(isInsideAoi(SPAWN.lon, SPAWN.lat), true);
  assert.equal(isInsideAoi(SHOP.lon, SHOP.lat), true);
  assert.equal(walkableRings(SPAWN.lon, SPAWN.lat, rings), true);
  assert.equal(walkableRings(SHOP.lon, SHOP.lat, rings), true);
  assert.equal(isInsideAoi(SPAWN.lon, southLimit - 1 / M_PER_DEG_LAT), false);
  assert.equal(isInsideAoi(SPAWN.lon, northLimit + 1 / M_PER_DEG_LAT), false);
  assert.equal(walkableRings(SPAWN.lon, southLimit - 3 / M_PER_DEG_LAT, rings), false);

  let lon = SPAWN.lon;
  let lat = SPAWN.lat;
  const dt = 0.05;
  const step = SPEED_MPS * dt;
  for (let i = 0; i < 4000; i += 1) {
    const next = { lon, lat: lat - step / M_PER_DEG_LAT };
    if (walkableRings(next.lon, next.lat, rings)) {
      lon = next.lon;
      lat = next.lat;
    }
  }
  const southM = (SPAWN.lat - lat) * M_PER_DEG_LAT;
  assert.ok(southM > 80, `should reach the south frame, got ${southM} m`);
  assert.ok(lat >= southLimit - 1e-9, `must not walk off the GeoJSON extent ${lat}`);
  assert.equal(walkableRings(lon, lat - 3 / M_PER_DEG_LAT, rings), false);
  const padM = (lat - southLimit) * M_PER_DEG_LAT;
  assert.ok(padM <= 1.3, `should sit on the inner face, pad ${padM}`);

  const slideLon0 = westLimit + 4 / metersPerDegLon(southLimit + 0.00001);
  let sLon = slideLon0;
  let sLat = southLimit + 0.15 / M_PER_DEG_LAT;
  for (let i = 0; i < 80; i += 1) {
    const trySouth = { lon: sLon, lat: sLat - step / M_PER_DEG_LAT };
    const tryWest = { lon: sLon - step / metersPerDegLon(sLat), lat: sLat };
    if (walkableRings(trySouth.lon, trySouth.lat, rings)) {
      sLon = trySouth.lon;
      sLat = trySouth.lat;
    } else if (walkableRings(tryWest.lon, tryWest.lat, rings)) {
      sLon = tryWest.lon;
      sLat = tryWest.lat;
    }
  }
  const westSlide = (slideLon0 - sLon) * metersPerDegLon(sLat);
  assert.ok(westSlide > 0.3, `diagonal into the south bound should slide west ${westSlide}`);
  assert.ok(sLat >= southLimit - 1e-9);
  assert.ok(sLon >= westLimit - 1e-9);
  assert.ok(sLon <= eastLimit + 1e-9);
});

test("A/D strafe does not turn heading; A from north walks east (screen-left)", () => {
  const start = { lon: SPAWN.lon, lat: SPAWN.lat, heading: 0, pose: "idle" };
  const rad = 0;
  const right = -1;
  const east = Math.sin(rad) * 0 - right * Math.cos(rad);
  const north = Math.cos(rad) * 0 + right * Math.sin(rad);
  assert.ok(east > 0.99, "demo flipped right: A facing north is east / screen-left");
  assert.ok(Math.abs(north) < 1e-9);
  assert.equal(start.heading, 0);

  const facedEast = { ...start, heading: 90 };
  const eastRad = (facedEast.heading * Math.PI) / 180;
  const aEast = Math.sin(eastRad) * 0 - right * Math.cos(eastRad);
  const aNorth = Math.cos(eastRad) * 0 + right * Math.sin(eastRad);
  assert.ok(Math.abs(aEast) < 1e-9);
  assert.ok(aNorth < -0.99, "A facing east is south / screen-left");
});

test("mouse look uses demo yaw sign; A/D strafe; walk pace; this-PC copy", () => {
  const look = readFileSync(join(root, "src", "avatar", "look.ts"), "utf8");
  const walk = readFileSync(join(root, "src", "avatar", "walk.ts"), "utf8");
  const avatar = readFileSync(join(root, "src", "avatar", "useAvatar.ts"), "utf8");
  const help = readFileSync(join(root, "src", "avatar", "StreetHelp.tsx"), "utf8");
  const play = readFileSync(join(root, "src", "play", "PlayView.tsx"), "utf8");
  const modes = readFileSync(join(root, "src", "modes", "modes.ts"), "utf8");
  assert.match(look, /LOOK_YAW_SIGN = -1/);
  assert.match(walk, /TURN_YAW_SIGN = -1/);
  assert.match(walk, /east: forward \* sinB - right \* cosB/);
  assert.match(walk, /north: forward \* cosB \+ right \* sinB/);
  assert.match(avatar, /applyLookMove\(faced, forward, keySide/);
  assert.equal(avatar.includes("applyFacingMove("), false);
  assert.match(help, /A\/D strafe/);
  assert.equal(help.includes("A/D turn"), false);
  assert.match(walk, /WALK_SPEED_MPS = 2\.55/);
  assert.match(walk, /SPRINT_SPEED_MPS = 4\.35/);
  assert.match(play, /BasicShadowMap/);
  assert.match(play, /PlayLoopGate/);
  assert.match(modes, /Máy này · 4175/);
  assert.equal(modes.includes('return "Đang kết nối"'), false);
});
